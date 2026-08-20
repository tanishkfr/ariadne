# SKILL MANIFEST

Fifteen capability modules. A skill is a **method**, not a tool and not a model.

Every skill file has the same shape: **Trigger** (when it activates), **Owner** (which role), **Class** (which capability tier from [MODEL-ROUTING.md](../MODEL-ROUTING.md)), **Inputs**, **Output**, **Method**, **Done when**, **Failure modes**.

---

## Index

| Skill | Trigger | Owner role | Class | Stage |
|---|---|---|---|---|
| [discovery](discovery.md) | A new project starts | Strategist | `R1` | S1 |
| [grilling](grilling.md) | `PROJECT.md` drafted but scope is soft | Strategist | `R1` | S1 |
| [live-research](live-research.md) | A claim depends on the current state of the world | Researcher | `R1`+`R4` | S2 |
| [reference-analysis](reference-analysis.md) | References or screenshots are supplied | Design director | `R1` | S2-S3 |
| [design-direction](design-direction.md) | Discovery is done, nothing is designed yet | Design director | `R1`+`R5` | S3 |
| [component-research](component-research.md) | A non-trivial interaction needs solving | Researcher | `R1`+`R4` | S2-S3 |
| [asset-generation](asset-generation.md) | The design needs an asset that does not exist | Asset specialist | `R5` | S3-S4 |
| [motion-design](motion-design.md) | Anything moves | Motion specialist | `R1`+`R2` | S3-S4 |
| [frontend-build](frontend-build.md) | G1 passed, handoff exists | Implementer | `R2` | S4 |
| [browser-qa](browser-qa.md) | Something is running | QA engineer | `R6`+`R4` | S5 |
| [accessibility](accessibility.md) | Before any G3 | Accessibility reviewer | `R6`+`R4` | S5 |
| [performance](performance.md) | Production build exists | Performance reviewer | `R6`+`R4` | S5 |
| [evaluation](evaluation.md) | Work is complete, or an audit is requested | Reviewer roles | `R1` | S5 |
| [deployment](deployment.md) | G3 granted | Implementer | `R6` | S6 |
| [content-strategy](content-strategy.md) | Content mode, or a post is needed | Content strategist | `R1` | Ongoing |

---

## Activation by mode

| Mode | Skills, in order |
|---|---|
| Premium client website | discovery, grilling, live-research, reference-analysis, design-direction, component-research, asset-generation, frontend-build, motion-design, browser-qa, accessibility, performance, evaluation, deployment |
| Personal portfolio | discovery, grilling, reference-analysis, design-direction, asset-generation, frontend-build, motion-design, browser-qa, accessibility, performance, evaluation, deployment |
| Product app | discovery, grilling, live-research, component-research, design-direction, frontend-build, browser-qa, accessibility, performance, evaluation, deployment |
| Game / experiment | discovery, design-direction, asset-generation, frontend-build, motion-design, browser-qa |
| Content system | discovery, grilling, live-research, content-strategy, evaluation |
| Audit / review | reference-analysis, browser-qa, accessibility, performance, evaluation |
| Benchmark | live-research, evaluation |

---

## Rules

**Skills are provider-neutral.** No skill file names a product. Tool-specific ways to run a skill live in [adapters/](../adapters/).

**Skills do not grant permission.** A skill describes a method. Whether an action is allowed is decided by [AUTONOMY-POLICY.md](../AUTONOMY-POLICY.md), always.

**A skill that cannot run says so.** If the required capability is unavailable — no browser, no image generation, no network — the skill reports that it cannot run. It does not approximate the result and present it as done.

**One skill at a time per stage.** Skills chain; they do not merge. `discovery` finishing is what starts `grilling`.

---

## Relationship to tool-native skills

Your Claude Code install has its own skills (design, motion, testing, writing). Those are **implementations**, and several map cleanly onto skills here — the mapping is in [adapters/claude-code.md](../adapters/claude-code.md).

The manifest is the contract; a tool-native skill is one way to satisfy it. When a tool-native skill is better than the method described here, use it and record why in the retrospective. When one does not exist, the method in the skill file is sufficient on its own — every skill here is written to be runnable by a person with no special tooling.
