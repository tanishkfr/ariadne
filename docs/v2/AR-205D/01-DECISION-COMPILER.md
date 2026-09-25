# 01 — Decision Compiler

The Decision Compiler (`ariadne_engine.decisions.compiler`) answers one question
before any intelligence is spent:

> What does Ariadne need to know before it can safely choose the next execution step?

It does not answer anything itself. It classifies each unresolved requirement
into the *form of intelligence* that requirement deserves, using a declared rule
table rather than a free-form agent, and records the result as a `DecisionPlan`.

## The classification order

```
CAN CODE KNOW IT?
      | yes - deterministic fact, no provider is consulted
      v
CAN IT BE A BOUNDED JUDGMENT?
      | yes - closed answer space plus a declared projection
      v
DOES IT REQUIRE CREATION / OPEN REASONING?
      | yes - generative execution with a declared reason
      v
UNRESOLVED - policy decides the escalation
```

A separate rule reserves some requirements to a human. `HUMAN` wins over every
model consideration: no confidence value can promote a release approval, a scope
expansion, a dependency install or an acceptance into a bounded question.

The five classes are exactly:

| Class | Meaning | Engine consequence |
|---|---|---|
| `DETERMINISTIC` | Code can establish the answer exactly. | A check runs; no model. |
| `BOUNDED` | Judgement with a closed, declared answer space. | One bounded question, batched with its independent siblings. |
| `GENERATIVE` | Creation or open-ended reasoning is required. | Generation, but only with a recorded justification. |
| `HUMAN` | Policy reserves the choice to a person. | A protected human gate. |
| `UNRESOLVED` | The compiler cannot classify safely. | Escalation to policy; never a silent default. |

`UNRESOLVED` never becomes `GENERATIVE`. Defaulting an unknown requirement to the
most expensive mechanism is the exact failure this table exists to prevent, so an
undeclared requirement kind escalates with `UNRESOLVED_CLASSIFICATION` instead.

## Code before judgment

A requirement that already carries a deterministically established value is
classified `DETERMINISTIC` with reason `CODE_KNOWS`, and no question is created
for it. The guard lives inside `classify_requirement`, so it cannot be bypassed
by a caller: `known=True` is checked before the rule table is consulted. The
benchmark case `decision-compiler.deterministic-fact-wins` proves that a counting
provider is never called for an exact fact, and the mutation
`remove the deterministic-first guard` proves the guard is load-bearing.

## The rule table

Requirement kinds are declared, versioned and explicit:

* deterministic kinds — `file-exists`, `file-count`, `content-hash`,
  `approval-exists`, `test-exit-code`, `capability-available`, `revision-match`,
  `policy-state`;
* bounded kinds — `failure-class`, `task-class`, `remediation-family`,
  `review-escalation`, `evidence-relevance`, `design-materiality`;
* generative kinds — `implementation`, `repair-content`,
  `architecture-synthesis`, `open-investigation`, `design-direction`,
  `writing-draft`;
* human kinds — `release-approval`, `scope-expansion`, `dependency-install`,
  `destructive-action`, `acceptance`, `protected-operation`, `review-waiver`,
  `policy-change`.

Every bounded kind names the projection contract its state must satisfy, and
every generative kind maps to a declared generation reason. Extending the
compiler means adding a row to a table, not teaching an agent a new trick.

## The plan record

`compile_plan` writes one `DecisionPlan` into the run state (unless the caller
asks for an unrecorded sub-plan). The record contains:

```
plan_id, task_id, stage, stakes, compiler_version
deterministic_facts        known values and outstanding checks
bounded_questions          question_id, primitive, options, projection_contract,
                           consequence, definition_version, depends_on
generative_needs           requirement, reason, detail
dependencies               requirement -> dependency edges (validated, acyclic)
verification_requirements  the obligations the caller declared
protected_actions          the human gates the plan refuses to decide
unresolved                 what could not be classified and why
escalations                structured reasons (for example NO_DECISION_PROVIDER)
fallback_policy            what happens when a mechanism is unavailable
classifications            the counts per class
fast_path                  whether this task needs no decision call at all
economics                  structural counts, no monetary claims
provider                   what was available, and why if not
policy_version, contract_version, authorization_effect: none, recorded_at
```

Dependency cycles and missing dependencies are refused at compile time. Duplicate
requirement ids are refused. A bounded question cannot declare a `PROTECTED`
consequence — that is a human gate, not a question. A generative requirement
without a declared reason is refused.

## The decision fast path

A plan whose requirements are all deterministic, whose stakes are low or medium,
and which has deterministic verification available reports
`fast_path.applies = true`. The fast path still waits for any outstanding
deterministic check to run; it does not guess. This is the T16 behaviour: knowing
when *not* to make a decision call is part of decision intelligence.

## Where it is used

The compiled plan feeds the decision graph, the batch planner and the
integrations. `ariadne decide --compile --graph` exposes it from the CLI;
`compile_decisions` and `compile_decision_graph` expose it through the programmatic
API. See [02 — Decision Graph](02-DECISION-GRAPH.md),
[03 — State projections](03-STATE-PROJECTIONS.md) and
[06 — Integrations](06-INTEGRATIONS.md).
