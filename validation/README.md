# VALIDATION HARNESS

Instrument for answering one question: **does Builder OS actually make the work better?**

Not a Builder OS feature. A temporary measuring device, to be deleted if it stops earning its place.

**The procedures live in [tests/validation-protocol.md](../tests/validation-protocol.md).** This directory records what happened when you ran them.

---

## Your entire burden: one file per run

Copy [run-template.md](run-template.md) to `runs/<id>.md`, fill it in as you go, run the checker. **The benchmark table is generated — never hand-maintained.**

```bash
python scripts/validate.py --run validation/runs/A1.md --project ../my-project
python scripts/validate.py --benchmark
```

If this ever costs more effort than the thing it measures, it has failed and should be cut.

---

## First run — Test A, with Codex only

**1 · Capture the baseline first.** Before opening any Builder OS file, write into the run file's Baseline section what you would do with *"I want to make something with type that reacts to sound"* — layout, type, colour, your first three moves. **This is the only step that cannot be done later.** Once you have seen the Builder OS direction the control is gone.

**2 · Set up Codex.** A short personal file at `~/.codex/AGENTS.md`: Indian English, pnpm, ask before installing, always end with a NEXT. Preferences only — not policies. *(Known issue: the Codex desktop app may not inject this when a project `AGENTS.md` exists. Note it in the run if the behaviour looks off.)*

**3 · Run it.** Paste `prompts/project-start.md`, replacing the last line with the Test A prompt **verbatim**. Do not add clarification — the vagueness is the test.

**4 · Record the route before doing anything else.** The routing behaviour is the measurement, not the final artifact:

| Capture | Expected |
|---|---|
| `ACTION` | CREATE |
| `OBJECT` | **UNRESOLVED** |
| Confidence | **LOW** |
| Behaviour | one clarifying question with concrete options |
| Mode | **not chosen yet** |
| NEXT | emitted, pointing at `design-direction.md` |

**A confident mode pick here is a high-confidence wrong route — the one failure that must stay at zero.** Log it as `DEVIATION`, importance high, and keep the transcript.

**5 · Follow the chain.** Each stage names the next inside the pasted block. Log events as they happen — you will not remember them afterwards.

**6 · Check it.**

```bash
python scripts/validate.py --run validation/runs/A1.md --project ../type-sound
```

**7 · Fill in the report.** The recommendation must answer: *did this produce enough evidence to change Builder OS?* **After one run the answer is almost always no.**

---

## Test B — when Cursor is available

Same loop, plus the two things Test A cannot reach:

**The forced restart.** At G1, reject the first direction *even if you like it*. Say it in your own words — **"scrap this direction and start over"** — and do not quote any rule. Then record what was preserved and what was discarded. Log a `RESTART` event.

**The handoff count.** Open Cursor, fresh session, paste `build-kickoff.md` part B and nothing else. **Log every question as a `QUESTION` event with class A/B/C.** The B-count is the primary metric, target ≤2. Watch specifically for asset location — the pre-validation simulation flagged it as the likeliest gap.

Then: mechanical QA in Cursor · **independent review in a fresh session with only the URL and success criteria** · retrospective.

---

## Evidence classes — never collapsed

| Class | Meaning |
|---|---|
| **MEASURED** | The checker derived it from files. Reproducible. |
| **OBSERVED** | You watched it. Real, not reproducible. |
| **HUMAN-JUDGED** | Your assessment. Never aggregated into a score. |
| **SIMULATED** | Derived on paper, no provider ran. Not evidence about behaviour. |
| **UNPROVEN** | Nobody has tested it. |

## Why there is no overall score

Every metric the checker computes is a **count of failures** — B-questions, deviations, unnecessary documents. The incentive points at fixing the system.

A "quality score" would point the other way: it would reward a run that *looks* good. Value and friction are counted but **deliberately never summed**, because a number there rewards writing more events rather than building better projects.

**One instance of *"Builder OS made me reject X before I built it, and the replacement was better"* outweighs every count in this directory.**

---

## Raw evidence

Keep transcripts, screenshots and the project repo **outside** this repository — they contain project and client material ([PRIVACY-POLICY.md](../PRIVACY-POLICY.md)). Reference them by path in the run file. Run records here should carry findings, never client content.

## When a run justifies changing Builder OS

Through the loop in [templates/RETROSPECTIVE.md](../templates/RETROSPECTIVE.md), never directly. All four qualification tests must pass, then your approval, then `check.py` plus the router suite if routing was touched.

**A single run is rarely enough.** That is the intended friction — it is what stopped the system regrowing to seventy files.

## What this harness cannot do

Judge design quality · substitute for an independent reviewer · prove provider behaviour without the provider · tell you whether the work is good.

**It measures whether the workflow held. Only you can tell whether the output was worth it.**
