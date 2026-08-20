# WORKFLOW

What happens after [ROUTER.md](ROUTER.md) picks a mode. Seven stages, five gates, one owner per stage.

The whole system is this table. Everything else is detail.

| Stage | Name | Owner role | Produces | Ends at |
|---|---|---|---|---|
| **S0** | Route | Strategist | Routing Block | Mode agreed |
| **S1** | Discover | Strategist | `PROJECT.md` | Scope agreed |
| **S2** | Research | Researcher | `RESEARCH.md` | Facts dated and sourced |
| **S3** | Direct | Design director + Architect | `DESIGN.md`, `ARCHITECTURE.md`, `ASSETS.md` | **G1: Direction Lock** |
| **S4** | Build | Implementer (+ motion, asset) | Working code, `TASKS.md` ticked | Build passes |
| **S5** | Verify | QA engineer + reviewers | `QA.md` | **G3: Build Complete** |
| **S6** | Ship & Learn | Implementer + Strategist | Deployment, `RETROSPECTIVE.md` | **G4: Ship** |

Roles: [AGENT-ROLES.md](AGENT-ROLES.md). Runners: [MODEL-ROUTING.md](MODEL-ROUTING.md). Gates: [AUTONOMY-POLICY.md](AUTONOMY-POLICY.md).

---

## The five gates

A gate is a full stop. The work does not continue until a human types approval.

| Gate | Name | Fires when | Approves what |
|---|---|---|---|
| **G1** | Direction Lock | End of S3 | The design thesis, before any UI is built |
| **G2** | Dependency | Any time a package is proposed | One named package, with justification |
| **G3** | Build Complete | End of S5 | QA passed, ready for human eyes |
| **G4** | Ship | Before push / deploy to production | Code leaving the machine |
| **G5** | Publish | Before any public content posts | Words going out under your name |

G2 and G5 can fire at any stage. G1, G3, G4 are sequential.

---

## S0 — Route

**Input:** one sentence from you.
**Output:** a Routing Block.

Read [ROUTER.md](ROUTER.md). Detect mode, set confidence, batch questions, log assumptions, name the first action.

Do not research. Do not design. Do not open an editor.

---

## S1 — Discover

**Input:** Routing Block + your answers.
**Output:** [`PROJECT.md`](templates/PROJECT.md).
**Skills:** [discovery](skills/discovery.md), then [grilling](skills/grilling.md) for the modes that need it.

Discovery collects. Grilling stress-tests. They are different skills and grilling is the one people skip.

Grilling is **mandatory** for premium client website, personal portfolio, product app, and content system. It is skipped for game/experiment and benchmark, where the cost of being wrong is a wasted afternoon rather than a wasted reputation.

S1 is done when you can answer, without hedging:
- What is this?
- Who is it for?
- What is deliberately not in it?
- How will we know it worked?

If any answer is vague, S1 is not done. Vague scope produces generic design. This is the single highest-leverage stage in the system.

---

## S2 — Research

**Input:** `PROJECT.md` open questions.
**Output:** [`RESEARCH.md`](templates/RESEARCH.md).
**Skills:** [live-research](skills/live-research.md), [component-research](skills/component-research.md), [reference-analysis](skills/reference-analysis.md).

Three separate research jobs, often confused:

| Job | Skill | Answers |
|---|---|---|
| World facts | live-research | What does this cost? Is this library alive? What are the limits? |
| Component landscape | component-research | Has this interaction been solved well? By whom? |
| Visual references | reference-analysis | What mechanism makes these references work? |

Every fact carries a date and a URL. See [RESEARCH-POLICY.md](RESEARCH-POLICY.md). Undated claims are not research, they are memory, and memory is stale.

S2 is compressed or skipped for game/experiment unless a technical unknown blocks the build.

---

## S3 — Direct

**Input:** `PROJECT.md`, `RESEARCH.md`.
**Output:** [`DESIGN.md`](templates/DESIGN.md), [`ARCHITECTURE.md`](templates/ARCHITECTURE.md), [`ASSETS.md`](templates/ASSETS.md).
**Skills:** [design-direction](skills/design-direction.md), [motion-design](skills/motion-design.md), [asset-generation](skills/asset-generation.md).

This is the stage that decides whether the output looks generic. Everything in [DESIGN-TASTE.md](DESIGN-TASTE.md) applies here, not at S4.

The core deliverable is the **design thesis**: one sentence naming the organising idea, which is specific enough that a different designer would produce recognisably the same thing and a generic template would fail it.

Design and architecture run in parallel. Architecture must not constrain the thesis before it exists, and the thesis must not demand something architecture cannot deliver. If they conflict, design wins on visual modes, architecture wins on product app.

### G1 — Direction Lock

Nothing gets built until the thesis is approved. Present:

1. The thesis, one sentence.
2. Typography and palette decisions with reasons.
3. The one memorable moment ("signature moment").
4. What this direction explicitly rejects.
5. Visual-quality scorecard self-assessment ([DESIGN-TASTE.md](DESIGN-TASTE.md)).

If you cannot state what the direction rejects, there is no direction.

---

## S4 — Build

**Input:** `DESIGN.md`, `ARCHITECTURE.md`, [`HANDOFF.md`](templates/HANDOFF.md).
**Output:** working code, [`TASKS.md`](templates/TASKS.md) progressing.
**Skills:** [frontend-build](skills/frontend-build.md), [motion-design](skills/motion-design.md), [asset-generation](skills/asset-generation.md).

Rules:

- One task per branch or worktree.
- Every task in `TASKS.md` has an acceptance criterion and a verification method before work starts.
- No new dependency without **G2**. See [LIBRARY-POLICY.md](LIBRARY-POLICY.md).
- Build the signature moment early, not last. If it is left to the end it gets cut.
- Production build must pass before a task is marked done. Not the dev server. The production build.

The implementer does not redesign. If the design cannot be built as specified, that is a finding to raise, not a licence to substitute something easier. Raise it, get a decision, then build.

---

## S5 — Verify

**Input:** working build.
**Output:** [`QA.md`](templates/QA.md).
**Skills:** [browser-qa](skills/browser-qa.md), [accessibility](skills/accessibility.md), [performance](skills/performance.md), [evaluation](skills/evaluation.md).

Two halves that must both happen:

**Mechanical** (does it work) — build, types, lint, console, responsive, a11y, performance. Full checklist in [QA-POLICY.md](QA-POLICY.md).

**Judgement** (is it good) — the review lenses in [EVALUATION-RUBRICS.md](EVALUATION-RUBRICS.md). At minimum: creative director + one mode-appropriate lens.

A build that passes every mechanical check and scores 2/5 on creative direction has **failed S5**. Both halves are pass/fail. This is the rule that stops the system from shipping technically-correct generic work.

### G3 — Build Complete

Present screenshots, the QA table, rubric scores, and known gaps. You look at it. You decide.

---

## S6 — Ship & Learn

**Input:** approved build.
**Output:** deployment + [`RETROSPECTIVE.md`](templates/RETROSPECTIVE.md).
**Skills:** [deployment](skills/deployment.md), [evaluation](skills/evaluation.md).

### G4 — Ship

Push and deploy require explicit approval every time. Approval for one deploy is not approval for the next.

### The retrospective is not optional

This is the stage that makes the Builder OS improve instead of ossify. Fifteen minutes, four questions:

1. Which stage took longest, and was that the right place to spend time?
2. Where did the output drift generic, and which rule failed to catch it?
3. Which questions should the router have asked and did not?
4. What changes in the Builder OS as a result?

Answer 4 by editing the relevant Builder OS file and logging it in [CHANGELOG.md](CHANGELOG.md). A retrospective that changes nothing was not a retrospective.

---

## Stage compression by mode

Not every project deserves seven stages. Compression is legitimate; skipping is not.

| Mode | S1 | S2 | S3 | S4 | S5 | S6 |
|---|---|---|---|---|---|---|
| Premium client website | Full | Full | Full | Full | Full | Full |
| Personal portfolio | Full | Light | Full | Full | Full | Full |
| Product app | Full | Full | Light visual, full architecture | Full | Full | Full |
| Game / experiment | Light | Skip unless blocked | Light | Full | Light | Light |
| Content system | Full | Full | N/A | Ongoing | Per post | Weekly |
| Audit / review | Light | As needed | N/A | N/A | Full (this *is* the work) | Findings only |
| Benchmark | Hypothesis only | Full | N/A | N/A | Full | Full |

**S3 is never skipped for anything with a visual surface.** A retro boxing game gets a light S3, not no S3, because "retro" without a thesis produces the same beige pixel-font output every time.

---

## Parallel work

Safe to run at the same time:

- S2 research and S1 grilling.
- Design direction and architecture within S3.
- Accessibility and performance review within S5.
- Asset generation alongside S4 build, provided `ASSETS.md` is locked.

Never parallel:

- S3 and S4. Building before direction is locked is how generic work happens.
- Two implementers on one branch.
- QA and fixes on the same file without re-running QA afterwards.
