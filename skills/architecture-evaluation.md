# SKILL: architecture-evaluation

**Trigger** — a feature or refactor admits more than one plausible structure and the choice will outlive the current task.
**Owner** — the worker planning the change; the design director keeps authority where a visual thesis is involved
**Inputs** — the required behaviour, the existing structure, the project's real constraints (stack, scale, deployment, team)
**Output** — the compared approaches with the chosen one, the constraint that rejects each alternative, and the migration cost

Structure is chosen against constraints, not taste. This method makes the
comparison explicit enough that a reviewer can disagree with the decision rather
than with the code that hides it.

## Method

1. **State the forces first.** What must the structure do: expected scale, change
   frequency, boundaries that must stay stable, failure modes, and what the project
   already uses. Constraints come from the repository and the task, never from a
   preference for a pattern.
2. **Write two or three real candidate structures.** A candidate is a sketch of
   boundaries and data flow, not a label. "Use a reducer" is not a candidate until
   you have named the state, the transitions, and what stays outside.
3. **Test each candidate against the forces.** For every candidate, name the force
   it serves best and the one it strains. A candidate with no strain is
   under-specified, not perfect.
4. **Prefer the simpler structure that satisfies the forces.** Fewer moving parts,
   fewer new concepts, fewer files touched, closer to the project's existing shape.
   Complexity must be bought by a named force, not anticipated scale.
5. **Cost the migration.** Every candidate is priced in files changed, interfaces
   broken, and checks to update. The cheapest structure that holds is usually the
   right one; say when it is not, and why.
6. **Record the rejected approaches.** The rejection list is the decision's
   evidence: it prevents the same comparison being re-argued at the next review,
   and it tells a reviewer exactly what to falsify.

## Recording

Approaches, forces, per-approach strain, chosen approach, migration cost, and the
constraint that decided it. A review that cannot see a rejected alternative cannot
tell a decision from a drift.

## Stop conditions

- The forces are unknown (no scale data, no usage evidence): mark them as
  assumptions, choose the reversible structure, and record what would change the
  decision.
- The decision needs a dependency or a paid service: that is a human gate; present
  the comparison, do not install anything.
- The project has an approved visual or architectural direction this would
  contradict: stop and raise it as a finding against the approved direction.
