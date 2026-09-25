# AR-203 — Architecture decision records

The durable decisions AR-203 took, with the alternatives that were rejected.
Every record cites the code that enforces the decision and the tests that would
catch its reversal.

---

## ADR-001 — Identity claim levels are explicit per field

**Context.** AR-202 kept `requested`, `reported` and `observed` as separate
fields, but a consumer still had to infer which field was trustworthy and whether
`requested model = X` meant "X ran". The AR-203 brief requires requested and
observed identity to remain distinct, with `UNKNOWN` preserved.

**Decision.** Every identity fact carries the level that established it
(`REQUESTED`, `ENGINE_CREATED`, `RUNTIME_OBSERVED`, `PROVIDER_OBSERVED`,
`VERIFIED`, `UNKNOWN`), resolved per field by `provenance.identity_claims`. A
worker claim never raises a level; when it differs from the resolved value it is
preserved as `worker_claim`.

**Alternatives rejected.**

* *A single `identity_source` field per execution.* It cannot express that
  provider is `RUNTIME_OBSERVED` while model is `UNKNOWN`, which is the normal
  case.
* *Promoting `requested` to `observed` when no observation exists.* That is the
  exact fabrication AR-203 exists to prevent.
* *Trusting the worker's report when it matches the request.* Agreement is not
  observation.

**Enforced by** `provenance.identity_claims`, `execution.identity_view`.
**Tested by** `execution-provenance.requested-and-observed-stay-distinct`,
`execution-provenance.worker-prose-cannot-replace-observed`.

---

## ADR-002 — Provider observation is a separate channel written only by engine-side observers

**Context.** A model adapter that really reports the model it ran is the strongest
runtime-available evidence of identity, but a worker's prose can claim the same
thing. AR-202's `reported` field could not distinguish them.

**Decision.** Add `provider_observed` on the execution record, written only by
`provenance.record_provider_observation`, which refuses sources naming worker
output. The raw observation and the observer are preserved. `execution.report`
stays the worker channel.

**Alternatives rejected.**

* *Let the adapter write `reported`.* Then worker prose and adapter evidence share
  a field and no consumer can tell them apart.
* *Verify provider identity by calling the provider again.* A paid call to
  re-check identity is out of scope, and re-asking is not proof either.
* *Drop `reported` entirely.* The worker's claim is still evidence of what the
  worker believes and is useful for mismatch detection.

**Enforced by** `provenance.record_provider_observation`,
`provenance.verify_observation_chain`, `contracts.capability_record_problems`
(worker-source refusal). **Tested by**
`execution-provenance.worker-prose-cannot-replace-observed`, engine-core
`worker output cannot write the provider-observed channel`.

---

## ADR-003 — Rendered verification requires the re-produced artifact, not a digest

**Context.** AR-202D's `render.verify` accepted `reproduced_sha256` from the
caller. A caller could pass the captured digest without re-producing anything, so
"independent re-production" was an assertion. AR-203 requires that hashing an
externally declared artifact is not independent reproduction.

**Decision.** `render.verify` requires `reproduced_artifact` (a path the engine
re-hashes) and requires that path to differ from the captured artifact. The
capture execution and the verifying execution must both be engine-created records
and must differ. A verification record is written with dependency fingerprints
(source revision, artifact digest, capture parameters, capture execution).
`reproduced_sha256` is still accepted as an extra consistency check, never as a
substitute.

**Alternatives rejected.**

* *Keep the digest-only form as a "compatibility" path.* It is the vulnerability;
  a compatibility path would be the same hole with a new name.
* *Require a second capture execution and trust its digest.* A digest can be
  computed from any file; requiring the artifact is what makes re-production real.
* *Bind only to the revision.* The brief's example — a screenshot exists but the
  current source did not produce it — needs the capture-parameter binding too.

**Enforced by** `render.verify`, `render.verification_dependencies`,
`render.verification_currentness`. **Tested by**
`render-verification.reproduction-must-be-a-new-artifact`,
`render-verification.changed-capture-parameters-invalidate`, engine-core
`re-hashing the original artifact is not re-production`.

---

## ADR-004 — A verification may observe through an engine-recorded anchor, but must verify through an engine execution

**Context.** Reference retrieval is performed by an adapter, not an engine
execution, so a retrieval verification has no observing execution to name. The
temptation was either to fabricate an execution record or to skip the verifier
requirement.

**Decision.** `verification.create` accepts `observed_anchor` (for example
`reference:<id>`) when no engine execution observed the claim, and still requires
a *different engine-created verifier execution* at `INDEPENDENTLY_REPRODUCED` and
above. The engine re-hashes the re-retrieved artifact itself and requires the
digest to match the recorded retrieval. Origin is recorded as proven only then.

**Alternatives rejected.**

* *Fabricate an engine execution for the adapter.* It would make the identity
  meaningless and violate "execution identity is engine-established".
* *Treat the reference record as the verifier.* Then the reference would verify
  itself, which is the self-attestation failure.
* *Require a local file for every retrieval.* External sources have no local
  artifact until retrieved; the record must describe what actually happened.

**Enforced by** `verification.create`, `references.record_retrieval_verification`,
`references.provenance_problems`. **Tested by**
`reference-verification.origin-proven-only-by-reproduction`,
`reference-verification.claimed-origin-without-verification-refused`.

---

## ADR-005 — Freshness is dependency-specific, and stale evidence answers as stale

**Context.** AR-202D made whole-artifact hashing the staleness test for rendered
evidence. AR-203 needs evidence to become stale when a *relevant* dependency
changes — and not when an unrelated file changes.

**Decision.** A record names the dependency fingerprints it was established
against (`dependencies` + `dependencies_digest`). `freshness_of` compares only
those names. A record with no dependencies is `UNKNOWN`, never `CURRENT`. A stale
record keeps `established_level` as history but answers as `STALE` for any current
requirement, and is never deleted. When the named dependencies match again,
`refresh` restores the level from `established_level` and records `restored_at`,
so a record can never report `CURRENT` freshness while its level says `STALE`.

**Alternatives rejected.**

* *Full-tree hash on every check.* It makes every artifact stale on any change and
  costs a tree walk per query.
* *A global revision only.* It cannot express "this capture is stale because the
  viewport changed but the source did not".
* *Delete stale evidence.* History is evidence; AR-202D already established that
  stale artifacts are kept.

**Enforced by** `verification.freshness_of`, `verification.refresh`,
`verification.effective_level`, `render.verification_currentness`.
**Tested by** `false-acceptance.stale-passing-evidence-does-not-close`,
`render-verification.changed-capture-parameters-invalidate`.

---

## ADR-006 — Capability evidence is a registry with an explicit routing policy

**Context.** AR-202 routing believed adapter declarations. The brief requires
declared, available and exercised capabilities to be distinguishable, and
requires routing policy to be explicit rather than equating `DECLARED` with
unusable.

**Decision.** A versioned capability registry with
`DECLARED/DISCOVERED/AVAILABLE/EXERCISED/VERIFIED/UNAVAILABLE/UNKNOWN`,
deterministic offline probes, and an `evidence_policy` parameter
(`declared`/`observed`/`strict`) recorded on every routing decision and candidate.
`VERIFIED` requires an existing verification record at `REPRODUCED`+ with
`CURRENT` freshness.

**Alternatives rejected.**

* *Treat declarations as unavailable for high-stakes work by default.* It would
  break existing behaviour for a fact nobody checked either way; the explicit
  policy makes the choice visible per route.
* *Probe capabilities by calling providers.* Paid calls to turn a status green are
  forbidden.
* *Infer capability from a model or vendor name.* Names are not evidence.

**Enforced by** `capabilities.observe`, `capabilities.satisfies`,
`routing.route_evidence`. **Tested by** the `capability-registry` benchmark group,
engine-core `the strict policy does not accept a declaration`.

---

## ADR-007 — Decision confidence is never authorization

**Context.** The Decision Plane introduces bounded judgement. A confident model
answer is exactly the kind of signal a workflow is tempted to treat as permission.

**Decision.** `authorization_effect` is always `none`; `contracts` refuses a
record claiming otherwise; `PROTECTED` consequences are refused regardless of
confidence; `mark_acted_on` refuses a refused decision; no threshold exists or can
exist that grants a gate, a scope, an install, a destructive action, an
acceptance or a release. Risk-adjusted policy maps consequence to evidence level
and confidence kind, and always names a fallback.

**Alternatives rejected.**

* *A global confidence threshold that unlocks actions.* It converts a
  self-reported number into authority.
* *Letting `PROTECTED` through at very high confidence.* Protected means
  human-controlled, full stop.
* *Silently proceeding when confidence is missing.* `NONE` is recorded and the
  consequence decides; low consequence accepts a low-confidence advisory, higher
  consequences fall back or escalate.

**Enforced by** `decisions.policy`, `contracts.decision_record_problems`.
**Tested by** `decision-plane.cannot-authorize-a-protected-action`,
`decision-plane.confidence-provenance-preserved`, engine-core
`a decision cannot authorize a protected action`.

---

## ADR-008 — Bounded decision intelligence only for unmapped, safe-class failures

**Context.** The first real integration had to demonstrate the hierarchy rather
than merely document it, and had to stay safe when the provider is missing,
failing or wrong.

**Decision.** `execution.classify_with_decision` classifies deterministically
first and consults a provider only for a source the declared vocabulary does not
map. The bounded option set excludes authorization, revision, conflict and design
failures, which are deterministic facts. Any provider problem produces
`UNKNOWN` + escalation, with the decision record returned as evidence. The class
only sets advisory flags; it never authorizes anything.

**Alternatives rejected.**

* *Classify everything with the model.* It replaces knowable facts with judgement.
* *Let the model propose any class.* It would allow "authorization failure" to be
  argued away.
* *Fail closed without recording the attempt.* The decision record is the evidence
  that judgement was attempted and unavailable.

**Enforced by** `execution.classify_with_decision`,
`contracts.DECISION_CLASSIFIABLE_FAILURE_CLASSES`, `execution.record_failure`.
**Tested by** `decision-plane.first-real-use-keeps-code-before-judgment`,
`decision-plane.deterministic-provider-failure-is-recorded`.

---

## ADR-009 — Review independence is bound to engine executions and recorded as a level

**Context.** AR-201 separated reviewer identity from implementer identity, but a
different string label is not an independent execution.

**Decision.** `review.independence_problems` requires two different
engine-created execution records. `review.independence_level` computes
`NONE/DECLARED_DISTINCT/ENGINE_DISTINCT_EXECUTION/DISTINCT_RUNTIME/DISTINCT_PROVIDER/HUMAN_REVIEW`
from observed facts only and records it on review and critique records. Policy —
not this module — decides which level a review requires.

**Alternatives rejected.**

* *Require provider diversity by default.* It is expensive and unnecessary for
  low-stakes deterministic changes.
* *Treat a different identity string as independence.* That is the relabelling
  attack.
* *Rank the levels as a universal quality order.* The brief is explicit that no
  level is categorically better for every task.

**Enforced by** `review.independence_problems`, `review.independence_level`,
`critique.build_review`, `contracts.review_problems`.
**Tested by** the `review-independence` benchmark group, engine-core
`a review bound to fabricated executions cannot establish independence`.

---

## ADR-010 — AR-203 records version themselves; the run-state file schema stays 1

**Context.** Four new record families arrive. The published `v1.6.7` runtime reads
`ariadne-run.json` and refuses an unknown `schema_version`.

**Decision.** Keep run-state file schema `1`. Add the collections additively with
independent record schemas (`SCHEMA_CAPABILITY`, `SCHEMA_VERIFICATION`,
`SCHEMA_DECISION` = 1) and contract markers
(`ariadne-capability-1`, `ariadne-verification-1`, `ariadne-decision-1`).
Migration invents nothing: a legacy state gains empty collections, and absence is
never converted into success.

**Alternatives rejected.**

* *Bump the run-state schema and migrate.* It would lock the published runtime out
  of user projects for no benefit and would auto-migrate, which earlier milestones
  forbade.
* *A side-car evidence store.* It would create a second evidence store that can
  drift and would break the atomic-write guarantees the run state has.
* *Back-fill verification/capability records for legacy runs.* That would invent
  evidence.

**Enforced by** `persistence.write_state`, `persistence.ADAPTIVE_COLLECTIONS`,
`contracts.AR203_COLLECTIONS`. **Tested by** engine-core
`a legacy state gains no invented capability, verification or decision record`,
`the run-state file schema stays 1 while the AR-203 record families are versioned`.
