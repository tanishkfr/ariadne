# QA POLICY

The mechanical half of S5: what must be true, and what evidence proves it. Run by the Implementer.

The judgement half — is it any good — runs in a **separate session** by a Reviewer who has not seen this file or the build context. That separation is deliberate: [EVALUATION-RUBRICS.md](EVALUATION-RUBRICS.md).

**A build that passes everything here and scores 2/5 on creative direction has failed S5.** Both halves are pass/fail.

Output: [templates/QA.md](templates/QA.md).

---

## The evidence rule

| State | Requires |
|---|---|
| **Pass** | Command output, a measured number, or a screenshot |
| **Fail** | The same, plus severity and a proposed fix |
| **Not run** | A reason |

**"Looks fine" is not a QA result.** A check that was not run is recorded as *not run* — never as passed, never blank. An honest gap is useful; a false pass is worse than no QA.

## Severity

**Blocking** (G3 cannot be granted) · **Major** (fix, or waive in writing) · **Minor** (polish) · **Note**

Blocking by default: build failure · type error · console error · keyboard trap · missing focus states · contrast failure on body text · motion ignoring `prefers-reduced-motion` · broken layout at any tested width · a missing signature moment · any anti-generic row present.

**Exception:** patterns declared as accepted in `PROJECT.md` (**R-PAT-1**, [ROUTER.md](ROUTER.md) section 10) drop from Blocking to Note. They still appear in the report.

If the stated rationale is not visible in the result, the reviewer rejects it and the row returns to Blocking — the declaration covers the choice, not the craft.

---

## The escalation ladder

Cheapest first. **Never skip a rung upward** — each catches what the next would spend far longer finding.

```
1. Production build      free, seconds, catches the most
2. Typecheck + lint      free, seconds
3. Playwright script     free, repeatable, runs again tomorrow
4. Browser agent         slow, but sees what a human sees
5. Your own eyes         the only thing that catches "this feels wrong"
```

Rung 4 is where usage disappears. **Anything you will check twice becomes a Playwright script** — it costs about one browser-agent pass, then costs nothing forever.

---

## 1. Build, types, lint

```bash
pnpm build          # PRODUCTION build, not the dev server
pnpm tsc --noEmit   # zero errors
pnpm lint
```

The dev server hides hydration errors, build-time failures, and font loading problems — precisely the bugs that surface first on a deployed preview. `any` introduced during the task is Major. `@ts-ignore` without a reason on the same line is Blocking.

## 2. Console

Load every route. Zero errors, zero React warnings. **Hydration mismatches are Blocking** — a real correctness bug, not noise. Record route, message, source.

## 3. Routes and states

Every route loads. Every interactive element responds. **Empty, loading, error, and success states exist and are designed.** Forms validate with real messages.

This is where AI-assisted builds are consistently thin, because the happy path is what gets built and demoed.

## 4. Responsive

Test at **375, 768, 900, 1280, 1920.** The 900-1100 range breaks more layouts than any other and is the one people skip.

Per width: no horizontal scroll · no overlap · no clipped text · touch targets ≥44px · **the signature moment still works or has a designed equivalent.** Screenshot each.

## 5. Accessibility

Automated tools (axe, Lighthouse) catch roughly a third of real problems. Run one, fix what it finds, then treat it as finished — a clean automated report says almost nothing about whether the site is usable. The manual passes are the ones that count, and take about twenty minutes on a small site.

**Keyboard.** Unplug the mouse. Tab every flow. Every action completable · **focus visible at every stop** · logical order matching visual order · no traps · Escape closes overlays and returns focus · custom controls operable by Enter and Space.

Removed focus outlines are the most common failure in art-directed work. A *designed* focus state looks better than the default anyway — never remove without replacing.

**Contrast**, measured on rendered pixels, not token values — including text over images, over gradients, and in every state. 4.5:1 body, 3:1 large text and UI boundaries.

When a deliberately low-contrast direction fails, that is a **Design director decision**. Route it up. Quietly darkening the palette to pass breaks the direction.

**Structure.** One `h1` · no skipped heading levels · landmarks · `alt` on images (empty `alt=""` for decorative is a real answer) · lists are lists · buttons are buttons.

**Reduced motion.** Enable the OS preference, reload, confirm **content still appears**. Anything revealed by an animation must exist without it.

**Forms.** Real labels · errors tied programmatically to inputs · errors stated in text, not colour alone.

**Independence.** Nothing conveyed by colour, hover, or motion alone. Hover-only content does not exist on touch — this catches signature moments built around hover.

**Zoom 200%** without loss of content or function.

### The genuine tensions

| Tension | Resolution |
|---|---|
| Low-contrast palette | Design director decides. Often solved by raising body-text contrast only. |
| Custom cursors, hover interactions | Needs keyboard and touch equivalents — **decided at S3** |
| Heavy scroll choreography | Reduced-motion state designed at S3, not retrofitted |
| Text over imagery | A scrim, a treatment, or move the text |

**Decide these at S3.** Accessibility discovered at QA is a rebuild; accessibility designed into the direction costs nothing.

## 6. Motion

Every animation has a stated purpose ([DESIGN-MOTION.md](DESIGN-MOTION.md)) · 60fps on a mid-range machine · `transform` and `opacity` only for anything continuous · reduced-motion path verified · nothing essential delayed past ~1s · behaves on fast scroll, refresh mid-page, and back-navigation.

## 7. Performance

**Measure on the deployed preview, not localhost.** Localhost numbers are optimistic to the point of being meaningless — no real network, no cold start, warm caches. Measure before optimising.

| Metric | Target | Blocking above |
|---|---|---|
| LCP | < 2.5s | 4.0s |
| CLS | < 0.1 | 0.25 |
| INP | < 200ms | 500ms |
| JS (gzip) | < 200KB | project budget |
| Largest image | < 300KB | 1MB |
| Fonts | ≤ 3 files | — |

Causes, in order of frequency: images (usually the biggest win) · fonts · a heavy dependency or client components that should be server components · third-party scripts · unsized images causing shift.

**Fix the biggest thing, then re-measure.** One change at a time — bundled optimisations make it impossible to know what worked, and half usually did nothing.

**Never silently cut a designed feature to gain a metric.** If the signature moment is expensive, that goes to the Design director and then to you. Lazy-load it, degrade it on slow connections, reduce its scope — deletion is the last option. A portfolio piece with a 3.2s LCP and a memorable interaction may be the right call; a generic site at 1.1s that nobody remembers is not.

## 8. Screenshots

Required for G3, from the production build or preview: each route at 375 and 1280 · the signature moment · every non-happy-path state · the reduced-motion rendering.

**Look at them yourself.** Capturing evidence and checking it are different acts.

---

## 9. Deployment (S6)

```bash
pnpm build && pnpm start   # verify the production build locally
git status                 # BEFORE git add. Every time.
```

### Secret protection — set up once per repository, by you

**Nothing in the Builder OS installs this.** It is a manual step, it is not automatic, and if you skip it there is no safety net — `git status` discipline is all that stands between you and a committed key.

`.git/hooks/` is not committed, so a hook placed there does not travel with the repo and does not survive a fresh clone. The portable form keeps the hook **inside** the repository and points git at it:

```bash
mkdir -p .githooks
cat > .githooks/pre-commit <<'HOOK'
#!/bin/sh
# Blocks committing env files and obvious credentials. Not exhaustive.
if git diff --cached --name-only | grep -Eq '(^|/)\.env($|\.)|(^|/)(id_rsa|\.pem|credentials\.json)$'; then
  echo "BLOCKED: an env or credential file is staged."
  echo "Check 'git status'. If this is intentional, commit with --no-verify."
  exit 1
fi
if git diff --cached -U0 | grep -Eq '(sk-[A-Za-z0-9]{20,}|ghp_[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16})'; then
  echo "BLOCKED: staged changes look like they contain an API key."
  exit 1
fi
HOOK
chmod +x .githooks/pre-commit
git config core.hooksPath .githooks
```

The hook file is committed and travels with the repo. **The `git config` line is per-clone and per-machine** — anyone cloning the repo, including you on another machine, must run it again or the hook silently does nothing.

**What this does not do:** catch secrets already in history · catch a key pasted into a chat · catch formats it does not know · protect a clone where `core.hooksPath` was never set. It is a backstop for one common mistake, not a security control. `--no-verify` bypasses it entirely, which is the point — it must not block legitimate work.

The most common secret leak is a `.env` committed before `.gitignore` existed. Confirm `.gitignore` covers `.env*`, credentials, build output, and any private asset directory.

Push the branch (**G4**), then **verify on the preview, not localhost** — this is where you find missing environment variables, broken image optimisation, real font loading, and anything that depended on a local file. Re-run section 7 there.

**Environment variables are set by you, in the platform's UI.** Never by an agent, never in a file, never in a commit. An agent may say which variables are needed; it may not read or echo a value.

**Production deploy is a separate G4.** Know the rollback before deploying — promoting the previous deployment, or reverting the merge commit. **If you cannot state how to undo it, do not do it.**

Vercel: preview per branch is the default and is why this workflow is cheap. Hobby is free for non-commercial; **client work needs a paid plan** — verify current terms rather than trusting this line, and bill it to the project.

---

## G3 presentation

```
G3: BUILD COMPLETE
Mechanical:  <n> passed / <n> failed / <n> not run
Blocking:    <list, or none>
Major:       <list>
Accepted:    <patterns declared in PROJECT.md, now Notes>
Screenshots: <paths>
Preview:     <url>
Known gaps:  <what was not tested, and why>
Recommend:   ship | fix first | return to S3
```

**Known gaps may not be empty.** Something is always untested; naming it is what makes the rest of the report trustworthy.

The Reviewer's rubric scores arrive separately, from a session that did not see this document.

---

## Other modes

**Audit / review** — this checklist plus the rubrics run against someone else's build. Findings only.

**Content** — different checks entirely: originality, voice, hook quality, no fabricated metrics. [CONTENT-SYSTEM.md](CONTENT-SYSTEM.md). G5 replaces G3/G4.

**Game / experiment** — compressed: build, console, one responsive pass, the mechanic is legible without instructions, reduced-motion. Skip the performance budget unless performance is the point.
