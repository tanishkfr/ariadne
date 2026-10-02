# Shadow mode

Shadow mode is the pattern that makes promotion possible without risking it. It is
also the default posture of the shipped product, and the place where the runtime's
most important property is structural rather than promised.

## The order

```
1. the authoritative path runs, unmodified
2. policy judges the answer and the decision is recorded
3. only then does the runtime see the question and predict
4. the prediction is recorded beside the decision, as evidence
```

The order is not negotiable. A shadow mode implemented the other way round -
runtime first, then decide whether to use it - is a fallback with extra steps and
none of the evidence.

In the code, that order is `observe.observe(state, runtime, question=..., projection=...,
authoritative_answer=..., authoritative_decision_id=...)`. The caller passes in an
authoritative result that is already recorded. The observer returns a shadow record
and nothing else the caller can use.

The four real Ariadne integration paths (`decisions.integrations`) are wired the
same way. Each takes an optional `runtime=` and calls the observer only after
`planner.evaluate_step` has returned a judged, recorded decision. The suite asserts
that attaching a runtime changes none of `class`, `source`, `reason`,
`escalation_required`, `escalation`, the recorded answer or its validity - only the
`shadow` block differs.

## What is recorded

`shadow.record_shadow` writes one record per observation into
`state["decision_shadow"]` (bounded by `MAX_SHADOW_RECORDS = 10000`):

```
shadow_id, schema_version, shadow_version, run_id, task_id
question_id, primitive, definition, definition_version, question_identity
projection_digest
answer, distribution, confidence, confidence_kind
agreement, ground_truth, authoritative_answer, authoritative_decision_id
runtime_kind, runtime_version, implementation, implementation_revision,
model, model_revision, device
abstained, reason
execution_effect, authorization_effect, recorded_at
```

The projection is stored **as its digest**. The question is stored **as its
identity**: a digest over the question id, instructions, primitive and options, so
a record names which question was asked without keeping the question's text twice.
The runtime's full identity is stored, so a record can be traced to the exact
engine revision that produced it - and so a later model revision cannot be
credited with an earlier prediction.

The suite checks the projection text is genuinely absent from the stored record
(`"Traceback" not in json.dumps(record)`), not merely that the field was renamed.

## What is deliberately not kept

The module states this itself, and the statement is worth repeating because it is
the difference between evidence about a runtime and a second copy of the user's
project:

```
kept      question identity, projection digest, answer, distribution,
          confidence and its kind, runtime identity, comparison
not kept  projected state text, repository content, credentials
```

Only projected state crosses the boundary in the first place, and only the fields
the projection contract declares. The runtime never reads the repository, the
conversation, or the user's files; the projection is already the smallest
defensible slice of the run. Keeping even the projected text in a long-lived
collection would turn a diagnostic record into an archive of project content with
no retention policy - and `PRIVACY-POLICY.md` would then apply to it.

## The isolation check

Four mechanisms, all of which fail closed.

**1. The record has one legal `execution_effect`.** It is not optional and it is
not a parameter: `record_shadow` writes the literal `"none"`.

**2. The record is validated before it is stored.** `contracts.shadow_record_problems`
refuses any record whose `execution_effect` is not `"none"` ("a shadow prediction
cannot have an execution effect") or whose `authorization_effect` is not `"none"`.
`record_shadow` runs that validation and raises rather than storing an invalid
record.

**3. Stored records are re-validated on the way out.** `shadow.shadow_problems`
walks `state["decision_shadow"]` and reports every structural problem.
`observe.require_isolated` raises a `ContractError` on any problem, with the
message "shadow isolation is broken: ...". The shadow report surfaces
`isolation_problems` rather than hiding them. The suite tampers with a stored
record's `execution_effect`, asserts the problem is detected, and asserts
`require_isolated` raises.

**4. Nothing in the Plane reads shadow records to make a decision.** This is the
asymmetry that makes the property structural rather than conventional. The
collection is written by `observe` and read by `evaluation` and diagnostics. There
is no read path from `state["decision_shadow"]` into a decision.

Plus the inverse check: `shadow_effect_problems(state, decisions)` looks for a
decision that shares a `(task_id, question_id, state_digest)` with a shadow record
while carrying no `execution_id` - the shape an influence bug would take. It
reports rather than blocks, because a false positive costs a diagnostic line and a
false negative costs the invariant.

The suite also proves the observer cannot break a decision that already worked: an
engine whose `decide` raises produces `runtime_failed: True`, `recorded: False`,
and no shadow record in the state. And an unavailable runtime is never called at
all.

## Ground truth, and its source

`shadow.agreement` compares three strings - the prediction, the authoritative
answer, and an explicit ground truth:

```
no prediction, or no authoritative answer   -> UNKNOWN
prediction == authoritative answer           -> MATCH
different, and no ground truth               -> DISAGREE
different, with ground truth                 -> MATCH if truth == prediction, else DISAGREE
```

Ground truth is attached separately by `record_ground_truth(state, shadow_id,
ground_truth=..., source=...)`, and **it must name its source**: an empty source
raises, and an empty ground truth raises. An unreferenced "this was wrong" is how a
runtime gets blamed for a disagreement that was really an unclear question. The
default source is `"verification"`, and whatever is passed is stored as
`ground_truth_source` alongside the re-derived agreement and a `reconciled_at`
timestamp.

When ground truth is attached, the agreement is recomputed immediately and written
back into the record. Returning the reconciled record without storing it would make
the call look like it worked while the state kept the unreconciled one, and the
export would never see the outcome that was just reviewed.

## Agreement states, honestly

`contracts.SHADOW_AGREEMENTS` declares four: `MATCH`, `DISAGREE`, `UNKNOWN`,
`UNREVIEWED`.

What the code actually writes:

| Value | Written when |
|---|---|
| `MATCH` | prediction equals the authoritative answer, or ground truth equals the prediction |
| `DISAGREE` | they differ and no ground truth exists, or ground truth sides against the prediction |
| `UNKNOWN` | the prediction or the authoritative answer is empty; **and** for every abstention, which is forced to `UNKNOWN` by `record_shadow` |
| `UNREVIEWED` | **never written today.** It is a declared bucket, initialised to zero in the `by_agreement` count of the comparison summary, with no writer. |

That last row is a real gap between the declared vocabulary and the
implementation, and it is better stated than papered over. The contract comment
says "absence of ground truth stays `UNREVIEWED` rather than becoming a loss", and
the *behaviour* it describes is implemented - a disagreement without ground truth
is not counted as a loss - but it is expressed by excluding such rows from
accuracy, not by writing the string. If you are counting agreement states, expect
`MATCH`, `DISAGREE` and `UNKNOWN`, and treat `UNREVIEWED` as reserved.

An abstention is forced to `UNKNOWN` regardless of anything else. A runtime that
declined to answer has not agreed, has not disagreed, and has not been reviewed.

## DISAGREE is not a verdict

`DISAGREE` is a difference between two implementations, and nothing more. Only
recorded ground truth says which side was right. `shadow.compare` is explicit
about this:

```python
"match_rate":  len(resolved) / len(comparable)   # or None
"accuracy":    len(resolved) / len(comparable)   # or None
"coverage":    predicted / len(rows)             # or None
```

`comparable` is the set of records that did not abstain *and* carry ground truth.
Everything else is excluded. So:

- with no ground truth anywhere, `accuracy` is `None`, not `0.0`. A state with no
  shadow evidence summarises with `records: 0`, `accuracy: None`, `coverage: None`
  - no accuracy claim at all.
- a disagreement rate without ground truth measures how often two implementations
  differ. That is interesting. It is not accuracy, and `compare()` says so in its
  own `note`.

Counting an unreviewed disagreement as a loss would bias promotion against the
very implementation being measured, which is how a shadow mode becomes a
self-fulfilling demotion.

## The summary, and what the doctor shows

`shadow.compare(state, definition=...)` returns `records`, `predicted`,
`abstained`, `ground_truth_records`, `by_agreement` (all four declared states,
zero-initialised), `match_rate`, `accuracy`, `coverage`, `model_revisions` and the
note above.

`observe.shadow_report(state)` wraps it with `isolation_problems` and
`influence_problems` and restates `execution_effect: "none"`, delegating both
checks to the shadow module so there is one definition of "a shadow record that
claims it acted" and both callers agree on the answer.

The `doctor` CLI action prints the record count, the predicted and abstained
counts, the agreement breakdown, and accuracy - or the words
`accuracy      : unknown (no recorded ground truth)`.

## Batching in shadow

`observe_many` sends several independent questions over one projected state as a
single inference and records one shadow record per answer, reporting
`inference_calls: 1`. A question the runtime did not answer is recorded as an
abstention rather than dropped, so coverage is visible in the shadow collection
itself rather than only in the engine's return value.

## Selection, and what happens in each mode

`selection.select_bounded_provider` returns one of three modes, and only one of
them involves the runtime deciding anything:

| Mode | When | What the provider is |
|---|---|---|
| `AUTHORITATIVE` | an `ACTIVE` slice covers this exact tuple *and* this scope | `LocalBoundedProvider` |
| `SHADOW` | a runtime exists but no slice, no identity, or the scope does not cover this use | the 2.0 provider, unchanged |
| `FALLBACK` | no usable runtime | the 2.0 provider, unchanged |

An explicitly configured, available provider always wins and is returned
unchanged - 2.0 behaviour is preserved exactly. In `SHADOW` mode the returned
provider is the caller's own (or `UnavailableProvider`), so the existing fallback
runs untouched and the runtime's prediction is recorded as evidence.
`observe_if_shadow` does nothing in the other two modes: a runtime that only ever
runs in shadow is influencing nothing, and an authoritative runtime does not also
need to watch itself.

That precedence is what makes promotion reachable eventually. Every promotion is
preceded by however many shadow observations it took to gather, with the
authoritative path untouched the whole time.
