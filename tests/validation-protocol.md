# REAL-WORLD VALIDATION PROTOCOL

Three tests. Test A has multiple recorded runs; Test B B1 is formally closed as
`PASS WITH PROVIDER-QUOTA EVIDENCE EXCEPTION`; Test C has not run. This status
update does not change the procedures below.

Router tests ([router-cases.md](router-cases.md)) prove the rules are internally consistent. They prove **nothing** about document quality, handoff sufficiency, design outcomes, QA effectiveness, or whether any of this saves time.

---

## What every test records

Fill this in **as you go**, not afterwards. Reconstructed notes are optimistic.

| Field | Why |
|---|---|
| Wall-clock per stage | Where the time actually goes |
| Questions asked | Against the cap of 5 |
| Documents created vs **actually reopened** | The only real test of whether a document has a consumer |
| Context loaded, where measurable | Against the budgets |
| **Moments you had to search Builder OS docs** | Every one is friction, and the V1 backlog |
| **Moments Builder OS prevented a bad decision** | Every one is the value, and the reason to keep it |
| Defects caught by the system | |
| Defects the system missed | More informative than the ones it caught |
| Unnecessary ceremony | Documents or steps that produced nothing |
| Proposed changes | Through the retrospective, not by editing files mid-project |

**The two bolded rows matter more than the rest combined.** They are the friction/value ledger, and the honest answer to "is this worth using".

---

## Test A — Tiny experiment · 1 day

**Prompt, verbatim:**

> "I want to make something with type that reacts to sound."

Deliberately vague. Do not add clarification when pasting it — the vagueness *is* the test.

**Expected routing:** `ACTION=CREATE` · `OBJECT=UNRESOLVED` · **LOW** confidence · asks one useful clarifying question with concrete options.

**Fails immediately if** it confidently picks a mode. That is a high-confidence wrong route, the one metric that must stay at zero.

**Documents:** `PROJECT.md` and `DESIGN.md`. **Nothing else** unless the clarified project genuinely needs it. Silent creation of `TASKS.md`, `ASSETS.md`, or `ARCHITECTURE.md` is a **failure**, not a nicety.

**Stages:** S0-S1 → S3 (light) → S4 → light QA. No S2 unless something genuinely blocks.

**Passes when all four hold:**
1. Routed LOW and asked, rather than guessing.
2. Only the two required documents exist.
3. S3 produced a direction with a **named rejection list**, not a mood.
4. The output does not look like your unprompted first attempt at the same brief. **Keep both artifacts side by side** — this comparison is the evidence, and it is the only way to see whether S3 does anything.

---

## Test B — Serious website + forced restart · 1–2 weeks

A **real** project. Do not invent success criteria — use the actual ones.

**Full path:** discovery → research where needed → design direction → **G1** → handoff → **fresh build session** → browser QA → independent review → retrospective.

### The mandatory intervention

**At G1, reject the first direction — even if you like it.** Say it in your own words:

> "scrap this direction and start over"

Do not quote any Builder OS rule. The router must recognise it unaided.

**Restart passes when:** the intent is recognised without special phrasing · only the rejected layer is discarded · **research, references and assets survive** · you are asked which layer restarts · the replacement direction is *actually different*, not the same idea restyled.

### The critical measurement

Hand `HANDOFF.md` to a **fresh build session** — no chat history, no prior context.

**Count every question it asks that `HANDOFF.md` should have answered.**

> **Target: ≤2.** Above that, the handoff template is the problem, and it is the highest-value fix in the system.

This single number is the most informative output of the entire validation program.

### Passes when

- G1 caught something **before** anything was built
- Restart preserved research and produced a genuinely different direction
- Handoff re-derivation count ≤2
- Browser QA caught **at least one real defect the build session missed**
- The independent review produced a finding you acted on
- No unapproved Amber action occurred at any point

---

## Test C — Content system · 3 weeks, in parallel

Runs alongside A and B at near-zero marginal cost. Use [prompts/content-system.md](../prompts/content-system.md).

**Setup once:** voice profile from 10–20 things you have actually written, including the anti-voice list. Content pillars — drop any you cannot supply a personal instance for.

**Then:** 6–8 real posts over three weeks. **You post them.** Nothing publishes automatically, ever.

**Do not fabricate analytics.** Paste in real numbers or record that none are available.

**Passes when:**
- `CONTENT-LEARNINGS.md` changed **at least twice** from real analytics
- **At least one pattern was refused promotion** for having only two occurrences

That refusal is the evidence the loop is honest rather than superstitious. **A loop that only ever adds rules is the 71-file failure returning in miniature.**

**Fails if** every weekly review produces a new rule, or no review produces anything.

---

## Design-quality evidence

**Do not score the project and call that proof.** Self-scoring clusters at 4 and measures willingness to feel finished — a failure this system already had once.

For Test B, the **independent reviewer** (fresh session, given only the URL and success criteria) answers these ten. Comparison and reasoning, not numbers:

1. What is the closest generic version of this?
2. Which anti-generic failure mode was most likely here?
3. What specifically prevented it?
4. Can the thesis be seen in the **actual artifact**, not the document?
5. Name three implementation decisions that would change if the thesis changed. *Fewer than three means the thesis never reached the work.*
6. What real reference does this compete with?
7. What does that reference do better?
8. Is there a memorable signature moment?
9. Does the mobile experience preserve the intended idea?
10. What would you remove given one more hour?

### The evidence that actually counts

Not: *"Builder OS scored 43/50."*

But: **"Builder OS caused us to reject X before implementation, and the replacement was demonstrably better."**

**One instance of that is worth more than every passing scorecard.** If three real projects produce zero such instances, the anti-generic apparatus is decoration and should be cut back to the four rules that are mechanically checkable — the 4× type ratio, the five motion purposes, the research-only library default, and the three-reference minimum.

---

## After the tests

Run [prompts/retrospective.md](../prompts/retrospective.md) on each. Proposals go through approval; nothing edits Builder OS directly.

Then decide, with evidence rather than impression:

| Question | Evidence |
|---|---|
| Is the output measurably less generic? | Test A's side-by-side comparison |
| Did the process cost more than it returned? | Time per stage |
| Which documents did you reopen? | The created-vs-used column |
| Which were written and never opened again? | **Delete them.** |
| Which gates were useful, and which always got waived? | The gate log |
| Did the tool split conserve usage? | Limits hit, and at which stage |

**If it is not working, it is more likely too heavy than too light. Cut first, add second.**

### The success criterion, set now

> **At least one piece of work exists that would not have been as good without this system — and you can name the specific rule that made the difference.**

If you cannot name the rule, the system did not do it. Anything else is confirmation bias, which is exactly what a validation program exists to prevent.

---

## Runtime state simulation

**SIMULATED — REQUIRES CODEX/CURSOR.** Traced against the written prompts and the
`AGENTS.md` template on 2026-08-21. This is not provider validation; it proves the
state mechanism is internally unambiguous, not that any tool honours it.

For each transition: (1) is current state unambiguous, (2) is next stage unambiguous,
(3) is the next prompt known, (4) does `AGENTS.md` hold enough for a fresh session,
(5) is conversation history required, (6) do canonical documents stay canonical.

| Transition | Who writes state | Result |
|---|---|---|
| S0 → S1 | S1 session generates `AGENTS.md` | **PASS** — Project section filled; Approved direction explicitly pending |
| S1 → S3 | no write needed | **PASS** — next prompt named in the NEXT block |
| S3 → G1 | **nothing written** | **PASS** — deliberate. `DESIGN.md` exists but G1 shows pending, so a fresh session presents it rather than building from it. |
| G1 reject → S3 | nothing to unwind | **PASS** — this is why S3 does not write. A rejected direction never claimed a gate. |
| G1 approve → S4 | **you paste the block** | **PASS** — manual by design; an agent must not record a gate it did not receive |
| S4 → S5 | S4 session, both ends | **PASS** — constraints at part A, state at part B |
| S5 → S6 | **you, at G3** | **PASS with a caveat** — the reviewer is forbidden from touching `AGENTS.md`, so between G3 and the retrospective the stage still reads S5. Documented as expected rather than patched with another mechanism. |
| S6 → done | S6 session closes out | **PASS** |

**7 transitions · 7 pass · 0 fail · 1 documented caveat.**

**Two deliberate manual writes:** G1 and G3. Both are gates, and a gate an agent
records for itself is not a gate. The cost is two paste operations per project.

**Fresh-session readiness at every point:** a session opening the repo cold reads
`AGENTS.md` for stage and gate, `HANDOFF.md` for implementation truth, `PROJECT.md`
and `DESIGN.md` for decisions. **No transition requires conversation history.**

**What this does not prove:** that Codex or Cursor actually load `AGENTS.md` as
documented, that an agent reliably updates the state block before ending a session,
or that the file stays small in practice. All three require the real environment.
