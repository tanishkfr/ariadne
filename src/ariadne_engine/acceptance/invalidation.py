"""Selective invalidation: what a change invalidated, and what has to run again.

The obvious implementation of "the work changed, so re-check" is to re-check everything.
It is correct, it is expensive, and it is why most verification systems are switched off
after a fortnight. Context economics argue against it directly: if four targeted checks
restore the same confidence as forty, the other thirty-six are a cost with no return.

So invalidation here is **selective and evidence-driven**, with three answers and no
fourth:

``PROVEN_UNAFFECTED``
    The changed artifact is provably outside this requirement's dependency set. Claimed
    only when a *recorded dependency fingerprint* says so -- never inferred from the fact
    that a requirement's text does not mention the changed file.

``POTENTIALLY_AFFECTED``
    The change touches the requirement's declared implementation scope, or a dependency
    whose fingerprint the requirement names and which has moved.

``UNKNOWN``
    The dependency relationship could not be established. **Not** reported as unaffected.

That last one is the whole design. An engine that guesses "probably fine" and records the
guess as ``PROVEN_UNAFFECTED`` has built selective forgetting, which is strictly worse than
selective verification: it is faster *and* wrong, and the wrongness is invisible. Here
``UNKNOWN`` is a real, reportable outcome and it keeps the requirement's verdict
suspended rather than letting an old pass carry it.

Re-verification is planned from the invalidated set with a deterministic minimum cover,
weighted by the cost of each check, and every selection records the reason it was chosen.
A requirement no registered check can cover is reported as uncovered rather than quietly
dropped -- an uncovered requirement is a gap in the check registry, and saying so is the
only way anyone finds out.
"""

from __future__ import annotations

import fnmatch
from typing import Any, Iterable, Mapping, Sequence

from .. import contracts
from ..contracts import ContractError

IMPACT_STATES = contracts.IMPACT_STATES
"""``PROVEN_UNAFFECTED`` / ``POTENTIALLY_AFFECTED`` / ``UNKNOWN``, reused from contracts."""

COST_TIERS = ("FREE", "CHEAP", "MODERATE", "EXPENSIVE")
"""Relative cost of a check, for planning only.

Not a duration and not a price. It exists so the planner can prefer four cheap targeted
checks over one expensive blanket run when both restore the same confidence, and the
number it actually used is recorded with the plan.
"""

COST_ORDER = {name: index for index, name in enumerate(COST_TIERS)}


def _matches(relative: str, pattern: str) -> bool:
    """Glob matching with a ``src/``-relative fallback.

    Both halves matter: patterns are written both as repository-relative
    (``src/app/Navigation.tsx``) and as bare globs (``*.tsx``), and a matcher that only
    honours one of them silently fails to invalidate requirements whose scope was
    declared in the other style -- a *false unaffected*, which is the failure this whole
    module is built to avoid.
    """
    target = str(relative or "").replace("\\", "/")
    if fnmatch.fnmatch(target, str(pattern)):
        return True
    tail = target.rsplit("/", 1)[-1]
    return fnmatch.fnmatch(tail, str(pattern))


def requirement_scope(requirement_record: Mapping[str, Any]) -> list[str]:
    return [str(item) for item in requirement_record.get("scope_paths") or ()]


def declared_dependencies(requirement_record: Mapping[str, Any]) -> dict[str, str]:
    """Dependency fingerprints the requirement itself declares.

    Optional, and the difference between ``UNKNOWN`` and ``PROVEN_UNAFFECTED``. A
    requirement that records ``{"package-lock": "sha256:..."}`` can be shown unaffected by
    a CSS change. One that records nothing cannot, however obviously unrelated the change
    looks, because "obviously" is exactly the judgement that was wrong last time.
    """
    declared = requirement_record.get("dependencies")
    if not isinstance(declared, Mapping):
        return {}
    return {str(key): str(value) for key, value in declared.items()}


def impact(
    requirement_record: Mapping[str, Any],
    *,
    changed: Sequence[str],
    current_dependencies: Mapping[str, str] | None = None,
) -> dict:
    """How one change affects one requirement.

    ``changed`` is a list of repository-relative paths that moved. Both the declared scope
    and the declared dependency fingerprints are consulted, and the *order* is what makes
    the result safe: a scope match is decisive in the affected direction, a dependency
    fingerprint that has moved is decisive, and only when neither says anything does the
    ``UNKNOWN`` fallback apply. Nothing here ever reaches ``PROVEN_UNAFFECTED`` by
    assuming.
    """
    scope = requirement_scope(requirement_record)
    moved = [str(item).replace("\\", "/") for item in changed or () if str(item).strip()]
    matched = sorted({
        pattern for pattern in scope
        if any(_matches(path, pattern) for path in moved)
    })
    if matched:
        return {
            "requirement_id": str(requirement_record.get("requirement_id", "")),
            "impact": "POTENTIALLY_AFFECTED",
            "changed": sorted(moved),
            "matched_scope": matched,
            "reason": (
                f"the change touches the requirement's declared implementation scope ({', '.join(matched)}), "
                "so anything established about it must be re-established"
            ),
        }
    declared = declared_dependencies(requirement_record)
    if declared and current_dependencies is not None:
        moved_dependencies = sorted(
            name for name, value in declared.items()
            if name in current_dependencies and str(current_dependencies[name]) != str(value)
        )
        if moved_dependencies:
            return {
                "requirement_id": str(requirement_record.get("requirement_id", "")),
                "impact": "POTENTIALLY_AFFECTED",
                "changed": sorted(moved),
                "moved_dependencies": moved_dependencies,
                "reason": (
                    f"the requirement's declared dependencies moved: {', '.join(moved_dependencies)}"
                ),
            }
        return {
            "requirement_id": str(requirement_record.get("requirement_id", "")),
            "impact": "PROVEN_UNAFFECTED",
            "changed": sorted(moved),
            "dependencies_checked": sorted(declared),
            "reason": (
                f"every dependency fingerprint the requirement declares is unchanged "
                f"({', '.join(sorted(declared))}) and the change matches none of its declared scope"
            ),
        }
    if not scope:
        return {
            "requirement_id": str(requirement_record.get("requirement_id", "")),
            "impact": "UNKNOWN",
            "changed": sorted(moved),
            "reason": (
                "the requirement declares no implementation scope and no dependency fingerprints, so "
                "there is nothing to check a change against. UNKNOWN is the honest answer and must "
                "not be reported as unaffected"
            ),
        }
    return {
        "requirement_id": str(requirement_record.get("requirement_id", "")),
        "impact": "UNKNOWN",
        "changed": sorted(moved),
        "matched_scope": [],
        "reason": (
            f"the change matches none of the requirement's declared scope ({', '.join(scope)}) and the "
            "requirement declares no dependency fingerprints that could prove it unaffected. An "
            "unestablished dependency relationship is UNKNOWN, not safe"
        ),
    }


def assess_change(
    state: Mapping[str, Any],
    *,
    contract_id: str,
    changed: Sequence[str],
    current_dependencies: Mapping[str, str] | None = None,
) -> dict:
    """Assess every active requirement against one change, with counts.

    The counts matter more than they look: a change that reports 40 requirements
    ``UNKNOWN`` has not told you they are fine, it has told you the contracts carry no
    scope information, and that is a finding about the *contracts*.
    """
    from . import requirements as requirements_module

    rows = requirements_module.active_requirements(state, contract_id=contract_id)
    impacts = [
        impact(row, changed=changed, current_dependencies=current_dependencies)
        for row in rows
    ]
    counts = {name: 0 for name in IMPACT_STATES}
    for row in impacts:
        counts[str(row.get("impact", "UNKNOWN"))] += 1
    return {
        "contract_id": str(contract_id),
        "changed": sorted(str(item).replace("\\", "/") for item in changed or ()),
        "requirements": len(rows),
        "impacts": impacts,
        "counts": counts,
        "stale": sorted(
            str(row["requirement_id"]) for row in impacts
            if str(row.get("impact")) == "POTENTIALLY_AFFECTED"
        ),
        "unknown": sorted(
            str(row["requirement_id"]) for row in impacts
            if str(row.get("impact")) == "UNKNOWN"
        ),
        "unaffected": sorted(
            str(row["requirement_id"]) for row in impacts
            if str(row.get("impact")) == "PROVEN_UNAFFECTED"
        ),
        "note": (
            "requirements whose dependency relationship could not be established are reported as "
            "UNKNOWN. Reporting them as unaffected would be selective forgetting, which is worse "
            "than re-running everything"
        ),
    }


def invalidate(
    state: dict,
    *,
    contract_id: str,
    changed: Sequence[str],
    current_dependencies: Mapping[str, str] | None = None,
) -> dict:
    """Mark every potentially-affected requirement's latest decision stale.

    ``UNKNOWN`` requirements are marked too. They cannot be shown current, so their
    previous verdict stops answering -- recorded with the reason, so a reader can see the
    difference between *proved unaffected* and *could not be shown unaffected*.
    """
    from . import decisions as decisions_module

    report = assess_change(
        state, contract_id=contract_id, changed=changed,
        current_dependencies=current_dependencies,
    )
    latest = decisions_module.latest_by_requirement(state, contract_id=contract_id)
    marked: list[dict] = []
    index = 0
    for decision in state.get(decisions_module.DECISION_COLLECTION, []) or []:
        requirement_id = str(decision.get("requirement_id", ""))
        current = latest.get(requirement_id)
        if current is None or str(current.get("verification_id", "")) != str(
            decision.get("verification_id", "")
        ):
            index += 1
            continue
        row = next(
            (item for item in report["impacts"]
             if str(item.get("requirement_id", "")) == requirement_id), {},
        )
        impact_state = str(row.get("impact", "UNKNOWN"))
        if impact_state == "PROVEN_UNAFFECTED":
            index += 1
            continue
        updated = dict(decision)
        updated["freshness"] = impact_state
        updated["stale_reason"] = str(row.get("reason", ""))
        updated["stale_at"] = contracts.utc_now()
        state[decisions_module.DECISION_COLLECTION][index] = updated
        marked.append({
            "verification_id": str(updated.get("verification_id", "")),
            "requirement_id": requirement_id,
            "impact": impact_state,
            "reason": str(row.get("reason", "")),
        })
        index += 1
    report["stale_decisions"] = marked
    return report


# ------------------------------------------------------- re-verification plan


def check(
    *,
    check_id: str,
    kind: str,
    requirement_ids: Sequence[str],
    cost: str = "CHEAP",
    method: str = "",
    produces: Sequence[str] = (),
    re_renders: bool = False,
) -> dict:
    """Register one re-runnable check against the requirements it can cover.

    ``kind`` is the evidence kind the check produces, which is what lets a plan explain
    *why* a check was chosen rather than merely that it was.
    """
    if str(cost) not in COST_ORDER:
        raise ContractError(f"unsupported check cost tier: {cost!r}")
    if not str(check_id or "").strip():
        raise ContractError("a check needs an id")
    if not str(kind or "").strip():
        raise ContractError(f"check {check_id} names no evidence kind, so a plan cannot explain it")
    return {
        "check_id": str(check_id),
        "kind": str(kind),
        "requirement_ids": [str(item) for item in requirement_ids or ()],
        "cost": str(cost),
        "method": str(method),
        "produces": [str(item) for item in produces or ()],
        "re_renders": bool(re_renders),
    }


def plan(
    *,
    stale_requirement_ids: Sequence[str],
    checks: Sequence[Mapping[str, Any]],
    must_cover_blocking: bool = True,
    blocking_ids: Sequence[str] = (),
) -> dict:
    """The minimum set of checks that restores confidence in the invalidated set.

    Deterministic greedy set cover, ordered by (cost tier, how many outstanding
    requirements the check newly covers, check id). Deterministic because a re-verification
    plan that differs between runs on identical inputs is a plan nobody can reproduce, and
    a plan nobody can reproduce is a plan nobody can review.

    Requirements no check covers are reported as ``uncovered`` rather than omitted.
    """
    outstanding = [str(item) for item in stale_requirement_ids or () if str(item)]
    if not outstanding:
        return {
            "selected": [], "uncovered": [], "cost": "FREE", "total_cost": 0,
            "requirements": [],
            "reason": "nothing was invalidated, so nothing has to be re-run",
        }
    remaining = set(outstanding)
    ordered = sorted(
        checks,
        key=lambda row: (COST_ORDER.get(str(row.get("cost", "CHEAP")), 99),
                         str(row.get("check_id", ""))),
    )
    selected: list[dict] = []
    while remaining:
        best: tuple[tuple[int, int, str], Mapping[str, Any]] | None = None
        for candidate in ordered:
            if any(str(row.get("check_id")) == str(candidate.get("check_id")) for row in selected):
                continue
            cover = remaining & {str(item) for item in candidate.get("requirement_ids") or ()}
            if not cover:
                continue
            key = (
                COST_ORDER.get(str(candidate.get("cost", "CHEAP")), 99),
                -len(cover),
                str(candidate.get("check_id", "")),
            )
            if best is None or key < best[0]:
                best = (key, candidate)
        if best is None:
            break
        candidate = best[1]
        cover = sorted(remaining & {str(item) for item in candidate.get("requirement_ids") or ()})
        remaining -= set(cover)
        selected.append({
            "check_id": str(candidate.get("check_id", "")),
            "kind": str(candidate.get("kind", "")),
            "cost": str(candidate.get("cost", "CHEAP")),
            "covers": cover,
            "re_renders": bool(candidate.get("re_renders")),
            "reason": (
                f"cheapest remaining check covering {len(cover)} outstanding requirement(s) "
                f"({', '.join(cover)})"
            ),
        })
    uncovered = sorted(remaining)
    total_cost = sum(COST_ORDER.get(str(row.get("cost", "CHEAP")), 99) for row in selected)
    worst = COST_TIERS[min(total_cost, len(COST_TIERS) - 1)]
    return {
        "selected": selected,
        "uncovered": uncovered,
        "uncovered_blocking": sorted(set(uncovered) & {str(item) for item in blocking_ids or ()}),
        "cost": worst,
        "total_cost": total_cost,
        "requirements": sorted(outstanding),
        "reason": (
            f"{len(selected)} targeted check(s) instead of re-running all evidence, chosen greedily "
            "by cost then by coverage, and every selection recorded"
        ),
        "note": (
            "an uncovered requirement is a gap in the check registry, not a satisfied requirement. "
            "It is reported so somebody finds out"
        ),
    }


def repair_plan(
    *,
    stale_report: Mapping[str, Any],
    checks: Sequence[Mapping[str, Any]],
    blocking_ids: Sequence[str] = (),
) -> dict:
    """Assess one change and plan exactly the re-verification it needs."""
    stale = list(stale_report.get("stale", []) or [])
    unknown = list(stale_report.get("unknown", []) or [])
    targeted = plan(
        stale_requirement_ids=[*stale, *unknown],
        checks=checks,
        blocking_ids=blocking_ids,
    )
    return {
        **targeted,
        "changed": list(stale_report.get("changed", []) or ()),
        "counts": dict(stale_report.get("counts", {})),
        "unaffected": list(stale_report.get("unaffected", []) or ()),
        "reason": (
            f"{len(stale_report.get('unaffected', []) or ())} requirement(s) were shown unaffected by "
            f"declared dependencies, {len(stale)} were potentially affected, and {len(unknown)} could "
            "not be shown unaffected at all"
        ),
    }


__all__ = [
    "COST_ORDER",
    "COST_TIERS",
    "IMPACT_STATES",
    "assess_change",
    "check",
    "declared_dependencies",
    "impact",
    "invalidate",
    "plan",
    "repair_plan",
    "requirement_scope",
]