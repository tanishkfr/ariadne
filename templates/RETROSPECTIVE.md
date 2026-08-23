# RETROSPECTIVE: <name>

> Template. Owner: Strategist · Stage: S6 · 15 minutes.
> **This is the stage that makes the Ariadne improve instead of ossify.**
> A retrospective that changes no Ariadne file was not a retrospective.

**Project:** <> · **Mode:** <> · **Shipped:** <date> · **Elapsed:** <>

---

## Outcome

| Success criterion (from `PROJECT.md`) | Met? | Evidence |
|---|---|---|
| 1 | yes / no / too early | |

**Final scorecard:** <n>/50 · **Lens verdicts:** <>

**Would I show this to <the audience from `PROJECT.md`>?** <yes/no, and why>

---

## The four questions

### 1. Which stage took longest, and was that the right place to spend time?

> Time in S1 and S3 is almost always well spent. Time in S4 fixing direction problems is not — it means S3 was rushed.

**Longest:** <stage> — <why> — **right place?** <>

### 2. Where did the output drift generic, and which rule failed to catch it?

> The most important question in this document. Be specific about the moment, not the outcome.

**Drift:** <where and when>
**Rule that should have caught it:** <which file, which section>
**Why it did not:** <the rule was missing / too vague / present but skipped>

### 3. Which questions should the router have asked and did not?

> These become router questions for the next project of this mode.

| Question | Would have changed | Add to |
|---|---|---|
| | | `modes/<mode>.md` |

### 4. What changes in Ariadne as a result?

> **A retrospective does not edit Ariadne.** It produces *proposals*; the human owner approves them.
> Direct mutation is how a system grows back to seventy files.

#### 4a. Qualification — all four must hold

> A candidate failing any one is **project-specific**. Record it above and stop. Most observations
> are project-specific; a retrospective that promotes everything is not being honest.

| # | Candidate | Recurs? | Evidence (2x, or 1x with named cost) | Names a specific rule? | Survives deletion test? | Verdict |
|---|---|---|---|---|---|---|
| 1 | <> | | | | | promote / project-only |

> **Deletion test:** if this rule existed and someone deleted it a year from now, would something
> break? If no, it is a note, not a rule.

#### 4b. Change proposals

> One file per proposal. A proposal touching three files is three proposals, or it is too big.
> **Propose deletions too** — a rule that never fired, or always got waived, is evidence against
> itself, and removing it is usually the more valuable change.

```
CHANGE PROPOSAL <n>
Observation:  <what happened>
Evidence:     <when, how often, what it cost>
Why systemic: <why this is not just this project>
File:         <the ONE Ariadne file that changes>
Change:       <exact edit - quote current text and replacement>
Prevents:     <the specific behaviour this stops next time>
Replaces:     <rule superseded, or "nothing - additive">
Regression:   <check.py always; tests/router-cases.md if routing is touched>
Complexity:   <+N words, +N files>
```

> **If `Prevents` cannot be filled in concretely, the proposal is a preference. Withdraw it.**

| # | Proposal | Status | Decided |
|---|---|---|---|
| 1 | <one line> | pending / approved / deferred / rejected | <date> |

> A deferred proposal stays here. **The same lesson deferred three times is itself the evidence** —
> promote it on the third.

**Candidates found:** <n> · **Promoted to proposals:** <n> · **Approved by the human owner:** <n>

---

## Tooling and usage

| Question | Answer |
|---|---|
| Which capability class did most of the work? | <`R1`-`R6`> |
| Did any tool hit its limit? At which stage? | |
| Was expensive reasoning used on anything cheap could have done? | |
| Was `HANDOFF.md` sufficient, or was context re-derived? | |
| Estimated usage spent vs value returned | |

> Repeatedly exhausting `R1` means S3 is under-specified and work is leaking into the expensive tier — not that you need a bigger plan. See [BUDGET-POLICY.md](../BUDGET-POLICY.md) section 8.

## Gates

| Gate | Fired? | Useful, or friction? |
|---|---|---|
| G1 Direction Lock | | |
| G2 Dependency | <n> times | |
| G3 Build Complete | | |
| G4 Ship | | |
| G5 Publish | | |

> A gate that never fires may be unnecessary. A gate that always gets waived is not really a gate.

## Design

- **Did the thesis survive to the shipped build?** <>
- **Was the signature moment built early, and did it survive?** <>
- **Which anti-pattern nearly got through?** <>
- **What would a stranger remember a day later?** <>

## Decisions worth keeping

| Decision | Outcome | Reusable? |
|---|---|---|
| | | |

## Mistakes

| Mistake | Cost | Prevention |
|---|---|---|
| | | <which Ariadne rule, new or amended> |

> Write the **lesson**, not the case ([PRIVACY-POLICY.md](../PRIVACY-POLICY.md) section 1).
> Not: "Client X's font was personal-use only."
> Instead: "Verify font licences at S3, before the direction depends on the face."

## Content ideas generated

> Retrospectives are the best content source you have — real instances, with specifics ([CONTENT-SYSTEM.md](../CONTENT-SYSTEM.md) section 4).

| Idea | The only-you element | Pillar |
|---|---|---|
| | | |

---

## One-line summary

> The single sentence you would tell someone about this project.

**<>**
