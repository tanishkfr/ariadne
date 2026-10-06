"""Vocabulary bridging, kept in one place so no module invents its own terms (AR-222).

The engine already had severity, dimension, evidence-state and outcome vocabularies.
Inventing AR-222-flavoured duplicates of any of them would mean a reader has to learn
which vocabulary a given record uses, and the two would drift.

So this module does the opposite of what a new subsystem usually does: it points at
the existing definitions and refuses the ones that would conflict. Where AR-222 genuinely
needed something new -- a capture plan, a render outcome, a coverage state -- the new
term lives in :mod:`ariadne_engine.contracts` and is re-exported here, so there is one
home and one import path for callers.

The one place this module does real work is :func:`severity_rank` and
:func:`blocking_findings`, because "which of these findings are serious enough to repair"
is a question several callers ask and only one of them should answer.
"""

from __future__ import annotations

from typing import Mapping, Sequence

from .. import contracts

#: Reused verbatim. AR-222 does not introduce a severity vocabulary.
SEVERITIES = contracts.DESIGN_SEVERITIES
SEVERITY_RANK = {"blocking": 0, "major": 1, "minor": 2, "note": 3}

#: Reused verbatim from AR-202D. Seventeen named critique dimensions.
DIMENSIONS = contracts.DESIGN_REVIEW_DIMENSIONS

#: Reused verbatim. The five-state evidence ladder.
EVIDENCE_STATES = contracts.RENDERED_EVIDENCE_STATES
CAPTURE_METHODS = contracts.RENDER_CAPTURE_METHODS

#: Reused verbatim from AR-221. Eleven material design categories.
MATERIALITY_CATEGORIES = contracts.MATERIAL_DESIGN_CATEGORIES

#: New in AR-222, defined once in contracts.
CAPTURE_PLAN_STATUSES = contracts.CAPTURE_PLAN_STATUSES
CAPTURE_TARGET_BASES = contracts.CAPTURE_TARGET_BASES
CAPTURE_TARGET_KINDS = contracts.CAPTURE_TARGET_KINDS
CAPTURE_BUDGET_DEFAULTS = contracts.DEFAULT_CAPTURE_BUDGET
RENDER_OUTCOMES = contracts.RENDER_OUTCOMES
COVERAGE_STATES = contracts.CRITIQUE_COVERAGE_STATES
FINDING_BASES = contracts.FINDING_BASES
ARTIFACT_VALIDATION_STATES = contracts.ARTIFACT_VALIDATION_STATES
REPAIR_FINDING_STATES = contracts.REPAIR_FINDING_STATES

#: AR-221's own binding decision, quoted so the two phases cannot drift on it.
VISUAL_ACCEPTANCE_NOT_CLAIMED = "NOT_CLAIMED"
VISUAL_ACCEPTANCE_BY_RENDER = "VERIFIED_BY_RENDERED_CHECK"
"""AR-221 reserved ``VERIFIED_BY_RENDERED_CHECK`` in
:func:`ariadne_engine.contracts.implementation_run_problems`, requiring a
``rendered_check_id`` because "source inspection cannot stand in for one". This phase
is what supplies that id: the critique that established the acceptance."""


def severity_rank(severity: str) -> int:
    return SEVERITY_RANK.get(str(severity), 3)


def blocking_findings(findings: Sequence[Mapping], *, at_least: str = "major") -> list[dict]:
    """Findings serious enough to justify a bounded repair attempt."""
    threshold = severity_rank(at_least)
    return [
        dict(row) for row in findings or ()
        if severity_rank(str(row.get("severity", "note"))) <= threshold
    ]


def observation_findings(findings: Sequence[Mapping]) -> list[dict]:
    """Findings that need no repair. Reported, deliberately not acted on."""
    return [dict(row) for row in findings or () if str(row.get("severity", "")) == "note"]


def actionable_findings(findings: Sequence[Mapping]) -> dict:
    """The triage, computed once.

    Separated rather than filtered so a caller can report what it did *not* act on. An
    observation that vanishes into a filter is indistinguishable from an observation that
    was never made, and §48 is explicit that real findings must be reported honestly --
    including the ones that need nothing done.
    """
    rows = [dict(row) for row in findings or ()]
    return {
        "blocking": blocking_findings(rows),
        "repairable": blocking_findings(rows, at_least="major"),
        "polish": [dict(row) for row in rows if str(row.get("severity", "")) == "minor"],
        "observations": observation_findings(rows),
        "note": (
            "an observation is a recorded result, not a discarded one; nothing here decides whether a "
            "polish item is worth doing"
        ),
    }


def counts_by(rows: Sequence[Mapping], key: str) -> dict[str, int]:
    out: dict[str, int] = {}
    for row in rows or ():
        value = str(dict(row).get(key, ""))
        out[value] = out.get(value, 0) + 1
    return out


def validate_visual_acceptance(acceptance: Mapping, *, rendered_check_id: str = "") -> list[str]:
    """Whether a visual-acceptance claim is one this phase can support.

    Delegates to the AR-221 contract rather than restating it, so the rule stays in one
    place: the claim may be ``VERIFIED_BY_RENDERED_CHECK`` only with a real critique id,
    and must otherwise carry the reason it was not claimed. Only the acceptance field is
    under test here, so the surrounding run record is built to be structurally valid --
    a harness that reported unrelated validation failures would hide the one it means to
    check.
    """
    claim = dict(acceptance)
    if rendered_check_id:
        claim["rendered_check_id"] = str(rendered_check_id)
    record = {
        "schema_version": contracts.SCHEMA_DESIGN,
        "run_record_id": contracts.new_record_id("dir"),
        "run_id": str(claim.get("run_id", "run-1")),
        "task_id": str(claim.get("task_id", "task-1")),
        "outcome": "MECHANICALLY_VALIDATED",
        "acceptance": claim,
        "plan_id": contracts.new_record_id("dip"),
        "direction_id": contracts.new_record_id("ddr"),
        "changes": [{"path": "src/app.css", "verdict": "GROUNDED"}],
        "validation": {
            "status": "PASSED",
            "checks": [{"check_id": "chk_1", "command": "npm run build", "status": "PASSED"}],
        },
        "context": {},
        "telemetry": {},
        "recorded_at": contracts.utc_now(),
    }
    return [
        item for item in contracts.implementation_run_problems(record)
        if "visual_acceptance" in item or "rendered_check" in item or "rendered" in item
    ]


__all__ = [
    "SEVERITIES",
    "SEVERITY_RANK",
    "DIMENSIONS",
    "EVIDENCE_STATES",
    "CAPTURE_METHODS",
    "MATERIALITY_CATEGORIES",
    "CAPTURE_PLAN_STATUSES",
    "CAPTURE_TARGET_BASES",
    "CAPTURE_TARGET_KINDS",
    "CAPTURE_BUDGET_DEFAULTS",
    "RENDER_OUTCOMES",
    "COVERAGE_STATES",
    "FINDING_BASES",
    "ARTIFACT_VALIDATION_STATES",
    "REPAIR_FINDING_STATES",
    "VISUAL_ACCEPTANCE_NOT_CLAIMED",
    "VISUAL_ACCEPTANCE_BY_RENDER",
    "severity_rank",
    "blocking_findings",
    "observation_findings",
    "actionable_findings",
    "counts_by",
    "validate_visual_acceptance",
]
