# Builder OS

A project router and operating system for building websites, apps, games, experiments and content — with a design quality bar that is written down and enforced, and a clear separation between which tool thinks and which tool builds.

It is not a framework, an app, or a dependency. It is a set of documents you point an AI tool at.

---

## The problem it solves

| Problem | Where it is handled |
|---|---|
| AI-generated UI feels generic | [DESIGN-TASTE.md](DESIGN-TASTE.md) — anti-generic rules, scorecard, reference synthesis |
| One agent doing planning, design, coding and review | [AGENT-ROLES.md](AGENT-ROLES.md) — 12 roles with inputs, outputs, approval boundaries |
| Wasting usage limits on context-heavy work | [MODEL-ROUTING.md](MODEL-ROUTING.md) — capability classes and conservation rules |
| No reliable design process | [WORKFLOW.md](WORKFLOW.md) — S3 Direction cannot be skipped; G1 blocks building without a thesis |
| No document or handoff structure | [templates/](templates/) — 11 documents with a defined handoff format |
| Not knowing which tool handles which task | [MODEL-ROUTING.md](MODEL-ROUTING.md) + [adapters/](adapters/) |
| Reinventing prompts every project | [prompts/](prompts/) — four copy-paste prompts |

---

## How it works

You paste one prompt. The router figures out the rest.

```
Your request
   -> ROUTER.md         detects the mode, asks up to 5 questions
   -> WORKFLOW.md       runs stages S0-S6
   -> AGENT-ROLES.md    assigns a role per stage
   -> MODEL-ROUTING.md  assigns a tool per role
   -> templates/        produces the documents
   -> QA-POLICY.md      verifies mechanically and by judgement
   -> RETROSPECTIVE     updates this system
```

Five human gates interrupt it: **G1** direction, **G2** dependencies, **G3** build complete, **G4** ship, **G5** publish. Nothing irreversible happens without you.

---

## Start here

**Never used it:** [GETTING-STARTED.md](GETTING-STARTED.md) — 15 minutes, sets up the tools and runs one real project.

**Using it today:** [DAILY-PLAYBOOK.md](DAILY-PLAYBOOK.md) — what to open, in what order, for each kind of work.

**Moving off Claude Code:** [MIGRATION-CHECKLIST.md](MIGRATION-CHECKLIST.md).

**Starting a project right now:** paste [prompts/project-start.md](prompts/project-start.md) into your reasoning tool.

---

## The seven modes

| Mode | For |
|---|---|
| [Premium client website](modes/premium-client-website.md) | Paid or reputation-critical work for someone else |
| [Personal portfolio](modes/personal-portfolio.md) | Your own work and reputation |
| [Product app](modes/product-app.md) | Real users, real state |
| [Game / experiment](modes/game-experiment.md) | Play, mechanics, class projects |
| [Content system](modes/content-system.md) | X and LinkedIn, with a learning loop |
| [Audit / review](modes/audit-review.md) | Critique something that exists |
| [Benchmark](modes/benchmark.md) | Measure the system itself |

---

## Repository map

```
Builder OS/
├─ ROUTER.md                  Mode detection, questions, dispatch      <- start here
├─ WORKFLOW.md                7 stages, 5 gates
├─ MODEL-ROUTING.md           Which tool does what, usage conservation
├─ AGENT-ROLES.md             12 roles with approval boundaries
├─ DESIGN-TASTE.md            Quality bar, anti-generic rules, scorecard
├─ AUTONOMY-POLICY.md         Green / Amber / Red actions
├─ LIBRARY-POLICY.md          How a package gets approved
├─ RESEARCH-POLICY.md         What must be verified, how it is recorded
├─ QA-POLICY.md               Mechanical + judgement checks
├─ EVALUATION-RUBRICS.md      9 review lenses
├─ CONTENT-SYSTEM.md          Writing, analytics, learning loop
├─ PRIVACY-POLICY.md          Secrets, client data, instruction boundary
├─ BUDGET-POLICY.md           INR budget, dated cost snapshot
├─ GETTING-STARTED.md         First-time setup
├─ DAILY-PLAYBOOK.md          Everyday use
├─ MIGRATION-CHECKLIST.md     Claude Code -> Codex + Cursor
├─ CHANGELOG.md               How this system has changed
├─ skills/                    15 capability modules + manifest
├─ templates/                 11 project documents
├─ modes/                     7 mode definitions
├─ adapters/                  codex / cursor / claude-code
├─ references/                Visual refs, UI + motion libraries, sources
├─ prompts/                   4 copy-paste prompts
├─ examples/                  4 worked examples
└─ validation/                Router tests, consistency checks, dry runs
```

---

## Principles

**Provider-neutral.** No document outside [adapters/](adapters/) names a product. Tools are referred to by capability class (`R1`-`R6`). If one tool disappears, you write one adapter file and nothing else changes.

**Design decisions are not library decisions.** Component libraries are research, not dependencies. See [LIBRARY-POLICY.md](LIBRARY-POLICY.md) section 4.

**Reversible by default, irreversible by approval.** One task per branch. Five gates. Nothing publishes or deploys itself.

**Verified, not remembered.** Anything that changes over time gets looked up and dated, or is marked unverified. See [RESEARCH-POLICY.md](RESEARCH-POLICY.md).

**The system improves itself.** Every retrospective edits a Builder OS file and logs it in [CHANGELOG.md](CHANGELOG.md). A retrospective that changes nothing was not one.

---

## What this system will not do

Stated plainly so it is not a surprise:

- It will not publish content, push code, or deploy without you.
- It will not install packages without a justification you approve.
- It will not add auth, a database, a CMS, or a dashboard to a project that does not need one.
- It will not guarantee good design. It makes generic design harder to ship accidentally, and it makes the failure visible when it happens.
- It does not automate taste. The scorecard is scored by a judgement call, and a dishonest score defeats the whole mechanism.

---

## Status

Version 0.1.0. Built and validated by dry run across five requests ([validation/dry-run-results.md](validation/dry-run-results.md)); **not yet validated by a real project.** Known weaknesses are listed in [validation/final-report.md](validation/final-report.md) — read that before trusting any part of this system further than you can check it.
