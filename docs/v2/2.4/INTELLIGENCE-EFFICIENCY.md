# Intelligence & Efficiency �?" Ariadne 2.4B

**Milestone:** 2.4B, Phase B of the 2.4 line.  
**Branch:** `release/2.4b-intelligence-efficiency`  
**Baseline:** `3ec1efc1764076043d08b13ba3b6aa6361bb6a04`  
**Status:** candidate, not published. Tagging, pushing and release publication
remain separate human decisions.

## 1. The thesis

Ariadne already preferred deterministic computation over bounded judgment and
bounded judgment over generative execution. 2.4B adds the feedback loop that was
missing:

```text
task attempt
   -> measured record (observed / reported / declared / unknown)
   -> model and skill evidence
   -> advisory route or skill proposal
   -> existing deterministic policy still decides
   -> verified outcome (or an honest refusal)
```

The goal is **verified outcomes per unit of resources consumed**, not cheaper
routes for their own sake. A cheap failed attempt is a cost, not a saving.

## 2. What was added

| Area | Module | What it does |
|---|---|---|
| Measurement | `ariadne_engine/measurement.py` | One versioned row per attempt; provenance per field; completed ≠ accepted; unknowns stay unknown |
| Model evidence | `ariadne_engine/model_evidence.py` | Qualification levels, freshness, sample-size gates, shadow recommendation, narrow human-promoted fallback |
| Context | `context.py`, `continuation.py` | Revision binding, byte accounting, adaptive reduction, stale refusal, structured continuation |
| Skills | `skill_intelligence.py` | Association-based effectiveness, mandatory preservation, human-reviewed proposals |
| Integration | `api.py`, `mcp.py`, `scripts/ariadne.py` | Same read-only report through CLI/API/MCP; no duplicate routing or verification semantics |
| Evaluation | `scripts/evaluate-intelligence.py`, `benchmarks/workloads/2.4b-intelligence.json` | 28 workloads, deterministic run, baseline comparison, context experiment |

## 3. Configuration and defaults

Every behaviour-sensitive setting remains behind an explicit flag:

| Setting | Values | Default |
|---|---|---|
| `context_reduction` | `off`, `adaptive` | `off` |
| `model_routing` | `off`, `shadow`, `apply_qualified` | `off` |
| `compaction` | `off`, `structured_v1` | `off` |
| `prompt_profile`, `tool_loading`, `history_format`, `packet_order` | unchanged | unchanged |

`model_routing=shadow` records advice without changing a route.
`model_routing=apply_qualified` still requires a human promotion and a
benchmark-qualified record with at least 8 samples; otherwise the existing
adapter order is used.

The efficiency configuration is recorded on the run state with a digest, so a
result can name the profile that produced it and be reverted deterministically.

## 4. Before/after results

### 4.1 Deterministic task verification

| Metric | Baseline 2.4A-R | 2.4B candidate | Status |
|---|---|---|---|
| Full benchmark passes | 338 | **346** | +8 new cases; no regressions |
| Full benchmark failures | 0 | **0** | equal |
| Full benchmark errors | 0 | **0** | equal |
| Observed | 5 | **5** | unchanged |
| Declared skips | 2 | **2** | unchanged |
| Release subset | 90/90 (2.4A-R record) | **97/97** | +7 new cases |
| Shared 2.4B workload cases | 20/20 | **27/27** (unique cases) | equal on shared, new cases pass |
| Engine core | 586/586 | **586/586** | equal |
| 2.4A reliability suite | 21/21 | **21/21** | equal |
| 2.3B/2.3C/2.3D | green | **green** | equal |
| Distribution / wheel install | green | **55/55, 14/14** | equal |

The full-benchmark duration differs (baseline 1065.656s, candidate 613.202s) but
the case sets and machine load differ; no speed claim is made from it.

### 4.2 Context efficiency (measured)

Same request, same validation command, same six unchanged helper files in scope;
only `context_reduction` differs:

| Metric | `off` | `adaptive` | Difference |
|---|---:|---:|---:|
| Packet bytes | 63,812 | 35,591 | **−28,221 (−44.2%)** |
| Included sources | 20 | 14 | −6 |
| Omitted sources | 0 | 6 | +6 |
| Contract/request/mandatory methods retained | yes | yes | required facts preserved |
| Provider token reduction | `UNKNOWN` | `UNKNOWN` | not estimated |
| Live success after reduction | not run | not run | `UNKNOWN` |

This is a real file-size measurement on a deterministic fixture, not a provider
token or billing claim. It is the one material efficiency benefit demonstrated
under comparable conditions in this pass.

### 4.3 Cache and repeated processing

| Metric | Value | Classification |
|---|---:|---|
| Local source-hash cache hits | 8 | Measured, deterministic run |
| Invalidations after source change | 4 | Measured |
| Stale cached hash reused | 0 | Refused by test |
| Provider prompt-cache reads | `UNKNOWN` | Not supplied by any provider |
| Tokens saved by cache | `UNKNOWN` | Not estimated |

### 4.4 Model routing

| Metric | Baseline | 2.4B |
|---|---|---|
| Operational performance registry | absent | **present** |
| Qualification levels | absent | **present** |
| Shadow recommendations | absent | **present** |
| Adapter order changed by evidence | absent | **0** (no promotion, no qualified live record) |
| Live provider samples | historical | **2 tasks; both validated + proof** |
| Model success-rate comparison | `UNKNOWN` | `UNKNOWN` |

The mechanism is implemented and tested; the live efficiency gain is **not
measured**. No live route was changed.

### 4.5 Skills

| Metric | Baseline | 2.4B |
|---|---|---|
| Selected/invoked/completed distinction | present | present |
| Association with accepted outcome | not reported | **reported as association** |
| Recurring unmet-method proposal | absent | **present** |
| Automatic registry change | absent | **refused by construction** |
| Mandatory method dropped | impossible | **still impossible** |
| Skill overhead (token) | `UNKNOWN` | `UNKNOWN` |

## 5. Integration

The same durable state yields the same read-only report through:

- `python scripts/ariadne.py intelligence --project <p> --json`
- `ariadne_engine.api.intelligence_report(state)`
- MCP tool `intelligence_report` (read-only; it cannot set approval, reviewer or
  acceptance fields)

`model-evidence`, `route-evidence`, `model-promote`, `continuation` and
`skills-proposals` are additive CLI surfaces. `task-start` gained
`--context-reduction` and `--model-routing` so the first packet of a run can
actually use the profile it will be measured under.

## 6. Rollback

- `context_reduction=off` restores the previous packet behavior.
- `model_routing=off` removes even shadow advice from run preparation; no route
  changes because none were applied.
- `model-promote` records a promotion but does not alter an adapter unless
  `apply_qualified` is also set.
- Continuations are additive records; deleting no evidence is required.
- Skill proposals are inert records; the trusted registry is untouched.

## 7. Limits

- The context benefit is fixture-bound and measured in bytes, not tokens.
- Model routing has no live qualified record, so its efficiency benefit is
  unmeasured; the verdict is PARTIAL for that reason.
- The two live tasks prove execution and validation, not a model ranking.
- No provider quota, authentication freshness, token count or cost was measured
  for the live samples.
- macOS and Linux were not executed.
- A cheap-looking total with poor measurement coverage is visible as such in the
  report; `UNKNOWN` is never zero.

## 8. Evidence

- [INTELLIGENCE-BASELINE.md](INTELLIGENCE-BASELINE.md)
- [MODEL-ROUTING-EVALUATION.md](MODEL-ROUTING-EVALUATION.md)
- [CONTEXT-EFFICIENCY.md](CONTEXT-EFFICIENCY.md)
- [SKILL-INTELLIGENCE.md](SKILL-INTELLIGENCE.md)
- [2.4B-QUALIFICATION.md](2.4B-QUALIFICATION.md)
- `scripts/test-ar24b.py`, `scripts/test-ar24b-mutations.py`
- `benchmarks/arbench/ar24b_cases.py`,
  `benchmarks/workloads/2.4b-intelligence.json`
