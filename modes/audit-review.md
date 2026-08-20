# MODE: Audit / review

Critique something that already exists. **QA *is* the deliverable** — there is no build stage.

---

## Detection

**Signals:** "review", "critique", "audit", "roast", "feedback on", "what's wrong with", a URL to an existing thing.

**Tie-break:** an existing artifact supplied (URL, repo, screenshot of a live thing) routes here — **unless** the request says "rebuild" or "redesign", which routes to the appropriate build mode with the audit as its S2 ([ROUTER.md](../ROUTER.md) 3.2).

---

## Questions

Three, and question 1 is the one that matters.

1. **Which lens?** — the nine in [EVALUATION-RUBRICS.md](../EVALUATION-RUBRICS.md). Default: creative director + one more matched to the artifact.
2. **Yours or someone else's?** — changes how blunt to be, and whether privacy rules apply
3. **Findings only, or fixes too?** — default: findings with fixes attached, but no code written

If the request is "roast this", the honest reading is design-school reviewer plus creative director, and the user has pre-authorised bluntness. Take it.

---

## Documents

`QA.md` (the findings) → `RETROSPECTIVE.md` (optional, only if it should change the Builder OS).

Nothing else. No `PROJECT.md`, no `DESIGN.md`.

## Skills

reference-analysis (to judge against a stated intent), browser-qa, accessibility, performance, evaluation

## Stages

S1 light · S2 as needed · **S5 is the entire mode** · S6 findings only.

## Gates

None fire. Nothing is built, installed, pushed, or published.

**Exception:** if the audit becomes "and fix it", that is a mode change to a build mode with full gates. Say so rather than sliding into implementation.

---

## Method

**1. Establish the intent before judging against it.** What was this trying to be? Without that, you are scoring it against your own taste, which is not a review.

If the intent is not stated, infer it, **say you inferred it**, and score against the inference.

**2. Use it properly.** Load it. Scroll it. Phone. Keyboard. Try the primary task. Five minutes of real use beats any amount of reasoning about a description or a screenshot.

**3. Run the lenses in separate sessions.** They contaminate each other ([skills/evaluation.md](../skills/evaluation.md)).

**4. Evidence for every finding.** Where (route, element, viewport), what (the observation), why (which criterion). A finding without evidence is an opinion.

**5. Attach a fix to everything.** What to change, roughly what it costs, what it risks.

**6. Name the one thing.** Mandatory. Twelve equal findings get ignored; one clear priority gets acted on.

**7. Run the three feel tests** — five-second, swap, recall ([skills/evaluation.md](../skills/evaluation.md)).

---

## Output

```
AUDIT: <target>
Intent:      <stated, or inferred — say which>
Lenses:      <which, and why these>

<per lens: the recommendation block from EVALUATION-RUBRICS.md>

CONSOLIDATED
Blocking:    <every one>
Major:       <ranked by how many lenses raised it>
Conflicts:   <where lenses disagree, and what decides it>
The one thing: <single highest-leverage change>
Feel tests:  five-second: <> | swap: <> | recall: <>
Verdict:     <>
```

---

## Reviewing your own work

The independence rule applies hardest here. **A session that built the thing cannot review it** — it defends every compromise because it knows why each one happened, which is exactly the sympathy the audience will not have.

Start fresh. Give it the URL and the success criteria. Nothing else. Not the design document, not the constraints, not the story.

---

## Being honest

This mode exists to tell you things you do not want to hear. Softening a verdict to be encouraging destroys its only value.

**"Competent and forgettable" is a valid, common, and useful verdict.** It is the one no other lens will say out loud, and it is the most actionable thing an audit can produce — because it points at S3, not at polish.

---

## Failure modes

| Failure | Countermeasure |
|---|---|
| Reviewing work from the session that built it | Fresh session, minimal context |
| Scoring against personal taste, not stated intent | Establish intent first |
| Reviewing screenshots instead of the live thing | Load it and use it |
| Softening to be encouraging | A no with a reason is the most useful output |
| Twelve equal findings | Name the one thing |
| Sliding from audit into fixing | That is a mode change; say so |
