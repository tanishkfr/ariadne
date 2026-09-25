# AR-204 — Report

Harness economics and execution efficiency. Closed on the AR-204 branch.

## 1. Question and answer

The milestone asked whether Ariadne can reach the same or better verified
completion for less unnecessary context, repeated work, tool overhead, model usage
and orchestration cost.

The answer this worktree can defend is narrow and measured. Ariadne now measures
the whole task instead of individual requests: every rendered byte is attributed to
a source bucket, the reusable share of a packet is 81.2% with the remainder
explained section by section, a task's cost includes its failed attempts, and the
primary metric is defined only for a task that actually reached a verified
completion. Two of the three levers with real savings in this repository — prompt
scaffolding and capability packs — are implemented behind flags and left off,
because no live model evaluation was run and the milestone forbids claiming parity
without one. The third — externalizing large tool output instead of discarding it —
is on by default because it removes no information.

## 2. What was built

| Area | Module | State |
| --- | --- | --- |
| deterministic serialization, prefixes, memo | `serialization.py` | default-on |
| task tree, cost, verified-completion metric, price profiles, cache telemetry, opportunity ranking | `economics.py` | default-on |
| request renderer, harness map, redaction | `harness.py` | inspection only |
| capability packs and schema economics | `tooling.py` | flag-gated |
| output externalization and retrieval | `artifacts.py` | default threshold |
| history economics and structured compaction | `history.py` | flag-gated |
| simple/standard/complex paths | `orchestration.py` | policy-derived |
| efficiency policy | `efficiency.py` | defaults in force |
| prompt audit and compact scaffolding | `prompting.py` | flag-gated |

Nine engine modules, four CLI commands (`economics`, `request-map`, `tool-packs`
and the efficiency settings on `economics`), fourteen API entry points, two
additive run-state collections and seven event types. No new dependency, no
provider call, no schema migration: the run-state file stays at schema 1.

## 3. What was measured

* Four real packets, 134,279 bytes, 27 sections, 81.2% reusable prefix.
* Source shares: project facts 35.7%, design context 23.5%, policy 14.3%, system
  26.5%.
* Declared tool surface: 2,896 bytes of always-loaded declaration against 107,777
  bytes that are deferrable.
* Compact prompt scaffolding removes 653 bytes, 0.49% of the rendered total.
* Two project ledgers, 22,251 bytes, are the entire explanation of the volatile
  share beyond the scaffolding.
* A large validation output of 61,779 bytes is now recoverable; before AR-204 the
  runtime kept a 64-character digest and nothing else.
* Local operations: `packet_map` 0.62 ms warm against 6.90 ms cold, and a memoised
  source hash 0.008 ms against 0.060 ms for the same work.

## 4. What was not measured, and will not be claimed

* No provider was called, so no token total exists per task and every monetary
  figure is `UNKNOWN`. A price-profile mechanism exists and its arithmetic is
  tested with synthetic prices; no real price is baked into the engine.
* No model-quality comparison exists for the prompt profile, the capability packs,
  the compaction strategy or the path planner. Each is recorded as `NOT_EXECUTED`.
* No subagent context-reduction measurement exists; the orchestration report says
  `UNKNOWN` for that question by name.
* No decision-batching cost comparison against a generative call exists.

## 5. Guardrails

The twelve new invariants are implemented as executable rules rather than prose:
cost cannot bypass authorization, context minimisation cannot remove required
evidence, offloading cannot hide a capability, cache reuse cannot satisfy stale
evidence, externalization cannot destroy output, compaction cannot erase
unresolved work, monetary cost cannot override capability, a fast path cannot skip
validation, unknown usage cannot become billing truth, deterministic tests cannot
stand in for model parity, volatile values cannot enter a cached prefix as stable,
and a supposedly parallel batch cannot carry an answer dependency. Ten mutations
target those rules and all ten are detected.

## 6. Honest limitations

Three findings are reported rather than fixed, and each has a reason:

* the packet's volatile values still precede its reusable content, because
  re-ordering what a worker reads is a behaviour change;
* the two timestamped project ledgers make 22 KB revision-volatile, because
  stripping per-entry timestamps from a delivered artifact would remove audit
  information;
* history compaction is implemented and measured but not enabled, because the
  behaviour question needs a live model.

## 7. Cost per verified completed task

That is the metric this milestone exists for, and the truthful current answer is
that it cannot be computed in this worktree: no provider was called, so no task has
a measured token total and no price profile is configured. What AR-204 delivers is
the machinery, the definitions and the guardrails that make the number computable
the moment an authorized run records usage — plus the accounting proof that it
counts failed attempts, review spend and validation spend rather than only the
successful call.

## 8. Git state

| Item | Value |
| --- | --- |
| Worktree | `<path>` |
| Branch | `v2/ar-204-harness-economics` |
| Base | `94b40f5d9f79ae24c4fd8033c64b301c59e7cbb8` (AR-203, frozen) |
| Closure commits | `7a4fc8a` implementation, `eda4c47` final evidence, then this report |
| Final HEAD | the commit that carries this line; read it with `git log -1 --format=%H` |
| Remote action | none: no push, tag, release or publication |
| AR-203 worktree | untouched at `94b40f5`, still on `v2/ar-203-verification-hardening`, clean |
| Boreal | not read, not modified, no state changed; the one work-in-progress deletion it carries predates this milestone |
