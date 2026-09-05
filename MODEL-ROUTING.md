# MODEL ROUTING

Which tool does which job, and how to not burn your subscription limits doing it.

**Provider-neutrality rule:** this file routes by *capability class*, never by brand. The capability classes are stable; the products filling them are not. When a product changes, you edit the one mapping table in section 3 and nothing else in the Ariadne changes.

Related: [adapters/](adapters/) for tool-specific mechanics · [BUDGET-POLICY.md](BUDGET-POLICY.md) for cost.

---

## 1. Capability classes

Route work to a *class* first. This is the layer that does not change.

| Class | Code | What it is good at | What it costs you |
|---|---|---|---|
| **Deep reasoning** | `R1` | Strategy, grilling, architecture, design critique, evaluation, ambiguity | Expensive. Highest-value per token. |
| **Fast implementation** | `R2` | Writing code against a clear spec, refactors, boilerplate, tests | Cheap. Highest-volume. |
| **Long-context reading** | `R3` | Reading a whole codebase, summarising, finding things | Medium. Context-hungry. |
| **Browser / visual** | `R4` | Loading a page, screenshots, DOM, console, interaction QA | Cheap per action, slow in wall-clock |
| **Generative visual** | `R5` | Images, textures, logo concepts, moodboards | Varies. Often the only paid-per-use thing. |
| **Local / free** | `R6` | Build, typecheck, lint, git, file ops, Playwright, Lighthouse | Free. Always prefer. |

**The single most important routing rule in this system:** anything in `R6` must never be done by `R1`. Do not ask a reasoning model whether the build passes. Run the build.

---

## 2. Stage-to-class routing

| Stage | Class | Why |
|---|---|---|
| S0 Route | `R1` (brief) | One decision, high consequence, tiny context |
| S1 Discover / grill | `R1` | Ambiguity resolution is the whole job |
| S2 Research | `R1` + `R4` | Judgement about sources, browser to fetch them |
| S3 Direct (design) | `R1` + `R5` | Thesis is reasoning; moodboards are generative |
| S3 Direct (architecture) | `R1` | Decisions are expensive to reverse |
| S4 Build | `R2` | Spec exists; execution is the job |
| S4 Build (novel interaction) | `R2` escalating to `R1` | Escalate only when `R2` visibly flails |
| S5 Verify (mechanical) | `R6` then `R4` | Free checks first, browser second |
| S5 Verify (judgement) | `R1` | Taste is not mechanisable |
| S6 Ship | `R6` | Git and deploy are commands, not reasoning |
| S6 Retrospective | `R1` (brief) | Small context, real judgement |

---

## 3. Product mapping

**This is the only table to edit when your tooling changes.** Reflects the stack you described. Verify against [BUDGET-POLICY.md](BUDGET-POLICY.md) before relying on plan details.

| Class | Primary | Fallback | Notes |
|---|---|---|---|
| `R1` Deep reasoning | ChatGPT Plus / Codex | Claude Code | Your orchestrator. Keep context small here. |
| `R2` Fast implementation | Cursor | Claude Code | Your daily driver. Most hours live here. |
| `R3` Long-context reading | Cursor (codebase indexing) | Claude Code | Prefer the indexed tool; do not paste files into `R1`. |
| `R4` Browser / visual | Cursor browser tools or Claude Code browser | Playwright script (`R6`) | Playwright is free and repeatable. Prefer it for anything you will run twice. |
| `R5` Generative visual | Image tooling available in your subscription | Hand-made CSS/SVG | Often skippable. See section 7. |
| `R6` Local / free | Terminal | none needed | pnpm, git, playwright, lighthouse |

### Role separation in one line each

- **Codex (`R1`)** — decides. Strategy, grilling, design direction, architecture, evaluation, retrospectives. It may retain a bounded high-reasoning implementation/debugging split named in `HANDOFF.md`; it does not absorb routine build volume.
- **Cursor (`R2`/`R3`/`R4`)** — builds. Implements the handoff, refactors, runs the browser, fixes QA findings. Reads documents. Writes most code.
- **Claude Code (`R2` fallback, `R4`)** — accepts the same S4B transport
  contract and can handle agentic multi-file work in a terminal. Transport
  compatibility is implemented; live implementation equivalence remains
  unverified. See [adapters/claude-code.md](adapters/claude-code.md).

If any one of these disappears tomorrow, the other two absorb its classes and the system still runs. That is the test of provider-neutrality, and it is the reason no Ariadne document outside [adapters/](adapters/) names a product.

### Runtime routing record and preflight

S4A records the decision in `HANDOFF.md`: capability class, provider or
orchestrator retention, model when known, effort, workload, split, and reason.
The stable decision is the capability requirement; a product name is a runtime
mapping, not a design decision.

Immediately before external S4B work, the runtime reads that record and checks
observable provider availability and quota. It records one of four evidence
states:

- **verified** — availability and sufficient usage were explicitly confirmed;
- **reasonably assumed** — a bounded workload has no known blocking signal;
- **human check required** — a large handoff has unknown availability or quota;
- **blocked** — the provider is unavailable, usage is insufficient, or limited
  availability cannot safely carry one large task.

If implementation stays with the orchestrator, external preflight is recorded
as not required. A blocked or human-check-required result cannot produce the
external build handoff. Change the provider mapping, split, or effort in the
handoff; do not weaken the capability class merely because a product is limited.

---

## 4. When to escalate to deep reasoning

Escalate to `R1` only on these signals:

- The same bug has survived two `R2` fix attempts.
- A decision is expensive to reverse (data model, routing structure, design thesis).
- Two requirements genuinely conflict.
- Output is passing tests but feels wrong and you cannot say why.
- You are about to spend more than a day on an approach.

Do **not** escalate for: syntax, a failing type, a CSS bug, a library's API, writing a test, or "make this nicer" without a stated axis of nicer.

## 5. When to stay on fast/cheap

Stay on `R2` for: implementing an approved spec, all CRUD, styling to a locked token set, tests, refactors, renames, migrations, copy edits, and every fix whose cause is already known.

Roughly 80% of hours on a healthy project should be `R2`. If you are spending most of your time in `R1`, you are either under-specifying at S3 or using a reasoning model as a text editor.

## 6. When to use a browser agent

Use `R4` when: verifying something rendered, catching console errors, checking responsive behaviour, testing an interaction, capturing screenshots for G3, or reviewing a Vercel preview.

Do **not** use `R4` for: reading source (that is `R3`), anything a Playwright script already covers, or "checking if it works" when the production build has not been run yet.

**Escalation ladder, cheapest first:** production build to typecheck to Playwright to browser agent to human eyes. Do not skip rungs upward.

## 7. When to use a generative visual skill

Use `R5` when the design *depends* on imagery that does not exist and cannot be substituted: texture, a hero image, a logo concept, a moodboard for G1.

Do not use `R5` when: a typographic solution works (usually), the client has real photography coming, or the image would be decorative. Generated placeholder imagery is on the anti-pattern list in [DESIGN-TASTE.md](DESIGN-TASTE.md).

Prefer, in order: existing real assets, typographic/CSS/SVG solutions, generated assets, stock. Stock imagery is last because it is the fastest route to generic.

---

## 8. Conserving subscription usage

The real constraint is not money, it is your monthly limits. These are ordered by impact.

1. **Never paste a codebase into `R1`.** Paste the interface, the error, and the constraint. Context is what exhausts limits.
2. **Documents are the compression layer.** `HANDOFF.md` exists so `R2` never has to re-derive what `R1` already decided. Re-deriving context is the single biggest waste in this system.
3. **Run free checks first.** Every `R6` check that catches a bug is a `R1`/`R2` round trip you did not spend.
4. **One question batch, not five conversations.** [ROUTER.md](ROUTER.md) 4.3.
5. **Start a new session per stage.** A single 200-message thread carries S1's context into S5 and pays for it every message.
6. **Do not use `R1` to write code it will then ask `R2` to rewrite.** Pick one.
7. **Cache decisions in files, not in chat history.** Chat is not durable and is re-sent every turn.
8. **Kill dead threads.** If a conversation has drifted, restart it with a fresh summary rather than continuing to pay for the drift.

### What should never touch a high-cost model

Build output. Test output. Lint errors with an obvious fix. File listings. Git operations. Dependency installs. Screenshots you have not looked at yourself. Formatting. Renames. "Is this working?" when a command answers it.

---

## 9. Recovering when a model hits its limit

| Situation | Action |
|---|---|
| `R1` exhausted mid-project | Stop deciding. Switch to `R2` work already specified in `TASKS.md`. Never let `R2` invent direction because `R1` is unavailable. |
| `R2` exhausted | Move to `R6` work: tests, build fixes, cleanup, documentation. Or hand the same `HANDOFF.md` to the fallback runner. |
| Both exhausted | S5 mechanical QA, retrospectives, and reference research are all human-doable. |
| Exhausted at S3 with an unapproved thesis | **Do not build.** Waiting is cheaper than rebuilding. |

**The recovery rule:** when a class is unavailable, do work from a *different class*, never the same work at a lower class. Downgrading direction work to a fast model is how projects go generic without anyone noticing.

---

## 10. Keeping this provider-neutral

Enforced by four rules:

1. Ariadne documents outside [adapters/](adapters/) refer to `R1`-`R6` and role names, never product names. Section 3 is the single exception, by design.
2. Every adapter implements the same contract: read `HANDOFF.md`, respect `AGENTS.md`, honour gates, report in the `QA.md` format.
3. Handoffs are plain markdown files, readable by any tool and by you.
4. Nothing depends on a proprietary feature. If a tool offers a shortcut, it goes in that tool's adapter as an *optimisation*, never as a requirement.

**The portability test**, run at each retrospective: *could a new tool replace one of mine by writing one adapter file?* If the answer is no, a product detail has leaked out of `adapters/` and must be moved back.
