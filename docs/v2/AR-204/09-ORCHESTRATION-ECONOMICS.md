# AR-204 — Orchestration Economics

Spend more where evidence justifies it, and know when not to orchestrate at all.

## 1. The task tree is the unit

Orchestration cost is only visible across the whole task, so the tree is built
from engine records and every node is attributable:

```text
task
├── coordinator        reasoner execution
├── decision batch     one request per independent question set
├── worker             implementer execution
│   └── repair         a later implementer execution after a failure
├── validation         validator execution
└── review             reviewer execution
```

`economics.task_tree_costs` reports per-kind measured totals and a share computed
from measured output tokens. A kind that was never measured reports `UNKNOWN`
rather than a share of a denominator nobody produced, and failed-node usage is
reported separately so a wasted attempt is visible instead of absorbed.

## 2. Two paths, both policy-derived

`orchestration.path_plan` derives the route from stakes, obligations and required
capabilities:

| Path | Retained steps | When |
| --- | --- | --- |
| simple | characterisation, worker, validation | low stakes, no design obligation, core capabilities only, no prior failure, no required review |
| standard | adds routing | medium stakes or one obligation |
| complex | decision, routing, review, validation, human acceptance | high stakes, design work or required human acceptance |

Every path retains validation, and `orchestration.require_verification_retained`
refuses a plan that dropped it — including a hand-built plan that never went
through the planner. Invariance 46 is therefore enforced twice: once by
construction and once by a guard.

## 3. A fast path cannot be a loophole

Five conditions block the simple path, each with a recorded reason: stakes above
low, a design obligation, a capability requirement beyond the core pack, a prior
failure on the task, and a required review or human acceptance. An unrecognised
stake level is treated as the strictest one, so an unparsed value cannot buy a
cheaper route. The benchmark asserts each blocker and the mutation that removes the
review condition is detected.

## 4. What orchestration bought

`orchestration.orchestration_economics` answers the brief's questions from records:

| Question | Source of the answer |
| --- | --- |
| did a repair avoid a restart | repairs recorded plus a completed implementer execution |
| did a review produce findings | critique records for the task, counted |
| did a decision call replace a generative call | measured decision batches |
| did duplicated exploration happen | duplicate source rows from the context decisions |
| did a subagent reduce parent context | not measured here; recorded as `UNKNOWN` |

That last row is deliberately `UNKNOWN`. Ariadne does not currently measure a
parent execution's context size before and after a child, and inventing a number
from execution counts would be exactly the fabricated saving the milestone
forbids. The AR-205 handoff names it as a measurement to add.

## 5. Shares, not absolutes

`task_tree_costs` reports the worker, validation and review shares of measured
output tokens. In the current worktree every share is `UNKNOWN`, because no
provider was called; the structure is exercised by fixtures that record usage
through the engine seam with a named observer. A run with measured usage gets real
shares, and a run without it says so.

## 6. When not to orchestrate

The engine's answer is structural: do not create a coordination node the path does
not require, do not batch questions that depend on each other, and do not route a
low-stakes mechanical task through a planner. Those three rules are the same rule —
every additional execution must be justified by an obligation the task actually
carries. Cost pressure can shorten a path only down to the policy floor, and the
floor always contains validation.
