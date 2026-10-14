# SKILL: anti-slop

**Trigger** — any write task; required by default for defect, feature, refactor, performance, and redesign work.
**Owner** — the worker making the change; the reviewer checks the result
**Inputs** — the task contract's objective and permitted scope, the existing code
**Output** — a change proportional to the problem, with every touched file justified

The failure this method prevents is not ugly code; it is code that solves a
problem nobody has yet, in a way that makes the real problem harder to see. Each
rule below is a default the reviewer can hold the change to, and each has a stated
escape hatch.

## Rules

1. **No speculative abstraction.** A new interface, base class, hook, or
   configuration point must serve the current task. "We may need it later" is not
   a reason; the second real use is.
2. **No duplicated logic.** Before writing the helper, search for it. If the same
   decision now lives in two places, one of them will be updated alone. Extend the
   existing owner instead of copying it.
3. **No weakened types.** `any`, unchecked casts, optional fields that are always
   present, and stringly-typed states are liabilities paid at the next change.
   Where the language's types cannot express it, say so in a comment next to the
   line, not in a shrug at the file level.
4. **No unearned configurability.** Every flag, option, and environment variable is
   a promise to support a combination. Add one when a real caller needs it.
5. **No drive-by changes.** Unrelated reformatting, renaming, and cleanup hide the
   real diff from the reviewer. Put them in their own change, or leave them.
6. **No dead scaffolding.** Half-wired modules, commented-out alternatives, and
   "TODO: remove" markers are removed before the change is offered as complete.
7. **Size the diff to the objective.** If a five-line fix needs twenty files, the
   twenty files are a finding about the design — raise it instead of swallowing it.

## Escape hatch

Each rule yields to a stated, project-specific reason recorded in the change —
compatibility with an external contract, a measured constraint, an approved
direction that requires the shape. The reason is the difference between a
deliberate choice and slop.

## Stop conditions

- Removing an abstraction breaks a consumer the task does not cover: keep it and
  record why; the blast-radius method owns that decision.
- The task cannot be done inside the rules (the interface genuinely needs an
  option, the types genuinely cannot express it): record the exception with its
  reason; do not silently lower the standard.
- The permitted scope forbids the file that must change: stop for an out-of-scope
  decision rather than widening the change quietly.
