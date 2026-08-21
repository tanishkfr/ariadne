# MIGRATION CHECKLIST

Moving from "Claude Code does everything" to "Codex decides, Cursor builds".

**The migration is not really about tools.** It is about separating *deciding* from *building*. That separation is what conserves usage and stops one agent from reviewing its own work — and it would be worth doing even if you kept exactly the tools you have.

---

## What actually changes

| Before | After |
|---|---|
| One agent plans, designs, codes, debugs, reviews | Deciding and building are separate tools with separate sessions |
| Context re-explained every conversation | `HANDOFF.md` carries decisions |
| Design happens while coding | Design locked at G1 before any code |
| Review by the thing that built it | Review in a fresh session |
| Packages installed when they seem useful | G2 on every one |
| Whatever the tool defaults to | Documents are the source of truth |

**If you did none of the tool migration and only adopted the G1 gate and the fresh-session review, you would get most of the benefit.** Worth knowing before you spend money.

---

## Phase 0 — Prerequisites

- [ ] **Install pnpm** — `corepack enable`, then `pnpm --version`. Not currently installed on this machine, and every default assumes it.
- [ ] **Confirm the ₹650 Cursor India plan at checkout.** It is not on the international pricing page. Record it in [BUDGET-POLICY.md](BUDGET-POLICY.md) section 3 with the date.
- [ ] **Confirm your actual ChatGPT charge in INR.** The official pricing page returned 403 during this build, so nothing about it here is verified.
- [ ] Update the cost table with both real numbers.

**Expected: around ₹2,649/month**, inside your ideal band. If the ₹650 plan does not exist, read [BUDGET-POLICY.md](BUDGET-POLICY.md) section 4 before subscribing to anything — the fallback order changes the answer.

---

## Phase 1 — Set up the reasoning tool

- [ ] Create the Codex/ChatGPT project with the instruction block from [adapters/codex.md](adapters/codex.md)
- [ ] Upload **[ROUTER.md](ROUTER.md)** and **[DESIGN-TASTE.md](DESIGN-TASTE.md)** only
- [ ] Test it: paste [prompts/project-start.md](prompts/project-start.md) with a fake request and check it emits a proper Routing Block

**Test it is working:** it should refuse to write implementation code and should end with one concrete next action. If it starts writing components, the instructions did not take.

---

## Phase 2 — Set up the build tool

- [ ] Configure Cursor per [adapters/cursor.md](adapters/cursor.md)
- [ ] Add the project rules block
- [ ] Confirm it uses pnpm, not npm
- [ ] Test: give it a filled `HANDOFF.md` and see whether it starts without asking you to re-explain the project

**Test it is working:** it should read `HANDOFF.md` and begin. If it asks what the project is about, the handoff was incomplete — which is a bug in the handoff, not in the tool.

---

## Phase 3 — Run one project in the new split

- [ ] Pick something small. [game-experiment](modes/game-experiment.md) mode.
- [ ] Reasoning tool: S0-S3, ending at **G1**
- [ ] Build tool: S4, from `HANDOFF.md` alone
- [ ] Build tool: S5 mechanical QA
- [ ] **Fresh session**: S5 judgement review
- [ ] Retrospective

**The thing to watch:** did the build tool need context that was not in `HANDOFF.md`? Every time it did, that is a gap to fix in the handoff template. This is the main thing Phase 3 is measuring.

---

## Phase 4 — Keep Claude Code as a fallback

Do not uninstall it. It stays useful:

| Use it for | Why |
|---|---|
| Long agentic multi-file work in a terminal | Genuinely better at this |
| When Cursor hits its limit | Same `HANDOFF.md`, no rework |
| Worktree-based parallel tasks | Handles them cleanly |
| Benchmarking against Cursor | [CHANGELOG.md](CHANGELOG.md), same handoff, one variable |

- [ ] Copy [templates/AGENTS.md](templates/AGENTS.md) into projects so both tools read the same rules
- [ ] Read the cautions in [adapters/claude-code.md](adapters/claude-code.md) — particularly that several installed design skills carry their own house style that can override `DESIGN.md`

---

## Phase 5 — Verify the separation held

After two projects, check honestly:

- [ ] Did the reasoning tool write production code? **It should not have.**
- [ ] Did the build tool make design decisions? **It should not have.**
- [ ] Did you re-explain context that was already in a document?
- [ ] Did any review run in the session that built the thing?
- [ ] Did G1 ever get skipped because the deadline was tight?

Each "yes" points at a specific fix: tighten the adapter instructions, improve the handoff, or start a fresh session. **A "yes" to the last one is the most serious** — it means the gate is not functioning as a gate.

---

## What NOT to migrate

- **Do not** rebuild existing projects to fit this system. Apply it to new work.
- **Do not** move private material into the Builder OS repo ([PRIVACY-POLICY.md](PRIVACY-POLICY.md)).
- **Do not** encode design judgement into a plugin or a skill — the thesis is per-project ([adapters/cursor.md](adapters/cursor.md)).
- **Do not** subscribe to anything until Phase 0 is done.

---

## Rollback

If the split makes things worse, going back costs nothing: the documents are plain markdown and every tool reads them.

Keep, regardless of tooling:

1. **G1** — direction approved before building
2. **Fresh-session reviews**
3. **`HANDOFF.md`** — decisions written down once

Those three carry most of the value and are tool-independent. The rest is optimisation.

---

## Timeline

| Phase | Time |
|---|---|
| 0 — Prerequisites | 20 min |
| 1 — Reasoning tool | 20 min |
| 2 — Build tool | 20 min |
| 3 — First project | 1-2 days |
| 4 — Fallback | 10 min |
| 5 — Verify | After 2 projects |

**Phases 0-2 are one hour.** Do them in one sitting; a half-configured setup is worse than either end state, because you will not know which part is failing.
