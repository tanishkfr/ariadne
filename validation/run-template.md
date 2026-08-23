# VALIDATION RUN

> Copy to `validation/runs/<id>.md` and fill in **as you go**. Reconstructed notes are optimistic.
> This is the only file you maintain per run. The benchmark table is generated from these.
>
> The procedures live in [tests/validation-protocol.md](../tests/validation-protocol.md) —
> this file records what actually happened, not what should.

## Run

| Field | Value |
|---|---|
| **Run ID** | `<A1 \| B1 \| B2 …>` |
| **Date** | `<YYYY-MM-DD>` |
| **Ariadne version** | `<v0.3.3 / commit>` |
| **Test** | `<A \| B \| C>` |
| **Project type** | `<one line — what you actually built>` |
| **Mode** | `<client-or-portfolio \| product-app \| game-experiment \| content-system \| audit-review>` |
| **Provider** | `<Codex \| Cursor \| Claude \| mixed>` |
| **Model** | `<the model actually used, per stage if it varied>` |
| **Started** | `<time>` |
| **Ended** | `<time>` |
| **Result** | `<PASS \| PARTIAL \| FAIL \| UNPROVEN>` |

**Stages reached:** `<S0 → … >`
**Raw evidence kept at:** `<paths to transcripts, screenshots, the project repo>`

---

## Baseline

> **Captured before running Ariadne.** Write this first, from the same brief, without
> opening any Ariadne file. A baseline written afterwards is not a control — you will
> have already seen the answer.

**Captured before opening Codex:** `<yes>`

> Answer `yes` only if it is true. This is the one thing the harness cannot infer,
> and the entire control rests on it. The checker fails the run until it says yes.

**My unprompted first direction:**

<what you would have done — be specific enough to compare: layout, type, colour, the
first three moves you would make>

**Time spent on the baseline:** `<minutes>`

### After the run — comparison

| | Baseline | Ariadne |
|---|---|---|
| First direction | | |
| What it rejected | | |
| Signature idea | | |
| Time to a direction | | |

**What changed, and which mechanism caused it:** <name the rule, or "nothing changed">

**Honest read:** <was the Ariadne version actually better, the same, or worse? "The same"
is a valid and important result.>

---

## Events

> Append as they happen. **Every row needs an evidence reference** — a transcript line, a
> file, a screenshot. An event with no evidence is a memory, and the checker rejects it.
>
> `QUESTION` rows **must** carry `class A/B/C`:
> **A** = a genuinely unresolved human decision · **B** = information Ariadne should
> already have supplied · **C** = legitimately unavailable.
> **B is the primary handoff metric.** Do not classify a real open decision as B.

| Type | Stage | What happened | Evidence | Expected? | Importance |
|---|---|---|---|---|---|
| VALUE | S1 | `<example row — delete>` | `transcript:L42` | no | high |
| QUESTION | S4 | `<build session asked X — class B>` | `transcript:L88` | no | high |

**Types:** VALUE · FRICTION · FAILURE · DECISION · INTERVENTION · RESTART · GATE · QUESTION · DEVIATION

---

## Metrics

> The checker computes the counts. Fill in only what it cannot see.

**MEASURED** *(the checker derives these — do not hand-edit)*

**OBSERVED**

| | |
|---|---|
| Wall-clock, total | `<>` |
| Wall-clock by stage | `<S1 … S3 … S4 …>` |
| Documents created | `<>` |
| Documents actually reopened | `<the honest number>` |
| Times you searched Ariadne docs | `<each one is friction>` |

**HUMAN-JUDGED** *(never aggregated into a score)*

| | |
|---|---|
| Did the implementation stay faithful to the thesis? | `<>` |
| Did QA catch something the build session missed? | `<>` |
| Did the independent reviewer find something meaningful? | `<>` |
| Would you have shipped the baseline version? | `<>` |

---

## Independence

> The boundary that makes the review worth anything. Record whether it actually held.

| Check | Held? |
|---|---|
| Implementation session had no design conversation | `<yes/no>` |
| Reviewer received **only** URL + success criteria | `<yes/no>` |
| Reviewer did **not** receive DESIGN / HANDOFF / AGENTS / PROJECT | `<yes/no>` |
| Reviewer was a genuinely separate session | `<yes/no>` |

**If any is "no", the review findings are contaminated — say so in the report rather than reporting them as evidence.**

---

## Report

### Result
`<PASS | PARTIAL | FAIL | UNPROVEN>`

### What happened
<narrative, short>

### Mechanical evidence
<what the checker reported>

### Human evidence
<what only you could see>

### Value
<moments Ariadne prevented or improved something — empty is a valid result>

### Friction
<moments you thought about Ariadne instead of the project — empty is valid>

### Failures
<what did not work>

### Unexpected behaviour
<things neither expected nor in the rules>

### Evidence-backed changes
<proposals that pass all four qualification tests in templates/RETROSPECTIVE.md — usually none after one run>

### Things that must NOT change yet
<what looked tempting but lacks evidence>

### Remaining unknowns
<>

### Recommendation

**Did this run produce enough evidence to change Ariadne?**

`<NO — FREEZE>` or `<YES — smallest change: …>`

> One occurrence is rarely enough. The learning loop requires a rule to recur, or to have
> cost something you can name in hours. **"Freeze" is the expected answer after a first run.**
