# MODE: Benchmark

Measure the Builder OS itself, or compare tools with evidence instead of impression.

Also contains the **30-day plan** (section 2) for validating this system after it starts being used.

---

## 1. The mode

### Detection

**Signals:** "test the system", "compare", "measure", "benchmark", "which is better", "is this working".

### Questions

Two only.

1. **What is the hypothesis?** — must be falsifiable. "Is Cursor good?" is not. "Cursor completes an S4 task faster than Claude Code at equal quality" is.
2. **What counts as a win?** — decided **before** running. Deciding afterwards guarantees you find what you wanted.

### Documents

`PROJECT.md` (hypothesis only) → `RETROSPECTIVE.md` (result). Nothing else.

### Skills

live-research, evaluation. **Gates:** none.

### Method

1. **One variable.** Changing tool *and* project *and* mode measures nothing.
2. **Same input.** Same `HANDOFF.md` to both runners. This is the main reason handoffs are plain markdown.
3. **Measure what you decided to measure** — wall-clock time, usage consumed, scorecard, number of build findings, QA failures.
4. **Blind the evaluation** where possible: score the outputs without knowing which tool produced which.
5. **"Inconclusive" is a real result.** Force a conclusion and you have built a superstition.

### Failure modes

| Failure | Countermeasure |
|---|---|
| Deciding the win condition afterwards | Question 2, before running |
| Changing three variables | One variable per run |
| One data point becoming a rule | Three occurrences, per [CONTENT-SYSTEM.md](../CONTENT-SYSTEM.md) section 11 |
| Measuring speed and ignoring quality | Score the output too |
| Benchmarking instead of building | Timebox it; the system is for shipping work |

---

## 2. The 30-day plan

Purpose: find out whether this system actually helps, using real projects rather than tests. **Do not run synthetic benchmarks** — run the projects you were going to run anyway and record what happens.

### Before day 1

- [ ] Complete [GETTING-STARTED.md](../GETTING-STARTED.md)
- [ ] Confirm the Cursor India plan at checkout — this converts four Unverified rows in [BUDGET-POLICY.md](../BUDGET-POLICY.md) into Verified ones
- [ ] Install pnpm (`corepack enable`) — **not currently installed on this machine**
- [ ] Record your starting point honestly: how long did your last project take, and what did it score?

### Week 1 — One small project, full process

Run **[game-experiment](game-experiment.md)** mode end to end. Small enough to finish, real enough to matter.

Record: time per stage · which gates fired · where the router asked a wrong question · the scorecard.

**Deliberate test:** does the light S3 produce something less generic than your usual first attempt? This is the system's core claim and the cheapest place to falsify it.

### Week 2 — One real project, full process

**[personal-portfolio](personal-portfolio.md)** or a real client site. The first genuine test.

Record: whether G1 caught anything before building · whether `HANDOFF.md` was sufficient or context got re-derived · which stage consumed the most usage · scorecard versus your Week 0 baseline.

**Deliberate test:** did the separation between deciding and building actually save usage, or just add ceremony?

### Week 3 — Stress the weak points

Pick the two that worry you most:

- **Router accuracy** — throw five ambiguous requests at it. Does it detect correctly, and does it name the runner-up?
- **Tool switching** — hand the same `HANDOFF.md` to two runners. Is it genuinely portable?
- **Audit honesty** — run [audit-review](audit-review.md) on your own Week 2 output in a fresh session. Does it find real problems?
- **Content loop** — one week of posts through the full method.

### Week 4 — Decide

Answer with evidence from weeks 1-3:

| Question | Evidence |
|---|---|
| Is the output measurably less generic? | Scorecards vs baseline |
| Did the process cost more than it returned? | Time per stage |
| Which documents were actually read? | Honest recall |
| Which were written and never opened? | **Delete them.** |
| Which gates were useful, and which always got waived? | Gate log |
| Did the tool split conserve usage? | Limits hit, and at which stage |
| Is the ₹2,649 configuration right? | [BUDGET-POLICY.md](../BUDGET-POLICY.md) |

### What to do with the answers

**Working:** log what and why in [CHANGELOG.md](../CHANGELOG.md), and stop changing it.

**Not working:** it is more likely the process is too heavy than too light. **Cut first, add second.** A document nobody reads is worse than no document, because it creates the illusion of process.

**Unclear after 30 days:** that is itself a finding. A system whose value is invisible after a month of real use is probably not delivering it.

### The honest success criterion

Set now, before the data exists:

> **After 30 days, at least one piece of work exists that would not have been as good without this system — and you can say specifically which rule made the difference.**

If you cannot name the rule, the system did not do it. Anything else is confirmation bias, which is exactly what a benchmark exists to prevent.
