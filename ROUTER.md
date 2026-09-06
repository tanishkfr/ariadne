# ROUTER

Turn a request into an interpretation, and an interpretation into a mode. The router dispatches; it does not design, code, or research.

Then: [WORKFLOW.md](WORKFLOW.md) for stages, gates, roles, and autonomy.

**The router does not match keywords.** It builds a small interpretation of what you asked for, then routes from that. Keyword matching confidently produces the wrong workflow whenever your intent differs from your literal words, which is most of the time.

---

## Rule index

Referenced by ID from everywhere else in the system. Change the rule here, not the copies.

| ID | Rule | Section |
|---|---|---|
| **R-ACT-1** | Action priority — the stated action outranks every other signal | 3.3 |
| **R-REF-1** | A reference modifies the work; it never selects the mode | 3.3 |
| **R-REF-2** | A replication request routes to CREATE; originality is a design conversation, not a refusal | 3.3 |
| **R-XFM-1** | Transformation is a creation action; route by the target | 3.3 |
| **R-DEST-1** | Destination is not the object; an unresolved object forces LOW | 3.3 |
| **R-INT-1** | Restart is an interrupt, not a mode | 11 |
| **R-PAT-1** | Accepted patterns are judged by intentionality, not quantity | 10 |
| **R-CONF-1** | Confidence is derived from what is unresolved | 3.5 |
| **R-ASK-1** | Ask the fewest highest-impact questions | 4 |

---

## 1. Vocabulary

| Term | Meaning |
|---|---|
| **Frame** | The router's interpretation of a request. Ten slots, section 3.1. |
| **Mode** | The kind of project. One of 5. |
| **Stage** | S0-S6. [WORKFLOW.md](WORKFLOW.md). |
| **Skill** | A method in [skills/](skills/). |
| **Role** | One of 5 jobs. [WORKFLOW.md](WORKFLOW.md). |
| **Gate** | A named human approval. G1-G5. |

## 2. The five modes

| Mode | The work is |
|---|---|
| [Client or portfolio](modes/client-or-portfolio.md) | A site whose job is reputation — yours or someone else's |
| [Product app](modes/product-app.md) | Something with state that outlives the session |
| [Game / experiment](modes/game-experiment.md) | A playable or experimental piece, any medium |
| [Content system](modes/content-system.md) | Writing for an audience, with a learning loop |
| [Audit / review](modes/audit-review.md) | Judgement of something that already exists |

### Writing intent

When `OBJECT` is writing, the router records one writing intent before the
content method begins. This is a method choice inside the existing workflow,
not a sixth mode or a second router. Use [WRITING-POLICY.md](WRITING-POLICY.md)
for the method and review lens.

| Intent | Signal | Method owner |
|---|---|---|
| `CREATIVE` | Original literary, narrative or imaginative artifact | `WRITING-POLICY.md` creative method |
| `ACADEMIC` | Assignment, argument or source-based analysis | `WRITING-POLICY.md` academic method |
| `SCIENTIFIC` | Scientific, technical or evidence-reporting document | `WRITING-POLICY.md` scientific method |
| `HUMAN-DRAFT TRANSFORMATION` | User supplies a draft and asks to improve, revise or transform it | `WRITING-POLICY.md` transformation contract |
| `SOCIAL` | Posts, threads, distribution strategy or supplied social results | `CONTENT-SYSTEM.md` and `skills/social-strategy.md` only |

Do not infer SOCIAL from the fact that writing has an audience. Do not apply
social hook, anti-voice or platform rules to academic, scientific or creative
writing. If a request says "improve my writing," preserve the draft by default
and resolve the requested intervention before replacing its voice.

Modes are **workflows**, not subject matter. "A dashboard" is not a mode; *building a stateful thing* is.

---

## 3. Interpretation

### 3.1 The frame

Fill these ten slots before deciding anything. Slots may be `UNRESOLVED` — that is information, not a failure.

| Slot | Values / meaning |
|---|---|
| `ACTION` | CREATE · TRANSFORM · ANALYZE · RESTART · EXTEND |
| `OBJECT` | What is produced or examined. **May be UNRESOLVED.** |
| `OUTCOME` | What should be true when it is done |
| `DESTINATION` | Where the output lives, or who sees it |
| `ARTIFACT` | none · **subject** · **source** · **reference** |
| `REFERENCE` | none · inspiration · analysis-target · replication-request |
| `TRANSFORM` | none · medium · platform · direction · scope |
| `CONSTRAINTS` | Stated limits — budget, stack, time, tools |
| `UNRESOLVED` | What is unknown, and whether it changes the workflow |
| `CONFIDENCE` | Derived from `UNRESOLVED`. **Never from how many words matched.** |

### 3.2 Filling the slots

**ACTION** — what does the user want done? These are calibration samples, **not a lookup table.**

| Action | Reads like |
|---|---|
| `CREATE` | build, make, design, write, start, "I want a…" |
| `TRANSFORM` | turn into, convert, adapt, port, remake, reinterpret, translate into, redesign, rebuild, restyle |
| `ANALYZE` | review, critique, audit, roast, break down, "what should I learn from", "why does X work" |
| `RESTART` | scrap, start over, rethink, abandon, forget this direction, "isn't working", "new direction" |
| `EXTEND` | add, fix, finish, continue — on work already in this project |

**If the verb is not listed, do not guess from nouns. Ask: what would the user do with the output?** A thing to use is CREATE. A judgement to read is ANALYZE. An existing thing becoming a different thing is TRANSFORM. That question resolves verbs no list will ever contain.

**OBJECT** — what is the thing? Mark it `UNRESOLVED` when the request names a category but not a thing: *"something"*, *"a piece"*, *"an idea"*, *"this"* with no antecedent. **This is the slot to be most honest about.**

**ARTIFACT** — if something already exists, which role does it play?

| Role | Meaning | Example |
|---|---|---|
| `subject` | The thing being judged | "review this site" |
| `source` | The input being transformed | "turn this into an installation" |
| `reference` | An exemplar to learn from | "build something like this" |

**Presence of an artifact tells you nothing on its own.** Its role is what matters, and the role comes from the action.

### 3.3 Routing rules

**R-ACT-1 — Action priority.** The stated action determines the workflow. No other slot may override it. **Only `ANALYZE` routes to audit-review.**

A request to *create* never becomes a review because a reference was mentioned. A request to *review* never becomes a build because the subject happens to be buildable.

**R-REF-1 — Reference handling.** A reference is a **modifier of the work, never a selector of the mode.** It flows to [reference-analysis](skills/reference-analysis.md) at S2/S3 and changes the design direction. It does not change what is being built.

| Request | ACTION | ARTIFACT | Routes to |
|---|---|---|---|
| "Build something like Burocratik" | CREATE | reference | build workflow + reference analysis |
| "Analyze Burocratik" | ANALYZE | subject | audit-review |
| "What should I learn from Burocratik?" | ANALYZE | subject | audit-review |
| "Use Burocratik as a reference for a new site" | CREATE | reference | build workflow + reference analysis |

**R-REF-2 — Replication requests.** If the request is to copy a reference outright, route to CREATE and do not refuse. Surface the originality constraint at S3, where [DESIGN-TASTE.md](DESIGN-TASTE.md) section 7 handles it. Refusing at the router is a mode error; this is a design conversation.

**R-XFM-1 — Transformation.** `TRANSFORM` is a creation action. **Route by the target, never by the source.**

"Turn this website into an installation" is an installation project that happens to start from a website. The source is an input; the target is the work.

**R-DEST-1 — Destination is not the object.** `DESTINATION` says where the output lives. `OBJECT` says what it is. **Mode comes from OBJECT.**

If `OBJECT` is `UNRESOLVED`, confidence is **LOW regardless of how clear DESTINATION is.** This is mechanical and cannot be overridden.

| Request | ACTION | OBJECT | DESTINATION | Result |
|---|---|---|---|---|
| "Create my portfolio" | CREATE | portfolio site | self | client-or-portfolio, HIGH |
| "Create something for my portfolio" | CREATE | **UNRESOLVED** | portfolio | **LOW — ask what the thing is** |
| "Create a game for my portfolio" | CREATE | game | portfolio | game-experiment, HIGH |
| "Review my portfolio" | ANALYZE | portfolio site | — | audit-review, HIGH |
| "Redesign my portfolio" | TRANSFORM (direction) | portfolio site | self | client-or-portfolio, HIGH |

Same noun in all five. Action and object separate them; no keyword exception is involved.

### 3.4 Mode from OBJECT

Reached only once `ACTION` is CREATE or TRANSFORM **and** `OBJECT` is resolved.

**Two actions never reach this table:**

- **`EXTEND` inherits the current project's mode.** Adding a leaderboard to a game does not make it a product app; adding a contact page does not re-derive a mode. An extension only re-routes if it triggers 3.6 — and that is a scope change you decide, not a silent reclassification.
- **`ANALYZE` with no `subject`** is a research question, not a project. "Which CMS should I use?" routes to [RESEARCH-POLICY.md](RESEARCH-POLICY.md) and gets answered — it does not become audit-review and does not open a project. Audit-review needs something concrete to judge.

| The object is | Mode |
|---|---|
| A site whose job is reputation — yours or a client's | client-or-portfolio |
| Something whose **state outlives the session** — accounts, saved data, returning users | product-app |
| A playable, experimental, or exhibited piece — **any medium, any input device** | game-experiment |
| Writing for an audience | content-system, with a recorded writing intent |

**State outliving the session wins over appearance.** A "game" where you log in to save a high score is a product-app. That is a property of the object, not a keyword.

**If nothing fits cleanly, pick the mode whose workflow is closest and say so.** An interactive installation built in web tech uses game-experiment because that is the closest workflow — the mode does not assume a desktop browser, and its input/display question establishes the real target. Do not invent a mode.

### 3.5 Confidence — R-CONF-1

Derived from `UNRESOLVED`. **Never a function of how many words matched.**

| Level | Means | Behaviour |
|---|---|---|
| **HIGH** | Action clear · object clear · mode clear · nothing material unresolved | Proceed |
| **MEDIUM** | Mode is clear, but one interpretation is unresolved and it changes the workflow | Proceed, name the assumption, ask **one** targeted question |
| **LOW** | Action or object ambiguous, or two materially different workflows are plausible | **Stop. Ask before committing.** |

**The rule that governs the others:**

> **A confidently wrong interpretation is worse than a low-confidence clarification.**

Do not optimise for asking fewer questions. Optimise for asking only questions whose answer changes the work. An `UNRESOLVED` object is always material — it decides the mode.

### 3.6 Changing mode mid-project

If evidence contradicts the mode — an experiment grows accounts — re-fire the router: say the mode changed and why · list which documents survive · re-run the gate schedule.

A mode change is a scope change and you decide. Do not quietly upgrade quality bars.

---

## 4. Questions — R-ASK-1

**Ask the smallest number of highest-impact questions needed to resolve the ambiguity.**

Before asking: *if the answer were A instead of B, would a different file get written?* If no — assume, log, move on.

- Prefer **one question with a useful set of choices** over several open ones.
- Prefer an **explicit assumption** when the decision is low-impact.
- Prefer **proceeding** when the ambiguity does not affect the workflow.
- **Never ask a question just because the router could.**

Cap: five. Batched, numbered, each with a proposed default so the reply can be "all defaults".

Never ask: which framework · whether it should be responsive or accessible · whether quality matters · anything already stated.

**When the object is UNRESOLVED**, the one question that matters is *what kind of thing is this?* — offered as concrete options drawn from the modes, not as an open prompt. Per-mode question sets live in each [mode file](modes/).

## 5. Default assumptions

Assume freely, log everything in `PROJECT.md` phrased so it can be contradicted in one line.

| Area | Default |
|---|---|
| Stack | Next.js + TypeScript strict + pnpm |
| Hosting | Vercel, preview per branch |
| Backend / CMS / auth / database / analytics | **None** until a requirement forces one |
| Styling | CSS custom properties. Tailwind only for genuine utility churn. |
| Motion | Motion.dev for component motion; GSAP when a timeline is central |
| Testing | Playwright; production build must pass |
| Budget | Subscriptions only, no pay-per-token |

**Never assume:** the design thesis · brand rules · what is true about you · whether something may be published · a real deadline · **what the object is when it is UNRESOLVED.**

`CONSTRAINTS` from the frame carry into `PROJECT.md` verbatim and survive every later stage. A constraint stated once is never re-asked and never quietly dropped.

---

## 6. Documents

**Required in every build mode: `PROJECT.md`, `DESIGN.md`, `HANDOFF.md`, `QA.md`.** Four.

Everything else is conditional. Creating a document nobody will read is worse than not creating it — it manufactures the appearance of process.

| Document | Create when |
|---|---|
| `ARCHITECTURE.md` | More than ~10 components, or any data model |
| `TASKS.md` | More than ~5 tasks, or more than one work session |
| `ASSETS.md` | The design depends on assets that do not yet exist |
| `RESEARCH.md` | A fact about the world blocks a decision |
| `AGENTS.md` | An AI tool will build it (almost always) |
| `RETROSPECTIVE.md` | The project shipped, or taught you something |
| `CONTENT-LEARNINGS.md` | SOCIAL intent only; it is the social learning loop |

| Mode | Required | Usually also |
|---|---|---|
| Client or portfolio | the four | AGENTS, ASSETS, RETROSPECTIVE |
| Product app | the four + **ARCHITECTURE** | TASKS, AGENTS, RETROSPECTIVE |
| Game / experiment | PROJECT, DESIGN | — |
| Content / writing system | PROJECT, intent-specific method output | SOCIAL adds CONTENT-LEARNINGS; RESEARCH only when a fact blocks a decision |
| Audit / review | QA only | — |

## 7. Skills

| Mode | Skills |
|---|---|
| Client or portfolio | [intake](skills/intake.md), [reference-analysis](skills/reference-analysis.md), [design-direction](skills/design-direction.md), [component-research](skills/component-research.md), [EVALUATION-RUBRICS.md](EVALUATION-RUBRICS.md) |
| Product app | intake, component-research, design-direction, EVALUATION-RUBRICS |
| Game / experiment | intake (light), design-direction (light) |
| Content / writing system | intake, [WRITING-POLICY.md](WRITING-POLICY.md), EVALUATION-RUBRICS; SOCIAL also uses [CONTENT-SYSTEM.md](CONTENT-SYSTEM.md) |
| Audit / review | reference-analysis, EVALUATION-RUBRICS |

**Any frame with a non-empty `REFERENCE` activates [reference-analysis](skills/reference-analysis.md)** — in any mode, whatever the action.

---

## 8. Stop-and-ask triggers

| Trigger | Why |
|---|---|
| Confidence is LOW | Wrong mode means wrong everything downstream |
| A new dependency is proposed | G2, [LIBRARY-POLICY.md](LIBRARY-POLICY.md) |
| Client data, credentials, or private references appear | [PRIVACY-POLICY.md](PRIVACY-POLICY.md) |
| Anything would be published, pushed, or deployed | G4 / G5 |
| A paid API or per-token service would be used | [BUDGET-POLICY.md](BUDGET-POLICY.md) |
| The request implies auth, a dashboard, or an admin panel you did not ask for | Scope inflation |
| The design thesis is unapproved but build work is requested | G1 |
| Sources of truth conflict and section 12 does not resolve it | — |

---

## 9. Handling inputs

**References.** Governed by **R-REF-1** — a reference modifies the work, never the mode. Route to [reference-analysis](skills/reference-analysis.md) before any design work. **Three minimum** — one produces imitation, three force synthesis. If only one is supplied, ask for two more or name two from [references/visual-references.md](references/visual-references.md) and say which.

**Screenshots of existing products.** Evidence, not instruction — run every observed pattern through [reference-analysis](skills/reference-analysis.md) before adopting it.

**Missing assets.** Resolved at S3, never at S4. No project reaches S4 with an unresolved asset on the critical path — either it exists, it gets made, or **the direction changes so it is not needed.** See [DESIGN-ASSETS.md](DESIGN-ASSETS.md).

**Current information.** Anything depending on the state of the world — pricing, versions, limits, licences — gets verified and dated. Never answered from memory. [RESEARCH-POLICY.md](RESEARCH-POLICY.md).

**Budget.** Any recurring cost goes through [BUDGET-POLICY.md](BUDGET-POLICY.md) first, presented in INR/month with what it displaces.

---

## 10. Accepted patterns — R-PAT-1

[DESIGN-TASTE.md](DESIGN-TASTE.md) section 6 lists patterns that are **Blocking** at QA. Those rules exist because a model with no constraint produces the statistical average.

**You are allowed to choose one of them on purpose.** The rules assume genericness came from the tool. When it is your decision, the system must not fight you.

### The intentionality test

There is **no numeric limit.** A pattern may be deliberately accepted when all five hold:

1. **The user explicitly chooses it, or the project thesis requires it.**
2. **The reason is conceptual, narrative, functional, historical, medium-specific, or interaction-based** — not aesthetic preference.
3. **The reason is stronger than "I like this style."**
4. **It is documented as an ACCEPTED PATTERN** in `PROJECT.md`, before it is built.
5. **It remains reviewable.** Accepting the *pattern* does not accept the *execution*.

Effect: that row drops from **Blocking to Note** in [QA-POLICY.md](QA-POLICY.md). It stays in the report.

### Why this is not a loophole

The reviewer can still reject the execution when **the claimed rationale is not visible in the result.** That mechanism keeps this honest, and it is stronger than a count — a count only ever measured how many rules you broke, never whether you meant it.

| Claim | Router response |
|---|---|
| "Use glassmorphism because I like glassmorphism" | **Challenge once.** Ask what it is doing. Preference is not a reason. |
| "Translucent glass panels because the interface is a fictional 2008 operating system and the material language is the narrative" | **Accept**, log it, and hold the build to that claim |
| "Card grid because the user monitors six live data streams and density is correct" | **Accept** |
| "A dashboard because it is a dashboard product" | **Challenge once** — what changes without the user watching? |

**If you challenge once and the user restates the preference, it is their project.** Log it as preference-based so the reviewer knows the rationale was never conceptual. Do not challenge twice, and do not block.

The Design director may argue against an acceptance. It may not override one.

---

## 11. Restart — R-INT-1

**Restart is an interrupt, not a mode.** It suspends the current stage; it does not change what is being built and it does not destroy work.

**Recognise it from the action, not from a phrase.** Any `ACTION = RESTART` fires this: *"start over"*, *"scrap this direction"*, *"the concept isn't working"*, *"let's rethink the whole thing"*, *"forget this"*, *"new direction"*, *"keep the research but abandon the visuals"*.

**You do not need to know this procedure exists.** The router recognises the intent and runs it.

### Procedure

1. **Freeze, do not delete.** The current direction stops being authoritative immediately. Nothing is overwritten or removed.
2. **Establish the layer.** Ask one question if it is not stated:

   | Layer | What restarts |
   |---|---|
   | Concept / thesis | The organising idea. `DESIGN.md` thesis and rejection list. |
   | Visual direction | Type, palette, layout, motion — the thesis survives |
   | Architecture | Structure and stack — the design survives |
   | Whole project | Back to S1. Scope was the problem; the direction was a symptom. |

3. **Preserve by default.** `RESEARCH.md`, references, assets, `PROJECT.md`, mechanical infrastructure, and the token *system* all survive. **Discard only what the user names.** Research and assets are never thrown away as a side effect.
4. **Retire the old direction as evidence.** Write down *why it failed* before writing the new one, into the new `DESIGN.md` under "What NOT to copy". Your own dead direction is a reference you must not repeat — this is the step that prevents restarting into the same place.
5. **Re-run only the necessary gate.** Concept or visual restart → G1. Architecture restart → the architecture half of S3. Whole project → S1.
6. **Log it** in `RETROSPECTIVE.md`. Two restarts on one project means S1 was under-specified, not that the direction was unlucky.

**Restarting is cheap at S3 and expensive at S5.** That asymmetry is the entire argument for G1.

---

## 12. Precedence

```
Project AGENTS.md → Project DESIGN.md → Project PROJECT.md
  → mode file → Ariadne core → global CLAUDE.md
```

If a conflict survives this chain, **stop and ask.** Do not average two instructions into a compromise neither party wanted.

---

## 13. Output — the Routing Block

```
ROUTING BLOCK
Action:       <CREATE | TRANSFORM | ANALYZE | RESTART | EXTEND>
Object:       <what, or UNRESOLVED>
Destination:  <where it lives, or unstated>
Artifact:     <none | subject | source | reference>
Constraints:  <stated limits, carried verbatim>
Unresolved:   <what is unknown, and whether it changes the workflow>

Mode:         <mode>  (confidence: HIGH | MEDIUM | LOW)
Questions:    <n, batched below — none if HIGH>
Assumptions:  <the 3-5 that matter>
Documents:    <the required four, plus any conditional ones and why>
Skills:       <which>
Gates ahead:  <G1 ... G5>
Budget:       <INR impact, or "none">
First action: <the single next thing>
```

**The frame is shown, not just the conclusion.** A wrong route is then visible in one line — you can see that `Object: UNRESOLVED` got filled in as a guess, or that a reference was read as a subject.

**First action is mandatory and must be one concrete step.** A Routing Block ending in "let me know how you'd like to proceed" has failed.

---

## 14. Known failure modes

| Failure | Countermeasure |
|---|---|
| Routing from a noun instead of the action | R-ACT-1; the frame requires ACTION first |
| An artifact forcing a review of something you wanted built | R-REF-1, R-XFM-1; artifact has a role, not a presence |
| Confidently building the wrong thing | R-DEST-1; UNRESOLVED object forces LOW, mechanically |
| Twelve questions, exhausted user | R-ASK-1; cap of 5, batched, with defaults |
| Building before direction is locked | G1 |
| Producing documents nobody reads | Four required; the rest conditional |
| Fighting a deliberate design choice | R-PAT-1, no cap |
| Restarting into the same weak direction | R-INT-1 step 4 |
| A new phrasing nobody anticipated | The frame has a slot for it. **If a case needs a new keyword rule, the frame is wrong — fix the frame, not the list.** |
