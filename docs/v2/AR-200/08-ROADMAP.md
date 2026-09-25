# AR-200 / 08 — REFINED ROADMAP

Changes from the brief's candidate milestones, with reasons:

- **AR-202 split kept** (adaptive routing/recovery vs design intelligence), because design intelligence depends on nothing in AR-202 and would otherwise block it.
- **One milestone added: AR-201B is not needed.** The handoff is folded into AR-201 because the first vertical slice must already exercise a complete lifecycle including a human gate and an independent validation — deferring gates to AR-203 would let the two confirmed authorization defects survive another milestone.
- **Independent verification hardening (AR-203) stays after AR-202** but its *invariant tests* are written in AR-201 (a case may be written and left failing; the fix is AR-203).
- **AR-204 (performance) stays last before release prep** because no profiling exists yet and optimisation without measurement is the overengineering risk 07 §1 names.
- **AR-205 absorbs the distribution rename and signing decisions** (04 §E D1/D6) as explicit, out-of-scope-for-now items.

Dependency chain: `AR-201 → AR-202 → AR-202D → AR-203 → AR-204 → AR-205`.
AR-202D may run in parallel with AR-202 (it touches `design/` and the creative ledgers, not the execution core), provided the transition choke point from AR-201 is already in place.

---

## AR-201 — Executable orchestration core (first vertical slice)

**Objective.** One complete, deterministic task lifecycle executed by the engine itself, with gates and validation that cannot be satisfied by the actor under test.

**Dependencies.** None (starts from `5819dae`). Requires AR-200 acceptance.

**Scope (exact).**
1. `src/ariadne_engine/contracts.py`, `statemachine.py`, `policy.py`, `persistence.py`, `api.py` — created by *moving* existing logic:
   - transition table + `apply_transition` (from `scripts/ariadne.py:3265-3536` guards; table shape from Boreal `model.py:59-69`);
   - `Approval` records + `gate_satisfied` (replacing `ariadne.py:905-915`, `2810`, `3363-3365`, `3498`);
   - `readable_schemas` + migration hook in `load_state` (`ariadne.py:261-271`) — H5;
   - Python API wrapping exactly the existing CLI operations.
2. `scripts/ariadne.py` keeps its 26 subcommands and exit codes but delegates policy/state to the new modules. **No user-visible behaviour change other than the two hardened gates.**
3. Benchmark: the three failing security cases must flip to `pass`; all 45 currently passing cases must stay passing; new cases for I-3, I-4, I-9, I-10.

**Explicitly out of scope.** Transactions, rollback, rendered QA, live providers, routing enforcement, recovery of interrupted transactions, distribution changes, any file move of `scripts/*`.

**Acceptance tests (all must pass).**
- `security.gate-forgery-in-agents-md` → pass (agent-written documents cannot satisfy G1).
- `security.creative-gate-bypass` → pass (identical preconditions on every path).
- `security.review-attestation-unverified` → pass (independence bound to evidence).
- `lifecycle.*` (16 cases) → pass, unchanged.
- New: `lifecycle.approval-stale-after-edit` (approve G1, edit `DESIGN.md`, expect refusal), `lifecycle.approval-channel-required` (a worker-channel approval cannot satisfy a gate), `lifecycle.migration-readable-schemas` (a v1 state file loads under a v2 reader with a recorded migration), `lifecycle.invalid-transition-refused` (direct illegal stage jump refused by the choke point).
- `suite.*` (14 cases) → pass or declared-skip, unchanged.
- `suite.repo-contract` and `suite.repo-self-test` → pass (no documentation drift).

**Evidence required for completion.** Benchmark result document with 0 `fail` and 0 `error` among executable cases; the diff of every moved function showing behaviour preserved; a written statement of the exact state-file schema change and its migration; confirmation that no original checkout or Boreal file changed.

**Risks.** Schema migration touching existing runs (mitigate: `readable_schemas`, backup, refusal-by-default for unknown fields); accidental CLI behaviour change (mitigate: existing suites + `check.py` contract); over-large first slice (mitigate: the five modules only).

---

## AR-202 — Adaptive context, routing and recovery

**Objective.** Cut unnecessary context and unnecessary model calls, and make routing and recovery decisions executable rather than advisory.

**Dependencies.** AR-201 (policy + state must be authoritative).

**Scope.**
1. Context HARDEN H4: content-addressed digest cache; memoised packet verification per command; operator-visible omission report.
2. Routing HARDEN H7: strategy selection consults `adapters/reasoners.json` capability classes and `references/capabilities.json`; override only as a recorded human intervention. Provider/model identity H6: requested-vs-reported comparison with explicit "no report ⇒ not verified".
3. Recovery H9: orphan packet, interrupted evidence write, interrupted state write; typed report; never invents success.
4. Telemetry H11: optional provider-reported usage aggregation and a per-run summary; `unknown` preserved.
5. Benchmark: add the 12 runtime-backed cases (needs an operator-authorized provider budget) and the `perf.verify-packet-cache` measurement.

**Acceptance tests.** New: `routing.design-capability-enforced`, `routing.identity-mismatch-recorded`, `routing.unavailable-model-refused-before-state`, `recovery.orphan-packet`, `recovery.interrupted-evidence`, `perf.verify-packet-cache` (must show a measured reduction, or be dropped), `context.omission-report`. All AR-201 cases must remain green.

**Evidence.** Before/after measurements for the cache; a routing decision record for each of the 9 routing scenarios; recovery transcripts from a deliberately killed process.

**Risks.** Cache invalidation producing stale evidence (mitigate: cache is read-only acceleration; hash comparison always runs on the *decision* path). Model-backed costs (mitigate: operator-authorized budget, ≥5 repeats, no ranking from one run).

**Out of scope.** Live agent adapters, decomposition, parallel execution, distribution.

---

## AR-202D — Design intelligence

**Objective.** Turn the design ledgers into an evidence-driven subsystem: provenance with retrieval, component evaluation, rendered QA with an offline-capable instrument, and bounded refinement.

**Dependencies.** AR-201 (evidence/approval binding). May run parallel to AR-202.

**Scope.** Implement 05-DESIGN-INTELLIGENCE.md: the 5-state provenance extension (ledger schema 3 with the existing dual-read pattern), `ReferenceAdapter` + local/project/approved-url adapters (X6), evaluation records + registry freshness enforcement (H8), requirement↔decision closure checks, the rendered-QA interface with a deterministic fixture capture adapter, and bounded refinement with regression re-runs. No browser dependency, no paid service, no installation.

**Acceptance tests.** `design.reference-fetch-provenance`, `design.inaccessible-honesty` (must fail on a fabricated observation), `design.component-compatibility`, `design.requirement-tracking`, `design.rendered-inspection` (fixture adapter, offline), `design.refinement-bounded`, `design.no-self-verification`. Existing design cases stay green; `creative-intelligence.py` self-test (46) and `creative-operations.py` self-test (34) stay green under the new schema.

**Evidence.** Ledger fixtures at schema 3 with v2 readable; provenance transitions each with their evidence artifact; a refinement transcript showing one defect fixed with a regression re-run.

**Risks.** Schema drift breaking existing ledgers (mitigate: versioned dual-read, never rewrite in place); scope explosion (mitigate: adapters are opt-in and disabled by default).

**Out of scope.** Real browser automation, paid reference services, publishing, social-execution automation.

---

## AR-203 — Independent verification hardening

**Objective.** Make every acceptance claim bound to evidence produced outside the actor under test, and make false acceptance measurable.

**Dependencies.** AR-201 (approvals/transitions), AR-202 (identity + recovery).

**Scope.** Review execution path with reviewer identity and session evidence (R3); fingerprint-pair validation (X4); false-acceptance measurement (seed a worker claim that contradicts the validator and assert rejection); repair-budget/escalation accounting; evidence provenance completeness (every acceptance cites approval id + validation id + review id + artifact digests).

**Acceptance tests.** `runtime.validation-false-claim` (must reject), `runtime.review-execution` (real reviewer, distinct identity), `verification.false-acceptance-count == 0` across the full deterministic suite, `lifecycle.acceptance-requires-review-and-gate` (already passing) plus `lifecycle.acceptance-cites-all-evidence`.

**Evidence.** Validation records with command hashes and fingerprint pairs; review records with identity; a false-acceptance report over the whole suite.

**Risks.** Reviewer impersonation inside one OS user account (documented residual; not solvable at this layer).

**Out of scope.** OS sandboxing, signing infrastructure, multi-user identity providers.

---

## AR-204 — Performance optimisation

**Objective.** Remove measured waste without weakening any invariant, and publish the measurement.

**Dependencies.** AR-202 (cache groundwork), AR-203 (measurement must exist before optimisation is claimed).

**Scope.** Profile the hot paths with evidence: repeated repository traversal, `verify_packet` cost on large projects, packet build cost, validation overhead, recovery cost. Add exclusions/rules and revision-aware caching only where a measurement justifies it. Publish before/after numbers for each change and keep a regression guard case per optimisation.

**Acceptance tests.** Each optimisation ships with a benchmark case that fails without it and a case that proves the invariant still holds (`perf.*` plus the corresponding `security.*`/`context.*` case). No optimisation may reduce a security or evidence check.

**Evidence.** Profile captures, before/after timings on the frozen fixture, and a statement of what was deliberately *not* optimised.

**Risks.** Optimising by weakening verification (mitigate: the mitigation list is normative — any change that removes a hash comparison is rejected).

**Out of scope.** Distribution changes, multi-process execution.

---

## AR-205 — Integration and release preparation

**Objective.** Make v2 adoptable: stable-enough contracts, compatibility statements, and release decisions taken deliberately.

**Dependencies.** AR-201…AR-204.

**Scope.** Freeze documented stable surfaces (03 §10); publish a compatibility matrix (v1 projects, run states, ledgers, installed runtimes, release manifests); version negotiation for adapters; the `ariadne` rename decision (D1) with a migration plan or an explicit "not now" with rationale; release-signing decision (D6); distribution integrity hardening H10; adoption guide for Boreal (adapter contract, translator, incremental rollout); no push, tag or publish without explicit human authority.

**Acceptance tests.** Compatibility suite: read a v1.6.7 project and run state without modification; migrate an older run state explicitly and reversibly; install/repair/rollback/doctor/uninstall on a clean machine fixture; adapter contract tests against a fixture Boreal-shaped client.

**Evidence.** The compatibility matrix with a test per row; an update/rollback transcript; a statement of every irreducible incompatibility.

**Risks.** Committing to a stable API before compatibility testing (mitigate: the API stays provisional until this milestone's tests exist).

**Out of scope.** Publishing, tagging, announcing, or any remote action — those remain human-only.

---

## Release criteria for v2 as a whole

1. Zero `fail`/`error` in the deterministic benchmark at the release commit.
2. Every invariant in 03 §6 has a passing case that can fail.
3. No acceptance path can be satisfied by the actor under test (proven by the false-acceptance report).
4. Model-backed results are reported as ranges over ≥5 runs, with the exact provider/model/version recorded.
5. v1.6.7 projects, run states and ledgers remain readable; every migration is explicit, recorded and reversible.
6. Public v1.6.7 artifacts are unchanged; the rename/signing decisions are documented either way.
7. No claim in v2 documentation lacks an evidence level and a source.
