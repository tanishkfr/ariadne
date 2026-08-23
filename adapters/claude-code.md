# ADAPTER: Claude Code

**Role in the system: implementation agent, interchangeable with Cursor.** Primary during the transition; a permanent fallback afterwards.

Capability classes: **`R2`**, **`R3`**, **`R4`**, **`R6`**. See [MODEL-ROUTING.md](../MODEL-ROUTING.md).

**By design, this adapter is replaceable.** If Claude Code disappeared, [cursor.md](cursor.md) absorbs its classes and nothing else in the Ariadne changes. That is the portability test ([MODEL-ROUTING.md](../MODEL-ROUTING.md) section 10).

---

## Owns

Same as [cursor.md](cursor.md): S4 implementation, S5 mechanical QA, S6 git and deploy commands. Roles: Implementer, Motion specialist, QA engineer.

**Stronger than Cursor at:** long agentic multi-file work in a terminal, running and reading build output, orchestrating shell commands, and worktree-based parallel work.

**Does not own:** the design thesis, architecture decisions, dependency approval, or judgement-half QA.

---

## Setup

**1. Delivered runtime state.** Claude Code reads `CLAUDE.md`, not `AGENTS.md`.
Ariadne does not add a provider-specific `CLAUDE.md` to projects. The S4B
packet explicitly transports the current project-root `AGENTS.md`, so Claude
must follow that delivered runtime state rather than relying on automatic file
discovery.

**2. Precedence.** Canonical Ariadne policy and the verified stage packet
outrank user-level Claude preferences. No claim is made about the contents of a
particular machine's global `~/.claude/CLAUDE.md`.

**3. Permissions.** Approve build, typecheck, lint, test, and git read commands so Green-tier work does not prompt constantly. **Do not** blanket-approve installs, pushes, or deploys — those are G2 and G4 and the prompt is the gate.

---

## Optional local skills

Provider-local skills are discovered at runtime and are never assumed to be
installed. Select at most one skill for a given job, record why it is useful,
and keep `DESIGN.md` and the canonical Ariadne policies authoritative. A local
skill that introduces paid or metered services still requires G2 approval.

---

## Working method

Identical to [cursor.md](cursor.md): read `HANDOFF.md` not chat history, one task per branch, token system first, verify in increments, production build as the standard for done, `BUILD FINDING` instead of silent substitution.

**Worktrees.** Claude Code handles worktrees well, which is the cleanest way to run parallel tasks. Rules still apply: one task per worktree, never two agents in one working directory, merges need G4.

**Browser tools.** Available for `R4`. Same escalation ladder — build, typecheck, Playwright, browser, eyes. Anything checked twice becomes a Playwright test.

---

## Transition status

You are moving toward Codex + Cursor. During that period:

| Situation | Use |
|---|---|
| Codex is exhausted, direction work is pending | **Wait.** Do not let an implementation tool invent direction. |
| Cursor is exhausted, tasks are specified | Claude Code, same `HANDOFF.md` |
| Long agentic multi-file work in a terminal | Claude Code — genuinely better at this |
| You want to compare the two | [CHANGELOG.md](../CHANGELOG.md), same handoff, one variable |

Full sequence: [MIGRATION-CHECKLIST.md](../MIGRATION-CHECKLIST.md).

---

## Failure modes

| Failure | Countermeasure |
|---|---|
| A design skill's house style overriding `DESIGN.md` | The thesis outranks every skill |
| Three design skills producing three directions | Pick one; record the choice |
| An image skill quietly spending money | Verify billing before running |
| Blanket-approving all permissions | Installs, pushes, deploys stay gated |
| Assuming Claude automatically discovers `AGENTS.md` | Use the verified packet that explicitly delivers it |
| Using Claude Code for S3 because Codex is out | Wait. Waiting is cheaper than rebuilding. |
