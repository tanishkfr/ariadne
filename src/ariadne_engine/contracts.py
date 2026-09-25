"""Versioned record contracts for the AR-201 orchestration core.

Two schemas exist in AR-201 and they are deliberately different things:

``SCHEMA_RUN``
    The version of the ``ariadne-run.json`` *file*. It stays ``1``: AR-201 adds
    fields to the run state, it does not replace the on-disk format. Keeping the
    file version unchanged means a run written by this runtime is still readable
    by the published v1.6.7 runtime (which hard-refuses any other version), and
    every original benchmark case keeps its recorded verdict.

``SCHEMA_RECORD``
    The version of the *records* this engine writes inside the run state
    (approvals, migration history, transitions, review records). Records carry
    their own ``schema_version`` so a reader can accept an older record set
    while refusing an unknown one.

Authority model
---------------
An approval binds an authorizing identity to one operation on one subject at
one revision:

* ``gate``           the operation class (G1 direction, G2 dependency, G3 review)
* ``subject_type`` / ``subject_id``
                     the target the operation applies to
* ``revision_hash``  a digest over a *declared field list* of the subject
* ``channel``        only ``human-cli`` satisfies a gate
* ``identity``       an operator-supplied label, recorded verbatim and not verified
* ``consumed_by``    operations that already spent a single-use approval

Declared field lists (the reason a cosmetic edit does not, and a semantic edit
does, invalidate an approval):

``design-direction``
    the DESIGN.md design-thesis line plus the normalised bodies of the
    ``Signature moment``, ``Responsive behaviour`` and ``Asset direction``
    sections. The creative-operations requirement ids are a deterministic
    function of exactly those sections (``creative-operations.derive_requirements``),
    so hashing the sections captures every edit that could change them while
    remaining computable before G1 (the operations ledger only exists after the
    direction is locked).

``handoff``
    the handoff file's sha256 plus the worker contract's scope rows and
    validation rows, which are what a dependency approval is really about.

``review``
    the reviewed S5 packet id, its ``packet_sha256``, the sha256 of the
    recorded review judgement and the reviewer identity. An approval for one
    review never authorizes a different review or revision.
"""

from __future__ import annotations

import fnmatch
import hashlib
import json
import os
import re
import uuid
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

# --------------------------------------------------------------------- schema

SCHEMA_RUN = 1
"""The ``ariadne-run.json`` file version this runtime writes."""

READABLE_RUN_SCHEMAS = (1,)
"""Run-state file versions this runtime can read. Anything else is refused."""

SCHEMA_RECORD = 2
"""The record contract version this runtime writes inside the run state."""

READABLE_RECORD_SCHEMAS = (1, 2)
"""Record contract versions this runtime can read."""

SCHEMA_ADAPTIVE = 1
"""The AR-202 record family (execution, routing, context, recovery, failure, event).

These records are versioned independently of ``SCHEMA_RECORD`` on purpose: an
AR-201 run state carries no adaptive records and stays readable and continuable
without a migration, and an adaptive record can evolve without moving the
authorization contract every AR-201 reader checks.
"""

READABLE_ADAPTIVE_SCHEMAS = (1,)
"""Adaptive record versions this runtime can read."""

ADAPTIVE_CONTRACT = "ariadne-adaptive-1"
"""Marker recorded in ``state["engine"]["adaptive_contract"]`` when adaptive records exist."""

POLICY_VERSION = "ar-202-policy-1"
"""The routing/context/recovery policy version recorded with every adaptive decision."""

ENGINE_CONTRACT = "ariadne-engine-1"
"""Marker written into every state this runtime persists (legacy detection)."""

APPROVAL_CHANNEL_HUMAN = "human-cli"
"""The only channel that satisfies a gate."""

APPROVAL_CHANNELS = ("human-cli", "worker-cli", "engine-api", "imported")
"""Channels that may appear on a record. Only ``human-cli`` grants authority."""

GATE_SUBJECT_TYPES = {
    "G1": "design-direction",
    "G2": "handoff",
    "G3": "review",
    "G1D": "design-direction-record",
}
"""Gate operations the engine enforces. G4/G5 stay human/operator actions.

``G1D`` (AR-202D) authorizes one *engine-created design-direction record* — the
constraint record AR-202D implementation work is checked against — on the human
channel only, bound to the record, its revision fingerprint, its task and its
scope. It is a distinct gate on purpose: ``G1`` authorizes ``DESIGN.md`` and a
``G1D`` record can never be substituted for it (or the reverse), so
``gate_satisfied``'s "latest approval wins" selection is untouched.
"""

SUBJECT_TYPES = ("design-direction", "handoff", "review", "design-direction-record")

REVISION_FIELDS: dict[str, tuple[str, ...]] = {
    "design-direction": (
        "design-thesis",
        "signature-moment",
        "responsive-behaviour",
        "asset-direction",
    ),
    "handoff": ("handoff-sha256", "scope-rows", "validation-rows"),
    "review": (
        "packet-id",
        "packet-sha256",
        "review-judgement-sha256",
        "reviewer-identity",
        "validated-revision",
    ),
    "design-direction-record": (
        "direction-id",
        "task-id",
        "scope",
        "constrained-body",
    ),
}
"""Declared field lists per subject type. Keep small, ordered and documented.

``design-direction-record`` hashes the record's id, the task it constrains, the
scope it applies to and the normalised bodies of every constraining section
(hierarchy, interaction, visual, content, constraints, accessibility,
responsive, approved deviations). Editing any constraining sentence after
approval therefore invalidates the approval rather than silently inheriting it,
while a cosmetic change outside those sections does not.
"""

TRANSITION_KINDS = ("stage", "worker-lifecycle")

REVIEW_KINDS = ("experience", "technical")


# --------------------------------------------------------------------- errors

class EngineError(RuntimeError):
    """Base class for engine refusals. The runtime reports these as STOPPED."""


class ContractError(EngineError):
    """The request or the artifact is malformed; nothing was changed."""


class StaleSchema(EngineError):
    """A stored record cannot be read under the running schema."""


class InvalidTransition(EngineError):
    """The requested transition is not in the declarative table."""


class PolicyRefusal(EngineError):
    """The transition is structurally legal but a precondition fails."""

    def __init__(self, problems: Iterable[str]):
        self.problems = [problem for problem in problems if problem]
        super().__init__("; ".join(self.problems) or "policy precondition failed")


class UnauthorizedApproval(EngineError):
    """An approval was requested or used outside its authorized scope."""


# ----------------------------------------------------------------- timestamp

def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def normalise(value: str) -> str:
    """Whitespace-insensitive form used by every declared-field fingerprint."""
    return re.sub(r"\s+", " ", (value or "").strip())


# ----------------------------------------------------------------- paths
#
# Containment and scope matching are trust boundaries, so they live in one
# place. Both operate on the *resolved* filesystem path (symlinks, junctions,
# ``..`` and separators are already folded away) and compare case-insensitively
# on Windows, where the filesystem itself does. A string-prefix test on the
# unresolved input is exactly the bug these helpers exist to prevent.

def resolved_within(path: Any, root: Any) -> Path | None:
    """The resolved path when it is inside ``root``; ``None`` when it is not.

    ``None`` means "outside the permitted root" and callers refuse. The check is
    made after resolution, so ``..`` traversal, absolute paths, drive-qualified
    paths and symlinks or junctions that leave the root are all caught by the
    same rule.
    """
    target = Path(str(path)).resolve()
    base = Path(str(root)).resolve()
    try:
        target.relative_to(base)
        return target
    except ValueError:
        pass
    if os.name == "nt":
        folded_target = os.path.normcase(str(target)).rstrip("\\/")
        folded_base = os.path.normcase(str(base)).rstrip("\\/")
        if folded_target == folded_base or folded_target.startswith(folded_base + "\\"):
            return target
    return None


def path_matches(path: str, pattern: str) -> bool:
    """The runtime's path-scope rule: exact, ``fnmatch`` glob, or ``/**`` prefix.

    ``src/app.py`` matches ``src/app.py`` and ``src/**`` but never ``src``
    (a bare directory name does not authorize its contents) and never
    ``srcx/evil.py`` or ``vendor/src/app.py``. This is the same rule the worker
    scope check applies, kept in one place so the two cannot drift.
    """
    candidate = str(path).replace("\\", "/").lstrip("./")
    wanted = str(pattern).replace("\\", "/").lstrip("./")
    if fnmatch.fnmatchcase(candidate, wanted):
        return True
    return bool(wanted.endswith("/**")) and candidate.startswith(wanted[:-3].rstrip("/") + "/")


def contained_evidence_path(path: Any, root: Any, *, label: str = "evidence") -> Path:
    """Resolve ``path`` and require it to be inside ``root``, or refuse.

    Refusal happens before the caller hashes, stores or trusts anything, so an
    out-of-root artifact cannot become provenance by being cited.
    """
    resolved = resolved_within(path, root)
    if resolved is None:
        raise ContractError(
            f"{label} must be inside the permitted root: {Path(str(path))} is not inside {Path(str(root))}"
        )
    return resolved


def contained_evidence_path_any(path: Any, roots: Iterable[Any], *, label: str = "evidence",
                                describe: str = "a permitted root") -> Path:
    """The first permitted root that contains ``path``, or a refusal.

    The multi-root form of :func:`contained_evidence_path`. A caller with more
    than one permitted surface (the project *or* the run's capture directory)
    uses this instead of open-coding the loop, so the containment rule and its
    refusal live in one place.
    """
    candidates = [root for root in roots if root is not None]
    if not candidates:
        raise ContractError(f"no permitted root is configured for {label}")
    for root in candidates:
        resolved = resolved_within(path, root)
        if resolved is not None:
            return resolved
    raise ContractError(f"{label} must be inside {describe}: {Path(str(path))} is not")


def permitted_project_root(state: Mapping[str, Any], *, label: str) -> Path:
    """The run's project root, or a refusal naming what needed it."""
    project_root = str(state.get("project", "") or "")
    if not project_root:
        raise ContractError(
            f"the run state names no project, so {label} has no permitted root and cannot be trusted"
        )
    return Path(project_root)


def digest_fields(subject_type: str, values: Mapping[str, Any]) -> str:
    """Hash a declared field list; unknown field names are rejected."""
    declared = REVISION_FIELDS.get(subject_type)
    if declared is None:
        raise ContractError(f"unknown approval subject type: {subject_type}")
    unknown = sorted(set(values) - set(declared))
    if unknown:
        raise ContractError(
            f"{subject_type} fingerprint has undeclared field(s): " + ", ".join(unknown)
        )
    payload = {name: normalise(str(values.get(name, ""))) for name in declared}
    encoded = json.dumps(
        {"subject_type": subject_type, "fields": payload}, sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def new_approval_id() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"apv_{stamp}_{uuid.uuid4().hex[:8]}"


@dataclass(frozen=True)
class Subject:
    """What an approval binds to. ``detail`` is human-readable provenance."""

    subject_type: str
    subject_id: str
    revision_hash: str
    detail: str = ""
    fields: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.subject_type not in SUBJECT_TYPES:
            raise ContractError(f"unknown approval subject type: {self.subject_type}")
        if not self.subject_id:
            raise ContractError("approval subject needs an id")
        if not re.fullmatch(r"[0-9a-f]{64}", self.revision_hash or ""):
            raise ContractError("approval subject revision must be a sha256 digest")

    def as_record(self) -> dict:
        return {
            "type": self.subject_type,
            "id": self.subject_id,
            "revision_hash": self.revision_hash,
            "detail": self.detail,
        }


@dataclass(frozen=True)
class Approval:
    """One recorded authorization decision."""

    schema_version: int
    approval_id: str
    gate: str
    subject_type: str
    subject_id: str
    revision_hash: str
    identity: str
    channel: str
    note: str = ""
    recorded_at: str = ""
    stage: str = ""
    packet_id: str = ""
    consumed_by: tuple[str, ...] = ()

    def as_record(self) -> dict:
        return {
            "schema_version": self.schema_version,
            "approval_id": self.approval_id,
            "gate": self.gate,
            "subject_type": self.subject_type,
            "subject_id": self.subject_id,
            "revision_hash": self.revision_hash,
            "identity": self.identity,
            "channel": self.channel,
            "note": self.note,
            "recorded_at": self.recorded_at,
            "stage": self.stage,
            "packet_id": self.packet_id,
            "consumed_by": list(self.consumed_by),
        }

    @classmethod
    def from_record(cls, value: Mapping[str, Any]) -> "Approval":
        if not isinstance(value, Mapping):
            raise ContractError("approval record is not an object")
        consumed = value.get("consumed_by") or ()
        if isinstance(consumed, str):
            consumed = (consumed,)
        return cls(
            schema_version=int(value.get("schema_version", 0)),
            approval_id=str(value.get("approval_id", "")),
            gate=str(value.get("gate", "")),
            subject_type=str(value.get("subject_type", "")),
            subject_id=str(value.get("subject_id", "")),
            revision_hash=str(value.get("revision_hash", "")),
            identity=str(value.get("identity", "")),
            channel=str(value.get("channel", "")),
            note=str(value.get("note", "")),
            recorded_at=str(value.get("recorded_at", "")),
            stage=str(value.get("stage", "")),
            packet_id=str(value.get("packet_id", "")),
            consumed_by=tuple(str(item) for item in consumed),
        )

    def consumed(self, operation_id: str) -> "Approval":
        return replace(self, consumed_by=tuple(self.consumed_by) + (operation_id,))


def approval_problems(record: Mapping[str, Any]) -> list[str]:
    """Structural validation of a stored approval record (fail closed)."""
    problems: list[str] = []
    if not isinstance(record, Mapping):
        return ["approval record is not an object"]
    schema = record.get("schema_version")
    if schema not in READABLE_RECORD_SCHEMAS:
        problems.append(f"approval record schema is unsupported: {schema!r}")
    approval_id = str(record.get("approval_id", ""))
    if not re.fullmatch(r"apv_[0-9TZ]+_[0-9a-f]{8}", approval_id):
        problems.append("approval record has a malformed approval id")
    gate = str(record.get("gate", ""))
    if gate not in GATE_SUBJECT_TYPES:
        problems.append(f"approval record names an unsupported gate: {gate or 'missing'}")
    subject_type = str(record.get("subject_type", ""))
    if subject_type not in SUBJECT_TYPES:
        problems.append(f"approval record has an unsupported subject type: {subject_type or 'missing'}")
    if not str(record.get("subject_id", "")):
        problems.append("approval record has no subject id")
    if not re.fullmatch(r"[0-9a-f]{64}", str(record.get("revision_hash", ""))):
        problems.append("approval record has no revision fingerprint")
    if not str(record.get("identity", "")).strip():
        problems.append("approval record has no recorded identity")
    channel = str(record.get("channel", ""))
    if channel not in APPROVAL_CHANNELS:
        problems.append(f"approval record has an unsupported channel: {channel or 'missing'}")
    if not str(record.get("recorded_at", "")).strip():
        problems.append("approval record has no timestamp")
    return problems


def approval_gate_problems(record: Mapping[str, Any], subject: Subject | None = None) -> list[str]:
    """Binding problems between a stored approval and the current subject."""
    problems = approval_problems(record)
    if subject is None:
        return problems
    if str(record.get("gate", "")) in GATE_SUBJECT_TYPES:
        expected = GATE_SUBJECT_TYPES[str(record["gate"])]
        got = str(record.get("subject_type", ""))
        if got != expected:
            problems.append(
                f"{record.get('gate')} approval is bound to {got or 'nothing'}, not {expected}"
            )
    if str(record.get("subject_type", "")) != subject.subject_type:
        problems.append("approval subject type does not match this operation")
    elif str(record.get("subject_id", "")) != subject.subject_id:
        problems.append("approval was recorded for a different target")
    elif str(record.get("revision_hash", "")) != subject.revision_hash:
        problems.append(
            "approval is stale: the subject changed after it was recorded"
        )
    return list(dict.fromkeys(problems))


@dataclass(frozen=True)
class TransitionRequest:
    """One proposed state change, checked by the transition table."""

    kind: str
    to: str
    reason: str
    evidence: tuple[str, ...] = ()
    packet: dict | None = None
    fields: Mapping[str, str] = field(default_factory=dict)
    actor: str = ""
    operation: str = ""

    def __post_init__(self) -> None:
        if self.kind not in TRANSITION_KINDS:
            raise ContractError(f"unsupported transition kind: {self.kind}")


@dataclass(frozen=True)
class ReviewRecord:
    """Evidence-bound review outcome (technical or experience oriented)."""

    schema_version: int
    review_id: str
    run_id: str
    packet_id: str
    review_kind: str
    reviewer_identity: str
    reviewer_role: str
    context_digest: str
    reviewed_revision: str
    requirements: tuple[str, ...]
    evidence: tuple[str, ...]
    findings: tuple[str, ...]
    outcome: str
    recommendation: str
    recorded_at: str
    independent: bool = True
    reviewer_execution: str = ""
    implementing_execution: str = ""

    def as_record(self) -> dict:
        return {
            "schema_version": self.schema_version,
            "review_id": self.review_id,
            "run_id": self.run_id,
            "packet_id": self.packet_id,
            "review_kind": self.review_kind,
            "reviewer_identity": self.reviewer_identity,
            "reviewer_role": self.reviewer_role,
            "context_digest": self.context_digest,
            "reviewed_revision": self.reviewed_revision,
            "requirements": list(self.requirements),
            "evidence": list(self.evidence),
            "findings": list(self.findings),
            "outcome": self.outcome,
            "recommendation": self.recommendation,
            "recorded_at": self.recorded_at,
            "independent": self.independent,
            "execution_binding": "engine" if self.reviewer_execution and self.implementing_execution else "",
            "reviewer_execution": self.reviewer_execution,
            "implementing_execution": self.implementing_execution,
        }

    @classmethod
    def from_record(cls, value: Mapping[str, Any]) -> "ReviewRecord":
        return cls(
            schema_version=int(value.get("schema_version", 0)),
            review_id=str(value.get("review_id", "")),
            run_id=str(value.get("run_id", "")),
            packet_id=str(value.get("packet_id", "")),
            review_kind=str(value.get("review_kind", "")),
            reviewer_identity=str(value.get("reviewer_identity", "")),
            reviewer_role=str(value.get("reviewer_role", "")),
            context_digest=str(value.get("context_digest", "")),
            reviewed_revision=str(value.get("reviewed_revision", "")),
            requirements=tuple(str(item) for item in value.get("requirements", ())),
            evidence=tuple(str(item) for item in value.get("evidence", ())),
            findings=tuple(str(item) for item in value.get("findings", ())),
            outcome=str(value.get("outcome", "")),
            recommendation=str(value.get("recommendation", "")),
            recorded_at=str(value.get("recorded_at", "")),
            independent=bool(value.get("independent", True)),
            reviewer_execution=str(value.get("reviewer_execution", "")),
            implementing_execution=str(value.get("implementing_execution", "")),
        )


# ------------------------------------------------------- AR-202 adaptive records

EXECUTION_STATES = (
    "REQUESTED",
    "CREATED",
    "STARTED",
    "OBSERVED",
    "COMPLETED",
    "FAILED",
    "UNKNOWN",
)
"""Execution identity lifecycle. ``OBSERVED`` means the runtime could report the
execution independently; a runtime that cannot report identity never claims it."""

EXECUTION_ROLES = ("reasoner", "implementer", "validator", "reviewer")

FAILURE_CLASSES = (
    "IMPLEMENTATION_FAILURE",
    "VALIDATION_FAILURE",
    "REVIEW_FAILURE",
    "AUTHORIZATION_FAILURE",
    "CAPABILITY_FAILURE",
    "PROVIDER_FAILURE",
    "TIMEOUT",
    "ENVIRONMENT_FAILURE",
    "CONTEXT_FAILURE",
    "STALE_REVISION",
    "CONFLICT",
    "INTERRUPTED",
    "DESIGN_FAILURE",
    "UNKNOWN",
)
"""The AR-202 failure taxonomy. Every class carries explicit retry/strategy and
escalation flags in :mod:`ariadne_engine.execution`; an unmapped source is UNKNOWN.

``DESIGN_FAILURE`` is the one class AR-202D adds: a design-workflow limit or
refusal that is not an implementation, validation, review, capability, context or
authorization failure. Everything else design-specific maps onto an existing
class (see ``execution.DESIGN_SOURCE_KINDS``)."""

CONTEXT_REASONS = (
    "REQUIRED_BY_STAGE",
    "REQUIRED_BY_TASK_TYPE",
    "RELEVANT_CHANGED_FILE",
    "REQUIRED_BY_VALIDATOR",
    "REQUIRED_BY_REVIEW",
    "UNCHANGED_CACHED_INPUT",
    "IRRELEVANT_TO_TASK",
    "FORBIDDEN_FOR_STAGE",
    "MISSING",
    "STALE",
    "SUPERSEDED",
    "OPTIONAL_NOT_SELECTED",
    "DEPENDENCY_OF_INCLUDED_SOURCE",
    "UNAVAILABLE",
)
"""Machine-readable reasons for a context inclusion/omission decision."""

ROUTING_RULES = (
    "capability-required",
    "policy-excluded",
    "sufficient-capability",
    "escalation-required",
    "repeat-failure-avoided",
    "no-authorized-candidate",
    "declared-default",
    "strategy-continuity",
    "design-evidence-unavailable",
)
"""Explicit routing rule ids. A route names the rule that decided it.

``design-evidence-unavailable`` is the AR-202D rule: a design step needs evidence
(visual inspection, interaction inspection, browser observation, critique) and no
declared adapter can supply it, so the route is blocked rather than guessed. A
capability is never inferred from a model or vendor name.
"""

RECOVERY_ACTIONS = (
    "adopt-packet",
    "discard-packet",
    "clear-interrupted-write",
    "abandon-execution",
)
"""Recovery actions AR-202 can apply. Everything else is refused and escalated."""


def new_execution_id() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"exe_{stamp}_{uuid.uuid4().hex[:8]}"


def new_record_id(prefix: str) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{prefix}_{stamp}_{uuid.uuid4().hex[:8]}"


def _non_empty(record: Mapping[str, Any], name: str, problems: list[str]) -> str:
    value = str(record.get(name, "")).strip()
    if not value:
        problems.append(f"adaptive record has no {name}")
    return value


def adaptive_schema_problems(record: Mapping[str, Any]) -> list[str]:
    """Shared structural validation for every AR-202 record family."""
    problems: list[str] = []
    if not isinstance(record, Mapping):
        return ["adaptive record is not an object"]
    if record.get("schema_version") not in READABLE_ADAPTIVE_SCHEMAS:
        problems.append(f"adaptive record schema is unsupported: {record.get('schema_version')!r}")
    return problems


def execution_problems(record: Mapping[str, Any]) -> list[str]:
    """Structural validation of an execution identity record (fail closed)."""
    problems = adaptive_schema_problems(record)
    if problems and not isinstance(record, Mapping):
        return problems
    if not re.fullmatch(r"exe_[0-9TZ]+_[0-9a-f]{8}", str(record.get("execution_id", ""))):
        problems.append("execution record has a malformed execution id")
    for name in ("run_id", "task_id", "adapter", "created_at"):
        _non_empty(record, name, problems)
    if str(record.get("role", "")) not in EXECUTION_ROLES:
        problems.append(f"execution record has an unsupported role: {record.get('role') or 'missing'}")
    if str(record.get("state", "")) not in EXECUTION_STATES:
        problems.append(f"execution record has an unsupported state: {record.get('state') or 'missing'}")
    if not re.fullmatch(r"[0-9a-f]{16,64}", str(record.get("nonce", ""))):
        problems.append("execution record has no nonce")
    revision = record.get("revision")
    if not isinstance(revision, Mapping) or not str(revision.get("revision_hash", "")):
        problems.append("execution record is not bound to a revision")
    provenance = record.get("provenance")
    if not isinstance(provenance, Mapping) or str(provenance.get("created_by", "")) != "engine":
        problems.append("execution record does not carry engine provenance")
    return problems


def failure_problems(record: Mapping[str, Any]) -> list[str]:
    """Structural validation of one classified failure."""
    problems = adaptive_schema_problems(record)
    if problems and not isinstance(record, Mapping):
        return problems
    if not re.fullmatch(r"fail_[0-9TZ]+_[0-9a-f]{8}", str(record.get("failure_id", ""))):
        problems.append("failure record has a malformed failure id")
    if str(record.get("class", "")) not in FAILURE_CLASSES:
        problems.append(f"failure record has an unsupported class: {record.get('class') or 'missing'}")
    for name in ("source", "operation", "recorded_at"):
        _non_empty(record, name, problems)
    if not isinstance(record.get("evidence"), list) or not record.get("evidence"):
        problems.append("failure record has no evidence")
    for name in ("retry_allowed", "strategy_change_allowed", "escalation_required"):
        if not isinstance(record.get(name), bool):
            problems.append(f"failure record needs a boolean {name}")
    kind = str(record.get("design_kind", "") or "")
    if kind and kind not in DESIGN_FAILURE_KINDS:
        problems.append(f"failure record names an unknown design kind: {kind}")
    classification = record.get("classification")
    if classification is not None:
        if not isinstance(classification, Mapping):
            problems.append("failure record classification is not an object")
        elif str(classification.get("source", "")) not in FAILURE_CLASSIFICATION_SOURCES:
            problems.append(
                f"failure record has an unsupported classification source: {classification.get('source') or 'missing'}"
            )
    return problems


def routing_problems(record: Mapping[str, Any]) -> list[str]:
    """Structural validation of one routing decision."""
    problems = adaptive_schema_problems(record)
    if problems and not isinstance(record, Mapping):
        return problems
    if not re.fullmatch(r"rte_[0-9TZ]+_[0-9a-f]{8}", str(record.get("decision_id", ""))):
        problems.append("routing record has a malformed decision id")
    for name in ("stage", "rule", "reason", "policy_version", "recorded_at"):
        _non_empty(record, name, problems)
    if str(record.get("rule", "")) not in ROUTING_RULES:
        problems.append(f"routing record names an unknown rule: {record.get('rule') or 'missing'}")
    if str(record.get("status", "")) not in ("selected", "fallback", "no-route", "blocked"):
        problems.append(f"routing record has an unsupported status: {record.get('status') or 'missing'}")
    candidates = record.get("candidates")
    if not isinstance(candidates, list) or not candidates:
        problems.append("routing record lists no candidates")
    return problems


def context_decision_problems(record: Mapping[str, Any]) -> list[str]:
    """Structural validation of one context decision."""
    problems = adaptive_schema_problems(record)
    if problems and not isinstance(record, Mapping):
        return problems
    if not re.fullmatch(r"ctx_[0-9TZ]+_[0-9a-f]{8}", str(record.get("decision_id", ""))):
        problems.append("context decision has a malformed decision id")
    for name in ("stage", "policy_version", "recorded_at"):
        _non_empty(record, name, problems)
    decisions = record.get("decisions")
    if not isinstance(decisions, list) or not decisions:
        problems.append("context decision lists no candidate sources")
        return problems
    for item in decisions:
        if not isinstance(item, Mapping):
            problems.append("context decision has a malformed source entry")
            continue
        if not str(item.get("path", "")).strip():
            problems.append("context decision source entry has no path")
        if str(item.get("decision", "")) not in ("included", "omitted"):
            problems.append("context decision source entry has no inclusion decision")
        if str(item.get("reason", "")) not in CONTEXT_REASONS:
            problems.append(
                f"context decision source entry has no machine-readable reason: {item.get('path')}"
            )
    return problems


def recovery_problems(record: Mapping[str, Any]) -> list[str]:
    """Structural validation of one recovery record."""
    problems = adaptive_schema_problems(record)
    if problems and not isinstance(record, Mapping):
        return problems
    if not re.fullmatch(r"rcv_[0-9TZ]+_[0-9a-f]{8}", str(record.get("recovery_id", ""))):
        problems.append("recovery record has a malformed recovery id")
    if str(record.get("action", "")) not in RECOVERY_ACTIONS:
        problems.append(f"recovery record has an unsupported action: {record.get('action') or 'missing'}")
    for name in ("identity", "reason", "recorded_at"):
        _non_empty(record, name, problems)
    if not str(record.get("target", "")).strip():
        problems.append("recovery record names no target")
    if str(record.get("outcome", "")) not in ("applied", "refused"):
        problems.append(f"recovery record has an unsupported outcome: {record.get('outcome') or 'missing'}")
    return problems


def review_problems(record: Mapping[str, Any]) -> list[str]:
    """Structural validation of a review record (fail closed)."""
    problems: list[str] = []
    if not isinstance(record, Mapping):
        return ["review record is not an object"]
    if record.get("schema_version") not in READABLE_RECORD_SCHEMAS:
        problems.append("review record schema is unsupported")
    if str(record.get("review_kind", "")) not in REVIEW_KINDS:
        problems.append("review record has an unsupported review kind")
    if not str(record.get("reviewer_identity", "")).strip():
        problems.append("review record has no reviewer identity")
    if not re.fullmatch(r"[0-9a-f]{64}", str(record.get("context_digest", ""))):
        problems.append("review record has no context digest")
    if not str(record.get("packet_id", "")):
        problems.append("review record has no packet id")
    if not str(record.get("recorded_at", "")).strip():
        problems.append("review record has no timestamp")
    if not record.get("evidence"):
        problems.append("review record has no evidence")
    if str(record.get("outcome", "")) not in ("passed", "failed", "blocked", "not-performed"):
        problems.append("review record has an unsupported outcome")
    reviewer_execution = str(record.get("reviewer_execution", ""))
    implementing_execution = str(record.get("implementing_execution", ""))
    if str(record.get("execution_binding", "")) != "engine":
        problems.append(
            "review record is not bound to an execution identity; a review recorded before the "
            "execution-binding contract must be re-recorded"
        )
    if not re.fullmatch(r"exe_[0-9TZ]+_[0-9a-f]{8}", reviewer_execution):
        problems.append("review record has no engine-created reviewer execution")
    if not re.fullmatch(r"exe_[0-9TZ]+_[0-9a-f]{8}", implementing_execution):
        problems.append("review record has no engine-created implementing execution")
    if reviewer_execution and reviewer_execution == implementing_execution:
        problems.append("review record names one execution as both reviewer and implementer")
    level = str(record.get("independence_level", "") or "")
    if level and level not in INDEPENDENCE_LEVELS:
        problems.append(f"review record names an unknown independence level: {level}")
    return problems


# ------------------------------------------------------------ AR-202D design

SCHEMA_DESIGN = 1
"""The AR-202D design-intelligence record family.

Versioned independently of ``SCHEMA_RECORD`` and ``SCHEMA_ADAPTIVE`` for the
same reason AR-202's family is: a run state written by an earlier milestone
carries no design records and stays readable, continuable and byte-compatible
without a migration.
"""

READABLE_DESIGN_SCHEMAS = (1,)
"""Design record versions this runtime can read."""

DESIGN_CONTRACT = "ariadne-design-1"
"""Marker recorded in ``state["engine"]["design_contract"]`` once design records exist."""

DESIGN_CHARACTERISTIC_VALUES = ("REQUIRED", "OPTIONAL", "NOT_REQUIRED", "UNKNOWN")
"""How strongly one design characteristic applies to a task.

``REQUIRED``     the task cannot be completed correctly without it;
``OPTIONAL``     it would help and the workflow may select it;
``NOT_REQUIRED`` evaluated deterministically and does not apply;
``UNKNOWN``      no evidence either way; never treated as required or absent.
"""

DESIGN_DEPTHS = ("NONE", "MINIMAL", "STANDARD", "DEEP")
"""The selected design-workflow depth. ``NONE`` means no design work runs."""

DESIGN_ORDINAL_VALUES = ("HIGH", "MEDIUM", "LOW", "UNKNOWN")
"""Ordinal values for the design characteristics that are not applicability flags.

``design_stakes`` and ``novelty`` are measures, not requirements: a task can need
design work without being high stakes, and the two questions must not be
collapsed into one vocabulary.
"""

DESIGN_MATURITY_VALUES = ("MATURE", "PARTIAL", "NONE", "UNKNOWN")
"""Project design-system maturity states."""

DESIGN_SCALE_VALUES = ("SMALL", "NEW_SURFACE", "UNKNOWN")
"""How large the declared task is.

``SMALL``       a bounded repair in declared scope: a fix, tweak or rename
``NEW_SURFACE`` the request builds or redesigns a surface
``UNKNOWN``     nothing in the request says

Scale is deliberately separate from relevance: a spacing fix *is* design work
and still must not trigger reference research.
"""

DESIGN_CHARACTERISTIC_DOMAINS: dict[str, tuple[str, ...]] = {
    "design_stakes": DESIGN_ORDINAL_VALUES,
    "novelty": DESIGN_ORDINAL_VALUES,
    "design_system_maturity": DESIGN_MATURITY_VALUES,
    "design_scale": DESIGN_SCALE_VALUES,
}
"""Per-characteristic allowed values. Anything unlisted uses
``DESIGN_CHARACTERISTIC_VALUES``."""

DESIGN_PIPELINE = (
    "UNDERSTAND", "RETRIEVE", "INSPECT", "ANALYSE", "DIRECT",
    "IMPLEMENT", "OBSERVE", "CRITIQUE", "REFINE",
)
"""The executable design pipeline, in order. Not every task executes every stage."""

PIPELINE_SELECTIONS = ("REQUIRED", "OPTIONAL", "SKIPPED")
"""Per-stage selection in a design plan, with the evidence that selected it."""

REFERENCE_STATES = ("FOUND", "ACCESSIBLE", "INSPECTED", "ANALYSED", "USED", "INACCESSIBLE")
"""Reference provenance lifecycle.

``FOUND``        the reference exists and is locatable; nothing about its content
``ACCESSIBLE``   the bytes/interface are reachable; still nothing observed
``INSPECTED``    a human or agent actually looked at it, with an evidence artifact
``ANALYSED``     observations were generalised into design implications
``USED``         a concrete design decision cites it
``INACCESSIBLE`` terminal: it could not be reached (a blocker is required)

States never skip: a URL existing is not inspection, and a search-result snippet
is not analysis.
"""

REFERENCE_TERMINAL_STATES = ("USED", "INACCESSIBLE")
"""States a reference record does not move out of."""

REFERENCE_INSPECTION_TYPES = ("CONTENT", "VISUAL", "INTERACTION")
"""What kind of inspection produced the observations.

``CONTENT``     text/structure was read (markup, documentation, registry entry)
``VISUAL``      a rendered appearance was looked at (screenshot, design file)
``INTERACTION`` behaviour was observed over time (scroll, transition, state change)

They are not interchangeable: reading HTML is not visual inspection, and seeing
a screenshot is not interaction inspection. A claim whose kind exceeds its
inspection evidence is refused rather than upgraded.
"""

REFERENCE_ANALYSIS_DIMENSIONS = (
    "hierarchy", "composition", "navigation", "typography", "spacing",
    "interaction", "motion", "information-density", "responsiveness",
    "accessibility", "component-patterns", "content-structure", "trust-signals",
    "conversion-structure",
)
"""Dimensions an analysis may be recorded against. Not every dimension is
required for every reference; an unlisted dimension is simply not analysed."""

REFERENCE_SOURCE_TYPES = (
    "local-file", "project-document", "project-screenshot", "user-reference",
    "approved-url", "official-api", "paid-provider", "fixture",
)
"""Declared reference source types. Every one of them is read-only."""

REFERENCE_ADAPTER_CAPABILITIES = (
    "discover", "retrieve_metadata", "retrieve_content", "inspect_visual", "inspect_interaction",
)
"""What a reference adapter may declare. A provider does not need all of them."""

REFERENCE_RETRIEVAL_MODES = ("local-read", "external-retrieval", "fixture", "declared")
"""How the bytes behind an accessible reference were obtained (AR-203 T6).

A local digest proves the bytes existed locally; it never proves remote origin,
and the retrieval mode is what keeps those two facts from collapsing.
"""

REFERENCE_DECISIONS = ("adopted", "rejected", "deferred")
"""How a reference finding was treated by the design."""

COMPONENT_LADDER = (
    "existing-project-component",
    "existing-design-system",
    "native-platform",
    "project-local-implementation",
    "approved-dependency",
    "approved-registry",
    "new-external-dependency",
)
"""The minimum-solution ladder, in order. A candidate is evaluated at the first
rung that actually solves the need; jumping straight to a dependency is refused."""

COMPONENT_DECISIONS = ("selected", "rejected", "deferred", "blocked")
"""A candidate evaluation outcome. ``blocked`` means it needs a human approval it
does not have; it is never silently treated as selected."""

COMPONENT_VERDICTS = ("verified", "claimed", "unknown")
"""How a compatibility/accessibility/maintenance claim was established."""

COMPONENT_APPROVAL_SOURCES = ("none", "recorded", "unverified")
"""Whether a candidate's cited approval actually exists in the run.

``recorded``   the approval id names an approval record the engine holds
``unverified`` an id was supplied but nothing in the run matches it
``none``       no approval was cited, so the dependency rung stays blocked

The source is recorded so a reviewer can tell an authorized recommendation from
an asserted one without re-reading the run state.
"""

RENDERED_EVIDENCE_STATES = (
    "SOURCE_SUGGESTS", "RENDERED", "OBSERVED", "VERIFIED", "UNVERIFIED",
)
"""Evidence strength for a rendered claim. These are never collapsed.

``SOURCE_SUGGESTS`` source text suggests the behaviour (a CSS declaration, a tag)
``RENDERED``        a capture artifact at a declared viewport/revision
``OBSERVED``        a behaviour was observed over time (interaction/measurement)
``VERIFIED``        an independent engine execution reproduced the evidence
``UNVERIFIED``      explicitly not captured, with a recorded blocker
"""

RENDERED_EVIDENCE_KINDS = (
    "source", "screenshot", "dom", "browser", "measurement",
    "interaction", "accessibility", "console", "video",
)
"""Artifact kinds a capture adapter may produce."""

RENDER_CAPTURE_METHODS = ("offline-fixture", "declared-observer")
"""How a capture artifact was produced. ``offline-fixture`` is the deterministic
adapter AR-202D ships; ``declared-observer`` is an operator-declared external
observer that recorded the artifact itself and is trusted only as far as it
declares its method, environment and revision."""

DESIGN_REVIEW_DIMENSIONS = (
    "hierarchy", "clarity", "composition", "density", "spacing", "typography",
    "interaction", "motion", "responsiveness", "accessibility", "consistency",
    "affordance", "feedback", "content-clarity", "design-system-fit",
    "reference-alignment", "requirement-satisfaction",
)
"""Critique dimensions. Use only the relevant ones; do not mechanically critique
every dimension."""

DESIGN_SEVERITIES = ("blocking", "major", "minor", "note")
"""Finding severity. No numeric design score exists in this contract."""

DESIGN_FINDING_STATES = ("open", "repaired", "unresolved", "accepted", "rejected")

DESIGN_REQUIREMENT_STATES = (
    "unaddressed", "planned", "implemented", "observed", "verified", "blocked", "rejected",
)
"""Requirement closure states.

``implemented`` code exists; ``observed`` rendered/behavioural evidence exists;
``verified`` independent evidence confirms the claim; ``rejected`` is an
explicit, recorded decision not to satisfy it.
"""

DESIGN_REQUIREMENT_EVIDENCE = ("source", "rendered", "behavioural")
"""What kind of evidence a requirement needs before it can close.

A ``behavioural`` or ``rendered`` requirement can never be verified from source
inspection alone, and an ``implemented`` mapping is not an observation.
"""

DESIGN_FAILURE_KINDS = (
    "REFERENCE_UNAVAILABLE",
    "REFERENCE_INSPECTION_FAILED",
    "REFERENCE_PROVENANCE_INVALID",
    "COMPONENT_INCOMPATIBLE",
    "DESIGN_DIRECTION_MISSING",
    "DESIGN_DIRECTION_STALE",
    "DESIGN_DIRECTION_UNAPPROVED",
    "RENDER_CAPTURE_FAILED",
    "RENDER_EVIDENCE_STALE",
    "ACCESSIBILITY_FAILURE",
    "DESIGN_REVIEW_FAILURE",
    "REQUIREMENT_EVIDENCE_INSUFFICIENT",
    "REFINEMENT_LIMIT_REACHED",
)
"""Design-specific failure kinds. Each maps onto an existing AR-202 failure class
in :mod:`ariadne_engine.execution`; the taxonomy itself is not duplicated."""

DESIGN_EVIDENCE_STRENGTH = {
    "SOURCE_SUGGESTS": 1,
    "UNVERIFIED": 0,
    "RENDERED": 2,
    "OBSERVED": 3,
    "VERIFIED": 4,
}
"""Ordinal evidence strength used for comparisons. Never presented as a quality score."""


def design_id_matches(prefix: str, value: str) -> bool:
    return bool(re.fullmatch(rf"{prefix}_[0-9TZ]+_[0-9a-f]{{8}}", value or ""))


def design_schema_problems(record: Mapping[str, Any]) -> list[str]:
    """Shared structural validation for every AR-202D record family."""
    problems: list[str] = []
    if not isinstance(record, Mapping):
        return ["design record is not an object"]
    if record.get("schema_version") not in READABLE_DESIGN_SCHEMAS:
        problems.append(f"design record schema is unsupported: {record.get('schema_version')!r}")
    return problems


def _is_sha256(value: Any) -> bool:
    return bool(re.fullmatch(r"[0-9a-f]{64}", str(value or "")))


def artifact_problems(record: Mapping[str, Any], name: str = "evidence") -> list[str]:
    """Structural validation of a ``{path, sha256, ...}`` evidence artifact."""
    value = record.get(name)
    if not isinstance(value, Mapping):
        return [f"design record has no {name} artifact"]
    problems: list[str] = []
    if not str(value.get("path", "")).strip():
        problems.append(f"{name} artifact has no path")
    if not _is_sha256(value.get("sha256")):
        problems.append(f"{name} artifact has no content hash")
    return problems


def reference_problems(record: Mapping[str, Any]) -> list[str]:
    """Structural validation of one reference provenance record (fail closed)."""
    problems = design_schema_problems(record)
    if not isinstance(record, Mapping):
        return problems
    if not design_id_matches("ref", str(record.get("reference_id", ""))):
        problems.append("reference record has a malformed reference id")
    for name in ("source", "locator", "recorded_at", "adapter"):
        _non_empty(record, name, problems)
    if str(record.get("source_type", "")) not in REFERENCE_SOURCE_TYPES:
        problems.append(f"reference record has an unsupported source type: {record.get('source_type') or 'missing'}")
    state = str(record.get("state", ""))
    if state not in REFERENCE_STATES:
        problems.append(f"reference record has an unsupported state: {state or 'missing'}")
    if not str(record.get("title", "")).strip() and state != "FOUND":
        problems.append("reference record has no title and is beyond FOUND")
    if state in ("ACCESSIBLE", "INSPECTED", "ANALYSED", "USED"):
        if not str(record.get("retrieved_at", "")).strip():
            problems.append(f"reference is {state} without a retrieval record")
        if not _is_sha256((record.get("content") or {}).get("sha256") if isinstance(record.get("content"), Mapping) else None):
            problems.append(f"reference is {state} without a retrieved content digest")
        mode = str((record.get("content") or {}).get("retrieval_mode", "") or "") if isinstance(record.get("content"), Mapping) else ""
        if mode and mode not in REFERENCE_RETRIEVAL_MODES:
            problems.append(f"reference records an unknown retrieval mode: {mode}")
    history = record.get("state_history")
    if not isinstance(history, list) or not history:
        problems.append("reference record has no lifecycle history")
    inspections = record.get("inspections") or []
    if not isinstance(inspections, list):
        problems.append("reference record inspections is not a list")
        inspections = []
    analysis = record.get("analysis")
    usage = record.get("usage")
    if state in ("INSPECTED", "ANALYSED", "USED") and not inspections:
        problems.append(f"reference is {state} without inspection evidence")
    if state in ("ANALYSED", "USED") and not isinstance(analysis, Mapping):
        problems.append(f"reference is {state} without an analysis record")
    if state == "USED" and not isinstance(usage, Mapping):
        problems.append("reference is USED without a usage record")
    if state == "USED" and isinstance(usage, Mapping) and not str(usage.get("artifact_anchor", "")).strip():
        problems.append("a used reference must record the artifact anchor its decision cites")
    if state == "INACCESSIBLE":
        if not str(record.get("blocker", "")).strip():
            problems.append("an inaccessible reference must record a blocker")
        if inspections:
            problems.append("an inaccessible reference cannot carry inspection evidence")
        if isinstance(analysis, Mapping) or isinstance(usage, Mapping):
            problems.append("an inaccessible reference cannot carry analysis or usage")
    for item in inspections:
        if not isinstance(item, Mapping):
            problems.append("reference inspection entry is malformed")
            continue
        if str(item.get("type", "")) not in REFERENCE_INSPECTION_TYPES:
            problems.append(f"reference inspection entry has an unsupported type: {item.get('type') or 'missing'}")
        if not item.get("observations"):
            problems.append("reference inspection entry has no observations")
        problems.extend(artifact_problems(item, "evidence"))
    return list(dict.fromkeys(problems))


def reference_analysis_problems(record: Mapping[str, Any]) -> list[str]:
    """Structural validation of one reference analysis record."""
    problems = design_schema_problems(record)
    if not isinstance(record, Mapping):
        return problems
    if not design_id_matches("ran", str(record.get("analysis_id", ""))):
        problems.append("reference analysis has a malformed analysis id")
    if not design_id_matches("ref", str(record.get("reference_id", ""))):
        problems.append("reference analysis names no reference")
    findings = record.get("findings")
    if not isinstance(findings, list) or not findings:
        problems.append("reference analysis records no findings")
        return list(dict.fromkeys(problems))
    for item in findings:
        if not isinstance(item, Mapping):
            problems.append("reference analysis finding is malformed")
            continue
        if str(item.get("dimension", "")) not in REFERENCE_ANALYSIS_DIMENSIONS:
            problems.append(f"reference analysis finding has an unsupported dimension: {item.get('dimension') or 'missing'}")
        for name in ("observation", "interpretation", "applicability"):
            if not str(item.get(name, "")).strip():
                problems.append(f"reference analysis finding has no {name}")
        if str(item.get("decision", "")) not in REFERENCE_DECISIONS:
            problems.append("reference analysis finding has no adoption decision")
    return list(dict.fromkeys(problems))


DIRECTION_SECTIONS = (
    "product_context", "key_hierarchy", "interaction_principles", "visual_principles",
    "content_principles", "constraints", "existing_system", "reference_findings_adopted",
    "findings_rejected", "accessibility_requirements", "responsive_requirements",
    "approved_deviations",
)
"""Every constraining section of a design direction. Each must be a non-empty list.

The docs (`docs/v2/AR-202D/04-DESIGN-DIRECTION.md` §1) make every section
mandatory, so the validator enforces exactly this tuple. A direction that
rejected nothing, adopted nothing, preserved nothing or deviated nowhere has not
recorded the decision that section exists to carry.
"""

DIRECTION_FINGERPRINT_SECTIONS = (
    "key_hierarchy", "interaction_principles", "visual_principles", "content_principles",
    "constraints", "accessibility_requirements", "responsive_requirements", "approved_deviations",
)
"""The sections a ``G1D`` approval binds to.

They are the ones the actionable ``statements`` are derived from plus the
approved deviations, so an edit that could change implementation obligations
invalidates the approval while a cosmetic edit outside the constraining body
does not.
"""

MAX_DESIGN_RECORDS = 10_000
"""Hard safety bound for one authoritative design collection.

A fully inspected reference record is ≈1.5 KB, so 10 000 records is ≈15 MB of
run state: far above any plausible single-task design workflow (a large design
project might record a few hundred references or captures) and far below a size
that makes state load, validation or serialisation pathological. Exceeding it is
refused with an explicit error; authoritative evidence is never silently
truncated.
"""

DESIGN_COLLECTION_KEYS = (
    "design_references", "rendered_evidence", "design_requirements", "design_directions",
    "component_candidates", "design_reviews", "design_refinements",
)
"""The append-only authoritative collections this bound applies to."""

MAX_REFERENCE_HISTORY = 100
"""Hard safety bound on one reference's lifecycle history.

The lifecycle's self-edges allow a second distinct inspection and a
re-analysis; 100 transitions is far beyond any honest inspection sequence and
stops a caller looping the same reference to grow run state without bound.
"""


def require_design_capacity(state: Mapping[str, Any], key: str) -> None:
    """Refuse to append to an authoritative design collection past its bound.

    The key must be one of :data:`DESIGN_COLLECTION_KEYS`, so a typo at a call
    site fails closed instead of silently skipping the bound.
    """
    if key not in DESIGN_COLLECTION_KEYS:
        raise ContractError(
            f"{key!r} is not an authoritative design collection; the bound applies to "
            + ", ".join(DESIGN_COLLECTION_KEYS)
        )
    values = state.get(key)
    if values is None:
        return
    if not isinstance(values, list):
        raise ContractError(
            f"{key} is not a list; the authoritative design collections are append-only lists"
        )
    limit = MAX_DESIGN_RECORDS
    if len(values) >= limit:
        raise ContractError(
            f"{key} has reached its safety bound of {limit} records; this run is too large for one "
            "task's design workflow and further records are refused rather than truncated"
        )


def component_candidate_problems(record: Mapping[str, Any]) -> list[str]:
    """Structural validation of one component-candidate evaluation."""
    problems = design_schema_problems(record)
    if not isinstance(record, Mapping):
        return problems
    if not design_id_matches("cnd", str(record.get("candidate_id", ""))):
        problems.append("component candidate has a malformed candidate id")
    for name in ("need", "task_id", "recorded_at"):
        _non_empty(record, name, problems)
    if str(record.get("rung", "")) not in COMPONENT_LADDER:
        problems.append(f"component candidate names an unknown ladder rung: {record.get('rung') or 'missing'}")
    if str(record.get("decision", "")) not in COMPONENT_DECISIONS:
        problems.append(f"component candidate has an unsupported decision: {record.get('decision') or 'missing'}")
    if not isinstance(record.get("alternatives"), list) or not record.get("alternatives"):
        problems.append("component candidate considers no alternative")
    if not isinstance(record.get("existing_equivalent"), Mapping):
        problems.append("component candidate does not record the existing-equivalent check")
    findings = record.get("findings")
    if not isinstance(findings, Mapping) or not findings:
        problems.append("component candidate records no findings")
    else:
        for name, value in findings.items():
            if not isinstance(value, Mapping) or str(value.get("verdict", "")) not in COMPONENT_VERDICTS:
                problems.append(f"component candidate finding {name} has no declared verdict")
    if str(record.get("install_authority", "")) != "none — human G2 required":
        problems.append("component candidate must record that installation authority is human-only")
    if str(record.get("approval_source", "")) not in COMPONENT_APPROVAL_SOURCES:
        problems.append(
            f"component candidate has an unsupported approval source: {record.get('approval_source') or 'missing'}"
        )
    return list(dict.fromkeys(problems))


def design_direction_problems(record: Mapping[str, Any]) -> list[str]:
    """Structural validation of one design-direction record.

    Direction must be actionable: every constraining section is required and a
    vague mood phrase is refused, because an unactionable direction cannot
    constrain implementation or be checked after the fact. The required sections
    come from :data:`DIRECTION_SECTIONS`, so the validator and the record
    builder cannot disagree about what "required" means.
    """
    problems = design_schema_problems(record)
    if not isinstance(record, Mapping):
        return problems
    if not design_id_matches("ddr", str(record.get("direction_id", ""))):
        problems.append("design direction has a malformed direction id")
    for name in ("task_id", "goal", "scope", "recorded_at", "revision_hash"):
        _non_empty(record, name, problems)
    if not _is_sha256(record.get("revision_hash")):
        problems.append("design direction is not bound to a revision fingerprint")
    for name in DIRECTION_SECTIONS:
        value = record.get(name)
        if not isinstance(value, list) or not [item for item in value if str(item).strip()]:
            problems.append(f"design direction has no {name}")
    for item in record.get("statements", []) or []:
        if str(item.get("value", "")).strip() and _generic_direction(str(item["value"])):
            problems.append(
                f"design direction statement is not actionable (generic mood language): {item['value']!r}"
            )
    return list(dict.fromkeys(problems))


_GENERIC_DIRECTION = re.compile(
    r"\b(modern|sleek|clean|minimal|elegant|premium|intuitive|beautiful|delightful|polished)\b",
    re.IGNORECASE,
)


def _generic_direction(value: str) -> bool:
    """True for a statement that names a mood instead of an actionable rule."""
    text = normalise(value)
    if not text:
        return False
    if len(text.split()) <= 6 and _GENERIC_DIRECTION.search(text):
        return True
    return bool(re.fullmatch(r"[\w\s,/-]*\b(modern|sleek|elegant|premium)\b[\w\s,/-]*", text, re.IGNORECASE)) and len(text.split()) <= 8


def design_requirement_problems(record: Mapping[str, Any]) -> list[str]:
    """Structural validation of one requirement-closure record."""
    problems = design_schema_problems(record)
    if not isinstance(record, Mapping):
        return problems
    if not design_id_matches("drq", str(record.get("record_id", ""))):
        problems.append("design requirement has a malformed record id")
    if not str(record.get("requirement_id", "")).strip():
        problems.append("design requirement names no requirement")
    if str(record.get("evidence_kind", "")) not in DESIGN_REQUIREMENT_EVIDENCE:
        problems.append(
            f"design requirement has an unsupported evidence kind: {record.get('evidence_kind') or 'missing'}"
        )
    if str(record.get("state", "")) not in DESIGN_REQUIREMENT_STATES:
        problems.append(f"design requirement has an unsupported state: {record.get('state') or 'missing'}")
    for name in ("decision", "implementation"):
        value = record.get(name)
        if not isinstance(value, Mapping):
            problems.append(f"design requirement has no {name} mapping")
    if not isinstance(record.get("evidence"), list):
        problems.append("design requirement evidence is not a list")
    if str(record.get("state", "")) in ("observed", "verified") and not record.get("evidence"):
        problems.append(f"a {record.get('state')} requirement must cite evidence")
    if str(record.get("state", "")) == "implemented":
        implementation = record.get("implementation") if isinstance(record.get("implementation"), Mapping) else {}
        if not str(implementation.get("summary", "")).strip():
            problems.append("an implemented requirement must record what was implemented")
    if str(record.get("state", "")) == "rejected" and not str(record.get("rejection_reason", "")).strip():
        problems.append("a rejected requirement must record why it was rejected")
    if record.get("stale"):
        problems.append("design requirement evidence is stale and cannot close the requirement")
    return list(dict.fromkeys(problems))


def rendered_evidence_problems(record: Mapping[str, Any]) -> list[str]:
    """Structural validation of one rendered-evidence artifact record."""
    problems = design_schema_problems(record)
    if not isinstance(record, Mapping):
        return problems
    if not design_id_matches("rnd", str(record.get("evidence_id", ""))):
        problems.append("rendered evidence has a malformed evidence id")
    for name in ("task_id", "revision_hash", "capture_method", "captured_at"):
        _non_empty(record, name, problems)
    if not _is_sha256(record.get("revision_hash")):
        problems.append("rendered evidence is not bound to a revision fingerprint")
    state = str(record.get("state", ""))
    if state not in RENDERED_EVIDENCE_STATES:
        problems.append(f"rendered evidence has an unsupported state: {state or 'missing'}")
    kind = str(record.get("kind", ""))
    if kind not in RENDERED_EVIDENCE_KINDS:
        problems.append(f"rendered evidence has an unsupported kind: {kind or 'missing'}")
    if str(record.get("capture_method", "")) not in RENDER_CAPTURE_METHODS:
        problems.append(f"rendered evidence names an unknown capture method: {record.get('capture_method') or 'missing'}")
    if state == "UNVERIFIED":
        if not str(record.get("blocker", "")).strip():
            problems.append("unverified rendered evidence must record a blocker")
        return list(dict.fromkeys(problems))
    problems.extend(artifact_problems(record, "artifact"))
    viewport = record.get("viewport")
    if not isinstance(viewport, Mapping) or not str(viewport.get("width", "")).strip():
        problems.append("rendered evidence has no viewport")
    if state in ("OBSERVED", "VERIFIED") and not str(record.get("observation", "")).strip():
        verification = record.get("verification") if isinstance(record.get("verification"), Mapping) else {}
        if state == "VERIFIED" and str(verification.get("method", "")).strip():
            pass  # re-production is what was established here; the method records it
        else:
            problems.append(f"{state} rendered evidence must record what was observed")
    if state == "VERIFIED":
        if not str(record.get("verification_execution", "")).strip():
            problems.append("verified rendered evidence must name the execution that verified it")
        if not record.get("prior_evidence_ids"):
            problems.append("verified rendered evidence must cite the earlier capture it re-produced")
    return list(dict.fromkeys(problems))


def design_review_problems(record: Mapping[str, Any]) -> list[str]:
    """Structural validation of one independent design critique."""
    problems = design_schema_problems(record)
    if not isinstance(record, Mapping):
        return problems
    if not design_id_matches("dsr", str(record.get("review_id", ""))):
        problems.append("design review has a malformed review id")
    if str(record.get("review_kind", "")) != "design":
        problems.append("design review must declare review_kind 'design'")
    for name in ("reviewer_identity", "recorded_at", "direction_id", "task_id"):
        _non_empty(record, name, problems)
    if not _is_sha256(record.get("direction_revision")):
        problems.append("design review is not bound to the approved direction revision")
    if str(record.get("execution_binding", "")) != "engine":
        problems.append("design review is not bound to an engine execution identity")
    if not re.fullmatch(r"exe_[0-9TZ]+_[0-9a-f]{8}", str(record.get("reviewer_execution", ""))):
        problems.append("design review has no engine-created reviewer execution")
    if not re.fullmatch(r"exe_[0-9TZ]+_[0-9a-f]{8}", str(record.get("implementing_execution", ""))):
        problems.append("design review has no engine-created implementing execution")
    if str(record.get("reviewer_execution", "")) == str(record.get("implementing_execution", "")):
        problems.append("design review names one execution as both reviewer and implementer")
    level = str(record.get("independence_level", "") or "")
    if level and level not in INDEPENDENCE_LEVELS:
        problems.append(f"design review names an unknown independence level: {level}")
    if not record.get("evidence"):
        problems.append("design review cites no evidence")
    if str(record.get("outcome", "")) not in ("passed", "failed", "blocked", "not-performed"):
        problems.append("design review has an unsupported outcome")
    for item in record.get("findings", []) or []:
        if not isinstance(item, Mapping):
            problems.append("design review finding is malformed")
            continue
        if str(item.get("dimension", "")) not in DESIGN_REVIEW_DIMENSIONS:
            problems.append(f"design review finding has an unsupported dimension: {item.get('dimension') or 'missing'}")
        if str(item.get("severity", "")) not in DESIGN_SEVERITIES:
            problems.append(f"design review finding has an unsupported severity: {item.get('severity') or 'missing'}")
        if not item.get("evidence_ids"):
            problems.append("design review finding cites no evidence")
        if not str(item.get("explanation", "")).strip():
            problems.append("design review finding has no explanation")
        if not str(item.get("repair_scope", "")).strip():
            problems.append("design review finding names no repair scope")
        if str(item.get("state", "open")) not in DESIGN_FINDING_STATES:
            problems.append("design review finding has an unsupported state")
    return list(dict.fromkeys(problems))


def refinement_problems(record: Mapping[str, Any]) -> list[str]:
    """Structural validation of one bounded refinement cycle."""
    problems = design_schema_problems(record)
    if not isinstance(record, Mapping):
        return problems
    if not design_id_matches("rfn", str(record.get("refinement_id", ""))):
        problems.append("refinement has a malformed refinement id")
    for name in ("finding_id", "artifact", "intended_change", "recorded_at", "task_id"):
        _non_empty(record, name, problems)
    expected = record.get("expected_evidence")
    if not isinstance(expected, list) or not [item for item in expected if str(item).strip()]:
        problems.append("refinement declares no expected evidence")
    if not isinstance(record.get("permitted_scope"), list) or not record.get("permitted_scope"):
        problems.append("refinement has no permitted scope")
    if not isinstance(record.get("regression_checks"), list) or not record.get("regression_checks"):
        problems.append("refinement declares no regression checks")
    if str(record.get("state", "")) not in ("proposed", "applied", "verified", "failed", "abandoned"):
        problems.append(f"refinement has an unsupported state: {record.get('state') or 'missing'}")
    return list(dict.fromkeys(problems))


DESIGN_RECORD_VALIDATORS = {
    "reference": reference_problems,
    "reference-analysis": reference_analysis_problems,
    "component-candidate": component_candidate_problems,
    "design-direction": design_direction_problems,
    "design-requirement": design_requirement_problems,
    "rendered-evidence": rendered_evidence_problems,
    "design-review": design_review_problems,
    "refinement": refinement_problems,
}
"""Record kind -> validator. One dispatch table, so no caller can append an
unvalidated design record to the run state."""


def design_kind_problems(kind: str, record: Mapping[str, Any]) -> list[str]:
    validator = DESIGN_RECORD_VALIDATORS.get(str(kind))
    if validator is None:
        return [f"unknown design record kind: {kind!r}"]
    return validator(record)


def direction_fingerprint(record: Mapping[str, Any]) -> str:
    """Fingerprint of the constraining content of a design-direction record."""
    scope = record.get("scope")
    if isinstance(scope, (list, tuple)):
        scope_text = ", ".join(normalise(str(item)) for item in scope)
    else:
        scope_text = normalise(str(scope or ""))
    body = "\n".join(
        " | ".join(normalise(str(item)) for item in record.get(name, []) or [])
        for name in DIRECTION_FINGERPRINT_SECTIONS
    )
    statements = "\n".join(
        normalise(str(item.get("value", "")))
        for item in (record.get("statements") or [])
        if isinstance(item, Mapping)
    )
    return digest_fields("design-direction-record", {
        "direction-id": str(record.get("direction_id", "")),
        "task-id": str(record.get("task_id", "")),
        "scope": scope_text,
        "constrained-body": "\n".join([body, statements]),
    })


# ------------------------------------------------------ AR-203 verification plane
#
# AR-203 adds three record families, each versioned independently of every
# earlier family for the same reason AR-202 and AR-202D did: a run state written
# by an earlier milestone carries none of them and stays readable, continuable
# and byte-compatible without a migration. The three families are deliberately
# separate things:
#
# capability records
#     what an adapter or runtime *can do now*, with the evidence that established
#     it. A declaration is not a verification.
# verification records
#     what claim was checked, by which engine-created execution, against which
#     revision, with which evidence, and what remains unverified.
# decision records
#     what bounded judgement was produced by which provider/model under which
#     contract and policy version. A decision is not an authorization.

SCHEMA_CAPABILITY = 1
"""The AR-203 capability-registry record family."""

READABLE_CAPABILITY_SCHEMAS = (1,)
"""Capability record versions this runtime can read."""

CAPABILITY_CONTRACT = "ariadne-capability-1"
"""Marker recorded in ``state["engine"]["capability_contract"]``."""

SCHEMA_VERIFICATION = 1
"""The AR-203 verification-record family."""

READABLE_VERIFICATION_SCHEMAS = (1,)
"""Verification record versions this runtime can read."""

VERIFICATION_CONTRACT = "ariadne-verification-1"
"""Marker recorded in ``state["engine"]["verification_contract"]``."""

SCHEMA_DECISION = 1
"""The AR-203 decision-record family."""

READABLE_DECISION_SCHEMAS = (1,)
"""Decision record versions this runtime can read."""

DECISION_CONTRACT = "ariadne-decision-1"
"""Marker recorded in ``state["engine"]["decision_contract"]``."""

DECISION_CONTRACT_VERSION = "ar-203-decision-contract-1"
"""The decision *contract* version recorded with every decision record.

It is distinct from :data:`SCHEMA_DECISION` on purpose: the stored shape can stay
at 1 while the question definitions, allowed answer spaces or confidence
semantics evolve, and a consumer must be able to tell which definitions produced
an answer.
"""

IDENTITY_CLAIM_LEVELS = (
    "DECLARED",
    "REQUESTED",
    "ENGINE_CREATED",
    "RUNTIME_OBSERVED",
    "PROVIDER_OBSERVED",
    "VERIFIED",
    "UNKNOWN",
)
"""How strongly one identity fact about an execution is established.

``DECLARED``          a party asserted it in prose; no engine evidence
``REQUESTED``         the run asked for it; the execution may not have used it
``ENGINE_CREATED``    the engine created the identity record that carries it
``RUNTIME_OBSERVED``  the runtime itself observed it at the boundary
``PROVIDER_OBSERVED`` the adapter/provider reported it for this execution
``VERIFIED``          independently reproduced by a different engine execution
``UNKNOWN``           nothing established it; it must never be guessed

The levels are not interchangeable: ``requested model = X`` does not imply
``observed model = X``, and a worker's prose never raises a claim above
``DECLARED``.
"""

IDENTITY_FIELDS = ("provider", "model")
"""Identity facts tracked per execution."""

CAPABILITY_STATUSES = (
    "DECLARED",
    "DISCOVERED",
    "AVAILABLE",
    "EXERCISED",
    "VERIFIED",
    "UNAVAILABLE",
    "UNKNOWN",
)
"""Evidence states for one capability.

``DECLARED``    an adapter says it supports it; nothing was checked
``DISCOVERED``  the surface was found to exist (a method, an executable on PATH)
``AVAILABLE``   a deterministic probe established it can be used here
``EXERCISED``   it actually produced a result in an engine-created execution
``VERIFIED``    a second engine execution reproduced the exercised result
``UNAVAILABLE`` it cannot be used here, with a recorded reason
``UNKNOWN``     nothing established it

A declared capability alone must never become ``VERIFIED``; reaching
``EXERCISED`` requires the execution that exercised it and ``VERIFIED`` requires
an existing verification record.
"""

CAPABILITY_STATUS_ORDER = {
    "UNKNOWN": 0,
    "UNAVAILABLE": 0,
    "DECLARED": 1,
    "DISCOVERED": 2,
    "AVAILABLE": 3,
    "EXERCISED": 4,
    "VERIFIED": 5,
}
"""Ordinal strength for comparisons. ``UNAVAILABLE`` is a fact, not a weak claim:
it is ranked with ``UNKNOWN`` because neither satisfies a capability requirement."""

CAPABILITY_FAMILIES = (
    "reference",
    "capture",
    "registry",
    "worker",
    "reasoner",
    "provider",
    "decision",
    "tool",
)
"""Adapter families a capability record may describe."""

CAPABILITY_FRESHNESS = ("CURRENT", "STALE", "UNKNOWN", "SUPERSEDED")
"""Whether a capability observation still describes the surface it was taken on.

``CURRENT``    the observed surface fingerprint still matches
``STALE``      the surface changed (version, adapter identity) since observation
``UNKNOWN``    no fingerprint was recorded, so currentness cannot be established
``SUPERSEDED`` a later observation for the same capability replaced this one
"""

VERIFICATION_LEVELS = (
    "UNVERIFIED",
    "DECLARED",
    "OBSERVED",
    "REPRODUCED",
    "INDEPENDENTLY_REPRODUCED",
    "VERIFIED",
    "STALE",
)
"""What a verification record actually established.

``UNVERIFIED``               nothing was established
``DECLARED``                 a party asserted the claim; no evidence was examined
``OBSERVED``                 the engine examined the evidence once, in a named execution
``REPRODUCED``               the same execution re-produced the observed result
``INDEPENDENTLY_REPRODUCED`` a *different* engine execution re-produced it
``VERIFIED``                 independently reproduced against the current revision and dependencies
``STALE``                    was established for a revision/dependency set that has since changed

``STALE`` is a currentness verdict, not a strength: a stale record keeps its
historical level in ``established_level`` but answers as ``STALE`` for any
current requirement. Re-hashing a declared artifact never raises a level.
"""

VERIFICATION_LEVEL_ORDER = {
    "UNVERIFIED": 0,
    "STALE": 0,
    "DECLARED": 1,
    "OBSERVED": 2,
    "REPRODUCED": 3,
    "INDEPENDENTLY_REPRODUCED": 4,
    "VERIFIED": 5,
}
"""Ordinal strength used for comparisons. ``STALE`` answers as nothing."""

FRESHNESS_STATES = ("CURRENT", "STALE", "UNKNOWN", "SUPERSEDED")
"""The one freshness vocabulary shared by capability, verification and design records."""

INDEPENDENCE_LEVELS = (
    "NONE",
    "DECLARED_DISTINCT",
    "ENGINE_DISTINCT_EXECUTION",
    "DISTINCT_RUNTIME",
    "DISTINCT_PROVIDER",
    "HUMAN_REVIEW",
)
"""How review independence was established.

``NONE``                     the reviewer is the implementer, or nothing distinguishes them
``DECLARED_DISTINCT``        two different labels were asserted; no engine fact separates them
``ENGINE_DISTINCT_EXECUTION``two engine-created executions that are provably different
``DISTINCT_RUNTIME``         additionally, the observed runtime differs (adapter/invocation)
``DISTINCT_PROVIDER``        additionally, the provider-observed provider/model differs
``HUMAN_REVIEW``             a recorded human channel reviewed the work

No level is categorically better for every task: policy decides which level a
review requires. A different string label is never by itself an independent
execution.
"""

CONFIDENCE_KINDS = (
    "CALIBRATED_PROBABILITY",
    "PROVIDER_PROBABILITY",
    "DERIVED_CONFIDENCE",
    "SELF_REPORTED_CONFIDENCE",
    "NONE",
)
"""Where a decision's confidence number came from.

``CALIBRATED_PROBABILITY`` a provider calibrated against known outcomes; the raw
                           distribution is preserved when the provider supplies one
``PROVIDER_PROBABILITY``   the provider reports a probability it did not calibrate
``DERIVED_CONFIDENCE``     Ariadne computed it deterministically from evidence
``SELF_REPORTED_CONFIDENCE`` a generative model said a number; it is not calibrated
``NONE``                   no confidence was supplied; the value stays UNKNOWN

A ``SELF_REPORTED_CONFIDENCE`` value must never silently become calibrated
confidence, and no threshold may grant authorization.
"""

DECISION_PRIMITIVES = ("BinaryDecision", "ChoiceDecision", "ScaleDecision", "MultiSelectDecision")
"""The bounded answer shapes a decision question may use.

A primitive bounds the *answer space*; it does not make the answer correct. Type
validity is not correctness.
"""

DECISION_CONSEQUENCES = ("LOW", "MEDIUM", "HIGH", "PROTECTED")
"""What acting on the decision could cost. Policy maps consequence to evidence.

``PROTECTED`` means the action is human-controlled regardless of confidence.
"""

DECISION_STATUSES = ("answered", "invalid", "refused", "failed", "unavailable")
"""The outcome of asking one bounded question.

``answered``    the provider returned an answer inside the allowed space
``invalid``     an answer arrived outside the allowed space; it is recorded and refused
``refused``     policy refused to accept the answer (evidence/confidence too weak)
``failed``      the provider failed; no answer exists
``unavailable`` no provider was available; the caller must fall back or escalate
"""

FAILURE_CLASSIFICATION_SOURCES = ("deterministic", "bounded-decision", "fallback-unknown")
"""How a failure class was decided.

``deterministic``     the declared vocabulary mapped the source; code decided
``bounded-decision``  a bounded decision proposed a class inside the safe subset
``fallback-unknown``  nothing established the class; it stays UNKNOWN and escalates
"""

DECISION_CLASSIFIABLE_FAILURE_CLASSES = (
    "IMPLEMENTATION_FAILURE",
    "VALIDATION_FAILURE",
    "TIMEOUT",
    "ENVIRONMENT_FAILURE",
    "PROVIDER_FAILURE",
    "CONTEXT_FAILURE",
    "UNKNOWN",
)
"""The only failure classes a bounded decision may propose.

Authorization, revision, conflict and design failures are deterministic facts
(a refused gate, a changed revision, an illegal state) and must never be derived
from model judgement.
"""

# ------------------------------------------- AR-205D decision intelligence

SCHEMA_DECISION_INTELLIGENCE = 1
"""The AR-205D decision-intelligence record family.

Plans, graphs, cache entries, consensus records, generation justifications and
calibration outcomes share one family. They are versioned independently of
``SCHEMA_DECISION`` for the same reason the AR-203 family is: a run state that
predates AR-205D stays readable, continuable and byte-compatible without a
migration, and the stored shape can evolve without moving the decision
contract every earlier reader checks.
"""

READABLE_DECISION_INTELLIGENCE_SCHEMAS = (1,)
"""Decision-intelligence record versions this runtime can read."""

DECISION_INTELLIGENCE_CONTRACT = "ariadne-decision-intelligence-1"
"""Marker recorded in ``state["engine"]["decision_intelligence_contract"]``."""

DECISION_CLASSIFICATIONS = ("DETERMINISTIC", "BOUNDED", "GENERATIVE", "HUMAN", "UNRESOLVED")
"""What form of intelligence one unresolved question deserves.

``UNRESOLVED`` means the compiler could not safely classify the requirement. It
must never silently become ``GENERATIVE``; policy decides the escalation.
"""

DECISION_GRAPH_NODE_KINDS = ("DETERMINISTIC", "DECISION_BATCH", "GENERATION", "VERIFICATION", "HUMAN_GATE")
"""The small execution vocabulary of the decision graph."""

DECISION_GRAPH_STATUSES = (
    "PENDING", "READY", "RUNNING", "SUCCEEDED", "FAILED", "BLOCKED",
    "REFUSED", "AWAITING_HUMAN", "AWAITING_GENERATION", "INVALIDATED", "SKIPPED",
)
"""Node status. ``AWAITING_HUMAN`` and ``AWAITING_GENERATION`` are execution
boundaries, not completions: a node that awaits authority is never reported as
done by the graph itself.
"""

ESCALATION_REASONS = (
    "NO_DETERMINISTIC_RULE",
    "NO_DECISION_PROVIDER",
    "LOW_CONFIDENCE",
    "NO_CONFIDENCE",
    "CAPABILITY_MISSING",
    "CONFLICTING_EVIDENCE",
    "OUT_OF_DISTRIBUTION",
    "DECISION_FAILED",
    "GENERATIVE_REQUIRED",
    "POLICY_REQUIRES_HUMAN",
    "INSUFFICIENT_STATE",
    "DECISION_CONFLICT",
    "UNRESOLVED_CLASSIFICATION",
    "DECISION_REFUSED",
)
"""Structured escalation reasons. A vague "needs a stronger model" is refused."""

GENERATION_REASONS = (
    "CREATION_REQUIRED",
    "OPEN_ENDED_REASONING_REQUIRED",
    "NO_BOUNDED_ANSWER_SPACE",
    "BOUNDED_DECISION_INSUFFICIENT",
    "REPAIR_CONTENT_REQUIRED",
    "SYNTHESIS_REQUIRED",
)
"""Why generative execution was justified. This is economics/provenance
evidence, not user-facing bureaucracy."""

PROJECTION_FIELD_MARKS = ("REQUIRED", "OPTIONAL", "FORBIDDEN")
"""How one field participates in a decision-specific state projection."""

CONSENSUS_POLICIES = (
    "single",
    "second_on_low_confidence",
    "second_on_high_stakes",
    "second_on_disagreement",
)
"""When an independent second decision is requested."""

CONSENSUS_VERDICTS = ("not_required", "agree", "disagree", "conflict", "second_unavailable")
"""The comparison of two independent decisions. Agreement is evidence of
agreement, never proof of correctness.
"""

REVIEW_ESCALATIONS = ("routine", "independent_review", "enhanced_review", "human_attention")
"""The bounded answer space for review escalation."""

EVIDENCE_RELEVANCE_ANSWERS = ("SUPPORTS", "PARTIALLY_SUPPORTS", "IRRELEVANT", "CONTRADICTS", "UNKNOWN")
"""The bounded answer space for evidence relevance."""

ROUTE_FAMILIES = ("mechanical", "implementation", "design", "research", "recovery", "unknown")
"""The bounded answer space for route-family selection."""

CALIBRATION_OUTCOME_CATEGORIES = ("SUPPORTED", "CONTRADICTED", "OVERRIDDEN", "UNRESOLVED")
"""How a recorded decision outcome is classified for later calibration analysis.

A downstream failure is never automatically labelled a wrong decision; only
recorded evidence may move a decision into ``CONTRADICTED`` or ``OVERRIDDEN``.
"""

MAX_DECISION_PLANS = 500
"""Hard safety bound for compiled decision plans."""

MAX_DECISION_GRAPHS = 200
"""Hard safety bound for decision graphs."""

MAX_DECISION_CACHE_ENTRIES = 5_000
"""Hard safety bound for reusable decision-cache entries."""

MAX_DECISION_CONSENSUS = 2_000
"""Hard safety bound for second-opinion comparison records."""

MAX_GENERATION_JUSTIFICATIONS = 2_000
"""Hard safety bound for generation-justification records."""

MAX_DECISION_OUTCOMES = 10_000
"""Hard safety bound for calibration outcome records."""

AR205D_COLLECTIONS = (
    "decision_plans",
    "decision_graphs",
    "decision_cache",
    "decision_consensus",
    "generation_justifications",
    "decision_outcomes",
)
"""The AR-205D decision-intelligence collections, additive and optional like
every earlier family."""

MAX_CAPABILITY_RECORDS = 5_000
"""Hard safety bound for the capability observation collection."""

MAX_VERIFICATION_RECORDS = 10_000
"""Hard safety bound for the verification-record collection."""

MAX_DECISION_RECORDS = 10_000
"""Hard safety bound for the decision-record collection."""

MAX_DECISION_BATCHES = 2_000
"""Hard safety bound for the decision-batch collection."""

AR203_COLLECTIONS = (
    "capability_records",
    "verifications",
    "decision_batches",
    "decisions",
)
"""The AR-203 record collections, additive and optional like every earlier family."""

MAX_ARTIFACT_RECORDS = 5_000
"""Hard safety bound for the AR-204 externalized-output reference collection."""

MAX_COMPACTION_RECORDS = 500
"""Hard safety bound for the AR-204 compaction records (each names a full archive)."""

AR204_COLLECTIONS = (
    "artifacts",
    "compaction_records",
)
"""The AR-204 economics collections, additive and optional like every earlier family."""

_COLLECTION_LIMITS = {
    "capability_records": MAX_CAPABILITY_RECORDS,
    "verifications": MAX_VERIFICATION_RECORDS,
    "decisions": MAX_DECISION_RECORDS,
    "decision_batches": MAX_DECISION_BATCHES,
    "artifacts": MAX_ARTIFACT_RECORDS,
    "compaction_records": MAX_COMPACTION_RECORDS,
    "decision_plans": MAX_DECISION_PLANS,
    "decision_graphs": MAX_DECISION_GRAPHS,
    "decision_cache": MAX_DECISION_CACHE_ENTRIES,
    "decision_consensus": MAX_DECISION_CONSENSUS,
    "generation_justifications": MAX_GENERATION_JUSTIFICATIONS,
    "decision_outcomes": MAX_DECISION_OUTCOMES,
}


def require_collection_capacity(state: Mapping[str, Any], key: str) -> None:
    """Refuse to append to a bounded engine collection past its bound.

    The key must be a declared collection, so a typo at a call site fails closed
    instead of silently skipping the bound. Evidence is refused rather than
    truncated.
    """
    limit = _COLLECTION_LIMITS.get(key)
    if limit is None:
        raise ContractError(
            f"{key!r} is not a bounded engine record collection; the bound applies to "
            + ", ".join([*AR203_COLLECTIONS, *AR204_COLLECTIONS, *AR205D_COLLECTIONS])
        )
    values = state.get(key)
    if values is None:
        return
    if not isinstance(values, list):
        raise ContractError(f"{key} is not a list; the bounded collections are append-only lists")
    if len(values) >= limit:
        raise ContractError(
            f"{key} has reached its safety bound of {limit} records; further records are refused "
            "rather than truncated"
        )


def _enum_problems(record: Mapping[str, Any], name: str, allowed: Iterable[str], problems: list[str]) -> str:
    value = str(record.get(name, ""))
    if value not in allowed:
        problems.append(f"{record.get('_kind', 'record')} has an unsupported {name}: {value or 'missing'}")
    return value


def capability_record_problems(record: Mapping[str, Any]) -> list[str]:
    """Structural validation of one capability-registry record (fail closed)."""
    problems: list[str] = []
    if not isinstance(record, Mapping):
        return ["capability record is not an object"]
    if record.get("schema_version") not in READABLE_CAPABILITY_SCHEMAS:
        problems.append(f"capability record schema is unsupported: {record.get('schema_version')!r}")
    if not design_id_matches("cap", str(record.get("capability_record_id", ""))):
        problems.append("capability record has a malformed capability record id")
    for name in ("capability_id", "adapter", "recorded_at", "mechanism"):
        _non_empty(record, name, problems)
    _enum_problems(record, "family", CAPABILITY_FAMILIES, problems)
    status = _enum_problems(record, "status", CAPABILITY_STATUSES, problems)
    _enum_problems(record, "freshness", CAPABILITY_FRESHNESS, problems)
    if not isinstance(record.get("evidence"), list):
        problems.append("capability record evidence is not a list")
    if status == "UNAVAILABLE" and not str(record.get("reason", "")).strip():
        problems.append("an unavailable capability must record the reason it is unavailable")
    if status == "EXERCISED":
        probe_artifact = str(record.get("mechanism", "")).startswith("probe:") and any(
            str(row.get("path", "") or "") or str(row.get("output_sha256", "") or "")
            for row in record.get("evidence", [])
            if isinstance(row, Mapping)
        )
        if not str(record.get("execution", "")).strip() and not probe_artifact:
            problems.append(
                "a capability that is EXERCISED must name the engine execution that exercised it or a "
                "recorded probe artifact"
            )
    if status == "VERIFIED":
        if not design_id_matches("vrf", str(record.get("verification_id", ""))):
            problems.append("a verified capability must cite an existing verification record")
    if str(record.get("observed_by", "")) in ("worker", "worker-output", "handoff", "self-reported"):
        problems.append("capability observations must come from the engine or an engine-side probe, not worker prose")
    return list(dict.fromkeys(problems))


def verification_record_problems(record: Mapping[str, Any]) -> list[str]:
    """Structural validation of one verification record (fail closed)."""
    problems: list[str] = []
    if not isinstance(record, Mapping):
        return ["verification record is not an object"]
    if record.get("schema_version") not in READABLE_VERIFICATION_SCHEMAS:
        problems.append(f"verification record schema is unsupported: {record.get('schema_version')!r}")
    if not design_id_matches("vrf", str(record.get("verification_id", ""))):
        problems.append("verification record has a malformed verification id")
    for name in ("subject", "claim", "method", "recorded_at"):
        _non_empty(record, name, problems)
    level = _enum_problems(record, "level", VERIFICATION_LEVELS, problems)
    _enum_problems(record, "freshness", FRESHNESS_STATES, problems)
    if not isinstance(record.get("evidence"), list):
        problems.append("verification record evidence is not a list")
    if not isinstance(record.get("limitations"), list):
        problems.append("verification record limitations is not a list")
    if not isinstance(record.get("dependencies"), Mapping):
        problems.append("verification record dependencies is not a mapping")
    if level in ("OBSERVED", "REPRODUCED", "INDEPENDENTLY_REPRODUCED", "VERIFIED"):
        if not re.fullmatch(r"exe_[0-9TZ]+_[0-9a-f]{8}", str(record.get("execution_id", ""))) and not str(
            record.get("observed_anchor", "")
        ).strip():
            problems.append(
                f"a verification at {level} must name the engine execution that observed it or the "
                "engine-recorded anchor the observation came from"
            )
        if not str(record.get("revision", "")).strip():
            problems.append(f"a verification at {level} must be bound to a revision")
    if level in ("REPRODUCED", "INDEPENDENTLY_REPRODUCED", "VERIFIED"):
        if not _is_sha256(record.get("observed_digest")):
            problems.append(f"a verification at {level} must record the observed digest it reproduced")
        if not _is_sha256(record.get("reproduced_digest")):
            problems.append(f"a verification at {level} must record the reproduced digest")
    if level in ("INDEPENDENTLY_REPRODUCED", "VERIFIED"):
        if not re.fullmatch(r"exe_[0-9TZ]+_[0-9a-f]{8}", str(record.get("verifier_execution_id", ""))):
            problems.append(f"a verification at {level} must name the independent verifying execution")
        if str(record.get("execution_id", "")) == str(record.get("verifier_execution_id", "")):
            problems.append(
                f"a verification at {level} names one execution as both observer and independent verifier"
            )
    if level == "VERIFIED" and str(record.get("freshness", "")) != "CURRENT":
        problems.append("a verification cannot be VERIFIED while its dependencies are not current")
    if record.get("superseded_by") and str(record.get("freshness", "")) != "SUPERSEDED":
        problems.append("a superseded verification record must record freshness SUPERSEDED")
    return list(dict.fromkeys(problems))


def decision_record_problems(record: Mapping[str, Any]) -> list[str]:
    """Structural validation of one decision record (fail closed)."""
    problems: list[str] = []
    if not isinstance(record, Mapping):
        return ["decision record is not an object"]
    if record.get("schema_version") not in READABLE_DECISION_SCHEMAS:
        problems.append(f"decision record schema is unsupported: {record.get('schema_version')!r}")
    if not design_id_matches("dec", str(record.get("decision_id", ""))):
        problems.append("decision record has a malformed decision id")
    if not design_id_matches("dcb", str(record.get("batch_id", ""))):
        problems.append("decision record names no batch")
    for name in ("question_id", "recorded_at", "policy_version", "contract_version"):
        _non_empty(record, name, problems)
    _enum_problems(record, "primitive", DECISION_PRIMITIVES, problems)
    _enum_problems(record, "confidence_kind", CONFIDENCE_KINDS, problems)
    _enum_problems(record, "consequence", DECISION_CONSEQUENCES, problems)
    status = _enum_problems(record, "status", DECISION_STATUSES, problems)
    if not _is_sha256(record.get("state_digest")):
        problems.append("decision record has no state digest")
    if not isinstance(record.get("options"), list):
        problems.append("decision record options is not a list")
    confidence = record.get("confidence")
    if confidence is not None:
        try:
            value = float(confidence)
        except (TypeError, ValueError):
            problems.append("decision record confidence is not a number")
        else:
            if not 0.0 <= value <= 1.0:
                problems.append("decision record confidence is outside [0, 1]")
    if str(record.get("confidence_kind", "")) == "NONE" and confidence is not None:
        problems.append("a decision with confidence_kind NONE cannot carry a confidence value")
    if confidence is not None and str(record.get("confidence_kind", "")) == "NONE":
        problems.append("a confidence value must record where it came from")
    if status == "answered" and not str(record.get("answer", "")).strip():
        problems.append("an answered decision must record its answer")
    if status == "answered" and record.get("answer_valid") is not True:
        problems.append("an answered decision must have validated its answer against the allowed space")
    if status == "invalid" and record.get("answer_valid") is not False:
        problems.append("an invalid decision must record answer_valid false")
    if str(record.get("authorization_effect", "")) != "none":
        problems.append(
            "a decision record must record that its authorization effect is none; "
            "decision confidence never grants authorization"
        )
    return list(dict.fromkeys(problems))


def decision_batch_problems(record: Mapping[str, Any]) -> list[str]:
    """Structural validation of one decision batch."""
    problems: list[str] = []
    if not isinstance(record, Mapping):
        return ["decision batch is not an object"]
    if record.get("schema_version") not in READABLE_DECISION_SCHEMAS:
        problems.append(f"decision batch schema is unsupported: {record.get('schema_version')!r}")
    if not design_id_matches("dcb", str(record.get("batch_id", ""))):
        problems.append("decision batch has a malformed batch id")
    for name in ("recorded_at", "provider", "policy_version", "contract_version"):
        _non_empty(record, name, problems)
    if record.get("provider_available") and not str(record.get("model", "")).strip():
        problems.append("an answered decision batch must record the model that answered it")
    if not _is_sha256(record.get("state_digest")):
        problems.append("decision batch has no state digest")
    questions = record.get("questions")
    if not isinstance(questions, list) or not questions:
        problems.append("decision batch lists no questions")
        return list(dict.fromkeys(problems))
    seen: set[str] = set()
    for item in questions:
        if not isinstance(item, Mapping):
            problems.append("decision batch question is malformed")
            continue
        question_id = str(item.get("question_id", ""))
        if not question_id:
            problems.append("decision batch question has no question id")
        if question_id in seen:
            problems.append(f"decision batch repeats question id {question_id}")
        seen.add(question_id)
        if str(item.get("primitive", "")) not in DECISION_PRIMITIVES:
            problems.append(f"decision batch question names an unsupported primitive: {item.get('primitive') or 'missing'}")
    if str(record.get("status", "")) not in ("answered", "partial", "failed", "unavailable"):
        problems.append(f"decision batch has an unsupported status: {record.get('status') or 'missing'}")
    if str(record.get("authorization_effect", "")) != "none":
        problems.append("a decision batch must record that its authorization effect is none")
    return list(dict.fromkeys(problems))


# ------------------------------------------- AR-205D decision-intelligence records


def _decision_intelligence_schema(record: Mapping[str, Any], problems: list[str], label: str) -> None:
    if record.get("schema_version") not in READABLE_DECISION_INTELLIGENCE_SCHEMAS:
        problems.append(f"{label} schema is unsupported: {record.get('schema_version')!r}")


def decision_plan_problems(record: Mapping[str, Any]) -> list[str]:
    """Structural validation of one compiled decision plan (fail closed)."""
    problems: list[str] = []
    if not isinstance(record, Mapping):
        return ["decision plan is not an object"]
    _decision_intelligence_schema(record, problems, "decision plan")
    if not design_id_matches("dcp", str(record.get("plan_id", ""))):
        problems.append("decision plan has a malformed plan id")
    _non_empty(record, "recorded_at", problems)
    if not isinstance(record.get("deterministic_facts"), list):
        problems.append("decision plan deterministic_facts is not a list")
    if not isinstance(record.get("bounded_questions"), list):
        problems.append("decision plan bounded_questions is not a list")
    if not isinstance(record.get("generative_needs"), list):
        problems.append("decision plan generative_needs is not a list")
    if not isinstance(record.get("dependencies"), Mapping):
        problems.append("decision plan dependencies is not a mapping")
    if not isinstance(record.get("fallback_policy"), Mapping):
        problems.append("decision plan fallback_policy is not a mapping")
    counts = record.get("classifications")
    if not isinstance(counts, Mapping):
        problems.append("decision plan classifications is not a mapping")
    else:
        for name in counts:
            if str(name) not in DECISION_CLASSIFICATIONS:
                problems.append(f"decision plan uses an unsupported classification: {name!r}")
    for item in record.get("bounded_questions") or []:
        if not isinstance(item, Mapping):
            problems.append("decision plan bounded question is malformed")
            continue
        if str(item.get("classification", "")) != "BOUNDED":
            problems.append("a bounded question must record classification BOUNDED")
        if not str(item.get("requirement_id", "")).strip():
            problems.append("a decision plan question has no requirement id")
        for dependency in item.get("depends_on") or []:
            if str(dependency) == str(item.get("requirement_id", "")):
                problems.append(
                    f"decision plan question {item.get('requirement_id')} depends on itself"
                )
    for item in record.get("generative_needs") or []:
        if not isinstance(item, Mapping):
            problems.append("decision plan generative need is malformed")
            continue
        if str(item.get("reason", "")) not in GENERATION_REASONS:
            problems.append(
                f"a generative need must record a declared generation reason: {item.get('reason')!r}"
            )
    if str(record.get("authorization_effect", "")) != "none":
        problems.append("a decision plan never grants authorization")
    return list(dict.fromkeys(problems))


def _graph_cycle_problems(nodes: Mapping[str, set[str]]) -> list[str]:
    problems: list[str] = []
    visiting: set[str] = set()
    visited: set[str] = set()

    def walk(node: str) -> bool:
        if node in visited:
            return False
        if node in visiting:
            return True
        visiting.add(node)
        for dependency in sorted(nodes.get(node, set())):
            if dependency in nodes and walk(dependency):
                return True
        visiting.discard(node)
        visited.add(node)
        return False

    for node in sorted(nodes):
        if walk(node):
            problems.append(f"the decision graph contains a cycle through {node!r}")
            break
    return problems


def decision_graph_record_problems(record: Mapping[str, Any]) -> list[str]:
    """Structural validation of one decision graph record (fail closed)."""
    problems: list[str] = []
    if not isinstance(record, Mapping):
        return ["decision graph is not an object"]
    _decision_intelligence_schema(record, problems, "decision graph")
    if not design_id_matches("dcg", str(record.get("graph_id", ""))):
        problems.append("decision graph has a malformed graph id")
    _non_empty(record, "recorded_at", problems)
    nodes = record.get("nodes")
    if not isinstance(nodes, list) or not nodes:
        problems.append("decision graph lists no nodes")
        return list(dict.fromkeys(problems))
    ids: list[str] = []
    dependency_map: dict[str, set[str]] = {}
    for item in nodes:
        if not isinstance(item, Mapping):
            problems.append("decision graph node is malformed")
            continue
        node_id = str(item.get("id", ""))
        if not node_id:
            problems.append("decision graph node has no id")
            continue
        if node_id in ids:
            problems.append(f"decision graph repeats node id {node_id!r}")
        ids.append(node_id)
        if str(item.get("kind", "")) not in DECISION_GRAPH_NODE_KINDS:
            problems.append(f"decision graph node {node_id} names an unsupported kind")
        if str(item.get("status", "")) not in DECISION_GRAPH_STATUSES:
            problems.append(f"decision graph node {node_id} has an unsupported status")
        dependencies = {str(value) for value in (item.get("dependencies") or [])}
        if node_id in dependencies:
            problems.append(f"decision graph node {node_id} depends on itself")
        dependency_map[node_id] = dependencies
    known = set(ids)
    for node_id, dependencies in dependency_map.items():
        missing = sorted(dependencies - known)
        if missing:
            problems.append(f"decision graph node {node_id} names missing dependencies: {', '.join(missing)}")
    problems.extend(_graph_cycle_problems(dependency_map))
    if str(record.get("authorization_effect", "")) != "none":
        problems.append("a decision graph never grants authorization; the human gate stays human")
    return list(dict.fromkeys(problems))


def decision_cache_entry_problems(record: Mapping[str, Any]) -> list[str]:
    """Structural validation of one decision-cache entry (fail closed).

    The key must bind the decision definition, the projected state, the provider
    and one concrete model version. A cache entry without a concrete model
    version is refused: an alias can move under a cached answer.
    """
    problems: list[str] = []
    if not isinstance(record, Mapping):
        return ["decision cache entry is not an object"]
    _decision_intelligence_schema(record, problems, "decision cache entry")
    if not design_id_matches("dch", str(record.get("cache_id", ""))):
        problems.append("decision cache entry has a malformed cache id")
    if not _is_sha256(record.get("key")):
        problems.append("decision cache entry has no key digest")
    _non_empty(record, "question_id", problems)
    _enum_problems(record, "primitive", DECISION_PRIMITIVES, problems)
    _non_empty(record, "definition_version", problems)
    if not _is_sha256(record.get("state_digest")):
        problems.append("decision cache entry has no state digest")
    _non_empty(record, "provider", problems)
    if not str(record.get("model_version", "")).strip():
        problems.append(
            "decision cache entry has no concrete model version; a cache key must bind a concrete model"
        )
    _non_empty(record, "policy_version", problems)
    _non_empty(record, "recorded_at", problems)
    if str(record.get("freshness", "")) not in ("CURRENT", "STALE", "REVOKED", "SUPERSEDED"):
        problems.append(f"decision cache entry has an unsupported freshness: {record.get('freshness')!r}")
    _enum_problems(record, "confidence_kind", CONFIDENCE_KINDS, problems)
    if not isinstance(record.get("answers"), list):
        problems.append("decision cache entry answers is not a list")
    if str(record.get("authorization_effect", "")) != "none":
        problems.append("a cached decision never carries an authorization effect")
    return list(dict.fromkeys(problems))


def decision_consensus_problems(record: Mapping[str, Any]) -> list[str]:
    """Structural validation of one second-opinion comparison record."""
    problems: list[str] = []
    if not isinstance(record, Mapping):
        return ["decision consensus record is not an object"]
    _decision_intelligence_schema(record, problems, "decision consensus record")
    if not design_id_matches("dcn", str(record.get("consensus_id", ""))):
        problems.append("decision consensus record has a malformed consensus id")
    _non_empty(record, "question_id", problems)
    _non_empty(record, "recorded_at", problems)
    _enum_problems(record, "policy", CONSENSUS_POLICIES, problems)
    _enum_problems(record, "verdict", CONSENSUS_VERDICTS, problems)
    if str(record.get("establishes_truth", "")) not in ("", "false", "False"):
        problems.append("decision consensus never establishes truth")
    if str(record.get("authorization_effect", "")) != "none":
        problems.append("decision consensus never grants authorization")
    return list(dict.fromkeys(problems))


def generation_justification_problems(record: Mapping[str, Any]) -> list[str]:
    """Structural validation of one generation-justification record."""
    problems: list[str] = []
    if not isinstance(record, Mapping):
        return ["generation justification is not an object"]
    _decision_intelligence_schema(record, problems, "generation justification")
    if not design_id_matches("gen", str(record.get("justification_id", ""))):
        problems.append("generation justification has a malformed justification id")
    _enum_problems(record, "reason", GENERATION_REASONS, problems)
    _non_empty(record, "recorded_at", problems)
    if str(record.get("authorization_effect", "")) != "none":
        problems.append("a generation justification never grants authorization")
    return list(dict.fromkeys(problems))


def decision_outcome_problems(record: Mapping[str, Any]) -> list[str]:
    """Structural validation of one calibration outcome record."""
    problems: list[str] = []
    if not isinstance(record, Mapping):
        return ["decision outcome is not an object"]
    _decision_intelligence_schema(record, problems, "decision outcome")
    if not design_id_matches("dco", str(record.get("outcome_id", ""))):
        problems.append("decision outcome has a malformed outcome id")
    if not design_id_matches("dec", str(record.get("decision_id", ""))):
        problems.append("decision outcome names no decision record")
    _enum_problems(record, "category", CALIBRATION_OUTCOME_CATEGORIES, problems)
    _non_empty(record, "recorded_at", problems)
    if not isinstance(record.get("evidence"), list):
        problems.append("decision outcome evidence is not a list")
    if str(record.get("authorization_effect", "")) != "none":
        problems.append("a decision outcome never grants authorization")
    return list(dict.fromkeys(problems))
