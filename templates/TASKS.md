# TASKS: <name>

> Template. Owner: Architect (writes) / Implementer (executes) · Stages S3-S4
> **Every task has an acceptance criterion and a verification method before work starts.**
> A task list updated at the end is a work of fiction. Update as you go.

**Status legend:** `todo` · `doing` · `blocked` · `review` · `done`

---

## Order

> Tasks are ordered by dependency, not by preference.
> **The signature moment is built early, not last.** Anything left to the end gets cut.

| # | Task | Depends on | Owner role | Acceptance criterion | Verified by | Status |
|---|---|---|---|---|---|---|
| 1 | Token system from `DESIGN.md` | — | Implementer | Every value in `DESIGN.md` exists as a CSS custom property | Visual diff against the design decisions | todo |
| 2 | <signature moment> | 1 | Implementer + Motion | <what "working" means concretely> | <how it is checked> | todo |
| 3 | | | | | | todo |

---

## Blocked

| # | Task | Blocked by | Needed from | Since |
|---|---|---|---|---|
| | | <gate / question / asset> | <who> | <date> |

## Findings raised

> From [frontend-build](../skills/frontend-build.md) step 7. Design could not be built as specified.
> **Never resolved by silent substitution.**

| # | Task | Specified | Problem | Options | Decision |
|---|---|---|---|---|---|
| | | | | A: <> B: <> | <who decided, when> |

## Dependency requests

> G2. Full format in [LIBRARY-POLICY.md](../LIBRARY-POLICY.md) section 6.

| Package | Requested | Status | Decided |
|---|---|---|---|
| | <date> | pending / approved / rejected | <date> |

---

## Writing a good task

**Acceptance criterion** — what is observably true when it is done. Not "build the hero" but "hero renders the display type at the specified clamp, the signature interaction responds within 200ms, and it works at 375px".

**Verification method** — how that is checked. A command, a Playwright assertion, a screenshot at a named width, or a specific manual step. If you cannot say how it will be verified, the criterion is too vague.

**Size** — one branch, ideally one sitting. A task spanning three days should be three tasks.

**Done** means: acceptance criterion met, production build passes, zero type errors, zero console errors, and every value from the token system. Not "it renders on the dev server".
