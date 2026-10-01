# Calibration

Ariadne's confidence contract distinguishes five origins. Exactly one of them,
`CALIBRATED_PROBABILITY`, means a probability that has been measured against known
outcomes. Everything else is a weaker, differently-shaped claim.

| Kind | Meaning |
|---|---|
| `CALIBRATED_PROBABILITY` | the provider calibrated this against known outcomes |
| `PROVIDER_PROBABILITY` | the provider reports a probability it did **not** calibrate |
| `DERIVED_CONFIDENCE` | Ariadne computed it deterministically from evidence |
| `SELF_REPORTED_CONFIDENCE` | a generative model said a number; it is not calibrated |
| `NONE` | no confidence was supplied; the value stays unknown |

A `CalibrationProfile` is the only thing that may grant the first. It is
deliberately hard to obtain, and there is no path from a missing profile to a
calibrated label.

## Why the reference engine cannot have one

Naive Bayes over correlated features is systematically overconfident, and no
rescaling makes its output a statement about how often it is right. The shipped
engine therefore reports `PROVIDER_PROBABILITY` on every answer and says so in
three places that can be checked rather than believed:

- `status["confidence_kinds"]` is `("PROVIDER_PROBABILITY", "NONE")`;
- `status["calibration_self_granted"]` is `False`;
- every answer slot carries `confidence_kind: "PROVIDER_PROBABILITY"`.

And the claim is checked in the other direction too. `DecisionRuntime.problems()`
reports `"the decision runtime claims to grant its own calibration"` for any
runtime whose status sets `calibration_self_granted: True`, which makes the
provider refuse to serve it. The suite constructs exactly such a lying engine and
asserts the refusal. `LocalBoundedProvider.confidence_kinds()` is hard-coded to
`("PROVIDER_PROBABILITY", "NONE")`, so the adapter cannot relabel a number even if
an engine beneath it tried to.

The `install` output states the same thing in user-facing words: "probabilities
from this engine are uncalibrated by construction".

## The profile

`profiles.CalibrationProfile` is a frozen dataclass. Frozen on purpose: a
calibration profile that can be edited in place after it has justified a promotion
is not evidence, it is a mutable claim.

Fields:

```
decision_definition       the decision family it was measured for
question_version          the question version(s)
runtime                   "local_bounded" or "external_bounded"
implementation            the engine name
model                     the model name
revision                  the concrete model revision
dataset_digest            a digest of the dataset bytes
dataset_size              how many cases
question_schema_digest    the shape of the questions asked
decision_definition_digest the shape plus the wording
calibration_method        how the numbers were obtained
accuracy, coverage, ece, brier    the measurements
thresholds_by_risk        a threshold per consequence class
status                    DRAFT | PROVEN | SUSPENDED | RETIRED
owner, created_at, profile_id, note
schema_version, authorization_effect
```

`as_record()` adds `model_revision` so the stored record names the field the
validator checks.

### The two digests, and why there are two

- **`question_schema_digest`** covers the contract, question id, primitive, ordered
  answer space and definition version, sorted so set order cannot change it. It
  deliberately excludes instructions. A rewording is not a different schema - it is
  a different *question*, and it has to be visible as one rather than hidden
  inside an unchanged schema.
- **`decision_definition_digest`** covers the same fields **plus** instructions and
  consequence. Rewording changes the decision. A calibration measured on one
  wording is not a calibration for another, because the wording is part of the
  contract a reader would be trusting.

The suite exercises both directions: rewording invalidates a profile (through the
definition digest), and a profile measured on one decision family does not transfer
to another (failure classification and review escalation are separate calibration
domains).

### Methods

```
TEMPERATURE_SCALING   ISOTONIC   PLATT   BINNED_RELIABILITY   MEASURED_ONLY
```

`MEASURED_ONLY` reports accuracy, coverage, ECE and Brier without rescaling
anything. It is the honest default: measuring is not the same as correcting, and a
profile that corrects must say which correction it made. An unknown method is
refused at build time.

## The four statuses

| Status | Meaning |
|---|---|
| `DRAFT` | recorded but not proven; cannot produce `CALIBRATED_PROBABILITY` |
| `PROVEN` | measured on a bound dataset for a concrete revision |
| `SUSPENDED` | withdrawn pending re-evaluation; falls back to provider probability |
| `RETIRED` | superseded permanently |

`build_profile` sets the status from what was actually measured:

```python
status = "DRAFT"
if dataset_size >= MIN_PROFILE_DATASET:
    status = "PROVEN"
```

There is no argument that sets `PROVEN` directly, because a caller that can set
the status can also set the evidence. `SUSPENDED` and `RETIRED` are reachable only
through `set_profile_status`.

`set_profile_status(state, profile_id, status)` validates the status name and
that the id is recorded, replaces the stored record at its index with the updated
copy, and returns it. It writes into `state` rather than merely computing a value
and leaving the caller to store it: a profile an operator had withdrawn, still
licensing `CALIBRATED_PROBABILITY` through `profile_for`, is precisely the failure
a status field exists to prevent, and the write-back is what makes `SUSPENDED`
mean something.

## The dataset floor

`MIN_PROFILE_DATASET = 50`. Below it the numbers are reported but the profile stays
`DRAFT`, and a `DRAFT` profile cannot license anything.

Fifty is not a threshold that makes a model good. It is the point below which a
single disagreement moves accuracy by two points, so a "calibrated" label would be
a statement about sampling noise rather than about the engine. The validator also
requires a positive integer `dataset_size`, `accuracy` and `coverage` inside
`[0, 1]`, and non-negative `ece` and `brier`; and a `PROVEN` profile with any
structural problem is refused with the extra reason "a calibration profile cannot
be PROVEN while it has structural problems".

## The exact match set

`profiles.profile_for` is the only function that decides whether a probability may
be relabelled. It returns:

```
{"accepted": bool, "profile": dict|None, "profile_id": str,
 "reasons": [...], "confidence_kind": str, "min_confidence": float|None,
 "threshold_risk": str}
```

A profile must match **all seven**, and every mismatch is named:

1. **`decision_definition`** must be equal. Failure classification does not
   inherit review escalation.
2. **`model_revision`** must satisfy `manifest.revision_matches`.
3. **`runtime`** must be equal - `local_bounded` is not `external_bounded`.
4. **`implementation`** must be equal. A different engine is a different
   measurement.
5. **`question_schema_digest`** must equal the digest of the question as asked.
6. **`decision_definition_digest`** must equal the digest including wording.
7. **`question_version`** must contain the version the question declares.

Then, and only then: `status == "PROVEN"`, and the profile must have no structural
problems. When several profiles match, the largest `dataset_size` wins, with
`profile_id` as a deterministic tie-break.

Each of those keys closes a specific way a calibrated number could be a lie, and
the suite proves each one: a different revision invalidates the profile; a
`definition_version` bump invalidates it; rewording invalidates it; a different
family does not inherit it; a moving alias satisfies nothing.

An unknown risk class is refused before any profile is even considered, with
`reasons: ["unknown risk class: CATASTROPHIC"]`.

## Why a moving alias satisfies nothing

`manifest.revision_matches(expected, observed)` is deliberately unforgiving:

```python
if want == got:
    return not _is_alias(want)
return False
```

Two moving aliases never match each other, and neither matches a concrete
revision. `MOVING_ALIAS_REVISIONS` is `("latest", "stable", "default", "current",
"edge", "preview", "main")`, and `_is_alias` also matches a label ending in
`-<alias>`.

So a profile bound to `ar-206-reference-1` is not satisfied by a runtime reporting
`latest`, and a runtime reporting `latest` satisfies no profile at all. That is
the point: **a model that moves under a recorded decision must invalidate it.** An
alias in a calibration binding would mean the numbers were measured against one
artifact and applied to whatever arrived later.

The same refusal is enforced in the record validator:
`calibration_profile_problems` runs `_concrete_revision` over `model_revision` and
reports "calibration profile names a moving model alias, not a revision". The
weighting here is worth noting: an **adoption slice** validator requires only a
non-empty `model_revision`, not a concrete one - so a slice pinned to `latest` is
*valid* but inert, because `promotion.find` matches through `revision_matches` and
will never return it for a concrete revision. An inert slice is safe; a calibrated
alias would not be.

`DecisionRuntime.revision_satisfies(expected)` answers the same question from the
other direction, comparing a recorded revision against what the session actually
loaded.

## No path from a missing profile to calibration

When nothing matches, `_refuse` returns:

```
accepted         False
profile          None
confidence_kind  "PROVIDER_PROBABILITY"
min_confidence   None
reasons          the specific causes, deduplicated
```

Every refusal names its cause. With no profiles recorded at all, the reason is "no
calibration profile is recorded for this decision family". With a `DRAFT` profile
recorded, it is "the matching profile is DRAFT, not PROVEN". Neither outcome
produces a calibrated label, and neither produces a default threshold.

The note the module returns in `describe()` is the contract in one line:

> a profile is the only licence for CALIBRATED_PROBABILITY; without a matching
> PROVEN profile the result stays PROVIDER_PROBABILITY and no threshold applies

## Recording, and what survives

`record_profile(state, profile)` refuses an invalid profile rather than storing it
for later, and respects the collection bound
(`MAX_CALIBRATION_PROFILES = 200`): evidence is refused past the bound, not
truncated.

A profile that later becomes invalid - because the engine was rebuilt, the
question reworded, the dataset replaced - does not corrupt anything. It simply
stops matching, and `profile_for` returns the refusal with a reason. That is the
whole invalidation model: no cascade, no rewrite, no deletion. Nothing has to
remember to revoke it, because the match is recomputed from identity every time.

## The state of the default installation

There are no calibration profiles in a fresh install. Every probability the
shipped Decision Runtime reports is `PROVIDER_PROBABILITY`. The `doctor` action
reports `0 profile(s), 0 PROVEN` until an operator records one, and the CLI
install output says in words that the probabilities are uncalibrated by
construction. Nothing in the product attempts to make a rule table look like a
calibrated model, and there is no code path by which the runtime could do so.
