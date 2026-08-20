# SKILL: motion-design

**Trigger** — anything moves.
**Owner** — Motion specialist · **Class** — `R1` (design) + `R2` (implementation)
**Inputs** — motion principles from `DESIGN.md`
**Output** — implemented motion + the motion section of [`QA.md`](../templates/QA.md)

Principles: [DESIGN-TASTE.md](../DESIGN-TASTE.md) section 6. This file is the procedure.

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

If the answer is "it looks nice", cut it. Every animation records its purpose in `DESIGN.md` or `QA.md`.

---

## Method

**1. Decide what motion is FOR in this project,** before animating anything. Some directions are still and should be. A specimen-sheet thesis probably wants type that does not bounce. Deciding "motion here is only feedback, never decoration" resolves fifty later decisions at once.

**2. Choose the technology per interaction,** within what `ARCHITECTURE.md` allows:

| Need | Reach for |
|---|---|
| Component enter/exit, state, gestures, layout shifts | Motion.dev |
| Multi-step timelines, scroll choreography, pinning, morphing | GSAP |
| Hover, focus, simple transitions | Plain CSS — cheapest and most robust |
| Continuous or generative motion | Canvas / WebGL, and only if it is the point |

**Do not ship two motion libraries** without a stated reason. That is a G2 conversation ([LIBRARY-POLICY.md](../LIBRARY-POLICY.md)).

**3. Set the timing system.** Pick a small set and reuse it — arbitrary durations are as much a tell as arbitrary font sizes.

- Interface response: **120-200ms**
- Entrances and transitions: **300-600ms**
- Deliberate, narrative motion: up to **1000ms**, with a reason
- Anything longer is a delay, not a delight

**4. Choose easing as characterisation.** Linear reads mechanical, sharp ease-out reads crisp and expensive, springs read playful. Pick from the thesis, define it as a token, reuse it. Default `ease-in-out` everywhere is the motion equivalent of Inter at 16px.

Fast in, slow out: interface response immediate, resolution eased.

**5. Choreograph.** Stagger follows reading order. Related elements move together; unrelated ones do not. Ten elements each fading in independently is noise, not choreography.

**6. Design the reduced-motion state.** Not "animations off" — a **designed** state. Content must appear and be usable. Test it by actually enabling the OS preference and reloading. This is a blocking QA check.

**7. Verify 60fps.** Animate `transform` and `opacity`. Watch for layout thrash, animated `box-shadow`/`filter`/`width`, and too many simultaneous compositor layers. If it drops frames on a mid-range machine, it is not shipping.

**8. Test the awkward cases.** Fast scroll. Refresh mid-page. Back-navigation. Resize during animation. Interrupt an animation with another action. Scroll-triggered work fails in these cases far more often than in normal use.

---

## Scroll-triggered motion

The default implementation — everything fades up 20px on scroll — is the single most recognisable AI motion pattern. It signals that a plugin was applied, not that motion was designed.

Legitimate uses of scroll: pinning a section while something changes, transforming an element through a range, revealing structure progressively, pacing a narrative, parallax with a real depth logic.

If you are using scroll only to delay content appearing, remove it. It makes the page slower and communicates nothing.

---

## Done when

Every animation has a recorded purpose · timing and easing come from a defined set · reduced-motion is designed and tested · 60fps verified · the awkward cases pass · the signature moment works on mobile.

---

## Failure modes

| Failure | Countermeasure |
|---|---|
| Scroll fade-ups everywhere | Section above; each needs a purpose |
| Arbitrary durations | Step 3's set, used as tokens |
| Default easing everywhere | Step 4: easing is characterisation |
| Reduced motion means "nothing appears" | Step 6: design the state, then test it |
| Animating `width`, `filter`, `box-shadow` | `transform` and `opacity` only |
| Motion that blocks reading | Nothing essential delayed past ~1s |
| Two motion libraries by accident | G2 before the second one |
| Hover-dependent signature moment | It does not exist on a phone — design the touch equivalent |
