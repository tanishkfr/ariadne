# GETTING STARTED

First-time setup. About 30 minutes, then one real project.

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

## Step 3 — Set up your reasoning tool (Codex / ChatGPT)

This is the tool that **decides**. It does not write your code.

1. Read the setup and session boundary in [adapters/codex.md](adapters/codex.md).
2. Start each stage in a fresh session.
3. Generate the stage's packet with [scripts/prepare-stage.py](scripts/prepare-stage.py). The packet carries only the canonical inputs that stage needs and records their hashes.

Do not upload the whole Builder OS. Generated packets are transient transport artifacts, not a second knowledge base.

---

## Step 4 — Set up your build tool (Cursor)

This is the tool that **builds**. It does not decide direction.

1. Follow [adapters/cursor.md](adapters/cursor.md).
2. Add the project rules block from that file.
3. Let S1 create the project-root `AGENTS.md`. Do not pre-create it; S1 must fill the runtime state from the routed project.

Claude Code works identically as a fallback — see [adapters/claude-code.md](adapters/claude-code.md). **Read the cautions in that file**, particularly about design skills whose house style can override your `DESIGN.md`.

---

## Step 5 — Run one real project

Do not read the rest of the documentation first. Run something small and real.

**Pick a [game-experiment](modes/game-experiment.md).** It is the lightest mode: three questions, two documents, and it finishes in a day.

1. Create an empty project repository containing only `.git` and `.gitignore`.
2. Put the brief in a text file outside the project, then prepare S1:

   ```bash
   python scripts/prepare-stage.py prepare --stage S1 --project <project-path> --output <runs-path>/P1-S1 --request-file <brief-path>
   ```

3. Open a fresh reasoning session rooted at the project and paste only `<runs-path>/P1-S1/packet.txt`.
4. Save the verbatim session transcript to `<runs-path>/P1-S1/evidence/transcript.md`.
5. Answer the routing questions. Once S1 has created `PROJECT.md` and `AGENTS.md`, prepare S3:

   ```bash
   python scripts/prepare-stage.py prepare --stage S3 --project <project-path> --output <runs-path>/P1-S3 --parent <runs-path>/P1-S1 --motion yes --assets no
   ```

   Set the two trigger flags from the actual project. Use `--references-file` when references exist; otherwise the packet explicitly carries `none yet`.

   If `PROJECT.md` contains a blocking factual question, prepare S2 first with
   `--stage S2 --parent <runs-path>/P1-S1`. Save its transcript and `RESEARCH.md`,
   then use the S2 packet directory as S3's parent. S2 transports only those
   blocking questions plus the canonical research policy and template.

Every stage hands you the next one. The packet verifier refuses stale canonical sources, a missing parent transcript, a wrong parent stage, or an existing output directory, so previous evidence is not silently overwritten.

When you reach **G1**, the system will present a design direction and stop. **This is the moment that matters.** Read it. If it says "clean, modern, minimal", reject it — that is a mood, not a direction, and the system is meant to catch that. Ask for a thesis specific enough that a template would fail it.

---

## Step 6 — Run one review

After S4B has completed mechanical QA, prepare S5 with the reachable target and the human-selected lens:

```bash
python scripts/prepare-stage.py prepare --stage S5 --project <project-path> --output <runs-path>/P1-S5 --parent <runs-path>/P1-S4B --target <url> --lenses "creative-director (light)"
```

Run its `packet.txt` in a **fresh independent session**. The generator extracts only intent, success criteria, and accepted patterns from `PROJECT.md`; it excludes the project documents, source, QA, and build history.

Fresh matters. A session that built the thing will defend it, because it knows why every compromise happened. That sympathy is exactly what your audience will not have.

---

## What to read, and when

Do not read all of it now. Read each file the first time you hit its stage.

| When | Read |
|---|---|
| Right now | This file, then [DAILY-PLAYBOOK.md](DAILY-PLAYBOOK.md) |
| Starting any project | [ROUTER.md](ROUTER.md) |
| Preparing any fresh stage | [scripts/prepare-stage.py](scripts/prepare-stage.py) |
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
