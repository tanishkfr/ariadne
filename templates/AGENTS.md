# AGENTS: <name>

> Template. Project-specific rules for any AI tool working in this repository.
> Place at the repository root. Cursor, Claude Code, and Codex all read a file like this.
> **This file is the highest authority in the precedence chain** — see [ROUTER.md](../ROUTER.md) section 8.
> Keep it short. A long rules file gets skimmed.

---

## What this is

<One paragraph: what the project is, who it is for, and its mode.>

**Mode:** <> · **Design thesis:** <one sentence from `DESIGN.md`>

## Read before working

| Document | Why |
|---|---|
| `PROJECT.md` | Scope and non-goals |
| `DESIGN.md` | The thesis. **Do not deviate without a decision.** |
| `ARCHITECTURE.md` | Structure and dependencies |
| `TASKS.md` | What to do next |
| `HANDOFF.md` | The current implementation brief |

## Commands

```bash
pnpm install
pnpm dev
pnpm build        # production build — the standard for "done"
pnpm tsc --noEmit
pnpm lint
pnpm test         # Playwright
```

**Use pnpm.** Do not run npm or yarn in this repository.

## Architecture constraints

- <e.g. Server components by default; `'use client'` only where interaction requires it>
- <e.g. No global state library — local, URL, or server state only>
- <e.g. No backend; forms go to <service>>
- <e.g. Content is co-located with components; there is no CMS>

## Design constraints

- **Every value comes from the token system** in `<path>`. Hardcoded colours, sizes, or spacing are a QA finding.
- <e.g. No scroll-triggered fade-ups anywhere. Motion is feedback and continuity only.>
- <e.g. Type scale is fixed at the ratio in `DESIGN.md`. No intermediate sizes.>
- <e.g. One accent colour. Do not introduce a second.>
- The signature moment is `<name>`. **Do not simplify or remove it** without a decision.

## Do not change

> Things that look wrong but are deliberate. Without this list, agents "helpfully" revert them.

| File / behaviour | Why it is like that |
|---|---|
| <> | <> |

## If the design cannot be built as specified

Raise a finding. Do not substitute something easier.

```
BUILD FINDING
Specified:  <what DESIGN.md says>
Problem:    <why it does not work>
Option A:   <closest achievable, what is lost>
Option B:   <alternative, what it costs>
Recommend:  <which, why>
```

Then wait for a decision. **Silent substitution is how art-directed work degrades into template work.**

## Testing rules

- Production build must pass before any task is marked done.
- Zero type errors. Zero console errors. Zero React warnings.
- Responsive: 375, 768, 900, 1280, 1920.
- Keyboard-operable, visible focus, reduced-motion designed.
- Add a Playwright test for anything you would otherwise check twice by hand.

## Git rules

- One task, one branch: `s4/<slug>`. Never commit to `main` directly.
- `git status` before `git add`. Never commit `.env` or any credential.
- **Do not push or deploy without explicit approval** (G4).
- Commit messages: what changed and why, not "updates".

## Approval required

Ask before: installing any dependency (G2), pushing or deploying (G4), using a secret or environment variable, deleting files you did not create, `git reset --hard` or force push, adding auth / a database / a CMS / analytics, or any paid service.

Full policy: [WORKFLOW.md](../WORKFLOW.md).

## Out of scope

> From `PROJECT.md` non-goals. Do not build these even if they seem obviously useful.

1. <>
2. <>
3. <>
