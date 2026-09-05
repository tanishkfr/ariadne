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

Ariadne itself needs Python 3.10 or newer and Codex. Git, Node.js, pnpm,
hosting accounts and external build tools are not first-run requirements. If a
project later needs one, Ariadne explains why and waits for the relevant
approval.

```bash
python --version
```

---

## Step 2 — Install Ariadne

Install the current public version directly from GitHub:

```bash
python -m pip install --user "https://github.com/tanishkfr/ariadne/releases/download/v1.6.1/ariadne-1.6.1-py3-none-any.whl"
python -m ariadne install
python -m ariadne doctor
```

This installs one user-local runtime and registers `$ariadne`; no source
checkout or manual skill copy is needed. See [INSTALL.md](INSTALL.md) for
platform locations and [TROUBLESHOOTING.md](TROUBLESHOOTING.md) if doctor finds
a problem.

The optional generic Codex baseline is not installed by default. If you want
it, run `python -m ariadne codex-baseline install`; existing user instructions
are never overwritten. Restart Codex afterwards.

Codex remains the default and Claude is not installed or enabled by this
process. If Claude Code is already installed and you explicitly want it as the
reasoner, run `python -m ariadne enable-claude`. Use `disable-claude` to
remove only that optional entry. Cursor remains the default external S4B tool.

---

## Step 3 — Describe one project

Open a clean Codex task and write:

```text
$ariadne
I want to make ...
```

Natural language such as “Use Ariadne for this project” also triggers it.
Ariadne creates or finds the durable run, reads the current packet itself,
and performs same-session reasoning work. It asks you only for a real decision
or an unavoidable external action.

Subscription and provider costs matter only if the chosen project reaches that
need. Verify current prices then and record them under [BUDGET-POLICY.md](BUDGET-POLICY.md);
do not subscribe merely to complete installation.

---

## Step 4 — Set up your build tool (Cursor)

This is the tool that **builds**. It does not decide direction.

1. Sign in only when Ariadne has selected an external implementation handoff.
2. Open the project directory and paste the one verified handoff Ariadne gives you.
3. Return the generated implementation-return block. Ariadne validates and stores it.

You do not need to copy project rules or canonical QA files manually; they are
inside the verified handoff packet. Let the project-brief pass create root
`AGENTS.md`; do not pre-create it.

Claude Code uses the same S4B packet contract as an optional fallback — see
[adapters/claude-code.md](adapters/claude-code.md). Its transport is prepared,
but live equivalence remains unverified. **Read the cautions in that file**,
particularly about design skills whose house style can override your
`DESIGN.md`.

---

## Step 5 — Run one real project

Do not read the rest of the documentation first. Run something small and real.

**Pick a [game-experiment](modes/game-experiment.md).** It is the lightest mode: three questions, two documents, and it finishes in a day.

1. Choose or create an empty project directory. Ariadne will initialise its
   local Git repository if required. For an existing repository, say explicitly
   that you want to adopt it; Ariadne uses its non-destructive adoption path
   instead of pretending the repository is empty.
2. Invoke `$ariadne` and describe the idea normally.
3. Answer the one batched set of material questions. Accept all proposed
   defaults in one line when they are right.
4. Review the design direction at G1. This is the first intentional pause.

Behind the scenes, Ariadne creates the run outside the project, transports
only the current stage's inputs, verifies their hashes, records available
evidence, and chooses research depth and only the methods the project actually
needs. A URL remains merely found until a retrieval or visual artefact exists;
a method remains merely recommended until it runs and produces an output. A
failure resumes from the last valid boundary; it does not overwrite history or
restart the project.

When external references or technical resources would change the direction,
Ariadne records what it inspected, what it rejected, what it used, and the
exact downstream decision. When research would not change a decision, it skips
the extra pass instead of manufacturing a bibliography.

When you reach **G1**, the system will present a design direction and stop. **This is the moment that matters.** Read it. If it says "clean, modern, minimal", reject it — that is a mood, not a direction, and the system is meant to catch that. Ask for a thesis specific enough that a template would fail it.

### What happens after G1

Once you approve the direction, Ariadne turns its thesis, signature moment,
responsive transformations, interactions and fixed handoff decisions into a
project-local implementation and visual-QA plan. You do not need to rewrite the
direction as a checklist or tell a fresh builder which canonical QA files to
find; the verified S4B packet carries the plan and the selected visual-QA
method.

Every S4B packet names one unique return file under
`.ariadne/returns/<packet-id>.md`. A builder that can write project files puts
the complete marked return there; `advance` ingests only the return belonging
to the current packet. If the provider cannot write the file, use the existing
manual return-ingestion path as recovery. Retries get new targets and preserve
the earlier evidence.

After implementation, Ariadne checks the actual rendered thesis, signature,
responsive transformations and important states. It records source inference,
rendered evidence, observed interaction, drift and environmental gaps as
different claims. An internal creative review gives one prioritised correction
before the isolated independent review. Neither review approves G3 for you.

Normal `$ariadne` progression runs the planning and evidence checks
automatically. If an installed run is interrupted, invoke `$ariadne` again in
the project and ask it to resume or recover; the managed skill locates the
active runtime and its low-level controller. Checkout-relative
`python scripts/ariadne.py ...` commands are maintainer diagnostics, not public
commands an installed user is expected to reconstruct.

If you explicitly ask for a social strategy, Ariadne may add the conditional
`SOCIAL-STRATEGY.md`. It reads the current project and real assets first, then
inspects current platform evidence where needed. Recommendations show what the
source said and what decision changed; voice-unsupported writing remains a
rough draft. If you later paste or attach performance results, Ariadne keeps
the plan, supplied result, bounded interpretation and next test in project-local
`CONTENT-LEARNINGS.md`. It never posts, authenticates or changes a build gate.

### Bringing in an existing project

Invoke `$ariadne` from the repository and say what outcome you want from the
existing project. Ariadne inspects the live repository during S1 but does not
rewrite implementation, delete files, or reset current behaviour. The runtime's
explicit recovery command is:

```bash
python scripts/ariadne.py start --project <project> --adopt-existing --request "<outcome>"
```

This is intentionally opt-in. Ordinary `start` still refuses a non-empty
directory. Adoption also refuses to overwrite an existing `PROJECT.md` or
`AGENTS.md`; in that case resume the recorded run or plan a deliberate merge.

---

## Step 6 — Run one review

After implementation and mechanical QA, Ariadne generates one isolated
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
| Starting any project | Invoke `$ariadne`; it loads [ROUTER.md](ROUTER.md) when needed |
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
