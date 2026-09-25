# AR-202 — Implementation

Milestone: AR-202 (adaptive execution)
Baseline: AR-201 `v2/ar-201-core` @ `8844b1a`
Branch: `v2/ar-202-adaptive-execution`
Worktree: `<path>`

This document says what was implemented and where. Behaviour is specified in
`02`–`06`; results are in `07`–`08`.

## 1. New engine modules (`src/ariadne_engine/`)

| File | Responsibility |
|---|---|
| `execution.py` | Execution identity records, lifecycle, result/review verification, the failure taxonomy and failure records |
| `routing.py` | Deterministic task characterisation and the executed routing decision |
| `context.py` | Context decisions, the transport-facing plan, the conservative context cache |
| `recovery.py` | Divergence detection, safe recovery proposals, explicit application |
| `events.py` | The canonical append-only engine event log, its integrity chain, and the projection hook |

`src/ariadne_engine/__init__.py` exports them; `contracts.py` gains the adaptive
record family (`SCHEMA_ADAPTIVE = 1`, `POLICY_VERSION`, vocabularies and
per-family validators) and `persistence.py` normalises the six new state
collections (`executions`, `failures`, `characterisations`,
`routing_decisions`, `context_decisions`, `recoveries`).

## 2. Changed engine modules

| File | Change |
|---|---|
| `contracts.py` | Adaptive record schemas, ids, validators; review records now require the execution binding |
| `persistence.py` | Adaptive state collections; `recovery_report` also scans the real packet location and skips in-flight executions |
| `policy.py` | `declared_dependencies`, `evidence_requirements` / `evidence_requirement_problems` / stale detection, wired into `continuation_problems` for `S4B` and `S5` |
| `review.py` | `independence_problems(..., reviewer_execution, implementing_execution)`, execution binding in `build_record`, legacy-unbound record replacement in `store` |
| `api.py` | `execution_status`, `engine_events`, `propose_recovery`, `apply_recovery`, `characterize_task`, `decide_context`, `select_route`, `create_execution`, `observe_execution`, `record_failure`, `execution_report` |

No AR-201 module was removed or renamed; no published entry point changed
signature.

## 3. Runtime (`scripts/ariadne.py`)

* `prepare_next` now: characterises the boundary, executes and records a routing
  decision, computes a context decision and passes the plan to the transport,
  reconciles the decision with the prepared manifest, updates the cache, creates
  the boundary's execution identity, and emits the corresponding events. A
  boundary with no authorized route or with insufficient continuation evidence
  pauses through `pause_continuation` **before** a packet directory is created.
* `ingest_return` resolves/verifies the implementer execution before writing
  anything, records the worker's runtime claim as *reported* identity, applies
  the mismatch policy, writes the machine record with the identity block, and
  completes the execution.
* `validate_worker` creates a fresh `validator` execution per attempt whose
  parent is the implementation it validated, classifies and records a failure on
  a non-passing result, and emits `execution_*` / `validation_recorded` events.
* `ingest_review` resolves the implementing execution (worker row, else the last
  S4B packet), refuses a review bound to a non-reviewer execution, creates a
  reviewer execution, binds both ids into the review record, and completes it.
* `record_result` binds every same-session stage result to a `reasoner`
  execution. `record_acceptance` emits `approval_consumed` when a G3 approval is
  really consumed and records a rejection as a human note that consumes nothing.
  `approve_gate` emits `approval_recorded`.
* New commands: `execution-status`, `engine-events`, `recover`; new optional
  flags `--execution` on `ingest-return` and `ingest-review`.
* `EVENTS.bind_projector(project_engine_event)` mirrors every canonical event
  into the AR-201 telemetry row schema.

## 4. Transport (`scripts/prepare-stage.py`)

* `plan_sources(stage, project, args)` — the candidate list with buckets,
  required/removable flags, existence (declared deliverability, not raw file
  presence) and the reason a conditional candidate would not be delivered.
* `resolve_sources(..., context_plan=None)` — materialises exactly those
  candidates under the plan: it may omit only removable candidates (refusing a
  required omission with `PacketError`), may reuse recorded hashes for an
  included source, and suppresses byte-identical duplicate deliveries as
  `SUPERSEDED`.
* `source_entry(..., reuse, context_reason, duplicate_of)` — recorded hash reuse
  is observable (`hashed_from: cache`), and every delivered source carries its
  reason.
* `prepare(args, context_plan=None)` — records the applied plan in the manifest
  as `context_decision`. Without a plan the output is byte-identical to AR-201.
* `RUNTIME_EVIDENCE_PATTERNS` — Ariadne's own ledgers are in-contract during
  worker validation, since the runtime's `record-creative` /
  `record-operations` commands write them.

## 5. Tests and benchmarks

* `scripts/test-engine-core.py` — extended from 96 to 145 deterministic checks:
  execution identity, failure taxonomy, routing, context decisions and cache,
  recovery, events, continuation evidence, and the new review binding.
* `benchmarks/arbench/adaptive_cases.py` — 24 new AR-202 cases in five groups
  (`adaptive-context`, `routing`, `execution-identity`, `recovery`,
  `evidence-continuation`), registered through `benchmarks/arbench/__init__.py`.
* `benchmarks/arbench/fixtures.py` — `record_skill_evidence`,
  `record_implementation_evidence`; the shared S4A/S5 helpers now record the
  continuation evidence a live session records.
* `scripts/ariadne.py --self-test` — the fixture records the S4A planning
  evidence, the S4B QA evidence and the implementation trace (still 125/125).

## 6. Documentation

`docs/v2/AR-202/` (this document set) and six ADRs in
`docs/v2/AR-202/adr/`: ADR-0210 execution identity, ADR-0211 adaptive context,
ADR-0212 executable routing, ADR-0213 failure taxonomy and recovery,
ADR-0214 canonical events, ADR-0215 continuation evidence and approval policy.

## 7. What was explicitly not built

No multi-agent swarm, scheduler, control plane, vector store, browser
automation, OS sandbox, GUI, cloud service, design-intelligence feature, Boreal
change, dependency addition, provider call, or product-version bump. Recovery
resolves four interruption shapes and refuses the rest; routing never invents
capability evidence; context never adds a source.
