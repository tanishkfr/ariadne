"""Grounded Design Execution: AR-221's implementation layer.

> **Implementation must be traceable to an approved design direction, not directly
> to inspiration.**

The permanent flow this package enforces:

```text
REFERENCE → OBSERVATION → DESIGN PRINCIPLE → APPROVED DIRECTION
         → IMPLEMENTATION CONSTRAINT → CODE
```

and the shortcut it refuses:

```text
REFERENCE → COPY UI
```

Six permanent rules, each enforced in code rather than asserted in prose:

> **References do not produce code. Approved principles produce constraints.**
> **Project identity outranks external inspiration.**
> **Aesthetic precedent grants no dependency, file or execution authority.**
> **Every material design choice should have a reason.**
> **Source code can prove implementation; only rendered evidence can prove appearance.**
> **Reuse what already exists before generating something new.**

The module map:

===================  =========================================================
:mod:`plan`          ``DesignImplementationPlan``; approval binding, precedence
:mod:`inventory`     project-first component discovery, reuse decisions, licence
:mod:`packet`        minimal reference context and its omission record
:mod:`grounding`     materiality, ungrounded changes, cloning, accessibility loss
:mod:`changes`       change records and the queryable design trace
:mod:`execution`     implement → validate → bounded repair → escalate
:mod:`vertical_slice`one real front-end fixture carried end to end, offline
===================  =========================================================

**Where this stops.** AR-221 ends at grounded implementation plus mechanical
validation. It never records a visual-acceptance claim, because source inspection
cannot produce one; judging whether the result looks like the approved direction
needs a real browser render, and that is the next phase's job.
"""

from __future__ import annotations

from pathlib import Path

from .. import contracts  # noqa: F401  (re-exported for callers of this package)
from . import (  # noqa: E402
    changes,
    execution,
    grounding,
    inventory,
    packet,
    plan,
)

FIXTURE_ROOT = Path(__file__).resolve().parent / "fixtures"
"""The frozen front-end fixture the vertical slice compiles against.

Committed in the state a project scaffold leaves a real repository in: real tokens,
real components, real build scripts - and a generic, undesigned shell. The slice then
implements an approved direction into a copy of it and mechanically validates the
result. Nothing here is mock output.
"""

IMPLEMENTATION_REFERENCE_ROOT = Path(__file__).resolve().parent / "fixtures" / "implementation-references"
"""Frozen implementation references, read for patterns and recorded with their licence."""


def summarise_state(state) -> dict:
    """A short machine view of everything AR-221 recorded in a run.

    Read-only, so inspecting an implementation can never change it.
    """
    plans = plan.plans(state)
    inventories = inventory.inventories(state)
    change_rows = changes.changes(state)
    runs = execution.runs(state)
    return {
        "plans": len(plans),
        "component_inventories": len(inventories),
        "implementation_changes": len(change_rows),
        "implementation_runs": len(runs),
        "plan_statuses": sorted({str(row.get("status", "")) for row in plans}),
        "outcomes": sorted({str(row.get("outcome", "")) for row in runs}),
        "change_summary": changes.change_summary(change_rows),
        "visual_acceptance_claimed": any(
            str((row.get("acceptance") or {}).get("visual_acceptance", "")) == "VERIFIED_BY_RENDERED_CHECK"
            for row in runs
        ),
        "note": (
            "visual_acceptance_claimed is False by construction in AR-221. It is reported rather than "
            "assumed so a reader can confirm no run quietly claimed appearance from source inspection"
        ),
    }


__all__ = [
    "FIXTURE_ROOT",
    "IMPLEMENTATION_REFERENCE_ROOT",
    "changes",
    "contracts",
    "execution",
    "grounding",
    "inventory",
    "packet",
    "plan",
    "summarise_state",
]