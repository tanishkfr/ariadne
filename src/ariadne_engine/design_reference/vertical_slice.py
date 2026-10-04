"""The AR-220 vertical slice, end to end (AR-220 exit criterion 16/17).

A real run, offline, from a request to approved-ready direction evidence:

```
1. inspect project-local design evidence
2. decide whether external references are useful
3. search getdesign.md
4. retrieve several public references
5. normalize DesignReference records
6. create a ReferenceSet
7. identify primary + counter references
8. extract observed patterns
9. produce a grounded design direction
10. emit provenance explaining each major design choice
```

The request the slice answers:

> *"Create a design direction for a serious desktop developer tool. It should feel
> precise, dense and calm, but not like a generic AI dashboard."*

The slice ends at **approved-ready direction evidence**. It does not implement
any UI, render anything, or critique a rendering; that is AR-221.

Everything runs against the frozen getdesign.md corpus, so the slice is
deterministic and repeatable. That is a deliberate trade: the *live* retrieval was
exercised once and frozen (see ``fixtures/getdesign-md/retrieval.json``), and the
regression suite runs the recording rather than the network. A vertical slice that
hit the network on every run would be a different test each time it ran.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Mapping, Sequence

from .. import contracts
from ..contracts import ContractError
from . import acquire, direction, discovery, getdesign, normalize, safety, sets

SLICE_REQUEST = (
    "Create a design direction for a serious desktop developer tool. It should feel precise, dense "
    "and calm, but not like a generic AI dashboard."
)
"""The exact request the AR-220 vertical slice answers."""

SLICE_QUERY = "developer tooling"
SLICE_COUNTER_QUERY = "vibrant gradient data dashboard"
SLICE_SCOPE = "desktop developer tool"

SLICE_TASK_ID = "ar220-vertical-slice"
"""The task id every AR-220 slice record carries.

Named rather than repeated inline, because AR-221 runs this same chain against a real
project and then looks the direction up by task id. A literal typed twice is a
coupling that fails silently the first time one copy changes.
"""

COUNTER_ANTI_PATTERN = (
    "a generic AI dashboard: a glassmorphic card grid with gradient glows, a centred hero and no "
    "information hierarchy"
)
"""What the design must not become.

Named explicitly because "not like a generic AI dashboard" is not executable on
its own. A counter-reference only earns its place by recording the specific
failure mode, and this is that failure mode.
"""

SLICE_PRIMARY_ROLES = ("PRIMARY_DIRECTION", "LAYOUT_REFERENCE")
SLICE_TYPOGRAPHY_ROLES = ("TYPOGRAPHY_REFERENCE",)
SLICE_IMPLEMENTATION_ROLES = ("IMPLEMENTATION_REFERENCE",)

PROJECT_FIXTURE = {
    "DESIGN.md": """---
version: 1
name: serious-tool-design
description: |
  A desktop developer tool that stays calm under density. Precision comes from a strict spacing
  ladder and hairline separation rather than from shadow and glow.
colors:
  canvas: "#0b0d0f"
  surface: "#121518"
  ink: "#e8eaed"
  ink-muted: "#9aa3ad"
  accent: "#7aa2f7"
  border: "#232a31"
typography:
  body:
    fontFamily: Inter
    fontSize: 13px
    lineHeight: 1.5
  heading:
    fontFamily: Inter
    fontSize: 18px
    fontWeight: 600
rounded:
  sm: 3px
  md: 5px
spacing:
  xs: 2px
  sm: 4px
  md: 8px
  lg: 16px
---

## Overview

The tool's own identity is quiet: a near-black canvas, one accent, and hairline
separators instead of elevation. Density is a feature, so whitespace is spent on
grouping rather than on air.

## Layout

Three-zone layout: a fixed-width primary column, a resizable secondary panel, and
an inspector that can collapse entirely.

## Do's and Don'ts

- Do keep separators hairline-thin and consistent.
- Do preserve a persistent context header across route changes.
- Don't introduce glassmorphic cards or gradient glows.
- Don't use elevation shadows to express hierarchy.
""",
    "styles/tokens.css": """:root {
  --canvas: #0b0d0f;
  --surface: #121518;
  --ink: #e8eaed;
  --ink-muted: #9aa3ad;
  --accent: #7aa2f7;
  --border: #232a31;
  --space-xs: 2px;
  --space-sm: 4px;
  --space-md: 8px;
  --space-lg: 16px;
  --radius-sm: 3px;
  --radius-md: 5px;
}
""",
    "src/components/Panel.tsx": "export function Panel() { return null; }\n",
    "src/components/Inspector.tsx": "export function Inspector() { return null; }\n",
}


def build_fixture_project(root: Path) -> Path:
    """Materialise the small isolated project the slice runs against."""
    for relative, text in PROJECT_FIXTURE.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return root


def run(
    *,
    project_root: Path | None = None,
    fixture_root: Path | None = None,
    request: str = SLICE_REQUEST,
    stamp: str = "2026-10-04T00:00:00Z",
) -> dict:
    """Run the whole slice and return one record describing what happened.

    Returns a report rather than raising, because a vertical slice that crashes is
    less informative than one that says exactly which step refused and why. Each
    step's refusal is captured in ``failures`` and the run stops there.
    """
    temporary = project_root is None
    root = Path(project_root) if project_root is not None else Path(tempfile.mkdtemp(prefix="ariadne-ar220-"))
    if project_root is None:
        build_fixture_project(root)
    fixtures = Path(fixture_root) if fixture_root is not None else Path(__file__).resolve().parent / "fixtures" / "getdesign-md"

    report: dict = {
        "request": str(request),
        "query": SLICE_QUERY,
        "scope": SLICE_SCOPE,
        "project": str(root),
        "counter_anti_pattern": COUNTER_ANTI_PATTERN,
        "steps": [],
        "failures": [],
        "references": [],
        "reference_set": {},
        "direction": {},
        "provenance": {},
        "offline": True,
        "completed": False,
    }

    def step(name: str, detail: str, **extra) -> None:
        report["steps"].append({"step": name, "detail": detail, **extra})

    state: dict = {
        "run_id": contracts.new_record_id("run"),
        "schema_version": contracts.SCHEMA_RECORD,
        "engine": {},
    }

    # -- 1. project-local evidence -------------------------------------------
    local = discovery.discover(root)
    report["discovery"] = local
    step(
        "project-evidence",
        (
            f"{len(local['probes']['design_documents'])} design document(s), "
            f"{local['probes']['design_tokens']['css_variable_count']} CSS variables, "
            f"{local['probes']['component_library']['component_files']} component files"
        ),
        identity_sources=list(local["identity_sources"]),
    )

    # -- 2. is external research warranted? -----------------------------------
    justified = discovery.external_reference_worthwhile(local, project_sufficient=True)
    report["external_justification"] = justified
    step("external-justification", f"{justified['verdict']}: {justified['reason']}")

    # -- 3-5. search, retrieve, normalize ------------------------------------
    # The research budget is expanded once, with a recorded reason: this request
    # asks for a direction plus an explicit anti-pattern, and one search cannot
    # answer both. `sets.resolve_budget` refuses an expansion that has no reason,
    # so this cannot become a quiet way to raise a limit.
    slice_budget = {
        "limits": {"candidate_retrieval": 24, "deep_inspection": 8},
        "reason": (
            "the request asks both for a direction and for an explicit anti-pattern, which are two "
            "searches. One search already spends the default candidate budget of 12, and the default "
            "deep-inspection budget of 5 cannot cover both searches within the recorded corpus"
        ),
    }
    outcome = acquire.acquire_references(
        state,
        project=root,
        query=SLICE_QUERY,
        counter_query=SLICE_COUNTER_QUERY,
        requirement_scope=SLICE_SCOPE,
        task_id=SLICE_TASK_ID,
        retrieved_at=stamp,
        allow_external=justified["verdict"] == "YES",
        project_sufficient=True,
        budget=slice_budget,
        catalog_entries=_catalog_entries(fixtures),
    )
    report["acquisition"] = {
        "external_capability": outcome["external_capability"],
        "candidates": len(outcome["candidates"]),
        "counter_candidates": len(outcome["counter_candidates"]),
        "normalized": outcome["normalized"],
        "rejected": outcome["rejected"],
        "bytes_retrieved": outcome["bytes_retrieved"],
        "budget": outcome["budget"],
        "injection": outcome["injection"],
        "stopped_because": outcome["stopped_because"],
        "steps": outcome["steps"],
    }
    step(
        "acquisition",
        (
            f"{len(outcome['candidates'])} candidate(s), {outcome['normalized']} normalized, "
            f"{outcome['rejected']} rejected, {outcome['bytes_retrieved']} bytes"
        ),
    )

    from .. import references as references_module

    by_id = {str(record["reference_id"]): record for record in references_module.references(state)}

    # -- 6-7. the reference set, with primary + counter references ------------
    counter_identity = ""
    for row in outcome["registered"]:
        if row.get("from_counter_search"):
            counter_identity = str(row.get("identity", ""))
            break
    report["counter_reference_identity"] = counter_identity
    members = _assign_members(
        state, by_id, counter_identity=counter_identity,
        limits=sets.resolve_budget(slice_budget)["limits"],
    )
    if not members:
        report["failures"].append(
            "no reference could be given a role; without primary references there is nothing to ground"
        )
        return report
    try:
        reference_set = sets.create(
            state,
            requirement_scope=SLICE_SCOPE,
            members=members,
            references_by_id=by_id,
            created_at=stamp,
            note=f"assembled for: {request}",
        )
    except ContractError as exc:
        report["failures"].append(str(exc))
        return report
    report["reference_set"] = reference_set
    report["diversity"] = reference_set["diversity"]
    report["coverage"] = reference_set["coverage"]
    report["treatments"] = _record_treatments(state, by_id)
    step(
        "treatments",
        "recorded: " + ", ".join(
            f"{row['reference_id']}={row['treatment']}" for row in report["treatments"]
        ),
    )
    step(
        "reference-set",
        f"{len(reference_set['members'])} member(s); coverage {reference_set['coverage']['verdict']}; "
        f"diversity {reference_set['diversity']['verdict']}",
        diversity=reference_set["diversity"]["verdict"],
        coverage=reference_set["coverage"]["verdict"],
    )

    # -- 8-9. patterns -> principles -> grounded direction -------------------
    project_identity = {
        "design_tokens": local["probes"]["design_tokens"],
        "component_library": local["probes"]["component_library"],
        "design_documents": local["probes"]["design_documents"],
    }
    principles = direction.extract_principles(members, by_id, applicable_to=SLICE_SCOPE)
    report["principles"] = [
        {
            "dimension": item["dimension"],
            "confidence": item["confidence"],
            "distinct_sources": item["distinct_sources"],
            "statement": item["statement"][:200],
        }
        for item in principles
    ]
    step("patterns-and-principles", f"{len(principles)} principle(s) extracted")

    try:
        compiled = direction.compile_candidate_direction(
            state,
            task_id=SLICE_TASK_ID,
            goal=str(request),
            scope=SLICE_SCOPE,
            requirement_scope=SLICE_SCOPE,
            reference_set_record=reference_set,
            references_by_id=by_id,
            members=members,
            project_identity=project_identity,
            product_context=[
                "engineers and power users working in long sessions on a desktop client",
                "a developer tool whose users read more than they click",
            ],
            accessible=[
                "every interactive element remains reachable and visible at 200% zoom",
                "focus order follows the reading order of the persistent context header",
                "state is never communicated by colour alone",
            ],
            responsive=[
                "the primary column keeps a minimum width; the inspector collapses before the column does",
                "the context header persists at every viewport below the desktop breakpoint",
            ],
            existing_system=[
                "preserve the project's own canvas, ink and accent tokens",
                "preserve the project's hairline separator treatment instead of introducing elevation",
            ],
            approved_deviations=[
                "deviate from the project's current single-column reading order by admitting a resizable "
                "secondary panel, because the request names density as a requirement",
            ],
            # Curated design analyses document colour, type, spacing and components.
            # They do not document how an interface behaves over time, so the
            # interaction section is grounded in the project's own documented
            # behaviour and is labelled `[project]` rather than attributed to a
            # reference that never said it.
            project_sections={
                "interaction_principles": [
                    "the context header stays persistent across route changes, so the working context is "
                    "never lost to navigation",
                    "the inspector collapses before the primary column narrows, because the primary column "
                    "carries the reading order",
                ],
            },
        )
    except ContractError as exc:
        report["failures"].append(str(exc))
        return report

    report["direction"] = {
        "direction_id": str(compiled["direction_id"]),
        "status": str(compiled["status"]),
        "approval_id": str(compiled.get("approval_id", "")),
        "fingerprint": contracts.direction_fingerprint(compiled),
        "sections": {
            name: compiled[name]
            for name in contracts.DIRECTION_FINGERPRINT_SECTIONS
            if name in compiled
        },
    }
    grounding = compiled["ar220_grounding"]
    report["grounding"] = {
        "reference_set_id": grounding["reference_set_id"],
        "ready_for_approval": grounding["ready_for_approval"],
        "ungrounded_sections": grounding["ungrounded_sections"],
        "counter_references": grounding["counter_references"],
        "treatment_counts": _treatment_counts(grounding["treatments"]),
        "choices": [
            {
                "section": row["section"],
                "grounding": row["grounding"],
                "statements": row.get("statements", 0),
                "project_statements": row.get("project_statements", 0),
                "supports": [item.get("reference_id", item.get("source", "")) for item in row["supports"]],
                "support_detail": row["supports"],
            }
            for row in grounding["choices"]
        ],
    }
    step(
        "grounded-direction",
        f"{compiled['direction_id']} is a {compiled['status']} candidate; "
        f"ready_for_approval={grounding['ready_for_approval']}",
    )

    # -- 10. provenance -------------------------------------------------------
    provenance = direction.direction_provenance(state, str(compiled["direction_id"]))
    report["provenance"] = provenance
    step("provenance", f"{len(provenance['lines'])} reference citation(s) in the direction record")

    report["references"] = [
        {
            "reference_id": str(record["reference_id"]),
            "title": str(record.get("title", "")),
            "source_kind": str(record.get("classification", {}).get("source_kind", "")),
            "evidence_level": str(record.get("classification", {}).get("evidence_level", "")),
            "provider": str(record.get("classification", {}).get("source_provider", "")),
            "state": str(record.get("state", "")),
            "patterns": len(record.get("observed_patterns") or []),
            "retrieved_at": str(record.get("retrieved_at", "")),
            "content_digest": str(record.get("classification", {}).get("content_digest", ""))[:16],
            "limitations": list(record.get("limitations") or []),
        }
        for record in by_id.values()
    ]
    report["contract_problems"] = (
        references_module.provenance_problems(state) + sets.provenance_problems(state)
    )
    report["completed"] = bool(
        grounding["ready_for_approval"] and not report["contract_problems"]
    )
    if not report["completed"]:
        report["failures"].append(
            "the slice did not reach approved-ready evidence: "
            + "; ".join(report["contract_problems"] or report["failures"] or ["ungrounded sections"])
        )
    report["state"] = state
    return report


def _catalog_entries(fixture_root: Path) -> list[dict]:
    import json

    catalog = Path(fixture_root) / "catalog.json"
    if not catalog.is_file():
        raise ContractError(f"no getdesign.md catalog fixture at {catalog}")
    return json.loads(catalog.read_text(encoding="utf-8")).get("entries", [])


def _assign_members(
    state: Mapping,
    by_id: Mapping[str, Mapping],
    counter_identity: str = "",
    limits: Mapping | None = None,
) -> list[dict]:
    """Give each reference the role(s) it can honestly serve, within budget.

    The assignment is deterministic and *derived from the record*, not chosen by
    taste: a reference is primary when its observed dimensions support direction,
    the project's own document is an implementation reference, and the
    counter-reference is the one the acquisition's **counter search** actually
    retrieved.

    Using the counter search's own result matters. An earlier version picked the
    first reference that happened to mention surfaces, which selected Cursor -
    a reference chosen as a *positive* example became the recorded anti-pattern,
    and the direction's "do not become" clause ended up describing something the
    slice had explicitly chosen to emulate.

    The role caps shape the selection rather than being reported after the fact.
    Four curated references all qualify as primary, and the default cap is three;
    a set that adopted all four and then reported the budget as exceeded would be
    reporting a consequence it had already accepted. Admitting the first
    ``primary_references`` qualifying references instead makes the bound do the
    work it exists to do.
    """
    from .. import references as references_module

    caps = {
        "primary": int((limits or {}).get("primary_references", contracts.REFERENCE_BUDGET_DEFAULTS["primary_references"])),
        "counter": int((limits or {}).get("counter_references", contracts.REFERENCE_BUDGET_DEFAULTS["counter_references"])),
    }
    order = [
        str(record["reference_id"]) for record in references_module.references(dict(state))
    ]

    members: list[dict] = []
    primaries_used = 0
    counter_assigned = False
    for reference_id in order:
        record = by_id.get(reference_id) or {}
        classification = record.get("classification") if isinstance(record.get("classification"), Mapping) else {}
        kind = str(classification.get("source_kind", ""))
        identity = str(classification.get("source_identity", ""))
        if kind == "LOCAL_DESIGN_FILE":
            members.append({
                "reference_id": reference_id,
                "roles": list(SLICE_IMPLEMENTATION_ROLES),
                "note": "the project's own design document: an implementation and identity constraint, "
                        "not an aesthetic reference",
            })
            continue
        dimensions = {
            str(row.get("dimension", ""))
            for row in (record.get("observed_patterns") or [])
            if isinstance(row, Mapping)
        }
        roles: list[str] = []
        wants_primary = bool(
            dimensions & {"information-hierarchy", "layout-grid", "density", "component-geometry"}
        )
        if wants_primary and primaries_used < caps["primary"]:
            roles.extend(SLICE_PRIMARY_ROLES)
            primaries_used += 1
        elif wants_primary:
            roles.append("COMPONENT_REFERENCE")
        if dimensions & {"typography", "spacing"}:
            roles.extend(SLICE_TYPOGRAPHY_ROLES)
        if not roles:
            roles = ["COMPONENT_REFERENCE"]
        if not counter_assigned and counter_identity and identity == counter_identity:
            roles.append("COUNTER_REFERENCE")
            members.append({
                "reference_id": reference_id,
                "roles": sorted(set(roles)),
                "counter_pattern": COUNTER_ANTI_PATTERN,
                "note": (
                    "retrieved by the counter-reference search, so it is the source chosen to stand for "
                    "what this direction must not become"
                ),
            })
            counter_assigned = True
            continue
        members.append({
            "reference_id": reference_id,
            "roles": sorted(set(roles)),
            "note": f"curated analysis of {classification.get('brand', 'a public brand')}; "
                    "evidence about public appearance, not a first-party design system",
        })
    if counter_identity and not counter_assigned:
        raise ContractError(
            f"the counter search retrieved {counter_identity!r} but no reference in the set carries that "
            "source identity; a direction cannot name an anti-pattern it did not read"
        )
    return members


TREATMENT_PLAN = {
    "BORROW": ("information-hierarchy", "layout-grid", "component-geometry", "density"),
    "ADAPT": ("typography", "spacing", "radii", "borders", "responsive-behavior"),
    "AVOID": ("surface-treatment", "motion"),
}
"""How this slice treats each dimension, decided before the principles are read.

``BORROW`` the structural disciplines the developer-tool references demonstrably
share. ``ADAPT`` the type and spacing scales, because a different product with
different content cannot reuse another product's exact scale. ``AVOID`` surface
treatment from the counter-reference, which is the whole reason it is in the set.

Unlisted dimensions default to ``ADAPT`` inside
:func:`normalize.build_treatments`, so a dimension nobody decided about is never
silently treated as permission to copy.
"""


def _record_treatments(state: Mapping, by_id: Mapping[str, Mapping]) -> list[dict]:
    """Attach a BORROW/ADAPT/AVOID treatment to every reference in the set.

    Recorded on the reference record itself, before the direction is compiled, so
    the treatment table and the principles come from the same evidence. A
    reference that reaches a direction without one is reported as untreated rather
    than quietly contributing its patterns.
    """
    rows: list[dict] = []
    for reference_id, record in by_id.items():
        patterns = record.get("observed_patterns") or []
        if not patterns:
            rows.append({"reference_id": reference_id, "treatment": "NONE", "patterns": 0})
            continue
        treatments = normalize.build_treatments(
            patterns,
            borrow=TREATMENT_PLAN["BORROW"],
            adapt=TREATMENT_PLAN["ADAPT"],
            avoid=TREATMENT_PLAN["AVOID"],
        )
        record["treatments"] = treatments
        breakdown = sorted({item["treatment"] for item in treatments})
        rows.append({
            "reference_id": reference_id,
            "treatment": "+".join(breakdown),
            "patterns": len(patterns),
            "dimensions": sorted({str(item["dimension"]) for item in treatments}),
        })
    return rows


def _treatment_counts(treatments: Sequence[Mapping]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in treatments or []:
        if not isinstance(row, Mapping):
            continue
        label = str(row.get("treatment", "UNTREATED")) if row.get("treated") else "UNTREATED"
        counts[label] = counts.get(label, 0) + 1
    return dict(sorted(counts.items()))


def summarise(report: Mapping) -> str:
    """A readable report of one slice run."""
    lines = [f"AR-220 vertical slice: {report.get('request', '')}"]
    for row in report.get("steps") or []:
        lines.append(f"  {row['step']}: {row['detail']}")
    for row in report.get("references") or []:
        lines.append(
            f"    - {row['title']} [{row['source_kind']}/{row['evidence_level']}] "
            f"{row['patterns']} patterns, {row['content_digest']}ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â¦"
        )
    grounding = report.get("grounding") if isinstance(report.get("grounding"), Mapping) else {}
    lines.append(
        f"  ready_for_approval={grounding.get('ready_for_approval')} "
        f"ungrounded={grounding.get('ungrounded_sections')} "
        f"treatments={grounding.get('treatment_counts')}"
    )
    if report.get("failures"):
        for failure in report["failures"]:
            lines.append(f"  FAILURE: {failure}")
    return "\n".join(lines)


__all__ = [
    "COUNTER_ANTI_PATTERN",
    "PROJECT_FIXTURE",
    "SLICE_PRIMARY_ROLES",
    "SLICE_QUERY",
    "SLICE_REQUEST",
    "SLICE_SCOPE",
    "build_fixture_project",
    "run",
    "summarise",
]
