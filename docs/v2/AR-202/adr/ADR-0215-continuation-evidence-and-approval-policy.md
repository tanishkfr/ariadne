# ADR-0215 — Continuation evidence, and the approval policy answers

Status: accepted (AR-202)
Deciders: AR-202 implementation
Evidence: `src/ariadne_engine/policy.py` (`evidence_requirements`, `evidence_requirement_problems`), `scripts/ariadne.py` (`record_acceptance`, `validate_worker`), benchmark group `evidence-continuation`

## Context
AR-201 left two gaps. First, the lifecycle evidence requirement was complete up to S4A but not at `S4A → S4B` or `S4B → S5`: a worker could record a structured return without any evidence that the S4A planning work or the S4B QA work actually ran, and the creative/operations ledgers were only checked at the S3 boundary. Second, AR-201 explicitly deferred two approval questions (expiry, and G3 versus rejection).

## Decision — evidence
`policy.evidence_requirements(state, target)` is the single evaluator for every continuation path, and `continuation_problems` is its only consumer:

- `S4A → S4B` requires the **S4A** creative skill evidence (the work that produced the handoff);
- `S4B → S5` requires the **S4B** creative skill evidence *and* the creative-operations implementation mapping;
- the S3 requirement at `S3 → S4A` is unchanged;
- requirements are **task-relevant**: a run that does not require creative evidence (`creative_evidence_required: false`) declares no creative requirement and cannot be blocked by one;
- each requirement reports its state (`satisfied`, `missing`, `unavailable`, `unresolved`, `stale`, `unsatisfied`, `optional-unresolved`) with evidence; required evidence that is not satisfied blocks, optional-but-open evidence is reported without blocking;
- **stale** means the ledger's recorded artifact digest no longer matches the file: a claim whose evidence moved is not evidence.

Because both `advance` and `prepare-next` funnel through `continuation_problems`, no ordering of commands can bypass the requirement.

## Decision — approval policy
- **No wall-clock expiry.** An approval becomes invalid when the revision, subject, operation or scope changes, when it is consumed, revoked, or superseded. Timestamps are not treated as an authority.
- **G3 authorizes acceptance only.** A rejected acceptance decision is recorded as a human note (kind `recovery`) with `approval_effect: none`; it consumes no G3 approval, is never reused as acceptance authority, and the engine does not ask for G3 until acceptance is actually being authorized.

## Alternatives considered
- **Requiring creative evidence for every run.** Rejected: a non-creative task would inherit gates it has no evidence to satisfy.
- **Treating a worker's statement ("I ran the QA skill") as evidence.** Rejected: that is the exact failure mode the milestone exists to close.
- **Blocking on selected *optional* skills at S4B.** Treated like the existing S3 rule (selected skills are required); unselected skills are recorded as `optional-unresolved`, never as a blocker.
- **Consuming G3 on rejection.** Rejected: rejection is not acceptance; consuming it would silently burn the human's authority.

## Consequences
- Runs that reached S4B or S5 without recording the skill evidence now pause with a named requirement instead of proceeding. That is a deliberate, documented tightening; the fixtures record the evidence where a live session would.
- The Ariadne-owned ledgers (`.ariadne/creative-evidence.json`, `.ariadne/creative-operations.json`) are treated as in-contract during worker validation, because the runtime's own commands write them; the worker's implementation scope is unchanged.
