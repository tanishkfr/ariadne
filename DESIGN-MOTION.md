# DESIGN: MOTION

Principles and procedure for anything that moves. Separate from [DESIGN-TASTE.md](DESIGN-TASTE.md) so a motion task loads ~900 words instead of 2,600.

Owned by the Design director (purpose) and the Implementer (execution).

---

## The gate every animation passes

**What does this tell the user?** One of five answers is acceptable:

| Purpose | Example |
|---|---|
| **Orientation** | Where did this come from, where did it go |
| **Feedback** | Your action registered |
| **Continuity** | This is the same object, moved |
| **Hierarchy** | Look here first |
| **Character** | This product has a personality |

**If the answer is "it looks nice", cut it.** Every animation records its purpose in `DESIGN.md`.

---

## Procedure

**1. Decide what motion is FOR in this project** before animating anything. Some directions are still and should be — a specimen-sheet thesis probably wants type that does not bounce. Deciding "motion here is feedback only, never decoration" resolves fifty later decisions at once.

**2. Choose the technology per interaction.**

| Need | Reach for |
|---|---|
| Hover, focus, simple state transitions | **Plain CSS** — cheapest, most robust. Try first. |
| Component enter/exit, gestures, layout shifts, springs | **Motion.dev** — approved default |
| Multi-step timelines, scroll choreography, pinning, morphing | **GSAP** — conditional; real weight |
| Continuous or generative motion | Canvas / WebGL — only when it is the point |
| Smooth scroll | Lenis — conditional; overrides native scroll, must respect reduced-motion |

Start at the top and move down only when the row above genuinely cannot do it. A surprising amount of good motion is CSS transitions with well-chosen easing.

**Do not ship two motion libraries** without a stated reason in `ARCHITECTURE.md`. That is a G2 conversation ([LIBRARY-POLICY.md](LIBRARY-POLICY.md)).

**3. Set the timing system.** A small set, reused. Arbitrary durations are as much a tell as arbitrary font sizes.

- Interface response: **120-200ms**
- Entrances and transitions: **300-600ms**
- Deliberate narrative motion: up to **1000ms**, with a reason
- Longer is a delay, not a delight

**4. Easing is characterisation.** Linear reads mechanical. Sharp ease-out reads crisp and expensive. Springs read playful. Pick from the thesis, define it as a token, reuse it. **Default `ease-in-out` everywhere is the motion equivalent of Inter at 16px.**

Fast in, slow out: response immediate, resolution eased.

**5. Choreograph.** Stagger follows reading order. Related elements move together; unrelated ones do not. Ten elements each fading in independently is noise, not choreography.

**6. Design the reduced-motion state.** Not "animations off" — a **designed** state. Content must appear and be usable. Test by actually enabling the OS preference and reloading. Blocking QA check.

**7. Verify 60fps.** Animate `transform` and `opacity`. Watch for layout thrash and animated `width` / `filter` / `box-shadow`. If it drops frames on a mid-range machine, it is not shipping.

**8. Test the awkward cases.** Fast scroll · refresh mid-page · back-navigation · resize during animation · interrupting one animation with another. Scroll-triggered work fails here far more often than in normal use.

---

## Scroll-triggered motion

**Everything fading up 20px on scroll is the single most recognisable AI motion pattern.** It signals that a plugin was applied, not that motion was designed.

Legitimate uses: pinning a section while something changes · transforming an element through a range · revealing structure progressively · pacing a narrative · parallax with a real depth logic.

If you are using scroll only to delay content appearing, remove it. It makes the page slower and communicates nothing.

**GSAP ScrollTrigger caution:** it makes scroll effects easy, which is exactly why they are everywhere and mostly generic.

---

## Where the signature moment usually lives

Motion is often where a site becomes memorable. Spend the budget there and keep the rest quiet. A hover-dependent signature moment **does not exist on a phone** — design the touch equivalent at S3, not S5.

---

## Done when

Every animation has a recorded purpose · timing and easing come from a defined set · reduced-motion is designed and tested by enabling the preference · 60fps verified · the awkward cases pass · the signature moment works on mobile.

## Failure modes

| Failure | Countermeasure |
|---|---|
| Scroll fade-ups everywhere | Each needs one of the five purposes |
| Arbitrary durations | The timing set, used as tokens |
| Default easing everywhere | Easing is characterisation |
| Reduced motion means nothing appears | Reload with the preference on and confirm |
| Animating `width`, `filter`, `box-shadow` | `transform` and `opacity` only |
| Motion blocking reading | Nothing essential delayed past ~1s |
| Two motion libraries by accident | G2 before the second |
