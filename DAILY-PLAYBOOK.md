# DAILY PLAYBOOK

What to open, in what order, for the work in front of you.

Setup: [GETTING-STARTED.md](GETTING-STARTED.md). Detail: [WORKFLOW.md](WORKFLOW.md).

---

## Which tool do I open first?

| Situation | Open | Why |
|---|---|---|
| New idea, nothing exists | **Codex**, invoke `$builderos` | It starts, routes, and records the run |
| Returning to a project | **Codex**, invoke `$builderos` | It discovers the run and resumes from durable state |
| Existing project, no Builder OS run | **Codex**, invoke `$builderos` and ask to adopt it | It preserves the repository and starts a non-destructive intake |
| Builder OS requests external implementation | **The named build tool** | The complete verified handoff is ready |
| Mid-build, a decision came up | Depends — see below | |
| A bug | **Build tool** | Bugs are `R2` work |
| Same bug, twice failed | Reasoning tool | Escalation signal |
| Something needs checking | **Terminal** | Free, definitive, instant |
| Reviewing finished work | Reasoning tool, **fresh session** | Independence |

**Default: if you are unsure, invoke Builder OS in the project.** It reads the
state instead of making you infer it. Most implementation hours can still
belong in the build tool without making the operator choose a stage manually.

---

## What Builder OS handles

| Human-facing moment | Builder OS action |
|---|---|---|
| “I have an idea” | Creates/fetches the run, routes it, asks one batched question set, writes the brief |
| Facts block direction | Prepares focused research with only the blocking questions |
| Direction is ready | Presents G1 and waits for your creative decision |
| Direction is approved | Produces the implementation handoff and reads its provider recommendation |
| External build is appropriate | Checks provider availability/quota and gives you one verified packet |
| Build returns | Validates the structured return and resumes without old chat history |
| Mechanical QA is complete | Creates the isolated independent-review handoff |
| Review is recorded | Presents G3; shipping still requires explicit G4 |

Prompts, packet IDs, manifests, hashes, parent records, evidence paths, and stage
names are debugging details. Builder OS manages them. The low-level commands in
[adapters/codex.md](adapters/codex.md) remain available for recovery.

## By situation

### "I have an idea"

1. Invoke `$builderos` in Codex.
2. Describe the idea and project directory normally.
3. Answer the batched material questions; Builder OS prepares the next valid work.

Do not start implementation or pick a framework. The repository stays empty until S1 writes its project documents.

### "I know what I'm building, I want to start"

Check: is `HANDOFF.md` written and was **G1** approved?

- **Yes** → open the build tool, start task 1 from `TASKS.md`.
- **No** → you are not ready. Go to S3. Building before direction is locked is the thing this system exists to prevent, and "the deadline is tight" is exactly when it happens.

### "I already have a project"

Invoke `$builderos` from that repository and say you want to adopt it. Builder
OS uses the existing source as read-only intake context, preserves every file,
and writes no implementation during S1. Existing Builder OS entry documents are
never overwritten: if `PROJECT.md` or `AGENTS.md` is present, the runtime asks
you to resume or migrate deliberately.

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

1. The implementation provider runs the mechanical checklist ([QA-POLICY.md](QA-POLICY.md) section 3) and returns its structured handoff.
2. Capture screenshots — **and look at them yourself**.
3. Give Builder OS's isolated review handoff to a **fresh independent session**.
4. Present G3.
5. On approval: G4 to ship.
6. Fifteen minutes on `RETROSPECTIVE.md`. Record proposals; edit Builder OS only after human approval, then log the approved change in [CHANGELOG.md](CHANGELOG.md).

### "I want to write a post"

[prompts/content-system.md](prompts/content-system.md), prompt 2. Start from something that actually happened — your `RETROSPECTIVE.md` files are the best source you have.

If there is no only-you element, do not post it.

### "I want feedback on my portfolio"

[prompts/portfolio-evaluation.md](prompts/portfolio-evaluation.md), in a fresh session, against the deployed URL. Expect it to hurt.

### "I was interrupted"

Invoke `$builderos` from the project again. It discovers the matching run,
verifies the current packet and evidence, and resumes from the last valid
boundary. If more than one history claims the project, it stops and asks which
one is authoritative rather than guessing.

The human-readable history is `OPERATIONS.md` in the run directory. Use it to
see what happened, why, what changed, what was verified, and the next action.

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
| Reasoning (`R1`) | Stop deciding. Do already-specified build work. **Never let the build tool invent direction.** |
| Build (`R2`) | Tests, build fixes, cleanup, docs — or hand the same `HANDOFF.md` to the fallback runner |
| Both | Mechanical QA, retrospectives, reference research. All human-doable. |
| At S3 with no approved thesis | **Wait.** Waiting is cheaper than rebuilding. |

**The rule:** when a class is unavailable, do work from a *different class* — never the same work at a lower class ([MODEL-ROUTING.md](MODEL-ROUTING.md) section 9).

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
- At 30 days: [CHANGELOG.md](CHANGELOG.md) "30-day check".

---

## The four sentences

1. **Decide in one tool, build in another, and let `HANDOFF.md` carry the decisions.**
2. **Nothing gets built before G1.**
3. **Free checks before paid ones, always.**
4. **Review in a session that did not build it.**
