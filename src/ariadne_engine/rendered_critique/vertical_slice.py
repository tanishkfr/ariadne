"""The AR-222 vertical slice: render Beacon for real, critique it, bound the repair.

This is the honest end of the chain. AR-221 built a workspace and proved it compiles;
this renders that exact build in a real browser, judges what actually appeared against
the approved direction, repairs what is genuinely repairable, and re-renders.

Three properties of this slice are deliberate and worth naming.

**It renders the AR-221 result before changing anything.** The first evidence set is
the *before* state, taken from a mechanically validated AR-221 run that has not been
touched. Improving it reflexively, before anyone has looked, would make every later
screenshot a picture of the author's intentions rather than of the product.

**The default reviewer is deterministic and says so.** :func:`deterministic_review`
reports only what a render can *prove*: horizontal overflow, absent focus indication,
controls with no accessible name, forbidden literal counter-patterns, runtime errors.
Those are real findings, reproducible by re-running this function, and they are not
fabricated. It explicitly refuses to guess at hierarchy or density, because a tool
that manufactures tasteful-sounding findings to look useful is worse than one that
reports nothing. A model or human reviewer receives the same isolated packet through
:func:`review_with` and may add ``BOUNDED_JUDGEMENT`` findings; those are recorded as
judgement, never as measurement.

**Zero repairs is a valid outcome.** If the AR-221 render genuinely satisfies the
direction, the slice closes with no refinement. Modifying the design to demonstrate the
refinement machinery would be theatre, and it would also destroy the one thing that
makes the before/after evidence meaningful.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
import time
from pathlib import Path
from typing import Callable, Mapping, Sequence

from .. import contracts
from ..contracts import ContractError
from . import adapter as adapter_module
from . import critique as critique_module
from . import evidence as evidence_module
from . import plan as plan_module
from . import refinement as refinement_module
from . import safety
from . import source as source_module
from . import trace as trace_module

SLICE_REQUEST = (
    "Capture the Beacon workspace that AR-221 built, judge what actually rendered "
    "against the approved direction, and repair only what is genuinely repairable."
)

ROUTE = "index.html"
SURFACE = "beacon-desktop-tool"

WORKSPACE_REGIONS = (".workspace", ".panel", ".log-table")
"""Structural regions this surface must contain in every capture.

Declared by the capture plan rather than guessed at review time, so a render whose
workspace collapsed to zero height is refused as ``NO_CONTENT`` instead of being
photographed and reported as an improvement. The navigation rail is deliberately not
listed: it survives nearly every layout failure, which is exactly why it cannot be the
thing whose presence proves content loaded.
"""

NARROW_MARKER = "AR-222: narrow-workspace"
"""Idempotence marker for the narrow-viewport repair.

The guard is compared against the exact token the repair emits, because a repair that
appends its rule again on the next cycle grows the stylesheet on every attempt, and each
duplicate copy surfaces as a fresh finding -- a repair loop that manufactures its own
work and then burns the whole allowance chasing it. The marker and the emitted comment
must stay in step."""

#: Beacon's approved direction claims a desktop tool with an explicit workspace. The
#: capture plan derives its viewports from that claim rather than from a default ladder.
DIRECTION_CLAIMS = {
    "viewport": "A desktop developer tool used at a desk-sized window",
    "responsive": (
        "The workspace keeps its primary layout at narrow widths; the inspector column "
        "stacks beneath the primary panel rather than forcing a horizontal scroll."
    ),
    "interaction": (
        "The request toolbar and the navigation rail are the two interactive surfaces "
        "that carry the approved interaction model."
    ),
}


def _principles(direction: Mapping) -> list[dict]:
    """The approved principles a render can be judged against.

    Drawn from the direction record itself rather than restated here, because a
    principle restated in two places is a principle that will drift.
    """
    rows: list[dict] = []

    def add(statement: str, category: str) -> None:
        text = str(statement or "").strip()
        if not text:
            return
        rows.append({
            "principle_id": f"prn_{category}_{len(rows) + 1}",
            "statement": text,
            "category": category,
            "source": "approved-direction",
        })

    add(str((direction.get("goal") or "")), "goal")
    hierarchy = direction.get("key_hierarchy")
    if isinstance(hierarchy, Mapping):
        for key, value in hierarchy.items():
            add(str(value), f"hierarchy-{key}")
    elif isinstance(hierarchy, (list, tuple)):
        for value in hierarchy:
            add(str(value), "hierarchy")
    for group in ("visual_principles", "content_principles", "interaction_principles"):
        value = direction.get(group)
        if isinstance(value, Mapping):
            for key, item in value.items():
                add(str(item), f"{group}-{key}")
        elif isinstance(value, (list, tuple)):
            for item in value:
                if isinstance(item, Mapping):
                    add(str(item.get("statement", item.get("text", item.get("principle", "")))), group)
                else:
                    add(str(item), group)
    for value in (direction.get("responsive_requirements") or []):
        add(str(value.get("requirement", value)) if isinstance(value, Mapping) else str(value), "responsive")
    for value in (direction.get("accessibility_requirements") or []):
        add(str(value.get("requirement", value)) if isinstance(value, Mapping) else str(value), "accessibility")
    seen: set[str] = set()
    unique: list[dict] = []
    for row in rows:
        if row["statement"] in seen:
            continue
        seen.add(row["statement"])
        unique.append(row)
    return unique


def _requirements(state: Mapping) -> list[dict]:
    rows = []
    for record in (state.get("design_requirements") or []):
        if not isinstance(record, Mapping):
            continue
        rows.append({
            "requirement_id": str(record.get("requirement_id", "")),
            "statement": str(record.get("statement", "") or record.get("description", "")),
            "materiality": [str(item) for item in (record.get("materiality") or [])],
        })
    return rows


def build_plan(state: Mapping, *, binding: Mapping, direction: Mapping, implementation_plan_id: str,
               project: Path) -> dict:
    """Choose what to capture, and justify each target.

    Derived from the direction's own claims: a desktop tool with a stated narrow-width
    behaviour gets one primary viewport and two responsive ones; a stated interaction
    model gets its interaction states; nothing gets a theme variant because Beacon has
    one theme and manufacturing a dark mode because some reference had one would be
    inventing a requirement.
    """
    targets: list[dict] = []
    primary = {"width": 1440, "height": 900}
    targets.append(plan_module.viewport_state(
        route=ROUTE, state="workspace-default", viewport=primary,
        basis=[{"basis": "REQUIREMENT", "reason": "the workspace shell is the surface the whole direction is about"},
               {"basis": "DIRECTION_PRINCIPLE", "reason": "every approved principle is expressed on this surface"}],
        notes="the before state: the AR-221 implementation exactly as it was validated",
        required_regions=WORKSPACE_REGIONS,
    ))
    targets.append(plan_module.interaction_state(
        route=ROUTE, state="toolbar-focused",
        action={"kind": "focus", "selector": ".toolbar .btn--primary"},
        basis=[{"basis": "MATERIALITY", "reason": "the primary action is the most material interactive element on the surface"},
               {"basis": "DIRECTION_PRINCIPLE", "reason": "the direction requires an operable primary action"}],
        notes="keyboard focus on the primary action: focus visibility is an accessibility floor, not a preference",
        required_regions=WORKSPACE_REGIONS,
    ))
    targets.append(plan_module.interaction_state(
        route=ROUTE, state="nav-item-focused",
        action={"kind": "focus", "selector": ".nav-item"},
        basis=[{"basis": "MATERIALITY", "reason": "navigation structure is a material design category"},
               {"basis": "DIRECTION_PRINCIPLE", "reason": "the rail is the way a user changes context"}],
        notes="keyboard focus in the navigation rail, to read focus indication against the rail surface",
        required_regions=WORKSPACE_REGIONS,
    ))
    targets.append(plan_module.responsive_state(
        route=ROUTE, viewport={"width": 1024, "height": 768}, state="workspace-default",
        basis=[{"basis": "DIRECTION_PRINCIPLE", "reason": str(DIRECTION_CLAIMS["responsive"])}],
        notes="narrow-desktop width named by the direction's responsive requirement",
        required_regions=WORKSPACE_REGIONS,
    ))
    targets.append(plan_module.responsive_state(
        route=ROUTE, viewport={"width": 390, "height": 844}, state="workspace-default",
        basis=[{"basis": "DIRECTION_PRINCIPLE", "reason": str(DIRECTION_CLAIMS["responsive"])}],
        notes="phone width; the direction states the inspector stacks rather than forcing horizontal scroll",
        required_regions=WORKSPACE_REGIONS,
    ))
    reduced = plan_module.viewport_state(
        route=ROUTE, state="workspace-reduced-motion", viewport=primary,
        basis=[{"basis": "REQUIREMENT", "reason": "accessibility is a floor; motion preference outranks a reference"}],
        notes="prefers-reduced-motion: reduce, emulated before capture",
        required_regions=WORKSPACE_REGIONS,
    )
    reduced["reduced_motion"] = True
    targets.append(reduced)
    binding_row = dict(binding)
    binding_row["project_root"] = str(project)
    return plan_module.create(
        implementation_plan_id=implementation_plan_id,
        direction_id=str(direction.get("direction_id", "")),
        binding=binding_row,
        target_surface=SURFACE,
        launch_command=["python", "--version"],
        targets=targets,
        browser_requirements={
            "engine": "any Chromium-class browser behind the RenderAdapter contract",
            "optional": True,
            "reason_if_absent": "RENDER_CAPABILITY_UNAVAILABLE -- a rendered review cannot be produced without one",
        },
        required_evidence=["navigation structure", "workspace hierarchy", "panel geometry", "focus indication"],
        notes=SLICE_REQUEST,
    )


def _duplicate_headings(headings: Sequence[Mapping]) -> list[str]:
    """Visible heading texts that appear more than once on a surface.

    Deliberately conservative: it requires the text to be identical and to appear on
    more than one heading tag. A panel header and an in-body heading carrying the same
    word is a duplicated hierarchy signal; two different labels that merely share a word
    are not, and reporting those would be noise.
    """
    counts: dict[str, int] = {}
    for row in headings or ():
        if not isinstance(row, Mapping):
            continue
        text = str(row.get("text", "")).strip()
        if len(text) < 2:
            continue
        counts[text] = counts.get(text, 0) + 1
    return sorted(text for text, count in counts.items() if count > 1)


def _defect_key(row: Mapping) -> str:
    """A stable identity for one defect, independent of which critique observed it.

    A critique mints fresh ``rfd_*`` ids every time, which is correct for the records but
    useless for tracking: without a stable key the same defect looks "resolved" in one
    cycle and "new" in the next, and a cycle that changed nothing reports progress. The
    key is derived from what the defect *is* -- dimension, expected basis, repair scope,
    viewport -- so an independent re-review of the same defect recognises it, and
    resolved/persistent/new means something.
    """
    parts = [
        str(row.get("dimension", "")),
        str(row.get("severity", "")),
        str(row.get("expected_basis", ""))[:80],
        str(row.get("repair_scope", ""))[:60],
        str(row.get("viewport_width", "")),
    ]
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:16]


def _reuse_finding_ids(findings: Sequence[Mapping], prior: Mapping[str, str]) -> None:
    """Carry a finding's original id across re-reviews when the defect is the same."""
    for row in findings:
        if not isinstance(row, dict):
            continue
        key = str(row.get("defect_key", ""))
        if key and key in prior:
            row["finding_id"] = str(prior[key])
            row["reobserved"] = True


def _known_defect_keys(state: Mapping) -> dict[str, str]:
    """defect_key -> finding_id, from every critique recorded so far."""
    out: dict[str, str] = {}
    for record in critique_module.critiques(state):
        for row in (record.get("findings") or []):
            if isinstance(row, Mapping) and str(row.get("defect_key", "")):
                out.setdefault(str(row.get("defect_key")), str(row.get("finding_id")))
    return out


def _merge_by_defect(findings: Sequence[Mapping]) -> list[dict]:
    """One finding per defect, citing every capture that shows it.

    The same layout problem visible in six captures is one defect, not six. Reporting it
    six times inflates the count, makes severity statistics meaningless, and hands a
    repair planner six findings that are really one job. The captures are all kept, so
    nothing is lost -- the evidence widens while the finding stays single.
    """
    order: list[tuple] = []
    merged: dict[tuple, dict] = {}
    for row in findings or ():
        item = dict(row)
        key = (
            str(item.get("dimension", "")),
            str(item.get("severity", "")),
            str(item.get("expected_basis", "")),
            str(item.get("repair_scope", "")),
            str(item.get("viewport_width", "")),
        )
        if key not in merged:
            merged[key] = item
            order.append(key)
            continue
        existing = merged[key]
        cited = list(dict.fromkeys(
            [str(value) for value in (existing.get("capture_ids") or [])]
            + [str(value) for value in (item.get("capture_ids") or [])]
        ))
        existing["capture_ids"] = cited
        if len(str(item.get("observation", ""))) > len(str(existing.get("observation", ""))):
            existing["observation"] = str(item.get("observation", ""))
    return [merged[key] for key in order]


def deterministic_review(packet: Mapping) -> dict:
    """The default reviewer: only what a render can prove.

    Every finding here is reproducible from the captured runtime report, and every one
    is labelled ``DETERMINISTIC``. Nothing about hierarchy, density or "feel" appears,
    because this function cannot establish those and a finding it cannot establish is a
    finding it must not report.
    """
    findings: list[dict] = []
    coverage: dict[str, dict] = {}
    captures = [row for row in (packet.get("captures") or []) if isinstance(row, Mapping)]
    capture_ids = [str(row.get("capture_id", "")) for row in captures]
    for row in captures:
        capture_id = str(row.get("capture_id", ""))
        runtime = row.get("runtime_checks") if isinstance(row.get("runtime_checks"), Mapping) else {}
        checks = runtime.get("checks") if isinstance(runtime.get("checks"), list) else []
        by_check = {str(item.get("check", "")): item for item in checks if isinstance(item, Mapping)}
        overflow = by_check.get("horizontal-overflow", {})
        if not bool(overflow.get("passed", True)):
            elements = runtime.get("overflowing_elements") or []
            findings.append({
                "dimension": "responsiveness",
                "severity": "major",
                "basis": "DETERMINISTIC",
                "observation": (
                    f"at {capture_id} the document scrolls horizontally "
                    f"({overflow.get('detail', '')}); {len(elements)} element(s) extend past the "
                    "viewport's right edge"
                ),
                "expected_basis": str(DIRECTION_CLAIMS["responsive"]),
                "actual_evidence": str(overflow.get("detail", "")),
                "capture_ids": [capture_id],
                "materiality": ["responsive_structure", "primary_layout"],
                "repair_scope": "the stylesheet rule that sets the non-wrapping column",
                "repairability": "REPAIRABLE",
                "direction_principle_ids": [],
                "requirement_ids": [],
                "rationale_tags": ["responsive-structure"],
            })
        a11y = row.get("accessibility_checks") if isinstance(row.get("accessibility_checks"), Mapping) else {}
        for entry in (a11y.get("findings") or []):
            if not isinstance(entry, Mapping):
                continue
            check = str(entry.get("check", ""))
            if check == "focus-visible":
                findings.append({
                    "dimension": "accessibility",
                    "severity": "blocking",
                    "basis": "DETERMINISTIC",
                    "observation": str(entry.get("detail", "")),
                    "expected_basis": "every keyboard-reachable control shows a visible focus indicator",
                    "actual_evidence": str(entry.get("detail", "")),
                    "capture_ids": [capture_id],
                    "materiality": ["interaction_model"],
                    "repair_scope": "the focus-visible rule for the control",
                    "repairability": "REPAIRABLE",
                    "rationale_tags": ["focus-visibility"],
                })
            elif check == "accessible-name":
                findings.append({
                    "dimension": "accessibility",
                    "severity": "major",
                    "basis": "DETERMINISTIC",
                    "observation": str(entry.get("detail", "")),
                    "expected_basis": "every interactive control exposes an accessible name",
                    "actual_evidence": json.dumps(entry.get("samples", []), default=str)[:300],
                    "capture_ids": [capture_id],
                    "materiality": ["interaction_model"],
                    "repair_scope": "the missing accessible name on the named control",
                    "repairability": "REPAIRABLE",
                    "rationale_tags": ["accessible-name"],
                })
            elif check == "reduced-motion":
                findings.append({
                    "dimension": "motion",
                    "severity": "minor",
                    "basis": "DETERMINISTIC",
                    "observation": str(entry.get("detail", "")),
                    "expected_basis": "prefers-reduced-motion removes non-essential motion",
                    "actual_evidence": str(entry.get("detail", "")),
                    "capture_ids": [capture_id],
                    "materiality": ["motion_system"],
                    "repair_scope": "the transition declaration under the reduced-motion media query",
                    "repairability": "REPAIRABLE",
                    "rationale_tags": ["reduced-motion"],
                })
        errors = by_check.get("no-runtime-errors", {})
        if not bool(errors.get("passed", True)):
            findings.append({
                "dimension": "requirement-satisfaction",
                "severity": "blocking",
                "basis": "DETERMINISTIC",
                "observation": f"the page raised runtime errors at {capture_id}",
                "expected_basis": "the surface renders without runtime errors",
                "actual_evidence": str(errors.get("detail", ""))[:300],
                "capture_ids": [capture_id],
                "materiality": ["primary_layout"],
                "repair_scope": "the code path that raised",
                "repairability": "REPAIRABLE",
                "rationale_tags": ["runtime-error"],
            })
        clipping = by_check.get("content-within-viewport", {})
        if not bool(clipping.get("passed", True)):
            unreached = runtime.get("beyond_viewport") or runtime.get("clipped_elements") or []
            width = str(runtime.get("viewport_width", "?"))
            named = "; ".join(
                f"{item.get('tag', '?')}.{str(item.get('cls', '')).split(' ')[0]} "
                f"reaches {item.get('right', '?')}px in a {width}px viewport"
                for item in unreached[:3]
            )
            findings.append({
                "dimension": "responsiveness",
                "severity": "major",
                "basis": "DETERMINISTIC",
                "observation": (
                    f"at {capture_id} ({width}px) {len(unreached)} element(s) extend past the right "
                    f"edge of the viewport, so their content is not visible in the capture: {named}"
                ),
                "expected_basis": str(DIRECTION_CLAIMS["responsive"]),
                "actual_evidence": json.dumps(unreached[:4], default=str)[:400],
                "capture_ids": [capture_id],
                "viewport_width": width,
                "materiality": ["responsive_structure", "component_geometry"],
                "repair_scope": "the stylesheet rule that fixes the non-wrapping column at narrow widths",
                "repairability": "REPAIRABLE",
                "rationale_tags": ["responsive-structure"],
            })
        headings = runtime.get("headings") or []
        duplicates = _duplicate_headings(headings)
        if duplicates:
            findings.append({
                "dimension": "hierarchy",
                "severity": "minor",
                "basis": "DETERMINISTIC",
                "observation": (
                    f"at {capture_id} the text {', '.join(repr(item) for item in duplicates[:3])} "
                    "appears in more than one visible heading"
                ),
                "expected_basis": (
                    "each panel states its subject once; a panel header and an in-body heading "
                    "carrying identical text is a duplicated hierarchy signal"
                ),
                "actual_evidence": json.dumps(headings[:8], default=str)[:400],
                "capture_ids": [capture_id],
                "materiality": ["primary_layout"],
                "repair_scope": "the shell's panel heading structure",
                "repairability": "REPAIRABLE",
                "rationale_tags": ["duplicate-heading"],
            })
    merged = _merge_by_defect(findings)
    for row in merged:
        row["defect_key"] = _defect_key(row)
    for dimension in ("accessibility", "responsiveness"):
        related = [row for row in merged if str(row.get("dimension")) == dimension]
        if related:
            coverage[dimension] = {
                "state": "REVIEWED",
                "capture_ids": sorted({c for row in related for c in row["capture_ids"]}),
                "note": "judged from deterministic inspection of the rendered DOM at these viewports",
            }
        elif any(str((row.get("viewport") or {}).get("width", "")) != "1440" for row in captures):
            coverage[dimension] = {
                "state": "REVIEWED",
                "capture_ids": [str(row.get("capture_id")) for row in captures],
                "note": "inspected; no defect was established",
            }
        else:
            coverage[dimension] = {
                "state": "PARTIAL",
                "capture_ids": capture_ids,
                "note": "inspected at the primary viewport only",
            }
    coverage["motion"] = {
        "state": "REVIEWED" if any(row.get("reduced_motion") for row in captures) else "NOT_APPLICABLE",
        "capture_ids": [str(row.get("capture_id")) for row in captures if row.get("reduced_motion")],
        "note": "prefers-reduced-motion was emulated and captured" if any(
            row.get("reduced_motion") for row in captures
        ) else "the surface declares no motion, so reduced-motion behaviour has nothing to change",
    }
    coverage["reference-alignment"] = {
        "state": "PARTIAL",
        "capture_ids": capture_ids,
        "note": (
            "counter-reference presence was checked against the implementation bytes; satisfaction of the "
            "approved principles needs a judgement this deterministic reviewer does not make"
        ),
    }
    for dimension in ("hierarchy", "density", "typography", "composition"):
        coverage[dimension] = {
            "state": "NOT_REVIEWED",
            "capture_ids": [],
            "note": "a bounded qualitative judgement a deterministic reviewer must not fabricate",
        }
    return {
        "findings": merged,
        "coverage": coverage,
        "unknowns": [
            "whether the rendered hierarchy expresses the approved information hierarchy",
            "whether the density matches the approved rhythm",
            "whether the typography scale matches the approved scale",
            "whether the surface reads as one visual language rather than a collection of panels",
        ],
        "reviewer_kind": "deterministic",
        "basis": (
            "every finding is derived from the captured runtime and accessibility inspection report and is "
            "reproducible by re-running this function; no aesthetic judgement is asserted"
        ),
    }


def review_with(reviewer: Callable[[Mapping], Mapping]) -> dict:
    """Wrap a model or human reviewer so it receives the isolated packet unchanged.

    The point of the wrapper is that there is no *other* path. A reviewer that wanted
    the implementation source, the worker's rationale or the previous critique has no
    argument to make here, because :func:`critique_module.assert_isolated` runs on the
    packet before it is delivered and again on the critique record before it is stored.
    """
    def _run(packet: Mapping) -> dict:
        critique_module.assert_isolated(packet)
        return dict(reviewer(packet))
    return _run


def _counter_review(project: Path, binding: Mapping) -> dict:
    texts: dict[str, str] = {}
    for relative in source_module.relevant_files(project):
        path = project / relative
        if path.suffix.lower() in (".css", ".html", ".ts", ".tsx", ".js", ".json") and path.is_file():
            try:
                texts[relative] = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
    return critique_module.counter_reference_review([], source_texts=texts)


def _require_principle_binding(findings: Sequence[Mapping], principles: Sequence[Mapping]) -> list[dict]:
    """Attach the approved principle that authorises each repairable finding.

    A finding with no authorising principle cannot become a repair plan, and that is the
    intended outcome rather than a gap to paper over. The match is on the principle's
    category against the finding's rationale tag, which is deliberately coarse: it
    establishes *that* an approved principle speaks to this defect, not that it
    prescribes a particular fix.
    """
    by_category: dict[str, dict] = {}
    for row in principles:
        category = str(row.get("category", ""))
        if category and category not in by_category:
            by_category[category] = dict(row)
    tagged: list[dict] = []
    for row in findings:
        item = dict(row)
        # Read the tags, never pop them. The tags are what a repair plan later matches
        # against to decide which bounded edit applies, so consuming them here silently
        # leaves every repair with nothing to do.
        tags = [str(value) for value in (item.get("rationale_tags") or [])]
        bound: list[str] = []
        for tag in tags:
            prefix = str(tag).split("-")[0]
            match = by_category.get(tag) or by_category.get(prefix)
            if match:
                bound.append(str(match.get("principle_id", "")))
        existing = [str(value) for value in (item.get("direction_principle_ids") or [])]
        item["direction_principle_ids"] = list(dict.fromkeys(existing + bound))
        tagged.append(item)
    return tagged


def run(
    *,
    working_root: Path | None = None,
    validate: bool = True,
    reviewer: Callable[[Mapping], Mapping] | None = None,
    allow_hosts: Sequence[str] | None = None,
) -> dict:
    """The whole AR-222 vertical slice, from AR-221's result to a final verdict."""
    from ..design_execution import vertical_slice as ar221

    clock = time.monotonic()
    temporary = working_root is None
    run_root = Path(working_root) if working_root is not None else Path(tempfile.mkdtemp(prefix="ariadne-ar222-"))
    run_root.mkdir(parents=True, exist_ok=True)
    report: dict = {
        "request": SLICE_REQUEST,
        "steps": [],
        "failures": [],
        "repairs": [],
        "completed": False,
    }

    def step(name: str, detail: str, **extra: object) -> None:
        report["steps"].append({"step": name, "detail": detail, **extra})

    # -- 1. AR-221's result, untouched. This is the before state. --------------
    project = run_root / "beacon"
    upstream = ar221.run(working_root=project, validate=validate)
    report["ar221"] = {
        "outcome": upstream.get("outcome"),
        "completed": bool(upstream.get("completed")),
        "changes": sorted({str(row.get("path", "")) for row in (upstream.get("changes") or [])}),
        "acceptance": dict(upstream.get("acceptance") or {}),
        "verdicts": dict(upstream.get("verdicts") or {}),
    }
    if not upstream.get("completed"):
        report["outcome"] = "RENDER_VALIDATION_BLOCKED"
        report["failures"].append(
            "the AR-221 implementation did not complete, so there is nothing rendered to critique: "
            + "; ".join(str(item) for item in (upstream.get("failures") or ["unknown"]))
        )
        report["duration_seconds"] = round(time.monotonic() - clock, 3)
        report["working_root"] = str(run_root)
        return report
    state: dict = upstream["state"]
    state.setdefault("project", str(project))
    state.setdefault("run_root", str(run_root))
    direction_id = str((state.get("design_directions") or [{}])[-1].get("direction_id", ""))
    direction = next(
        (row for row in (state.get("design_directions") or []) if str(row.get("direction_id")) == direction_id),
        {},
    )
    implementation_plan_id = str((state.get("design_implementation_plans") or [{}])[-1].get("plan_id", ""))
    step("ar221-result", f"AR-221 produced {upstream.get('outcome')} at {project}")

    # -- 2. exact source binding for the implementation about to be rendered ---
    binding = source_module.bind(project)
    binding["project_root"] = str(project)
    report["source_binding"] = {
        "render_source_digest": binding["render_source_digest"],
        "source_commit": binding.get("source_commit", ""),
        "dirty": binding.get("dirty", False),
        "file_count": binding.get("file_count", 0),
        "tracked_diff_sha256": binding.get("tracked_diff_sha256", ""),
    }
    step("source-binding", source_module.describe(binding))

    # -- 3. a bounded, justified capture plan ---------------------------------
    capture_plan = build_plan(
        state, binding=binding, direction=direction, implementation_plan_id=implementation_plan_id,
        project=project,
    )
    report["capture_plan"] = {
        "capture_plan_id": capture_plan["capture_plan_id"],
        "targets": len(capture_plan["targets"]),
        "counts_by_kind": plan_module.counts(capture_plan),
        "budget": capture_plan["capture_budget"],
        "routes": capture_plan["routes"],
        "targets_detail": [
            {
                "target_id": row["target_id"], "kind": row["kind"], "route": row["route"],
                "state": row["state"], "viewport": row["viewport"],
                "basis": [str(item.get("basis")) for item in row["materiality_basis"]],
            }
            for row in capture_plan["targets"]
        ],
    }
    step("capture-plan", plan_module.describe(capture_plan))

    # -- 4. real browser rendering -------------------------------------------
    adapters = adapter_module.select_adapters(project, launch_command=["python", "--version"], allow_hosts=allow_hosts)
    render_adapter = adapters[adapter_module.ChromiumRenderAdapter.id]
    available, reason = render_adapter.available()
    report["render_capability"] = {
        "available": available,
        "reason": reason,
        "matrix": adapter_module.capability_matrix(adapters),
    }
    if not available:
        report["outcome"] = "RENDER_VALIDATION_BLOCKED"
        report["failures"] = [f"RENDER_CAPABILITY_UNAVAILABLE: {reason}"]
        step("render-blocked", reason)
        report["duration_seconds"] = round(time.monotonic() - clock, 3)
        report["working_root"] = str(run_root)
        return report
    surface = project / "dist"
    server = adapter_module.LocalServer(surface)
    base_url = server.start()
    step("surface-served", f"Beacon dist/ served at {base_url}")
    capabilities = _register_capability(state, render_adapter, base_url)
    report["capability_record"] = capabilities

    try:
        cycles: list[dict] = []
        current_source = project
        evidence_directory = run_root / "render-evidence"
        digest = str(binding["render_source_digest"])
        manifest = _render_cycle(
            state, capture_plan=capture_plan, adapter=render_adapter, binding=binding,
            directory=evidence_directory, base_url=base_url, project=current_source,
            allow_hosts=allow_hosts, cycle="before",
        )
        evidence_module.append(state, manifest)
        report["evidence_sets"] = [evidence_module.summary(manifest)]
        step("render-before", evidence_module.describe(manifest))

        # -- 5. independent critique of the render --------------------------
        reviewer_fn = review_with(reviewer) if reviewer is not None else deterministic_review
        cycle_number = 1
        critique_record, packets = _critique_cycle(
            state, manifest=manifest, direction=direction, direction_id=direction_id,
            reviewer=reviewer_fn, cycle=cycle_number,
            prior_evidence_set_id="",
        )
        # critique_module.build() appends the record itself; appending here as well would
        # store every critique twice and make every finding appear twice in triage.
        step("critique-1", critique_module.describe(critique_record))
        report["critiques"] = [critique_module.telemetry(critique_record)]
        report["critique_detail"] = [
            {
                "critique_id": critique_record["critique_id"],
                "overall_status": critique_record["overall_status"],
                "findings": critique_record["findings"],
                "coverage": critique_module.coverage_report(critique_record)["counts"],
                "isolation": critique_record["isolation"],
                "reference_alignment": critique_record["reference_alignment"],
                "counter_reference_review": critique_record["counter_reference_review"],
                "unknowns": critique_record["unknowns"],
            }
        ]

        # -- 6. bounded refinement, mechanical validation, re-render ---------
        attempt = 1
        while attempt <= refinement_module.MAX_REPAIR_ATTEMPTS:
            repairable = critique_module.open_findings(state, severity_at_least="minor")
            blocking = [
                row for row in repairable
                if str(row.get("repairability", "REPAIRABLE")) == "REPAIRABLE"
                and str(row.get("severity")) in ("blocking", "major", "minor")
                and str(row.get("direction_principle_ids") or [])
            ]
            if not blocking:
                report["refinement_decision"] = {
                    "attempt": attempt,
                    "decision": "NO_REPAIRABLE_FINDINGS",
                    "detail": (
                        "no open finding is both repairable and bound to an approved principle, so a "
                        "refinement plan could not be authorised"
                    ),
                }
                step("refinement-skipped", "no repairable, principle-bound finding")
                break
            plan_record = _plan_refinement(
                state, critique_record=critique_record, findings=blocking, project=project, attempt=attempt,
            )
            if plan_record is None:
                break
            report["refinement_decision"] = {
                "attempt": attempt,
                "decision": "PLAN_CREATED",
                "refinement_plan_id": plan_record["refinement_plan_id"],
                "finding_ids": plan_record["finding_ids"],
                "allowed_scope": plan_record["allowed_scope"],
                "authorising_principles": plan_record["authorising_principles"],
                "escalated_findings": plan_record["escalated_findings"],
            }
            worker_packet = refinement_module.packet(
                plan_record,
                captures=[row for row in (manifest.get("captures") or [])],
                changed_files=sorted(source_module.relevant_files(project)),
            )
            report.setdefault("repair_packets", []).append({
                "refinement_plan_id": plan_record["refinement_plan_id"],
                "context": worker_packet["context"],
                "captures_transported": worker_packet["context"]["captures_transported"],
            })
            applied = _apply_repair(state, plan_record, findings=blocking, project=project)
            report["repairs"].append(applied)
            step("repair-attempt", f"attempt {attempt}: {applied['summary']}")
            if not applied.get("applied"):
                # Nothing changed, so there is nothing to re-render and nothing to review.
                # Re-capturing here would produce a fresh evidence set bound to an unchanged
                # source digest, which looks like progress in a report and is not.
                report["refinement_decision"] = {
                    "attempt": attempt,
                    "decision": "NO_DERIVABLE_EDIT",
                    "detail": (
                        "the accepted findings remain open, but no bounded, scope-legal edit is derivable "
                        "for them; the remaining gaps need a decision this phase must not make"
                    ),
                    "refinement_plan_id": plan_record["refinement_plan_id"],
                    "open_finding_ids": [str(row.get("finding_id")) for row in blocking],
                }
                step("repair-not-derivable", applied["summary"])
                break
            validation = _validate(project, validate=validate)
            refinement_module.record_validation(
                state, plan_record["refinement_plan_id"],
                checks=validation["checks"], duration_seconds=validation["seconds"],
            )
            applied["validation"] = validation
            if validation["status"] != "PASSED":
                step("validation-failed", applied["summary"])
                attempt += 1
                continue
            new_binding = source_module.bind(project)
            new_binding["project_root"] = str(project)
            after = _render_cycle(
                state, capture_plan=capture_plan, adapter=render_adapter, binding=new_binding,
                directory=evidence_directory / f"attempt-{attempt}", base_url=base_url,
                project=project, allow_hosts=allow_hosts, cycle=f"after-{attempt}",
            )
            evidence_module.append(state, after)
            report["evidence_sets"].append(evidence_module.summary(after))
            refinement_module.mark_rerendered(
                state, plan_record["refinement_plan_id"],
                evidence_set_id=str(after["evidence_set_id"]),
                render_source_digest=str(new_binding["render_source_digest"]),
            )
            step("re-render", evidence_module.describe(after))
            re_critique, _ = _critique_cycle(
                state, manifest=after, direction=direction, direction_id=direction_id,
                reviewer=reviewer_fn, cycle=attempt + 1,
                prior_evidence_set_id=str(critique_record["critique_id"]),
                implementing_execution=str(refinement_module.by_id(
                    state, plan_record["refinement_plan_id"]
                ).get("repair_execution", "")),
                prior_findings=_known_defect_keys(state),
            )
            report["critiques"].append(critique_module.telemetry(re_critique))
            report["critique_detail"].append({
                "critique_id": re_critique["critique_id"],
                "cycle": attempt + 1,
                "overall_status": re_critique["overall_status"],
                "findings": re_critique["findings"],
                "coverage": critique_module.coverage_report(re_critique)["counts"],
            })
            resolution = _close_cycle(
                state, plan_record=plan_record, re_critique=re_critique, before=critique_record,
            )
            applied["resolution"] = resolution
            critique_record = re_critique
            cycles.append({"attempt": attempt, "evidence_set_id": after["evidence_set_id"], **resolution})
            attempt += 1
            if attempt > refinement_module.MAX_REPAIR_ATTEMPTS:
                report["refinement_decision"] = {
                    "attempt": attempt - 1,
                    "decision": "REPAIR_LIMIT_EXHAUSTED",
                    "detail": refinement_module.repair_budget(state, critique_id=critique_record["critique_id"])["reason"],
                }
                step("repair-limit", "the bounded repair allowance is spent; a human decides next")
                break

        # -- 7. final state, trace and economics -----------------------------
        final = refinement_module.summary(state)
        report["rendered_state"] = final
        rendered_trace = trace_module.build(
            requirements=_requirements(state),
            principles=_principles(direction),
            direction=direction,
            files=sorted({str(row.get("path", "")) for row in (upstream.get("changes") or [])}),
            manifests=evidence_module.evidence_sets(state),
            critiques=critique_module.critiques(state),
            plans=refinement_module.plans(state),
        )
        report["trace"] = rendered_trace
        report["trace_summary"] = trace_module.summarise(rendered_trace)
        report["design_explanation"] = critique_module.design_explanation(critique_record)
        report["acceptance"] = _acceptance(state, critique_record)
        report["capture_economics"] = _economics(state, capture_plan)
        report["cycles"] = cycles
        report["outcome"] = final["final_status"]
        report["completed"] = True
        step("final", f"render status {final['final_status']}")
    finally:
        server.shutdown()
    report["duration_seconds"] = round(time.monotonic() - clock, 3)
    report["working_root"] = str(run_root)
    report["temporary"] = temporary
    return report


def _register_capability(state: Mapping, adapter: adapter_module.RenderAdapter, base_url: str) -> dict:
    """Record the rendering capability in the engine's existing registry.

    Uses :mod:`ariadne_engine.capabilities` rather than a private list, so the browser
    becomes a first-class capability with the same evidence obligations as everything
    else -- and so ``RENDER_CAPABILITY_UNAVAILABLE`` in one run is visible to a later
    one instead of being rediscovered from scratch.

    The evidence is a probe artifact on disk rather than the URL, because the registry
    re-hashes whatever it is given and a URL is not a file. A capability claim backed
    by something the engine cannot re-read is a declaration, and declarations stop at
    ``DECLARED``.
    """
    import hashlib

    from .. import capabilities

    probe = adapter.probe()
    probe_dir = Path(str(state.get("run_root", "."))) / "capability-probes"
    probe_dir.mkdir(parents=True, exist_ok=True)
    probe_path = probe_dir / "browser-render-probe.json"
    payload = (
        json.dumps(
            {"probe": probe.as_record(), "surface": base_url, "probed_at": contracts.utc_now()},
            indent=2, sort_keys=True, default=str,
        ) + "\n"
    ).encode("utf-8")
    # write_bytes, not write_text: on Windows a text write translates "\n" to "\r\n", so
    # the bytes on disk would not be the bytes the registry is about to re-hash.
    probe_path.write_bytes(payload)
    probe_row = capabilities.observe(
        state,
        capability_id="browser-render",
        adapter=probe.adapter,
        family="capture",
        status="EXERCISED" if probe.available else "UNAVAILABLE",
        mechanism=f"probe:{probe.mechanism.split(':', 1)[-1]}" if probe.available else probe.mechanism,
        reason=probe.reason,
        evidence=[{"path": str(probe_path), "sha256": hashlib.sha256(payload).hexdigest()}]
        if probe.available else [],
        fingerprint=str(probe.extra.get("browser_executable", "")),
        runtime=probe.engine,
        observed_by="engine-render",
    )
    return dict(probe_row)


def _render_cycle(
    state: Mapping, *, capture_plan: Mapping, adapter: adapter_module.RenderAdapter, binding: Mapping,
    directory: Path, base_url: str, project: Path, allow_hosts: Sequence[str] | None, cycle: str,
) -> dict:
    adapter.launch()
    try:
        return evidence_module.execute(
            capture_plan, adapter=adapter, binding=binding, directory=directory,
            base_url=base_url, allow_hosts=allow_hosts,
            capture_execution=str(state.get("run_id", "")),
            expected_content={ROUTE: ("Beacon", "Request")},
        )
    finally:
        adapter.shutdown()


def _critique_cycle(
    state: Mapping, *, manifest: Mapping, direction: Mapping, direction_id: str,
    reviewer: Callable[[Mapping], Mapping], cycle: int, prior_evidence_set_id: str,
    implementing_execution: str = "", prior_findings: Mapping[str, str] | None = None,
) -> tuple[dict, dict]:
    """Build the isolated packet, run the reviewer, and record the critique.

    The packet is asserted isolated on the way in *and* the resulting record is validated
    on the way out, because the two ends of a boundary are both places it can be
    crossed: a caller can smuggle a field into the packet, or can write a record
    claiming isolation it did not have.

    ``implementing_execution`` is the execution that produced the render under review. On
    a re-review cycle that must be the repair's own execution -- the closure check in
    :func:`refinement.resolve` refuses to let a re-review of an unrelated revision close
    a finding, so passing a fresh id here would (correctly) fail.
    """
    principles = _principles(direction)
    requirements = _requirements(state)
    packet = critique_module.reviewer_packet(
        task_id=str(state.get("run_id", "")),
        requirements=requirements or [{"requirement_id": "req_slice", "statement": "the workspace shell renders the approved structure"}],
        direction=direction,
        principles=principles,
        reference_decisions={
            "borrow": "structure and restraint from the approved reference analysis",
            "adapt": "the reference's information density, expressed in Beacon's own identity",
            "avoid": "the counter-reference's surface treatments",
        },
        manifest=manifest,
        captures=[row for row in (manifest.get("captures") or [])],
    )
    critique_module.assert_isolated(packet)
    judged = reviewer(packet)
    findings = _require_principle_binding(judged.get("findings") or [], principles)
    _reuse_finding_ids(findings, prior_findings or {})
    reviewer_execution = _execution(state, "reviewer", cycle=cycle)
    implementer = str(implementing_execution or "") or _execution(state, "implementer", cycle=cycle)
    reviewer_identity = f"independent-rendered-reviewer@{state.get('run_id', 'run')}"
    _note_implementing_worker(state, implementer)
    record = critique_module.build(
        state,
        task_id=str(state.get("run_id", "")),
        direction_id=direction_id,
        manifest=manifest,
        findings=findings,
        reviewer_identity=reviewer_identity,
        reviewer_execution=reviewer_execution,
        implementing_execution=implementer,
        coverage=judged.get("coverage") or {},
        requirement_ids=[str(row.get("requirement_id", "")) for row in requirements],
        capture_ids=[str(row.get("capture_id", "")) for row in (manifest.get("captures") or [])],
        principles=principles,
        reference_decisions={"borrow": "approved structure", "adapt": "project identity", "avoid": "counter-reference surfaces"},
        counter_review=_counter_review_cached(state, manifest),
        unknowns=judged.get("unknowns") or (),
        verdict=str(judged.get("overall_status", "")) if judged.get("overall_status") else "",
        run_from=[prior_evidence_set_id] if prior_evidence_set_id else [],
    )
    return record, packet


_COUNTER_CACHE: dict[str, dict] = {}


def _counter_review_cached(state: Mapping, manifest: Mapping) -> dict:
    digest = str(manifest.get("render_source_digest", ""))
    if digest not in _COUNTER_CACHE:
        root = Path(str(state.get("project", ".")))
        _COUNTER_CACHE[digest] = _counter_review(root, {}) if root.is_dir() else {
            "mechanically_checked": [], "requires_visual_judgement": [],
            "limitation": "the rendered project root is not readable, so no counter-pattern check ran",
        }
    return dict(_COUNTER_CACHE[digest])


def _note_implementing_worker(state: dict, implementing_execution: str) -> None:
    """Register the implementing side as a worker identity.

    :func:`ariadne_engine.review.independence_problems` refuses a reviewer whose
    identity matches a recorded worker identity. Registering the implementer here is
    what makes the reviewer-identity half of that check bite in this slice rather than
    passing vacuously.
    """
    worker = state.setdefault("worker", {})
    worker.setdefault("identity", "ar221-beacon-implementation-worker")
    worker.setdefault("worker_role", "grounded-implementation-worker")
    worker["implementing_execution"] = str(implementing_execution)


def _execution(state: Mapping, role: str, *, cycle: int = 1) -> str:
    """Create a real engine execution record, so independence is a fact not a label.

    :func:`ariadne_engine.review.independence_problems` requires both executions to
    resolve to engine-created records in this run. A hard-coded id would be refused, and
    rightly so -- two strings that differ are not two executions.
    """
    from .. import api

    record = api.create_execution(
        state,
        task_id=str(state.get("run_id", "")),
        role="reviewer" if role == "reviewer" else "implementer",
        adapter="ariadne-engine",
        invocation=f"ar222-{role}-cycle-{cycle}",
    )
    return str(record.get("execution_id", ""))


def _plan_refinement(state: Mapping, *, critique_record: Mapping, findings: Sequence[Mapping],
                    project: Path, attempt: int) -> dict | None:
    """Compile findings into a bounded plan, or report honestly why none is possible."""
    authorising: list[dict] = []
    seen: set[str] = set()
    for row in findings:
        for principle_id in (row.get("direction_principle_ids") or []):
            key = str(principle_id)
            if key in seen:
                continue
            seen.add(key)
            principle = _principle_by_id(critique_record, key)
            if principle:
                authorising.append({
                    "principle_id": key,
                    "statement": str(principle.get("statement", "")),
                    "direction_id": str(critique_record.get("direction_id", "")),
                })
    if not authorising:
        return None
    scopes: list[str] = []
    for row in findings:
        for item in _scope_candidates(project, row):
            if item not in scopes:
                scopes.append(item)
    if not scopes:
        return None
    try:
        return refinement_module.plan(
            state,
            critique_id=str(critique_record.get("critique_id", "")),
            finding_ids=[str(row.get("finding_id", "")) for row in findings],
            allowed_scope=scopes,
            required_outcomes=[
                str(row.get("expected_basis", "")) for row in findings if row.get("expected_basis")
            ] or ["the rendered defect is no longer observable at the same viewport"],
            validation=["npm run typecheck", "npm run build", "npm test"],
            authorising_principles=authorising,
            attempt=attempt,
        )
    except ContractError:
        return None


def _principle_by_id(critique_record: Mapping, principle_id: str) -> dict:
    for row in (critique_record.get("reference_alignment") or {}).get("principles", []):
        if isinstance(row, Mapping) and str(row.get("principle_id")) == principle_id:
            return dict(row)
    return {}


def _scope_candidates(project: Path, finding: Mapping) -> list[str]:
    """Which project files could carry the fix for this finding.

    Narrow on purpose. A plan's allowed scope is a list of specific files, so a repair
    worker cannot drift into the design system while chasing a focus ring.
    """
    tags = {str(value) for value in (finding.get("rationale_tags") or [])}
    if not tags:
        tags = {str(finding.get("dimension", ""))}
    candidates: list[str] = []
    stylesheet = project / "src" / "styles" / "app.css"
    if stylesheet.is_file():
        candidates.append("src/styles/app.css")
    for tag in sorted(tags):
        lowered = tag.lower()
        if "focus" in lowered or "accessible" in lowered or "target" in lowered or "motion" in lowered:
            if stylesheet.is_file():
                candidates.append("src/styles/app.css")
        if "responsive" in lowered or "overflow" in lowered:
            if stylesheet.is_file():
                candidates.append("src/styles/app.css")
    ordered: list[str] = []
    for item in candidates:
        if item not in ordered:
            ordered.append(item)
    return ordered


def _apply_repair(state: Mapping, plan_record: Mapping, *, findings: Sequence[Mapping], project: Path) -> dict:
    """Perform the bounded repair through the ordinary implementation machinery.

    There is no magic CSS-repair function here. The worker edits an allowed file with
    an ordinary edit and AR-221's :class:`ValidationRunner` re-runs the declared
    commands; what this function adds is the *record* of who changed what, under which
    plan, so the change is attributable and its scope is checkable.
    """
    from ..design_execution import execution as execution_module

    repair_execution = _execution(state, "implementer", cycle=int(plan_record.get("attempt", 1)) + 100)
    refinement_module.mark_started(state, plan_record["refinement_plan_id"], execution=repair_execution)
    stylesheet = project / "src" / "styles" / "app.css"
    original = stylesheet.read_text(encoding="utf-8") if stylesheet.is_file() else ""
    updated, applied, notes = _repair_text(original, findings)
    if not applied:
        record = refinement_module.by_id(state, plan_record["refinement_plan_id"])
        if record is not None:
            record["status"] = "REJECTED"
            record["notes"] = "no deterministic edit was derivable for the accepted findings"
        return {
            "refinement_plan_id": plan_record["refinement_plan_id"],
            "attempt": plan_record.get("attempt"),
            "changed_files": [],
            "applied": False,
            "summary": "no bounded edit was derivable; nothing was changed",
            "notes": notes,
        }
    stylesheet.write_text(updated, encoding="utf-8")
    changed = ["src/styles/app.css"]
    refinement_module.record_change(
        state, plan_record["refinement_plan_id"],
        execution=repair_execution, changed_files=changed, notes="; ".join(notes),
    )
    return {
        "refinement_plan_id": plan_record["refinement_plan_id"],
        "attempt": plan_record.get("attempt"),
        "changed_files": changed,
        "applied": True,
        "repair_execution": repair_execution,
        "summary": "; ".join(notes),
        "notes": notes,
        "before_bytes": len(original),
        "after_bytes": len(updated),
    }


def _repair_text(css: str, findings: Sequence[Mapping]) -> tuple[str, list[str], list[str]]:
    """Derive a minimal, bounded stylesheet repair from the accepted findings.

    Bounded on purpose in three ways. Only rules named by the findings are touched;
    nothing is restyled "while we are here"; and every edit records which finding it
    serves, so the closing re-review can tell a fix from a coincidence.
    """
    updated = css
    applied: list[str] = []
    notes: list[str] = []
    tags = {str(value) for row in findings for value in (row.get("rationale_tags") or [])}
    if "focus-visibility" in tags and ":focus-visible" not in updated:
        updated += (
            "\n/* AR-222 repair: focus visibility is an accessibility floor (finding: focus ring absent). */\n"
            ".btn:focus-visible,\n"
            ".nav-item:focus-visible,\n"
            ".icon-btn:focus-visible,\n"
            "a:focus-visible,\n"
            "button:focus-visible {\n"
            "  outline: 2px solid var(--accent);\n"
            "  outline-offset: 2px;\n"
            "}\n"
        )
        applied.append("focus-visible outline rule")
        notes.append("added a focus-visible outline to the interactive controls the finding named")
    if "responsive-structure" in tags:
        if NARROW_MARKER not in updated:
            updated += (
                "\n/* AR-222 repair: the workspace must reach its content at narrow widths.\n"
                "   Two things have to be released together. Collapsing the columns alone is not\n"
                "   enough, because the shell also pins grid-template-rows to 100% -- with one\n"
                "   column and a single fixed-height row the workspace overflows out of the box and\n"
                "   the capture shows nothing but the navigation rail. So both the columns and the\n"
                "   row height are set to auto here, and the log table is allowed to wrap rather\n"
                "   than be cut off at the viewport edge. */\n"
                "@media (max-width: 720px) {\n"
                "  /* AR-222: narrow-workspace -- stack instead of pushing content past the edge. */\n"
                "  .app {\n"
                "    grid-template-columns: minmax(0, 1fr);\n"
                "    grid-template-rows: auto;\n"
                "  }\n"
                "  .nav {\n"
                "    flex-direction: row;\n"
                "    flex-wrap: wrap;\n"
                "  }\n"
                "  .workspace {\n"
                "    grid-template-columns: minmax(0, 1fr);\n"
                "  }\n"
                "  .panel__body {\n"
                "    overflow-x: auto;\n"
                "  }\n"
                "  .log-table {\n"
                "    min-width: 0;\n"
                "    width: 100%;\n"
                "    font-size: var(--text-xs);\n"
                "  }\n"
                "  .log-table th,\n"
                "  .log-table td {\n"
                "    white-space: nowrap;\n"
                "  }\n"
                "  /* The time column is the widest and the least load-bearing, so it yields\n"
                "     the space first. Truncating a timestamp beats splitting one across two\n"
                "     lines, which is what a global word-break produces. */\n"
                "  .log-table th:first-child,\n"
                "  .log-table td:first-child {\n"
                "    max-width: 5.5em;\n"
                "    overflow: hidden;\n"
                "    text-overflow: ellipsis;\n"
                "    white-space: nowrap;\n"
                "  }\n"
                "}\n"
            )
            applied.append("narrow-viewport workspace rule")
            notes.append(
                "released the fixed column and the pinned row height at <=720px so the workspace stacks "
                "and the log table's columns stop being cut off at the viewport edge"
            )
    if "reduced-motion" in tags and "@media (prefers-reduced-motion: reduce)" not in updated:
            updated += (
                "\n/* AR-222 repair: honour the reduced-motion preference (finding: motion under reduce). */\n"
                "@media (prefers-reduced-motion: reduce) {\n"
                "  *,\n"
                "  *::before,\n"
                "  *::after {\n"
                "    transition-duration: 0.01ms !important;\n"
                "    animation-duration: 0.01ms !important;\n"
                "  }\n"
                "}\n"
            )
            applied.append("reduced-motion media query")
            notes.append("added the reduced-motion media query so the preference is honoured")
    return updated, applied, notes


def _validate(project: Path, *, validate: bool) -> dict:
    if not validate:
        return {"status": "BLOCKED", "checks": [], "seconds": 0.0,
                "note": "mechanical validation was not run, so no re-render is authorised"}
    from ..design_execution import execution as execution_module

    runner = execution_module.ValidationRunner(project=project)
    clock = time.monotonic()
    result = runner.run([
        {"command": "npm run typecheck", "required": True},
        {"command": "npm run build", "required": True},
        {"command": "npm test", "required": True},
    ])
    return {
        "status": result["status"],
        "checks": [
            {"command": str(row.get("command", "")), "status": str(row.get("status", "")),
             "required": bool(row.get("required", True))}
            for row in (result.get("checks") or [])
        ],
        "seconds": round(time.monotonic() - clock, 3),
    }


def _close_cycle(state: Mapping, *, plan_record: Mapping, re_critique: Mapping, before: Mapping) -> dict:
    """Close from the independent re-review, reporting resolved / persistent / new."""
    before_findings = {
        str(row.get("finding_id", "")): dict(row) for row in (before.get("findings") or [])
    }
    after_findings = {str(row.get("finding_id", "")) for row in (re_critique.get("findings") or [])}
    targeted = [str(item) for item in (plan_record.get("finding_ids") or [])]
    resolved: list[str] = []
    persistent: list[str] = []
    for finding_id in targeted:
        still = critique_module.finding(state, finding_id)
        if still is not None and str(still.get("state")) in ("OPEN", "REPAIRED_CANDIDATE", "ACCEPTED_FOR_REPAIR"):
            if finding_id in after_findings:
                persistent.append(finding_id)
            else:
                resolved.append(finding_id)
    new_ids = [finding_id for finding_id in after_findings if finding_id not in before_findings]
    if resolved or persistent or new_ids:
        refinement_module.resolve(
            state,
            refinement_plan_id=str(plan_record.get("refinement_plan_id", "")),
            re_critique_id=str(re_critique.get("critique_id", "")),
            resolved=resolved, still_present=persistent, new_findings=new_ids,
        )
    return {
        "resolved": resolved,
        "persistent": persistent,
        "new": new_ids,
        "note": (
            "the closing re-review inspected the whole affected capture set, not only the region the "
            "repair touched, because a repair can fix one finding and introduce another"
        ),
    }


def _acceptance(state: Mapping, critique_record: Mapping) -> dict:
    """The visual-acceptance claim, bound to the critique that established it.

    AR-221 recorded ``NOT_CLAIMED`` with a reason. AR-222 can record
    ``VERIFIED_BY_RENDERED_CHECK`` -- but only naming the critique, and only when that
    critique found nothing material. A render with known findings is *reviewed*, not
    *accepted*, and this phase does not grant the human acceptance gate.
    """
    status = str(critique_record.get("overall_status", ""))
    findings = critique_module.open_findings(state, severity_at_least="minor")
    if status == "RENDERED_DIRECTION_CONFORMANT" and not findings:
        return {
            "visual_acceptance": "VERIFIED_BY_RENDERED_CHECK",
            "rendered_check_id": str(critique_record.get("critique_id", "")),
            "reason": (
                "an independent critique of fresh rendered evidence, bound to the exact source digest, "
                "found no material finding against the approved direction"
            ),
            "human_acceptance": "NOT_GRANTED",
            "note": (
                "rendered critique contributes to REVIEWED. The human acceptance gate is unchanged and "
                "this phase does not forge it."
            ),
        }
    return {
        "visual_acceptance": "NOT_CLAIMED",
        "reason": (
            f"the rendered review concluded {status or 'RENDER_VALIDATION_BLOCKED'}; "
            f"{len(findings)} finding(s) remain open, so no visual acceptance is claimed"
        ),
        "human_acceptance": "NOT_GRANTED",
        "rendered_check_id": str(critique_record.get("critique_id", "")),
    }


def _economics(state: Mapping, capture_plan: Mapping) -> dict:
    rows = evidence_module.evidence_sets(state)
    total_bytes = sum(int(row.get("capture_bytes", 0) or 0) for row in rows)
    durations = [float(row.get("duration_seconds", 0) or 0) for row in rows]
    critiques = critique_module.critiques(state)
    capture_ids = {
        str(capture.get("capture_id", "")) for row in rows for capture in (row.get("captures") or [])
        if isinstance(capture, Mapping)
    }
    return {
        "planned_captures": len(capture_plan.get("targets") or []),
        "actual_captures": len(capture_ids),
        "capture_bytes": total_bytes,
        "capture_seconds": round(sum(durations), 3),
        "cycles": len(rows),
        "critique_evidence_bytes": sum(
            len(json.dumps(row.get("captures", []), default=str).encode("utf-8")) for row in rows
        ),
        "curated_for_review": evidence_module.curate(rows[-1] if rows else {"captures": []}),
        "mechanical_validation_seconds": round(
            sum(float(row.get("validation_seconds", 0) or 0) for row in refinement_module.plans(state)), 3
        ),
        "note": (
            "bytes and durations are measured. No quality score is produced from them: a cheap run is "
            "not a good run."
        ),
    }


def describe(report: Mapping) -> str:
    return (
        f"AR-222 slice {report.get('outcome')} with {len(report.get('repairs') or [])} repair attempt(s) "
        f"in {report.get('duration_seconds', 0)}s"
    )


__all__ = [
    "SLICE_REQUEST",
    "ROUTE",
    "SURFACE",
    "DIRECTION_CLAIMS",
    "deterministic_review",
    "review_with",
    "build_plan",
    "run",
    "describe",
]
