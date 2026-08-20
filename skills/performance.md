# SKILL: performance

**Trigger** — a production build exists.
**Owner** — Performance reviewer · **Class** — `R6` + `R4`
**Inputs** — production build, deployed preview
**Output** — the performance section of [`QA.md`](../templates/QA.md)

Targets: [QA-POLICY.md](../QA-POLICY.md) section 3.9. Rubric: [EVALUATION-RUBRICS.md](../EVALUATION-RUBRICS.md) lens 6.

**Measure first.** Optimising before measuring is how people spend a day saving 4KB while a 3MB image sits in the hero.

---

## Method

**1. Measure on the preview, not localhost.** Localhost numbers are optimistic to the point of being useless — no real network, no cold start, warm caches, no CDN. Every number that goes in `QA.md` comes from the deployed preview.

**2. Record numbers, not impressions.** LCP, CLS, INP, total JS gzipped, largest image, font count and weight. "Feels fast" is not a measurement, and it is measured on your machine and your connection.

**3. Find the actual cost.** Almost always, in order:

| Cause | Typical fix |
|---|---|
| Images | Correct dimensions, AVIF/WebP, lazy below the fold. Usually the single biggest win. |
| Fonts | Fewer files, subset, `font-display`, self-host, preload the one that matters |
| JavaScript | A heavy dependency, or client components that should be server components |
| Third-party scripts | Analytics, embeds, widgets. Frequently the worst offender per KB. |
| Layout shift | Unsized images, late-loading fonts, injected content |

**4. Check the animation cost separately.** Frame rate during motion, not just load metrics. Watch for layout thrash, animated `width`/`filter`/`box-shadow`, and too many compositor layers. See [motion-design](motion-design.md).

**5. Test on a real constrained device** if the audience plausibly includes one. A mid-range Android on 4G is the realistic case for an Indian audience, and it behaves nothing like a development laptop.

**6. Fix the biggest thing, then re-measure.** One change at a time. Bundled optimisations make it impossible to know what worked, and half of them usually did nothing.

---

## The design tension

**Never silently cut a designed feature to gain a metric.**

If the signature moment is expensive, that is a real tradeoff and it goes to the Design director and then to you. Options are almost always available before deletion: lazy-load it, degrade it on slow connections, reduce its scope, or accept the cost because it is the point of the project.

A portfolio piece with a 3.2s LCP and a genuinely memorable interaction may be the right call. A generic site with a 1.1s LCP that nobody remembers is not a win. **Record the decision** in `QA.md` either way.

---

## Budgets

Set in `ARCHITECTURE.md` at S3, before building. A budget agreed afterwards is a rationalisation of whatever happened.

Reasonable defaults for a portfolio-quality site: JS under 200KB gzipped, largest image under 300KB, three font files or fewer, LCP under 2.5s on the preview.

---

## Done when

All metrics measured on the preview and recorded as numbers · the largest cost identified · fixes applied one at a time with before/after · any design-versus-performance tradeoff explicitly decided and recorded.

---

## Failure modes

| Failure | Countermeasure |
|---|---|
| Measuring on localhost | Preview only |
| Optimising before measuring | Step 1 precedes everything |
| Bundling five optimisations | One change, re-measure |
| Cutting the signature moment to hit a number | Design director decision, then yours |
| Ignoring animation frame cost | Step 4 is separate from load metrics |
| Budgets set after the fact | Set at S3, in `ARCHITECTURE.md` |
| Testing only on a fast laptop | Step 5 |
