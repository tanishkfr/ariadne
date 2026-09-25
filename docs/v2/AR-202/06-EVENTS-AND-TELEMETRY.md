# AR-202 — Events and telemetry

Module: `src/ariadne_engine/events.py` · Projection: `scripts/ariadne.py` (`project_engine_event`)
Tests: `scripts/test-engine-core.py` (`event_checks`)

## 1. The canonical log

`<run_root>/engine-events.jsonl` — one JSON object per line, append-only.

```json
{
  "schema_version": 1,
  "event_id": "evt_20260922T203315Z_5c1a77e0",
  "type": "route_selected",
  "recorded_at": "2026-09-22T20:33:15+00:00",
  "seq": 12,
  "previous_digest": "…",
  "digest": "…",
  "run_id": "typographic-experiment",
  "task_id": "typographic-experiment-S4B",
  "stage": "S4B",
  "execution": "exe_…",
  "revision": "…",
  "actor": "",
  "data": {"status": "selected", "rule": "declared-default", "reason": "…", "worker_role": "bulk", "requested_provider": "Cursor"}
}
```

* `seq` is monotonic; `digest = sha256(previous_digest + canonical(event))`.
  `events.integrity_problems()` verifies the chain and reports breaks,
  duplicates or gaps. It never repairs: a broken chain is a finding.
* An event type outside `EVENT_TYPES` is refused, so the vocabulary cannot drift.
* `events.read(limit=…)` returns events oldest-first; `events.summarise()`
  returns counts, the last type and the integrity result.

## 2. Vocabulary

`task_characterized`, `context_decided`, `context_cache_hit`,
`context_invalidated`, `route_selected`, `execution_created`,
`execution_started`, `execution_observed`, `execution_completed`,
`execution_failed`, `fallback_selected`, `recovery_proposed`,
`recovery_applied`, `approval_recorded`, `approval_consumed`,
`validation_recorded`, `review_recorded`, `failure_classified`.

Every event type the milestone brief named exists; `approval_recorded` and
`failure_classified` were added so approvals and classified failures have a
first-class record instead of being smuggled into another type.

## 3. Compatibility projections

| Surface | Status | Mapping |
|---|---|---|
| `worker-telemetry.jsonl` | unchanged schema, one row per engine event | `project_engine_event` writes `event: "engine:<type>"` with the AR-201 defaults (`usage`/`cost` = `unknown`), the task/role/provider/model it can derive from the payload, and an added `execution` field. The existing `worker-prepared`, `worker-run` and `worker-validation` rows are still written where they were |
| `OPERATIONS.md` | unchanged human log | the runtime's `append_log` calls are unchanged; recovery application adds one human log entry |
| stdout / pause messages | unchanged shape | routing and evidence pauses print `Paused: <reason>` |
| `ariadne-run.json` | new collections, same file and schema | `executions`, `failures`, `characterisations`, `routing_decisions`, `context_decisions`, `recoveries`; `engine.adaptive_contract`/`adaptive_schema` markers |

The projection is called defensively: a projector failure never breaks the
engine path. The log is the source of truth; the projections are views.

## 4. What an event is not

An event records that the engine *decided* or *observed* something. It is not
authorization: no event grants a gate, satisfies a review, or authorizes a
transition. It is not evidence by itself either — it carries the execution id,
decision id and revision needed to find the record that is. Recovery, routing,
approvals and reviews all re-check their own preconditions from the records, not
from the log.

## 5. Operator surface

```
ariadne.py engine-events --run-root <run> [--limit 50] [--json]
ariadne.py execution-status --run-root <run> [--json]     # executions, last characterisation/route/context, failures, events summary
```

`execution-status --json` embeds `events: {path, events, types, last,
integrity_problems}`, so a single command answers "what actually happened".
