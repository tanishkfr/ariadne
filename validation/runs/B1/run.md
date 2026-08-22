# VALIDATION RUN — B1

> Prepared from the existing Test B procedure in
> [tests/validation-protocol.md](../../../tests/validation-protocol.md).
> Record events as they happen. Do not reconstruct provider evidence afterwards.

## Run

| Field | Value |
|---|---|
| **Run ID** | `B1` |
| **Date** | `2026-08-22` |
| **Builder OS version** | `a3cb65f731ab49c7c5ebcb559da9e36fb58f8617` at B1 packet generation; closure recorded from maintainer checkout `06d290655cd5e0e575b59fc0354591a94260d2bc` |
| **Test** | `B` |
| **Project type** | `single-page independent-cinema programme website` |
| **Mode** | `client-or-portfolio` |
| **Provider** | `Codex for S1/S3/S4A; Cursor for S4B` |
| **Model** | `Codex model not recorded in B1 evidence; Cursor used Grok 4.6 Medium per project-owner judgement` |
| **Started** | `2026-08-22` |
| **Ended** | `2026-08-23 — closed by project-owner decision` |
| **Result** | `PASS` |
| **Closure status** | `PASS WITH PROVIDER-QUOTA EVIDENCE EXCEPTION` |

**Stages reached:** `S1 → S3 → forced S3 restart → S4A → S4B implementation started; provider quota ended the run before completion`

**Project:** `C:\Users\snprasad\Builder OS Tests\afterimage-B1`

**Raw evidence:** `C:\Users\snprasad\Builder OS Tests\afterimage-B1-validation`

**Input brief:** `C:\Users\snprasad\Builder OS Tests\afterimage-B1-validation\brief.txt`

---

## Baseline

**Captured before opening Codex:** `yes`

**My unprompted first direction:**

Without Builder OS, I would probably make this as an editorial film-programme website: a large cinematic hero for the featured film, strong typography, a dark or muted palette, film information arranged around the hero, and a scrolling programme underneath. I would probably use subtle image or text transitions and a fairly art-directed layout, but I would not yet have a specific interaction or visual system in mind.

**Time spent on the baseline:** `<not supplied>`

### After the run — comparison

| | Baseline | Builder OS |
|---|---|---|
| First direction | `<fill after the run>` | `<fill after the run>` |
| What it rejected | `<fill after the run>` | `<fill after the run>` |
| Signature idea | `<fill after the run>` | `<fill after the run>` |
| Time to a direction | `<fill after the run>` | `<fill after the run>` |

**What changed, and which mechanism caused it:** `<fill after the run>`

**Honest read:** `<fill after the run>`

---

## Events

| Type | Stage | What happened | Evidence | Expected? | Importance |
|---|---|---|---|---|---|
| QUESTION | S1 | class A — primary visitor and arrival context | `afterimage-B1-validation/B1-S1/evidence/transcript.md:L640` | yes | medium |
| QUESTION | S1 | class A — available programme material and assets | `afterimage-B1-validation/B1-S1/evidence/transcript.md:L643` | yes | medium |
| QUESTION | S1 | class A — minimum scope if implementation time were halved | `afterimage-B1-validation/B1-S1/evidence/transcript.md:L646` | yes | medium |
| QUESTION | S1 | class A — intended memory and differentiation benchmarks | `afterimage-B1-validation/B1-S1/evidence/transcript.md:L649` | yes | medium |
| QUESTION | S1 | class A — approval, timing, budget, and browser constraints | `afterimage-B1-validation/B1-S1/evidence/transcript.md:L652` | yes | medium |
| VALUE | S1 | Routed the concrete website brief to `client-or-portfolio` and produced the project intake state after the defaults were accepted. | `afterimage-B1-validation/B1-S1/evidence/transcript.md:L634`; `PROJECT.md`; `AGENTS.md` | yes | high |
| GATE | S3 | The first direction reached G1 and was approved before the mandatory intervention. | `afterimage-B1-validation/B1-S3/evidence/transcript.md:L89-L103` | yes | high |
| RESTART | S3 | The owner rejected the first direction; the direction layer restarted without starting implementation, and a genuinely different replacement was produced. | `afterimage-B1-validation/B1-S3/evidence/transcript.md:L157-L222` | yes | high |
| GATE | S3 | The project owner approved and locked the replacement direction, The Borrowed Edge. | `afterimage-B1-validation/B1-S3/evidence/transcript.md:L224-L242` | yes | high |
| VALUE | S4A | A fresh-stage handoff was created and the canonical S4B carry-forward inputs were named. | `afterimage-B1-validation/B1-S4A/evidence/transcript.md:L43-L56`; `B1-S4A/manifest.json` | yes | high |
| VALUE | S4 | The verified S4B packet reached a fresh Cursor session; per the separate project-owner judgement, the provider understood the project and began implementation without re-explanation. No missing provider transcript was reconstructed. | `validation/runs/B1/CLOSURE.md`; `B1-S4B/manifest.json` | yes | high |
| FRICTION | S4 | Cursor Hobby/Grok 4.6 Medium exhausted its available Agent usage before implementation, QA, and return handoff completed. | `validation/runs/B1/CLOSURE.md` | no | high |
| DECISION | S6 | The project owner closed B1 as PASS WITH PROVIDER-QUOTA EVIDENCE EXCEPTION and authorised V1 hardening to proceed without another Cursor run. | `validation/runs/B1/CLOSURE.md` | no | high |

**Types:** VALUE · FRICTION · FAILURE · DECISION · INTERVENTION · RESTART · GATE · QUESTION · DEVIATION

For Test B, every `QUESTION` event must include `class A`, `class B`, or `class C`.
The mandatory G1 restart must be recorded as a `RESTART` event before any S4/S4B event.

---

## Metrics

**MEASURED:** generated by `scripts/validate.py`; do not hand-edit.

**OBSERVED**

| | |
|---|---|
| Wall-clock, total | `<unfilled>` |
| Wall-clock by stage | `<unfilled>` |
| Documents created | `<unfilled>` |
| Documents actually reopened | `<unfilled>` |
| Times Builder OS docs were searched | `<unfilled>` |

**HUMAN-JUDGED**

| | |
|---|---|
| Did the implementation stay faithful to the thesis? | `Partially observed by the project owner before quota exhaustion; final fidelity was not reviewed.` |
| Did QA catch something the build session missed? | `Not observed — final Cursor QA did not occur.` |
| Did the independent reviewer find something meaningful? | `Not observed — independent review was not reached.` |
| Would you have shipped the baseline version? | `Not judged in the closure evidence.` |

---

## Independence

| Check | Held? |
|---|---|
| Implementation session had no design conversation | `yes — fresh S4B packet/session boundary` |
| Reviewer received only URL + success criteria | `not reached` |
| Reviewer did not receive DESIGN / HANDOFF / AGENTS / PROJECT | `not reached` |
| Reviewer was a genuinely separate session | `not reached` |

---

## Report

### Result

`PASS WITH PROVIDER-QUOTA EVIDENCE EXCEPTION`

### What happened

B1 progressed through S1, S3, the mandatory forced restart, S4A, and into S4B.
The fresh Cursor session consumed the generated handoff and began implementation.
Cursor Hobby/Grok 4.6 Medium then exhausted its available Agent usage. The
project owner closed the test with the evidence exception recorded separately
in `CLOSURE.md`.

### Mechanical evidence

- S1, S3, and S4A transcripts are preserved under the B1 evidence root.
- The S4B packet and manifest verify successfully against their recorded
  canonical sources and B1-S4A parent hashes.
- The S4B transcript path is absent. No transcript was fabricated.
- The exact S4B question count, full implementation, final QA, fidelity review,
  and return handoff remain unmeasured or unobserved.

### Human evidence

The project-owner judgement records that Cursor/Grok 4.6 Medium understood the
Afterimage project, began implementation in the intended project, and did not
require the project to be re-explained before quota exhaustion. This evidence
is not represented as a provider transcript or as proof of completion.

### Value

The S4B handoff mechanism demonstrated practical viability across the
Codex-to-Cursor boundary. The replacement S3 direction and project state were
usable by a fresh implementation provider without carrying the design
conversation.

### Friction

Packet discovery, generation, document transport, transcript location,
continuation setup, and transition discovery required repeated operator work.
The provider quota limitation was discovered during implementation rather than
before assigning the large task.

### Failures

No Builder OS handoff, routing, or implementation defect was established. The
external provider quota ended the run before full implementation, QA,
independent review, and return handoff.

### Unexpected behaviour

The Cursor-to-Codex return handoff remains unverified. The surviving evidence
does not support reconstructing an exact S4B question count.

### Evidence-backed changes

See `CLOSURE.md` for the five project-owner requirements to carry into V1
hardening. They are retrospective inputs, not implemented policy changes.

### Things that must NOT change yet

Do not redesign the viable S4B handoff without a concrete weakness. Do not
change canonical policies from this closure alone. Do not rewrite missing
Cursor evidence or infer implementation completion.

### Remaining unknowns

- Full Cursor implementation completion.
- Final Cursor QA and independent fidelity review.
- Cursor-to-Codex return-handoff execution.
- Exact S4B handoff re-derivation question count.

### Recommendation

`YES — close Test B and proceed to V1 hardening under the recorded provider-quota evidence exception.`
