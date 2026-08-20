# EVALUATION RUBRICS

Nine lenses for looking at finished work. Each is a different person with different priorities, and they disagree with each other on purpose.

Used at S5 ([WORKFLOW.md](WORKFLOW.md)) and as the whole deliverable in audit/review mode ([modes/audit-review.md](modes/audit-review.md)).

**Independence rule:** a lens runs in a session that did not build the work. A reviewer with build context defends the build. Give the reviewer the URL and the success criteria from `PROJECT.md` — nothing else.

---

## Shared mechanics

These apply to every lens. They are stated once here rather than repeated nine times.

### Scoring

| Score | Meaning |
|---|---|
| **1** | Absent or actively harmful |
| **2** | Present but weak; a reviewer would raise it unprompted |
| **3** | Competent. Nothing wrong, nothing memorable. **This is the AI default and the score to fear.** |
| **4** | Strong. Clearly considered. |
| **5** | Exceptional. Would be cited as an example. |

Most AI-assisted work scores 3 across the board. A rubric that returns straight 3s is telling you the work is forgettable, not that it is fine.

### Severity

**Blocking** (cannot ship) · **Major** (fix or waive in writing) · **Minor** (polish) · **Note** (observation). Same definitions as [QA-POLICY.md](QA-POLICY.md) section 2.

### Evidence requirement

Every score below 4 requires: **where** (route, element, viewport), **what** (the specific observation), **why** (which criterion it fails). 

- Useless: "Typography could be stronger."
- Usable: "Home hero, 1280px: display type at 48px against 16px body is a 3x ratio; [DESIGN-TASTE.md](DESIGN-TASTE.md) 2.3 requires extreme contrast. Reads as a template."

A score without evidence is an opinion, and opinions do not survive disagreement.

### Fix format

Every finding carries a fix: what to change, roughly what it costs, and what it risks. A finding without a fix is a complaint.

### Final recommendation

Every lens ends with exactly this:

```
LENS: <name>
Score:    <total>/<max>  (<n> criteria)
Verdict:  Ship | Ship with fixes | Do not ship | Rebuild the direction
Blocking: <list, or none>
The one thing: <the single highest-leverage change>
Would I <lens-specific test>? <yes/no + one sentence>
```

**The one thing** is mandatory. If everything is important, nothing is, and a list of twelve equal findings gets ignored.

---

## 1. Creative director

*Is there an idea here, and is it executed?* The default lens. Run it on everything with a visual surface.

| # | Criterion | Looking for |
|---|---|---|
| 1 | Concept | A thesis visible in the work, not just in the document |
| 2 | Execution consistency | The idea applied everywhere, not in one hero section |
| 3 | Typography | Distinctive face, real scale, extreme contrast |
| 4 | Composition | Asymmetry, deliberate grid breaks, hierarchy |
| 5 | Colour and material | Motivated palette, consistent treatment |
| 6 | Motion | Choreographed and characterful, not decorative |
| 7 | Signature moment | Something a person would describe to someone else |
| 8 | Originality | Not recognisably a reference or a genre |

Max 40. **Below 24: rebuild the direction. 24-31: ship with fixes. 32+: ship.**

Test: *Would I put this in the studio's showreel?*

---

## 2. Senior product designer

*Does it work for a person trying to do something?* Primary lens for product app mode.

| # | Criterion | Looking for |
|---|---|---|
| 1 | Task clarity | The primary action is obvious within seconds |
| 2 | Information architecture | Grouping matches user mental models, not database tables |
| 3 | State design | Empty, loading, error, success all designed |
| 4 | Feedback | Every action visibly acknowledged |
| 5 | Error recovery | Mistakes are cheap and reversible |
| 6 | Cognitive load | No screen asks for more than it needs |
| 7 | Consistency | The same thing behaves the same way everywhere |
| 8 | Progressive disclosure | Complexity revealed on demand |

Max 40. **Below 24: not usable. 24-31: fix before real users. 32+: ship.**

Test: *Could someone complete the core task without being told how?*

---

## 3. Strict client

*Did I get what I paid for?* Deliberately unsympathetic. Primary lens for premium client website mode.

| # | Criterion | Looking for |
|---|---|---|
| 1 | Brief satisfaction | Every stated requirement met |
| 2 | Business communication | A visitor understands what is offered and why it matters |
| 3 | Credibility | Looks like a real, serious organisation |
| 4 | Differentiation | Does not look like the competitor's site |
| 5 | Content quality | Real copy, real specifics, no filler |
| 6 | Completeness | No placeholders, no dead links, no "coming soon" |
| 7 | Cross-device | Works on the client's own phone |
| 8 | Handover readiness | The client can maintain or hand off what they own |

Max 40. **Below 28: do not present to the client. 28-34: fix first. 35+: present.**

Test: *Would I pay the second invoice?*

---

## 4. Accessibility reviewer

*Who has been excluded?* Findings here are frequently Blocking. See [skills/accessibility.md](skills/accessibility.md).

| # | Criterion | Looking for |
|---|---|---|
| 1 | Keyboard | Every flow completable; visible focus; no traps |
| 2 | Screen reader | Meaningful structure, labels, announcements |
| 3 | Contrast | Measured on rendered pixels; 4.5:1 body, 3:1 large/UI |
| 4 | Motion | Reduced-motion is a designed state, not disabled animation |
| 5 | Structure | One `h1`, no skipped levels, landmarks, alt text |
| 6 | Forms | Labels, errors tied to inputs, errors not colour-only |
| 7 | Targets and zoom | 44px minimum; 200% zoom without loss |
| 8 | Independence | No information conveyed by colour, hover, or motion alone |

Max 40. **Any criterion at 1 is Blocking regardless of total. Below 28: do not ship.**

Test: *Could someone using only a keyboard and a screen reader complete the primary task?*

---

## 5. Frontend engineer

*Would I want to maintain this?*

| # | Criterion | Looking for |
|---|---|---|
| 1 | Type safety | Strict mode honoured; no unexplained `any` |
| 2 | Component design | Sensible boundaries; no 600-line components |
| 3 | Token discipline | Values from the system, not hardcoded one-offs |
| 4 | Dependencies | Justified, documented, minimal ([LIBRARY-POLICY.md](LIBRARY-POLICY.md)) |
| 5 | Correctness | No hydration mismatches, no console errors, no race conditions |
| 6 | Reusability | Repeated patterns extracted; single-use abstractions not invented |
| 7 | Readability | A stranger can follow it in ten minutes |
| 8 | Build health | Production build clean, fast, no ignored warnings |

Max 40. **Below 24: refactor before extending. 24-31: acceptable. 32+: good.**

Test: *Could I add a feature to this in six months without rereading everything?*

---

## 6. Performance reviewer

*What does this cost the person loading it?* Numbers only — no impressions. See [skills/performance.md](skills/performance.md).

| # | Criterion | Looking for |
|---|---|---|
| 1 | LCP | < 2.5s on the preview |
| 2 | CLS | < 0.1 |
| 3 | INP | < 200ms |
| 4 | JS weight | Within the `ARCHITECTURE.md` budget |
| 5 | Images | Sized, modern format, lazy where appropriate |
| 6 | Fonts | Minimal files, no invisible-text flash |
| 7 | Animation cost | 60fps, compositor-only properties |
| 8 | Network | No waterfall, no blocking third parties |

Max 40. **Below 24: Blocking. 24-31: ship with a plan. 32+: ship.**

Test: *Would this be usable on a mid-range Android on 4G?*

---

## 7. Conversion reviewer

*Does it cause the intended action?* Only for work with a business goal. Skip for experiments and most portfolios.

| # | Criterion | Looking for |
|---|---|---|
| 1 | Value clarity | Offer understood within one screen |
| 2 | Primary action | One obvious next step per page |
| 3 | Friction | Nothing unnecessary between intent and action |
| 4 | Trust | Evidence, specifics, real proof rather than claims |
| 5 | Objection handling | The obvious hesitation is addressed |
| 6 | Copy | Specific and concrete, not aspirational filler |

Max 30. **Below 18: reconsider the structure. 18-23: fix. 24+: ship.**

Test: *Would a qualified visitor know what to do next?*

Caution: this lens pulls toward conventional SaaS patterns, which is exactly what [DESIGN-TASTE.md](DESIGN-TASTE.md) rejects. When it conflicts with the creative director lens, the mode decides — premium client work weights conversion, portfolio work weights creative direction.

---

## 8. Portfolio reviewer

*Does this help or hurt the person who made it?* Primary lens for personal portfolio mode. Assumes 60 seconds of attention and a hundred other portfolios.

| # | Criterion | Looking for |
|---|---|---|
| 1 | Memorability | Recallable a day later |
| 2 | Positioning | Clear what this person is good at |
| 3 | Depth of proof | Process and thinking visible, not just finished screens |
| 4 | Curation | Fewer, stronger pieces; the weakest piece sets the perceived level |
| 5 | Craft | Execution quality signals professional standard |
| 6 | Range vs focus | Deliberate, not accidental |
| 7 | Writing | Case studies explain decisions, not features |
| 8 | Signal | Distinguishable from a template portfolio |

Max 40. **Below 24: rework before sending anywhere. 24-31: usable, not competitive. 32+: competitive.**

Test: *Would I remember this tomorrow, among a hundred others?*

---

## 9. Design-school reviewer

*Defend your decisions.* The hardest lens. It ignores polish and interrogates reasoning. Use when you want to be told the uncomfortable thing.

| # | Criterion | Looking for |
|---|---|---|
| 1 | Conceptual rigour | The idea holds up when pushed |
| 2 | Research evidence | The direction came from somewhere, not from taste alone |
| 3 | Process | Iteration and rejected alternatives visible |
| 4 | Justification | Every major decision has a reason beyond preference |
| 5 | Self-awareness | Knows its own weaknesses |
| 6 | Reference literacy | Understands what it borrowed and why |
| 7 | Risk | Attempted something that could have failed |
| 8 | Resolution | Finished, not abandoned at 80% |

Max 40. **Below 24: the concept is not there. 24-31: sound, not distinctive. 32+: strong.**

Test: *If I asked "why?" three times about any decision, would the answers hold?*

This lens is entitled to say the work is competent and pointless. That verdict is the most useful thing it produces — it is the one no other lens will say out loud.

---

## Running a multi-lens review

1. Pick lenses per [QA-POLICY.md](QA-POLICY.md) section 4.3.
2. Run each in a **separate session**. Lenses contaminate each other — a reviewer that just scored accessibility will unconsciously weight it.
3. Collect the recommendation blocks.
4. Consolidate: every Blocking finding, then Majors ranked by how many lenses raised them. A Major flagged by three lenses outranks a Blocking flagged by one in *practice* — but it does not unblock G3.
5. Where lenses conflict, name the conflict and let the mode decide. Do not average scores across lenses; the average of nine perspectives is the statistical centre, which is what this whole system is built to avoid.
