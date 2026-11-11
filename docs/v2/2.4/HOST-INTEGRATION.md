# Host Integration Contract — Ariadne 2.4C

**Contract:** `ariadne-host-1`  
**Protocol:** `ariadne-consumer` version 2 (version 1 still accepted)  
**Authority:** none. Every response is read-only.

A host (desktop app, editor, service) may display Ariadne's state and ask the
engine to perform work. It must not duplicate workflow, validation, review,
proof, recovery or authorization. This document is the provider-neutral
contract for that boundary.

## 1. Ownership

| Ariadne owns | The host owns |
|---|---|
| workflow decisions | user interface |
| task and attempt records | session navigation |
| model/skill recommendations | user-facing notifications |
| evidence | host permissions |
| validation | host-specific computer/browser interaction |
| review | its own application state |
| proof | transport to the user |
| recovery state | |
| human-gate requirements | |

Neither system silently grants the other's permissions.

## 2. Interfaces

The same derivation is exposed through four doors:

```bash
python scripts/ariadne.py host-status --run-root <run> --json
python scripts/ariadne.py host-events --run-root <run> --cursor '<json>' --json
```

```python
from ariadne_engine import api
api.host_status(run_root=...)
api.host_events(run_root=..., cursor=..., limit=100)
api.host_status_state(state)
api.host_events_state(state, cursor=..., limit=100)
```

```python
from ariadne_engine import mcp
mcp.dispatch(state, tool="host_status", params={})
mcp.dispatch(state, tool="host_events", params={"cursor": ..., "limit": 100})
```

```python
from ariadne_engine import integration
adapter = integration.ConsumerAdapter(client, consumer="my-host/1",
                                     required_capabilities=["host-contract", "events-cursor"])
adapter.call("host_status", {"run_root": ...})
adapter.call("host_events", {"run_root": ..., "cursor": ...})
```

All four derive from the same durable state and the runtime's one
`task_report`/host projection. There is no second state store.

## 3. Status fields

`host-status` returns:

| Block | Fields |
|---|---|
| task | task/run id, objective, lifecycle state, stage, active attempt, repository revision, revision drift, attempts |
| execution | selected adapter, observed provider/model with evidence level, routing explanation, active operation, progress/open executions/unmet skills |
| verification | last validation and freshness, review id/outcome/findings/blockers, proof id/state/receipt digest, creative review binding, unresolved blockers, rendered status |
| recovery | interrupted operation, safe continuation, required human action, last durable operation |
| authority | pending gate (`G3` or `TASK_ACCEPTANCE`), gate subject id/digest, decision required/recorded, permitted action boundary, `authority_effect=none` |
| resources | measured usage, explicit unknowns, efficiency profile, skill telemetry |
| events | current cursor, log integrity, polling instructions |
| limits | read-only, no internal paths by default, no secrets, observation time |

The projection does not expose absolute artifact paths by default. A host that
needs a rendered artifact asks its own engine-side adapter; it is not handed a
filesystem path.

## 4. Events and cursor

The existing append-only log (`engine-events.jsonl`) is the event source. Each
event has a stable `event_id`, a monotonic `seq`, a `previous_digest` and a
`digest`.

A page returns:

```json
{
  "status": "OK",
  "events": [...],
  "cursor": {"seq": 9, "event_id": "evt_...", "digest": "..."},
  "next_cursor": {"seq": 14, "event_id": "evt_...", "digest": "..."},
  "has_more": false,
  "integrity_problems": []
}
```

Rules:

- a cursor is the last event the host processed;
- the next page returns only events with a greater `seq`;
- an unknown, out-of-range or digest-mismatched cursor returns
  `CURSOR_INVALID` with **no events** — it is never treated as "start over";
- a host restart resumes from its persisted cursor and must not see the same
  logical transition twice;
- `integrity_problems` is a finding, never silently repaired;
- delivery is polling; no daemon or message broker is introduced.

## 5. Authority

- The host surface is read-only: `read_only=true`,
  `authority_effect="none"`.
- It cannot approve a gate, record a review, validate work, accept a task or mint
  a proof.
- A host that needs a write operation must call the existing authorized engine
  entry point (`approve_gate`, `task_accept`, `record_acceptance`, ...), where the
  engine's own identity and gate checks still apply.
- `approve` in the protocol-2 consumer adapter is a compatibility transport onto
  the same `approve_gate` engine entry point, not a host-side authority. It is
  not part of `host-status`/`host-events`.

## 6. External consumer fixture

`tests/fixtures/external-host-consumer/consumer.py` is outside the engine
package and imports no `ariadne_engine` module. It:

1. discovers/open a task through `host-status`;
2. reads task state, execution identity, validation, review and proof;
3. reads an event page;
4. detects the pending human gate;
5. persists its cursor and resumes after a simulated restart;
6. refuses a malformed/stale cursor;
7. asserts the read-only/authority boundary.

`scripts/test-ar24c.py` runs it twice against a real disposable run and asserts
no duplicate event ids and a `CURSOR_INVALID` refusal.

This fixture proves the contract is consumable. **Juno is not integrated** until
Juno actually consumes it.

## 7. Compatibility

- Protocol 1 requests remain accepted (`min_supported=1`).
- Protocol 2 adds `host_status`, `host_events`, `host-contract` and
  `events-cursor`; a protocol-1 client sees none of them and no weaker authority
  boundary.
- The envelope schema remains version 1; the new operations do not change the
  envelope shape.
- The host schema is versioned as `ariadne-host-1`; a future additive field keeps
  the version until a breaking change.

## 8. Degree of integration

| Item | Status |
|---|---|
| Ariadne host contract | implemented, tested |
| CLI/API/MCP parity | tested |
| External consumer fixture | implemented, tested across restart |
| Juno consumption | **not claimed** |
| Desktop UI | not built (outside this milestone) |
| Remote transport/auth | not provided; the host owns its transport |

## 9. Evidence

- `src/ariadne_engine/host.py`
- `src/ariadne_engine/api.py` (`host_status`, `host_events`, state helpers)
- `src/ariadne_engine/mcp.py` (`host_status`, `host_events`)
- `src/ariadne_engine/integration.py` (protocol 2)
- `scripts/ariadne.py` (`host-status`, `host-events`)
- `tests/fixtures/external-host-consumer/consumer.py`
- `scripts/test-ar24c.py`
