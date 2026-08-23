# Builder OS

A project router and operating system for building websites, apps, games, experiments and content — with a design quality bar that is written down and enforced, and a clear separation between which tool thinks and which tool builds.

Not a framework or a project dependency. Canonical Markdown plus a small
runtime controller, deterministic transport, and validation tools.

---

## The problem it solves

| Problem | Where |
|---|---|
| AI-generated UI feels generic | [DESIGN-TASTE.md](DESIGN-TASTE.md) — anti-generic rules, the G1 check, reference synthesis |
| One agent planning, designing, coding and reviewing | [WORKFLOW.md](WORKFLOW.md) — 5 roles, 5 gates, an independence rule |
| Wasting usage limits on context | [MODEL-ROUTING.md](MODEL-ROUTING.md) |
| No reliable design process | S3 cannot be skipped; **G1 blocks building without a thesis** |
| Research claims can outrun evidence | Project-local creative evidence separates recommended, invoked, completed and used work; found, inspected and used references; and selected, executed and returned providers |
| No document or handoff structure | [templates/](templates/) — four required documents, the rest conditional |
| Not knowing which tool does what | [MODEL-ROUTING.md](MODEL-ROUTING.md) + [adapters/](adapters/) |
| Reinventing prompts every project | [prompts/](prompts/) |

## How it works

```
Your request
  -> builderos skill        starts or resumes the right run
  -> builderos.py           discovers state and prepares the next boundary
  -> creative evidence      selects only useful methods and verifies source/use traces
  -> ROUTER.md              detects the mode, asks up to 5 questions
  -> WORKFLOW.md            runs S0-S6, assigns a role, enforces the gates
  -> prepare-stage.py       transports only the current canonical inputs
  -> templates/             produces PROJECT, DESIGN, HANDOFF, QA
  -> QA-POLICY.md           mechanical checks (the builder)
  -> EVALUATION-RUBRICS.md  judgement checks (a fresh session)
  -> RETROSPECTIVE          proposes changes for human approval
```

Five gates interrupt it: **G1** direction · **G2** dependencies · **G3** build complete · **G4** ship · **G5** publish. Nothing irreversible happens without you.

## Start here

**Never used it:** [GETTING-STARTED.md](GETTING-STARTED.md) — install the entry skill, then describe one real project.
**Using it today:** [DAILY-PLAYBOOK.md](DAILY-PLAYBOOK.md).
**Current productization evidence:** [V1.3-READINESS.md](V1.3-READINESS.md).
**Moving off Claude Code:** [MIGRATION-CHECKLIST.md](MIGRATION-CHECKLIST.md).
**Starting now:** in a clean Codex task, invoke `$builderos` (or say “Use Builder OS”) and describe the project normally. Builder OS locates prompts, packets, evidence, and the next valid boundary.

**Existing project:** say that you want Builder OS to adopt the current
repository. The entry skill uses the opt-in `--adopt-existing` path: it inspects
the live repository read-only during intake, preserves every existing file and
current behaviour, and creates only the missing Builder OS entry documents. If
`PROJECT.md` or `AGENTS.md` already exists, it stops instead of overwriting it.

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
├─ .agents/skills/   Builder OS Codex entry point
├─ skills/       7   project-specific methods selected only when useful
├─ templates/   13   4 required, the rest conditional or transport
├─ modes/        5
├─ adapters/     3   codex / cursor / claude-code
├─ references/   2   visual references, UI libraries
├─ prompts/      8   start, conditional research, direction, build, review,
│                    portfolio, content, retrospective
├─ tests/            router-cases.md (regression suite),
│                    validation-protocol.md (Test A exercised; B/C unrun)
└─ scripts/          builderos.py · prepare-stage.py · check.py · validate.py
```

## Principles

**Provider-neutral.** Product-specific *instructions* live only in [adapters/](adapters/). Swapping a tool means rewriting one adapter and one table row.

**Design decisions are not library decisions.** Component libraries are research, not dependencies ([LIBRARY-POLICY.md](LIBRARY-POLICY.md)).

**Reversible by default, irreversible by approval.** One task per branch. Five gates.

**Verified, not remembered.** Anything that changes over time is looked up and dated, or marked unverified.

**Observed, not asserted.** A recommended skill is not a completed skill, a URL
is not an inspected reference, and a selected provider is not an executed one.
New projects retain those distinctions in a hashed project-local evidence
ledger; generated packets transport it only to the stages that need it.

**Rendered, not inferred.** After G1, approved decisions become traceable
implementation and visual-QA requirements. Source code may suggest a state; it
does not prove the rendered experience. Drift, environmental gaps and creative
judgement remain separate records, and none grants a gate.

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

**v1.3.0-rc.1.** Builder OS now carries approved design decisions into hashed
implementation mappings, project-specific rendered QA, drift records and an
evidence-backed creative review. It classifies human interventions, gives each
S4B packet a unique non-overwriting project return target, and can produce an
explicitly requested current-evidence social strategy without posting. A
managed Codex entry skill still starts or resumes the project and the router
still routes on **intent**, not keywords.

Earlier: v0.2.0 restructured after an independent audit — 71 files to 49, 12 roles to 5, 9 lenses to 5, scorecard moved out of the author's session.

**Status: V1.3 READY FOR PRIVATE USE.** A local rendered fixture exercised the
new visual evidence and creative-review loop and exposed a real tablet drift;
unsupported reduced-motion observation remained unverified. External provider
automation, a complete V1.3 provider return and independent S5 remain
externally unverified, not presented as live passes. See
[V1.3-READINESS.md](V1.3-READINESS.md).

Run `python scripts/check.py` after any edit.
