# ADAPTER: Claude Code

**Role in the system: implementation agent, interchangeable with Cursor.** Primary during the transition; a permanent fallback afterwards.

Capability classes: **`R2`**, **`R3`**, **`R4`**, **`R6`**. See [MODEL-ROUTING.md](../MODEL-ROUTING.md).

**By design, this adapter is replaceable.** If Claude Code disappeared, [cursor.md](cursor.md) absorbs its classes and nothing else in the Builder OS changes. That is the portability test ([MODEL-ROUTING.md](../MODEL-ROUTING.md) section 10).

---

## Owns

Same as [cursor.md](cursor.md): S4 implementation, S5 mechanical QA, S6 git and deploy commands. Roles: Implementer, Motion specialist, QA engineer.

**Stronger than Cursor at:** long agentic multi-file work in a terminal, running and reading build output, orchestrating shell commands, and worktree-based parallel work.

**Does not own:** the design thesis, architecture decisions, dependency approval, or judgement-half QA.

---

## Setup

**1. `AGENTS.md` at the project root** ([templates/AGENTS.md](../templates/AGENTS.md)) — Claude Code reads it. A project `CLAUDE.md` works too; do not maintain both, since two rule files drift apart.

**2. Precedence.** Your global `~/.claude/CLAUDE.md` already carries rules that align closely with this system — think before coding, simplicity first, surgical changes, one task at a time. Project `AGENTS.md` outranks it ([ROUTER.md](../ROUTER.md) section 8).

**3. Permissions.** Approve build, typecheck, lint, test, and git read commands so Green-tier work does not prompt constantly. **Do not** blanket-approve installs, pushes, or deploys — those are G2 and G4 and the prompt is the gate.

---

## Installed skills on this machine

Verified present at `C:\Users\User\.claude\skills` on 2026-08-21. **Their existence is verified; their quality and behaviour are not — I have not run them.** Treat this table as a starting point to test, not a recommendation.

| Builder OS skill | Candidate local skill | Notes |
|---|---|---|
| [intake](../skills/intake.md) | `grill-me` | Closest direct match in the set |
| [design-direction](../skills/design-direction.md) | `design-taste-frontend`, `high-end-visual-design`, `impeccable` | Three overlapping options — pick one and stay with it, or they will fight each other |
| [DESIGN-MOTION.md](../DESIGN-MOTION.md) | `design-motion-principles` | Has an audit mode for catching generic motion |
| [QA-POLICY.md](../QA-POLICY.md) | `webapp-testing` | Playwright-based |
| [DESIGN-ASSETS.md](../DESIGN-ASSETS.md) | `banana`, `brandkit`, `imagegen-frontend-web`, `imagegen-frontend-mobile` | **Check whether any bills per token** before use ([BUDGET-POLICY.md](../BUDGET-POLICY.md)) |
| [component-research](../skills/component-research.md) | `ui-ux-pro-max` | Local database of patterns |
| [CONTENT-SYSTEM.md](../CONTENT-SYSTEM.md) | `humanizer` | Useful for the anti-AI-tell sweep specifically |
| [EVALUATION-RUBRICS.md](../EVALUATION-RUBRICS.md) | `claude-mem:design-is`, `design-motion-principles` (audit mode) | Neither replaces the rubrics in [EVALUATION-RUBRICS.md](../EVALUATION-RUBRICS.md) |
| [reference-analysis](../skills/reference-analysis.md) | **none** | Use the skill file's method |
| [QA-POLICY.md](../QA-POLICY.md) | **none directly** | Use the skill file's method |
| [QA-POLICY.md](../QA-POLICY.md) | **none directly** | Use the skill file's method |
| [RESEARCH-POLICY.md](../RESEARCH-POLICY.md) | built-in web search | |
| [QA-POLICY.md](../QA-POLICY.md) | built-in bash | |

Built-in commands worth knowing: `/code-review` (diff review, user-triggered), `/security-review`, `/init`, `/run`.

**Three cautions.**

First, several of these skills carry **their own strong aesthetic opinions** — `minimalist-ui`, `industrial-brutalist-ui`, `gpt-taste`, `high-end-visual-design`. Those opinions can override your `DESIGN.md` thesis and produce that skill's house style instead of your direction. **`DESIGN.md` outranks any skill.** If a skill's output fights the thesis, the skill is wrong.

Second, having three overlapping design skills is itself a risk. Pick one, learn its behaviour, and record which one you chose and why in the retrospective.

Third, image-generation skills may use paid APIs. Verify before running one — pay-per-token is Amber ([BUDGET-POLICY.md](../BUDGET-POLICY.md)).

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
| Both `CLAUDE.md` and `AGENTS.md` in a project | Keep one |
| Using Claude Code for S3 because Codex is out | Wait. Waiting is cheaper than rebuilding. |
