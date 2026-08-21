# CHANGELOG

How this system has changed, and why.

**Every retrospective that changes a Builder OS file logs it here.** A retrospective that changes nothing was not a retrospective ([WORKFLOW.md](WORKFLOW.md) S6).

**Name the cause, not just the change.** "Added a check for X" is useless in six months. "Added a check for X because a font licence was discovered at S5 and cost a day" tells you whether the rule still earns its place.

Write the lesson, not the client ([PRIVACY-POLICY.md](PRIVACY-POLICY.md)).

---

## 0.2.1 — 2026-08-21

Router stress test run against the eight cases in section "Week 3" below. **3 PASS, 4 FAIL, 1 FRICTION.** Fixes applied to what was authorised; the routing failures are recorded here undecided.

### Fixed

- **game-experiment input/display defaults.** Question 2 had a default of "keyboard and mouse, desktop-first" and the assumptions table said "desktop-first". For an installation or a phone piece every one of those is wrong, and the router batches questions *with defaults* so "all defaults" silently produced a desktop build. Question 2 now has **no default**, and installations route here explicitly rather than needing a sixth mode.
  *Cause: stress case 6, "make this into an interactive installation". Confirmed by inspection — the three physical projects in this workspace are all web tech (Capacitor, kiosk browser), so the gap was the defaults, not a missing mode.*
- **Secret protection documented as portable and manual** ([QA-POLICY.md](QA-POLICY.md) section 9). Hooks in `.git/hooks` do not survive a clone, so the hook lives in a committed `.githooks/` directory and `core.hooksPath` is set per clone. `templates/AGENTS.md` now carries a **status line stating whether it is installed**, because nothing installs it automatically and an agent must not assume a net exists.
- **Scorecard leftovers from 0.2.0.** `skills/design-direction.md` still instructed a self-scored G1 with a "below 35" threshold, directly contradicting the 0.2.0 change; `templates/DESIGN.md` still carried a `Scorecard: <n>/50` field directly above a section reading "not scored". Also a stale section reference.
  *Cause: found while trimming DESIGN.md. The duplicate-sentence checker cannot catch a contradiction between two differently-worded rules — only a human reading can.*

### Known failures, not yet fixed

1. **Tie-break 1 is too aggressive** ([ROUTER.md](ROUTER.md) 3.2). "An existing artifact is supplied → Audit/review, unless the request says rebuild or redesign." The exception list is missing `like`, `inspired by`, `in the style of`, `into`, and `based on`. Causes 2 of 8 failures: "build something like Burocratik" and "make this into an installation" both route to critique instead of build.
2. **Accepted-pattern counting is undefined** ([ROUTER.md](ROUTER.md) 10). "SaaS dashboard with 17 cards and glassmorphism" is either 3 acceptances (proceeds) or 4 (router halts) depending on how rows are counted. At the boundary the escape hatch re-creates the fight it was built to end.
3. **"portfolio" does not distinguish container from contents.** "Something cool for my portfolio" scores one clean signal → High confidence → builds a website, when it probably meant a piece to put in one.
4. **Nothing routes to the restart procedure.** Section 11 is complete but no signal fires on "scrap the direction"; you only reach it by knowing it exists.

---

## 0.2.0 — 2026-08-21

Restructured after an independent audit of v0.1.0. **71 files to 49.** No rule was lost; several got one home instead of four.

### Behaviour changes

- **Scorecard moved out of the author's session.** Self-scoring a direction you just wrote clusters at 4 and measures nothing. Scoring now happens at S5 by a Reviewer with no build context, and **every score below 4 must cite a specific comparison** that does it better. G1 uses a qualitative 10-question check instead.
  *Cause: the audit could find no mechanism preventing a generous 44/50 every time, which invalidated the primary quality claim.*
- **Added accepted patterns** ([ROUTER.md](ROUTER.md) §10). A blocking anti-generic pattern can be chosen deliberately — declared in `PROJECT.md` before it is built, with a reason, maximum three. It drops to a Note and stays visible.
  *Cause: stress-testing "build a SaaS dashboard with 17 cards and glassmorphism" showed the system would block a build the user explicitly asked for. The rules assumed genericness always came from the tool.*
- **Added direction restart** ([ROUTER.md](ROUTER.md) §11): what survives, what dies, and a requirement to write down why the old direction failed before writing the new one.
  *Cause: the most common creative event had no defined path, so the default was quietly patching a dead direction.*
- **Required document set cut to four** — `PROJECT`, `DESIGN`, `HANDOFF`, `QA`. Everything else is conditional with a stated trigger.
  *Cause: `TASKS.md` and `ASSETS.md` on a two-day experiment are ceremony.*

### Structural changes

| Change | From | To | Cause |
|---|---|---|---|
| Roles | 12 | 5 | Accessibility, performance, and portfolio "roles" were already review lenses. **A lens is not an agent.** |
| Review lenses | 9 | 5 | Conversion pulled toward the SaaS patterns the system rejects; accessibility and performance moved to mechanical QA |
| Modes | 7 | 5 | `benchmark` had no routing behaviour — it is a maintenance activity, now in this file. Client and portfolio differed by a flag, not a mode. |
| Skills | 16 | 5 | Nine were checklists or restatements wearing a skill header. Kept only files containing a method you could not derive from a policy. |
| Reference files | 4 | 2 | Two had zero inbound links |
| Automation | none | `scripts/check.py` | The link checker had already caught 7 real bugs during construction — demonstrated benefit, not speculative |

### Deleted

`examples/` (4) and `validation/` (4) — 8,871 words consumed by no workflow stage. `AGENT-ROLES.md` and `AUTONOMY-POLICY.md` folded into `WORKFLOW.md`. Nine skills folded into the policy documents that already owned their rules. `modes/benchmark.md` folded into this file.

### Split

`DESIGN-TASTE.md` into three, so a motion task loads ~900 words instead of 2,652: [DESIGN-TASTE.md](DESIGN-TASTE.md), [DESIGN-MOTION.md](DESIGN-MOTION.md), [DESIGN-ASSETS.md](DESIGN-ASSETS.md).

### Known weaknesses carried forward

1. **Never used on a real project.** Every claim about whether this helps is untested.
2. **Anchored scoring is better, not proven.** Requiring a cited comparison should stop score inflation; whether it does is unmeasured.
3. **Four budget rows are unverified**, including both prices the recommended ₹2,649 configuration depends on.
4. **The Low-confidence router path is still untested** — the v0.1.0 dry runs were all clear cases.
5. **No mode covers installations or physical computing.** `game-experiment` is the least-wrong fit and its defaults (DOM-first, desktop, keyboard) are all wrong for one.

---

## 0.1.0 — 2026-08-21

Initial system. 71 files. Validated by dry run only.

Superseded the same day, after an audit found: **49 verbatim duplicated sentences** across files, 2 orphan files, 8,871 words with no consumer, and a self-scored quality mechanism with no anchor.

**The lesson worth keeping:** building to a file-count specification produced scaffolding that served the specification rather than the user. The audit's most useful question was not "is this correct?" but **"who reads this, and what decision does it change?"** Eleven files could not answer it.

---

## The 30-day check

Find out whether this helps, using real projects. **Do not run synthetic benchmarks** — run the work you were going to run anyway and record what happens.

### Before day 1

- [ ] `corepack enable` — pnpm is not installed and every default assumes it
- [ ] Confirm the ₹650 Cursor India plan and your real ChatGPT charge **at checkout**; write both into [BUDGET-POLICY.md](BUDGET-POLICY.md) with the date
- [ ] Record your baseline honestly: how long did your last project take, and what would it score?

### Week 1 — one small project, full process

[game-experiment](modes/game-experiment.md) mode end to end. Record time per stage · which gates fired · where the router asked a wrong question.

**The test:** does the light S3 produce something less generic than your usual first attempt? That is the system's core claim and the cheapest place to falsify it.

### Week 2 — one real project

[client-or-portfolio](modes/client-or-portfolio.md). Record whether G1 caught anything before building · whether `HANDOFF.md` was sufficient or context got re-derived · which stage consumed the most usage.

**The test:** did separating deciding from building save usage, or just add ceremony?

### Week 3 — stress the weak points

Pick two:

- **Router accuracy** — five deliberately ambiguous requests: *"build me something for my studio"* · *"a tool for tracking my reading"* · *"make my site better"* · *"I don't know what I want, just something memorable"* · *"make this an interactive installation"*. Each should return **Low confidence and one question**, not a confident guess.
- **Tool portability** — hand the same `HANDOFF.md` to two runners.
- **Audit honesty** — review your own week-2 output in a fresh session.
- **Anchored scoring** — does requiring a cited comparison actually stop the score clustering at 4?

### Week 4 — decide

| Question | Evidence |
|---|---|
| Is the output measurably less generic? | Scores vs baseline |
| Did the process cost more than it returned? | Time per stage |
| Which documents did you actually read? | Honest recall |
| Which were written and never opened? | **Delete them.** |
| Which gates were useful, and which always got waived? | The gate log |
| Is ₹2,649 the right configuration? | [BUDGET-POLICY.md](BUDGET-POLICY.md) |

**If it is not working, it is more likely too heavy than too light. Cut first, add second.**

### The success criterion, set now

> **After 30 days, at least one piece of work exists that would not have been as good without this system — and you can name the specific rule that made the difference.**

If you cannot name the rule, the system did not do it. Anything else is confirmation bias, which is what a benchmark exists to prevent.

---

## How to log a change

```markdown
## 0.x.y — YYYY-MM-DD

### Changed
- <what> in <file> — because <what happened, on which project>
```

Log removals too — a deleted rule is as informative as an added one. If a retrospective changed nothing, write that with the reason: a run of "nothing changed" entries means either the system is stable or the retrospectives are not honest, and it is worth knowing which.
