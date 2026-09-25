# AR-203 — Test Results

Every number below was produced by running the command in this worktree, at the
commit recorded in `09-AR-203-REPORT.md`. Nothing is reported as passing that was
not run; paths that could not be executed are recorded as `NOT_EXECUTED` or
`DECLARED_SKIP`.

## 1. Starting baseline (reproduced before any change)

Worktree: `<path>`, HEAD
`03fd9a4df9b8e2057d31cb929490103d4155e7ec`, branch `v2/ar-202d-hardening`, clean.

```text
python benchmarks/run_benchmarks.py --label ar-203-baseline
```

Result: **157 cases — 152 pass, 0 fail, 3 observed, 0 error, 2 declared-skip**
in 576.1s. Recorded in `benchmarks/results/AR-203-baseline-reproduced.json`
(byte-copy of `ar-200-20260924T194608.json`). The reported AR-202D-H state was
reproduced exactly, including `suite.engine-core` at 246/246.

## 2. Final benchmark

```text
python benchmarks/run_benchmarks.py --label ar-203-final
```

Result: **190 cases — 185 pass, 0 fail, 3 observed, 0 error, 2 declared-skip.**
Recorded in `benchmarks/results/AR-203-final.json` and `LATEST.json`.
`benchmarks/manifest.json` regenerated (`190 cases`).

| Group | Cases | Result |
|---|---|---|
| All 157 pre-existing cases | 157 | pass, unchanged |
| `execution-provenance` | 5 | pass |
| `capability-registry` | 5 | pass |
| `review-independence` | 3 | pass |
| `render-verification` | 3 | pass |
| `reference-verification` | 3 | pass |
| `decision-plane` | 8 | pass |
| `false-acceptance` | 6 | pass |

The 3 `observed` cases (`context.packet-size-baseline`,
`adaptive-context.preparation-measurements`, `design-measurements.deterministic-counters`)
and the 2 `declared-skip` cases (`suite.reasoner-rollback`, `suite.wheel-install`)
are unchanged from the baseline.

## 3. Engine core

```text
python scripts/test-engine-core.py
```

**330/330 PASS** (246 preserved + 84 new AR-203 checks). The new checks live in
`ar203_checks` (provenance, capability registry, verification records, review
independence, rendered/reference verification, decision plane, events,
compatibility) and `cli_checks` (the four new CLI commands, including a refusal
that must match the engine's).

## 4. Repository suites

Run individually, exactly as the benchmark runs them:

| Suite | Command | Result |
|---|---|---|
| Runtime self-test | `python scripts/ariadne.py --self-test` | 125/125 |
| Transport self-test | `python scripts/prepare-stage.py --self-test` | 50/50 (via benchmark) |
| Repo contract self-test | `python scripts/check.py --self-test` | PASS (via benchmark) |
| Repo contract (full) | `python scripts/check.py` | PASS — 427 links, 74 required files, 0 duplicated sentences |
| Distribution lifecycle | `python scripts/test-distribution.py` | 55/55 |
| Release tooling | `python scripts/build-release.py --self-test` | 18/18 (via benchmark) |
| Reasoners | `python scripts/reasoners.py` | 15/15 (via benchmark) |
| Real projects | `python scripts/test-real-projects.py` | 29/29 (via benchmark) |
| Social intelligence | `python scripts/test-social-intelligence.py` | 68/68 (via benchmark) |
| Validation guards | `python scripts/validate.py --self-test` | 29 guards (via benchmark) |
| Validation benchmark | `python scripts/validate.py --benchmark` | 1 run read (via benchmark) |
| Writing architecture | `python scripts/test-writing-architecture.py` | exit 0 (via benchmark) |
| Writing execution | `python scripts/test-writing-execution.py` | exit 0 (via benchmark) |
| Engine core | `python scripts/test-engine-core.py` | 330/330 |
| Complete benchmark | `python benchmarks/run_benchmarks.py` | 190 cases, 0 fail, 0 error |

## 5. Cross-surface parity

* CLI and API delegate to one implementation: `api.verify_claim`,
  `api.create_decision_batch`, `api.inspect_capabilities`,
  `api.inspect_execution_identity` and the engine-level wrappers all call the same
  engine functions the CLI commands call.
* `false-acceptance.cli-and-engine-refuse-the-same-claim` asserts the CLI refuses
  a fabricated execution id with the same engine reason, and the engine-core CLI
  checks assert the same for `provenance`, `verify`, `decide` and `capabilities`.
* No rule was duplicated to make a surface pass: the refusals come from
  `provenance.require_engine_execution` and `verification.create` in both cases.

## 6. Mutation testing

Six critical protections were broken in memory, one at a time, and the specific
benchmark case was re-run. Each mutation was detected (the case fails), and each
file was restored byte-exact (sha256 verified). No mutation code was committed.

| # | Protection mutated | Case used | Detected |
|---|---|---|---|
| M1 | execution-ID binding (`require_engine_execution` returns a synthetic record) | `execution-provenance.fabricated-execution-id-refused` | yes |
| M2 | self-review restriction (`independence_problems` returns `[]`) | `review-independence.execution-bound-not-label-bound` | yes |
| M3 | stale evidence rejection (`freshness_of` never reports `STALE`) | `false-acceptance.stale-passing-evidence-does-not-close` | yes |
| M4 | declared-capability elevation (`observe` skips the `VERIFIED` obligation) | `capability-registry.declared-is-not-verified` | yes |
| M5 | confidence-as-authorization (`may_act` returns accepted unconditionally) | `decision-plane.cannot-authorize-a-protected-action` | yes |
| M6 | bounded-decision validation (unknown answers coerced to the first option) | `decision-plane.invalid-answer-refused-not-coerced` | yes |

Two findings worth recording:

* M5's first form (disabling the `PROTECTED` branch in `confidence_verdict`) did
  **not** flip the test, because `evidence_verdict` and the consequence table
  refuse a protected action independently. The protection is defended in depth;
  the mutation was re-formed to target the decision point itself.
* M4's first form (changing `capability_status` for the no-record branch) was
  inert for the case, because the case first *declares* a capability. The mutation
  was re-formed to target `observe`'s verification obligation, which is the rule
  the case actually guards.

## 7. Completion criteria

| # | Criterion | Evidence |
|---|---|---|
| 1 | AR-202D-H preserved | frozen worktree untouched; baseline reproduced from `03fd9a4` |
| 2 | Execution provenance engine-bound | `provenance.require_engine_execution` used by every verification path |
| 3 | Requested and observed identity distinct | `execution-provenance.requested-and-observed-stay-distinct` |
| 4 | Capability claims have evidence levels | `capability-registry` group, 5 cases |
| 5 | Review independence execution-bound | `review-independence` group, 3 cases |
| 6 | Verification records exist | `verification.py`; `render-verification.reproduction-must-be-a-new-artifact` |
| 7 | Freshness enforceable | `false-acceptance.stale-passing-evidence-does-not-close` |
| 8 | Render/reference cannot be elevated by declaration | `render-verification.declared-observer-never-self-verifies`, `reference-verification.claimed-origin-without-verification-refused` |
| 9 | Cross-surface enforcement consistent | §5 above; CLI parity case |
| 10 | False-acceptance attacks covered | `false-acceptance` group, 6 cases; adversarial pass in `06` |
| 11 | Decision Plane contracts exist | `decisions/` package; `decision-plane` group |
| 12 | One bounded-decision path affects real behaviour | `execution.classify_with_decision`; `decision-plane.first-real-use-keeps-code-before-judgment` |
| 13 | Decision confidence cannot grant authorization | `decision-plane.cannot-authorize-a-protected-action`; mutation M5 |
| 14 | Confidence provenance explicit | `decision-plane.confidence-provenance-preserved` |
| 15 | Deterministic decision provider exists | `decisions.providers.DeterministicProvider` |
| 16 | Provider-neutral optional adapters possible | `OptionalProviderAdapter` contract, disabled by default |
| 17 | Economics telemetry recorded when available | `execution.record_usage`; engine-core usage checks; `07-ECONOMICS-TELEMETRY.md` |
| 18 | Existing benchmarks do not regress | 157 pre-existing cases all pass |
| 19 | Engine core green | 330/330 |
| 20 | Repository suites green | §4 above |
| 21 | No paid provider required | no network call anywhere; `DECLARED`/`UNKNOWN` recorded honestly |
| 22 | Boreal unmodified | no Boreal file touched or tested |
| 23 | No remote actions | local commits only; no push, tag or release |
| 24 | Worktree clean | see `09-AR-203-REPORT.md` §Git state |
| 25 | AR-204 handoff ready | `10-AR-204-HANDOFF.md` |

## 8. Performance

Measured overhead of the AR-203 seams, 200 repeats each (100 for the record
writers), median wall time in milliseconds. Comparable existing operations are
shown for scale; nothing was optimised and no measurement was taken with a
weakened protection.

| Operation | Median | p95 |
|---|---|---|
| `execution.create` (existing seam, for scale) | 0.0156 ms | — |
| `provenance.identity_claims` | 0.0023 ms | 0.0030 ms |
| `provenance.execution_provenance` | 0.0146 ms | 0.0273 ms |
| `capabilities.declare` | 0.0285 ms | 0.0444 ms |
| `capabilities.capability_status` | 0.0343 ms | 0.0516 ms |
| `verification.create` (OBSERVED, includes re-hashing the artifact) | 0.3313 ms | 0.5157 ms |
| `verification.freshness_of` | 0.0008 ms | 0.0011 ms |
| `decisions.batch.evaluate` (one scripted batch) | 0.0415 ms | 0.0687 ms |
| `execution.classify_with_decision` (deterministic path) | 0.0005 ms | 0.0007 ms |

Overhead is negligible at the scale of a stage: the deterministic classification
path costs microseconds, a capability lookup tens of microseconds, and the most
expensive new operation (`verification.create`) is dominated by the artifact hash
that makes the verification real. The benchmark's own duration is dominated by
the pre-existing suites; AR-203 added 33 fast cases (≈0.3s total). No
optimisation is warranted or attempted; AR-204 owns economics.
