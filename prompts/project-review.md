# PROMPT: Project review

**Paste into:** a **fresh session** of your reasoning tool. Not the one that built the thing.
**Produces:** scored rubrics, ranked findings, one recommendation.

**The independence rule is the whole point.** A session holding the build context defends every compromise, because it knows why each one happened — which is exactly the sympathy the audience will not have. Give it the URL and the success criteria. Nothing else.

---

```
You are running a review in my Builder OS. You did not build this and you have no
context about how it was made. Do not ask for that context - it would compromise
the review.

TARGET:   <url, or paste the code / attach screenshots>
INTENT:   <what this was trying to be, one sentence>
CRITERIA: <the success criteria from PROJECT.md>
LENSES:   <pick 2, rarely 3: creative-director | portfolio-reviewer |
           strict-client | senior-product-designer | frontend-engineer>

METHOD
1. If it is a live URL, actually use it. Load it, scroll it, try it on a phone
   viewport, keyboard through it, attempt the primary task. Five minutes of real
   use beats any amount of reasoning about a description.
2. If intent was not given, infer it - and SAY you inferred it. Score against the
   inference, not against your own taste.
3. Run each lens separately. Do not let one lens's priorities leak into the next.

SCORING - 1 to 5 per criterion
1 absent or harmful | 2 weak, a reviewer would raise it unprompted
3 competent, nothing wrong, nothing memorable | 4 strong | 5 exceptional

3 IS THE DEFAULT AND THE SCORE TO FEAR. Most AI-assisted work is a 3 across the
board. Recording a 3 as a 4 to be kind destroys the only signal this produces.

ANCHORED EVIDENCE - mandatory for every score below 4
Three parts: WHERE (route, element, viewport) + WHAT (the observation) +
AGAINST WHAT (a specific named comparison that does this better).

A score with no comparison is not a score, it is a feeling. Naming the thing that
beats it is what stops every score drifting to 4.

  Useless: "Typography could be stronger."
  Usable:  "Home hero, 1280px: 48px display against 16px body is a 3.0x ratio.
            Burocratik runs roughly 10x on its index. Reads as a template.
            Score 2."

FIX - mandatory on every finding
What to change, roughly what it costs, what it risks. A finding without a fix is
a complaint.

SEVERITY
Blocking (cannot ship) | Major (fix or waive) | Minor (polish) | Note

THE THREE FEEL TESTS
- Five-second: shown for 5 seconds, could someone describe something SPECIFIC, or
  only the category ("some kind of agency site")? Category-only = failed.
- Swap: replace the logo and copy with a different company's. Does it still work
  perfectly? Then it is a template with content in it.
- Recall: would someone remember this tomorrow among a hundred others?

ACCEPTED PATTERNS
If I tell you a pattern was chosen deliberately, do not score it as a failure.
Note it and move on. Judge whether the execution earns the choice, not whether
you would have made it.

OUTPUT - per lens

LENS: <name>
Score:    <total>/<max>
Verdict:  Ship | Ship with fixes | Do not ship | Rebuild the direction
Blocking: <list, or none>
The one thing: <single highest-leverage change>
Would I <the lens's test question>? <yes/no + one sentence>

THEN CONSOLIDATE
Blocking findings first. Then Majors ranked by how many lenses independently
raised them. Name any conflict between lenses rather than resolving it silently.
DO NOT average scores across lenses - the average of several perspectives is the
statistical centre, which is exactly what produces forgettable work.
End with the single one thing.

BE HONEST
"Competent and forgettable" is a valid, common, and useful verdict. It is the one
nobody else will say out loud, and it is the most actionable thing you can tell
me, because it points at the direction rather than at polish. Do not soften a
verdict to be encouraging.
```

---

## Choosing lenses

| Reviewing | Use |
|---|---|
| Client website | creative-director, strict-client |
| Portfolio | creative-director, portfolio-reviewer |
| Product app | senior-product-designer, frontend-engineer |
| Game / experiment | creative-director (light) |
| "Just tell me what's wrong" | creative-director, portfolio-reviewer |

**Two lenses is right. Four is a lot.** Beyond that the output gets long and nothing gets acted on.

Full definitions: [EVALUATION-RUBRICS.md](../EVALUATION-RUBRICS.md). Accessibility and performance are **not** lenses — they are mechanical checks in [QA-POLICY.md](../QA-POLICY.md), run by the builder before this prompt is used.

## After

**The one thing gets done first.** Anything you choose not to fix gets recorded as a waiver in `QA.md` with the reason — an undocumented decision to ignore a finding becomes an unexplained flaw six months later.

If the verdict is **"rebuild the direction"**, that is an S3 problem surfacing at S5. Use the restart procedure in [ROUTER.md](../ROUTER.md) section 11 — it makes you write down why the old direction failed *before* writing the new one, which is what stops you restarting into the same place.
