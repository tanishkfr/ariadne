# AR-224 Architecture Freeze

AR-224 reuses AR-220 through AR-223 without redesigning them.

## AR-220 — Grounded references / ReferenceSet

`src/ariadne_engine/design_reference`: inspect project-local, decide external
usefulness, search getdesign, fetch via safety+transports, normalize to
DesignReference, build ReferenceSet with roles/counter/diversity/budget,
observe patterns, ground direction, provenance, explicit G1D approval gate.

## AR-221 — Grounded design execution

`src/ariadne_engine/design_execution`: frozen ReferenceSet in, grounded
candidate, refusal-without-approval probe, explicit approval,
DesignImplementationPlan, component inventory+reuse, worker packet+omission
record, scripted edits, implement-validate-bounded-repair-escalate,
provenance+trace. Ends at MECHANICALLY_VALIDATED.

## AR-222 — Rendered evidence / critique / refinement

`src/ariadne_engine/rendered_critique`: exact source binding, bounded capture
plan, real Chromium render via local server, rendered evidence, independent
critique in an isolated reviewer packet, bounded refinement, mechanical
re-validate, re-render, re-critique with defect continuity, proof readiness
(COMPLETE/INCOMPLETE only, no verdict), trace.

## AR-222D — Specificity, sources, provenance, interruption, harness

Design Specificity Grammar, 36-entry source registry with role/capability/
access/auth/paid/reuse/terms/verification-date/enabled-reason, proof-ready
provenance, Minimal Creative Interruption (G1D is the principal interruption),
shared mutation ledger with transactional restore, test-inventory floors.

## AR-223 — Contracts, requirements, claims, evidence, verification, acceptance

`src/ariadne_engine/acceptance`: immutable contracts, requirement identity with
per-requirement evidence policy, worker claims that are never evidence,
requirement-bound evidence with freshness, six verdicts
(PROVEN/PARTIAL/UNPROVEN/FAILED/CONTRADICTED-claim-only/NEEDS_HUMAN),
selective invalidation/re-verification, Beacon mixed-verdict Proof Pass,
406-case reviewed corpus, calibration/promotion/scheduler with
authorization_effect none.

## AR-224 rule

Public interfaces delegate into these systems. No duplicated semantics.
No second QA engine. No weak-family promotion to make numbers look better.
