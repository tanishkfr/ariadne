# ARCHITECTURE: <name>

> Template. Owner: Architect · Stage: S3 (parallel with DESIGN.md)
> Default stack assumptions: [ROUTER.md](../ROUTER.md) section 5. Dependencies: [LIBRARY-POLICY.md](../LIBRARY-POLICY.md).

**Status:** <draft | locked> · **Last updated:** <date>

---

## Stack

| Layer | Choice | Why |
|---|---|---|
| Framework | Next.js <version> | Default |
| Language | TypeScript, strict | Default |
| Package manager | pnpm | Default — do not mix managers |
| Styling | CSS custom properties + <modules / Tailwind> | <Tailwind only if genuine utility churn> |
| Motion | <Motion.dev / GSAP / CSS> | <per interaction> |
| Testing | Playwright | Default |
| Hosting | Vercel | Default |

**Deviations from the default stack:** <what, and why>

## Routes

| Path | Purpose | Rendering | Notes |
|---|---|---|---|
| `/` | | static / dynamic | |

## Component map

> Structure, not a file listing. Where boundaries are and why.

```
<tree>
```

| Component | Responsibility | Client? | Notes |
|---|---|---|---|
| | | server/client | |

## Data model

> Only if data exists. **"None — content is co-located with components" is a valid and common answer.**

## State model

| State | Where it lives | Why there |
|---|---|---|
| | local / URL / server / context | |

> Prefer, in order: local state, URL state, server state. A state library is almost never needed for a site.
> Reaching for one requires a real cross-tree requirement.

## Design tokens

> The contract between `DESIGN.md` and the code. Built before any component.

```css
:root {
  /* type scale */
  /* spacing scale */
  /* colour */
  /* easing + duration */
  /* radii */
}
```

**Rule:** every value in the codebase comes from here. A hardcoded literal is a QA finding.

## Dependencies

> Every entry needs a date and a reason. Approved via G2. Undocumented dependencies become future mysteries.

| Package | Version | Added | Reason | Approved |
|---|---|---|---|---|
| | | <date> | | <date> |

**Removal candidates:** <used once, superseded, or the feature was cut>

## CMS decision

**Decision:** <none / which>

> Default is none. A CMS is justified only when a non-developer must edit copy.
> If none: how does copy get updated? <>

## Backend decision

**Decision:** <none / which>

> Default is none. Frontend-first. A backend needs a requirement forcing it — not a feeling that one is expected.
> If none: how are forms, if any, handled? <>

## Performance constraints

> Set **now**, at S3. A budget agreed after building is a rationalisation.

| Budget | Target |
|---|---|
| JS (gzip) | < 200KB |
| Largest image | < 300KB |
| Font files | <= 3 |
| LCP (preview) | < 2.5s |
| CLS | < 0.1 |

## Accessibility constraints

> Direction-level decisions made here, not discovered at S5.

- Contrast approach: <>
- Keyboard equivalents for hover interactions: <>
- Reduced-motion strategy: <>
- Focus state design: <not the default outline, and not removed>

## Deployment plan

- **Repo:** <name> · <private / public>
- **Branching:** one task per branch, `s4/<slug>`
- **Previews:** per branch on Vercel
- **Production:** <domain, or none yet> — requires G4
- **Environment variables:** <names and purposes only, never values>
- **Rollback:** <how>

## Risks

| Risk | Impact | Mitigation |
|---|---|---|
| | | |
