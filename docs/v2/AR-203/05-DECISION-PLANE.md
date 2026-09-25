# AR-203 — Decision Plane

Ariadne's intelligence hierarchy is now explicit and enforced by where work is
allowed to happen:

```text
Layer 1  deterministic computation   code decides what is knowable
Layer 2  decision intelligence       bounded judgement when the answer space can be closed
Layer 3  generative intelligence     creation, repair, synthesis, open-ended reasoning
Layer 4  verification                what actually occurred, independently established
Layer 5  human control               protected choices stay human, whatever a model thinks
```

The Decision Plane is Layer 2. It is deliberately small, provider-neutral and
optional: nothing in it requires a paid service, a network call or a third-party
dependency, and the architecture stays meaningful when no specialised decision
model exists.

## 1. Package layout

```text
src/ariadne_engine/decisions/
    __init__.py      the layer and its boundaries
    contracts.py     primitives, question validation, the decision record shape
    providers.py     the provider interface, the deterministic fixture, the optional adapter boundary
    policy.py        risk-adjusted acceptance; confidence is never authorization
    batch.py         independent questions over one projected state, durable records
```

## 2. Primitives

| Primitive | Answer space | Notes |
|---|---|---|
| `BinaryDecision` | one of two declared answers (default yes/no) | the two must differ |
| `ChoiceDecision` | exactly one of a declared option set (≥ 2) | the failure-classification primitive |
| `ScaleDecision` | one declared ordinal step (≥ 2, ordered) | severity, confidence bands |
| `MultiSelectDecision` | one or more of a declared option set, bounded by `max_selections` | included because a bounded multi-answer shape is needed and testable |

Every question declares its id, instructions, allowed answer space, consequence,
definition version and the digest of the projected state it was asked against.
`validate_answer` refuses anything outside the space and never coerces: an answer
outside the closed set is recorded as `invalid` with the raw value preserved.
**Type validity is not correctness** — an answer inside the space can still be
wrong, which is why a decision record is evidence of what judgement was produced,
never proof that a side effect occurred or that it was authorized.

## 3. The confidence contract

`contracts.CONFIDENCE_KINDS`:

```text
CALIBRATED_PROBABILITY     provider-calibrated; the raw distribution is preserved when supplied
PROVIDER_PROBABILITY       a probability the provider reports but did not calibrate
DERIVED_CONFIDENCE         Ariadne computed it deterministically from evidence
SELF_REPORTED_CONFIDENCE   a generative model said a number; it is not calibrated
NONE                       no confidence was supplied; the value stays null
```

A normal generative model saying "confidence 0.93" is `SELF_REPORTED_CONFIDENCE`
and never silently becomes calibrated confidence. `NONE` is a valid, recorded
answer; the value is never guessed. A record with a confidence value but kind
`NONE`, or an unknown kind, fails `contracts.decision_record_problems`.

Thresholds, if they ever exist, are keyed
`provider|model_version|primitive|question_id` (`policy.threshold_key`), so a
moving model alias cannot silently inherit an earlier version's calibration.
`policy.register_threshold` refuses an empty model version. AR-203 registers no
thresholds: no calibration data exists, and inventing one would be false
precision. The keying exists so a later milestone can add entries without a
contract change.

## 4. Confidence is not permission

Three invariants, enforced in code:

1. `policy.authorization_effect()` is always `"none"`, and every decision record
   stores it; `contracts.decision_record_problems` fails a record claiming
   otherwise.
2. `policy.protected_action_problems(record, action)` always returns a problem:
   a decision cannot authorize a protected action, whatever its confidence.
3. `policy.confidence_verdict` refuses a `PROTECTED` consequence regardless of
   confidence, and `may_act` returns `accepted: false` with `fallback: escalate`.

No rule in the Decision Plane grants a gate, a scope expansion, a dependency
install, a destructive action, an acceptance or a release. Decision evidence
informs policy; it never replaces authorization.

## 5. Risk-adjusted policy

`policy.MIN_EVIDENCE_BY_CONSEQUENCE` maps consequence to the evidence level the
judgement's supporting facts must reach, and `confidence_verdict` maps
consequence to acceptable confidence kinds:

| Consequence | Evidence behind the judgement | Confidence accepted | Fallback on refusal |
|---|---|---|---|
| `LOW` | none required beyond a valid answer | any kind, including `NONE` (marked low-confidence) | deterministic |
| `MEDIUM` | `OBSERVED` | `DERIVED`/`PROVIDER`/`CALIBRATED` | deterministic |
| `HIGH` | `REPRODUCED` | `CALIBRATED`, or `PROVIDER`/`DERIVED` plus independent verification | escalate |
| `PROTECTED` | `VERIFIED` (and still insufficient) | none | escalate to the human gate |

`may_act(record, consequence=..., verification_level=...)` combines answer
validity, confidence policy and evidence policy and always names the fallback:
deterministic path, or escalation. It never silently proceeds.

## 6. Batches and state projection

`batch.evaluate(state, questions=[...], projection=..., provider=..., ...)` asks
**one** provider call for a batch of **independent** questions. Questions must be
independent: no answer may depend on another answer in the same batch; a
dependent question is a second decision step. The batch record carries the batch
id, state digest, the projection, the question definitions, the provider identity
(provider, model, model version, request id, usage where available), the results
and the status (`answered`, `partial`, `failed`, `unavailable`).

`batch.project(entries={...})` bounds the projection: at most 64 named entries
and 16,000 characters, refused rather than truncated, because a decision made
against silently missing evidence is worse than no decision. The projection
digest is recorded on every decision, so a replay against a different state is
detectable (`a different projected state produces a different decision digest`).

Projections are built from the AR-202 adaptive-context material and carry only
what the question needs — a command result, a validator result, a previous
attempt, environment status, relevant failure evidence, a requirement and its
provenance. The full repository is never sent to a decision.

## 7. Providers

`DecisionProvider` is the interface: `available()`, `describe()`,
`confidence_kinds()`, `answer(request)`. Three implementations ship:

* `DeterministicProvider` — scripted answers, scripted confidence, scripted
  distributions, per-question or whole-provider failure. It exists for offline
  verification and never pretends to be a live model.
* `UnavailableProvider` — the honest default: nothing is configured, so the batch
  is `unavailable` and the caller falls back or escalates.
* `OptionalProviderAdapter` — a contract-only boundary for a licensed or
  specialised service (for example a Jev-style decision service). It is enabled
  only by an explicitly injected interface object; it never installs a
  dependency, reads credentials, opens a socket or calls anything implicitly.
  `requirements()` documents what a concrete adapter must supply: a concrete model
  version (a moving alias such as `jev-latest` is not acceptable as a recorded
  model identity), answers inside the declared space, probability/confidence
  metadata with its kind preserved, a provider request id, the raw provider model
  identity, and usage figures where exposed.

No concrete Jev adapter is implemented, no SDK is required and no paid call is
made anywhere in this milestone.

## 8. First real bounded-decision use

The first integration is **failure classification**
(`execution.classify_with_decision`), chosen because judgement there was
previously free-form and the deterministic fallback is safe:

1. **Code before judgment.** `execution.classify(source, detail)` maps the
   declared failure vocabulary. A mapped source is classified deterministically
   and no provider is consulted at all (`the deterministic path never consults a
   provider`).
2. **Bounded judgement only when needed.** Only an unmapped source may be put to a
   decision, and only inside `contracts.DECISION_CLASSIFIABLE_FAILURE_CLASSES`:
   implementation, validation, timeout, environment, provider, context, unknown.
   Authorization, revision, conflict and design failures are deterministic facts
   (a refused gate, a changed revision, an illegal state) and can never be
   model-derived; `record_failure` refuses a bounded-decision classification that
   names one.
3. **Deterministic fallback.** Provider unavailable, provider failure, an answer
   outside the set, or a policy refusal all produce `class: UNKNOWN`,
   `source: fallback-unknown`, `escalation_required: true` — with the decision
   record returned either way, so the attempt is evidence rather than a silent
   fallback.
4. **The class never authorizes anything.** It selects advisory flags
   (`retry_allowed`, `strategy_change_allowed`, `escalation_required`) that
   already existed; the human gates, scopes and authorizations are untouched.

The decision → action trace (`decisions.batch.trace`, `mark_acted_on`) makes
questions like *"why did Ariadne retry instead of escalating?"* answerable from
structured evidence: the decision record, its policy verdict, the action it drove
and the verification that followed — not from model prose.

## 9. Versioned decisions

Every model-backed decision records the requested provider, the requested
model/version, the observed provider/model where available, the decision-contract
version (`contracts.DECISION_CONTRACT_VERSION`), the schema version, and the
policy version (`decisions.policy.POLICY_VERSION`). A decision record is evidence
of what judgement was produced; it is not proof that the resulting side effect
occurred, and `acted_on` stays `false` until the engine records the action.

## 10. Events

`decision_batch_created`, `decision_recorded`, `decision_low_confidence` and
`decision_failed` join the canonical append-only event chain with the same digest
integrity as every other event; there is no second decision event system.

## 11. Tests

Engine suite (`ar203_checks`): valid choice decision with provenance,
fabricated execution refused, invalid answer refused, independent batch questions
in one call, missing confidence recorded as `NONE`, unavailable provider produces
an unavailable batch, protected action refused, medium consequence refuses
self-reported confidence, threshold keying, state-digest change, undeclared
confidence kind refused, and the four-way classification matrix.

Benchmark group `decision-plane`:
`valid-choice-decision-recorded`, `invalid-answer-refused-not-coerced`,
`confidence-provenance-preserved`, `missing-confidence-is-allowed-to-be-missing`,
`cannot-authorize-a-protected-action`, `batch-questions-are-independent`,
`deterministic-provider-failure-is-recorded`,
`first-real-use-keeps-code-before-judgment`.
