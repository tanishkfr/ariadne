# SKILL: design-direction

**Trigger** — discovery is complete, references are analysed, nothing has been designed yet. S3.
**Owner** — Design director
**Inputs** — `PROJECT.md`, `RESEARCH.md`, pooled mechanisms from [reference-analysis](reference-analysis.md)
**Output** — [`DESIGN.md`](../templates/DESIGN.md) and the G1 presentation

**This is the stage that decides whether the output looks generic.** Every rule in [DESIGN-TASTE.md](../DESIGN-TASTE.md) applies here, not at S4. Fixing genericness at build time costs ten times more and usually fails.

---

## Method

**1. Write the thesis.** One sentence naming the organising idea. Specific enough that a different designer following it would produce recognisably the same thing, and a generic template would fail it.

- Weak: "Clean, modern, minimal with a premium feel."
- Strong: "A specimen sheet — the work is set like type in a catalogue, so type *is* the image and photography appears only as evidence."

Test it: does it tell you what to do when someone asks for a hero image? If not, it is a mood, not a thesis.

**2. Build the thesis from conflict.** Take the pooled mechanisms and pick two or three that **conflict**. Conflict is what makes a direction original. Three harmonious mechanisms from three similar sites is a copy of the genre. A rigorous archival grid plus playful physical motion is a direction.

**3. Ground it in the subject.** Apply the mechanisms to *this* project's actual content. This is where originality actually comes from — the same mechanism applied to a boxing game and a law firm produces entirely different work.

**4. Derive, do not decide.** Every subsequent choice descends from the thesis and is written with its reason:

- **Typography** — face, scale ratio, extreme size contrast, leading, tracking. See [DESIGN-TASTE.md](../DESIGN-TASTE.md) section 2.
- **Colour** — achromatic base first, one accent with a stated source. Section 3.
- **Layout** — grid, where it breaks and why, edge behaviour, density. Section 4.
- **Material** — texture, image treatment, elevation. Section 5.
- **Motion** — what motion is *for* in this project. Section 6, and [DESIGN-MOTION.md](../DESIGN-MOTION.md).
- **Responsive** — how the direction changes at 375, not how it shrinks. Section 7.

A decision without a reason traceable to the thesis is a decision that will drift at S4.

**5. Name the signature moment** ([DESIGN-TASTE.md](../DESIGN-TASTE.md) 1.4). Where it lives, what happens, why it is memorable, and its mobile equivalent. Build it first at S4 — anything left to the end gets cut.

**6. Write the project's rejection list.** Minimum three, specific to this project, beyond the global anti-generic table. "No scroll-triggered fade-ups anywhere" is a real constraint. "Avoid generic design" is not.

**7. Resolve the asset question now** ([DESIGN-ASSETS.md](../DESIGN-ASSETS.md)). Does the direction depend on assets that do not exist? Either commission them, generate them ([DESIGN-ASSETS.md](../DESIGN-ASSETS.md)), or **change the direction so it does not need them.** A type-led direction eliminates the dependency entirely and is usually the better answer.

**8. Score it.** The ten-criterion scorecard, [EVALUATION-RUBRICS.md](../EVALUATION-RUBRICS.md), scored against the *direction*. Below 35 means the direction is not ready — do not present it.

---

## G1 presentation

```
G1: DIRECTION LOCK
Thesis:      <one sentence>
Tension:     <the two opposed qualities>
Typography:  <faces, scale, why>
Colour:      <palette, source>
Layout:      <grid, breaks, why>
Motion:      <what motion is for here>
Signature:   <the memorable moment + its mobile form>
Rejects:     <this project's specific anti-patterns, 3+>
Assets:      <resolved how>
Scorecard:   <n>/50, lowest criterion named
Risks:       <what could make this fail>
```

Nothing is built until this is approved. If you cannot state what the direction rejects, there is no direction and G1 fails.

---

## Done when

Thesis written and testable · every choice traceable to it · signature moment named with a mobile equivalent · rejection list has 3+ specific entries · assets resolved · scorecard ≥35 · G1 approved.

---

## Failure modes

| Failure | Countermeasure |
|---|---|
| A mood board instead of a thesis | Apply the hero-image test to the sentence |
| Adjectives that could describe anything | Ban "clean", "modern", "premium" from the thesis |
| Harmonious mechanisms producing a genre copy | Step 2 requires conflict |
| Direction that only works at 1440px | Step 4 designs 375 as a composition, not a squash |
| Signature moment deferred to S4 | Named at S3, built first |
| Scoring the direction generously to move on | A scorecard that always returns 44 measures nothing |
| Building before G1 because the deadline is tight | Waiting is cheaper than rebuilding. Always. |
