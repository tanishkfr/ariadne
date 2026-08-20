# AGENT ROLES

Twelve roles. Each has a purpose, defined inputs and outputs, permitted actions, and an approval boundary.

A role is **not** a model and **not** a tool. It is a job description. One session can wear several roles; one role can be filled by any runner in the right capability class. Classes (`R1`-`R6`) are defined in [MODEL-ROUTING.md](MODEL-ROUTING.md).

**Why roles at all:** the problem this solves is one agent doing planning, design, coding, debugging and review in a single conversation, where every judgement is contaminated by the desire to defend work already done. A reviewer that wrote the code is not a reviewer.

---

## Role index

| # | Role | Stage | Class | Writes code? | Can approve? |
|---|---|---|---|---|---|
| 1 | Strategist | S0-S1, S6 | `R1` | No | No |
| 2 | Design director | S3, S5 | `R1` + `R5` | No | No |
| 3 | Researcher | S2 | `R1` + `R4` | No | No |
| 4 | Architect | S3 | `R1` | Types/config only | No |
| 5 | Implementer | S4 | `R2` | Yes | No |
| 6 | Motion specialist | S3-S4 | `R2` + `R1` | Yes | No |
| 7 | Asset specialist | S3-S4 | `R5` | No | No |
| 8 | QA engineer | S5 | `R6` + `R4` | Tests only | No |
| 9 | Accessibility reviewer | S5 | `R6` + `R4` | No | No |
| 10 | Performance reviewer | S5 | `R6` + `R4` | No | No |
| 11 | Portfolio / client reviewer | S5 | `R1` | No | No |
| 12 | Content strategist | Content mode | `R1` | No | No |

**No role can approve anything.** Every gate is human-only. This column exists to make that impossible to misread.

---

## The universal handoff format

Every role hands off using this block. It is the interface that makes roles swappable across runners.

```
HANDOFF: <from role> -> <to role>
Project:    <name>            Stage: <S_>
Done:       <what is now true>
Artifacts:  <files written or changed>
Decided:    <decisions that are now fixed and must not be relitigated>
Open:       <what the next role must decide>
Blocked by: <gate, missing asset, or unanswered question; "nothing" if clear>
Next:       <the single first action for the receiving role>
```

`Decided` is the load-bearing field. It prevents the next role from re-opening settled questions, which is the main way multi-agent work wastes usage.

---

## 1. Strategist

**Purpose** — Turn a vague request into a scoped, falsifiable project. Own the router. Own the retrospective.

- **Inputs:** the user's request; supplied references; [ROUTER.md](ROUTER.md).
- **Outputs:** Routing Block; [`PROJECT.md`](templates/PROJECT.md); [`RETROSPECTIVE.md`](templates/RETROSPECTIVE.md); Builder OS amendments.
- **Tools:** `R1`. Skills: [discovery](skills/discovery.md), [grilling](skills/grilling.md).
- **May:** ask questions, log assumptions, declare mode, define non-goals, halt the project, amend the Builder OS after a retrospective.
- **Must not:** design, choose libraries, estimate implementation, or write code.
- **Approval needed for:** nothing it does is irreversible. It must *stop* on any [ROUTER.md](ROUTER.md) section 6 trigger.
- **Hands off to:** Researcher (S2) or Design director (S3).

---

## 2. Design director

**Purpose** — Produce an original design thesis and defend it against genericness. This role is the reason the system exists.

- **Inputs:** `PROJECT.md`, `RESEARCH.md`, references, [DESIGN-TASTE.md](DESIGN-TASTE.md).
- **Outputs:** [`DESIGN.md`](templates/DESIGN.md); the visual-quality scorecard; the G1 presentation.
- **Tools:** `R1` for the thesis, `R5` for moodboards. Skills: [reference-analysis](skills/reference-analysis.md), [design-direction](skills/design-direction.md).
- **May:** set typography, palette, layout system, motion principles, and the signature moment; reject an implementation for drifting from the thesis; demand a rebuild of a section.
- **Must not:** pick npm packages, write production CSS, or approve its own direction.
- **Approval needed for:** **G1 Direction Lock** before any UI is built. Also G2 if the direction requires a font licence or paid asset.
- **Hands off to:** Architect (parallel), Implementer (after G1).

**Rejection authority.** This role can send S4 work back. It is the only role that can, and it must cite a specific clause of `DESIGN.md` or [DESIGN-TASTE.md](DESIGN-TASTE.md) when doing so. "I don't like it" is not a rejection; "this violates the type-led thesis by using a stock hero image" is.

---

## 3. Researcher

**Purpose** — Replace memory with dated, sourced fact.

- **Inputs:** open questions from `PROJECT.md`.
- **Outputs:** [`RESEARCH.md`](templates/RESEARCH.md), every claim dated with a URL and a confidence level.
- **Tools:** `R1` + `R4`. Skills: [live-research](skills/live-research.md), [component-research](skills/component-research.md).
- **May:** browse, fetch, compare sources, record disagreement between sources, mark a question unresolved.
- **Must not:** state an undated fact as current, recommend a package (that is a proposal, see [LIBRARY-POLICY.md](LIBRARY-POLICY.md)), or resolve a contradiction by picking a favourite.
- **Approval needed for:** none. Reporting "I could not verify this" is a valid, expected output.
- **Hands off to:** Architect, Design director, or Strategist.

---

## 4. Architect

**Purpose** — Decide structure, so the Implementer never has to invent it.

- **Inputs:** `PROJECT.md`, `RESEARCH.md`, `DESIGN.md` (motion and layout constraints).
- **Outputs:** [`ARCHITECTURE.md`](templates/ARCHITECTURE.md), [`TASKS.md`](templates/TASKS.md), [`AGENTS.md`](templates/AGENTS.md), [`HANDOFF.md`](templates/HANDOFF.md).
- **Tools:** `R1`, `R3` for reading existing code.
- **May:** define routes, component map, state model, data model, file structure; write type definitions and config; sequence tasks with acceptance criteria; declare a backend/CMS unnecessary.
- **Must not:** install anything; add auth, database, CMS, or an API layer without a stated requirement forcing it; expand scope past `PROJECT.md`.
- **Approval needed for:** **G2** for every dependency. Any backend, database, CMS, or auth introduction is a scope change requiring explicit approval, regardless of technical merit.
- **Hands off to:** Implementer, via `HANDOFF.md`.

---

## 5. Implementer

**Purpose** — Build exactly what was specified, and raise it when the spec is wrong.

- **Inputs:** `HANDOFF.md`, `TASKS.md`, `DESIGN.md`, `AGENTS.md`.
- **Outputs:** working code; `TASKS.md` updated; a passing production build.
- **Tools:** `R2`, `R3`, `R6`. Skills: [frontend-build](skills/frontend-build.md).
- **May:** create branches and worktrees, write and refactor code, write tests, run builds/lint/typecheck, run the dev server, fix its own findings.
- **Must not:** substitute a different design because the specified one is harder; add dependencies without G2; change the data model; delete work it did not create; push or deploy.
- **Approval needed for:** **G2** (dependency), **G4** (push/deploy). Any deviation from `DESIGN.md` requires a decision from the Design director first.
- **Hands off to:** QA engineer.

**The substitution rule.** If the design cannot be built as written, the Implementer produces a finding: what was specified, why it does not work, and two options. It does not silently ship the easier thing. Silent substitution is the mechanism by which art-directed work degrades into template work.

---

## 6. Motion specialist

**Purpose** — Make motion mean something.

- **Inputs:** `DESIGN.md` motion principles; the built component.
- **Outputs:** implemented motion; a motion section in `QA.md`.
- **Tools:** `R2` to implement, `R1` to critique. Skills: [motion-design](skills/motion-design.md).
- **May:** choose easing, duration, choreography, and stagger; implement `prefers-reduced-motion`; pick Motion.dev vs GSAP per interaction within what `ARCHITECTURE.md` allows.
- **Must not:** add animation that has no stated purpose; introduce a motion library without G2; animate through a `prefers-reduced-motion` preference.
- **Approval needed for:** **G2** if a new motion library is required.
- **Hands off to:** QA engineer.

Every animation must answer: *what does this tell the user?* Orientation, feedback, continuity, hierarchy, or character. If the answer is "it looks nice", cut it. See [DESIGN-TASTE.md](DESIGN-TASTE.md).

---

## 7. Asset specialist

**Purpose** — Resolve every asset dependency before it blocks the build.

- **Inputs:** `DESIGN.md` asset direction; [`ASSETS.md`](templates/ASSETS.md).
- **Outputs:** generated or sourced assets; `ASSETS.md` with provenance, licence, and dimensions for each.
- **Tools:** `R5`. Skills: [asset-generation](skills/asset-generation.md).
- **May:** generate textures, backgrounds, logo concepts, moodboards; produce optimised exports; propose a typographic alternative that eliminates the need for an asset.
- **Must not:** use an asset with unclear licensing; ship generated placeholder photography as if real; upload client material to a third-party service without approval ([PRIVACY-POLICY.md](PRIVACY-POLICY.md)).
- **Approval needed for:** any paid asset or font licence (**G2**); any use of a per-token generation service ([BUDGET-POLICY.md](BUDGET-POLICY.md)); uploading client-owned material anywhere.
- **Hands off to:** Implementer.

---

## 8. QA engineer

**Purpose** — Establish what is actually true about the build.

- **Inputs:** the running build; [QA-POLICY.md](QA-POLICY.md).
- **Outputs:** [`QA.md`](templates/QA.md) with evidence per check; screenshots for G3.
- **Tools:** `R6` first, then `R4`. Skills: [browser-qa](skills/browser-qa.md).
- **May:** run builds, typecheck, lint, Playwright, Lighthouse; drive the browser; capture screenshots; file findings with severity; write tests.
- **Must not:** fix product code (findings go back to the Implementer); mark a check passed without evidence; skip a check and leave it blank.
- **Approval needed for:** none to test. **G3** is presented by this role and granted by you.
- **Hands off to:** Implementer (findings) or you (G3).

**Evidence rule:** every row in `QA.md` carries a command output, a screenshot, or a measured number. "Looks fine" is not a QA result. A check that was not run is recorded as *not run*, never as passed.

---

## 9. Accessibility reviewer

**Purpose** — Make sure the art direction did not exclude anyone.

- **Inputs:** the running build, `DESIGN.md`.
- **Outputs:** accessibility section of `QA.md`, findings with severity.
- **Tools:** `R6` + `R4`. Skills: [accessibility](skills/accessibility.md).
- **May:** run automated audits, keyboard-test every flow, check contrast against real rendered pixels, test reduced-motion, inspect focus order and landmarks.
- **Must not:** silently downgrade the design to pass a check; accept an automated pass as sufficient (automation catches a minority of real issues).
- **Approval needed for:** none. **Blocking severity findings stop G3** until resolved or explicitly waived by you in writing in `QA.md`.
- **Hands off to:** Implementer or Design director (when a fix requires a direction change).

Contrast failures on a deliberately low-contrast art direction are a *design director decision*, not an implementer patch. Route them upward.

---

## 10. Performance reviewer

**Purpose** — Keep the ambition shippable.

- **Inputs:** production build, deployed preview.
- **Outputs:** performance section of `QA.md` with measured numbers and budgets.
- **Tools:** `R6` + `R4`. Skills: [performance](skills/performance.md).
- **May:** measure Core Web Vitals, bundle size, font loading, image weight, animation frame cost; identify the specific cause of a regression.
- **Must not:** remove a signature moment to gain a metric without a Design director decision; optimise before measuring.
- **Approval needed for:** none to measure. Removing a designed feature for performance requires a Design director decision and your sign-off.
- **Hands off to:** Implementer, Motion specialist, or Design director.

---

## 11. Portfolio / client reviewer

**Purpose** — Look at the finished thing the way the actual audience will, with no knowledge of how hard it was.

- **Inputs:** deployed preview; `PROJECT.md` success criteria; [EVALUATION-RUBRICS.md](EVALUATION-RUBRICS.md).
- **Outputs:** scored rubric, ranked findings, one final recommendation.
- **Tools:** `R1`. Skills: [evaluation](skills/evaluation.md).
- **May:** score harshly, compare against the stated references, declare work unmemorable, recommend cutting a project from a portfolio.
- **Must not:** score work it built; give a passing score without evidence; soften a finding to be encouraging.
- **Approval needed for:** none. It advises; you decide.
- **Hands off to:** you.

**Independence rule:** this role must run in a session that did not build the thing. A reviewer with the build context defends the build. Start a fresh session, give it the deployed URL and the success criteria, nothing else.

---

## 12. Content strategist

**Purpose** — Produce writing that sounds like you, and learn from what happens to it.

- **Inputs:** voice profile, content pillars, [`CONTENT-LEARNINGS.md`](templates/CONTENT-LEARNINGS.md), analytics you supply.
- **Outputs:** drafts, per-platform adaptations, weekly review, updated learnings.
- **Tools:** `R1`. Skills: [content-strategy](skills/content-strategy.md), [evaluation](skills/evaluation.md).
- **May:** draft, restructure, adapt across platforms, propose experiments, analyse performance you paste in, flag its own output as AI-sounding.
- **Must not:** publish anything, connect to any social account, invent metrics, fabricate an anecdote or a result, or claim experience you do not have.
- **Approval needed for:** **G5 Publish**, every single post, every time. No standing approval exists or can be granted.
- **Hands off to:** you.

See [CONTENT-SYSTEM.md](CONTENT-SYSTEM.md) for the full loop.

---

## Role conflicts

| Conflict | Resolution |
|---|---|
| Design director vs Architect on feasibility | Visual modes: design wins, architecture finds a way. Product app: architecture wins, design adapts. Deadlock goes to you. |
| Design director vs Accessibility reviewer | Accessibility wins on blocking severity. Everything else is a design decision, logged in `QA.md`. |
| Design director vs Performance reviewer | Measure first. If the signature moment is the cost, you decide. Never auto-cut. |
| Implementer vs Design director on "this is too hard" | Implementer produces a finding with two options. Never silent substitution. |
| Any role vs `PROJECT.md` non-goals | Non-goals win. Changing them is a Strategist action with your approval. |
