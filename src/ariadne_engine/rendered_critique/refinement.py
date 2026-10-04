"""Bounded rendered refinement (AR-222).

Critique does not mutate source. It produces findings; findings that survive triage
become a :class:`RefinementPlan`; the plan goes to an ordinary implementation worker;
the result is mechanically validated, re-rendered, and independently re-reviewed.

Three rules carry the weight.

**A repair moves toward a direction that was already approved.** §32 is the sharp
edge: if the honest conclusion from looking at a render is "this needs a different
visual language", that is not a repair. It is :data:`DIRECTION_REVISION_REQUIRED`,
and it goes back to design direction and a human. Letting the repair phase redesign the
product would make the whole approval chain decorative -- the direction would stop
being a constraint and become a suggestion.

**The worker that made the change cannot close its own finding.** §40. Resolution
requires fresh rendered evidence *and* a critique from a different execution. The
worker may mark a finding ``REPAIRED_CANDIDATE``, which is a claim about its own work;
only an independent re-review moves it to ``VERIFIED_RESOLVED``. That distinction is
recorded rather than assumed, and a mutation test holds it in place.

**Re-review looks at the whole affected set.** §41. A repair that fixes a focus ring
and breaks the panel ratio has not succeeded, and a reviewer shown only the crop around
the ring would never notice. So the re-review receives every materially affected
capture, and its output is three lists: resolved, persistent, and new.

The repair budget is :data:`ariadne_engine.contracts.DEFAULT_CAPTURE_BUDGET`'s
``repair_capture_cycles``, which is 2 -- deliberately the same number as AR-221's
mechanical repair budget and this module's own ``MAX_REPAIR_ATTEMPTS``, so one stage
cannot claim a fresh allowance at each layer.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Mapping, Sequence

from .. import contracts, design as design_module, review as review_module
from ..contracts import ContractError
from . import critique as critique_module
from . import evidence as evidence_module
from . import safety

MAX_REPAIR_ATTEMPTS = 2
"""Two repair attempts maximum (§34). Not a preference: an unbounded repair loop on a
visual judgement converges by talking itself into whatever it was already doing."""

FORBIDDEN_SCOPE_TOKENS = (
    "package.json", "tsconfig.json", "node_modules", "vite.config", "tailwind.config",
    "next.config", ".ariadne", "docs/", "references/",
)
"""Files a design repair must not touch. Changing the toolchain, the build config or
the reference corpus during a *visual* repair would change what can be expressed,
which is a design-system decision and not a bug fix."""


def repairable(state: dict, *, critique_id: str, finding_ids: Sequence[str]) -> tuple[list[dict], list[dict]]:
    """Split findings into those a bounded repair may address and those it may not.

    Separated rather than filtered so the caller can report *why* something was held
    back. A finding held for direction revision is the most consequential output this
    module produces, and it must not disappear silently into a "skipped" list.
    """
    record = critique_module.by_id(state, critique_id)
    if record is None:
        raise ContractError(f"no rendered critique matches {critique_id!r}")
    accepted: list[dict] = []
    escalations: list[dict] = []
    wanted = [str(item) for item in finding_ids]
    if not wanted:
        raise ContractError("a refinement plan must name the findings it addresses")
    for finding_id in wanted:
        row = critique_module.finding(state, finding_id)
        if row is None:
            raise ContractError(f"the critique {critique_id} records no finding {finding_id!r}")
        owner = next(
            (item for item in (record.get("findings") or []) if str(item.get("finding_id")) == finding_id),
            None,
        )
        if owner is None:
            raise ContractError(f"finding {finding_id} does not belong to critique {critique_id!r}")
        if str(row.get("state", "OPEN")) in ("VERIFIED_RESOLVED", "ESCALATED", "WAIVED_BY_HUMAN"):
            raise ContractError(f"finding {finding_id} is {row.get('state')} and cannot be repaired again")
        if str(row.get("severity")) == "note":
            escalations.append({
                "finding_id": finding_id, "reason": "OBSERVATION",
                "detail": "this is an observation, not a defect; repairing it would be unrequested redesign",
            })
            continue
        if str(row.get("requires_direction_revision")) in ("True", True):
            escalations.append({
                "finding_id": finding_id, "reason": "DIRECTION_REVISION_REQUIRED",
                "detail": str(row.get("direction_revision_reason", "satisfying this would require a new visual language")),
            })
            continue
        if str(row.get("repairability", "REPAIRABLE")) not in ("REPAIRABLE",):
            escalations.append({
                "finding_id": finding_id, "reason": str(row.get("repairability")),
                "detail": str(row.get("repairability_reason", "this finding is not safely repairable within the approved direction")),
            })
            continue
        accepted.append(dict(row))
    if not accepted:
        raise ContractError(
            "no finding in this set is repairable within the approved direction"
            + (": " + "; ".join(f"{item['finding_id']} {item['reason']}" for item in escalations) if escalations else "")
        )
    return accepted, escalations


def plan(
    state: dict,
    *,
    critique_id: str,
    finding_ids: Sequence[str],
    allowed_scope: Sequence[str],
    required_outcomes: Sequence[str],
    validation: Sequence[str],
    authorising_principles: Sequence[Mapping],
    forbidden_scope: Sequence[str] = (),
    attempt: int = 1,
    run_before: str = "",
) -> dict:
    """Compile accepted findings into one bounded, authorised plan.

    The plan is the artefact that keeps refinement from becoming redesign. It must name
    the approved principles it serves, what it may change, what it may not, and the
    validation that must pass before anything is re-rendered. A plan missing any of
    those is refused rather than defaulted, because a default would be a guess about
    the design, which is the thing this whole phase is not allowed to do.
    """
    record = critique_module.by_id(state, critique_id)
    if record is None:
        raise ContractError(f"no rendered critique matches {critique_id!r}")
    accepted, escalations = repairable(state, critique_id=critique_id, finding_ids=finding_ids)
    budget = repair_budget(state, critique_id=critique_id)
    if int(attempt) > budget["limit"]:
        raise ContractError(
            f"the bounded repair budget is {budget['limit']} attempts and {budget['attempts']} have been "
            f"used (REPAIR_LIMIT_EXHAUSTED): {budget['reason']}; a human must decide whether to continue"
        )
    if int(attempt) <= budget["attempts"]:
        raise ContractError(
            f"repair attempt {attempt} was already recorded for this critique; an attempt number is "
            "monotone so a cycle cannot be re-run under a lower number"
        )
    scope = [str(item).strip() for item in (allowed_scope or []) if str(item).strip()]
    if not scope:
        raise ContractError("a refinement plan must name the files it may change")
    violations = [
        item for item in scope
        if any(token in item for token in FORBIDDEN_SCOPE_TOKENS)
    ]
    if violations:
        raise ContractError(
            "a design refinement may not change build configuration, dependency manifests or the "
            "reference corpus; that is a design-system decision, not a visual repair: "
            + ", ".join(sorted(violations))
        )
    principles = [dict(row) for row in authorising_principles or ()]
    if not principles:
        raise ContractError(
            "a refinement plan must name the approved principles it serves; a change with no "
            "authorising principle is a redesign in a plan's clothing"
        )
    for entry in principles:
        entry.setdefault("direction_id", str(record.get("direction_id", "")))
        if str(entry.get("direction_id", "")) != str(record.get("direction_id", "")):
            raise ContractError(
                "an authorising principle belongs to a different direction than the critique under repair"
            )
        if not str(entry.get("outcome", "")).strip():
            entry["outcome"] = (
                f"the render expresses {str(entry.get('statement', '')).strip() or 'this principle'} "
                "more faithfully after the change"
            )
    outcomes = [str(item).strip() for item in (required_outcomes or []) if str(item).strip()]
    if not outcomes:
        raise ContractError("a refinement plan must state what the change is required to achieve")
    checks = [str(item).strip() for item in (validation or []) if str(item).strip()]
    if not checks:
        raise ContractError(
            "a refinement plan must declare mechanical validation; a visually promising change with a "
            "broken build is not progress"
        )
    introduces = False
    reason = ""
    for row in accepted:
        if str(row.get("introduces_new_visual_language")) in ("True", True):
            introduces = True
            reason = str(row.get("direction_revision_reason", ""))
    record_value = {
        "schema_version": contracts.SCHEMA_DESIGN,
        "refinement_plan_id": contracts.new_record_id("rfp"),
        "run_id": str(state.get("run_id", "")),
        "task_id": str(record.get("task_id", "")),
        "critique_id": str(critique_id),
        "evidence_set_id": str(record.get("evidence_set_id", "")),
        "render_source_digest_before": str(record.get("render_source_digest", "")),
        "direction_id": str(record.get("direction_id", "")),
        "finding_ids": [str(row.get("finding_id", "")) for row in accepted],
        "escalated_findings": escalations,
        "allowed_scope": scope,
        "forbidden_scope": [str(item) for item in (forbidden_scope or ())] + list(FORBIDDEN_SCOPE_TOKENS),
        "authorising_principles": principles,
        "required_outcomes": outcomes,
        "constraints": [
            "the approved direction is fixed; a change that needs a new direction is not a repair",
            "reference comparison remains principle-based; pixel similarity is not a target",
            "project identity outranks every reference",
            "accessibility is a floor, not a preference",
        ],
        "validation": checks,
        "context": {
            "captures_transported": sorted({
                capture for row in accepted for capture in (row.get("capture_ids") or [])
            }),
            "principles_transported": len(principles),
            "references_transported": 0,
            "policy": (
                "only the captures that support the selected findings travel with the plan; every other "
                "capture in the set stays in the evidence set for the reviewer"
            ),
        },
        "attempt": int(attempt),
        "status": "PROPOSED",
        "introduces_new_direction": introduces,
        "escalation_reason": reason,
        "ran_from": str(run_before),
        "recorded_at": contracts.utc_now(),
        "provenance": {"created_by": "engine", "policy_version": contracts.POLICY_VERSION},
    }
    problems = contracts.refinement_plan_problems(record_value)
    if problems:
        raise ContractError("refinement plan is malformed: " + "; ".join(problems))
    contracts.require_design_capacity(state, "refinement_plans")
    state.setdefault("refinement_plans", []).append(record_value)
    for row in accepted:
        critique_module.finding(state, str(row.get("finding_id", "")))["state"] = "ACCEPTED_FOR_REPAIR"
    return record_value


def repair_budget(state: dict, *, critique_id: str) -> dict:
    """How many repair attempts remain, and why."""
    attempts = [
        row for row in plans(state) if str(row.get("critique_id", "")) == str(critique_id)
        and str(row.get("status", "")) in ("PROPOSED", "IN_PROGRESS", "VALIDATED", "RE_RENDERED")
    ]
    remaining = max(0, MAX_REPAIR_ATTEMPTS - len(attempts))
    return {
        "limit": MAX_REPAIR_ATTEMPTS,
        "attempts": len(attempts),
        "remaining": remaining,
        "reason": (
            "two bounded attempts are the whole allowance; a third means the direction is probably "
            "wrong rather than the implementation"
        ),
    }


def plans(state: dict) -> list[dict]:
    rows = state.get("refinement_plans")
    if not isinstance(rows, list):
        return []
    return [item for item in rows if isinstance(item, Mapping)]


def by_id(state: dict, refinement_plan_id: str) -> dict | None:
    """The stored plan record, not a copy.

    This returns the live object on purpose. Every mutation in this module -- marking a
    plan started, recording its changed files, closing it against a re-review -- writes
    through this handle, and a defensive ``dict(row)`` here would make each of those
    writes silently vanish while still returning a plausible-looking value to the
    caller. ``ariadne_engine.critique.refinement`` sets the precedent: a lookup used for
    mutation hands back the record itself.
    """
    for row in plans(state):
        if str(row.get("refinement_plan_id", "")) == str(refinement_plan_id):
            return row
    return None


def packet(plan_record: Mapping, *, captures: Sequence[Mapping], changed_files: Sequence[str] = ()) -> dict:
    """What the repair worker receives.

    Minimal by construction (§36): the findings being repaired, the principles that
    authorise the change, the files it may touch, the commands that must pass, and the
    captures that support those specific findings. Nothing else -- not the full evidence
    set, not the reference corpus, not the worker's previous rationale. The context
    budget is measured here so "we kept it minimal" is a number rather than an intention.
    """
    rows = [
        row for row in captures
        if str(row.get("capture_id", "")) in set(plan_record.get("context", {}).get("captures_transported", []))
    ]
    rendered = {
        "plan_id": str(plan_record.get("refinement_plan_id", "")),
        "attempt": int(plan_record.get("attempt", 1)),
        "accepted_findings": [
            {
                "finding_id": finding_id,
                "observation": str(
                    next(
                        (row.get("observation", "") for row in (plan_record.get("findings") or [])
                         if str(row.get("finding_id")) == finding_id),
                        "",
                    )
                ),
            }
            for finding_id in (plan_record.get("finding_ids") or [])
        ],
        "authorising_principles": [dict(row) for row in (plan_record.get("authorising_principles") or [])],
        "required_outcomes": list(plan_record.get("required_outcomes") or []),
        "allowed_scope": list(plan_record.get("allowed_scope") or []),
        "forbidden_scope": list(plan_record.get("forbidden_scope") or []),
        "constraints": list(plan_record.get("constraints") or []),
        "validation": [{"command": str(item), "required": True} for item in (plan_record.get("validation") or [])],
        "target_files": [str(item) for item in changed_files],
        "captures": [
            safety.as_data(
                f"capture_id={row.get('capture_id')} route={row.get('route')} "
                f"state={row.get('state')} viewport={(row.get('viewport') or {}).get('width')}px "
                f"artifact={row.get('artifact_path')}",
                origin=f"capture:{row.get('capture_id')}",
            )
            for row in rows
        ],
        "stop_conditions": [
            "STOP if satisfying the outcome would require a change outside allowed_scope.",
            "STOP if satisfying the outcome would need a different visual language; report "
            "DIRECTION_REVISION_REQUIRED instead of proceeding.",
            "STOP if any validation command fails; a visually promising change with a broken build "
            "is not progress.",
        ],
        "escalation_conditions": [
            "ESCALATE if two bounded attempts have been used.",
            "ESCALATE if a finding is not repairable within the approved direction.",
        ],
    }
    import json as _json

    payload = _json.dumps(rendered, default=str)
    rendered["context"] = {
        "captures_transported": len(rows),
        "capture_bytes_available": sum(int(row.get("bytes", 0) or 0) for row in rows),
        "packet_bytes": len(payload.encode("utf-8")),
        "captures_available_but_not_transported": max(0, len(captures) - len(rows)),
    }
    return rendered


def mark_started(state: dict, refinement_plan_id: str, *, execution: str) -> dict:
    """The repair worker begins. Recorded, so 'who changed it' is not a later guess."""
    record = by_id(state, refinement_plan_id)
    if record is None:
        raise ContractError(f"no refinement plan matches {refinement_plan_id!r}")
    if str(record.get("status")) != "PROPOSED":
        raise ContractError(f"refinement plan {refinement_plan_id} is {record.get('status')}; it is not open")
    reviewer = review_module.independence_problems(
        state, f"repair-worker@{state.get('run_id', 'run')}",
        reviewer_execution=execution,
        implementing_execution=str(record.get("implementing_execution", "")) or execution,
    )
    record["status"] = "IN_PROGRESS"
    record["repair_execution"] = str(execution)
    record["started_at"] = contracts.utc_now()
    record["notes"] = ""
    return record


def record_change(
    state: dict,
    refinement_plan_id: str,
    *,
    execution: str,
    changed_files: Sequence[str],
    notes: str = "",
) -> dict:
    """Record what the worker changed, and refuse anything out of scope.

    Scope is checked here rather than trusted, because a repair worker that quietly
    edits a fourth file has done something no reviewer will notice until it is much
    more expensive to undo.
    """
    record = by_id(state, refinement_plan_id)
    if record is None:
        raise ContractError(f"no refinement plan matches {refinement_plan_id!r}")
    if str(record.get("status")) not in ("PROPOSED", "IN_PROGRESS"):
        raise ContractError(f"refinement plan {refinement_plan_id} is {record.get('status')}")
    changed = [str(item).strip() for item in changed_files if str(item).strip()]
    if not changed:
        raise ContractError(
            "a repair that changed no file cannot resolve a rendered finding; record the abandonment "
            "instead so the budget is not silently consumed"
        )
    allowed = [str(item) for item in (record.get("allowed_scope") or [])]
    outside = [item for item in changed if not any(contracts.path_matches(item, entry) for entry in allowed)]
    if outside:
        raise ContractError(
            "the repair changed files outside its allowed scope: " + ", ".join(sorted(outside))
            + "; a bounded repair that expands its own scope is not a bounded repair"
        )
    record["status"] = "VALIDATED"
    record["changed_files"] = changed
    record["change_notes"] = safety.critique_text_is_data(str(notes)) if notes else ""
    record["validated_at"] = contracts.utc_now()
    record["repair_execution"] = str(execution)
    for finding_id in (record.get("finding_ids") or []):
        row = critique_module.finding(state, str(finding_id))
        if row is not None:
            row["state"] = "REPAIRED_CANDIDATE"
            row["repair_plan_id"] = str(refinement_plan_id)
    return record


def record_validation(
    state: dict, refinement_plan_id: str, *, checks: Sequence[Mapping], duration_seconds: float = 0.0
) -> dict:
    """§37: mechanical validation must pass before anything is re-rendered.

    A repair that fails typecheck does not get a re-render. Recording it as failed and
    stopping is the point -- otherwise a broken build gets photographed and a reviewer
    critiques a compile error's layout.
    """
    record = by_id(state, refinement_plan_id)
    if record is None:
        raise ContractError(f"no refinement plan matches {refinement_plan_id!r}")
    rows = [dict(row) for row in checks or ()]
    declared = [str(item) for item in (record.get("validation") or [])]
    ran = {str(row.get("command", "")) for row in rows}
    missing = [item for item in declared if item not in ran]
    failed = [str(row.get("command", "")) for row in rows if str(row.get("status", "")) != "PASSED"]
    record["validation_results"] = rows
    record["validation_seconds"] = round(float(duration_seconds), 3)
    record["validation_missing"] = missing
    record["validation_failed"] = failed
    if missing or failed:
        record["status"] = "REJECTED"
        record["validation_note"] = (
            "mechanical validation did not pass, so this attempt produced no re-render"
            + (f"; missing: {', '.join(missing)}" if missing else "")
            + (f"; failed: {', '.join(failed)}" if failed else "")
        )
    return record


def mark_rerendered(state: dict, refinement_plan_id: str, *, evidence_set_id: str,
                    render_source_digest: str) -> dict:
    """The fresh capture exists. The finding is *not* resolved yet."""
    record = by_id(state, refinement_plan_id)
    if record is None:
        raise ContractError(f"no refinement plan matches {refinement_plan_id!r}")
    if str(record.get("status")) != "VALIDATED":
        raise ContractError(
            f"refinement plan {refinement_plan_id} is {record.get('status')}; a re-render requires "
            "mechanically validated changes first"
        )
    manifest = evidence_module.by_id(state, evidence_set_id)
    if manifest is None:
        raise ContractError(f"no rendered evidence set matches {evidence_set_id!r}")
    if str(manifest.get("render_source_digest", "")) != str(render_source_digest):
        raise ContractError(
            "the re-render is bound to a different source digest than the repair produced; a re-render "
            "of unchanged source is not evidence that anything was repaired"
        )
    record["status"] = "RE_RENDERED"
    record["after_evidence_set_id"] = str(evidence_set_id)
    record["render_source_digest_after"] = str(render_source_digest)
    record["rerendered_at"] = contracts.utc_now()
    return record


def resolve(
    state: dict,
    *,
    refinement_plan_id: str,
    re_critique_id: str,
    resolved: Sequence[str],
    still_present: Sequence[str] = (),
    new_findings: Sequence[str] = (),
) -> dict:
    """Close the cycle from an *independent* re-review.

    The re-review is the only party that may say ``VERIFIED_RESOLVED``, and this
    function refuses to take that claim from anyone else -- including the worker, and
    including an engine caller passing its own execution id.
    """
    plan_record = by_id(state, refinement_plan_id)
    if plan_record is None:
        raise ContractError(f"no refinement plan matches {refinement_plan_id!r}")
    if str(plan_record.get("status")) != "RE_RENDERED":
        raise ContractError(
            f"refinement plan {refinement_plan_id} is {plan_record.get('status')}; a cycle closes only "
            "after fresh rendered evidence exists"
        )
    re_critique = critique_module.by_id(state, re_critique_id)
    if re_critique is None:
        raise ContractError(f"no rendered critique matches {re_critique_id!r}")
    if str(re_critique.get("render_source_digest", "")) != str(plan_record.get("render_source_digest_after", "")):
        raise ContractError(
            "the re-review judged a different source digest than the repair produced; closing a finding "
            "against stale renders would make the repair unverifiable"
        )
    if str(re_critique.get("implementing_execution", "")) != str(plan_record.get("repair_execution", "")):
        raise ContractError(
            "the re-review must judge the render produced by the recorded repair execution; a re-review "
            "of an unrelated revision cannot close this finding"
        )
    if str(re_critique.get("reviewer_execution", "")) == str(plan_record.get("repair_execution", "")):
        raise ContractError(
            "the re-reviewing execution is the repair execution; the worker that made the change does "
            "not get to certify that its own change worked"
        )
    if str(re_critique.get("critique_id")) == str(plan_record.get("critique_id")):
        raise ContractError("a re-review must be a fresh critique, not the one that raised the finding")
    resolved_rows = [str(item) for item in resolved]
    if not resolved_rows and not list(still_present) and not list(new_findings):
        raise ContractError(
            "a closing re-review must report which findings resolved, which persisted, and which are new; "
            "'no change' is an answer only when it is said explicitly"
        )
    target = set(str(item) for item in (plan_record.get("finding_ids") or []))
    unknown = [item for item in resolved_rows + [str(x) for x in still_present] if item not in target]
    if unknown:
        raise ContractError(
            "the re-review resolves findings this plan did not address: " + ", ".join(sorted(unknown))
        )
    # Resolution must be attributable, not merely asserted. A finding is only shown to
    # be fixed if (a) the independent re-review no longer reports it and (b) the re-review
    # actually looked at the captures that evidenced it. Without (b), "resolved" would
    # mean "nobody mentioned it", which is indistinguishable from nobody looking.
    re_findings = {str(row.get("finding_id", "")) for row in (re_critique.get("findings") or [])}
    inspected: set[str] = set()
    for entry in (re_critique.get("coverage") or {}).values():
        if isinstance(entry, Mapping):
            inspected |= {str(item) for item in (entry.get("capture_ids") or [])}
    for row in (re_critique.get("findings") or []):
        if isinstance(row, Mapping):
            inspected |= {str(item) for item in (row.get("capture_ids") or [])}
    for finding_id in resolved_rows:
        if finding_id in re_findings:
            raise ContractError(
                f"the re-review claims finding {finding_id} resolved but still reports it; a finding "
                "cannot be both repaired and present"
            )
        origin = critique_module.finding(state, finding_id) or {}
        original_captures = {str(item) for item in (origin.get("capture_ids") or [])}
        uninspected = sorted(original_captures - inspected)
        if original_captures and uninspected:
            raise ContractError(
                f"the re-review did not inspect the captures that evidenced finding {finding_id} "
                f"({', '.join(uninspected)}); absence from an unreviewed capture is not resolution"
            )
    for finding_id in resolved_rows:
        row = critique_module.finding(state, finding_id)
        if row is not None:
            row["state"] = "VERIFIED_RESOLVED"
            row["resolved_by_critique"] = str(re_critique_id)
    for finding_id in [str(item) for item in still_present]:
        row = critique_module.finding(state, finding_id)
        if row is not None:
            row["state"] = "STILL_PRESENT"
    plan_record["status"] = "RE_RENDERED"
    plan_record["closed_by_critique"] = str(re_critique_id)
    plan_record["resolved_findings"] = resolved_rows
    plan_record["persistent_findings"] = [str(item) for item in still_present]
    plan_record["new_findings"] = [str(item) for item in new_findings]
    plan_record["resolution"] = {
        "resolved": len(resolved_rows),
        "persistent": len(list(still_present)),
        "new": len(list(new_findings)),
        "note": (
            "a repair can fix one finding and introduce another, so a closing re-review reports all "
            "three numbers rather than a verdict"
        ),
    }
    plan_record["closed_at"] = contracts.utc_now()
    return plan_record


def escalate(state: dict, refinement_plan_id: str, *, reason: str, kind: str = "DIRECTION_REVISION_REQUIRED") -> dict:
    """Hand the question back to design direction and a human.

    This is a success path, not a failure path. The alternative -- letting the repair
    phase quietly adopt a new visual language because the render looked wrong -- would
    mean the approved direction was never actually a constraint.
    """
    record = by_id(state, refinement_plan_id)
    if record is None:
        raise ContractError(f"no refinement plan matches {refinement_plan_id!r}")
    if not str(reason).strip():
        raise ContractError("an escalation must state what question a human has to answer")
    record["status"] = "ESCALATED"
    record["escalation"] = {
        "kind": str(kind),
        "reason": str(reason),
        "escalated_at": contracts.utc_now(),
        "returned_to": "design-direction-and-human-approval",
    }
    for finding_id in (record.get("finding_ids") or []):
        row = critique_module.finding(state, str(finding_id))
        if row is not None:
            row["state"] = "ESCALATED"
    return record


def summary(state: dict, *, critique_id: str = "") -> dict:
    """Final rendered state: resolved, persistent, new, and what was escalated."""
    rows = [row for row in plans(state) if not critique_id or str(row.get("critique_id")) == critique_id]
    findings = critique_module.all_findings(state)
    resolved = [row for row in findings if str(row.get("state")) == "VERIFIED_RESOLVED"]
    persistent = [row for row in findings if str(row.get("state")) in ("STILL_PRESENT", "OPEN")]
    escalated = [row for row in findings if str(row.get("state")) == "ESCALATED"]
    waived = [row for row in findings if str(row.get("state")) == "WAIVED_BY_HUMAN"]
    latest = critique_module.critiques(state)
    return {
        "attempts": len(rows),
        "budget": {"limit": MAX_REPAIR_ATTEMPTS, "used": len(rows), "remaining": max(0, MAX_REPAIR_ATTEMPTS - len(rows))},
        "resolved_findings": [str(row.get("finding_id")) for row in resolved],
        "persistent_findings": [str(row.get("finding_id")) for row in persistent],
        "escalated_findings": [str(row.get("finding_id")) for row in escalated],
        "waived_findings": [str(row.get("finding_id")) for row in waived],
        "escalations": [dict(row.get("escalation")) for row in rows if row.get("escalation")],
        "final_status": str(latest[-1].get("overall_status")) if latest else "RENDER_VALIDATION_BLOCKED",
        "final_critique_id": str(latest[-1].get("critique_id")) if latest else "",
        "no_worker_self_closure": True,
    }


def describe(record: Mapping) -> str:
    return (
        f"{record.get('refinement_plan_id')} attempt {record.get('attempt')} "
        f"{record.get('status')} for {len(record.get('finding_ids') or [])} finding(s)"
    )


__all__ = [
    "MAX_REPAIR_ATTEMPTS",
    "FORBIDDEN_SCOPE_TOKENS",
    "repairable",
    "plan",
    "repair_budget",
    "plans",
    "by_id",
    "packet",
    "mark_started",
    "record_change",
    "record_validation",
    "mark_rerendered",
    "resolve",
    "escalate",
    "summary",
    "describe",
]
