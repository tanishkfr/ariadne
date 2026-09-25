"""Independent design critique and bounded refinement (AR-202D T9/T10).

Four QA activities are kept apart, and each needs its own evidence:

``functional``   does it work (command records, returncodes, output digests)
``accessibility`` can it be operated and perceived (a11y rules, manual checks)
``regression``   did the rendering change unexpectedly (capture comparison)
``judgement``    does it satisfy the intended experience and direction

They are never merged into one PASS score, because a page can be functionally
correct and badly designed, look right and be inaccessible, and pass a
screenshot comparison while violating the direction it was supposed to follow.

The critique itself is bound to execution provenance: the reviewer is an
engine-created execution, the implementer is a different engine-created
execution, the direction must be the approved one *for its current revision*,
and the rendered evidence must exist and be current. An implementer cannot
certify its own visual quality, a review without rendered evidence is refused
where rendering is required, and a critique against a stale direction is refused.

Refinement is defect-scoped and bounded. A finding produces a plan that names
the smallest artifacts to change and the regression checks to re-run; "the design
could be better" produces nothing. The repair budget is the same bounded number
the rest of the engine uses, so design refinement and implementation repair
cannot each claim a fresh budget.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Mapping, Sequence

from . import contracts, design as design_module, render as render_module, review as review_module
from .contracts import (
    DESIGN_FINDING_STATES,
    DESIGN_REVIEW_DIMENSIONS,
    DESIGN_SEVERITIES,
    ContractError,
)

MAX_DESIGN_REFINEMENTS = 2
"""Bounded automatic design refinement cycles. Deliberately the same number as
``policy.MAX_ROUTINE_REPAIRS``: one global notion of repair budget per stage."""

QA_ACTIVITIES = ("functional", "accessibility", "regression", "judgement")

BROAD_SCOPE_TOKENS = ("everything", "all screens", "the whole", "entire interface", "full redesign", "all pages")

FINDING_REQUIRED = ("dimension", "severity", "evidence_ids", "explanation", "repair_scope")


def reviews(state: dict) -> list[dict]:
    values = state.get("design_reviews")
    if not isinstance(values, list):
        return []
    return [item for item in values if isinstance(item, Mapping)]


def review(state: dict, review_id: str) -> dict | None:
    for record in reviews(state):
        if str(record.get("review_id", "")) == str(review_id):
            return record
    return None


def findings(state: dict) -> list[dict]:
    rows: list[dict] = []
    for record in reviews(state):
        for finding in (record.get("findings") or []):
            if isinstance(finding, Mapping):
                rows.append(dict(finding))
    return rows


def finding(state: dict, finding_id: str) -> dict | None:
    for record in findings(state):
        if str(record.get("finding_id", "")) == str(finding_id):
            return record
    return None


def finding_problems(state: dict) -> list[str]:
    """Every finding must cite evidence and name a repair scope."""
    problems: list[str] = []
    for record in findings(state):
        if str(record.get("state", "open")) not in DESIGN_FINDING_STATES:
            problems.append(f"design finding {record.get('finding_id')} has an unsupported state")
        if not record.get("evidence_ids"):
            problems.append(f"design finding {record.get('finding_id')} cites no evidence")
        if not str(record.get("repair_scope", "")).strip():
            problems.append(f"design finding {record.get('finding_id')} names no repair scope")
    return problems


# --------------------------------------------------------------- preparation

def _evidence_preconditions(
    state: dict,
    *,
    task_id: str,
    evidence_ids: Sequence[str],
    revision_hash: str = "",
) -> tuple[list[dict], list[str]]:
    """(evidence descriptors, problems) for a critique's rendered evidence.

    Shared by preparation *and* ingest on purpose: the ingest path is reachable
    directly from an event, so a precondition that only preparation enforces is a
    precondition a caller can skip by constructing the event differently.
    """
    problems: list[str] = []
    rows: list[dict] = []
    rendered_required = _rendered_required(state, task_id=task_id)
    if not evidence_ids:
        if rendered_required:
            problems.append(
                "this task requires rendered evidence, and a critique without it is refused; "
                "record the capture before preparing the review"
            )
        return rows, problems
    stale = {
        str(item.get("evidence_id"))
        for item in render_module.stale_records(state, revision_hash=revision_hash)
    }
    for evidence_id in evidence_ids:
        record = render_module.by_id(state, str(evidence_id))
        if record is None:
            problems.append(f"critique cites unknown rendered evidence: {evidence_id}")
            continue
        if str(record.get("state")) == "UNVERIFIED":
            problems.append(
                f"critique cites evidence that was never captured: {evidence_id}"
            )
            continue
        if str(evidence_id) in stale:
            problems.append(f"critique cites stale rendered evidence: {evidence_id} (RENDER_EVIDENCE_STALE)")
            continue
        rows.append({
            "evidence_id": record.get("evidence_id"),
            "state": record.get("state"),
            "kind": record.get("kind"),
            "viewport": record.get("viewport"),
        })
    if rendered_required and rows and not any(
        render_module.strength(str(item.get("state"))) >= render_module.strength("RENDERED")
        for item in rows
    ):
        problems.append("a critique of rendered work cannot rest on source suggestions alone")
    return rows, problems


def prepare_review(
    state: dict,
    *,
    task_id: str,
    direction_id: str = "",
    requirement_ids: Sequence[str] = (),
    evidence_ids: Sequence[str] = (),
    reviewer_role: str = "independent-reviewer",
    dimensions: Sequence[str] = (),
    revision_hash: str = "",
    reviewer_execution: str = "",
    implementing_execution: str = "",
) -> dict:
    """Assemble the critique request and verify its preconditions before any review runs."""
    problems: list[str] = []
    required_stage = design_module.stage_selection(
        design_module.latest_characterisation(state, task_id=task_id), "CRITIQUE",
    )
    direction = design_module.direction(state, direction_id) if direction_id else design_module.active_direction(state, task_id=task_id)
    if not direction:
        problems.append(
            "an independent design critique needs the approved direction it judges against "
            "(DESIGN_DIRECTION_MISSING)"
        )
    else:
        satisfied, reason = _direction_gate(state, direction)
        if not satisfied:
            problems.append(
                "the direction under review is not the approved revision (DESIGN_DIRECTION_STALE): " + reason
            )
    dimension_list = [str(item) for item in (dimensions or ()) if str(item).strip()]
    unknown = sorted(set(dimension_list) - set(DESIGN_REVIEW_DIMENSIONS))
    if unknown:
        problems.append("unknown critique dimension(s): " + ", ".join(unknown))
    evidence_rows, evidence_problems = _evidence_preconditions(
        state, task_id=task_id, evidence_ids=evidence_ids, revision_hash=revision_hash,
    )
    problems.extend(evidence_problems)
    if not requirement_ids:
        problems.append("a design critique must name the requirements it judges")
    problems.extend(review_module.independence_problems(
        state, _reviewer_label(state, reviewer_role),
        reviewer_execution=reviewer_execution, implementing_execution=implementing_execution,
    ))
    if problems:
        raise ContractError("design review cannot be prepared: " + "; ".join(dict.fromkeys(problems)))
    request = {
        "schema_version": contracts.SCHEMA_DESIGN,
        "request_id": contracts.new_record_id("drq"),
        "run_id": str(state.get("run_id", "")),
        "task_id": str(task_id),
        "direction_id": str(direction.get("direction_id", "")),
        "direction_revision": design_module.direction_revision(direction),
        "requirement_ids": [str(item) for item in requirement_ids],
        "evidence": evidence_rows,
        "dimensions": dimension_list or list(DESIGN_REVIEW_DIMENSIONS),
        "reviewer_role": str(reviewer_role),
        "reviewer_execution": str(reviewer_execution),
        "implementing_execution": str(implementing_execution),
        "critique_stage": required_stage,
        "qa_separation": {
            "functional": "does it work; evidence is a command record, not a screenshot",
            "accessibility": "can it be operated and perceived; evidence is a rule result or a manual check",
            "regression": "did the rendering change unexpectedly; evidence is a capture comparison",
            "judgement": "does it satisfy the intended experience and the approved direction",
            "note": "these four are recorded and reported separately and never collapsed into one score",
        },
        "questions": [
            "which dimensions fail, at which location, with which evidence?",
            "which requirement does each finding affect?",
            "what is the smallest repair that would resolve it?",
            "what would that repair risk breaking?",
        ],
        "recorded_at": contracts.utc_now(),
    }
    return request


def _reviewer_label(state: dict, reviewer_role: str) -> str:
    """A reviewer identity that is not the implementation worker, deterministically."""
    worker_ids = {value.lower() for value in review_module.worker_identities(state)}
    candidate = f"{reviewer_role}@{state.get('run_id', 'run')}"
    if candidate.lower() in worker_ids:
        candidate = f"{candidate}#design"
    return candidate


def _rendered_required(state: dict, *, task_id: str) -> bool:
    record = design_module.latest_characterisation(state, task_id=task_id)
    value = str(((record.get("characteristics") or {}).get("rendered_qa") or {}).get("value", ""))
    return value == "REQUIRED"


def _direction_gate(state: dict, direction: Mapping) -> tuple[bool, str]:
    from . import policy

    return policy.gate_satisfied(state, "G1D", design_module.direction_subject(direction))


# ------------------------------------------------------------------- ingest

def build_review(
    state: dict,
    *,
    task_id: str,
    direction_id: str,
    findings: Sequence[Mapping],
    reviewer_identity: str,
    reviewer_execution: str,
    implementing_execution: str,
    requirement_ids: Sequence[str] = (),
    evidence_ids: Sequence[str] = (),
    outcome: str = "passed",
    differential: str = "",
    qa_records: Mapping | None = None,
    reviewer_role: str = "independent-reviewer",
    revision_hash: str = "",
) -> dict:
    """Record one independent critique. Independence and evidence are checked here.

    The evidence preconditions are the same ones preparation enforces, because
    this function is reachable directly from an event: a guard that only
    preparation applies is a guard a caller can avoid.
    """
    problems = review_module.independence_problems(
        state, reviewer_identity,
        reviewer_execution=reviewer_execution, implementing_execution=implementing_execution,
    )
    if problems:
        raise ContractError("design review refused: " + "; ".join(problems))
    direction = design_module.direction(state, direction_id)
    if not direction:
        raise ContractError(f"no design-direction record matches {direction_id!r}")
    satisfied, reason = _direction_gate(state, direction)
    if not satisfied:
        raise ContractError("design review refused: the direction under review is not the approved revision: " + reason)
    if outcome not in ("passed", "failed", "blocked", "not-performed"):
        raise ContractError(f"unsupported design review outcome: {outcome!r}")
    if not requirement_ids:
        raise ContractError("a design critique must name the requirements it judges")
    _, evidence_problems = _evidence_preconditions(
        state, task_id=task_id, evidence_ids=evidence_ids, revision_hash=revision_hash,
    )
    if evidence_problems:
        raise ContractError("design review refused: " + "; ".join(dict.fromkeys(evidence_problems)))
    stale = {str(item.get("evidence_id")) for item in render_module.stale_records(state, revision_hash=revision_hash)}
    rows: list[dict] = []
    for item in findings or ():
        if not isinstance(item, Mapping):
            raise ContractError("a design finding must be an object")
        row = dict(item)
        missing = [name for name in FINDING_REQUIRED if not row.get(name)]
        if missing:
            raise ContractError(
                "a design finding must record " + ", ".join(missing) + "; a finding without evidence or a "
                "repair scope cannot be acted on"
            )
        if str(row.get("dimension")) not in DESIGN_REVIEW_DIMENSIONS:
            raise ContractError(f"unknown critique dimension: {row.get('dimension')!r}")
        if str(row.get("severity")) not in DESIGN_SEVERITIES:
            raise ContractError(f"unknown finding severity: {row.get('severity')!r}")
        citations = [str(value) for value in (row.get("evidence_ids") or [])]
        for citation in citations:
            if render_module.by_id(state, citation) is None:
                raise ContractError(f"a design finding cites unknown evidence: {citation}")
            if citation in stale:
                raise ContractError(
                    f"a design finding cites stale evidence: {citation}; re-capture before critiquing it"
                )
        if row.get("requirement_id") and requirement_ids and str(row["requirement_id"]) not in {
            str(value) for value in requirement_ids
        }:
            raise ContractError(
                f"a design finding names requirement {row['requirement_id']}, which is not in the reviewed set"
            )
        row.setdefault("finding_id", contracts.new_record_id("dfn"))
        row.setdefault("state", "open")
        row.setdefault("confidence", "unsupported")
        row.setdefault("requirement_id", "")
        row["evidence_ids"] = citations
        rows.append(row)
    record = {
        "schema_version": contracts.SCHEMA_DESIGN,
        "review_id": contracts.new_record_id("dsr"),
        "run_id": str(state.get("run_id", "")),
        "task_id": str(task_id),
        "review_kind": "design",
        "reviewer_identity": str(reviewer_identity).strip(),
        "reviewer_role": str(reviewer_role).strip(),
        "direction_id": str(direction_id),
        "direction_revision": design_module.direction_revision(direction),
        "requirements": [str(item) for item in (requirement_ids or ())],
        "evidence": [str(item) for item in (evidence_ids or ())],
        "findings": rows,
        "outcome": str(outcome),
        "differential": str(differential),
        "qa_activities": _qa_activities(state, qa_records or {}),
        "execution_binding": "engine",
        "reviewer_execution": str(reviewer_execution),
        "implementing_execution": str(implementing_execution),
        "independence_level": review_module.independence_level(
            state,
            reviewer_execution=str(reviewer_execution),
            implementing_execution=str(implementing_execution),
        ),
        "recorded_at": contracts.utc_now(),
        "provenance": {"created_by": "engine", "policy_version": contracts.POLICY_VERSION},
    }
    problems = contracts.design_review_problems(record)
    if problems:
        raise ContractError("design review is malformed: " + "; ".join(problems))
    contracts.require_design_capacity(state, "design_reviews")
    state.setdefault("design_reviews", []).append(record)
    return record


def _qa_activities(state: dict, supplied: Mapping) -> dict:
    """The four QA activities, each with its own evidence. Never one merged verdict."""
    values = dict(supplied or {})
    rows: dict[str, dict] = {}
    for activity in QA_ACTIVITIES:
        value = values.get(activity)
        if isinstance(value, Mapping):
            rows[activity] = {
                "state": str(value.get("state", "not-recorded")),
                "evidence": [str(item) for item in (value.get("evidence") or [])],
                "detail": str(value.get("detail", "")),
            }
        else:
            rows[activity] = {
                "state": "not-recorded",
                "evidence": [],
                "detail": "this activity was not recorded for this revision",
            }
    rows["note"] = "the four activities are reported separately; there is no combined design score"
    return rows


# ------------------------------------------------------------- refinement

def refinements(state: dict) -> list[dict]:
    values = state.get("design_refinements")
    if not isinstance(values, list):
        return []
    return [item for item in values if isinstance(item, Mapping)]


def refinement(state: dict, refinement_id: str) -> dict | None:
    for record in refinements(state):
        if str(record.get("refinement_id", "")) == str(refinement_id):
            return record
    return None


def refinement_budget(state: dict, *, task_id: str = "") -> dict:
    """How much bounded repair budget remains for this task, stated once."""
    attempts = [
        record for record in refinements(state)
        if (not task_id or str(record.get("task_id", "")) == str(task_id))
        and str(record.get("state", "")) in ("proposed", "applied", "verified", "failed")
    ]
    from . import policy

    worker_allowed, worker_reason = policy.repair_allowed(state)
    remaining = max(0, MAX_DESIGN_REFINEMENTS - len(attempts))
    return {
        "limit": MAX_DESIGN_REFINEMENTS,
        "attempts": len(attempts),
        "remaining": remaining,
        "worker_repair_allowed": bool(worker_allowed),
        "worker_repair_reason": worker_reason,
    }


def propose_refinement(
    state: dict,
    finding_id: str,
    *,
    task_id: str,
    artifact: str,
    intended_change: str,
    permitted_scope: Sequence[str],
    expected_evidence: Sequence[str],
    regression_checks: Sequence[str],
    revision_hash: str = "",
) -> dict:
    """Turn one finding into a defect-scoped repair plan, or refuse."""
    finding_row = finding(state, finding_id)
    if finding_row is None:
        raise ContractError(f"no design finding matches {finding_id!r}")
    if str(finding_row.get("state", "open")) in ("repaired", "rejected"):
        raise ContractError(f"finding {finding_id} is already {finding_row.get('state')}")
    budget = refinement_budget(state, task_id=task_id)
    if budget["remaining"] <= 0:
        raise ContractError(
            f"the bounded refinement budget ({budget['limit']}) is exhausted for this task "
            "(REFINEMENT_LIMIT_REACHED); a human must decide whether to continue"
        )
    if not budget["worker_repair_allowed"] and str(finding_row.get("severity")) != "blocking":
        raise ContractError(
            "the run's routine repair budget is already spent; only a blocking finding may still "
            "justify a repair: " + budget["worker_repair_reason"]
        )
    scope = [str(item).strip() for item in (permitted_scope or []) if str(item).strip()]
    if not scope:
        raise ContractError("a refinement must name the smallest artifacts it changes")
    joined = " ".join(scope).lower()
    if any(token in joined for token in BROAD_SCOPE_TOKENS) and str(finding_row.get("severity")) != "blocking":
        raise ContractError(
            "a non-blocking finding cannot authorize a broad redesign; name the specific artifacts instead"
        )
    expected = [str(item).strip() for item in (expected_evidence or []) if str(item).strip()]
    if not expected:
        raise ContractError(
            "a refinement must declare the evidence it will re-take; a repair that produces no new "
            "evidence cannot be shown to have fixed anything"
        )
    checks = [str(item).strip() for item in (regression_checks or []) if str(item).strip()]
    if not checks:
        raise ContractError(
            "a refinement must declare the regression checks it will re-run; a fix that breaks a passing "
            "check is a regression, not a fix"
        )
    record = {
        "schema_version": contracts.SCHEMA_DESIGN,
        "refinement_id": contracts.new_record_id("rfn"),
        "run_id": str(state.get("run_id", "")),
        "task_id": str(task_id),
        "finding_id": str(finding_id),
        "artifact": str(artifact),
        "intended_change": str(intended_change),
        "permitted_scope": scope,
        "expected_evidence": expected,
        "regression_checks": checks,
        "revision_hash": str(revision_hash),
        "state": "proposed",
        "regressions": [],
        "resolved": False,
        "recorded_at": contracts.utc_now(),
        "provenance": {"created_by": "engine", "policy_version": contracts.POLICY_VERSION},
    }
    problems = contracts.refinement_problems(record)
    if problems:
        raise ContractError("refinement is malformed: " + "; ".join(problems))
    contracts.require_design_capacity(state, "design_refinements")
    state.setdefault("design_refinements", []).append(record)
    return record


def record_refinement(
    state: dict,
    refinement_id: str,
    *,
    applied: bool,
    changed_artifacts: Sequence[str],
    revalidated: Mapping | None = None,
    recaptured: Sequence[str] = (),
    regressions: Sequence[str] = (),
    notes: str = "",
) -> dict:
    """Close one refinement cycle: scope respected, evidence re-taken, regressions checked."""
    record = refinement(state, refinement_id)
    if record is None:
        raise ContractError(f"no refinement matches {refinement_id!r}")
    if str(record.get("state")) not in ("proposed",):
        raise ContractError(f"refinement {refinement_id} is {record.get('state')}; it is not open")
    permitted = {str(item) for item in (record.get("permitted_scope") or [])}
    changed = [str(item) for item in (changed_artifacts or [])]
    outside = [item for item in changed if permitted and not _within_scope(item, permitted)]
    if not applied:
        record["state"] = "abandoned"
        record["closed_at"] = contracts.utc_now()
        record["notes"] = str(notes)
        return record
    if outside:
        raise ContractError(
            "the refinement changed artifacts outside its permitted scope: " + ", ".join(sorted(outside))
        )
    regression_list = [str(item) for item in (regressions or [])]
    record["state"] = "verified" if not regression_list else "failed"
    record["applied_at"] = contracts.utc_now()
    record["changed_artifacts"] = changed
    record["revalidated"] = dict(revalidated or {})
    record["recaptured"] = [str(item) for item in (recaptured or [])]
    record["regressions"] = regression_list
    record["notes"] = str(notes)
    expected = [str(item) for item in (record.get("expected_evidence") or [])]
    missing = [item for item in expected if str(item) not in {str(value) for value in (recaptured or ())}]
    if missing:
        record["state"] = "failed"
        record["regressions"] = regression_list + [
            f"expected evidence was not re-taken: {item}" for item in missing
        ]
    return record


def _within_scope(item: str, permitted: set[str]) -> bool:
    """Whether one changed artifact is inside the refinement's permitted scope.

    Delegates to :func:`ariadne_engine.contracts.path_matches`, the same rule the
    runtime's worker scope check applies: exact equality, an ``fnmatch`` glob, or
    a ``/**`` directory prefix. The previous substring clause admitted
    ``srcx/evil.py`` for a permitted ``src`` and ``vendor/src/app.py`` for a
    permitted ``src/app.py``, and never matched the ``src/**`` vocabulary the
    runtime itself uses.
    """
    return any(contracts.path_matches(item, entry) for entry in permitted)


def resolve_findings(state: dict, refinement_id: str, *, resolved: Sequence[str], still_open: Sequence[str] = ()) -> dict:
    """Update finding states after a scored refinement cycle."""
    record = refinement(state, refinement_id)
    if record is None:
        raise ContractError(f"no refinement matches {refinement_id!r}")
    updated: list[dict] = []
    resolved_set = {str(item) for item in resolved}
    open_set = {str(item) for item in still_open}
    for review_row in (state.get("design_reviews") or []):
        if not isinstance(review_row, Mapping):
            continue
        for finding_row in (review_row.get("findings") or []):
            if not isinstance(finding_row, Mapping):
                continue
            finding_id = str(finding_row.get("finding_id", ""))
            if finding_id == str(record.get("finding_id")):
                finding_row["state"] = "repaired" if str(record.get("state")) == "verified" else "unresolved"
                record["resolved"] = finding_row["state"] == "repaired"
            elif finding_id in resolved_set:
                finding_row["state"] = "repaired"
            elif finding_id in open_set:
                finding_row["state"] = "unresolved"
            updated.append(dict(finding_row))
    record["finding_states"] = updated
    return record


def refinement_summary(state: dict, *, task_id: str = "") -> dict:
    """What remains visible after refinement: resolved, unresolved, regressions."""
    rows = [record for record in refinements(state) if not task_id or str(record.get("task_id", "")) == str(task_id)]
    remaining = [
        item for item in findings(state) if str(item.get("state", "open")) in ("open", "unresolved")
    ]
    regressions: list[str] = []
    for record in rows:
        regressions.extend(str(item) for item in (record.get("regressions") or []))
    return {
        "cycles": len(rows),
        "resolved": sum(1 for record in rows if record.get("resolved")),
        "regressions": regressions,
        "remaining_findings": [
            {
                "finding_id": item.get("finding_id"),
                "dimension": item.get("dimension"),
                "severity": item.get("severity"),
                "state": item.get("state", "open"),
            }
            for item in remaining
        ],
        "budget": refinement_budget(state, task_id=task_id),
    }


def describe(record: Mapping) -> str:
    return (
        f"{record.get('review_id')} {record.get('outcome')} with "
        f"{len(record.get('findings') or [])} finding(s) against direction "
        f"{record.get('direction_id')}"
    )


__all__ = [
    "MAX_DESIGN_REFINEMENTS",
    "QA_ACTIVITIES",
    "FINDING_REQUIRED",
    "reviews",
    "review",
    "findings",
    "finding",
    "finding_problems",
    "prepare_review",
    "build_review",
    "refinements",
    "refinement",
    "refinement_budget",
    "propose_refinement",
    "record_refinement",
    "resolve_findings",
    "refinement_summary",
    "describe",
]
