# EXAMPLE: Audit / review

> **Fictional worked example.** The target and its findings are invented. It shows the output shape of an audit and, more importantly, what an honest hard verdict reads like.

**Request:** *"Review this site like an elite portfolio reviewer."*

---

## S0 — Routing

```
ROUTING BLOCK
Mode:         audit-review  (confidence: High)
Runner-up:    personal-portfolio — rejected: an existing artifact was supplied
              and the request says "review", not "rebuild"
Stage:        S0 -> S5  (S5 IS the mode — nothing is built)
Questions:    3
Assumptions:  Findings with fixes attached; no code written
Documents:    QA.md only
Skills:       reference-analysis, browser-qa, accessibility, performance, evaluation
Owner:        Portfolio reviewer on R1, FRESH SESSION
Gates ahead:  none — nothing is built, installed, pushed, or published
Budget:       none
First action: Load the site and use it for five minutes before scoring anything.
```

**Questions:** which lens · yours or someone else's · findings only or fixes too.

"Like an elite portfolio reviewer" names the lens directly, so question 1 answers itself: **portfolio reviewer + design-school reviewer**, and the phrasing pre-authorises bluntness.

---

## Method notes

**Intent was not stated**, so it was inferred and *said to be inferred*: "a designer positioning for studio work". Everything is scored against that inference, not against the reviewer's personal taste.

**The site was used, not described.** Loaded, scrolled, opened on a phone viewport, keyboarded through, primary task attempted. Five minutes of real use beats any amount of reasoning about a screenshot.

**Lenses ran in separate sessions.** A reviewer that just scored accessibility unconsciously weights it in the next pass.

---

## Output shape

```
AUDIT: <url>
Intent:  INFERRED — "a designer positioning for studio work"
Lenses:  portfolio-reviewer, design-school-reviewer

LENS: Portfolio reviewer
Score:    26/40
Verdict:  Ship with fixes
Blocking: none
The one thing: Cut the two weakest projects. Six pieces at mixed quality reads
               as an inability to judge your own work; the weakest sets the
               perceived level.
Would I remember this tomorrow, among a hundred others? No — I would remember
the scroll effect, not the work.

LENS: Design-school reviewer
Score:    21/40
Verdict:  Rebuild the direction
Blocking: Criterion 1 (conceptual rigour) scored 1 — no thesis is discoverable
          from the work itself.
The one thing: The site has a style but no argument. Decide what it is claiming
               before decorating it further.
If I asked "why?" three times about any decision, would the answers hold? No.
Type choice, palette, and motion each survive one "why" and not two.

CONSOLIDATED
Blocking:  Conceptual rigour at 1 (design-school lens)
Major:     Curation (both lenses) · case studies describe features, not
           decisions (both lenses) · scroll motion has no stated purpose
Conflicts: Portfolio lens says "ship with fixes"; design-school says "rebuild".
           Mode decides: for studio applications, the design-school reading is
           the relevant one.
The one thing: There is no thesis. Everything else is downstream of that.

Feel tests
Five-second: category only — "a designer's portfolio". Nothing specific.
Swap:        FAILS. Replace the name and work and it functions identically.
Recall:      One thing survives — a horizontal scroll section. Not the work.
```

---

## The verdict this example exists to show

**"Competent and forgettable."**

Every mechanical check passes. It is responsive, it is accessible, it loads quickly, there are no console errors. And it is a template with someone's content in it — which the swap test proves in ten seconds.

This is the verdict no other lens will say out loud, and it is the most actionable thing an audit can produce, because it **points at S3 rather than at polish.** Adding more animation would make it worse, not better.

Softening this to be encouraging would destroy the entire value of running the review.

---

## What this example demonstrates

| Point | Where |
|---|---|
| An existing artifact routes to audit, not rebuild | Runner-up rejection |
| No gates fire — nothing is built | Routing Block |
| Inferred intent must be declared as inferred | Method notes |
| Lenses run separately and are allowed to disagree | The conflict line |
| The mode decides conflicts, not an average | "For studio applications..." |
| The one thing is mandatory | Both lenses, then consolidated |
| Mechanical pass + judgement fail is a real outcome | The verdict |

**If the request had been "review it and fix it"**, that is a mode change to a build mode with full gates. Say so rather than sliding from audit into implementation.
