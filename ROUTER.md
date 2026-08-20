# ROUTER

The entry point of the Builder OS. Every project starts here.

The router does one job: **turn a vague request into a mode, a question set, a document set, and an owner.** It does not design, code, or research. It dispatches.

Related: [WORKFLOW.md](WORKFLOW.md) (what happens after routing) · [AGENT-ROLES.md](AGENT-ROLES.md) (who does it) · [MODEL-ROUTING.md](MODEL-ROUTING.md) (which tool)

---

## 1. Vocabulary

Used identically in every file of this system.

| Term | Meaning |
|---|---|
| **Mode** | The kind of project. One of 7. Determines documents, skills, and quality bar. |
| **Stage** | A phase of work. S0-S6. See [WORKFLOW.md](WORKFLOW.md). |
| **Skill** | A reusable capability module in [skills/](skills/). Provider-neutral. |
| **Role** | A responsibility with defined inputs/outputs. See [AGENT-ROLES.md](AGENT-ROLES.md). |
| **Runner** | The actual tool doing the work (Codex, Cursor, Claude Code). See [adapters/](adapters/). |
| **Gate** | A named approval checkpoint. Work stops until a human says yes. See [AUTONOMY-POLICY.md](AUTONOMY-POLICY.md). |
| **Routing Block** | The router's output. Section 9. |

---

## 2. The seven modes

| Mode | File | Use when |
|---|---|---|
| Premium client website | [modes/premium-client-website.md](modes/premium-client-website.md) | Paid or reputation-critical site for someone else |
| Personal portfolio | [modes/personal-portfolio.md](modes/personal-portfolio.md) | Your own work, your own reputation |
| Product app | [modes/product-app.md](modes/product-app.md) | Sustained interaction, state, real users |
| Game / experiment | [modes/game-experiment.md](modes/game-experiment.md) | Play, mechanics, class work, throwaway probes |
| Content system | [modes/content-system.md](modes/content-system.md) | X/LinkedIn writing, analytics, learning loop |
| Audit / review | [modes/audit-review.md](modes/audit-review.md) | Critique something that already exists |
| Benchmark | [modes/benchmark.md](modes/benchmark.md) | Measure the Builder OS itself |

---

## 3. Mode detection

### 3.1 Signals

Score each mode. Highest score wins. Signals are cumulative.

| Signal in the request | Points to |
|---|---|
| "client", "for a company", "they want", a real brand name, money mentioned | Premium client website |
| "my portfolio", "my site", "about me", "my work" | Personal portfolio |
| "app", "tool", "dashboard", "users can", "log in", "save", "track" | Product app |
| "game", "experiment", "class", "assignment", "playable", "sketch", "toy" | Game / experiment |
| "post", "tweet", "LinkedIn", "content", "audience", "engagement", "voice" | Content system |
| "review", "critique", "audit", "roast", "feedback on", a URL to an existing thing | Audit / review |
| "test the system", "compare", "measure", "benchmark", "which is better" | Benchmark |

### 3.2 Tie-breaks

Applied in order:

1. **An existing artifact is supplied** (URL, repo, screenshot of a live thing) then route to Audit / review, unless the request says "rebuild" or "redesign".
2. **Someone else's reputation is at stake** then route to Premium client website. It has the strictest gates; over-applying it is safe, under-applying it is not.
3. **State outlives the session** (accounts, saved data, returning users) then route to Product app, even if it looks like a site.
4. **Still tied** then ask. One question, offering the two candidates.

### 3.3 Confidence

| Confidence | Meaning | Router behaviour |
|---|---|---|
| **High** | One mode scored, no competing signal | Proceed. State the mode in the Routing Block. |
| **Medium** | One mode leads, another is plausible | Proceed, but name the runner-up and the assumption in the Routing Block. |
| **Low** | Two modes tied after 3.2, or the request is one sentence with no object | Stop. Ask one disambiguating question. |

**Never silently pick between two plausible modes.** Naming the runner-up costs one line and prevents a whole wasted build.

### 3.4 Mode switching mid-project

Modes are not locked. If evidence contradicts the mode (a "small experiment" grows a login screen), the router re-fires:

1. Say the mode changed and why.
2. List which already-generated documents survive, which need revision.
3. Re-run the gate schedule for the new mode.

Do not quietly upgrade quality bars. A mode change is a scope change and the user decides.

---

## 4. Questions

### 4.1 The rule

**Maximum 5 questions. Only questions whose answer changes the work.**

Before asking, apply this test:

> If the user answered A instead of B, would a *different file get written*?

If no, do not ask it. Assume it, log the assumption, move on.

Never ask for: preferred framework (default stack applies), whether they want it "responsive" or "accessible" (always yes), whether quality matters, or anything already answered in the request.

### 4.2 Per-mode question sets

The full sets live in each mode file. Summary of what is always worth asking:

| Mode | The questions that actually change output |
|---|---|
| Premium client website | Who is the client and what do they sell? What must a visitor *do* or *feel*? What assets exist (logo, photos, copy)? Hard deadline? Any brand rules that cannot be broken? |
| Personal portfolio | Which 3-5 projects, and what should each prove? Who is the reader: recruiter, studio, client, awards jury? What is the one thing you want remembered? Do you have process artifacts or only finals? |
| Product app | What is the single core loop? What must persist between sessions? Who else touches the data? What is explicitly out of scope for v1? |
| Game / experiment | What is the core mechanic in one sentence? Input device? Win/lose or endless? Is this graded, and against what rubric? |
| Content system | Which platforms? What are you actually known for? What do you refuse to post? Do you have access to past post analytics? |
| Audit / review | Which lens ([EVALUATION-RUBRICS.md](EVALUATION-RUBRICS.md))? Is this yours or someone else's? Do you want fixes or only findings? |
| Benchmark | What is the hypothesis? What counts as a win? |

### 4.3 Ask in one batch

All questions at once, numbered, each with the router's proposed default so the user can reply "all defaults" or "1: X, rest default". Never interrogate one question at a time.

---

## 5. When the router may assume

Assume freely, and log it. **Every assumption goes in `PROJECT.md` under Assumptions**, phrased so it can be contradicted in one line.

| Area | Default assumption |
|---|---|
| Stack | Next.js + TypeScript (strict) + pnpm. See [templates/ARCHITECTURE.md](templates/ARCHITECTURE.md). |
| Hosting | Vercel, preview per branch |
| Backend | None until a requirement forces one |
| CMS | None until a non-developer must edit copy |
| Auth | None. See [AUTONOMY-POLICY.md](AUTONOMY-POLICY.md). |
| Styling | CSS variables + custom tokens. Tailwind only if the project has many one-off utility needs. |
| Motion | Motion.dev for component/state motion, GSAP when a timeline or scroll choreography is central |
| Testing | Playwright for flows, production build must pass |
| Language | English, Indian-English spellings where they differ |
| Budget | Subscription tools only, no pay-per-token. See [BUDGET-POLICY.md](BUDGET-POLICY.md). |

**The router must never assume**: the design thesis, the client's brand rules, what content is true about the user, whether something may be published, or what a real deadline is.

---

## 6. Stop-and-ask triggers

The router halts, regardless of mode, when any of these appear. These are not style preferences. They are the difference between a reversible mistake and an expensive one.

| Trigger | Why |
|---|---|
| Mode confidence is Low (3.3) | Wrong mode means wrong everything downstream |
| A new dependency is proposed | Gate G2, [LIBRARY-POLICY.md](LIBRARY-POLICY.md) |
| Real client data, credentials, or private references appear | [PRIVACY-POLICY.md](PRIVACY-POLICY.md) |
| Anything would be published, pushed, or deployed | Gates G4/G5 |
| A paid API or per-token service would be used | [BUDGET-POLICY.md](BUDGET-POLICY.md) |
| The request implies work the user said they did not want (auth, dashboard, admin) | Scope inflation |
| Two sources of truth conflict and the precedence chain does not resolve it | Section 8 |
| The design thesis has not been approved but build work is being requested | Gate G1 |

---

## 7. Handling inputs

### 7.1 References, screenshots, moodboards

When the user supplies references:

1. Route to the **reference-analysis** skill ([skills/reference-analysis.md](skills/reference-analysis.md)) before any design work.
2. Extract *mechanisms*, never surfaces. "Type is the image" is a mechanism. "Big serif in the corner" is a surface.
3. Require **at least three** references before forming a direction. One reference produces imitation; three force synthesis.
4. Record in `DESIGN.md` under "What to borrow" and "What NOT to copy". The second list is mandatory and must be specific.

If the user supplies exactly one reference, the router asks for two more or names two itself from [references/visual-references.md](references/visual-references.md) and says so.

### 7.2 Screenshots of an existing product

Treat as evidence, not instruction. A screenshot showing a pattern is not approval to reuse that pattern. Run it through [DESIGN-TASTE.md](DESIGN-TASTE.md) anti-generic rules first.

### 7.3 Missing assets

Assets are the most common silent blocker. The router resolves this at S1, never at S4.

| Situation | Router action |
|---|---|
| No logo | Ask if one exists. If not, use the asset-generation skill or a typographic wordmark. Never a placeholder box. |
| No photography | Decide *at direction time* whether the design is image-led or type-led. A type-led direction removes the dependency entirely. |
| No copy | Draft real copy in `PROJECT.md` voice. Never ship lorem ipsum, never ship generic AI copy. See [DESIGN-TASTE.md](DESIGN-TASTE.md). |
| Client will supply "later" | Log as a risk in `HANDOFF.md` and design a fallback that works without it. |

**Rule: no project proceeds to S4 (Build) with an unresolved asset dependency on the critical path.** Either the asset exists, is generated, or the design no longer needs it.

### 7.4 Current information

Route to the **live-research** skill ([skills/live-research.md](skills/live-research.md)) whenever the answer depends on the state of the world: pricing, library versions, whether a tool still exists, platform limits, API availability. Never answer these from memory. See [RESEARCH-POLICY.md](RESEARCH-POLICY.md).

### 7.5 Budget constraints

Any suggestion with a recurring cost goes through [BUDGET-POLICY.md](BUDGET-POLICY.md) before it reaches the user. The router presents cost in INR/month, states what it displaces, and defaults to the free or already-owned option.

---

## 8. Precedence

When documents conflict:

```
Project AGENTS.md
  then Project DESIGN.md
  then Project PROJECT.md
  then Builder OS mode file
  then Builder OS core docs
  then global CLAUDE.md
```

If a conflict survives this chain, **stop and ask**. Do not average two instructions into a compromise neither party wanted.

---

## 9. Router output: the Routing Block

Every routing decision produces exactly this. It is short on purpose; it is a dispatch slip, not a document.

```
ROUTING BLOCK
Mode:         <mode>  (confidence: High | Medium | Low)
Runner-up:    <mode or none> and why not chosen
Stage:        S0 -> S1
Questions:    <n, batched below>
Assumptions:  <the 3-5 that matter; full list goes to PROJECT.md>
Documents:    <files to create, in order>
Skills:       <skills to activate>
Owner:        <role> on <runner>
Gates ahead:  <G1 ... G5 relevant to this mode>
Budget:       <INR impact, or "none, existing subscriptions">
First action: <the single next thing>
```

The **First action** line is mandatory and must be a single concrete step. A Routing Block that ends in "let me know how you'd like to proceed" has failed.

---

## 10. Documents and skills per mode

Authoritative per-mode detail is in each mode file. This is the index.

| Mode | Documents (in order) | Skills |
|---|---|---|
| Premium client website | PROJECT, RESEARCH, DESIGN, ARCHITECTURE, ASSETS, TASKS, AGENTS, HANDOFF, QA, RETROSPECTIVE | discovery, grilling, live-research, reference-analysis, design-direction, component-research, frontend-build, motion-design, asset-generation, browser-qa, accessibility, performance, deployment, evaluation |
| Personal portfolio | PROJECT, DESIGN, ARCHITECTURE, TASKS, AGENTS, HANDOFF, QA, RETROSPECTIVE | discovery, grilling, reference-analysis, design-direction, frontend-build, motion-design, asset-generation, browser-qa, accessibility, performance, deployment, evaluation |
| Product app | PROJECT, ARCHITECTURE, DESIGN, TASKS, AGENTS, HANDOFF, QA, RETROSPECTIVE | discovery, grilling, live-research, design-direction, component-research, frontend-build, browser-qa, accessibility, performance, deployment, evaluation |
| Game / experiment | PROJECT, DESIGN (short), TASKS, HANDOFF, QA (short) | discovery, design-direction, frontend-build, motion-design, asset-generation, browser-qa |
| Content system | PROJECT, RESEARCH, CONTENT-LEARNINGS, TASKS, AGENTS | discovery, grilling, live-research, content-strategy, evaluation |
| Audit / review | QA, RETROSPECTIVE (findings live in QA.md) | reference-analysis, evaluation, browser-qa, accessibility, performance |
| Benchmark | PROJECT (hypothesis), RETROSPECTIVE (result) | live-research, evaluation |

Templates for all of these: [templates/](templates/).

---

## 11. Router failure modes

Known ways this router degrades, and the countermeasure. Reviewed at every retrospective.

| Failure | Countermeasure |
|---|---|
| Asking 12 questions and exhausting the user | Hard cap of 5, the 4.1 test, batched |
| Picking the comfortable mode instead of the right one | 3.2 tie-break 2 biases toward the stricter mode |
| Routing straight to Build because the request sounded simple | S3 Direction cannot be skipped for any visual mode; G1 blocks it |
| Producing documents nobody reads | Section 10 sets are minimal per mode; game mode gets 4 documents, not 10 |
| Treating references as things to copy | 7.1 requires 3+ references and a "do not copy" list |
| Silent scope growth | 3.4 mode-switch procedure surfaces it as a user decision |
