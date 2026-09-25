# AR-202 — Failure taxonomy and recovery

Modules: `src/ariadne_engine/execution.py` (taxonomy), `src/ariadne_engine/recovery.py`, `src/ariadne_engine/persistence.py` (detection)
Tests: `scripts/test-engine-core.py` (`failure_checks`, `recovery_checks`), benchmark group `recovery`

## 1. Failure taxonomy

One class per failure, mapped from the existing vocabularies by an explicit
table; anything unmapped is `UNKNOWN`.

| Class | Mapped from | retry | strategy change | escalate |
|---|---|---|---|---|
| `IMPLEMENTATION_FAILURE` | `routine`, `worker-blocked` | yes | yes | no |
| `VALIDATION_FAILURE` | `validation-command`, `contract` | yes | no | no |
| `REVIEW_FAILURE` | `review-failed`, `review-blocked` | yes | no | no |
| `AUTHORIZATION_FAILURE` | `out-of-scope`, `dangerous-action` | no | no | yes |
| `CAPABILITY_FAILURE` | `missing-capability` | no | yes | yes |
| `PROVIDER_FAILURE` | `provider-unavailable`, `provider-blocked`, `provider-mismatch` | yes | yes | no |
| `TIMEOUT` | `validation-timeout` | yes | yes | no |
| `ENVIRONMENT_FAILURE` | `runtime-unavailable`, `missing-dependency` | yes | yes | no |
| `CONTEXT_FAILURE` | `context-missing`, `packet-missing` | yes | no | yes |
| `STALE_REVISION` | `stale-revision`, `revision-changed`, `context-stale` | no | yes | yes |
| `CONFLICT` | `repository-conflict`, `duplicate-result` | no | yes | yes |
| `INTERRUPTED` | `interrupted`, `orphan-execution`, `interrupted-write` | yes | no | no |
| `UNKNOWN` | everything else | no | no | yes |

Each failure record carries the execution, task, revision, operation, class,
evidence, the three flags above, the failing `strategy`, and a timestamp.
The flags describe what the class *permits*; the AR-201 routine-repair budget
(`MAX_ROUTINE_REPAIRS = 2`) and the worker lifecycle table remain the only
enforcement of how many attempts actually happen. A failure without evidence is
refused, so a failure can never be asserted into existence.

## 2. Detection

`recovery.detect(run_root, state)` (read-only) reports:

| Finding | Meaning |
|---|---|
| `orphan-packet` | a packet directory with a manifest that run state does not record (crash between writing the packet and recording the transition). Annotated with `belongs_to_tip` and `legal_next_stage` |
| `missing-packet` | state names a packet whose directory or manifest is gone |
| `interrupted-write` | a leftover `.ariadne-run.json.*.tmp`; the live state is intact |
| `interrupted-execution` | an execution still open while the recorded boundary has moved on |
| `duplicate-result` | two completed executions claim a result for the same role and task |
| `packet-identity-mismatch` | the recorded packet id disagrees with the manifest on disk |

Detection scans the real packet location (direct children of the run root) as
well as the historical `packets/` directory, and it deliberately does **not**
report an execution whose task is still the current boundary: an in-flight
execution is not a divergence.

## 3. Safe actions

| Action | Allowed when | Mechanism | Rollback |
|---|---|---|---|
| `adopt-packet` | the orphan's recorded parent is the current tip, its stage is a legal next stage, and `continuation_problems` still hold *now* | `statemachine.apply_transition(kind="stage", operation="recovery:adopt-packet")` with `actor` = operator identity | the pre-recovery state is copied to `ariadne-run.recovery-<stamp>.bak`, byte-identical |
| `discard-packet` | any detected orphan | the directory is moved to `<run_root>/recovery-quarantine/`; the manifest digest is recorded | move the directory back |
| `clear-interrupted-write` | any detected temporary file | the file is moved to quarantine; its digest is recorded | move the file back |
| `abandon-execution` | an open execution the boundary has moved past | `execution.abandon` → `FAILED` + a class-`INTERRUPTED` failure record | the pre-recovery state backup; the execution stays FAILED |

Every action requires `--identity` and `--reason`; both are recorded. Applying
an action writes a `recoveries[]` record (action, target, identity, reason,
outcome, evidence, backup, before/after) and emits `recovery_proposed` and
`recovery_applied` events.

## 4. Refusals

Refused with the reason, changing nothing:

* orphan whose recorded parent is not the current tip (it may belong to an
  abandoned attempt; adopting it would record a transition that never happened);
* orphan whose stage is not a legal transition from the current stage;
* adoption whose preconditions no longer hold (re-checked at apply time);
* a missing packet (nothing can rebuild the delivered bytes);
* duplicate completed results for one task (the state is ambiguous);
* a packet id that disagrees with its manifest;
* any recovery action without an operator identity or reason;
* an unknown finding kind.

An ambiguous state stops and escalates; recovery never chooses one result over
another and never fabricates a validation, review or success.

## 5. Operator surface

```
ariadne.py recover --run-root <run> [--json]                       # inspect (exit 2 when diverged)
ariadne.py recover --run-root <run> --apply adopt-packet \
    --target <packet-id> --identity <who> --reason <why>           # apply one safe action
```

`ENGINE_API.propose_recovery(...)` and `ENGINE_API.apply_recovery(...)` expose
the same core; both delegate to the same functions the CLI calls.

## 6. Worked example (benchmark `recovery.adopts-orphan-packet-with-backup`)

1. S1 and S3 are prepared normally; the S3 entry is removed from run state,
   simulating a crash between the packet write and the transition record.
2. `recover --json` → exit 2, `orphan-packet` with `belongs_to_tip: true`,
   `legal_next_stage: true`, proposal `adopt-packet` marked safe.
3. `recover --apply adopt-packet …` → the S3 packet is appended through
   `apply_transition` with `operation: recovery:adopt-packet`, a recovery record
   is written, a backup of the pre-recovery state exists and is byte-identical
   to the previous file.
