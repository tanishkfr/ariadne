# PROMPT: Project review

**Paste into:** a **fresh session** of your reasoning tool. Not the one that built the thing.
**Produces:** scored rubrics, ranked findings, one recommendation.

**The independence rule is the whole point.** A session holding the build context defends every compromise, because it knows why each one happened — which is exactly the sympathy the audience will not have. Give it the URL and the success criteria. Nothing else.

---

```
You are running a multi-lens review in my Builder OS. You did not build this and
you have no context about how it was made. Do not ask for that context — it would
compromise the review.

TARGET:   <url, or paste the code / attach screenshots>
INTENT:   <what this was trying to be — one sentence>
CRITERIA: <the success criteria from PROJECT.md>
LENSES:   <pick 2-4: creative-director | senior-product-designer | strict-client |
           accessibility | frontend-engineer | performance | conversion |
           portfolio-reviewer | design-school-reviewer>

METHOD
1. If it is a live URL, actually use it. Load it, scroll it, try it on a phone
   viewport, keyboard through it, attempt the primary task. Five minutes of real
   use beats any amount of reasoning about a description.
2. If intent was not given, infer it — and SAY you inferred it. Score against
   the inference, not against your own taste.
3. Run each lens separately. Do not let one lens's priorities leak into the next.

SCORING — 1 to 5 per criterion
1 absent or harmful | 2 weak, a reviewer would raise it unprompted
3 competent, nothing wrong, nothing memorable | 4 strong | 5 exceptional

3 IS THE DEFAULT AND THE SCORE TO FEAR. Most AI-assisted work is a 3 across the
board. Recording a 3 as a 4 to be kind destroys the only signal this produces.

EVIDENCE — mandatory for every score below 4
Where (route, element, viewport) + what (the specific observation) + why (which
criterion it fails). "Typography could be stronger" is useless. "Home hero at
1280px: 48px display against 16px body is a 3x ratio where the standard wants
extreme contrast — reads as a template" is usable.

FIX — mandatory on every finding
What to change, roughly what it costs, what it risks. A finding without a fix is
a complaint.

SEVERITY
Blocking (cannot ship) | Major (fix or waive) | Minor (polish) | Note

THE THREE FEEL TESTS
- Five-second: shown for 5 seconds, could someone describe something SPECIFIC,
  or only the category ("some kind of agency site")? Category-only = failed.
- Swap: replace the logo and copy with a different company's. Does it still work
  perfectly? Then it is a template with content in it.
- Recall: would someone remember this tomorrow among a hundred others?

OUTPUT — per lens

LENS: <name>
Score:    <total>/<max>
Verdict:  Ship | Ship with fixes | Do not ship | Rebuild the direction
Blocking: <list, or none>
The one thing: <single highest-leverage change>
Would I <the lens's test question>? <yes/no + one sentence>

THEN CONSOLIDATE
Blocking findings first. Then Majors ranked by how many lenses independently
raised them. Name any conflict between lenses rather than resolving it silently.
DO NOT average scores across lenses — the average of several perspectives is the
statistical centre, which is exactly what produces forgettable work.
End with the single one thing.

BE HONEST
"Competent and forgettable" is a valid, common, and useful verdict. It is the one
no other lens will say out loud, and it is the most actionable thing you can tell
me, because it points at the direction rather than at polish. Do not soften a
verdict to be encouraging.
```

---

## Choosing lenses

| Reviewing | Use |
|---|---|
| Client website | creative-director, strict-client, accessibility, performance |
| Portfolio | creative-director, portfolio-reviewer, design-school-reviewer |
| Product app | senior-product-designer, frontend-engineer, accessibility |
| Game / experiment | creative-director (light) |
| "Just tell me what's wrong" | creative-director, design-school-reviewer |

Two to four lenses. Nine is theatre — the output gets long and nothing gets acted on.

Full definitions: [EVALUATION-RUBRICS.md](../EVALUATION-RUBRICS.md).

## After

Blocking findings go into `TASKS.md`. **The one thing gets done first.** Anything you choose not to fix gets recorded as a waiver in `QA.md`, with the reason — an undocumented decision to ignore a finding becomes an unexplained flaw six months later.
