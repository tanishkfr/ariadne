# DESIGN: <name>

> Template. Owner: Design director · Stage: S3 · Skill: [design-direction](../skills/design-direction.md)
> Rules: [DESIGN-TASTE.md](../DESIGN-TASTE.md). **Approved at G1 before anything is built.**

**Status:** <draft | locked at G1 on (date)> · **Scorecard:** <n>/50

---

## Design thesis

> One sentence naming the organising idea.
> Test: does it tell you what to do when someone asks for a hero image? If not, it is a mood.
> Banned words: clean, modern, minimal, premium, sleek, elegant.

**<the sentence>**

**The tension:** <two opposed qualities, e.g. "archival but immediate">

## Emotional target

> What someone should feel in the first five seconds, and what they should remember a day later.

- **First five seconds:** <>
- **Remembered a day later:** <>

## Visual references

| Reference | Mechanism taken | Max 2 per reference |
|---|---|---|
| <url> | <mechanism, not surface> | |

> A mechanism transfers to a different subject. A surface does not.
> Surface: "black background with big white serif type."
> Mechanism: "a single achromatic field so type scale alone carries hierarchy."

## What to borrow

1. <mechanism> — from <reference> — applied here as <how it lands on this subject>
2. <>
3. <>

## What NOT to copy

> **Mandatory. Minimum three. Specific.**
> Not "don't copy the layout" — "do not use their split-screen scroll transition; it is what people recognise their site by."

1. <>
2. <>
3. <>

---

## Typography

| Decision | Value | Why |
|---|---|---|
| Display face | <> | <> |
| Text face | <> | <> |
| Scale ratio | <> | <> |
| Size range | <smallest> to <largest> | Ratio: <n>x — [DESIGN-TASTE.md](../DESIGN-TASTE.md) 2.3 wants extreme |
| Display leading | <> | Tight: 0.9-1.05 |
| Body leading | <> | Generous: 1.5-1.7 |
| Tracking | <by size> | Negative at large, positive at small |
| Licence | <> | See [LIBRARY-POLICY.md](../LIBRARY-POLICY.md) 9 |

## Palette

> Achromatic base first. One accent. Colour has a source.

| Token | Value | Role |
|---|---|---|
| `--bg` | <off-white/off-black, not #fff/#000> | |
| `--fg` | <> | |
| `--accent` | <> | |

**Source of the palette:** <where it came from — brand, subject, era, material. "It looked nice" is not a source.>

**Dark mode:** <yes / no / N-A> — <why>

## Layout system

- **Grid:** <columns, gutters, margins>
- **Where it breaks, and why:** <>
- **Edge behaviour:** <full-bleed / hard margins / elements running off-canvas>
- **Density:** <sparse / dense — and why the subject demands it>
- **Vertical rhythm:** <how section spacing varies, and what varies it>

## Interaction principles

> How the interface responds. Hover, focus, active, drag, scroll.
> Every hover-dependent behaviour needs a touch equivalent — record it here, not at S5.

## Motion principles

> What motion is FOR in this project. See [motion-design](../skills/motion-design.md).

- **Purpose of motion here:** <orientation / feedback / continuity / hierarchy / character>
- **Timing set:** response <ms>, transition <ms>, narrative <ms>
- **Easing:** <token> — <what it characterises>
- **Reduced-motion design:** <the designed state, not "animations off">

## Signature moment

> The one thing a person would describe to someone else. Built FIRST at S4.

- **What:** <>
- **Where:** <>
- **Why memorable:** <>
- **Mobile equivalent:** <mandatory — a hover-based moment does not exist on a phone>

## Asset direction

> Resolved at S3, never at S4. See [asset-generation](../skills/asset-generation.md).

| Asset | Exists? | Plan | Blocking? |
|---|---|---|---|
| <> | yes/no | <real / generate / typographic substitute / cut> | |

**If the direction depends on assets that do not exist and cannot be made, change the direction.**

## Responsive behaviour

> How the direction *changes* at each size — not how it shrinks.

| Width | Composition |
|---|---|
| 375 | <> |
| 768 | <> |
| 1280 | <> |
| 1920 | <> |

## Anti-patterns for this project

> This project's specific rejection list, beyond the global table in [DESIGN-TASTE.md](../DESIGN-TASTE.md) 8.
> Minimum three. "Avoid generic design" is not one.

1. <>
2. <>
3. <>

---

## Scorecard (G1)

> [DESIGN-TASTE.md](../DESIGN-TASTE.md) section 11. Score the *direction*. Below 35 is not ready to present.

| # | Criterion | Score | Evidence |
|---|---|---|---|
| 1 | Concept clarity | /5 | |
| 2 | Typographic quality | /5 | |
| 3 | Compositional strength | /5 | |
| 4 | Colour discipline | /5 | |
| 5 | Material quality | /5 | |
| 6 | Motion purpose | /5 | |
| 7 | Signature moment | /5 | |
| 8 | Anti-generic compliance | /5 | |
| 9 | Craft | /5 | |
| 10 | Originality | /5 | |

**Total: <n>/50** · Lowest criterion: <name>

**Risks:** <what could make this direction fail>
