"""The AR-221 vertical slice, end to end, against a real front-end project.

> *"Implement that direction. It should feel precise, dense and calm, but not like
> a generic AI dashboard."*

The full path, with no mocks in the core:

```text
project inspection
        â†“
project-local DESIGN.md / tokens
        â†“
ReferenceSet (AR-220, frozen corpus, offline)
        â†“
grounded candidate direction (AR-220)
        â†“
explicit test approval through the real G1D boundary
        â†“
DesignImplementationPlan
        â†“
component inventory + reuse decisions
        â†“
implementation worker packet, with an omission record
        â†“
code changes in a real project
        â†“
typecheck Â· build Â· tests
        â†“
implementation provenance and design trace
```

**What the "worker" is here, stated plainly.** The edits in :data:`IMPLEMENTATION_EDITS`
are a scripted stand-in for an implementation worker, applied deterministically by
string replacement. They are not a live model, and the slice does not pretend
otherwise. What the slice genuinely exercises is everything around them: the plan,
the precedence rules, the scope boundary, the classification of each edit against
the plan, the provenance records, and a real ``tsc``/build/test run on a real
project. A live model would replace :data:`IMPLEMENTATION_EDITS` and nothing else -
the plan, the gates and the trace are already doing the work that matters.

**Where the approval comes from.** :data:`FIXTURE_APPROVER` is a declared test
identity, and the approval is recorded by calling ``design.approve_direction`` - the
same function an operator uses, through the same ``G1D`` gate. There is no fixture
bypass anywhere in the engine. The plan compiler requires an approval the run
actually holds and will refuse a candidate direction; what the slice supplies is a
recorded approval, not a way around the check.
"""

from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path
from typing import Mapping, Sequence

from .. import contracts
from ..contracts import ContractError
from ..design_reference import safety
from ..design_reference import vertical_slice as ar220
from . import changes as changes_module
from . import execution as execution_module
from . import inventory as inventory_module
from . import packet as packet_module
from . import plan as plan_module

SLICE_REQUEST = (
    "Implement that direction for a serious desktop developer tool. It should feel precise, dense and "
    "calm, but not like a generic AI dashboard."
)
"""The request the AR-221 slice answers - AR-220's, carried forward."""

TASK_ID = "ar221-vertical-slice"
FIXTURE_APPROVER = "ar221-fixture-operator"
"""The declared identity a test run approves as.

Named rather than left anonymous because "somebody" is not an accountable identity,
and a record of who approved a direction is the record a later reader needs. It is a
test identity: in a real project the approving identity is a person, and this
function is what they call.
"""

FIXTURE_SOURCE = FIXTURE_ROOT = Path(__file__).resolve().parent / "fixtures" / "desktop-tool"
"""The committed pre-implementation fixture project."""

ALLOWED_SCOPE = (
    "src/styles/app.css",
    "src/app/shell.ts",
    "src/lib/panel-split.ts",
    "tests/shell.test.ts",
    "tests/direction.test.ts",
)
"""The files this implementation may touch.

Narrow on purpose. "Improve dashboard visual hierarchy" does not authorise a routing
change, a dependency bump or a database migration, and the boundary is declared
before the work starts rather than negotiated after it.
"""

FORBIDDEN_SCOPE = ("src/styles/tokens.css", "src/lib/ui.ts", "src/lib/icons.ts", "src/lib/density.ts", "package.json")
"""Files the implementation may not modify, and why each is tempting.

``tokens.css`` holds the project identity this whole exercise is about protecting;
``ui.ts`` and ``icons.ts`` hold the components being reused, so "improving" them would
destroy the evidence that reuse happened. Recorded explicitly because a scope
boundary nobody can see is not a boundary.
"""

TARGET_SURFACES = (
    "navigation rail", "workspace layout", "toolbar", "panels", "typography", "surface hierarchy",
)
"""The surfaces the approved direction obliges the implementation to change."""


# --------------------------------------------------------------------- constraints

def build_constraints(
    *,
    direction_record: Mapping,
    inventory_found: Mapping,
    pattern_reference: Mapping,
    tokens: Mapping,
) -> list[dict]:
    """Derive implementation constraints from the approved direction and the project.

    Each constraint names the evidence it came from, and the bases are deliberately
    mixed. That is the point of the exercise: an implementation whose every decision
    traces to an external reference has been designed by somebody else's brand, and
    an implementation whose every decision traces to the project has learned nothing.
    A real plan is mostly project identity with references informing structure.
    """
    grounding = direction_record.get("ar220_grounding") if isinstance(
        direction_record.get("ar220_grounding"), Mapping
    ) else {}
    principles = {
        str(row.get("dimension", "")): row
        for row in grounding.get("principles") or []
        if isinstance(row, Mapping)
    }
    rejected = " ".join(str(item) for item in direction_record.get("findings_rejected") or [])
    token_files = ", ".join(str(item) for item in (tokens.get("files") or [])) or "src/styles/tokens.css"
    accent = str((tokens.get("css_variables") or {}).get("accent", "--accent"))

    rows: list[dict] = [
        plan_module.constraint(
            category="color",
            statement=(
                f"Beacon's accent is {accent} from {token_files}. No reference palette value is written "
                "into a brand slot"
            ),
            basis="PROJECT_IDENTITY",
evidence=f"{token_files} declares {accent}; DESIGN.md names it as the product's own brand colour",
            surfaces=("all",),
            # No literal detector on purpose. "The accent is --accent" is enforced by
            # the grounding rule, not by a string match: `var(--accent)` in the
            # stylesheet is the constraint being *obeyed*, so a detector that fired on
            # it would report compliance as a violation. A literal colour in added
            # source is already a material change, and an ungrounded one is refused.
        ),
        plan_module.constraint(
            category="surface",
            statement="exactly three surface levels exist: canvas, surface, raised; a fourth is a decision that needs justifying",
            basis="PROJECT_IDENTITY",
            evidence="fixture DESIGN.md, Surfaces section",
            surfaces=("workspace layout", "panels"),
        ),
        plan_module.constraint(
            category="component",
            statement=(
                "behaviour is expressed by surface level and a hairline rule; glass, glow and large radii "
                "are removed rather than restyled"
            ),
            basis="PROJECT_IDENTITY",
            evidence="fixture DESIGN.md, Identity and Surfaces sections: 'not by shadow, glow or rounded card edges'",
            surfaces=("workspace layout", "panels", "toolbar"),
            treatment="AVOID",
        ),
        plan_module.constraint(
            category="typography",
            statement=(
                "the compact type scale already declared in tokens.css is used as-is; a reference type "
                "family does not replace the product's own"
            ),
            basis="PROJECT_IDENTITY",
            evidence=f"{token_files} declares --font-sans and the --text-* scale; DESIGN.md names the typeface as the product's",
            surfaces=("typography",),
        ),
        plan_module.constraint(
            category="accessibility",
            statement="every interactive control keeps a visible keyboard focus ring",
            basis="PROJECT_IDENTITY",
            evidence="fixture DESIGN.md, Accessibility section: 'a visible focus ring'",
            surfaces=("navigation rail", "toolbar", "panels"),
            accessibility_floor=True,
        ),
        plan_module.constraint(
            category="motion",
            statement="reduced-motion support stays present; decorative motion does not replace it",
            basis="PROJECT_IDENTITY",
            evidence="fixture DESIGN.md, Motion section: reduced-motion 'is not removed'",
            surfaces=("panels", "navigation rail"),
            accessibility_floor=True,
        ),
        plan_module.constraint(
            category="layout",
            statement=(
                "the shell becomes a three-zone working surface - navigation rail, primary column, "
                "collapsible inspector - instead of a centred welcome panel"
            ),
            basis="APPROVED_DIRECTION",
            evidence=(
                "approved direction key_hierarchy: "
                + "; ".join(str(item) for item in direction_record.get("key_hierarchy") or [])[:240]
            ),
            surfaces=("workspace layout", "navigation rail"),
            principle_ids=[str(principles.get("layout-grid", {}).get("principle_id", ""))]
            if principles.get("layout-grid") else [],
            reference_ids=[
                str(row.get("reference_id", ""))
                for row in (principles.get("layout-grid", {}).get("evidence") or [])
            ] if principles.get("layout-grid") else [],
        ),
        plan_module.constraint(
            category="navigation",
            statement=(
                "navigation is a persistent rail of the project's own NavItem, sized for a full working "
                "day rather than centred as a row of pills"
            ),
            basis="APPROVED_DIRECTION",
            evidence=(
                "approved direction key_hierarchy and interaction_principles: "
                + "; ".join(str(item) for item in direction_record.get("key_hierarchy") or [])[:200]
            ),
            surfaces=("navigation rail",),
            principle_ids=[str(principles.get("navigation", {}).get("principle_id", ""))]
            if principles.get("navigation") else [],
            reference_ids=[
                str(row.get("reference_id", ""))
                for row in (principles.get("navigation", {}).get("evidence") or [])
            ] if principles.get("navigation") else [],
        ),
        plan_module.constraint(
            category="component",
            statement=(
                "the resizable inspector divider is operable from the keyboard and clamped to usable "
                "bounds, adapting the project's own Panel rather than replacing it"
            ),
            basis="IMPLEMENTATION_REFERENCE",
            evidence=(
                f"{pattern_reference.get('source')} @ {pattern_reference.get('revision')} "
                f"({pattern_reference.get('reuse_status')}): the divider contract, adapted onto "
                f"src/lib/ui.ts panel() and src/lib/density.ts"
            ),
            surfaces=("panels",),
            detectors=("role=\"separator\"", "aria-orientation"),
        ),
        plan_module.constraint(
            category="spacing",
            statement=(
                "row heights commit to the density ladder already declared in density.ts; no row grows "
                "past the height a thousand log lines need to stay scannable"
            ),
            basis="PROJECT_IDENTITY",
            evidence="fixture DESIGN.md, Density section; src/lib/density.ts DENSITY.rowHeight",
            surfaces=("panels", "workspace layout"),
        ),
        plan_module.constraint(
            category="component",
            statement="existing project primitives are extended, never regenerated",
            basis="ENGINEERING_CONSTRAINT",
            evidence=(
                f"component inventory found "
                f"{len(inventory_found.get('components') or [])} component file(s) already shipping "
                f"{', '.join(sorted(inventory_found.get('primitives', {}).get('present') or []))}"
            ),
            surfaces=("all",),
        ),
    ]
    if rejected:
        rows.append(plan_module.constraint(
            category="surface",
            statement=f"the approved direction's rejection stands: {rejected[:200]}",
            basis="APPROVED_DIRECTION",
            evidence="approved direction findings_rejected, from the counter-reference's recorded anti-pattern",
            surfaces=("workspace layout", "panels", "toolbar", "navigation rail"),
            treatment="AVOID",
        ))
    return rows


# ------------------------------------------------------------- implementation

IMPLEMENTATION_EDITS: tuple[dict, ...] = (
    {
        "path": "src/styles/app.css",
        "name": "app-css",
        "constraint_kinds": ("APPROVED_DIRECTION:layout", "PROJECT_IDENTITY:color", "PROJECT_IDENTITY:surface"),
        "change_kind": "surface-and-accent-restraint",
        "find": """.app {
  display: block;
  padding: var(--space-4);
}
""",
        "replace": """.app {
  display: grid;
  grid-template-columns: var(--nav-rail-width, 176px) minmax(0, 1fr);
  grid-template-rows: 100%;
  min-height: 100vh;
  background: var(--canvas);
}
""",
    },
    {
        "path": "src/styles/app.css",
        "name": "hero-to-workspace",
        "constraint_kinds": ("APPROVED_DIRECTION:layout", "PROJECT_IDENTITY:typography", "PROJECT_IDENTITY:surface"),
        "change_kind": "remove-centred-hero",
        "find": """/* A centred welcome panel, of the kind every generated dashboard ships with. */
.hero {
  text-align: center;
  padding: 64px 24px;
  border-radius: var(--radius-lg);
  background: radial-gradient(circle at 50% 0%, rgba(79, 124, 255, 0.35), rgba(11, 13, 17, 0) 70%);
  border: 1px solid var(--border);
}

.hero h1 {
  font-size: 32px;
  margin: 0 0 8px;
}

.hero p {
  color: var(--text-muted);
  margin: 0 0 24px;
}
""",
        "replace": """/* The primary working column. No hero, no introductory copy: this is a tool. */
.workspace {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  min-width: 0;
}

.workspace__primary {
  min-width: 0;
  padding: var(--space-3);
}

.workspace__heading {
  font-size: var(--text-lg);
  font-weight: 600;
  line-height: var(--leading-tight);
  margin: 0 0 var(--space-3);
  letter-spacing: -0.01em;
}
""",
    },
    {
        "path": "src/styles/app.css",
        "name": "cards-to-panels",
        "constraint_kinds": ("PROJECT_IDENTITY:surface", "APPROVED_DIRECTION:surface", "PROJECT_IDENTITY:typography"),
        "change_kind": "remove-glass-cards",
        "find": """/* Translucent cards on a blurred backdrop. */
.card-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: var(--space-3);
  margin-top: var(--space-4);
}

.glass-card {
  position: relative;
  padding: var(--space-4);
  border-radius: var(--radius-lg);
  background: linear-gradient(160deg, rgba(255, 255, 255, 0.06), rgba(255, 255, 255, 0.02));
  border: 1px solid var(--border);
  backdrop-filter: blur(18px);
  -webkit-backdrop-filter: blur(18px);
  box-shadow: 0 12px 32px rgba(0, 0, 0, 0.45);
}

.glass-card h2 {
  margin: 0 0 var(--space-2);
  font-size: var(--text-lg);
}

.glass-card p {
  margin: 0;
  color: var(--text-muted);
  font-size: var(--text-sm);
}
""",
        "replace": """/* Hierarchy is a surface level and a hairline rule, never elevation. */
.panel {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.panel--raised {
  background: var(--raised);
}

.panel__header {
  display: flex;
  align-items: center;
  height: 28px;
  padding: 0 var(--space-2);
  border-bottom: 1px solid var(--border);
}

.panel__title {
  margin: 0;
  font-size: var(--text-sm);
  font-weight: 500;
  color: var(--text-muted);
  letter-spacing: 0.02em;
}

.panel__body {
  min-width: 0;
  padding: var(--space-2);
  font-size: var(--text-sm);
}

.panel[data-scrollable="true"] .panel__body {
  overflow: auto;
  max-height: 60vh;
}
""",
    },
    {
        "path": "src/styles/app.css",
        "name": "pills-to-rail",
        "constraint_kinds": ("APPROVED_DIRECTION:navigation", "PROJECT_IDENTITY:component"),
        "change_kind": "replace-pill-navigation",
        "find": """/* Every action is a pill. */
.chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 14px;
  border-radius: 999px;
  border: 1px solid var(--border-strong);
  background: var(--raised);
  color: var(--text);
  font-size: var(--text-sm);
  cursor: pointer;
}

.chip-primary {
  border-radius: 999px;
  background: var(--accent);
  border-color: var(--accent);
  color: var(--accent-ink);
}

.chip-row {
  display: flex;
  justify-content: center;
  gap: var(--space-2);
  margin-bottom: var(--space-4);
}

.cta-label {
  text-shadow: 0 0 18px rgba(79, 124, 255, 0.8);
}
""",
        "replace": """.nav {
  display: flex;
  flex-direction: column;
  background: var(--surface);
  border-right: 1px solid var(--border);
  padding: var(--space-2) 0;
  gap: 1px;
}

.nav-item {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  height: 24px;
  padding: 0 var(--space-3);
  border-left: 2px solid transparent;
  color: var(--text-muted);
  font-size: var(--text-sm);
  text-decoration: none;
}

.nav-item:hover {
  background: var(--raised);
  color: var(--text);
}

.nav-item[data-active="true"] {
  border-left-color: var(--accent);
  background: var(--raised);
  color: var(--text);
}

.toolbar {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  height: 28px;
  padding: 0 var(--space-2);
  border-bottom: 1px solid var(--border);
  background: var(--surface);
}

.btn {
  height: 22px;
  padding: 0 var(--space-2);
  border-radius: var(--radius);
  border: 1px solid var(--border-strong);
  background: var(--raised);
  color: var(--text);
  font-size: var(--text-sm);
  cursor: pointer;
}

.btn--primary {
  background: var(--accent);
  border-color: var(--accent);
  color: var(--accent-ink);
}

.icon-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 22px;
  height: 22px;
  border-radius: var(--radius);
  border: 1px solid transparent;
  background: transparent;
  color: var(--text-muted);
  cursor: pointer;
}

.icon {
  width: 14px;
  height: 14px;
  fill: none;
  stroke: currentColor;
  stroke-width: 1.4;
  stroke-linecap: round;
  stroke-linejoin: round;
}

.divider {
  border: 0;
  border-top: 1px solid var(--border);
  margin: 0;
}

.panel-split {
  display: flex;
  min-width: 0;
}

.panel-split__divider {
  width: 1px;
  background: var(--border);
  border: 0;
  padding: 0;
  cursor: col-resize;
}
""",
    },
    {
        "path": "src/styles/app.css",
        "name": "density-and-focus",
        "constraint_kinds": ("PROJECT_IDENTITY:spacing", "PROJECT_IDENTITY:accessibility"),
        "change_kind": "tighten-rows-and-restore-focus-ring",
        "find": """.log-table th,
.log-table td {
  text-align: left;
  padding: 12px var(--space-3);
  border-bottom: 1px solid var(--border);
}
""",
        "replace": """.log-table th,
.log-table td {
  text-align: left;
  height: 24px;
  padding: 0 var(--space-2);
  border-bottom: 1px solid var(--border);
}
""",
    },
    {
        "path": "src/styles/app.css",
        "name": "focus-ring",
        "constraint_kinds": ("PROJECT_IDENTITY:accessibility",),
        "change_kind": "restore-visible-focus-ring",
        "find": """:focus-visible {
  outline: 1px solid var(--accent);
}
""",
        "replace": """:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: 1px;
}

.panel-split__divider:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: 2px;
}
""",
    },
    {
        "path": "src/styles/app.css",
        "name": "motion-scoped",
        "constraint_kinds": ("PROJECT_IDENTITY:motion", "PROJECT_IDENTITY:surface"),
        "change_kind": "remove-decorative-hover-motion",
        "find": """@media (prefers-reduced-motion: no-preference) {
  .glass-card {
    transition: transform var(--duration-base) var(--ease-standard);
  }

  .glass-card:hover {
    transform: translateY(-2px);
  }
}""",
        "replace": """/* Motion marks state changes a user would otherwise have to hunt for. Nothing decorative. */
@media (prefers-reduced-motion: no-preference) {
  .nav-item,
  .btn {
    transition: background-color var(--duration-fast) var(--ease-standard);
  }
}
""",
    },
    {
        "path": "src/lib/panel-split.ts",
        "name": "panel-split-module",
        "constraint_kinds": ("IMPLEMENTATION_REFERENCE:component", "PROJECT_IDENTITY:accessibility", "ENGINEERING_CONSTRAINT:component"),
        "change_kind": "add-keyboard-operable-divider",
        "create": """/**
 * The resizable inspector divider.
 *
 * The divider contract comes from the frozen implementation reference recorded in
 * this plan (an Ariadne-authored pattern note, Apache-2.0). What is taken is the
 * *contract* - a separator role, an orientation, clamped bounds and keyboard steps -
 * and the code is written against this project's own `density` helpers and `panel`
 * primitive. No source was copied, and the reference's aesthetic is not adopted.
 */

import { clampPane, stepPane } from "./density.ts";

export type SplitDirection = 1 | -1;

export const SPLIT_MIN = 96;
export const SPLIT_MAX = 720;
export const SPLIT_KEY_STEP = 16;

export interface SplitState {
  readonly size: number;
  readonly collapsed: boolean;
}

/** Initial state for an inspector panel. */
export function initialSplit(size: number): SplitState {
  return { size: clampPane(size, SPLIT_MIN, SPLIT_MAX), collapsed: false };
}

/** Arrow keys move the divider; Home and End jump to the bounds. */
export function resizeBy(
  state: SplitState,
  key: string,
): SplitState {
  switch (key) {
    case "ArrowLeft":
      return { ...state, size: stepPane(state.size, -1, SPLIT_KEY_STEP) };
    case "ArrowRight":
      return { ...state, size: stepPane(state.size, 1, SPLIT_KEY_STEP) };
    case "Home":
      return { ...state, size: SPLIT_MIN };
    case "End":
      return { ...state, size: SPLIT_MAX };
    default:
      return state;
  }
}

/** Collapse without losing the width the user had chosen. */
export function toggleCollapsed(state: SplitState): SplitState {
  return { ...state, collapsed: !state.collapsed };
}

/** Markup for the divider itself: a separator with an accessible name and a value. */
export function dividerMarkup(label: string, state: SplitState): string {
  const value = state.collapsed ? "collapsed" : `${state.size}px`;
  return `<div class="panel-split__divider" role="separator" aria-orientation="vertical"`
    + ` aria-label="${label}" aria-valuenow="${value}" tabindex="0" data-collapsed="${state.collapsed}"></div>`;
}
""",
    },
    {
        "path": "src/app/shell.ts",
        "name": "shell-workspace",
        "constraint_kinds": (
            "APPROVED_DIRECTION:layout", "APPROVED_DIRECTION:navigation",
            "PROJECT_IDENTITY:accessibility",
            "ENGINEERING_CONSTRAINT:component", "IMPLEMENTATION_REFERENCE:component",
        ),
        "change_kind": "restructure-shell",
        "find": """export function shell(activeRoute = defaultRoute().id): string {
  const primary = ROUTES.filter((entry) => entry.group === "primary");
  const railItems = primary
    .map((entry) => `<a class="chip" href="#${entry.id}" data-active="${entry.id === activeRoute}">${entry.label}</a>`)
    .join("\\n  ");
  return [
    `<main class="app" data-row-height="${DENSITY.rowHeight}">`,
    `  <nav class="chip-row" aria-label="Sections">`,
    `  ${railItems}`,
    "  </nav>",
    divider(),
    `  ${welcomePanel()}`,
    `  ${logPanel()}`,
    "</main>",
  ].join("\\n");
}
""",
        "replace": """function navRail(activeRoute: string): string {
  const items = ROUTES
    .filter((entry) => entry.group === "primary")
    .map((entry) => `    ${navItem(entry, entry.id === activeRoute)}`)
    .join("\\n");
  return [
    '<nav class="nav" aria-label="Sections">',
    items,
    "</nav>",
  ].join("\\n");
}

function requestPanel(): string {
  return panel(
    { id: "request", title: "Request", surface: "surface", scrollable: false },
    [
      `    <h1 class="workspace__heading">Request</h1>`,
      `    ${toolbar("Request actions", [button("Send", "primary"), button("Save"), iconButton("play", "Send request", "request")])}`,
      '    <p class="panel__body">No request composed.</p>',
    ].join("\\n")
  );
}

export function shell(activeRoute = defaultRoute().id): string {
  const state = initialSplit(DENSITY.inspectorWidth);
  return [
    `<main class="app" data-row-height="${DENSITY.rowHeight}">`,
    `  ${navRail(activeRoute)}`,
    '  <div class="workspace">',
    '    <div class="workspace__primary">',
    `      ${requestPanel()}`,
    `      ${logPanel()}`,
    "    </div>",
    `    ${dividerMarkup("Resize inspector", state)}`,
    '    <aside class="panel panel--raised" aria-label="Inspector">',
    '      <div class="panel__body">Inspector</div>',
    "    </aside>",
    "  </div>",
    "</main>",
  ].join("\\n");
}
""",
    },
    {
        "path": "src/app/shell.ts",
        "name": "shell-imports-and-hero-removal",
        "constraint_kinds": ("APPROVED_DIRECTION:layout", "PROJECT_IDENTITY:surface"),
        "change_kind": "reuse-project-primitives",
        "find": """import { DENSITY } from "../lib/density.ts";
import { button, divider, logRow, logTable, panel } from "../lib/ui.ts";
import { ROUTES, defaultRoute } from "./routes.ts";
""",
        "replace": """import { DENSITY } from "../lib/density.ts";
import { iconButton } from "../lib/icons.ts";
import { dividerMarkup, initialSplit } from "../lib/panel-split.ts";
import { button, logRow, logTable, navItem, panel, toolbar } from "../lib/ui.ts";
import { ROUTES, defaultRoute } from "./routes.ts";
""",
    },
    {
        "path": "src/app/shell.ts",
        "name": "remove-welcome-panel",
        "constraint_kinds": ("APPROVED_DIRECTION:layout", "PROJECT_IDENTITY:typography", "PROJECT_IDENTITY:surface"),
        "change_kind": "remove-welcome-panel",
        "find": """function welcomePanel(): string {
  return panel(
    { id: "welcome", title: "Beacon", surface: "raised", scrollable: false },
    [
      '  <div class="hero">',
      '    <h1 class="cta-label">Ship requests faster</h1>',
      '    <p>Everything you need to inspect, replay and audit API traffic.</p>',
      '    <div class="chip-row">',
      `      ${button("New request", "primary")}`,
      `      ${button("Open history")}`,
      "    </div>",
      "  </div>",
      '  <div class="card-grid">',
      `    ${panel({ id: "quickstart", title: "Quickstart", surface: "raised", scrollable: false }, '<p>Send your first request in three steps.</p>')}`,
      `    ${panel({ id: "environments", title: "Environments", surface: "raised", scrollable: false }, '<p>Three environments configured.</p>')}`,
      `    ${panel({ id: "recent", title: "Recent", surface: "raised", scrollable: false }, '<p>Twelve requests in the last hour.</p>')}`,
      "  </div>",
    ].join("\\n")
  );
}

""",
        "replace": "",
    },
    {
        "path": "tests/direction.test.ts",
        "name": "direction-regression-tests",
        "constraint_kinds": ("APPROVED_DIRECTION:surface", "PROJECT_IDENTITY:accessibility"),
        "change_kind": "add-direction-regression-tests",
        "create": """/**
 * Regression tests for the approved design direction.
 *
 * These exist because the direction is now executable: the plan forbids glass,
 * gradients, pill geometry and a centred hero, and a design regression should fail a
 * build rather than wait for someone to notice.
 *
 * They assert structural absence and presence in source. They do not judge whether
 * the interface looks right; that needs a render.
 */

import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { test } from "node:test";

import { documentBody, shell } from "../src/app/shell.ts";

const css = () => readFile(new URL("../src/styles/app.css", import.meta.url), "utf8");

test("the stylesheet keeps no backdrop-filter glass", async () => {
  assert.doesNotMatch(await css(), /backdrop-filter/);
});

test("the stylesheet declares no gradient surface", async () => {
  assert.doesNotMatch(await css(), /(?:linear|radial|conic)-gradient\\(/);
});

test("the stylesheet uses no pill geometry", async () => {
  assert.doesNotMatch(await css(), /border-radius:\\s*(?:999|100%)/);
});

test("the stylesheet keeps only the small radius language", async () => {
  const styles = await css();
  const radii = [...styles.matchAll(/border-radius:\\s*([^;]+);/g)].map((match) => match[1].trim());
  for (const radius of radii) {
    assert.match(radius, /var\\(--radius/, `unexpected radius literal: ${radius}`);
  }
});

test("the shell has no centred welcome hero", () => {
  const html = shell();
  assert.doesNotMatch(html, /class="hero"/);
  assert.doesNotMatch(html, /card-grid/);
  assert.doesNotMatch(html, /class="chip/);
});

test("the shell is a three-zone working surface", () => {
  const html = shell();
  assert.match(html, /<nav class="nav"/);
  assert.match(html, /class="workspace"/);
  assert.match(html, /<aside class="panel/);
});

test("the inspector divider is a named, focusable separator", () => {
  const html = shell();
  assert.match(html, /role="separator"/);
  assert.match(html, /aria-orientation="vertical"/);
  assert.match(html, /aria-label="Resize inspector"/);
  assert.match(html, /tabindex="0"/);
});

test("the toolbar is a labelled toolbar landmark", () => {
  assert.match(shell(), /role="toolbar"/);
  assert.match(shell(), /aria-label="Request actions"/);
});

test("rows are dense, not padded", async () => {
  assert.match(await css(), /height:\\s*24px/);
});

test("the project accent survives in tokens and is not restated in the app stylesheet", async () => {
  const tokens = await readFile(new URL("../src/styles/tokens.css", import.meta.url), "utf8");
  assert.match(tokens, /--accent:\\s*#4f7cff/);
  const styles = await css();
  const accents = [...styles.matchAll(/#[0-9a-fA-F]{6}\\b/g)].map((match) => match[0].toLowerCase());
  for (const value of accents) {
    assert.notEqual(value, "#4f7cff", "the app stylesheet must reference --accent, not repeat its value");
  }
});

test("the product typeface is not restated in the app stylesheet", async () => {
  assert.doesNotMatch(await css(), /font-family:\\s*["']/);
});

test("the built document keeps its landmarks", () => {
  const html = documentBody();
  assert.match(html, /<nav/);
  assert.match(html, /<main/);
  assert.match(html, /<aside/);
});
""",
    },
)
"""The scripted implementation: path, the text to replace, and the constraint kinds it answers.

Every entry names its constraints by ``basis:category`` and the slice resolves them
against the compiled plan, so a constraint that is not in the plan cannot be cited -
which is the property that makes the grounding verdict mean something.
"""


PATTERN_REFERENCE_FILE = Path(__file__).resolve().parent / "fixtures" / "implementation-references" / "two-pane-split.md"
"""The frozen implementation reference this slice actually reads.

Ariadne's own pattern note, committed beside the code. It is read from disk rather
than inlined, because ``files_inspected`` in the reference record has to name a file
that exists - a record claiming an inspection that did not happen is precisely the
kind of provenance this phase is meant to remove.
"""


TOOLCHAIN_MODULES = "node_modules"
"""Installed dev dependencies, when the fixture already has them.

The fixture declares ``typescript`` and ``@types/node`` as devDependencies, exactly
as a real project would, and they are installed from the local npm cache with
``--offline``. The slice does **not** install anything: it reuses an installation that
already happened and hard-links it into the working copy, because a validation run
against a missing compiler would prove nothing and reporting ``BLOCKED`` is the
correct answer rather than a convenient one.
"""


def _materialise(root: Path) -> Path:
    """Copy the committed fixture into a working directory.

    ``node_modules`` is hard-linked rather than copied: it is large, immutable, and
    already installed. If it is absent the working copy simply has no toolchain, and
    the run reports that honestly instead of pretending to have validated anything.
    """
    root.mkdir(parents=True, exist_ok=True)
    for item in sorted(FIXTURE_SOURCE.rglob("*")):
        if any(part in {"node_modules", "dist", ".git"} for part in item.parts):
            continue
        target = root / item.relative_to(FIXTURE_SOURCE)
        if item.is_dir():
            target.mkdir(parents=True, exist_ok=True)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(item, target)
    source_modules = FIXTURE_SOURCE / TOOLCHAIN_MODULES
    if source_modules.is_dir():
        shutil.copytree(source_modules, root / TOOLCHAIN_MODULES, copy_function=_link_or_copy)
    return root


def _link_or_copy(source: str, target: str) -> str:
    """Hard-link when the filesystem allows it; fall back to a byte copy."""
    try:
        os.link(source, target)
    except OSError:
        shutil.copy2(source, target)
    return target


def toolchain_present(root: Path) -> bool:
    """Whether the working copy has an installed TypeScript compiler."""
    return (Path(root) / TOOLCHAIN_MODULES / "typescript" / "bin" / "tsc").is_file()


def _apply_edits(root: Path, edits: Sequence[Mapping], constraint_lookup: Mapping[str, str]) -> list[dict]:
    """Apply the scripted edits and return one change record per edit."""
    results: list[dict] = []
    for edit in edits:
        relative = str(edit["path"])
        target = root / relative
        safety.contained_path(relative, root, label=f"implementation path {relative}")
        if "create" in edit:
            before = ""
            after = str(edit["create"])
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(after, encoding="utf-8")
        else:
            before = target.read_text(encoding="utf-8")
            needle = str(edit["find"])
            if needle not in before:
                raise ContractError(
                    f"the scripted implementation expected text in {relative} that is not there; "
                    "the fixture changed under the slice"
                )
            after = before.replace(needle, str(edit["replace"]), 1)
            target.write_text(after, encoding="utf-8")
        constraint_ids = [
            constraint_lookup.get(str(kind), "") for kind in edit.get("constraint_kinds") or ()
        ]
        results.append({
            "path": relative,
            "before": before,
            "after": after,
            "constraint_ids": [item for item in constraint_ids if item],
            "reference_ids": [],
            "principle_ids": [],
            "requirement_ids": [],
            "treatment": "AVOID" if "remove-" in str(edit.get("change_kind", "")) else "",
            "implementation_source": "ar221-scripted-implementer (deterministic edit table)",
            "change_kind": str(edit.get("change_kind", "")),
            "component": str(edit.get("name", "")),
        })
    return results


def run(
    *,
    working_root: Path | None = None,
    stamp: str = "2026-10-05T00:00:00Z",
    validate: bool = True,
) -> dict:
    """Run the whole slice and return one report.

    Returns a report rather than raising, because a slice that crashes says less than
    one that names the step that refused.
    """
    temporary = working_root is None
    root = Path(working_root) if working_root is not None else Path(tempfile.mkdtemp(prefix="ariadne-ar221-"))
    if working_root is None or not (root / "src" / "app" / "shell.ts").is_file():
        _materialise(root)

    report: dict = {
        "request": SLICE_REQUEST,
        "project": str(root),
        "steps": [],
        "failures": [],
        "offline": True,
        "completed": False,
    }

    def step(name: str, detail: str, **extra) -> None:
        report["steps"].append({"step": name, "detail": detail, **extra})

    # -- 1-2. project inspection and component inventory --------------------
    found = inventory_module.inventory(root)
    tokens = found["tokens"]
    report["inventory"] = {
        "component_files_scanned": found["component_files_scanned"],
        "components": [row["path"] for row in found["components"]],
        "primitives_present": found["primitives"]["present"],
        "primitives_absent": found["primitives"]["absent"],
        "css_variable_count": tokens["css_variable_count"],
        "token_groups": sorted(tokens["groups"]),
        "accent": tokens["css_variables"].get("accent", ""),
        "registry": found["registry"]["declared"],
        "files_scanned": found["component_files_scanned"],
    }
    step(
        "project-inspection",
        f"{found['component_files_scanned']} component file(s), {tokens['css_variable_count']} CSS "
        f"variables, accent {tokens['css_variables'].get('accent', 'UNKNOWN')}",
    )

    state: dict = {
        "run_id": contracts.new_record_id("run"),
        "schema_version": contracts.SCHEMA_RECORD,
        "engine": {},
    }

    # -- 3-4. the AR-220 chain, pointed at the real project ------------------
    upstream = ar220.run(project_root=root, stamp=stamp)
    report["ar220"] = {
        "completed": bool(upstream.get("completed")),
        "reference_set_id": str((upstream.get("reference_set") or {}).get("reference_set_id", "")),
        "principles": len(upstream.get("principles") or []),
        "counter_reference_identity": str(upstream.get("counter_reference_identity", "")),
        "failures": list(upstream.get("failures") or []),
    }
    if not upstream.get("completed"):
        report["failures"].append(
            "the AR-220 evidence chain did not complete: "
            + "; ".join(upstream.get("failures") or ["unknown"])
        )
        return report
    state = upstream["state"]
    from .. import references as references_module

    references_by_id = {
        str(record["reference_id"]): record for record in references_module.references(state)
    }
    step(
        "reference-set",
        f"AR-220 produced reference set {report['ar220']['reference_set_id']} with "
        f"{report['ar220']['principles']} principles, offline",
    )

    from .. import design as design_module

    candidate = design_module.latest_direction(state, task_id=ar220.SLICE_TASK_ID)
    direction_id = str(candidate.get("direction_id", ""))
    step("grounded-direction", f"{direction_id} is a {candidate.get('status')} candidate")

    # -- 5. explicit approval through the real G1D boundary ------------------
    refusal = _attempt_plan_before_approval(state, direction_id, str(report["ar220"]["reference_set_id"]))
    report["refusal_without_approval"] = refusal
    step("refusal-without-approval", f"compile refused before approval: {refusal[:160]}")
    design_module.approve_direction(
        state, direction_id, identity=FIXTURE_APPROVER,
        note="AR-221 vertical slice: explicit fixture approval through the real G1D gate",
    )
    approved = design_module.direction(state, direction_id) or {}
    step(
        "explicit-approval",
        f"{direction_id} approved by {FIXTURE_APPROVER}; approval {approved.get('approval_id')}",
    )

    # -- 6. implementation references ---------------------------------------
    note_text = PATTERN_REFERENCE_FILE.read_text(encoding="utf-8")
    pattern_reference = inventory_module.implementation_reference(
        source="ariadne pattern note: two-pane split with a keyboard-operable divider",
        license_name="Apache-2.0 (this repository)",
        revision=f"frozen fixture, {len(note_text)} bytes",
        files_inspected=(str(PATTERN_REFERENCE_FILE.relative_to(Path(__file__).resolve().parents[4])),),
        reuse_status="REUSE_ALLOWED",
        pattern="divider contract: separator role, keyboard steps, clamped bounds",
    )
    report["pattern_reference_note_bytes"] = len(note_text)
    registry_reference = inventory_module.implementation_reference(
        source="Ariadne capability candidate registry (references/capabilities.json)",
        license_name="various; per-entry",
        revision="2026-09-05",
        files_inspected=("references/capabilities.json",),
        reuse_status="INSPECT_ONLY",
        pattern="candidate component sources; recorded as candidates, never resolved",
    )
    dependency_request = inventory_module.dependency_request(
        need="a resizable inspector divider",
        package="shadcn-ui resizable panels",
        requested_by="implementation reference for the divider contract",
        reason=(
            "the fixture's own density helpers cover the contract, so the registry candidate is recorded "
            "as evidence rather than adopted"
        ),
    )
    report["implementation_references"] = [
        pattern_reference, registry_reference, dependency_request,
    ]
    step(
        "implementation-references",
        f"pattern note {pattern_reference['reuse_status']}; registry {registry_reference['reuse_status']}; "
        f"dependency request {dependency_request['status']}",
    )

    # -- 7. the plan --------------------------------------------------------
    constraints = build_constraints(
        direction_record=approved, inventory_found=found, pattern_reference=pattern_reference,
        tokens=tokens,
    )
    forbidden, treatments, treatment_counts = _treatments(approved)
    state_record = inventory_module.record_inventory(
        state,
        task_id=TASK_ID,
        project_root=str(root),
        found=found,
        needs=("Panel", "Button", "NavItem", "Toolbar", "Divider", "IconButton", "DataTable"),
        recorded_at=stamp,
    )
    report["reuse_decisions"] = state_record["reuse_decisions"]
    step(
        "component-inventory",
        "; ".join(
            f"{row['need']}={row['decision']}" for row in state_record["reuse_decisions"]
        ),
    )
    try:
        plan_record = plan_module.compile_plan(
            state,
            direction_id=direction_id,
            reference_set_id=str(report["ar220"]["reference_set_id"]),
            project_root=str(root),
            target_surfaces=TARGET_SURFACES,
            constraints=constraints,
            component_reuse_decisions=state_record["reuse_decisions"],
            forbidden_copy_patterns=forbidden,
            validation_requirements=_validation_requirements(),
            implementation_references=[pattern_reference, registry_reference],
            borrow_adapt_avoid_bindings=treatments,
            created_at=stamp,
            note=f"compiled from: {SLICE_REQUEST}",
        )
    except ContractError as exc:
        report["failures"].append(str(exc))
        return report
    report["plan"] = {
        "plan_id": plan_record["plan_id"],
        "constraints": len(plan_record["constraints"]),
        "suppressed": plan_record["suppressed_constraints"],
        "forbidden": [row["pattern_id"] for row in plan_record["forbidden_copy_patterns"]],
        "bases": sorted({str(row["basis"]) for row in plan_record["constraints"]}),
        "treatment_bindings": len(plan_record["borrow_adapt_avoid_bindings"]),
        "treatment_counts": treatment_counts,
    }
    step(
        "implementation-plan",
        f"{plan_record['plan_id']}: {len(plan_record['constraints'])} constraint(s) across bases "
        f"{report['plan']['bases']}; {len(forbidden)} forbidden pattern(s); "
        f"{len(plan_record['suppressed_constraints'])} suppressed by precedence",
    )

    # -- 8. the worker packet ----------------------------------------------
    worker_packet = packet_module.build_worker_packet(
        state, plan=plan_record, inventory=state_record, references_by_id=references_by_id,
        allowed_scope=ALLOWED_SCOPE, forbidden_scope=FORBIDDEN_SCOPE,
    )
    attribution = worker_packet["context_attribution"]
    report["context"] = {
        "raw_reference_bytes_available": attribution["raw_reference_bytes_available"],
        "reference_bytes_transported": attribution["reference_bytes_transported"],
        "references_available": attribution["references_available"],
        "references_transported": attribution["references_transported"],
        "references_omitted": attribution["references_omitted"],
        "worker_packet_bytes": attribution["worker_packet_bytes"],
        "design_direction_bytes": attribution["design_direction_bytes"],
        "implementation_plan_bytes": attribution["implementation_plan_bytes"],
        "components_inspected": attribution["components_inspected"],
        "external_sources_inspected": attribution["external_sources_inspected"],
    }
    step(
        "worker-packet",
        f"{attribution['worker_packet_bytes']} bytes; "
        f"{attribution['reference_bytes_transported']} of {attribution['raw_reference_bytes_available']} "
        f"reference bytes transported; {attribution['references_omitted']} source(s) omitted with reasons",
    )

    # -- 9. the implementation ---------------------------------------------
    constraint_lookup = {
        f"{row['basis']}:{row['category']}": str(row["constraint_id"])
        for row in plan_record["constraints"]
    }
    try:
        changes = _apply_edits(root, IMPLEMENTATION_EDITS, constraint_lookup)
    except ContractError as exc:
        report["failures"].append(str(exc))
        return report
    step("implementation", f"{len(changes)} scripted edit(s) applied to {len({c['path'] for c in changes})} file(s)")

    # -- 10. mechanical validation -----------------------------------------
    report["toolchain"] = "PRESENT" if toolchain_present(root) else "ABSENT"
    runner = execution_module.ValidationRunner(project=root)
    if not validate:
        runner = execution_module.ValidationRunner(project=root, run=_no_run)
        report["validation_skipped"] = (
            "the slice was asked not to validate; no check was run and nothing here claims otherwise"
        )
    result = execution_module.run_grounded_implementation(
        state,
        plan=plan_record,
        project=root,
        inventory=state_record,
        references_by_id=references_by_id,
        implemented_changes=changes,
        validation_runner=runner,
        allowed_scope=ALLOWED_SCOPE,
        forbidden_scope=FORBIDDEN_SCOPE,
    )
    report["outcome"] = result["outcome"]
    report["validation"] = result["validation"]
    report["verdicts"] = result["verdicts"]
    report["escalation_reason"] = result["escalation_reason"]
    report["acceptance"] = result["acceptance"]
    report["telemetry"] = result["run_record"]["telemetry"]
    report["changes"] = [
        {
            "path": row["path"],
            "verdict": row["verdict"],
            "material": row["material"],
            "categories": sorted(row["categories"]),
            "constraint_ids": row["constraint_ids"],
            "change_kind": row["change_kind"],
        }
        for row in result["changes"]
    ]
    step(
        "mechanical-validation",
        f"outcome {result['outcome']}; "
        + "; ".join(
            f"{row['command']} {row['status']}" for row in (result["validation"].get("checks") or [])
        ),
    )

    # -- 11. provenance and trace ------------------------------------------
    report["trace"] = changes_module.render_trace(result["trace"])
    report["trace_gaps"] = result["trace"]["gaps"]
    report["change_summary"] = result["trace"]["summary"]
    step(
        "design-trace",
        f"{len(result['trace']['chain'])} link(s), {len(result['trace']['gaps'])} gap(s)",
    )

    report["contract_problems"] = (
        plan_module.plan_problems(state) + _state_problems(state)
    )
    report["completed"] = bool(
        result["outcome"] == "MECHANICALLY_VALIDATED" and not report["contract_problems"]
    )
    if not report["completed"]:
        report["failures"].append(
            "the slice did not reach a mechanically validated implementation: "
            + "; ".join(report["contract_problems"] or [result["escalation_reason"] or result["outcome"]])
        )
    report["state"] = state
    report["working_root"] = str(root)
    report["temporary"] = temporary
    report["run_summary"] = execution_module.summarise_run(result["run_record"])
    return report


def _no_run(*_args, **_kwargs):
    """A stand-in used only when the slice is told not to validate."""
    raise ContractError(
        "no executable toolchain was available, so mechanical validation could not run. The slice "
        "reports the absence rather than passing an unvalidated implementation"
    )


def _state_problems(state: Mapping) -> list[str]:
    """Every AR-220 and AR-221 cross-record check, over the shared run state."""
    from .. import references as references_module
    from ..design_reference import sets as sets_module

    return references_module.provenance_problems(state) + sets_module.provenance_problems(state)


def _attempt_plan_before_approval(state: Mapping, direction_id: str, reference_set_id: str) -> str:
    """Try to compile a plan from an unapproved direction, and capture the refusal.

    Recorded as evidence rather than assumed: the whole point of the approval boundary
    is that it holds under the pressure of needing something to consume, and a claim
    that it does is worth nothing without the attempt.
    """
    try:
        plan_module.compile_plan(
            state, direction_id=direction_id, reference_set_id=reference_set_id,
            project_root=".", target_surfaces=("navigation rail",),
            constraints=[plan_module.constraint(
                category="layout", statement="probe", basis="PROJECT_IDENTITY", evidence="probe",
            )],
            validation_requirements=_validation_requirements(),
        )
    except ContractError as exc:
        return str(exc)
    return ""


def _treatments(direction_record: Mapping) -> tuple[list[dict], list[dict], dict]:
    """Turn the direction's BORROW/ADAPT/AVOID treatments into executable bindings.

    An AVOID treatment becomes a *forbidden pattern* only when the pattern text yields
    literal signatures to check. When it does not, the treatment is still bound to the
    plan and still travels to the worker, but it is recorded as not mechanically
    detectable rather than being given a made-up detector. A prohibition nobody can
    evaluate is an intention, and dressing one up as a check would be worse than the
    gap it hides.
    """
    grounding = direction_record.get("ar220_grounding") if isinstance(
        direction_record.get("ar220_grounding"), Mapping
    ) else {}
    bindings: list[dict] = []
    forbidden: list[dict] = []
    counts = {"BORROW": 0, "ADAPT": 0, "AVOID": 0, "AVOID_NOT_DETECTABLE": 0}
    for index, row in enumerate(grounding.get("treatments") or []):
        if not isinstance(row, Mapping) or not row.get("treated"):
            continue
        treatment = str(row.get("treatment", ""))
        pattern = str(row.get("pattern", ""))
        reference_id = str(row.get("reference_id", ""))
        counts[treatment] = counts.get(treatment, 0) + 1
        detectors = plan_module.detectors_for_anti_pattern(pattern) if treatment == "AVOID" else []
        if treatment == "ADAPT":
            bindings.append({
                "reference_id": reference_id, "treatment": treatment, "pattern": pattern,
                "dimension": str(row.get("dimension", "")),
                "project_anchor": "the project's own tokens and primitives in src/styles/tokens.css "
                                  "and src/lib/ui.ts",
                "meaning": "the reference's scale is transformed onto the project's own values, not adopted",
                "mechanically_detectable": False,
            })
            continue
        bindings.append({
            "reference_id": reference_id, "treatment": treatment, "pattern": pattern,
            "dimension": str(row.get("dimension", "")),
            "project_anchor": "",
            "meaning": (
                "borrowed as a structural discipline"
                if treatment == "BORROW"
                else "excluded, and mechanically detectable as a forbidden pattern"
            ),
            "mechanically_detectable": treatment == "BORROW" or bool(detectors),
        })
        if treatment != "AVOID":
            continue
        if not detectors:
            counts["AVOID_NOT_DETECTABLE"] += 1
            continue
        forbidden.append(plan_module.forbidden_pattern_from_avoid(
            pattern_id=f"avoid-{index:03d}",
            reason=(
                f"the approved direction rules out {pattern!r} on the authority of counter-reference "
                f"{reference_id}; reproducing it is the shortcut the direction exists to prevent"
            ),
            reference_id=reference_id,
            anti_pattern=pattern,
            detectors=detectors,
        ))
    if not forbidden:
        forbidden.append(plan_module.forbidden_pattern_from_avoid(
            pattern_id="avoid-counter-default",
            reason=(
                "the approved direction's counter-reference rules out a glassmorphic card grid with "
                "gradient glows; that prohibition is executable even when no AVOID row carried a "
                "machine-detectable keyword"
            ),
            reference_id=str((grounding.get("counter_references") or [{}])[0].get("reference_id", "")),
            anti_pattern="a glassmorphic card grid with gradient glows",
            detectors=plan_module.detectors_for_anti_pattern("glassmorphic card grid gradient glows"),
        ))
    return forbidden, bindings, counts


def _validation_requirements() -> list[dict]:
    """The mechanical checks this fixture can actually run.

    ``npm run <verb>`` passes the transport's package-manager allowlist, and all three
    are real: a TypeScript compiler, a build that emits the document, and a test
    suite. Nothing here is a placeholder for a check nobody ran.
    """
    return [
        {"check_id": "beacon-typecheck", "command": "npm run typecheck", "kind": "typecheck", "required": True},
        {"check_id": "beacon-build", "command": "npm run build", "kind": "build", "required": True},
        {"check_id": "beacon-test", "command": "npm test", "kind": "test", "required": True},
    ]


__all__ = [
    "ALLOWED_SCOPE",
    "FIXTURE_APPROVER",
    "FIXTURE_SOURCE",
    "FORBIDDEN_SCOPE",
    "IMPLEMENTATION_EDITS",
    "PATTERN_REFERENCE_FILE",
    "TOOLCHAIN_MODULES",
    "toolchain_present",
    "SLICE_REQUEST",
    "TARGET_SURFACES",
    "TASK_ID",
    "build_constraints",
    "run",
]

