# AR-201 — 05 TEST RESULTS

Machine-readable results are in `benchmarks/results/`; this file explains what each number
is and how to reproduce it. All runs were deterministic and offline: model calls 0, cost 0,
no network, sandbox under `%TEMP%`.

## 1. Environment

| Item | Value |
|---|---|
| Host | Windows, PowerShell 5.1 |
| Python | 3.11.9 (`<path>`) |
| AR-201 worktree | `<path>`, branch `v2/ar-201-core`, base `921fd8f` |
| Final code commit | `b2ca17b` (AR-201 implementation) |
| Baseline worktree (frozen) | `<path>` @ `921fd8f` |
| Sandboxes | `%TEMP%\kilo\ar201-*` (deleted or kept as evidence separately from the repo) |

## 2. Original benchmark: baseline versus final

The 51 original cases are exactly those in the AR-200 manifest
(`benchmarks/results/ar-200-20260922T185718.json`).

| Run | Case count | PASS | FAIL | OBSERVED | ERROR | DECLARED_SKIP | Wall clock |
|---|---|---|---|---|---|---|---|
| AR-200 baseline (`ar-200-20260922T185718.json`, committed by AR-200) | 51 | 45 | 3 | 1 | 0 | 2 | 270.1 s |
| AR-201 reproduction at `921fd8f` (`ar-200-20260922T192828.json`) | 51 | 45 | 3 | 1 | 0 | 2 | 162.5 s |
| AR-201 original-51 subset, fixed code (`ar-200-20260922T202523-original-51.json`) | 51 | 48 | 0 | 1 | 0 | 2 | 196.1 s |
| AR-201 full suite, fixed code, 61 cases (`ar-200-20260922T201711.json`, superseded; kept for provenance) | 61 | 58 | 0 | 1 | 0 | 2 | 185.0 s |
| AR-201 full suite, fixed code (`ar-200-20260922T203250.json`, superseded by the dead-code trim; kept for provenance) | 62 | 59 | 0 | 1 | 0 | 2 | 221.1 s |
| **AR-201 full suite, final code (`ar-200-20260922T204334.json` = `LATEST.json`, `git_head baf3d34`)** | **62** | **59** | **0** | **1** | **0** | **2** | 310.2 s |

The final run was recorded at `git_head baf3d34` (branch `v2/ar-201-core`); the measured
code tree is that commit. Wall clock on this host varies widely between identical-code runs
(185 s, 221 s, 310 s for the same suite), so the counts — not the timings — are the
deterministic result; §7 states what the timings can and cannot support.
The three failing cases in both baseline runs were
`security.gate-forgery-in-agents-md`, `security.creative-gate-bypass` and
`security.review-attestation-unverified`; all three pass in the final run. The observed and
declared-skip classifications are unchanged: `context.packet-size-baseline` is still
`observed`, and `suite.reasoner-rollback` and `suite.wheel-install` are still declared
skips (the latter is not executable here: it needs pip/venv and is slow).

The final run's evaluation counters are all zero where they were not before:
`false_acceptance 2 → 0`, `gate_bypass 1 → 0`, plus the new counters
`self_authorization 0`, `bypasses_allowed 0`, `migrations_implicit 0`,
`approval_reuse 0`, `replay_acceptance 0`, `fabricated_review_accepted 0`,
`invented_approvals 0`, `orphans_adopted 0`.

Reproduce:

```
python benchmarks/run_benchmarks.py --label ar-201-final
python benchmarks/run_benchmarks.py --write-manifest        # 61 cases
```

## 3. New cases (11)

Ten behaviour cases plus one suite case, all deterministic and offline:

| Case | What it establishes |
|---|---|
| `lifecycle.approval-stale-after-edit` | a semantic edit invalidates a recorded approval; the record is preserved but unbound |
| `lifecycle.approval-channel-required` | a hand-written `worker-cli` approval cannot satisfy G1 |
| `lifecycle.invalid-transition-refused` | the table refuses an illegal jump; a refused transition leaves the state byte-identical |
| `lifecycle.schema-migration-explicit` | legacy state refused without `--migrate`; migration is additive, backed up, idempotent, creates no approval; unknown schema still refused |
| `lifecycle.api-vertical-slice` | start → record-result → prepare-next → approve-gate → status through `ENGINE_API` only; the unapproved continuation returns exit 2 as a `Result`, and `state_changed` matches the writes |
| `security.approval-wrong-target-refused` | an approval does not cross operation, target or revision boundaries |
| `security.acceptance-after-review-and-single-use` | acceptance needs the review record and the bound G3 approval; the approval is spent once and the replay is refused |
| `security.review-record-required` | a hand-written judgement file grants neither the gate nor acceptance |
| `security.migrated-legacy-gate-refused` | migration never converts a document gate field into an approval |
| `lifecycle.recovery-reports-interrupted-work` | interrupted work is reported, never adopted or inferred as success |
| `suite.engine-core` | `scripts/test-engine-core.py` (73 checks) exits 0 |

## 4. Existing suites

Every suite the repository ships ran inside the benchmark (no separate harness) and all
passed in the final run:

| Benchmark case | Suite | Result |
|---|---|---|
| `suite.repo-self-test` | repository aggregate (18 named suites) | pass |
| `suite.runtime-self-test` | `scripts/ariadne.py --self-test` | pass 125/125 |
| `suite.transport-self-test` | `scripts/prepare-stage.py --self-test` | pass 50/50 |
| `suite.reasoner-self-test` | `scripts/reasoners.py --self-test` | pass |
| `suite.repo-contract` | `scripts/check.py` | pass |
| `suite.validation-guards` | `scripts/validate.py` guards | pass |
| `suite.distribution-lifecycle` | `scripts/test-distribution.py` | pass 55/55 |
| `suite.release-bundle` | `scripts/build-release.py --self-test` | pass 18/18 |
| `suite.real-project-fixtures` | real-project fixtures | pass |
| `suite.social-fixtures` | social fixture suite | pass |
| `suite.writing-contracts` | `scripts/test-writing-architecture.py` | pass |
| `suite.writing-execution` | `scripts/test-writing-execution.py` | pass |
| `suite.validation-run-benchmark` | recorded validation runs | pass |

Direct commands that were also run while developing (all exit 0):
`python scripts/ariadne.py --self-test`, `python scripts/prepare-stage.py --self-test`,
`python scripts/check.py`, `python scripts/test-distribution.py`,
`python scripts/build-release.py --self-test`, `python scripts/test-engine-core.py`.

## 5. Fixture and evaluation changes (documented, with reasons)

Three changes to the harness were required. None of them weakens an assertion; each is
recorded here because the AR-201 stop conditions require reporting test changes.

1. **Shared fixtures now record the human gate and the creative evidence.**
   `benchmarks/arbench/fixtures.py`: `complete_s1` establishes the project's creative plan
   (the runtime's own `low_assessment()`), `design_md()` carries the design-quality
   contract (tension, three rejections, ten-row G1 check), and `lock_g1` records the
   direction evidence and the G1 approval through `approve-gate` instead of hand-writing
   the document fields the old runtime trusted. Reason: the fixed policy requires both
   before G1 on every path, and the pre-AR-201 fixtures were relying on the very bypass
   being fixed. The document mirrors are still written (they are what a human reads), so
   every unchanged assertion about them still holds.
2. **`security.creative-gate-bypass` records the approval without the creative evidence.**
   Its `prepare_box` now writes the documents and calls `record_g1_approval` (approval only,
   no direction evidence), so the sandbox still isolates the creative-evidence precondition
   as the case's task describes. Without this, the shared fixture would have supplied the
   evidence and the case would have become vacuous.
3. **`security.review-attestation-unverified` was re-expressed as a pass/fail evaluation.**
   The AR-200 version returned `fail` when the defect reproduced and `error` otherwise, so
   it could never report `pass`. The rewritten evaluation keeps the original reproduction
   as a regression fixture (`false_acceptance` is 1 if an identity-less review is accepted)
   and adds three variants in the same sandbox: the implementer's own identity, the
   attestation line removed, and an independent identity that must be accepted and
   recorded. The `security.gate-forgery-in-agents-md` and `security.creative-gate-bypass`
   evaluations were left pass/fail as AR-200 wrote them.

Additionally, `scripts/ariadne.py --self-test` fixtures were completed so the shipped
suite can reach S4A under the fixed policy: the brief now selects the creative plan
(`creative-plan`) and records the S3 direction work, and the G1 step calls `approve_gate`
instead of only writing documents. No assertion was changed. The same applies to the
runtime's DESIGN.md fixture, which now satisfies the design-quality contract the runtime
always declared.

## 6. Failed tests and repairs during AR-201

| Symptom | Cause | Repair |
|---|---|---|
| `S1 -> S1 is not permitted` (runtime self-test) | the declared stage table omitted same-stage reasoner retries | added `(S1,S1)`, `(S2,S2)` |
| `validation-pending -> validated is not permitted` | two lifecycle values produced by `ingest_return` were missing from the table | added `validation-pending` / `repair-or-escalation` states and their transitions, and routed `ingest_return` through the choke point |
| `DESIGN.md has no usable design thesis` | `markdown_section_body` normalised newlines before the thesis line was parsed | split `section_raw` (verbatim) from the normalised fingerprint form |
| distribution lifecycle 54/55 | the fixture bundle is built from `runtime_sources()`, which did not include the engine | added `src/ariadne_engine` to `RUNTIME_TREES` |
| `missing stage output: RESEARCH.md` on retries | the S2/S3 precondition duplicated the proposal function and misfired for same-stage retries | same-stage retries return no entry preconditions |
| `stale source: .ariadne/creative-evidence.json` (runtime self-test) | the fixture recorded the direction evidence after the packet that delivered the ledger | the fixture records it before the S3 packet is prepared, so the delivered ledger is stable |
| `security.review-attestation-unverified` error (`accepted=1, control=1`) | expected: the case's AR-200 evaluation cannot report pass | evaluation rewritten (§5.3) |
| `security.creative-gate-bypass` error (repo handle) | `Sandbox.create` did not carry the repo | `Ctx.sandbox`/`Sandbox.create` now pass the repo, and the loader registers modules in `sys.modules` |
| `lifecycle.api-vertical-slice` fail (`s4a=1`) | the new case skipped the S3 stage result that `record-result` normally writes before a continuation, so the transport refused the parent evidence (case-authoring error, not a runtime defect) | the case records the S3 result through the API before continuing |

## 7. Performance

Measured on the same host, Python 3.11.9, one process per command. Nothing was optimized
for AR-201; the point of these numbers is to show where the cost went.

**Suite level** (`total_duration_seconds`, wall clock):

| Run | Cases | Executed | Wall clock | Per executed case |
|---|---|---|---|---|
| AR-200 baseline (committed, AR-200 host) | 51 | 49 | 270.1 s | 5.51 s |
| AR-201 reproduction at `921fd8f` | 51 | 49 | 162.5 s | 3.32 s |
| AR-201 original 51, fixed code, uncontended | 51 | 49 | 196.1 s | 4.00 s |
| AR-201 original 51, fixed code, contended | 51 | 49 | 229.4 s | 4.68 s |
| AR-201 full suite (61 cases), fixed code | 61 | 59 | 185.0 s | 3.14 s |
| AR-201 full suite (62 cases) | 62 | 60 | 221.1 s | 3.69 s |
| AR-201 full suite (62 cases), final code commit `baf3d34` | 62 | 60 | 310.2 s | 5.17 s |

**Caveat on the suite numbers.** Identical code produced 185 s, 221 s and 310 s for the same
62-case suite on this host across three runs (shared machine, other workloads running). The
suite wall clock therefore supports only one conclusion: the original 51 cases are not
*faster* and the added cases cost the extra fixture work described above. No timing claim
beyond that is made, and AR-204 owns optimization.

The original 51 cases are ~21 % slower after the change (162.5 s → 196.1 s) on the same
host, though the run-to-run spread above shows that even that delta should be read with
care. What is attributable: the shared deep fixture now runs three extra commands per case
(`creative-plan`, `record-creative`, `approve-gate`) because the fixed policy requires the
human gate and the creative evidence the old fixture obtained by writing two document
fields — fixture work, not transition cost.

**Per process / per command:**

| Measurement | Pre-AR-201 | AR-201 | Delta |
|---|---|---|---|
| `exec_module(scripts/ariadne.py)` (median of 8) | 41 ms | 48 ms | +7 ms (engine package load) |
| in-process `status` (median of 30, includes the approval/review policy imports) | – | 5.6 ms | engine work per command is single-digit ms |
| `python scripts/ariadne.py --help` (mean of 8) | 280 ms | 302 ms | +22 ms |
| `python scripts/ariadne.py status --json` (median of 30, whole process) | 250 ms | 346 ms | +96 ms, of which interpreter/subprocess noise dominates (the same tree varies by ±40 ms between runs) |

What AR-201 actually adds per state-changing command: one extra JSON validation pass, the
approval/review precondition evaluation (text hashing of small artifacts), one audit record
appended to `state["transitions"]`, and — in the API layer — a sha256 of the state file
before and after the call to report `state_changed`. The state hash is O(state) per command;
for the packet sizes measured here (S1 21.9 KB, S3 51.5 KB packet content, run state tens of
KB) that is far below a millisecond. AR-204 can replace the before/after hash with a
mtime+size check if it ever matters, but the brief's rule applies: no full-repository
hashing was introduced, and no premature optimization was done at the cost of correctness.

No claim of a speed-up is made anywhere in `docs/v2/AR-201/`.

## 8. What was not executed

* `suite.wheel-install` (declared skip): needs pip/venv; unchanged from AR-200.
* `suite.reasoner-rollback` (declared skip): needs two built release bundles; unchanged.
* The AR-200 report lists 12 planned runtime-backed and 8 planned design-runtime cases that
  are specified but not executed (`06-BENCHMARKS.md` §6). They have not been executed by
  AR-201 either, and no claim is made about them.
* No Boreal test, no paid model call, no network operation, no release or publish step.
