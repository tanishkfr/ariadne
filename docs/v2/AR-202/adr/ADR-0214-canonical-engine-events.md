# ADR-0214 — One canonical event log, existing logs as projections

Status: accepted (AR-202)
Deciders: AR-202 implementation
Evidence: `src/ariadne_engine/events.py`, `06-EVENTS-AND-TELEMETRY.md`

## Context
AR-201 records state in `ariadne-run.json`, human history in `OPERATIONS.md`, and worker facts in `worker-telemetry.jsonl`. Each is a partial view; none is the structured record of *what the engine decided*. Rewriting all three would break consumers for no benefit and would put AR-201 surfaces at risk.

## Decision
Add one append-only, machine-readable log beside the run state: `<run_root>/engine-events.jsonl`.

- A fixed event vocabulary (characterisation, context decisions, cache hits/invalidations, route selection, execution create/start/observe/complete/fail, fallbacks, recovery, approvals, validation, review, failure classification).
- Each record carries `seq` and a `previous_digest` chain, so a truncated or rewritten log is *detected* by `integrity_problems()` and never repaired.
- An undocumented event type is refused, so the vocabulary cannot drift into ad-hoc names.
- The runtime binds a projector: every event also appends one row to the AR-201 `worker-telemetry.jsonl` with the row schema unchanged (the event name is namespaced `engine:<type>` and an `execution` field is added). `OPERATIONS.md` and the runtime's stdout/pause messages remain the human views.
- A projection failure can never break the engine path: the projector is called defensively.

## Alternatives considered
- **Writing JSON lines into `OPERATIONS.md`.** Rejected: that file is the human log, and a machine reader should not parse prose.
- **A separate log per concern (routing.jsonl, context.jsonl, …).** Rejected: correlation would require joining files, and the sequence chain would fragment.
- **Replacing telemetry.** Rejected: existing consumers (self-test, benchmark, operators) read it; it stays a projection.
- **Hash-chaining with signatures.** Rejected as false assurance (see ADR-0210); the digest chain gives tamper evidence, not authentication.

## Consequences
- `engine-events` prints the log with its integrity check; `execution-status --json` embeds the summary.
- Telemetry consumers see new event rows (namespaced) and one additional key; the AR-201 row contract is otherwise unchanged and still passes its own case.
- The event log is evidence of decisions, not authorization: it never grants a gate, a review or an approval.
