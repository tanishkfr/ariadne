"""Authorization, gates, continuation preconditions and the repair budget.

This module holds the *only* implementation of four policies:

``gate_satisfied``
    Whether a gate is authorized right now: an approval record for that gate,
    on the human channel, bound to the current revision fingerprint of the
    subject, not already consumed by this operation. Document fields in
    ``AGENTS.md`` / ``DESIGN.md`` are readable mirrors written *after* an
    approval; they are never an enforcement input.

``continuation_problems``
    The single precondition set for a stage transition. ``advance`` and
    ``prepare_next`` (and any other continuation path) call this function, so a
    requirement cannot be enforced on one route and skipped on another.

``repair_allowed``
    The bounded routine-repair budget and the rule that a blocked return never
    enters routine repair.

``review_subject`` / ``review_problems``
    Delegated to :mod:`ariadne_engine.review`; re-exported here so callers have
    one policy import.

The transport helpers (worker contract rows, scope classification, validation
record shape) stay where they are - in ``scripts/prepare-stage.py`` - and this
module delegates to them instead of re-implementing them.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import re
from pathlib import Path
from typing import Mapping

from . import contracts, review as review_module
from .contracts import (
    APPROVAL_CHANNEL_HUMAN,
    GATE_SUBJECT_TYPES,
    ContractError,
    Subject,
    UnauthorizedApproval,
    approval_gate_problems,
    digest_fields,
    new_approval_id,
    normalise,
    utc_now,
)

MAX_ROUTINE_REPAIRS = 2

_TOOLS: dict[str, object] = {}


def bind(*, transport=None, creative=None, operations=None, runtime=None) -> None:
    """Inject already-loaded runtime helpers (optional; they load on demand)."""
    for name, value in (
        ("transport", transport), ("creative", creative),
        ("operations", operations), ("runtime", runtime),
    ):
        if value is not None:
            _TOOLS[name] = value


def _load_script(name: str):
    root = Path(__file__).resolve().parents[2] / "scripts" / name
    spec = importlib.util.spec_from_file_location(f"ariadne_engine_{name.replace('-', '_').replace('.', '_')}", root)
    if spec is None or spec.loader is None:
        raise ContractError(f"engine dependency could not be loaded: {name}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _tool(name: str):
    if name not in _TOOLS:
        filenames = {
            "transport": "prepare-stage.py",
            "creative": "creative-intelligence.py",
            "operations": "creative-operations.py",
        }
        if name not in filenames:
            raise ContractError(f"unknown engine dependency: {name}")
        _TOOLS[name] = _load_script(filenames[name])
    return _TOOLS[name]


def sha256_file(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def tool(name: str):
    """Public accessor for the runtime scripts this engine delegates to.

    One loader for every engine module: a second loader would be a second place
    where a stale or swapped script could enter the engine's decisions.
    """
    return _tool(name)


# ------------------------------------------------------------ design subjects

def section_raw(text: str, heading: str) -> str:
    """Body of one ``## <heading>`` section, verbatim."""
    pattern = re.compile(rf"(?im)^#{{2,3}}\s+{re.escape(heading)}\s*$")
    match = pattern.search(text or "")
    if not match:
        return ""
    remainder = text[match.end():]
    end = re.search(r"(?m)^#{2,3}\s+\S", remainder)
    return remainder[: end.start()] if end else remainder


def markdown_section_body(text: str, heading: str) -> str:
    """The same section, normalised for fingerprinting (whitespace-insensitive)."""
    return normalise(section_raw(text, heading))


def design_thesis(text: str) -> str:
    """The approved design thesis line (moved from the runtime, unchanged semantics)."""
    for line in section_raw(text, "Design thesis").splitlines():
        match = re.match(r"^\s*\*\*(.+?)\*\*\s*$", line)
        if match and "<" not in match.group(1):
            return normalise(re.sub(r"[`*_]", "", match.group(1)))
    return ""


def design_direction_subject(project: Path) -> Subject:
    """Fingerprint of the locked design direction (see contracts.REVISION_FIELDS)."""
    design_path = Path(project) / "DESIGN.md"
    text = design_path.read_text(encoding="utf-8") if design_path.is_file() else ""
    fields = {
        "design-thesis": design_thesis(text),
        "signature-moment": markdown_section_body(text, "Signature moment"),
        "responsive-behaviour": markdown_section_body(text, "Responsive behaviour"),
        "asset-direction": markdown_section_body(text, "Asset direction"),
    }
    if not fields["design-thesis"]:
        raise ContractError("DESIGN.md has no usable design thesis to bind an approval to")
    return Subject(
        subject_type="design-direction",
        subject_id="DESIGN.md",
        revision_hash=digest_fields("design-direction", fields),
        detail=fields["design-thesis"],
        fields=fields,
    )


def handoff_subject(project: Path) -> Subject:
    """Fingerprint of the implementation handoff a dependency approval covers."""
    transport = _tool("transport")
    handoff_path = Path(project) / "HANDOFF.md"
    if not handoff_path.is_file():
        raise ContractError("HANDOFF.md is missing; there is nothing to approve")
    text = handoff_path.read_text(encoding="utf-8")
    contract = transport.worker_contract(text)
    scope_rows = [" | ".join(normalise(str(cell)) for cell in row) for row in contract.get("scope_rows", [])]
    validation_rows = [" | ".join(normalise(str(cell)) for cell in row) for row in contract.get("validation_rows", [])]
    fields = {
        "handoff-sha256": sha256_file(handoff_path),
        "scope-rows": "\n".join(scope_rows),
        "validation-rows": "\n".join(validation_rows),
    }
    return Subject(
        subject_type="handoff",
        subject_id="HANDOFF.md",
        revision_hash=digest_fields("handoff", fields),
        detail=f"worker role {contract.get('worker_role') or 'unknown'}",
        fields=fields,
    )


def review_subject(state: dict, packet: Path) -> Subject | None:
    """Fingerprint of the recorded review of one S5 packet (None if no review)."""
    record = review_module.current_review(state, packet_id=Path(packet).name)
    if record is None:
        return None
    judgement = Path(packet) / "evidence" / "review-judgement.md"
    manifest_path = Path(packet) / "manifest.json"
    manifest = {}
    if manifest_path.is_file():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            manifest = {}
    validation = (state.get("worker") or {}).get("last_validation")
    fields = {
        "packet-id": str(record.get("packet_id", "")),
        "packet-sha256": str(manifest.get("packet_sha256", "")),
        "review-judgement-sha256": sha256_file(judgement) if judgement.is_file() else "",
        "reviewer-identity": str(record.get("reviewer_identity", "")),
        "validated-revision": sha256_file(Path(validation)) if validation and Path(validation).is_file() else "",
    }
    return Subject(
        subject_type="review",
        subject_id=str(record.get("packet_id", "")),
        revision_hash=digest_fields("review", fields),
        detail=f"reviewer {record.get('reviewer_identity')}; outcome {record.get('outcome')}",
        fields=fields,
    )


# ------------------------------------------------------------------ approvals

def approvals(state: dict, gate: str | None = None) -> list[dict]:
    records = state.get("approvals")
    if not isinstance(records, list):
        return []
    return [record for record in records if isinstance(record, dict) and (gate is None or record.get("gate") == gate)]


def highest_gate(state: dict) -> str | None:
    recorded = {str(record.get("gate", "")) for record in approvals(state)}
    ladder = [gate for gate in ("G1", "G2", "G3", "G4", "G5") if gate in recorded]
    return ladder[-1] if ladder else None


def approve(
    state: dict,
    gate: str,
    subject: Subject,
    identity: str,
    note: str = "",
    *,
    channel: str = APPROVAL_CHANNEL_HUMAN,
    stage: str = "",
    packet_id: str = "",
) -> dict:
    """Record one authorization decision and return the stored record.

    Only the human channel may record authority: a worker-equivalent caller that
    supplies another channel is refused, so no adapter or worker can
    self-authorize. Nothing here proves a human typed the command; it records
    the channel the operator surface used, which is the authorization boundary
    the runtime enforces.
    """
    if gate not in GATE_SUBJECT_TYPES:
        raise UnauthorizedApproval(
            f"{gate} is not an engine-enforced gate; "
            "G4 ship and G5 publish stay human/operator actions outside the orchestration core"
        )
    if not str(identity or "").strip():
        raise ContractError("an approval needs a recorded identity; nothing was written")
    if channel != APPROVAL_CHANNEL_HUMAN:
        raise UnauthorizedApproval(
            f"channel {channel!r} cannot record an approval; only {APPROVAL_CHANNEL_HUMAN!r} satisfies a gate"
        )
    if subject.subject_type != GATE_SUBJECT_TYPES[gate]:
        raise UnauthorizedApproval(
            f"{gate} approves a {GATE_SUBJECT_TYPES[gate]}, not a {subject.subject_type}"
        )
    for record in approvals(state, gate):
        if (
            record.get("subject_id") == subject.subject_id
            and record.get("revision_hash") == subject.revision_hash
            and not record.get("consumed_by")
        ):
            raise UnauthorizedApproval(
                f"{gate} is already approved for this exact revision; the existing record stands "
                f"(approval {record.get('approval_id')})"
            )
    record = {
        "schema_version": contracts.SCHEMA_RECORD,
        "approval_id": new_approval_id(),
        "gate": gate,
        "subject_type": subject.subject_type,
        "subject_id": subject.subject_id,
        "revision_hash": subject.revision_hash,
        "identity": str(identity).strip(),
        "channel": channel,
        "note": str(note or ""),
        "recorded_at": utc_now(),
        "stage": stage,
        "packet_id": packet_id,
        "consumed_by": [],
    }
    state.setdefault("approvals", []).append(record)
    return record


def gate_satisfied(
    state: dict,
    gate: str,
    subject: Subject | None,
    *,
    consume: str | None = None,
    operation: str = "",
) -> tuple[bool, str]:
    """(satisfied, reason) for one gate against the current subject revision."""
    if gate not in GATE_SUBJECT_TYPES:
        return False, f"{gate} is outside the engine's authorization model"
    if subject is None:
        return False, f"{gate} cannot be checked: the subject it approves does not exist yet"
    records = approvals(state, gate)
    if not records:
        return False, (
            f"no {gate} approval is recorded for this run; project documents are a mirror, not an "
            f"authorization channel (use the operator approval command)"
        )
    latest = records[-1]
    problems = approval_gate_problems(latest, subject)
    if str(latest.get("channel", "")) != APPROVAL_CHANNEL_HUMAN:
        problems.append(
            f"{gate} approval was recorded on channel {latest.get('channel')!r}; "
            f"only {APPROVAL_CHANNEL_HUMAN!r} satisfies a gate"
        )
    if problems:
        return False, f"{gate} approval {latest.get('approval_id')} cannot be used: " + "; ".join(problems)
    if consume:
        if operation in tuple(latest.get("consumed_by") or ()):
            return False, (
                f"{gate} approval {latest.get('approval_id')} was already consumed by {operation!r}; "
                "a single-use approval cannot be replayed"
            )
        updated = [dict(record) for record in state.get("approvals", []) if isinstance(record, dict)]
        for record in updated:
            if record.get("approval_id") == latest.get("approval_id"):
                record["consumed_by"] = list(record.get("consumed_by") or []) + [operation]
        state["approvals"] = updated
    return True, ""


# ------------------------------------------------------------- preconditions

def creative_evidence_problems(state: dict, project: Path) -> list[str]:
    """The creative-evidence requirement, enforced at the S3 -> S4A boundary."""
    if not state.get("creative_evidence_required"):
        return []
    creative = _tool("creative")
    ledger = creative.load_ledger(Path(project))
    if ledger is None:
        return ["the project has no creative plan or skill-execution record"]
    return list(creative.project_problems(Path(project), "S3"))


def g1_problems(state: dict, project: Path) -> list[str]:
    """The G1 gate: a bound human approval for the current design direction."""
    try:
        subject = design_direction_subject(project)
    except ContractError as exc:
        return [str(exc)]
    satisfied, reason = gate_satisfied(state, "G1", subject)
    return [] if satisfied else [reason]


def dependency_rows(project: Path) -> list[list[str]]:
    transport = _tool("transport")
    handoff = Path(project) / "HANDOFF.md"
    if not handoff.is_file():
        return []
    rows = []
    for row in transport.worker_contract(handoff.read_text(encoding="utf-8")).get("scope_rows", []):
        rows.append(row)
    return rows


def declared_dependencies(project: Path) -> list[str]:
    """Package names the handoff declares in ``## Dependencies to install``.

    One implementation, used by the G2 gate and by task characterisation, so a
    dependency can never be counted in one place and ignored in the other.
    """
    handoff = Path(project) / "HANDOFF.md"
    if not handoff.is_file():
        return []
    text = handoff.read_text(encoding="utf-8")
    match = re.search(r"(?im)^##\s+Dependencies to install\s*$", text)
    if not match:
        return []
    remainder = text[match.end():]
    end = re.search(r"(?m)^##\s+\S", remainder)
    section = remainder[: end.start()] if end else remainder
    rows = []
    for line in section.splitlines():
        if not line.strip().startswith("|"):
            continue
        cells = [normalise(cell.replace("`", "")) for cell in line.strip().strip("|").split("|")]
        if not cells or all(re.fullmatch(r"[-: ]*", cell) for cell in cells):
            continue
        rows.append(cells)
    rows = rows[1:] if rows and rows[0][0].lower() in ("package", "dependency", "name") else rows
    return [row[0] for row in rows if row and row[0].lower() not in ("none", "n/a", "")]


def g2_problems(state: dict, project: Path) -> list[str]:
    """G2 holds only when the handoff declares dependencies that need installing."""
    if not declared_dependencies(project):
        return []
    try:
        subject = handoff_subject(project)
    except ContractError as exc:
        return [str(exc)]
    satisfied, reason = gate_satisfied(state, "G2", subject)
    if satisfied:
        return []
    return [
        f"the handoff declares dependencies to install, so a bound G2 approval is required: {reason}"
    ]


def preflight_problems(state: dict) -> list[str]:
    preflight = state.get("provider_preflight") or {}
    if preflight.get("decision") in ("verified", "reasonably-assumed", "not-required"):
        return []
    return ["Provider preflight must clear before the external build handoff."]


def validation_problems(state: dict, packet: Path) -> list[str]:
    transport = _tool("transport")
    entry_id = None
    packets = state.get("packets") or []
    if packets:
        entry_id = str(packets[-1].get("id", "")) or None
    return_target = Path(packet) / "evidence" / "return-handoff.md"
    if not return_target.is_file():
        return ["The structured implementation return is missing; complete or recover it before independent review."]
    if transport.return_handoff_status(return_target.read_text(encoding="utf-8")) != "complete":
        return ["Implementation returned partial or blocked; resume it before independent review."]
    project = Path(state.get("project", ""))
    if not (project / "QA.md").is_file():
        return ["Implementation or mechanical QA is incomplete."]
    validation_path = Path(packet) / "evidence" / "validation.json"
    if not validation_path.is_file():
        return ["Ariadne's independent worker validation is missing; do not trust the worker self-report."]
    try:
        validation = json.loads(validation_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [f"Independent worker validation is malformed: {exc}"]
    problems = transport.worker_validation_problems(validation, entry_id)
    if problems:
        return ["Independent worker validation is malformed: " + "; ".join(problems)]
    if validation.get("status") != "passed":
        return ["Independent worker validation did not pass; repair or escalate before review."]
    return []


def review_requirements_problems(state: dict, packet: Path) -> list[str]:
    return review_module.required_review_problems(state, Path(packet))


# ---------------------------------------------------------------- T1 evidence

EVIDENCE_STATES = (
    "satisfied",
    "optional-unresolved",
    "missing",
    "unavailable",
    "unresolved",
    "stale",
    "unsatisfied",
)
"""How a declared evidence requirement stands right now.

``satisfied``            the evidence exists and satisfies the requirement;
``optional-unresolved``  optional evidence the workflow selected but did not finish (not a blocker);
``missing``              the ledger or artifact does not exist;
``unavailable``          the requirement cannot be evaluated at all (fail closed where required);
``unresolved``           the evidence is recorded but the required step is still open;
``stale``                the recorded evidence no longer matches the artifact it names;
``unsatisfied``          the evidence exists and contradicts the requirement.""" 

CREATIVE_STAGE_REQUIREMENTS = {"S4B": "S4A", "S5": "S4B"}
"""Target boundary -> the stage whose selected creative skills it requires.

Entering S4B is authorized by evidence that the S4A implementation planning
actually ran; entering S5 by evidence that the S4B QA work actually ran. (The
S3 direction evidence is required at the S3 -> S4A boundary by
``creative_evidence_problems``, unchanged.)"""

OPERATIONS_REQUIREMENT_LEVEL = {"S5": "implementation"}
"""The creative-operations level a boundary requires.

The ledger is created while the S4B packet is prepared, so it is only required
from the review boundary on; asking for it earlier would demand evidence the
workflow creates later."""

DESIGN_REQUIREMENT_BOUNDARIES = ("S4B", "S5")
"""Boundaries where AR-202D design evidence is an entry precondition.

Nothing is required at a boundary whose design plan did not select the
corresponding stage, so a task with no design records — or a design task at
``MINIMAL`` depth — is never blocked by design intelligence.
"""

DESIGN_EVIDENCE_KIND_BY_OPERATIONS = {
    "source": "source",
    "dom": "source",
    "screenshot": "rendered",
    "browser": "rendered",
    "measurement": "behavioural",
    "interaction": "behavioural",
}
"""How a creative-operations requirement's expected evidence maps onto the
AR-202D closure model. One table, so the two ledgers cannot disagree."""


def _record_digest_matches(project: Path, record: Mapping) -> bool:
    """True when a ledger's recorded evidence artifact still has its recorded digest."""
    path = str(record.get("path", "")).strip()
    expected = str(record.get("sha256", "")).strip()
    if not path or not expected:
        return True
    target = Path(path)
    if not target.is_file():
        return False
    try:
        return sha256_file(target) == expected
    except OSError:
        return False


def stale_creative_evidence(project: Path, ledger: Mapping, stage: str) -> list[str]:
    """Skills whose recorded output artifact changed after the evidence was written."""
    stale: list[str] = []
    for skill in ledger.get("skills", []):
        if not isinstance(skill, Mapping) or skill.get("stage") != stage or not skill.get("selected"):
            continue
        for row in (skill.get("history") or [])[-3:]:
            if not isinstance(row, Mapping):
                continue
            for key in ("output", "downstream", "evidence"):
                record = row.get(key)
                if isinstance(record, Mapping) and not _record_digest_matches(Path(project), record):
                    stale.append(f"{skill.get('name')} {key}")
    return sorted(set(stale))


def creative_evidence_requirement(state: dict, project: Path, stage: str) -> dict:
    """The creative-intelligence requirement at one boundary, as a record.

    Task relevance: a run that does not require creative evidence declares no
    creative requirement at all, so a non-creative task is never blocked by it.
    """
    requirement = {
        "id": f"creative-{stage}-skills",
        "source": "creative-intelligence",
        "stage": stage,
        "required": False,
        "state": "satisfied",
        "detail": "this run does not require creative evidence",
        "evidence": [],
    }
    if not state.get("creative_evidence_required"):
        return requirement
    requirement["required"] = True
    creative = _tool("creative")
    ledger = creative.load_ledger(Path(project))
    if ledger is None:
        requirement.update({
            "state": "missing",
            "detail": "the project has no creative plan or skill-execution record",
        })
        return requirement
    problems = list(creative.stage_problems(ledger, stage))
    stale = stale_creative_evidence(Path(project), ledger, stage)
    selected = [
        str(skill.get("name"))
        for skill in ledger.get("skills", [])
        if isinstance(skill, Mapping) and skill.get("selected") and skill.get("stage") == stage
    ]
    requirement["evidence"] = selected
    if stale:
        requirement.update({
            "state": "stale",
            "detail": "recorded creative evidence no longer matches its artifact: " + ", ".join(stale),
        })
        return requirement
    if problems:
        # A mandatory skill that failed or was skipped cannot be satisfied by
        # re-running; it is 'unsatisfied'. An unresolved recommendation is still
        # open, so it is 'unresolved'.
        failed = [item for item in problems if "did not complete" in item]
        requirement.update({
            "state": "unsatisfied" if failed else "unresolved",
            "detail": "; ".join(problems),
        })
        return requirement
    requirement.update({"state": "satisfied", "detail": "selected creative skills are resolved with evidence"})
    return requirement


def operations_evidence_requirement(state: dict, project: Path, level: str) -> dict:
    """The creative-operations requirement at one boundary, as a record."""
    requirement = {
        "id": f"operations-{level}",
        "source": "creative-operations",
        "stage": "",
        "required": False,
        "state": "satisfied",
        "detail": "this run does not require creative operations evidence",
        "evidence": [],
    }
    if not state.get("creative_evidence_required"):
        return requirement
    ledger_path = Path(project) / ".ariadne" / "creative-operations.json"
    if not ledger_path.exists():
        requirement.update({
            "state": "missing",
            "detail": "post-G1 creative operations are not recorded",
            "required": True,
        })
        return requirement
    operations = _tool("operations")
    requirement["required"] = True
    problems = list(operations.project_problems(Path(project), level))
    requirement["evidence"] = [str(ledger_path)]
    if problems:
        level_failures = [item for item in problems if "implementation" in item or "drift" in item or "visual" in item]
        requirement.update({
            "state": "unsatisfied" if level_failures else "unresolved",
            "detail": "; ".join(problems),
        })
        return requirement
    requirement.update({
        "state": "satisfied",
        "detail": f"the operations ledger satisfies the {level} requirement",
    })
    return requirement


def evidence_requirements(state: dict, target: str, *, project: Path | None = None) -> list[dict]:
    """The declared creative/operations/design evidence for one stage transition.

    One list, one evaluator, used by every continuation path. Optional-but-open
    evidence is reported as ``optional-unresolved`` and never blocks; required
    evidence that is missing, stale, unresolved or unsatisfied does.
    """
    project = Path(project or state.get("project", ""))
    requirements: list[dict] = []
    required_stage = CREATIVE_STAGE_REQUIREMENTS.get(target)
    if required_stage:
        requirement = creative_evidence_requirement(state, project, required_stage)
        requirement["stage"] = required_stage
        requirement["boundary"] = target
        requirements.append(requirement)
    level = OPERATIONS_REQUIREMENT_LEVEL.get(target)
    if level:
        requirement = operations_evidence_requirement(state, project, level)
        requirement["stage"] = target
        requirement["boundary"] = target
        requirements.append(requirement)
    if target in DESIGN_REQUIREMENT_BOUNDARIES and state.get("design_characterisations"):
        requirement = design_evidence_requirement(state, project, target)
        requirement["boundary"] = target
        requirements.append(requirement)
    return requirements


# ------------------------------------------------------ design evidence (T6)

def planned_design_requirements(project: Path) -> list[dict]:
    """The approved requirements that need rendered or behavioural evidence.

    The requirement set comes from the same creative-operations ledger the
    implementation is built from, so design closure cannot invent a shorter list.
    """
    operations = _tool("operations")
    ledger = operations.load_ledger(Path(project))
    if not isinstance(ledger, Mapping):
        return []
    rows: list[dict] = []
    for requirement in ledger.get("requirements") or []:
        if not isinstance(requirement, Mapping):
            continue
        expected = str(requirement.get("expected_evidence_kind", "screenshot") or "screenshot")
        rows.append({
            "id": str(requirement.get("id", "")),
            "kind": str(requirement.get("kind", "")),
            "evidence_kind": DESIGN_EVIDENCE_KIND_BY_OPERATIONS.get(expected, "rendered"),
            "expected_evidence_kind": expected,
        })
    return [row for row in rows if row["id"]]


def design_evidence_requirement(state: dict, project: Path, target: str) -> dict:
    """The AR-202D requirement at one boundary, as a record.

    ``S4B`` requires an approved, current design direction when the plan selected
    the direction stage. ``S5`` requires the selected observation work to be
    closed with real evidence and the selected critique to exist.
    """
    from . import design as design_module

    requirement = {
        "id": f"design-{target.lower()}",
        "source": "design-intelligence",
        "stage": target,
        "required": False,
        "state": "satisfied",
        "detail": "this task selected no design-intelligence work at this boundary",
        "evidence": [],
    }
    characterisation = design_module.latest_characterisation(state)
    if not characterisation:
        return requirement
    plan = design_module.latest_plan(state)
    stages = plan.get("stages") if isinstance(plan.get("stages"), Mapping) else {}
    task_id = str(characterisation.get("task_id", ""))

    def selection(stage: str) -> str:
        return str((stages.get(stage) or {}).get("selection", "SKIPPED"))

    if target == "S4B":
        if selection("DIRECT") != "REQUIRED":
            requirement["detail"] = (
                "the design plan did not select the direction stage; no direction approval is required"
            )
            return requirement
        requirement["required"] = True
        problems = design_module.direction_problems(state, task_id=task_id, require_approval=True)
        requirement["evidence"] = [
            str(record.get("direction_id"))
            for record in design_module.directions(state)
            if not task_id or str(record.get("task_id", "")) == task_id
        ]
        if problems:
            stale = any("stale" in item.lower() for item in problems)
            requirement.update({
                "state": "stale" if stale else "missing",
                "detail": "; ".join(problems),
            })
            return requirement
        requirement.update({"state": "satisfied", "detail": "the design direction is approved for its current revision"})
        return requirement

    # ------------------------------------------------------------------ S5
    if selection("OBSERVE") == "REQUIRED" or selection("CRITIQUE") == "REQUIRED":
        requirement["required"] = True
    problems: list[str] = []
    if selection("OBSERVE") == "REQUIRED":
        stale = design_module.stale_requirements(state)
        if stale:
            problems.append(
                "rendered evidence no longer matches what a requirement was closed with: "
                + "; ".join(str(item.get("requirement_id")) for item in stale)
            )
        required_rows = [
            row for row in planned_design_requirements(Path(project))
            if row["evidence_kind"] in ("rendered", "behavioural")
        ]
        if required_rows:
            problems.extend(design_module.requirement_problems(state, required_rows))
    if selection("CRITIQUE") == "REQUIRED":
        from . import critique as critique_module

        passed = [
            record for record in critique_module.reviews(state)
            if str(record.get("outcome")) in ("passed", "failed")
        ]
        if not passed:
            problems.append(
                "the design plan requires an independent critique and none is recorded "
                "(DESIGN_REVIEW_FAILURE)"
            )
        elif str(passed[-1].get("outcome")) == "failed":
            open_findings = [
                item for item in critique_module.findings(state)
                if str(item.get("state", "open")) in ("open", "unresolved")
            ]
            summary = critique_module.refinement_summary(state)
            if open_findings and not summary["budget"]["remaining"] and summary["cycles"] >= critique_module.MAX_DESIGN_REFINEMENTS:
                problems.append(
                    "the independent critique found unresolved defects and the bounded refinement "
                    "budget is exhausted; a human decision is required (REFINEMENT_LIMIT_REACHED)"
                )
    requirement["evidence"] = [
        str(record.get("evidence_id")) for record in (state.get("rendered_evidence") or [])
        if isinstance(record, Mapping)
    ][-10:]
    if problems:
        requirement.update({"state": "unsatisfied", "detail": "; ".join(dict.fromkeys(problems))})
        return requirement
    if not requirement["required"]:
        requirement["detail"] = "this task selected no design observation or critique work"
        return requirement
    requirement.update({"state": "satisfied", "detail": "design observation and critique evidence is closed"})
    return requirement


def evidence_requirement_problems(requirements: list[dict]) -> list[str]:
    """Only requirements that are required and not satisfied block a transition."""
    problems: list[str] = []
    for requirement in requirements:
        if not requirement.get("required"):
            continue
        if str(requirement.get("state")) == "satisfied":
            continue
        problems.append(
            f"{requirement.get('source')} evidence for {requirement.get('stage') or requirement.get('id')} "
            f"(boundary {requirement.get('boundary') or '?'}) is {requirement.get('state')}: "
            f"{requirement.get('detail')}"
        )
    return problems


def optional_evidence(state: dict, target: str, *, project: Path | None = None) -> list[dict]:
    """Evidence the workflow selected that is not finished, reported but not enforced."""
    return [
        requirement for requirement in evidence_requirements(state, target, project=project)
        if str(requirement.get("state")) == "optional-unresolved" or not requirement.get("required")
    ]


def continuation_problems(state: dict, target: str, *, project: Path | None = None) -> list[str]:
    """The single precondition set for a stage transition to ``target``."""
    project = Path(project or state.get("project", ""))
    packets = state.get("packets") or []
    current = str(packets[-1].get("stage")) if packets else None
    packet = Path(packets[-1].get("path")) if packets else None
    problems: list[str] = []
    if target == current:
        # Same-boundary re-entry (routine repair, escalation or a reasoner retry):
        # the entry preconditions were satisfied when the boundary was first
        # entered, and the retry policy (budget, blocked return) governs instead.
        return problems
    if target in ("S2", "S3"):
        # The proposal function already refuses to propose these while the current
        # boundary is incomplete, so no extra policy precondition applies here.
        # (A same-stage retry re-enters S3 for a rejected or reasoner-failed direction.)
        return problems
    if target == "S4A":
        missing = [name for name in ("DESIGN.md", "AGENTS.md") if not (project / name).is_file()]
        problems.extend(f"missing stage output: {name}" for name in missing)
        if not missing:
            problems.extend(creative_evidence_problems(state, project))
            problems.extend(g1_problems(state, project))
        return problems
    if target == "S4B":
        problems.extend(preflight_problems(state))
        problems.extend(g2_problems(state, project))
        problems.extend(evidence_requirement_problems(evidence_requirements(state, target, project=project)))
        return problems
    if target == "S5":
        if packet is not None:
            problems.extend(validation_problems(state, packet))
        problems.extend(evidence_requirement_problems(evidence_requirements(state, target, project=project)))
        return problems
    if target == "S6":
        if packet is not None:
            problems.extend(review_requirements_problems(state, packet))
        return problems
    return problems


def repair_allowed(state: dict) -> tuple[bool, str]:
    """The bounded routine-repair budget, stated once for every caller."""
    worker = state.get("worker") or {}
    try:
        attempt = max(1, int(worker.get("attempt", 1) or 1))
    except (TypeError, ValueError):
        attempt = 1
    try:
        limit = int(worker.get("repair_limit", MAX_ROUTINE_REPAIRS) or 0)
    except (TypeError, ValueError):
        limit = 0
    if attempt - 1 >= limit:
        return False, (
            "Routine worker retry is not permitted: the bounded repair budget is exhausted. "
            "Use --escalate with a stronger worker role."
        )
    state_value = str(worker.get("validation_state", ""))
    if state_value == "BLOCKED":
        return False, (
            "Routine worker retry is not permitted: the previous result was blocked, and a blocked "
            "result never enters routine repair. Use --escalate with a stronger worker role."
        )
    return True, ""


def retry_problems(state: dict, packet: Path) -> list[str]:
    """Preconditions for repeating the current S4B boundary."""
    problems: list[str] = []
    prior_return = Path(packet) / "evidence" / "return-handoff.md"
    transport = _tool("transport")
    if prior_return.is_file() and transport.return_handoff_status(prior_return.read_text(encoding="utf-8")) == "blocked":
        problems.append(
            "Routine worker retry is not permitted after a blocked return. "
            "Inspect the recorded conflict and use --escalate with a stronger worker role."
        )
        return problems
    allowed, reason = repair_allowed(state)
    if not allowed:
        problems.append(reason)
        return problems
    prior_validation = Path(packet) / "evidence" / "validation.json"
    if prior_validation.is_file():
        try:
            validation = json.loads(prior_validation.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return problems
        worker = state.get("worker") or {}
        from . import statemachine
        prior_outcome = statemachine.worker_transition_for(
            validation.get("status", "blocked"),
            validation.get("failure_kind", "routine"),
            max(0, int(worker.get("attempt", 1) or 1) - 1),
            int(worker.get("repair_limit", MAX_ROUTINE_REPAIRS) or 0),
        )
        if not prior_outcome["retryable"]:
            problems.append(
                "Routine worker retry is not permitted: " + prior_outcome["next"]
                + " Use --escalate with a stronger worker role."
            )
    return problems
