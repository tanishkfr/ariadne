# 12 — Release delta

This document is the exact change set AR-205D introduces on top of the accepted
AR-205 release candidate. The baseline is commit
`937cbde6e5ef55951b71f07ed2cbc26cea364718` on
`v2/ar-205-release-candidate`; the AR-205D work is on
`v2/ar-205d-decision-intelligence`.

Nothing is published, tagged or pushed. The version stays `2.0.0rc1`; the
AR-205 artifacts are superseded and are **not** reused for publication — the
AR-205D candidate is built from its own final source commit
([11 — Report](11-AR-205D-REPORT.md) records the commit and hashes).

## 1. Added: the decision-intelligence module set

| Module | Purpose |
|---|---|
| `decisions/compiler.py` | T1/T16: classify requirements into DETERMINISTIC / BOUNDED / GENERATIVE / HUMAN / UNRESOLVED and compile a `DecisionPlan`; deterministic-first, explicit rules, no free-form agent. |
| `decisions/graph.py` | T2: the bounded decision graph (kinds DETERMINISTIC, DECISION_BATCH, GENERATION, VERIFICATION, HUMAN_GATE), cycle/dependency refusal, immutable outcomes, transitive invalidation. |
| `decisions/planner.py` | T3: dependency staging and automatic batching of independent questions; one provider call per projection group. |
| `decisions/projections.py` | T4: four closed projection contracts with REQUIRED / OPTIONAL / FORBIDDEN marks and `INSUFFICIENT_STATE` on a missing required field. |
| `decisions/cache.py` | T5: state/question/provider/model/policy-bound decision cache; content-driven invalidation; reuse preserves provenance and never authorizes. |
| `decisions/escalation.py` | T6: the explicit ladder with structured reasons (`NO_DETERMINISTIC_RULE`, `LOW_CONFIDENCE`, …); stronger means capability-shaped, never price-ranked. |
| `decisions/consensus.py` | T7: optional independent second decision; agreement is evidence of agreement, never of correctness; `DECISION_CONFLICT` on disagreement. |
| `decisions/integrations.py` | T8: four real engine paths (failure classification, review escalation, evidence relevance, route family) through one compile → project → batch → policy → escalate path. |
| `decisions/generation.py` | T10: the generation gate; generation records a declared justification. |
| `decisions/trace.py` | T11: the record-derived decision trace and the `decision-trace` explanation. |
| `decisions/calibration.py` | T12: raw outcome collection (answer, confidence, provider/model, downstream result, contradiction, human override) with no self-tuning. |
| `decisions/economics.py` | T15: structural decision economics and the compiled-plan comparison; no monetary claim. |

`decisions/providers.py` is extended (not replaced): generic capability
descriptions, concrete model-version identity (`requested` vs `observed`),
`OptionalProviderAdapter`, a Jev-shaped adapter boundary whose live use is
`NOT_EXECUTED`, and an explicit `UnavailableProvider`. `decisions/policy.py`
gains a strict usable-probability check: `0.0`, out-of-range and non-numeric
confidence values can no longer satisfy MEDIUM/HIGH consequence.

## 2. Added: engine contracts

* `SCHEMA_DECISION_INTELLIGENCE = 1`, `DECISION_INTELLIGENCE_CONTRACT`.
* Vocabularies: `DECISION_CLASSIFICATIONS`, `DECISION_GRAPH_NODE_KINDS`,
  `DECISION_GRAPH_STATUSES`, `ESCALATION_REASONS`, `GENERATION_REASONS`,
  `PROJECTION_FIELD_MARKS`, `CONSENSUS_POLICIES`, `CONSENSUS_VERDICTS`,
  `REVIEW_ESCALATIONS`, `EVIDENCE_RELEVANCE_ANSWERS`, `ROUTE_FAMILIES`,
  `CALIBRATION_OUTCOME_CATEGORIES`.
* Persisted collections with explicit caps: `decision_plans`, `decision_graphs`,
  `decision_cache`, `decision_consensus`, `generation_justifications`,
  `decision_outcomes`.
* Structural validators for every new record family (fail closed).

## 3. Changed: existing engine surfaces

| Surface | Change |
|---|---|
| `execution.py` | failure classification consults the Decision Plane only after the deterministic vocabulary fails. |
| `review.py` | `escalation_advice` — bounded advice on review intensity; the review policy still decides what is required. |
| `verification.py` | `relevance_advice` — bounded relevance judgement that can never override freshness or provenance. |
| `routing.py` | `family_advice` — bounded route family, consumed as an input; protected policy wins. |
| `events.py` | ten `decision_*` / `generation_justified` event types on the existing append-only log. |
| `persistence.py` | the new collections participate in state read/write and migration. |
| `api.py` | eight provisional entry points: `compile_decisions`, `compile_decision_graph`, `decision_advice`, `decision_trace`, `decision_intelligence_report`, `justify_generation`, `record_decision_outcome`, `invalidate_decision_cache`. |
| `scripts/ariadne.py` | `ariadne decision-trace` and `decide --compile/--graph/--providers` (offline JSON provider specs only). |

No v1 command, exit code, file format, migration behaviour, packaging surface or
public stable API changed. Boreal is untouched and not required.

## 4. Decision-graph output contracts

Verification nodes now declare `{"required": ["verified"], "true":
["verified"]}` and a VERIFICATION node cannot succeed with `verified` false,
`"no"` or `0`; required outputs must be present and non-empty. A deterministic
fact may still be `False` or `0` — `False` is a value, absence is not.

## 5. Benchmark and test changes

* benchmark cases 259 → **295** (36 new: compiler 5, graph 5, batching 4,
  cache 5, escalation 5, integrations 4, economics 3, golden workflows D1–D5);
* release subset 45 → **56** (eleven AR-205D cases added);
* engine core 457 → **574** checks; AR-205D adds regression coverage for the
  adversarial repairs below;
* release tests 81 → **97** checks;
* new `scripts/test-decision-mutations.py` (9/9 mutations caught, sources
  restored byte-identical).

## 6. Adversarial repairs (post-review)

The bounded adversarial review found six genuine defects; all six are fixed and
covered by regressions:

| # | Defect | Fix |
|---|---|---|
| D1 | `cache.materialise` served an answer to a different question | question id and definition digest are checked; the cached answer is re-validated against the current option set |
| D2 | `materialise` trusted caller-supplied projection entries | entries are re-hashed and must reproduce the recorded digest |
| D3 | `0.0` calibrated probability accepted as sufficient evidence | confidence must be a usable probability in (0, 1] for MEDIUM/HIGH |
| D4 | a fact could be `known: True` with `value: None` | a `None` value is never a known fact; an explicit `known: None` falls through to real facts |
| D5 | FORBIDDEN keys were smuggled through `projection_entries` | the integrations path refuses contract-forbidden slices; `credentials` is FORBIDDEN in every contract |
| D6 | `verified: false` satisfied a verification output contract | verification nodes require an affirmed `verified` output |

## 7. Documentation

New `docs/v2/AR-205D/` 01–12 plus measured overhead in
`measurements/decision-intelligence-perf.json`; README gains the intelligence
hierarchy section and a link to the milestone report. No roadmap milestone was
retro-opened and no other subsystem's documentation was restructured.

## 8. Known limits at this delta

* no live decision provider, no calibration data, no threshold registered;
* no dollar figure is claimed (structural counters only);
* Jev-shaped adapter boundary only; live use `NOT_EXECUTED`;
* prompt-in-state semantic manipulation remains an honest limitation
  ([09 — Security](09-SECURITY.md)).
