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
    "acceptance-claim": (
        "actor",
        "statement",
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

# ---------------------------------------------------------------------------
# AR-220 grounded-design vocabulary.
#
# These extend the AR-202D reference family rather than replacing it. A
# ``DesignReference`` is an AR-202D reference record plus the classification a
# design workflow needs in order to reason about *which kind of evidence* it is
# holding, and the AR-202D lifecycle still governs how that evidence was
# reached. Nothing here is a trust score.
# ---------------------------------------------------------------------------

REFERENCE_SOURCE_KINDS = (
    "FIRST_PARTY_DESIGN_MD",
    "CURATED_DESIGN_ANALYSIS",
    "LIVE_SITE_INSPECTION",
    "FIGMA_DOCUMENT",
    "SOURCE_REPOSITORY",
    "COMPONENT_REGISTRY",
    "LOCAL_DESIGN_FILE",
    "MCP_RESULT",
    "CLI_RESULT",
    "SECONDARY_DESCRIPTION",
)
"""What kind of source produced a design reference.

The kinds are not equal trust and are never collapsed into one ranking. A
curated analysis of a real design system is useful evidence about that system's
public appearance, and it is *not* the vendor's own design documentation. The
kind is recorded so a reader can tell the two apart without re-deriving it.

``FIRST_PARTY_DESIGN_MD``    published by the brand itself
``CURATED_DESIGN_ANALYSIS``  a third party's analysis of publicly visible design
``LIVE_SITE_INSPECTION``     a rendering or a live page that was looked at
``FIGMA_DOCUMENT``           a design-tool document
``SOURCE_REPOSITORY``        tokens/components read out of a code repository
``COMPONENT_REGISTRY``       a published component registry entry
``LOCAL_DESIGN_FILE``        a design document already inside this project
``MCP_RESULT``               returned by an MCP transport
``CLI_RESULT``               returned by a CLI transport
``SECONDARY_DESCRIPTION``    prose describing a design, with nothing inspected
"""

REFERENCE_EVIDENCE_LEVELS = (
    "DIRECTLY_INSPECTED",
    "SOURCE_INSPECTED",
    "CAPTURED",
    "CURATED_ANALYSIS",
    "SECONDARY_DESCRIPTION",
    "UNVERIFIED",
)
"""How the evidence behind a reference was actually obtained.

These deliberately echo :data:`RENDERED_EVIDENCE_STATES`: a claim is never
recorded at a strength above what was performed, and ``UNVERIFIED`` is a valid,
recorded answer rather than an absence.

``DIRECTLY_INSPECTED``     the source itself was read or looked at
``SOURCE_INSPECTED``       the primary source code/design was inspected
``CAPTURED``               a rendered artifact was captured and hashed
``CURATED_ANALYSIS``       a third party's published analysis was read
``SECONDARY_DESCRIPTION``  prose only; nothing was inspected
``UNVERIFIED``             a claim exists with no supporting retrieval
"""

REFERENCE_ROLES = (
    "PRIMARY_DIRECTION",
    "INTERACTION_REFERENCE",
    "LAYOUT_REFERENCE",
    "TYPOGRAPHY_REFERENCE",
    "COMPONENT_REFERENCE",
    "IMPLEMENTATION_REFERENCE",
    "COUNTER_REFERENCE",
)
"""What job one reference is being asked to do.

A reference may hold several roles at once, and ``COUNTER_REFERENCE`` is a role
rather than a rejection: it records the anti-pattern the design must avoid
becoming, with the same evidence requirement as any other role.

``IMPLEMENTATION_REFERENCE`` is deliberately distinct from the aesthetic roles.
``Linear`` is hierarchy evidence; a resizable-panel implementation is
implementation evidence. Conflating them is how a reference turns into a
clone instruction.
"""

REFERENCE_TREATMENTS = ("BORROW", "ADAPT", "AVOID")
"""How one reference's characteristics may be used.

``BORROW``  use the principle as observed
``ADAPT``   use the principle, changed for this project
``AVOID``   the observed characteristic is the anti-pattern here

This is the executable form of "a reference is evidence, not an instruction to
copy": every extracted characteristic must land in exactly one of the three.
"""

REFERENCE_ACCESS_MODES = (
    "PUBLIC",
    "ACCESS_RESTRICTED",
    "DECLARED_LOCAL",
    "UNREACHABLE",
)
"""How a source was reached.

``ACCESS_RESTRICTED`` is a real, valid, terminal answer. Ariadne never bypasses
a login, a paywall or an entitlement, and a source it may not read is recorded
as restricted rather than approximated.
"""

REFERENCE_FRESHNESS = ("CURRENT", "STALE", "CHANGED", "HISTORICAL", "UNKNOWN")
"""Freshness of a reference's evidence.

``STALE``/``CHANGED`` reuse :func:`ariadne_engine.references.reference_currentness`
so the AR-202D vocabulary is not forked. ``HISTORICAL`` is a deliberate choice -
a 1996 design is not stale if it was selected to be a 1996 design.
"""

REFERENCE_DIVERSITY_VERDICTS = ("DIVERSE_ENOUGH", "TOO_HOMOGENEOUS", "UNKNOWN")
"""The deterministic verdict over a reference set's spread.

``UNKNOWN`` is returned whenever the set carries too little classified
information to judge. Reporting ``UNKNOWN`` is honest; reporting
``DIVERSE_ENOUGH`` from three unclassified records would not be.
"""

REFERENCE_PATTERN_DIMENSIONS = (
    "information-hierarchy", "navigation", "density", "layout-grid", "spacing",
    "typography", "color-roles", "surface-treatment", "borders", "radii",
    "depth", "component-geometry", "interaction", "motion",
    "responsive-behavior", "imagery-media",
)
"""The controlled vocabulary a normalised observation is filed under.

This is deliberately *not* the same list as ``REFERENCE_ANALYSIS_DIMENSIONS``.
That list is what an analysis may be recorded against; this one is what a
normalised reference may have observed about it, so extraction and judgement
stay separate steps. Some useful references are qualitative, and a qualitative
observation belongs here too.
"""

REFERENCE_BUDGET_DEFAULTS = {
    "candidate_retrieval": 12,
    "deep_inspection": 5,
    "primary_references": 3,
    "counter_references": 2,
}
"""Bounded research budget defaults. Defaults, not universal truths.

A task may expand a budget, and the expansion is recorded with a reason rather
than applied silently. There is no unbounded "keep researching until satisfied"
loop, because that loop is how a reference budget stops existing.
"""

MAX_DESIGN_REFERENCE_BYTES = 262_144
"""Hard cap on one retrieved design document (256 KiB).

One giant design document must not be able to consume the run's whole context.
Oversized input is refused with a named reason, not truncated into a summary
that looks like the whole thing.
"""

MAX_DESIGN_REFERENCE_CANDIDATES = 64
"""Hard cap on the candidates one search may return into the run."""

MAX_DESIGN_REFERENCE_INDEX = 1024
"""Hard cap on a *supplied* catalog index.

Deliberately separate from :data:`MAX_DESIGN_REFERENCE_CANDIDATES`. The real
getdesign.md catalog publishes 550+ entries and the maintainers' own collection
index lists 73, so bounding the index at the candidate cap would refuse the real
corpus in order to protect a much smaller thing. What has to stay bounded is how
many candidates enter a run and how many are deeply inspected; a supplied index
is operator-supplied input to a local search, not a fan-out.
"""

MAX_DESIGN_REFERENCE_SECTIONS = 200
"""Hard cap on parsed sections in one design document."""

MAX_DESIGN_REFERENCE_PATTERNS = 64
"""Hard cap on normalised observations kept per reference."""

# ---------------------------------------------------------------------------
# AR-221 grounded design execution vocabulary
#
# Everything below exists to answer one question about a *code change*:
#
#     > Why was this component changed, and what says it should look like that?
#
# AR-220 classified the evidence a direction rests on. AR-221 classifies the
# obligations a direction imposes on the code, and requires every material one
# to name where it came from.
# ---------------------------------------------------------------------------

IMPLEMENTATION_CONSTRAINT_CATEGORIES = (
    "layout", "typography", "color", "spacing", "component", "interaction",
    "motion", "surface", "responsive", "accessibility", "navigation", "asset",
)
"""The kinds of obligation an approved direction can impose on an implementation.

A category is not a permission: it says which part of the interface a constraint
governs, so a colour constraint cannot be used to justify a navigation change and
a reviewer can see at a glance which parts of the design were actually specified.
"""

IMPLEMENTATION_CONSTRAINT_BASES = (
    "PROJECT_IDENTITY",
    "REQUIREMENT",
    "APPROVED_DIRECTION",
    "REFERENCE_PRINCIPLE",
    "IMPLEMENTATION_REFERENCE",
    "ENGINEERING_CONSTRAINT",
)
"""Where an implementation constraint comes from. Every material one must name one.

The order in this tuple is *not* the precedence order; :data:`CONSTRAINT_PRECEDENCE`
is. The tuple is the vocabulary, and it deliberately separates two things that are
usually conflated: a ``REFERENCE_PRINCIPLE`` says what an inspected source
demonstrates, while an ``APPROVED_DIRECTION`` says a human accepted it for *this*
project. A reference principle that was never adopted into an approved direction has
no standing to constrain code.
"""

CONSTRAINT_PRECEDENCE = {
    "REQUIREMENT": 100,
    "PROJECT_IDENTITY": 80,
    "APPROVED_DIRECTION": 60,
    "ENGINEERING_CONSTRAINT": 55,
    "IMPLEMENTATION_REFERENCE": 30,
    "REFERENCE_PRINCIPLE": 20,
}
"""Permanent precedence: the highest number wins.

    explicit user requirement
            >
    approved project identity / local design system
            >
    approved design direction
            >
    external references

``ENGINEERING_CONSTRAINT`` sits between the direction and an implementation
reference because a correct engineering constraint (a build that must typecheck, a
route that must exist) outranks a borrowed pattern while still losing to a human
decision. Accessibility is not in this table at all: it is a floor under every row,
enforced by :data:`ACCESSIBILITY_FLOOR_BASES` rather than by out-ranking anything.
"""

ACCESSIBILITY_FLOOR_BASES = ("REQUIREMENT", "PROJECT_IDENTITY", "ENGINEERING_CONSTRAINT")
"""Bases an accessibility constraint may legitimately hold.

An accessibility obligation may never be introduced *by* a reference principle, and
no other basis may cancel one. That asymmetry is the point: inspiration cannot
justify removing keyboard access, focus visibility, semantics, labels, contrast,
reduced-motion support or touch targets.
"""

PLAN_STATUSES = ("READY", "IMPLEMENTING", "IMPLEMENTED", "MECHANICALLY_VALIDATED", "ESCALATED", "REFUSED")
"""Lifecycle of one ``DesignImplementationPlan``.

``MECHANICALLY_VALIDATED`` is the ceiling AR-221 can reach. There is deliberately no
``ACCEPTED`` and no ``APPROVED``: source inspection can prove that code exists and
passes its checks, and cannot prove that it looks right. Judging appearance is
AR-222's job and it needs rendered evidence AR-221 does not produce.
"""

COMPONENT_REUSE_DECISIONS = (
    "REUSE_PROJECT_COMPONENT",
    "ADAPT_PROJECT_COMPONENT",
    "USE_APPROVED_REGISTRY_COMPONENT",
    "BUILD_CUSTOM_COMPONENT",
)
"""How one required primitive will be obtained, in preference order.

The order is the decision procedure, not a ranking of desirability. External
registries are *last*, and only ever after the project's own components have been
inspected and found wanting. Generating a replacement for a component the repository
already ships is a defect, not a neutral choice, so it has to be recorded as one.
"""

REUSE_STATUSES = (
    "INSPECT_ONLY",
    "REUSE_ALLOWED",
    "REUSE_WITH_ATTRIBUTION",
    "REUSE_RESTRICTED",
    "UNKNOWN",
)
"""What may be done with a reusable implementation reference.

``UNKNOWN`` is not a permissive default. An unrecorded licence is an unrecorded
licence, and code copied under it is a liability the run cannot characterise. The
distinction matters most for the state a reader is most likely to misread as
permission.
"""

MATERIAL_DESIGN_CATEGORIES = (
    "brand_color",
    "type_family",
    "type_scale",
    "navigation_structure",
    "primary_layout",
    "component_geometry",
    "interaction_model",
    "motion_system",
    "surface_language",
    "responsive_structure",
    "asset_identity",
)
"""The design decisions that need grounding before they enter the code.

Everything outside this list is *incidental*: a 1px alignment correction, a padding
nudge, vendor-prefix normalisation, a browser quirk. Refusing incidental detail
would train the workflow to attach a rationale to every line, which is its own kind
of dishonesty - the traceability record stops meaning anything.
"""

CATEGORY_GROUNDS_MATERIAL = {
    "color": ("brand_color",),
    "typography": ("type_family", "type_scale"),
    "spacing": ("component_geometry",),
    "layout": ("primary_layout", "responsive_structure"),
    "navigation": ("navigation_structure",),
    "component": ("component_geometry",),
    "interaction": ("interaction_model",),
    "accessibility": ("interaction_model",),
    "motion": ("motion_system",),
    "surface": ("surface_language",),
    "responsive": ("responsive_structure",),
    "asset": ("asset_identity",),
}
"""Which material categories a plan constraint of each kind accounts for.

A declared correspondence rather than a name comparison, because the two vocabularies
answer different questions: a plan states *what it governs* (colour, navigation) while
the material detector reports *what changed in the source* (a radius, a landmark).
Matching the strings directly would ground a layout constraint for a font-size change
or refuse a navigation constraint for a `<nav>`, both of which are wrong in the same
direction - the trace would look complete and mean nothing.

``spacing`` maps to ``component_geometry`` deliberately. A padding nudge matches none
of the geometry signals and so stays incidental, while a row height, a min-width or a
radius does - which is the distinction between tuning and committing to a geometry.
Giving spacing its own material category would make every padding tweak look
deliberate.
"""

MAX_IMPLEMENTATION_CONSTRAINTS = 200
MAX_IMPLEMENTATION_CHANGES = 2_000
MAX_PLAN_FORBIDDEN_PATTERNS = 64
MAX_PLAN_REUSE_DECISIONS = 200
"""Bounds on one plan's tables.

A plan is an interface contract, not a document. Past these sizes it stops being
readable by the worker it is written for, and a rule nobody can read is not a rule.
"""


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

RENDER_CAPTURE_METHODS = ("offline-fixture", "declared-observer", "browser-render")
"""How a capture artifact was produced. ``offline-fixture`` is the deterministic
adapter AR-202D ships; ``declared-observer`` is an operator-declared external
observer that recorded the artifact itself and is trusted only as far as it
declares its method, environment and revision; ``browser-render`` (AR-222) is an
artifact a real rendering engine produced in this run, bound to the exact source
digest and environment that produced it.

The method names how the bytes were made. It never says whose judgement they
carry: a browser capture is evidence of what rendered, never evidence that the
render satisfies the direction."""

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
    # AR-222: the rendered-critique phase. Each is a distinct refusal, not a
    # synonym for RENDER_CAPTURE_FAILED, because they call for different
    # responses: an unavailable browser is an environment answer, a stale
    # capture is a re-capture, an exhausted budget is a human decision.
    "RENDER_CAPABILITY_UNAVAILABLE",
    "RENDER_STALE_EVIDENCE",
    "RENDER_CAPTURE_INVALID",
    "RENDER_CAPTURE_BUDGET_EXCEEDED",
    "RENDER_REVIEW_NOT_INDEPENDENT",
    "RENDER_REPAIR_LIMIT_EXHAUSTED",
    "DIRECTION_REVISION_REQUIRED",
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

# ------------------------------------------------------------------ AR-222

CAPTURE_PLAN_STATUSES = ("PLANNED", "CAPTURED", "PARTIAL", "ABANDONED")
"""Lifecycle of one bounded capture plan.

``PLANNED``   targets chosen and justified, nothing captured yet
``CAPTURED``   every planned target was captured and validated
``PARTIAL``    some targets were not captured, each with a recorded reason
``ABANDONED``  the plan was not executed; the reason is recorded
"""

CAPTURE_TARGET_BASES = ("REQUIREMENT", "DIRECTION_PRINCIPLE", "MATERIALITY", "REGRESSION")
"""Why a capture target exists. A target with no basis is a screenshot nobody asked for."""

CAPTURE_TARGET_KINDS = ("viewport-state", "interaction-state", "responsive-state", "theme-variant")
"""The four kinds of capture a plan may justify. Deliberately not a matrix."""

DEFAULT_CAPTURE_BUDGET = {
    "primary_viewport_states": 3,
    "interaction_states": 6,
    "responsive_captures": 3,
    "theme_variants": 2,
    "repair_capture_cycles": 2,
}
"""Bounded capture economics (AR-222).

These are *defaults*, not universal limits: a plan may exceed any of them by
recording a reason in ``budget_expansions``. What is not permitted is exceeding
one silently, or producing captures nobody can name a basis for. The
``repair_capture_cycles`` default is deliberately the same number as
``design_execution``'s repair budget, so one stage cannot claim a fresh
allowance for every phase.
"""

RENDER_OUTCOMES = (
    "RENDERED_DIRECTION_CONFORMANT",
    "RENDERED_WITH_KNOWN_FINDINGS",
    "DIRECTION_REVISION_REQUIRED",
    "RENDER_VALIDATION_BLOCKED",
)
"""The precise result of a rendered review. There is no ``looks good``.

``RENDERED_DIRECTION_CONFORMANT``    the render satisfies the approved direction
``RENDERED_WITH_KNOWN_FINDINGS``     it does not fully, and the gaps are named
``DIRECTION_REVISION_REQUIRED``      satisfying it would need a new direction
``RENDER_VALIDATION_BLOCKED``        the render could not be established here
"""

CRITIQUE_COVERAGE_STATES = ("REVIEWED", "PARTIAL", "NOT_APPLICABLE", "NOT_REVIEWED")
"""Per-dimension coverage. Reported instead of one scalar score.

``NOT_APPLICABLE`` is a real answer and is preferred over inventing criticism
about a dimension the surface does not have.
"""

FINDING_BASES = ("DETERMINISTIC", "BOUNDED_JUDGEMENT")
"""Whether a finding is a reproducible fact or a bounded qualitative judgement.

A qualitative judgement is never presented as a measurement. Both are findings;
collapsing them would let taste acquire the authority of arithmetic.
"""

ARTIFACT_VALIDATION_STATES = ("VALID", "BLANK", "LOADING", "ERROR_DOCUMENT", "UNREADABLE", "NO_CONTENT")
"""Why a captured artifact cannot stand as evidence of the intended interface.

These are refusals, not grades: an error page is not a badly designed page, and
critiquing one is a category error rather than a finding.
"""

REPAIR_ATTEMPT_OUTCOMES = ("VALIDATED", "FAILED_VALIDATION", "ABANDONED")
"""What one bounded repair attempt achieved before the next capture cycle."""

REPAIR_FINDING_STATES = (
    "OPEN",
    "ACCEPTED_FOR_REPAIR",
    "REPAIRED_CANDIDATE",
    "VERIFIED_RESOLVED",
    "STILL_PRESENT",
    "ESCALATED",
    "WAIVED_BY_HUMAN",
)
"""Finding lifecycle across a rendered repair cycle.

``REPAIRED_CANDIDATE`` means the worker changed something. Only an independent
re-review of fresh rendered evidence can produce ``VERIFIED_RESOLVED``; the
worker that made the change cannot be the party that closes its own finding.
"""

DIRECTION_BOUNDED_REPAIRS = (
    "increase hierarchy contrast",
    "reduce excessive spacing",
    "restore project accent",
    "fix panel proportions",
    "remove forbidden surface treatment",
    "correct typography scale",
    "improve focus visibility",
    "fix responsive overflow",
)
"""Named repairs that move a render *toward* an already-approved direction.

A repair outside this vocabulary is not automatically forbidden -- a blocking
accessibility failure is not cosmetic -- but it must be justified by a cited
principle, and one that would introduce a new visual language is refused with
``DIRECTION_REVISION_REQUIRED`` rather than quietly taken.
"""


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
    # AR-220: when a record carries an AR-220 classification block it is held to
    # the grounded-design vocabulary here, so the check runs on every lifecycle
    # transition rather than only at normalisation time.
    problems.extend(design_reference_classification_problems(record))
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
    "design_reference_sets",
    "design_implementation_plans", "design_component_inventories",
    "design_implementation_changes", "design_implementation_runs",
    # AR-222: the rendered-critique collections. `persistence.DESIGN_COLLECTIONS` must
    # name the same three, or a persisted run state would be neither defaulted nor
    # type-checked for them -- which is exactly the half-integration that
    # `design_reference_sets` suffered from.
    "rendered_evidence_sets", "rendered_critiques", "refinement_plans",
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


def reference_set_problems(record: Mapping[str, Any]) -> list[str]:
    """Structural validation for an AR-220 ``ReferenceSet`` record.

    A reference set exists to assemble enough evidence to support a design
    direction, so the refusals here are about evidential sufficiency rather than
    taste: a set with no primary reference has no direction to ground, and a
    set that records a counter-reference must record what it is countering.
    """
    problems: list[str] = []
    if str(record.get("schema_version", "")) != str(SCHEMA_DESIGN):
        problems.append("reference set carries the wrong schema version")
    for name in ("reference_set_id", "run_id", "requirement_scope", "created_at"):
        if not str(record.get(name, "")).strip():
            problems.append(f"reference set is missing {name}")
    members = record.get("members")
    if not isinstance(members, list):
        problems.append("reference set members must be a list")
        members = []
    if not members:
        problems.append("a reference set must contain at least one reference")
    seen: set[str] = set()
    role_counts: dict[str, int] = {}
    for member in members:
        if not isinstance(member, Mapping):
            problems.append("reference set member must be a mapping")
            continue
        reference_id = str(member.get("reference_id", "")).strip()
        if not reference_id:
            problems.append("reference set member names no reference")
            continue
        if reference_id in seen:
            problems.append(f"reference set lists {reference_id} more than once")
        seen.add(reference_id)
        if member.get("counter_pattern") is not None and "COUNTER_REFERENCE" in (member.get("roles") or []):
            if not str(member.get("counter_pattern", "")).strip():
                problems.append(
                    f"reference set member {reference_id} is a counter-reference and must record the "
                    "anti-pattern it rules out; disliking something is not a counter-reference"
                )
        for role in member.get("roles") or []:
            if str(role) not in REFERENCE_ROLES:
                problems.append(f"reference set member {reference_id} has an unknown role: {role}")
            else:
                role_counts[str(role)] = role_counts.get(str(role), 0) + 1
    if members and not role_counts.get("PRIMARY_DIRECTION"):
        problems.append(
            "a reference set with no PRIMARY_DIRECTION reference cannot ground a design direction"
        )
    coverage = record.get("coverage")
    if not isinstance(coverage, Mapping) or not str(coverage.get("verdict", "")):
        problems.append("a reference set must record a deterministic coverage verdict")
    diversity = record.get("diversity")
    if not isinstance(diversity, Mapping) or not str(diversity.get("verdict", "")):
        problems.append("a reference set must record a deterministic diversity verdict")
    budget = record.get("budget")
    if not isinstance(budget, Mapping) or not str(budget.get("verdict", "")):
        problems.append("a reference set must record its research budget verdict")
    return list(dict.fromkeys(problems))


def reference_set_member_problems(
    member: Mapping[str, Any], *, references_by_id: Mapping[str, Mapping[str, Any]]
) -> list[str]:
    """Cross-record checks a ``ReferenceSet`` cannot make on its own.

    A set may only name references that exist, and may only give a member a role
    that its own evidence supports. The second check is the one that matters:
    a curated analysis cannot be recorded as if it were a first-party design
    system just by naming it in a set.
    """
    problems: list[str] = []
    reference_id = str(member.get("reference_id", "")).strip()
    record = references_by_id.get(reference_id)
    if record is None:
        return [f"reference set names {reference_id or 'an unnamed reference'}, which does not exist"]
    classification = record.get("classification")
    if not isinstance(classification, Mapping):
        problems.append(f"{reference_id} carries no source classification, so it cannot hold a set role")
        return problems
    declared = str(classification.get("source_kind", ""))
    if declared not in REFERENCE_SOURCE_KINDS:
        problems.append(f"{reference_id} has an unsupported source kind: {declared or 'missing'}")
    if str(classification.get("evidence_level", "")) not in REFERENCE_EVIDENCE_LEVELS:
        problems.append(f"{reference_id} has an unsupported evidence level")
    roles = [str(role) for role in (member.get("roles") or [])]
    if "COUNTER_REFERENCE" in roles and str(declared) == "FIRST_PARTY_DESIGN_MD":
        # Not impossible, but it must be said out loud: a vendor's own design
        # system used as an anti-pattern is a claim a reviewer should see.
        if not str(member.get("note", "")).strip():
            problems.append(
                f"{reference_id} is a first-party source used as a counter-reference and must say why"
            )
    treatments = member.get("treatments")
    if treatments is not None:
        if not isinstance(treatments, list) or not treatments:
            problems.append(f"{reference_id} declares treatments and must list at least one")
        else:
            for treatment in treatments:
                if not isinstance(treatment, Mapping):
                    problems.append(f"{reference_id} declares a malformed treatment")
                    continue
                if str(treatment.get("treatment", "")) not in REFERENCE_TREATMENTS:
                    problems.append(f"{reference_id} declares an unknown treatment: {treatment.get('treatment')}")
                if not str(treatment.get("pattern", "")).strip():
                    problems.append(f"{reference_id} declares a treatment with no observed pattern")
    return problems


def design_reference_classification_problems(record: Mapping[str, Any]) -> list[str]:
    """Validate the AR-220 classification block of a reference record."""
    problems: list[str] = []
    classification = record.get("classification")
    if classification is None:
        return problems
    if not isinstance(classification, Mapping):
        return ["a reference classification must be a mapping"]
    source_kind = str(classification.get("source_kind", ""))
    if source_kind not in REFERENCE_SOURCE_KINDS:
        problems.append(f"unsupported reference source kind: {source_kind or 'missing'}")
    if str(classification.get("evidence_level", "")) not in REFERENCE_EVIDENCE_LEVELS:
        problems.append(f"unsupported reference evidence level: {classification.get('evidence_level') or 'missing'}")
    if str(classification.get("access_mode", "")) not in REFERENCE_ACCESS_MODES:
        problems.append(f"unsupported reference access mode: {classification.get('access_mode') or 'missing'}")
    if str(classification.get("freshness", "")) not in REFERENCE_FRESHNESS:
        problems.append(f"unsupported reference freshness: {classification.get('freshness') or 'missing'}")
    if not str(classification.get("source_provider", "")).strip():
        problems.append("a classified reference must name the provider it came from")
    if not str(classification.get("source_identity", "")).strip():
        problems.append("a classified reference must name a stable source identity")
    if not str(classification.get("retrieved_at", "")).strip():
        problems.append("a classified reference must record when it was retrieved")
    if not re.fullmatch(r"[0-9a-f]{64}", str(classification.get("content_digest", ""))):
        problems.append("a classified reference must bind its normalised record to a content digest")
    observed = record.get("observed_patterns")
    if observed is not None:
        if not isinstance(observed, list):
            problems.append("observed_patterns must be a list")
        else:
            if len(observed) > MAX_DESIGN_REFERENCE_PATTERNS:
                problems.append(
                    f"observed_patterns exceeds the bound of {MAX_DESIGN_REFERENCE_PATTERNS} entries"
                )
            for pattern in observed:
                if not isinstance(pattern, Mapping):
                    problems.append("observed pattern must be a mapping")
                    continue
                dimension = str(pattern.get("dimension", ""))
                if dimension not in REFERENCE_PATTERN_DIMENSIONS:
                    problems.append(f"unknown observed-pattern dimension: {dimension or 'missing'}")
                if not str(pattern.get("observation", "")).strip():
                    problems.append(f"an observed pattern on {dimension or 'an unnamed dimension'} says nothing")
                if dimension in ("behavior", "behaviour", "motion", "interaction") and not str(
                    pattern.get("basis", "")
                ).strip():
                    problems.append(
                        f"an observed {dimension} pattern must name the basis it was read from; "
                        "motion and behaviour cannot be observed in static text"
                    )
    treatments = record.get("treatments")
    if treatments is not None:
        if not isinstance(treatments, list) or not treatments:
            problems.append("treatments must be a non-empty list when present")
        else:
            for treatment in treatments:
                if not isinstance(treatment, Mapping):
                    problems.append("treatment must be a mapping")
                    continue
                if str(treatment.get("treatment", "")) not in REFERENCE_TREATMENTS:
                    problems.append(f"unknown reference treatment: {treatment.get('treatment')}")
                if not str(treatment.get("pattern", "")).strip():
                    problems.append("a treatment must name the observed pattern it applies to")
    return list(dict.fromkeys(problems))


def implementation_plan_problems(record: Mapping[str, Any]) -> list[str]:
    """Structural validation of one ``DesignImplementationPlan``.

    A plan converts an *approved* direction into obligations on code, so the
    refusals are about authority and traceability rather than taste:

    * it must be bound to a direction, a reference set and a recorded approval;
    * every material constraint must name a basis, and a basis has a precedence;
    * a constraint asserted by a reference principle may not claim the precedence of
      a human decision, because that is how a borrowed pattern becomes a rule;
    * an accessibility constraint may not be sourced from an external reference;
    * every AVOID treatment must arrive as a *detector*, not as prose a worker is
      asked to remember.
    """
    problems: list[str] = []
    if str(record.get("schema_version", "")) != str(SCHEMA_DESIGN):
        problems.append("implementation plan carries the wrong schema version")
    if not design_id_matches("dip", str(record.get("plan_id", ""))):
        problems.append("implementation plan has a malformed plan id")
    for name in ("run_id", "task_id", "direction_id", "reference_set_id", "created_at", "project_scope"):
        _non_empty(record, name, problems)
    binding = record.get("approval_binding")
    if not isinstance(binding, Mapping):
        problems.append("an implementation plan must bind an approval; a plan with no approval is a wish")
    else:
        if str(binding.get("gate", "")) != "G1D":
            problems.append(f"an implementation plan must bind gate G1D, not {binding.get('gate') or 'none'}")
        for name in ("approval_id", "direction_revision_hash", "approved_at", "identity", "channel"):
            if not str(binding.get(name, "")).strip():
                problems.append(f"implementation plan approval binding is missing {name}")
        if not _is_sha256(binding.get("direction_revision_hash")):
            problems.append("implementation plan approval binding is not bound to a direction revision digest")
        if str(binding.get("channel", "")) not in APPROVAL_CHANNELS:
            problems.append(f"implementation plan records an unknown approval channel: {binding.get('channel')}")

    if str(record.get("status", "")) not in PLAN_STATUSES:
        problems.append(f"implementation plan has an unsupported status: {record.get('status') or 'missing'}")

    surfaces = record.get("target_surfaces")
    if not isinstance(surfaces, list) or not [str(item).strip() for item in surfaces]:
        problems.append("an implementation plan must name the target surfaces it governs")

    constraints = record.get("constraints")
    if not isinstance(constraints, list):
        problems.append("implementation plan constraints must be a list")
        constraints = []
    elif not constraints:
        problems.append("an implementation plan states no implementation constraint")
    if len(constraints) > MAX_IMPLEMENTATION_CONSTRAINTS:
        problems.append(f"implementation plan exceeds the bound of {MAX_IMPLEMENTATION_CONSTRAINTS} constraints")
    seen_constraints: set[str] = set()
    for constraint in constraints:
        if not isinstance(constraint, Mapping):
            problems.append("implementation constraint must be a mapping")
            continue
        constraint_id = str(constraint.get("constraint_id", ""))
        if not design_id_matches("dic", constraint_id):
            problems.append(f"implementation constraint has a malformed id: {constraint_id or 'missing'}")
        elif constraint_id in seen_constraints:
            problems.append(f"implementation plan repeats constraint {constraint_id}")
        seen_constraints.add(constraint_id)
        if str(constraint.get("category", "")) not in IMPLEMENTATION_CONSTRAINT_CATEGORIES:
            problems.append(f"implementation constraint has an unsupported category: {constraint.get('category') or 'missing'}")
        basis = str(constraint.get("basis", ""))
        if basis not in IMPLEMENTATION_CONSTRAINT_BASES:
            problems.append(f"implementation constraint has an unsupported basis: {basis or 'missing'}")
        if not str(constraint.get("statement", "")).strip():
            problems.append(f"implementation constraint {constraint_id} states nothing")
        if not str(constraint.get("evidence", "")).strip():
            problems.append(
                f"implementation constraint {constraint_id} names a basis but no evidence; a basis "
                "without a source is a label"
            )
        if str(constraint.get("category", "")) == "accessibility" and basis not in ACCESSIBILITY_FLOOR_BASES:
            problems.append(
                f"accessibility constraint {constraint_id} is sourced from {basis or 'nothing'}; an external "
                "reference cannot be the origin of an accessibility obligation, and no reference may cancel one"
            )
        if str(constraint.get("accessibility_floor", "")) == "TRUE" and basis not in ACCESSIBILITY_FLOOR_BASES:
            problems.append(f"constraint {constraint_id} claims the accessibility floor from {basis or 'nothing'}")

    # Every AVOID treatment has to become a checkable prohibition. A rejection a
    # worker is merely *told* about is a rejection that survives review.
    treatments = record.get("borrow_adapt_avoid_bindings")
    if not isinstance(treatments, list) or not treatments:
        problems.append("an implementation plan binds no BORROW/ADAPT/AVOID treatment to any constraint")
    else:
        for binding_row in treatments:
            if not isinstance(binding_row, Mapping):
                problems.append("treatment binding must be a mapping")
                continue
            if str(binding_row.get("treatment", "")) not in REFERENCE_TREATMENTS:
                problems.append(f"unknown treatment in plan: {binding_row.get('treatment')}")
            if not str(binding_row.get("pattern", "")).strip():
                problems.append("a treatment binding must name the observed pattern it applies to")
            if str(binding_row.get("treatment", "")) == "ADAPT" and not str(binding_row.get("project_anchor", "")).strip():
                problems.append(
                    "an ADAPT treatment must name the project anchor it was transformed onto; an "
                    "adaptation with nothing to adapt to is a borrow recorded under another name"
                )

    forbidden = record.get("forbidden_copy_patterns")
    if not isinstance(forbidden, list):
        problems.append("forbidden_copy_patterns must be a list")
    else:
        if len(forbidden) > MAX_PLAN_FORBIDDEN_PATTERNS:
            problems.append(f"forbidden_copy_patterns exceeds the bound of {MAX_PLAN_FORBIDDEN_PATTERNS}")
        for row in forbidden:
            if not isinstance(row, Mapping):
                problems.append("forbidden copy pattern must be a mapping")
                continue
            if not str(row.get("pattern_id", "")).strip():
                problems.append("a forbidden copy pattern must have an id")
            if not str(row.get("reason", "")).strip():
                problems.append(f"forbidden copy pattern {row.get('pattern_id')} records no reason")
            if not isinstance(row.get("detectors"), list) or not row.get("detectors"):
                problems.append(
                    f"forbidden copy pattern {row.get('pattern_id')} has no detector; a prohibition "
                    "nobody can evaluate is an intention"
                )

    reuse = record.get("component_reuse_decisions")
    if not isinstance(reuse, list) or not reuse:
        problems.append("an implementation plan records no component reuse decision")
    else:
        if len(reuse) > MAX_PLAN_REUSE_DECISIONS:
            problems.append(f"component_reuse_decisions exceeds the bound of {MAX_PLAN_REUSE_DECISIONS}")
        for row in reuse:
            if not isinstance(row, Mapping):
                problems.append("component reuse decision must be a mapping")
                continue
            if str(row.get("decision", "")) not in COMPONENT_REUSE_DECISIONS:
                problems.append(f"unsupported component reuse decision: {row.get('decision') or 'missing'}")
            if not str(row.get("need", "")).strip():
                problems.append("a component reuse decision must name the need it answers")
            if not str(row.get("reason", "")).strip():
                problems.append(f"component reuse decision for {row.get('need')} records no reason")
            if str(row.get("decision", "")) == "USE_APPROVED_REGISTRY_COMPONENT" and not str(
                row.get("approval_id", "")
            ).strip():
                problems.append(
                    f"component reuse decision for {row.get('need')} selects an approved registry component "
                    "with no recorded approval; an authorization id is a claim like any other"
                )

    if not isinstance(record.get("validation_requirements"), list) or not record.get("validation_requirements"):
        problems.append("an implementation plan declares no mechanical validation requirement")

    for name in ("requirement_bindings", "reference_bindings", "target_surfaces"):
        value = record.get(name)
        if value is not None and not isinstance(value, list):
            problems.append(f"implementation plan {name} must be a list")

    provenance = record.get("provenance")
    if not isinstance(provenance, Mapping) or not str(provenance.get("created_by", "")).strip():
        problems.append("implementation plan carries no provenance")
    return list(dict.fromkeys(problems))


def component_inventory_problems(record: Mapping[str, Any]) -> list[str]:
    """Structural validation of one project component inventory."""
    problems: list[str] = []
    if str(record.get("schema_version", "")) != str(SCHEMA_DESIGN):
        problems.append("component inventory carries the wrong schema version")
    if not design_id_matches("dci", str(record.get("inventory_id", ""))):
        problems.append("component inventory has a malformed inventory id")
    for name in ("run_id", "task_id", "project_root", "recorded_at"):
        _non_empty(record, name, problems)
    if not isinstance(record.get("probes"), list) or not record.get("probes"):
        problems.append("a component inventory records no probe")
    components = record.get("components")
    if not isinstance(components, list):
        problems.append("component inventory components must be a list")
    else:
        for row in components:
            if not isinstance(row, Mapping):
                problems.append("inventory component must be a mapping")
                continue
            if not str(row.get("path", "")).strip():
                problems.append("an inventory component must name the path it was found at")
            if _path_escapes_project(str(row.get("path", ""))):
                problems.append(f"inventory component path is not project-relative: {row.get('path')}")
    if not isinstance(record.get("reuse_decisions"), list) or not record.get("reuse_decisions"):
        problems.append("a component inventory records no reuse decision")
    return list(dict.fromkeys(problems))


def _path_escapes_project(value: str) -> bool:
    """Whether a recorded change path reaches outside the project.

    A drive-letter path is absolute without a leading slash or a ``..``, so a check
    that only looks for those two treats ``C:/Windows/System32/config`` as
    project-relative - on the one platform where that matters most.
    """
    normalised = str(value).replace("\\", "/")
    if normalised.startswith(("/", "\\")):
        return True
    if ".." in normalised.split("/"):
        return True
    return bool(re.match(r"^[A-Za-z]:[\\/]", normalised))


def implementation_change_problems(record: Mapping[str, Any]) -> list[str]:
    """Structural validation of one implementation change record."""
    problems: list[str] = []
    if str(record.get("schema_version", "")) != str(SCHEMA_DESIGN):
        problems.append("implementation change carries the wrong schema version")
    if not design_id_matches("dic", str(record.get("change_id", ""))):
        problems.append(f"implementation change has a malformed id: {record.get('change_id') or 'missing'}")
    for name in ("plan_id", "task_id", "path", "change_kind", "recorded_at"):
        _non_empty(record, name, problems)
    if _path_escapes_project(str(record.get("path", ""))):
        problems.append(f"implementation change path escapes the project: {record.get('path')}")
    verdict = str(record.get("verdict", ""))
    if verdict not in IMPLEMENTATION_CHANGE_VERDICTS:
        problems.append(f"implementation change has an unsupported verdict: {verdict or 'missing'}")
    if not str(record.get("implementation_source", "")).strip():
        problems.append(f"implementation change {record.get('change_id')} names no implementation source")
    if verdict == "UNGROUNDED_DESIGN_CHANGE" and not str(record.get("problem", "")).strip():
        problems.append("an ungrounded design change must say what is ungrounded about it")
    if verdict == "GROUNDED" and not record.get("constraint_ids"):
        problems.append(
            f"implementation change {record.get('change_id')} claims to be grounded but cites no "
            "implementation constraint"
        )
    if verdict == "GROUNDED" and not record.get("grounding_constraint_ids"):
        problems.append(
            f"implementation change {record.get('change_id')} is GROUNDED but records no grounding "
            "constraint; citing a constraint that does not account for the change is the same as "
            "citing nothing"
        )
    for name in ("requirement_ids", "principle_ids", "reference_ids"):
        value = record.get(name)
        if value is not None and not isinstance(value, list):
            problems.append(f"implementation change {name} must be a list")
    return list(dict.fromkeys(problems))


def implementation_run_problems(record: Mapping[str, Any]) -> list[str]:
    """Structural validation of one grounded implementation run."""
    problems: list[str] = []
    if str(record.get("schema_version", "")) != str(SCHEMA_DESIGN):
        problems.append("implementation run carries the wrong schema version")
    if not design_id_matches("dir", str(record.get("run_record_id", ""))):
        problems.append("implementation run has a malformed run record id")
    for name in ("plan_id", "task_id", "started_at"):
        _non_empty(record, name, problems)
    if str(record.get("outcome", "")) not in IMPLEMENTATION_RUN_OUTCOMES:
        problems.append(f"implementation run has an unsupported outcome: {record.get('outcome') or 'missing'}")
    if str(record.get("outcome", "")) == "ESCALATED" and not str(record.get("escalation_reason", "")).strip():
        problems.append("an escalated implementation run must record why it escalated")
    if not isinstance(record.get("validation_attempts"), list) or not record.get("validation_attempts"):
        problems.append("an implementation run records no mechanical validation attempt")
    if not isinstance(record.get("telemetry"), Mapping):
        problems.append("an implementation run records no telemetry")
    acceptance = record.get("acceptance")
    if not isinstance(acceptance, Mapping):
        problems.append("an implementation run records no acceptance boundary")
    else:
        if str(acceptance.get("visual_acceptance", "")) not in ("NOT_CLAIMED", "VERIFIED_BY_RENDERED_CHECK"):
            problems.append(
                f"implementation run records an unknown visual-acceptance claim: "
                f"{acceptance.get('visual_acceptance') or 'missing'}"
            )
        reason = str(acceptance.get("reason", "")).strip()
        if str(acceptance.get("visual_acceptance", "")) != "VERIFIED_BY_RENDERED_CHECK" and not reason:
            problems.append(
                "a run that does not claim visual acceptance must say why; silence reads as a claim that "
                "none was needed, which is the assumption this field exists to remove"
            )
        if str(acceptance.get("visual_acceptance", "")) == "VERIFIED_BY_RENDERED_CHECK" and not str(
            acceptance.get("rendered_check_id", "")
        ).strip():
            problems.append(
                "a run that claims visual acceptance must name the independent rendered check that "
                "established it; source inspection cannot stand in for one"
            )
    return list(dict.fromkeys(problems))


IMPLEMENTATION_CHANGE_VERDICTS = (
    "GROUNDED",
    "GROUNDED_INCIDENTAL",
    "UNGROUNDED_DESIGN_CHANGE",
    "ACCESSIBILITY_REGRESSION",
    "REFERENCE_CLONING",
    "OUT_OF_SCOPE",
)
"""How one file-level change stands relative to the approved plan.

``GROUNDED`` requires a cited constraint. ``GROUNDED_INCIDENTAL`` is the honest
answer for a 1px correction, and refusing it would make the grounded tier
meaningless. The three failure verdicts are separate values rather than a single
``failed`` because a reference-cloning violation and an accessibility regression
call for different responses from the same reader.
"""

IMPLEMENTATION_RUN_OUTCOMES = (
    "IMPLEMENTED",
    "MECHANICALLY_VALIDATED",
    "ESCALATED",
    "REFUSED",
)
"""What one grounded implementation run actually achieved.

No outcome in this tuple asserts that the result looks right. ``MECHANICALLY_VALIDATED``
means the build, typecheck and tests passed; appearance is AR-222's judgement, made
from rendered evidence this phase does not capture.
"""


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


def render_capture_plan_problems(record: Mapping[str, Any]) -> list[str]:
    """Structural validation of one bounded render-capture plan (AR-222).

    The load-bearing check here is that every target names a *basis*. A plan whose
    targets exist because nobody objected to them is not a bounded plan, it is a
    screenshot matrix, and refusing it here is cheaper than triaging fifty images
    nobody asked for.
    """
    problems = design_schema_problems(record)
    if not isinstance(record, Mapping):
        return problems
    if not design_id_matches("rcp", str(record.get("capture_plan_id", ""))):
        problems.append("capture plan has a malformed capture_plan_id")
    for name in ("implementation_plan_id", "direction_id", "render_source_digest", "recorded_at"):
        _non_empty(record, name, problems)
    if not _is_sha256(record.get("render_source_digest")):
        problems.append("capture plan is not bound to a render source digest")
    if str(record.get("status", "")) not in CAPTURE_PLAN_STATUSES:
        problems.append(f"capture plan has an unsupported status: {record.get('status') or 'missing'}")
    targets = record.get("targets")
    if not isinstance(targets, list) or not targets:
        problems.append("capture plan declares no targets")
        return list(dict.fromkeys(problems))
    seen_ids: set[str] = set()
    for target in targets:
        if not isinstance(target, Mapping):
            problems.append("a capture target must be an object")
            continue
        target_id = str(target.get("target_id", ""))
        if not design_id_matches("rct", target_id):
            problems.append(f"capture target has a malformed target id: {target_id or 'missing'}")
        elif target_id in seen_ids:
            problems.append(f"capture plan repeats a target id: {target_id}")
        else:
            seen_ids.add(target_id)
        if str(target.get("kind", "")) not in CAPTURE_TARGET_KINDS:
            problems.append(f"capture target has an unsupported kind: {target.get('kind') or 'missing'}")
        basis = target.get("materiality_basis")
        if not isinstance(basis, list) or not [item for item in basis if str(item).strip()]:
            problems.append(f"capture target {target_id or '?'} names no materiality basis")
        for entry in (basis or []):
            if not isinstance(entry, Mapping) or str(entry.get("basis", "")) not in CAPTURE_TARGET_BASES:
                problems.append(f"capture target {target_id or '?'} has an unsupported materiality basis")
        viewport = target.get("viewport")
        if not isinstance(viewport, Mapping) or not str(viewport.get("width", "")).strip():
            problems.append(f"capture target {target_id or '?'} declares no viewport width")
    problems.extend(capture_budget_problems(record))
    return list(dict.fromkeys(problems))


def capture_budget_problems(record: Mapping[str, Any]) -> list[str]:
    """Bounded capture economics: exceeding a default needs a recorded reason.

    The defaults are advisory; silence about exceeding them is not. This is the
    difference between "these defaults did not fit this task" -- which is a normal
    answer -- and a run that quietly captured everything.
    """
    problems: list[str] = []
    budget = record.get("capture_budget")
    if not isinstance(budget, Mapping):
        problems.append("capture plan records no capture budget")
        return problems
    limits: dict[str, int] = {}
    for name, default in DEFAULT_CAPTURE_BUDGET.items():
        limit = budget.get(name, default)
        try:
            limit_value = int(limit)
        except (TypeError, ValueError):
            problems.append(f"capture budget entry {name} is not a count")
            continue
        if limit_value < 0:
            problems.append(f"capture budget entry {name} cannot be negative")
        limits[name] = limit_value
    expansions = budget.get("expansions")
    if not isinstance(expansions, list):
        problems.append("capture budget records no expansion list")
        return problems
    stated = {str(item.get("name", "")) for item in expansions if isinstance(item, Mapping)}
    for expansion in expansions:
        if not isinstance(expansion, Mapping):
            problems.append("a capture budget expansion must be an object")
            continue
        if not str(expansion.get("reason", "")).strip():
            problems.append(
                f"expanding {expansion.get('name', '?')} requires a recorded reason"
            )
    counts = capture_counts_over_budget(record)
    for name, count in sorted(counts.items()):
        limit = limits.get(name)
        if limit is None:
            continue
        if count > limit and name not in stated:
            problems.append(
                f"the plan captures {count} {name} against a budget of {limit} without recording "
                "why the default did not fit this task"
            )
    return problems


def capture_counts_over_budget(record: Mapping[str, Any]) -> dict[str, int]:
    """Measured capture counts per budget axis, so the budget is arithmetic not opinion."""
    counts = {"primary_viewport_states": 0, "interaction_states": 0, "responsive_captures": 0, "theme_variants": 0}
    for target in record.get("targets") or []:
        if not isinstance(target, Mapping):
            continue
        kind = str(target.get("kind", ""))
        if kind == "viewport-state":
            counts["primary_viewport_states"] += 1
        elif kind == "interaction-state":
            counts["interaction_states"] += 1
        elif kind == "responsive-state":
            counts["responsive_captures"] += 1
        elif kind == "theme-variant":
            counts["theme_variants"] += 1
    return counts


def rendered_evidence_set_problems(record: Mapping[str, Any]) -> list[str]:
    """Structural validation of one capture run's manifest (AR-222).

    A manifest is the unit that makes captures checkable in aggregate: it names the
    source digest every capture in the run was bound to, and it names the browser
    that produced them. A capture list without a source digest is a gallery.
    """
    problems = design_schema_problems(record)
    if not isinstance(record, Mapping):
        return problems
    if not design_id_matches("res", str(record.get("evidence_set_id", ""))):
        problems.append("rendered evidence set has a malformed evidence_set_id")
    for name in ("capture_plan_id", "render_source_digest", "started_at", "browser"):
        _non_empty(record, name, problems)
    if not _is_sha256(record.get("render_source_digest")):
        problems.append("rendered evidence set is not bound to a render source digest")
    if str(record.get("status", "")) not in ("COMPLETE", "PARTIAL", "FAILED"):
        problems.append(f"rendered evidence set has an unsupported status: {record.get('status') or 'missing'}")
    captures = record.get("captures")
    if not isinstance(captures, list) or not captures:
        problems.append("rendered evidence set records no captures")
        return list(dict.fromkeys(problems))
    seen: set[str] = set()
    for capture in captures:
        if not isinstance(capture, Mapping):
            problems.append("a capture entry must be an object")
            continue
        capture_id = str(capture.get("capture_id", ""))
        if not capture_id:
            problems.append("a capture entry has no capture_id")
        elif capture_id in seen:
            problems.append(f"rendered evidence set repeats a capture id: {capture_id}")
        else:
            seen.add(capture_id)
        for name in ("route", "state", "viewport", "artifact_path", "digest", "captured_at"):
            _non_empty(capture, name, problems)
        viewport = capture.get("viewport")
        if not isinstance(viewport, Mapping) or not str(viewport.get("width", "")).strip():
            problems.append(f"capture {capture_id or '?'} declares no viewport width")
        if not _is_sha256(capture.get("digest")):
            problems.append(f"capture {capture_id or '?'} has no artifact digest")
        if capture.get("render_source_digest") is not None and not _is_sha256(capture.get("render_source_digest")):
            problems.append(f"capture {capture_id or '?'} has a malformed source digest")
        elif str(capture.get("render_source_digest", "")) != str(record.get("render_source_digest", "")):
            problems.append(
                f"capture {capture_id or '?'} is bound to a different source digest than its evidence set; "
                "a set that mixes revisions cannot be reviewed as one result"
            )
    return list(dict.fromkeys(problems))


def rendered_critique_problems(record: Mapping[str, Any]) -> list[str]:
    """Structural validation of one independent rendered critique (AR-222).

    Two things are checked that a structural review cannot check on its own, because
    they are the two ways this record could otherwise be forged:

    1. the reviewer must be a different execution from the implementer, and
    2. the review must not have been handed the implementation's rationale.

    The second is a *record* of what was withheld, not a claim about the reviewer's
    reading. It is checkable; the reviewer's state of mind is not, and pretending
    otherwise would be the exact impersonation this phase exists to prevent.
    """
    problems = design_schema_problems(record)
    if not isinstance(record, Mapping):
        return problems
    if not design_id_matches("drc", str(record.get("critique_id", ""))):
        problems.append("rendered critique has a malformed critique_id")
    for name in ("evidence_set_id", "direction_id", "reviewer_identity", "recorded_at"):
        _non_empty(record, name, problems)
    if not _is_sha256(record.get("render_source_digest")):
        problems.append("rendered critique is not bound to the source digest it reviewed")
    if str(record.get("overall_status", "")) not in RENDER_OUTCOMES:
        problems.append(f"rendered critique has an unsupported overall status: {record.get('overall_status') or 'missing'}")
    reviewer = str(record.get("reviewer_execution", ""))
    implementer = str(record.get("implementing_execution", ""))
    if not reviewer:
        problems.append("rendered critique names no reviewer execution")
    if not implementer:
        problems.append("rendered critique names no implementing execution")
    if reviewer and implementer and reviewer == implementer:
        problems.append(
            "the reviewing execution is the implementing execution; the worker that produced a render "
            "does not get to decide whether its own render looks right"
        )
    isolation = record.get("isolation")
    if not isinstance(isolation, Mapping):
        problems.append("rendered critique records no review isolation boundary")
    else:
        if not str(isolation.get("withheld", "") or "").strip():
            problems.append("rendered critique records nothing it withheld from the reviewer")
        if isolation.get("implementation_rationale_transported"):
            problems.append(
                "the reviewer was handed implementation rationale; a visual review of a render cannot "
                "start from the worker's account of what it intended to build"
            )
    coverage = record.get("coverage")
    if not isinstance(coverage, Mapping) or not coverage:
        problems.append("rendered critique reports no coverage")
    else:
        for dimension, verdict in coverage.items():
            if not isinstance(verdict, Mapping):
                problems.append(f"coverage entry for {dimension} is not an object")
                continue
            if str(verdict.get("state", "")) not in CRITIQUE_COVERAGE_STATES:
                problems.append(f"coverage for {dimension} has an unsupported state")
            if str(verdict.get("state", "")) == "REVIEWED" and not verdict.get("capture_ids"):
                problems.append(f"coverage for {dimension} is REVIEWED but cites no capture")
    findings = record.get("findings")
    if not isinstance(findings, list):
        problems.append("rendered critique records no findings list")
        return list(dict.fromkeys(problems))
    for finding in findings:
        if not isinstance(finding, Mapping):
            problems.append("a rendered critique finding must be an object")
            continue
        for name in ("finding_id", "dimension", "severity", "basis", "observation", "expected_basis"):
            _non_empty(finding, name, problems)
        if str(finding.get("dimension", "")) not in DESIGN_REVIEW_DIMENSIONS:
            problems.append(f"rendered critique finding has an unsupported dimension: {finding.get('dimension')}")
        if str(finding.get("severity", "")) not in DESIGN_SEVERITIES:
            problems.append(f"rendered critique finding has an unsupported severity: {finding.get('severity')}")
        if str(finding.get("basis", "")) not in FINDING_BASES:
            problems.append(f"rendered critique finding has an unsupported basis: {finding.get('basis')}")
        citations = finding.get("capture_ids")
        if not isinstance(citations, list) or not citations:
            problems.append(
                f"rendered critique finding {finding.get('finding_id', '?')} cites no rendered capture; "
                "a judgement about a render must point at the render"
            )
        if str(finding.get("state", "OPEN")) not in REPAIR_FINDING_STATES:
            problems.append(f"rendered critique finding has an unsupported state: {finding.get('state')}")
    return list(dict.fromkeys(problems))


def refinement_plan_problems(record: Mapping[str, Any]) -> list[str]:
    """Structural validation of one bounded rendered-refinement plan (AR-222).

    The plan is bounded in three directions at once, and all three are checked here:
    what it may change, what it may not change, and which approved principle authorises
    it. A plan that cannot name the principle it serves is a redesign in a plan's
    clothing.
    """
    problems = design_schema_problems(record)
    if not isinstance(record, Mapping):
        return problems
    if not design_id_matches("rfp", str(record.get("refinement_plan_id", ""))):
        problems.append("refinement plan has a malformed refinement_plan_id")
    for name in ("critique_id", "direction_id", "recorded_at"):
        _non_empty(record, name, problems)
    if str(record.get("status", "")) not in ("PROPOSED", "IN_PROGRESS", "VALIDATED", "RE_RENDERED", "REJECTED", "ESCALATED"):
        problems.append(f"refinement plan has an unsupported status: {record.get('status') or 'missing'}")
    finding_ids = record.get("finding_ids")
    if not isinstance(finding_ids, list) or not finding_ids:
        problems.append("refinement plan names no findings")
    if not isinstance(record.get("allowed_scope"), list) or not record.get("allowed_scope"):
        problems.append("refinement plan has no allowed scope")
    if not isinstance(record.get("forbidden_scope"), list):
        problems.append("refinement plan records no forbidden scope")
    outcomes = record.get("required_outcomes")
    if not isinstance(outcomes, list) or not [item for item in outcomes if str(item).strip()]:
        problems.append("refinement plan declares no required outcomes")
    if not isinstance(record.get("validation"), list) or not record.get("validation"):
        problems.append("refinement plan declares no validation commands")
    justification = record.get("authorising_principles")
    if not isinstance(justification, list) or not justification:
        problems.append(
            "refinement plan names no authorising approved principle; a repair must move the result "
            "toward a direction that was already approved, not invent one"
        )
    for entry in (justification or []):
        if not isinstance(entry, Mapping) or not str(entry.get("principle_id", "")).strip():
            problems.append("an authorising principle entry names no principle")
        elif not str(entry.get("direction_id", "")).strip():
            problems.append("an authorising principle entry is not bound to a direction")
    new_direction = record.get("introduces_new_direction")
    if new_direction:
        problems.append(
            "refinement plan declares that it introduces a new design direction; that is "
            "DIRECTION_REVISION_REQUIRED, not a repair"
        )
    try:
        attempt = int(record.get("attempt", 0))
    except (TypeError, ValueError):
        problems.append("refinement plan attempt is not a count")
    else:
        if attempt < 1:
            problems.append("a refinement plan records an attempt below 1")
    return list(dict.fromkeys(problems))


DESIGN_RECORD_VALIDATORS = {
    "reference": reference_problems,
    "reference-analysis": reference_analysis_problems,
    "reference-set": reference_set_problems,
    "component-candidate": component_candidate_problems,
    "design-direction": design_direction_problems,
    "design-requirement": design_requirement_problems,
    "implementation-plan": implementation_plan_problems,
    "component-inventory": component_inventory_problems,
    "implementation-change": implementation_change_problems,
    "implementation-run": implementation_run_problems,
    "rendered-evidence": rendered_evidence_problems,
    "design-review": design_review_problems,
    "refinement": refinement_problems,
    "render-capture-plan": render_capture_plan_problems,
    "rendered-evidence-set": rendered_evidence_set_problems,
    "rendered-critique": rendered_critique_problems,
    "refinement-plan": refinement_plan_problems,
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

# ------------------------------------------- AR-206 native decision runtime

SCHEMA_DECISION_RUNTIME = 1
"""The AR-206 Decision Runtime record family.

Shadow predictions, calibration profiles, evaluation reports, adoption slices and
runtime manifests share one family. It is versioned separately from
``SCHEMA_DECISION_INTELLIGENCE`` for the same reason every other family is: a run
state that predates the Decision Runtime stays readable and byte-compatible
without a migration, so adopting bounded local inference never requires a user to
migrate their project.
"""

READABLE_DECISION_RUNTIME_SCHEMAS = (1,)
"""Decision-Runtime record versions this runtime can read."""

DECISION_RUNTIME_CONTRACT = "ariadne-decision-runtime-1"
"""Marker recorded in ``state["engine"]["decision_runtime_contract"]``."""

DECISION_RUNTIME_STATUSES = (
    "AVAILABLE",
    "AVAILABLE_CPU",
    "AVAILABLE_GPU",
    "WARM",
    "COLD",
    "WARMING",
    "UNAVAILABLE",
    "UNAVAILABLE_RESOURCE",
    "UNAVAILABLE_LICENSE",
)
"""Observable capability state of the native Decision Runtime.

``AVAILABLE*`` and ``WARM*`` mean the runtime can answer now. ``COLD`` means it is
installed but must load before its first answer. ``UNAVAILABLE_RESOURCE`` means the
hardware cannot support it and the safe fallback must run — never a crash, and never
a promise of latency that depends on hardware Ariadne does not own.
"""

DECISION_RUNTIME_KINDS = ("local_bounded", "external_bounded")
"""What kind of implementation answered.

``local_bounded``     an on-device bounded engine (the reference engine, or a
                      checkpoint-backed one installed by the user)
``external_bounded``  a bounded decision service reached over a transport

Neither value is user-facing vocabulary. Both are recorded because provenance that
cannot name its implementation is not evidence.
"""

CANONICAL_RUNTIME_ID = "ariadne-decision-runtime"
"""The one identity a Decision Runtime records and a calibration profile binds.

Chosen over the alternatives because it is the *name*, not a category or a registry
key. ``local_bounded`` names a kind of implementation and ``local-bounded-runtime`` names
a registry entry; both stay exactly where they are, because both are live 2.0 surface
with different jobs. This is the provenance identity: the thing that appears in a
decision record and that a calibration profile must match.
"""

RUNTIME_ID_ALIASES = {
    "local_bounded": CANONICAL_RUNTIME_ID,
    "local-bounded-runtime": CANONICAL_RUNTIME_ID,
    CANONICAL_RUNTIME_ID: CANONICAL_RUNTIME_ID,
}
"""Historical spellings that name *this* runtime, and nothing else.

Every entry is read compatibility. An unrecognised value is returned unchanged rather
than guessed at, and ``external_bounded`` is deliberately absent: aliasing an external
runtime's kind onto the local runtime's identity would let a profile measured against a
different implementation match this one.
"""


def canonical_runtime_id(value: Any) -> str:
    """Normalise a recorded Decision Runtime identity to its canonical form.

    One function, applied at interpretation boundaries, rather than a string replacement
    scattered across modules. New records write only the canonical value; records written
    during 2.1 development may carry a historical spelling and stay readable without the
    operator rewriting project state.

    Normalisation is deliberately narrow. It reconciles *names for the same runtime* and
    nothing else: a different implementation, model revision, decision definition or
    policy still fails to match, because those are compared separately and exactly.
    """
    label = str(value or "").strip()
    return RUNTIME_ID_ALIASES.get(label, label)


RUNTIME_PRIMITIVE_MAPPINGS = {
    "BinaryDecision": "noul",
    "ChoiceDecision": "choice",
    "ScaleDecision": "score",
}
"""Ariadne primitive to runtime task type.

``MultiSelectDecision`` is deliberately absent. The bounded runtime answers exactly
one closed label per question, and faking a set-valued answer by scoring options
independently would report a confidence for a combination that was never evaluated.
A ``MultiSelectDecision`` therefore returns ``UNSUPPORTED_PRIMITIVE`` and takes
Ariadne's normal fallback and escalation path.
"""

UNSUPPORTED_PRIMITIVE = "UNSUPPORTED_PRIMITIVE"
"""The bounded runtime cannot represent this primitive faithfully."""

ADOPTION_STATES = (
    "UNTESTED",
    "SHADOW",
    "EVALUATED",
    "ELIGIBLE",
    "ACTIVE",
    "SUSPENDED",
)
"""Lifecycle of one bounded-runtime slice (a decision definition, question version
and model revision, for one risk class).

``UNTESTED``  the slice exists but has never been evaluated
``SHADOW``    the runtime predicts; the authoritative path is unaffected
``EVALUATED`` measured evidence exists and is identity-bound
``ELIGIBLE``  the evidence and the risk policy permit promotion
``ACTIVE``    the runtime is authoritative for this slice, inside its scope
``SUSPENDED`` promotion was withdrawn; the previous authoritative path resumes

A slice may skip ``EVALUATED``/``ELIGIBLE`` only by refusing to reach ``ACTIVE``.
"""

SHADOW_AGREEMENTS = ("MATCH", "DISAGREE", "UNKNOWN", "UNREVIEWED")
"""How a shadow prediction compares to the authoritative result.

``DISAGREE`` is not a verdict on the runtime. Only recorded ground truth
(``authoritative_outcome``/``verification``) can say which side was right, and
absence of ground truth stays ``UNREVIEWED`` rather than becoming a loss.
"""

CALIBRATION_PROFILE_STATUSES = ("DRAFT", "PROVEN", "SUSPENDED", "RETIRED")
"""Whether a ``CalibrationProfile`` may be used to label a probability calibrated.

``DRAFT``     recorded but not proven; cannot produce ``CALIBRATED_PROBABILITY``
``PROVEN``    measured on a bound dataset for a concrete revision
``SUSPENDED`` withdrawn pending re-evaluation; falls back to provider probability
``RETIRED``   superseded permanently

There is no path from a missing profile to ``CALIBRATED_PROBABILITY``.
"""

EVALUATION_COMPARABILITY_KEYS = (
    "dataset_digest",
    "question_schema_digest",
    "decision_definition_digest",
    "runtime_version",
    "implementation_revision",
    "model_revision",
)
"""What binds an evaluation run's identity.

A metric comparison across runs that differ in any of these is not a comparison of
the same experiment, so the gate refuses it rather than printing a delta.
"""

DECISION_RUNTIME_EVENT_TYPES = (
    "decision_runtime_requested",
    "decision_runtime_started",
    "decision_runtime_completed",
    "decision_runtime_abstained",
    "decision_runtime_failed",
    "decision_runtime_cache_hit",
    "decision_runtime_shadow_recorded",
    "decision_runtime_promoted",
    "decision_runtime_suspended",
)
"""Canonical engine events for the Decision Runtime.

These are ordinary :mod:`ariadne_engine.events` entries. Ariadne has one event
system; the Decision Runtime does not get a second one.
"""

MAX_SHADOW_RECORDS = 10_000
"""Hard safety bound for shadow prediction records."""

MAX_CALIBRATION_PROFILES = 200
"""Hard safety bound for calibration-profile records."""

MAX_ADOPTION_SLICES = 200
"""Hard safety bound for adoption-slice records."""

AR206_COLLECTIONS = (
    "decision_shadow",
    "calibration_profiles",
    "decision_adoption",
)
"""The AR-206 Decision Runtime collections, additive and optional like every earlier
family. A run state that has none of them is a complete 2.0 run state.
"""

# ------------------------------------------------------- AR-223 acceptance plane

SCHEMA_ACCEPTANCE = 1
"""The AR-223 acceptance record family (contract, requirement, claim, evidence,
verification decision, verification pass).

Its own schema family, additive and optional in exactly the way AR-202/AR-203's are: a
run state written by an earlier milestone carries none of these collections and stays
readable and continuable, which is why nothing here forces a run-state migration.
"""

READABLE_ACCEPTANCE_SCHEMAS = (1,)
"""Acceptance record versions this runtime can read. Anything else is refused."""

ACCEPTANCE_CONTRACT = "ariadne-acceptance-1"
"""Marker recorded in ``state["engine"]["acceptance_contract"]`` when these records exist."""

ACCEPTANCE_CONTRACT_VERSION = "ar-223-acceptance-contract-1"
"""Which acceptance contract produced these records, distinct from the record schema.

Same reason ``DECISION_CONTRACT_VERSION`` exists: a consumer reading a state has to be
able to tell *which definitions* produced an answer, not merely which shape it has.
"""

ACCEPTANCE_VERDICTS = (
    "PROVEN",
    "PARTIAL",
    "UNPROVEN",
    "FAILED",
    "CONTRADICTED",
    "NEEDS_HUMAN",
)
"""The stable verdict vocabulary for one requirement in one verification pass.

**There is deliberately no order over these.** Every earlier ordinal in this module --
``VERIFICATION_LEVEL_ORDER``, for instance -- exists because its members really are a
ladder. These are not: ``FAILED`` is not "more" than ``UNPROVEN``, it is a different
answer, and a system that sorts them has already decided that missing evidence is
failure. The two distinctions that matter most are the two this tuple refuses to blur:

    UNPROVEN  != FAILED          no evidence either way is not a violation
    FAILED    != CONTRADICTED    violating a requirement is not disproving a claim

``CONTRADICTED`` is also *not* a requirement verdict in the ordinary case: it describes
a worker's statement, and :mod:`ariadne_engine.acceptance.decisions` keeps requirement
verdicts and claim verdicts in separate records precisely so the two cannot be
conflated.

``NEEDS_HUMAN`` is a first-class outcome, not a failure to decide. Abstention is a
valid answer and pretending otherwise would make the system's confidence its
weakness.
"""

REQUIREMENT_ORIGINS = ("EXPLICIT", "DERIVED", "ASSUMED")
"""Where a requirement came from, and what each is allowed to do.

``EXPLICIT``  the request says it. Blocking.
``DERIVED``   it follows necessarily from an explicit one. Surfaced, not blocking.
``ASSUMED``   Ariadne supplied it. Never blocking, always asks a human.

The asymmetry is the whole point. A one-sentence request may legitimately become one
requirement per surface; it does not become forty-seven blocking obligations the user
never agreed to. An inferred obligation that can block acceptance is a guess with the
power to stop a project.
"""

REQUIREMENT_KINDS = (
    "FUNCTIONAL",
    "VISUAL",
    "INTERACTION",
    "CONSTRAINT",
    "REGRESSION",
    "ACCESSIBILITY",
    "PERFORMANCE",
    "SECURITY",
    "CONTENT",
    "SUBJECTIVE",
)
"""What kind of obligation a requirement states.

``SUBJECTIVE`` is the honest admission that some obligations cannot become deterministic
``PROVEN`` -- "feels premium" is not a testable predicate, and an engine that grades it
any other way is grading its own mood.
"""

EVIDENCE_STANCES = ("AUTHORITATIVE", "REQUIRED", "SUPPORTING", "INSUFFICIENT_ALONE")
"""Where one evidence kind sits for **one requirement**.

Not an ordering of evidence kinds. There is no global ranking of evidence, because the
ranking is false: a build result directly establishes *it compiles* and establishes
nothing at all about whether a button works, a screenshot establishes nothing about
backend persistence, and a unit test establishes nothing about subjective polish.
Strength is a property of the (requirement, evidence) pair, so it is declared there.
"""

ACCEPTANCE_EVIDENCE_KINDS = (
    "TEST",
    "BUILD",
    "STATIC_ANALYSIS",
    "DIFF",
    "RUNTIME",
    "RENDER",
    "SCREENSHOT",
    "INTERACTION",
    "ACCESSIBILITY",
    "REVIEW",
    "PERFORMANCE",
    "PROVENANCE",
)
"""The evidence families a requirement's policy may name.

Deliberately a superset of the earlier vocabularies rather than a replacement:
:data:`DESIGN_REQUIREMENT_EVIDENCE` is ``source``/``rendered``/``behavioural`` and
``RENDERED_EVIDENCE_KINDS`` is viewport-scoped. Those stay where they are and are
*mapped into* this vocabulary by
:mod:`ariadne_engine.acceptance.integrations`, so a rendered-evidence set produced by
AR-222 remains usable input without being rewritten.
"""

CLAIM_TYPES = (
    "IMPLEMENTED",
    "FIXED",
    "TESTED",
    "PRESERVED",
    "VERIFIED",
    "COMPLETE",
)
"""What a worker says it did. Distinct from evidence kinds by construction.

A claim type is a statement *about* work. An evidence kind is an observation *of* work.
Keeping the two vocabularies separate in the type system is what makes "claim treated
as evidence" a structural impossibility rather than a rule somebody has to remember.
"""

EVIDENCE_STANCES_FOR_CLAIM = ("SUPPORTS", "PARTIALLY_SUPPORTS", "CONTRADICTS")
"""What a piece of evidence does to a requirement, as opposed to what kind it is.

One evidence item can be a ``TEST`` (kind) that ``CONTRADICTS`` (stance). Conflating
the two axes is how "screenshot > test > diff" got believed in the first place.
"""

EVIDENCE_SOURCE_KINDS = (
    "ENGINE_RECORD",
    "CI_RUN",
    "RENDERED_CAPTURE",
    "HUMAN_OBSERVATION",
    "ARTIFACT",
)
"""Where an observation came from, when it is not a re-readable artefact.

Required alongside ``source_record_id`` so "evidence" that points at nothing is refused:
an assertion with no source is a claim, and
:mod:`ariadne_engine.acceptance.claims` is where claims live with a different status.
``HUMAN_OBSERVATION`` is in the list rather than treated as second-class -- a human
looking at a screen and reporting what they saw is real evidence, and refusing it would
only push the system toward trusting files it can re-hash.
"""

IMPACT_STATES = ("PROVEN_UNAFFECTED", "POTENTIALLY_AFFECTED", "UNKNOWN")
"""How a code change affects a requirement.

``UNKNOWN`` is not a failure state to be minimised; it is the honest answer when the
dependency relationship cannot be established, and it must never be reported as
``PROVEN_UNAFFECTED``. Pretending an unknown relationship is a safe one is how selective
invalidation turns into selective *forgetting*.
"""

ACCEPTANCE_STATES = ("NOT_ACCEPTED", "ACCEPTED")
"""The aggregate outcome. Two values, because a percentage would be a lie.

``5 PROVEN, 1 FAILED, 2 UNPROVEN`` is five proven requirements, one failed one and two
unproven ones. Reducing that to *74%* invents a scale nobody measured, destroys exactly
the distinction the verdicts exist to preserve, and produces a number that goes **up**
when a requirement is deleted.
"""

HUMAN_GATE_REASONS = (
    "AMBIGUOUS_PRODUCT_INTENT",
    "SUBJECTIVE_FINAL_ACCEPTANCE",
    "PROTECTED_AUTHORIZATION",
    "MEANING_CHANGING_DESIGN_CHOICE",
    "POLICY_REQUIRED_HUMAN_GATE",
    "ASSUMED_REQUIREMENT",
    "EVIDENCE_CONFLICT_UNRESOLVED",
)
"""Why a requirement cannot honestly be decided automatically.

Kept as a finite, named vocabulary rather than free text so ``NEEDS_HUMAN`` is
actionable: an operator can tell "ask the human about the product" from "the policy
requires a human gate here" and act on them differently.
"""

MAX_ACCEPTANCE_CONTRACTS = 500
"""Hard safety bound for the contract collection."""

MAX_ACCEPTANCE_REQUIREMENTS = 5_000
"""Hard safety bound for the requirement-definition collection."""

MAX_ACCEPTANCE_CLAIMS = 10_000
"""Hard safety bound for the claim collection."""

MAX_ACCEPTANCE_EVIDENCE = 50_000
"""Hard safety bound for the acceptance-evidence collection.

Higher than the other bounds on purpose: evidence is the one collection that grows with
every observation, and refusing to record it because there is a lot of it would push
exactly the behaviour a refusal is supposed to prevent -- deciding without evidence.
"""

MAX_VERIFICATION_DECISIONS = 50_000
"""Hard safety bound for the verification-decision collection."""

MAX_VERIFICATION_PASSES = 5_000
"""Hard safety bound for the verification-pass collection."""

AR223_COLLECTIONS = (
    "acceptance_contracts",
    "acceptance_requirements",
    "acceptance_claims",
    "acceptance_evidence",
    "verification_decisions",
    "verification_passes",
)
"""The AR-223 acceptance collections, additive and optional like every earlier family."""

MAX_PROOF_RECEIPTS = 5_000
"""Hard safety bound for the AR-224 proof-receipt collection."""

AR224_COLLECTIONS = (
    "proof_receipts",
)
"""The AR-224 proof-receipt collection, additive and optional like every earlier family."""


def _acceptance_schema(record: Mapping[str, Any], problems: list[str], kind: str) -> None:
    if record.get("schema_version") not in READABLE_ACCEPTANCE_SCHEMAS:
        problems.append(
            f"{kind} schema is unsupported: {record.get('schema_version')!r}"
        )


def acceptance_contract_problems(record: Mapping[str, Any]) -> list[str]:
    """Structural validation of one acceptance contract (fail closed)."""
    problems: list[str] = []
    if not isinstance(record, Mapping):
        return ["acceptance contract is not an object"]
    _acceptance_schema(record, problems, "acceptance contract")
    if not design_id_matches("ctr", str(record.get("contract_id", ""))):
        problems.append("acceptance contract has a malformed contract id")
    _enum_problems(record, "status", CONTRACT_STATUSES, problems)
    _enum_problems(record, "origin", CONTRACT_ORIGINS, problems)
    for name in ("task_id", "source_text", "source_digest"):
        _non_empty(record, name, problems)
    if str(record.get("source_digest", "")) and not re.fullmatch(
        r"[0-9a-f]{64}", str(record.get("source_digest", ""))
    ):
        problems.append("acceptance contract source digest is not a sha256")
    revision = record.get("revision")
    if not isinstance(revision, int) or isinstance(revision, bool) or revision < 1:
        problems.append("acceptance contract revision must be a positive integer")
    if isinstance(revision, int) and not isinstance(revision, bool) and revision > 1:
        if not str(record.get("supersedes", "")):
            problems.append(
                "a contract past revision 1 must name the revision it supersedes. A revision "
                "without a predecessor cannot be audited"
            )
        elif not str(record.get("material_change_reason", "")):
            problems.append(
                "a contract past revision 1 must state why the previous one was replaced"
            )
    if str(record.get("status", "")) == "SUPERSEDED" and not str(record.get("superseded_by", "")):
        problems.append("a superseded contract must name what superseded it")
    return list(dict.fromkeys(problems))


CONTRACT_STATUSES = ("ACTIVE", "SUPERSEDED")
"""A contract is either the live interpretation of a request or the history of one.

Two states, not one. A superseded contract stays readable forever, because a decision made
against it has to remain auditable against the interpretation it was actually made
against -- and deleting the interpretation turns that audit into archaeology.
"""

CONTRACT_ORIGINS = ("USER_REQUEST", "OPERATOR", "IMPORTED", "GENERATIVE")
"""Who supplied the request text a contract interprets.

``GENERATIVE`` exists so an interpretation Ariadne produced is labelled as one. It does
not make the contract less binding -- it makes its authorship visible, which is the only
honest thing to do with text the user never wrote.
"""


def acceptance_requirement_problems(record: Mapping[str, Any]) -> list[str]:
    """Structural validation of one requirement definition (fail closed)."""
    problems: list[str] = []
    if not isinstance(record, Mapping):
        return ["acceptance requirement is not an object"]
    _acceptance_schema(record, problems, "acceptance requirement")
    if not design_id_matches("rqm", str(record.get("requirement_id", ""))):
        problems.append("acceptance requirement has a malformed requirement id")
    _enum_problems(record, "kind", REQUIREMENT_KINDS, problems)
    origin = _enum_problems(record, "origin", REQUIREMENT_ORIGINS, problems)
    _enum_problems(record, "status", ("ACTIVE", "SUPERSEDED"), problems)
    _enum_problems(record, "verification_mode", DECISION_CLASSIFICATIONS, problems)
    for name in ("contract_id", "text"):
        _non_empty(record, name, problems)
    if not isinstance(record.get("blocking", None), bool):
        problems.append("acceptance requirement blocking must be true or false")
    if not isinstance(record.get("human_gate", None), bool):
        problems.append("acceptance requirement human_gate must be true or false")
    if origin == "ASSUMED" and bool(record.get("blocking")):
        problems.append(
            "an ASSUMED requirement cannot block acceptance. The only honest contribution an "
            "assumption can make is a question, and a question must not be able to stop a project"
        )
    if origin == "ASSUMED" and not bool(record.get("human_gate")):
        problems.append("an ASSUMED requirement must carry a human gate")
    if origin == "EXPLICIT" and not bool(record.get("blocking")):
        problems.append(
            "an EXPLICIT requirement the user actually asked for cannot be advisory; dropping it "
            "from blocking acceptance is how a requested obligation quietly stops being graded"
        )
    policy = record.get("evidence_policy")
    if not isinstance(policy, Mapping):
        problems.append("acceptance requirement declares no evidence policy")
    else:
        for stance in EVIDENCE_STANCES:
            values = policy.get(stance, [])
            if not isinstance(values, (list, tuple)):
                problems.append(f"evidence policy {stance} is not a list")
                continue
            for value in values:
                if str(value) not in ACCEPTANCE_EVIDENCE_KINDS:
                    problems.append(f"evidence policy names an unknown evidence kind: {value}")
        if not any(policy.get(stance) for stance in EVIDENCE_STANCES):
            problems.append(
                "the requirement names no evidence that could establish it, so nothing could ever "
                "satisfy it"
            )
        overlap = (
            {str(item) for item in policy.get("required", ()) or ()}
            & {str(item) for item in policy.get("insufficient_alone", ()) or ()}
        )
        if overlap:
            problems.append(
                "evidence is both required and insufficient alone: " + ", ".join(sorted(overlap))
            )
        for value in policy.get("insufficient_alone", ()) or ():
            if str(value) in ("CLAIM", "STATEMENT"):
                problems.append(
                    f"{value} cannot be evidence at all. A claim may be what is being verified; "
                    "it is never the thing that verifies it"
                )
    return list(dict.fromkeys(problems))


def acceptance_claim_problems(record: Mapping[str, Any]) -> list[str]:
    """Structural validation of one worker claim (fail closed).

    There is no field here that lets a claim assert its own truth. A claim carries a
    statement, an actor, a revision and a set of requirements it is about -- and that is
    the complete list, because a claim that could carry evidence ids would be a claim
    that could launder itself into acceptance.
    """
    problems: list[str] = []
    if not isinstance(record, Mapping):
        return ["acceptance claim is not an object"]
    _acceptance_schema(record, problems, "acceptance claim")
    if not design_id_matches("clm", str(record.get("claim_id", ""))):
        problems.append("acceptance claim has a malformed claim id")
    _enum_problems(record, "claim_type", CLAIM_TYPES, problems)
    _enum_problems(record, "origin", ("PROSE", "STRUCTURED", "CI", "OPERATOR", "IMPORTED"), problems)
    _enum_problems(record, "actor_role", PROOF_ACTOR_ROLES, problems)
    _enum_problems(record, "status", ("AWAITING_EVIDENCE", "ASSESSED", "WITHDRAWN"), problems)
    for name in ("actor", "statement", "statement_digest", "claim_version"):
        _non_empty(record, name, problems)
    if not isinstance(record.get("requirement_ids", None), (list, tuple)):
        problems.append("acceptance claim requirement_ids is not a list")
    else:
        for requirement_id in record.get("requirement_ids") or ():
            if not design_id_matches("rqm", str(requirement_id)):
                problems.append(f"acceptance claim names a malformed requirement id: {requirement_id}")
    assertion = record.get("assertion")
    if not isinstance(assertion, Mapping):
        problems.append("acceptance claim assertion is not an object")
    else:
        for value in assertion.values():
            if isinstance(value, bool) or not isinstance(value, (int, float, str)):
                problems.append("a claim assertion holds only checkable scalars")
    if str(record.get("external")) not in ("True", "False"):
        problems.append("acceptance claim external must be a boolean")
    return list(dict.fromkeys(problems))


PROOF_ACTOR_ROLES = (
    "user_or_human_approver",
    "implementation_worker",
    "evidence_producer",
    "independent_reviewer",
    "repair_worker",
    "engine",
)
"""The identities a proof path must be able to distinguish.

Moved here from :mod:`ariadne_engine.rendered_critique.proof` in AR-223 rather than
duplicated, because from this point on two subsystems need the same list: proof
*readiness* to detect a collision, and acceptance to *refuse* one. A list that existed
twice would let the detector and the enforcer drift, which is the failure mode this
whole family of records exists to prevent.

The reason the list exists at all is a single rule: *the worker cannot independently
certify itself.*
"""

SELF_CERTIFICATION_PAIRS = (
    ("implementation_worker", "independent_reviewer"),
    ("repair_worker", "independent_reviewer"),
    ("implementation_worker", "evidence_producer"),
    ("repair_worker", "evidence_producer"),
)
"""Role pairs that may not be held by the same actor.

Evidence produced by the party whose work it evidences, and reviewed by the party that
implemented or repaired it, are the two ways independence can be faked.
"""


def acceptance_evidence_problems(record: Mapping[str, Any]) -> list[str]:
    """Structural validation of one acceptance-evidence record (fail closed).

    Producer identity, work digest and artefact digest are all mandatory, because each
    of them closes a different laundering route: a worker presenting its own screenshot
    as independent review, a stale capture presented as current, and a renamed or edited
    artefact presented as the one that was observed.
    """
    problems: list[str] = []
    if not isinstance(record, Mapping):
        return ["acceptance evidence is not an object"]
    _acceptance_schema(record, problems, "acceptance evidence")
    if not design_id_matches("evd", str(record.get("evidence_id", ""))):
        problems.append("acceptance evidence has a malformed evidence id")
    _enum_problems(record, "kind", ACCEPTANCE_EVIDENCE_KINDS, problems)
    _enum_problems(record, "stance", EVIDENCE_STANCES_FOR_CLAIM, problems)
    _enum_problems(record, "producer_role", PROOF_ACTOR_ROLES, problems)
    _enum_problems(record, "state", FRESHNESS_STATES, problems)
    for name in ("producer", "work_digest", "contract_revision", "observation"):
        _non_empty(record, name, problems)
    if str(record.get("work_digest", "")) and not re.fullmatch(
        r"[0-9a-f]{16,64}", str(record.get("work_digest", ""))
    ):
        problems.append("acceptance evidence work_digest is not a digest")
    artifact = record.get("artifact")
    if not isinstance(artifact, Mapping):
        problems.append("acceptance evidence artifact is not an object")
    elif artifact:
        for name in ("path", "sha256"):
            if not str(artifact.get(name, "")):
                problems.append(f"acceptance evidence artifact is missing {name}")
        if str(artifact.get("sha256", "")) and not re.fullmatch(
            r"[0-9a-f]{64}", str(artifact.get("sha256", ""))
        ):
            problems.append("acceptance evidence artifact sha256 is not a sha256")
    if not artifact and not str(record.get("source_record_id", "")):
        problems.append(
            "acceptance evidence cites neither a re-readable artefact nor the record it was "
            "derived from. Evidence that points at nothing is an assertion, and an assertion is a "
            "claim -- a different record type with a different status"
        )
    if str(record.get("source_kind", "")) and str(record.get("source_kind", "")) not in EVIDENCE_SOURCE_KINDS:
        problems.append(
            f"acceptance evidence names an unknown source kind: {record.get('source_kind')}"
        )
    requirements = record.get("requirement_ids")
    if not isinstance(requirements, (list, tuple)) or not requirements:
        problems.append(
            "acceptance evidence names no requirement. Evidence that is not about anything cannot "
            "establish anything"
        )
    return list(dict.fromkeys(problems))


def verification_decision_problems(record: Mapping[str, Any]) -> list[str]:
    """Structural validation of one verification decision (fail closed).

    The two separations this validator exists to hold:

    * a decision names a **requirement**, and a decision's verdict is about that
      requirement -- it may not claim ``CONTRADICTED``, which is a statement about a
      worker's claim and is therefore refused here;
    * a decision names a **decision path**, so "the model said so with high confidence"
      is not an available explanation.
    """
    problems: list[str] = []
    if not isinstance(record, Mapping):
        return ["verification decision is not an object"]
    _acceptance_schema(record, problems, "verification decision")
    if not design_id_matches("vdz", str(record.get("verification_id", ""))):
        problems.append("verification decision has a malformed verification id")
    verdict = _enum_problems(record, "verdict", ACCEPTANCE_VERDICTS, problems)
    for name in ("requirement_id", "work_digest", "contract_id", "contract_revision",
                 "decision_path", "reviewer", "rationale"):
        _non_empty(record, name, problems)
    if verdict == "CONTRADICTED":
        problems.append(
            "CONTRADICTED describes a worker's claim, not a requirement. A requirement that "
            "current evidence violates is FAILED; the claim it contradicts is a separate record"
        )
    if not str(record.get("evidence_ids", "")) and verdict in ("PROVEN", "FAILED", "PARTIAL"):
        problems.append(
            f"a {verdict} requirement must cite the evidence that decided it. A verdict with no "
            "evidence is an assertion"
        )
    for name in ("evidence_ids", "claim_ids", "human_gate_reasons"):
        value = record.get(name, [])
        if not isinstance(value, (list, tuple)):
            problems.append(f"verification decision {name} is not a list")
    uncertainty = record.get("uncertainty", "")
    if not isinstance(uncertainty, str):
        problems.append("verification decision uncertainty is not text")
    if str(record.get("authorization_effect", "")) != "none":
        problems.append("a verification decision never grants authorization")
    return list(dict.fromkeys(problems))


def verification_pass_problems(record: Mapping[str, Any]) -> list[str]:
    """Structural validation of one verification pass (fail closed).

    A pass is one look at one work digest under one contract revision. It carries no
    aggregate score, because a pass that reported one would be reporting a number whose
    construction destroyed the distinctions the verdicts preserve.
    """
    problems: list[str] = []
    if not isinstance(record, Mapping):
        return ["verification pass is not an object"]
    _acceptance_schema(record, problems, "verification pass")
    if not design_id_matches("vps", str(record.get("pass_id", ""))):
        problems.append("verification pass has a malformed pass id")
    _enum_problems(record, "acceptance_state", ACCEPTANCE_STATES, problems)
    _enum_problems(record, "pass_kind", ("INITIAL", "REVERIFICATION", "REPAIR"), problems)
    for name in ("contract_id", "contract_revision", "work_digest"):
        _non_empty(record, name, problems)
    decisions = record.get("requirement_decisions")
    if not isinstance(decisions, (list, tuple)):
        problems.append("verification pass requirement_decisions is not a list")
    assessments = record.get("claim_assessments")
    if not isinstance(assessments, (list, tuple)):
        problems.append("verification pass claim_assessments is not a list")
    if record.get("aggregate_score") is not None:
        problems.append(
            "a verification pass records requirement-level state, never a completion percentage. "
            "Counts are acceptable; a composite score is not"
        )
    if str(record.get("pass_kind", "")) == "REVERIFICATION" and not str(
        record.get("supersedes_pass_id", "")
    ):
        problems.append("a re-verification pass must name the pass it re-verifies")
    return list(dict.fromkeys(problems))

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
    "decision_shadow": MAX_SHADOW_RECORDS,
    "calibration_profiles": MAX_CALIBRATION_PROFILES,
    "decision_adoption": MAX_ADOPTION_SLICES,
    "acceptance_contracts": MAX_ACCEPTANCE_CONTRACTS,
    "acceptance_requirements": MAX_ACCEPTANCE_REQUIREMENTS,
    "acceptance_claims": MAX_ACCEPTANCE_CLAIMS,
    "acceptance_evidence": MAX_ACCEPTANCE_EVIDENCE,
    "verification_decisions": MAX_VERIFICATION_DECISIONS,
    "verification_passes": MAX_VERIFICATION_PASSES,
    "proof_receipts": MAX_PROOF_RECEIPTS,
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
            + ", ".join([*AR203_COLLECTIONS, *AR204_COLLECTIONS, *AR205D_COLLECTIONS,
                         *AR223_COLLECTIONS, *AR224_COLLECTIONS])
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


def _decision_runtime_schema(record: Mapping[str, Any], problems: list[str], label: str) -> None:
    if record.get("schema_version") not in READABLE_DECISION_RUNTIME_SCHEMAS:
        problems.append(f"{label} schema is unsupported: {record.get('schema_version')!r}")


def shadow_record_problems(record: Mapping[str, Any]) -> list[str]:
    """Structural validation of one shadow prediction record (fail closed).

    The load-bearing rule here is ``execution_effect``. A shadow record that claims
    it influenced execution is not a shadow record, so the shape refuses it rather
    than trusting the caller.
    """
    problems: list[str] = []
    if not isinstance(record, Mapping):
        return ["shadow record is not an object"]
    _decision_runtime_schema(record, problems, "shadow record")
    if not design_id_matches("dsh", str(record.get("shadow_id", ""))):
        problems.append("shadow record has a malformed shadow id")
    _enum_problems(record, "agreement", SHADOW_AGREEMENTS, problems)
    if str(record.get("execution_effect", "")) != "none":
        problems.append("a shadow prediction cannot have an execution effect")
    if str(record.get("authorization_effect", "")) != "none":
        problems.append("a shadow prediction never grants authorization")
    confidence = record.get("confidence")
    if confidence is not None and not isinstance(confidence, (int, float)):
        problems.append("shadow confidence is not a number")
    elif isinstance(confidence, bool):
        problems.append("shadow confidence is not a number")
    elif isinstance(confidence, (int, float)) and not 0.0 <= float(confidence) <= 1.0:
        problems.append("shadow confidence is outside [0, 1]")
    if str(record.get("confidence_kind", "")) not in CONFIDENCE_KINDS:
        problems.append("shadow record has an unsupported confidence kind")
    if str(record.get("confidence_kind", "NONE")) == "NONE" and confidence is not None:
        problems.append("a shadow confidence kind of NONE cannot carry a value")
    _non_empty(record, "question_id", problems)
    _non_empty(record, "projection_digest", problems)
    _non_empty(record, "model_revision", problems)
    return list(dict.fromkeys(problems))


def calibration_profile_problems(record: Mapping[str, Any]) -> list[str]:
    """Structural validation of one ``CalibrationProfile`` (fail closed).

    ``PROVEN`` is only reachable with a dataset digest, a question-schema digest and
    a concrete model revision. A profile that claims to be proven without the
    evidence that proves it is refused, because its whole purpose is to be the
    thing that licenses ``CALIBRATED_PROBABILITY``.
    """
    problems: list[str] = []
    if not isinstance(record, Mapping):
        return ["calibration profile is not an object"]
    _decision_runtime_schema(record, problems, "calibration profile")
    if not design_id_matches("dcp", str(record.get("profile_id", ""))):
        problems.append("calibration profile has a malformed profile id")
    status = _enum_problems(record, "status", CALIBRATION_PROFILE_STATUSES, problems)
    for name in ("decision_definition", "question_version", "runtime", "implementation"):
        _non_empty(record, name, problems)
    for name in ("dataset_digest", "question_schema_digest", "model_revision"):
        _non_empty(record, name, problems)
    if str(record.get("model_revision", "")) and not _concrete_revision(str(record["model_revision"])):
        problems.append("calibration profile names a moving model alias, not a revision")
    size = record.get("dataset_size")
    if not isinstance(size, int) or isinstance(size, bool) or size <= 0:
        problems.append("calibration profile has no positive dataset size")
    for name in ("accuracy", "coverage"):
        value = record.get(name)
        if not isinstance(value, (int, float)) or isinstance(value, bool) or not 0.0 <= float(value) <= 1.0:
            problems.append(f"calibration profile {name} is outside [0, 1]")
    for name in ("ece", "brier"):
        value = record.get(name)
        if not isinstance(value, (int, float)) or isinstance(value, bool) or float(value) < 0.0:
            problems.append(f"calibration profile {name} is not a non-negative number")
    thresholds = record.get("thresholds_by_risk")
    if not isinstance(thresholds, Mapping):
        problems.append("calibration profile thresholds are not an object")
    else:
        for risk, threshold in thresholds.items():
            if str(risk) not in DECISION_CONSEQUENCES:
                problems.append(f"calibration profile threshold names an unknown risk class: {risk}")
            elif not isinstance(threshold, (int, float)) or isinstance(threshold, bool) or not 0.0 < float(threshold) <= 1.0:
                problems.append(f"calibration profile threshold for {risk} is outside (0, 1]")
    if status == "PROVEN" and problems:
        problems.append("a calibration profile cannot be PROVEN while it has structural problems")
    return list(dict.fromkeys(problems))


def _concrete_revision(value: str) -> bool:
    """A revision names one artifact state, not a moving alias."""
    label = str(value or "").strip()
    if not label:
        return False
    lowered = label.lower()
    return not any(lowered == alias or lowered.endswith(f"-{alias}") for alias in MOVING_ALIAS_REVISIONS)


MOVING_ALIAS_REVISIONS = ("latest", "stable", "default", "current", "edge", "preview", "main")
"""Labels that name a moving pointer. A calibration profile bound to one of these
is bound to nothing, so it is refused rather than silently re-used.
"""


def adoption_slice_problems(record: Mapping[str, Any]) -> list[str]:
    """Structural validation of one adoption slice (fail closed).

    An ``ACTIVE`` slice must carry its eligibility scope and the evaluation identity
    that justified promotion. Without both, "promoted" is an assertion rather than a
    record, and an assertion cannot be rolled back safely.
    """
    problems: list[str] = []
    if not isinstance(record, Mapping):
        return ["adoption slice is not an object"]
    _decision_runtime_schema(record, problems, "adoption slice")
    if not design_id_matches("dad", str(record.get("slice_id", ""))):
        problems.append("adoption slice has a malformed slice id")
    status = _enum_problems(record, "status", ADOPTION_STATES, problems)
    for name in ("decision_definition", "question_version", "model_revision"):
        _non_empty(record, name, problems)
    scope = record.get("scope")
    if not isinstance(scope, Mapping) or not scope:
        problems.append("adoption slice has no eligibility scope")
    if status in ("ELIGIBLE", "ACTIVE"):
        evaluation = record.get("evaluation_id")
        if not str(evaluation or "").strip():
            problems.append(f"an {status} slice must name the evaluation that justified it")
    if str(record.get("authorization_effect", "")) != "none":
        problems.append("an adoption slice never grants authorization")
    return list(dict.fromkeys(problems))


