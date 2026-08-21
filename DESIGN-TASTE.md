# DESIGN TASTE

The quality bar, written so it can be enforced instead of hoped for.

This exists because of one failure: **AI-generated UI is competent and forgettable.** It fails by averaging — given no constraint, a model produces the statistical centre of everything it has seen, which is a centred hero, three feature cards, a gradient, and rounded corners. Every rule here is a device for refusing the average.

Owned by the Design director. Applied at S3, checked at S5.

Motion: [DESIGN-MOTION.md](DESIGN-MOTION.md) · Images and assets: [DESIGN-ASSETS.md](DESIGN-ASSETS.md) · Scoring: [EVALUATION-RUBRICS.md](EVALUATION-RUBRICS.md)

---

## 1. Principles

**1.1 Concept before surface.** Every project has a thesis: one sentence naming the organising idea, from which decisions descend. Without one you have a mood, and a mood produces inconsistent output because there is nothing to check a decision against.

A thesis is testable:

- Weak: "Clean, modern, minimal with a premium feel."
- Strong: "A specimen sheet. The work is set like type in a catalogue, so type *is* the image and photography appears only as evidence."

The second tells you what to do when someone asks for a hero image. The first does not. **That is the test.**

**1.2 One idea, executed completely.** One strong device applied everywhere beats five clever moments. Consistency reads as intentional; variety reads as indecision.

**1.3 Art direction is a set of refusals.** If your direction cannot say what it rejects, it is not a direction. Every `DESIGN.md` carries a project-specific rejection list.

**1.4 The signature moment.** One thing a person would describe to someone else. Named at S3, built first at S4, protected at S5. If it gets cut for schedule, the project failed even if it shipped.

**1.5 Specificity over polish.** A rough site with a real point of view outperforms a polished site with none — for studios, juries, and serious clients alike.

**1.6 Restraint is not minimalism.** Minimalism is a style. Restraint is fewer elements each carrying more. A dense, maximal layout can be restrained if every element is load-bearing.

## 2. Typography

Carries more of the "expensive" signal than any other variable, and is where generic output is most detectable.

**2.1** Two families maximum, usually one, with weight and size doing the work.

**2.2 Choose a face with a position.** Inter, Roboto, Open Sans, and Poppins are competent and say nothing. An editorial serif, a grotesque with quirks, a variable display face, a well-chosen mono — these communicate before a word is read. Check the licence ([LIBRARY-POLICY.md](LIBRARY-POLICY.md)).

**2.3 Extreme scale contrast.** Generic design lives between 16px and 48px. Editorial work runs 14px captions against 120px+ display. **If your largest and smallest sizes are within 4x, the page will read as a template.** This is checkable by someone who is not a designer.

**2.4** Pick a ratio and hold it. Every size comes from the scale. Arbitrary sizes are the fastest visual tell of unconsidered work.

**2.5** Body copy 60-75 characters. Display type gets tight leading (0.9-1.05); body gets generous (1.5-1.7). **Display type set at body leading is the most common AI typography error.**

**2.6** Large type needs negative tracking; small labels need positive. Default tracking at 100px is always wrong.

**2.7 Type can be the image.** Before reaching for a picture, ask whether type at scale solves it. Usually it does, and it eliminates an asset dependency.

**2.8 Align to something.** Every block relates to a grid line, an optical edge, or another element. Text floating in centred boxes is the default AI layout.

## 3. Colour

**3.1 Start achromatic.** Build in black, white, and grey. Add colour only once the composition works without it. Colour used to rescue a weak layout never works.

**3.2 One accent** with a job. Two needs justification. Rainbow palettes are a tell.

**3.3 Off-black and off-white.** `#000` and `#fff` are harsh defaults. Warming or cooling them slightly moves a page toward "considered" more cheaply than anything else.

**3.4 Colour has a source** — the brand, the subject, the era, the material. "It looked nice" is not a source. Record it in `DESIGN.md`.

**3.5 Gradients need a reason.** Simulating a light source, a depth, or a material is fine. Purple-to-blue behind a hero because the space felt empty is not.

**3.6 Contrast is a design tool, then an accessibility rule.** Design it deliberately, then verify against WCAG. When a low-contrast direction fails, that is a **Design director decision**, not an implementer patch.

**3.7 Dark mode is a decision, not a default.** Decide explicitly and write it down.

## 4. Composition

**4.1 Asymmetry by default.** Centred everything reads as default.

**4.2 Use a real grid, then break it deliberately.** Twelve columns with three deliberate breaks reads as art direction. No grid reads as accident.

**4.3 Scale contrast between elements.** If every block is the same size there is no hierarchy. Something should be dramatically larger.

**4.4 Whitespace is structural.** Uniform padding everywhere produces a page with no argument. Vary section spacing by conceptual distance.

**4.5 Edge-awareness.** Full-bleed, hard margins, elements running off-canvas. Everything inside a centred `max-width: 1200px` is a template.

**4.6 Vertical rhythm.** A tall section followed by a compressed one creates pace.

**4.7 Density is allowed.** Editorial and archival work is often dense. Density with a clear reading order beats sparse with none.

## 5. Responsive

**5.1 Design the direction at both extremes**, not desktop-then-squash. A type-led direction at 375px is a different composition, not a narrower one.

**5.2** Type scales non-linearly. Use fluid clamps with intent and check the rendered result.

**5.3 The signature moment must survive mobile** or have a designed equivalent. A hover-dependent moment does not exist on a phone.

**5.4** Test at 375, 768, 900, 1280, 1920. The 900-1100 range breaks more layouts than any other.

**5.5** Touch targets 44px minimum. Hover states never load-bearing.

---

## 6. Anti-generic rules

**Blocking at QA** — a finding, not a preference. Unless declared as an accepted pattern (**R-PAT-1**, [ROUTER.md](ROUTER.md) section 10), in which case it drops to a Note and stays visible in the report. **There is no limit on how many** — the test is intentionality, not quantity.

| Rejected | Why | Do instead |
|---|---|---|
| Generic SaaS layout (centred hero, 3 cards, logo strip, CTA band) | The statistical average of the web | Derive layout from the thesis |
| Random gradients | Decoration standing in for an idea | Achromatic base, one motivated accent |
| Default glassmorphism | A 2021 default that adds nothing | Real material logic, or nothing |
| Repetitive card grids | Everything looks equally important | Vary scale, break the grid, editorial lists |
| Empty hero sections | Big type, no idea, wasted first screen | The first screen states the thesis |
| Generic AI copy ("Elevate your…", "Seamlessly…") | Instantly recognisable, kills credibility | Real, specific sentences |
| Arbitrary animation | Motion without meaning | [DESIGN-MOTION.md](DESIGN-MOTION.md) |
| Component-library soup | Five libraries, five visual languages | Own tokens ([LIBRARY-POLICY.md](LIBRARY-POLICY.md)) |
| Placeholder imagery | Signals unfinished work | [DESIGN-ASSETS.md](DESIGN-ASSETS.md) |
| Predictable typography (Inter/Poppins, 16-48px, one weight) | The default look | 2.2, 2.3 |
| Unmotivated bento grids | A trend applied without reason | Only if the content is genuinely modular |
| Overuse of rounded cards | Everything soft, nothing distinct | Vary radius, or commit to sharp |
| Overuse of shadows | Fake depth for a flat medium | One elevation level, or none |
| Unnecessary dashboards | Enterprise cosplay | Only when the user monitors changing data |
| Decorative motion | No purpose | Cut it |

### The two tests

**Five-second test** — show the page for five seconds. If they can only describe the *category* ("some kind of agency site"), the direction failed.

**Swap test** — replace the logo and copy with a different company's. If it still works perfectly, it is not art-directed; it is a template with your content in it.

---

## 7. Building an original direction

Reference *analysis* — how to extract mechanisms from a reference — is [skills/reference-analysis.md](skills/reference-analysis.md). This is what you do with the results.

1. **Pool the mechanisms** from all references, attribution dropped.
2. **Pick two or three that conflict.** Conflict is what makes a direction original. Three harmonious mechanisms from three similar sites is a copy of the genre; a rigorous archival grid plus playful physical motion is a direction.
3. **Ground it in the subject.** Apply them to *this* project's content. The same mechanism on a boxing game and a law firm produces entirely different work. **This is where originality actually comes from.**
4. **Write the thesis** — one sentence, no adjectives that could describe anything.
5. **Write the rejection list** — minimum three, specific to this project.

### Avoiding a copy

- **No single reference contributes more than two mechanisms** ([skills/reference-analysis.md](skills/reference-analysis.md)).
- **Never lift layout structure.** Mechanisms transfer; page structure does not.
- **The attribution test:** could the referenced designer recognise their own site in your output? If yes, you copied. A shared *sensibility* is the goal.
- **Record it.** `DESIGN.md` has a mandatory "What NOT to copy" section.

---

## 8. G1 direction check

At G1 the direction is checked qualitatively, not scored. **Numeric scoring happens at S5, by a reviewer who did not write the direction** — see [EVALUATION-RUBRICS.md](EVALUATION-RUBRICS.md) for why.

Answer these, in writing:

1. Does the thesis tell you what to do when someone asks for a hero image?
2. Does it avoid "clean", "modern", "minimal", "premium", "sleek", "elegant"?
3. Is the largest-to-smallest type ratio at least 4x?
4. Does the palette have a stated source that is not "it looked nice"?
5. Does motion have a purpose from the five in [DESIGN-MOTION.md](DESIGN-MOTION.md)?
6. Is the signature moment named, with a mobile equivalent?
7. Are there three or more specific rejections?
8. Are all asset dependencies resolved?
9. Would this survive the swap test?
10. Which of the anti-generic rows does this direction come closest to, and why is it not that?

**Any "no" is a blocker at G1.** Question 10 is the one that catches self-deception — every direction is near something generic, and naming which one forces you to articulate the difference.
