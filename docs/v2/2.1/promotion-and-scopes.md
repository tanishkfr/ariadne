# Promotion and scopes

Promoting a new implementation of a judgement is the riskiest thing Ariadne does
in the 2.1 milestone. This is how it is scoped so narrowly that the risk is
contained rather than managed.

## A slice, not a runtime

An adoption slice is not "the Decision Runtime". It is one exact tuple:

```
decision definition x question version x model revision x scope
```

Promotion applies to that tuple and nothing else. A slice promoted for low-risk,
reversible failure classification in English with verification available says
nothing about a protected dependency change, and the engine refuses to let it.

`promotion.find` matches on all three of definition, question version and
`revision_matches` on the model revision, returning the most recent matching
record. A slice promoted for a different revision, question version or definition
does not apply, even if its definition name matches exactly.

`open_slice` refuses a slice with an empty `model_revision`:
`adoption_slice_problems` requires it non-empty, and promotion without a pinned
revision would be a claim about a checkpoint that can move under it.

## The lifecycle

```
ADOPTION_STATES = UNTESTED, SHADOW, EVALUATED, ELIGIBLE, ACTIVE, SUSPENDED
```

| State | Meaning |
|---|---|
| `UNTESTED` | the slice exists and has never been evaluated |
| `SHADOW` | the runtime predicts; the authoritative path is unaffected |
| `EVALUATED` | measured evidence exists and is identity-bound |
| `ELIGIBLE` | the evidence and the risk policy permit promotion |
| `ACTIVE` | the runtime is authoritative for this slice, inside its scope |
| `SUSPENDED` | promotion was withdrawn; the previous authoritative path resumes |

A slice opens in `UNTESTED`, never `ACTIVE`.

## The transition table

`promotion.TRANSITIONS` is the only way a status changes, and it enforces the
order:

```
UNTESTED  ->  SHADOW, SUSPENDED
SHADOW    ->  EVALUATED, UNTESTED, SUSPENDED
EVALUATED ->  ELIGIBLE, SHADOW, SUSPENDED
ELIGIBLE  ->  ACTIVE, EVALUATED, SHADOW, SUSPENDED
ACTIVE    ->  SUSPENDED
SUSPENDED ->  UNTESTED, SHADOW, EVALUATED
```

Three things to read off that table.

- **`ACTIVE` can only be left for `SUSPENDED`.** There is no path from `ACTIVE`
  back to `EVALUATED` or `SHADOW`. To re-evaluate an active slice you suspend it
  first, which is the correct sequence anyway - you stop trusting it before you
  start measuring it again.
- **`UNTESTED` cannot reach `ACTIVE`.** The suite asserts that a straight
  `UNTESTED -> ACTIVE` transition raises, with a message naming the allowed
  targets.
- **A slice cannot be suspended twice.** `SUSPENDED -> SUSPENDED` is not in the
  table, so a second suspension raises. That is not pedantry: it stops a
  contradictory history being recorded.

Backwards moves exist where they should (`SHADOW -> UNTESTED`,
`ELIGIBLE -> EVALUATED`, `EVALUATED -> SHADOW`) because a measured slice that stops
measuring well is a fact about the evidence, not a mistake. What does not exist is
a shortcut forward.

## What ACTIVE requires

`promotion.transition(state, slice_id, target, reason=..., evaluation_id=...,
calibration_profile_id=...)` enforces, in addition to the table:

- **A non-empty reason.** Every status change is an adoption event, and an
  unlabelled one cannot be reviewed later. `transition(state, slice_id, "SHADOW")`
  with no reason raises.
- **An evaluation identity for `ELIGIBLE` and `ACTIVE`.** `evaluation_id` must be
  non-empty, or already present on the record. "Promoted" without one is an
  assertion rather than a record, and an assertion cannot be rolled back safely.
  `adoption_slice_problems` refuses an `ELIGIBLE` or `ACTIVE` slice without one,
  independently of the transition function.
- **A structurally valid record after the change.** `transition` re-validates and
  refuses rather than storing an invalid slice.
- **A valid scope.** Validated at `open_slice` and again inside `scope_matches` on
  every use.

A calibration profile id is accepted and recorded but **not** required. Nothing in
the transition path insists that an `ACTIVE` slice have a `PROVEN` calibration
profile, and the suite's promotion-to-`ACTIVE` case passes one. Read this as what
it is: `ACTIVE` means *this runtime's judgement is the recorded decision for this
slice inside this scope*, which is a statement about authority over a decision and
not about the quality of its probabilities. Calibrated probability is a separate,
separately-gated label. An operator who wants both should ensure both, and should
be aware the engine will not enforce the second for them.

## The history is an append

Each transition appends to the slice's `history`:

```
{"status": ..., "at": utc_now(), "reason": ..., "note": ...}
```

Nothing is rewritten and nothing is tidied. The suite asserts the exact history
after a promotion that went `UNTESTED, SHADOW, EVALUATED, SHADOW, EVALUATED,
ELIGIBLE, ACTIVE` - including the two `SHADOW` steps and the back-step - and
asserts that suspending appends rather than erases, so a later reviewer can see the
re-evaluation that actually happened rather than a clean path that never occurred.
`slice_problems` validates that every step in a stored history is a legal
transition from the previous one.

## The eligibility scope

`SCOPE_FIELDS = ("risk", "reversible", "languages", "verification_available")`.
`risk`, `reversible` and `verification_available` are structurally required and
type-checked; `languages` must be a non-empty list. An unknown field is refused.

| Field | What it means | Why it is here |
|---|---|---|
| `risk` | the consequence class the slice was evaluated for: `LOW`, `MEDIUM`, `HIGH`, `PROTECTED` | a threshold or accuracy measured for one consequence class does not transfer to another |
| `reversible` | whether the slice was evaluated on reversible operations only | promotion of an irreversible operation cannot be undone by suspending a slice |
| `languages` | the languages the evaluation covered | an accuracy measured in English does not transfer to German, and that has to be stated rather than assumed |
| `verification_available` | whether verification was available during evaluation | promoting a slice that cannot be verified removes the ability to catch it being wrong |

The reference installation declares `languages: ("en",)` - which is why a slice
evaluated there refuses to serve a `de` request.

## Scope is checked per call, not trusted from a record

`promotion.scope_matches(slice_record, requested)` is one-directional and strict:

- **Risk.** Widening is refused outright. A slice declared for `LOW` cannot answer
  a `HIGH` question. A slice proven safe for `HIGH` still covers `LOW` and
  `MEDIUM`, so narrowing is allowed - the ordering is `LOW < MEDIUM < HIGH <
  PROTECTED`.
- **Reversibility.** `if declared["reversible"] and not requested["reversible"]` -
  a slice declared reversible cannot serve an irreversible use.
- **Verification.** `if declared["verification_available"] and not
  requested["verification_available"]` - a slice that required verification does
  not cover an unverified use.
- **Languages.** `requested - declared` must be empty. Every requested language
  must appear in the declared set; extras are reported by name.

The check runs on **every call**, in `selection.select_bounded_provider`, before
the runtime is made authoritative. This is the answer to "why not just check the
scope once at promotion time": because the scope of a call is not the scope of the
promotion. A slice promoted for a low-risk, reversible, English, verified call
meets a high-risk irreversible call every time the caller happens to be in that
context, and the only moment at which the answer is known is the moment of the
call. Checking once would make the property a claim; checking per call makes it a
condition.

The consequence is worth internalising: **out of scope does not fail closed to
nothing - it falls back to shadow.** `select_bounded_provider` returns mode
`SHADOW` with the scope problems named, the runtime attached as an observer, and
the 2.0 provider returned as the answerer. The suite asserts this for each of the
four fields independently, and separately for a runtime reporting a different
model revision (which finds no slice at all, `slice: None`).

If a caller passes an explicit `scope`, that scope is what gets checked. Otherwise
one is built from the call's own context: `risk` from `consequence`,
`reversible`, `verification_available` and `languages` from the arguments.

## Suspension

`promotion.suspend(state, slice_id, reason=...)` delegates to
`transition(..., "SUSPENDED", ...)`. It is unconditional in the sense that matters:
**it requires no evidence, no evaluation identity, no profile and no scope check.**
It needs only a recorded reason and a legal source state.

The asymmetry is intentional and worth stating plainly: being able to stop a
thing quickly matters more than being able to start it carefully. Starting
requires the whole ladder and a measured evaluation; stopping requires a sentence
explaining why.

What suspension restores is immediate and complete. Because nothing was ever
migrated - a slice is a record, not a rewrite of the run - suspending simply
returns the next call to `SHADOW` mode with the 2.0 authoritative path answering
again. Nothing in the user's project changed; nothing needs undoing.

## Summaries

`promotion.summarise(state)` reports the slice count, a `by_status` breakdown over
all six states, and `active_definitions` - the sorted definition names that
currently have an `ACTIVE` slice. `active_for(state, decision_definition=,
question_version=, model_revision=)` returns a single caller-shaped result:
`{"active", "slice", "scope", "evaluation_id", "calibration_profile_id"}`.

`all_definitions`, `scopes_of` and `covered_languages` are read-only helpers for
diagnostics. The collection is bounded by `MAX_ADOPTION_SLICES = 200`; past the
bound, records are refused rather than truncated.

## The default posture

No adoption slice ships `ACTIVE`. Not one, for any definition, in any language. A
fresh run has `decision_adoption` absent entirely, `select_bounded_provider`
returns `SHADOW` whenever a runtime is present, and the 2.0 path decides
everything. Reaching `ACTIVE` is a deliberate act by an operator who has an
evaluation report in hand, a recorded reason, and a scope they are willing to
stand behind - and it takes one command to undo.
