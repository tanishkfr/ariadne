# SKILL: frontend-build

**Trigger** — G1 passed, `HANDOFF.md` exists. S4.
**Owner** — Implementer · **Class** — `R2`
**Inputs** — `HANDOFF.md`, `TASKS.md`, `DESIGN.md`, `ARCHITECTURE.md`, `AGENTS.md`
**Output** — working code, `TASKS.md` updated, a passing production build

---

## Method

**1. Read the handoff, not the chat history.** `HANDOFF.md` exists so the decisions do not have to be re-derived. Re-deriving context is the single biggest waste of usage limits in this system ([MODEL-ROUTING.md](../MODEL-ROUTING.md) section 8).

**2. Set up the token system first.** Before any component: CSS custom properties for type scale, spacing scale, colour, easing, durations, radii. Every later value comes from here.

This is what makes the difference between a designed interface and an assembled one. Hardcoded one-off values are the mechanism by which a locked direction drifts back to default.

**3. Build the signature moment early.** Not last. Anything left to the end gets cut by schedule pressure, and it is the one thing that cannot be cut.

**4. One task, one branch.** `s4/<slug>`. Never on the default branch. Each task has an acceptance criterion and a verification method *before* work starts — if `TASKS.md` lacks them, that is a blocker to raise, not a detail to improvise.

**5. Work in verifiable increments.** After each meaningful change: does it build, typecheck, and render. Catching a break within one change is minutes; catching it ten changes later is an afternoon.

**6. Production build before marking anything done.** Not the dev server. `pnpm build`. The dev server hides hydration errors, build-time failures, and font loading problems — precisely the class of bug that appears first on the deployed preview.

**7. Raise findings; do not substitute.** If the design cannot be built as specified, produce a finding:

```
BUILD FINDING
Specified:  <what DESIGN.md says>
Problem:    <why it does not work — be technical>
Option A:   <closest achievable, and what is lost>
Option B:   <alternative approach, and what it costs>
Recommend:  <which, and why>
```

Then wait for a Design director decision. **Silent substitution is the mechanism by which art-directed work degrades into template work.** It is the most important rule in this skill.

**8. No new dependency without G2.** Not even to try. Prototype on a scratch branch and say so. [LIBRARY-POLICY.md](../LIBRARY-POLICY.md).

**9. Keep `TASKS.md` current** as you go. A task list updated at the end is a work of fiction.

---

## Code standards

- Strict TypeScript. No `any` without a comment justifying it.
- Components under ~200 lines. Past that, the boundary is wrong.
- Every value from the token system. A hardcoded `#1a1a1a` or `margin: 37px` is a finding.
- Semantic HTML first. `<button>` for buttons, real headings, real lists. Most accessibility problems are prevented here for free.
- Server components by default; `'use client'` only where interaction requires it.
- No dead code, no commented-out blocks, no `console.log` in committed work.
- Match the existing conventions of the file you are in, even where you would have chosen differently.

---

## Done when

Every task meets its acceptance criterion · production build passes · zero type errors · zero console errors · every value from tokens · the signature moment is built and works on mobile · `TASKS.md` reflects reality.

---

## Failure modes

| Failure | Countermeasure |
|---|---|
| Silently building something easier than specified | Step 7. Always a finding, never a substitution. |
| Hardcoded values drifting from the design | Step 2, then a QA sweep for literals |
| Signature moment cut for time | Step 3: build it first |
| "Works on my dev server" | Step 6: production build is the standard |
| Installing a package to "just try it" | G2 first, scratch branch if needed |
| A 900-line component | 200-line ceiling as a boundary signal |
| Reading the whole chat history to find a decision | It is in `HANDOFF.md`; if it is not, that is the bug |
