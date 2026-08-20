# QA: <name>

> Template. Owner: QA engineer · Stage: S5 · Policy: [QA-POLICY.md](../QA-POLICY.md)
> **Every row needs evidence: a command output, a measured number, or a screenshot.**
> A check that was not run is recorded as **not run** — never as passed, never left blank.

**Build:** <commit> · **Preview:** <url> · **Date:** <>

---

## Severity

**Blocking** (G3 cannot be granted) · **Major** (fix or waive in writing) · **Minor** (polish) · **Note**

---

## Mechanical

| # | Check | State | Evidence |
|---|---|---|---|
| 1 | Production build (`pnpm build`) | pass / fail / not run | <output, time, warnings> |
| 2 | Types (`tsc --noEmit`) | | <error count> |
| 3 | Lint + format | | |
| 4 | Console clean, every route | | <route: message> |
| 5 | All routes load | | |
| 6 | Empty / loading / error states | | |
| 7 | Responsive 375 | | <screenshot> |
| 8 | Responsive 768 | | |
| 9 | Responsive 900-1100 | | <the range that breaks most layouts> |
| 10 | Responsive 1280 | | |
| 11 | Responsive 1920 | | |
| 12 | Keyboard: every flow | | |
| 13 | Focus visible at every stop | | |
| 14 | Contrast (rendered pixels) | | <measured ratios> |
| 15 | Heading structure, landmarks, alt | | |
| 16 | Forms: labels, errors, not colour-only | | |
| 17 | Reduced motion (preference enabled, reloaded) | | <content still appears?> |
| 18 | Zoom 200% | | |
| 19 | Motion 60fps | | |
| 20 | Motion: fast scroll, refresh mid-page, back-nav | | |
| 21 | LCP (preview) | | <n>s |
| 22 | CLS | | <n> |
| 23 | INP | | <n>ms |
| 24 | JS gzipped | | <n>KB vs budget |
| 25 | Largest image | | <n>KB |

---

## Judgement

### Visual quality scorecard

> [DESIGN-TASTE.md](../DESIGN-TASTE.md) section 11, scored against the **build** this time.
> Below 35 is not shippable. Any single criterion at 1 is Blocking regardless of total.

| # | Criterion | Score | Evidence (one sentence) |
|---|---|---|---|
| 1 | Concept clarity | /5 | |
| 2 | Typographic quality | /5 | |
| 3 | Compositional strength | /5 | |
| 4 | Colour discipline | /5 | |
| 5 | Material quality | /5 | |
| 6 | Motion purpose | /5 | |
| 7 | Signature moment | /5 | |
| 8 | Anti-generic compliance | /5 | |
| 9 | Craft | /5 | |
| 10 | Originality | /5 | |

**Total: <n>/50**

### Anti-generic sweep

> [DESIGN-TASTE.md](../DESIGN-TASTE.md) section 8. **Any present is Blocking.**

| Pattern | Present? | Where |
|---|---|---|
| Generic SaaS layout | | |
| Random gradients | | |
| Default glassmorphism | | |
| Repetitive card grids | | |
| Empty hero | | |
| Generic AI copy | | |
| Arbitrary animation | | |
| Component-library soup | | |
| Placeholder imagery | | |
| Predictable typography | | |
| Unmotivated bento | | |
| Overuse of rounded cards | | |
| Overuse of shadows | | |
| Unnecessary dashboard | | |
| Decorative motion | | |

### The two tests

- **Five-second test:** <what they described — category only, or something specific?>
- **Swap test:** <does it still work with someone else's logo and copy?>

### Review lenses

> [EVALUATION-RUBRICS.md](../EVALUATION-RUBRICS.md). Run in sessions that did not build this.

| Lens | Score | Verdict | The one thing |
|---|---|---|---|
| | /40 | | |

---

## Findings

| # | Severity | Where | What | Why it fails | Fix | Status |
|---|---|---|---|---|---|---|
| 1 | Blocking | <route, element, width> | | <criterion> | | open / fixed / waived |

**Waivers** — Major findings accepted without fixing, and by whom:

| # | Finding | Reason accepted | Approved by | Date |
|---|---|---|---|---|

---

## Screenshots

| View | Path |
|---|---|
| Home 375 | |
| Home 1280 | |
| Signature moment | |
| Reduced motion | |
| Error / empty state | |

> Look at these yourself. Capturing evidence and checking it are different acts.

---

## G3 presentation

```
G3: BUILD COMPLETE
Mechanical:  <n> passed / <n> failed / <n> not run
Blocking:    <list, or none>
Major:       <list>
Scorecard:   <n>/50  (lowest: <criterion> at <n>)
Lenses:      <lens: verdict> ...
Screenshots: <paths>
Preview:     <url>
Known gaps:  <what was not tested, and why>
Recommend:   ship | fix first | return to S3
```

> **Known gaps may not be empty.** Something is always untested. Naming it is what makes the rest of the report trustworthy.
