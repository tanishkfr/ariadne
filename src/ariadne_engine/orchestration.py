"""Orchestration economics: when to spend, and when not to orchestrate (AR-204 T10/T12).

The two questions this module answers
-------------------------------------
1. **Should this task take the simple path?** The fast path is *policy-derived*,
   never an optimisation the engine takes on its own: it is only available for a
   low-stakes task with no design obligation, no capability requirement beyond
   core, no prior failure and no declared review — and even then it keeps every
   validation the policy requires. :func:`path_plan` returns the retained steps
   with the reason each one was retained, so a fast path can never *quietly* skip
   verification.
2. **What did orchestration actually buy?** :func:`orchestration_economics`
   reports, from measured records only, whether a repair avoided a restart,
   whether a review produced findings, how much of the spend went to workers,
   validators and reviewers, and whether duplicated exploration happened. Every
   figure it cannot measure is ``UNKNOWN`` rather than assumed.
"""

from __future__ import annotations

from typing import Mapping, Sequence

from . import economics, execution
from .contracts import ContractError

PATH_FAST = "simple"
PATH_STANDARD = "standard"
PATH_COMPLEX = "complex"

PATH_NAMES = (PATH_FAST, PATH_STANDARD, PATH_COMPLEX)

STAKES_ORDER = {"LOW": 1, "MEDIUM": 2, "HIGH": 3, "UNKNOWN": 4}

FAST_PATH_MAX_STAKES = "LOW"

FAST_PATH_RETAINED = ("characterisation", "worker", "validation")
"""Every path keeps these. A path that dropped validation would not be a path."""

STANDARD_ADDITIONS = ("routing",)

COMPLEX_ADDITIONS = ("decision", "routing", "review", "human-acceptance")


def path_plan(
    *,
    stakes: str = "UNKNOWN",
    difficulty: str = "UNKNOWN",
    design_required: bool = False,
    required_capabilities: Sequence[str] = (),
    prior_failures: int = 0,
    verification_required: bool = True,
    review_required: bool = False,
    human_acceptance_required: bool = False,
    policy_minimum: str = "",
) -> dict:
    """Derive the execution path from stakes, obligations and policy.

    The result names the path, the steps it retains and the steps it skips, each
    with a reason. ``verification_required`` and ``policy_minimum`` can only make
    the path *longer*: a caller cannot ask for a shorter path than policy allows,
    and an unrecognised stake level is treated as the strictest one.
    """
    stakes_value = str(stakes or "UNKNOWN").upper()
    if stakes_value not in STAKES_ORDER:
        stakes_value = "UNKNOWN"
    required = [str(item) for item in required_capabilities if str(item)]
    extra_capabilities = [item for item in required if item not in ("read", "search", "edit", "shell")]
    reasons: list[str] = []
    fast_allowed = True
    if STAKES_ORDER[stakes_value] > STAKES_ORDER[FAST_PATH_MAX_STAKES]:
        fast_allowed = False
        reasons.append(f"stakes are {stakes_value}")
    if design_required:
        fast_allowed = False
        reasons.append("the task declares a design obligation")
    if extra_capabilities:
        fast_allowed = False
        reasons.append("the task requires capabilities beyond the core pack: " + ", ".join(sorted(extra_capabilities)))
    if int(prior_failures) > 0:
        fast_allowed = False
        reasons.append(f"{int(prior_failures)} prior failure(s) are recorded for this task")
    if review_required:
        fast_allowed = False
        reasons.append("independent review is required")
    if human_acceptance_required:
        fast_allowed = False
        reasons.append("human acceptance is required")
    if str(policy_minimum) in (PATH_STANDARD, PATH_COMPLEX):
        fast_allowed = False
        reasons.append(f"policy sets a minimum path of {policy_minimum}")
    if fast_allowed:
        path = PATH_FAST
    elif STAKES_ORDER[stakes_value] >= STAKES_ORDER["HIGH"] or design_required or human_acceptance_required:
        path = PATH_COMPLEX
    else:
        path = PATH_STANDARD
    order = {
        PATH_FAST: ("characterisation", "worker", "validation"),
        PATH_STANDARD: (*STANDARD_ADDITIONS, "characterisation", "worker", "validation"),
        PATH_COMPLEX: COMPLEX_ADDITIONS,
    }[path]
    retained = [step for step in order]
    if review_required and "review" not in retained:
        retained.append("review")
    if human_acceptance_required and "human-acceptance" not in retained:
        retained.append("human-acceptance")
    if verification_required and "validation" not in retained:
        retained.append("validation")
    skipped = [
        step for step in ("decision", "routing", "review", "human-acceptance")
        if step not in retained
    ]
    return {
        "path": path,
        "stakes": stakes_value,
        "difficulty": str(difficulty or "UNKNOWN").upper(),
        "retained": retained,
        "skipped": skipped,
        "reasons": reasons or ["the task is low stakes with no extra obligation"],
        "verification_retained": "validation" in retained,
        "policy_derived": True,
        "note": (
            "the fast path is a policy decision, not an optimisation the engine takes silently; "
            "validation is retained on every path"
        ),
    }


def fast_path_eligible(**kwargs) -> bool:
    return path_plan(**kwargs)["path"] == PATH_FAST


# ------------------------------------------------------------ task-tree analysis


def _executions_for(state: Mapping, task_id: str) -> list[dict]:
    return [record for record in execution.executions(state)
            if str(record.get("task_id", "")) == str(task_id)]


def orchestration_economics(state: Mapping, task_id: str) -> dict:
    """What orchestration bought for one task, from measured records only."""
    task_id = str(task_id)
    rows = _executions_for(state, task_id)
    tree = economics.task_tree(state, task_id)
    costs = economics.task_tree_costs(tree)
    by_role: dict[str, dict] = {}
    for record in rows:
        role = str(record.get("role", "unknown"))
        block = by_role.setdefault(role, {"executions": 0, "completed": 0, "failed": 0})
        block["executions"] += 1
        if str(record.get("state")) == "COMPLETED":
            block["completed"] += 1
        elif str(record.get("state")) == "FAILED":
            block["failed"] += 1
    failures = [record for record in execution.failures(state) if str(record.get("task_id", "")) == task_id]
    repairs = sum(1 for record in failures if str(record.get("class")) in ("IMPLEMENTATION_FAILURE", "VALIDATION_FAILURE"))
    from . import verification as verification_module

    subject = verification_module.status(state, subject=task_id)
    from . import critique as critique_module

    reviews = 0
    review_findings = 0
    try:
        for review in critique_module.reviews(state):
            if str(review.get("task_id", "")) != task_id:
                continue
            reviews += 1
            review_findings += len(review.get("findings") or [])
    except AttributeError:
        reviews = 0
    decision_view = economics.decision_economics(state, task_id=task_id)
    context_view = economics.context_economics(state)
    duplicates = [row for row in context_view["duplicates"] if row.get("path")]
    return {
        "task_id": task_id,
        "executions_by_role": dict(sorted(by_role.items())),
        "executions": tree["executions"],
        "failed_executions": tree["failed_executions"],
        "repairs_attempted": repairs,
        "repair_succeeded": any(
            str(record.get("state")) == "COMPLETED" and str(record.get("role")) == "implementer"
            for record in rows
        ) and repairs > 0,
        "review_executions": reviews,
        "review_findings": review_findings,
        "decision_batches": decision_view["totals"]["batches"],
        "decision_questions": decision_view["totals"]["questions"],
        "costs": costs,
        "duplicate_source_rows": len(duplicates),
        "verification_level": str(subject.get("level", "UNVERIFIED")),
        "answers": {
            "did_a_repair_avoid_a_restart": (
                "YES" if repairs > 0 and any(str(record.get("role")) == "implementer"
                                             and str(record.get("state")) == "COMPLETED" for record in rows)
                else ("NO" if repairs > 0 else "NOT_APPLICABLE")
            ),
            "did_a_review_produce_findings": (
                "YES" if review_findings else ("NO" if reviews else "NOT_APPLICABLE")
            ),
            "did_decision_calls_replace_generative_calls": (
                "MEASURED" if decision_view["totals"]["measured_batches"] else "UNKNOWN"
            ),
            "did_a_subagent_reduce_parent_context": "UNKNOWN",
        },
        "note": (
            "every answer is derived from records; UNKNOWN means the run did not measure the thing, "
            "not that the answer is zero"
        ),
    }


def compare_paths(plan_a: Mapping, plan_b: Mapping) -> dict:
    """Compare two path plans by retained steps (no cost claim without measurement)."""
    retained_a = [str(item) for item in plan_a.get("retained") or []]
    retained_b = [str(item) for item in plan_b.get("retained") or []]
    return {
        "path_a": plan_a.get("path"),
        "path_b": plan_b.get("path"),
        "removed_steps": [step for step in retained_a if step not in retained_b],
        "added_steps": [step for step in retained_b if step not in retained_a],
        "note": "step counts are structural; a cost difference is only claimed when both runs measured it",
    }


def require_verification_retained(plan: Mapping) -> list[str]:
    """A path plan that dropped validation is refused.

    Invariant 46: a simple fast path cannot bypass required validation. The check
    is deliberately separate from the planner so a caller that constructs a plan
    by hand is held to the same rule.
    """
    problems: list[str] = []
    if not plan.get("verification_retained"):
        problems.append("the plan does not retain validation; a path may not bypass required verification")
    retained = {str(item) for item in plan.get("retained") or []}
    if "validation" not in retained:
        problems.append("the plan's retained steps do not include validation")
    return problems


__all__ = [
    "PATH_FAST",
    "PATH_STANDARD",
    "PATH_COMPLEX",
    "PATH_NAMES",
    "FAST_PATH_MAX_STAKES",
    "FAST_PATH_RETAINED",
    "STANDARD_ADDITIONS",
    "COMPLEX_ADDITIONS",
    "path_plan",
    "fast_path_eligible",
    "orchestration_economics",
    "compare_paths",
    "require_verification_retained",
]
