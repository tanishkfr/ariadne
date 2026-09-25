# AR-202D — Design review and bounded refinement

Source: `src/ariadne_engine/critique.py`. Contracts:
`contracts.design_review_problems`, `contracts.refinement_problems`,
`contracts.design_requirement_problems`.

## 1. Four QA activities, kept apart

| Activity | Question | Evidence it needs | If it fails |
|---|---|---|---|
| `functional` | does it work? | a command record, returncode, output digest | fix the code |
| `accessibility` | can users operate and perceive it? | a rule result or a manual check | fix the interface |
| `regression` | did the rendering change unexpectedly? | a capture comparison | investigate the change |
| `judgement` | does it satisfy the intended experience and the direction? | the approved direction + rendered evidence | scoped design repair |

They are recorded as four separate blocks in the review record
(`qa_activities`), each with its own state, evidence and detail. There is **no
combined score**, and `critique._qa_activities` writes an explicit note saying so.
A page can be functionally correct and poorly designed, look right and be
inaccessible, and pass a screenshot comparison while violating the direction that
was supposed to govern it — the record now shows which of those happened.

## 2. Preparation (`critique.prepare_review`)

Preparation verifies every precondition *before* a review runs, and refuses with a
named reason:

| Precondition | Refusal if missing |
|---|---|
| the approved direction exists and is current | `DESIGN_DIRECTION_MISSING` / `DESIGN_DIRECTION_STALE` |
| the requested dimensions are real dimensions | unknown dimension named |
| rendered evidence exists when the task requires it | "a critique without it is refused" |
| cited evidence exists and is not stale | unknown or stale evidence named |
| some evidence is at least `RENDERED` for rendered work | "cannot rest on source suggestions alone" |
| the requirements under review are named | "a design critique must name the requirements it judges" |
| reviewer execution ≠ implementing execution | `review.independence_problems` |

The prepared request is an isolated, self-contained object: direction revision,
requirements, evidence descriptors (id, state, kind, viewport — not the artifacts
themselves), the dimensions, the QA separation and the four questions a critique
must answer. It deliberately carries **no implementation narrative and no
worker chain-of-thought** (§29): the reviewer gets the direction, the
requirements and the rendered evidence, which is what judgement requires.

## 3. Findings

Each finding carries:

| Field | Enforced |
|---|---|
| `dimension` | one of the 17 declared critique dimensions |
| `severity` | `blocking` / `major` / `minor` / `note` |
| `evidence_ids` | required; each must exist and be current |
| `requirement_id` | must belong to the reviewed requirement set when given |
| `location` | where in the artifact |
| `explanation` | why it is a defect |
| `repair_scope` | the smallest repair that would resolve it |
| `confidence` | evidence strength, not a score |
| `state` | `open` / `repaired` / `unresolved` / `accepted` / `rejected` |

A finding without evidence or without a repair scope is refused. There is no
`8.7/10` anywhere in the contract: `contracts.DESIGN_SEVERITIES` is ordinal
language and the only numeric values in a review record are counts.

## 4. Independence is execution provenance

A critique binds two **engine-created** executions:

* `implementing_execution` — the execution that produced the reviewed revision;
* `reviewer_execution` — a fresh execution created for this review.

`review.independence_problems` refuses a self-review on both axes, and
`contracts.design_review_problems` refuses a record where the two ids are equal,
where the binding is not `engine`, or where either id is malformed. Identity is
recorded and checked as well, so naming the implementer as the reviewer is refused
even with a different execution id.

Independence is about *execution provenance*, not vendor: a different model, a
different provider or a different session are all acceptable ways to obtain a
reviewer execution, and no commercial model is required or preferred anywhere in
the milestone.

A critique can never grant a human gate: `G3` remains the human acceptance of a
reviewed revision, and the design review record is not an approval.

## 5. Bounded refinement

`critique.propose_refinement` turns **one finding** into a defect-scoped plan:

| Field | Enforced |
|---|---|
| `finding_id` | the finding it repairs; an already-repaired finding is refused |
| `artifact` | the artifact to change |
| `intended_change` | what will change |
| `permitted_scope` | the smallest affected artifacts; a broad scope is refused for a non-blocking finding |
| `expected_evidence` | the evidence that will be re-taken |
| `regression_checks` | required — a fix that breaks a passing check is a regression, not a fix |

`critique.record_refinement` then enforces the result:

* changes outside `permitted_scope` are refused and the refinement stays
  `proposed`;
* the declared `expected_evidence` must actually be re-captured, or the cycle
  fails;
* reported regressions make the cycle `failed` and the finding `unresolved`;
* only a clean, fully re-evidenced cycle is `verified` and resolves its finding.

Scope is matched by `contracts.path_matches`, the same rule the runtime's worker
scope check applies: exact equality, an `fnmatch` glob, or a `/**` directory
prefix. A permitted `src/app.py` therefore never admits `vendor/src/app.py`, a
permitted `src` never admits `srcx/evil.py`, and the `src/**` vocabulary the
handoff tables actually use is honoured.

The budget is `critique.MAX_DESIGN_REFINEMENTS = 2`, deliberately the same number
as `policy.MAX_ROUTINE_REPAIRS`, and `refinement_budget` reports the worker-repair
state too, so implementation repair and design refinement cannot each claim a
fresh budget. A third attempt is refused with `REFINEMENT_LIMIT_REACHED`, and
`policy.design_evidence_requirement` reports the same condition at `S5` when
findings remain open and the budget is spent — which is a human decision, not an
automatic loop.

**What refusal looks like.** "The design could be better" produces nothing: there
is no finding, so there is no plan. A minor finding cannot authorize "the entire
interface". A repair that would touch an unrelated page is refused. A repair that
did not re-take its evidence is `failed`. An unresolved finding stays visible in
`critique.refinement_summary` and in `design-check`.

## 6. Requirement closure and the review

Requirements are closed with evidence, not with prose
(`design.record_requirement`):

| `evidence_kind` | minimum to reach `observed` | minimum to reach `verified` |
|---|---|---|
| `source` | any current evidence record | `VERIFIED` evidence, or an independent review that covers the requirement |
| `rendered` | `RENDERED` or stronger at the required revision | `VERIFIED` |
| `behavioural` | `OBSERVED` or stronger | `VERIFIED` |

`implemented` is explicitly not an observation, a source suggestion cannot close a
rendered requirement, a stale artifact closes nothing, and a rejected requirement
must record why. `design.requirement_problems` is what `policy` consumes at `S5`,
so a design boundary cannot be crossed on an unclosed rendered requirement.

## 7. Failure kinds

| Kind | Class |
|---|---|
| `DESIGN_REVIEW_FAILURE` | `REVIEW_FAILURE` |
| `REQUIREMENT_EVIDENCE_INSUFFICIENT` | `VALIDATION_FAILURE` |
| `ACCESSIBILITY_FAILURE` | `VALIDATION_FAILURE` |
| `REFINEMENT_LIMIT_REACHED` | `DESIGN_FAILURE` (the one new class; escalation required) |
