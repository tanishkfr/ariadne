# DRY RUN RESULTS

Five requests run through [ROUTER.md](../ROUTER.md) on **2026-08-21**.

**What this is:** a trace of what the router *should* produce for each request, verified by hand against the routing rules.

**What this is not:** evidence that the system works. Nothing was built. No model executed these. **A dry run tests whether the router is internally consistent and complete — not whether it produces good work.** That requires a real project, and none has been run.

---

## 1. "I want to create a retro-style boxing game."

| | |
|---|---|
| **Detected mode** | game-experiment — **High** confidence |
| **Signals** | "game", "create", no client, no persistence, no existing artifact |
| **Runner-up** | none |
| **Questions (3)** | Core mechanic in one sentence? · Input device? *(default: keyboard, desktop-first)* · Graded, and against what rubric? *(default: not graded)* |
| **Assumptions** | One mechanic, no menus, no persistence, DOM/CSS unless the mechanic needs Canvas, desktop-first, no audio |
| **Skills** | discovery (light), design-direction (light), asset-generation, frontend-build, motion-design, browser-qa |
| **Documents** | PROJECT (short), DESIGN (short), TASKS, HANDOFF, QA (compressed). **No** ARCHITECTURE, RESEARCH, or AGENTS. |
| **Routing** | Strategist `R1` → Design director `R1` → Implementer + Motion `R2` → QA `R6`+`R4` |
| **Stack** | Next.js + TS + pnpm; Canvas only if the mechanic demands it; Motion.dev or CSS; no backend |
| **QA path** | Compressed: build, console, one responsive pass, mechanic legible without instructions, reduced-motion |
| **Gates** | G1 (light), G2 if a package is needed |
| **Handoff** | Token system → signature moment → mechanic → states. Signature moment is **task 2 of 5**. |

**Check — does the router prevent generic output here?** Yes, via the S3 compression rule ([modes/game-experiment.md](../modes/game-experiment.md)): *light* S3, never *no* S3. The four era/device/motion/refusal questions are what stop "retro" from returning the default beige-scanline-pixel-font output. Worked example: [examples/retro-game/](../examples/retro-game/README.md).

---

## 2. "Build a clean, high-end website for a serious client."

| | |
|---|---|
| **Detected mode** | premium-client-website — **High** confidence |
| **Signals** | "client", "serious", someone else's reputation |
| **Runner-up** | personal-portfolio — rejected by tie-break 2 ([ROUTER.md](../ROUTER.md) 3.2) |
| **Questions (5)** | Who is the client and what do they sell? · What must a visitor do or feel? · What assets exist? · Hard deadline? · Brand rules that cannot break? |
| **Also established** | Who signs off — asked at S1 because a stakeholder appearing at S5 is the most common cause of rework |
| **Assumptions** | Home/work/about/contact · real copy drafted by us · no CMS · no backend, form to a third-party service · **Vercel paid plan** (commercial) · client owns the domain |
| **Skills** | All 14 for this mode |
| **Documents** | All 10, nothing compressed |
| **Routing** | Strategist → Researcher → Design director ∥ Architect → Implementer → QA + a11y + perf → reviewers → Implementer (ship) |
| **Stack** | Next.js + TS + pnpm, CSS variables, Motion.dev or GSAP per interaction, Vercel paid |
| **QA path** | Full mechanical + creative director, **strict client**, accessibility, performance |
| **Gates** | G1, G2 (every font licence), G3, G4 |
| **Handoff** | Full, with an asset fallback per image slot |

**Check — does the router catch "clean, high-end" as a non-brief?** Yes. `grilling` is mandatory in this mode, and [DESIGN-TASTE.md](../DESIGN-TASTE.md) 1.1 bans those exact adjectives from a thesis. Worked example: [examples/premium-client-site/](../examples/premium-client-site/README.md).

---

## 3. "Create my personal portfolio."

| | |
|---|---|
| **Detected mode** | personal-portfolio — **High** confidence |
| **Signals** | "my", "portfolio" |
| **Runner-up** | none |
| **Questions (5)** | Which 3-5 projects and what each proves? · Who is the reader? · The one thing to be remembered for? · Process artifacts or only finals? · Deadline? |
| **Assumptions** | Index + case studies · no CMS · no backend · Vercel Hobby (free, non-commercial) · you write the copy |
| **Skills** | discovery, **grilling (mandatory)**, reference-analysis, design-direction, asset-generation, frontend-build, motion-design, browser-qa, accessibility, performance, evaluation, deployment |
| **Documents** | PROJECT, DESIGN, ARCHITECTURE, TASKS, AGENTS, HANDOFF, QA, RETROSPECTIVE. S2 light. |
| **Routing** | Strategist → Design director → Architect → Implementer → QA → **fresh-session reviewers** |
| **Stack** | Next.js + TS + pnpm, CSS variables, Motion.dev, Vercel Hobby |
| **QA path** | Full mechanical + creative director, portfolio reviewer, design-school reviewer |
| **Gates** | G1, G2, G3, G4 |
| **Handoff** | Full |

**Check — quality bar.** 43+ scorecard; portfolio-reviewer below 32 is not competitive. The recall test is the real bar. Worked example: [examples/portfolio-project/](../examples/portfolio-project/README.md).

---

## 4. "Review this site like an elite portfolio reviewer."

| | |
|---|---|
| **Detected mode** | audit-review — **High** confidence |
| **Signals** | "review", an existing artifact supplied, a lens named explicitly |
| **Runner-up** | personal-portfolio — rejected by tie-break 1: artifact supplied, request says "review" not "rebuild" |
| **Questions (3, and Q1 self-answers)** | Which lens? *(answered by the request: portfolio + design-school)* · Yours or someone else's? · Findings only or fixes too? *(default: findings with fixes, no code)* |
| **Assumptions** | Intent inferred if unstated — **and declared as inferred** |
| **Skills** | reference-analysis, browser-qa, accessibility, performance, evaluation |
| **Documents** | QA.md only. Optionally RETROSPECTIVE if it should change the Builder OS. |
| **Routing** | Portfolio reviewer `R1` + design-school reviewer `R1`, **each in its own fresh session** |
| **Stack** | N/A — nothing is built |
| **QA path** | S5 **is** the entire mode |
| **Gates** | **None fire.** Nothing built, installed, pushed, or published. |
| **Handoff** | Consolidated findings + the one thing |

**Check — independence.** Enforced by [skills/evaluation.md](../skills/evaluation.md): fresh session, given only the URL and success criteria. **If the request became "and fix it", that is a mode change to a build mode with full gates** — stated rather than slid into. Worked example: [examples/audit-review/](../examples/audit-review/README.md).

---

## 5. "Create a content system for X and LinkedIn."

| | |
|---|---|
| **Detected mode** | content-system — **High** confidence |
| **Signals** | "content system", "X", "LinkedIn" |
| **Runner-up** | none |
| **Questions (5)** | Which platforms? *(default: both)* · What are you actually known for? · What do you refuse to post? *(push for 3+)* · Past analytics available? *(default: no history)* · Realistic cadence? *(default: 2-3/week)* |
| **Assumptions** | No account access · analytics pasted in by you · no scheduling tool · voice profile built from your existing writing |
| **Skills** | discovery, **grilling (mandatory)**, live-research, content-strategy, evaluation |
| **Documents** | PROJECT, RESEARCH (platform specifics, verified live), CONTENT-LEARNINGS, TASKS, AGENTS. **No** DESIGN, ARCHITECTURE, or HANDOFF. |
| **Routing** | Strategist → Content strategist `R1`, ongoing |
| **Stack** | **None.** This mode builds no software. |
| **QA path** | Per post: only-you element, hook ≥4, five originality checks, read-aloud |
| **Gates** | **G5 only — and it fires on every single post.** No standing approval. |
| **Handoff** | A G5 publish request per post; you copy and post it yourself |

**Check — the two things that could go wrong.** First, autoposting: prevented structurally — G5 is per-post, account connection is Amber and defaults to no. Second, the loop never closing: the weekly review must change `CONTENT-LEARNINGS.md`, and "no rule change this week" is an explicitly valid entry so the check stays honest.

---

## What the dry runs found

| Finding | Action taken |
|---|---|
| Request 2's "clean, high-end" would pass an unguarded router | Grilling is mandatory in that mode; the adjectives are banned in a thesis |
| Request 1 risked the generic-retro failure | S3 compression rule made explicit in the mode file, with four required questions |
| Request 4 could slide from audit into implementation | Mode-change requirement stated in the mode file and the Routing Block |
| Request 5's stack row is empty | Correct — content mode builds no software. Confirms the mode table is not over-fitted to build modes. |
| Question counts: 3, 5, 5, 3, 5 | All within the cap of 5 |
| Confidence: High on all five | **A weakness, not a strength** — see below |

**The honest caveat.** All five test requests are *clear* — they are the examples from the specification. High confidence on all five means the **Low-confidence path was never exercised**, and neither was the mode-switch procedure ([ROUTER.md](../ROUTER.md) 3.4). Those are the paths most likely to be wrong, and they remain untested.

Deliberately ambiguous cases to run before trusting the router — for example *"build me something for my studio"* (portfolio or client?), *"a tool for tracking my reading"* (product app or experiment?), and *"make my site better"* (audit or rebuild?) — are listed in [router-test-cases.md](router-test-cases.md).
