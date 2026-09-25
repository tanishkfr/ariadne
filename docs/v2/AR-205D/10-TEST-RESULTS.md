# 10 — Test results

Every result below was produced in this worktree
(`<path>`) with the standard library only, no
network and no model calls. Nothing was published, and no test was weakened,
skipped or deleted to reach a green state.

## 1. Suite results

| Command | Result |
|---|---|
| `python scripts/ariadne.py --self-test` | `PASS 125/125` |
| `python scripts/prepare-stage.py --self-test` | `PASS 50/50` |
| `python scripts/check.py` | `PASS` (18 sections, 0 broken links) |
| `python scripts/check.py --self-test` | `SELF-TEST PASS` |
| `python scripts/reasoners.py --self-test` | `PASS 15/15` |
| `python scripts/validate.py --self-test` | `PASS 29/29 guards all fail correctly on broken input` |
| `python scripts/test-distribution.py` | `PASS 55/55` |
| `python scripts/build-release.py --self-test` | `PASS 18/18` |
| `python scripts/test-real-projects.py` | `PASS 29/29` |
| `python scripts/test-social-intelligence.py` | `PASS 68/68` |
| `python scripts/test-writing-architecture.py` | `PASS 15/15` |
| `python scripts/test-writing-execution.py` | `PASS 14/14` |
| `python scripts/test-engine-core.py` | `PASS 578/578` (all suites; AR-205D adds 121 checks) |
| `python scripts/test-release.py` | `PASS 97/97` |
| `python scripts/test-wheel-install.py` | `PASS 14/14` |
| `python benchmarks/run_benchmarks.py --release` | release subset 56 cases, 0 fail / 0 error |
| `python benchmarks/run_benchmarks.py` | exhaustive 295 cases: 288 pass / 5 observed / 2 declared skip, 0 fail / 0 error |
| `python scripts/release-check.py --dist dist` | `PASS: the release gate is green` |

The AR-205 baseline for comparison: engine core 457/457, release tests 81/81,
benchmark 259 cases (252 pass / 5 observed / 2 declared skip / 0 fail /
0 error), release subset 45 cases. AR-205D keeps every one of those and adds
new coverage; the 259 legacy cases are unchanged.

## 2. AR-205D benchmark groups

36 new cases were added; all 36 pass individually against the repaired sources:

| Group | Cases | Result |
|---|---|---|
| `decision-compiler` | 5 | pass |
| `decision-graph` | 5 | pass |
| `decision-batching` | 4 | pass |
| `decision-cache` | 5 | pass |
| `decision-escalation` | 5 | pass |
| `decision-integrations` | 4 | pass |
| `decision-economics` | 3 new (6 in the group with AR-204) | pass |
| `golden-workflows` (D1–D5 new, 11 total) | 5 new | pass |

The five golden decision workflows are deterministic end-to-end fixtures:

| Fixture | What it proves |
|---|---|
| D1 `code-knows` | an exact fact never becomes a decision or a model call |
| D2 `bounded-judgment-drives-one-repair` | one bounded judgement, one repair, one verification |
| D3 `escalation-does-not-disguise-uncertainty` | a low-confidence decision escalates to a stronger path |
| D4 `high-confidence-still-stops-at-human` | a 0.99 decision on a protected operation still needs the human gate |
| D5 `cache-invalidation-on-relevant-change` | reuse only while the state is identical |

## 3. Mutation testing

`python scripts/test-decision-mutations.py` mutates critical protections in
copies of the sources under a workspace; the original module must refuse the
mutated behaviour and the mutant must allow it. Result: **9/9 mutations caught**,
sources left byte-identical.

| Mutation | Caught by |
|---|---|
| remove the deterministic-first guard | original refuses the model call for a known fact |
| weaken batch independence | original refuses a chained batch |
| remove the cache model-version binding | original refuses reuse under a changed version |
| allow confidence to authorize a protected action | original refuses at `PROTECTED` |
| remove the protected human gate | original keeps the gate human |
| accept an answer outside the closed set | original records it `invalid` |
| bypass the projected state digest | original refuses an unknown digest |
| permit a revoked cached decision | original refuses `REVOKED` |
| skip the generation justification | original refuses an unexplained generative need |

## 4. Adversarial review and repairs

One bounded adversarial review ran 15 probe scripts across classification,
cache, batching, escalation, authority, prompt-in-state, verification and
generation. It found six genuine defects (D1–D6); all six were fixed and now
have permanent regression coverage in `test-engine-core.py`:

| # | Attack | Before | After |
|---|---|---|---|
| D1 | serve a cached answer to a different question | served, `answer_valid: true` | refused: "cannot be reused" |
| D2 | forge the projection entries behind a real digest | recorded verbatim | refused: entries re-hashed and must match |
| D3 | `0.0` calibrated probability as sufficient evidence | accepted at MEDIUM/HIGH | refused: not a usable probability in (0, 1] |
| D4 | `known: true, value: null` fact | recorded as known | a `None` is never a known fact; falls through to facts |
| D5 | smuggle `prompt`/`credentials` through `projection_entries` | nested under `supplied_evidence` | refused before any provider call |
| D6 | `verified: false` satisfies a verification node | `SUCCEEDED` | refused: declared output not satisfied |

Re-running the probes after the repairs shows the safe behaviour for D1–D6, and
no new bypass appeared. The honest remaining limitation is unchanged:
prompt-in-state semantic manipulation inside the closed answer space is not
claimed to be fully resisted ([09 — Security](09-SECURITY.md)).

## 5. Repaired defects and new CLI coverage

While validating the new `decide --advise` surface, one additional defect was
found and fixed: a request missing its required arguments raised a `TypeError`
traceback instead of a clean CLI refusal. The command now validates the
arguments and stops with `STOPPED: decision advice '<family>' needs
argument(s): …` (exit 1). Four CLI checks cover the new surfaces:
`decision-trace`, `decide --providers`, `decide --compile --graph`, and the
advice-argument refusal.

## 6. Performance

Structural overhead was measured locally (Windows, CPython 3.11.9) and the raw
numbers live in `measurements/decision-intelligence-perf.json` (summarised in
[08 — Economics](08-DECISION-ECONOMICS.md)). Median costs in microseconds:
projection 13.4, trace 16.7, cache lookup 20.4, batch planning 27.0, plan
compilation 33.1, graph construction 52.6; the largest p95 is 137 µs. Every
operation is sub-millisecond, and none of these numbers measures provider
latency or model quality.

## 7. Reproduction

```text
python scripts/test-engine-core.py
python scripts/test-release.py
python scripts/test-decision-mutations.py
python scripts/ariadne.py --self-test
python scripts/prepare-stage.py --self-test
python scripts/check.py
python scripts/validate.py --self-test
python scripts/test-distribution.py
python scripts/build-release.py --self-test
python scripts/test-real-projects.py
python scripts/test-social-intelligence.py
python scripts/test-writing-architecture.py
python scripts/test-writing-execution.py
python scripts/test-wheel-install.py
python benchmarks/run_benchmarks.py
python scripts/release-check.py --dist dist
```
