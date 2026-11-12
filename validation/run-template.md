# VALIDATION RUN

> Copy this file to `validation/runs/<id>.md` and fill it in as you go.
> Reconstructed notes are optimistic. The procedures live in
> [the validation protocol](../tests/validation-protocol.md); this file records
> what actually happened, not what should have happened.

## Run

| Field | Value |
|---|---|
| **Run ID** | `<A1 \| B1 \| B2 …>` |
| **Date** | `<YYYY-MM-DD>` |
| **Ariadne version** | `<version / commit>` |
| **Test** | `<A \| B \| C>` |
| **Project type** | `<one line: what was actually built>` |
| **Mode** | `<client-or-portfolio \| product-app \| game-experiment \| content-system \| audit-review>` |
| **Provider** | `<the host tool>` |
| **Model** | `<the model actually used, per stage if it varied>` |
| **Started** | `<time>` |
| **Ended** | `<time>` |
| **Result** | `<PASS \| PARTIAL \| FAIL \| UNPROVEN>` |

**Stages reached:** `<S0 → …>`
**Raw evidence kept at:** `<transcripts, screenshots, the project repository>`

---

## Baseline

> Capture this before running Ariadne, from the same brief, without opening an
> Ariadne file. A baseline written afterwards is not a control.

**Captured before opening Codex:** `<yes>`

**My unprompted first direction:**

`<layout, type, colour, and the first three moves you would make>`

**Time spent on the baseline:** `<minutes>`

### After the run — comparison

| | Baseline | Ariadne |
|---|---|---|
| First direction | | |
| What it rejected | | |
| Signature idea | | |
| Time to a direction | | |

**What changed, and which mechanism caused it:** `<name the rule, or "nothing changed">`

**Honest read:** `<better, the same, or worse>`

---

## Events

> Append as events happen. Every row needs an evidence reference: an event with
> no evidence is a memory, and the checker rejects it.
>
> A `QUESTION` row must carry `class A/B/C`. Class **B** is a question Ariadne
> should already have answered, and it is the primary handoff metric.

| Type | Stage | What happened | Evidence | Expected? | Importance |
|---|---|---|---|---|---|
| VALUE | S1 | `<example row — delete>` | `transcript:L42` | no | high |
| QUESTION | S4 | `<build session asked X — class B>` | `transcript:L88` | no | high |

**Types:** VALUE · FRICTION · FAILURE · DECISION · INTERVENTION · RESTART · GATE · QUESTION · DEVIATION

---

## Metrics

> The checker derives the MEASURED counts. Fill in only what it cannot observe.

**MEASURED** *(derived by the checker — do not hand-edit)*

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

> The review is evidence only if the boundary actually held.

| Check | Held? |
|---|---|
| Implementation session had no design conversation | `<yes/no>` |
| Reviewer received only URL + success criteria | `<yes/no>` |
| Reviewer did not receive DESIGN / HANDOFF / AGENTS / PROJECT | `<yes/no>` |
| Reviewer was a genuinely separate session | `<yes/no>` |

**If any answer is "no", the review findings are contaminated; report that rather than the findings.**

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

### Remaining unknowns
<>

### Recommendation

**Did this run produce enough evidence to change Ariadne?**

`<NO — FREEZE>` or `<YES — smallest change: …>`

> One occurrence is rarely enough. "Freeze" is the expected answer after a first run.
