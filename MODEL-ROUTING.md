# MODEL ROUTING

Which tool does which job, and how to not burn your subscription limits doing it.

**Provider-neutrality rule:** this file routes by *capability class*, never by brand. The capability classes are stable; the products filling them are not. When a product changes, you edit the one mapping table in section 3 and nothing else in Ariadne changes.

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

**This is the runtime table to edit when your tooling changes.** Reflects the current model landscape (dated 2026-09-05; verify before relying on plan details).

| Class | Primary | Fallback | Notes |
|---|---|---|---|
| `R1` Deep reasoning | ChatGPT Plus / Codex (GPT-5.6 Sol / Terra / Luna, GPT-6 Astra) | Claude Code | Your orchestrator. Match model tier and reasoning effort to the task. |
| `R2` Fast implementation | Cursor (implementation models, including Grok where available) | Claude Code | Your daily driver. Most hours live here. Model chosen inside adapter. |
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

### Runtime model landscape and freshness

Model capabilities, quotas, and pricing are runtime mappings that drift over time.
Treat all model claims as dated observations (`reported` or `unverified` until directly checked), not immutable system rules.

- **GPT-5.6 Luna (`R1`)** — inexpensive, bounded reasoning. Best for straightforward synthesis, low ambiguity, high reversibility, and tasks where extra intelligence is unlikely to materially improve the result. Supports low and medium effort.
- **GPT-5.6 Terra (`R1`)** — balanced middle ground where available. Handles normal analysis and planning. Supports low, medium, and high effort.
- **GPT-5.6 Sol (`R1`)** — difficult, consequential, ambiguous, or high-value reasoning. Design thesis, architecture choices, tricky trade-offs, difficult debugging, and irreversible decisions. Supports low, medium, and high effort.
- **GPT-6 Astra (`R1`)** — exceptional, novel, or high-complexity reasoning where deep capability is justified. Unprecedented constraints and novel domain modeling. Supports low, medium, high, and xhigh/max effort.
- **Cursor implementation models (`R2`)** — execution runtime inside the Cursor adapter. Multiple models may be exposed (including Grok where available for rapid frontend iteration). Kept runtime-aware; no temporary model is treated as permanently best.
- **Claude Code (`R1` / `R2` fallback)** — terminal agentic execution when primary subscriptions hit usage limits.

### Multi-dimensional model selection

Ariadne evaluates tasks using a five-step abstraction:

```
TASK → CAPABILITY CLASS → MODEL/PROVIDER → EFFORT → SESSION STRATEGY
```

Within `R1`, model selection is never a simplistic "easy = Luna, hard = Astra" heuristic. The router reads nine concrete dimensions:

1. **Task complexity:** bounded/modular vs multi-faceted vs novel/unprecedented.
2. **Ambiguity:** well-specified inputs vs underspecified or conflicting requirements.
3. **Consequence of error:** minor localized flaw vs core architectural breakdown.
4. **Reversibility:** cheap `git revert` vs expensive data/thesis rewrite.
5. **Visual and creative importance:** routine utility vs core brand differentiation.
6. **Context requirements:** compact summary vs dense multi-file constraints.
7. **Expected iterations:** one-pass synthesis vs tight multi-turn debugging. Operator judgement; the router accepts this signal but does not yet act on it.
8. **Primary nature:** pure reasoning (`R1`) vs execution (`R2`) vs free checks (`R6`).
9. **Reliable threshold:** whether a cheaper tier can solve it with high confidence.

**Governing rule:** quality per successful task. The cheapest model and capability that can reliably solve the task must win. Do not spend Sol or Astra on tasks Luna or `R2` can handle; equally, do not under-route to a cheap model when failure carries high recovery costs.

#### The two gates

Those dimensions are not summed into a score. Inside `R1` they collapse into two ordinal gates:

- **Difficulty** — how hard is this to get right? Driven by complexity, ambiguity, and context requirements.
- **Stakes** — how expensive is it to be wrong? Driven by consequence, reversibility, and visual or creative value.

**Escalation requires both gates, never one alone.** The reasoning behind that rule:

- A hard problem whose answer is cheap to check and cheap to undo is better retried on a smaller model than escalated. Paying for capability buys nothing that a second attempt would not.
- An easy problem with serious downside needs care and verification, not a larger model. The expensive part is the review, not the token budget.
- Only when a problem is both hard to get right and expensive to get wrong does extra capability pay for itself.

The resulting table is the whole `R1` policy:

| Difficulty \ Stakes | low | medium | high |
|---|---|---|---|
| **low** | Luna | Luna | Terra |
| **medium** | Luna | Terra | Sol |
| **high** | Terra | Sol | Sol |
| **exceptional** | Terra | Sol | Astra |

Two consequences worth stating plainly, because both were previously wrong:

- **`novel` alone does not buy Astra.** Novelty is an operator's assessment of a task, not evidence that the largest model is required. Novel work that is cheap to retry routes to Terra.
- **One isolated `high` label does not buy Sol.** A single elevated dimension moves the recommendation exactly one tier, and no further.

These tier boundaries are argued from cost reasoning, not measured against outcomes. Nothing here establishes that Luna actually matches Sol on the work routed to it; treat the table as a defensible default you are expected to override when you know better.

### Reasoning effort selection framework

Effort is reasoned about independently from model choice. Ariadne assigns effort on a four-tier scale:

- **low** — bounded or straightforward reasoning, mechanical decomposition, clear inputs.
- **medium** — normal analysis, standard planning, balanced trade-off evaluation.
- **high** — substantial ambiguity, architecture definition, design judgement, or difficult debugging.
- **xhigh / max** — genuinely difficult, novel, or high-consequence work requiring deep exploration.

Effort is derived from the same two gates as the model, by a separate rule, so a stronger model does not automatically imply deeper reasoning. Sol runs at high; Terra runs anywhere from medium to high; Luna runs at low or medium.

Three rules govern effort:
1. **Model compatibility:** recommend only effort levels actually supported by the target model (e.g. Luna caps at medium; Sol supports low/medium/high; Astra supports through max).
2. **Anti-waste:** do not recommend maximum effort merely because it is available. A high-tier model assigned to a clear task should run at low or medium effort.
3. **Cheap retry damping:** when being wrong is both cheap to detect and cheap to undo, deep deliberation is not worth buying either, so effort is held at medium however hard the problem looks.

The router itself never emits `max`. That level remains an operator override recorded by hand in `HANDOFF.md`.

### Operator-facing recommendation format

When surfacing routing advice to the operator, Ariadne formats the recommendation as a concise block:

```
RECOMMENDED
- Capability: <R1–R6 class and description>
- Model: <concrete model or runtime tool>
- Effort: <low | medium | high | xhigh | max>
- Session: <Continue | New>
- Why: <short reason explaining the recommendation>
- Model landscape: dated <date>, <unverified | operator-reported> (check before relying on it)
```

The final line is the freshness marker. `unverified` means the model name came from the dated table in section 3 and nobody has checked it since; `operator-reported` means the operator named the runtime model themselves. The marker is never `verified`, because Ariadne performs no live capability lookup. Recommendations that name no vendor model at all omit the line.

`python scripts/ariadne.py route --help` lists the flags. The CLI exposes only per-task judgements a human can reasonably make about the work in front of them. Provider and quota state come from the preflight flags; runtime model identity comes from `--runtime-model`; expected iterations is accepted by the library function but does not currently change any decision.

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
5. **Context-aware session strategy.** Do not restart chats mechanically at every stage boundary. Restart when moving across major objectives, when independent judgement is required (such as S5 review), when stale context introduces noise, or when separating implementation from strategy. Continue when the same objective is active and context continuity materially helps.
6. **Do not use `R1` to write code it will then ask `R2` to rewrite.** Pick one.
7. **Cache decisions in files, not in chat history.** Chat is not durable and is re-sent every turn.
8. **Kill dead threads.** If a conversation has drifted, restart it with a fresh summary rather than continuing to pay for the drift.

### Context-aware session strategy

Session boundaries exist to manage context value versus independence, not as an inflexible ritual.

Recommend **CONTINUE** when:
- The same objective remains active.
- Existing context remains directly relevant and useful.
- Work is ongoing within the same artifact or phase (e.g. iterating on S3 design direction or refining S4 implementation).
- Continuity materially reduces re-prompting and re-explanation friction.

Recommend **NEW SESSION** when:
- Changing projects.
- Changing major objectives or phases (e.g. transitioning from strategy to build, or from build to verification).
- Independent judgement is required (specifically S5 review: the reviewer must not inherit the author's internal reasoning or justifications).
- Stale assumptions or abandoned ideas could bias subsequent work.
- Accumulated conversation context has drifted, becoming noisy or irrelevant.
- Implementation must be isolated from strategic deliberations.
- The value of fresh, clean context clearly exceeds the value of continuity.

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
