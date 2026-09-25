# AR-201 — 01 IMPLEMENTATION

What AR-201 built, which existing code it reused, and how the new core enforces the
existing Ariadne workflow. Paths are relative to the AR-201 worktree root
(`<path>`, branch `v2/ar-201-core`, base `921fd8f`).

## 1. Shape of the change

The engine is a new package, `src/ariadne_engine/`, loaded by the existing runtime from
the same checkout (no installation step, no new dependency, stdlib only):

```
src/ariadne_engine/
  __init__.py       package marker, version, submodule wiring
  contracts.py      versioned records: schema constants, Approval, Subject,
                    TransitionRequest, ReviewRecord, fingerprints, typed errors
  persistence.py    read/write/migrate run state; refusal policy; recovery report
  statemachine.py   the declarative transition tables and the single choke point
  policy.py         gate satisfaction, approval records, continuation preconditions,
                    repair budget, human-readable mirrors
  review.py         evidence-bound review records, independence, per-kind evidence
  api.py            narrow programmatic API (Result/format_result + operations)
```

`scripts/ariadne.py` keeps every command it had and delegates the protected parts:

| Existing code | Reused as |
|---|---|
| `scripts/prepare-stage.py` (transport) | unchanged; the engine delegates scope, worker-contract and validation-record checks to it (`policy._tool("transport")`, `policy.validation_problems`, `policy.retry_problems`) |
| `scripts/creative-intelligence.py` | unchanged; `policy.creative_evidence_problems` calls `load_ledger`/`project_problems` |
| `scripts/creative-operations.py` | unchanged; still owns the operations ledger |
| `scripts/reasoners.py` | unchanged |
| `ariadne.py:load_state/write_json` | replaced by `persistence.load_state` / `persistence.write_state` (atomic replace + engine marker) |
| `ariadne.py:worker_outcome` | classification moved to `statemachine.worker_transition_for`; the runtime function now delegates and keeps its public shape |
| `ariadne.py:design_thesis` | moved to `policy.design_thesis`; the runtime name delegates |
| `ariadne.py:replace_with_retry` behaviour | reimplemented once in `persistence.replace_with_retry` (temp file + retry), used for every state write |
| `scripts/build-release.py:RUNTIME_TREES` | `src/ariadne_engine` added so released runtimes ship the engine |
| `scripts/check.py`, `scripts/validate.py`, `scripts/*test*.py` | unchanged |

## 2. State machine

`statemachine.py` holds two declarative tables and one choke point.

`STAGE_TRANSITIONS` (from, to) covers start → S1, S1/S2/S3 with same-stage retries
(reasoner switch) and S1→S2, S1→S3, S2→S3, S3→S4A, S4A→S4B, S4B→S5, S5→S6, S6→done.
`WORKER_LIFECYCLE_TRANSITIONS` covers the worker states the runtime actually produces:
`baseline`, `validation-pending`, `repair-or-escalation`, `routine-repair`,
`escalation-required`, `validated`, `reviewed`, `accepted`, `rejected`.

`apply_transition(state, request, *, permitted, problems)` is the only function that
writes:

* `state["packets"]` (exactly one appended packet per stage transition),
* `state["worker"]["lifecycle"]`,
* `state["worker"]["implementation_state" | "validation_state" | "review_state" |
  "acceptance_state" | "last_validation" | "acceptance_evidence"]`.

It validates the change against the table, refuses with `InvalidTransition`, refuses with
`PolicyRefusal` when `permitted` is false, appends an audit record to
`state["transitions"]` (bounded at 50) and returns the mutated dict. It never writes the
file: the caller persists atomically afterwards, so a refused or failed transition leaves
the stored state untouched.

`scripts/ariadne.py` entry points that now delegate: `start` (S1 packet),
`prepare_next` (packet append + worker attempt baseline), `update_worker_state`,
`finish_worker_validation`, `ingest_return`, `ingest_review`, `record_acceptance`.
`restart_direction`, `select_reasoner` and `record_reasoner_failure` reach the same
choke point because they continue through `prepare_next`. No other code path appends a
packet or assigns a lifecycle value (`grep` for `packets"].append` and
`["lifecycle"] =` returns only the engine and the two classification dicts).

The four success concepts stay separate: `implementation_state`, `validation_state`,
`review_state`, `acceptance_state` are distinct fields with distinct transitions, and each
stage transition is authorised separately.

## 3. Authorization

An approval is a versioned record (`contracts.Approval`, record schema 2) stored in
`state["approvals"]`:

```json
{"schema_version": 2, "approval_id": "apv_20260922T201500Z_1a2b3c4d", "gate": "G1",
 "subject_type": "design-direction", "subject_id": "DESIGN.md",
 "revision_hash": "<sha256>", "identity": "operator-name", "channel": "human-cli",
 "note": "...", "recorded_at": "...", "stage": "S3", "packet_id": "<packet id>",
 "consumed_by": []}
```

* `policy.approve` writes the record. It refuses a non-human channel
  (`UnauthorizedApproval`), a missing identity, a gate the engine does not enforce
  (G4/G5), a subject type that does not belong to the gate, and a duplicate approval for
  the same revision.
* `policy.gate_satisfied(state, gate, subject, consume=..., operation=...)` is the only
  way a gate becomes satisfied. It reads the **latest** approval for the gate, validates
  the record (`contracts.approval_problems`), requires `channel == "human-cli"` and
  re-derives the subject fingerprint now, so a stale or mismatched record cannot
  authorize anything. With `consume` it spends a single-use approval for one operation.
* `revision_hash` is a declared-field fingerprint (`contracts.REVISION_FIELDS`,
  `contracts.digest_fields`): `design-direction` = thesis line + the normalised
  `Signature moment`, `Responsive behaviour` and `Asset direction` sections; `handoff` =
  handoff sha256 + worker-contract scope rows + validation rows; `review` = S5 packet id
  + `packet_sha256` + judgement sha256 + reviewer identity + validated-revision digest.
  Cosmetic edits (the `**Status:**` line) keep an approval valid; semantic edits
  invalidate it.
* The CLI surface is `approve-gate --gate G1|G2|G3 --identity ... [--note ...]`
  (the only new subcommand). `--identity` is required by the parser for this new
  command, so no legacy invocation changes.
* Document fields are mirrors only: `approve-gate` updates the `**Last gate passed**` row
  in `AGENTS.md` (the file documents itself as runtime state) and deliberately does not
  rewrite `DESIGN.md`, which is a hash-anchored artifact of recorded creative evidence.

## 4. Continuation preconditions

`policy.continuation_problems(state, target, project=...)` is the single precondition set
for a stage transition:

| target | preconditions |
|---|---|
| S2, S3 | none beyond the proposal (`infer_next_stage` already refuses an incomplete boundary) |
| S4A | DESIGN.md + AGENTS.md exist, creative evidence resolved (`creative.project_problems(project, "S3")`), G1 approval bound to the current direction |
| S4B | provider preflight cleared, G2 approval bound to the handoff when the handoff declares dependencies to install |
| S5 | independent validation recorded, passed and well-formed |
| S6 | the required review is recorded for the packet |
| same-stage retry | none (entry preconditions already held; the retry policy governs) |

Both `advance` and `prepare_next` call it, so a requirement cannot hold on one path and be
skipped on another. `advance` additionally uses `policy.creative_evidence_problems` and
`policy.g1_problems` for its S3 presentation branch, i.e. the same functions.

`policy.repair_allowed` states the bounded routine-repair rule once (attempts vs
`repair_limit`, and "a blocked result never enters routine repair"); `prepare_next`'s retry
path raises the same messages it always did.

## 5. Review evidence

`review.py` records a review as a versioned record in `state["reviews"]` and beside the
evidence as `evidence/review-record.json`:

```json
{"schema_version": 2, "review_id": "rev_...", "run_id": "...", "packet_id": "...",
 "review_kind": "experience|technical", "reviewer_identity": "...",
 "reviewer_role": "...", "context_digest": "<S5 packet sha256>",
 "reviewed_revision": "<sha256 of validation.json>", "requirements": [...],
 "evidence": [...], "findings": [...], "outcome": "passed|failed|blocked|not-performed",
 "recommendation": "...", "recorded_at": "...", "independent": true}
```

`ingest_review` now requires a reviewer identity that is not one of the identities
recorded for the implementation worker (`review.independence_problems` compares
`worker_role`, `provider`, `model`, `task_id`, `identity`). The `--reviewer-identity`
argument is optional at the parser level (existing invocations still parse) and enforced at
runtime with exit code 1, which is the same refusal channel as before. `--kind` selects the
review lens; `review.REQUIRED_EVIDENCE` gives each kind its own required evidence set
(experience: review context + judgement + mechanical QA; technical: judgement +
independent validation + reviewed source revision), and an unknown or missing item refuses
ingestion.

`NOT_PERFORMED` is preserved: `review_state` stays `NOT_REVIEWED`,
`review.required_review_problems` reports the absence, `record_acceptance` refuses, and no
document or worker statement can substitute for the record.

## 6. Persistence, migration and recovery

* The run-state **file** schema stays `1` (`contracts.SCHEMA_RUN`). AR-201 adds fields,
  it does not replace the format, so a run written by this runtime is still readable by
  published v1.6.7 and no original benchmark expectation about the file version changes.
  The new **record** contract is `2` (`contracts.SCHEMA_RECORD`) and each record carries
  its own `schema_version`.
* `persistence.load_state(run_root, migrate_state=False)` refuses (exit 1, "Run state
  schema is unsupported") any version outside `READABLE_RUN_SCHEMAS`, refuses malformed
  state, and refuses a state that predates the engine contract until `--migrate` is given
  explicitly. Nothing is written on read.
* `--migrate` is an optional flag on every run-selecting command (the flag is additive;
  no required argument changed).
* `persistence.write_state` is atomic (temp file + retry + replace) and normalises the
  fields the engine owns (`approvals`, `migration_history`, `transitions`, `engine`).
* `persistence.recovery_report` reports an interrupted write, an orphan packet or a
  missing packet without adopting or inferring anything.

See `03-MIGRATION.md` for the compatibility policy and `05-TEST-RESULTS.md` for evidence.

## 7. API and CLI

`api.py` implements `Result(exit_code, message, artifacts, state_changed)` and
`format_result`, plus `start_run`, `status`, `approve_gate`, `prepare_next`,
`record_result`, `ingest_return`, `validate_worker`, `prepare_review`, `ingest_review`,
`record_acceptance`, `recovery_report`. Each wraps the same runtime command function the
CLI uses, captures its operator text and returns the same exit code; a raised runtime
error becomes exit code 1 with the same `STOPPED:` text the CLI prints.

The CLI in `main()` dispatches to the same API objects for the delegated commands and
writes `format_result(result)` to stdout, so the two surfaces cannot drift. Commands whose
output is not protected state (`discover`, `route`, creative/operations ledgers, notes,
reasoner selection) keep their original implementations.

See `04-API-CONTRACT.md` for the surface and stability status.

## 8. Deviations from the AR-200 handoff (with evidence)

1. **Run-state file schema stays 1; the versioned contract is the record schema.**
   The handoff (`09-AR-201-HANDOFF.md`, T1) proposed `SCHEMA_RUN = 2` as the version the
   runtime writes. That is incompatible with two original cases that must keep passing on
   unchanged definitions: `lifecycle.start-creates-verified-s1` asserts the persisted
   `schema_version == 1`, and `lifecycle.state-schema-mismatch-refused` mutates the state
   to `2` and asserts the runtime refuses it (its own verification column in the handoff
   claims this case "still passes"). Writing `2` would also strand every existing run for
   the published runtime, which AR-200's own risk register warns about. AR-201 therefore
   keeps the file version and versions the *records*, and adds
   `lifecycle.schema-migration-explicit` (legacy contract → current, explicit, additive,
   reversible) plus `lifecycle.state-schema-mismatch-refused` unchanged as the two sides of
   the compatibility policy. See `03-MIGRATION.md` §1.
2. **`--reviewer-identity` is enforced in code, not by the parser.** Stop condition 6
   forbids gaining a *required* argument on an existing command, so the parser accepts the
   optional flag and `ingest_review` refuses without it (exit 1, explicit reason). The
   security case that must flip reads the exit code only.
3. **The creative-evidence requirement is enforced at the S3→S4A boundary on every path.**
   The runtime's S1/S2/S4A creative "nudges" existed only on the `advance` path and were
   removed in favour of the single precondition set (I-9). `design.unsupported-claim-blocks-g1`
   and `lifecycle.s3-blocks-without-human-g1` keep their recorded verdicts; the S3 requirement
   is stricter, not weaker, because it now applies to `prepare-next` as well.
4. **The gate-fingerprint field list for the design direction uses the DESIGN.md sections
   rather than the creative ledgers' requirement ids.** At approval time (S3) the
   operations ledger does not exist yet, so requirement ids cannot be part of a stable
   fingerprint; the ids are a deterministic function of exactly those sections, so hashing
   the sections captures every edit that could change them.
5. **Fixtures and one evaluation changed, documented in `05-TEST-RESULTS.md` §4.** The
   benchmark fixtures now record the human gate and the creative evidence the workflow
   requires, and the three authorization cases were re-expressed as pass/fail evaluations
   that still fail if the defect returns.
