# GETTING STARTED

First-time setup. About 30 minutes, then one real project.

Written for someone who has never used this system. If any step assumes knowledge you do not have, that is a bug in this file — fix it when you hit it.

---

## The whole system in 60 seconds

You describe what you want. A **router** decides what kind of project it is. That determines which **questions** get asked, which **documents** get written, and which **tool** does which part.

**One tool decides. Another tool builds.** They communicate through a file called `HANDOFF.md`, not through you re-explaining things.

Five **gates** stop the process for your approval: before designing (G1), before installing anything (G2), before showing you the finished build (G3), before shipping (G4), before publishing (G5).

That is it. Everything else is detail.

---

## Step 1 — Prerequisites

Already on this machine: node, npm, git, gh (authenticated), corepack.

**Missing: pnpm.** Every default in this system assumes it.

```bash
corepack enable
```

Then verify:

```bash
pnpm --version
```

If `corepack enable` fails on permissions, run the terminal as Administrator once.

---

## Step 2 — Confirm your budget reality

**Do this before subscribing to anything.** It takes two minutes and converts four unverified rows in [BUDGET-POLICY.md](BUDGET-POLICY.md) into verified ones.

1. Open Cursor's pricing page **while in India** and look for the ₹650 plan you mentioned. It does not appear on the international page. Confirm the price at checkout, not on the marketing page.
2. Open ChatGPT's pricing page and record what you are actually charged in INR.
3. Write both into the table in [BUDGET-POLICY.md](BUDGET-POLICY.md) section 3 with today's date.

**Expected total: around ₹2,649/month**, which is inside your ideal band. If the ₹650 plan does not exist, read section 4 of that file — the fallback order is there, and it changes what you should subscribe to.

---

## Step 3 — Set up your reasoning tool (Codex / ChatGPT)

This is the tool that **decides**. It does not write your code.

1. Create a project or custom instruction set.
2. Paste the setup instructions from [adapters/codex.md](adapters/codex.md).
3. Upload two files to its knowledge: **[ROUTER.md](ROUTER.md)** and **[DESIGN-TASTE.md](DESIGN-TASTE.md)**.

Those two carry most of the system's value. Do not upload the whole system — you will pay for that context on every message, and it will not read them all anyway.

---

## Step 4 — Set up your build tool (Cursor)

This is the tool that **builds**. It does not decide direction.

1. Follow [adapters/cursor.md](adapters/cursor.md).
2. Add the project rules block from that file.
3. For each new project, copy [templates/AGENTS.md](templates/AGENTS.md) to the project root and fill it in.

Claude Code works identically as a fallback — see [adapters/claude-code.md](adapters/claude-code.md). **Read the cautions in that file**, particularly about design skills whose house style can override your `DESIGN.md`.

---

## Step 5 — Run one real project

Do not read the rest of the documentation first. Run something small and real.

**Pick a [game-experiment](modes/game-experiment.md).** It is the lightest mode: three questions, two documents, and it finishes in a day.

1. Copy [prompts/project-start.md](prompts/project-start.md).
2. Paste it into your reasoning tool. Replace the last line with your idea.
3. Answer the questions.
4. The session ends by naming the next prompt. **Paste [prompts/design-direction.md](prompts/design-direction.md).**

Every stage hands you the next one. You should never finish a stage and have to browse this repository to work out what happens next — if you do, that is a bug worth recording.

When you reach **G1**, the system will present a design direction and stop. **This is the moment that matters.** Read it. If it says "clean, modern, minimal", reject it — that is a mood, not a direction, and the system is meant to catch that. Ask for a thesis specific enough that a template would fail it.

---

## Step 6 — Run one review

After you have built something, run [prompts/project-review.md](prompts/project-review.md) in a **fresh session**.

Fresh matters. A session that built the thing will defend it, because it knows why every compromise happened. That sympathy is exactly what your audience will not have.

---

## What to read, and when

Do not read all of it now. Read each file the first time you hit its stage.

| When | Read |
|---|---|
| Right now | This file, then [DAILY-PLAYBOOK.md](DAILY-PLAYBOOK.md) |
| Starting any project | [ROUTER.md](ROUTER.md) |
| At your first G1 | [DESIGN-TASTE.md](DESIGN-TASTE.md) — the most valuable file here |
| First time an agent wants to install something | [LIBRARY-POLICY.md](LIBRARY-POLICY.md) |
| First time you run QA | [QA-POLICY.md](QA-POLICY.md) |
| First review | [EVALUATION-RUBRICS.md](EVALUATION-RUBRICS.md) |
| First client project | [modes/client-or-portfolio.md](modes/client-or-portfolio.md), [PRIVACY-POLICY.md](PRIVACY-POLICY.md) |
| Starting content | [CONTENT-SYSTEM.md](CONTENT-SYSTEM.md) |
| After 30 days | [CHANGELOG.md](CHANGELOG.md) "30-day check" |

---

## The five things that actually matter

If you remember nothing else:

1. **Nothing gets built before the design direction is approved (G1).** This is the single rule that prevents generic output.
2. **The tool that decides is not the tool that builds.** `HANDOFF.md` is how they talk. It exists so decisions are never re-derived — which is what burns your usage limits.
3. **Every value comes from the token system.** Hardcoded colours and sizes are how a locked direction drifts back to default.
4. **Reviews run in a fresh session.** Independence is the whole point.
5. **The direction is checked by you at G1, and scored later by a session that did not write it.** Scoring your own direction clusters at 4 and measures nothing.

---

## Common mistakes in week one

| Mistake | What happens | Fix |
|---|---|---|
| Reading all the docs before building | Two hours gone, nothing made | Run a small project first |
| Skipping G1 because it feels slow | Generic output, then a rebuild | It is 15 minutes. It saves days. |
| Using the reasoning tool to write code | Limits gone by mid-month | It writes `HANDOFF.md`, not components |
| Pasting the codebase to ask one question | Same | Paste the interface and the error |
| Approving a weak direction to start building | The thing you were trying to avoid | Reject moods; demand a thesis |
| Filling in every template on a small project | Documentation nobody reads | Modes compress. Game mode needs two documents. |

---

## If it feels like too much process

It might be. **The honest fix is to cut, not to push through.**

After 30 days, run the review in [CHANGELOG.md](CHANGELOG.md) "30-day check". Any document you wrote and never opened again should be deleted — a document nobody reads is worse than no document, because it creates the illusion of process.

The success criterion is deliberately narrow, and it is in [CHANGELOG.md](CHANGELOG.md) under "The 30-day check".
