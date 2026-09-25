# AR-202 — Test results

Host: Windows 10.0.26200 (AMD64), Python 3.11.9, all runs offline (`model_calls: 0`, `cost: 0.0`).
Harness: `benchmarks/run_benchmarks.py`; sandboxes under the OS temp directory, never in a repository.
Artifacts: `benchmarks/results/AR-202-final.json` (final), `benchmarks/results/AR-202-baseline-reproduced.json` (AR-201 baseline), `benchmarks/results/LATEST.json`, `benchmarks/manifest.json` (87 cases).

## 1. Reproduction of the AR-201 baseline

Before any AR-202 change, in the AR-202 worktree at `8844b1a`:

| Classification | Count |
|---|---|
| PASS | 59 |
| FAIL | 0 |
| OBSERVED | 1 |
| ERROR | 0 |
| DECLARED_SKIP | 2 |
| **Cases** | **62** |

This matches the AR-201 published expanded result exactly (59 / 0 / 1 / 0 / 2), so the comparison baseline is the reported one, not a re-measured one.

## 2. Final AR-202 result

| Classification | Count |
|---|---|
| PASS | 83 |
| FAIL | 0 |
| OBSERVED | 2 |
| ERROR | 0 |
| DECLARED_SKIP | 2 |
| **Cases** | **87** |

Wall clock: **236.2 s** for all 87 cases (case durations sum to 236.3 s; the harness reports 33.4 s of *measured* case metrics and 462 checks, 415 of which carry pass/fail semantics).

**AR-201 subset inside the final run:** the 62 AR-201 cases are 59 PASS, 1 OBSERVED, 2 DECLARED_SKIP — identical to the baseline. **No AR-201 case regressed, no assertion was weakened.**

**New AR-202 cases:** 25 cases in five groups (`adaptive-context` 6, `routing` 7, `execution-identity` 4, `recovery` 4, `evidence-continuation` 4): 24 PASS, 1 OBSERVED, 0 FAIL, 0 ERROR.

| Group | Cases | Group time |
|---|---|---|
| `suites` | 16 (14 pass, 2 declared skip) | 28.2 s |
| `lifecycle` | 22 | 53.9 s |
| `security` | 12 | 50.4 s |
| `context` | 5 (4 pass, 1 observed) | 6.4 s |
| `design` | 3 | 6.2 s |
| `distribution` | 4 | 5.7 s |
| `adaptive-context` | 6 (5 pass, 1 observed) | 18.9 s |
| `routing` | 7 | 25.0 s |
| `execution-identity` | 4 | 17.4 s |
| `recovery` | 4 | 7.9 s |
| `evidence-continuation` | 4 | 16.3 s |

## 3. Repository suites, exactly as executed

Every command below ran in the final suite run; the ratio is the runtime's own output.

| Command | Result |
|---|---|
| `scripts/check.py --self-test` | exit 0, `SELF-TEST PASS` |
| `scripts/ariadne.py --self-test` | `PASS 125/125` |
| `scripts/prepare-stage.py --self-test` | `PASS 50/50` |
| `scripts/reasoners.py` | `PASS 15/15` |
| `scripts/check.py` | 18 ok, 0 fail |
| `scripts/validate.py --self-test` | `PASS 29 guards all fail correctly on broken input` |
| `scripts/test-distribution.py` | `PASS 55/55` |
| `scripts/build-release.py --self-test` | `PASS 18/18` |
| `scripts/test-real-projects.py` | `PASS 29/29` |
| `scripts/test-social-intelligence.py` | `PASS 68/68` |
| `scripts/test-writing-architecture.py` | exit 0 |
| `scripts/test-writing-execution.py` | exit 0 |
| `scripts/validate.py --benchmark` | 1 recorded validation run read |
| `scripts/test-engine-core.py` | `PASS 145/145` (was 96 in AR-201) |
| `benchmarks/run_benchmarks.py` | 87 cases, 83/0/2/0/2 |

## 4. Skips, observations and unverified cases

Declared skips (unchanged from AR-200, both environmental):

* `suite.reasoner-rollback` — needs two built release bundles; the reasoner-switch path itself is covered by `suite.runtime-self-test`.
* `suite.wheel-install` — needs a working pip/venv and is slow.

Observations (recorded, never judged):

* `context.packet-size-baseline` — S1 21 889 bytes / 2 sources; S3 51 451 bytes / 7 sources.
* `adaptive-context.preparation-measurements` — see §5.

Not executed / not verified (reported as unknown rather than as a pass):

* No model provider was contacted; token usage and cost are `UNKNOWN`, not estimated.
* Live provider routing is **not** verified: routing correctness is verified against the adapter contract and deterministic fixtures only. Fake-fixture success is not evidence that a real provider obeys a route.
* `observed` runtime identity remains unavailable by design (see `02-EXECUTION-IDENTITY.md`).
* AR-204 owns performance work; nothing here is a performance claim.

## 5. Measurements

From `adaptive-context.preparation-measurements` (5 repetitions per variant, one sandbox, medians and ranges):

| Measurement | Median | Range |
|---|---|---|
| Packet preparation, no plan (S3, 7 sources, 50 259 bytes) | 106.233 ms | 103.102 – 112.163 ms |
| Packet preparation, cache-hit plan (same packet) | 100.693 ms | 97.881 – 106.016 ms |
| Routing decision (`ROUTING.route`, 50 samples) | 0.042 ms | 0.033 – 0.147 ms |
| Context decision (`CONTEXT.decide`, 50 samples) | 0.625 ms | 0.492 – 0.804 ms |
| Recovery detection (`RECOVERY.detect`, 10 samples) | 1.401 ms | 0.972 – 1.861 ms |

Deterministic effects (measured, not estimated):

* 6 delivered source hashes reused from the cache in one preparation; **40 334 bytes not re-hashed**.
* Cache misses on the first hit run: 0 (the retry saw every delivered source unchanged).
* Budget accounting across the whole run: 22 sources considered, 16 included, 8 cache hits, 4 invalidations, and the bytes above.

**Honest reading of the timing:** the preparation-time difference (106.2 ms vs 100.7 ms, overlapping ranges) is **inconclusive on this fixture**. The dominant cost of a preparation is the project snapshot and packet assembly, not hashing a handful of small files, so the retrieval of 40 KB of hashing does not move the median reliably. The claim AR-202 makes is the *deterministic* one: unchanged sources are not re-hashed, and the reused hash is verified by `verify_packet`. AR-204 can revisit larger, measured contexts.

## 6. Refusal paths proven

Security-relevant refusals added by AR-202 (all deterministic):

* forged/unknown execution id → ingest refused, no evidence written;
* result for another task, another revision, or a finished execution → refused;
* reviewer bound to the implementing execution → refused;
* review record without the execution binding → refused by the contract;
* worker-reported runtime identity never becomes observed identity;
* pinned model identity mismatch → return refused and recorded as `PROVIDER_FAILURE`;
* authorization failure → routing stops (`policy-excluded`), no packet created;
* missing human gate → no packet, no route, no approval invented;
* context plan attempting to omit a required source → `PacketError` from the transport;
* cache cannot add a source, so a forbidden source cannot be delivered at S5;
* S4A→S4B and S4B→S5 without the required skill/operations evidence → pause with the named requirement;
* evidence whose artifact changed → refused as `stale`;
* ambiguous orphans, missing packets, duplicate completed results → refused, state unchanged;
* recovery without identity or reason → refused, nothing changed.
