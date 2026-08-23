# PROMPT: Retrospective (S6)

**Paste into:** your reasoning tool, after the project ships or stops.
**Produces:** `RETROSPECTIVE.md`, and **zero or more change proposals** for Ariadne.
**Gate:** none for the retrospective. **Your approval is required before any Ariadne file changes.**

Fifteen minutes. This is the stage that makes the system improve instead of ossify — and the stage that, done carelessly, regrows it into seventy files.

---

```
You are the Strategist in my Ariadne. Stage S6.

REQUIRED INPUTS
- PROJECT.md.
- QA.md, including the independent S5 QA judgement block when S5 ran.
- AGENTS.md from the project repository root.
- templates/RETROSPECTIVE.md as the canonical retrospective structure.

IF MISSING
Verify the applicable inputs before starting. If any is missing, STOP. Name it;
do not reconstruct review findings from conversation history, do not write a
partial RETROSPECTIVE.md, do not update AGENTS.md, and do not propose a Builder
OS change.

END WITH:
  NEXT: S6 Retrospective retry.
  Run prompts/retrospective.md again with the missing project evidence.
  Blocked on: <exact missing input>
END IF MISSING

READ: PROJECT.md, QA.md (including its independent review findings), AGENTS.md,
and the supplied templates/RETROSPECTIVE.md. Not the whole system. Write the
project's RETROSPECTIVE.md using that supplied structure.

PART 1 - WHAT HAPPENED

1. Which stage took longest, and was that the right place to spend time?
   Time in S1 and S3 is usually well spent. Time in S4 fixing direction
   problems means S3 was rushed.
2. Where did the output drift generic, and which rule failed to catch it?
   Name the moment, not the outcome.
3. Which questions should the router have asked and did not?
4. Did the handoff work? How many questions did the build session ask that
   HANDOFF.md should have answered? A number, not an impression.
5. Where did I have to think about Ariadne instead of the project?
   Every one of those is friction and worth more than any score.
6. Where did Ariadne prevent a bad decision? Be specific or say none.

PART 2 - LESSON CANDIDATES

For each observation, apply ALL FOUR qualification tests. A candidate that
fails any one of them is PROJECT-SPECIFIC. Record it in RETROSPECTIVE.md and
stop there - do not propose a system change.

  1. WOULD RECUR - not caused by this project's unique constraints
  2. EVIDENCE - happened at least twice, OR once with a cost you can name
     in hours
  3. SPECIFIC - names a rule that was missing, vague, or wrong.
     "Be more careful" is not a lesson.
  4. DELETION TEST - if this rule existed and someone deleted it a year from
     now, would something break? If no, it is a note, not a rule.

Report how many candidates you found and how many survived. If all of them
survived, you are being too generous - most observations are project-specific,
and a retrospective that promotes everything is how a system grows to seventy
documents.

PART 3 - CHANGE PROPOSALS

Only for candidates that passed all four. Use exactly this format:

CHANGE PROPOSAL <n>
Observation:  <what happened>
Evidence:     <when, how often, what it cost>
Why systemic: <why this is not just this project>
File:         <the ONE Ariadne file that changes>
Change:       <the exact edit - quote the current text and the replacement>
Prevents:     <the specific behaviour this stops, next time>
Replaces:     <existing rule this supersedes, or "nothing - this is additive">
Regression:   <which tests must pass: check.py always; tests/router-cases.md
               if routing is touched>
Complexity:   <+N words, +N files. Additive proposals need a stronger case
               than replacements.>

RULES
- One file per proposal. A proposal touching three files is three proposals,
  or it is too big.
- If Prevents cannot be filled in concretely, the proposal is a preference.
  Withdraw it.
- Propose DELETIONS too. A rule that never fired, or always got waived, is
  evidence against itself. Deletions need the same format and are usually
  the more valuable proposal.

FINALLY, update AGENTS.md ## Current state:
  Stage S6 | Last gate passed G4 (if shipped) | Next stage done |
  Next prompt none | Updated <today>

That is the last write. The repository is now readable by any future session
without this conversation.

THEN STOP. Do not edit any Ariadne file. I approve, defer, or reject each
proposal. A deferred proposal stays in RETROSPECTIVE.md - if the same lesson
gets deferred three times, that repetition is itself the evidence.
```

---

## After approval

For each proposal **you** approve:

1. Make the edit — one file, exactly as the proposal quoted it.
2. Run `python scripts/check.py`.
3. If routing changed, re-run `tests/router-cases.md`.
4. Log it in [CHANGELOG.md](../CHANGELOG.md) naming the **cause**, not just the change.

If a regression check fails, revert. The whole system is text, so rollback is free — use it rather than debating it.

**If nothing was approved, write that in the CHANGELOG with the reason.** A run of "nothing changed" entries means either the system is stable or the retrospectives are not honest, and it is worth knowing which.
