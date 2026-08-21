# ROUTER

Turn a vague request into a mode, a question set, a document set, and an owner. The router dispatches; it does not design, code, or research.

Then: [WORKFLOW.md](WORKFLOW.md) for stages, gates, roles, and autonomy.

---

## 1. Vocabulary

| Term | Meaning |
|---|---|
| **Mode** | The kind of project. One of 5. |
| **Stage** | S0-S6. [WORKFLOW.md](WORKFLOW.md). |
| **Skill** | A method in [skills/](skills/). |
| **Role** | One of 5 jobs. [WORKFLOW.md](WORKFLOW.md). |
| **Runner** | The tool doing the work. [adapters/](adapters/). |
| **Gate** | A named human approval. G1-G5. |

## 2. The five modes

| Mode | Use when |
|---|---|
| [Client or portfolio](modes/client-or-portfolio.md) | A site whose job is reputation — yours or someone else's |
| [Product app](modes/product-app.md) | Sustained interaction, state, returning users |
| [Game / experiment](modes/game-experiment.md) | Play, mechanics, class work, throwaway probes |
| [Content system](modes/content-system.md) | X/LinkedIn writing with a learning loop |
| [Audit / review](modes/audit-review.md) | Critique something that already exists |

---

## 3. Detection

### 3.1 Signals

| In the request | Points to |
|---|---|
| "portfolio", "my site", "client", "for a company", a brand name, money | Client or portfolio |
| "app", "tool", "dashboard", "users can", "log in", "save", "track" | Product app |
| "game", "experiment", "class", "assignment", "playable", "sketch", "installation" | Game / experiment |
| "post", "tweet", "LinkedIn", "content", "audience", "voice" | Content system |
| "review", "critique", "audit", "roast", a URL to an existing thing | Audit / review |

### 3.2 Tie-breaks, in order

1. **An existing artifact is supplied** → Audit / review, unless the request says "rebuild" or "redesign".
2. **State outlives the session** (accounts, saved data, returning users) → Product app, even when it looks like a site or a game.
3. **Still tied** → ask. One question, offering the two candidates.

### 3.3 Confidence

| Level | Behaviour |
|---|---|
| **High** | One mode, no competing signal. Proceed. |
| **Medium** | One leads, another is plausible. Proceed, but **name the runner-up** in the Routing Block. |
| **Low** | Tied after 3.2, or the request is one sentence with no object. **Stop. Ask one question.** |

**Never silently pick between two plausible modes.** Naming the runner-up costs one line and prevents a wasted build.

### 3.4 Switching mode mid-project

If evidence contradicts the mode — an experiment grows a login screen — the router re-fires: say the mode changed and why · list which documents survive · re-run the gate schedule.

Do not quietly upgrade quality bars. A mode change is a scope change and you decide.

---

## 4. Questions

**Maximum 5. Only questions whose answer changes the work.**

Before asking: *if the answer were A instead of B, would a different file get written?* If no, assume it, log it, move on.

Never ask: which framework · whether it should be responsive or accessible · whether quality matters · anything already stated.

**Ask in one batch**, numbered, each with a proposed default, so the reply can be "all defaults" or "2: X, rest default".

Per-mode question sets live in each [mode file](modes/).

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

**Never assume:** the design thesis · brand rules · what is true about you · whether something may be published · a real deadline.

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
| `CONTENT-LEARNINGS.md` | Content mode only |

| Mode | Required | Usually also |
|---|---|---|
| Client or portfolio | the four | AGENTS, ASSETS, RETROSPECTIVE |
| Product app | the four + **ARCHITECTURE** | TASKS, AGENTS, RETROSPECTIVE |
| Game / experiment | PROJECT, DESIGN | — |
| Content system | PROJECT, CONTENT-LEARNINGS | RESEARCH |
| Audit / review | QA only | — |

## 7. Skills

| Mode | Skills |
|---|---|
| Client or portfolio | [intake](skills/intake.md), [reference-analysis](skills/reference-analysis.md), [design-direction](skills/design-direction.md), [component-research](skills/component-research.md), [EVALUATION-RUBRICS.md](EVALUATION-RUBRICS.md) |
| Product app | intake, component-research, design-direction, evaluation |
| Game / experiment | intake (light), design-direction (light) |
| Content system | intake, [CONTENT-SYSTEM.md](CONTENT-SYSTEM.md), evaluation |
| Audit / review | reference-analysis, evaluation |

---

## 8. Stop-and-ask triggers

| Trigger | Why |
|---|---|
| Mode confidence is Low | Wrong mode means wrong everything downstream |
| A new dependency is proposed | G2, [LIBRARY-POLICY.md](LIBRARY-POLICY.md) |
| Client data, credentials, or private references appear | [PRIVACY-POLICY.md](PRIVACY-POLICY.md) |
| Anything would be published, pushed, or deployed | G4 / G5 |
| A paid API or per-token service would be used | [BUDGET-POLICY.md](BUDGET-POLICY.md) |
| The request implies auth, a dashboard, or an admin panel you did not ask for | Scope inflation |
| The design thesis is unapproved but build work is requested | G1 |
| Sources of truth conflict and section 11 does not resolve it | — |

---

## 9. Handling inputs

**References.** Route to [reference-analysis](skills/reference-analysis.md) before any design work. **Three minimum** — one produces imitation, three force synthesis. If only one is supplied, ask for two more or name two from [references/visual-references.md](references/visual-references.md) and say which.

**Screenshots of existing products.** Evidence, not instruction — run every observed pattern through [skills/reference-analysis.md](skills/reference-analysis.md) before adopting it.

**Missing assets.** Resolved at S3, never at S4. No project reaches S4 with an unresolved asset on the critical path — either it exists, it gets made, or **the direction changes so it is not needed.** A type-led direction removes the dependency entirely. See [DESIGN-ASSETS.md](DESIGN-ASSETS.md).

**Current information.** Anything depending on the state of the world — pricing, versions, limits, licences — gets verified and dated. Never answered from memory. [RESEARCH-POLICY.md](RESEARCH-POLICY.md).

**Budget.** Any recurring cost goes through [BUDGET-POLICY.md](BUDGET-POLICY.md) first, presented in INR/month with what it displaces.

---

## 10. Accepted patterns — the deliberate-choice escape hatch

[DESIGN-TASTE.md](DESIGN-TASTE.md) lists patterns that are **Blocking** at QA. Those rules exist because a model with no constraint produces the statistical average.

**But you are allowed to choose one of them on purpose.** A dashboard with cards is right for some products. A gradient can be correct. The rules assume genericness came from the tool; sometimes it is your decision, and the system must not fight you.

To accept a pattern deliberately, declare it in `PROJECT.md`:

```
ACCEPTED PATTERNS
<pattern>  — because <reason specific to this project>
```

Effect: that row drops from **Blocking to Note** in [QA-POLICY.md](QA-POLICY.md). It still appears in the report, so it stays visible, but it no longer stops G3.

**Three constraints, or this becomes a way to disable the quality bar:**

1. **Declared at S1 or S3, before it is built.** Accepting a pattern at S5 to make a failing build pass is a waiver, not a decision — it gets recorded as a waiver with your name on it.
2. **A reason, not a preference.** "The user monitors six live data streams, so a card grid is the correct density" is a reason. "I like cards" is not, and the router should push back once.
3. **Maximum three per project.** Four or more means the direction is generic and the acceptances are papering over it. At four, the router stops and says so.

The Design director may argue against an acceptance. It may not override one.

---

## 11. Restarting a direction

"Scrap it and start over" is the most common creative event and needs a defined procedure, because the default — quietly patching the old direction — produces incoherent work.

**When it fires:** you reject the thesis at G1 · the work is built and the Reviewer returns "rebuild the direction" · you look at it and it is wrong.

**Procedure:**

1. **Say which layer is being restarted.** Direction only, or scope too? If `PROJECT.md` was wrong, this is an S1 restart and the direction was a symptom.
2. **Survives:** `PROJECT.md` (unless scope was the problem), `RESEARCH.md`, the token *system* (not its values), the architecture, anything mechanical.
3. **Dies:** the thesis, the rejection list, the signature moment, and **every component whose form came from the old thesis.** Keeping "the good bits" is what produces incoherence — the bits were good *relative to a direction that no longer exists*.
4. **Write down why it failed** before writing the new thesis. Put it in the new `DESIGN.md` under "What NOT to copy" — your own failed direction is a reference you must not repeat. This is the step that prevents restarting into the same place.
5. **G1 re-fires.** Full presentation, new scorecard.
6. **Log it** in `RETROSPECTIVE.md`. Two restarts on one project means S1 was under-specified, not that the direction was unlucky.

**Restarting is cheap at S3 and expensive at S5.** That asymmetry is the entire argument for G1.

---

## 12. Precedence

```
Project AGENTS.md → Project DESIGN.md → Project PROJECT.md
  → mode file → Builder OS core → global CLAUDE.md
```

If a conflict survives this chain, **stop and ask.** Do not average two instructions into a compromise neither party wanted.

---

## 13. Output — the Routing Block

```
ROUTING BLOCK
Mode:         <mode>  (confidence: High | Medium | Low)
Runner-up:    <mode or none> and why not
Questions:    <n, batched below>
Assumptions:  <the 3-5 that matter>
Documents:    <required, plus any conditional ones and why>
Skills:       <which>
Gates ahead:  <G1 ... G5>
Budget:       <INR impact, or "none">
First action: <the single next thing>
```

**First action is mandatory and must be one concrete step.** A Routing Block ending in "let me know how you'd like to proceed" has failed.

---

## 14. Known failure modes

| Failure | Countermeasure |
|---|---|
| Twelve questions, exhausted user | Cap of 5, batched, with defaults |
| Routing straight to Build because it sounded simple | S3 cannot be skipped for visual modes; G1 blocks it |
| Producing documents nobody reads | Four required; the rest conditional (section 6) |
| Treating references as things to copy | Three minimum, plus a mandatory "do not copy" list |
| Silent scope growth | 3.4 makes a mode change your decision |
| Fighting a deliberate design choice | Section 10 |
| Restarting into the same weak direction | Section 11 step 4 |
