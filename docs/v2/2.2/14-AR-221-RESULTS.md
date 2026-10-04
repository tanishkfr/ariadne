# 14 — AR-221 Results

```text
AR-221 COMPLETE — READY FOR RENDERED DESIGN CRITIQUE
```

Everything below was produced by running the code in this repository. Where a number
varies between runs, that is said, rather than one run's number being presented as the
truth.

## 1. What was added

```text
src/ariadne_engine/design_execution/
├── __init__.py                  module map and summarise_state
├── plan.py                      DesignImplementationPlan, approval binding, precedence
├── inventory.py                 component discovery, reuse decisions, licence, dependencies
├── packet.py                    worker packet, context attribution, omission record
├── grounding.py                 materiality, cloning, accessibility regression, classifier
├── changes.py                   change records, design trace, change summary
├── execution.py                 implement → validate → bounded repair → escalate
├── vertical_slice.py            the real end-to-end slice
└── fixtures/
    ├── desktop-tool/            a real TypeScript front end, pre-implementation
    └── implementation-references/  a frozen, licensed implementation reference

scripts/
├── test-design-execution.py              68 tests
├── test-design-execution-mutations.py    25 mutations
└── test-design-execution-adversarial.py  35 bypass attempts
```

Extended, not duplicated: `contracts.py` (vocabulary, five record validators, three
category maps, four collection keys), `persistence.py`, `api.py` (five PROVISIONAL
operations), `public.py`, `events.py` (eight names), `policy.py` (one
`transport_tool()` seam), `design_reference/normalize.py` (`size_bytes`),
`design_reference/vertical_slice.py` (`SLICE_TASK_ID`), and `scripts/ariadne.py`
(three verbs).

## 2. The vertical slice

**Input.** AR-220's request, carried forward:

> "Create a serious desktop developer tool. It should feel precise, dense and calm,
> but not like a generic AI dashboard."

**Fixture.** `fixtures/desktop-tool/` — a real TypeScript desktop developer tool:
5 component files with exported primitives, 28 CSS custom properties, a `DESIGN.md`,
its own route table, a zero-dependency build, and 14 of its own tests. It is committed
in the state a template scaffold leaves a project in: a centred welcome panel, glass
cards with `backdrop-filter`, an oversized gradient hero, and every action shaped like
a pill. Working and generic — which is the honest starting point.

**The path, all of it real:**

```text
project inspection     5 component files, 28 CSS variables, accent #4f7cff
AR-220 chain           reference set + 12 principles, from the frozen corpus, offline
grounded direction     ddr_…  status candidate
refusal                "only an approved direction can be implemented"
explicit approval     design.approve_direction(…, identity="ar221-fixture-operator")
implementation refs    pattern note REUSE_ALLOWED · registry INSPECT_ONLY
                       · dependency request REFUSED_PENDING_HUMAN_G2
component inventory    6 REUSE_PROJECT_COMPONENT · 1 BUILD_CUSTOM_COMPONENT
plan                   dip_…  10 constraints · 2 forbidden patterns · 2 suppressed
worker packet          14 675 bytes · 22 308 of 111 885 reference bytes · 4 omitted
implementation         12 edits across 4 files
mechanical validation  typecheck PASSED · build PASSED · tests PASSED
trace                  55 links · 0 gaps
outcome                MECHANICALLY_VALIDATED
```

**Grounding.** 12 change records: 9 `GROUNDED`, 3 `GROUNDED_INCIDENTAL`, **0**
ungrounded, **0** accessibility regressions, **0** cloning findings.

| File | Change | Material categories |
|---|---|---|
| `src/styles/app.css` | surface-and-accent-restraint | component_geometry, navigation_structure, primary_layout |
| `src/styles/app.css` | remove-centred-hero | component_geometry, primary_layout, type_scale |
| `src/styles/app.css` | remove-glass-cards | component_geometry, primary_layout, type_scale |
| `src/styles/app.css` | replace-pill-navigation | component_geometry, navigation_structure |
| `src/styles/app.css` | tighten-rows-and-restore-focus-ring | — (incidental) |
| `src/styles/app.css` | restore-visible-focus-ring | interaction_model |
| `src/styles/app.css` | remove-decorative-hover-motion | motion_system, navigation_structure |
| `src/lib/panel-split.ts` | add-keyboard-operable-divider | interaction_model |
| `src/app/shell.ts` | restructure-shell | navigation_structure |
| `src/app/shell.ts` | reuse-project-primitives | — (incidental) |
| `src/app/shell.ts` | remove-welcome-panel | — (incidental, removals recorded) |
| `tests/direction.test.ts` | add-direction-regression-tests | brand_color, component_geometry, interaction_model, navigation_structure |

Navigation, workspace layout, toolbar, panels, typography and surface hierarchy all
changed, and every material decision names the constraint that required it.

## 3. The five proofs the brief asked for

### Project identity survived

Before and after, from the run record:

```text
accent in src/styles/tokens.css          #4f7cff   unchanged
"#4f7cff" in src/styles/app.css          absent    the token is referenced, not repeated
"var(--accent)" in src/styles/app.css    present   the brand colour is used, from the token
--font-sans restated in app.css          absent    the product typeface is not borrowed
```

The plan's colour constraint is sourced `PROJECT_IDENTITY` with evidence
`src/styles/tokens.css`, and the CSS change that could have introduced a literal colour
is `GROUNDED` against it.

### The counter-reference changed the result

AR-220's counter-reference is a `CURATED_DESIGN_ANALYSIS` whose finding is *"do not
adopt a generic AI dashboard: a glassmorphic card grid with gradient glows, a centred
hero and no information hierarchy."* Two AVOID treatments became machine-checkable
prohibitions:

```text
avoid-051  detectors: backdrop-filter, -webkit-backdrop-filter, card-grid,
                       glass-card, hero-card
avoid-067  detectors: card-grid, glass-card, hero-card
```

and the post-implementation stylesheet contains **none** of
`backdrop-filter`, `linear-gradient(`, `radial-gradient(`, `border-radius: 999`,
`glass-card`, `card-grid`. Not because the implementer happened to avoid them, but
because the plan said not to and the classifier would have refused them.

A third AVOID treatment set — *"oversized gradients"* on a reference with no literal
signature to check — is bound to the plan and travels to the worker, and recorded as
**not mechanically detectable**. It was not given an invented detector.

### Component reuse

Six of seven primitives were found in the project and reused rather than regenerated;
`DataTable` had no local equivalent and no approved registry entry, so it was built
inside the project. `src/lib/ui.ts`, `src/lib/icons.ts` and `src/styles/tokens.css`
were in `FORBIDDEN_SCOPE` for the entire run — reusing the components and protecting
the identity that makes reuse meaningful are the same discipline.

### Implementation reference use

```text
source         ariadne pattern note: two-pane split with a keyboard-operable divider
license        Apache-2.0 (this repository)
revision       frozen fixture, 1602 bytes
files_inspected fixtures/implementation-references/two-pane-split.md
reuse_status   REUSE_ALLOWED
aesthetic_inherited  false
```

The *contract* was taken — separator role, `aria-orientation`, arrow/`Home`/`End`
steps, clamped bounds, collapse-preserves-width — and the code written against the
project's own `panel()` primitive and `density` helpers. No source was copied, and the
reference's aesthetic was not adopted; the record says so explicitly.

The registry candidate was recorded as `INSPECT_ONLY` with
`install_authority: "none — human G2 required"`, and the dependency request for
`shadcn-ui resizable panels` — the package the reference would have pulled in — ended as
`REFUSED_PENDING_HUMAN_G2` with `installed: false`.

### Ungrounded detection, both directions

The brief's controlled case — a new purple gradient hero — is detected, by the strictest
available detector, as `REFERENCE_CLONING`, because it literally reproduces a treatment
the approved direction ruled out. A variant with no gradient token (new radius, new
typeface, a decorative `@keyframes`) is `UNGROUNDED_DESIGN_CHANGE` with
`"material design change (brand_color, type_family, motion_system, …) with no approved
basis"`.

The false-positive direction is tested too: a change that references `var(--accent)`
is **not** flagged as a `brand_color` change, because obeying identity is not changing
it.

## 4. Counts

| | |
|---|---|
| AR-221 tests | **68 / 68** |
| AR-221 mutations | **25 / 25 caught** |
| AR-221 adversarial attempts | **35 / 35 refused** |
| AR-220 tests | 109 / 109 |
| AR-220 mutations | 22 / 22 |
| Engine core | 578 / 578 |
| Decision Runtime | 510 / 510 |
| Decision mutations | 9 / 9 |
| Runtime mutations | 38 / 38 |
| Release tests | 97 / 97 |
| Distribution | 55 / 55 |
| Runtime bundle | 19 / 19 |
| Release benchmark subset | 79 pass / 0 fail |
| Wheel install | 14 / 14 |
| Repository contract | PASS |
| Public API surface | 37 stable, 71 provisional |

`scripts/release-check.py` runs all nine engine suites — AR-220's two and AR-221's
three included — and names each one in its report. Five of the nine used to run
*un-named*: the report appended a suite's `PASS ` line when one existed and silently
omitted the suite otherwise, so "engine suites PASS" covered four suites and implied
nine. The detail now falls back to a suite's last non-empty line.

## 4b. One number that varies

`reference_bytes_transported` differs between runs of the vertical slice — 20 471 in
one, 22 308 in another — because it depends on which references the approved
direction's extracted principles happened to cite, and that depends on the run
timestamp that names each record. The plan and the packet are internally consistent
within a run; the figure is not a constant and should not be quoted as one.

## 5. Defects found while building this, and fixed

Nine genuine defects. Each was found by running the thing against real data, not by
inspection.

| # | Defect | How it surfaced |
|---|---|---|
| 1 | References recorded no byte size, so Context Economics was unmeasurable | asked for `raw_reference_bytes_available` and got 0 |
| 2 | Component inventory reported **zero** components and **zero** tokens for a project that has both | the first real slice against Beacon |
| 3 | Every package-manager validation check reported `BLOCKED` on Windows | the first slice that ran validation |
| 4 | `accessibility_regressions` could never detect anything: it included removed lines in the "after" set | the first slice that added a focus-ring change |
| 5 | `\blabel\b` as an accessibility signal matched `.cta-label`, so deleting a CSS class read as removing a label | the same slice |
| 6 | Materiality read *removed* lines, so the edit the AVOID treatment required was flagged as the failure it prevented | the same slice |
| 7 | The clone detector scanned plan detectors over the whole file but structural patterns per line, so the project's own regression test was flagged | the same slice |
| 8 | `resolve_precedence` only suppressed a constraint arriving *after* the one that beat it, so declaration order silently decided precedence | the precedence tests |
| 9 | `worker_transition` defaulted any unrecognised status to `blocked`, turning a typo into a false escalation | the repair-budget tests |

Four more were found by **mutation testing** — tests that documented a rule they did
not actually enforce:

* dropping `reference_ids` from a grounded change, and
* dropping the direction's `requirement_bindings`, and
* widening the grounding set to any declared constraint, and
* the ADAPT `project_anchor` check being unreachable.

And four by **adversarial review** being wrong about itself: the first version of that
script reported three attacks as held that had only hit a *previous* attack's
stale-approval check. It now snapshots and restores the run between attempts, and says
so at the top of the file.

### Two more, found the hard way

Both were found while investigating why the suite had become slow, and both are about
the harness rather than the product:

| # | Defect | How it surfaced |
|---|---|---|
| 10 | Validation subprocesses inherited the caller's stdin, so a child that read it could block until something else timed out | the first slice run under a supervisor reported as a hang |
| 11 | The mutation harness edited files in place with no way to undo an interrupted run | an interrupted mutation run left M21 applied: the repair loop became `attempt_index = attempt_index` and the suite ran forever |

Defect 11 is the more interesting one, because it was invisible. The mutated file lives
in an **untracked** directory, so `git diff` reported nothing, and the first check —
"is the tree clean?" — was structurally incapable of noticing. The symptom was a slow
test suite, which sent the investigation into `shutil.which` and `pathlib` before the
actual cause turned up in the source itself.

The fix is structural rather than a matter of care: the harness writes the replaced
bytes to `.ariadne-mutation-restore.json` *before* editing, clears it only after
restoring, and restores any marker it finds on startup. The file is gitignored. A
harness that edits files in place must be able to undo itself, because being interrupted
is not an exceptional case.

Defect 10 is worth keeping even though nothing in the current fixture reads stdin: the
fix is one keyword, and the failure mode it prevents is a run that hangs for reasons
unrelated to the code under test.

## 6. Known limitations

1. **Nothing here judges appearance.** `MECHANICALLY_VALIDATED` means the code exists
   and passes its checks. Whether it *looks* like the approved direction is AR-222, and
   needs a real browser render this phase deliberately does not build.
2. **The slice's implementer is scripted.** `IMPLEMENTATION_EDITS` is a deterministic
   edit table, not a live model, and the docstring in `vertical_slice.py` says so. What
   the slice genuinely exercises is everything around it: the plan, the precedence
   rules, the scope boundary, the per-edit classification, the provenance, and a real
   `tsc`/build/test run. A live model replaces the table and nothing else.
3. **The fixture's devDependencies are installed once, offline, from the local npm
   cache.** Ariadne does not install them; the slice hard-links an installation that
   already exists and reports `BLOCKED` honestly when it does not. On a machine without
   that cache the slice's validation assertions cannot run and say so.
4. **Cloning detection is structural, not a plagiarism detector**, and the record says
   so. It catches brand assets, external stylesheets, pasted source headers and
   forbidden literal patterns introduced by a change. It cannot tell deliberate
   reimplementation from coincidence.
5. **Two AVOID treatments in the slice have no literal signature** and are recorded as
   not mechanically detectable rather than given an invented detector. A prohibition
   nobody can evaluate stays a prohibition a reviewer must apply.
6. **Materiality is a declared list.** Eleven categories. A large decorative animation
   is material; a 1px correction is incidental. The boundary is stated, bounded and
   tested, but it is a judgement the project can revisit — and every judgement of that
   kind is a place where a reasonable person could disagree.
7. **The component directory list is a heuristic**, now with a bounded fallback. It
   finds framework layouts and flat `src/lib` structures; a project that hides its
   components somewhere undeclared may still report zero, and the record then says a
   fallback scan ran so the negative result is at least checkable.
8. **Precedence requires a declared category to collide.** Two constraints that
   genuinely conflict across categories — a `layout` claim and a `navigation` claim
   about the same region — do not suppress each other. `CATEGORY_GROUNDS_MATERIAL` is
   the declared correspondence, and it is the place a future conflict would have to be
   added.
9. **No rendered evidence, no rendered claims.** Nothing in AR-221 opens a browser.
   Route availability and runtime smoke are the boundary of what §30 permits, and this
   phase did not need even those.

## 7. What was deliberately not done

* No screenshot, capture or comparison pipeline. That is AR-222.
* No reference-aware visual critique loop. That is AR-222.
* No MCP or CLI provider. Both are optional; capability absence degrades safely and is
  tested.
* No second store for reference records. `DesignReference` from AR-202D is extended.
* No parallel design executor. The S4B repair budget, the transport allowlist, path
  containment, injection scanning and the event log are all the existing ones.
* `VERSION` is untouched. AR-221 is an unreleased phase boundary.
* Boreal is untouched.

Next: AR-222 — Grounded Rendered Critique & Refinement.