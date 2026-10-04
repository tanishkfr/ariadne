"""Bounded capture planning (AR-222).

The instinct behind a visual QA tool is to screenshot everything: every route, every
viewport, every hover state, light and dark. That produces fifty images, and a
reviewer who looks at fifty images finds nothing, because there is no longer any
question the images are asking.

So a plan here has to *justify* itself per target. Each target names a basis drawn
from :data:`ariadne_engine.contracts.CAPTURE_TARGET_BASES`:

``REQUIREMENT``            a requirement says this surface must be seen
``DIRECTION_PRINCIPLE``    an approved principle is only checkable on this surface
``MATERIALITY``            the surface carries a material category that can break
``REGRESSION``             a prior finding means a re-capture of this exact state

A target with no basis is refused. That is the entire anti-matrix mechanism, and it
is enforced in the contract validator as well as here, because a plan built by a
caller that skipped this function must not be able to smuggle in a capture nobody
asked for.

The budget in :data:`ariadne_engine.contracts.DEFAULT_CAPTURE_BUDGET` bounds capture
*economics*, not capture *possibility*. Exceeding a default is allowed with a
recorded reason, because the task may genuinely need it; exceeding one silently is
not, because then the bound is decoration.
"""

from __future__ import annotations

from pathlib import Path
from typing import Mapping, Sequence

from .. import contracts
from ..contracts import (
    CAPTURE_TARGET_BASES,
    CAPTURE_TARGET_KINDS,
    DEFAULT_CAPTURE_BUDGET,
    ContractError,
)

PRIMARY_VIEWPORT = {"width": 1440, "height": 900}
"""The default primary desktop viewport. A number, not a standard: the plan records
what it used and why, so a different number needs no permission."""


def _target(
    *,
    kind: str,
    route: str,
    state: str,
    viewport: Mapping,
    basis: Sequence[Mapping],
    theme: str = "project-default",
    interaction: Mapping | None = None,
    reduced_motion: bool = False,
    required_regions: Sequence[str] = (),
    notes: str = "",
) -> dict:
    if kind not in CAPTURE_TARGET_KINDS:
        raise ContractError(f"unsupported capture target kind: {kind!r}")
    rows: list[dict] = []
    for entry in basis or ():
        value = entry.get("basis") if isinstance(entry, Mapping) else str(entry)
        reason = entry.get("reason") if isinstance(entry, Mapping) else ""
        if value not in CAPTURE_TARGET_BASES:
            raise ContractError(f"unsupported capture materiality basis: {value!r}")
        rows.append({"basis": str(value), "reason": str(reason or "")})
    if not rows:
        raise ContractError(
            "a capture target must name why it exists; a screenshot nobody asked for is not "
            "rendered evidence, it is clutter with a timestamp"
        )
    return {
        "target_id": contracts.new_record_id("rct"),
        "kind": kind,
        "route": str(route),
        "state": str(state),
        "viewport": dict(viewport),
        "theme": str(theme),
        "interaction": dict(interaction or {}),
        "reduced_motion": bool(reduced_motion),
        "required_regions": [str(item) for item in (required_regions or ())],
        "materiality_basis": rows,
        "notes": str(notes),
    }


def viewport_state(
    *,
    route: str,
    state: str = "default",
    viewport: Mapping | None = None,
    basis: Sequence[Mapping],
    theme: str = "project-default",
    required_regions: Sequence[str] = (),
    notes: str = "",
) -> dict:
    return _target(
        kind="viewport-state", route=route, state=state, viewport=viewport or PRIMARY_VIEWPORT,
        basis=basis, theme=theme, required_regions=required_regions, notes=notes,
    )


def interaction_state(
    *,
    route: str,
    state: str,
    action: Mapping,
    basis: Sequence[Mapping],
    viewport: Mapping | None = None,
    theme: str = "project-default",
    required_regions: Sequence[str] = (),
    notes: str = "",
) -> dict:
    if not str(action.get("kind", "")).strip():
        raise ContractError(
            "an interaction capture must name the action that produces the state; a declared state "
            "nobody performed is a source declaration wearing a capture's name"
        )
    return _target(
        kind="interaction-state", route=route, state=state, viewport=viewport or PRIMARY_VIEWPORT,
        basis=basis, theme=theme, interaction=action, required_regions=required_regions, notes=notes,
    )


def responsive_state(
    *,
    route: str,
    viewport: Mapping,
    state: str = "default",
    basis: Sequence[Mapping],
    theme: str = "project-default",
    required_regions: Sequence[str] = (),
    notes: str = "",
) -> dict:
    return _target(
        kind="responsive-state", route=route, state=state, viewport=viewport,
        basis=basis, theme=theme, required_regions=required_regions, notes=notes,
    )


def theme_variant(
    *,
    route: str,
    theme: str,
    basis: Sequence[Mapping],
    viewport: Mapping | None = None,
    state: str = "default",
    required_regions: Sequence[str] = (),
    notes: str = "",
) -> dict:
    return _target(
        kind="theme-variant", route=route, state=state, viewport=viewport or PRIMARY_VIEWPORT,
        basis=basis, theme=theme, required_regions=required_regions, notes=notes,
    )


def responsive_viewports(direction: Mapping, implementation: Mapping | None = None) -> list[dict]:
    """The viewports this surface actually needs, derived -- not a default ladder.

    A desktop-only tool does not need three widths. The decision is made from what
    the approved direction claims about the surface plus what the implementation
    declares about its own breakpoints, and the basis is recorded either way. Guessing
    a responsive ladder for a desktop-only product spends capture budget proving
    nothing.
    """
    claims_ = direction.get("claims")
    claim_text = []
    if isinstance(claims_, Mapping):
        # Keys count as much as values: a claim *labelled* responsive is a responsive
        # claim even when its prose avoids the word, which is the common case.
        claim_text.extend(str(key).lower() for key in claims_.keys())
        claim_text.extend(str(value).lower() for value in claims_.values() if isinstance(value, str))
    else:
        claim_text.append(str(claims_ or "").lower())
    claim_text.extend(str(item).lower() for item in direction.get("principles", []) or [])
    claims = " ".join(claim_text)
    responsive_claimed = any(
        token in claims for token in ("responsive", "mobile", "narrow", "breakpoint", "phone", "tablet")
    )
    implementation = dict(implementation or {})
    breakpoints = [int(item) for item in implementation.get("breakpoints", []) or [] if str(item).strip().isdigit()]
    if not responsive_claimed and not breakpoints:
        return []
    widths: list[int] = []
    if responsive_claimed:
        widths.extend([PRIMARY_VIEWPORT["width"], 1024, 390])
    elif breakpoints:
        widths.append(PRIMARY_VIEWPORT["width"])
        widths.extend(sorted(breakpoints)[:2])
    ordered: list[int] = []
    for width in widths:
        if width not in ordered:
            ordered.append(width)
    return [
        {"width": width, "height": 900 if width >= 1024 else 844}
        for width in ordered
    ]


def capture_budget(
    overrides: Mapping | None = None, expansions: Sequence[Mapping] | None = None
) -> dict:
    budget = dict(DEFAULT_CAPTURE_BUDGET)
    for name, value in dict(overrides or {}).items():
        if name not in DEFAULT_CAPTURE_BUDGET:
            raise ContractError(f"unknown capture budget axis: {name!r}")
        try:
            budget[name] = int(value)
        except (TypeError, ValueError) as exc:
            raise ContractError(f"capture budget axis {name} is not a count") from exc
    budget["expansions"] = [
        {"name": str(item.get("name", "")), "reason": str(item.get("reason", ""))}
        for item in (expansions or [])
    ]
    return budget


def create(
    *,
    implementation_plan_id: str,
    direction_id: str,
    binding: Mapping,
    target_surface: str,
    launch_command: Sequence[str],
    targets: Sequence[Mapping],
    browser_requirements: Mapping | None = None,
    budget: Mapping | None = None,
    required_evidence: Sequence[str] = (),
    notes: str = "",
) -> dict:
    """Assemble one bounded capture plan and validate it before anything launches.

    Validating here rather than at capture time is deliberate: a plan that would
    exceed its budget or capture an unjustified state should fail while it is still a
    plan, not after a browser has spent four minutes producing images nobody will use.
    """
    if not implementation_plan_id:
        raise ContractError("a capture plan must name the implementation plan it renders")
    if not direction_id:
        raise ContractError("a capture plan must name the approved direction it checks against")
    digest = str(binding.get("render_source_digest", ""))
    if not contracts._is_sha256(digest):
        raise ContractError(
            "a capture plan must be bound to the exact implementation it renders; without a "
            "render source digest the captures would describe nothing in particular"
        )
    argv = [str(item) for item in (launch_command or [])]
    if not argv:
        raise ContractError("a capture plan must name the command that brings the surface up")
    rows = [dict(target) for target in targets or ()]
    if not rows:
        raise ContractError(
            "a capture plan with no targets captures nothing; if the surface cannot be rendered, "
            "record that as a blocker rather than an empty plan"
        )
    record = {
        "schema_version": contracts.SCHEMA_DESIGN,
        "capture_plan_id": contracts.new_record_id("rcp"),
        "run_id": str(binding.get("run_id", "")),
        "task_id": str(binding.get("task_id", "")),
        "implementation_plan_id": str(implementation_plan_id),
        "direction_id": str(direction_id),
        "render_source_digest": digest,
        "source_binding": {
            "source_commit": str(binding.get("source_commit", "")),
            "dirty": bool(binding.get("dirty", False)),
            "tracked_diff_sha256": str(binding.get("tracked_diff_sha256", "")),
            "file_count": int(binding.get("file_count", 0)),
            "build_identity": dict(binding.get("build_identity", {}) or {}),
        },
        "target_surface": str(target_surface),
        "launch_command": argv,
        "routes": sorted({str(row.get("route", "")) for row in rows}),
        "targets": rows,
        "required_evidence": [str(item) for item in (required_evidence or ())],
        "browser_requirements": dict(browser_requirements or {}),
        "capture_budget": dict(budget or capture_budget()),
        "status": "PLANNED",
        "notes": str(notes),
        "recorded_at": contracts.utc_now(),
        "provenance": {"created_by": "engine", "policy_version": contracts.POLICY_VERSION},
    }
    problems = contracts.render_capture_plan_problems(record)
    if problems:
        raise ContractError("capture plan is not admissible: " + "; ".join(problems))
    return record


def counts(plan: Mapping) -> dict:
    return contracts.capture_counts_over_budget(plan)


def planned_capture_total(plan: Mapping) -> int:
    return len(plan.get("targets") or [])


def skipped_targets(plan: Mapping, captured_ids: Sequence[str]) -> list[dict]:
    """Planned targets that were never captured, each with the reason recorded.

    A plan that silently drops half its targets reports as if it had run them. This
    is what makes ``PARTIAL`` a distinguishable answer from ``CAPTURED``.
    """
    captured = {str(item) for item in captured_ids}
    rows: list[dict] = []
    for target in plan.get("targets") or []:
        if not isinstance(target, Mapping):
            continue
        if str(target.get("target_id", "")) in captured:
            continue
        rows.append({
            "target_id": str(target.get("target_id", "")),
            "route": str(target.get("route", "")),
            "state": str(target.get("state", "")),
            "kind": str(target.get("kind", "")),
            "reason_skipped": str(target.get("skip_reason", "") or "no reason was recorded for skipping this target"),
        })
    return rows


def summarise(plan: Mapping, *, captured: Sequence[str] = (), capture_bytes: int = 0,
              duration_seconds: float = 0.0) -> dict:
    """Capture economics, measured. No invented quality score."""
    rows = skipped_targets(plan, captured)
    return {
        "planned_captures": planned_capture_total(plan),
        "actual_captures": len(list(captured)),
        "capture_bytes": int(capture_bytes),
        "capture_seconds": round(float(duration_seconds), 3),
        "counts_by_kind": counts(plan),
        "budget": dict(plan.get("capture_budget") or {}),
        "states_skipped": len(rows),
        "skipped": rows,
        "interpretation": (
            "counts and bytes are measured. They are capture economics, not a measure of design "
            "quality: a cheap run is not a good run."
        ),
    }


def project_root_of(plan: Mapping) -> Path:
    root = str((plan.get("source_binding") or {}).get("project_root", "") or "")
    return Path(root) if root else Path(".")


def describe(record: Mapping) -> str:
    targets = record.get("targets") or []
    routes = sorted({str(item.get("route", "")) for item in targets if isinstance(item, Mapping)})
    return (
        f"{record.get('capture_plan_id')} {len(targets)} target(s) across {len(routes)} route(s) "
        f"bound to {str(record.get('render_source_digest', ''))[:12]}"
    )


__all__ = [
    "PRIMARY_VIEWPORT",
    "viewport_state",
    "interaction_state",
    "responsive_state",
    "theme_variant",
    "responsive_viewports",
    "capture_budget",
    "create",
    "counts",
    "planned_capture_total",
    "skipped_targets",
    "summarise",
    "describe",
]
