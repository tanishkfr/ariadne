# MODE: Client or portfolio

A site whose job is reputation. One mode with a `client` flag, because the process is identical and only four things change.

---

## The flag

Ask once: **is this yours, or someone else's?**

| | Portfolio (yours) | Client (someone else's) |
|---|---|---|
| Review lens | Portfolio reviewer | Strict client |
| Privacy | Normal | [PRIVACY-POLICY.md](../PRIVACY-POLICY.md) applies; private repo |
| Costs | Yours; Vercel Hobby is free | **Billed to the client**; Vercel needs a paid plan |
| Approval chain | You | **Ask at S1 who signs off** |

Everything else — questions, documents, skills, gates, quality bar — is the same.

---

## Detection

**Reached when the `OBJECT` is a site whose job is reputation** — yours or someone else's.

**The word "portfolio" does not route here** ([ROUTER.md](../ROUTER.md) R-DEST-1). "Create my portfolio" does, because the object is the site. "Create something for my portfolio" does not — there the portfolio is the *destination* and the object is unresolved, which is LOW confidence and a question.

**Not this mode if:** state outlives the session ([product app](product-app.md)), or `ACTION = ANALYZE` ([audit / review](audit-review.md)).

**"Redesign my portfolio" is this mode** — a TRANSFORM of direction, routed by its target (R-XFM-1), not a review.

## Questions

1. **Client:** who are they and what do they actually sell? · **Portfolio:** which 3-5 projects, and what should each prove? *(no default either way — this is the brief)*
2. Who is the reader, and what must they do or feel? *(default: portfolio → studios and serious clients; client → understand the offer and make contact)*
3. What assets exist — logo, photography, copy, brand rules? *(default: assume only a logo)*
4. Hard deadline? *(default: none)*
5. **Client:** what brand rules cannot be broken? · **Portfolio:** what is the one thing you want remembered? *(default: none / no default)*

**Also establish for client work, even though it is not one of the five: who signs off.** A stakeholder appearing at S5 with opinions is the most common cause of rework, and one question at S1 prevents it.

## Assumptions

Home / work / about / contact until told otherwise · real copy drafted by you, never lorem ipsum · no CMS unless a non-developer edits copy · no backend, form to a third-party service · content co-located with components.

## Documents

**Required:** `PROJECT.md`, `DESIGN.md`, `HANDOFF.md`, `QA.md`
**Usually also:** `AGENTS.md`, `ASSETS.md` (if image-led), `RETROSPECTIVE.md`
**Only if warranted:** `ARCHITECTURE.md` (>10 components), `TASKS.md` (>5 tasks), `RESEARCH.md`

## Skills

[intake](../skills/intake.md) — **challenge pass mandatory** · [reference-analysis](../skills/reference-analysis.md) · [design-direction](../skills/design-direction.md) · [component-research](../skills/component-research.md) · [EVALUATION-RUBRICS.md](../EVALUATION-RUBRICS.md)

## Gates

G1 (non-negotiable), G2 (**every font licence**), G3, G4.

## Quality bar

Creative director **40+/50** · the mode's review lens **32+/40** (client: 35+ to present) · zero undeclared anti-generic patterns · zero placeholders · works on a real phone.

---

## The traps

**"Clean, high-end" is not a brief.** It describes a category, and every competitor would satisfy it. Push until you have something like: *this client sells a slow, expensive, handmade product while every competitor looks fast and cheap — so the site should feel slow on purpose.* That is a direction.

**Showing everything.** Four strong pieces beat eight mixed ones. **The weakest piece sets the perceived level**, and a reviewer with 60 seconds will find it.

**Case studies that describe features.** "I built a filter system" is a feature. "The filter had to work before the data loaded, so I inverted the fetch order" is a decision. Reviewers hire for decisions.

**Assets that "will come later".** They arrive late or never. Make the direction type-led so photography enhances rather than blocks, and design a fallback per image slot ([DESIGN-ASSETS.md](../DESIGN-ASSETS.md)).

**Font licensing.** Free-for-personal-use faces on client work are a real liability. Caught at S3 via G2, it is one email. Caught after launch, it is a rebuild of the type system.

**Designing for yourself instead of the reader.** A portfolio is a persuasion document with an audience and a goal. The challenge pass exists to make you say which opportunity it is for.

## Failure modes

| Failure | Countermeasure |
|---|---|
| Building before the direction is approved | G1, without exception |
| A stakeholder appearing at S5 | Establish the approval chain at S1 |
| Blocked on assets that never arrive | Fallback designed at S3 |
| Absorbing a font licence cost | Quote it; it is a line item |
| Client work on a free hosting tier | Check the terms; bill the plan to the project |
| Endless polish, never shipped | Set a real deadline at S1, even an artificial one |
| The site is better than the work in it | The portfolio-reviewer lens will say so |
