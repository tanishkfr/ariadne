"""Measured skill usefulness, and proposals that a human must review.

Ariadne already selects native skills deterministically and records a method
ledger: a selected method may be ``selected``, worker-reported ``invoked``,
engine-observed ``completed``, or ``unmet``. 2.4B adds the two things that
ledger alone cannot answer:

* **effectiveness by skill and intent family**, with correct attribution. A task
  that succeeded while carrying a skill does not prove the skill helped. This
  module therefore reports association, never causation, and keeps ``selected``,
  ``invoked`` and ``completed`` separate.
* **safe improvement proposals**. A recurring unmet mandatory method, an
  optional method that is never used, or a repeated validation failure without a
  regression method produces a recorded proposal with evidence, risk and a
  validation procedure. It never edits the trusted registry. A proposal becomes
  a change only after a human authorizes it and somebody reviews the actual
  change; there is no automatic apply path here.
"""

from __future__ import annotations

from typing import Mapping, Sequence

from . import contracts
from .contracts import ContractError
from .serialization import canonical_json, digest_text

SCHEMA = "ar-24b-skill-intelligence-1"
POLICY = "skill-intelligence-1"
COLLECTION = "skill_proposals"
MAX_PROPOSALS = 500
PROPOSAL_STATUSES = ("PROPOSED", "AUTHORIZED", "DEFERRED", "REJECTED")


def _plans(state: Mapping) -> tuple[dict, dict]:
    by_task: dict[str, dict] = {}
    by_id: dict[str, dict] = {}
    for record in state.get("task_plans") or ():
        if not isinstance(record, Mapping):
            continue
        row = dict(record)
        if str(row.get("task_id", "")).strip():
            by_task[str(row["task_id"])] = row
        if str(row.get("plan_id", "")).strip():
            by_id[str(row["plan_id"])] = row
    return by_task, by_id


def _bucket() -> dict:
    return {
        "selected": 0,
        "invoked": 0,
        "completed": 0,
        "unmet": 0,
        "not_reported": 0,
        "mandatory_selected": 0,
        "tasks": 0,
        "validated_tasks": 0,
        "accepted_tasks": 0,
        "review_failed_tasks": 0,
        "validation_failures": 0,
        "repairs": 0,
        "families": {},
        "reasons": {},
        "documents_bytes": "UNKNOWN",
        "association": "tasks accepted with this skill completed; association, not causation",
    }


def effectiveness(state: Mapping) -> dict:
    """Per-skill selection, invocation, observation and associated outcomes."""
    plans, plans_by_id = _plans(state)
    per_skill: dict[str, dict] = {}
    tasks: list[dict] = []
    for task in state.get("tasks") or ():
        if not isinstance(task, Mapping):
            continue
        task = dict(task)
        task_id = str(task.get("task_id", ""))
        plan = plans.get(task_id) or plans_by_id.get(str(task.get("plan_id", ""))) or {}
        selection = dict(plan.get("skills") or {})
        selected_rows = [
            dict(item) for item in selection.get("selected") or () if isinstance(item, Mapping)
        ]
        # A task record is the durable authority for methods that were actually
        # selected; the plan explains why. Prefer the record's ledger states.
        ledger = {
            str(item.get("id", "")): dict(item)
            for item in task.get("skills") or ()
            if isinstance(item, Mapping)
        }
        reasons = {
            str(item.get("id", "")): str(item.get("reason", ""))
            for item in selected_rows
        }
        versions = {
            str(item.get("id", "")): str(item.get("version", ""))
            for item in selected_rows
        }
        attempts = [item for item in task.get("attempts") or () if isinstance(item, Mapping)]
        validation_failures = sum(
            1 for item in attempts
            if str((item.get("validation") or {}).get("status", "")) in ("failed", "blocked")
        )
        validated = any(
            str((item.get("validation") or {}).get("status", "")) == "passed"
            for item in attempts
        )
        review = dict(task.get("review") or {})
        accepted = str((task.get("acceptance") or {}).get("outcome", "")) == "accepted"
        family = str(task.get("intent", "") or "unknown")
        selected_ids: list[str] = []
        for entry in selected_rows or [
            {"id": str(item.get("id", ""))} for item in task.get("skills") or () if isinstance(item, Mapping)
        ]:
            skill_id = str(entry.get("id", ""))
            if not skill_id:
                continue
            selected_ids.append(skill_id)
            bucket = per_skill.setdefault(skill_id, _bucket())
            bucket["selected"] += 1
            bucket["mandatory_selected"] += 1 if entry.get("mandatory") else 0
            bucket["tasks"] += 1
            bucket["families"][family] = bucket["families"].get(family, 0) + 1
            reason = str(entry.get("reason", "") or reasons.get(skill_id, ""))
            if reason:
                bucket["reasons"][reason] = bucket["reasons"].get(reason, 0) + 1
            bucket["validated_tasks"] += 1 if validated else 0
            bucket["accepted_tasks"] += 1 if accepted else 0
            bucket["review_failed_tasks"] += 1 if str(review.get("outcome", "")) == "failed" else 0
            bucket["validation_failures"] += validation_failures
            bucket["repairs"] += max(0, len(attempts) - 1)
            ledger_row = ledger.get(skill_id, {})
            ledger_state = str(ledger_row.get("state", "selected"))
            if ledger_state in ("invoked", "completed", "unmet"):
                bucket[ledger_state] += 1
            elif ledger_state == "selected":
                bucket["not_reported"] += 1
        tasks.append({
            "task_id": task_id,
            "intent": family,
            "status": str(task.get("status", "")),
            "accepted": accepted,
            "validated": validated,
            "validation_failures": validation_failures,
            "repairs": max(0, len(attempts) - 1),
            "review_outcome": str(review.get("outcome", "")),
            "selected": selected_ids,
            "selected_versions": {key: versions.get(key, "") for key in selected_ids},
            "ledger": {
                key: str(value.get("state", "selected")) for key, value in sorted(ledger.items())
            },
            "unmet": [key for key, value in ledger.items() if str(value.get("state")) == "unmet"],
            "completed": [key for key, value in ledger.items() if str(value.get("state")) == "completed"],
        })
    tasks.sort(key=lambda item: item["task_id"])
    for bucket in per_skill.values():
        bucket["families"] = dict(sorted(bucket["families"].items()))
        bucket["reasons"] = dict(sorted(bucket["reasons"].items()))
        bucket["association"] = (
            f"{bucket['accepted_tasks']} accepted task(s) also carried this skill; "
            "association is not causation"
        )
    return {
        "schema_version": SCHEMA,
        "policy": POLICY,
        "tasks": tasks,
        "per_skill": dict(sorted(per_skill.items())),
        "totals": {
            "tasks": len(tasks),
            "selected_skills": sum(len(item["selected"]) for item in tasks),
            "tasks_with_no_selected_skill": len([item for item in tasks if not item["selected"]]),
            "skills": len(per_skill),
        },
        "unknowns": [
            "whether an invoked method caused the validated outcome",
            "provider tokens attributable to a skill document",
            "time spent reading skill instructions",
        ],
        "note": (
            "selected, invoked and completed are different states. An accepted task that carried a "
            "skill is an association; it does not prove usefulness, and no skill is removed by "
            "this report."
        ),
        "recorded_at": contracts.utc_now(),
    }


def _proposal(
    *,
    skill_id: str,
    version: str,
    task_family: str,
    kind: str,
    original_failure: str,
    evidence: Sequence[str],
    suggested_change: str,
    expected_benefit: str,
    risks: Sequence[str],
    validation_procedure: Sequence[str],
) -> dict:
    content = {
        "skill_id": str(skill_id),
        "skill_version": str(version),
        "task_family": str(task_family),
        "kind": str(kind),
        "original_failure": str(original_failure),
        "evidence": [str(item) for item in evidence if str(item).strip()],
        "suggested_change": str(suggested_change),
        "expected_benefit": str(expected_benefit),
        "risks": [str(item) for item in risks],
        "validation_procedure": [str(item) for item in validation_procedure],
    }
    return {
        "schema_version": SCHEMA,
        "proposal_id": "skp_" + digest_text(canonical_json(content))[:16],
        **content,
        "status": "PROPOSED",
        "authorization": {},
        "authority": "none; this proposal cannot change the trusted registry",
        "recorded_at": contracts.utc_now(),
    }


def candidate_proposals(state: Mapping, *, min_recurrence: int = 2) -> list[dict]:
    """Deterministic proposals from recurring measured conditions."""
    view = effectiveness(state)
    proposals: list[dict] = []
    for skill_id, bucket in view["per_skill"].items():
        if bucket["unmet"] >= max(2, min_recurrence):
            proposals.append(_proposal(
                skill_id=skill_id,
                version="",
                task_family=", ".join(bucket["families"]) or "unknown",
                kind="unmet-mandatory-method",
                original_failure=(
                    f"{skill_id} was mandatory but the return did not report usable evidence "
                    f"in {bucket['unmet']} task(s)"
                ),
                evidence=[f"skill {skill_id}: {bucket['unmet']} unmet, {bucket['selected']} selected"],
                suggested_change=(
                    "Strengthen the method's reporting requirement in the task contract or add a "
                    "deterministic evidence check before acceptance."
                ),
                expected_benefit="Fewer mandatory methods left unmet without silently dropping the method.",
                risks=[
                    "extra contract text adds context cost",
                    "a stricter check could reject an honest return that used a different valid method",
                ],
                validation_procedure=[
                    "Re-run a task whose return previously omitted the method and confirm the new check refuses it.",
                    "Re-run the matching accepted tasks and confirm no passing task is newly refused.",
                ],
            ))
        if bucket["selected"] >= max(3, min_recurrence) and bucket["invoked"] == 0 and bucket["completed"] == 0 and not bucket["mandatory_selected"]:
            proposals.append(_proposal(
                skill_id=skill_id,
                version="",
                task_family=", ".join(bucket["families"]) or "unknown",
                kind="never-invoked-optional-method",
                original_failure=(
                    f"{skill_id} was selected in {bucket['selected']} task(s) but reported as neither "
                    "invoked nor completed"
                ),
                evidence=[f"skill {skill_id}: {bucket['selected']} selected, 0 invoked, 0 completed"],
                suggested_change=(
                    "Review whether this optional skill should remain in the default selection for this "
                    "task family. It is not removed automatically."
                ),
                expected_benefit="Less optional instruction context without dropping a mandatory method.",
                risks=[
                    "the method may have been useful without being reported",
                    "a smaller sample can misattribute a reporting gap to the skill",
                ],
                validation_procedure=[
                    "Compare task outcomes before and after the selection change on the same workload.",
                    "Confirm every mandatory method for the family remains selected.",
                ],
            ))
    # A write task whose validation failed repeatedly and which did not select
    # the regression-testing method is a concrete, reviewable signal.
    tasks = view["tasks"]
    write_failures: dict[str, list[str]] = {}
    for task in tasks:
        if task["validation_failures"] < 2:
            continue
        if "behavior-tests" in task["selected"]:
            continue
        family = task["intent"] or "unknown"
        write_failures.setdefault(family, []).append(task["task_id"])
    for family, task_ids in sorted(write_failures.items()):
        proposals.append(_proposal(
            skill_id="behavior-tests",
            version="",
            task_family=family,
            kind="repeated-validation-failure-without-regression-method",
            original_failure=(
                f"{len(task_ids)} {family} task(s) recorded at least two failed validations while "
                "behavior-tests was not selected"
            ),
            evidence=[f"tasks: {', '.join(task_ids[:5])}"],
            suggested_change=(
                "Evaluate whether behavior-tests should be mandatory or default-selected for this "
                "intent family. Review the task contracts before changing the registry."
            ),
            expected_benefit="Earlier executable proof of the intended behaviour.",
            risks=[
                "a read-only task may not be able to run a test",
                "more mandatory work can slow a small task",
            ],
            validation_procedure=[
                "Reproduce one failing task with the proposed selection and confirm the test fails before the fix.",
                "Run the same task with the fix and confirm the test passes without weakening validation.",
            ],
        ))
    return proposals


def proposals(state: Mapping) -> list[dict]:
    values = state.get(COLLECTION) if isinstance(state, Mapping) else None
    if not isinstance(values, list):
        return []
    return [dict(item) for item in values if isinstance(item, Mapping)]


def proposal_problems(record: Mapping) -> list[str]:
    problems: list[str] = []
    if not isinstance(record, Mapping):
        return ["skill proposal is not an object"]
    if str(record.get("schema_version", "")) != SCHEMA:
        problems.append("skill proposal has an unsupported schema version")
    for name in ("proposal_id", "skill_id", "kind", "original_failure", "suggested_change", "expected_benefit"):
        if not str(record.get(name, "")).strip():
            problems.append(f"skill proposal has no {name}")
    if str(record.get("status", "")) not in PROPOSAL_STATUSES:
        problems.append("skill proposal has an unsupported status")
    if not isinstance(record.get("validation_procedure"), list):
        problems.append("skill proposal has no validation procedure")
    if str(record.get("authorization", {}).get("scope", "none")) not in ("none", "proposal-only"):
        problems.append("a skill proposal authorization may only cover the proposal, never the registry")
    return problems


def record_proposals(state: dict, rows: Sequence[Mapping]) -> list[dict]:
    """Store proposed improvements, deduplicated by their content digest."""
    written: list[dict] = []
    existing = {str(item.get("proposal_id", "")) for item in proposals(state)}
    for raw in rows or ():
        value = dict(raw)
        problems_list = proposal_problems(value)
        if problems_list:
            raise ContractError("skill proposal is malformed: " + "; ".join(problems_list))
        if str(value.get("proposal_id", "")) in existing:
            continue
        contracts.require_collection_capacity(state, COLLECTION)
        state.setdefault(COLLECTION, []).append(value)
        existing.add(str(value["proposal_id"]))
        written.append(value)
    return written


def authorize(state: dict, proposal_id: str, *, identity: str, reason: str = "") -> dict:
    """Record a human's authorization to *implement* a proposal, nothing more."""
    if not str(identity or "").strip():
        raise ContractError("a skill-proposal authorization needs the human identity that made it")
    for row in state.setdefault(COLLECTION, []):
        if not isinstance(row, dict) or str(row.get("proposal_id", "")) != str(proposal_id):
            continue
        row["status"] = "AUTHORIZED"
        row["authorization"] = {
            "identity": str(identity).strip(),
            "reason": str(reason),
            "scope": "proposal-only",
            "authority": "does not modify the trusted skill registry; a reviewed change is still required",
            "recorded_at": contracts.utc_now(),
        }
        return row
    raise ContractError(f"no skill proposal matches {proposal_id!r}")


def apply_to_registry(*_args, **_kwargs) -> dict:
    """Refuse the automatic apply path by construction.

    A proposal may inform a reviewed change to a skill body. It may not rewrite
    trusted instructions, grant permissions, widen a scope or disable
    verification, and no caller in this runtime invokes a registry mutation from
    a proposal.
    """
    raise ContractError(
        "a skill proposal cannot modify the trusted registry automatically; "
        "authorize the proposal, review an explicit change, and validate it"
    )


def status(state: Mapping) -> dict:
    rows = proposals(state)
    return {
        "schema_version": SCHEMA,
        "policy": POLICY,
        "proposals": rows,
        "counts": {
            "proposed": sum(1 for row in rows if str(row.get("status")) == "PROPOSED"),
            "authorized": sum(1 for row in rows if str(row.get("status")) == "AUTHORIZED"),
        },
        "authority": "none; proposals never change trusted instructions automatically",
    }


def describe(state: Mapping) -> str:
    view = effectiveness(state)
    totals = view["totals"]
    return (
        f"skills: {totals['selected_skills']} selection(s) across {totals['tasks']} task(s); "
        f"{len(proposals(state))} recorded proposal(s); selection is not proof of use"
    )


__all__ = [
    "SCHEMA",
    "POLICY",
    "COLLECTION",
    "MAX_PROPOSALS",
    "PROPOSAL_STATUSES",
    "effectiveness",
    "candidate_proposals",
    "proposals",
    "proposal_problems",
    "record_proposals",
    "authorize",
    "apply_to_registry",
    "status",
    "describe",
]
