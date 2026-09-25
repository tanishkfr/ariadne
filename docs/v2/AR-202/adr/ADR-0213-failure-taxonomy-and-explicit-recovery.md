# ADR-0213 — Failures are classified; recovery is explicit and reversible

Status: accepted (AR-202)
Deciders: AR-202 implementation
Evidence: `src/ariadne_engine/execution.py` (taxonomy), `src/ariadne_engine/recovery.py`, `05-RECOVERY.md`, benchmark group `recovery`

## Context
AR-201 recovery *reported* divergence and deliberately resolved nothing. Failures were represented by the transport's small vocabulary (`routine`, `contract`, `validation-command`, `out-of-scope`, `dangerous-action`, `repository-conflict`) plus worker lifecycle states, which is enough to drive the repair budget but not enough to distinguish "the implementation is wrong" from "the provider is gone" or "the revision moved".

## Decision
1. **One taxonomy** (`IMPLEMENTATION_FAILURE`, `VALIDATION_FAILURE`, `REVIEW_FAILURE`, `AUTHORIZATION_FAILURE`, `CAPABILITY_FAILURE`, `PROVIDER_FAILURE`, `TIMEOUT`, `ENVIRONMENT_FAILURE`, `CONTEXT_FAILURE`, `STALE_REVISION`, `CONFLICT`, `INTERRUPTED`, `UNKNOWN`) mapped from the existing vocabularies by an explicit table; unmapped input is `UNKNOWN`, never guessed.
2. Each failure records execution, task, revision, operation, evidence, and the *advisory* flags `retry_allowed`, `strategy_change_allowed`, `escalation_required`. The flags describe what the class permits; the AR-201 repair budget remains the only enforcement of how many retries happen.
3. **Recovery is operator-invoked and few**: `adopt-packet` (an orphan whose parent *is* the recorded tip and whose stage is a legal next stage, with preconditions re-checked at apply time), `discard-packet` (quarantine), `clear-interrupted-write` (quarantine a leftover temporary file), `abandon-execution` (record a stranded open execution as `FAILED`/`INTERRUPTED`).
4. Adoption goes through `statemachine.apply_transition` — the same boundary as any other transition — and the pre-recovery state is copied byte-for-byte to a backup whose digest is recorded.
5. Anything ambiguous is refused: a packet whose parent is not the tip, an illegal stage jump, failing preconditions, a missing packet, duplicate completed results for one task, an identity mismatch between state and disk.

## Alternatives considered
- **Automatic repair on startup.** Rejected: the engine cannot distinguish an abandoned attempt from an interrupted one without evidence, and AR-201's rule ("report, never infer") is correct.
- **Reconstructing a missing packet from its evidence.** Rejected: nothing can rebuild the delivered bytes; a reconstruction would be a fabricated packet.
- **A `retryable: true/false` boolean.** Rejected: it collapses timeout, provider, authorization and implementation failures into one unhelpful bit and hides the escalation decision.
- **Time-based recovery windows.** Rejected: timestamps are not an authority, and wall-clock expiry was explicitly deferred in AR-202's approval policy.

## Consequences
- Divergence detection now also scans the real packet location and open executions, so `recover` is useful on real runs rather than only on synthetic layouts.
- Every applied recovery leaves a recovery record, an engine event, and a restorable pre-recovery state.
- Recovery never fabricates a validation, a review or a success.
