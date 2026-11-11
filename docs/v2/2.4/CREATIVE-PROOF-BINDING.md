# Creative Proof Binding — Ariadne 2.4C

**Purpose:** close the 2.4A-R limitation where the final Proof Receipt proved the
corrected implementation and its engine validation but did not bind the
independent S5 review. This document defines the binding, its refusals and the
authority boundary. It does not create a second proof engine.

## 1. The gap being closed

The 2.4A-R live lifecycle ended with:

```text
corrected implementation
  -> engine validation
  -> independent S5 review (passed, Present G3)
  -> Proof Receipt VP-0001 (ACCEPTED)
  -> G3 still pending
```

The receipt named the review only as `{reviewer: ...}`. It did not bind the
review packet, the reviewer execution, the independence level, the reviewed
revision, the review evidence digest, or the correction lineage. A reader could
not tell from the receipt which S5 review, if any, authorized the corrected
revision.

## 2. The binding

`src/ariadne_engine/creative_proof.py` builds a versioned record:

```json
{
  "schema_version": "ar-24c-creative-review-binding-1",
  "required": true,
  "packet_id": "qualification-after-S5",
  "packet_digest": "<sha256 of the current S5 packet>",
  "review_id": "rev_...",
  "review_kind": "experience",
  "reviewer_identity": "...",
  "reviewer_execution": "exe_...",
  "implementing_execution": "exe_...",
  "independence_level": "DISTINCT_RUNTIME",
  "outcome": "passed",
  "recommendation": "present g3",
  "reviewed_revision": "<sha256 of the reviewed validation record>",
  "review_context_digest": "<review.context_digest>",
  "implementation_revision": "<the receipt work digest>",
  "implementation_fingerprint": "<current implementation fingerprint>",
  "review_evidence_digest": "<sha256 binding review + packet + judgement + validation>",
  "review_judgement_sha256": "<sha256 of review-judgement.md>",
  "findings": [],
  "outstanding_findings": [],
  "correction_lineage": [],
  "authorization_effect": "none",
  "binding_digest": "<sha256 of this record>"
}
```

The Proof Receipt schema becomes `ar-224-proof-receipt-2`; the binding is stored
under `creative_review`. Version 1 receipts remain readable and are **not**
silently reinterpreted as carrying a review binding.

## 3. Conditions for counting a passed review

`creative_proof.build()` refuses unless all of these hold:

1. The run has a current S5 packet with a `packet_sha256`.
2. A review record exists for **that packet id** (not the run's latest review,
   not another attempt's review).
3. The review's context digest equals the current packet digest.
4. The review outcome is `passed` and its recommendation is `Present G3`.
5. The review judgement file exists and its digest matches the recorded
   `review_judgement_sha256`.
6. The reviewed validation record is current, `passed`, and its digest matches
   both `reviewed_revision` and `validation_sha256`.
7. The reviewer and implementer executions are engine-created records in this
   run and are different executions.
8. The independence level is one of `ENGINE_DISTINCT_EXECUTION`,
   `DISTINCT_RUNTIME`, `DISTINCT_PROVIDER`, `HUMAN_REVIEW`.
9. The reviewed implementation fingerprint equals the fingerprint being
   verified.
10. The binding digest and every required field are self-consistent.

If any condition fails, the Proof Pass raises before a receipt is created. It
does not store a weaker binding and does not reuse an older review.

## 4. Revision freshness

A new implementation revision invalidates the previous review because the
review's validation record digest and implementation fingerprint no longer
match. A corrected revision needs a fresh S5 packet, a fresh review and a fresh
validation before a new receipt can bind it.

`creative_proof.current_problems(binding, state, work_digest=..., implementation_fingerprint=...)`
re-checks a stored receipt against the current packet, review record, judgement
file, validation record and implementation. The host projection calls this and
reports `fresh=false` with the named problems instead of displaying a stale
proof as current.

## 5. G3 is still human-owned

The binding is evidence, never authorization:

- `authorization_effect` is `none` on the binding and the receipt;
- the Proof Pass does not add an approval record;
- `policy.gate_satisfied(state, "G3", subject)` still requires a recorded
  human-channel approval;
- `record_acceptance` still refuses `accepted` until G3 exists;
- a passing review plus a passing proof receipt is not a G3 decision.

The qualification receipt is `ACCEPTED` because every requirement is proven; it
still has no G3 approval. The human decision remains outstanding.

## 6. Refusal cases covered by tests

`scripts/test-ar24c.py` covers:

- missing review;
- failed review with findings;
- changed review judgement file;
- different implementation revision/fingerprint;
- another packet's review substituted;
- reviewer and implementer the same execution;
- stale S5 packet digest;
- tampered binding;
- tampered receipt digest;
- G3 absent after a passing review and proof;
- forged host proof state.

`scripts/test-ar24c-mutations.py` removes each of the first four boundaries and
confirms the targeted test goes red.

## 7. Compatibility

- `ar-224-proof-receipt-1` receipts remain readable and unchanged.
- A non-creative T1 receipt has no `creative_review` field; no new obligation is
  invented for it.
- A creative run at the S5 boundary must produce a binding; an old receipt
  without one cannot be presented as proof of independent review.
- The binding is additive: no existing receipt is rewritten, and no historical
  record is relabelled.

## 8. Qualification result

The disposable design qualification (`validation/runs/2.4c/design/`) produced:

```text
packet      qualification-after-S5
review      rev_... (passed, Present G3)
independence DISTINCT_RUNTIME
receipt     VP-0001 ACCEPTED
binding     ar-24c-creative-review-binding-1
G3          not recorded
```

The receipt's creative binding names the current packet, reviewer execution,
independence level, reviewed revision and evidence digest. The human gate was
not created by the proof.

## 9. Evidence

- `src/ariadne_engine/creative_proof.py`
- `src/ariadne_engine/proof.py`
- `scripts/test-ar24c.py`
- `scripts/test-ar24c-mutations.py`
- `validation/runs/2.4c/design/run/proof-receipt.json`
- `validation/runs/2.4c/design/report-after.json`
