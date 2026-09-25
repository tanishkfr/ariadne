# AR-200 / 03 — ARCHITECTURE

Principle: **the smallest structure that makes the proven defects impossible, reuses what exists, and adds no infrastructure without a demonstrated need.**

The baseline does not need a message broker, a database, microservices or a distributed scheduler. The v1.6.7 runtime is 5 modules and zero dependencies, and its measured weaknesses are *policy placement* and *evidence binding*, not throughput. v2 therefore changes boundaries, not technology.

## 1. Module map and ownership

Proposed package: `src/ariadne_engine/` (import package) with the existing runtime preserved in place. Nothing is renamed or moved in AR-200; the package below is the AR-201 target, built by moving *existing* functions behind clean seams.

```
src/ariadne_engine/
  contracts.py      Core record types + schema versions + validation.        OWNER: core
  statemachine.py   Stage/worker/run states, transition table, single choke point.  OWNER: core
  policy.py         Authorization, gates, scope, repair budget, forbidden actions.  OWNER: core
  events.py         Append-only event records + readers.                     OWNER: core
  context.py        Stage spec, conditional resolution, packet build/verify.  OWNER: execution
  routing.py        Capability classification, provider/native selection, identity check. OWNER: execution
  worker.py         Worker protocol (start/collect/cancel), claims, coordination.  OWNER: execution
  recovery.py       Interrupted-work resolution, journal replay, state repair. OWNER: execution
  validation.py     Command execution, scope/fingerprint checks, outcome classify. OWNER: evidence
  review.py         Review request build, ingestion, independence binding.    OWNER: evidence
  provenance.py     Evidence records, hashing, revision binding.              OWNER: evidence
  design/           reference adapters, component registry, direction, rendered QA, critique. OWNER: design
  workspace.py      Revisions, transactions, journal, rollback, conflicts.    OWNER: workspace
  adapters/         Runtime adapter protocols (human CLI, opencode-style, fixture). OWNER: integration
  api.py            Python API (thin, typed, side-effect-explicit).           OWNER: integration
  cli.py            Operator CLI (existing commands, same exit codes).        OWNER: integration
  persistence.py    Versioned stores, schema negotiation, migration hooks.    OWNER: persistence
```

Mapping to what already exists (no rewrite required for these):

| v2 module | Existing source of truth |
|---|---|
| `statemachine.py` | `ariadne.py:3481-3536` (`infer_next_stage`), `advance`/`prepare_next` guards; Boreal `model.py:59-69`, `engine.py:321-335` for the single choke point |
| `policy.py` | `ariadne.py:2695-2852` (review/acceptance), `905-915` + `3363-3365` (gate parsing → to be replaced), `prepare-stage.py:336-431` (worker contract), `worker_outcome` `ariadne.py:203-247` |
| `context.py` | `prepare-stage.py` in full (stage table, `resolve_sources`, `build_packet`, `verify_packet`, `load_parent`, isolation checks) |
| `validation.py` | `ariadne.py:2415-2665`; Boreal `validator.py` for the fingerprint model |
| `provenance.py` | the hashing/anchoring discipline already in `creative-intelligence.py:123-156`, `creative-operations.py:128-155` |
| `design/*` | `creative-intelligence.py`, `creative-operations.py` (KEEP), Boreal `references.py` (EXTRACT), plus new rendered-QA instrument (ADD) |
| `workspace.py` | Boreal `transactions.py` (EXTRACT, adaptation required) |
| `persistence.py` | `ariadne.py:261-271` + `prepare-stage.py:1657-1810` verified today; add schema negotiation |

## 2. Core contracts

Records are immutable value objects serialised to JSON with an explicit `schema_version`. Field names below are the *planned* contract; where a field already exists in v1.6.7 it is marked ✓.

```python
class RunState(Record):            # ariadne-run.json  (currently schema_version=1)
    schema_version: int            # ✓
    run_id: str                    # ✓
    project: str                   # ✓  absolute path
    request: str                   # ✓
    readable_schemas: tuple[int,...]   # + NEW: schemas this runtime can read (default (1,2))
    packets: list[PacketRef]       # ✓  {id, stage, path, reasoner_output_baseline}
    worker: WorkerState | None     # ✓
    provider_preflight: dict | None# ✓
    reasoner: dict                 # ✓
    reasoner_history: list[dict]   # ✓
    human_interventions: list[Intervention]  # ✓
    approvals: list[Approval]      # + NEW (see §4)
    notes: list[dict]              # ✓
    events_seq: int                # + NEW: monotonic counter for the event log
    next: str                      # ✓

class Packet(Record):              # manifest.json  (currently SCHEMA_VERSION=1)
    schema_version, packet_id, stage, project, provider
    sources: list[SourceRef]       # {label, path, kind, source_sha256, content_sha256, delivered, delivered_content_sha256}
    omitted_conditionals: list[str]
    forbidden_inputs: list[str]
    parent_id, parent_evidence_kind, parent_evidence_sha256, parent_manifest_sha256
    worker: WorkerContract | None  # {task_id, role, attempt, repair_limit, contract_sha256}
    project_baseline: RepoSnapshot | None
    return_target: str | None
    packet_sha256

class Evidence(Record):
    evidence_id, kind, run_id, packet_id, revision, artifact{path,sha256} | None,
    payload: dict, source: str, identity: str, recorded_at

class Approval(Record):            # NEW (adopted from Boreal's model, simplified)
    approval_id, gate: str,                 # "G1" | "G2" | "G3" | "G4" | "G5"
    subject: {type, id, revision_hash},     # binds to the fingerprint of what was approved
    identity: str,                          # who/what recorded it ("human-cli", "operator:<name>")
    channel: str,                           # "human-cli" is the only channel that can satisfy a gate
    note: str, recorded_at
```

`Approval` replaces the current practice of reading `**Last gate passed:** G1` out of `AGENTS.md`. The document field may remain as a *human-readable mirror*, but it must never be the enforcement input. Invariant I-3 (§6) makes that testable.

## 3. State machine

**Stages** (unchanged from v1.6.7, KEEP): `S1 → S2? → S3 → S4A → S4B → S5 → S6`, where S2 is conditional on blocking research questions (`infer_next_stage` already decides this from `PROJECT.md`).

**Worker lifecycle** (unchanged, KEEP — it is validated by 125 self-tests and the new lifecycle cases): `NOT_STARTED → IMPLEMENTED → (VALIDATED | FAILED | BLOCKED) → REVIEWED → (ACCEPTED | REJECTED)`, with `routine-repair` bounded to `MAX_ROUTINE_REPAIRS = 2` and `escalation-required` as the terminal non-accepting state.

**Enforcement rule (REDESIGN):** exactly one function may change a stage or lifecycle field — `apply_transition(state, event) -> state` — validating against a single declarative table. Every current call site (`advance`, `prepare_next`, `validate_worker`, `finish_worker_validation`, `ingest_review`, `record_acceptance`, `record_reasoner_failure`) routes through it. This is the Boreal pattern; it removes the four-way re-derivation that produced confirmed defect 2.

```
STAGE_TRANSITIONS = {
  ("S1","S2"), ("S1","S3"), ("S2","S3"), ("S3","S3-retry"), ("S3","S4A"),
  ("S4A","S4A-retry"), ("S4A","S4B"), ("S4B","S4B-retry"), ("S4B","S4B-escalate"),
  ("S4B","S5"), ("S5","S5-retry"), ("S5","S6"), ("S6", None),
}
```
A transition may be *proposed* by any command but is *permitted* only if its preconditions hold (evidence present, parent legal, gate satisfied, budget available). Preconditions are policy functions in `policy.py`, each returning a list of human-readable problems so refusals stay explainable.

## 4. Authorization, gates and identity

Three separate concerns, deliberately not conflated:

1. **Binding.** An approval binds to `revision_hash` of the subject (design thesis digest for G1; task/handoff digest for G2/G3). Any subsequent edit to the subject makes the approval `stale` and blocks the dependent transition. Adopt Boreal's `subject{type,id,revision,hash}` + liveness check.
2. **Identity.** Only `channel == "human-cli"` can satisfy a gate, and the approval record is written by an operator-run command (`ariadne gate approve --gate G1 --subject-hash <hash>`) that is **not** part of the worker's packet contract and is not documented as an agent action. Approvals are appended to an approve-only log (`approvals.jsonl`) in the run root with `identity` and `recorded_at`. This does not prove a human typed it; it does remove the current situation where the ordinary worker flow writes the approval field itself.
3. **Isolation.** Explicitly out of scope for v2: no job objects, containers, AppContainer or filesystem ACLs. Nothing in v2 may claim sandbox containment. Approval channels are *authorization*, not *containment* (see 07-RISKS).

Gate set (unchanged semantics): G1 direction lock, G2 dependency install, G3 review acceptance, G4 ship, G5 publish. G4/G5 remain human/operator actions outside the engine.

## 5. Execution

- **Strategy selection (ADD, small).** A deterministic selector maps (mode, stage, task signals) to a *strategy record*: worker role, repair limit, required checks, review requirement, whether a rendered-QA step is required, and which provider capability is required. It consumes `references/capabilities.json` for the *component* question and the reasoner capability matrix for the *provider* question, so dead data becomes load-bearing. No model is consulted.
- **Context compiler (KEEP + HARDEN).** Keep `resolve_sources` / `build_packet` / `verify_packet` semantics exactly: canonical inputs, conditional inputs with recorded omissions, hash-stamped sections, parent provenance, S5 isolation. Harden with (a) a content-addressed source digest cache so verification does not re-read every source on every command, (b) a delivered-content digest check already present but always exercised, (c) an operator-visible omission report.
- **Worker protocol (KEEP + EXTRACT).** Define `WorkerAdapter` as a protocol: `available() -> Capability`, `start(spec, workspace) -> Handle`, `collect(handle, timeout) -> Claim`, `cancel(handle)`, `identity() -> str`. The human CLI worker and the fixture worker implement it in AR-201; an opencode-style adapter is a later, opt-in implementation (Boreal's `agent/opencode.py` proves the shape but is app-coupled and 1 108 lines of protocol detail — do not port it wholesale).
- **Recovery (HARDEN, ADD).** `recovery.py` resolves: orphan packet (packet on disk not in `state.packets`), orphan state write (attempt during atomic replace), interrupted validation (evidence file written but lifecycle not advanced), and interrupted transaction (delegate to `workspace.recover`). Recovery never invents success: an unresolvable state is reported as `blocked` with the exact divergence.

## 6. Invariants (each must have a benchmark case)

| ID | Invariant | Enforced by | Case |
|---|---|---|---|
| I-1 | A packet is never consumed unless every delivered source hash matches and the packet hash matches | `context.verify_packet` | `security.packet-tamper-detected`, `lifecycle.stale-project-input-detected`, `context.delivered-source-hashes-match` |
| I-2 | S5 is prepared only from a *passed* independent validation + complete return | `prepare-stage.py:1330-1344` | `lifecycle.s5-isolation` |
| I-3 | A stage cannot advance past a gate without an `Approval` whose `subject.revision_hash` matches the current subject and whose channel is `human-cli` | `policy.gate_satisfied` | **new**: `security.gate-forgery-*` must pass in v2 (currently fails) |
| I-4 | Review independence is bound to evidence, not a text field | `review.independence_problems` | **new** positive + negative pair |
| I-5 | Routine repair never exceeds the declared budget; blocked returns never enter routine repair | `policy.repair_allowed` | `lifecycle.repair-budget-bounded`, `lifecycle.blocked-return-halts` |
| I-6 | Scope, immutability and sensitive-path rules are re-checked at validation *and* at apply time | `validation.scope_check`, `workspace.apply` | `security.out-of-scope-write-blocked`, `security.sensitive-path-write-blocked`, `security.handoff-immutability` |
| I-7 | Recorded evidence is never overwritten | evidence writers | `security.evidence-not-overwritable` |
| I-8 | Unknown provider usage/cost stays the literal `unknown` | telemetry writer | `lifecycle.telemetry-keeps-unknowns` |
| I-9 | Every continuation path applies the same preconditions (no path-dependent gates) | single transition choke point | **new**: `security.creative-gate-bypass` must pass in v2 (currently fails) |
| I-10 | State that cannot be read under the running schema is refused, never silently migrated | `persistence.load` | `lifecycle.state-schema-mismatch-refused` |
| I-11 | A transaction never applies over an unrecognized destination state and never destroys user edits on rollback | `workspace.apply/rollback` | **new** (ported from Boreal's transaction tests) |
| I-12 | No agent-authored document can satisfy an authorization gate | I-3 mechanism | `security.gate-forgery-in-agents-md` |

## 7. Persistence

- **Versioned schemas.** Every record carries `schema_version`. Readers declare `readable_schemas` and an ordered migration list. Migration is explicit, recorded in the event log, never destructive, and reversible by keeping the pre-migration file (`<name>.v<n>.bak`). This is the HARDEN path; AR-200 tests only the *refusal* behaviour, which already works.
- **Durable state.** Keep the temp-file + `replace_with_retry` pattern (Windows sharing-violation tolerant, already proven). Add the transaction journal from `workspace.py` for multi-file mutations so an interrupted apply is resolvable.
- **Layout.** Unchanged from v1.6.7 (`<project>/.ariadne/*`, sibling run root with `ariadne-run.json`, `packets/<id>/…`, `evidence/…`) plus `approvals.jsonl` and `events.jsonl` in the run root. Do not change existing paths in AR-201 — the compatibility surface is already public.
- **Locking.** Single-writer is currently an assumption in both systems. v2 should detect concurrent writers (state file mtime/sequence mismatch) and refuse with a typed error rather than corrupt. A real lock is DEFER until a multi-writer use case exists.

## 8. Integration boundaries

- **Python API (`ariadne.api`)** — thin functions over the CLI operations, all side-effect-explicit and returning result records rather than printing: `start_run`, `prepare_next`, `record_result`, `ingest_return`, `validate_worker`, `ingest_review`, `record_acceptance`, `status`, `route`, `gate_approve`, `transaction_*`. The CLI becomes a presentation layer over this API (same subcommands, same exit codes 0/1/2 — do not change them; they are asserted by existing tests and documentation).
- **Runtime adapter protocol** — `WorkerAdapter` (§5) plus a `RuntimeAdapter` for reasoner providers: `detect() -> Capability`, `invoke(packet) -> transcript|structured_result`, `identity()`. The existing `reasoners.py` already models detect/classify; extend rather than replace.
- **Boreal adapter (target, not built here)** — Boreal integrates by calling the Python API or the CLI in a subprocess, translating between *its* versioned records and Ariadne's. Rules: Ariadne's persistence is independent of Boreal's; neither imports the other's schema module; the contract is version-negotiated (`engine_contract` version in both directions); Boreal's coordinator remains the owner of UI state, permissions and its own transactions. Ariadne must be usable with Boreal absent.

## 9. Error semantics

| Class | Meaning | Exit | Mutation |
|---|---|---|---|
| `PolicyRefusal` | The state is legal but a precondition fails (gate missing, budget exhausted, evidence absent) | 2 | none |
| `ContractError` | The request or artifact is malformed (bad return handoff, bad packet, bad review block) | 1 | none |
| `StaleArtifact` | A hash/fingerprint no longer matches (packet, source, approval subject) | 1 | none |
| `ConflictError` | Destination state changed under an operation (repository conflict, transaction conflict) | 1 | preserves user data, records conflict |
| `EnvironmentError` | A required external tool/provider is unavailable | 1 | none created ("nothing was created" is stated today and must remain true) |
| `InternalError` | A bug; always reported, never swallowed | 70 | partial state left intact for `recover` |

Rule: no error is ever converted into `passed`/`VALIDATED`/`ACCEPTED`. Today's validator already honours this (`engine.py`-style fail-closed); the redesign must preserve it while adding the missing `recover` path.

## 10. Stability classification

**Stable (must not change without a major version):** on-disk paths (`<project>/.ariadne/…`, sibling run root, `ariadne-run.json`, `packets/*/{packet.txt,manifest.json}`, `worker-telemetry.jsonl`); CLI subcommand names and exit-code semantics; packet section header format (`===== BEGIN <label> | SOURCE <path> | SOURCE-SHA256 … =====`); manifest key names (`sources`, `omitted_conditionals`, `return_target`, `worker`, `project_baseline`); the S1–S6 stage names and G1–G5 gate names.

**Internal (may change freely):** module layout inside `src/ariadne_engine/`, dataclass field names not yet serialised, the transition-table representation, verification caching, the internal shape of `evidence`. 

**Provisional (do not promise stability):** the Python API signatures (`ariadne.api`), the `WorkerAdapter`/`RuntimeAdapter` protocols, the design subsystem's new records (reference provenance extension, rendered-QA artifacts), and any Boreal contract. Mark them provisional until AR-203 compatibility tests exist.
