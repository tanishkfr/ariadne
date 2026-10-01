"""The Decision Runtime session: what Ariadne sees, and where it lives.

This is the whole user-facing surface of bounded local inference, and it is
deliberately not a provider picker. There is no
``--decision-provider`` argument, no vendor list and nothing for a normal user to
choose. Ariadne looks for a Decision Runtime, and if it finds one it uses it where
policy allows. If it does not, Ariadne remains fully functional on its 2.0 safe
fallback path.

    >>> runtime = DecisionRuntime.discover()
    >>> runtime.status()["status"]
    'AVAILABLE'
    >>> runtime.status()["detail"]
    'Decision Runtime: available'

The vocabulary in that status is the product vocabulary. ``implementation``,
``model_revision`` and ``checkpoint`` are also in the status record, because
provenance that cannot name its implementation is not evidence — but they are
diagnostics, not what the user is asked to understand.

Discovery order, first match wins:

1. an explicitly passed root (tests, advanced configuration);
2. ``ARIADNE_DECISION_RUNTIME`` in the environment;
3. ``<data home>/decision-runtime/current``;
4. ``<data home>/decision-runtime/<ariadne version>``.

Everything under the data home follows the launcher's existing
``user_data_home`` convention, so the Decision Runtime installs and uninstalls with
the rest of the product instead of inventing a second place for itself.
"""

from __future__ import annotations

import os
import platform
from pathlib import Path
from typing import Any, Mapping, Sequence

import json

from ...contracts import (
    DECISION_RUNTIME_KINDS,
    DECISION_RUNTIME_STATUSES,
    UNSUPPORTED_PRIMITIVE,
    ContractError,
)
from ..providers import DEFAULT_CAPABILITIES
from .manifest import (
    DEFAULT_CONTEXT_LIMITS,
    MANIFEST_NAME,
    check_request_bounds,
    revision_matches,
    verify_files,
)
from .transport import (
    RuntimeTransport,
    RuntimeTransportError,
    SubprocessTransport,
    UnavailableTransport,
    resolve_installation,
    sidecar_command,
    sidecar_environment,
)

RUNTIME_DIRECTORY = "decision-runtime"
"""Directory name under the Ariadne data home."""

ENVIRONMENT_OVERRIDE = "ARIADNE_DECISION_RUNTIME"
"""Explicit runtime root. Advanced configuration; never required for normal use."""

REFERENCE_ENGINE_PRIMITIVES = ("BinaryDecision", "ChoiceDecision", "ScaleDecision")
"""What the reference engine answers. ``MultiSelectDecision`` is absent on purpose."""


def user_data_home(
    *,
    system: str | None = None,
    environ: Mapping[str, str] | None = None,
    home: Path | None = None,
) -> Path:
    """Where Ariadne keeps user-managed installations.

    Mirrors :func:`ariadne.cli.user_data_home` exactly, including the
    ``ARIADNE_DATA_HOME`` override, so the Decision Runtime is uninstalled and
    versioned by the same mechanism as the rest of the product.
    """
    environ = os.environ if environ is None else environ
    home = Path.home() if home is None else home
    override = environ.get("ARIADNE_DATA_HOME")
    if override:
        return Path(override).expanduser().resolve()
    system = platform.system() if system is None else system
    if system == "Windows":
        base = Path(environ.get("LOCALAPPDATA", home / "AppData" / "Local"))
        return (base / "Ariadne").resolve()
    if system == "Darwin":
        return (home / "Library" / "Application Support" / "Ariadne").resolve()
    base = Path(environ.get("XDG_DATA_HOME", home / ".local" / "share"))
    return (base / "ariadne").resolve()


def runtime_search_paths(*, version: str = "", environ: Mapping[str, str] | None = None) -> list[Path]:
    """Every place a Decision Runtime may be installed, in priority order."""
    environ = os.environ if environ is None else environ
    candidates: list[Path] = []
    override = environ.get(ENVIRONMENT_OVERRIDE)
    if override:
        candidates.append(Path(override).expanduser())
    home = user_data_home(environ=environ)
    base = home / RUNTIME_DIRECTORY
    candidates.append(base / "current")
    if version:
        candidates.append(base / version)
    return candidates


def find_installation(
    *,
    version: str = "",
    environ: Mapping[str, str] | None = None,
) -> dict:
    """Locate a runtime installation without starting anything."""
    tried: list[str] = []
    for root in runtime_search_paths(version=version, environ=environ):
        if not root.is_dir():
            tried.append(f"{root} (absent)")
            continue
        found = resolve_installation(root)
        if found["installed"]:
            # `searched` always names every place that was considered, including the one
            # that matched. "Found in the first place" and "found in the fourth" are
            # different facts about a machine, and a diagnostic that cannot tell them
            # apart is hiding a configuration problem.
            tried.append(f"{root} (installed)")
            return {**found, "searched": tried}
        tried.append(f"{root} ({found['reason']})")
    return {
        "installed": False,
        "reason": "no decision runtime installation was found in " + "; ".join(tried),
        "root": "",
        "manifest": None,
        "searched": tried,
    }


class DecisionRuntime:
    """The narrow native runtime API.

    ``status``       capability facts and the product-level state string
    ``decide``       one projected state, many independent questions, one inference
    ``decide_batch`` many states, many questions, still one call
    ``evaluate``     score recorded shadow predictions against recorded outcomes
    ``warm``         load ahead of the first question
    ``shutdown``     release the engine

    It deliberately does not re-expose the full provider API. The Decision Plane
    already has one; a second copy would be a second contract to keep honest.
    """

    def __init__(self, transport: RuntimeTransport, *, manifest: Mapping[str, Any] | None = None) -> None:
        self._transport = transport
        self._manifest = dict(manifest or {})
        self._closed = False

    # -- construction ------------------------------------------------------

    @classmethod
    def discover(
        cls,
        *,
        root: Path | str | None = None,
        version: str = "",
        environ: Mapping[str, str] | None = None,
        start_timeout: float | None = None,
    ) -> DecisionRuntime:
        """Find and start a Decision Runtime, or return an honest unavailable one.

        Never raises for a missing or broken runtime. "Not installed" and "installed
        but will not start" are normal states that the caller routes around, and the
        reason is preserved for the diagnostic view.
        """
        target = Path(root) if root is not None else None
        if target is not None:
            found = resolve_installation(target)
        else:
            found = find_installation(version=version, environ=environ)
        if not found["installed"]:
            return cls(UnavailableTransport(str(found["reason"])))
        resolved = Path(found["root"])
        try:
            command = sidecar_command(resolved)
        except Exception as exc:  # noqa: BLE001 - reported, never raised at discovery
            return cls(UnavailableTransport(f"the decision runtime sidecar is unusable: {exc}"))
        environment = dict(os.environ)
        environment.update(sidecar_environment())
        transport = SubprocessTransport(
            command,
            description={"root": str(resolved), "runtime_kind": "local_bounded"},
            env=environment,
        )
        runtime = cls(transport, manifest=found["manifest"])
        try:
            transport.status(timeout=start_timeout)
        except RuntimeTransportError as exc:
            # A runtime that will not start is not a crash. It becomes an unavailable
            # runtime with its reason, and the caller falls back. The transport's own
            # `available()` reason must not be used here: it reports that the sidecar is
            # *installed*, which is true, and is the opposite of the fact the user needs.
            return cls(UnavailableTransport(str(exc)), manifest=found["manifest"])
        return runtime

    @classmethod
    def in_process(cls, engine: Any, *, description: Mapping[str, Any] | None = None) -> DecisionRuntime:
        """Wrap an engine that already lives here. Used by the deterministic fixture
        and by tests; never used for anything heavy."""
        from .transport import InProcessTransport

        return cls(InProcessTransport(engine, description=description))

    @classmethod
    def unavailable(cls, reason: str = "no decision runtime is installed") -> DecisionRuntime:
        return cls(UnavailableTransport(str(reason)))

    # -- capability --------------------------------------------------------

    def available(self) -> tuple[bool, str]:
        if self._closed:
            return False, "the decision runtime session is closed"
        return self._transport.available()

    def status(self) -> dict:
        """Capability facts in both product and provenance vocabularies.

        The product fields (``status``, ``detail``) are what a user should read. The
        provenance fields (``implementation``, ``model_revision``, ``runtime_kind``)
        are what a reviewer needs, and they are never *instead of* the product fields.
        """
        available, reason = self.available()
        described = dict(self._transport.describe())
        state, detail = self._state_for(available, reason, described)
        primitives = tuple(str(item) for item in described.get("primitives", ()) or ())
        return {
            "status": state,
            "detail": f"Decision Runtime: {detail}",
            "reason": reason,
            "available": bool(available and state in ("AVAILABLE", "AVAILABLE_CPU", "AVAILABLE_GPU", "WARM", "COLD")),
            "primitives": primitives,
            "unsupported_primitives": self._unsupported_primitives(primitives),
            "runtime_kind": str(described.get("runtime_kind", "local_bounded" if available else "")),
            "implementation": str(described.get("implementation", "")),
            "implementation_revision": str(described.get("implementation_revision", "")),
            "runtime_version": str(described.get("runtime_version", "")),
            "model": str(described.get("model", "")),
            "model_revision": str(described.get("model_revision", "")),
            "device": str(described.get("device", "")),
            "transport": str(described.get("transport", "")),
            "root": str(described.get("root", "")),
            "confidence_kinds": tuple(str(item) for item in described.get("confidence_kinds", ()) or ()),
            "calibration_self_granted": bool(described.get("calibration_self_granted", False)),
            "digest_pinned": bool(described.get("digest_pinned", False)),
            "note": "bounded local inference; never an authorization and never verification",
        }

    @staticmethod
    def _state_for(available: bool, reason: str, described: Mapping[str, Any]) -> tuple[str, str]:
        if not available:
            lowered = str(reason).lower()
            if "resource" in lowered or "memory" in lowered or "device" in lowered:
                return "UNAVAILABLE_RESOURCE", f"unavailable on this hardware, using fallback ({reason})"
            if "licen" in lowered:
                return "UNAVAILABLE_LICENSE", f"unavailable, licence not satisfied ({reason})"
            return "UNAVAILABLE", f"unavailable, using fallback ({reason})"
        device = str(described.get("device", "")).lower()
        warm = bool(described.get("warm", False))
        if warm:
            return "WARM", "available (warm)"
        if device == "gpu":
            return "COLD", "warming"
        return "COLD", "available (cold)"

    @staticmethod
    def _unsupported_primitives(primitives: Sequence[str]) -> tuple[str, ...]:
        """Ariadne primitives this runtime cannot represent faithfully."""
        from ...contracts import DECISION_PRIMITIVES

        declared = set(primitives)
        return tuple(name for name in DECISION_PRIMITIVES if name not in declared)

    def integrity(self, expected_digests: Mapping[str, str] | None = None) -> dict:
        """Byte-level verification against a reviewed digest record.

        ``UNKNOWN`` is a real result. Ariadne never mints a digest from the bytes it
        just found and calls that independent verification.
        """
        if not self._manifest:
            return {"status": "UNKNOWN", "detail": "no runtime manifest is loaded", "checked": 0,
                    "mismatched": [], "missing": []}
        return verify_files(Path(str(self._manifest.get("root", "."))), expected_digests or self._manifest.get("files"))

    def revision_satisfies(self, expected: str) -> bool:
        """Whether a recorded revision is met by what actually loaded."""
        observed = str(self._transport.describe().get("model_revision", ""))
        return revision_matches(str(expected), observed)

    # -- calls -------------------------------------------------------------

    def decide(
        self,
        state_projection: Mapping[str, Any],
        questions: Sequence[Mapping[str, Any]],
        *,
        policy: Mapping[str, Any] | None = None,
        min_confidence: float | None = None,
        timeout: float | None = None,
    ) -> Mapping[str, Any]:
        """Answer independent questions over one projected state as one inference."""
        check_request_bounds([state_projection], questions)
        return self._transport.call(
            "decide",
            {
                "state": dict(state_projection),
                "questions": [dict(question) for question in questions],
                "min_confidence": self._threshold(policy, min_confidence),
            },
            timeout=timeout,
        )

    def decide_batch(
        self,
        state_projections: Sequence[Mapping[str, Any]],
        questions: Sequence[Mapping[str, Any]],
        *,
        policy: Mapping[str, Any] | None = None,
        min_confidence: float | None = None,
        timeout: float | None = None,
    ) -> Mapping[str, Any]:
        """Answer many questions over many states in one bounded inference unit."""
        check_request_bounds(state_projections, questions)
        return self._transport.call(
            "decide_batch",
            {
                "states": [dict(projection) for projection in state_projections],
                "questions": [dict(question) for question in questions],
                "min_confidence": self._threshold(policy, min_confidence),
            },
            timeout=timeout,
        )

    def evaluate(self, request: Mapping[str, Any], *, timeout: float | None = None) -> Mapping[str, Any]:
        """Ask the runtime to score a recorded evaluation set.

        Kept separate from ``decide`` so an evaluation run can never be mistaken for
        a live decision, and so an engine that cannot self-evaluate says so instead
        of returning a plausible metric.
        """
        return self._transport.call("evaluate", dict(request), timeout=timeout)

    @staticmethod
    def _threshold(policy: Mapping[str, Any] | None, min_confidence: float | None) -> float | None:
        """Which threshold applies.

        An explicit caller value wins; otherwise the contextual policy value is used.
        There is no default. A runtime with no threshold answers everything it can and
        Ariadne's own abstention machinery decides what to do with weak answers — a
        universal constant like ``0.8`` would be a claim about every question at once.
        """
        if min_confidence is not None:
            return float(min_confidence)
        if isinstance(policy, Mapping):
            value = policy.get("min_confidence")
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                return float(value)
        return None

    def warm(self, *, timeout: float | None = None) -> dict:
        """Load ahead of the first question. Failure is reported, not raised."""
        try:
            return dict(self._transport.call("warm", {}, timeout=timeout))
        except RuntimeTransportError as exc:
            return {"warmed": False, "reason": str(exc)}

    def shutdown(self) -> None:
        """Release the engine. Safe to call repeatedly."""
        if self._closed:
            return
        self._closed = True
        try:
            self._transport.close()
        except Exception:  # noqa: BLE001 - shutdown must never raise
            pass

    def __enter__(self) -> DecisionRuntime:
        return self

    def __exit__(self, *_exc: object) -> None:
        self.shutdown()

    # -- diagnostics -------------------------------------------------------

    def problems(self) -> list[str]:
        """Reasons this runtime is not usable as-is. Empty means usable."""
        status = self.status()
        if not status["available"]:
            return [str(status["reason"])]
        if not status["primitives"]:
            return ["the decision runtime declares no primitives"]
        if status["calibration_self_granted"]:
            # An engine that claims its own probabilities are calibrated is making a
            # claim only Ariadne's measured profiles are allowed to make.
            return ["the decision runtime claims to grant its own calibration"]
        if not status["model_revision"]:
            return ["the decision runtime names no concrete model revision"]
        return []

    def describe(self) -> dict:
        return {"status": self.status(), "problems": self.problems(), "runtime_kinds": DECISION_RUNTIME_KINDS,
                "statuses": DECISION_RUNTIME_STATUSES, "manifest": MANIFEST_NAME,
                "unsupported_primitive": UNSUPPORTED_PRIMITIVE,
                "default_capabilities": dict(DEFAULT_CAPABILITIES)}


def default_runtime_capabilities() -> dict:
    """What Ariadne tells the capability registry about the Decision Runtime.

    Registered through the ordinary capability registry rather than special-cased in
    the engine, exactly like every other provider.
    """
    from .reference import ENGINE_NAME, ENGINE_REVISION

    return {
        "primitives": REFERENCE_ENGINE_PRIMITIVES,
        "batching": True,
        "parallel_questions": 32,
        "max_questions": 32,
        "max_options": 32,
        "probabilities": True,
        "confidence_kinds": ("PROVIDER_PROBABILITY", "NONE"),
        "explicit_model_versions": True,
        "state_limit_chars": 16_000,
        "usage_metadata": True,
        "capability_names": ("local-bounded", ENGINE_NAME, ENGINE_REVISION),
    }