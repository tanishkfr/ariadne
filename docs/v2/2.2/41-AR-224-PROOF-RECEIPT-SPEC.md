# AR-224 Proof Receipt Spec

Product thesis: workers produce. Ariadne determines what is actually proven.

## Schema

`schema_version`: `ar-224-proof-receipt-1`

Fields:

```
schema_version
proof_id            VP-NNNN, append-only sequence
engine_pass_id      vps_... lineage to the verification pass
task_id
contract_id
contract_revision
work_digest
created_at
requirement_decisions
requirement_verdicts
verdict_counts
claim_assessments
contradicted_claims
blocking_summary
acceptance_state    ACCEPTED | NOT_ACCEPTED | VERIFICATION_BLOCKED
reviewer / provenance
previous_proof_id
receipt_digest
```

A receipt is a stable projection of a verification pass. VerificationDecision
records are not duplicated; the receipt references their outcomes.

## Verdicts

Per requirement: PROVEN, PARTIAL, UNPROVEN, FAILED, NEEDS_HUMAN.
CONTRADICTED describes a worker claim, not a requirement.

Aggregate: ACCEPTED, NOT_ACCEPTED, VERIFICATION_BLOCKED.

No quality percentage. Counts only.

## Integrity

`receipt_digest` is sha256 over canonical JSON excluding itself.
Modifying content invalidates it. Digest integrity is not third-party
attestation. Never call a hash a signature.

## History

Later runs create VP-0042; VP-0041 is never overwritten. Work digest,
contract revision, requirements, decisions, claims, evidence links and
timestamps are preserved. Historical failures remain historical.

## Comparison

`compare` requires identical task/contract lineage and identical requirement
sets. Material contract-revision change yields an explicit revision boundary,
not a silent direct comparison.

## Storage

Contained in run state collection `proof_receipts`, bounded at 5000,
append-only, recoverable, queryable by proof id. No secrets by default.
Share-safe export redacts absolute paths, usernames, env, credentials,
private URLs and secret-bearing logs, and carries its own share_digest.

## Language

Permitted: Evaluated against 8 requirements using Proof Pass VP-0041.
Never: bug-free, perfect, fully secure, certified correct, guaranteed,
unless an independent external certification actually exists.
