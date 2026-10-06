# 09 — Grounded Design Execution (AR-221)

> **Implementation must be traceable to an approved design direction, not directly
> to inspiration.**

AR-220 classified the *evidence* a design direction rests on. AR-221 is the layer
that has to lose nothing between that direction and a changed file, because a
direction is prose and code is not. Prose survives translation by being re-read; an
implementation plan does not.

## The permanent flow

```text
REFERENCE
    ↓
OBSERVATION
    ↓
DESIGN PRINCIPLE
    ↓
APPROVED DIRECTION
    ↓
IMPLEMENTATION CONSTRAINT
    ↓
CODE
```

And the shortcut AR-221 exists to refuse:

```text
REFERENCE → COPY UI
```

There is no code path from a reference to an edit. The only way a reference reaches
code is through a constraint the plan holds, and the only way a constraint reaches
code is through a change record that cites it.

## Six rules, each in code rather than in prose

| Rule | Enforced by |
|---|---|
| References do not produce code; approved principles produce constraints | `plan.approval_binding`, `plan.compile_plan` |
| Project identity outranks external inspiration | `contracts.CONSTRAINT_PRECEDENCE`, `plan.resolve_precedence` |
| Aesthetic precedent grants no dependency, file or execution authority | `packet.build_worker_packet`, `inventory.dependency_request`, `plan._validation_rows` |
| Every material design choice should have a reason | `grounding.classify_change`, `contracts.CATEGORY_GROUNDS_MATERIAL` |
| Source code proves implementation; only rendered evidence proves appearance | `contracts.PLAN_STATUSES`, `implementation_run_problems` |
| Reuse what exists before generating something new | `inventory.inventory`, `inventory.decide_reuse` |

## What was reused, and what was added

AR-221 extends the existing execution path. It does not have a parallel "design
executor". Concretely:

| Reused | From |
|---|---|
| `G1D` approval and its anti-self-approval rule | `design.approve_direction`, `policy.approve` |
| The `GRANTED`/fingerprint staleness check | `design.direction_problems` |
| Bounded repair arithmetic | `statemachine.worker_transition_for` via `execution.worker_transition` |
| Validation-command allowlist | `prepare-stage.safe_validation_argv`, reached through the new `policy.transport_tool()` seam |
| Path containment | `design_reference.safety.contained_path` |
| Injection scanning | `design_reference.safety.reference_text_is_data` |
| Context byte accounting | `economics.source_record`, `economics.source_accounting` |
| Scope semantics | `contracts.path_matches` |
| The event log | eight new names appended to `events.EVENT_TYPES` |
| The record family | `SCHEMA_DESIGN` record validators, `DESIGN_COLLECTION_KEYS` |

New, because nothing existed to extend: the plan record and its compiler, the
component inventory, the worker packet, the change classifier, the change records,
the design trace, and the run record.

## The four refusals that matter

**No approval, no plan.** `plan.approval_binding` requires the direction to carry
`status == "approved"`, requires the run to actually hold the recorded approval id,
requires that approval to bind the direction's *current* fingerprint, requires the
human channel, and refuses an approving identity that is this run's implementation
worker. There is no fixture bypass anywhere in the engine. The vertical slice's
approval is recorded by calling `design.approve_direction` with a declared test
identity — the same function an operator uses, through the same gate.

**The reference set must be the one the direction was built from.** A plan compiled
against a different set is a different design, however similar the topics.

**A reference principle cannot outrank a human decision.** Precedence is explicit and
contradictions are *suppressed and recorded*, not silently resolved:

```text
explicit user requirement      100
approved project identity      80
approved design direction      60
engineering constraint         55
implementation reference       30
reference principle            20
```

A final pass removes anything still outranked by a survivor, so precedence never
depends on the order constraints happen to be written in.

**Accessibility is a floor, not a competitor.** It has no precedence number because
it is not competing. A reference-sourced constraint is suppressed wherever it shares
a surface with a floor, in any category — the rule is keyed on the *origin* of the
constraint ("inspiration may not trade away accessibility") rather than on category
matching, because a reference-sourced layout constraint and an accessibility floor
share no category and would otherwise never meet.

## Materiality

Material design decisions need grounding:

```text
brand_color · type_family · type_scale · navigation_structure
primary_layout · component_geometry · interaction_model
motion_system · surface_language · responsive_structure · asset_identity
```

Everything else is incidental — a 1px alignment correction, a padding nudge,
vendor-prefix normalisation. Refusing incidental detail would train the workflow to
attach a rationale to every line, and the traceability record would stop meaning
anything.

Three verdicts, and the distinction between the first two is the whole design:

| Verdict | When |
|---|---|
| `GROUNDED` | a material change a cited constraint accounts for |
| `GROUNDED_INCIDENTAL` | a change no material category covers |
| `UNGROUNDED_DESIGN_CHANGE` | a material change with no basis |

plus three refusals that are not degrees of the same thing, because they call for
different responses: `ACCESSIBILITY_REGRESSION`, `REFERENCE_CLONING`, `OUT_OF_SCOPE`.

## Two directions that matter in the classifier

Two bugs in the first version of this layer were both about reading a diff in the
wrong direction, and both are now regression-tested:

**Categories come from the lines the change *added*, not the ones it removed.**
Reading removed lines too reported the deletion of a glass card as a
`surface_language` and `brand_color` decision — so the one edit the approved
direction explicitly asked for would be flagged as the failure the direction was
written to prevent. What a change removed is still reported, under
`removed_categories`, and a change that removes a material category *and* cites an
AVOID-bound constraint is `GROUNDED`, not incidental. That distinction matters: it is
the only way the counter-reference's effect is visible at all.

**Accessibility presence is measured over each whole version of the file.** An early
version computed a set difference over *diff lines* and included the removed lines in
the "after" set, which meant nothing could ever be lost and the check silently passed
everything. The real suite caught it on the first real vertical slice.

## The ceiling, and what is below it

`PLAN_STATUSES` has no `ACCEPTED` and no `APPROVED`. The highest outcome AR-221 can
record is `MECHANICALLY_VALIDATED`, and every run stores:

```text
acceptance.visual_acceptance = NOT_CLAIMED
acceptance.reason            = source inspection establishes that code exists and
                               passes its checks. It cannot establish that the
                               result looks or behaves like the approved direction.
```

The validator refuses a `VERIFIED_BY_RENDERED_CHECK` claim that names no independent
rendered check, and refuses a `NOT_CLAIMED` record that gives no reason — silence
would read as a claim that none was needed, which is the assumption the field exists
to remove.

Judging appearance is AR-222, and it needs a real browser render that this phase
deliberately does not build.

Next: [10 — Design Implementation Plan](10-DESIGN-IMPLEMENTATION-PLAN.md)