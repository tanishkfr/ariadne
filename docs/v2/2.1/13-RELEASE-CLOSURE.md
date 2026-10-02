# Ariadne 2.1 - Release Closure

The closure pass for `2.1.0rc1`. It closes the one correctness gap that remained after
the feature was complete: the Decision Runtime could abstain, and nothing in production
ever asked it to.

Everything here is verifiable. Where a claim could not be verified, it is not made.

---

## 1. The defect

`decisions.batch.evaluate` built its provider request without a `policy` key:

```python
request = {
    "batch_id": batch_id,
    "state_digest": projection_digest,
    "projection": dict(projection.get("entries") or {}),
    "questions": [question.as_record() for question in ordered],
    "instructions": (...),
}
response = dict(provider.answer(request) or {})
```

`LocalBoundedProvider.answer` forwards `request.get("policy")` to `session.decide`, and
`session._threshold(policy, min_confidence)` resolves to `None` when the policy is
absent. `None` is the correct answer to "nobody stated a threshold" - it is the whole
point of there being no default - and it is also what made the runtime's own threshold
path unreachable:

```
batch.evaluate -> request with no policy -> session._threshold -> None
              -> engine never compares -> BELOW_MIN_CONFIDENCE never raised
```

The machinery was not missing. `score_question` accepted `min_confidence`, the
`Score` carried a `BELOW_MIN_CONFIDENCE` reason, the provider counted abstentions, and
`scripts/test-decision-runtime.py` exercised all of it by calling `session.decide`
directly. Every one of those tests passed for the entire life of the feature while the
product could not abstain once, because every one of them bypassed the caller.

## 2. Root cause

The threshold was a parameter of the *engine* call with no producer. The calibration
machinery that could have produced it existed in
`decisions/runtime/profiles.py` and was reachable only from
`decisions/runtime/selection.py`, which is the promotion path and is not on the default
route. Nothing in `decisions.batch` - the actual production caller - consulted it.

This is the second time in 2.1 that a guard existed and was not reachable, and both
times it was invisible to a functional suite for the same reason: the suite tested the
component, not the route.

## 3. The wiring

One resolver, added to `decisions/batch.py`, answering one question per question in the
batch:

```python
resolved = effective_policy(
    state, ordered,
    runtime=provider.provider,
    implementation=provider.model,
    model_revision=provider.model_version,
)
effective = tighten_with_caller_policy(resolved, requested_policy)
request["policy"] = {
    "min_confidence_by_question": effective["min_confidence_by_question"],
    "calibration_profile_by_question": effective["calibration_profile_by_question"],
}
```

`effective_policy` calls `profiles.profile_for`, which already existed and already
answered exactly the right question. Nothing re-decides the matching rules: the resolver
asks, and honours the answer, including "no".

The engine, the session and the transport then carry the per-question thresholds:

- `session._per_question_thresholds(policy)` reads `min_confidence_by_question` and the
  profile that produced each one;
- `session.decide` / `decide_batch` send them as `min_confidence_by_question` and
  `calibration_profile_by_question`;
- the reference engine resolves `by_question.get(question_id, min_confidence)` per
  question, and records `threshold` and `calibration_profile_id` on the slot.

Per question rather than per batch is the load-bearing detail. A batch-wide threshold
would abstain a question whose profile justifies none, and would apply one risk class's
evidence to another's decision.

## 4. Calibration matching

A threshold exists only where `profiles.profile_for` accepts a `PROVEN` profile matching
all of:

| Bound | Source |
|---|---|
| decision definition | `question.projection_contract` |
| question schema digest | the question as asked, including its options |
| decision definition digest | the instructions the compiler wrote |
| question version | `definition_version` |
| runtime kind | `provider.provider` |
| implementation | `provider.model` |
| concrete model revision | `provider.model_version`, moving aliases refused |
| risk class | the profile must declare a threshold for it |

Only `PROVEN` supplies a threshold. `RETIRED`, `DRAFT`, `REVOKED` and every other status
supply none, and `RETIRED` in particular is checked by writing the status back to the
state - the bug fixed earlier in 2.1, where retirement was a silent no-op.

No matching profile means `threshold = None`. That is a valid outcome, not a failure, and
it is the outcome on a fresh installation.

## 5. A caller may tighten, never loosen

`batch.evaluate` accepts `requested_policy`. It is merged by `tighten_with_caller_policy`:

- a caller threshold **above** the resolved one is adopted, and is labelled
  `caller-stated (stricter)` rather than being recorded as calibration;
- a caller threshold **below** the resolved one is ignored, so a caller cannot buy its
  way past a calibration profile;
- a non-numeric, boolean or out-of-range value is discarded rather than coerced.

A caller also cannot mint a confidence kind. `confidence_kind` is validated against the
provider's own `describe()`, and `CALIBRATED_PROBABILITY` is not in it.

## 6. Abstention semantics

A below-threshold answer becomes a `refused` decision record - the existing vocabulary's
word for "policy would not accept this answer" - carrying:

- `status: "refused"` and `abstention_reason: "BELOW_MIN_CONFIDENCE"`
- `threshold_applied` and `calibration_profile_id`
- `candidate_answer` and `candidate_confidence`: the label and probability the engine
  actually reasoned with
- `answer: ""` and `answer_valid: false`: **there is no answer**

The engine keeps the evidence because discarding it would make an abstention
indistinguishable from never having looked. It is named `candidate_*` and the `answer`
stays empty, so a caller that looks for an answer still finds none.

`LocalBoundedProvider` gained `abstained_questions`, distinct from `failed_questions`. A
deliberate refusal and a crash are different events and previously looked identical.

The batch status is `partial` when a question is refused. Calling a batch `failed` when
policy said no would tell an escalation that something broke, when everything worked.

## 7. Escalation

No new ladder. `_bounded_answer` already computed `accepted = status == "answered"`, so a
refused row routes to the existing `escalation.escalation_for`, with
`source: "fallback-unknown"` and an honest `UNKNOWN` rather than an invented class. The
integration's `reason` now names the abstention:

```
the bounded engine abstained (BELOW_MIN_CONFIDENCE) and Ariadne escalated
```

There is no blind retry: the escalation changes what happens next, not the same model
answering the same question the same way again.

## 8. Authority

Unchanged and re-verified. `authorization_effect` is `"none"` on the decision record, the
provider response, the shadow record and the batch. `acted_on` is `False`. A
`PROTECTED`-consequence decision with a 0.97 confidence is still refused unless the
evidence reached `VERIFIED`.

**Confidence is evidence, not authority.**

## 9. A second defect this pass found

The decision cache key bound the question, projection, provider, model revision and
policy version - but not the effective threshold. So a decision cached before a profile
existed was served *after* one appeared:

```
classify_failure()                     -> answered, cached
record a calibration profile
classify_failure()                     -> served the pre-profile answer
```

The profile resolved correctly, the runtime abstained correctly, and the cache defeated
both. The effective threshold and its profile id are now part of the key, so a profile
appearing, changing or retiring invalidates cached decisions for it.

This was found by the golden workflow, not by reading: it only reproduced because that
test deliberately makes a first run before recording the profile.

## 10. Tests added

**Functional: 369 -> 425 checks.** `abstention_wiring_checks` covers cases A-J, the
protected-action case and the caller-forgery cases, all through
`decisions.batch.evaluate`. `golden_workflow_checks` runs two end-to-end workflows
through `classify_failure`.

| | Case | Expectation |
|---|---|---|
| A | matched profile, answer below threshold | `BELOW_MIN_CONFIDENCE` |
| B | matched profile, answer above threshold | accepted |
| C | no profile | no threshold invented |
| D | retired profile | ignored |
| E | draft / revoked profiles | ignored |
| F | wrong model revision | no threshold |
| G | wrong decision definition | no threshold |
| H | wrong question version | no threshold |
| I | LOW profile, HIGH decision | no threshold |
| J | mixed batch | per-question, no bleed |

**Mutations: 15 -> 25.** Ten added, all routed through the production caller:

| Mutation | Caught by |
|---|---|
| remove the resolved policy from the batch request | abstention does not fire |
| invent a universal fallback threshold | a threshold appears with no profile |
| let a RETIRED profile act | a retired profile supplies a threshold |
| ignore the model revision | a drifted profile supplies one |
| ignore the question version and schema digests | a v1 profile supplies one for v2 |
| borrow another risk class's threshold | a HIGH decision gets a LOW threshold |
| apply the first question's threshold to the batch | the sibling abstains too |
| discard the evidence behind an abstention | the candidate is gone |
| relabel a provider probability as calibrated | a rogue sidecar's claim passes through |
| let confidence grant authorization | a protected decision reports `acted_on` |

Four of the ten were re-targeted after the first attempt, because the mutant survived -
and in each case the reason was that *another* guard independently covered the same
property. A mutation that survives is not a caught mutation, and it is not evidence that
anything is load-bearing, so those four now target the guard that is actually
load-bearing. Two of them needed multiple simultaneous edits for the same reason.

**Benchmarks: 71 -> 76 in the release subset.** Five abstention cases added, all passing.

## 11. Adversarial attempts

Twelve attempts from the closure brief, all refused, all with a check:

| Attempt | Result |
|---|---|
| caller injects a fake calibrated flag | kind narrowed to `SELF_REPORTED_CONFIDENCE`, refused |
| caller injects an arbitrary threshold | adopted only when stricter, and labelled |
| retired profile reused | supplies nothing |
| profile from another model revision reused | supplies nothing |
| profile from another decision family reused | supplies nothing |
| profile from another risk class reused | supplies nothing |
| `None` confidence treated as 0 | confidence nulled before it reaches a record |
| confidence 0 treated as missing | refused as implausible, not recorded as absent |
| malformed threshold | discarded, not coerced |
| threshold outside `[0, 1]` | refused on the wire, ignored from a caller |
| low-confidence answer becomes authorization | `authorization_effect` stays none |
| batch threshold leaks between questions | per-question resolution, mutation-caught |

## 12. Performance

Measured on the reference engine, in-process, 200 iterations per row, on one machine on
one day. These are measurements, not thresholds, and nothing fails because a number
moved.

| Path | Measured |
|---|---|
| threshold resolution, one question, no profile | 0.011 ms |
| threshold resolution, one question, one recorded profile | 0.074 ms |
| `batch.evaluate`, one question, no policy | 0.197 ms |
| above-threshold path, one question | 0.185 ms |
| `batch.evaluate`, three questions, no policy | 0.431 ms |
| abstention path, three questions, one profiled | 0.393 ms |

The overhead is proportional and small: policy resolution is a digest over recorded
profiles, paid per question rather than per batch, and it is two orders of magnitude
below the call it guards. No premature optimisation was attempted; there was nothing to
optimise. The subprocess transport is not in these numbers and dominates them anyway -
its cost is process lifetime, not per-call work.

## 13. Documentation changed

- `RELEASE-NOTES.md` - the open item is removed and replaced with what is actually true,
  including the three runtime-identity spellings and the fact that abstention is a policy
  threshold and not truth detection.
- `README.md` - the abstention bullet states the profile-backed rule.
- `docs/v2/2.1/abstention-and-thresholds.md` - the production wiring, per-question
  resolution, and the caller-tightens rule.
- `docs/v2/2.1/calibration.md` - the runtime identity a profile must name.
- `docs/v2/2.1/evaluation-and-comparability.md` - unchanged; the abstention path does not
  affect comparability.
- This document.

## 14. Known limitations

1. Three spellings of the runtime identity exist in 2.1. A profile built against the
   wrong one never matches. The refusal names the mismatch, so it is visible, but it is a
   usability wrinkle rather than a designed interface.
2. No calibration profile ships with the runtime, so on a fresh installation the
   abstention path exists and is exercised by tests but never fires. That is correct - a
   threshold requires evidence - and means the operator-visible behaviour is unchanged
   until an operator measures one.
3. `python -m ariadne doctor` does not check the Decision Runtime. The engine
   controller's `ariadne decision-runtime --action doctor` does.
4. The reference engine is rule-derived, not trained.

## 15. Verification

```
scripts/test-decision-runtime.py            425/425
scripts/test-decision-runtime-mutations.py    25/25 mutations caught
scripts/test-engine-core.py                  578/578
scripts/test-decision-mutations.py             9/9 mutations caught
benchmarks --release                           76/76, 0 fail, 0 error
scripts/release-check.py                      green
```

Source commit and artifact hashes are recorded in the closure report, not here, because
this document is committed and the commit cannot contain its own hash.
