# AR-201 — 07 AR-202 HANDOFF

Precise handoff for the next milestone (adaptive context, routing and recovery). Everything
below is grounded in what AR-201 actually implemented; nothing here is claimed to exist yet.

## 1. What AR-201 leaves in place (the base AR-202 builds on)

* `src/ariadne_engine/contracts.py` — versioned records with declared-field fingerprints
  (`REVISION_FIELDS`, `digest_fields`), `Subject`, `Approval`, `TransitionRequest`,
  `ReviewRecord`, typed errors, `EngineError` hierarchy.
* `src/ariadne_engine/statemachine.py` — `STAGE_TRANSITIONS`,
  `WORKER_LIFECYCLE_TRANSITIONS`, `apply_transition` (the only writer of protected fields),
  `worker_transition_for`, and `state["transitions"]` as the audit trail (bounded at 50).
* `src/ariadne_engine/policy.py` — `continuation_problems(state, target, project)` as the
  single precondition set for a stage transition, `gate_satisfied` with binding and
  single-use consumption, `approve`, `repair_allowed`, `retry_problems`, `bind(...)` for
  injected tool modules.
* `src/ariadne_engine/persistence.py` — `load_state`/`write_state` (atomic),
  `recovery_report`, `migrate`/`migrate_file` with preserved backups and history.
* `src/ariadne_engine/review.py` — evidence-bound review records, per-kind required
  evidence, independence checks.
* `src/ariadne_engine/api.py` — `Result`/`format_result` and the operation surface the CLI
  delegates to.
* `scripts/ariadne.py` — all commands unchanged, delegating protected parts;
  `ENGINE_API`, `POLICY`, `REVIEWS`, `STATEMACHINE`, `CONTRACTS`, `PERSISTENCE` exposed.
* Benchmark harness: 61 deterministic cases, `benchmarks/manifest.json`,
  `benchmarks/results/LATEST.json`; fixture helpers `lock_g1`, `record_g1_approval`,
  `record_g3`, `ingest_independent_review`, `establish_creative_plan`,
  `record_direction_evidence`.
* `scripts/test-engine-core.py` — 73 checks covering contracts, transitions, persistence,
  policy, review and the API; run it before and after every change.

## 2. Starting point for the next milestone

**First action:** branch from the AR-201 tip (`v2/ar-201-core`) into `v2/ar-202-*` in its own
worktree; the AR-201 worktree then becomes a frozen comparison baseline like AR-200's.

**Immediate AR-202 backlog, in dependency order:**

1. **Extend the precondition set to the remaining boundaries.** Add the S4A→S4B and S4B→S5
   creative/operations evidence to `policy.continuation_problems` (the current-stage skills
   and `operations.project_problems`). This is the deliberate AR-201 limit: only the
   S3→S4A boundary was unified because that is where the defect lived. The deep fixtures
   already build workflow-complete ledgers, so the change is testable with the existing
   helpers (`record-creative`, `record-operations`).
2. **Adaptive context and routing.** AR-201 added no context or routing behaviour. The
   seams to build on: `state["provider_preflight"]` and `policy.preflight_problems` (the
   S4B precondition), `reasoners.py` selection (`select_reasoner`, `record_reasoner_failure`
   already continue through `prepare_next` and therefore through the choke point), and
   `state["transitions"]` for the history a router would need. Keep routing decisions
   *recorded* (a decision is evidence), not implied by a run's shape.
3. **Recovery beyond reporting.** `persistence.recovery_report` reports
   `orphan-packet`/`missing-packet`/`interrupted-write` and never repairs. AR-202 should
   add an explicit, operator-invoked recovery operation that resolves a divergence (adopt
   with a recorded justification, or discard into a quarantine path), routed through
   `apply_transition` so recovery itself is a legal, audited transition. Do not let recovery
   infer success: an adopted packet must carry the operator identity and the evidence that
   justified adoption.
4. **Machine-verifiable identity.** Replace or augment the operator-supplied
   `identity`/`reviewer_identity` strings with a verifiable execution identity (signed
   approval record, provider attestation, or a separate execution context the implementer
   cannot enter). Keep the existing fields as provenance; do not weaken binding.
5. **Context-engine work.** AR-200's extraction plan lists the context engine as a later
   milestone. Relevant AR-201 facts: canonical vs project vs conditional sources are still
   assembled by `prepare-stage.py` (`resolve_sources`, `omitted_conditionals`), packet
   `packet_sha256` is the review/approval binding input, and AR-201's record schema gives a
   place to record what was delivered without changing the packet format.
6. **Review enforcement hardening.** `review.independence_problems` compares recorded
   identities only. AR-202 should bind the reviewer to the *execution* that produced the
   judgement (transcript hash, session identity), and should let a run require a technical
   review as well as an experience review (`review.REVIEW_KINDS` and `REQUIRED_EVIDENCE`
   are already parameterised for this).

## 3. Constraints carried forward

* Do not change the run-state file schema version without a backward-compatible reader plan;
  AR-201 proved the published runtime hard-refuses anything but `1`
  (`docs/v2/AR-201/03-MIGRATION.md` §1).
* Do not add a dependency, a network call or a paid model call to the deterministic path.
* Keep one implementation of each rule: extend `policy.continuation_problems` rather than
  adding a check to one command.
* Every new precondition needs a negative case and a workflow-complete positive fixture;
  the AR-201 fixture helpers exist so a positive path does not have to hand-write documents.
* The transition table is the contract: if a new legitimate move exists, add it to
  `statemachine.py` explicitly rather than bypassing `apply_transition`.

## 4. Known-good commands for the next session

```
python scripts/test-engine-core.py                 # 73 engine checks
python scripts/ariadne.py --self-test              # 125 runtime checks
python scripts/prepare-stage.py --self-test        # 50 transport checks
python scripts/check.py                            # repository contract
python scripts/test-distribution.py                # 55 distribution checks
python benchmarks/run_benchmarks.py --label <name> # 61 deterministic cases
python benchmarks/run_benchmarks.py --write-manifest
```

## 5. Open questions AR-201 did not answer

1. Should a gate approval expire by time as well as by revision? AR-201 binds approval to
   revision and to a single consuming operation; no expiry field exists.
2. Should `record_acceptance --outcome rejected` also consume the G3 approval? Today only
   acceptance consumes it, so a rejection leaves the approval reusable for a later
   acceptance of the same revision. That is deliberate but worth a decision in AR-202.
3. Should the operator log (`OPERATIONS.md`) and `worker-telemetry.jsonl` become one
   append-only event log? AR-201 writes both (a migration records in both) and did not
   unify them.
