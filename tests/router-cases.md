# ROUTER REGRESSION SUITE

Persistent test cases for the interpretation frame in [ROUTER.md](../ROUTER.md).

**Why this file exists:** the v0.2 refactor deleted `validation/` on the grounds that it had no consumer. That was right about dry-run narratives and wrong about executable test cases — **their consumer is every future router change.** For one version this suite existed only in a chat log and could not be re-run.

**Run it when:** ROUTER.md changes · a rule ID is added, edited, or removed · a mode is added or removed · before tagging any release.

**How to run:** paste each `Input` into a session primed with `ROUTER.md`, using [prompts/project-start.md](../prompts/project-start.md). Compare the emitted Routing Block against `Expect`. This is a **reasoning protocol, not a parser** — there is no automated runner and building one would mean building a language model. `scripts/check.py` verifies the suite's *structure*; a human runs the cases.

**Result vocabulary:** `PASS` · `FAIL` (wrong behaviour) · `FRICTION` (correct but needs unnecessary interaction) · `AMBIGUOUS` (the rules do not determine an answer — a spec bug, not a test failure).

**The only metric that must be zero: high-confidence wrong routes.** A LOW-confidence clarification is always preferable to a confident wrong interpretation.

---

## Category 1 — Core cases

The eight originals. These must never regress.

| # | Input | Expect |
|---|---|---|
| 1.1 | "something cool for my portfolio" | `ACTION=CREATE` · `OBJECT=UNRESOLVED` · `DEST=portfolio` · **LOW** · asks what kind of thing, with options · **R-DEST-1** |
| 1.2 | "build me something for my studio" | `ACTION=CREATE` · `OBJECT=UNRESOLVED` · **LOW** · asks · **R-DEST-1** |
| 1.3 | "a SaaS dashboard with 17 cards and glassmorphism" | `ACTION=CREATE` · `OBJECT=stateful app` · `product-app` · **HIGH** · does **not** refuse · asks once for rationale per pattern · **R-PAT-1** |
| 1.4 | "scrap the direction and start over" | `ACTION=RESTART` · no mode change · asks which layer · preserves research · **R-INT-1** |
| 1.5 | "build something like Burocratik" | `ACTION=CREATE` · `ARTIFACT=reference` · `client-or-portfolio` · **MEDIUM** · **not** audit-review · reference-analysis activated · **R-ACT-1**, **R-REF-1** |
| 1.6 | "make this into an interactive installation" | `ACTION=TRANSFORM` · `ARTIFACT=source` · target=installation · `game-experiment` · **HIGH** · **R-XFM-1** |
| 1.7 | "I don't know what I want, just something memorable" | `ACTION=CREATE` · `OBJECT=UNRESOLVED` · **LOW** · asks · **R-DEST-1** |
| 1.8 | "build this without APIs or new paid tools" | `OBJECT=UNRESOLVED` · **LOW** · **constraints captured verbatim** and never re-asked · **R-DEST-1** |

## Category 2 — CREATE with a reference

Tests that a reference never selects the mode. All four must route to a **build** workflow.

| # | Input | Expect |
|---|---|---|
| 2.1 | "Build something like Burocratik." | build + reference-analysis · **R-REF-1** |
| 2.2 | "Make something inspired by Burocratik." | same as 2.1 — wording change must not alter the route |
| 2.3 | "Use Burocratik as a reference for a new site." | `OBJECT=site` (explicit) · `client-or-portfolio` · **MEDIUM** |
| 2.4 | "Reinterpret Burocratik's visual language." | `ACTION=TRANSFORM` · target **UNRESOLVED** → **LOW**, asks "into what?" · **not** audit-review |
| 2.5 | "Copy Burocratik's homepage exactly." | routes to **CREATE**, is **not refused**; originality surfaces at S3 · **R-REF-2** |

## Category 3 — ANALYZE

Same nouns as category 2, opposite route. This pair is the sharpest test of `R-ACT-1`.

| # | Input | Expect |
|---|---|---|
| 3.1 | "Analyze Burocratik." | `ACTION=ANALYZE` · `ARTIFACT=subject` · `audit-review` · **HIGH** |
| 3.2 | "What should I learn from Burocratik?" | `audit-review` · **HIGH** |
| 3.3 | "Break down why Burocratik works." | `audit-review` · **HIGH** |
| 3.4 | "Which CMS should I use?" | `ACTION=ANALYZE` · **no subject** → a research question, **not** audit-review, **no project opened** · ROUTER 3.4 |

## Category 4 — Portfolio wording

Same noun, five routes. If any of these needs a keyword exception, the frame is wrong.

| # | Input | Expect |
|---|---|---|
| 4.1 | "Create my portfolio." | `OBJECT=portfolio site` · `client-or-portfolio` · **HIGH** |
| 4.2 | "Create something for my portfolio." | `OBJECT=UNRESOLVED` · **LOW** · asks · **R-DEST-1** |
| 4.3 | "Create a game for my portfolio." | `OBJECT=game` · `game-experiment` · **HIGH** |
| 4.4 | "Review my portfolio." | `ACTION=ANALYZE` · `audit-review` · **HIGH** |
| 4.5 | "Redesign my portfolio." | `ACTION=TRANSFORM(direction)` · `client-or-portfolio` · **HIGH** · **not** audit-review |

## Category 5 — TRANSFORM

| # | Input | Expect |
|---|---|---|
| 5.1 | "Turn this into an installation." | target=installation · `game-experiment` · **R-XFM-1** |
| 5.2 | "Adapt this for an installation." | same as 5.1 |
| 5.3 | "Convert this into a mobile experience." | target under-specified → **MEDIUM/LOW**, asks "mobile what?" |
| 5.4 | "Analyze this installation." | `ACTION=ANALYZE` · `audit-review` — **must not** be read as TRANSFORM |
| 5.5 | "Add a leaderboard to my game." | `ACTION=EXTEND` · **inherits game-experiment** · does **not** re-derive to product-app · ROUTER 3.4 |

## Category 6 — RESTART

All must be recognised without special phrasing, and none may delete work.

| # | Input | Expect |
|---|---|---|
| 6.1 | "Start over." | `RESTART` · asks which layer |
| 6.2 | "Scrap this direction." | `RESTART` · layer=direction |
| 6.3 | "The concept isn't working." | `RESTART` · layer=concept |
| 6.4 | "Let's rethink the whole thing." | `RESTART` · layer=whole project → S1 |
| 6.5 | "Keep the research but abandon the visual direction." | `RESTART` · layer=visual · **research explicitly preserved** · **R-INT-1** step 3 |

## Category 7 — Anti-generic intent

The deliberate/accidental split. This is what makes `R-PAT-1` more than a loophole.

| # | Input / situation | Expect |
|---|---|---|
| 7.1 | "Glassmorphism because the interface is a fictional 2008 OS and the material language is the narrative" | **Accept** · rationale type `narrative` · logged |
| 7.2 | "Use glassmorphism because I like glassmorphism" | **Challenge once.** If restated, accept and log as `preference` — it is the user's project. **Never challenge twice, never block.** |
| 7.3 | Agent produced glassmorphism; user never asked | **Blocking** at QA — not an accepted pattern |
| 7.4 | "Card grid — the user monitors six live data streams" | **Accept** · `functional` |
| 7.5 | Card grid appears with no declaration | **Blocking** |
| 7.6 | "A dashboard because it's a dashboard product" | **Challenge once** — what changes without the user watching? |
| 7.7 | Four+ patterns declared with real reasons | **All accepted.** There is no numeric cap. |

## Category 8 — Constraint preservation

| # | Input | Expect |
|---|---|---|
| 8.1 | "no APIs or new paid tools" | Already the default. Logged as a constraint, **not asked about**. |
| 8.2 | "must work offline" | Captured verbatim, carried to `PROJECT.md`, survives to S4 |
| 8.3 | Constraint stated at S1, project reaches S4 | **Never re-asked, never silently dropped** · ROUTER 5 |

---

## Result log

Append a dated run. Do not overwrite — a regression is only visible against history.

### Run: 2026-08-21 · v0.3.1 · post-P0 structural fixes

| Category | Cases | Pass | Fail | Friction | Ambiguous |
|---|---|---|---|---|---|
| 1 Core | 8 | 8 | 0 | 0 | 0 |
| 2 CREATE + ref | 5 | 5 | 0 | 0 | 0 |
| 3 ANALYZE | 4 | 4 | 0 | 0 | 0 |
| 4 Portfolio | 5 | 5 | 0 | 0 | 0 |
| 5 TRANSFORM | 5 | 5 | 0 | 0 | 0 |
| 6 RESTART | 5 | 5 | 0 | 0 | 0 |
| 7 Anti-generic | 7 | 7 | 0 | 0 | 0 |
| 8 Constraints | 3 | 3 | 0 | 0 | 0 |
| **Total** | **42** | **42** | **0** | **0** | **0** |

**High-confidence wrong routes: 0.**

**Method caveat, stated because it matters:** this run was executed by tracing each input against the written rules, by the same author who wrote them. That is weaker evidence than an independent run and weaker still than a real project. Every expectation above cites the rule that justifies it, so the reasoning is checkable rather than trusted. **Treat this as a structural baseline, not proof of behaviour.**

**Not yet exercised by any real project:** category 6 in a live build with real files at stake · category 7 where a declared pattern reaches QA · `EXTEND` on a project that already has momentum.
