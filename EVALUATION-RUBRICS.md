# EVALUATION RUBRICS

The judgement half of S5. Five lenses, each a different person with different priorities, who disagree on purpose.

Also the whole deliverable in [audit / review](modes/audit-review.md) mode.

---

## Two rules that make this work

**1. Independence.** A lens runs in a session that **did not build the work and has not read [QA-POLICY.md](QA-POLICY.md)**. Give it the deployed URL and the success criteria from `PROJECT.md`. Nothing else — not the design document, not the constraints, not the story.

A reviewer holding build context defends the build: it knows why every compromise happened. That sympathy is exactly what the audience will not have.

**2. Anchored scoring.** Every score below 4 must cite **a specific comparison** — a named reference, a competitor, or a prior version — that does this better, and say how.

This is the fix for the failure mode that destroys rubrics: a model scoring its own work clusters at 4, and a scorecard that always returns 44/50 measures nothing except your willingness to feel finished. **A score with no comparison is not a score.**

---

## Scoring

| Score | Meaning | What it looks like |
|---|---|---|
| **1** | Absent or harmful | The criterion was not considered. Default framework output. |
| **2** | Weak; a reviewer raises it unprompted | Considered once, then abandoned. Inconsistent application. |
| **3** | **Competent. Nothing wrong, nothing memorable.** | Correct choices, no argument. **This is the AI default and the score to fear.** |
| **4** | Strong; clearly considered | A decision was made and held throughout. You can name the reason. |
| **5** | Exceptional; would be cited as an example | Someone would screenshot this and send it to a colleague. |

**Most AI-assisted work is a 3 across the board.** A rubric returning straight 3s is telling you the work is forgettable, not that it is fine.

### Evidence, required below 4

Three parts: **where** (route, element, viewport) · **what** (the observation) · **against what** (the comparison).

- Useless: "Typography could be stronger."
- Usable: "Home hero, 1280px: 48px display against 16px body is a 3.0x ratio. [DESIGN-TASTE.md](DESIGN-TASTE.md) 2.3 requires 4x minimum. Burocratik runs roughly 10x on its index. Reads as a template. **Score 2.**"

### Fix, required on every finding

What to change · roughly what it costs · what it risks. A finding without a fix is a complaint.

### Severity

**Blocking** · **Major** · **Minor** · **Note** — same definitions as [QA-POLICY.md](QA-POLICY.md).

### Output, per lens

```
LENS: <name>
Score:    <total>/<max>
Verdict:  Ship | Ship with fixes | Do not ship | Rebuild the direction
Blocking: <list, or none>
The one thing: <the single highest-leverage change>
Would I <the lens's test question>? <yes/no + one sentence>
```

**The one thing is mandatory.** If everything is important, nothing is — a list of twelve equal findings gets ignored.

---

## 1. Creative director

*Is there an idea here, and is it executed?* **The default lens.** Run it on everything with a visual surface. This is also the visual-quality scorecard — there is not a separate one.

| # | Criterion | 2 | 4 |
|---|---|---|---|
| 1 | **Concept clarity** | A thesis exists in the document, not in the work | Visible in every decision |
| 2 | **Typography** | Considered face, safe 2-3x scale | Distinctive face, 4x+ contrast, real scale |
| 3 | **Composition** | Grid present, some hierarchy | Asymmetric, deliberate breaks, strong hierarchy |
| 4 | **Colour discipline** | One accent, safe neutrals | Motivated palette with a stated source |
| 5 | **Material quality** | Some texture or treatment | Consistent material logic throughout |
| 6 | **Motion purpose** | Functional but generic | Choreographed, characterful, reduced-motion designed |
| 7 | **Signature moment** | Present but quiet | Genuinely memorable, survives mobile |
| 8 | **Anti-generic** | 1-2 undeclared violations | Zero, or all declared as accepted patterns |
| 9 | **Craft** | Mostly consistent | Every value from the system |
| 10 | **Originality** | Recognisably a genre | Recognisably its own |

**Max 50.** Below 30: rebuild the direction. 30-39: ship with fixes. 40+: ship.

**Any criterion at 1 is Blocking regardless of total.** A 45 with no signature moment is a failure, not a pass.

Test: *Would I put this in the studio's showreel?*

## 2. Portfolio reviewer

*Does this help or hurt the person who made it, and do their decisions hold up?* Assumes 60 seconds of attention and a hundred other portfolios.

| # | Criterion | Looking for |
|---|---|---|
| 1 | Memorability | Recallable a day later |
| 2 | Positioning | Clear what this person is good at |
| 3 | Curation | Fewer, stronger. **The weakest piece sets the perceived level.** |
| 4 | Depth of proof | Process and thinking visible, not just finished screens |
| 5 | Writing | Case studies explain **decisions**, not features |
| 6 | Conceptual rigour | The idea holds up when pushed |
| 7 | Justification | Every major decision survives three "why?"s |
| 8 | Risk | Attempted something that could have failed |

**Max 40.** Below 24: rework before sending anywhere. 24-31: usable, not competitive. 32+: competitive.

Test: *Would I shortlist this, among a hundred others?*

This lens is entitled to say the work is **competent and pointless.** That verdict is the most useful thing it produces, because it points at S3 rather than at polish — and it is the one no other lens will say out loud.

## 3. Strict client

*Did I get what I paid for?* Deliberately unsympathetic.

| # | Criterion | Looking for |
|---|---|---|
| 1 | Brief satisfaction | Every stated requirement met |
| 2 | Business communication | A visitor understands the offer and why it matters |
| 3 | Credibility | Looks like a real, serious organisation |
| 4 | Differentiation | Does not look like the competitor's site |
| 5 | Content quality | Real copy, real specifics, no filler |
| 6 | Completeness | No placeholders, no dead links, no "coming soon" |
| 7 | Cross-device | Works on the client's own phone |
| 8 | Handover | The client can maintain or hand off what they own |

**Max 40.** Below 28: do not present. 28-34: fix first. 35+: present.

Test: *Would I pay the second invoice?*

## 4. Senior product designer

*Does it work for a person trying to do something?* Primary lens for product app mode.

| # | Criterion | Looking for |
|---|---|---|
| 1 | Task clarity | The primary action is obvious within seconds |
| 2 | Information architecture | Grouping matches mental models, not database tables |
| 3 | State design | Empty, loading, error, success all designed |
| 4 | Feedback | Every action visibly acknowledged |
| 5 | Error recovery | Mistakes are cheap and reversible |
| 6 | Cognitive load | No screen asks for more than it needs |
| 7 | Consistency | The same thing behaves the same way everywhere |
| 8 | Progressive disclosure | Complexity revealed on demand |

**Max 40.** Below 24: not usable. 24-31: fix before real users. 32+: ship.

Test: *Could someone complete the core task without being told how?*

## 5. Frontend engineer

*Does this behave like a robust frontend in use?* This is an external,
rendered-product lens. Do not infer source structure, component boundaries, or
maintainability from the interface; those checks belong to the mechanical half
in [QA-POLICY.md](QA-POLICY.md).

| # | Criterion | Looking for |
|---|---|---|
| 1 | State stability | Repeated interactions do not leave stale, contradictory, or broken states |
| 2 | Visual-system consistency | Repeated controls and patterns render and behave consistently |
| 3 | Responsive integrity | Core paths remain coherent across supplied desktop and narrow viewports |
| 4 | Feedback and recovery | Actions, errors, retries, and disabled states are legible and recoverable |
| 5 | Perceived performance | Loading, transition, and input response do not visibly fight the task |
| 6 | Keyboard and focus | Core paths remain understandable and operable without pointer-only assumptions |

**Max 30.** Below 18: refactor before extending. 18-23: acceptable. 24+: good.

Test: *Can I repeat the core path across the supplied viewports without visible
state, interaction, or system-consistency failures?*

---

## Which lenses per mode

| Mode | Lenses |
|---|---|
| Client site | Creative director, **Strict client** |
| Portfolio | Creative director, **Portfolio reviewer** |
| Product app | **Senior product designer**, Frontend engineer |
| Game / experiment | Creative director (light) |
| Audit / review | Whichever the request named |

## Writing editorial lens

Use this lens in the independent review session for a non-SOCIAL writing
intent. It supplements the general reviewer rules above and does not replace
them.

| Intent | Review criteria |
|---|---|
| General | Purpose, audience fit, clarity, specificity, structure, coherence, prose quality, rhythm, padding, genericness, unsupported claims |
| CREATIVE | Voice, specificity, imagery, pacing, subtext, narrative judgment, cliche avoidance |
| ACADEMIC | Prompt adherence, thesis/argument, reasoning, evidence, synthesis, counterargument, academic register, citation integrity |
| SCIENTIFIC | Claim discipline, evidence fidelity, uncertainty, methodological precision, reproducibility, causal discipline, terminology, structure |
| HUMAN-DRAFT TRANSFORMATION | Voice preservation, idea preservation, structural improvement, unnecessary rewriting, homogenisation, authorial intent |

The reviewer receives the final artifact, original draft when applicable,
intent, audience, purpose and success criteria. It does not receive the
drafting rationale as proof. Each finding names location, severity, why it
matters and the smallest useful revision; unknown evidence remains unknown.

**Two lenses is right. Four is a lot.** Beyond that the output gets long and nothing gets acted on.

## Consolidating

1. **Blocking findings first** — every one stops G3.
2. **Majors ranked by how many lenses raised them.** Something two lenses independently noticed is real.
3. **Name conflicts** rather than resolving them silently. The mode decides.
4. **Do not average across lenses.** The average of several perspectives is the statistical centre — precisely what this system exists to avoid producing.

## Evaluating "feel"

Run the **five-second** and **swap** tests from [DESIGN-TASTE.md](DESIGN-TASTE.md) section 6, plus a third:

- **Recall test** — describe it tomorrow without looking. What survives? Usually one thing. Sometimes none.

**If all three fail, the work is competent and forgettable, and polish will not fix it.** That is an S3 problem surfacing at S5, and the honest recommendation is to restart the direction (**R-INT-1**, [ROUTER.md](ROUTER.md) section 11).
