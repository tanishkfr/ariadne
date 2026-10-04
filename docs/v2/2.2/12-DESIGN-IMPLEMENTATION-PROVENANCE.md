# 12 — Design Implementation Provenance

> **Every material design choice should have a reason.**

AR-220's provenance answered *"why does the direction say this?"* AR-221's answers
*"why was this file changed?"* — and, more usefully, **a missing link is visible**.

## The change record

One per meaningful UI change, at file/component level:

```text
change_id                 dic_…
plan_id  task_id  path  component
change_kind               restructure-shell, remove-glass-cards, …
verdict                   GROUNDED · GROUNDED_INCIDENTAL
                          · UNGROUNDED_DESIGN_CHANGE · ACCESSIBILITY_REGRESSION
                          · REFERENCE_CLONING · OUT_OF_SCOPE
material                  bool
categories{}              the material categories the *added* lines touched
removed_categories{}      what the change took out — the evidence an AVOID produced
constraint_ids[]          every constraint the implementation *declared*
grounding_constraint_ids[] the subset that actually accounts for the change
reference_ids[]  principle_ids[]  requirement_ids[]
treatment                 BORROW · ADAPT · AVOID
implementation_source     who did it
validation_status
explanation  problem
```

Per-line provenance is deliberately absent. It would be a large volume of assertion
nobody reads, and a reviewer who cannot read the provenance does not check it.

### `constraint_ids` versus `grounding_constraint_ids`

Both, because the difference is the useful part:

```text
constraint_ids           "I consulted these while making this change"
grounding_constraint_ids "these are the ones that account for it"
```

A change citing a colour constraint while changing only geometry records the colour
constraint as *consulted* and nothing as *grounding* — and is `UNGROUNDED_DESIGN_CHANGE`.
Without the split, a record cannot tell "I read it" from "it justified this", and one
that cannot tell is a record that will accept any citation at all.

Mutation testing found this: an early classifier dropped `reference_ids` while keeping
the verdict, and every test still passed. Both are now separately asserted.

## The run record

```text
run_record_id  plan_id  task_id  started_at  finished_at
outcome             IMPLEMENTED · MECHANICALLY_VALIDATED · ESCALATED · REFUSED
validation_attempts[]  attempt · status · checks[] · returncode · stdout/stderr digests
constraint_exposure[]  constraint_id · outcome · detectors · files_checked
escalation_reason
telemetry{}
acceptance          visual_acceptance · reason
```

`acceptance` is the permanent invariant:

```json
{
  "visual_acceptance": "NOT_CLAIMED",
  "reason": "source inspection establishes that code exists and passes its checks. It cannot establish that the result looks or behaves like the approved direction; that judgement needs rendered evidence, which is out of scope for this phase"
}
```

The validator refuses a `VERIFIED_BY_RENDERED_CHECK` that names no independent rendered
check, and refuses a `NOT_CLAIMED` with no reason.

## Context economics

Measured, never estimated, and never converted into tokens:

```json
{
  "raw_reference_bytes_available": 111885,
  "reference_bytes_transported":    20471,
  "references_available": 5, "references_transported": 1, "references_omitted": 4,
  "design_direction_bytes": 4546,
  "implementation_plan_bytes": 4062,
  "worker_packet_bytes": 14423,
  "components_inspected": 5,
  "external_sources_inspected": 1,
  "transport_budget_bytes": 24576
}
```

Selection is by **reach**, not relevance guesswork: a reference is transported only
when the plan holds a constraint that cites it. Everything else is recorded as omitted
with its size and the reason. That is a deterministic rule a reviewer can reproduce,
which a relevance judgement cannot be.

Two distinct omission reasons, and the distinction is tested:

```text
no approved implementation constraint cites this reference.
  It informed the direction's reasoning but obliges nothing in the code

transporting it would exceed the packet budget of 24576 bytes.
  The constraint still applies; the packet cites the principle instead of the whole document
```

The packet's own interpretation field says plainly:

> byte counts are measured, not estimated, and never converted into tokens. The reduction
> in transported reference bytes is a reduction; it is not a measured quality improvement
> and no price profile was applied.

## The design trace

```text
Requirement
    ↓
ReferenceSet
    ↓
Principle
    ↓
Approved direction
    ↓
Implementation constraint
    ↓
File/component
```

```bash
python scripts/ariadne.py design-implementation-trace --run-root <run>
```

```text
Design trace for plan dip_20261004T013142Z_c7d1a5e0
  ok  REQUIREMENT         navigation is addressed consistently by 2 inspected source(s)…
  ok  REFERENCE_SET       rfs_20261004T013142Z_a3f81c22
  ok  PRINCIPLE           prn_20261004T013142Z_5c1e77b3
  ok  APPROVED_DIRECTION  ddr_20261004T013142Z_2b9f0e11
  ok  CONSTRAINT          dic_…  (in a file)
  ok  CONSTRAINT          dic_…  (holds by absence: verified, not exercised)
  ok  FILE                src/styles/app.css
  ok  FILE                src/lib/panel-split.ts
  ok  FILE                src/app/shell.ts
  ok  FILE                tests/direction.test.ts
  no gaps: every constraint reached a file and every file cites a constraint
```

### Gaps, and two things that are deliberately not gaps

A gap is reported, never repaired. A trace that quietly fixed itself would be worse
than no trace, because it manufactures exactly the confidence a reader was checking
for.

Two things are **not** gaps, and calling them gaps would make the report cry wolf:

* **`GROUNDED_INCIDENTAL`.** A file in the chain with a positive verdict is not a hole
  in it. Earlier versions listed them as gaps, which buried the real ones.
* **A constraint that holds by absence.** "Do not introduce a literal colour" is
  satisfied by nobody writing one. Demanding a file that proves a negative would push
  authors to fabricate a change so the trace looked tidy, so the run records
  `VERIFIED_BY_ABSENCE` with the detectors it checked and the files it checked them in.
  A constraint with no detectors and no citing change stays `NOT_EXERCISED` and stays a
  gap — nothing can excuse a constraint it cannot actually check.

## Ungrounded-change detection

Structural detectors over the diff: literal colour values, `backdrop-filter`, a new
`@keyframes` block, a removed `aria-*`/`tabindex`/`:focus-visible`, a nulled focus ring,
an external brand asset, a bare directory name treated as authority.

What this can and cannot decide, stated in the module:

* It **can** catch the choices that announce themselves in source.
* It **cannot** evaluate taste, judge whether a layout reads well, or prove that a
  change looks right. Refusing to pretend otherwise is what keeps the three verdicts
  worth reading.
* A cloning match **records** a finding and never silently edits the code away. Silent
  removal is how a cloning attempt becomes invisible instead of refused.

## From the vertical slice

```text
material changes: 9, grounded: 9, ungrounded: 0
accessibility regressions: 0
cloning findings: 0
grounded-incididental: 3
trace gaps: 0
components reused 6 · created 1
dependencies installed 0
validation attempts 1 (repairs: 0)
visual acceptance NOT_CLAIMED
```

Nine material decisions across four files, every one accounted for by a constraint
whose basis is recorded, and no gap in the chain.

## Events

```text
design_implementation_plan_created
design_component_inventory_created
design_component_reuse_selected
design_implementation_started
design_implementation_change_recorded
design_implementation_ungrounded_change
design_implementation_validated
design_implementation_escalated
```

The brief's dotted names map onto this log's existing convention rather than starting
a second one: `design.implementation.plan_created` is recorded as
`design_implementation_plan_created`, next to `design_direction_approved`.

Next: [13 — Design Execution Security](13-DESIGN-EXECUTION-SECURITY.md)