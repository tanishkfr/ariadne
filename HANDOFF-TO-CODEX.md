# HANDOFF TO CODEX

**From:** Claude (previous AI maintainer) · **To:** Codex (primary AI maintainer from now on)
**Repository state at handoff:** `d4c9bbb` · Builder OS **v0.3.3** · core **FROZEN**
**Written:** 2026-08-21

You have no conversation history. You do not need any. Everything required to continue is in this repository, and this document tells you where it is and what has actually been established.

Read this file, then `README.md`, then `WORKFLOW.md`. Do not read the whole repository before acting — see §2 on why.

> **One-line summary:** Builder OS is frozen and structurally sound; its *validation harness* has been fixed four times; **Builder OS itself has never produced a design artifact in a live run.** Your first job is to make that happen, not to improve the repository.

---

## 1. PROJECT IDENTITY

### What Builder OS is

A personal, provider-neutral **workflow specification** for AI-assisted creative and development work. It is plain Markdown: policies, stage prompts you paste into a reasoning tool, document templates, and a small set of Python checkers. There is no application, no server, no package.

### The problem it solves

One agent doing planning, design, implementation and review in a single conversation produces **generic work** and **contaminated judgement** — a reviewer that wrote the code is not a reviewer. Left alone, an AI session converges on the most probable solution, which is the most generic one, and then defends it.

### The core thesis

> Separating roles, forcing a design direction *before* implementation, and putting human gates between stages produces less generic work than one continuous conversation.

**This thesis is not yet proven.** See §7.

### Who it is for

One person — the repository owner — building portfolio and client work with Codex (reasoning) and Cursor (implementation), on a constrained budget. It is not a team tool and not a product.

### What Builder OS is NOT

- Not a SaaS product, framework, library, or app
- Not an autonomous agent system — **no role can approve anything; every gate is human**
- Not a prompt collection — the router, gates and role separation are the substance
- Not a scoring system — it deliberately produces **no composite quality number**
- Not tied to any vendor — `MODEL-ROUTING.md` routes by *capability class*, never by brand

### The role of the runtime layer

The **project's own repository is the project's memory.** A future session must be able to pick up a project without conversation history.

That is what `AGENTS.md` at a project root does. `AGENTS.md` is a real open standard (auto-discovered by Codex, Cursor and many other tools), so the runtime rides on something that already exists rather than inventing a mechanism. It carries **current state** and **a short list of things not to change** — nothing else.

---

## 2. CURRENT ARCHITECTURE

```
   YOU (all gates, all approvals)
        │
   ┌────┴─────────────────────────────────────────────┐
   │  BUILDER OS CORE (frozen)                        │
   │  ROUTER · WORKFLOW · design rules · QA · modes   │
   │  skills · templates · prompts                    │
   └────┬─────────────────────────────────────────────┘
        │  you paste a stage prompt
        ▼
   ┌──────────────┐   HANDOFF.md    ┌──────────────┐
   │ CODEX (R1)   │ ──────────────▶ │ CURSOR (B1)  │
   │ reasoning:   │                 │ implement:   │
   │ S0-S3, S6    │                 │ S4-S5 mech.  │
   └──────┬───────┘                 └──────┬───────┘
          │                                │
          ▼                                ▼
   ┌──────────────────────────────────────────────────┐
   │  PROJECT REPOSITORY  = the memory                │
   │  PROJECT.md · DESIGN.md · [HANDOFF · QA] ·       │
   │  AGENTS.md (current state)                       │
   └──────────────────────────────────────────────────┘
          │
          ▼
   FRESH SESSION REVIEW (S5) — gets ONLY the URL + success criteria
          │
          ▼
   RETROSPECTIVE (S6) → change proposals → you approve → core changes
```

**Frozen core.** The canonical policies. Paste-time knowledge. Changed only under §4's rule.

**Stage prompts** (`prompts/`). Each is a fenced block you copy into a tool. Everything the agent needs must be **inside the fence** — a real defect (`B1`, fixed in `466be45`) was an instruction sitting *outside* it, so the agent never received it. `check.py` guards this now.

**Codex = reasoning (R1).** Routes, scopes, directs, retrospects. **Writes no production code** — it produces `HANDOFF.md` that another tool builds from.

**Cursor = implementation (B1).** Builds from the handoff. Does not design.

**Fresh-session review (S5).** A separate session receives **only the URL and success criteria** — no `DESIGN.md`, no `HANDOFF.md`, no `AGENTS.md`. This is enforced by instruction, not technically. If the boundary breaks, the findings are contaminated and must be reported as such rather than used as evidence.

**Retrospective / learning loop** (`templates/RETROSPECTIVE.md`). The only route by which experience becomes a rule. Four qualification tests, all must hold. See §13.

**Canonical ownership.** Every rule has exactly one home. Other files *reference* it; they never restate it. `check.py` fails on duplicated sentences and on rule IDs defined twice or referenced without definition.

### Why the system deliberately avoids a giant context dump

Loading the whole repository into a session costs a large fraction of the context window before any work happens, and buries the three rules that matter for the current stage under fifty that do not. Each stage prompt therefore names **only the files that stage needs** — S3's prompt says explicitly: *"Do not load the whole Builder OS. Those files and nothing else."*

Two boundaries exist for the same reason and must not be collapsed:

| Boundary | Why it exists |
|---|---|
| Reasoning ≠ implementation | A session that designed something will defend it instead of building what was specified |
| Builder ≠ reviewer | A reviewer with build context reviews its own intentions, not the artifact |

---

## 3. CANONICAL OWNERSHIP

**`AGENTS.md` is NOT a second policy system.** Its authority covers two sections only — the current-state block and the do-not-change list (see `templates/AGENTS.md` for the exact contract). Everything else in it **mirrors** `PROJECT.md` and `DESIGN.md`. The direction of change is one-way: edit the canonical document first, then update the runtime. **Anything recorded nowhere but the runtime file has not actually been recorded.** Copying Builder OS policy text into it is a defect — `check.py` detects wholesale policy blocks.

| Concept / policy | Canonical file | Codex may edit? | Evidence required |
|---|---|---|---|
| Routing frame, rule IDs, modes, restart | `ROUTER.md` | **No** | Deterministic defect, or promoted retrospective proposal |
| Stages, roles, gates, autonomy tiers | `WORKFLOW.md` | **No** | Same |
| Design quality bar | `DESIGN-TASTE.md` | **No** | Same |
| Motion rules | `DESIGN-MOTION.md` | **No** | Same |
| Asset rules | `DESIGN-ASSETS.md` | **No** | Same |
| Mechanical QA | `QA-POLICY.md` | **No** | Same |
| Judgement QA / review lenses | `EVALUATION-RUBRICS.md` | **No** | Same |
| Mode definitions | `modes/*.md` | **No** | Multiple real projects |
| Skill methods | `skills/*.md` | **No** | Repeated need **and** a unique method |
| Stage prompts | `prompts/*.md` | **No** | Deterministic defect only |
| Document templates | `templates/*.md` | **No** | Deterministic defect only |
| Runtime state contract | `templates/AGENTS.md` | **No** | Deterministic defect only |
| Router regression suite | `tests/router-cases.md` | **Append results only** | Never rewrite past results |
| Validation procedures (Tests A/B/C) | `tests/validation-protocol.md` | **No** | This is the canonical protocol — do not write a new one |
| Library policy | `LIBRARY-POLICY.md` | **No** | Real project evidence |
| Research policy | `RESEARCH-POLICY.md` | **No** | Real project evidence |
| Budget | `BUDGET-POLICY.md` | **Yes**, factual updates | A dated source URL |
| Capability-class → product mapping | `MODEL-ROUTING.md` §3 | **Yes**, mapping table only | A product actually changed |
| Tool mechanics | `adapters/*.md` | **Yes** | A tool actually changed |
| Repository checker | `scripts/check.py` | **Yes** | Every new guard negative-tested |
| Run validator | `scripts/validate.py` | **Yes** | Same |
| Test A runner | `scripts/setup-test-a.py`, `scripts/finish-test-a.py` | **Yes** | Same |
| Run record format | `validation/run-template.md` | **Yes** | Keep existing records readable |
| Run records | `validation/runs/<id>/` | **Yes** — generated | Never edit a past run's findings |
| Version history | `CHANGELOG.md` | **Yes** | Record what actually happened |

**Project-level ownership** (inside a project repo, not this one): `PROJECT.md` owns scope and accepted patterns; `DESIGN.md` owns the thesis and design decisions; `AGENTS.md` owns only current state.

---

## 4. FROZEN CORE

Frozen at `3f7402c` (v0.3.3) and **verified untouched through `d4c9bbb`**:

```
ROUTER.md              WORKFLOW.md
DESIGN-TASTE.md        DESIGN-MOTION.md        DESIGN-ASSETS.md
QA-POLICY.md           EVALUATION-RUBRICS.md
modes/                 skills/                 prompts/         templates/
tests/router-cases.md  tests/validation-protocol.md
```

### The freeze rule

A frozen component may change **only** because of:

1. **A deterministic defect** — a link to a file that does not exist, a prompt that contradicts itself, an instruction outside the fence it must be inside, a rule ID referenced but never defined. Something a checker can demonstrate.
2. **Real project evidence** — it broke, or cost you nameable time, during actual work.
3. **Evidence from the validation protocol** — a Test A/B/C run in `validation/runs/`.

It may **not** change because of:

- A hypothetical concern ("this could confuse someone")
- Aesthetic or structural preference ("this would be cleaner")
- **Another audit.** The repository has already had several. More auditing is not more evidence.
- A single observation that has not passed the retrospective's four qualification tests

**Why this rule exists:** v0.1.0 was 71 files and ~64,000 words. It reached v0.3.3 at 61 tracked files by deleting things. Without a freeze rule it regrows, and a workflow nobody can hold in their head is not a workflow.

---

## 5. CURRENT VERSION / GIT STATE

| | |
|---|---|
| Version | **v0.3.3** (`CHANGELOG.md`: *V1 CANDIDATE · CORE FROZEN*) |
| Commit | **`d4c9bbb`** |
| Tracked files | **61** (56 Markdown) at `d4c9bbb`, before this handoff was added |
| Working tree | clean at handoff |
| `python scripts/check.py` | **PASS** — 7/7 |
| `python scripts/validate.py --self-test` | **PASS** — 21 guards |
| Validation runs recorded | **none in-repo** (`validation/runs/` holds only `_README.md`) |

**Structure:** 18 root Markdown documents · `prompts/` 7 · `modes/` 5 · `skills/` 4 · `templates/` 11 · `adapters/` 3 · `tests/` 2 · `references/` 2 · `validation/` 4 · `scripts/` 4.

**Router rule IDs (9):** `R-ACT-1` `R-ASK-1` `R-CONF-1` `R-DEST-1` `R-INT-1` `R-PAT-1` `R-REF-1` `R-REF-2` `R-XFM-1`
**Gates (5):** G1 Direction · G2 Dependency · G3 Build complete · G4 Ship · G5 Publish
**Stages:** S0-S1 Route+Discover → S2 Research *(conditional)* → S3 Direct **(G1)** → S4 Build → S5 Verify **(G3)** → S6 Ship & Learn **(G4)**

### Commit history

| Commit | What it was |
|---|---|
| `77658cf` | v0.1.0 — initial build, 71 files |
| `233b125` | file-count correction |
| `ad134b1` | v0.2.0 — restructure after independent audit |
| `53db8d4` | v0.2.1 — router stress test, game-experiment defaults, env protection |
| `f1645e1` | v0.3.0 — router routes on **intent**, not keywords |
| `5c441a8` | v0.3.1 — closed V1 structural blockers |
| `466be45` | v0.3.2 — **fixed B1**: NEXT instruction moved *inside* the fenced block |
| `3f7402c` | v0.3.3 — thin runtime layer; **CORE FROZEN** |

### The five commits since the freeze — all harness, none core

| Commit | Files | What changed |
|---|---|---|
| `4622470` | `validate.py`, `validation/` | Built the validation harness: run records, generic run checker, 13 self-test guards |
| `0468696` | `setup-test-a.py`, `finish-test-a.py`, fixture | Test A one-command runner; `validate.py` gained `resolve_run()` + benchmark glob |
| `3aa9455` | `check.py`, `validate.py`, both runners, template, README | **Four parser defects** (see §6-A2) + automatic routing extraction from the transcript |
| `c4045e5` | `check.py`, `validate.py` | Generated run records removed from the **repository** check and moved to the **run** checker — a stale record could otherwise permanently block all future runs |
| `d4c9bbb` | `finish-test-a.py`, `setup-test-a.py` | Removed a **false-positive deviation**; fixed the escaped-pipe bug in the record *writer*; made extraction tolerant of markdown; corrected the assumption that FRAME must be emitted |

**Read that table again before you start work.** Five consecutive commits since the freeze, all in `scripts/` and `validation/`. See §6's warning.

---

## 6. VALIDATION HISTORY

Canonical procedures: **`tests/validation-protocol.md`**. Do not write a new protocol.

Neither run's artifacts are in this repository — A2 ran on a different machine. Both are reconstructed here from the run record and `RESULT.md` the operator produced. Treat the *behavioural* findings as real and the *file-level* details as reported.

### A1 — routing only

- **Tested:** Test A condition 1. Prompt: *"I want to make something with type that reacts to sound."*
- **Happened:** `ACTION=CREATE`, `OBJECT=UNRESOLVED`, **confidence Low**, no mode committed, one clarifying question with a concrete default, `NEXT` emitted with `Blocked on`.
- **Proven:** R-DEST-1 held — an unresolved object produced Low confidence rather than a confident guess.
- **Deviation:** the closing `NEXT` block omitted `References to bring`. **One occurrence. Did not recur in A2.** Below the change threshold.
- **Unproven:** everything after routing. No documents were written.

### A2 — routing only, again

- **Tested:** Test A condition 1 again, different Codex model (`gpt5.6sol med`).
- **Happened:** ambiguous object → **Low confidence** → closest mode named *with* Low confidence → clarifying question asked → **no project files written** → full `NEXT` block including `Blocked on`.
- **Proven:** routing correct a second time, different wording, different model. **Zero high-confidence wrong routes across both runs** — the one metric the protocol says must stay at zero.
- **Unproven:** the same everything. `Documents present: []`.

> **A2's "confidence is Low but a mode was committed" was NOT a Builder OS defect.**
> It was a **harness false positive**, fixed in `d4c9bbb`. STEP 3 of `prompts/project-start.md` *requires* the line `Mode: <mode> (confidence: High|Medium|Low)`, and the prompt says to *"pick the closest workflow and SAY SO."* The project directory was empty, so the session had in fact stopped and asked — exactly what Low confidence demands. The check now measures whether documents were **written**, not what the mode was **called**. Do not reintroduce this finding.

### Harness defects found and fixed

| # | Defect | Consequence | Fixed in |
|---|---|---|---|
| 1 | `field()` split table rows on a bare `\|`, ignoring escaped pipes | Placeholders truncated, then reported as *wrong* values (`unknown mode '<client-or-portfolio '`) | `3aa9455` |
| 2 | Only `Run ID` was placeholder-checked | `Mode`/`Model`/`Result` placeholders read as real values | `3aa9455` |
| 3 | The template's **example event rows** were parsed as real events | **Fabricated `VALUE=1` and one B-class question on an empty record** | `3aa9455` |
| 4 | Baseline guard word-counted the template's own ~160 words of instructions | A blank baseline passed; the report printed the instructions *as* the baseline | `3aa9455` |
| 5 | `check.py` walked generated run records | A stale record from a past run **permanently blocked all future runs** | `c4045e5` |
| 6 | Records written two directories deeper than the template, links not adjusted | Broken relative link in every record | `3aa9455`/`c4045e5` |
| 7 | `setfield()` had defect 1 in the **writer** | Every generated record carried orphaned tails: `\| **Run ID** \| \`A2\` \| B1 \\\| B2 …>\` \|` | `d4c9bbb` |
| 8 | Extraction matched only a bare `KEY: value` line | Markdown-formatted replies extracted **nothing**; R-DEST-1 silently unchecked while the report looked complete | `d4c9bbb` |
| 9 | Assumed the FRAME must be emitted | It is internal (*"fill these before deciding"*); only the ROUTING BLOCK is required output | `d4c9bbb` |
| 10 | Baseline capture bled into the comparison subsection | Same empty table printed twice | `d4c9bbb` |

### What those fixes do NOT prove

They prove the **instrument** is more trustworthy. They prove **nothing about Builder OS.** A harness that reads a transcript correctly has not validated a workflow.

### ⚠ The warning this history carries

**Three of the last four findings that appeared to be Builder OS defects were harness bugs.** Five consecutive commits since the freeze touched only the instrument. There are now roughly 86 negative-tested guards validating a system that **has never written a single file.**

That is inverted. Two runs both stopped at the S1 question, so conditions 2, 3 and 4 of Test A remain entirely unexercised.

**Stop over-validating the harness. Start exercising Builder OS.** When something looks anomalous, your first hypothesis should be *"the instrument is wrong"* — historically it has been, three times out of four.

---

## 7. CURRENT EVIDENCE

Never collapse these into a score. They are different kinds of evidence and mixing them hides which is which.

### PROVEN — deterministic or observed in a live run

- `check.py` passes 7/7; `validate.py --self-test` passes 21 guards; all negative-tested
- Frozen core untouched from `3f7402c` → `d4c9bbb` (verified by `git diff`, empty)
- Every rule ID defined once, no dangling references, no duplicated sentences
- All 4 chained stage prompts emit `NEXT` **inside** the fence
- **Live, twice:** an ambiguous brief produced Low confidence, a clarifying question, and no premature mode commitment. **Zero high-confidence wrong routes.**
- **Live, twice:** the `NEXT` block was emitted with `Blocked on`

### SIMULATED — reasoned on paper, never executed

- Router behaviour across 64 cases (42 in `tests/router-cases.md` + 22 adversarial). **Self-derived, never independently re-run by a second agent.**
- 7 runtime state transitions traced against the written prompts (7 pass, 1 documented caveat)
- Cold-start, handoff sufficiency, and mode-executability traces
- **Simulation is not validation.** It shows the written rules are internally unambiguous, not that any tool honours them.

### UNPROVEN — no evidence of any kind

- **Builder OS has never produced a real design artifact through S3 in a live run.** No `DESIGN.md`, no thesis, no rejection list, no signature moment has ever been generated.
- **Builder OS has never written a single file in a live run.** Not one `PROJECT.md`, not one `AGENTS.md`.
- Whether only the required documents appear, or ceremony leaks in (Test A condition 2)
- Whether S3 produces a direction rather than a mood (condition 3)
- Whether Builder OS output differs from the operator's unprompted attempt (**condition 4 — the protocol calls this the only way to see whether S3 does anything**)
- Handoff sufficiency · implementation fidelity · independent review · browser QA · accessibility · performance · deployment · provider switching · long-session drift
- **Design quality** — must never be self-assessed; requires an independent reviewer (Test B)
- **The core thesis itself** (§1)

---

## 8. CURRENT RECOMMENDATION

**Run A3 through S1 → S3 → G1.**

`tests/validation-protocol.md` defines Test A with **four** pass conditions. A1 and A2 tested **condition 1, twice**. A third routing-only run would test it a third time and add almost nothing.

1. **Routing is the only thing established.** Two live runs, two models, zero wrong routes. Further samples have sharply diminishing value.
2. **The untested half is the half the system exists for.** `WORKFLOW.md` calls the Design director *"why the system exists."* It has never run.
3. **The protocol names the missing evidence explicitly:** *"Keep both artifacts side by side — this comparison is the evidence, and it is the only way to see whether S3 does anything."*
4. **A usable baseline exists now and has a shelf life.** A2 produced only a routing question — no design content — so the operator's baseline is still uncontaminated *with respect to design direction*. That stops being true the moment Builder OS shows a direction.
5. **S3 is the last stage reachable without Cursor.** It is a reasoning stage producing `DESIGN.md` + a G1 presentation. S4 needs Cursor. **G1 is exactly where the current tooling boundary sits.**

A3 must: reuse the A2 baseline · answer the routing question **without leaking the baseline's visual ideas** · let S1 write `PROJECT.md` and `AGENTS.md` · run `prompts/design-direction.md` · reach G1 · **stop before approval and before any build** · compare the resulting direction against the baseline.

**Do not run another routing-only test.**

---

## 9. A3 EXPERIMENT PROTOCOL

Canonical procedure: **`tests/validation-protocol.md` → Test A**. This section is the operational sequence, not a new protocol.

### Step 0 — setup

```bash
python scripts/setup-test-a.py
```

Allocates the **next free run ID** by scanning `validation/runs/` — `A3` if `A1` and `A2` exist there locally, a lower number if they do not. Run records are not committed, so the ID depends on the machine; use whatever it prints and refer to that run everywhere below. It also creates an **empty** project directory outside this repository, writes `validation/runs/<id>/run.md` from the template, and prints the exact prompt (also saved to `validation/runs/<id>/PASTE-INTO-CODEX.txt`).

Prefer the file over copying from the terminal — Windows consoles mangle em-dashes.

### Step 1 — baseline: carry it over, do not rewrite it

Copy the **A2 baseline verbatim** into A3's `## Baseline`. Keep `Captured before opening Codex: yes` and add: `carried over from A2, written before any Builder OS output`.

**Writing a new baseline now would be writing it after seeing A2's output. The control would be gone.**

### Step 2 — S1

Paste `validation/runs/A3/PASTE-INTO-CODEX.txt` into a **fresh** Codex session. The brief is deliberately vague; that vagueness is the test.

**Save the raw first reply to `validation/runs/A3/evidence/transcript.md` before replying to anything.** Routing extraction reads that file; without it there is no routing measurement.

### Step 3 — answer the routing question ⚠ the step that can ruin the run

Answer **only what the object is**, in one sentence — accept its proposed default, or say *"a browser-based interactive piece using live microphone input."*

**Do not mention dark backgrounds, grotesques, variable weight, amplitude mapping, or any visual idea.** That is the baseline. Feeding it in makes S3 echo the operator and **condition 4 becomes unmeasurable.**

Let S1 write `PROJECT.md` and `AGENTS.md`.

### Step 4 — S3

In the same session, paste the fenced block from `prompts/design-direction.md`.

For `REFERENCES:` write **`none yet`**. Do not supply your own. What the session does with that is itself a measurement — the prompt tells it to ask or propose and say which it chose. Record whether it could load live sites.

### Step 5 — stop at G1

When the `G1: DIRECTION LOCK` block appears, **stop.**

Do not approve. Do not paste `build-kickoff.md`. Do not let it write code. Do not update `AGENTS.md` to `S4`/`G1` — S3 deliberately writes nothing and emits a block to paste **on approval**, so a rejected direction never claims a gate it did not pass.

Save the full transcript.

### What NOT to tell Codex

- That this is a test, a validation run, or that a harness is watching
- That a previous session asked a question
- Which mode you expect, or the word `game-experiment`
- Anything from the baseline

### Step 6 — record

In `validation/runs/A3/run.md`:

- `Mode` — **a bare mode name only.** A2 put commentary in this field and the required-documents check could not run. Commentary belongs in an event row.
- `Model`, `Started`, `Ended`, `Result`
- Events **as they happen** — especially `FRICTION` (any moment spent thinking about Builder OS instead of the project) and `QUESTION` rows with `class A/B/C`. Every row needs an evidence reference.

### Step 7 — validate

```bash
python scripts/finish-test-a.py
```

Generates `validation/runs/A3/RESULT.md` (PROVEN / OBSERVED / HUMAN JUDGEMENT / UNPROVEN), updates the benchmark, and prints the contract check.

### Step 8 — inspect by eye

**Do not build tooling for this.** Design quality must not be auto-scored.

| Look at | Expected |
|---|---|
| Documents in the project | `PROJECT.md`, `DESIGN.md`, `AGENTS.md` — **anything else is a finding** |
| `AGENTS.md` state | Stage `S3`, gate `none` — claiming G1 before approval is a real defect |
| Thesis | one sentence; **none of**: clean, modern, minimal, premium, sleek, elegant |
| Rejection list | 3+, specific to this project |
| Signature moment | named, **with a stated mobile equivalent** |
| Contract check | deviations, B-class count |

**The measurement that matters:** put the baseline and the G1 thesis side by side and answer honestly — *did it reject something the operator would have shipped, and can a specific rule be named as the cause?*

---

## 10. CODEX'S ROLE GOING FORWARD

You are now technical maintainer, implementation owner, systems architect, validation operator, skeptical reviewer, and documentation maintainer.

**You are not the authority on whether Builder OS is good.** The human is the final decision maker. Every gate is human-only — that is a core property, not a formality.

You must:

- **Inspect before changing.** Read the actual file and git history. Do not act on a summary, including this one.
- **Preserve canonical ownership.** One rule, one home. Reference; never restate.
- **Never create a second policy system.** Especially not in `AGENTS.md`.
- **Distinguish evidence from hypothesis.** "I think this could break" is not a finding. "Here is the input that breaks it" is.
- **Negative-test every deterministic check.** A guard that cannot fail is not evidence — this repository has shipped vacuous guards **twice**, and both times a negative test caught it.
- **Include positive controls.** A filter that discards everything passes a negative test while destroying real data.
- **Never modify the frozen core without evidence** meeting §4.
- **Report uncertainty honestly.** If you could not verify something, say so and say why. If artifacts are missing, say they are missing.
- **Never manufacture evidence.** An unparseable transcript is `NOT EXTRACTED`, not a guess. Empty is a valid result.
- **Never collapse human judgement into an automated score.** No composite number, anywhere, for any reason.

### A specific trap, from this project's own history

Automated file-patching through shells has repeatedly corrupted this repository's scripts: `\b` becoming literal backspace bytes (`0x08`), and `\n` inside f-strings becoming real newlines that broke Python syntax. Both produced checks that silently passed everything.

**After any scripted edit to a `.py` file, run `python -m py_compile` on it and re-run the negative tests.**

---

## 11. WHAT CODEX MUST NOT DO

Forbidden unless real evidence appears:

- **Build a Builder OS skill** — it would duplicate the `AGENTS.md` standard and work in one vendor's product instead of many
- **Build cross-product automation** — nothing should drive Codex and Cursor from one controller
- **Build `.builder-os/`** — the four required documents plus the runtime file already are the context packet
- **Split `ROUTER.md`**
- **Redesign the interpretation frame**
- **Add modes** — requires evidence from multiple real projects
- **Reorganize QA**
- **Add S3 design scoring** — the system forbids self-scoring; an automated S3 grader would violate the thing it measures
- **Build a composite quality score** — anywhere, for anything
- **Automate independent review** — the independence *is* the mechanism
- **Add context-packet infrastructure**
- **Modify the frozen core because of a hypothetical concern**
- **Write a new validation protocol** — `tests/validation-protocol.md` is canonical

And, most importantly:

> **Do not continue endlessly auditing the validation harness instead of using Builder OS.**
>
> Five commits since the freeze have all been harness work. The next commit that is not the result of a real run is a mistake. If you find yourself improving the instrument again, stop and ask whether a run would produce more information — it almost certainly would.

---

## 12. DECISION HIERARCHY

| Rank | Authority |
|---|---|
| 1 | **Human decision** |
| 2 | **Frozen canonical Builder OS policies** |
| 3 | **Real project evidence** |
| 4 | **Validation protocol** (`tests/validation-protocol.md`) |
| 5 | **Retrospective / learning loop** |
| 6 | **Codex judgement** |

**Your judgement must never silently override a higher layer.** If you believe a frozen policy is wrong, you may **say so and propose a change with evidence** — you may not act on the belief. Surface the conflict and let the human decide.

If layers conflict, the higher one wins. If the conflict cannot be resolved, stop and ask.

---

## 13. HOW CHANGES ARE PROPOSED

```
observation → retrospective → qualification (4 tests) → written proposal
           → HUMAN APPROVAL → canonical file edited → checks re-run
```

**An observation does not become a rule.** Most observations are project-specific; a retrospective that promotes everything is not being honest.

All four qualification tests in `templates/RETROSPECTIVE.md` must hold:

1. **Recurs?** — would it happen again on a different project
2. **Evidence** — seen twice, or once with a **named cost** in hours
3. **Names a specific rule** — not a mood or a direction
4. **Survives the deletion test** — if the rule existed and someone deleted it a year later, would anything actually break? A "no" means you have an observation, not a rule.

Then: one file per proposal (a proposal touching three files is three proposals, or it is too big) · **propose deletions too** — a rule that never fired, or was always waived, is evidence against itself · human approves · edit the **canonical** file only · re-run `python scripts/check.py`, plus the router suite if routing was touched · record it in `CHANGELOG.md`.

**A single occurrence is rarely enough. "Freeze" is the expected answer after any one run.** That friction is what stopped the system regrowing to seventy files.

---

## 14. IMMEDIATE NEXT ACTION

**NEXT: Run A3 through S1 → S3 → G1.**

```bash
python scripts/setup-test-a.py
```

After setup, follow **§9**, which operationalises the canonical Test A in `tests/validation-protocol.md`. Carry the A2 baseline over unchanged, answer the routing question without leaking any visual idea, let S1 write its documents, run `prompts/design-direction.md`, and **stop at G1** — no approval, no build.

Then run `python scripts/finish-test-a.py` and compare the direction against the baseline.

**Do not begin any other work first.** Do not improve the harness on the way.

### Decision rule for A3's result

| Outcome | Action |
|---|---|
| All four Test A conditions hold, ≤1 deviation, only required documents | **Freeze and continue.** Get Cursor, run S4 / Test B. *This is the expected outcome.* |
| Run is compliant but the report misreads it | **Fix the harness only.** Default assumption for anything anomalous — historically correct 3 times in 4. |
| A **deterministic** defect appears (dangling `NEXT`, a prompt demanding a file that does not exist, `AGENTS.md` claiming an unapproved gate) | **Core change permitted**, via §13. |
| S1 never writes `PROJECT.md` | **Postpone S3.** The document path is broken; that is the finding. |
| S3 produces a direction near-identical to the baseline | **Record it and change nothing.** This is a legitimate, important result — not a failure to fix. One occurrence fails the recurrence test. The protocol already states the consequence if three real projects yield zero *"it made me reject X"* instances: cut the anti-generic apparatus back to the four mechanically checkable rules. **Do not preempt that with one run.** |

---

## 15. HANDOFF COMPLETENESS CHECK

A fresh Codex session with only this repository can answer:

| Question | Where |
|---|---|
| What is Builder OS? | §1, then `README.md`, `WORKFLOW.md` |
| What is frozen? | §4 — explicit file list and the three-part change rule |
| What can I change? | §3 — per-file table with evidence required |
| What has actually been proven? | §7 PROVEN — routing, twice, live |
| What has not been proven? | §7 UNPROVEN — **no design artifact, no file ever written in a live run** |
| Why are we running A3? | §8 — conditions 2/3/4 of Test A are untested; the baseline has a shelf life |
| What exactly should I do next? | §9 operational procedure, §14 first command |
| What must I not do? | §11, plus §12's authority order |
| Who decides? | §12 — the human, always |
| How does something become a rule? | §13 — four qualification tests, then human approval |

**Nothing above depends on the prior Claude conversation.** Where a fact could not be verified from the repository — A1 and A2 artifacts live on other machines — §6 says so explicitly rather than presenting reconstruction as record.

**Deliberately not included:** an architectural roadmap, a redesign proposal, a skill spec, or any new machinery. The repository does not need more structure. It needs a run.

---

*Handoff prepared by inspecting the repository and its full git history at `d4c9bbb`. No frozen-core file was modified. `check.py` 7/7 PASS · `validate.py --self-test` 21 guards PASS.*
