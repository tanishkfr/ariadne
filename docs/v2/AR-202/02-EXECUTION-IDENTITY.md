# AR-202 — Execution identity

Module: `src/ariadne_engine/execution.py` · Record family: `SCHEMA_ADAPTIVE = 1`
Tests: `scripts/test-engine-core.py` (`execution_checks`, `failure_checks`), benchmark group `execution-identity`

## 1. What an execution identity is

One record per boundary the engine prepares or ingests, created by the engine:

```json
{
  "schema_version": 1,
  "execution_id": "exe_20260922T203315Z_4f1c9ab2",
  "run_id": "typographic-experiment",
  "task_id": "typographic-experiment-S4B",
  "role": "implementer",
  "adapter": "scripts/prepare-stage.py:worker",
  "invocation": "prepare-next --stage S4B (attempt from ...-S4A)",
  "state": "STARTED",
  "created_at": "...", "started_at": "...", "observed_at": "", "completed_at": "", "failed_at": "",
  "nonce": "9f2c…",
  "parent_execution": "",
  "requested": {"provider": "Cursor", "model": "provider default - unverified", "effort": "", "worker_role": "bulk"},
  "reported":   {"provider": "Cursor", "model": "claude-sonnet-5", "trust": "worker-reported-unverified"},
  "observed":   {"provider": "UNKNOWN", "model": "UNKNOWN", "source": "unavailable"},
  "revision": {"project": "...", "baseline": "…head…", "packet_id": "...", "packet_sha256": "...", "revision_hash": "..."},
  "result": {"packet_id": "...", "status": "complete", "artifact": "...", "sha256": "..."},
  "failure": {},
  "provenance": {"created_by": "engine", "source": "runtime-boundary", "policy_version": "ar-202-policy-1", "reason": "..."}
}
```

Roles: `reasoner`, `implementer`, `validator`, `reviewer`.

## 2. Lifecycle

```
REQUESTED ─▶ CREATED ─▶ STARTED ─▶ OBSERVED ─▶ COMPLETED
                 │          │           │
                 └──────────┴───────────┴────▶ FAILED
UNKNOWN ──▶ FAILED
```

* `REQUESTED` exists for callers that only declare intent; the runtime goes
  straight to `CREATED → STARTED` at the boundary it prepared.
* `OBSERVED` means the **runtime** could report something about the execution.
  `observe()` refuses `source ∈ {"worker", "handoff", "self-reported", ""}`, so a
  worker statement can never be promoted to an observation.
* `COMPLETED`/`FAILED` are terminal; a finished execution cannot accept another
  result (replay refusal).
* Every transition is validated against the table and re-validated as a whole
  record, so a malformed identity cannot be written.

## 3. How identity is bound to work

| Binding | Mechanism |
|---|---|
| Identity is engine-created | `create()` has no `execution_id` parameter; ids are generated (`new_execution_id`) |
| Identity is revision-bound | `revision_hash` over project baseline head + packet id + packet digest; verified again when a result arrives |
| Results are bound | `ingest-return` resolves the execution *before* writing anything and refuses: unknown id, wrong role, wrong task, finished execution, different revision |
| Validation is bound | `validate-worker` creates a fresh `validator` execution per attempt, parented to the implementation it validated |
| Reviews are bound | `review-record.json` carries `execution_binding: engine`, `reviewer_execution`, `implementing_execution`; `contracts.review_problems` refuses a record without them, and refuses an identical pair |
| Legacy runs | an AR-201 packet has no execution; `ingest-return` adopts one, records `source: runtime-boundary` with an explicit adoption reason, and never claims it was prepared by AR-202 |

## 4. Requested vs reported vs observed

* **requested** — what the packet/preflight declared (`manifest.provider`, preflight model/effort, worker role).
* **reported** — what the worker wrote in its return handoff (`**Provider:**`, `**Model:**`). Stored as `trust: worker-reported-unverified`.
* **observed** — only an engine-side observer may write it. This runtime cannot observe provider/model, so it is `UNKNOWN` with `source: unavailable`, permanently.

An identity mismatch (requested vs reported) is **always recorded** and emits an
`execution_observed` event. It **refuses** (`PROVIDER_FAILURE`, no result
written) only when the run pinned a concrete model identity. A pin is a
*concrete* declared model: `declared_identity_pin` ignores placeholders
(`provider default - unverified`, `not specified`, `unknown`, `n/a`, `<…>`), and
prefers the handoff's declared routing over the preflight, so an honest run that
declared no model is never punished for reporting what it actually used.

## 5. Guarantees, and what is *not* authenticated

Verified by tests (engine-core + benchmark group `execution-identity`):

* a caller cannot choose an execution id (`forged-and-replayed-refused`);
* a duplicate/foreign/finished execution cannot accept a result;
* a result for another task or another revision is refused;
* a reviewer cannot bind the implementing execution
  (`review-binds-two-executions`, plus the engine-level check);
* a worker's runtime claim is never promoted to observed identity;
* a review record without the execution binding is refused.

**Not provided, and never claimed:** user authentication, cryptographic signing,
process isolation, OS sandboxing, transcript provenance, or any guarantee about
what a provider actually executed. Identity here means "the engine created this
id for this boundary, bound it to this revision, and accepted this result for it"
— nothing more.

## 6. Limitations

* The `adapter`/`invocation` strings describe the engine-side call site, not the
  external session. For an external worker they are descriptive provenance.
* Two executions created in the same second differ by the random suffix, not by
  time.
* An adopted execution (legacy packet) has an accurate creation time but no
  start time from before adoption; `started_at` equals the adoption time, and the
  provenance records that it was adopted.
* `reported` identity is prose and can be wrong; it is recorded, not trusted.
