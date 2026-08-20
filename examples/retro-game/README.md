# EXAMPLE: Retro boxing game

> **Fictional worked example.** Not a real project. It exists to show what the router does with a vague request, and specifically how the light S3 stops "retro" from producing the default retro output.

**Request:** *"I want to create a retro-style boxing game."*

---

## S0 — Routing

```
ROUTING BLOCK
Mode:         game-experiment  (confidence: High)
Runner-up:    none — "game" is unambiguous, no client, no persistence
Stage:        S0 -> S1
Questions:    3 (batched below)
Assumptions:  Desktop-first, keyboard input, one mechanic, no persistence,
              no menus, DOM/CSS rendering unless the mechanic needs Canvas
Documents:    PROJECT.md (short), DESIGN.md (short), TASKS.md, HANDOFF.md
Skills:       discovery (light), design-direction (light), asset-generation,
              frontend-build, motion-design, browser-qa
Owner:        Strategist on R1
Gates ahead:  G1 (light), G2 if a package is needed
Budget:       none — existing subscriptions
First action: Answer the 3 questions below.
```

**Questions asked:**

1. What is the core mechanic, in one sentence? *(no default — this is the whole brief)*
2. Input device? *(default: keyboard, desktop-first)*
3. Is this graded, and against what rubric? *(default: not graded)*

**Not asked, per the max-5 rule:** framework, whether it should be responsive, whether it should look good, what colours to use. All assumed and logged.

**Answers given:** *(1) Timing-based — you read the opponent's tell and counter in a narrow window. (2) Keyboard, two keys. (3) Not graded.*

---

## S3 — Where this example earns its place

**"Retro" is not a direction.** Given only "retro", every model produces the same thing: a beige-and-teal palette, a pixel font, CRT scanlines, and a 4:3 frame. That is the statistical centre of "retro", and a model with no further constraint returns the centre.

The light S3 is four questions, ten minutes:

| Question | Answer for this project |
|---|---|
| **Which specific era, region, medium?** | Not "retro" — **1980s Japanese arcade cabinet**, specifically the printed marquee and instruction card, not the screen |
| **What is the one visual device?** | The whole game is presented as a **printed instruction card**: flat spot colours, registration offset, halftone dots |
| **What does motion feel like?** | Heavy and mechanical. Nothing eases. Everything snaps or slams. |
| **What are you refusing?** | No CRT scanlines. No pixel font. No 4:3 frame. No chiptune. |

**The refusal list is the useful half.** Those four rejections remove the default output entirely, and they took thirty seconds to write.

**Design thesis:** *A boxing match printed on an arcade instruction card — flat spot colours in imperfect registration, where the only motion is the impact.*

**Signature moment:** on a successful counter, the entire screen shifts registration by 4px for 80ms — as if the print run slipped. The impact is a printing error, not a screen shake.

**Mobile equivalent:** tap zones replace the two keys; the registration shift is identical.

---

## S4 — Build order

Note that the signature moment is task 2, not task 8.

| # | Task | Why here |
|---|---|---|
| 1 | Token system: spot colours, halftone, registration offset | Everything else derives from it |
| 2 | **Registration-shift impact** | The signature moment. Built early so it cannot be cut. |
| 3 | Timing window + tell system | The actual mechanic |
| 4 | Opponent tell animations | |
| 5 | Win/lose state | |

---

## S5 — Compressed QA

Game mode gets a light `QA.md`: production build passes, zero console errors, one responsive pass, the mechanic is legible without instructions, reduced-motion respected.

**Reduced motion is not skipped even here.** Games are the worst offenders and the easiest to fix — the registration shift becomes an instant colour change rather than a movement.

Scorecard target: **35+**, not the 43+ that a portfolio piece needs.

---

## What this example demonstrates

| Point | Where |
|---|---|
| Compression is not skipping | 4 documents, 3 questions — but S3 still happens |
| A ten-minute direction beats no direction | The four S3 questions |
| The refusal list does the heavy lifting | "No scanlines, no pixel font" removes the default |
| The signature moment is built early | Task 2 of 5 |
| Quality bars differ by mode | 35+ here, 43+ for a portfolio |

**If this game turned out well and belonged in the portfolio**, it re-enters as [personal-portfolio](../../modes/personal-portfolio.md) mode and has to clear 43+. That is a separate decision made after it exists — not a reason to over-build it now.
