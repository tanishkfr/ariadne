# AR-203 — Execution Provenance

AR-202 introduced execution identities: the engine creates them, a worker cannot
choose one, and requested / reported / observed identity are separate fields.
AR-203 asks what those fields are actually *worth*, and strengthens the boundary
in three ways: explicit claim levels, a separate provider-observation channel, and
a requirement that an execution used as provenance must be an engine-created
record in this run.

## 1. The identity record

`execution.create` (`src/ariadne_engine/execution.py`) produces a record carrying:

| Field | Meaning | Who establishes it |
|---|---|---|
| `execution_id` | `exe_<utc>_<nonce>` | the engine, at creation |
| `run_id`, `task_id`, `role` | what the execution is for | the engine boundary |
| `adapter`, `invocation` | how it was invoked | the engine boundary |
| `parent_execution` | the execution this one descends from | the engine boundary |
| `requested` | provider/model/effort/worker role asked for | the run |
| `reported` | what the worker said about itself | the worker (unverified prose) |
| `observed` | what the runtime observed at the boundary | the runtime, or `UNKNOWN` |
| `provider_observed` | what the model/provider adapter reported | an engine-side adapter only |
| `revision` | the project revision the execution was created against | the engine boundary |
| `usage` | measured provider usage, if supplied | an adapter or runtime, measured only |
| `created_at` / `started_at` / `completed_at` / `failed_at` | lifecycle timestamps | the engine state machine |
| `state`, `result` / `failure` | outcome | the engine state machine |
| `provenance.created_by` / `.source` | who created the record | the engine |

`provenance.execution_provenance(state, execution_id)` returns the full view,
including per-field claim levels, a stable `provenance_digest` over the
identity-bearing facts, and the recorded limitations.

## 2. Claim levels

`contracts.IDENTITY_CLAIM_LEVELS`:

```text
DECLARED          a party asserted it in prose; no engine evidence
REQUESTED         the run asked for it; the execution may not have used it
ENGINE_CREATED    the engine created the identity record that carries it
RUNTIME_OBSERVED  the runtime itself observed it at the boundary
PROVIDER_OBSERVED the adapter/provider reported it for this execution
VERIFIED          independently reproduced by a different engine execution
UNKNOWN           nothing established it; it must never be guessed
```

`provenance.identity_claims(record)` resolves each of `provider` and `model`
independently. Precedence is provider-observed, then runtime-observed, then
requested, then declared, then `UNKNOWN` — and the value never moves upward:

```text
requested model = deepseek-x        →  claim level REQUESTED
reported  model = gpt-x             →  recorded as worker_claim, not as observed
observed  model = UNKNOWN           →  stays UNKNOWN; nothing rewrites it
provider-observed model = deepseek-x-2026-01
                                    →  PROVIDER_OBSERVED, with the raw observation kept
```

A worker statement is never promoted. `record_provider_observation` refuses
sources that name worker output, and `verify_observation_chain` reports a record
whose observed channel carries a worker source.

## 3. What "engine-created" means, and its limit

`provenance.require_engine_execution(state, execution_id, role=..., task_id=...)`
is the single gate used by rendered verification, retrieval verification,
capability exercise, decision batches and review independence. It refuses:

* a missing or empty id;
* an id that does not resolve to a record in this run's state
  (`a caller-chosen id is not an execution identity`);
* a record that fails `contracts.execution_problems`;
* a record whose role or task does not match the operation;
* optionally, an execution that already finished.

**Honest limitation.** The engine cannot authenticate a process or prove a named
model executed. A caller who writes `ariadne-run.json` directly can fabricate a
record; that is the trust boundary, and it is the same boundary every earlier
milestone has. What AR-203 removes is the much weaker boundary that accepted a
well-formed *string*. The stronger claim — cryptographic process attestation —
would need infrastructure this milestone is forbidden to add, and is recorded as
`NOT_EXECUTED` rather than implied.

## 4. Observation conflicts

`provenance.provider_request_problems(state)` reports two executions claiming the
same provider request id. A provider request id ties a provider-side trace or bill
to one execution; two executions claiming one is a replay or a mislabelled
observation, never a coincidence to ignore. `execution.identity_view` records
every requested/reported and requested/observed mismatch explicitly rather than
letting one field silently win.

## 5. Tests

Engine suite (`scripts/test-engine-core.py`, `ar203_checks`):

* `requested identity is not observed identity by default`
* `worker prose never raises a claim above DECLARED`
* `worker output cannot write the provider-observed channel`
* `a provider observation is recorded with its observer and level`
* `an observed identity that differs from the request is a recorded mismatch`
* `two executions claiming one provider request id is a provenance conflict`
* `a well-formed but engine-unknown execution id is refused`
* `an execution used under the wrong role is refused`
* `the provenance digest changes when identity facts change`
* `a worker source on the observed channel is a finding`
* `a result for a stale revision is refused`, `... wrong role ...`, `... wrong task ...`
* `a replayed result is refused`

Benchmark (`benchmarks/arbench/ar203_cases.py`, group `execution-provenance`):

* `execution-provenance.requested-and-observed-stay-distinct`
* `execution-provenance.worker-prose-cannot-replace-observed`
* `execution-provenance.fabricated-execution-id-refused`
* `execution-provenance.stale-and-misattached-results-refused`
* `execution-provenance.replay-and-duplicate-request-refused`
