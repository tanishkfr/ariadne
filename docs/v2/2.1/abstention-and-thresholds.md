# Abstention and thresholds

An abstention is a named refusal, not a null answer and not a low number. This
document is about the difference.

The Decision Runtime can abstain when a decision falls below an evidence-backed
threshold. Thresholds are tied to matching calibration profiles and concrete model
revisions; Ariadne does not invent a universal confidence cutoff.

What abstention means, precisely: **the bounded decision is insufficiently trustworthy
for this policy.** It does not mean the task failed, that permission is revoked or
granted, that verification failed, that human review is required, or that the provider is
wrong. Ariadne's policy decides what happens next. And abstention is a policy threshold,
not truth detection - Ariadne does not know when a decision is wrong, only when measured
evidence is too weak for this decision.

## How a threshold reaches the runtime

There is exactly one producer, and it is the run's own recorded calibration state:

```
decisions.batch.evaluate(state, questions=..., provider=...)
    |
    +-- effective_policy(state, questions, runtime, implementation, model_revision)
    |       |
    |       +-- profiles.profile_for(...)  per question
    |             PROVEN + every binding matches -> threshold for that risk class
    |             anything else                 -> no threshold
    |
    +-- tighten_with_caller_policy(resolved, requested_policy)
    |       a caller may raise a threshold; never lower one
    |
    +-- request["policy"] = { min_confidence_by_question, calibration_profile_by_question }
              |
              +-- LocalBoundedProvider.answer -> session.decide(policy=...)
                    |
                    +-- engine: per question, by_question.get(qid, batch_level)
```

`effective_policy` is a caller, not a second policy engine. It calls the existing
`profiles.profile_for` and honours whatever it says, including "no".

A profile must name the runtime the way the provider names itself. On the decision path
that is `ariadne-decision-runtime`, which is the identity recorded in provenance. A
profile built against another spelling simply never matches, and the refusal says so.

## Per question, not per batch

Thresholds travel as `min_confidence_by_question`, and the engine resolves
`by_question.get(question_id, min_confidence)` for each question separately. A batch-wide
threshold would abstain a question whose profile justifies none, and would apply one risk
class's evidence to another question's decision.

```
Q1 threshold 0.72   Q2 no threshold   Q3 threshold 0.88
```

## What the refusal keeps

A `BELOW_MIN_CONFIDENCE` abstention is a `refused` decision record carrying
`abstention_reason`, `threshold_applied`, `calibration_profile_id`, and the
`candidate_answer` / `candidate_confidence` the engine actually reasoned with. The
`answer` stays empty: **there is no answer.**

Keeping the evidence is not a concession to usefulness. An abstention that discarded what
it had seen would be indistinguishable from never having looked, and the escalation that
follows could not be judged on the evidence - only obeyed.

## What a caller may do

`batch.evaluate(..., requested_policy=...)` lets a caller ask for a *stricter* gate. It
cannot lower a threshold Ariadne's evidence set, relabel a provider probability as
calibrated, or mark a decision authorised, acted on or verified. A caller threshold that
is adopted is recorded as `caller-stated (stricter)`, so it is never mistaken for a
calibration measurement.

## The cache is bound to the policy too

A decision cached with no threshold is a different decision from one made under a
threshold, so both the effective threshold and the profile that produced it are part of
the decision cache key. Without that, a profile appearing would silently have no effect
on any state that had already been decided.

## The structured reasons

`reference.score_question` refuses in three ways, each returning an `abstained`
score with a reason string. Only `BELOW_MIN_CONFIDENCE` keeps a label and a probability:
the other two had nothing to reason from.

### `NO_LOCAL_MODEL`

The question's identity digest is not present in this installation's weight book.
It is not "the confidence was low"; it is "this runtime has nothing fitted for
this question". The engine answers `abstained: true`, `answer: null`,
`valid: false`, and an empty distribution.

This is the honest state for a runtime with no weights at all. A missing
`weights.json` is not an error: `sidecar.build_engine` loads an empty book and the
engine abstains on every question with `NO_LOCAL_MODEL`, which Ariadne escalates.
Shipping with no weights would have made the "baked in" claim hollow - every
bounded question would abstain on a fresh install - which is why `seeds.py`
derives the first weight set from Ariadne's own tables.

The practical consequence is important for anyone adding a question: an unfitted
question is refused, not approximated. There is no nearest-neighbour fallback, no
default family, and no degraded scoring path.

### `BELOW_MIN_CONFIDENCE`

A threshold was supplied and the answer's probability did not meet it. The label
is cleared and the probability is zeroed, but the **distribution is returned**, so
a caller can see the shape of the disagreement rather than only its existence.
That is a deliberate choice: withholding the distribution would hide the fact that
the answer was close.

### `ANSWER_SPACE_MISMATCH`

A weight family *was* found for the question's identity, but its `labels` tuple
does not equal the space the question declares. This should be unreachable - the
identity digest already covers the ordered answer space - which is exactly why it
is a separate named refusal rather than a silent correction. If it fires, the
weight file and the question have diverged and the engine refuses to reconcile
them on its own.

### `UNSUPPORTED_PRIMITIVE` - a refusal, not an abstention

Worth separating, because it travels differently. An unsupported primitive makes
`score_question` **raise** `EngineError` containing `UNSUPPORTED_PRIMITIVE`,
rather than returning an abstained score. `decide_batch` catches that, records the
slot with `valid: false` and the message as its `reason`, and appends the slot key
to `failed_questions`. It does not appear in the `abstained` map.

So the distinction is: `NO_LOCAL_MODEL`, `BELOW_MIN_CONFIDENCE` and
`ANSWER_SPACE_MISMATCH` are abstentions - the engine engaged with the question and
declined to answer it. `UNSUPPORTED_PRIMITIVE` is a refusal - the engine could not
engage with the question's shape at all. Both leave the answer empty and both are
counted; they are counted in different places, and `usage.abstained` and
`usage.failed` are correspondingly different.

## No default threshold, anywhere

`session.DecisionRuntime._threshold(policy, min_confidence)` is the whole of the
policy, and it is four lines long:

```python
if min_confidence is not None:
    return float(min_confidence)
if isinstance(policy, Mapping):
    value = policy.get("min_confidence")
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
return None
```

An explicit caller value wins. Otherwise a contextual policy value is used.
Otherwise there is no threshold at all. The function returns `None`, `None` is
sent on the wire, and the engine scores without one.

The docstring gives the reason, and the reason is the whole design:

> There is no default. A runtime with no threshold answers everything it can and
> Ariadne's own abstention machinery decides what to do with weak answers - a
> universal constant like `0.8` would be a claim about every question at once.

That is the argument in full. A constant of `0.8` is simultaneously a claim about
failure classification, about review escalation, about evidence relevance and
about route family - four different questions, four different difficulty levels,
four different score distributions. A single number cannot be honest for all of
them, and picking one because it is comfortable is exactly the failure this
architecture is built against. There is no such constant anywhere in the shipped
product, and the suite asserts the resolution function directly.

Two smaller properties of the same function, both asserted:

- **A boolean is not a threshold.** `{"min_confidence": True}` yields `None`.
  Python would otherwise accept `True` as `1.0`, and a threshold of 1.0 is a
  number nobody should be able to set by accident.
- **Caller beats policy.** `policy={"min_confidence": 0.4}` with an explicit
  `min_confidence=0.9` sends `0.9`.

## How a caller or a policy supplies one

Three routes, in increasing order of authority.

**Per call.** `runtime.decide(state, questions, min_confidence=0.55)` sets it for
that call only. Through the provider, the same value rides in the request's
`policy` mapping, which `LocalBoundedProvider.answer` forwards as
`policy=request.get("policy")`.

**Per risk class, from a calibration profile.** A `PROVEN` profile carries
`thresholds_by_risk`, keyed by the declared consequence classes `LOW`, `MEDIUM`,
`HIGH`, `PROTECTED`. `profiles.profile_for` returns the threshold for the risk
class it was asked about, and it will not extrapolate one:

- a threshold declared for the requested class is returned as `min_confidence`;
- a class **narrower** than everything the profile declares - asking for `LOW` of
  a profile measured on `MEDIUM` - is accepted with `min_confidence: None` and the
  reason "the matched profile declares no threshold for LOW; no gate applies".
  Narrowing is the only direction that does not widen the evidence behind the
  number;
- anything else is **refused**: "profile <id> declares no threshold for risk class
  'HIGH'; it was measured for ['LOW']". Asking a profile measured on `LOW`
  examples to relabel a `PROTECTED` decision as calibrated, with no threshold to
  apply, would be exactly the overreach the profile exists to prevent.

So a threshold fitted for `LOW` never gates a `HIGH` question, and cannot be
borrowed to label one calibrated either.

**From the plane's own threshold registry.** `decisions.policy.register_threshold`
stores a calibrated threshold keyed by
`provider|model_version|primitive|question_id`, refusing an empty or alias-shaped
model version. That registry is separate from the runtime and is empty in 2.0 and
2.1; nothing registers into it by default.

## What happens with no threshold

The engine answers every question it can. `BELOW_MIN_CONFIDENCE` never fires
unless someone asked for a threshold. What decides whether a weak answer may drive
an action is Ariadne's own policy machinery, which reasons from the confidence
*kind* and the consequence class, and which escalates with the declared reasons
`LOW_CONFIDENCE` (a confidence kind that exists but is not strong enough) or
`NO_CONFIDENCE` (kind `NONE`).

This division is deliberate. Policy asks "is this answer good enough to act on for
*this* question at *this* consequence class"; the engine asks only "here is the
argmax and here is how far ahead it is". Collapsing the two would let a classifier
make a policy decision, and a policy decision is exactly what a classifier must
not make.

## Through the provider

`LocalBoundedProvider.answer` translates an abstention without softening it:

```
answer           None
confidence       None
confidence_kind  "NONE"
distribution     preserved from the runtime
abstained        True
reason           the engine's reason string
```

and the question id is appended to `failed_questions`, and `provider.abstentions`
is incremented alongside `provider.calls`. The provider's own counters are the
honest record: a provider that abstains on three of four questions has not
answered three questions.

The confidence kind is `NONE`, not `0.0`, and not the runtime's own probability
kind. `decisions.contracts.answer_from_provider` reports "a confidence value must
declare where it came from" when a `NONE` kind carries a value, so an abstention
cannot be re-read downstream as a confident zero.

## Coverage is visible

Because abstentions are counted rather than hidden, the question "how much of this
question does the runtime actually answer?" has an answer:

- `usage.abstained` and `usage.failed` per call;
- `provider.abstentions` and `provider.failures` cumulatively, both surfaced in
  `provider.describe()`;
- `coverage = answered / cases` and `abstention_rate = abstained / cases` in an
  evaluation report;
- `coverage` and `by_agreement` in the shadow comparison.

A runtime with good accuracy and 20% coverage is a different proposition from one
with the same accuracy and 100% coverage, and the records make the difference
impossible to miss. Nothing in the design rewards answering when it should
abstain.
