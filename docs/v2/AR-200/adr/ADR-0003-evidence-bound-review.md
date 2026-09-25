# ADR-0003 — Independent review is bound to evidence, not an attestation

Status: accepted (AR-200) — drives AR-201 T5
Deciders: AR-200 audit
Evidence: 01-BASELINE.md §7 defect 3; 06-BENCHMARKS.md (`security.review-attestation-unverified` = fail)

## Context
`ingest_review` accepts any file whose marked block contains `**Reviewed independently:** yes`, valid headings, the required fields and an allowed recommendation. Nothing records who reviewed, in what session, or with what context. A benchmark case proved that removing that single line is the only enforced difference between an accepted and a rejected review. Boreal's engine is more honest (it stores `asserted-caller-not-verified`) but no more verified.

## Decision
A review verdict must carry: `reviewer_identity` (distinct from the worker identity recorded in run state), `review_session_evidence` (an artifact produced outside the build workspace, hashed), and `context_digest` (the sha256 of the S5 packet actually delivered). `ingest_review` refuses when the identity matches the worker's, or when the context digest does not equal the current S5 packet hash. The existing structural checks and the attestation line stay as secondary, non-sufficient signals.

## Alternatives considered
- **Keep the attestation and rely on process discipline.** Rejected: the point of the engine is to make the honest path the enforced path.
- **Require a signed review artifact.** Rejected for AR-201: key management is a distribution decision (ADR-0006 scope). Hashed identity + digest binding closes the demonstrated gap at near-zero cost.

## Consequences
- S5 remains structurally isolated (already proven by `lifecycle.s5-isolation`); the verdict is now bound to that isolation.
- A same-machine reviewer can still be impersonated by anything with write access; documented as residual risk, not a solved problem.
- Any future reviewer adapter must supply the identity field, not infer it.
