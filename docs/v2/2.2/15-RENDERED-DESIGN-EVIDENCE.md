# 15 — Rendered Design Evidence

> AR-202D introduced rendered design evidence as a concept: a capture artifact, bound to
> a revision, with a method that says how the bytes were made. What it did not have was a
> way to *produce* one, or any reason to believe the bytes depict the code.
>
> This document records what AR-222 adds to that model, what it deliberately reuses, and
> the one distinction the whole phase turns on.

## The gap AR-202D left open

AR-202D shipped three capture methods. Two of them were honest refusals:

| Method | What it is | What it proves |
| --- | --- | --- |
| `offline-fixture` | a deterministic adapter writing a manifest beside the artifact | a capture happened |
| `declared-observer` | an operator-declared external observer | the observer said so |
| `local-browser` (AR-200 `ADD`) | **an explicit stub that refused** | nothing |

The `LocalBrowserAdapter` seam existed with a docstring saying as much. That refusal was
correct and it was also the reason a rendered review could not happen: no browser, no
render, and `source_suggests` versus `rendred` never became a decision anyone could act
on. Worse, the only way to satisfy the old contract was to lie about the method.

AR-222 adds a third method that is real:

```
RENDER_CAPTURE_METHODS = ("offline-fixture", "declared-observer", "browser-render")
```

`browser-render` means: an artifact a real rendering engine produced in this run, bound
to the exact source digest and environment that produced it.

## Three kinds of proof, none impersonating another

This is the load-bearing distinction of the phase.

```
MECHANICAL EVIDENCE     build, typecheck, tests
RENDERED EVIDENCE       what actually appeared and behaved
REVIEW EVIDENCE         independent judgement that it satisfies the direction
```

A green build cannot answer a design question. AR-221 already reserved the vocabulary
for this — `implementation_run_problems` accepts `VERIFIED_BY_RENDERED_CHECK` only with a
`rendered_check_id`, precisely because "source inspection cannot stand in for one" — and
recorded `NOT_CLAIMED` with a reason. AR-222 supplies the id.

What is forbidden is the *reverse* direction too, and that is the half that gets
forgotten. Rendered evidence does not prove the code is correct; a screenshot of a
beautiful error page proves nothing about the intended interface. Nor does review
evidence become mechanical evidence: a reviewer saying "it looks right" does not typecheck
anything.

The rendered evidence set therefore records, per capture, what was checked mechanically
and what was checked visually, and never lets the second stand in for the first.

## What was reused, and what was genuinely missing

The instruction was to extend the existing model rather than build a second visual QA
system. Concretely:

### Reused unchanged

- **`ariadne_engine.render`** — `CaptureArtifact`, `record()`, `verify()`,
  `currentness_problems()`, `stale_records()`, the `CAPTURE_DIR` / `MANIFEST_NAME`
  convention, and the five-state evidence ladder
  (`UNVERIFIED < SOURCE_SUGGESTS < RENDERED < OBSERVED < VERIFIED`).
- **`ariadne_engine.critique`** — `FINDING_REQUIRED`, `_evidence_preconditions`,
  `BROAD_SCOPE_TOKENS`, `build_review`, `propose_refinement`, `resolution_ledger`,
  `independence_problems`.
- **`ariadne_engine.review`** — S5 independence, `worker_identities`, the requirement
  that both executions resolve to engine-created records.
- **`contracts.DESIGN_SEVERITIES`**, **`DESIGN_REVIEW_DIMENSIONS`**,
  **`MATERIAL_DESIGN_CATEGORIES`**, **`RENDERED_EVIDENCE_STATES`**.
- **`design_execution.execution.ValidationRunner`** — re-run, unchanged, for mechanical
  validation after every repair.
- **`capabilities.observe()`** — the browser is registered through the existing registry,
  with a probe artifact as evidence, so `RENDER_CAPABILITY_UNAVAILABLE` in one run is
  visible to a later one.

`contracts_bridge.py` exists specifically to hold this line: it re-exports the existing
vocabularies and refuses the ones that would conflict, so no AR-222-flavoured duplicate
of severity, dimension or evidence-state ever appears.

### Genuinely missing

1. **A bounded capture plan.** Nothing decided *what* to capture. The existing model
   described a capture once one existed.
2. **A real rendering capability.** The seam existed and refused.
3. **Exact source binding for a dirty worktree.** `revision_hash` binds a capture to a
   revision. During an intentional repair there is no revision to bind to.
4. **A capture manifest per run.** AR-202D had a per-capture manifest; nothing
   aggregated a whole planned run under one source identity.
5. **A rejection path for unusable artifacts.** Nothing distinguished a blank viewport
   from the intended interface, and nothing needed to.
6. **Capture economics.** No bound on how many captures a run may take.

## The evidence set

One `RenderedEvidenceSet` per capture run, written as
`rendered-evidence-set.json` beside the artifacts. Distinct from AR-202D's
`capture-manifest.json`: that one proves a single artifact came from a capture; this one
aggregates a whole run under a single source identity.

Each capture carries route, state, viewport, device scale, theme, artifact path, digest,
byte count, capture timestamp, source digest, the runtime checks, the accessibility
checks, and the artifact validation verdict. A PNG with no accompanying metadata is a
mystery object — a reviewer cannot tell which state it shows, and nothing can detect that
it is stale.

## Artifact validation

An artifact can exist, open correctly, have a plausible size, and still be evidence of
nothing. Each of these produces a real PNG:

| State | What it means |
| --- | --- |
| `VALID` | usable as evidence of the interface |
| `BLANK` | zero bytes, or a uniform image |
| `LOADING` | the page still declared itself busy |
| `ERROR_DOCUMENT` | the browser's own error page, or an error response |
| `NO_CONTENT` | the shell loaded but the target content did not |
| `UNREADABLE` | not a PNG, or the header cannot be read |

The `NO_CONTENT` case earned its place during the vertical slice. A repair that collapsed
a layout to zero height still renders a nav rail, still says "Request" and "History",
and produces a perfectly valid 4 KB PNG. Text presence cannot detect it. Counting the
regions the capture plan declares the surface must have can:

```python
WORKSPACE_REGIONS = (".workspace", ".panel", ".log-table")
```

The nav rail is deliberately not in that list — it survives nearly every layout failure,
which is exactly why its presence cannot prove content loaded.

This check found a real defect in our own repair, and reported it in the only way that
mattered: the repair that broke the layout was caught, and the finding stayed open
instead of being marked resolved.

## Accessibility evidence, stated precisely

Every capture records what was deterministically established:

```json
{
  "findings": [{"check": "focus-visible", "determinate": true, "detail": "...", "samples": [...]}],
  "not_established": [
    "WCAG conformance",
    "screen-reader announcement order",
    "colour contrast as perceived (no deterministic tool ran here)",
    "keyboard path completeness beyond the elements present at this viewport",
    "behaviour at viewports and input devices not captured"
  ]
}
```

The `not_established` list is the point. The failure mode this guards against is a
confident sentence: one screenshot at one viewport with one input device cannot
establish conformance, and a record that quietly omitted that limitation would let a
reader infer it had.

`focus-visible` is recorded **per element**, not as a page-wide boolean. An earlier
version OR-ed across all focusable elements, which meant one well-styled control
satisfied the check and every control showing nothing was invisible to it. That defect
was found by reading rendered output, not by reading test output.

## Boundary summary

```
reference            != authority
observation          != recommendation
recommendation       != approval
constraint consulted != constraint satisfied
source implementation != rendered correctness
mechanical evidence   != rendered evidence != review evidence
reference alignment   != pixel similarity
```

See `16-RENDER-CAPTURE-CONTRACT.md` for the capture contract itself.
