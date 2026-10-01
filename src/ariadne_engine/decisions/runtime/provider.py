"""The local bounded provider: how the Decision Runtime reaches the Decision Plane.

The Decision Plane already has exactly the interface this needs —
``available()``, ``capabilities()``, ``confidence_kinds()``, ``describe()`` and
``answer(request)`` — and it already validates answers against a closed set, records
digests, binds the cache and escalates on weakness. So the Decision Runtime arrives
as one more :class:`~ariadne_engine.decisions.providers.DecisionProvider`
subclass and inherits all of that.

That is the whole design intent. Nothing in the Decision Plane learns that a local
runtime exists; the runtime is selected by a caller that already knows how to select
a provider, and everything downstream is unchanged 2.0 behaviour.

Three things this adapter refuses to do:

*Promote confidence.* The runtime reports ``PROVIDER_PROBABILITY``. Only a measured
:class:`~ariadne_engine.decisions.runtime.profiles.CalibrationProfile` may relabel a
decision ``CALIBRATED_PROBABILITY``, and that happens in the record, not here.

*Fabricate a model version.* ``model_version`` is the runtime's own concrete revision.
If the runtime cannot name one, ``available()`` is False. A bounded decision bound to
an alias would let the cache serve a decision a moved model no longer supports.

*Answer a primitive it cannot represent.* ``MultiSelectDecision`` returns
``UNSUPPORTED_PRIMITIVE`` as a failed question rather than a fabricated set, and the
Plane's own fallback takes over.
"""

from __future__ import annotations

from typing import Any, Mapping

import math

from ...contracts import UNSUPPORTED_PRIMITIVE
from ..contracts import answer_from_provider
from ..providers import DecisionProvider, DecisionProviderError
from .reference import SUPPORTED_PRIMITIVES
from .session import DecisionRuntime, default_runtime_capabilities

LOCAL_PROVIDER_ID = "local-bounded-runtime"
"""The registry id. It names the *kind* of implementation, never a vendor."""

LOCAL_PROVIDER_NAME = "ariadne-decision-runtime"
"""What provenance records name, and what users see in diagnostics."""


class LocalBoundedProvider(DecisionProvider):
    """Ariadne's native Decision Runtime, presented as a decision provider."""

    id = LOCAL_PROVIDER_ID
    provider = LOCAL_PROVIDER_NAME

    def __init__(
        self,
        runtime: DecisionRuntime | None = None,
        *,
        model_version: str = "",
        timeout: float | None = None,
    ) -> None:
        self._runtime = runtime or DecisionRuntime.discover()
        self._timeout = timeout
        self.calls = 0
        self.abstentions = 0
        self.failures = 0
        self._model_version = str(model_version or self._observed_revision())

    def _observed_revision(self) -> str:
        described = self._runtime.status()
        return str(described.get("model_revision", "") or "")

    # -- identity ----------------------------------------------------------

    @property
    def model(self) -> str:
        return str(self._runtime.status().get("model", "")) or LOCAL_PROVIDER_NAME

    @property
    def model_version(self) -> str:
        """The revision the runtime reports *now*, not the one it reported at startup.

        The transport transparently respawns a sidecar that died, and the replacement
        may be a different build. A latched value would stamp an answer computed by the
        new revision with the old one, and serve the old revision's cached answers to the
        new one -- which is the moving label the cache exists to prevent.
        """
        return self._observed_revision() or self._model_version

    def _assert_revision_agrees(self, response: Mapping[str, Any]) -> None:
        """Refuse a response whose revision is not the one this provider just observed.

        The transport restarts a dead child transparently, so an answer can arrive from a
        build that was not the one this provider last reported. Recording it would pair
        a decision with the wrong revision in the decision record and the cache key.
        """
        observed = self._observed_revision()
        claimed = str(response.get("model_version", "") or "")
        if observed and claimed and observed != claimed:
            raise DecisionProviderError(
                f"the decision runtime answered as {claimed!r} but now reports {observed!r}; "
                "a restarted sidecar must not be trusted to answer as the previous revision"
            )

    # -- capability --------------------------------------------------------

    def available(self) -> tuple[bool, str]:
        ok, reason = self._runtime.available()
        if not ok:
            return False, reason
        if not self._model_version:
            # No concrete revision means a bounded decision could be cached against a
            # label that moves. Refuse rather than record a version that cannot be
            # honoured.
            return False, "the decision runtime names no concrete model revision"
        problems = self._runtime.problems()
        if problems:
            return False, "; ".join(problems)
        return True, str(self._runtime.status().get("reason", "the decision runtime is available"))

    def capabilities(self) -> dict:
        declared = default_runtime_capabilities()
        supported = set(self._runtime.status().get("primitives", ()) or SUPPORTED_PRIMITIVES)
        declared["primitives"] = tuple(
            primitive for primitive in declared["primitives"] if primitive in supported
        )
        declared["state_limit_chars"] = int(
            self._runtime.status().get("context_limits", {}).get("max_state_chars", 16_000)
        ) or 16_000
        return declared

    def confidence_kinds(self) -> tuple[str, ...]:
        """Provider probability only. The runtime cannot grant itself calibration."""
        return ("PROVIDER_PROBABILITY", "NONE")

    def describe(self) -> dict:
        described = super().describe()
        status = self._runtime.status()
        described.update(
            {
                "runtime_kind": str(status.get("runtime_kind", "")),
                "implementation": str(status.get("implementation", "")),
                "implementation_revision": str(status.get("implementation_revision", "")),
                "device": str(status.get("device", "")),
                "runtime_status": str(status.get("status", "")),
                "runtime_detail": str(status.get("detail", "")),
                "unsupported_primitives": tuple(status.get("unsupported_primitives", ()) or ()),
                "calls": self.calls,
                "abstentions": self.abstentions,
                "failures": self.failures,
                "authorization_effect": "none",
            }
        )
        return described

    # -- answering ---------------------------------------------------------

    def answer(self, request: Mapping) -> Mapping:
        """One bounded inference for one projected state and its questions."""
        from ..contracts import DecisionQuestion

        questions = [DecisionQuestion.from_record(row) for row in request.get("questions") or []]
        unsupported = [
            question.question_id for question in questions if question.primitive not in SUPPORTED_PRIMITIVES
        ]
        if unsupported:
            # Refusing the whole call is safer than sending a question the runtime
            # cannot represent and reading its error as an answer.
            raise DecisionProviderError(
                f"{UNSUPPORTED_PRIMITIVE}: the decision runtime cannot represent "
                + ", ".join(sorted(unsupported))
                + f"; it answers {', '.join(SUPPORTED_PRIMITIVES)}"
            )
        projection = dict(request.get("projection") or {})
        self.calls += 1
        try:
            response = self._runtime.decide(
                projection,
                [question.as_record() for question in questions],
                policy=request.get("policy"),
                timeout=self._timeout,
            )
        except Exception as exc:  # noqa: BLE001 - a provider failure is recorded, never answered
            self.failures += 1
            raise DecisionProviderError(str(exc)) from exc
        try:
            self._assert_revision_agrees(response)
        except DecisionProviderError:
            self.failures += 1
            raise
        return self._translate(response, questions, projection)

    def _translate(
        self,
        response: Mapping[str, Any],
        questions: list,
        projection: Mapping[str, Any],
    ) -> Mapping:
        raw_answers = dict(response.get("answers") or {})
        failed: list[str] = []
        answers: dict[str, Any] = {}
        for position, question in enumerate(questions):
            slot = raw_answers.get(f"0:{question.question_id}")
            if not isinstance(slot, Mapping):
                failed.append(question.question_id)
                continue
            reason = str(slot.get("reason", ""))
            if not slot.get("valid", False):
                if slot.get("abstained"):
                    self.abstentions += 1
                failed.append(question.question_id)
                answers[question.question_id] = {
                    "answer": None,
                    "confidence": None,
                    "confidence_kind": "NONE",
                    "distribution": dict(slot.get("distribution", {}) or {}),
                    "abstained": True,
                    "reason": reason,
                }
                continue
            payload = {
                "answer": slot.get("answer"),
                "confidence": _bounded_confidence(slot.get("confidence")),
                "confidence_kind": _declared_confidence_kind(
                    slot.get("confidence_kind"), self.confidence_kinds()
                ),
                "distribution": dict(slot.get("distribution", {}) or {}),
            }
            # Validate through the Plane's own contract so a runtime cannot widen the
            # answer space by returning something the question never declared.
            parsed = answer_from_provider(question, payload)
            if parsed.problems:
                failed.append(question.question_id)
                answers[question.question_id] = {**payload, "problems": list(parsed.problems)}
                continue
            if not _plausible(payload):
                # The wire answer was inside the answer space, but the confidence it
                # carried is not something this provider is willing to vouch for. Refusing
                # is the honest response: a policy reading a confidence of 1e-9 as a weak
                # opinion rather than a refusal is exactly the confusion to avoid.
                failed.append(question.question_id)
                answers[question.question_id] = {
                    **payload,
                    "abstained": True,
                    "reason": "the runtime reported a confidence its provider does not offer",
                    "problems": [
                        "confidence_kind was not one this provider declares: "
                        f"{sorted(self.confidence_kinds())}",
                    ],
                }
                continue
            answers[question.question_id] = {
                **payload,
                "answers": list(parsed.answers),
                "family": str(slot.get("family", "")),
                "abstained": False,
                "reason": "",
            }
        return {
            "provider": self.provider,
            "model": self.model,
            "model_version": self.model_version,
            "implementation_revision": str(response.get("implementation_revision", "")),
            "runtime_version": str(response.get("runtime_version", "")),
            "device": str(response.get("device", "")),
            "request_id": f"{LOCAL_PROVIDER_ID}-{position_id(projection)}",
            "answers": answers,
            "failed_questions": failed,
            "usage": dict(response.get("usage", {}) or {}),
            "projection_digest": str(projection.get("digest", "")),
            "authorization_effect": "none",
        }


def _bounded_confidence(value: Any) -> float | None:
    """A finite confidence in ``[0, 1]``, or ``None``.

    A non-finite or out-of-range number from the wire is not a weak opinion, it is a
    malformed answer, and passing it through would let a policy compare against it.
    """
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number) or number < 0.0 or number > 1.0:
        return None
    return number


def _declared_confidence_kind(value: Any, offered: tuple[str, ...]) -> str:
    """The runtime's claimed kind, narrowed to one this provider actually offers.

    ``describe()`` is the contract this provider publishes. A sidecar that answers with
    a kind absent from it is making a claim about its own calibration that the provider
    has not made and cannot make on its behalf.
    """
    claimed = str(value or "PROVIDER_PROBABILITY")
    return claimed if claimed in offered else "SELF_REPORTED_CONFIDENCE"


def _plausible(payload: Mapping[str, Any]) -> bool:
    """Whether the provider is willing to stand behind this answer's confidence.

    A kind the provider does not offer, or a confidence of effectively zero attached to
    a real answer, is a refusal expressed as a number. Refusing it keeps the two apart.
    """
    if payload.get("confidence_kind") == "NONE":
        return False
    if payload.get("confidence_kind") == "SELF_REPORTED_CONFIDENCE":
        return False
    confidence = payload.get("confidence")
    if confidence is not None and 0.0 < float(confidence) <= 0.01:
        return False
    return True


def position_id(projection: Mapping[str, Any]) -> str:
    """A stable short suffix for a provider request id.

    Derived from the projection digest, so the same projected state produces the same
    request id and a different state does not. A random id would be easier; a stable
    one is what makes two runs of the same question comparable.
    """
    digest = str(projection.get("digest", ""))
    return digest[:12] if digest else "noprojection"


def local_provider(runtime: DecisionRuntime | None = None) -> LocalBoundedProvider:
    """Build the provider for an auto-discovered runtime.

    This is the normal path. There is no vendor argument because there is no vendor
    choice to make: Ariadne found a Decision Runtime or it did not.
    """
    return LocalBoundedProvider(runtime)