# Overview

## What the Decision Runtime is

Ariadne routes every task down a ladder of three forms of intelligence:

```
deterministic computation  ->  bounded local decision  ->  generation
```

The middle rung was the one nobody had built. 2.0 had the plane around it - a
compiler that classifies each unresolved requirement, a projection that narrows
the state a question needs, a planner that batches independent questions, policy
that judges, a cache that binds the answer to the state and revision that produced
it, and a structured escalation ladder. What it did not have was a bounded
implementation that ships with the product. With no provider configured, every
decision path reported `unavailable`.

The Decision Runtime is that implementation, and only that. It is a small local
engine plus the machinery required to use one without trusting it: a narrow wire
protocol to a sidecar process, a question-identity scheme that binds weights to a
question, a shadow mode that watches decisions without touching them, a
calibration licence, a scoped promotion lifecycle, and an evaluation harness that
refuses to compare two runs that are not the same experiment.

It ships with weights derived from Ariadne's own decision tables
(`ariadne_engine.decisions.runtime.seeds`), which is what makes the middle rung
reachable on a fresh install with no download, no network, no paid API and no
third-party dependency.

## The problem it solves

Four problems, in the order they bite.

**Bounded judgement was unreachable.** A task that needed a closed judgement -
which failure class, how much review, does this evidence support the requirement -
had no cheap answer. It either went to a generative model, at generative cost and
generative risk, or it was resolved by an LLM-shaped proxy that Ariadne then had
to distrust. Neither is the same as a bounded classifier with a declared option
set.

**A bounded answer is easy to over-trust.** Once a number exists, there is a
strong pull to read it as a verdict, and a stronger pull to gate on it. Every
Ariadne record already separates decision from authorization, execution from
verification, and verification from acceptance. The risk here is narrower and
sharper: that a newly-introduced local model gets read as though it were an
approval, a proof, or a licence.

**The natural way to add a model makes the product worse.** Bounded inference is
the one place a machine-learning stack would genuinely help, and it is also the
place where a 118 MiB wheel and 800 MiB to 2.5 GiB of CUDA would land inside
`pip install ariadne`. Making that decision silently, inside an install, is not a
decision a user consented to. So the engine lives behind a subprocess boundary and
the shipped engine is pure standard library.

**Adopting a new implementation of a judgement is the riskiest thing in the
milestone.** Not building it is not an option either; leaving the middle rung
empty means the product's central claim is unmet. What is needed is a way to
observe a candidate implementation on real questions without ever letting it
change an answer, and a way to adopt it later only if the evidence justifies it,
only for the exact scope the evidence covers, and only reversibly.

## The five design rules

These are first-class. Each one has code that enforces it and a check in
`scripts/test-decision-runtime.py` that fails when the enforcement is removed.

### 1. It never authorises anything

Every record the runtime produces - a provider response, a shadow prediction, an
adoption slice, an evaluation report - carries `authorization_effect: "none"`, and
the engine contract validator refuses any that does not. The provider adapter
states it in its own `describe()`. The status record says, in words, that the
runtime is "bounded local inference; never an authorization and never
verification".

The structural version of this rule is in
`ariadne_engine.contracts.protected_action_problems`, which reports a problem for
*any* attempt to use a decision record as authorization, at every confidence
value. The Decision Runtime is added to that list, not exempted from it.

### 2. It is never verification

A prediction selects a path. Only verification establishes an outcome. The
runtime writes nothing to the verification collection, produces no verification
record, and cannot set a verification level. A shadow prediction is stored beside
the decision it observed; it is evidence *about a runtime*, which is a different
kind of statement from evidence *about the work*.

### 3. It observes before it influences

The order is fixed and not negotiable: the authoritative path runs first, its
answer is judged by policy and recorded; only then does the runtime see the
question and predict. The prediction is written to a separate collection with
`execution_effect: "none"`, a field that has exactly one legal value, and the
record validator refuses any other.

The asymmetry is what makes this a property rather than a promise. Nothing in the
Decision Plane reads `state["decision_shadow"]` to make a decision; the collection
is written by the observer and read by evaluation and diagnostics. And
`shadow_effect_problems` exists so a test can assert the property rather than
trust it: a decision that shares a question and projection digest with a shadow
record but records no execution is reported as suspicious.

### 4. It abstains rather than guessing

No weights for a question means `NO_LOCAL_MODEL`, not a low-confidence label. A
threshold the answer cannot meet means `BELOW_MIN_CONFIDENCE`, not a hedge. An
answer space that does not match the fitted one means `ANSWER_SPACE_MISMATCH`. A
primitive the engine cannot represent faithfully means `UNSUPPORTED_PRIMITIVE`.
Each is a structured refusal with a name and a slot for the reason.

There is no universal confidence threshold anywhere in the product, and no
default one. A threshold is supplied per call by the caller or per question by
contextual policy; where none is supplied the runtime answers what it can and
leaves the abstention decision to Ariadne's own policy machinery. A constant like
`0.8` would be a claim about every question at once, and nothing here supports
such a claim.

### 5. It cannot certify itself

Three separate mechanisms, because three different claims could otherwise be
smuggled in.

**Calibration is licensed, not self-declared.** A probability is labelled
`CALIBRATED_PROBABILITY` only when a `PROVEN` `CalibrationProfile` matches runtime
kind, implementation, model revision, decision definition, decision definition
digest, question schema digest and question version exactly. There is no
argument that sets `PROVEN`, and no path from a missing profile to a calibrated
label. The shipped engine reports `calibration_self_granted: false`, and
`problems()` refuses any runtime that claims otherwise.

**Promotion is scoped, ordered and reversible.** A slice is one exact tuple of
decision definition, question version, model revision and eligibility scope.
It moves through `UNTESTED -> SHADOW -> EVALUATED -> ELIGIBLE -> ACTIVE` in that
order, `ACTIVE` can only be left for `SUSPENDED`, and the scope is re-checked on
every call rather than trusted from the record.

**Comparison is identity-bound.** Metrics are only compared across runs whose
experiment identity matches exactly. Otherwise the gate refuses and names the
differing key, instead of printing a delta that means nothing.

## Further constraints

These are not the five rules, but they are equally deliberate.

- **Zero ML dependencies.** `pyproject.toml` declares `dependencies = []`, and the
  shipped engine is pure standard library. Nothing downloads, nothing trains,
  there is no self-training path, and the package contains no trainer.
- **`MultiSelectDecision` is refused.** The engine scores one closed label per
  question. Scoring options independently would report a confidence for a
  combination that was never evaluated, so the primitive takes Ariadne's normal
  fallback and escalation path.
- **Migration is additive.** A 2.0 caller with no runtime configured produces the
  same results as before, plus one extra inert key on each integration result.
- **The shipped probabilities are uncalibrated.** By construction, and the install
  output says so.

## What is not done

Stated plainly, because a reader deciding whether to rely on this needs the real
limits.

- **The shipped engine is not a trained model.** It is a multinomial naive-Bayes
  log-odds scorer over features of the projected state, with weights derived from
  Ariadne's own deterministic decision tables. It is weak on long, subtle text
  and strong on enumerated structure. That happens to match the decision families
  it is asked about, which are closed vocabularies over small structured
  projections - but the weights are rule-derived features, not parameters learned
  from a labelled corpus. The weight file's own `source` field says exactly that.
- **Its probabilities are overconfident by construction.** Naive Bayes with
  correlated features is systematically overconfident, and no rescaling makes it
  a statement about how often it is right. Hence `PROVIDER_PROBABILITY`, always.
- **Nothing is promoted by default.** No adoption slice ships `ACTIVE`. The
  default posture is that the runtime observes in shadow while the 2.0 path
  decides, and a promotion is a deliberate, recorded, reversible act by an
  operator who has evaluation evidence in hand.
- **No live provider evidence, no cross-platform proof, no signatures.** The
  transport was exercised on one platform. Release artifacts and runtime bytes are
  authenticated by SHA-256 digest against a reviewed record, not by a maintainer
  signing key. See [Security model](security-model.md).
- **No live Jev-shaped service is involved.** 2.0 ships a `JevShapedAdapter`
  interface for a third-party bounded service; it is injection-only, performs no
  network call, requires no credentials, and is recorded as `NOT_EXECUTED`. The
  Decision Runtime has no relationship to it and contains no code from it.

## Where the code is

`src/ariadne_engine/decisions/runtime/` - 18 files: 17 modules plus the package
initialiser. `ariadne_engine.contracts` carries the AR-206 record families
(`SCHEMA_DECISION_RUNTIME`, `DECISION_RUNTIME_STATUSES`, `DECISION_RUNTIME_KINDS`,
`ADOPTION_STATES`, `SHADOW_AGREEMENTS`, `CALIBRATION_PROFILE_STATUSES`,
`EVALUATION_COMPARABILITY_KEYS`) and the validators that enforce them.
`ariadne_engine.api` exposes the ten `decision_runtime_*` functions, all
classified `PROVISIONAL` in the public surface - none of them is stable in 2.0.
