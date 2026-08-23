# DESIGN: <name>

> Template. Owner: Design director · Stage: S3 · Skill: [design-direction](../skills/design-direction.md)
> Rules: [DESIGN-TASTE.md](../DESIGN-TASTE.md). **Approved at G1 before anything is built.**

**Status:** <draft | locked at G1 on (date)>

---

## Design thesis

> One sentence naming the organising idea.
> **Test: does it tell you what to do when someone asks for a hero image?** If not, it is a mood.
> Banned: clean, modern, minimal, premium, sleek, elegant.

**<the sentence>**

**The tension:** <two opposed qualities, e.g. "archival but immediate">

## Emotional target

- **First five seconds:** <>
- **Remembered a day later:** <>

## Visual references

> Mechanisms, not surfaces — a mechanism transfers to a different subject.
> Surface: "black background with big white serif type."
> Mechanism: "a single achromatic field, so type scale alone carries hierarchy."
> Method: [reference-analysis](../skills/reference-analysis.md).

| Reference | Mechanism taken (max 2 each) |
|---|---|
| <url> | <> |

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
| Size range | <smallest> to <largest> | Ratio: <n>x — **4x minimum** |
| Display leading | <> | Tight: 0.9-1.05 |
| Body leading | <> | Generous: 1.5-1.7 |
| Tracking | <by size> | Negative at large, positive at small |
| Licence | <> | [LIBRARY-POLICY.md](../LIBRARY-POLICY.md) 9 |

## Palette

| Token | Value | Role |
|---|---|---|
| `--bg` | <off-white/off-black, not #fff/#000> | |
| `--fg` | <> | |
| `--accent` | <> | |

**Source of the palette:** <brand, subject, era, material. "It looked nice" is not a source.>

**Dark mode:** <yes / no / N-A> — <why>

## Layout system

- **Grid:** <columns, gutters, margins>
- **Where it breaks, and why:** <>
- **Edge behaviour:** <full-bleed / hard margins / off-canvas>
- **Density:** <sparse / dense — and why the subject demands it>
- **Vertical rhythm:** <what varies section spacing>

## Interaction principles

> **Every hover-dependent behaviour needs a touch equivalent — recorded here, not discovered at S5.**

<hover, focus, active, drag, scroll>

## Motion principles

> [DESIGN-MOTION.md](../DESIGN-MOTION.md).

- **Purpose of motion here:** <orientation / feedback / continuity / hierarchy / character>
- **Timing set:** response <ms>, transition <ms>, narrative <ms>
- **Easing:** <token> — <what it characterises>
- **Reduced-motion design:** <the designed state, not "animations off">

## Signature moment

> [DESIGN-TASTE.md](../DESIGN-TASTE.md) 1.4. Built FIRST at S4.

- **What / where:** <>
- **Why memorable:** <>
- **Mobile equivalent:** <mandatory — a hover-based moment does not exist on a phone>

## Asset direction

> [DESIGN-ASSETS.md](../DESIGN-ASSETS.md). **If the direction depends on assets that cannot be made, change the direction.**

| Asset | Exists? | Plan | Blocking? |
|---|---|---|---|
| <> | yes/no | <real / generate / typographic substitute / cut> | |

## Responsive behaviour

> How the direction *changes* at each size — not how it shrinks.
> Sizes here should match the real display target, which for an installation or a phone piece is not this list.

| Width | Composition |
|---|---|
| 375 | <> |
| 768 | <> |
| 1280 | <> |
| 1920 | <> |

## Anti-patterns for this project

> Beyond the global table in [DESIGN-TASTE.md](../DESIGN-TASTE.md) section 6.
> Minimum three. "Avoid generic design" is not one.

1. <>
2. <>
3. <>

## Accepted patterns

> Blocking patterns chosen deliberately, carried over from `PROJECT.md` (**R-PAT-1**, no limit).
> If this section has entries, the direction must work *because* of them, not despite them —
> the reviewer checks whether the stated rationale is visible in the result.

| Pattern | Because | Rationale type |
|---|---|---|

---

## G1 direction check

> Qualitative, **not scored.** Numeric scoring happens at S5, by a reviewer who did not write this
> ([EVALUATION-RUBRICS.md](../EVALUATION-RUBRICS.md)).
>
> **Any "no" is a blocker.**

| # | Check | Y/N | If no, why not |
|---|---|---|---|
| 1 | Thesis tells you what to do about a hero image | | |
| 2 | No "clean / modern / minimal / premium / sleek / elegant" | | |
| 3 | Type ratio at least 4x | | |
| 4 | Palette has a stated source | | |
| 5 | Motion has one of the five purposes | | |
| 6 | Signature moment named, with a mobile equivalent | | |
| 7 | Three or more specific rejections | | |
| 8 | All asset dependencies resolved | | |
| 9 | Survives the swap test | | |
| 10 | **Which anti-generic row is this closest to, and why is it not that?** | | |

> Question 10 catches self-deception. Every direction is near something generic; naming which one forces you to articulate the difference.

**Risks:** <what could make this direction fail>
