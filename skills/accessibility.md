# SKILL: accessibility

**Trigger** — before any G3.
**Owner** — Accessibility reviewer · **Class** — `R6` + `R4`
**Inputs** — the running build, `DESIGN.md`
**Output** — the accessibility section of [`QA.md`](../templates/QA.md)

Checklist: [QA-POLICY.md](../QA-POLICY.md) section 3.7. Rubric: [EVALUATION-RUBRICS.md](../EVALUATION-RUBRICS.md) lens 4.

**Automated tools catch roughly a third of real problems.** The manual passes below are the ones that matter, and they are fast — the full manual sweep on a small site is about twenty minutes.

---

## Method

**1. Run the automated audit** (axe, Lighthouse, or equivalent). Fix what it finds. Then treat it as finished, because it is: a clean automated report says almost nothing about whether the site is usable.

**2. Keyboard pass.** Unplug the mouse, genuinely. Tab through every flow.

- Can every action be completed?
- Is focus **visible at every stop**? (Removed focus outlines are the most common failure in art-directed work — and a designed focus state is better-looking than the default anyway.)
- Is the order logical, matching the visual order?
- Any traps — anywhere focus enters and cannot leave?
- Does Escape close overlays? Does focus return where it came from?
- Are custom controls (a `div` acting as a button) operable by Enter and Space?

**3. Contrast, measured on rendered pixels.** Not on the token values — on what actually renders, including text over images, over gradients, and in every state. 4.5:1 body, 3:1 large text and UI boundaries.

When a deliberately low-contrast direction fails, that is a **Design director decision**, not an implementer patch. Route it upward. Quietly darkening the palette to pass a check breaks the direction.

**4. Structure.** One `h1`. No skipped heading levels. Landmarks present. Images have `alt` — empty `alt=""` for decorative, which is a real answer, not a cop-out. Lists are lists. Buttons are buttons.

**5. Reduced motion.** Enable the OS preference, reload, and check that **content still appears**. Anything revealed by an animation must exist without it. A reduced state should be *designed*, not merely disabled.

**6. Forms.** Every input has a real label. Errors are tied to the input programmatically, stated in text, and not communicated by colour alone. Required fields are marked in more than one way.

**7. Independence.** Nothing conveyed by colour, hover, or motion alone. Hover-only content does not exist on touch devices — this is both an accessibility and a mobile failure, and it catches signature moments built around hover.

**8. Zoom to 200%.** Nothing lost, nothing overlapping, no horizontal scroll on body content.

---

## The relationship with art direction

Ambitious visual work and accessibility conflict less often than people assume. The genuine tensions:

| Tension | Resolution |
|---|---|
| Low-contrast palette | Design director decides. Often solved by raising contrast on body text only and keeping the low-contrast treatment for large display type. |
| Custom cursors, hover-driven interactions | Must have a keyboard and touch equivalent. This is a design requirement, decided at S3. |
| Heavy scroll choreography | Reduced-motion state designed at S3, not retrofitted |
| Removed focus outlines | Never. Design a better focus state instead. |
| Text over imagery | A scrim, a treatment, or move the text. All three are design decisions. |

**Decide these at S3, not S5.** Accessibility discovered at QA is a rebuild; accessibility designed into the direction costs nothing.

---

## Done when

Automated audit clean · keyboard pass complete on every flow · contrast measured on rendered pixels · structure verified · reduced-motion tested by actually enabling it · forms checked · nothing hover-only · 200% zoom passes.

**Any criterion failing at the lowest level is Blocking regardless of the total.** Blocking findings stop G3 until fixed or waived by you in writing in `QA.md`.

---

## Failure modes

| Failure | Countermeasure |
|---|---|
| Treating a clean axe report as done | Step 1 is the start, not the finish |
| Contrast checked on tokens, not pixels | Measure what renders, in every state |
| Reduced motion means content never appears | Step 5: reload and confirm content exists |
| Focus outlines removed for aesthetics | Design a better one |
| Hover-only signature moment | Caught at S3, not S5 |
| Implementer quietly changing the palette to pass | Route contrast failures to the Design director |
| Accessibility as a final checklist | It is a direction decision made at S3 |
