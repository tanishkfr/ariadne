# AR-203 — Milestone Report

Milestone: **AR-203, Verification Hardening & Decision Plane Foundation**.
Base: AR-202D-H closure `03fd9a4df9b8e2057d31cb929490103d4155e7ec`
(`v2/ar-202d-hardening`). Branch: `v2/ar-203-verification-hardening`.
Version file unchanged at `1.6.7`. No push, no tag, no release, no publication,
no remote modification. Boreal untouched.

## 1. What the milestone answered

> How does Ariadne know that the thing it says happened actually happened,
> through the execution, capability, reviewer and evidence path it claims?

By making five concepts that used to collapse into one another executable and
testable:

```text
DECISION ≠ AUTHORIZATION ≠ EXECUTION ≠ VERIFICATION ≠ ACCEPTANCE
```

* **Execution.** Identity facts carry claim levels; requested never becomes
  observed; provider observation is a separate, engine-side channel; an execution
  used as provenance must be an engine-created record in this run.
* **Capability.** Declared, available, exercised and verified are distinct
  registry states with real obligations; routing policy is explicit and recorded.
* **Review.** Independence is bound to two different engine executions and
  recorded as a level computed from observed facts, never labels.
* **Verification.** One record family answers what claim, by which execution,
  against which evidence, revision and dependencies, at which level, with what
  remains unverified — and freshness is dependency-specific.
* **Acceptance.** Untouched. No decision, verification or confidence grants a
  gate, a scope, an acceptance or a release.

## 2. What was implemented

| System | Source |
|---|---|
| Execution provenance and identity claim levels | `src/ariadne_engine/provenance.py` |
| Live capability registry and offline probes | `src/ariadne_engine/capabilities.py` |
| Verification records, levels, freshness | `src/ariadne_engine/verification.py` |
| Rendered-verification binding and currentness | `src/ariadne_engine/render.py` |
| Reference retrieval verification and origin honesty | `src/ariadne_engine/references.py` |
| Decision Plane (contracts, providers, policy, batches) | `src/ariadne_engine/decisions/` |
| Bounded failure classification (first real use) | `src/ariadne_engine/execution.py` |
| Economics telemetry seam | `src/ariadne_engine/execution.py` |
| Capability-evidence routing policy | `src/ariadne_engine/routing.py` |
| Execution-bound review independence | `src/ariadne_engine/review.py`, `critique.py` |
| Vocabularies, validators, collection bounds | `src/ariadne_engine/contracts.py` |
| Event vocabulary (14 types) | `src/ariadne_engine/events.py` |
| Collections and contract markers | `src/ariadne_engine/persistence.py` |
| API operations and engine wrappers | `src/ariadne_engine/api.py` |
| CLI: `capabilities`, `verify`, `decide`, `provenance`, `design-plan --evidence-policy` | `scripts/ariadne.py` |
| Engine suite: `ar203_checks` (84 checks) | `scripts/test-engine-core.py` |
| Benchmark: 33 cases in 7 groups | `benchmarks/arbench/ar203_cases.py` |
| Documentation: 11 documents | `docs/v2/AR-203/` |

New modules: 5. New record families: 4. New dependencies: 0.

## 3. The intelligence hierarchy, now enforced

```text
Layer 1  deterministic computation   hashes, counts, revision comparison, path scope,
                                     authorization, exit codes, artifact existence,
                                     required-evidence presence
Layer 2  decision intelligence       bounded judgement with a closed answer space,
                                     explicit confidence provenance, risk-adjusted policy
Layer 3  generative intelligence     creation, repair, synthesis, exploration
Layer 4  verification                what actually occurred, independently established
Layer 5  human control               protected choices stay human
```

The first real Layer 2 use is failure classification: code first, bounded
judgement only for unmapped sources inside a safe class subset, deterministic
fallback of `UNKNOWN` + escalation, and a decision record either way.

## 4. Security invariants

All previous invariants are preserved. AR-203 adds and tests:

| # | Invariant | Test |
|---|---|---|
| 26 | Requested identity does not equal observed identity by default | `execution-provenance.requested-and-observed-stay-distinct` |
| 27 | Worker prose cannot replace engine execution provenance | `execution-provenance.worker-prose-cannot-replace-observed` |
| 28 | Declared capability is not verified capability | `capability-registry.declared-is-not-verified` |
| 29 | Review independence is bound to executions, not labels | `review-independence.execution-bound-not-label-bound` |
| 30 | Verification evidence is revision/currentness-bound | `render-verification.changed-capture-parameters-invalidate` |
| 31 | Re-hashing a declaration does not constitute reproduction | `render-verification.reproduction-must-be-a-new-artifact` |
| 32 | A bounded decision cannot authorize a protected operation | `decision-plane.cannot-authorize-a-protected-action` |
| 33 | Confidence provenance must remain explicit | `decision-plane.confidence-provenance-preserved` |
| 34 | Self-reported confidence is not calibrated confidence | `decision-plane.confidence-provenance-preserved` |
| 35 | Decision type validity is not correctness | `decision-plane.invalid-answer-refused-not-coerced` |
| 36 | Decision records do not prove downstream side effects | `decision-plane.valid-choice-decision-recorded` (`acted_on` false) |
| 37 | Stale verification does not satisfy a current requirement | `false-acceptance.stale-passing-evidence-does-not-close` |
| 38 | Unknown identity/capability/confidence remains unknown | `execution-provenance.requested-and-observed-stay-distinct` |

## 5. False-acceptance testing

Six dedicated adversarial cases plus the adjacent groups attempt fabricated
success through real surfaces: fabricated execution ids, worker runtime claims,
self-attested verification, stale passing evidence, orphan results, recovery of
ambiguous states, CLI/API divergence. All are refused. The full adversarial pass
(15 attacks) is recorded in `06-FALSE-ACCEPTANCE.md` §2; no genuine bypass was
found, and two hardening repairs that emerged during implementation are recorded
as ADR-003 and ADR-004.

## 6. Deviations and honest limitations

* `render.verify` now requires `reproduced_artifact`; two engine-core fixtures
  were updated to create real capture/verification executions and a real
  re-produced artifact. No assertion was weakened; three assertions were added.
* `MIN_EVIDENCE_BY_CONSEQUENCE["LOW"]` is "no evidence level required" rather than
  `DECLARED`, because a `DECLARED` floor would have required inventing a
  verification level for projections that carry none.
* Reference retrieval verification uses an `observed_anchor` because the original
  retrieval is adapter-supplied; the verifier is still an engine execution.
* The run-state writer is the trust boundary: a caller who writes
  `ariadne-run.json` directly can fabricate a record. Cryptographic process
  attestation is `NOT_EXECUTED` and not implied.
* No live provider was called. Live capability evidence and measured usage remain
  `DECLARED`/`UNKNOWN`; the usage fields exist but are unpopulated.
* No mutation of Boreal, no remote action, no paid service, no new dependency.

## 7. Results

* Benchmark: **190 cases** (157 preserved + 33 new), 0 FAIL, 0 ERROR.
* Engine core: **330 checks** (246 preserved + 84 new), all passing.
* All previously green repository suites re-run green; exact commands and counts
  in `08-TEST-RESULTS.md`.
* Mutation testing: five critical protections broken in memory, each confirmed by
  a failing test, each restored byte-exact.

## 8. Closure

All twenty-five completion criteria are satisfied; the criterion-by-criterion
statement is in `08-TEST-RESULTS.md` §7. AR-204 starts from the AR-203 closure
commit with `10-AR-204-HANDOFF.md`.

## 9. Git state

| | |
|---|---|
| Worktree | `<path>` |
| Branch | `v2/ar-203-verification-hardening` |
| Base | `03fd9a4df9b8e2057d31cb929490103d4155e7ec` (`v2/ar-202d-hardening`, frozen) |
| Implementation commit | `c3a5e37` — engine, CLI, API, engine checks, benchmark cases and manifest |
| Documentation commit | `65d768c` — the eleven AR-203 documents and the benchmark result artifacts |
| Closure addendum | this section's commit; `git log -1` reports the tip |
| Remote actions | none: no push, no tag, no release, no publication |
| Status | clean at closure (no untracked or modified files) |

Boreal was not accessed, modified or tested. No paid provider was called. No new
dependency was added.
