# Ariadne 2.4A — Execution Reliability

Status: release-candidate architecture note for `2.4.0rc1`. This phase adds no
new intelligence feature and no second workflow engine. It hardens the lifecycle
that already existed: implement, validate, review, repair, revalidate, re-review,
prove, accept, and recover after interruption.

## 1. One lifecycle, two worker boundaries

The same attempt/evidence contract is used at both boundaries:

| Boundary | Implementation | Validation | Review | Human close |
|---|---|---|---|---|
| T1 task | `task_execution.py` + worker adapter | `task-validate` | `task-review` | `task-accept` |
| Creative S4B/S5 | `prepare-stage.py` + implementation worker | `validate-worker` | `ingest-review` | `record-acceptance` |

A failed review is not a generic retry. It authorizes a **linked corrective
attempt**:

```text
validated attempt A
  └─ review R fails with "fix and re-review"
       └─ correction A+1 (parent_attempt=A, review_id=R)
            ├─ same declared scope
            ├─ empty validation record
            ├─ new packet + new engine validation
            └─ review must be performed again
```

The previous attempt, return, validation and review remain on disk and in
history. The failed review is retired from the *current* gate slot when the
correction is prepared, so it cannot approve the corrected revision.

### Budgets

- `MAX_ROUTINE_REPAIRS = 2`: failed validation retries.
- `MAX_REVIEW_CORRECTIONS = 2`: review-directed corrections, tracked per task
  (T1) or per creative packet chain (S4B). The two budgets are separate; an
  exhausted review budget refuses rather than silently becoming a routine retry.

### Refusals that are part of the contract

- a correction cannot inherit a passing validation (`record_attempt_validation`
  requires a real record bound to the attempt's packet and implementing
  execution);
- a review cannot be ingested by an implementation execution or an identity
  already recorded for the task;
- a review of another attempt or another validation digest is stale;
- a proof receipt belongs to one attempt, review and validation; a receipt id
  absent from the durable receipt store cannot be accepted;
- a changed task scope invalidates the correction authorization;
- a failed later correction never falls back to an earlier pass;
- acceptance requires a current validation, a current passing review when
  policy requires one, and a current proof receipt.

## 2. Evidence and revision binding

A T1 validation now carries:

```json
{
  "packet_id": "app-T1-H1",
  "attempt_id": "atm_app-T1-H1",
  "validated_revision": {
    "head": "<git head>",
    "implementation_fingerprint": "<sha256 of the implementation surface>"
  }
}
```

The attempt record stores the record digest (`validation_sha256`) and the
implementation fingerprint. Reviews store the attempt id and the validation
digest they reviewed; proofs store the attempt, review and validation. This is
the chain every gate checks:

```text
current attempt -> validation file digest -> validated revision fingerprint
                -> review attempt/digest -> proof attempt/review/digest
```

If the implementation moves, the fingerprint changes and the old chain is
`stale-evidence`; it is never silently reused.

## 3. Durable operations and recovery

Each task carries an append-only `operations` list. An operation is recorded
before its side effect:

`launch`, `execute`, `collect-return`, `ingest-return`, `validate`,
`persist-evidence`, `review`, `repair`, `proof`, `accept`.

`task-recover` reports:

- last durable state and last durable operation;
- the interrupted operation (a `started` record with no completion);
- current attempt and packet;
- last verified revision;
- current repository revision and whether it still matches;
- safe continuation (`ingest-return`, `recover-validation`, `validate`,
  `review`, `prepare-review-correction`, `proof`, `repair`, `run`,
  `wait-or-abandon-open`, `stop-stale-evidence`, `escalate`, `accept`, `none`);
- the human action required, if any.

Safe continuations are deliberately narrow:

- a recorded validation is finalized from its durable bytes without rerunning
  the checks;
- a return already on disk is reconciled without writing the return again;
- a completed proof is not minted twice;
- an open execution is not declared dead automatically;
- a stale revision stops recovery instead of reusing the old pass;
- a lock whose owning process is gone is broken; a live lock is respected;
- a contract left by a preparation that never reached its state write is
  preserved as an orphan and the correction is prepared afresh.

Repeated `task-recover --apply` calls are idempotent for attempts, proofs and
approvals.

## 4. Adapter conformance

`adapter-conformance` is a shared matrix, not a vendor-specific branch in the
lifecycle. It records these checks:

`identity`, `kind-and-transport`, `capability-declaration`,
`executable-discovery`, `version-reporting`, `authentication`,
`argument-compatibility`, `working-directory`, `prompt-delivery`,
`file-edit-permission`, `structured-return`, `cancellation`, `timeout`,
`nonzero-exit`, `interrupted-session-recovery`, `scope-enforcement`,
`independent-validation`.

A structural check can be `pass`; an observation that was not executed is
`declared` or `not-observed`, never `pass`. A missing executable is `blocked`,
not a failure of the adapter contract.

The CLI invocation owns its process group/tree. A timeout terminates the whole
tree before the failure is recorded, so a child cannot continue editing after
the attempt was declared lost.

Live qualification evidence for this release is in
[`docs/HOSTS-AND-LIMITS.md`](../../HOSTS-AND-LIMITS.md) and
`validation/runs/2.4a/2.4a-live-adapters.txt`.

## 5. Observability

`task-status --json` (and the Python API/MCP read-only surface) reports:

```text
task_id, objective, status, current_attempt, selected_worker, current_operation,
last_validation {status, failure_kind, path, validated_revision, fresh, problems},
review {outcome, reviewer_identity, findings}, review_findings, review_blockers,
review_corrections / review_correction_limit, evidence_freshness,
baseline_head, current_head, revision_drift, gates, proof, acceptance,
recovery, continuation
```

The representation is derived from durable records only. It does not show an
optimistic "running" when the last durable state is a failed or stale attempt.
MCP exposes the same object through a read-only `task_status` tool; it cannot
mutate lifecycle state or mint authority.

## 6. Compatibility and migration

- Standard: additive optional fields on task records (`attempt_id`,
  `parent_attempt_id`, `repair_kind`, `reviews`, `operations`,
  `current_operation`, `review_corrections`, `proof_history`).
- No run-state schema bump and no migration step: a 2.3 task record remains
  readable; a missing field is absent, not fabricated. An old passing validation
  without a fingerprint is refused as unprovable-current rather than trusted.
- CLI flags and existing commands remain valid. New surface:
  `task-recover`, `adapter-conformance`, `task-status` fields, `task-*` Python
  API functions, and MCP `task_status`.
- The S4B packet parent contract expands from `S4A/S4B` to `S4A/S4B/S5`; an S5
  parent is accepted only when the recorded review authorizes a correction.
- Creative skill evidence may be re-recorded for a new packet id after
  `completed`; the history retains both cycles. This is the creative-evidence
  equivalent of a fresh attempt, not a rewind.

## 7. Tests

Focused reliability suite:

```bash
python scripts/test-ar24a.py
```

Lifecycle mutation harness (run it from a disposable worktree; it edits the
implementation it lives in and restores it transactionally):

```bash
git worktree add --detach /tmp/ariadne-mutations HEAD
cd /tmp/ariadne-mutations
python scripts/test-ar24a-mutations.py --report /path/to/mutations.json
```

Adapter conformance (structural; live cases need existing authenticated CLIs):

```bash
python scripts/test-ar24a-adapters.py
ARIADNE_LIVE_ADAPTERS=1 python scripts/test-ar24a-adapters.py
```

Full deterministic benchmark and release subset:

```bash
python benchmarks/run_benchmarks.py
python benchmarks/run_benchmarks.py --release
python benchmarks/run_benchmarks.py --case lifecycle.s4b-review-correction
```

The focused suite covers failed review -> correction, correction -> failed
validation, successful correction -> re-review, two sequential corrections,
correction budget exhaustion, unchanged passing attempt no-op, stale validation,
cross-attempt evidence, forged reviewer identity, out-of-scope correction,
forged and tampered proof receipts, a missing human identity at acceptance, real
process interruption during worker execution, real process interruption during
validation, recorded-validation recovery without rerunning checks, interrupted
return ingestion, changed repository state, repeated resume, CLI/API/MCP status
parity, and the S4B correction contract.

2.4A-R fresh evidence (Windows, Python 3.11.9):

- focused suite: 21/21 (the 19 original cases plus the tampered-receipt and
  human-identity regressions);
- mutation harness: 17 attempted, 17 valid, 17 killed, 0 survived, 0 invalid,
  restoration proven; the first pass's two survivors are kept in
  `validation/runs/2.4a-r/mutations-attempt1.json`;
- full benchmark: 338 pass, 0 fail, 0 error, 5 observed, 2 skip; release subset
  90/90;
- engine core 586/586, AR-23B 27/29 (2 declared opt-in skips), AR-23C 22/22,
  AR-23D 25/25, AR-225 51/51, release 97/97, distribution 55/55, wheel install
  14/14;
- live S4B/S5: Command Code 1.88.5 / DeepSeek V4.1 Flash implemented and
  corrected; a fresh OpenCode 2.2.5 / GitHub Copilot (`gpt-5.6-luna`) session
  produced the failed first review and the passing re-review; the corrected
  validation is `live-s4b-S4B-C3`, the final review is on `live-s4b-S5-C1`, and
  `VP-0001` is ACCEPTED. G3 was not recorded and acceptance refused at the human
  gate. The evidence is in `validation/runs/2.4a-r/live-s4b/`.

The creative S4B/S5 boundary's final gate is the human G3 plus the passed review.
`ariadne.py verify` can issue a VP receipt for the corrected work and its
engine-run validation, but it does not bind the S5 review into that receipt. Do
not describe a VP receipt as approval of the review; the review record and the
human gate are the separate authorities.

`validate.py --benchmark` accepts `--runs-dir <directory>` so a benchmark can
exercise the reader without depending on one machine's gitignored
`validation/runs/` tree. The tracked template is
`validation/run-template.md`; its self-test is part of
`suite.validation-guards`.

