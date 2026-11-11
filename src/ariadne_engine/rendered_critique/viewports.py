"""Declared viewport matrices for responsive verification (Ariadne 2.4C).

A viewport ladder invented by the tool is not a requirement. This module accepts
a matrix the project declares -- representative widths and the breakpoints it
actually supports -- records it with the capture plan, and refuses a matrix that
is internally contradictory or outside the declared supported range.

The five classes are names for roles, not device models::

    narrow    the smallest supported window, usually 320-360 CSS px
    mobile    a phone-sized window
    tablet    a tablet-sized window
    desktop   the primary desktop window
    wide      a wide desktop window

A project that declares only some of them is not wrong; the matrix records what
it declared. A responsive claim that declares none of them is not evidence of
responsive verification, and :func:`matrix_problems` says so.
"""

from __future__ import annotations

from typing import Mapping, Sequence

from ..contracts import ContractError

VIEWPORT_CLASSES = ("narrow", "mobile", "tablet", "desktop", "wide")
CLASS_ORDER = {name: index for index, name in enumerate(VIEWPORT_CLASSES)}
MIN_WIDTH = 240
MAX_WIDTH = 5120
MIN_HEIGHT = 240
MAX_HEIGHT = 4320
MIN_SCALE = 0.5
MAX_SCALE = 4.0


def _entry(value: Mapping) -> dict:
    name = str(value.get("class") or value.get("name") or value.get("viewport_class") or "").strip().lower()
    if not name:
        raise ContractError("a declared viewport must name its class (narrow/mobile/tablet/desktop/wide)")
    if name not in VIEWPORT_CLASSES:
        raise ContractError(
            f"declared viewport class {name!r} is not one of {', '.join(VIEWPORT_CLASSES)}"
        )
    try:
        width = int(value.get("width"))
        height = int(value.get("height", 900))
    except (TypeError, ValueError) as exc:
        raise ContractError(f"declared viewport {name!r} needs integer width and height") from exc
    try:
        scale = float(value.get("device_scale_factor", value.get("device_pixel_ratio", 1)) or 1)
    except (TypeError, ValueError) as exc:
        raise ContractError(f"declared viewport {name!r} has a non-numeric scale factor") from exc
    if not MIN_WIDTH <= width <= MAX_WIDTH:
        raise ContractError(f"declared viewport {name!r} width {width} is outside {MIN_WIDTH}..{MAX_WIDTH}")
    if not MIN_HEIGHT <= height <= MAX_HEIGHT:
        raise ContractError(f"declared viewport {name!r} height {height} is outside {MIN_HEIGHT}..{MAX_HEIGHT}")
    if not MIN_SCALE <= scale <= MAX_SCALE:
        raise ContractError(f"declared viewport {name!r} scale {scale} is outside {MIN_SCALE}..{MAX_SCALE}")
    return {
        "viewport_class": name,
        "width": width,
        "height": height,
        "device_scale_factor": scale,
        "supported": bool(value.get("supported", True)),
        "notes": str(value.get("notes", "") or ""),
    }


def declared(implementation: Mapping | None) -> list[dict] | None:
    """The matrix the implementation declares, or ``None`` when it declares none.

    ``viewports`` is the preferred key. ``viewport_matrix`` is accepted as the
    same declaration under its descriptive name; a project that used either is
    understood, and a project that used neither gets the historical ladder
    rather than a fabricated one.
    """
    if not isinstance(implementation, Mapping):
        return None
    raw = implementation.get("viewports", implementation.get("viewport_matrix"))
    if raw is None:
        return None
    if not isinstance(raw, (list, tuple)):
        raise ContractError("declared viewports must be a list")
    if not raw:
        raise ContractError("a declared viewport matrix is empty; declare at least one viewport")
    rows = [_entry(item) for item in raw if isinstance(item, Mapping)]
    if len(rows) != len(raw):
        raise ContractError("every declared viewport must be an object")
    return normalise(rows)


def normalise(rows: Sequence[Mapping]) -> list[dict]:
    ordered = sorted((dict(row) for row in rows), key=lambda row: (
        CLASS_ORDER.get(str(row.get("viewport_class", "")), 99), int(row.get("width", 0) or 0)
    ))
    seen: set[str] = set()
    widths: set[int] = set()
    output: list[dict] = []
    for row in ordered:
        name = str(row.get("viewport_class", ""))
        width = int(row.get("width", 0) or 0)
        if name in seen:
            raise ContractError(f"declared viewport matrix repeats class {name!r}")
        if width in widths:
            raise ContractError(f"declared viewport matrix repeats width {width}")
        seen.add(name)
        widths.add(width)
        output.append(dict(row))
    return output


def matrix_problems(
    implementation: Mapping | None,
    *,
    responsive_claimed: bool = False,
    rows: Sequence[Mapping] | None = None,
) -> list[str]:
    problems: list[str] = []
    declared_rows = list(rows) if rows is not None else (declared(implementation) or [])
    if not declared_rows:
        if responsive_claimed:
            problems.append(
                "the surface claims responsive behaviour but declares no viewport matrix; a "
                "responsive claim without declared supported viewports cannot be verified"
            )
        return problems
    classes = {str(row.get("viewport_class", "")) for row in declared_rows}
    supported = [row for row in declared_rows if bool(row.get("supported", True))]
    if not supported:
        problems.append("every declared viewport is marked unsupported; there is nothing to verify")
    if responsive_claimed:
        missing = [name for name in VIEWPORT_CLASSES if name not in classes]
        if missing:
            problems.append(
                "the responsive declaration omits viewport class(es): " + ", ".join(missing)
            )
    range_row = None
    if isinstance(implementation, Mapping):
        range_row = implementation.get("supported_width_range")
    if isinstance(range_row, (list, tuple)) and len(range_row) == 2:
        try:
            low, high = int(range_row[0]), int(range_row[1])
        except (TypeError, ValueError):
            problems.append("supported_width_range must contain two integers")
        else:
            for row in declared_rows:
                width = int(row.get("width", 0) or 0)
                if not low <= width <= high:
                    problems.append(
                        f"declared viewport {row.get('viewport_class')} width {width} is outside "
                        f"the declared supported range {low}..{high}"
                    )
    return list(dict.fromkeys(problems))


def targets(
    rows: Sequence[Mapping],
    *,
    routes: Sequence[str],
    state: str = "default",
    basis: Sequence[Mapping] = (),
    interaction_by_class: Mapping[str, Mapping] | None = None,
    required_regions: Sequence[str] = (),
) -> list[dict]:
    """One capture target per (route, viewport class), with no duplicate width.

    This is a target *description*, not a capture: it still goes through
    :func:`ariadne_engine.rendered_critique.plan.create` so the ordinary basis,
    budget and provenance rules apply.
    """
    from . import plan

    output: list[dict] = []
    for route in routes:
        for row in rows:
            if not bool(row.get("supported", True)):
                continue
            name = str(row.get("viewport_class"))
            viewport = {
                "width": int(row.get("width")),
                "height": int(row.get("height")),
                "device_scale_factor": float(row.get("device_scale_factor", 1) or 1),
                "viewport_class": name,
            }
            interaction = dict((interaction_by_class or {}).get(name) or {})
            if interaction:
                output.append(plan.interaction_state(
                    route=route, state=state, action=interaction, viewport=viewport,
                    basis=basis, required_regions=required_regions,
                    notes=f"declared {name} viewport",
                ))
            else:
                output.append(plan.responsive_state(
                    route=route, viewport=viewport, state=state, basis=basis,
                    required_regions=required_regions, notes=f"declared {name} viewport",
                ))
    return output


def coverage(rows: Sequence[Mapping]) -> dict:
    return {
        "classes": {
            str(row.get("viewport_class")): {
                "width": int(row.get("width", 0) or 0),
                "height": int(row.get("height", 0) or 0),
                "supported": bool(row.get("supported", True)),
            }
            for row in rows
        },
        "declared": len(rows),
        "supported": sum(1 for row in rows if bool(row.get("supported", True))),
        "missing_classes": [
            name for name in VIEWPORT_CLASSES
            if f"'{name}'" not in {repr(str(row.get("viewport_class"))) for row in rows}
            and name not in {str(row.get("viewport_class")) for row in rows}
        ],
    }


def describe(rows: Sequence[Mapping]) -> str:
    return ", ".join(
        f"{row.get('viewport_class')}={row.get('width')}x{row.get('height')}"
        for row in rows
    )
