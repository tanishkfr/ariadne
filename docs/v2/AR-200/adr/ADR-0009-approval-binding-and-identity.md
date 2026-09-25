# ADR-0009 — Approval binding fields and review identity, as implemented in AR-201

Status: accepted (AR-201) — narrows ADR-0002 and ADR-0003 with implementation detail
Deciders: AR-201 implementation
Evidence: `src/ariadne_engine/contracts.py`, `policy.py`, `review.py`;
`benchmarks/results/ar-200-20260922T201711.json`;
`docs/v2/AR-201/02-SECURITY-FIXES.md`

## Context

ADR-0002 specified an approval as `{gate, subject{type, id, revision_hash}, identity,
channel, note, recorded_at}` and ADR-0003 required reviews to be bound to evidence. AR-201
had to decide exactly which fields a fingerprint covers, which operations an approval may
authorize, and how a reviewer's independence is established from information the runtime
actually has.

## Decision — approval records

An approval is stored in `state["approvals"]` and carries
`schema_version, approval_id, gate, subject_type, subject_id, revision_hash, identity,
channel, note, recorded_at, stage, packet_id, consumed_by`.

* `gate` ∈ {G1 design-direction, G2 handoff, G3 review} (`GATE_SUBJECT_TYPES`). G4/G5 stay
  human/operator actions outside the engine; `approve-gate` refuses them instead of
  recording a decision nothing consumes.
* Only `channel == "human-cli"` satisfies a gate. `worker-cli`, `engine-api` and `imported`
  records may exist but never authorize.
* A gate is checked against the **latest** record for that gate only, so an older valid
  approval cannot be resurrected after a newer one was superseded.
* `consumed_by` implements single-use authorization: `record_acceptance --outcome accepted`
  spends its G3 approval with an operation id and a replay is refused.

## Decision — declared revision fields

`contracts.REVISION_FIELDS` is the declared field list per subject type, hashed
whitespace-insensitively (`digest_fields`):

* `design-direction`: the DESIGN.md design-thesis line plus the normalised
  `Signature moment`, `Responsive behaviour` and `Asset direction` sections. The
  `creative-operations` requirement ids are a deterministic function of exactly those
  sections and do not exist yet when G1 is granted (the operations ledger is created when
  S4B is prepared), so hashing the sections is both sufficient and computable at approval
  time. The `**Status:**` line is deliberately outside the fingerprint: it is a display
  field and a cosmetic edit must not invalidate a decision.
* `handoff`: handoff sha256 plus the worker contract's scope rows and validation rows —
  what a dependency approval (G2) is actually about, so a widened scope invalidates it.
* `review`: S5 packet id, packet `packet_sha256`, judgement sha256, reviewer identity and
  the validated-revision digest.

The field lists are declared, not free-form: a fingerprint with an undeclared field raises
`ContractError`, so a future field cannot silently enter or leave a binding.

## Decision — review identity and evidence

A review record (`review.ReviewRecord`) carries `review_kind` (`experience` | `technical`),
`reviewer_identity`, `reviewer_role`, `context_digest` (S5 packet sha256),
`reviewed_revision` (validation digest), `requirements`, `evidence`, `findings`, `outcome`,
`recommendation`, `recorded_at`.

* Independence: the reviewer identity must differ from the implementation worker's recorded
  identities (`worker_role`, `provider`, `model`, `task_id`, `identity`). There is no
  positive attestation to satisfy.
* Required evidence depends on the review kind (`review.REQUIRED_EVIDENCE`); a technical
  review additionally requires a passed independent validation. Neither kind accepts the
  implementer's summary.
* The record is stored in `state["reviews"]` and as `evidence/review-record.json`, refuses
  overwrite, and is the only thing that satisfies `record-acceptance` (together with the
  bound G3 approval). A review record never grants acceptance.

## Known limitation (explicit, unchanged from ADR-0002/0003)

Both identities are operator-supplied strings recorded verbatim. The engine binds and
audits them; it does not verify a person or an execution context, and a process with write
access to the run state can forge a well-formed record. This is authorization, not
isolation. Machine-verifiable identity is handed to AR-202
(`docs/v2/AR-201/07-AR-202-HANDOFF.md` §2.4).

## Consequences

* `ingest-review` requires a reviewer identity at runtime (optional at the parser level so
  no existing invocation changes exit-code class at parse time).
* Editing an approved direction invalidates G1; widening a handoff invalidates G2; a new
  review invalidates nothing but requires its own G3 approval.
* The approval log grows; it is small (a few hundred bytes per decision) and is kept in
  full as the audit record.
