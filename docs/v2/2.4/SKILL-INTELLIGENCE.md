# Skill Intelligence �?" Ariadne 2.4B

**Policy:** `skill-intelligence-1`  
**Registry authority:** unchanged. No skill body, mandatory method or trusted
instruction is rewritten by this feature.

## 1. The distinction the report keeps

```text
selected  !=  invoked  !=  completed  !=  proven useful
```

- **selected** �?" the deterministic selector chose the skill for this task.
- **invoked** �?" the worker reported that it used the method. This is a worker
  claim, not an engine observation.
- **completed** �?" the engine observed the evidence the method declares, for
  example a required validation pass for `behavior-tests`, a recorded
  independent review for `adversarial-review`, or a reproduction plus a passing
  revision for `root-cause`.
- **proven useful** �?" not claimed. A task that was accepted while carrying a
  skill is an **association**, not evidence that the skill caused the outcome.

The existing ledger already preserved the first three states. 2.4B adds a
per-skill/role/family view and an honest `association` label:

```text
N accepted task(s) also carried this skill; association is not causation
```

## 2. What is measured

For each task and skill:

- skill id and version from the plan;
- intent family and selection reason;
- required capabilities and whether the host declared them;
- whether the instruction document was selected and delivered;
- ledger state (`selected`, `invoked`, `completed`, `unmet`);
- the engine validation outcome;
- review outcome and findings;
- repair/attempt count;
- packet and document context cost where measured;
- acceptance decision.

For each skill, the report aggregates selections, invocations, completions,
unmet mandatory methods, validation failures, repairs, associated accepted tasks
and families. Token cost attributable to a skill document remains `UNKNOWN`;
no character-count estimate is presented as a measurement.

## 3. Selection changes

**None.** The deterministic selector in `ariadne_engine/skills.py` is unchanged:

- a mandatory method for a family cannot be dropped;
- an unavailable host capability is a recorded gap, not an invented execution;
- an unselected method costs no context;
- a conflict refuses the selection instead of silently choosing;
- a skill document cannot grant a gate, widen a scope or waive validation.

The new report can *propose* a selection change. It cannot apply it.

## 4. Proposal mechanism

`ariadne_engine/skill_intelligence.py` produces a proposal only from a recurring,
recorded condition:

| Condition | Proposal |
|---|---|
| A mandatory method is `unmet` in at least two tasks | Strengthen the reporting/evidence check; add a deterministic precondition |
| An optional method is selected at least three times with no invocation/completion | Review whether it should remain default-selected for that family |
| A write task records at least two failed validations without `behavior-tests` selected | Evaluate whether the regression method should be mandatory/default for that family |

Each proposal records the original failure, evidence references, suggested
change, expected benefit, relevant skill version, risks and a validation
procedure. It is stored as `PROPOSED` with `authority: none`.

`authorize` records a human identity and a `proposal-only` scope. It does not
change the registry. `apply_to_registry` refuses by construction: a proposal may
inform a reviewed change, but no caller can turn it into trusted instructions
automatically.

## 5. External skills

The existing external-skill boundary is preserved and re-tested:

- a candidate is untrusted until a human approval binds one identity to one
  exact digest and scope;
- a changed file makes the approval `stale`, never silently reused;
- instructions that claim approval, a gate, a permission or a validation waiver
  are refused by `document_authority_problems`;
- discovery reads metadata only; installation requires a matching approval;
- no external skill can widen a project scope or read another private project.

## 6. Observed results in this pass

- The mandatory-skill selection test passes: `root-cause` and `anti-slop` remain
  selected for a `bug` task regardless of the optional set.
- The attribution test passes: a selected but unreported `behavior-tests` is
  `not_reported`, not `completed`; `root-cause` is completed only because the
  validation passed and the reproduction was reported.
- The proposal test records a recurring unmet-mandatory proposal and refuses the
  automatic apply path.
- The external injection and stale-approval tests pass.
- No production skill proposal was generated from the two live samples; the
  mechanism is exercised by deterministic fixtures. That is a limitation, not a
  claim of learned skill quality.

## 7. What is not claimed

- That any skill is useful merely because an accepted task carried it.
- That a skill is useless because a worker did not report it.
- That a sample of two tasks supports a selection change.
- That a proposal has been applied. No proposal was applied in this pass.
- That token savings from dropping a skill are measurable here; provider token
  usage was not supplied by the live adapters.

## 8. Review procedure for a proposal

1. Reproduce the original failure with the current skill version.
2. Apply the proposed change in a branch, not in the trusted registry.
3. Run the affected tasks and the same validation rows before/after.
4. Confirm every mandatory method remains selected.
5. Run an independent review of the skill change.
6. Have a human authorize the change in the repository's normal review process.
7. Re-run the skill, regression and adversarial suites.
