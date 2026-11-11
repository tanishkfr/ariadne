# Ariadne 2.4B �?" Intelligence Baseline

**Baseline:** Ariadne 2.4A-R at `3ec1efc1764076043d08b13ba3b6aa6361bb6a04`
(`release/2.4a-r-hardening`), reproduced in a detached worktree at the same
commit.
**Candidate:** `release/2.4b-intelligence-efficiency`.
**Status:** this is a measurement record, not a claim that 2.4B is better. The
candidate/after comparison is in
[2.4B-QUALIFICATION.md](2.4B-QUALIFICATION.md).

## 1. What was measured before changing behaviour

The baseline was established in four layers, in this order:

1. **Execution records already owned by the engine.** A T1 task record contains
   attempts, the engine's own validation, the independent review, the Proof Pass
   receipt and the human acceptance decision. An execution record contains the
   requested, worker-reported and engine-observed identity, plus usage only when
   an adapter or the runtime supplied it.
2. **A new projection, not a new store of truth.** `ariadne_engine/measurement.py`
   projects those records into one versioned row per attempt. Every field carries
   `OBSERVED`, `REPORTED`, `DECLARED` or `UNKNOWN` provenance. An update
   supersedes the earlier row instead of overwriting it.
3. **A reproducible workload set.**
   [`benchmarks/workloads/2.4b-intelligence.json`](../../../benchmarks/workloads/2.4b-intelligence.json)
   defines 28 bounded workloads in the required families: 27 deterministic and
   one live. Each names the original request, starting revision, permitted scope,
   required validation, expected behaviour and mapped benchmark case.
4. **A direct baseline run.** The full deterministic benchmark was executed on a
   clean worktree at the baseline SHA, not inferred from another milestone's
   report.

## 2. Baseline deterministic results

Windows, Python 3.11.9. Same machine class, same command, separate worktree.

| Suite | Result | Evidence |
|---|---|---|
| Full benchmark at baseline SHA | **338 pass, 0 fail, 0 error, 5 observed, 2 skip** in 1065.656s | `validation/runs/2.4b/bench-baseline-full.txt` |
| Shared 2.4B workloads on baseline | **20/20 pass** (the 7 new `intelligence.*` cases do not exist there) | `validation/runs/2.4b/evaluation-full.json` |
| Release subset at baseline | **90/90** recorded by the 2.4A-R hardening pass | [RELEASE-HARDENING.md](RELEASE-HARDENING.md) |
| Engine core | **586/586** recorded by the 2.4A-R hardening pass | [RELEASE-HARDENING.md](RELEASE-HARDENING.md) |

The 338/5/2 counts are identical to the 2.4A-R report at the same SHA. The
baseline release-subset run attempted for this pass timed out at the harness
bound and was not counted; the 90/90 value above is the recorded 2.4A-R result,
not a fresh 2.4B measurement. This distinction is kept deliberately.

## 3. Routing behaviour at baseline

Before 2.4B, model selection was already deterministic and capability-based:

- routing used **capability class, execution role, difficulty, stakes,
  reversibility and recorded failures**; it did not consume model-performance
  observations because none existed;
- adapter selection used declared capabilities, executable discovery, recorded
  failures for the task and a declared preference order;
- a missing capability produced a named blocker; an authorization refusal was
  never routed around;
- review independence was an execution/identity fact, not a model label;
- the only provider-performance data in a run was per-execution telemetry, and
  usage/cost stayed `UNKNOWN` when no adapter supplied them.

There was no operational model-performance registry, no evidence-backed
recommendation and no shadow comparison. `model_routing` did not exist.

## 4. Context behaviour at baseline

The AR-202 adaptive-context layer already:

- recorded an include/omit decision and machine-readable reason for every
  candidate source;
- omitted design sources from non-design tasks and forbidden sources from a
  stage;
- deduplicated identical content;
- cached source hashes in a run-root `context-cache.json`, invalidated by size,
  mtime, stage, policy version and revision;
- never allowed a plan to add a source the transport did not already allow.

What it did **not** have:

- a revision binding on the decision record itself;
- measured included/omitted byte totals;
- an explicit `context_reduction=adaptive` rule that removes an unchanged
  optional scope file while leaving it readable in place;
- a task-level continuation projection independent of conversation history.

The context-cache benchmark cases already recorded **8 cache hits and 4
invalidations** in the shared release run at both baseline and candidate. That
number is real but small and fixture-bound; it is not a provider prompt-cache
measurement.

## 5. Skill behaviour at baseline

Skill selection was already deterministic and mandatory-preserving. The AR-23C
ledger already distinguished `selected`, worker-reported `invoked`,
engine-observed `completed` and `unmet`. The baseline report could say what was
selected and what was observed, but it could not:

- separate a skill's **association** with an accepted task from evidence that
  the skill caused the outcome;
- produce a human-reviewable improvement proposal from recurring unmet or
  never-invoked methods;
- refuse an automatic registry rewrite by construction.

## 6. Available metrics and missing metrics

| Metric | Baseline availability | Source |
|---|---|---|
| Verified task outcome | Available for T1 tasks | task record + validation + review + proof |
| Attempt count / repairs | Available | task record |
| Wall-clock attempt time | Available where timestamps exist | attempt/execution records |
| Packet size | Available for a prepared task | packet file size |
| Context sources included/omitted | Available | `context_decisions` |
| Cache hits/misses/invalidations | Available | context decision + cache file |
| Provider/model identity | Observed only if the runtime observed it | execution record |
| Input/output tokens | Only provider-reported | execution usage |
| Cached input tokens | Only provider-reported | execution usage |
| Provider cost | `UNKNOWN` unless billing is recorded | economics |
| Provider quota / authentication | `UNKNOWN` | not measured by the engine |
| Model revision | `UNKNOWN` unless reported | provider usage |
| Skill document bytes | Registry metadata where measured | skills registry |
| Human intervention | Acceptance identity / interventions | run state |
| Prompt-cache read/write tokens | `UNKNOWN` | no provider exposed it |

## 7. Baseline limitations

- The full benchmark is deterministic and offline: it proves engine mechanics,
  not output quality, provider reliability or cost.
- The machine was shared during the baseline run; the 1065s duration is not a
  performance target.
- The fixture tasks are small. A 44% packet reduction on a six-file fixture does
  not prove a 44% reduction on every real repository.
- Live provider observations are bounded samples, not a model ranking. Two live
  tasks are recorded in [2.4B-QUALIFICATION.md](2.4B-QUALIFICATION.md).
- No measured baseline exists for model-routing quality because there was no
  registry to compare against. 2.4B starts that measurement; it does not inherit
  one.

## 8. Reproduction

```bash
# baseline, in a clean worktree at 3ec1efc
python benchmarks/run_benchmarks.py

# candidate, with the new workload suite
python scripts/evaluate-intelligence.py \
  --baseline-worktree <clean-2.4A-R-worktree>
```

The evaluation writes `validation/runs/2.4b/evaluation.json` with the workload
records, benchmark summary, baseline summary and context experiment. Run
records are local operator evidence and are gitignored; the case definitions
and this document are tracked.
