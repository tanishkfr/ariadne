# AR-203 — Implementation

Milestone: **AR-203, Verification Hardening & Decision Plane Foundation** of Ariadne v2.
Base: AR-202D-H closure at `03fd9a4df9b8e2057d31cb929490103d4155e7ec` (`v2/ar-202d-hardening`).
Branch: `v2/ar-203-verification-hardening`. Version file unchanged at `1.6.7`.

This document maps the milestone: every system AR-203 adds, the file it lives in,
and the rule it makes executable. Behaviour is documented in `02`–`07`; the
adversarial model is `06`; results are `08`; the milestone narrative is `09`; the
next milestone is `10`; durable decisions are `11`.

## 1. Thesis

AR-202D-H asked whether Ariadne could tell a *declared* artifact from an
*observed* one. AR-203 asks the harder question: **how does Ariadne know that the
thing it says happened actually happened, through the execution, capability,
reviewer and evidence path it claims?**

The answer is not a better model. It is five concepts that must never collapse
into one another:

```text
DECISION ≠ AUTHORIZATION ≠ EXECUTION ≠ VERIFICATION ≠ ACCEPTANCE
```

* a model may *decide* "this looks like a validation failure" — that authorizes
  nothing and proves nothing;
* a worker may *report* "tests passed" — that does not establish that tests ran;
* a reviewer may *say* "approved" — that is not human acceptance;
* a runtime may be *requested* as model X — that does not prove model X executed;
* a screenshot may *exist* — that does not prove the current source produced it.

AR-203 makes each distinction executable and testable, and adds the foundation of
the Decision Plane: deterministic computation for knowable facts, bounded
decision intelligence for judgment, generative intelligence for creation,
verification for what actually occurred, and human control for protected choices.

## 2. Systems and source paths

| # | System | Source | Contract |
|---|---|---|---|
| T1 | Execution provenance and identity claim levels | `src/ariadne_engine/provenance.py` | `contracts.IDENTITY_CLAIM_LEVELS`, `provenance.identity_claims` |
| T2 | Live capability registry and deterministic probes | `src/ariadne_engine/capabilities.py` | `contracts.capability_record_problems` |
| T3 | Capability-evidence routing policy | `src/ariadne_engine/routing.py` | `routing.route_evidence(..., evidence_policy=)` |
| T4 | Review independence bound to executions | `src/ariadne_engine/review.py`, `critique.py` | `review.independence_level`, `contracts.INDEPENDENCE_LEVELS` |
| T5 | Verification records, levels and freshness | `src/ariadne_engine/verification.py` | `contracts.verification_record_problems` |
| T6 | Rendered-verification binding and currentness | `src/ariadne_engine/render.py` | `render.verification_dependencies`, `render.verification_currentness` |
| T7 | Reference retrieval verification and origin honesty | `src/ariadne_engine/references.py` | `contracts.REFERENCE_RETRIEVAL_MODES`, `references.record_retrieval_verification` |
| T8 | Decision primitives, confidence contract, batches | `src/ariadne_engine/decisions/` | `contracts.decision_record_problems`, `decision_batch_problems` |
| T9 | Risk-adjusted decision policy | `src/ariadne_engine/decisions/policy.py` | `policy.may_act`, `MIN_EVIDENCE_BY_CONSEQUENCE` |
| T10 | Deterministic decision provider and optional adapter boundary | `src/ariadne_engine/decisions/providers.py` | `DecisionProvider`, `DeterministicProvider`, `OptionalProviderAdapter` |
| T11 | First real bounded-decision use: failure classification | `src/ariadne_engine/execution.py` | `execution.classify_with_decision` |
| T12 | Economics telemetry | `src/ariadne_engine/execution.py` | `execution.record_usage`, `USAGE_FIELDS`, `CONTEXT_COMPOSITION_BUCKETS` |
| — | AR-203 vocabularies and validators | `src/ariadne_engine/contracts.py` | `SCHEMA_CAPABILITY/VERIFICATION/DECISION`, `AR203_COLLECTIONS` |
| — | Event vocabulary | `src/ariadne_engine/events.py` | 14 new event types |
| — | Record collections | `src/ariadne_engine/persistence.py` | `ADAPTIVE_COLLECTIONS` extended by `contracts.AR203_COLLECTIONS` |
| — | Programmatic API | `src/ariadne_engine/api.py` | 8 new operations + 10 engine-level wrappers |
| — | Command surface | `scripts/ariadne.py` | `capabilities`, `verify`, `decide`, `provenance`; `design-plan --evidence-policy` |
| — | Benchmarks | `benchmarks/arbench/ar203_cases.py` | 33 cases in 7 groups |
| — | Engine suite | `scripts/test-engine-core.py` | `ar203_checks` (84 checks) + CLI checks (8) |

New modules: 5 (`provenance.py`, `capabilities.py`, `verification.py`,
`decisions/` with four modules). New public engine records: 4 families. New event
types: 14. New CLI commands: 4. No new dependency; standard library only.

## 3. What each layer enforces

### Execution provenance (`provenance.py`)

Every identity fact about an execution carries the level that established it:
`REQUESTED`, `ENGINE_CREATED`, `RUNTIME_OBSERVED`, `PROVIDER_OBSERVED`,
`VERIFIED`, `UNKNOWN`. `requested model = X` never silently becomes
`observed model = X`. Provider observation is its own channel
(`record_provider_observation`) and refuses worker sources; a worker's claim
stays on the `reported` channel and appears as `worker_claim` when it differs.
`require_engine_execution` replaces every shape-only check: an id must resolve to
an engine-created record *in this run's state*, with a supported role and task.
`provider_request_problems` reports two executions claiming one provider request
id.

### Capability registry (`capabilities.py`)

`DECLARED → DISCOVERED → AVAILABLE → EXERCISED → VERIFIED`, plus `UNAVAILABLE`
and `UNKNOWN`. A declaration is never a verification. `EXERCISED` requires the
engine execution that exercised it, or a deterministic probe artifact whose
output digest is recorded. `VERIFIED` requires an existing verification record at
`REPRODUCED` or stronger with `CURRENT` freshness. Probes are offline:
`ExecutableProbe` (PATH lookup), `AdapterMethodProbe` (declared capability plus
callable method), `FixtureCommandProbe` (one declared command in an isolated
fixture, bounded timeout, stdout digest recorded). Routing consumes the registry
under an explicit `evidence_policy` (`declared` | `observed` | `strict`) that is
recorded on the routing decision.

### Review independence (`review.py`, `critique.py`)

`independence_problems` now requires both executions to be engine-created records
and different. `independence_level` computes `NONE`, `DECLARED_DISTINCT`,
`ENGINE_DISTINCT_EXECUTION`, `DISTINCT_RUNTIME`, `DISTINCT_PROVIDER` or
`HUMAN_REVIEW` from observed facts only — never from labels — and the level is
recorded on review and critique records.

### Verification records (`verification.py`)

One record answers: what claim, about what subject, observed by which execution
(or engine-recorded anchor), examined against which evidence the engine re-hashed
itself, reproduced by which artifact, bound to which revision and dependency
fingerprints, at which level, with which limitations. Levels never skip:
`OBSERVED` needs a real artifact and a named execution/anchor; `REPRODUCED` needs
a *different* artifact the verifier re-produced; `INDEPENDENTLY_REPRODUCED` needs
a different engine execution; `VERIFIED` needs named dependency fingerprints that
are current. Re-hashing a declaration raises nothing. Freshness is
dependency-specific: `refresh` re-evaluates only the named dependencies, and a
stale record answers as `STALE` while keeping `established_level` as history.

### Rendered verification (`render.py`)

`verify` requires the engine-created capture execution, a distinct engine-created
verifier execution, and the artifact the verifier re-produced (a real, different
file the engine re-hashes). The verification record binds source revision,
artifact digest, capture parameters (kind, method, adapter, viewport,
environment) and the capture execution; `verification_currentness` re-evaluates
it, so a changed capture parameter or revision makes the verification stale.

### Reference verification (`references.py`)

Retrieval records its mode (`local-read`, `external-retrieval`, `fixture`,
`declared`). A local digest proves local bytes only; `origin.remote_origin_proven`
is `False` until an independent retrieval verification reproduces the digest, and
`provenance_problems` reports any reference that claims a proven origin without
one. `reference_currentness` makes changed content or a changed locator stale.

### Decision Plane (`decisions/`)

Four primitives (`BinaryDecision`, `ChoiceDecision`, `ScaleDecision`,
`MultiSelectDecision`) bound a closed answer space declared before the provider is
asked. `state_digest` binds every decision to the projected state it was made
against; projections are refused when oversized rather than truncated. Confidence
provenance is explicit (`CALIBRATED_PROBABILITY`, `PROVIDER_PROBABILITY`,
`DERIVED_CONFIDENCE`, `SELF_REPORTED_CONFIDENCE`, `NONE`), and no threshold can
grant authorization: `authorization_effect` is always `none` and a `PROTECTED`
consequence is refused regardless of confidence. Batches ask independent
questions in one provider call; a dependent question is a second step. The first
real use is failure classification (`execution.classify_with_decision`):
deterministic first, bounded judgement only for unmapped sources, inside the safe
class subset, with a deterministic fallback of `UNKNOWN` plus escalation.

### Economics telemetry (`execution.py`)

`record_usage` records provider-reported figures with their observer: input,
output, cached and uncached input, reasoning tokens, turns, tool calls, tool
errors, duration, and context composition by bucket. Absent fields stay absent;
nothing is estimated and no billing figure is invented. `telemetry_summary`
totals measured fields only.

## 4. Compatibility

Run-state file schema stays `1`. The four new collections are additive and
optional; a state written by any earlier milestone is read, continued and written
back without inventing a capability, verification, decision or execution
observation. The AR-203 records version themselves independently
(`SCHEMA_CAPABILITY = 1`, `SCHEMA_VERIFICATION = 1`, `SCHEMA_DECISION = 1`) and
`persistence.write_state` records the contract markers
(`ariadne-capability-1`, `ariadne-verification-1`, `ariadne-decision-1`) without
changing `contract` or `record_schema`.

## 5. Deliberate deviations from the AR-203 brief

* The brief's suggested decision-package shape (`contracts.py`, `batch.py`,
  `policy.py`, `providers.py`) is used as written; `MultiSelectDecision` is
  implemented because the primitive set needed a bounded multi-answer shape to be
  complete, and it is covered by contract tests.
* The brief lists `DECLARED` as the lowest evidence level in
  `MIN_EVIDENCE_BY_CONSEQUENCE` for low-consequence decisions. Implementation
  treats low consequence as requiring *no* evidence level beyond a valid answer,
  because a `DECLARED` floor would have required inventing a verification level
  for projections that carry none. This is stricter, not looser: no evidence is
  claimed that does not exist.
* `render.verify` gained a mandatory `reproduced_artifact` argument. The previous
  `reproduced_sha256`-only form could be satisfied without any artifact, which is
  the defect AR-203 exists to close; two engine-core fixtures were updated to
  create real capture/verification executions and a real re-produced artifact.
  No assertion was weakened.
* Reference retrieval verification uses an `observed_anchor`
  (`reference:<id>`) because the original retrieval is adapter-supplied and has no
  engine execution. The *verifier* is still an engine-created execution, and the
  engine re-hashes the re-retrieved artifact itself.

## 6. Where to look first

* `02-EXECUTION-PROVENANCE.md` — identity levels and the trust boundary.
* `04-VERIFICATION-MODEL.md` — levels, reproduction and freshness.
* `05-DECISION-PLANE.md` — primitives, confidence, policy, first use.
* `06-FALSE-ACCEPTANCE.md` — the adversarial model and every attack attempted.
* `11-ADR.md` — the durable decisions and their rejected alternatives.
