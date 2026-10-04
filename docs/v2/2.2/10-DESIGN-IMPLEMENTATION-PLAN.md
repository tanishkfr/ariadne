# 10 — The Design Implementation Plan

> **References do not produce code. Approved design principles produce implementation
> constraints.**

The `DesignImplementationPlan` is the record that converts an approved direction into
obligations on code. It is the first link in the chain that can lose information,
which is why every row in it names where it came from.

## The record

```text
DesignImplementationPlan (dip_…)
├── schema_version, plan_id, run_id, task_id, created_at
├── direction_id            the approved direction, by id
├── reference_set_id        the evidence set the direction was built from
├── approval_binding        gate G1D · approval_id · direction_revision_hash
│                           approved_at · identity · channel · note
├── project_scope           the root this plan may be implemented in
├── target_surfaces[]       what it governs: navigation rail, panels, typography…
├── constraints[]           the obligations themselves (§ below)
├── suppressed_constraints[] what precedence removed, and why
├── component_reuse_decisions[]
├── implementation_references[]   licence, revision, files, reuse status
├── borrow_adapt_avoid_bindings[]
├── requirement_bindings[] copied from the approved direction
├── reference_bindings[]    which reference reached which constraint
├── forbidden_copy_patterns[] each with a detector
├── validation_requirements[]    each resolved to a bounded argv
├── status                  READY · IMPLEMENTING · IMPLEMENTED
│                           · MECHANICALLY_VALIDATED · ESCALATED · REFUSED
└── provenance
```

## Constraints

```text
constraint_id    dic_…
category         layout · typography · color · spacing · component · interaction
                 motion · surface · responsive · navigation · accessibility · asset
statement        what the code must do
basis            PROJECT_IDENTITY · REQUIREMENT · APPROVED_DIRECTION
                 · REFERENCE_PRINCIPLE · IMPLEMENTATION_REFERENCE
                 · ENGINEERING_CONSTRAINT
authority        the precedence number, derived from basis
evidence         the file, token, section or observation this rests on
material         whether the decision needs grounding
treatment        BORROW · ADAPT · AVOID, when it came from a reference
surfaces[]       what it governs; empty means all of them
principle_ids[]  the extracted principles behind it
reference_ids[]  the references it rests on
accessibility_floor   whether it sits under the design rather than in the ranking
detectors[]      literal signatures, when absence can be checked mechanically
```

The constructor makes `category`, `statement`, `basis` and `evidence` mandatory and
keyword-only. The failure this record exists to prevent is a constraint carrying a
category and a statement and nothing else, so the arguments that make it mean
something cannot be omitted.

**Why `evidence` is mandatory.** A basis without a source is a label. `PROJECT_IDENTITY`
with no `tokens.css` line behind it is indistinguishable from `VIBES`, and the whole
precedence table is built on the difference.

## Categories versus material categories

The plan states what it *governs*; the classifier reports what *changed in the
source*. Two vocabularies, deliberately, and a declared correspondence:

```text
CATEGORY_GROUNDS_MATERIAL
  color          → brand_color
  typography     → type_family, type_scale
  spacing        → component_geometry
  layout         → primary_layout, responsive_structure
  navigation     → navigation_structure
  component      → component_geometry
  interaction    → interaction_model
  accessibility  → interaction_model
  motion         → motion_system
  surface        → surface_language
  responsive     → responsive_structure
  asset          → asset_identity
```

Matching the strings directly would ground a layout constraint for a font-size change
and refuse a navigation constraint for a `<nav>` — both wrong in the same direction:
the trace would look complete and mean nothing.

`spacing` maps to `component_geometry` deliberately. A padding nudge matches none of
the geometry signals and so stays incidental, while a row height, a `min-width` or a
radius does — which is the difference between tuning and committing to a geometry.

## Precedence

```text
explicit user requirement      100
approved project identity      80
approved design direction      60
engineering constraint         55
implementation reference       30
reference principle            20
```

Two rules, and only two:

1. **Authority.** Two constraints sharing a category and an overlapping surface are
   competing for one slot. The lower precedence loses, and the loser is *recorded*.
2. **Literal contradiction.** At *equal* authority they conflict only when both commit
   to a concrete value and the values differ. Two constraints that defer to the
   project's tokens agree, and neither is dropped.

Then an **accessibility pass**: a floor is never suppressed, and every
reference-sourced constraint that shares a surface with one is. And finally an
**authority pass** over the survivors, because the incremental loop can only suppress
a constraint that arrives *after* the one that beats it — without this, writing the
borrowed palette first and the project identity second would let the borrowed palette
stand, which is precisely how an accidental ordering becomes an unstated policy.

An empty `surfaces` list means **all** surfaces, not none. Scoping a constraint narrows
it; it never exempts it. An earlier version treated empty as "collides with nothing",
which quietly immunised every unscoped rule — including colour.

## Detectors and prohibitions

An AVOID treatment becomes a `forbidden_copy_patterns` entry only when its text yields
literal signatures to check. When it does not, the treatment is still bound to the
plan and still travels to the worker, but it is recorded as *not mechanically
detectable*. A prohibition nobody can evaluate is an intention, and dressing one up as
a check is worse than the gap it hides.

```text
pattern_id          avoid-051
anti_pattern        glassmorphic card grid
detectors[]         backdrop-filter, -webkit-backdrop-filter, card-grid,
                    glass-card, hero-card
outcome_on_match    REFERENCE_CLONING
reason              the counter-reference rules this out
```

Detectors match **what the change introduced**. A detector that only looks at the
state after the change cannot tell an implementation that reproduces a reference from
one that deletes it — and the second is exactly what an AVOID treatment asks for.
Mentions are excluded: a test asserting `backdrop-filter` is absent necessarily
contains the string, and a detector that punishes its own regression test gets
switched off within a week, taking the prohibition with it.

## Approval binding

```text
approval_binding
  gate                    G1D — the same gate as 2.1 direction approval
  approval_id             must exist in state["approvals"]
  direction_revision_hash must equal contracts.direction_fingerprint(direction)
  channel                 must be the human channel
  identity                must not be this run's implementation worker
```

The revision hash is what makes the binding live rather than historical: edit the
direction after approval and every plan against it becomes stale and is refused,
which is checked both at compile time and by `plan.plan_problems` on every read.

## Validation requirements

Declared as commands, resolved to bounded argv through the **existing** transport
allowlist (`prepare-stage.safe_validation_argv`), reached via the new
`policy.transport_tool()` seam. Re-implementing that allowlist inside the engine would
create a second one that could drift from the one S4B actually enforces.

The reason this is not decoration: validation commands arrive from design material, and
design material has already been shown to contain instructions aimed at execution.
Routing them through the existing boundary means a reference cannot smuggle `sh -c`
into the mechanical checks that certify its own implementation.

A plan whose every declared check is optional is refused. A plan with no check at all
is refused. "Mechanical validation" that may be skipped certifies nothing.

## Refusals at compile time

```text
direction not approved
direction has no reference-set grounding
reference set is not the one the direction was built from
approval id not recorded in this run
approval is for another gate
approval did not arrive on the human channel
approval is stale against the current direction
approving identity is this run's implementation worker
target surfaces not named
no implementation constraint proposed
every proposed constraint suppressed by precedence
no mechanical validation requirement
every declared validation optional
validation command refused by the transport boundary
plan malformed against contracts.implementation_plan_problems
```

## Read it

```bash
python scripts/ariadne.py design-implementation-plan --run-root <run>
python scripts/ariadne.py design-implementation-plan --run-root <run> --json
```

```python
from ariadne_engine import api
view = api.implementation_plans(state)   # PROVISIONAL
```

Next: [11 — Component Reuse](11-COMPONENT-REUSE.md)