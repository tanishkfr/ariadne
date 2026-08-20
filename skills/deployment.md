# SKILL: deployment

**Trigger** — G3 granted. S6.
**Owner** — Implementer · **Class** — `R6`
**Inputs** — approved build
**Output** — a deployed preview or production release

**Deploying to production is G4 and requires explicit approval every time.** Approval for one deploy is not approval for the next. See [AUTONOMY-POLICY.md](../AUTONOMY-POLICY.md).

---

## Method

**1. Verify the production build locally.**

```bash
pnpm build
pnpm start
```

Then load it. A dev server passing tells you nothing about a production deploy — hydration errors, build-time failures, and font problems appear here first.

**2. Check what is about to be committed.**

```bash
git status
```

Before `git add`. Every time. The most common secret leak is a `.env` committed before `.gitignore` existed. Confirm `.gitignore` covers `.env*`, credentials, build output, and any private asset directory. See [PRIVACY-POLICY.md](../PRIVACY-POLICY.md) section 6.

**3. Push the branch** (G4) and let the preview build.

**4. Verify on the preview, not on localhost.** The preview is where you find missing environment variables, broken image optimisation, real font loading behaviour, and anything that quietly depended on a local file. Re-run the performance checks here — localhost numbers do not transfer.

**5. Walk the preview** through [browser-qa](browser-qa.md): every route, console clean, responsive widths, the signature moment, the non-happy-path states.

**6. Production deploy is a separate G4.** Present:

```
SHIP REQUEST
Branch:     <name>            Target: <environment>
Contains:   <what changed, one line>
QA:         <QA.md link; G3 granted? yes/no>
Preview:    <url, verified>
Reversible: <how to roll back>
```

**7. Verify after deploying.** Load the production URL. Check the console. Confirm the deployed commit is the one you expected. A deploy that succeeded in CI and is broken in the browser is a normal occurrence.

---

## Environment variables

Set by **you**, in the platform's own UI. Never by an agent, never in a file, never in a commit.

An agent may say which variables are needed and what they are for. It may not read, echo, or paste a value. See [PRIVACY-POLICY.md](../PRIVACY-POLICY.md) section 2.

---

## Vercel notes

- Preview per branch is the default and is the main reason this workflow is cheap — every branch gets a real URL to review.
- The Hobby tier is free for non-commercial use. **Client work requires a paid plan** — check current terms before deploying commercial work, and bill it to the project ([BUDGET-POLICY.md](../BUDGET-POLICY.md) section 6).
- Domains for client projects are registered and owned by the client, not by you.

Verify platform limits and terms live rather than from memory ([RESEARCH-POLICY.md](../RESEARCH-POLICY.md)); they change.

---

## Rollback

Know the rollback before deploying. On Vercel that is promoting the previous deployment; in git it is reverting the merge commit. **If you cannot state how to undo it, do not do it** — that is the whole test for whether an action is safe.

---

## Done when

Production build verified locally · nothing secret staged · preview verified in a browser · G4 granted explicitly · production verified after deploy · rollback path known.

---

## Failure modes

| Failure | Countermeasure |
|---|---|
| `.env` in the first commit | `git status` before `git add`, always |
| Deploying without a G4 | Every deploy, every time |
| Verifying on localhost and calling it done | Preview is the source of truth |
| Missing environment variables found by users | Step 4 catches them |
| No rollback plan | State it before deploying |
| Client work on a free tier | Check the terms; bill the plan to the project |
