"""Decision providers: the interface, a deterministic fixture, and the optional
provider boundary a future service adapter would implement.

The provider interface is deliberately provider-neutral:

``answer(request)``
    receive one batch request (the projected state plus the independent
    questions) and return one answer per question with the provider's own
    identity, model version, request id and usage where available.

``capabilities()``
    declare, in the generic vocabulary, what the provider can actually do:
    which primitives, whether batching is supported and to what bound, whether
    probabilities are real, whether model versions are concrete, the state
    limit and the usage metadata. A question is never sent to a provider that
    does not declare it can answer it, and capability declarations are
    registered in the engine's capability registry rather than special-cased
    anywhere in the engine.

Three providers ship, plus one mapping adapter:

``DeterministicProvider``
    scripted answers, scripted confidence, scripted probability distributions and
    predictable failure. It exists for offline verification and never pretends to
    be a live model.
``UnavailableProvider``
    the honest default: nothing is configured, so the answer is ``unavailable``
    and the caller falls back or escalates.
``OptionalProviderAdapter``
    a contract-only boundary for a licensed or specialised service (for example a
    Jev-style decision service). It is disabled unless an interface object is
    injected, it never installs a dependency, never reads credentials and never
    makes a network call itself.
``JevShapedAdapter``
    a concrete mapping from a Jev-shaped capability vocabulary (``BINARY``,
    ``CHOICE``, ``SCALE``, ``MULTISELECT``, ``PARALLEL_BATCH``, ``PROBABILITIES``,
    ``VERSIONED_MODEL``) onto the generic interface. It is exercised with offline
    fixtures; live use is recorded as ``NOT_EXECUTED``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from ..contracts import DECISION_PRIMITIVES, ContractError

DEFAULT_CAPABILITIES: dict[str, Any] = {
    "primitives": (),
    "batching": False,
    "parallel_questions": 1,
    "max_questions": 1,
    "max_options": 0,
    "probabilities": False,
    "confidence_kinds": ("NONE",),
    "explicit_model_versions": False,
    "state_limit_chars": 0,
    "usage_metadata": False,
    "capability_names": (),
}
"""The conservative capability shape. Nothing is claimed unless declared."""

JEV_SHAPED_CAPABILITIES = {
    "BINARY": {"primitives": ("BinaryDecision",)},
    "CHOICE": {"primitives": ("ChoiceDecision",)},
    "SCALE": {"primitives": ("ScaleDecision",)},
    "MULTISELECT": {"primitives": ("MultiSelectDecision",)},
    "PARALLEL_BATCH": {"batching": True},
    "PROBABILITIES": {"probabilities": True},
    "VERSIONED_MODEL": {"explicit_model_versions": True},
}
"""Jev-shaped capability labels and what each one means generically.

The mapping lives here so no Jev-specific name is special-cased anywhere else
in the engine.
"""

MOVING_ALIASES = ("latest", "stable", "default", "current", "edge", "preview")
"""Model labels that are aliases, not concrete versions. An alias can move under
a cached decision or a recorded model identity, so it is never accepted as one.
"""


def concrete_model_version(value: str) -> bool:
    label = str(value or "").strip()
    if not label:
        return False
    lowered = label.lower()
    return not any(lowered == alias or lowered.endswith(f"-{alias}") for alias in MOVING_ALIASES)


class DecisionProviderError(RuntimeError):
    """The provider failed. A failure is recorded, never converted into an answer."""


class DecisionProvider:
    """The provider interface. Implementations declare what they are."""

    id = "abstract-provider"
    provider = "abstract"
    model = ""
    model_version = ""

    def available(self) -> tuple[bool, str]:
        return False, "no decision provider is configured"

    def capabilities(self) -> dict:
        return dict(DEFAULT_CAPABILITIES)

    def confidence_kinds(self) -> tuple[str, ...]:
        """Which confidence kinds this provider can honestly report."""
        return ("NONE",)

    def describe(self) -> dict:
        available, reason = self.available()
        return {
            "id": self.id,
            "provider": self.provider,
            "model": self.model,
            "model_version": self.model_version,
            "available": bool(available),
            "reason": str(reason),
            "confidence_kinds": self.confidence_kinds(),
            "capabilities": self.capabilities(),
        }

    def answer(self, request: Mapping) -> Mapping:
        raise DecisionProviderError(f"provider {self.id!r} implements nothing")


@dataclass
class DeterministicProvider(DecisionProvider):
    """A scripted provider for deterministic, offline verification.

    The script maps a question id to ``{"answer": ..., "confidence": ...,
    "confidence_kind": ..., "distribution": {...}}``. ``fail`` names questions
    whose call raises :class:`DecisionProviderError`; ``unavailable`` makes the
    whole provider unavailable. A question with no scripted answer is returned as
    a failed answer for that question only, so partial scripts stay honest.
    """

    script: Mapping[str, Mapping] = field(default_factory=dict)
    id: str = "deterministic"
    provider: str = "deterministic-fixture"
    model: str = "scripted-answers"
    model_version: str = "1"
    fail: tuple[str, ...] = ()
    unavailable_reason: str = ""
    request_id: str = "req_fixture_00000000"
    usage: Mapping[str, Any] = field(default_factory=dict)
    calls: list[dict] = field(default_factory=list)

    def available(self) -> tuple[bool, str]:
        if self.unavailable_reason:
            return False, self.unavailable_reason
        return True, ""

    def confidence_kinds(self) -> tuple[str, ...]:
        return ("NONE", "SELF_REPORTED_CONFIDENCE", "PROVIDER_PROBABILITY", "CALIBRATED_PROBABILITY")

    def capabilities(self) -> dict:
        return {
            **DEFAULT_CAPABILITIES,
            "primitives": tuple(DECISION_PRIMITIVES),
            "batching": True,
            "parallel_questions": 32,
            "max_questions": 32,
            "max_options": 64,
            "probabilities": True,
            "confidence_kinds": self.confidence_kinds(),
            "explicit_model_versions": True,
            "state_limit_chars": 16_000,
            "usage_metadata": bool(self.usage),
        }

    def answer(self, request: Mapping) -> Mapping:
        available, reason = self.available()
        if not available:
            raise DecisionProviderError(f"provider unavailable: {reason}")
        questions = [dict(item) for item in (request.get("questions") or []) if isinstance(item, Mapping)]
        self.calls.append({"questions": [str(item.get("question_id", "")) for item in questions]})
        answers: dict[str, dict] = {}
        failures: list[str] = []
        for question in questions:
            question_id = str(question.get("question_id", ""))
            if question_id in self.fail:
                failures.append(question_id)
                continue
            scripted = self.script.get(question_id)
            if scripted is None:
                failures.append(question_id)
                continue
            answers[question_id] = dict(scripted)
        if failures and len(failures) == len(questions):
            raise DecisionProviderError(
                "the deterministic provider has no scripted answer for: " + ", ".join(failures)
            )
        return {
            "answers": answers,
            "failed_questions": failures,
            "provider": self.provider,
            "model": self.model,
            "model_version": self.model_version,
            "request_id": self.request_id,
            "usage": dict(self.usage),
            "raw": {"scripted": True},
        }


@dataclass
class UnavailableProvider(DecisionProvider):
    """The default provider: nothing is configured, and it says so."""

    id: str = "unavailable"
    provider: str = "none"
    model: str = ""
    model_version: str = ""
    reason: str = (
        "no decision provider is configured; bounded decision intelligence is optional and "
        "the deterministic fallback applies"
    )

    def available(self) -> tuple[bool, str]:
        return False, self.reason

    def capabilities(self) -> dict:
        return {**DEFAULT_CAPABILITIES, "capability_names": ()}

    def answer(self, request: Mapping) -> Mapping:
        raise DecisionProviderError(self.reason)


class OptionalProviderAdapter(DecisionProvider):
    """A contract-only boundary for a licensed or specialised decision service.

    It is enabled only by an explicitly injected interface object. A concrete
    adapter for a service such as Jev must supply, at minimum:

    * ``describe()`` returning the concrete provider, model and *model version*
      (a moving alias such as ``jev-latest`` must be resolved to a concrete
      version before any answer is accepted);
    * ``capabilities()`` (or a Jev-shaped capability list) naming what the
      service can answer;
    * ``answer(request)`` returning one answer per question with the raw value;
    * probability or confidence metadata *with its kind* (``CALIBRATED_PROBABILITY``
      or ``PROVIDER_PROBABILITY``), never a bare number;
    * a provider request id and the raw provider model identity;
    * usage figures where the provider exposes them, and ``None``/absent fields
      where it does not.

    This class never installs a dependency, never reads credentials, never opens
    a socket and never calls anything unless an interface object was supplied by
    the operator.
    """

    id = "optional-provider"

    def __init__(self, *, name: str = "optional", interface=None, version: str = "") -> None:
        self.provider = str(name)
        self.model = str(version)
        self.model_version = str(version)
        self.interface = interface

    def available(self) -> tuple[bool, str]:
        if self.interface is None:
            return False, (
                f"no licensed interface for provider {self.provider!r} is configured; "
                "Ariadne never installs one or calls it implicitly"
            )
        return True, ""

    def capabilities(self) -> dict:
        declared = {}
        if self.interface is not None and hasattr(self.interface, "capabilities"):
            try:
                declared = dict(self.interface.capabilities() or {})
            except Exception:
                declared = {}
        merged = {**DEFAULT_CAPABILITIES, **declared}
        merged["confidence_kinds"] = tuple(merged.get("confidence_kinds") or ("NONE",))
        merged["primitives"] = tuple(merged.get("primitives") or ())
        return merged

    def describe(self) -> dict:
        value = super().describe()
        value["requirements"] = self.requirements()
        value["live_use"] = "NOT_EXECUTED"
        return value

    def requirements(self) -> list[str]:
        return [
            "a concrete model version (a moving alias is not acceptable as a recorded model identity)",
            "declared capabilities in the generic vocabulary (which primitives, batching, probabilities)",
            "answers inside the declared option set for each question",
            "probability/confidence metadata with its confidence kind preserved",
            "a provider request id and the raw provider model identity",
            "usage figures where the provider exposes them; absent values stay unknown",
        ]

    def answer(self, request: Mapping) -> Mapping:
        available, reason = self.available()
        if not available:
            raise DecisionProviderError(reason)
        if not hasattr(self.interface, "answer"):
            raise DecisionProviderError(
                f"the configured interface for {self.provider!r} does not implement answer()"
            )
        payload = self.interface.answer(dict(request))
        if not isinstance(payload, Mapping):
            raise DecisionProviderError("the configured interface returned a non-object answer")
        described = {}
        if hasattr(self.interface, "describe"):
            described = dict(self.interface.describe() or {})
        return {
            **dict(payload),
            "provider": str(described.get("provider", self.provider)),
            "model": str(described.get("model", self.model)),
            "model_version": str(described.get("model_version", self.model_version)),
        }


class JevShapedAdapter(OptionalProviderAdapter):
    """Map a Jev-shaped decision service onto the generic provider interface.

    The injected interface declares a capability list in the Jev vocabulary
    (``BINARY``, ``CHOICE``, ``SCALE``, ``MULTISELECT``, ``PARALLEL_BATCH``,
    ``PROBABILITIES``, ``VERSIONED_MODEL``) and answers generic requests. This
    adapter translates the vocabulary and refuses to serve when the interface
    does not declare a concrete model version.

    It performs no network call, needs no credentials and no paid call; an
    offline fixture interface covers the adapter contract. Live use is recorded
    as ``NOT_EXECUTED`` because no live service was contacted.
    """

    id = "jev-shaped-adapter"

    def __init__(self, *, interface=None, name: str = "jev") -> None:
        described = {}
        if interface is not None and hasattr(interface, "describe"):
            try:
                described = dict(interface.describe() or {})
            except Exception:
                described = {}
        super().__init__(
            name=str(described.get("provider", name)),
            interface=interface,
            version=str(described.get("model_version", "") or ""),
        )
        if interface is not None and not concrete_model_version(self.model_version):
            self.interface = None
            self.unavailable_reason = (
                "the Jev-shaped interface must report a concrete model version; a moving alias "
                "cannot be recorded as a model identity"
            )
        else:
            self.unavailable_reason = ""

    def available(self) -> tuple[bool, str]:
        if getattr(self, "unavailable_reason", ""):
            return False, self.unavailable_reason
        return super().available()

    def jev_labels(self) -> tuple[str, ...]:
        declared = self._declared()
        if not declared:
            return ()
        labels = declared.get("jev_capabilities") or declared.get("capabilities")
        if labels is None and not isinstance(getattr(self, "_raw_labels", None), tuple):
            labels = getattr(self, "_raw_labels", ())
        return tuple(str(item) for item in labels or ())

    def _declared(self) -> dict:
        if self.interface is None or not hasattr(self.interface, "capabilities"):
            return {}
        try:
            declared = self.interface.capabilities() or {}
        except Exception:
            return {}
        if isinstance(declared, Mapping):
            return dict(declared)
        self._raw_labels = tuple(str(item) for item in declared)
        return {}

    def capabilities(self) -> dict:
        declared = self._declared()
        labels = tuple(str(item) for item in (declared.get("capabilities") or declared.get("jev_capabilities") or ()))
        if not labels:
            labels = tuple(getattr(self, "_raw_labels", ()))
        merged = {**DEFAULT_CAPABILITIES, "capability_names": labels}
        primitives: list[str] = []
        for label in labels:
            mapped = JEV_SHAPED_CAPABILITIES.get(label)
            if not mapped:
                continue
            if "primitives" in mapped:
                primitives.extend(item for item in mapped["primitives"] if item not in primitives)
            for key, value in mapped.items():
                if key != "primitives":
                    merged[key] = value
        merged["primitives"] = tuple(primitives)
        if any(key in declared for key in ("parallel_questions", "max_questions", "max_options",
                                           "state_limit_chars", "usage_metadata", "confidence_kinds")):
            merged.update({
                key: declared[key] for key in ("parallel_questions", "max_questions", "max_options",
                                                "state_limit_chars", "usage_metadata", "confidence_kinds")
                if key in declared
            })
        if merged["batching"]:
            merged["parallel_questions"] = int(merged.get("parallel_questions") or 8) or 8
            if not declared.get("max_questions"):
                merged["max_questions"] = int(merged["parallel_questions"])
        if merged["probabilities"] and not declared.get("confidence_kinds"):
            merged["confidence_kinds"] = (
                "NONE", "SELF_REPORTED_CONFIDENCE", "PROVIDER_PROBABILITY", "CALIBRATED_PROBABILITY",
            )
        merged["confidence_kinds"] = tuple(merged.get("confidence_kinds") or ("NONE",))
        return merged

    def describe(self) -> dict:
        value = super().describe()
        value["capability_names"] = list(self.jev_labels())
        value["note"] = (
            "the adapter contract is offline-verified with fixtures; live service use is NOT_EXECUTED"
        )
        return value


def capability_problems(provider: DecisionProvider) -> list[str]:
    """Structural problems of one provider's declared capabilities.

    A provider that is not available is judged on structure only: it is not
    required to declare model versions it could never have produced.
    """
    problems: list[str] = []
    capabilities = provider.capabilities()
    available, _ = provider.available()
    unknown_primitives = sorted(set(capabilities.get("primitives") or ()) - set(DECISION_PRIMITIVES))
    if unknown_primitives:
        problems.append(f"declared primitives are not decision primitives: {unknown_primitives}")
    if int(capabilities.get("max_questions", 0) or 0) < 1:
        problems.append("a provider must declare how many questions it accepts")
    if capabilities.get("batching") and int(capabilities.get("parallel_questions", 0) or 0) < 2:
        problems.append("a batching provider must declare at least two parallel questions")
    if available and capabilities.get("explicit_model_versions") is not True:
        problems.append("the provider does not declare concrete model versions; cached decisions cannot bind it")
    if capabilities.get("probabilities") and "PROVIDER_PROBABILITY" not in tuple(capabilities.get("confidence_kinds") or ()):
        problems.append("a provider that declares probabilities must declare a probability confidence kind")
    return problems


def supports(
    provider: DecisionProvider,
    *,
    primitive: str = "ChoiceDecision",
    question_count: int = 1,
    option_count: int = 0,
    state_chars: int = 0,
    needs_probabilities: bool = False,
    needs_batching: bool = False,
) -> dict:
    """Whether the provider declares it can answer this request shape."""
    capabilities = provider.capabilities()
    reasons: list[str] = []
    if primitive not in tuple(capabilities.get("primitives") or ()):
        reasons.append(f"the provider does not declare the {primitive} primitive")
    if question_count > int(capabilities.get("max_questions", 0) or 0):
        reasons.append(
            f"the provider accepts at most {capabilities.get('max_questions')} question(s); "
            f"{question_count} were requested"
        )
    if needs_batching and not capabilities.get("batching"):
        reasons.append("the provider does not declare batching")
    if option_count and option_count > int(capabilities.get("max_options", 0) or 0):
        reasons.append(
            f"the provider accepts at most {capabilities.get('max_options')} options; {option_count} were requested"
        )
    limit = int(capabilities.get("state_limit_chars", 0) or 0)
    if state_chars and limit and state_chars > limit:
        reasons.append(f"the projected state is {state_chars} characters; the provider limit is {limit}")
    if needs_probabilities and not capabilities.get("probabilities"):
        reasons.append("the provider does not declare probability output")
    return {"supported": not reasons, "reasons": reasons, "capabilities": capabilities}


def register_capabilities(state: dict, provider: DecisionProvider, *, reason: str = "") -> dict:
    """Register a provider's declared capabilities in the capability registry.

    A declaration is never more than ``DECLARED`` evidence. Capabilities live
    in the one registry, so the engine can inspect them without special-casing
    any provider.
    """
    from .. import capabilities as registry

    available, unavailable_reason = provider.available()
    caps = provider.capabilities()
    return registry.declare(
        state,
        capability_id=f"decision-provider:{provider.id}",
        adapter=str(provider.provider or provider.id),
        family="decision",
        available=bool(available),
        reason=str(reason or unavailable_reason or (
            "declared decision-provider capabilities"
        )),
        version=str(provider.model_version or ""),
        provider=str(provider.provider or ""),
        model=str(provider.model or ""),
        fingerprint=",".join(str(item) for item in caps.get("capability_names") or caps.get("primitives") or ()),
    )


def describe(provider: DecisionProvider) -> dict:
    if not isinstance(provider, DecisionProvider):
        raise ContractError("a decision provider must implement the DecisionProvider interface")
    value = provider.describe()
    value["capability_problems"] = capability_problems(provider)
    if isinstance(provider, JevShapedAdapter):
        value["live_use"] = "NOT_EXECUTED"
    return value


__all__ = [
    "DEFAULT_CAPABILITIES",
    "JEV_SHAPED_CAPABILITIES",
    "MOVING_ALIASES",
    "concrete_model_version",
    "DecisionProviderError",
    "DecisionProvider",
    "DeterministicProvider",
    "UnavailableProvider",
    "OptionalProviderAdapter",
    "JevShapedAdapter",
    "capability_problems",
    "supports",
    "register_capabilities",
    "describe",
]
