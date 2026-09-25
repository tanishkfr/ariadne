# AR-202D — Implementation

Milestone: **AR-202D, Design Intelligence** of Ariadne v2.
Base: AR-202 at `8e1a2fd8343ff986eb397348589c0bba0cbe55bb` (`v2/ar-202-adaptive-execution`).
Branch: `v2/ar-202d-design-intelligence`. Version file unchanged at `1.6.7`.

This document is the map: which systems exist, where they live, and what each one
enforces. The behaviour of each system is documented in `02`–`06`; the evidence
that it works is in `07`; the milestone narrative is `08`; the next milestone is
`09`.

## 1. Thesis

Ariadne should produce better interface design by making the design process
inspectable, not by asking a model to be more creative. The engine can now
answer, from recorded evidence rather than from prose:

* what design problem is being solved, and how deep the design work needs to go;
* what references were actually found, which were reachable, which were
  inspected, what was learned, and which findings influenced a decision;
* which existing project component already solves part of the problem, and
  whether a new dependency is justified;
* what direction was approved, by whom, at which revision;
* whether implementation matches that direction;
* what the rendered product actually looked like, at which viewport and revision;
* what an independent critique found, and what changed during refinement;
* whether the refinement fixed the defect without breaking something else.

## 2. Systems and source paths

| # | System | Source | Contract |
|---|---|---|---|
| T1 | Design task characterisation and pipeline selection | `src/ariadne_engine/design.py` | `contracts.characterisation_problems` |
| T2 | Reference provenance lifecycle | `src/ariadne_engine/references.py` | `contracts.reference_problems` |
| T3 | Reference adapters (capability-declaring, read-only) | `src/ariadne_engine/references.py` | `ReferenceAdapter.capability_record` |
| T4 | Reference analysis (observation → implication) | `src/ariadne_engine/references.py` | `contracts.reference_analysis_problems` |
| T5 | Component intelligence and the minimum-solution ladder | `src/ariadne_engine/components.py` | `contracts.component_candidate_problems` |
| T6 | Design-direction records and the `G1D` gate | `src/ariadne_engine/design.py`, `policy.py`, `contracts.py` | `contracts.design_direction_problems`, `contracts.direction_fingerprint` |
| T7 | Requirement closure | `src/ariadne_engine/design.py`, `policy.py` | `contracts.design_requirement_problems` |
| T8 | Rendered evidence and capture adapters | `src/ariadne_engine/render.py` | `contracts.rendered_evidence_problems` |
| T9 | Independent design critique, QA separation | `src/ariadne_engine/critique.py` | `contracts.design_review_problems` |
| T10 | Bounded refinement | `src/ariadne_engine/critique.py` | `contracts.refinement_problems` |
| — | Design failure kinds | `src/ariadne_engine/execution.py` | `execution.DESIGN_SOURCE_KINDS` |
| — | Design events | `src/ariadne_engine/events.py` | `events.EVENT_TYPES` |
| — | Design evidence routing | `src/ariadne_engine/routing.py` | `routing.DESIGN_EVIDENCE_REQUIREMENTS` |
| — | Design context rules | `src/ariadne_engine/context.py` | `context.design_source_state` |
| — | Design boundary requirements | `src/ariadne_engine/policy.py` | `policy.design_evidence_requirement` |
| — | Record collections | `src/ariadne_engine/persistence.py` | `persistence.DESIGN_COLLECTIONS` |
| — | Programmatic API | `src/ariadne_engine/api.py` | 17 new operations |
| — | Command surface | `scripts/ariadne.py` | `design-plan`, `record-design`, `design-check`, `design-report`, `approve-design-direction` |
| — | Benchmarks | `benchmarks/arbench/design_cases.py` | 70 cases in 12 groups |
| — | Engine suite | `scripts/test-engine-core.py` | `design_checks` (59 checks) + `hardening_checks` (41 checks) |

New modules: 5. New public engine records: 9. New event types: 17. New CLI
commands: 5. No new dependency; the whole milestone is standard library only.

## 3. What each layer enforces

### Characterisation (`design.characterize`)

Every design question is answered with `REQUIRED` / `OPTIONAL` / `NOT_REQUIRED` /
`UNKNOWN`, and every answer carries `source` and `evidence`. The inputs are
deterministic and local: the request text, the handoff's *declared* permitted
scope rows, the locked design artefacts, the creative ledger's assessment when one
exists, the project's own design-system markers, and the adapters that actually
report themselves available.

The repository is never an input. Twelve front-end files in the project do not
raise the depth of a database migration, and that is a benchmark assertion
(`design-characterisation.repository-code-is-not-task-evidence`).

Depth is then selected from those answers (`NONE` / `MINIMAL` / `STANDARD` /
`DEEP`) and a per-stage pipeline is recorded with the reason each stage was
selected, made optional, or skipped. A bounded repair is capped at `MINIMAL`, so
a spacing fix never selects reference research.

### Reference provenance (`references`)

`FOUND → ACCESSIBLE → INSPECTED → ANALYSED → USED`, with `INACCESSIBLE` as a
valid terminal outcome *before* anything has been observed. A transition that is
not in the table is refused, not coerced. Inspection requires a real, hashed,
re-hashable evidence artifact and at least one concrete observation. Analysis
requires an `INSPECTED` parent and must cite the inspection ids it generalised.
Usage requires an `ANALYSED` parent, a decision, and an anchor that actually
occurs in the artifact the decision changed.

### Inspection types and claim bounds

`CONTENT`, `VISUAL` and `INTERACTION` are separate, and each supports only some
claim kinds (`structure`, `content`, `appearance`, `behaviour`, `timing`,
`feedback`). Reading markup cannot support an appearance claim; a screenshot
cannot support a behaviour claim. A later interaction inspection is what makes a
behavioural claim legitimate, and the record keeps both.

### Component intelligence (`components`)

The existing minimum-solution ladder is preserved verbatim as
`components.COMPONENT_LADDER` and an evaluation is recorded at the first rung
that solves the need. Every evaluation names at least one alternative, records the
existing-equivalent check (including "not checked, because"), records findings
with explicit verdicts rather than invented scores, and reports
`install_authority = "none — human G2 required"`. A dependency whose licence or
framework compatibility is `unknown` is blocked rather than selected.

### Direction records (`design`, `policy`, `contracts`)

A direction record is created by the engine, starts as a `candidate`, and is
approved only on the human channel through the **`G1D`** gate. The approval binds
the record id, the task, the scope and a fingerprint of exactly the constraining
sections (`contracts.direction_fingerprint`). Editing any constraining sentence
invalidates the approval; editing the body outside them does not.

### Requirement closure (`design`, `policy`)

`Requirement → decision → implementation → evidence`, with states
`unaddressed / planned / implemented / observed / verified / blocked / rejected`.
The evidence needed to close a requirement depends on the claim: a source-level
requirement may close from source evidence, a rendered requirement needs a
capture, a behavioural one needs an observation, and `verified` needs
independent re-production (or, for source claims, an independent review that
covers it). Stale evidence closes nothing, and `implemented` is explicitly not an
observation.

### Rendered evidence (`render`)

`SOURCE_SUGGESTS / RENDERED / OBSERVED / VERIFIED / UNVERIFIED`, never collapsed.
A record must name the adapter, capture method, viewport, environment, revision
and artifact digest, and the engine re-hashes the artifact before accepting it.
Provenance is method-specific and checked: an `offline-fixture` artifact needs the
capture manifest the adapter wrote beside it, and a `declared-observer` artifact
needs the observer's explicit declaration and can never exceed `RENDERED`.
`VERIFIED` requires a *different* engine-created execution to re-produce the same
digest.

### Critique and refinement (`critique`)

A critique binds two engine-created executions (reviewer ≠ implementer), the
approved direction revision, the requirements under review and the rendered
evidence. It is refused without rendered evidence when the task requires it, and
refused against a changed direction. Findings carry dimension, severity, evidence
ids, location, explanation, repair scope and confidence — never a design score.
The four QA activities (functional, accessibility, regression, judgement) are
recorded separately and reported separately.

A refinement is defect-scoped: it names the smallest artifacts, the evidence it
will re-take and the regression checks it will re-run; a non-blocking finding
cannot authorize a broad redesign; changes outside the permitted scope are
refused; and the whole cycle is bounded by the same number the rest of the engine
uses (`critique.MAX_DESIGN_REFINEMENTS = 2`, equal to `policy.MAX_ROUTINE_REPAIRS`).

### Routing, context, events, failures

* **Routing** (`routing.route_evidence`): a design evidence need is routed through
  the AR-202 routing vocabulary. Capabilities come from adapter declarations,
  never from a model or vendor name; an unsatisfiable need produces a `blocked`
  decision with the new `design-evidence-unavailable` rule. Needs that only deepen
  the work (interaction inspection of an external reference) are recorded as
  opportunities and never block.
* **Context** (`context.decide`): a source that declares `requires: design` or
  `requires: reference` is omitted with `IRRELEVANT_TO_TASK` unless this task
  actually needs it, and `RELEVANT_CHANGED_FILE` is available for artifact-anchored
  sources. Role and stage isolation is unchanged.
* **Events** (`events.EVENT_TYPES`): 17 design event types join the one
  append-only log and its digest chain. There is no second design log.
* **Failures** (`execution`): 13 design kinds map onto the existing AR-202
  classes; exactly one new class (`DESIGN_FAILURE`) exists, for a design-workflow
  limit that no other class models.

## 4. Reuse rather than duplication

* The creative ledgers (`scripts/creative-intelligence.py`,
  `scripts/creative-operations.py`) are read, never replaced. The creative
  assessment feeds characterisation; the operations ledger's requirements are the
  canonical requirement set the closure model checks.
* The AR-202 characterisation, routing rules, execution identity, review
  independence, failure taxonomy, adaptive context and event chain are all
  extended in place.
* `MAX_DESIGN_REFINEMENTS` is deliberately the same number as
  `policy.MAX_ROUTINE_REPAIRS`, so implementation repair and design refinement
  cannot each claim a fresh budget.
* Approval authority is unchanged: `policy.approve` remains the only writer, and
  the new gate is enforced by the same function.

## 5. Compatibility

* Run-state file schema stays `1`; the published `v1.6.7` runtime keeps reading
  the file. Design records use their own schema family
  (`contracts.SCHEMA_DESIGN = 1`, `DESIGN_CONTRACT = "ariadne-design-1"`), so no
  migration is triggered and none is performed.
* `VERSION` is unchanged; `v1.6.7` artefacts are untouched.
* Every existing CLI command, stage name, gate name and packet contract is
  unchanged. The new commands are additive, and `--gate` still accepts exactly
  `G1/G2/G3` for the existing `approve-gate` path.
* A run without design records behaves exactly as it did in AR-202: no design
  boundary requirement, no design context rule, no design route.
