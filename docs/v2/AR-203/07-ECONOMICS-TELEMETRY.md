# AR-203 — Economics Telemetry

AR-204 owns harness economics and performance. AR-203 owns making sure the raw
measurements **exist** and are honest. Nothing in this milestone optimises cost,
and no figure below is estimated: a field that was not supplied stays `null`/
absent, and a value that was supplied is recorded with the observer that measured
it.

## 1. What is recorded

`execution.record_usage(state, execution_id, source=..., **values)` writes
`usage` onto the execution record:

| Field | Meaning | When recorded |
|---|---|---|
| `input_tokens` | provider-reported input tokens | when the adapter/runtime measures them |
| `output_tokens` | provider-reported output tokens | same |
| `cached_input_tokens` | tokens served from a provider cache | same |
| `uncached_input_tokens` | tokens billed outside the cache | same |
| `reasoning_tokens` | reasoning tokens, where the provider exposes them | same |
| `turns` | provider turns consumed | same |
| `tool_calls` | tool calls made | same |
| `tool_errors` | tool calls that failed | same |
| `duration_seconds` | measured execution duration | same |
| `provider`, `model`, `model_version`, `request_id` | the identity the usage belongs to | same |
| `context_composition` | per-bucket context size, when already known | same |

Context buckets (`execution.CONTEXT_COMPOSITION_BUCKETS`): `static_system`,
`tool_schemas`, `project_context`, `retrieved_source`, `evidence`, `history`,
`summaries`.

Every record also stores `measured: true`, the `source` (the engine-side observer
that supplied the figures), and `recorded_at`.

## 2. What is refused

* `source` naming worker output (`worker`, `worker-output`, `handoff`,
  `self-reported`) — a worker's claim is not a measurement.
* negative values — refused, not clamped.
* non-numeric values — refused.
* undeclared field names — refused.
* unknown context buckets — refused.

## 3. What is never done

* No estimation. If a provider does not report cached tokens, `cached_input_tokens`
  is absent; it is never derived from `input_tokens`.
* No billing arithmetic. AR-203 does not multiply tokens by a price and does not
  present a cost figure; that is AR-204's job and needs a price source AR-203 does
  not have.
* No back-fill from a model name. A model identity never implies a context size or
  a token count.
* `execution.telemetry_summary(state)` totals only measured fields and states the
  number of executions that actually carried measurements; unknown fields stay
  unknown in the output.

## 4. Where usage comes from today

The runtime already records worker telemetry through its own ledger
(`append_worker_telemetry`, preserved unchanged). AR-203 adds the engine-level
seam so a provider adapter that *does* expose usage can bind it to the execution
that produced it, with the observer named. Because AR-203 calls no paid provider,
the fields remain unpopulated in this milestone's runs — `UNKNOWN`, honestly,
rather than a plausible-looking zero.

## 5. Read surfaces

* `execution.usage_view(state, execution_id)` — one execution's measured usage,
  with `unknown_fields` listed explicitly and the note *"only measured fields are
  recorded; absent fields are unknown, not zero"*.
* `execution.telemetry_summary(state)` — run-level totals over measured fields.
* `provenance.execution_provenance(state, id)["usage"]` — usage as part of the
  provenance view.
* CLI `provenance` (list form) prints the telemetry summary; `provenance
  --execution <id> --json` includes the usage view.

## 6. What AR-204 should measure next

The seam exists; the data does not yet, because no measured provider was called.
AR-204 should populate these fields from a real provider, then investigate cost
per verified completed task, context cost by source, static versus volatile
context, prompt-cache structure, tool-schema cost, dynamic capability packs,
large tool-output externalisation, context reuse, duplicate context, turns per
task, worker/subagent cost share, routing economics, task-level provider usage,
deterministic serialisation, compaction, tool-error cost and decision-batching
economics. AR-203 deliberately adds no optimisation that would distort those
measurements.
