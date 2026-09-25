"""Rendered evidence: capture provenance, evidence states and re-production (AR-202D T7).

Source code cannot prove rendered quality, and a file called ``screenshot.png``
cannot either. This module makes a rendered claim carry the provenance that
makes it checkable:

``SOURCE_SUGGESTS``  source text suggests a behaviour (a declaration, a tag)
``RENDERED``         a capture adapter produced an artifact at a declared viewport/revision
``OBSERVED``         a behaviour was observed over time (interaction/measurement artifact)
``VERIFIED``         an independent engine execution re-produced the evidence
``UNVERIFIED``       explicitly not captured, with a recorded blocker

The states are never collapsed. ``record`` refuses a bare file path: an artifact
is accepted only through a capture record the adapter produced, which names the
method, the environment, the viewport, the revision and the artifact digest the
engine then re-verifies. Re-production is bound to a *different* engine-created
execution, so "verified" is an execution fact rather than a declaration.

The instrument is dependency-free and offline by default. ``offline-fixture``
produces deterministic artifacts from a declared scene, so the workflow is
testable without a browser. A real browser is an operator-approved optional
capability, never required, never installed, and never started from here.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping, Sequence

from . import contracts
from .contracts import (
    RENDERED_EVIDENCE_KINDS,
    RENDERED_EVIDENCE_STATES,
    RENDER_CAPTURE_METHODS,
    ContractError,
)

CAPTURE_DIR = "design-captures"
MANIFEST_NAME = "capture-manifest.json"
OFFLINE_ENVIRONMENT = {"kind": "offline-fixture", "browser": "none", "engine": "ariadne-design"}

OBSERVING_KINDS = ("interaction", "measurement", "video")

EVIDENCE_ORDER = ("UNVERIFIED", "SOURCE_SUGGESTS", "RENDERED", "OBSERVED", "VERIFIED")
"""Ordinal strength. An inequality is a fact about evidence, not a quality score."""


def evidence_root(state: Mapping) -> Path | None:
    """The root a capture artifact may live in: the run's capture directory.

    Returns ``None`` when the state names neither a run root nor a project, so a
    caller can refuse rather than fall back to "anywhere".
    """
    run_root = str(state.get("run_root", "") or state.get("project", "") or "")
    return capture_root(Path(run_root)) if run_root else None


def permitted_evidence_path(state: Mapping, path: Any, *, label: str = "rendered evidence") -> Path:
    """Resolve a captured artifact and require it inside the run's capture root.

    A fixture capture is materialised by the engine under the run root, so a
    fixture-method artifact that resolves anywhere else is refused. The
    ``declared-observer`` method is the one explicit external-reference case: an
    operator's own artifact is accepted only with its declaration, and the
    record says out loud that the engine did not produce it.
    """
    root = evidence_root(state)
    if root is None:
        raise ContractError(
            "the run state names no run root, so a captured artifact has no permitted root and cannot be trusted"
        )
    return contracts.contained_evidence_path(path, root, label=label)


def strength(state: str) -> int:
    return EVIDENCE_ORDER.index(state) if state in EVIDENCE_ORDER else -1


def capture_root(run_root: Path) -> Path:
    return Path(run_root) / CAPTURE_DIR


@dataclass(frozen=True)
class CaptureArtifact:
    """One artifact a capture adapter produced, with the provenance it declares."""

    kind: str
    path: str
    sha256: str
    viewport: Mapping[str, object] = field(default_factory=dict)
    environment: Mapping[str, object] = field(default_factory=dict)
    method: str = "offline-fixture"
    observation: str = ""
    extra: Mapping[str, object] = field(default_factory=dict)

    def as_record(self) -> dict:
        return {
            "kind": self.kind,
            "path": self.path,
            "sha256": self.sha256,
            "viewport": dict(self.viewport),
            "environment": dict(self.environment),
            "method": self.method,
            "observation": self.observation,
            "extra": dict(self.extra),
        }


class CaptureAdapter:
    """A source of rendered evidence. Never starts a browser, never installs."""

    id = "abstract-capture"

    def available(self) -> tuple[bool, str]:
        return False, "no capture capability is configured"

    def capabilities(self) -> tuple[str, ...]:
        return ()

    def capture(self, spec: Mapping) -> CaptureArtifact:
        raise ContractError(f"capture adapter {self.id!r} cannot capture anything here")

    def compare(self, a: Mapping, b: Mapping, thresholds: Mapping | None = None) -> dict:
        """Structural comparison of two artifacts. Digests decide equality."""
        left = str(a.get("sha256", ""))
        right = str(b.get("sha256", ""))
        return {
            "identical": bool(left) and left == right,
            "left": left,
            "right": right,
            "thresholds": dict(thresholds or {}),
            "note": "digest comparison only; no pixel tooling is bundled",
        }

    def capability_record(self) -> dict:
        available, reason = self.available()
        return {
            "id": self.id,
            "available": bool(available),
            "reason": str(reason),
            "capabilities": list(self.capabilities()),
            "method": "offline-fixture" if self.id == "offline-fixture" else "declared-observer",
        }


def _write(path: Path, payload: bytes) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    return hashlib.sha256(payload).hexdigest()


class OfflineFixtureAdapter(CaptureAdapter):
    """Deterministic offline capture. Proves the workflow, not a browser.

    A fixture declares scenes: ``{route, viewport, dom, accessibility, console,
    interaction, screenshot_bytes}``. Every artifact is materialised under the
    run root and hashed by the engine, and the adapter writes a capture manifest
    beside them. Nothing is simulated *as* a browser: the record says exactly
    what produced the bytes.
    """

    id = "offline-fixture"

    def __init__(self, run_root: Path, fixture: Mapping) -> None:
        self.run_root = Path(run_root)
        self.fixture = dict(fixture or {})
        self.scenes = [dict(item) for item in (self.fixture.get("scenes") or []) if isinstance(item, Mapping)]

    def available(self) -> tuple[bool, str]:
        if not self.scenes:
            return False, "the fixture declares no scenes"
        return True, ""

    def capabilities(self) -> tuple[str, ...]:
        return ("screenshot", "dom", "accessibility", "console", "interaction", "measurement")

    def _scene(self, spec: Mapping) -> dict:
        wanted = str(spec.get("route", "") or "")
        for scene in self.scenes:
            if str(scene.get("route", "")) == wanted:
                return scene
        raise ContractError(f"the offline fixture declares no scene for route {wanted!r}")

    def capture(self, spec: Mapping) -> CaptureArtifact:
        available, reason = self.available()
        if not available:
            raise ContractError(f"offline fixture capture is unavailable: {reason}")
        scene = self._scene(spec)
        kind = str(spec.get("kind", "screenshot"))
        if kind not in self.capabilities():
            raise ContractError(f"the offline fixture cannot produce {kind!r}")
        route = str(scene.get("route", ""))
        viewport = dict(spec.get("viewport") or scene.get("viewport") or {})
        width = str(viewport.get("width", "") or "")
        if not width:
            raise ContractError("a capture needs a viewport width")
        directory = capture_root(self.run_root) / _slug(route) / str(width)
        directory.mkdir(parents=True, exist_ok=True)
        if kind == "screenshot":
            payload = bytes(scene.get("screenshot_bytes") or b"")
            if not payload:
                payload = _deterministic_png(scene, viewport)
            path = directory / "screenshot.png"
            digest = _write(path, payload)
            record = CaptureArtifact(
                kind=kind, path=str(path.resolve()), sha256=digest, viewport=viewport,
                environment=OFFLINE_ENVIRONMENT, method=self.id, extra={"encoding": "fixture-bytes"},
            )
        elif kind == "dom":
            text = str(scene.get("dom", ""))
            if not text.strip():
                raise ContractError(f"the fixture declares no DOM for route {route!r}")
            path = directory / "dom.html"
            digest = _write(path, text.encode("utf-8"))
            record = CaptureArtifact(
                kind=kind, path=str(path.resolve()), sha256=digest, viewport=viewport,
                method=self.id, extra={"nodes": text.count("<")},
            )
        elif kind == "accessibility":
            rules = [dict(item) for item in (scene.get("accessibility") or []) if isinstance(item, Mapping)]
            path = directory / "accessibility.json"
            digest = _write(path, (json.dumps(rules, indent=2, sort_keys=True) + "\n").encode("utf-8"))
            violations = [item for item in rules if str(item.get("severity", "")) in ("critical", "serious")]
            record = CaptureArtifact(
                kind=kind, path=str(path.resolve()), sha256=digest, viewport=viewport,
                method=self.id, extra={"rules": rules, "violations": violations},
            )
        elif kind == "console":
            lines = [str(item) for item in (scene.get("console") or [])]
            path = directory / "console.log"
            digest = _write(path, ("\n".join(lines) + "\n").encode("utf-8"))
            errors = [line for line in lines if "error" in line.lower()]
            record = CaptureArtifact(
                kind=kind, path=str(path.resolve()), sha256=digest, viewport=viewport,
                method=self.id, extra={"lines": lines, "errors": errors},
            )
        elif kind in ("interaction", "measurement"):
            steps = [dict(item) for item in (scene.get("interaction") or []) if isinstance(item, Mapping)]
            if not steps:
                raise ContractError(f"the fixture declares no interaction transcript for route {route!r}")
            path = directory / "interaction.json"
            digest = _write(path, (json.dumps(steps, indent=2, sort_keys=True) + "\n").encode("utf-8"))
            record = CaptureArtifact(
                kind=kind, path=str(path.resolve()), sha256=digest, viewport=viewport,
                method=self.id, observation=str(steps[-1].get("observed", "")),
                extra={"steps": steps},
            )
        else:  # pragma: no cover - guarded above
            raise ContractError(f"unsupported offline capture kind: {kind!r}")
        manifest = directory / MANIFEST_NAME
        manifest.write_text(
            json.dumps({
                "adapter": self.id,
                "route": route,
                "viewport": viewport,
                "kind": kind,
                "artifact": {"path": record.path, "sha256": record.sha256},
                "environment": {"kind": "offline-fixture", "browser": "none"},
                "recorded_at": contracts.utc_now(),
            }, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return record


def _deterministic_png(scene: Mapping, viewport: Mapping) -> bytes:
    """A deterministic byte sequence for a declared scene.

    It is deliberately *not* a real PNG and is never presented as one: the kind
    is recorded as ``screenshot`` with ``encoding: fixture-bytes``, so nobody can
    mistake fixture evidence for browser evidence.
    """
    payload = json.dumps(
        {
            "route": scene.get("route"),
            "viewport": viewport,
            "blocks": scene.get("dom", ""),
            "marks": scene.get("visual_marks", []),
        },
        sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")
    return b"ARIADNE-OFFLINE-FIXTURE\x00" + hashlib.sha256(payload).digest() + payload


class DeclaredObserverAdapter(CaptureAdapter):
    """An operator-declared observer that recorded artifacts itself.

    It is accepted only with an explicit declaration of how the artifact was
    produced, in what environment and at what revision, and its records can never
    reach ``OBSERVED`` or ``VERIFIED``. That is the honest ceiling for evidence the
    engine did not produce itself.
    """

    id = "declared-observer"

    def __init__(self, *, environment: Mapping | None = None, method: str = "") -> None:
        self.environment = dict(environment or {})
        self.method_description = str(method or "")

    def available(self) -> tuple[bool, str]:
        if not self.method_description:
            return False, "no declared capture method is configured"
        return True, ""

    def capabilities(self) -> tuple[str, ...]:
        return ("screenshot", "dom", "browser", "measurement", "interaction", "accessibility", "console", "video")

    def capture(self, spec: Mapping) -> CaptureArtifact:
        available, reason = self.available()
        if not available:
            raise ContractError(f"declared observer is unavailable: {reason}")
        path = Path(str(spec.get("path", "")))
        if not path.is_file():
            raise ContractError(f"declared observer artifact does not exist: {path}")
        return CaptureArtifact(
            kind=str(spec.get("kind", "screenshot")),
            path=str(path.resolve()),
            sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
            viewport=dict(spec.get("viewport") or {}),
            environment={"declared": True, **self.environment},
            method=self.id,
            observation=str(spec.get("observation", "")),
            extra={"declaration": self.method_description, "trust": "declared"},
        )


class LocalBrowserAdapter(CaptureAdapter):
    """A local browser capture capability, declared but not exercised here.

    AR-202D ships the contract and reports its own availability truthfully. A
    real browser run is an operator-approved optional capability: it is never
    installed, never started implicitly, and none of AR-202D's claims depend on
    it. When no authorized capability is configured the answer is an honest
    "unavailable", not a fabricated artifact.
    """

    id = "local-browser"

    def __init__(self, *, configured_command: str = "", reason: str = "") -> None:
        self.configured_command = str(configured_command or "")
        self._reason = reason or (
            "no authorized local browser capture capability is configured; Ariadne does not install "
            "or start a browser, and nothing in this milestone requires one"
        )

    def available(self) -> tuple[bool, str]:
        if self.configured_command:
            return True, ""
        return False, self._reason

    def capabilities(self) -> tuple[str, ...]:
        return ("screenshot", "dom", "interaction", "measurement", "accessibility", "console")


def default_adapters(run_root: Path, *, fixture: Mapping | None = None,
                     declared_observer: Mapping | None = None) -> dict[str, CaptureAdapter]:
    adapters: list[CaptureAdapter] = [
        LocalBrowserAdapter(),
        DeclaredObserverAdapter(**dict(declared_observer or {})),
    ]
    if fixture is not None:
        adapters.insert(0, OfflineFixtureAdapter(run_root, fixture))
    return {adapter.id: adapter for adapter in adapters}


def capability_matrix(adapters: Mapping[str, CaptureAdapter]) -> list[dict]:
    """Declared capture capabilities. Never inferred from a model or vendor name."""
    return [adapter.capability_record() for adapter in adapters.values()]


# --------------------------------------------------------------- record I/O

def evidence(state: dict) -> list[dict]:
    values = state.get("rendered_evidence")
    if not isinstance(values, list):
        return []
    return [item for item in values if isinstance(item, Mapping)]


def by_id(state: dict, evidence_id: str) -> dict | None:
    for record in evidence(state):
        if str(record.get("evidence_id", "")) == str(evidence_id):
            return record
    return None


def _require(state: dict, evidence_id: str) -> dict:
    record = by_id(state, evidence_id)
    if record is None:
        raise ContractError(f"no rendered evidence record matches {evidence_id!r}")
    return record


def _verify_artifact(record: Mapping) -> list[str]:
    """Re-hash the recorded artifact. A moved or edited file is not evidence."""
    artifact = record.get("artifact") if isinstance(record.get("artifact"), Mapping) else {}
    path = Path(str(artifact.get("path", "")))
    if not path.is_file():
        return [f"rendered evidence artifact is missing: {path}"]
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    if actual != str(artifact.get("sha256", "")):
        return [f"rendered evidence artifact changed after capture: {path}"]
    return []


def _provenance_problems(value: CaptureArtifact, path: Path, adapter: str) -> list[str]:
    """Whether the artifact carries the provenance its capture method requires.

    A digest only proves the file did not change since somebody hashed it. It does
    not prove that a capture happened, so each method has a provenance obligation
    the engine can check without trusting the caller:

    ``offline-fixture``
        the artifact directory must contain the capture manifest the adapter wrote
        at capture time, naming this artifact and this digest.
    ``declared-observer``
        the artifact must carry the observer's explicit declaration, so the record
        says out loud that the engine did not produce it.
    """
    problems: list[str] = []
    if value.method == "offline-fixture":
        manifest_path = path.parent / MANIFEST_NAME
        if not manifest_path.is_file():
            return [
                "no capture manifest accompanies this artifact, so the engine cannot establish that a "
                "capture produced it; a file that merely exists is not rendered evidence"
            ]
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            return [f"the capture manifest beside the artifact is unreadable: {exc}"]
        declared = manifest.get("artifact") if isinstance(manifest, Mapping) else {}
        if str((declared or {}).get("path", "")) != str(path.resolve()):
            problems.append("the capture manifest beside the artifact names a different artifact")
        if str((declared or {}).get("sha256", "")) != value.sha256:
            problems.append("the capture manifest does not record the artifact digest being claimed")
        if str(manifest.get("adapter", "")) != adapter:
            problems.append(f"the capture manifest was written by {manifest.get('adapter')!r}, not {adapter!r}")
    elif value.method == "declared-observer":
        if str(value.extra.get("trust", "")) != "declared":
            problems.append(
                "a declared-observer artifact must carry the observer's declaration; the engine cannot "
                "treat an undeclared file as observed evidence"
            )
        if not str(value.extra.get("declaration", "")).strip():
            problems.append("the declared observer recorded no method declaration")
    else:
        problems.append(f"unknown capture method: {value.method!r}")
    return problems


def record(
    state: dict,
    *,
    task_id: str,
    revision_hash: str,
    artifact: CaptureArtifact | Mapping,
    adapter: str,
    adapter_available: bool = True,
    capture_execution: str = "",
    requirement_id: str = "",
    direction_id: str = "",
    comparison: Mapping | None = None,
) -> dict:
    """Record one captured artifact as ``RENDERED``. Provenance is mandatory.

    A bare file path is refused: evidence arrives as a :class:`CaptureArtifact`
    an adapter produced, the engine re-hashes the artifact, and the artifact's
    capture method has a provenance obligation that is checked here.
    """
    if not re.fullmatch(r"[0-9a-f]{64}", str(revision_hash or "")):
        raise ContractError("rendered evidence must be bound to a revision fingerprint")
    if not adapter_available:
        raise ContractError(
            f"capture adapter {adapter!r} reports itself unavailable; no rendered evidence can be "
            "claimed from a capability that is not configured"
        )
    value = artifact if isinstance(artifact, CaptureArtifact) else CaptureArtifact(
        kind=str(dict(artifact).get("kind", "")),
        path=str(dict(artifact).get("path", "")),
        sha256=str(dict(artifact).get("sha256", "")),
        viewport=dict(dict(artifact).get("viewport") or {}),
        environment=dict(dict(artifact).get("environment") or {}),
        method=str(dict(artifact).get("method", "")),
        observation=str(dict(artifact).get("observation", "")),
        extra=dict(dict(artifact).get("extra") or {}),
    )
    if value.kind not in RENDERED_EVIDENCE_KINDS:
        raise ContractError(f"unsupported rendered evidence kind: {value.kind!r}")
    if value.method not in RENDER_CAPTURE_METHODS:
        raise ContractError(f"unknown capture method: {value.method!r}")
    if value.method == "declared-observer" and adapter != "declared-observer":
        raise ContractError("a declared observer artifact must be recorded through the declared observer adapter")
    path = Path(value.path)
    if not path.is_file():
        raise ContractError(f"capture artifact does not exist: {path}")
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    if actual != value.sha256:
        raise ContractError(
            "the capture artifact does not match the digest the adapter declared; "
            "an unverifiable artifact is not rendered evidence"
        )
    provenance_problems = _provenance_problems(value, path, str(adapter))
    if provenance_problems:
        raise ContractError("rendered evidence provenance is not established: " + "; ".join(provenance_problems))
    if value.method == "offline-fixture":
        # Containment is checked once the artifact would otherwise be accepted, so a
        # fixture capture can only ever be recorded from the run's own capture root.
        path = permitted_evidence_path(state, path, label="a fixture capture artifact")
    viewport = dict(value.viewport)
    if not str(viewport.get("width", "") or "").strip():
        raise ContractError("rendered evidence must declare the viewport it was captured at")
    state_name = "RENDERED"
    if value.method == "declared-observer":
        state_name = "RENDERED"
    record_value = {
        "schema_version": contracts.SCHEMA_DESIGN,
        "evidence_id": contracts.new_record_id("rnd"),
        "run_id": str(state.get("run_id", "")),
        "task_id": str(task_id),
        "revision_hash": str(revision_hash),
        "requirement_id": str(requirement_id),
        "direction_id": str(direction_id),
        "kind": value.kind,
        "state": state_name,
        "capture_method": value.method,
        "adapter": str(adapter),
        "capture_execution": str(capture_execution),
        "verification_execution": "",
        "verification_id": "",
        "prior_evidence_ids": [],
        "observation": str(value.observation),
        "viewport": viewport,
        "environment": dict(value.environment),
        "artifact": {"path": str(path.resolve()), "sha256": actual},
        "extra": dict(value.extra),
        "comparison": dict(comparison or {}),
        "blocker": "",
        "captured_at": contracts.utc_now(),
        "provenance": {
            "created_by": "engine",
            "method": value.method,
            "adapter": str(adapter),
            "revision_bound": True,
        },
    }
    problems = contracts.rendered_evidence_problems(record_value)
    if problems:
        raise ContractError("rendered evidence is malformed: " + "; ".join(problems))
    contracts.require_design_capacity(state, "rendered_evidence")
    state.setdefault("rendered_evidence", []).append(record_value)
    return record_value


def record_source_suggests(
    state: dict,
    *,
    task_id: str,
    revision_hash: str,
    source_path: Path,
    source_anchor: str,
    observation: str,
    requirement_id: str = "",
) -> dict:
    """Record ``SOURCE_SUGGESTS``: the weakest state, and never more than that."""
    path = contracts.contained_evidence_path(
        source_path,
        contracts.permitted_project_root(state, label="a source artifact"),
        label="source evidence",
    )
    if not path.is_file():
        raise ContractError(f"source artifact does not exist: {path}")
    if not str(source_anchor or "").strip():
        raise ContractError(
            "a source claim needs the anchor it cites; without one it is a claim about a file rather "
            "than about the code in it"
        )
    text = path.read_text(encoding="utf-8", errors="replace")
    if source_anchor not in text:
        raise ContractError(
            f"the source anchor {source_anchor!r} does not occur in {path.name}; "
            "a source claim must point at the source that makes it"
        )
    record_value = {
        "schema_version": contracts.SCHEMA_DESIGN,
        "evidence_id": contracts.new_record_id("rnd"),
        "run_id": str(state.get("run_id", "")),
        "task_id": str(task_id),
        "revision_hash": str(revision_hash),
        "requirement_id": str(requirement_id),
        "direction_id": "",
        "kind": "source",
        "state": "SOURCE_SUGGESTS",
        "capture_method": "declared-observer",
        "adapter": "source-inspection",
        "capture_execution": "",
        "verification_execution": "",
        "prior_evidence_ids": [],
        "observation": str(observation),
        "viewport": {"width": "source", "height": "source", "device_pixel_ratio": 1},
        "environment": {"kind": "source"},
        "artifact": {"path": str(path.resolve()), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()},
        "extra": {"anchor": str(source_anchor)},
        "comparison": {},
        "blocker": "",
        "captured_at": contracts.utc_now(),
        "provenance": {
            "created_by": "engine",
            "method": "source-inspection",
            "revision_bound": True,
        },
    }
    problems = contracts.rendered_evidence_problems(record_value)
    if problems:
        raise ContractError("source evidence is malformed: " + "; ".join(problems))
    contracts.require_design_capacity(state, "rendered_evidence")
    state.setdefault("rendered_evidence", []).append(record_value)
    return record_value


def observe(
    state: dict,
    evidence_id: str,
    *,
    artifact: Mapping,
    observation: str,
    kind: str = "interaction",
    execution: str = "",
) -> dict:
    """Promote a capture to ``OBSERVED`` with a behaviour/measurement artifact."""
    record_value = _require(state, evidence_id)
    if strength(str(record_value.get("state", ""))) < strength("RENDERED"):
        raise ContractError(
            "a source suggestion cannot be observed; capture the rendering first"
        )
    if kind not in OBSERVING_KINDS:
        raise ContractError(f"an observation needs an observing kind, not {kind!r}")
    if not str(observation or "").strip():
        raise ContractError("an observation must record what was actually observed")
    path = Path(str(artifact.get("path", "")))
    if record_value.get("capture_method") == "declared-observer":
        raise ContractError(
            "an externally declared artifact cannot be promoted to OBSERVED by the engine; "
            "the ceiling for declared evidence is RENDERED"
        )
    allowed_roots: list[Path] = []
    project_root = str(state.get("project", "") or "")
    if project_root:
        allowed_roots.append(Path(project_root))
    run_root = evidence_root(state)
    if run_root is not None:
        allowed_roots.append(run_root)
    path = contracts.contained_evidence_path_any(
        path, allowed_roots, label="an observation artifact",
        describe="a permitted root (the project or the run's capture root)",
    )
    if not path.is_file():
        raise ContractError(f"observation artifact does not exist: {path}")
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if str(artifact.get("sha256", "")) != digest:
        raise ContractError("the observation artifact does not match its declared digest")
    candidate = dict(record_value)
    candidate["state"] = "OBSERVED"
    candidate["observation"] = str(observation)
    candidate["observed_at"] = contracts.utc_now()
    candidate["observation_artifact"] = {"path": str(path.resolve()), "sha256": digest, "kind": kind}
    candidate["observation_execution"] = str(execution)
    problems = contracts.rendered_evidence_problems(candidate)
    if problems:
        raise ContractError("rendered evidence is malformed: " + "; ".join(problems))
    record_value.update(candidate)
    return record_value


def verify(
    state: dict,
    evidence_id: str,
    *,
    verification_execution: str,
    reproduced_artifact: Mapping | None = None,
    method: str,
    tolerance: str = "exact",
    reproduced_sha256: str = "",
) -> dict:
    """Promote to ``VERIFIED`` by re-production in an independent execution.

    AR-203 requires the *artifact* the verifier re-produced, not only a digest:
    the engine re-hashes that file itself, requires it to be a different file
    than the original capture, and requires its digest to equal the captured
    artifact's. Re-opening or re-hashing the original file in a second execution
    is not re-production and is refused. The verifying execution must be an
    engine-created execution record in this run, and a verification record is
    written so the claim has a currentness-aware evidence trail.
    """
    record_value = _require(state, evidence_id)
    if strength(str(record_value.get("state", ""))) < strength("RENDERED"):
        raise ContractError("only captured evidence can be verified by re-production")
    if str(record_value.get("capture_method")) == "declared-observer":
        raise ContractError(
            "an externally declared artifact cannot be verified by re-production; re-hashing the "
            "same file in a second execution is not independent re-production, and the ceiling for "
            "declared evidence is RENDERED"
        )
    from . import provenance, verification as verification_module

    verifier = provenance.require_engine_execution(
        state, verification_execution, label="a rendered-evidence verification",
    )
    verification_execution = str(verifier.get("execution_id", ""))
    capture_execution = str(record_value.get("capture_execution", ""))
    if not capture_execution:
        raise ContractError(
            "this rendered evidence names no engine-created capture execution, so nothing can be "
            "re-produced independently of it"
        )
    provenance.require_engine_execution(
        state, capture_execution, label="the capture execution this verification re-produces",
    )
    if capture_execution == verification_execution:
        raise ContractError(
            "the verifying execution is the capturing execution; re-production by the same "
            "execution is not independent verification"
        )
    if not str(method or "").strip():
        raise ContractError("verification needs a recorded method")
    artifact = record_value.get("artifact") if isinstance(record_value.get("artifact"), Mapping) else {}
    expected = str(artifact.get("sha256", ""))
    if not isinstance(reproduced_artifact, Mapping) or not str(reproduced_artifact.get("path", "")):
        raise ContractError(
            "verification needs the artifact the verifier re-produced (a path the engine re-hashes), "
            "not only a digest"
        )
    reproduced_path = Path(str(reproduced_artifact.get("path", "")))
    if not reproduced_path.is_file():
        raise ContractError(f"the re-produced artifact does not exist: {reproduced_path}")
    reproduced_path = permitted_evidence_path(state, reproduced_path, label="a re-produced artifact")
    if str(reproduced_path) == str(Path(str(artifact.get("path", ""))).resolve()):
        raise ContractError(
            "the re-produced artifact is the captured artifact itself; re-hashing one file is not "
            "re-production"
        )
    actual = hashlib.sha256(reproduced_path.read_bytes()).hexdigest()
    if reproduced_sha256 and str(reproduced_sha256) != actual:
        raise ContractError("the declared reproduction digest does not match the re-produced artifact")
    if actual != expected:
        raise ContractError(
            "the re-produced artifact does not match the captured artifact; a mismatch is a finding, "
            "not a verification"
        )
    revision = str(record_value.get("revision_hash", ""))
    dependencies = verification_dependencies(record_value)
    verification_record = verification_module.create(
        state,
        subject=str(evidence_id),
        subject_type="rendered-evidence",
        claim=f"the rendered artifact {expected[:12]} is re-producible from revision {revision[:12]}",
        level="INDEPENDENTLY_REPRODUCED",
        method=str(method),
        execution_id=capture_execution,
        verifier_execution_id=verification_execution,
        revision=revision,
        evidence=[{"path": str(artifact.get("path", "")), "sha256": expected}],
        reproduced_artifact={"path": str(reproduced_path), "sha256": actual},
        dependencies=dependencies,
        limitations=[
            "re-production proves the capture pipeline is deterministic for the recorded parameters; "
            "it does not prove the rendering is aesthetically or functionally correct",
        ],
    )
    if str(verification_record.get("freshness", "")) == "CURRENT" and revision:
        verification_record["level"] = "VERIFIED"
        problems = contracts.verification_record_problems(verification_record)
        if problems:
            raise ContractError("verification record is malformed: " + "; ".join(problems))
    candidate = dict(record_value)
    candidate["state"] = "VERIFIED"
    candidate["verification_execution"] = verification_execution
    candidate["prior_evidence_ids"] = [str(record_value.get("evidence_id"))]
    candidate["verification_id"] = str(verification_record.get("verification_id", ""))
    candidate["verification"] = {
        "method": str(method),
        "tolerance": str(tolerance),
        "reproduced_sha256": str(actual),
        "reproduced_artifact": {"path": str(reproduced_path), "sha256": str(actual)},
        "verified_at": contracts.utc_now(),
        "dependencies": dict(dependencies),
    }
    problems = contracts.rendered_evidence_problems(candidate)
    if problems:
        raise ContractError("rendered evidence is malformed: " + "; ".join(problems))
    record_value.update(candidate)
    return record_value


def verification_dependencies(record: Mapping) -> dict:
    """The dependency fingerprints a rendered verification is bound to.

    Capture parameters, viewport, method, adapter, artifact digest and revision:
    when any of them changes, the verification's currentness must be
    re-evaluated rather than inherited.
    """
    artifact = record.get("artifact") if isinstance(record.get("artifact"), Mapping) else {}
    parameters = {
        "kind": str(record.get("kind", "")),
        "capture_method": str(record.get("capture_method", "")),
        "adapter": str(record.get("adapter", "")),
        "viewport": dict(record.get("viewport") or {}),
        "environment": dict(record.get("environment") or {}),
    }
    return {
        "source-revision": str(record.get("revision_hash", "")),
        "artifact": str(artifact.get("sha256", "")),
        "capture-parameters": hashlib.sha256(
            json.dumps(parameters, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
        ).hexdigest(),
        "capture-execution": str(record.get("capture_execution", "")),
    }


def verification_currentness(
    state: dict,
    evidence_id: str,
    *,
    revision_hash: str = "",
    current_dependencies: Mapping | None = None,
) -> dict:
    """Re-evaluate a rendered verification against the evidence record as it is now.

    A changed capture parameter, a changed revision or a changed artifact makes
    the verification stale; a missing verification record makes it UNKNOWN.
    """
    from . import verification as verification_module

    record_value = _require(state, evidence_id)
    verification_id = str(record_value.get("verification_id", ""))
    if not verification_id:
        return {"state": "UNKNOWN", "problems": ["this evidence has no verification record"], "verification_id": ""}
    verification_record = verification_module.verification(state, verification_id)
    if verification_record is None:
        return {
            "state": "UNKNOWN",
            "problems": [f"the verification record {verification_id} no longer exists"],
            "verification_id": verification_id,
        }
    current = dict(current_dependencies or verification_dependencies(record_value))
    if revision_hash:
        current["source-revision"] = str(revision_hash)
    verdict = verification_module.freshness_of(verification_record, current=current)
    return {"state": verdict["state"], "problems": verdict["problems"], "verification_id": verification_id}


def mark_unverified(
    state: dict,
    *,
    task_id: str,
    revision_hash: str,
    requirement_id: str,
    blocker: str,
    viewport: Mapping | None = None,
) -> dict:
    """Record that a required observation was *not* made. Never a silent pass."""
    if not str(blocker or "").strip():
        raise ContractError("unverified evidence must record the blocker that prevented capture")
    record_value = {
        "schema_version": contracts.SCHEMA_DESIGN,
        "evidence_id": contracts.new_record_id("rnd"),
        "run_id": str(state.get("run_id", "")),
        "task_id": str(task_id),
        "revision_hash": str(revision_hash or "0" * 64),
        "requirement_id": str(requirement_id),
        "direction_id": "",
        "kind": "source",
        "state": "UNVERIFIED",
        "capture_method": "declared-observer",
        "adapter": "",
        "capture_execution": "",
        "verification_execution": "",
        "prior_evidence_ids": [],
        "observation": "",
        "viewport": dict(viewport or {"width": "unverified"}),
        "environment": {},
        "artifact": {},
        "extra": {},
        "comparison": {},
        "blocker": str(blocker),
        "captured_at": contracts.utc_now(),
        "provenance": {"created_by": "engine", "method": "not-captured"},
    }
    problems = contracts.rendered_evidence_problems(record_value)
    if problems:
        raise ContractError("unverified evidence is malformed: " + "; ".join(problems))
    contracts.require_design_capacity(state, "rendered_evidence")
    state.setdefault("rendered_evidence", []).append(record_value)
    return record_value


def currentness_problems(
    record: Mapping,
    *,
    revision_hash: str = "",
    require_captured: bool = False,
    verification_state: Mapping | None = None,
) -> list[str]:
    """Whether one evidence record is still current. One implementation of the rule.

    ``require_captured`` distinguishes the two questions callers actually ask:
    staleness ("a capture happened but no longer holds") and closure ("may this
    record close a requirement at all"). An ``UNVERIFIED`` record is not stale —
    nothing was captured to become stale — but it can never close anything, which
    is why the difference is a named parameter rather than two copies of the
    digest check.

    ``verification_state`` is the caller's evaluated
    :func:`verification_currentness` verdict for this record. When a record is
    ``VERIFIED`` and that verdict is not ``CURRENT``, the record does not answer
    as verified any more.
    """
    problems: list[str] = []
    if require_captured and str(record.get("state")) == "UNVERIFIED":
        problems.append("the evidence was never captured")
    problems.extend(_verify_artifact(record))
    if revision_hash and str(record.get("revision_hash", "")) != str(revision_hash):
        problems.append("rendered evidence was captured for a different revision")
    if str(record.get("state")) == "VERIFIED" and verification_state is not None:
        state_name = str(verification_state.get("state", ""))
        if state_name != "CURRENT":
            reasons = "; ".join(str(item) for item in (verification_state.get("problems") or []))
            problems.append(
                f"the rendered verification is {state_name or 'UNKNOWN'}"
                + (f": {reasons}" if reasons else "")
            )
    return problems


# ------------------------------------------------------------ staleness

def stale_records(state: dict, *, revision_hash: str = "") -> list[dict]:
    """Evidence whose artifact changed, whose revision no longer matches, or whose
    verification is no longer current."""
    stale: list[dict] = []
    for record_value in evidence(state):
        if str(record_value.get("state")) == "UNVERIFIED":
            continue
        verification_state = None
        if str(record_value.get("state")) == "VERIFIED":
            verification_state = verification_currentness(
                state, str(record_value.get("evidence_id", "")), revision_hash=revision_hash,
            )
        reasons = currentness_problems(
            record_value, revision_hash=revision_hash, verification_state=verification_state,
        )
        if reasons:
            stale.append({"evidence_id": record_value.get("evidence_id"), "reasons": reasons})
    return stale


def for_requirement(state: dict, requirement_id: str) -> list[dict]:
    return [record for record in evidence(state) if str(record.get("requirement_id", "")) == str(requirement_id)]


def strongest(state: dict, requirement_id: str, *, viewport_width: str = "") -> dict:
    """The strongest current evidence for a requirement, optionally at a viewport."""
    rows = for_requirement(state, requirement_id)
    if viewport_width:
        rows = [
            record for record in rows
            if str((record.get("viewport") or {}).get("width", "")) == str(viewport_width)
        ]
    if not rows:
        return {}
    return max(rows, key=lambda record: strength(str(record.get("state", ""))))


def summarise(state: dict) -> dict:
    """Deterministic rendered-evidence counters."""
    records = evidence(state)
    counts = {value.lower(): 0 for value in RENDERED_EVIDENCE_STATES}
    artifacts = 0
    for record in records:
        counts[str(record.get("state", "")).lower()] = counts.get(str(record.get("state", "")).lower(), 0) + 1
        if record.get("artifact"):
            artifacts += 1
    return {
        "records": len(records),
        "states": counts,
        "artifacts": artifacts,
        "stale": len(stale_records(state)),
        "methods": sorted({str(record.get("capture_method", "")) for record in records if record.get("capture_method")}),
    }


def describe(record: Mapping) -> str:
    return (
        f"{record.get('evidence_id')} {record.get('state')} {record.get('kind')} "
        f"at {((record.get('viewport') or {}).get('width'))}"
    )


def _slug(value: str) -> str:
    text = re.sub(r"[^A-Za-z0-9._-]+", "-", str(value or "")).strip("-")
    return text or "root"


__all__ = [
    "CAPTURE_DIR",
    "MANIFEST_NAME",
    "OBSERVING_KINDS",
    "EVIDENCE_ORDER",
    "strength",
    "capture_root",
    "evidence_root",
    "permitted_evidence_path",
    "CaptureArtifact",
    "CaptureAdapter",
    "OfflineFixtureAdapter",
    "DeclaredObserverAdapter",
    "LocalBrowserAdapter",
    "default_adapters",
    "capability_matrix",
    "evidence",
    "by_id",
    "record",
    "record_source_suggests",
    "observe",
    "verify",
    "mark_unverified",
    "currentness_problems",
    "stale_records",
    "verification_dependencies",
    "verification_currentness",
    "for_requirement",
    "strongest",
    "summarise",
    "describe",
]
