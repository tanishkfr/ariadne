# Builder OS

A project router and operating system for building websites, apps, games, experiments and content — with a design quality bar that is written down and enforced, and a clear separation between which tool thinks and which tool builds.

Not a framework, an app, or a dependency. Canonical Markdown plus small deterministic transport and validation tools.

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
  -> prepare-stage.py       transports only this stage's canonical inputs
  -> templates/             produces PROJECT, DESIGN, HANDOFF, QA
  -> QA-POLICY.md           mechanical checks (the builder)
  -> EVALUATION-RUBRICS.md  judgement checks (a fresh session)
  -> RETROSPECTIVE          proposes changes for human approval
```

Five gates interrupt it: **G1** direction · **G2** dependencies · **G3** build complete · **G4** ship · **G5** publish. Nothing irreversible happens without you.

## Start here

**Never used it:** [GETTING-STARTED.md](GETTING-STARTED.md) — 30 minutes, then one real project.
**Using it today:** [DAILY-PLAYBOOK.md](DAILY-PLAYBOOK.md).
**Moving off Claude Code:** [MIGRATION-CHECKLIST.md](MIGRATION-CHECKLIST.md).
**Starting now:** generate a fresh S1 packet with [prepare-stage.py](scripts/prepare-stage.py), then paste `packet.txt` into your reasoning tool.

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
├─ ROUTER.md               Interpretation frame, routing rules, restarts   <- start
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
├─ skills/       4   intake, reference-analysis, design-direction,
│                    component-research
├─ templates/   11   4 required, 7 conditional
├─ modes/        5
├─ adapters/     3   codex / cursor / claude-code
├─ references/   2   visual references, UI libraries
├─ prompts/      8   start, conditional research, direction, build, review,
│                    portfolio, content, retrospective
├─ tests/            router-cases.md (regression suite),
│                    validation-protocol.md (Test A exercised; B/C unrun)
└─ scripts/          check.py · validate.py · deterministic stage packets
```

## Principles

**Provider-neutral.** Product-specific *instructions* live only in [adapters/](adapters/). Swapping a tool means rewriting one adapter and one table row.

**Design decisions are not library decisions.** Component libraries are research, not dependencies ([LIBRARY-POLICY.md](LIBRARY-POLICY.md)).

**Reversible by default, irreversible by approval.** One task per branch. Five gates.

**Verified, not remembered.** Anything that changes over time is looked up and dated, or marked unverified.

**Four documents, not eleven.** `PROJECT`, `DESIGN`, `HANDOFF`, `QA`. The rest exist when they earn it — a document nobody reads is worse than none, because it manufactures the appearance of process.

**The system learns under human control.** A retrospective proposes a specific change; the human approves, defers, or rejects it before any Builder OS file changes.

## What it will not do

- Publish, push, or deploy without you.
- Install packages without a justification you approve.
- Add auth, a database, a CMS, or a dashboard to a project that does not need one.
- **Fight a deliberate design choice.** The anti-generic rules assume genericness came from the tool. When it is your decision, declare it — no limit, but the reason has to be a reason (**R-PAT-1**).
- Guarantee good design. It makes generic design harder to ship accidentally, and makes the failure visible when it happens.

---

## Status

**v0.3.6.** Stage prompts can now be delivered as verified, paste-ready packets with explicit parents, source hashes, expected transcript paths, and stale-source detection. The router still routes on **intent**, not keywords.

Earlier: v0.2.0 restructured after an independent audit — 71 files to 49, 12 roles to 5, 9 lenses to 5, scorecard moved out of the author's session.

**Status: NEAR READY — not v1.0.0.** A Codex Test A exercise has reached S5, but Cursor remains prepared rather than validated and no Test B or Test C has completed. See [V1-READINESS.md](V1-READINESS.md).

Run `python scripts/check.py` after any edit.
