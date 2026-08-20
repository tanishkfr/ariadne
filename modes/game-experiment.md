# MODE: Game / experiment

Play, mechanics, class projects, throwaway probes. **The lightest mode** — being wrong costs an afternoon, not a reputation.

Compressed, not skipped. The compression is the point: heavy process on a two-day experiment is how experiments stop happening.

---

## Detection

**Signals:** "game", "experiment", "class", "assignment", "playable", "sketch", "toy", "try", "prototype".

**Not this mode if:** it is going in the portfolio as a finished piece (personal portfolio), or it has accounts and persistence (product app).

**Mode switch warning:** experiments that grow login screens have become product apps. Re-fire the router ([ROUTER.md](../ROUTER.md) 3.4) rather than quietly upgrading.

---

## Questions

Three, not five. This mode is about starting.

1. **What is the core mechanic, in one sentence?** — no default
2. **Input device — keyboard, mouse, touch, gamepad?** — default: keyboard and mouse, desktop-first
3. **Is this graded, and against what rubric?** — default: not graded

If graded, **the rubric replaces the quality bar below.** Ask for it and follow it; a marking scheme is a client brief.

---

## Assumptions

| Area | Default |
|---|---|
| Scope | One mechanic, done well. Not a game with menus, levels, and progression. |
| Persistence | None. Refresh resets. |
| Rendering | DOM/CSS if it can be; Canvas when it must be; WebGL only if 3D is the point |
| Audio | None unless the mechanic needs it |
| Mobile | Desktop-first; mobile only if touch is the input |
| Menus | Skip. Start in the game. |

---

## Documents

Four only: `PROJECT.md` (short) → `DESIGN.md` (short) → `TASKS.md` → `HANDOFF.md`, plus a compressed `QA.md`.

No `ARCHITECTURE.md`, no `RESEARCH.md`, no `AGENTS.md` unless the project outgrows the mode.

## Skills

discovery (light), design-direction (light), asset-generation, frontend-build, motion-design, browser-qa

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

**If it turns out well and belongs in the portfolio**, it re-enters as [personal-portfolio](personal-portfolio.md) mode and has to clear a 43+ bar. That is a separate decision, made after it exists.

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
