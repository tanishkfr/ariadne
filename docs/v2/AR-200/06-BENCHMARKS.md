# AR-200 / 06 — BENCHMARKS

## 1. What was built

A reproducible, machine-readable, fully offline deterministic benchmark inside the v2 worktree:

```
benchmarks/
  run_benchmarks.py        entry point (stdlib only; no network, no model calls)
  arbench/driver.py        sandboxed subprocess driver for the real runtime
  arbench/fixtures.py      fixture documents, reusing the runtime's own generators
  arbench/cases.py         51 registered cases across 7 groups
  manifest.json            generated, machine-readable case manifest
  results/LATEST.json      latest run (also archived per timestamp)
```

Commands:

```
python benchmarks/run_benchmarks.py --list                 # 51 cases
python benchmarks/run_benchmarks.py                       # run everything executable
python benchmarks/run_benchmarks.py --only security       # one group
python benchmarks/run_benchmarks.py --case <id>           # one case
python benchmarks/run_benchmarks.py --write-manifest      # regenerate manifest.json
python benchmarks/run_benchmarks.py --work-root D:\tmp\ar-bench --keep-sandbox
```

Design rules honoured: fixtures live outside every repository (default `%TEMP%\ariadne-bench-*`, deleted on completion); the runtime under test is invoked exactly as an operator would (`python scripts/ariadne.py <cmd>`); every verdict records the commands, exit codes, artifacts and hashes behind it; a harness failure is reported as `error`, never as a pass.

## 2. Case taxonomy

| Group | Count | Method | Needs a model? | Needs the network? |
|---|---|---|---|---|
| `suites` | 14 (2 declared-not-executable) | Re-runs the repository's existing deterministic suites and parses their verdicts | no | no |
| `lifecycle` | 16 | Drives the real CLI through S1 → S3 → G1 → S4A → S4B → validation → S5 in an isolated sandbox | no | no |
| `security` | 8 | Adversarial probes of the authorization, scope, immutability and evidence boundaries | no | no |
| `context` | 5 | Packet compilation, conditional inclusion/omission, hash parity, package size | no | no |
| `design` | 3 | Creative-plan gating, unsupported-claim blocking, requirements derivation | no | no |
| `distribution` | 4 | Manifest validation, version/schema coupling, offline tooling, lifecycle guards | no | no |
| `runtime-backed` (planned) | 12 | See §6 — real implementation, model selection, provider failure, multi-file debugging, actual review execution | yes | yes |
| `design-runtime` (planned) | 8 | See §6 — reference provenance with a real fetch, component compatibility, requirement tracking, rendered inspection, refinement | yes | yes |

Case statuses: `pass` (integrity expectation met) · `fail` (expectation violated — a real defect) · `observed` (measurement recorded, no judgement) · `error` (harness could not evaluate) · `skip` (declared not executable here).

Every case in `manifest.json` carries: id, group, title, task, required inputs, expected outcome, evaluation method, evidence required for success, environment requirements, provider requirements, cost implications, whether it is currently executable, and the layer.

## 3. Results of the AR-200 baseline run

Run: 2026-09-22, runtime `5819dae` (v2 worktree), Python 3.11.9, Windows.
Archived: `benchmarks/results/ar-200-20260922T185718.json` (and `LATEST.json`).

```
pass 45 · fail 3 · observed 1 · error 0 · skip 2      total wall time 270 s
model calls 0 · token usage UNKNOWN (no provider invoked) · cost 0.00
```

Existing deterministic suites re-run and passing:

| Case | Result |
|---|---|
| `suite.repo-self-test` (18 embedded suites) | PASS |
| `suite.runtime-self-test` | 125/125 |
| `suite.transport-self-test` | 50/50 |
| `suite.reasoner-self-test` | 15/15 |
| `suite.repo-contract` | 18 ok / 0 fail |
| `suite.validation-guards` | 29/29 guards can fail |
| `suite.distribution-lifecycle` | 55/55 |
| `suite.release-bundle` | 18/18 |
| `suite.real-project-fixtures` | 29/29 |
| `suite.social-fixtures` | 68/68 |
| `suite.writing-contracts`, `suite.writing-execution` | exit 0 |
| `suite.validation-run-benchmark` | 1 recorded run read |
| `suite.reasoner-rollback` | **skip** — requires two built release bundles |
| `suite.wheel-install` | **skip** — requires pip/venv (build + isolated install) |

Strengths proven by the new cases (all `pass`):

- `lifecycle.independent-validation-executes` — validation ran the declared command for real (`git diff --check`), recorded returncode, stdout/stderr hashes and scope `within-contract`.
- `security.sensitive-path-write-blocked` — a `.env` created by the worker is classified `dangerous-action`, status `blocked`.
- `security.out-of-scope-write-blocked` — an unauthorised file is classified `out-of-scope` and named.
- `security.handoff-immutability` — editing `HANDOFF.md` after preparation yields `repository-conflict` with `HANDOFF.md` in the immutable list.
- `security.evidence-not-overwritable` — return and validation evidence refuse the second write; the recorded hash is unchanged.
- `security.packet-tamper-detected` — an injected line in `packet.txt` is detected by hash and the continuation is refused.
- `lifecycle.repair-budget-bounded` — widening `repair_limit` beyond 2 is rejected by packet verification.
- `lifecycle.s5-isolation` — the review packet delivers exactly `["current S5 prompt block", "EVALUATION-RUBRICS.md"]` and verifies clean.
- `context.*` — every delivered source hash matches canonical bytes; a creative ledger naming another project is refused; omissions are recorded.
- `distribution.manifest-rejects-incomplete` — 7/7 malformed manifests rejected, real generator manifest accepted.

Measured context sizes (deterministic fixture): **S1 = 21 889 bytes / 2 sources; S3 = 39 252 bytes / 6 sources** (`context.packet-size-baseline`, status `observed`).

Defects proven (`fail`, with reproduction inside the result JSON):

| Case | Observed behaviour | Integrity expectation |
|---|---|---|
| `security.gate-forgery-in-agents-md` | Writing `**Status:** locked at G1` in `DESIGN.md` + `**Last gate passed:** G1` in `AGENTS.md` and recording a stage result prepares S4A; the runtime records the human creative decision as **resolved** | An agent-writable document must not satisfy a human gate |
| `security.creative-gate-bypass` | `advance` at S3 without a stage result = exit 2; the same command **after** `record-result` = exit 0 → S4A; `prepare-next` likewise | The same preconditions on every continuation path |
| `security.review-attestation-unverified` | A review with a self-written `**Reviewed independently:** yes` is accepted; removing that line is the only enforced difference | Independence must rest on evidence the reviewed actor cannot produce |

These three are the AR-201/AR-203 drivers (03 §6 invariants I-3, I-9, I-4).

## 4. Metrics captured, and which are UNKNOWN

Measured in this run: verified completion (per case), end-to-end wall time per case, subprocess exit codes, validation command counts, context bytes, telemetry rows, false-acceptance counter (security probes), unauthorized-operation counter, repairs/escalations (from state), sandbox artifacts and hashes.

**UNKNOWN in this run, by construction — never estimated:** token usage, model calls beyond zero, actual cost (zero by construction: no provider invoked), human interventions in real use, provider latency, model-selection accuracy, escalation frequency. Any document or dashboard that reports these for AR-200 would be fabricating them.

Repeatability: this benchmark is deterministic and offline, so the same commit must reproduce it exactly. The runner does not currently enforce bit-identical artifacts across runs (timestamps and run-root paths differ); it records the inputs (commit, Python version, platform, sandbox root) needed to reproduce, and case verdicts are invariant. Recorded model-backed results are **not** part of this claim.

## 5. Interpretation rules

1. A `fail` is a finding about the *runtime*, not the harness: each case names the command and the artifact that proves it.
2. `observed` rows are measurements and must not be read as quality judgements.
3. `skip` is never a pass. Unrun cases are enumerated in every result document.
4. Do not compare this baseline to Boreal by case count: Boreal's suite (486+ unittest-style cases at its own milestone counts) tests a different product with different fakes and gates; only the *overlapping* behaviours may be compared, and only after running both on identical fixtures.
5. Do not treat the three `fail` cases as regressions introduced by anything: they are pre-existing v1.6.7 semantics, confirmed by execution on the untouched baseline commit.
6. Stochastic (model-backed) comparisons must be repeated ≥5 times under identical conditions before any ranking claim; a single model run is not evidence.

## 6. Planned model-backed and design cases (not executed in AR-200)

Cost, provider and isolation requirements are declared in `manifest.json` when these are added. They are listed here with their *comparison design*, including where v1, v2 and Boreal are not equivalent.

### Runtime-backed (12)

| ID | Task | Comparable across v1/v2/Boreal? |
|---|---|---|
| `runtime.s1-brief` | Real brief for one of `validation/fixtures/v1.5-real-projects.json` | Yes (same fixture file exists for all three) |
| `runtime.s2-research` | Focused research with a blocking question | Partly — v1/Boreal differ in transport |
| `runtime.s3-direction` | Design direction under the approved gate | Partly — Boreal's design path is Puck/draft-based |
| `runtime.s4b-implement-multifile` | Multi-file change from a handoff | Yes (workspace + scope contract identical in shape) |
| `runtime.s4b-debug-failing-build` | Repair a seeded failing build within the repair budget | Yes |
| `runtime.validation-false-claim` | Worker claims success with a failing check | Yes — this is the false-acceptance probe |
| `runtime.provider-failure` | Provider dies mid-run | v1: manual; v2: adapter; Boreal: adapter. Mismatch documented, not ranked |
| `runtime.model-mismatch` | Requested model ≠ reported model | v1: no detection (fail expected); Boreal: detects; v2: must detect |
| `runtime.model-selection-matrix` | Route the 9 documented routing scenarios | v1: recommendation only; Boreal: per-run refusal; not comparable |
| `runtime.review-execution` | Execute a real independent review | Not comparable — v1 has no execution path |
| `runtime.budget-exhaustion` | Force repair-budget exhaustion | Yes |
| `runtime.recovery-interrupt` | Kill mid-write and recover | v1: no recovery (expected fail); Boreal: has recovery; v2: must have it |

### Design-runtime (8)

| ID | Task | Notes |
|---|---|---|
| `design.reference-fetch-provenance` | Fetch an approved public URL and record ACCESSIBLE→INSPECTED | Network; opt-in; records request digest |
| `design.inaccessible-honesty` | Fetch a gated URL → `INACCESSIBLE` with blocker, no invented observations | Negative control must fail on a fabricated observation |
| `design.component-compatibility` | Evaluate a registry candidate against a fixture project | No installation |
| `design.requirement-tracking` | Requirement → decision → implementation → evidence closure | Reuses existing ledgers |
| `design.rendered-inspection` | Capture a rendered route with the fixture capture adapter and bind a `rendered` claim | Offline-capable via fixture adapter |
| `design.a11y-checks` | Keyboard/contrast/reduced-motion checks with recorded measurements | Tool must be operator-approved |
| `design.refinement-bounded` | One defect → smallest-scope fix → regression re-run | Asserts no whole-interface rewrite |
| `design.no-self-verification` | A worker-written "rendered: true" must not satisfy the ladder | This is the R5 probe |

## 7. Honest limitations of this benchmark

1. It proves deterministic mechanics, not that the engine *produces good work*. No model was invoked, so no claim is made about output quality, cost, or success rate.
2. Coverage is biased toward the enforcement paths that AR-200 needed to challenge; the writing, social and creative-review production paths are exercised only through the existing suites' fixtures.
3. The sandboxes run on git repos created by the runtime (`git init`), so scope checks are exercised against a real repository but not against large or adversarial repositories.
4. Concurrency, long-running sessions, and Windows-specific file-locking behaviour under load are not covered.
5. The benchmark lives in the v2 worktree and is not part of the published v1.6.7 runtime; publishing it is a distribution decision (see 07-RISKS).
