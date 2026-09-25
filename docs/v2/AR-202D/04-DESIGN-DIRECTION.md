# AR-202D — Design direction

Source: `src/ariadne_engine/design.py` (`create_direction`, `direction_subject`,
`approve_direction`, `direction_problems`), `policy.py`, `contracts.py`.

## 1. A direction is a constraint record, not a brief

A direction record captures exactly what constrains implementation:

| Field | Meaning |
|---|---|
| `product_context` | who this is for |
| `key_hierarchy` | what the eye must reach first, second, third |
| `interaction_principles` | how state changes behave |
| `visual_principles` | what carries emphasis |
| `content_principles` | what each surface must say first |
| `constraints` | what must not change or be added |
| `existing_system` | the project system to preserve |
| `reference_findings_adopted` | which analysed findings were taken |
| `findings_rejected` | what was deliberately **not** taken, and why |
| `accessibility_requirements` | how it stays operable and perceivable |
| `responsive_requirements` | how it behaves across viewports |
| `approved_deviations` | where it deliberately departs from the system |

Every one of those sections is required and must be non-empty. A direction
without `findings_rejected` is refused: a direction that rejected nothing has not
made a decision.

## 2. Actionable or refused

A statement is refused as unactionable when it names a mood instead of a rule.
`contracts._generic_direction` rejects short statements built only from
`modern / sleek / clean / minimal / elegant / premium / intuitive / beautiful /
delightful / polished`. The benchmark asserts the refusal on
`"modern, sleek and intuitive"`.

Actionable means checkable:

> "Primary action remains persistent at the bottom edge on mobile; secondary
> actions move into overflow."

is a rule somebody can verify from a screenshot. Directions are stored as
statements with an `actionable` flag derived from whether they carry a condition
(when/while/at/on/if/before/after/within/above/below), so the mechanical check
and the human reading agree.

## 3. Approval: gate `G1D`

| | |
|---|---|
| Gate | **`G1D`** (`contracts.GATE_SUBJECT_TYPES`) |
| Subject type | `design-direction-record` |
| Bound fields | `direction-id`, `task-id`, `scope`, `constrained-body` |
| Channel | `human-cli` only |
| Record | the same `policy.approve` approval record every other gate produces |

The approval is recorded through the one existing authorization writer, so it
inherits channel enforcement, identity recording, revision binding, listing and
consumption. `G1D` is a **separate gate on purpose** (ADR-001): `G1` authorizes
`DESIGN.md`, `G1D` authorizes the engine's constraint record, and neither can
substitute for the other. `policy.highest_gate` still tracks `G1`–`G5`, so mirror
writes and the stage ladder are untouched.

Refusals, all tested:

* **an implementer cannot approve its own direction** — an identity already
  recorded as this run's worker is refused;
* **no non-human channel** — `worker-cli` or any other channel raises
  `UnauthorizedApproval`;
* **a missing record** — approving an unknown direction id is refused;
* **nothing is recorded on refusal** — `status` stays `candidate`.

## 4. Binding and staleness

`contracts.direction_fingerprint` hashes the record id, the task, the scope and
the normalised bodies of every constraining section. Consequences:

* a material edit (adding an interaction rule, changing a responsive
  requirement) changes the fingerprint and **invalidates** the approval — the
  gate reports `stale`, and `design.direction_problems` reports
  `DESIGN_DIRECTION_STALE`;
* a cosmetic edit outside those sections does **not** invalidate it;
* an implementation boundary that requires the direction (`S4B`) refuses to
  proceed against a stale or missing approval and states which of
  `DESIGN_DIRECTION_MISSING` / `DESIGN_DIRECTION_UNAPPROVED` /
  `DESIGN_DIRECTION_STALE` applies.

A changed direction is also refused by the critique path: a design review cannot
judge against a revision nobody approved.

## 5. Proportionality

Direction is required in proportion to the work. `design.select_pipeline` marks
`DIRECT`:

* `REQUIRED` at `STANDARD` and `DEEP` depth;
* `OPTIONAL` at `MINIMAL` depth;
* `SKIPPED` when the task is not an interface task.

`policy.design_evidence_requirement` only demands an approval at `S4B` when the
plan selected `DIRECT: REQUIRED`. A spacing fix therefore selects
`DIRECT: OPTIONAL` and is never blocked by the direction workflow — asserted by
`design-direction.trivial-task-needs-no-direction`.

## 6. Traceability

A direction record is:

* **created** by the engine with `provenance.created_by = "engine"` and the
  policy version;
* **bound** to the implementation boundary's task revision (`revision_hash`);
* **approved** by a recorded human identity with the `G1D` approval id stored on
  the record (`status: "approved"`, `approval_id`, `approved_at`);
* **referenced** by each reference usage (`usage.direction_id`), by rendered
  evidence (`direction_id`), and by every design review
  (`direction_id` + `direction_revision`).

That chain is what makes "implemented within the approved direction" a claim with
a subject, a revision and an author rather than an assertion.
