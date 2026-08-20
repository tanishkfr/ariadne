# SKILL: evaluation

**Trigger** — work is complete, or an audit is requested.
**Owner** — Portfolio/client reviewer and the other reviewer roles · **Class** — `R1`
**Inputs** — the deployed work, `PROJECT.md` success criteria
**Output** — scored rubrics and a recommendation

Rubrics: [EVALUATION-RUBRICS.md](../EVALUATION-RUBRICS.md). This file is how to run one honestly.

---

## The independence rule

**Run evaluation in a session that did not build the thing.**

A reviewer holding the build context defends the build. It knows the constraint that caused each compromise, it remembers how hard the hard part was, and it will score accordingly. That is exactly the sympathy the actual audience will not have.

Give the reviewer: the URL, the success criteria from `PROJECT.md`, and the rubric. Nothing else. Not the design document, not the constraints, not the story.

---

## Method

**1. Pick the lenses.** Per [QA-POLICY.md](../QA-POLICY.md) section 4.3, or whichever the request named. Two to four is right. Nine is theatre.

**2. Run each lens in a separate session.** They contaminate each other — a reviewer that just scored accessibility unconsciously weights it in the next pass.

**3. Look before scoring.** Load it. Scroll it. Use it on a phone. Try the primary task. Five minutes of actual use beats any amount of reasoning about a description.

**4. Score against the rubric definitions, not against effort.** Remember what 3 means: competent, nothing wrong, nothing memorable. **3 is the AI default and it is the score to fear.** Most work is a 3. Recording it as a 4 to be kind destroys the only signal the rubric produces.

**5. Evidence for everything below 4.** Where, what, why — the specific route, element, and viewport, and which criterion it fails. A score without evidence is an opinion and will not survive disagreement.

**6. Every finding carries a fix.** What to change, roughly what it costs, what it risks. A finding without a fix is a complaint.

**7. Name the one thing.** The single highest-leverage change. Mandatory. A list of twelve equally-weighted findings gets ignored; one clear priority gets acted on.

**8. Answer the lens's test question** honestly. "Would I put this in the showreel?" "Would I pay the second invoice?" "Would I remember this tomorrow?" A no with a reason is the most valuable output an evaluation produces.

---

## Consolidating multiple lenses

1. All Blocking findings first — every one stops G3.
2. Majors ranked by how many lenses raised them. Something three lenses independently noticed is real.
3. Name conflicts explicitly rather than resolving them silently. Conversion versus creative direction is a genuine tension, and the mode decides: premium client work weights conversion, portfolio work weights creative direction.
4. **Do not average scores across lenses.** The average of nine perspectives is the statistical centre — which is precisely what this system exists to avoid producing.

---

## Evaluating "feel"

The thing rubrics struggle with. Three usable proxies:

- **Five-second test** — show it for five seconds. Can they describe something specific, or only the category? Category-only means the direction failed.
- **Swap test** — replace the logo and copy with a different company's. Still works perfectly? Then it is a template with content in it.
- **Recall test** — describe it a day later without looking. What survives is what the work actually communicates. Usually one thing, sometimes none.

If all three fail, the work is competent and forgettable, and no amount of polish fixes it. That is an S3 problem surfacing at S5 and the honest recommendation is to rework the direction.

---

## Done when

Each lens scored with evidence · fixes attached · the one thing named · the test question answered · findings consolidated with conflicts named.

---

## Failure modes

| Failure | Countermeasure |
|---|---|
| Reviewing work you built | Separate session, minimal context |
| Generous scoring | 3 means forgettable; say so |
| Findings without evidence | Where, what, why |
| Twelve equal findings | Name the one thing |
| Averaging lens scores | Consolidate, do not average |
| Scoring from a description | Load it and use it |
| Softening a verdict to be encouraging | A no with a reason is the most useful output |
