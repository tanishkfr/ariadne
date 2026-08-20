# DESIGN TASTE

The quality bar, written down so it can be enforced instead of hoped for.

This file exists because of one specific failure: **AI-generated UI is competent and forgettable.** It fails by averaging. Given no constraint, a model produces the statistical centre of everything it has seen, which is a centred hero, three feature cards, a gradient, and rounded corners. Every rule here is a device for refusing the average.

Owned by the Design director ([AGENT-ROLES.md](AGENT-ROLES.md)). Applied at S3, enforced at S5.

---

## 1. Design principles

**1.1 Concept before surface.** Every project has a thesis: one sentence naming the organising idea. Decisions descend from it. Without a thesis you get a mood, and a mood produces inconsistent output because there is nothing to check a decision against.

A thesis is testable. Compare:

- Weak: "Clean, modern, minimal with a premium feel."
- Strong: "A specimen sheet. The work is set like type in a catalogue: the type *is* the image, and photography appears only as evidence."

The second one tells you what to do when someone asks for a hero image. The first does not.

**1.2 One idea, executed completely.** A site with one strong device applied everywhere beats a site with five clever moments. Consistency is what reads as intentional; variety reads as indecision.

**1.3 Art direction is a set of refusals.** If your direction cannot say what it rejects, it is not a direction. Every `DESIGN.md` has an explicit anti-pattern list for that project, not just the global one.

**1.4 The signature moment.** Every project has one thing a person would describe to someone else. Identify it at S3, build it first at S4, protect it at S5. If it gets cut for schedule, the project has failed even if it ships.

**1.5 Specificity over polish.** A rough site with a real point of view outperforms a polished site with none, for every audience that matters here: studios, juries, serious clients.

**1.6 Restraint is not minimalism.** Minimalism is a style. Restraint is choosing fewer elements and making each one carry more. A dense, maximal layout can be restrained if every element is load-bearing.

---

## 2. Typography principles

Typography carries more of the "expensive" signal than any other variable. It is also where generic output is most detectable.

**2.1 Two families maximum.** Usually one, with weight and size doing the work. A third family needs a reason in `DESIGN.md`.

**2.2 Choose a face with a position.** Inter, Roboto, Open Sans and Poppins are competent and say nothing. A face with real character — an editorial serif, a grotesque with quirks, a variable display face, a well-chosen mono — communicates before a word is read. Check the licence (see [LIBRARY-POLICY.md](LIBRARY-POLICY.md)).

**2.3 Extreme scale contrast.** Generic design lives between 16px and 48px. Real editorial work runs 14px captions against 120px+ display type. If your largest and smallest sizes are within 4x, the page will read as a template.

**2.4 Set a real scale.** Pick a ratio and hold it. Every size on the page comes from the scale. Arbitrary sizes are the fastest visual tell of unconsidered work.

**2.5 Measure and leading.** Body copy: 60-75 characters. Display type gets tight leading (0.9-1.05); body gets generous leading (1.5-1.7). Display type set at body leading is the single most common AI typography error.

**2.6 Tracking follows size.** Large type needs negative tracking. Small caps and small labels need positive tracking. Default tracking at 100px is always wrong.

**2.7 Type can be the image.** Before reaching for a picture, ask whether type at scale solves it. This eliminates the most common asset dependency and usually looks better.

**2.8 Align to something.** Every text block relates to a grid line, an optical edge, or another element. Text floating in centred boxes with no relationship is the default AI layout.

---

## 3. Colour principles

**3.1 Start achromatic.** Build in black, white, and greys. Introduce colour only when the composition works without it. Colour used to rescue a weak layout never works.

**3.2 One accent.** One colour with a job. Two accents require justification in `DESIGN.md`. Rainbow palettes are a tell.

**3.3 Off-black and off-white.** `#000` and `#fff` are harsh and default. Warm or cool them slightly. This single change moves a page toward "considered" more cheaply than anything else.

**3.4 Colour has a source.** From the brand, the subject matter, the era being referenced, the material being evoked. "It looked nice" is not a source. Record the source in `DESIGN.md`.

**3.5 Gradients need a reason.** A gradient that simulates a light source, a depth, or a material is fine. A purple-to-blue gradient behind a hero because the space felt empty is on the reject list.

**3.6 Contrast is a design tool, not only an accessibility rule.** Design the contrast deliberately, then verify it against WCAG. When a low-contrast direction fails, it is a Design director decision, not an implementer patch. See [AGENT-ROLES.md](AGENT-ROLES.md) role 9.

**3.7 Dark mode is a decision, not a default.** If the direction is a printed specimen sheet, a dark mode may be wrong. Decide explicitly and write it down.

---

## 4. Composition principles

**4.1 Asymmetry by default.** Centred everything is the default and reads as default. Asymmetric layouts need a grid to hold them together, which is the actual work.

**4.2 Use a real grid, then break it deliberately.** A 12-column grid with three deliberate breaks reads as art direction. No grid reads as accident.

**4.3 Scale contrast between elements.** If every block is roughly the same size, there is no hierarchy and the eye has nowhere to go. Something should be dramatically larger.

**4.4 Whitespace is structural.** Space separates ideas and creates rhythm. Uniform padding everywhere produces a page with no argument. Vary section spacing according to conceptual distance.

**4.5 Edge-awareness.** Full-bleed, hard margins, and elements that run off-canvas are compositional tools. A page where everything sits inside a `max-width: 1200px` centred container is a template.

**4.6 Vertical rhythm.** Sections should not all be the same height with the same padding. A tall section followed by a compressed one creates pace.

**4.7 Density is allowed.** Editorial and archival work is often dense. Density with a clear reading order beats sparse with none.

---

## 5. Image and texture principles

**5.1 Real over generated over stock.** In that order. Stock is last because it is the fastest path to generic.

**5.2 No placeholder imagery, ever.** If an image does not exist, either generate a real one, or change the direction so it is not needed. Grey boxes and lorem-ipsum photography are forbidden in anything presented for review.

**5.3 Images need treatment.** Consistent crop logic, grain, duotone, a border rule, a mask shape, a grid relationship. Untreated images pasted into a layout look pasted in.

**5.4 Texture is cheap differentiation.** Paper grain, noise, print misregistration, halftone, scanlines. A small amount of texture removes the plastic quality of default web rendering. It must be motivated by the thesis.

**5.5 Prefer CSS/SVG over raster.** Sharper, smaller, animatable, no licensing question.

**5.6 Every asset has provenance.** Source, licence, dimensions, and whether it can ship, in [`ASSETS.md`](templates/ASSETS.md). No exceptions for client work.

---

## 6. Motion principles

**6.1 Motion must mean something.** Every animation answers: orientation, feedback, continuity, hierarchy, or character. If it answers none, cut it.

**6.2 Fast in, slow out.** Interface response should be immediate (120-200ms). Entrances can be slower (300-600ms). Anything over 800ms without a reason is a delay, not a delight.

**6.3 Easing is characterisation.** Linear reads mechanical. A sharp ease-out reads crisp and expensive. A spring reads playful. Pick easing from the thesis and reuse it. Default `ease-in-out` everywhere is a tell.

**6.4 Choreograph, don't decorate.** Stagger should follow reading order. Related elements move together, unrelated elements do not. Ten elements each with their own fade-in is noise.

**6.5 Scroll-triggered fade-ins are the default and are boring.** If everything fades up 20px on scroll, you have applied a plugin, not designed motion. Use scroll for pinning, transformation, revealing structure, or narrative pacing.

**6.6 Motion must survive `prefers-reduced-motion`.** Not "animations off" — a designed reduced state. Content must never depend on an animation to appear. This is a blocking QA check.

**6.7 60fps or cut it.** Animate `transform` and `opacity`. If a motion drops frames on a mid-range machine, it is not shipping.

**6.8 The signature moment usually lives here.** Motion is often where a site becomes memorable. Spend the budget there and keep the rest quiet.

---

## 7. Responsive principles

**7.1 Design the direction at both extremes.** Not desktop-then-squash. A type-led direction at 375px is a different composition, not a narrower one.

**7.2 Type scales non-linearly.** A 120px desktop display size is not 120px on mobile, and it is not 40px either. Use fluid clamps with intent, and check the actual rendered result.

**7.3 The signature moment must survive mobile,** or have a designed mobile equivalent. A hover-dependent signature moment does not exist on a phone.

**7.4 Test at real sizes:** 375, 768, 1280, 1920. Plus the awkward middle (900-1100) where most layouts break.

**7.5 Touch targets 44px minimum,** hover states never load-bearing, and no content reachable only by hover.

---

## 8. Anti-generic rules

These are **blocking**. Any of these appearing in a build is a QA finding at S5, not a matter of preference.

| Rejected | Why | Do instead |
|---|---|---|
| Generic SaaS layout (centred hero, 3 cards, logo strip, CTA band) | The statistical average of the web | Derive layout from the thesis |
| Random gradients | Decoration standing in for an idea | Achromatic base, one motivated accent |
| Default glassmorphism | 2021 default, adds nothing | Real material logic, or nothing |
| Repetitive card grids | Everything looks equally important | Vary scale, break the grid, use editorial lists |
| Empty hero sections | Big type, no idea, wasted first screen | The first screen states the thesis |
| Generic AI copy ("Elevate your...", "Seamlessly...") | Instantly recognisable, kills credibility | Real, specific sentences. See [skills/content-strategy.md](skills/content-strategy.md) |
| Arbitrary animation | Motion without meaning | Section 6.1 |
| Component-library soup | Five libraries, five visual languages | Own tokens; libraries as reference. See [LIBRARY-POLICY.md](LIBRARY-POLICY.md) |
| Placeholder imagery | Signals unfinished work | Section 5.2 |
| Predictable typography (Inter/Poppins, 16-48px, one weight) | The default look | Sections 2.2, 2.3 |
| Unmotivated bento grids | A 2023 trend applied without reason | Only if the content is genuinely modular |
| Overuse of rounded cards | Everything soft, nothing distinct | Vary radius, or commit to sharp |
| Overuse of shadows | Fake depth for a flat medium | One elevation level, or none |
| Unnecessary dashboards | Enterprise cosplay | Only when the user monitors changing data |
| Decorative motion with no purpose | Section 6.1 | Cut it |

### The five-second test

Show the page to someone for five seconds. Ask what it was about. If they can only describe the *category* ("some kind of agency site"), the direction has failed. They should be able to name something specific.

### The swap test

Replace the logo and copy with a different company's. If the design still works perfectly, it is not art-directed — it is a template with your content in it.

---

## 9. Reference analysis process

Owned by [skills/reference-analysis.md](skills/reference-analysis.md). Method:

**Step 1 — Collect at least three.** One reference produces imitation. Three force synthesis. See [references/visual-references.md](references/visual-references.md).

**Step 2 — Extract mechanisms, not surfaces.** For each reference, answer:

- What is the organising principle? (grid, sequence, material, metaphor, constraint)
- What does the type do that a default would not?
- What is the colour strategy?
- What does motion do, structurally?
- What is deliberately absent?
- **Why does it feel expensive?** Usually: restraint, extreme type contrast, real photography, or motion that responds precisely.

**Step 3 — Write it as mechanisms.**

- Surface (useless): "black background with big white serif type"
- Mechanism (usable): "a single achromatic field so the only variable is type scale, which makes size alone carry hierarchy"

Mechanisms transfer to a different subject. Surfaces do not, which is why copying a surface produces a knock-off.

**Step 4 — Name the tension.** Most memorable work holds two opposed qualities: rigorous but playful, archival but immediate, brutal but warm. Name the tension you are aiming for; it will resolve dozens of small decisions.

---

## 10. Building an original direction from multiple references

The synthesis method, in five steps.

1. **List mechanisms** from all references in one place, ignoring which came from where.
2. **Pick two or three mechanisms that conflict.** Conflict is what makes a direction original. A rigorous archival grid plus playful physical motion is a direction. Three harmonious mechanisms from three similar sites is a copy of the genre.
3. **Ground it in the subject.** Apply the mechanisms to *this* project's actual content. A grid mechanic applied to a boxing game and to a law firm produce entirely different work. This is where originality actually comes from.
4. **Write the thesis** as one sentence, no adjectives that could apply to anything ("clean", "modern", "premium").
5. **Write the rejection list.** What this direction refuses. Minimum three, specific to this project.

### How to avoid copying any single source

Hard rules:

- **No single reference contributes more than two mechanisms.** Three or more means you are rebuilding that site.
- **Never lift the layout structure.** Mechanisms transfer; page structure does not.
- **Change the domain.** If the reference is a photography portfolio and you are making a boxing game, the mechanism must survive translation. If it cannot, it was a surface.
- **The attribution test:** could the referenced designer look at your output and recognise their site? If yes, you copied. If they would recognise a shared *sensibility*, you synthesised.
- **Record it.** `DESIGN.md` has a mandatory "What NOT to copy" section naming the specific things you are deliberately not taking.

---

## 11. Visual quality scorecard

Scored by the Design director at G1 (against the direction) and again at S5 (against the build). 1-5 per criterion.

| # | Criterion | 1 | 3 | 5 |
|---|---|---|---|---|
| 1 | **Concept clarity** | No thesis | Thesis exists, loosely applied | Thesis visible in every decision |
| 2 | **Typographic quality** | Default face, default scale | Considered face, safe scale | Distinctive face, extreme contrast, real scale |
| 3 | **Compositional strength** | Centred, uniform | Grid present, some hierarchy | Asymmetric, deliberate breaks, strong hierarchy |
| 4 | **Colour discipline** | Random / rainbow / gradients | One accent, safe neutrals | Motivated palette with a stated source |
| 5 | **Material quality** | Flat defaults | Some texture or treatment | Consistent material logic throughout |
| 6 | **Motion purpose** | None, or decorative | Functional | Choreographed, characterful, reduced-motion designed |
| 7 | **Signature moment** | None | Present but quiet | Genuinely memorable, survives mobile |
| 8 | **Anti-generic compliance** | 3+ violations | 1-2 violations | Zero violations |
| 9 | **Craft** | Misalignments, inconsistent spacing | Mostly consistent | Every value from the system |
| 10 | **Originality** | Recognisably a reference | Recognisably a genre | Recognisably its own |

**Thresholds**

- **Below 35/50** — not shippable. Return to S3.
- **35-42** — shippable for a class project or an experiment. Not for a portfolio or a client.
- **43+** — portfolio and client standard.
- **Any single criterion at 1** — blocking regardless of total. A 45 with zero signature moment is a failure, not a pass.

Score honestly. A scorecard that always returns 44 is measuring nothing, and its only effect is to make you feel finished. Record scores in `QA.md` with one sentence of evidence per criterion.
