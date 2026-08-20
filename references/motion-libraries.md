# MOTION LIBRARIES

Principles: [DESIGN-TASTE.md](../DESIGN-TASTE.md) section 6. Method: [motion-design](../skills/motion-design.md).

**Do not ship two motion libraries** without a stated reason. That is a G2 conversation and usually a sign that the choice was never actually made.

---

## Choosing

| Need | Reach for | Why |
|---|---|---|
| Hover, focus, simple state transitions | **Plain CSS** | Cheapest, most robust, no dependency. Try this first. |
| Component enter/exit, gestures, layout shifts, springs | **Motion.dev** | Approved default ([LIBRARY-POLICY.md](../LIBRARY-POLICY.md) section 2) |
| Multi-step timelines, scroll choreography, pinning, morphing | **GSAP** | Conditional — real weight, and it overlaps Motion.dev |
| Continuous or generative motion | **Canvas / WebGL** | Specialty. Only when it is the point of the project. |
| Smooth scroll | **Lenis** | Conditional. Accessibility risk; must respect reduced-motion. |

**Start at the top of this table and move down only when the row above genuinely cannot do it.** A surprising amount of good motion is CSS transitions with well-chosen easing.

---

## Motion.dev

The default for component and state motion. Declarative, springs, layout animations, gesture handling.

Use for: enter/exit, state changes, layout shifts, drag, hover with physical feel.

Reach past it when: you need a multi-step timeline with precise sequencing, scroll-driven choreography across several elements, or SVG morphing.

## GSAP

Reach for it when the *timeline* is the design. Scroll choreography, pinning, sequencing, morphing.

Cost: real weight, and shipping it alongside Motion.dev means two motion systems in one bundle. That needs a stated reason in `ARCHITECTURE.md`, not a shrug.

**ScrollTrigger caution.** It makes scroll effects easy, which is why scroll effects are everywhere and mostly generic. Everything fading up 20px on scroll is the single most recognisable AI motion pattern — it signals that a plugin was applied, not that motion was designed ([motion-design](../skills/motion-design.md)).

Legitimate scroll uses: pinning while something changes, transforming through a range, revealing structure progressively, pacing a narrative, parallax with a real depth logic.

## Lenis

Smooth scroll. Adopt only when smoothness is integral to the direction, not as a default polish layer.

Real costs: it overrides native scroll behaviour, can break anchor links and browser find, and interacts badly with some accessibility tools. **Must respect `prefers-reduced-motion`.** Test keyboard scrolling and screen-reader navigation before committing.

## Canvas / WebGL

`three` and `@react-three/fiber` are Specialty. Very heavy. Justified only when 3D is the project, not decoration on a site that would work without it.

## Haikei

[haikei.app](https://haikei.app/) — a generator for SVG backgrounds and shapes. Not a motion library; listed here because it is in the same toolbox.

**Caution:** its outputs are recognisable. Blob shapes and layered waves from generators are a visual tell of the same kind as a default gradient. Use it as a starting point to modify, or take the technique and draw your own. Anything from it must still obey the [DESIGN-TASTE.md](../DESIGN-TASTE.md) rules — a generated wave shape with no relationship to the thesis is decoration.

---

## Before adopting any of these

Verify freshness — last release, maintenance, framework compatibility ([RESEARCH-POLICY.md](../RESEARCH-POLICY.md) section 6). **None of the above has been verified in this session**; the characterisations are structural, not current-status claims.

Then check, for the specific thing you are building:

- Does it animate `transform` and `opacity`, or does it force layout?
- Does it degrade correctly under `prefers-reduced-motion`?
- Does it hold 60fps on a mid-range machine?
- Does the interaction have a keyboard and touch equivalent?

---

## The rule that outranks the library choice

**Every animation answers: what does this tell the user?** Orientation, feedback, continuity, hierarchy, or character.

If the answer is "it looks nice", cut it — regardless of which library made it easy. The library is never the reason for the motion.
