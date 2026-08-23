# MODE: Game / experiment

Play, mechanics, class projects, throwaway probes. **The lightest mode** — being wrong costs an afternoon, not a reputation.

Compressed, not skipped. The compression is the point: heavy process on a two-day experiment is how experiments stop happening.

---

## Detection

**Reached when the `OBJECT` is a playable, experimental, or exhibited piece — any medium, any input device.** Games, sketches, class work, generative pieces, installations, tangible interfaces.

**Not this mode if:** it has accounts and persistence ([product app](product-app.md)), or the deliverable is a site rather than a piece ([client or portfolio](client-or-portfolio.md)).

**Installations and physical pieces route here.** They are not a separate mode — they are this mode with a different input and display target, which question 2 establishes. Web tech usually still applies: a Capacitor build on a tablet, a kiosk browser, a projected canvas. What changes is the composition, not the stack.

**Mode switch warning:** an experiment that grows accounts has become a product app — state outliving the session is what decides it. Re-fire the router ([ROUTER.md](../ROUTER.md) 3.6) rather than quietly upgrading.

**Adding a feature is not a mode switch.** Extending an experiment inherits this mode; only persistent state re-routes it.

---

## Questions

Three, not five. This mode is about starting.

1. **What is the core mechanic, in one sentence?** — no default
2. **What is the input, and what is it displayed on?** — **no default.** Keyboard on a laptop, touch on a phone, a sensor, a controller, a projector, a physical object. This question decides the rendering target, the interaction model, and half the design direction. Do not assume a desktop browser.
3. **Is this graded, and against what rubric?** — default: not graded

If graded, **the rubric replaces the quality bar below.** Ask for it and follow it; a marking scheme is a client brief.

---

## Assumptions

| Area | Default |
|---|---|
| Scope | One mechanic, done well. Not a game with menus, levels, and progression. |
| Persistence | None. Refresh resets. |
| Rendering | DOM/CSS if it can be; Canvas when it must be; WebGL only if 3D is the point. Web tech still applies when the output is physical — Capacitor, a kiosk browser, or a projector all run the same build. |
| Audio | None unless the mechanic needs it. For an installation, assume it does. |
| Display target | **Whatever question 2 said.** A phone, a projection, a kiosk, an installation screen, and a laptop are five different compositions, not one design at five widths. |
| Menus | Skip. Start in the game. |

---

## Documents

**Required: `PROJECT.md` (short) and `DESIGN.md` (short). Two.**

Add `HANDOFF.md` only if a different tool builds it, `TASKS.md` only past ~5 tasks, and a compressed `QA.md` before you show anyone. Never `ARCHITECTURE.md`, `RESEARCH.md`, or `ASSETS.md` unless the project outgrows the mode.

## Skills

[intake](../skills/intake.md) (light, challenge pass skipped) · [design-direction](../skills/design-direction.md) (light)

**Grilling is skipped.** The cost of a wrong assumption here is a wasted afternoon, which is an acceptable price for moving quickly.

## Stages

S1 light · **S2 skipped** unless a technical unknown blocks the build · S3 light · S4 full · S5 light · S6 light

## Gates

G1 (light — a paragraph, not a presentation), G2, G4 if it is deployed. G3 is compressed into "it works and someone played it".

---

## S3 is still not skipped

A **light** S3, not no S3. This is the rule that matters most in this mode.

"Retro" without a thesis produces the same beige pixel-font CRT-scanline output every single time, because that is the statistical centre of "retro" and a model with no constraint returns the centre.

A light direction is one paragraph answering:

- **Which specific era, region, or medium?** "Retro" is not an answer. 1980s Japanese arcade cabinet, 1990s Western PC shareware, and Game Boy monochrome are three completely different directions.
- **What is the one visual device?** Palette limit, type treatment, screen effect, physicality.
- **What does motion feel like?** Weight, snap, impact. In a game, motion *is* the feel.
- **What are you refusing?** Minimum two.

Ten minutes of this is the difference between a distinctive experiment and the default output.

---

## Quality bar

- Scorecard **35+** — shippable for an experiment, not for a portfolio
- Lens: creative director (light)
- The mechanic works and is legible without instructions
- No console errors, production build passes
- Reduced-motion respected — games are the worst offenders and the easiest to fix

**If it turns out well and belongs in the portfolio**, it re-enters as [client-or-portfolio](client-or-portfolio.md) mode and has to clear a 43+ bar. That is a separate decision, made after it exists.

---

## Failure modes

| Failure | Countermeasure |
|---|---|
| Building menus and settings before the mechanic | Start in the game |
| "Retro" producing generic retro | The light S3 questions above |
| Scope growing into a real game | One mechanic; re-route if it grows |
| Heavy process killing the experiment | Four documents, three questions |
| Ignoring a marking rubric | Ask for it; it outranks this file |
| Motion that ignores reduced-motion | Still a blocking check, even here |
