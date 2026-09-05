# LIBRARY POLICY

How a package gets into a project, and how it gets out.

The problem this solves: **component libraries are a substitute for design decisions.** Installing five UI libraries produces five visual languages, none of them yours. The libraries in [references/ui-libraries.md](references/ui-libraries.md) are excellent as *research* and dangerous as *dependencies*.

Rule of thumb: **every dependency is a decision you have outsourced.** Outsource the boring ones. Never outsource the ones your work is judged on.

---

## 1. The tiers

| Tier | Meaning | Approval |
|---|---|---|
| **Default candidate** | Familiar part of the default stack, but still needs an exact-version G2 approval before installation | G2, brief |
| **Conditional** | Fine for a stated purpose, needs a one-line reason | G2, brief |
| **Research-only** | Read the source, take the technique, do not install | Installing needs full G2 with justification |
| **Specialty** | Heavy or niche; only when the project is *about* that thing | Full G2 |
| **Forbidden by default** | Fails the criteria in section 5 | G2 plus an explicit override from you |

---

## 2. Default candidates

These are normal candidates for the default stack. They reduce research work;
they do **not** grant installation authority. Every exact dependency set still
requires human G2 approval before the first install command.

| Package | For |
|---|---|
| `next`, `react`, `react-dom` | Framework |
| `typescript`, `@types/*` | Types |
| `eslint`, `prettier` + configs | Lint and format |
| `@playwright/test` | Browser testing |
| `motion` (Motion.dev) | Component and state motion |
| `clsx` / `tailwind-merge` | Only if Tailwind is in use |
| `tailwindcss` | Only when the project has genuine utility-churn; not automatic |
| `sharp` | Image processing in a build step |
| `zod` | Runtime validation, when there is real external input |

Everything else, including things that feel obvious, also goes through G2.

### Minimum-solution ladder

Before proposing a package, walk this order and stop at the first rung that
meets the project need without weakening accessibility or the approved design:

1. Use an existing project capability.
2. Use a browser or language primitive.
3. Write the smallest project-local implementation.
4. Reuse an already approved dependency.
5. Compare a registered external capability against the project constraints.
6. Research a new external capability only when the earlier rungs fail.

Record the rejected rung and reason in the G2 proposal. Discovery never grants
permission to install, and a familiar package name is not evidence of need.

The dated [capability registry](references/capabilities.json) is an advisory
comparison index for rung 5. It records what a source may provide, provenance,
licence, side effects, and design-authority risk. It is not a preferred-library
list, does not replace current source inspection, and cannot approve G2. When a
registry row is stale, unpinned, or incompatible with the project, return to
research or choose an earlier rung.

---

## 3. Conditional

Legitimate, but each brings a cost that must be worth paying. State the reason in one line and proceed.

| Package | Legitimate use | The cost |
|---|---|---|
| `gsap` | Scroll choreography, timelines, morphing | Weight; overlaps with Motion.dev. Do not ship both without a reason. |
| `three` / `@react-three/fiber` | 3D is the point of the project | Very heavy. Specialty in most cases. |
| `lenis` | Smooth scroll integral to the direction | Accessibility risk; must respect reduced-motion |
| `@radix-ui/*` | Accessible primitives for complex widgets (dialog, popover, select) | Unstyled, so it does not harm art direction. Preferred over styled kits. |
| `next-mdx-remote` / `contentlayer` | Content-heavy site with real MDX need | Build complexity |
| `date-fns` | Real date logic | Often replaceable with `Intl` |
| A state library (`zustand`, `jotai`) | Product app with genuine cross-tree state | Almost never needed for a site |

---

## 4. Research-only

**Read these. Do not install them.** Study how a component is built, then build your own in your own token system.

All of the UI/motion sources you collected — Aceternity, Magic UI, React Bits, Kokonut, Motion Primitives, 8bitcn, bklit, watermelon — are research-only by default. Full list and rationale: [references/ui-libraries.md](references/ui-libraries.md).

Why:

- They carry a recognisable house style. Using them makes your work look like everyone else using them.
- Most are copy-paste catalogues, so *taking the technique is the intended use*.
- They frequently assume Tailwind and a specific token setup.
- A component you wrote can be art-directed. A component you installed resists it.

**Approved use:** open it, understand the technique, close it, implement your version against your tokens. Record what you learned in `RESEARCH.md`, including the source URL.

**If you genuinely need to install one**, that is a full G2 with an explicit statement of why building it yourself is the wrong call.

---

## 5. Forbidden by default

A package is forbidden unless overridden if **any** of these is true:

1. **It imposes a visual identity** — a styled component kit (MUI, Chakra, Ant, Bootstrap, DaisyUI). These make portfolio-quality art direction effectively impossible.
2. **Unclear or restrictive licence** — no licence file, a non-commercial clause, or an unclear font EULA.
3. **Unmaintained** — no release in 12 months *and* open issues on current framework versions. Section 7.
4. **Inaccessible by construction** — ships components that cannot be made keyboard-operable.
5. **Disproportionate weight** — more than ~30KB gzipped for something implementable in under 100 lines.
6. **Duplicates an existing dependency** — a second motion library, a second date library, a second HTTP client.
7. **Requires a paid service or API key** to function. See [BUDGET-POLICY.md](BUDGET-POLICY.md).
8. **Runs arbitrary code at install time** without a clear reason.

Criterion 1 is the one that matters most for your stated goals. Everything else is hygiene; criterion 1 is the difference between art direction and template assembly.

---

## 6. How an agent proposes a package

Exact format. A proposal missing a field is rejected without discussion.

```
DEPENDENCY REQUEST (G2)
Package:      <name@version>
Tier:         Conditional | Research-only | Specialty | Forbidden-override
Purpose:      <the specific thing it does in THIS project>
Alternative:  <what building it ourselves costs, in hours and lines>
Weight:       <KB gzipped, and % of current bundle>
Licence:      <SPDX id, verified how>
Maintenance:  <last release date, open issue count, framework compatibility>
Accessibility:<keyboard/SR status, or N/A>
Removal:      <what breaks if removed later>
Recommend:    install | build ourselves | skip entirely
```

Rules for the proposing agent:

- **Recommend honestly.** "Build ourselves" is a frequent correct answer and proposing it builds trust.
- **Never bundle.** One package, one request. Three packages is three decisions.
- **Verify, do not recall.** Weight, licence, and last-release dates are looked up now and dated. See [RESEARCH-POLICY.md](RESEARCH-POLICY.md).
- **Never install while waiting.** Not even to test. Use a scratch branch if you must prototype, and say so.

On approval, record it in `ARCHITECTURE.md` under Dependencies: package, version, date, one-line reason, and who approved it. An undocumented dependency is a future mystery.

---

## 7. The checks, concretely

**Licence.** Read the actual `LICENSE` file, not the npm badge. MIT / Apache-2.0 / BSD / ISC are fine. GPL/AGPL need a decision. Fonts are the most common trap: a free-for-personal font on a client site is a real liability. Record the licence in `ASSETS.md` or `ARCHITECTURE.md`.

**Maintenance.** Last publish date, commits in the last 6 months, open issues mentioning your framework's current major version, and whether a maintainer replies. A popular package that stopped tracking React's major versions is a future migration you have volunteered for.

**Accessibility.** Keyboard operable, focus visible, correct roles, respects `prefers-reduced-motion`. Test the actual demo with a keyboard — do not trust the README's claim.

**Bundle size.** Measure gzipped, with tree-shaking as you will actually import it. Compare to the current total. A budget lives in `ARCHITECTURE.md`; a package that consumes more than 10% of it needs a strong reason.

**Performance.** Runtime cost, not just size: does it force client rendering, block hydration, add a build step, or animate off the compositor?

---

## 8. Removing a package

Dependencies accumulate. Removal is a normal maintenance action, done at retrospectives.

1. List every import site.
2. Decide: replace, inline, or delete the feature.
3. Remove in its own branch and commit — never bundled with feature work.
4. Verify: production build, typecheck, full QA run, bundle size before and after.
5. Update `ARCHITECTURE.md` and note the size delta in the retrospective.

**Removal candidates:** used in one place; replaced by a platform feature; the feature that needed it was cut; unmaintained since it was added.

---

## 9. Fonts

Fonts are dependencies with the highest visual leverage and the worst licensing risk.

- Self-host via `next/font/local` where the licence allows. Faster, private, no third-party request.
- Google Fonts: free, safe, and everyone uses the popular ones. Prefer the less-used faces.
- Commercial fonts: **G2 with the actual licence terms and cost in INR.** Check webfont vs desktop rights and any pageview cap.
- Free-for-personal-use fonts are **forbidden on client work** without a purchased licence. This is the single most common licensing mistake in portfolio-quality work.
- Record every font in `ASSETS.md`: name, foundry, licence type, cost, where the licence document lives.

Trial or unlicensed fonts must never reach a production deploy. If a licence is pending at G4, the deploy waits.
