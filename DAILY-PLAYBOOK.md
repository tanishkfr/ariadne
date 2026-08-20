# DAILY PLAYBOOK

What to open, in what order, for the work in front of you.

Setup: [GETTING-STARTED.md](GETTING-STARTED.md). Detail: [WORKFLOW.md](WORKFLOW.md).

---

## Which tool do I open first?

| Situation | Open | Why |
|---|---|---|
| New idea, nothing exists | **Reasoning tool** (Codex) | It routes and decides |
| Documents exist, `HANDOFF.md` is written | **Build tool** (Cursor) | Nothing left to decide |
| Mid-build, a decision came up | Depends — see below | |
| A bug | **Build tool** | Bugs are `R2` work |
| Same bug, twice failed | Reasoning tool | Escalation signal |
| Something needs checking | **Terminal** | Free, definitive, instant |
| Reviewing finished work | Reasoning tool, **fresh session** | Independence |

**Default: if you are unsure, open the build tool.** Roughly 80% of hours belong there. If you are spending most of your time in the reasoning tool, S3 was under-specified and work is leaking into your expensive tier.

---

## By situation

### "I have an idea"

1. Paste [prompts/project-start.md](prompts/project-start.md) into the reasoning tool.
2. Answer up to 5 questions.
3. Follow the Routing Block's **First action**.

Do not open an editor. Do not pick a framework. Do not start a repo.

### "I know what I'm building, I want to start"

Check: is `HANDOFF.md` written and was **G1** approved?

- **Yes** → open the build tool, start task 1 from `TASKS.md`.
- **No** → you are not ready. Go to S3. Building before direction is locked is the thing this system exists to prevent, and "the deadline is tight" is exactly when it happens.

### "I'm mid-build and something needs deciding"

| The decision | Who |
|---|---|
| How to implement something already specified | Build tool. Just do it. |
| The design cannot be built as specified | **Raise a `BUILD FINDING`.** Never substitute silently. |
| Needs a new package | **Stop. G2.** |
| Cheaper approach that changes the design | Design director decision, not yours to make mid-task |
| Genuinely ambiguous spec | Reasoning tool, with just the ambiguity — not the codebase |

### "Something is broken"

```
1. pnpm build          free, seconds, catches the most
2. pnpm tsc --noEmit   free
3. Read the actual error
4. Build tool, with the error and the relevant file
5. Failed twice? Escalate to the reasoning tool
```

**Do not open the reasoning tool at step 1.** It cannot see your build output, and asking it to guess is the most expensive way to get a worse answer.

### "I need to check whether it works"

Cheapest first, never skip upward:

```
production build → typecheck → Playwright → browser agent → your own eyes
```

Anything you will check twice becomes a Playwright test. Writing it costs about one browser-agent pass and then costs nothing forever.

### "It's done"

1. Build tool: run the mechanical checklist ([QA-POLICY.md](QA-POLICY.md) section 3). Record evidence per row.
2. Capture screenshots — **and look at them yourself**.
3. **Fresh session**: run [prompts/project-review.md](prompts/project-review.md).
4. Present G3.
5. On approval: G4 to ship.
6. Fifteen minutes on `RETROSPECTIVE.md`. **Edit one Builder OS file.** Log it in [CHANGELOG.md](CHANGELOG.md).

### "I want to write a post"

[prompts/content-system.md](prompts/content-system.md), prompt 2. Start from something that actually happened — your `RETROSPECTIVE.md` files are the best source you have.

If there is no only-you element, do not post it.

### "I want feedback on my portfolio"

[prompts/portfolio-evaluation.md](prompts/portfolio-evaluation.md), in a fresh session, against the deployed URL. Expect it to hurt.

---

## A typical project day

| Time | Work | Tool |
|---|---|---|
| First 15 min | Read `TASKS.md`, pick one task, branch | Terminal |
| Bulk of the day | Implement, verify in increments | Build tool |
| Whenever stuck twice | Escalate with the specific blocker | Reasoning tool |
| Last 30 min | Production build, update `TASKS.md`, commit | Terminal + build tool |

**One task, one branch.** Never `main`. This is what makes nearly everything reversible with `git checkout`.

---

## Conserving usage

The five that matter most ([MODEL-ROUTING.md](MODEL-ROUTING.md) section 8):

1. **Never paste a codebase into the reasoning tool.** Paste the interface, the error, the constraint.
2. **Let `HANDOFF.md` do the explaining.** Re-deriving decided context is the biggest recurring waste in this system.
3. **Run free checks first.** Every build that catches a bug is a round trip you did not spend.
4. **New session per stage.** One long thread carries S1's context into S5 and pays on every message.
5. **Never use the reasoning tool as a text editor.**

**Never send to a high-cost model:** build output, test output, obvious lint errors, file listings, git operations, formatting, renames, or "is this working?" when a command answers it.

---

## When a tool hits its limit

| Out of | Do |
|---|---|
| Reasoning (`R1`) | Stop deciding. Do specified `TASKS.md` work. **Never let the build tool invent direction.** |
| Build (`R2`) | Tests, build fixes, cleanup, docs — or hand the same `HANDOFF.md` to the fallback runner |
| Both | Mechanical QA, retrospectives, reference research. All human-doable. |
| At S3 with no approved thesis | **Wait.** Waiting is cheaper than rebuilding. |

**The rule:** when a class is unavailable, do work from a *different class* — never the same work at a lower class. Downgrading direction work to a fast model is how projects go generic without anyone noticing.

---

## Weekly, 20 minutes

- Any `TASKS.md` blocked more than a week? Unblock or cut it.
- Any dependency added that is now used once? Removal candidate.
- Retrospective from a finished project not yet actioned? Do it.
- Content: run the weekly review, update `CONTENT-LEARNINGS.md`.

## Monthly

- Re-verify anything in [BUDGET-POLICY.md](BUDGET-POLICY.md) older than 30 days.
- Which subscription earned its cost this month?
- Which Builder OS documents did you actually open? **Delete the ones you did not.**
- At 30 days: [modes/benchmark.md](modes/benchmark.md) section 2.

---

## The four sentences

1. **Decide in one tool, build in another, and let `HANDOFF.md` carry the decisions.**
2. **Nothing gets built before G1.**
3. **Free checks before paid ones, always.**
4. **Review in a session that did not build it.**
