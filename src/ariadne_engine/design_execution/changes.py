"""From an approved direction to a changed file: the trace, and its gaps.

> **Requirement → ReferenceSet → Principle → Approved direction →
> Implementation constraint → File/component**

A chain is only worth having if a break in it is visible. This module assembles the
chain from records that already exist and reports every link that is missing,
rather than filling one in afterwards. A trace that quietly repairs itself is worse
than no trace, because it manufactures exactly the confidence a reader was checking
for.

So the query has two halves and both are honest:

* ``chain`` - what connects, assembled from recorded ids only;
* ``gaps``  - what does not, each with the missing link named.

Component/file-level provenance is deliberate. Per-line provenance would be a large
volume of assertion nobody reads, and a reviewer who cannot read the provenance does
not check it.
"""

from __future__ import annotations

from typing import Mapping, Sequence

from .. import contracts
from ..contracts import ContractError


def record_change(
    state: dict,
    *,
    plan: Mapping,
    path: str,
    classification: Mapping,
    change_kind: str = "",
    requirement_ids: Sequence[str] = (),
    principle_ids: Sequence[str] = (),
    reference_ids: Sequence[str] = (),
    implementation_source: str = "",
    validation_status: str = "NOT_RUN",
    component_name: str = "",
    recorded_at: str = "",
) -> dict:
    """Record one meaningful UI change, classified against the plan.

    The classification comes from :mod:`grounding` and is not recomputed here, so the
    recorded verdict and the verdict a reviewer would compute are the same object.
    What this adds is the lineage the plan cannot supply for itself: which
    requirements, principles and references the change carries, and where its
    implementation came from.
    """
    verdict = str(classification.get("verdict", ""))
    if verdict not in contracts.IMPLEMENTATION_CHANGE_VERDICTS:
        raise ContractError(f"cannot record a change with verdict {verdict!r}")
    if not str(implementation_source).strip():
        raise ContractError(
            f"the change to {path!r} names no implementation source; 'the worker did it' is not a source"
        )
    record = {
        "schema_version": contracts.SCHEMA_DESIGN,
        "change_id": contracts.new_record_id("dic"),
        "run_id": str(state.get("run_id", "")),
        "plan_id": str(plan.get("plan_id", "")),
        "task_id": str(plan.get("task_id", "")),
        "path": str(path),
        "component": str(component_name),
        "change_kind": str(change_kind or verdict),
        "verdict": verdict,
        "material": bool(classification.get("material", False)),
        "categories": dict(classification.get("categories") or {}),
        "removed_categories": dict(classification.get("removed_categories") or {}),
        "constraint_ids": [str(item) for item in classification.get("constraint_ids") or []],
        "grounding_constraint_ids": [
            str(item) for item in classification.get("grounding_constraint_ids") or []
        ],
        "reference_ids": [str(item) for item in reference_ids],
        "principle_ids": [str(item) for item in principle_ids],
        "requirement_ids": [str(item) for item in requirement_ids],
        "treatment": str(classification.get("treatment", "")),
        "implementation_source": str(implementation_source),
        "validation_status": str(validation_status),
        "explanation": str(classification.get("explanation", "")),
        "problem": str(classification.get("problem", "")),
        "recorded_at": str(recorded_at or contracts.utc_now()),
        "provenance": {"created_by": "engine", "policy_version": contracts.POLICY_VERSION},
    }
    problems = contracts.implementation_change_problems(record)
    if problems:
        raise ContractError("implementation change is malformed: " + "; ".join(problems))
    contracts.require_design_capacity(state, "design_implementation_changes")
    state.setdefault("design_implementation_changes", []).append(record)
    return record


def changes(state: Mapping, *, plan_id: str = "") -> list[dict]:
    values = state.get("design_implementation_changes")
    if not isinstance(values, list):
        return []
    return [
        dict(item) for item in values
        if isinstance(item, Mapping) and (not plan_id or str(item.get("plan_id", "")) == str(plan_id))
    ]


def change_summary(records: Sequence[Mapping]) -> dict:
    """Counts a reviewer actually reads, with unknowns left unknown."""
    verdicts: dict[str, int] = {}
    categories: dict[str, int] = {}
    material = 0
    grounded_material = 0
    for row in records:
        verdict = str(row.get("verdict", ""))
        verdicts[verdict] = verdicts.get(verdict, 0) + 1
        if row.get("material"):
            material += 1
            if verdict == "GROUNDED":
                grounded_material += 1
        for category in (row.get("categories") or {}):
            categories[str(category)] = categories.get(str(category), 0) + 1
    return {
        "changes": len(records),
        "material": material,
        "grounded_material": grounded_material,
        "ungrounded_material": verdicts.get("UNGROUNDED_DESIGN_CHANGE", 0),
        "accessibility_regressions": verdicts.get("ACCESSIBILITY_REGRESSION", 0),
        "cloning_findings": verdicts.get("REFERENCE_CLONING", 0),
        "verdicts": verdicts,
        "categories": categories,
    }


def trace(state: Mapping, *, plan_id: str = "", exposure: Sequence[Mapping] = ()) -> dict:
    """Assemble the full chain and name every missing link.

    Walks recorded ids only. Where a link is absent it appears in ``gaps`` with the
    reason, and the corresponding chain entry is marked ``MISSING`` rather than
    dropped - a gap nobody can see is a gap nobody will fix.

    Two things are deliberately *not* gaps, because calling them gaps would make the
    report cry wolf:

    * a change classified ``GROUNDED_INCIDENTAL``. It is a file in the chain with a
      positive verdict, not a hole in it.
    * a constraint that no change cited but which the run verified holds by absence -
      "do not introduce a literal colour" is satisfied by nobody writing one, and
      demanding a file that proves a negative would push authors toward fabricating
      one.
    """
    from . import plan as plan_module

    record = (
        plan_module.plan(state, plan_id) if plan_id else plan_module.latest_plan(state)
    )
    if not record:
        return {"found": False, "plan_id": str(plan_id), "chain": [], "gaps": [
            "no implementation plan exists for this run, so there is nothing to trace"
        ]}
    plan_identifier = str(record.get("plan_id", ""))
    constraints = plan_module.constraint_index(record)
    change_rows = changes(state, plan_id=plan_identifier)
    grounding = _direction_grounding(state, record)
    checked = {
        str(row.get("constraint_id", "")): dict(row)
        for row in (exposure or _recorded_exposure(state, plan_identifier))
        if isinstance(row, Mapping)
    }

    chain: list[dict] = []
    gaps: list[str] = []

    for binding in record.get("requirement_bindings") or []:
        if not isinstance(binding, Mapping):
            continue
        chain.append({
            "link": "REQUIREMENT",
            "id": str(binding.get("binding", "")),
            "source": str(binding.get("source", "")),
            "present": True,
        })

    chain.append({
        "link": "REFERENCE_SET",
        "id": str(record.get("reference_set_id", "")),
        "source": "APPROVED_DIRECTION",
        "present": bool(str(record.get("reference_set_id", ""))),
    })
    if not str(record.get("reference_set_id", "")):
        gaps.append("the plan names no reference set, so its evidence lineage is empty")

    principles = sorted({
        str(principle_id)
        for row in grounding.get("principles") or []
        if isinstance(row, Mapping)
        for principle_id in [str(row.get("principle_id", ""))]
    } - {""})
    for principle_id in principles:
        chain.append({
            "link": "PRINCIPLE",
            "id": principle_id,
            "source": "REFERENCE_SET",
            "present": True,
        })

    chain.append({
        "link": "APPROVED_DIRECTION",
        "id": str(record.get("direction_id", "")),
        "source": str((record.get("approval_binding") or {}).get("approval_id", "")),
        "present": bool(str((record.get("approval_binding") or {}).get("approval_id", ""))),
    })

    referenced_constraints: set[str] = set()
    for constraint_id, row in constraints.items():
        referenced = bool(
            [change for change in change_rows if constraint_id in (change.get("constraint_ids") or [])]
        )
        exposure_row = checked.get(constraint_id, {})
        outcome = str(exposure_row.get("outcome", "")) if exposure_row else ""
        if referenced:
            referenced_constraints.add(constraint_id)
        chain.append({
            "link": "CONSTRAINT",
            "id": constraint_id,
            "source": str(row.get("basis", "")),
            "category": str(row.get("category", "")),
            "present": True,
            "reached_a_file": referenced,
            "verified_by_absence": outcome == "VERIFIED_BY_ABSENCE",
        })
        if not referenced and outcome == "VERIFIED_BY_ABSENCE":
            continue
        if not referenced:
            gaps.append(
                f"implementation constraint {constraint_id} ({row.get('basis')}, "
                f"{row.get('category')}) reached no file and could not be checked; the approved direction "
                "asked for something nothing implemented and nothing demonstrated"
            )

    for change in change_rows:
        verdict = str(change.get("verdict", ""))
        chain.append({
            "link": "FILE",
            "id": str(change.get("path", "")),
            "source": str(change.get("implementation_source", "")),
            "present": True,
            "verdict": verdict,
            "grounded": verdict in ("GROUNDED", "GROUNDED_INCIDENTAL"),
            "constraints": list(change.get("constraint_ids") or []),
        })
        if verdict in ("GROUNDED", "GROUNDED_INCIDENTAL"):
            continue
        gaps.append(
            f"{change.get('path')} carries verdict {verdict}: "
            + str(change.get("problem") or change.get("explanation") or "no reason recorded")
        )

    orphan_references = sorted({
        str(reference_id)
        for change in change_rows
        for reference_id in (change.get("reference_ids") or [])
        if str(reference_id) not in {
            str(row.get("reference_id", "")) for row in record.get("reference_bindings") or []
            if isinstance(row, Mapping)
        }
    })
    for reference_id in orphan_references:
        gaps.append(
            f"a change cites reference {reference_id}, which the plan never bound to a constraint"
        )

    return {
        "found": True,
        "plan_id": plan_identifier,
        "direction_id": str(record.get("direction_id", "")),
        "reference_set_id": str(record.get("reference_set_id", "")),
        "approval_id": str((record.get("approval_binding") or {}).get("approval_id", "")),
        "chain": chain,
        "gaps": sorted(set(gaps)),
        "complete": not gaps,
        "constraints_verified_by_absence": sorted(
            constraint_id for constraint_id, row in checked.items()
            if str(row.get("outcome", "")) == "VERIFIED_BY_ABSENCE"
        ),
        "summary": change_summary(change_rows),
        "note": (
            "the chain is assembled from recorded identifiers only. A link that was never recorded "
            "appears as a gap; it is not reconstructed after the fact"
        ),
    }


def _recorded_exposure(state: Mapping, plan_id: str) -> list[dict]:
    """Constraint exposure recorded by the most recent run of this plan."""
    values = state.get("design_implementation_runs")
    if not isinstance(values, list):
        return []
    for record in reversed(values):
        if not isinstance(record, Mapping):
            continue
        if str(record.get("plan_id", "")) != str(plan_id):
            continue
        exposure = record.get("constraint_exposure")
        return [dict(row) for row in exposure or [] if isinstance(row, Mapping)]
    return []


def _direction_grounding(state: Mapping, record: Mapping) -> Mapping:
    from .. import design as design_module

    direction = design_module.direction(dict(state), str(record.get("direction_id", ""))) or {}
    grounding = direction.get("ar220_grounding")
    return grounding if isinstance(grounding, Mapping) else {}


def render_trace(report: Mapping) -> str:
    """A short human view of the chain, gaps included."""
    if not report.get("found"):
        return "No implementation plan found for this run."
    lines = [f"Design trace for plan {report.get('plan_id')}"]
    for link in report.get("chain") or []:
        marker = "ok " if link.get("present") else "MISSING"
        detail = ""
        if link.get("link") == "CONSTRAINT":
            if link.get("reached_a_file"):
                detail = "  (in a file)"
            elif link.get("verified_by_absence"):
                detail = "  (holds by absence: verified, not exercised)"
            else:
                detail = "  (no file)"
        if link.get("link") == "FILE" and link.get("verdict") not in ("GROUNDED", "GROUNDED_INCIDENTAL"):
            detail = f"  [{link.get('verdict')}]"
        lines.append(f"  {marker} {link.get('link'):<19} {link.get('id')}{detail}")
    gaps = report.get("gaps") or []
    if gaps:
        lines.append(f"  {len(gaps)} gap(s):")
        for gap in gaps:
            lines.append(f"    - {gap}")
    else:
        lines.append("  no gaps: every constraint reached a file and every file cites a constraint")
    return "\n".join(lines)


__all__ = [
    "change_summary",
    "changes",
    "record_change",
    "render_trace",
    "trace",
]