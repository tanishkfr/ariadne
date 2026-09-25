# AR-204 — Test Results

Every command below was run in this worktree on the AR-204 branch, offline, with
no provider call.

## 1. Benchmark

```text
python benchmarks/run_benchmarks.py --label ar-204-final
```

The recorded final run executed on commit `7a4fc8a` with a clean tree
(`dirty_entries: 0` at run start) and is preserved as
`benchmarks/results/AR-204-final.json`, with `benchmarks/results/LATEST.json`
holding the same document. The AR-203 baseline is preserved as
`benchmarks/results/AR-203-final.json`; this worktree reproduced it exactly before
any AR-204 change was made.

| Metric | AR-203 baseline | AR-204 |
| --- | ---: | ---: |
| Cases | 190 | 226 |
| Pass | 185 | 219 |
| Fail | 0 | 0 |
| Observed | 3 | 5 |
| Error | 0 | 0 |
| Declared skip | 2 | 2 |
| Model calls | 0 | 0 |
| Cost | 0.0 | 0.0 |

All 190 AR-203 cases are preserved and pass unchanged. The 36 new cases are the
eight AR-204 groups plus the two measurement cases:
| Group | Cases | Result |
| --- | ---: | --- |
| `economics-accounting` | 5 | pass |
| `request-rendering` | 5 | pass |
| `tool-schemas` | 4 | pass |
| `externalized-output` | 6 | pass |
| `context-economics` | 4 | pass |
| `compaction` | 4 | pass |
| `decision-economics` | 3 | pass |
| `orchestration-economics` | 3 | pass |
| `harness-metrics` | 2 | observed |

The two observed cases are measurement-only: `harness-metrics.packet-economics`
and `harness-metrics.local-performance`. Their evidence is committed under
`docs/v2/AR-204/measurements/`.

## 2. Engine core

```text
python scripts/test-engine-core.py
```

`457/457` checks pass. The AR-203 suite contributed 330 of them and is unchanged;
`ar204_checks` adds 127 covering serialization determinism, source accounting,
price profiles, billing refusal, cache-observation channels, the task tree, the
verified-completion metric, the efficiency policy, rendering and redaction, the
prompt audit, capability packs, artifacts, history compaction, the execution
paths, decision batching and the twelve new security invariants. Seven CLI checks
cover the four new commands, including that an unsupported prompt profile is a
parser error and that a missing packet is refused.

## 3. The full known-good suite

| Suite | Command | Result |
| --- | --- | --- |
| Runtime self-test | `python scripts/ariadne.py --self-test` | 125/125 |
| Transport self-test | `python scripts/prepare-stage.py --self-test` | 50/50 |
| Repo contract | `python scripts/check.py` | PASS |
| Distribution lifecycle | `python scripts/test-distribution.py` | 55/55 |
| Release tooling | `python scripts/build-release.py --self-test` | 18/18 |
| Reasoners | `python scripts/reasoners.py` | 15/15 |
| Real projects | `python scripts/test-real-projects.py` | 29/29 |
| Social intelligence | `python scripts/test-social-intelligence.py` | 68/68 |
| Validation guards | `python scripts/validate.py --self-test` | 29 guards |
| Validation benchmark | `python scripts/validate.py --benchmark` | runs read, no failure |
| Writing architecture | `python scripts/test-writing-architecture.py` | exit 0 |
| Writing execution | `python scripts/test-writing-execution.py` | exit 0 |
| Engine core | `python scripts/test-engine-core.py` | 457/457 |
| Complete benchmark | `python benchmarks/run_benchmarks.py` | 226 cases, 0 fail, 0 error |

The repo-contract check prints its own link, required-file and duplicated-sentence
counts; they are quoted from its output rather than restated here.

## 4. Mutation testing

Ten economics protections were broken in memory, each re-tested, each restored
byte-exact (sha256 compared before and after). Every mutation was detected by the
case or check that exists to protect that rule:

| # | Protection mutated | Detecting case or check | Detected |
| --- | --- | --- | --- |
| M1 | required-context guard removed | `context-economics.required-context-not-removed` | yes |
| M2 | stale context cache accepted | `context-economics.cache-invalidation-on-source-change` | yes |
| M3 | failed attempt excluded from task cost | `economics-accounting.failed-attempt-included-in-task-cost` | yes |
| M4 | artifact truncated instead of stored whole | `externalized-output.large-output-stored-completely` | yes |
| M5 | required-capability guard disabled | `tool-schemas.missing-required-capability-refuses` | yes |
| M6 | review requirement ignored by the path planner | `orchestration-economics.cost-cannot-bypass-policy` | yes |
| M7 | unmeasured usage reported as zero | `economics-accounting.unknown-usage-stays-unknown` | yes |
| M8 | batch dependency guard disabled | `decision-economics.dependent-decision-requires-new-step` | yes |
| M9 | compaction drops a protected entry | `compaction.unresolved-work-preserved` | yes |
| M10 | structural cacheability reported as a cache hit | engine check for the cache-telemetry contract | yes |

No mutation file remains in the worktree: the harness lived outside the repository
and every touched file was restored and re-verified.

## 5. Measurement cases

```text
python benchmarks/run_benchmarks.py --only harness-metrics --label ar-204-measurement
```

Two observed cases ran in 7.6 seconds with zero model calls. The packet case
measured 134,279 bytes across four real packets with an 81.2% stable prefix; the
performance case measured twelve operations with warm-up and repeats and reports
cold figures alongside the warm medians. Both evidence documents are under
`docs/v2/AR-204/measurements/`.

## 6. Performance

| Operation | Before this milestone's optimisation | After |
| --- | ---: | ---: |
| `harness.packet_map`, median | 8.26 ms | 0.62 ms warm |
| `harness.render_request`, median | 11.72 ms | 0.91 ms warm |
| source hash, 16 KB | 0.060 ms | 0.008 ms memoised |
| `history.compact`, median | not applicable (new) | 0.83 ms for 9 entries |
| `tooling.pack_sizes`, median | not applicable (new) | 0.20 ms |

Cold figures sit next to the warm ones because repeated identical input is what the
memo accelerates: a first `packet_map` costs 6.90 ms and a first render 8.90 ms in
the committed artifact. Run-to-run variance on this host was visible and is
reported: `packet_map` warm ranged 0.32-0.75 ms and cold 5.8-9.6 ms across four
runs. No regression was measured elsewhere; the remaining timed operations are
below one millisecond with p90 values in the measurement artifact.

## 7. Completion criteria

| # | Criterion | State |
| ---: | --- | --- |
| 1 | AR-203 frozen and reproducible | yes, from `94b40f5` |
| 2 | Actual request assembly mapped | `01-HARNESS-MAP.md` |
| 3 | Task-level usage accounting exists | `economics.task_cost` |
| 4 | Context attributable by source | four buckets over four packets |
| 5 | Stable versus volatile measurable | `stable_prefix_digest`, per-section basis |
| 6 | Serialization deterministic | byte-identity checks |
| 7 | Cache structure represented | prefix plan plus split telemetry |
| 8 | Large outputs externalized without loss | artifact plus digest plus excerpts |
| 9 | Tool-schema economics measured | `06-TOOL-ECONOMICS.md` |
| 10 | Capability packs exist where justified | seven packs, no invented ones |
| 11 | Prompt instructions audited | `04-PROMPT-AUDIT.md` |
| 12 | Behavioural prompt changes reversible | `prompt_profile` default legacy |
| 13 | Adaptive context economics measured | `03-CONTEXT-ECONOMICS.md` |
| 14 | History strategy preserves evidence | archive plus protected kinds |
| 15 | Decision economics measurable | batch economics and layer comparison |
| 16 | Orchestration cost visible | task tree and shares |
| 17 | Simple paths do not bypass verification | guard plus mutation M6 |
| 18 | Routing cannot trade capability for price | invariant 45 checks |
| 19 | Verification invariants unregressed | 190 AR-203 cases still pass |
| 20 | Existing benchmarks green | 0 fail, 0 error |
| 21 | New benchmarks green | 34 pass, 0 fail, 0 error |
| 22 | Repository suites green | §3 |
| 23 | Mutation tests detect regressions | 10 of 10 |
| 24 | No paid provider required | 0 model calls, 0.0 cost |
| 25 | No fabricated quality claim | every `NOT_EXECUTED` recorded |
| 26 | Boreal unmodified | not touched |
| 27 | No remote action | no push, tag, release or publication |
| 28 | Worktree clean at closure | see `12-AR-204-REPORT.md` |
| 29 | AR-205 has an implementation-ready handoff | `13-AR-205-HANDOFF.md` |
