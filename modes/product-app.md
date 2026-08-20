# MODE: Product app

Sustained interaction, real state, returning users. **The mode where architecture outranks visual direction** — and the mode most at risk of quietly becoming an enterprise dashboard nobody asked for.

---

## Detection

**Signals:** "app", "tool", "dashboard", "users can", "log in", "save", "track", "manage".

**Tie-break:** if state outlives the session — accounts, saved data, returning users — this mode wins even when it looks like a site ([ROUTER.md](../ROUTER.md) 3.2).

**Not this mode if:** the "app" is really a marketing site with a form (premium client website), or a single-session toy (game/experiment).

---

## Questions

1. **What is the single core loop?** — the one thing a user does repeatedly. No default.
2. **What must persist between sessions?** — default: nothing. Push hard on this. Most "apps" do not need a backend.
3. **Who else touches the data?** — default: only the user. Multi-user changes everything.
4. **What is explicitly out of scope for v1?** — default: settings, admin, analytics, teams, sharing
5. **Is this yours or a client's?** — determines quality bar and privacy handling

Question 2 is the highest-leverage question in this mode. "It saves your work" might mean localStorage, not a database and auth.

---

## Assumptions

| Area | Default |
|---|---|
| Auth | **None.** Requires an explicit requirement, and it is a scope change ([AUTONOMY-POLICY.md](../AUTONOMY-POLICY.md)). |
| Database | **None** until persistence across devices is genuinely required |
| Persistence | localStorage or URL state first |
| Admin panel | **Never** by default |
| Analytics | **None** by default |
| Settings page | Not until there is something worth configuring |
| Multi-user | Single-user until stated otherwise |

**These defaults exist because you said you do not want SaaS scaffolding by default.** Each one is a scope change requiring approval, not a natural next step.

---

## Documents

`PROJECT.md` → **`ARCHITECTURE.md`** → `DESIGN.md` → `TASKS.md` → `AGENTS.md` → `HANDOFF.md` → `QA.md` → `RETROSPECTIVE.md`

**Architecture comes before design here** — the only mode where it does. The data and state model constrain what the interface can be, and discovering that after the direction is locked is expensive.

## Skills

discovery, grilling, live-research, component-research, design-direction, frontend-build, browser-qa, accessibility, performance, evaluation, deployment

Motion is lighter than in visual modes: feedback and continuity, rarely character.

## Stages

S3 is **light on visual direction, full on architecture**. When design and architecture conflict in this mode, **architecture wins** and design adapts ([AGENT-ROLES.md](../AGENT-ROLES.md) role conflicts).

## Gates

All except G5. **G2 fires more often here** — real functionality creates real dependency pressure, and this is the mode where component-library soup accumulates fastest.

---

## Quality bar

- Scorecard **38+** — lower than the visual modes, because usability outranks distinctiveness here
- Lenses: **senior product designer**, frontend engineer, accessibility
- Senior product designer below 32 means not ready for real users
- Every state designed: empty, loading, error, success. **This is where AI-assisted builds are consistently thin**, because the happy path is what gets built and demoed.

A product app is allowed to look quieter than a portfolio piece. It is not allowed to look unconsidered — and "it's a tool, so it can be plain" is the excuse that produces the generic dashboard.

---

## Avoiding the SaaS trap

The default AI response to "build an app" is: dashboard, sidebar, cards, settings page, auth. Almost none of that is usually needed.

Before adding any of it, ask:

| Feature | The question that kills it |
|---|---|
| Auth | Is there anything worth protecting, or multiple users? |
| Database | Does state need to survive a device change? |
| Dashboard | Is the user monitoring something that changes without them? |
| Settings | Is there a real preference, or just options nobody will change? |
| Admin panel | Is there an administrator who is not you? |
| Analytics | Will you actually act on the numbers? |

If the answer is no, it is a non-goal. Write it in `PROJECT.md` so it stays one.

---

## Failure modes

| Failure | Countermeasure |
|---|---|
| Building auth nobody needs | Default none; explicit approval required |
| A database for data that fits in localStorage | Question 2, pushed hard |
| A dashboard because apps have dashboards | The table above |
| Happy path only | Every state designed, in the quality bar |
| Design locked before the data model | Architecture first in this mode |
| Component-library soup | G2 on every package ([LIBRARY-POLICY.md](../LIBRARY-POLICY.md)) |
| "It's a tool so it can look plain" | Quieter, yes. Unconsidered, no. |
