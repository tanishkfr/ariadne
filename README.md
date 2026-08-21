# Builder OS

A project router and operating system for building websites, apps, games, experiments and content — with a design quality bar that is written down and enforced, and a clear separation between which tool thinks and which tool builds.

Not a framework, an app, or a dependency. A set of documents you point an AI tool at.

---

## The problem it solves

| Problem | Where |
|---|---|
| AI-generated UI feels generic | [DESIGN-TASTE.md](DESIGN-TASTE.md) — anti-generic rules, the G1 check, reference synthesis |
| One agent planning, designing, coding and reviewing | [WORKFLOW.md](WORKFLOW.md) — 5 roles, 5 gates, an independence rule |
| Wasting usage limits on context | [MODEL-ROUTING.md](MODEL-ROUTING.md) |
| No reliable design process | S3 cannot be skipped; **G1 blocks building without a thesis** |
| No document or handoff structure | [templates/](templates/) — four required documents, the rest conditional |
| Not knowing which tool does what | [MODEL-ROUTING.md](MODEL-ROUTING.md) + [adapters/](adapters/) |
| Reinventing prompts every project | [prompts/](prompts/) |

## How it works

```
Your request
  -> ROUTER.md              detects the mode, asks up to 5 questions
  -> WORKFLOW.md            runs S0-S6, assigns a role, enforces the gates
  -> templates/             produces PROJECT, DESIGN, HANDOFF, QA
  -> QA-POLICY.md           mechanical checks (the builder)
  -> EVALUATION-RUBRICS.md  judgement checks (a fresh session)
  -> RETROSPECTIVE          edits this system, logged in CHANGELOG
```

Five gates interrupt it: **G1** direction · **G2** dependencies · **G3** build complete · **G4** ship · **G5** publish. Nothing irreversible happens without you.

## Start here

**Never used it:** [GETTING-STARTED.md](GETTING-STARTED.md) — 30 minutes, then one real project.
**Using it today:** [DAILY-PLAYBOOK.md](DAILY-PLAYBOOK.md).
**Moving off Claude Code:** [MIGRATION-CHECKLIST.md](MIGRATION-CHECKLIST.md).
**Starting now:** paste [prompts/project-start.md](prompts/project-start.md) into your reasoning tool.

## The five modes

| Mode | For |
|---|---|
| [Client or portfolio](modes/client-or-portfolio.md) | A site whose job is reputation — yours or a client's |
| [Product app](modes/product-app.md) | Real users, real state |
| [Game / experiment](modes/game-experiment.md) | Play, mechanics, class projects |
| [Content system](modes/content-system.md) | X and LinkedIn, with a learning loop |
| [Audit / review](modes/audit-review.md) | Critique something that exists |

## Map

```
Builder OS/
├─ ROUTER.md               Modes, questions, accepted patterns, restarts   <- start
├─ WORKFLOW.md             Stages, gates, 5 roles, what agents may do
├─ DESIGN-TASTE.md         The quality bar and anti-generic rules
├─ DESIGN-MOTION.md        Motion principles and procedure
├─ DESIGN-ASSETS.md        Imagery, texture, licensing
├─ QA-POLICY.md            Mechanical checks + deployment
├─ EVALUATION-RUBRICS.md   5 review lenses, anchored scoring
├─ LIBRARY-POLICY.md       How a package gets approved
├─ RESEARCH-POLICY.md      What must be verified, and how
├─ PRIVACY-POLICY.md       Secrets, client data, instruction boundary
├─ MODEL-ROUTING.md        Which tool does what, usage conservation
├─ BUDGET-POLICY.md        INR budget, dated cost snapshot
├─ CONTENT-SYSTEM.md       Writing, analytics, learning loop
├─ CHANGELOG.md            How this system changed + the 30-day check
├─ GETTING-STARTED.md · DAILY-PLAYBOOK.md · MIGRATION-CHECKLIST.md
├─ skills/       5   intake, reference-analysis, design-direction,
│                    component-research, evaluation
├─ templates/   11   4 required, 7 conditional
├─ modes/        5
├─ adapters/     3   codex / cursor / claude-code
├─ references/   2   visual references, UI libraries
├─ prompts/      4   start, review, portfolio, content
└─ scripts/          check.py — links, required files, duplicate rules
```

## Principles

**Provider-neutral.** Product-specific *instructions* live only in [adapters/](adapters/). Swapping a tool means rewriting one adapter and one table row.

**Design decisions are not library decisions.** Component libraries are research, not dependencies ([LIBRARY-POLICY.md](LIBRARY-POLICY.md)).

**Reversible by default, irreversible by approval.** One task per branch. Five gates.

**Verified, not remembered.** Anything that changes over time is looked up and dated, or marked unverified.

**Four documents, not eleven.** `PROJECT`, `DESIGN`, `HANDOFF`, `QA`. The rest exist when they earn it — a document nobody reads is worse than none, because it manufactures the appearance of process.

**The system improves itself.** Every retrospective edits a file here and logs it in [CHANGELOG.md](CHANGELOG.md).

## What it will not do

- Publish, push, or deploy without you.
- Install packages without a justification you approve.
- Add auth, a database, a CMS, or a dashboard to a project that does not need one.
- **Fight a deliberate design choice.** The anti-generic rules assume genericness came from the tool. When it is your decision, declare it ([ROUTER.md](ROUTER.md) section 10).
- Guarantee good design. It makes generic design harder to ship accidentally, and makes the failure visible when it happens.

---

## Status

**v0.2.0.** Restructured after an independent audit of v0.1.0 — 71 files to 49, 12 roles to 5, 9 review lenses to 5, and the scorecard moved out of the author's session because self-scoring clusters at 4 and measures nothing.

**Still not validated by a real project.** Run `python scripts/check.py` after any edit. The 30-day check in [CHANGELOG.md](CHANGELOG.md) is how this stops being a guess.
