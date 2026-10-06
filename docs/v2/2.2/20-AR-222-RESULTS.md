# 20 — AR-222 Results

> What actually happened when Ariadne rendered its own work and looked at it.

Everything below was measured in this repository. Where a number is an estimate it says
so, and where something did not work it is reported rather than smoothed over.

---

## 1. Baseline, and one discrepancy worth stating

AR-221's claimed baseline did not reproduce. `test-design-execution.py` gave **67/68**:

```
AssertionError: the real vertical slice reaches mechanical validation
```

The cause was not a code defect. The Beacon fixture's `node_modules` was not installed,
so `tsc` could not run — and the assertion that failed explicitly guarded against exactly
that (*"the fixture's devDependencies must be installed for this assertion to mean
anything"*). `npm ci` from the committed lockfile fixed it. This is recorded because the
brief said not to trust the counts over the tree, and it was right not to.

Baseline once green:

```
Engine core             578/578      Release tests             97/97
Decision Runtime        510/510      Distribution              55/55
Decision mutations        9/9         Bundle                    19/19
Runtime mutations        38/38        Wheel                     14/14
AR-220                  109/109       Benchmarks (release)      79/79
AR-220 mutations         22/22        AR-221                     68/68
AR-221 mutations         25/25        AR-221 adversarial         35/35
check.py                 PASS
```

## 2. What the audit found

AR-222 extends rather than duplicates. Reused **unchanged**: `render.py`'s
`CaptureArtifact` / `record()` / `verify()` / `currentness_problems()` / the five-state
ladder; `critique.py`'s `FINDING_REQUIRED`, `_evidence_preconditions`,
`BROAD_SCOPE_TOKENS`, `propose_refinement`, `resolution_ledger`; `review.py`'s S5
independence; all four existing vocabularies; `ValidationRunner`; `capabilities.observe`.

Genuinely missing: a bounded capture plan, a real rendering capability (AR-200's
`LocalBrowserAdapter` was an explicit refusal), exact source binding for a dirty
worktree, a per-run capture manifest, a rejection path for unusable artifacts, and any
notion of capture economics.

## 3. What was built

`src/ariadne_engine/rendered_critique/` — eight modules, ~4,000 lines:

| Module | Role |
| --- | --- |
| `source.py` | `render_source_digest`, dirty-worktree binding, `staleness()` |
| `plan.py` | `RenderCapturePlan`, material bases, capture budget |
| `adapter.py` | `RenderAdapter` contract, `ChromiumRenderAdapter`, `LocalServer` |
| `evidence.py` | `RenderedEvidenceSet`, artifact/runtime validation, evidence-ladder join |
| `critique.py` | reviewer whitelist, findings, coverage, alignment, counter-reference |
| `refinement.py` | `RefinementPlan`, bounded scope, validation gate, closure |
| `trace.py` | `RenderedDesignTrace` |
| `vertical_slice.py` | the Beacon slice |

Plus `contracts_bridge.py`, four contract validators, seven new failure kinds, six new
event types, and `browser-render` added to `RENDER_CAPTURE_METHODS` with the same
provenance obligation as a fixture capture.

## 4. The vertical slice — real numbers

Beacon, the AR-221 fixture, rendered by real Chromium via Playwright on `win32`.

**Capture plan** — 6 targets, all justified:

```
primary_viewport_states  2    viewport-state @ 1440x900 (default, reduced-motion)
interaction_states       2    .btn--primary focused, .nav-item focused
responsive_captures      2    1024x768, 390x844
theme_variants           0    Beacon has one theme; none was manufactured
```

**Evidence** — 2 evidence sets, 12 captures, 0 skipped, 0 failures:

```
before   6 captures  167,142 bytes  5.312s  COMPLETE
after    6 captures  167,614 bytes  5.453s  COMPLETE
total   334,756 bytes  10.765s  capture time
         9.125s  mechanical validation (tsc + build + npm test, twice)
```

**Findings.** Both `DETERMINISTIC`, both discovered by reading rendered output rather
than by reading test output:

| Severity | Dimension | Finding | Final state |
| --- | --- | --- | --- |
| minor | hierarchy | `'Request'` appears in two visible headings 20px apart — the panel header and the in-body `<h1>` | persistent |
| major | responsiveness | at 390px the log table reaches 568px; `method` and `path` columns are cut off and unreachable | persistent (12 → 5 elements) |

**Repair.** One bounded CSS edit to `src/styles/app.css`, mechanically validated
(`npm run typecheck`, `npm run build`, `npm test` — all PASSED), re-rendered, and
independently re-reviewed:

```
attempt 1   applied   validation PASSED   re-render COMPLETE
           resolved 0   persistent 2   new 0
attempt 2   no bounded edit derivable -> stopped
```

**Final status: `RENDERED_WITH_KNOWN_FINDINGS`** — 0 resolved, 2 persistent, 0 new,
0 escalated. Visual acceptance `NOT_CLAIMED`; human acceptance `NOT_GRANTED`.

The repair improved the defect (12 clipped elements → 5) without eliminating it, and
AR-222 says so rather than claiming a win.

## 5. Defects found in this milestone's own code

Five real ones, all found by running rather than reading:

1. **`by_id()` returned copies.** Every mutation in `refinement.py` — scope enforcement,
   validation gating, finding closure — was silently a no-op. The no-self-review guarantee
   was vacuous.

2. **Inspection ran before capture.** `inspect()` focuses every focusable element and
   blurs the last one, so photographing *after* it captured the default state. The
   "focused" capture was byte-identical to the unfocused one.

3. **The first repair blanked the narrow layout.** `.app` pins `grid-template-rows: 100%`;
   collapsing only the columns pushed the workspace out of view entirely. The system
   reported the finding `VERIFIED_RESOLVED`, because a blanked page has no headings to
   complain about. Fixed by having capture plans declare required structural regions.

4. **Focus indication was OR-ed across all elements.** One well-styled control satisfied
   the check and hid every control showing nothing.

5. **`LocalServer.start()` raced.** It returned its URL right after `Popen`, so the first
   navigation could reach a port nothing was listening on. Every capture was refused and
   the failure surfaced as *"no validated capture is available to critique"* — far from its
   cause. Reproduced in ~1 fresh process in 4. This is the defect most likely to have been
   filed as flakiness and closed.

Plus one false *report*: this milestone initially claimed Beacon's primary button had no
focus ring. It has a clear one. The reading was an artifact of defect 2.

## 6. Counter-reference review — corrected

The first run reported `glassmorphism: PRESENT` and `generic-card-grid: PRESENT` on a
Beacon stylesheet that has neither. The scan was matching Beacon's own regression test:

```typescript
test("the stylesheet keeps no backdrop-filter glass", ...)
assert.doesNotMatch(await css(), /backdrop-filter/)
```

A test asserting a pattern is *absent* necessarily contains it. The corpus is now
stylesheets and templates only. Corrected result:

```
glassmorphism      ABSENT      gradient-hero      ABSENT
pill-overload      ABSENT      excessive-glow     ABSENT
generic-card-grid  ABSENT
```

A check that cries wolf on its own regression test is worse than no check.

## 7. Test counts

```
AR-222 suite        87/87
AR-222 mutations    40/40
AR-222 adversarial  27/27
Benchmark (release) 89/89   (79 before AR-222, +10 new cases)
```

The mutation suite's 40 mutations are each a surgical deletion or inversion of one
load-bearing behaviour. A mutation that survives is a boundary that is not being
enforced, whatever the test count says.

**The mutation suite caught the absence of a test.** During the containment-test rewrite,
line-range surgery swallowed `a_launch_argument_may_not_carry_a_nul_or_an_implausible_length`.
The suite went green — 86/86 — and only the mutation *"browser launch argument
injection"* surviving revealed that a real guarantee had lost its coverage. This is the
clearest argument in the milestone for running mutations at all.

## 8. Adversarial review

27 attacks, all held. The ones that mattered most:

- **Stale render laundering** — edit the stylesheet after capture; refused as
  `STALE_RENDER_EVIDENCE` naming both digests
- **Critique self-certification** — reviewer = implementer; refused
- **Worker closes its own finding** — forged `reviewer_execution` on the stored record;
  `resolve()` re-derives independence rather than trusting it
- **Partial re-review** — closed a finding from a re-review that inspected 2 of the 4
  captures evidencing it; refused, *absence from an unreviewed capture is not resolution*
- **Hidden overflow** — a table reaching 568px in a 390px viewport inside a scrolling
  container, where the document never overflows; caught
- **Capture artifact tampering** — a digest disagreeing with the capture manifest, and a
  manifest naming a different artifact; both refused

## 9. Known limitations

Stated plainly, because a rendered-critique milestone that overstates its coverage is
worse than one that does not.

1. **The default reviewer is deterministic and says so.** It reports what a render can
   prove — overflow, focus indication, accessible names, clipping, runtime errors,
   duplicate headings. It does **not** judge hierarchy, density, or composition, and marks
   those dimensions `NOT_REVIEWED` rather than inventing criticism. A model or human
   reviewer supplies those through the same isolated packet.

2. **No model or human judgement ran.** `review_with()` is the seam and it is tested, but
   the slice used `deterministic_review()`. The four `NOT_REVIEWED` dimensions are honestly
   unjudged.

3. **Two findings remain open.** The duplicate heading needs a `shell.ts` structure
   decision; the residual clipping needs a different responsive approach. Neither is a
   bounded CSS edit, which is why attempt 2 stopped instead of guessing. That is §32
   working, not a failure — but it does mean the slice does not close conformant.

4. **Playwright is required in practice.** The abstraction is vendor-neutral and the
   probe is honest, but only the Playwright path is implemented. A different engine means a
   new adapter, not a rewrite.

5. **The launch retry is a mitigation.** Three bounded attempts at starting a browser,
   because it intermittently failed under gate load. Navigation, capture and inspection are
   never retried, and a test asserts that.

6. **Accessibility claims are bounded by construction.** Every capture records
   `not_established`, and nothing here asserts WCAG conformance.

7. **Loopback-only.** Rendering an arbitrary remote origin is a different threat model and
   is refused.

8. **`evaluate_readonly` is a grammar, not a sandbox.** It narrows what a malicious capture
   plan can ask for a page; it is not a defence against engine compromise.

9. **The mutation suite takes ~90 minutes.** Forty complete suite runs at ~133s each. The
   release gate budgets 6h. Two options would cut it — a browser-free subset, or parallel
   mutations — and both trade a real risk of reintroducing flakiness for wall-clock.

## 10. Where the phase closes

```
Requirement -> Principle -> Direction -> File -> Capture
                                          -> Critique finding -> Refinement -> Final capture
```

Trace: 17 principles, 1 direction, 4 files, 6 captures, 2 findings, 2 refinements,
2 final capture sets, **0 gaps**.

Zero gaps is worth qualifying: it means every capture supported a finding or a coverage
entry, not that the design is finished. The trace reports structure, not quality — a trace
that closed its own gaps would be asserting a completeness it did not measure.

The chain AR-222 was built to close is closed. And it closes honestly: the rendered result
**contradicts part of the approved direction's responsive intent**, and Ariadne says so
even though every test passes.

```text
The implementation worker does not get to decide whether its work looks right.
A screenshot without source identity is not evidence.
Source inspection cannot close a rendered-quality requirement.
References define principles, not pixels.
Critique may repair an approved direction; it may not secretly invent a new one.
Every repair must be mechanically valid, re-rendered, and independently re-reviewed.
Before and after are both evidence. Never overwrite history.
If the rendered result contradicts the approved direction, Ariadne should say so
even when all tests pass.
```