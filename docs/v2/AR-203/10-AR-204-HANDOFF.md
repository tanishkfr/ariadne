# AR-203 — AR-204 Handoff

**Milestone for AR-204: Harness Economics & Execution Efficiency.**

Base for AR-204: the AR-203 closure commit (recorded in `09-AR-203-REPORT.md`),
branch `v2/ar-203-verification-hardening`. Recommended worktree:
`<path>`, created from the AR-203 closure commit.
AR-203 must not be modified by AR-204 except to fix a defect AR-204 proves.

AR-203 deliberately measured and did **not** optimise. AR-204 should measure
before optimising, and every optimisation must keep the AR-203 verification
protections intact: a cheaper harness that cannot prove what ran is a regression,
not an improvement.

## 1. What AR-203 already provides

| Thing | Where | State |
|---|---|---|
| Measured usage fields on executions | `execution.record_usage`, `USAGE_FIELDS` | seam implemented, unpopulated (no paid provider called) |
| Context-composition buckets | `execution.CONTEXT_COMPOSITION_BUCKETS` | recorded when the runtime already knows them |
| Usage view / totals | `execution.usage_view`, `telemetry_summary` | implemented |
| Provenance and identity levels | `provenance.py` | implemented and enforced |
| Capability registry | `capabilities.py` | implemented; offline probes only |
| Verification records and freshness | `verification.py` | implemented |
| Decision batches and usage passthrough | `decisions/batch.py` (`usage` on batch and decision records) | implemented |
| Benchmark measurement boundaries | `benchmarks/run_benchmarks.py` result document | `model_calls: 0`, token usage `UNKNOWN` — keep this honest |

The benchmark result document already separates deterministic measurements from
model-backed ones. AR-204 must preserve that separation: an optimisation may not
be reported as a win on a metric that was never measured.

## 2. Required investigation list

1. **Cost per verified completed task.** Define the unit: a task that reached a
   verified completion (AR-203 verification record at `VERIFIED` for the task's
   acceptance evidence) divided by the measured provider cost of everything spent
   on it, including failed and abandoned attempts. Report the denominator honestly.
2. **Context cost by source.** Use `CONTEXT_COMPOSITION_BUCKETS` and the AR-202
   adaptive-context decisions (`context_decisions`, `context.summarise`) to
   attribute input tokens to static/system, tool schemas, project context,
   retrieved source, evidence, history and summaries.
3. **Static vs volatile context.** Which parts of the prompt change per turn and
   which do not. This determines what can be cached at all.
4. **Prompt-cache structure.** Order context so the stable prefix is maximal;
   measure `cached_input_tokens`/`uncached_input_tokens` before and after.
   Requires a provider that reports cache fields — record `UNKNOWN` if it does not.
5. **Tool-schema cost.** Tokens spent on tool definitions per turn; whether
   schemas can be loaded per stage rather than per session.
6. **Dynamic capability packs.** Load only the capability documentation a stage
   needs; use the AR-203 capability registry to decide what is even available.
7. **Large tool-output externalisation.** Store big tool outputs as artifacts and
   pass a reference plus digest; keep the AR-203 rule that an artifact must be
   re-hashable (a reference without a readable artifact is not evidence).
8. **Context reuse and caching.** The AR-202 context cache exists; measure hit
   rates and their effect on input tokens, not only on latency.
9. **Duplicate context.** Detect the same source delivered twice under different
   names.
10. **Turns per task.** Measured turns (provider turns and engine steps) per task
    and per stage, split by success and failure.
11. **Worker/subagent cost share.** Attribute usage to the execution that caused
    it, using AR-203 provenance (`parent_execution`, roles).
12. **Routing economics.** Cost of the chosen route versus the cheapest route that
    would have satisfied the AR-203 capability policy; do not weaken the policy to
    win the comparison.
13. **Task-level provider usage.** Per-task totals from execution usage records.
14. **Deterministic serialization.** Stable ordering and formatting of context and
    tool payloads so cache prefixes and digests are stable.
15. **Compaction.** Summarising history and evidence; measure what is lost and
    record the loss as a limitation (a summary is not the artifact).
16. **Tool-error cost.** Tokens spent on failed tool calls and retries.
17. **Decision-batching economics.** Cost of one batch of independent questions
    versus one call per question, using the `usage` field AR-203 already records
    on batches and decisions.

## 3. Constraints carried forward

* No paid provider is required to complete AR-204 either; if a real provider is
  used it must be explicitly authorised and its usage recorded as measured.
* The verification plane must keep working: usage recording stays measured-only;
  no optimisation may make `record_usage` accept estimates, and no caching may
  bypass `provenance.require_engine_execution`.
* Boreal is still out of scope (AR-205).
* No new third-party dependency without an ADR.
* Every optimisation needs a before/after measurement with the same benchmark
  label discipline AR-200 established, and a statement of what it costs in
  verification strength (ideally nothing).

## 4. Suggested first steps

1. Read `docs/v2/AR-203/07-ECONOMICS-TELEMETRY.md` and
   `docs/v2/AR-202/03-ADAPTIVE-CONTEXT.md`.
2. Pick one measured provider (or a deterministic harness that reports synthetic
   usage into the AR-203 seam) and produce the first honest cost-per-verified-task
   number.
3. Build the context-composition attribution from the existing context decisions
   before changing any prompt structure.
4. Add benchmark cases that fail if an optimisation reduces verification strength
   (for example: a cached context that skips a required source must still be
   refused).

## 5. Open limitations AR-204 inherits

* No live provider usage was measured in AR-203; the fields are unpopulated.
* `context_composition` is recorded only when the runtime already computes it.
* Capability evidence for external services is `DECLARED`/`UNKNOWN`; AR-204 may
  add `AVAILABLE` evidence through an authorised, measured probe, but must not
  make a paid call merely to turn a status green.
* The run-state writer remains the trust boundary for execution provenance
  (`docs/v2/AR-203/02-EXECUTION-PROVENANCE.md` §3).
