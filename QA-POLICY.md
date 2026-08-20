# QA POLICY

What must be true before work is shown to a human, and what evidence proves it.

Two halves, both mandatory: **mechanical** (does it work) and **judgement** (is it good). A build that passes every mechanical check and looks generic has failed QA. That rule is the reason this system exists.

Owned by the QA engineer ([AGENT-ROLES.md](AGENT-ROLES.md)). Output: [templates/QA.md](templates/QA.md).

---

## 1. The evidence rule

Every check records one of three states:

| State | Requires |
|---|---|
| **Pass** | Command output, a measured number, or a screenshot |
| **Fail** | The same evidence, plus severity and a proposed fix |
| **Not run** | A reason |

**"Looks fine" is not a QA result.** A check that was not run is recorded as *not run* — never as passed, never left blank. An honest gap is useful; a false pass is worse than no QA at all.

---

## 2. Severity

| Level | Meaning | Effect |
|---|---|---|
| **Blocking** | Broken, inaccessible, or violates the design thesis | G3 cannot be granted |
| **Major** | Noticeably wrong; a reviewer would comment | Fix before ship, or you waive it in writing |
| **Minor** | Polish | Log it; fix if time allows |
| **Note** | Observation, not a defect | Record only |

Blocking by default: build failure, type error, console error, keyboard trap, missing focus states, contrast failure on body text, motion that ignores `prefers-reduced-motion`, broken layout at any tested width, a visual-quality criterion scored 1, and a missing signature moment.

---

## 3. Mechanical checks

Run in this order. Cheap and local first — every failure caught here is one a browser agent or a human did not have to find. See the escalation ladder in [MODEL-ROUTING.md](MODEL-ROUTING.md) section 6.

### 3.1 Build

```bash
pnpm build
```

The **production** build, not the dev server. Dev-only passes are not evidence. Record: pass/fail, warnings, build time.

### 3.2 Types

```bash
pnpm tsc --noEmit
```

Zero errors. `any` introduced during the task is a Major finding. `@ts-ignore` requires a comment explaining why, or it is Blocking.

### 3.3 Lint and format

```bash
pnpm lint
pnpm format --check
```

Zero errors. Warnings are triaged, not ignored wholesale. A rule disabled inline needs a reason on the same line.

### 3.4 Console

Load every route. Zero errors, zero React warnings (keys, hydration, invalid nesting). Hydration mismatches are **Blocking** — they indicate a real correctness problem, not noise.

Record: route, message, source.

### 3.5 Routes and states

Every route loads. Every interactive element responds. Empty, loading, and error states exist and are designed, not default. Forms validate and show real messages. External links have correct targets.

### 3.6 Responsive

Test at **375, 768, 900, 1280, 1920**. The 900-1100 range breaks more layouts than any other and is the one people skip.

Per width: no horizontal scroll, no overlap, no clipped text, touch targets ≥44px, and — the one that matters — **the signature moment still works or has a designed equivalent.**

Evidence: a screenshot per width.

### 3.7 Accessibility

Automated (axe or equivalent) catches roughly a third of real problems. The manual passes are the ones that count:

- **Keyboard:** tab through every flow. Visible focus at every stop. No traps. Logical order. Escape closes overlays.
- **Contrast:** measured on rendered pixels, not on the token values. 4.5:1 body, 3:1 large text and UI boundaries.
- **Structure:** one `h1`, no skipped heading levels, landmarks present, images have `alt` (empty `alt` for decorative), inputs have labels.
- **Reduced motion:** enable `prefers-reduced-motion` and reload. Content must appear. A reduced *design*, not just disabled animation.
- **Zoom:** 200% without loss of content or function.

Contrast failures caused by a deliberately low-contrast direction route to the Design director, not to the Implementer. See [AGENT-ROLES.md](AGENT-ROLES.md) role 9.

### 3.8 Motion

- Every animation has a stated purpose ([DESIGN-TASTE.md](DESIGN-TASTE.md) section 6.1).
- 60fps on a mid-range machine — check for dropped frames, not just smoothness.
- `transform` and `opacity` only for anything animating continuously.
- Reduced-motion path verified.
- No animation blocks interaction or delays content past ~1s.
- Scroll-triggered work behaves on fast scroll, on refresh mid-page, and on back-navigation.

### 3.9 Performance

Measured on the **production build**, ideally the Vercel preview rather than localhost.

| Metric | Target | Blocking above |
|---|---|---|
| LCP | < 2.5s | 4.0s |
| CLS | < 0.1 | 0.25 |
| INP | < 200ms | 500ms |
| Total JS (gzip) | < 200KB | project budget in `ARCHITECTURE.md` |
| Largest image | < 300KB | 1MB |
| Fonts | ≤ 3 files, `font-display: swap` or a designed fallback | — |

Measure before optimising. Record the number, not an impression. Removing a designed feature to gain a metric requires a Design director decision.

---

## 4. Judgement checks

Mechanical QA cannot detect generic. This half can.

### 4.1 Visual quality scorecard

Score all ten criteria in [DESIGN-TASTE.md](DESIGN-TASTE.md) section 11. Record the score **and one sentence of evidence per criterion.** Thresholds and blocking rules are in that file.

### 4.2 Anti-generic sweep

Walk the fifteen-row table in [DESIGN-TASTE.md](DESIGN-TASTE.md) section 8 and mark each present/absent. Any present is Blocking.

### 4.3 Review lenses

At minimum: **creative director** plus one mode-appropriate lens from [EVALUATION-RUBRICS.md](EVALUATION-RUBRICS.md).

| Mode | Required lenses |
|---|---|
| Premium client website | Creative director, strict client, accessibility, performance |
| Personal portfolio | Creative director, portfolio reviewer, design-school reviewer |
| Product app | Senior product designer, frontend engineer, accessibility |
| Game / experiment | Creative director (light) |
| Audit / review | Whichever lens the request named |

**Independence:** judgement checks run in a session that did not build the thing. A reviewer holding the build context defends the build instead of assessing it.

### 4.4 The two tests

- **Five-second test** — can someone describe something specific, or only the category?
- **Swap test** — replace logo and copy with a different company's. Does it still work perfectly? Then it is a template.

Both from [DESIGN-TASTE.md](DESIGN-TASTE.md) section 8.

---

## 5. Screenshot review

Required for G3. Capture from the production build or preview:

- Each route at 375 and 1280.
- The signature moment, mid-motion if it is a motion piece.
- Every state that is not the happy path: empty, loading, error, form validation.
- The reduced-motion rendering.

Look at them yourself before presenting them. An agent that captures screenshots without inspecting them has automated the *taking* of evidence, not the *checking* of it.

---

## 6. Preview review

Deploy previews are Green for feature branches on an already-connected repo; production is G4.

On the preview, verify what localhost cannot tell you: real network conditions, real font loading, real image optimisation, correct environment variables, and that nothing depended on a local file. Then re-run section 3.9 there — localhost performance numbers are optimistic and largely meaningless.

---

## 7. Human gates

| Gate | Presented by | You decide |
|---|---|---|
| **G1** Direction Lock | Design director | Is this direction right, before anything is built |
| **G3** Build Complete | QA engineer | Is this ready for the world |
| **G4** Ship | Implementer | Does this leave the machine |

**G3 presentation format:**

```
G3: BUILD COMPLETE
Mechanical:  <n passed / n failed / n not run>
Blocking:    <list, or none>
Major:       <list>
Scorecard:   <total>/50  (lowest criterion: <name> at <n>)
Lenses:      <lens: recommendation> ...
Screenshots: <paths>
Preview:     <url>
Known gaps:  <what was not tested, and why>
Recommend:   ship | fix first | return to S3
```

The **Known gaps** field is mandatory and may not be empty. Something is always untested; naming it is what makes the rest of the report trustworthy.

---

## 8. QA on non-build modes

**Audit / review** — QA *is* the deliverable. Run sections 3.6-3.9 and all of section 4 against the target. Findings go in `QA.md` with severity and evidence.

**Content system** — different checks entirely: originality, voice match, hook quality, factual accuracy, no fabricated metrics or experiences. See [CONTENT-SYSTEM.md](CONTENT-SYSTEM.md). G5 replaces G3/G4.

**Game / experiment** — compressed: build, console, one responsive pass, the core mechanic works, reduced-motion. Skip the performance budget unless performance is the point.
