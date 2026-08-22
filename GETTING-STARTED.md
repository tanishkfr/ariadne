# GETTING STARTED

First-time setup. About five minutes, then one real project.

Written for someone who has never used this system. If any step assumes knowledge you do not have, that is a bug in this file — fix it when you hit it.

---

## The whole system in 60 seconds

You describe what you want. A **router** decides what kind of project it is. That determines which **questions** get asked, which **documents** get written, and which **tool** does which part.

**One tool decides. Another tool builds.** They communicate through a file called `HANDOFF.md`, not through you re-explaining things.

Five **gates** stop the process for your approval: before building (G1), before installing anything (G2), after build and review evidence (G3), before shipping (G4), before publishing (G5).

That is it. Everything else is detail.

---

## Step 1 — Prerequisites

Required for Builder OS itself: Python 3.8+ and Git. Required when a project reaches the default build stack: Node.js and pnpm. GitHub authentication, hosting accounts, and Cursor sign-in are not prerequisites for routing or design.

```bash
python --version
git --version
node --version
pnpm --version
```

If a build prerequisite is missing, stop and install it deliberately; do not substitute a package manager or Node version silently.

---

## Step 2 — Confirm your budget reality

**Do this before subscribing to anything.** It takes two minutes and converts four unverified rows in [BUDGET-POLICY.md](BUDGET-POLICY.md) into verified ones.

1. Open Cursor's pricing page **while in India** and look for the ₹650 plan you mentioned. It does not appear on the international page. Confirm the price at checkout, not on the marketing page.
2. Open ChatGPT's pricing page and record what you are actually charged in INR.
3. Write both into the table in [BUDGET-POLICY.md](BUDGET-POLICY.md) section 3 with today's date.

**Expected total: around ₹2,649/month**, which is inside your ideal band. If the ₹650 plan does not exist, read section 4 of that file — the fallback order is there, and it changes what you should subscribe to.

---

## Step 3 — Install the Builder OS entry

From the Builder OS repository, run:

```bash
python scripts/install-builderos-skill.py install
python scripts/install-builderos-skill.py verify
```

The installed skill is a managed copy that points back to this checkout. The
repository remains canonical. Re-run `install` after pulling a Builder OS
update; `verify` detects drift and refuses an unmanaged skill directory.

Open a clean Codex task and write:

```text
$builderos
I want to make ...
```

Natural language such as “Use Builder OS for this project” also triggers it.
Builder OS creates or finds the durable run, reads the current packet itself,
and performs same-session reasoning work. It asks you only for a real decision
or an unavoidable external action.

---

## Step 4 — Set up your build tool (Cursor)

This is the tool that **builds**. It does not decide direction.

1. Sign in only when Builder OS has selected an external implementation handoff.
2. Open the project directory and paste the one verified handoff Builder OS gives you.
3. Return the generated implementation-return block. Builder OS validates and stores it.

You do not need to copy project rules or canonical QA files manually; they are
inside the verified handoff packet. Let the project-brief pass create root
`AGENTS.md`; do not pre-create it.

Claude Code works identically as a fallback — see [adapters/claude-code.md](adapters/claude-code.md). **Read the cautions in that file**, particularly about design skills whose house style can override your `DESIGN.md`.

---

## Step 5 — Run one real project

Do not read the rest of the documentation first. Run something small and real.

**Pick a [game-experiment](modes/game-experiment.md).** It is the lightest mode: three questions, two documents, and it finishes in a day.

1. Choose or create an empty project directory. Builder OS will initialise its
   local Git repository if required. For an existing repository, say explicitly
   that you want to adopt it; Builder OS uses its non-destructive adoption path
   instead of pretending the repository is empty.
2. Invoke `$builderos` and describe the idea normally.
3. Answer the one batched set of material questions. Accept all proposed
   defaults in one line when they are right.
4. Review the design direction at G1. This is the first intentional pause.

Behind the scenes, Builder OS creates the run outside the project, transports
only the current stage's inputs, verifies their hashes, records available
evidence, and chooses research or design from the actual project state. A
failure resumes from the last valid boundary; it does not overwrite history or
restart the project.

When you reach **G1**, the system will present a design direction and stop. **This is the moment that matters.** Read it. If it says "clean, modern, minimal", reject it — that is a mood, not a direction, and the system is meant to catch that. Ask for a thesis specific enough that a template would fail it.

### Bringing in an existing project

Invoke `$builderos` from the repository and say what outcome you want from the
existing project. Builder OS inspects the live repository during S1 but does not
rewrite implementation, delete files, or reset current behaviour. The runtime's
explicit recovery command is:

```bash
python scripts/builderos.py start --project <project> --adopt-existing --request "<outcome>"
```

This is intentionally opt-in. Ordinary `start` still refuses a non-empty
directory. Adoption also refuses to overwrite an existing `PROJECT.md` or
`AGENTS.md`; in that case resume the recorded run or plan a deliberate merge.

---

## Step 6 — Run one review

After implementation and mechanical QA, Builder OS generates one isolated
review handoff for a **fresh independent session**. It extracts only intent,
success criteria, accepted patterns, the target, and the canonical rubric. It
excludes project documents, source, QA, and build history.

Fresh matters. A session that built the thing will defend it, because it knows why every compromise happened. That sympathy is exactly what your audience will not have.

---

## What to read, and when

Do not read all of it now. Read each file the first time you hit its stage.

| When | Read |
|---|---|
| Right now | This file, then [DAILY-PLAYBOOK.md](DAILY-PLAYBOOK.md) |
| Starting any project | Invoke `$builderos`; it loads [ROUTER.md](ROUTER.md) when needed |
| Debugging transport | [scripts/prepare-stage.py](scripts/prepare-stage.py) |
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
