# AR-203 — Verification Model

AR-203 introduces one reusable verification record and one freshness contract,
shared by rendered evidence, reference retrieval, capability exercise, review
independence and the Decision Plane. Specialised evidence contracts are kept:
the verification record is the *proof of verification*, not a replacement for
`rendered_evidence_problems`, `reference_problems` or `design_review_problems`.

## 1. The record

```text
VerificationRecord
├── verification_id          engine-generated (vrf_<utc>_<nonce>)
├── schema_version           contracts.SCHEMA_VERIFICATION
├── subject / subject_type   what the claim is about (evidence id, reference id, ...)
├── claim                    the sentence that was verified
├── method                   how it was established
├── execution_id             the engine-created execution that observed it
├── observed_anchor          an engine-recorded anchor when no execution observed it
├── verifier_execution_id    the different engine execution that reproduced it
├── revision                 the revision the claim is bound to
├── evidence[]               artifacts the engine re-hashed itself
├── observed_digest          what was observed
├── reproduced_digest        what the verifier re-produced
├── reproduction             {path, sha256} of the re-produced artifact
├── dependencies{}           named dependency fingerprints
├── dependencies_digest      a stable digest over them
├── level                    what was actually established
├── freshness                CURRENT | STALE | UNKNOWN | SUPERSEDED
├── established_level        history kept when a record goes stale
├── superseded_by            the record that replaced it
├── limitations[]            what remains unverified
└── recorded_at
```

## 2. Levels and their obligations

| Level | Obligation |
|---|---|
| `DECLARED` | a subject and a claim; no evidence was examined |
| `OBSERVED` | a named engine execution *or* an engine-recorded anchor, a revision, and at least one real artifact the engine re-hashes |
| `REPRODUCED` | plus a *different artifact* the verifier re-produced with a matching digest |
| `INDEPENDENTLY_REPRODUCED` | plus a *different engine-created execution* as verifier |
| `VERIFIED` | plus named dependency fingerprints, all current |
| `STALE` | a freshness verdict, never a level a record is created at |
| `UNVERIFIED` | nothing was established |

Three rules are enforced rather than documented:

1. **Re-hashing is not reproduction.** `REPRODUCED` requires a reproduction
   artifact whose path differs from the observed artifact's; re-opening the same
   file is refused with *"re-hashing one file is not re-production"*.
2. **One execution cannot be its own independent verifier.** At
   `INDEPENDENTLY_REPRODUCED` and `VERIFIED`, observer and verifier must be
   different engine-created executions.
3. **A level cannot skip.** `REPRODUCED` with a different verifier is refused and
   told it is `INDEPENDENTLY_REPRODUCED`; `VERIFIED` requires dependencies that
   can be re-evaluated later.

`verification.create` validates the record with
`contracts.verification_record_problems` before it is stored, so a malformed
record cannot exist even transiently.

## 3. Freshness

`FRESHNESS_STATES` is the one vocabulary shared by capability, verification and
design records:

```text
CURRENT      every named dependency still matches
STALE        a named dependency changed
UNKNOWN      a named dependency was not supplied, or none were recorded
SUPERSEDED   a later record replaced this one
```

Freshness is *dependency-specific*: a record names the fingerprints it was
established against, and it becomes stale only when one of **those** changes. An
unrelated file change cannot invalidate it. `verification.refresh(state, id,
current={...})` re-evaluates and records the verdict; `verification.effective_level`
answers with `STALE` for a stale record even though `established_level` keeps
what it once established. A stale artifact remains useful history and is never
deleted; it simply cannot satisfy a current requirement. When the dependencies
match again, `refresh` restores the level from `established_level` and records
`restored_at`, so `freshness` and `level` can never disagree.

`verification.supersede(state, old, by=new)` marks a record replaced by a later
one for the same subject, keeping both.

## 4. Rendered verification

`render.verify` now requires:

* the engine-created **capture execution** the evidence came from;
* a **different** engine-created verification execution;
* the **artifact** the verifier re-produced — a real file the engine re-hashes,
  at a different path from the capture, with a digest equal to the capture's.

It writes a verification record bound to source revision, artifact digest,
capture parameters (kind, method, adapter, viewport, environment) and the capture
execution. `render.verification_dependencies(record)` exposes those fingerprints
and `render.verification_currentness(state, evidence_id, revision_hash=,
current_dependencies=)` re-evaluates them, so a changed capture parameter or
revision makes the verification `STALE`. `render.stale_records` consults that
verdict, so a stale verification no longer answers as verified anywhere.

Declared-observer artifacts remain capped at `RENDERED`: re-hashing the same
external file under a second execution is not independent re-production, and the
refusal names the ceiling.

## 5. Reference retrieval verification

`references.record_retrieval_verification` requires an engine-created verification
execution and the artifact the verifier re-retrieved; the engine re-hashes it and
requires the digest to equal the recorded retrieval. Only then is
`content.origin.remote_origin_proven` recorded `True`, together with the
verification id and the execution. `references.reference_currentness` reports
`STALE` when the content digest or locator changed, and
`references.provenance_problems` reports any reference that claims a proven
remote origin without a verification record — *a URL string is not retrieval
proof*.

The observation anchor is the reference record itself
(`observed_anchor = reference:<id>`): the original retrieval is adapter-supplied
and has no engine execution, while the verifier is still an engine-created
execution. That distinction is recorded rather than smoothed over.

## 6. Review independence

`review.independence_problems` requires both executions to be engine-created
records and different. `review.independence_level` computes the level from
observed facts only:

| Level | Established by |
|---|---|
| `NONE` | the same execution, or nothing distinguishes them |
| `DECLARED_DISTINCT` | two different labels or non-engine ids |
| `ENGINE_DISTINCT_EXECUTION` | two different engine-created executions |
| `DISTINCT_RUNTIME` | plus a different observed adapter/invocation |
| `DISTINCT_PROVIDER` | plus different provider-observed provider/model |
| `HUMAN_REVIEW` | a recorded human channel reviewed the work |

No level is categorically better for every task; policy decides which level a
review requires. The level is recorded on `review.build_record` and
`critique.build_review` records so the claim is auditable.

## 7. Tests

Engine suite: level obligations, re-hash refusal, self-verifier refusal,
dependency freshness, supersede, and the review-independence levels. Benchmark
groups `render-verification`, `reference-verification`, `review-independence`,
plus `false-acceptance.stale-passing-evidence-does-not-close`.
