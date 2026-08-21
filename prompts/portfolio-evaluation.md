# PROMPT: Portfolio evaluation

**Paste into:** a **fresh session**. Not one that has seen your work before.
**Produces:** a brutal read of your portfolio as an actual reviewer would give it.

Harsher than [project-review.md](project-review.md). It assumes 60 seconds of attention and a hundred other portfolios in the queue — which is the real condition.

---

```
You are reviewing my portfolio the way an elite reviewer actually would: with
60 seconds of attention, a hundred other portfolios in the queue, and no
knowledge of how hard any of it was to build.

You did not make this. Do not ask me for context about my process, my
constraints, or my intentions - a reviewer would not have that, and having it
would make you sympathetic in a way the real audience will not be.

PORTFOLIO: <url>
I WANT:    <what this is for - a studio job, freelance clients, an awards
            submission, a specific opportunity>

RUN TWO LENSES, IN SEPARATE PASSES

1. PORTFOLIO REVIEWER (max 40) - does this help or hurt the person who made it,
   and do their decisions hold up?
   Memorability | Positioning | Curation | Depth of proof | Writing |
   Conceptual rigour | Justification | Risk
   Test: would I shortlist this, among a hundred others?
   Below 24: rework before sending anywhere.
   24-31: usable, not competitive.  32+: competitive.

2. CREATIVE DIRECTOR (max 50) - is there an idea here, and is it executed?
   Concept | Typography | Composition | Colour | Material | Motion |
   Signature moment | Anti-generic | Craft | Originality
   Test: would I put this in the studio's showreel?
   Below 30: rebuild the direction.  30-39: ship with fixes.  40+: ship.

SCORING - 1 to 5 per criterion
3 means competent, nothing wrong, nothing memorable. MOST PORTFOLIOS ARE A 3.
Scoring a 3 as a 4 to be kind is the single way to make this exercise worthless.

ANCHORED EVIDENCE - required for every score below 4.
WHERE + WHAT + AGAINST WHAT: name a specific site or portfolio that does this
better, and say how. A score with no comparison is a feeling, not a score.

ALSO ANSWER, DIRECTLY

- FIRST IMPRESSION, 5 SECONDS: what did you actually register? If the answer is
  only a category ("a designer's site"), say so plainly.
- THE WEAKEST PIECE: name it. The weakest piece sets the perceived level, and a
  reviewer with 60 seconds will find it. Should it be cut?
- CURATION: is anything here making the rest look worse?
- POSITIONING: after two minutes, what am I good at? If you cannot say, that is
  the finding.
- CASE STUDIES: do they explain DECISIONS or list FEATURES? Reviewers hire for
  decisions. Quote an example of each if both exist.
- PROCESS: can you see how this person thinks, or only what they shipped?
- THE SWAP TEST: replace the name and work with someone else's. Does the site
  still work perfectly? Then it is a template with content in it.
- RECALL: describe this portfolio tomorrow without looking. What survives?
  Usually one thing. Sometimes none. Say which.
- IS THE SITE BETTER THAN THE WORK IN IT? An uncomfortable question. Answer it.

FINALLY

THE ONE THING: the single change that would most improve my chances at
<what I said this is for>. One. Not a list.

WOULD YOU SHORTLIST ME? Yes or no, and the actual reason.

Do not soften this to be encouraging. A "no" with a real reason is the most
useful thing you can give me. "Competent and forgettable" is a valid verdict and
if it applies, say it - it points at the direction, not at polish, and it is the
thing nobody else will tell me.
```

---

## Before running this

Deploy it. Reviewing a local build misses font loading, real performance, and how it behaves on a phone — which is where a meaningful share of the 60 seconds gets spent.

## After running this

Expect it to hurt. That is the point of the lens.

Then be careful about what you act on:

1. **The one thing** — do this.
2. **Findings raised by both lenses** — real, act on them.
3. **The weakest piece** — cutting is almost always right. Fewer, stronger.
4. **Single-lens findings you disagree with** — a reviewer with 60 seconds and no context *is* your audience. Disagreeing is allowed, but record why in `RETROSPECTIVE.md`; if the same finding comes back next time, it was not wrong.

If the verdict is **"rebuild the direction"**, that is an S3 problem surfacing at S5. Say so plainly — the router recognises it as a restart (**R-INT-1**) and freezes the direction without deleting research or assets. It makes you write down why the old direction failed *before* writing the new one, which is what stops you restarting into the same place.
