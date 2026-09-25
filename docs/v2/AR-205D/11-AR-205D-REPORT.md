# 11 — AR-205D milestone report

## 1. Repository state

| Field | Value |
|---|---|
| Repository | `<path>` (worktrees as siblings) |
| Worktree | `<path>` |
| Branch | `v2/ar-205d-decision-intelligence` |
| Base commit | `937cbde6e5ef55951b71f07ed2cbc26cea364718` (AR-205 release candidate) |
| Final source commit | `1d65bf796e83f08689284954a7a423d0e57831b9` (the artifacts embed this commit in `ariadne-release.json`) |
| Publication | local-only; nothing was pushed, tagged, released or sent anywhere |

## 2. Starting AR-205 baseline

The AR-205 release candidate was verified before any change: worktree at the
exact base commit with a clean tree, AR-205 `release-check` green, and
`benchmarks/results/LATEST.json` recording the accepted run (259 cases, 252 pass,
5 observed, 2 declared skip, 0 fail, 0 error; engine core 457/457, release tests
81/81, wheel 14/14, release subset 45). AR-205 was then frozen; AR-205D never
reopened its subsystems.

## 3. Decision Compiler

`decisions/compiler.py`. Deterministic construction from declared state and rule
tables — it asks no one. Each requirement classifies as `DETERMINISTIC`,
`BOUNDED`, `GENERATIVE`, `HUMAN` or `UNRESOLVED`; a fact code already knows wins
before the rule table (`CODE_KNOWS`); an undeclared kind is `UNRESOLVED` with an
escalation reason and never silently becomes `GENERATIVE`. The plan carries
deterministic facts, bounded questions with projection contracts, dependency
edges (cycles and missing dependencies refused), generative needs with a
declared reason, verification requirements, protected human actions, a
fast-path verdict and structured escalations. `facts={"id": null}` is not a
known value, and an explicit `known: null` falls through to a real fact.

## 4. Decision Graph

`decisions/graph.py`. A small record-based graph (kinds `DETERMINISTIC`,
`DECISION_BATCH`, `GENERATION`, `VERIFICATION`, `HUMAN_GATE`) over the existing
run state — no parallel orchestrator. Cycles and missing dependencies are
refused at creation; only ready nodes run; outcomes are immutable; a
`HUMAN_GATE` never completes by engine action and needs a recorded human
identity on a human channel; invalidating an input transitively invalidates
dependents; completion is never inferred as success. Verification nodes require
an affirmed `verified` output.

## 5. State projections

`decisions/projections.py`. Four closed contracts — failure classification,
review escalation, evidence relevance, route family — each declaring every field
as `REQUIRED`, `OPTIONAL` or `FORBIDDEN`. A missing required field raises
`INSUFFICIENT_STATE` rather than guessing; unknown fields are refused; forbidden
material (authorization, approvals, credentials, prompt text) never enters. The
integrations path refuses contract-forbidden caller slices before any provider
call, and every projection carries its own digest.

## 6. Decision cache

`decisions/cache.py`. The key binds the question definition digest, the
projection digest, provider, concrete model version and policy version; a moving
alias cannot form a key. Lookup checks freshness, expiry, revocation,
supersession and stored fingerprints; a hit is served by `materialise`, which
re-validates the question identity, re-hashes the offered entries against the
recorded digest, re-validates the cached answer against the current option set
and re-judges it under the current policy. Reuse is a new decision record that
cites the original and preserves confidence provenance; it never raises
confidence and never authorizes.

## 7. Escalation

`decisions/escalation.py`. `DETERMINISTIC → BOUNDED → STRONGER_BOUNDED →
GENERATIVE → HUMAN`, with structured reasons (`NO_DETERMINISTIC_RULE`,
`NO_DECISION_PROVIDER`, `LOW_CONFIDENCE`, `NO_CONFIDENCE`, `CAPABILITY_MISSING`,
`CONFLICTING_EVIDENCE`, `OUT_OF_DISTRIBUTION`, `DECISION_FAILED`,
`GENERATIVE_REQUIRED`, `POLICY_REQUIRES_HUMAN`). "Stronger" is capability-shaped
(better calibration, specialised provider, richer projection, alternate
question version, independent second decision), never price-ranked. Optional
consensus records agreement as agreement, not truth; disagreement is an explicit
`DECISION_CONFLICT`, never an averaged label.

## 8. Real integrations

`decisions/integrations.py` implements four genuine engine choices through one
compile → project → batch → policy → escalate path:

| Integration | Engine entry point | Deterministic-first rule |
|---|---|---|
| failure classification | `execution.classify_with_decision` | a mapped source never consults a provider |
| review escalation | `review.escalation_advice` | protected/low-stakes/high-stakes rules answer first; policy still controls required review |
| evidence relevance | `verification.relevance_advice` | stale evidence and missing provenance answer `IRRELEVANT`/`UNKNOWN` deterministically; freshness can never be overridden |
| route family | `routing.family_advice` | a declared task-kind map answers first; protected policy wins |

## 9. Provider architecture

`decisions/providers.py`. The generic contract expresses supported primitives,
batching, probabilities, explicit model versions, maximum options, state limits,
parallel questions and usage metadata; capabilities live in the capability
registry, and nothing in the engine special-cases a vendor. An optional adapter
boundary and a Jev-shaped capability map (`BINARY`, `CHOICE`, `SCALE`,
`MULTISELECT`, `PARALLEL_BATCH`, `PROBABILITIES`, `VERSIONED_MODEL`) are present;
the offline fixture interface keeps tests credential-free, and live use is
recorded `NOT_EXECUTED`. `UnavailableProvider` keeps provider absence a
structured state, not a crash; no paid provider is required anywhere.

## 10. Confidence and risk

`decisions/policy.py`. The policy is categorical: consequence classes `LOW`,
`MEDIUM`, `HIGH`, `PROTECTED`; evidence levels must reach `OBSERVED` (medium)
and `REPRODUCED` (high); confidence is accepted only as a usable probability in
`(0, 1]` and only from `CALIBRATED_PROBABILITY`, `PROVIDER_PROBABILITY` or
Ariadne's own `DERIVED_CONFIDENCE` — never a generative self-report. `PROTECTED`
refuses under every confidence, including 1.0. Confidence is never permission,
and five independent test families and two mutations assert it.

## 11. Decision trace

`decisions/trace.py` derives the trace from records only: facts known, decisions
and their confidence kind, policy verdicts, escalation reasons and their next
rung, generation justifications, cache reuse, consensus and verification
outcomes. `ariadne decision-trace --run-root … --json` and
`ariadne decide --explain/--inspect` expose it read-only; hidden provider
reasoning is never exposed.

## 12. Decision economics

`decisions/economics.py` reports structural counters from records: calls avoided
by deterministic facts and by bounded decisions, generative calls required,
batches and questions per batch, cache hits and reuses, escalations, second
opinions, state bytes and decision-plane overhead. No monetary saving is claimed
without measured comparable usage, and the compiled-plan comparison states
plainly that no quality parity is claimed. Measured local overhead is
sub-millisecond per operation (§19).

## 13. Calibration data

`decisions/calibration.py` records raw outcome evidence per decision — answer,
confidence and kind, provider/model, downstream verified result, later
contradiction, human override — under explicit categories (`SUPPORTED`,
`CONTRADICTED`, `OVERRIDDEN`, `UNRESOLVED`). Nothing is tuned automatically and
a downstream failure is never auto-labelled a wrong decision; future analysis
belongs after v2. Calibration uses ids, digests and outcome categories rather
than raw sensitive task content.

## 14. Security and adversarial review

`docs/v2/AR-205D/09-SECURITY.md`. One bounded review ran 15 probe scripts; it
found six genuine defects (cache reuse not bound to the question, trusted
projection entries, zero-confidence acceptance, `known` with a null value,
forbidden-key smuggling, verification output by key presence only). All six are
fixed with permanent regressions; re-running the probes shows the safe
behaviour. Authority attacks, prompt-in-state closed-set enforcement and the
human gate held throughout. One further defect was found while validating the
new CLI: an advice request missing required arguments now stops cleanly instead
of raising a traceback.

## 15. Mutation tests

`python scripts/test-decision-mutations.py`: 9/9 critical protections catch their
mutation and the sources are restored byte-identical (deterministic-first guard,
batch independence, cache model-version binding, confidence-is-not-authority,
protected human gate, closed answer set, state digest, revoked-cache refusal,
generation justification).

## 16. Benchmarks before and after

| | AR-205 baseline | AR-205D |
|---|---|---|
| exhaustive cases | 259 | 295 |
| pass / fail / error / observed / skip | 252 / 0 / 0 / 5 / 2 | 288 / 0 / 0 / 5 / 2 |
| engine core | 457/457 | 578/578 |
| release tests | 81/81 | 97/97 |
| release subset | 45 | 56, 0 fail |

All 36 new cases pass, including the five golden decision workflows D1–D5. No
legacy case was changed or removed.

## 17. Full regression

Every named suite is green: runtime 125/125, transport 50/50, repository
contract PASS, repository aggregate self-test PASS, reasoners 15/15, validation
guards 29/29, distribution 55/55, release bundle 18/18, real projects 29/29,
social 68/68, writing 15/15 and 14/14, engine core 578/578, AR-205 release tests
97/97. 0 FAIL / 0 ERROR.

## 18. Release regression

Migration behaviour, packaging, versioning and the public surface are unchanged.
The definitive gate ran on the clean source commit with artifacts built from it:

```text
PASS  clean worktree
PASS  version consistency                  all surfaces name 2.0.0rc1
PASS  public API surface                   37 stable, 54 provisional
PASS  experimental defaults                all AR-204 experiments keep their conservative defaults
PASS  repository contract                  PASS
PASS  release tests                        PASS 97/97
PASS  distribution lifecycle               PASS 55/55
PASS  runtime bundle and private material  PASS 18/18
PASS  release benchmark subset             pass 56, fail 0, error 0
PASS  wheel install                        PASS 14/14
PASS  release artifacts                    7 artifacts verified against the manifest
PASS: the release gate is green
```

The built candidate wheel was additionally installed into a throwaway venv with
no network and verified: version `Ariadne 2.0.0rc1`, managed install, `doctor`,
and an ordinary-language project start from the installed runtime, with the
source checkout absent from the runtime path.

## 19. Performance

Measured local overhead (Windows, CPython 3.11.9; 200 iterations):
state projection 13.4 µs median, trace 16.7 µs, cache hit 20.4 µs, batch
planning 27.0 µs, compile plan 33.1 µs, graph build 52.6 µs. All sub-millisecond;
these are structural overheads, not provider latency.

## 20. Files changed

New decision modules: `src/ariadne_engine/decisions/{compiler,graph,planner,
projections,cache,escalation,consensus,integrations,generation,trace,
calibration,economics}.py`; extended `decisions/{providers,policy,contracts,
__init__}.py`. Engine: `contracts.py`, `persistence.py`, `events.py`, `api.py`,
`public.py`, `execution.py`, `routing.py`, `review.py`, `verification.py`.
Scripts: `ariadne.py`, `test-engine-core.py`, `test-release.py`, new
`test-decision-mutations.py`. Benchmarks: `arbench/ar205d_cases.py`, `arbench/
__init__.py`, `arbench/release_subset.py`, `manifest.json`. Docs: `README.md`,
`docs/v2/AR-205D/01–12` and `measurements/`. Exact list: `git diff --stat
937cbde6..<final>`.

## 21. Honest limitations

No live decision provider was called, so no calibration, threshold or
provider-quality claim exists. Structural counters are not money. The Jev-shaped
adapter boundary is unexercised (`NOT_EXECUTED`). Prompt-in-state semantic
manipulation within the closed answer space is not claimed to be fully resisted.
Boreal remains untouched and contract-verified only, exactly as AR-205 left it.

## 22. Release delta

[12 — Release delta](12-RELEASE-DELTA.md). Summary: decision-intelligence
becomes a normal execution mechanism — compiler, graph, automatic batching,
minimal projections, state/version-bound cache, escalation, four real
integrations, generation gate, trace, calibration collection, provider contract
and structural economics — while every AR-205 release surface is preserved. The
version stays `2.0.0rc1`; the AR-205 artifacts are superseded and not reused.

## 23. Git state

All AR-205D work is committed on `v2/ar-205d-decision-intelligence`:

| Commit | Contents |
|---|---|
| `1d65bf796e83f08689284954a7a423d0e57831b9` | the AR-205D source commit: engine, contracts, integrations, CLI, tests, benchmarks, docs 01–12, benchmark results |
| the record commit that follows | documentation-only: this report's artifact hashes and the gate output |

The artifacts were built from the source commit, and `ariadne-release.json`
records `source_commit: 1d65bf796e83f08689284954a7a423d0e57831b9`. No remote
action occurred: nothing was pushed, tagged, released or published.

## 24. Closure decision

**READY_FOR_USER_ACCEPTANCE**

The release gate ran green on the clean source commit `1d65bf7` with artifacts
built from it: clean worktree, versions, public API, experimental defaults,
repository contract, release tests 97/97, distribution 55/55, release bundle
18/18, release subset 56 cases 0 fail / 0 error, wheel install 14/14, and seven
artifacts verified against the manifest. The full regression is green
(0 FAIL / 0 ERROR) and the exhaustive benchmark is 295 cases with 0 fail /
0 error. The human still decides whether to tag, publish and ship; AR-205D has
prepared the candidate and performed no public release action.

## 25. Final v2 release candidate

Version `2.0.0rc1`, built from source commit
`1d65bf796e83f08689284954a7a423d0e57831b9` (`dist/ariadne-release.json`):

| Artifact | SHA-256 |
|---|---|
| runtime zip | `09cae8d139da6c5a7ec923596e95490354e16a7dd719289e79c80e90f58d078d` |
| launcher wheel | `5cccc382d060c2fc9f4f1cf980bcfcebd95811d1aa0af1a86464b5009f7095e5` |
| release descriptor | `807300ad0f40221558d391fca9e8292934d6b8f0d2e2befef8f03979cacbaeda` |
| release notes | `0ad45a897022a1c208fcce89d1f6ed45321f17757bfad81809bd72a355277383` |

The artifact manifest verifies without problems; an isolated environment
installed and started the wheel from `dist` (§18). No tag, push, release or
publication occurred.
