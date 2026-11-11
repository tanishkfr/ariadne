# Model Routing Evaluation �?" Ariadne 2.4B

**Policy:** `model-evidence-1`  
**Shipped mode:** shadow/advisory only (`model_routing=off` by default; `shadow`
records advice, `apply_qualified` is a separate human-promoted path).  
**Authority:** none. This document evaluates routing evidence; it does not
authorize a provider, a model, a gate or a release.

## 1. What changed

Ariadne's router already selected by capability, role, difficulty, stakes,
reversibility, context need and prior failure. 2.4B adds an **evidence registry**
and a **shadow recommendation** over those decisions:

```
task measurement -> model observation -> registry record -> recommendation
                                                              |
                                      deterministic route keeps control
```

The registry is
[`src/ariadne_engine/model_evidence.py`](../../../src/ariadne_engine/model_evidence.py).
It does not replace `routing.py`; `routing.evidence_advice()` attaches advice to
an already-made decision and always sets `controls_execution: false`.

## 2. Qualification vocabulary

| Level | Meaning | Can inform a recommendation? |
|---|---|---|
| `DECLARED` | an adapter claims a capability; nothing was checked | **No** |
| `DIRECTLY_OBSERVED` | at least one engine-recorded attempt exists | Only as context, never as qualified |
| `OBSERVED_QUALIFIED` | at least 5 attempts and at least 4 validated | Yes, shadow advice |
| `BENCHMARK_QUALIFIED` | at least 5 formal benchmark observations and 4 validated | Yes; the only level a human may promote |
| `UNAVAILABLE` | a probe or observation established it cannot be used | Excluded |
| `STALE` | older than 30 days or describing an older model revision | Excluded |
| `UNKNOWN` | provider/model identity was not observed | Excluded |

These are **policy gates over measured counts**, not probabilities. A record with
4/5 validated is not "80% likely to succeed"; it is a record with four validated
outcomes and one that did not validate.

## 3. Recommendation rules

The deterministic rules are intentionally simple and auditable:

1. No observation for the baseline → `KEEP_BASELINE`.
2. Baseline stale, unavailable, or with at least two recorded validation
   failures → a fresh, qualified alternative may be recommended.
3. Baseline qualified and healthy → `KEEP_BASELINE`, even when alternatives are
   qualified. A working route is not shuffled for variety.
4. A lighter alternative is recommended only when the caller **declared** its
   tier and the task is low/medium stakes and not high complexity. Tiers are
   never inferred from a model name.
5. The independent-review role excludes the implementer's adapter, provider and
   model. A recommendation cannot override that boundary.
6. An empty authorized-provider set returns `NO_AUTHORIZED_PROVIDER`; no route
   is invented.
7. `UNKNOWN` identity cannot qualify. A worker's claim is not an observation.

## 4. Application gate

`adapter_ranking()` may reorder eligible adapters only when **all** of these
hold:

- `model_routing=apply_qualified` is explicitly recorded for the run;
- the candidate is `BENCHMARK_QUALIFIED`, current, and has at least 8 samples;
- a **human promotion** exists for that provider/model/capability/family;
- the baseline is degraded or unavailable;
- the candidate is not excluded by an independence boundary;
- the adapter already satisfies the ordinary capability, discovery and scope
  checks.

Anything less returns `apply: false`. An explicit `--adapter` request still wins
and is never reordered. This is the documented deterministic fallback: the
existing preference order remains the control path.

## 5. Evidence recorded in this pass

### Deterministic cases

All of the following are in `scripts/test-ar24b.py` and the `intelligence`
benchmark group:

| Boundary | Result |
|---|---|
| No observation → keep baseline | pass |
| Declared capability is not qualified | pass |
| 4 samples are insufficient | pass |
| Unknown model identity is not qualified | pass |
| Stale observation is not used | pass |
| Degraded baseline with qualified alternative | pass (advice only) |
| Healthy baseline is not shuffled | pass |
| Lighter tier only with declared tier and low stakes | pass |
| Independent review excludes implementer | pass |
| Unpromoted evidence cannot reorder adapters | pass |
| No authorized provider is refused | pass |
| Promotion requires benchmark qualification, freshness and 8 samples | pass |

### Live provider probes

| Adapter | Version | Auth observed | Live task result | Measured wall-clock |
|---|---|---|---|---|
| `command-code` | 1.88.5 | Command Code subscription (prior 2.4A-R observation; not re-authenticated by this suite) | validated, Proof `VP-0001` ACCEPTED | 169.4s |
| `opencode` | v2.2.5 | stored provider entry; GitHub Copilot available | validated, Proof `VP-0001` ACCEPTED | 94.0s |
| `codex` | 0.166.0 | ChatGPT login reported by `codex login status` | not run in this pass | `UNKNOWN` |
| `claude` | 2.1.245 | `claude auth status` reports `loggedIn: false` | not run | `UNKNOWN` |
| `cursor-agent` | not installed | `UNKNOWN` | not run | `UNKNOWN` |

Evidence: `validation/runs/2.4b/live-command-code.log`,
`validation/runs/2.4b/live-opencode.log`.

The live samples establish that the existing T1 path still executes through two
distinct authenticated adapters. They do **not** establish a model ranking:
each adapter ran one small task and no provider reported token usage. The
registry therefore contains no `BENCHMARK_QUALIFIED` live record.

## 6. What is not claimed

- No claim that DeepSeek V4.1 Flash, GPT-5.6 Luna, GPT-6.1 Terra or any other
  model is better than another.
- No claim that a cheap model matches an expensive one.
- No provider quota, price or cache metric was measured.
- No production route was changed by model evidence in this pass. The default
  is `off`; the evaluation used shadow advice only.
- The deterministic benchmarks prove the refusal and qualification rules work on
  fixtures. They do not prove a live efficiency gain.

## 7. Promotion requirements

Before any route change can be applied:

1. Run the same bounded workloads on the baseline and candidate model under the
   same starting revision, scope and validation.
2. Record at least 8 formal benchmark observations per candidate capability and
   task family, with the actual provider/model/revision.
3. Keep the independent review distinct from the implementer.
4. Have a human record `model-promote` with a reason and a narrow family scope.
5. Re-run the regression, adversarial and false-acceptance suites.
6. Keep the baseline route available as the deterministic fallback.

Until then, 2.4B's routing improvement is **operational shadow evidence**, not a
proven live efficiency gain.
