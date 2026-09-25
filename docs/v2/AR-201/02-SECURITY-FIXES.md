# AR-201 — 02 SECURITY FIXES

The three authorization defects AR-200 reproduced, their root causes, the fixes and the
adversarial evidence. Every claim below was produced by the deterministic suite; commands
are in `05-TEST-RESULTS.md`.

## Defect 1 — `security.gate-forgery-in-agents-md`

**Original case.** An actor with ordinary write access and CLI access writes
`**Status:** locked at G1 …` into `DESIGN.md` and `**Last gate passed** | `G1`` into
`AGENTS.md`, records the S3 stage result, then continues. No human decision is supplied.

**Baseline behaviour (reproduced twice, `921fd8f`).** The runtime read the two document
fields as the gate, prepared the S4A packet (`exit 0`, stages `S1, S3, S4A`) and recorded
the human creative decision as *resolved* in `state["human_interventions"]`.

**Root cause.** The gate was not a record at all: `ariadne.py:advance` tested
`re.search(r"(?im)^\*\*Status:\*\*.*locked at G1", DESIGN.md)` and
`re.match(r"G1\b", state_field(AGENTS.md, "Last gate passed"))`, and
`record_acceptance` tested `project_runtime(project).get("gate") == "G3"`. Any process that
can write a project file could therefore grant a gate, and the runtime's own log recorded
that as the human's decision. The same fields are what the runtime instructed the human to
edit, so there was no way to distinguish "the human edited it" from "the worker edited it".

**Affected entry points.** `advance` (S3 → G1 presentation), `prepare_next`
(`infer_next_stage` S3 branch), `handoff_context_problems` (direction mirror),
`record_acceptance` (G3). Document mirrors were also consumed by
`creative-operations.design_locked`, which gates the S4B preparation.

**Fix.**
* `contracts.Approval` + `policy.approve` + `policy.gate_satisfied`
  (`src/ariadne_engine/contracts.py`, `policy.py`).
* `advance` and `prepare_next` ask `policy.g1_problems(state, project)`; `record_acceptance`
  asks `policy.gate_satisfied(state, "G3", policy.review_subject(...))`.
* `approve-gate` is the only writer of an approval and only records on the `human-cli`
  channel; the engine refuses any other channel, a missing identity, a gate it does not
  enforce, a subject type that does not belong to the gate, and a duplicate for the same
  revision.
* Document fields remain human-readable mirrors written *after* approval; the runtime no
  longer reads them for enforcement. `handoff_context_problems`' mirror check is unchanged
  (it is a consistency check on a human artifact, not an authorization input).

**Adversarial tests.** `security.gate-forgery-in-agents-md` (original reproduction, now
passes: "G1 was not accepted from project documents; recorded approvals=0"),
`security.migrated-legacy-gate-refused` (a migrated legacy run whose documents claim G1
gets `approvals=0` and must re-obtain the gate), `lifecycle.approval-channel-required`
(a hand-written `worker-cli` record leaves G1 unsatisfied), `lifecycle.approval-stale-after-edit`
(approve then edit the thesis), `security.approval-wrong-target-refused` (G1 approval does
not satisfy G2, does not bind the handoff target, does not travel to another revision),
`security.acceptance-after-review-and-single-use` (G3 approval is spent by the accepted
outcome and cannot be replayed), `security.review-record-required` (acceptance without a
review record).

**Remaining risk.** An approval records the *channel* the operator surface used; it does
not prove a human typed the command. A process with file-write access can write an
`approvals` entry directly into `ariadne-run.json` — it would then have to forge a valid
subject type, the current revision fingerprint, a human channel, an unused approval id and
a fresh timestamp, which is detectable in review but not cryptographically prevented. That
is the machine-boundary step AR-200 identified; AR-201 removes the *ordinary worker flow*
that wrote the approval field itself. Recorded here rather than claimed as solved.

## Defect 2 — `security.creative-gate-bypass`

**Original case.** At S3 with a locked direction and no recorded creative evidence,
compare three continuation paths: `advance` without a stage result, `advance` after
recording one, and `prepare-next`.

**Baseline behaviour.** The un-recorded path was refused (`exit 2`) while the other two
prepared S4A (`exit 0`): the creative-evidence requirement lived inside
`advance`'s "no stage evidence" branch, so recording the stage result first skipped it.

**Root cause.** Path-dependent policy: the check was a branch of one entry point
(`ariadne.py:advance`, the `if not stage_has_evidence(packet)` block) instead of a
precondition of the transition. `prepare_next` had no creative check at all.

**Affected entry points.** `advance` (S1/S2/S3/S4A creative branches) and `prepare_next`
(no check), plus any future caller of either.

**Fix.** `policy.creative_evidence_problems(state, project)` is the one implementation,
and `policy.continuation_problems(state, "S4A", project=...)` includes it next to the G1
approval check. Both `advance` and `prepare_next` consult that set before a transition, so
all three paths refuse with the same reason. The `advance`-only nudges at other stages were
removed rather than duplicated, leaving one rule applied everywhere (I-9).

**Adversarial tests.** `security.creative-gate-bypass` (all three paths now `exit 2`,
consistent), `design.unsupported-claim-blocks-g1` and
`lifecycle.s3-blocks-without-human-g1` (unchanged verdicts: an unsupported claim still
blocks the G1 request), `lifecycle.g1-locked-prepares-s4a` (a workflow-complete direction
still reaches S4A, so the stricter rule is not a blanket refusal).

**Remaining risk.** The later-stage creative skills (S4A implementation planning, S4B QA)
are still checked by `creative-check`/`operations-check` rather than by the S4A→S4B and
S4B→S5 transitions; AR-201 unified the direction boundary that the defect exposed. AR-202
should extend the same precondition set to those boundaries (listed in `07-AR-202-HANDOFF.md`).

## Defect 3 — `security.review-attestation-unverified`

**Original case.** Ingest a review judgement whose independence claim is written by the
same actor, and a control without the claim; the attested one was accepted and the
unattested one refused — the only enforced difference was a self-written text field.

**Baseline behaviour.** `ingest-review` required the `**Reviewed independently:** yes`
line, which the implementer writes in its own response. Independence was an attestation,
not evidence.

**Root cause.** The review had no actor identity of its own: `ingest_review` copied a
marked block and set `worker["review_state"] = "REVIEWED"` without recording who reviewed,
what revision was reviewed, or which evidence the reviewer had.

**Affected entry points.** `ingest_review` (acceptance of the judgement),
`record_acceptance` (which trusted `review_state` and the review file's existence).

**Fix.** `src/ariadne_engine/review.py`:
* `independence_problems(state, reviewer_identity)` requires a recorded identity that is
  not one of the implementation worker's recorded identities (`worker_role`, `provider`,
  `model`, `task_id`, `identity`).
* `build_record` binds the review to the S5 packet id, its `packet_sha256`, the judgement
  digest, the reviewer identity and the validated revision, validates it and stores it both
  in `state["reviews"]` and as `evidence/review-record.json`.
* `review_evidence_problems(..., kind)` enforces a distinct evidence set per review kind
  (experience vs technical).
* `record_acceptance` requires `policy.review_subject(...)` (i.e. the record) and the G3
  approval bound to that revision; a hand-written judgement file cannot grant either.

**Adversarial tests.** `security.review-attestation-unverified` now compares four variants
in one sandbox — no identity (refused), the implementer's own identity `bulk` (refused),
the same block with the attestation removed (refused), and an independent identity
(accepted, with the record inspected) — `security.review-record-required` (a convincing
judgement file plus no record refuses both the gate and acceptance),
`security.acceptance-after-review-and-single-use` (the positive path and the replay
refusal), and `suite.engine-core`'s review checks (evidence sets, overwrite refusal,
NOT_PERFORMED reporting).

**Remaining risk.** The reviewer identity is operator-supplied text, like the approval
identity: the engine records and binds it, it does not verify a person. A worker that knows
the recorded worker identities can claim a different one. Making independence
machine-verifiable (separate execution identity, signature or provider attestation) belongs
to the AR-202/machine-boundary work.

## Cross-cutting failure scenarios

| Scenario | Behaviour in AR-201 | Evidence |
|---|---|---|
| Stale state (revision A approved, workspace moves to B) | the approval fingerprint is re-derived at check time; a mismatch names staleness and refuses | `lifecycle.approval-stale-after-edit` |
| Partial operation (intermediate record written, then failure) | transitions are validated before any mutation and persisted atomically after; a refusal changes no field | `lifecycle.invalid-transition-refused`, `suite.engine-core` |
| Interrupted persistence | atomic replace keeps the previous state; a leftover temp file is reported, never applied | `lifecycle.recovery-reports-interrupted-work` |
| Duplicate operation | a single-use approval records `consumed_by` and a replay is refused; packet and review evidence refuse overwrite | `security.acceptance-after-review-and-single-use`, `security.evidence-not-overwritable` |
| Forged worker output | a structured return is classified but never validates itself; a review must be a record; acceptance needs the human approval | `security.review-record-required`, `lifecycle.independent-validation-executes` |
| Incompatible legacy state | readable-but-old states are refused until `--migrate`; migration invents no approval | `security.migrated-legacy-gate-refused`, `lifecycle.schema-migration-explicit` |
