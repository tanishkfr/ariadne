# AR-205 — 04 — Versioned consumer integration contract

## Shape

```
consumer application
        |
        v
ConsumerAdapter          (ariadne_engine.integration)
        |
        v
EngineClient / public API (ariadne_engine.public)
        |
        v
transition authority      (the engine; unchanged)
```

The adapter is shipped on the Ariadne side only. It owns no state, writes
nothing itself, and imports no consumer, editor, network or paid provider code.

## Versions and negotiation

| Field | Value |
|---|---|
| Protocol name | `ariadne-consumer` |
| Protocol version | `1` (supported range `1..1`) |
| Envelope schema | `1` |
| Engine contract | `ariadne-engine-1` |
| Run-state file schema | `1` |
| Record schema | `2` |

A consumer calls `describe()` and `negotiate(request)` before any operation.
`negotiate` refuses when the protocol version is outside the supported range or
when a required capability is not advertised, and reports unknown request fields
in `ignored_fields`. Unknown fields are never interpreted as permission; the
fixtures include `grant_approval` and `trust_me` to prove it.

Capabilities advertised: `lifecycle`, `approval`, `verification`, `decision`,
`capability-evidence`, `execution-identity`, `events`, `economics`,
`design-evidence`, `recovery`, `migration`.

## Operations

| Operation | Engine call | Notes |
|---|---|---|
| `describe` | contract description | safe before negotiation |
| `open_project` | `status` | reports absence explicitly |
| `start_task` | `start_run` | request or request file |
| `inspect_task` | `status(as_json)` | parsed state in `data.state` |
| `approve` | `approve_gate` | engine binds gate, revision and identity |
| `execute` | `prepare_next` | prepares the next boundary; does not run a model |
| `validate` | `validate_worker` | refuses without worker evidence |
| `review` | `ingest_review` | independence enforced by the engine |
| `recover` | `recovery_report` / `apply_recovery` | explicit action required to apply |
| `inspect_capabilities` | `inspect_capabilities` | registry, evidence levels |
| `get_events` | `engine_events` | append-only log with integrity problems |
| `get_evidence` | status + verification + capabilities | one assembled view |
| `inspect_migration` | `plan_migration` | dry run through the contract |
| `apply_migration` | `apply_migration` | explicit, backup first |

There is deliberately **no operation that records verification**. A consumer
cannot mint a validation, a review or an approval; it can only ask the engine to
perform the operation under the engine's own rules.

## Envelope

```json
{
  "schema_version": 1,
  "protocol_version": 1,
  "operation": "inspect_task",
  "consumer": "example/1",
  "status": "ok | refused | needs-human | unknown",
  "message": "the operator text the engine produced",
  "data": { "...": "operation-specific" },
  "problems": [],
  "authority": "engine"
}
```

`status` is derived from the engine exit code (`0`, `1`, `2`); `authority` is a
constant. A consumer that reads `data` as permission rather than as a report has
misread the contract.

## Verification status

Contract fixtures in `integration.CONTRACT_FIXTURES` and the release tests cover:
happy path, unsupported protocol version, missing required capability, absent
optional capability, unknown fields, unsupported operation, approval without a
gate/with an approving extra field, validation without evidence, event replay,
and the migration boundary.

Status: **CONTRACT_VERIFIED** — the Ariadne side behaves as documented against
deterministic fixtures. **Not BOREAL_LIVE_VERIFIED**: no consumer application was
executed in this milestone (see [05-BOREAL-COMPATIBILITY.md](05-BOREAL-COMPATIBILITY.md)).
