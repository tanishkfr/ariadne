# Design Verification — Ariadne 2.4C

**Status:** implemented and qualified on a disposable rendered surface. This
document describes what the engine can establish about a rendered interface,
what it cannot, and where the evidence lives. It does not introduce a second
design engine; every capability extends `ariadne_engine.rendered_critique`,
`ariadne_engine.render`, `ariadne_engine.critique` and the existing design-review
records.

## 1. The workflow

```text
request
  -> design/reference intelligence (existing)
  -> approved design direction (G1D)
  -> implementation
  -> declared viewport matrix
  -> real browser capture
  -> interaction scripts and assertions
  -> deterministic accessibility checks
  -> independent visual critique (rendered evidence)
  -> bounded correction
  -> fresh captures + visual comparison
  -> fresh review / proof
```

A screenshot without a source digest, viewport, route, state, browser identity
and capture manifest is not rendered evidence. The existing AR-222 provenance
rules are unchanged and still apply.

## 2. Declared viewport matrices

`rendered_critique/viewports.py` accepts a project-declared matrix:

```json
{
  "viewports": [
    {"class": "narrow",  "width": 320,  "height": 800},
    {"class": "mobile",  "width": 390,  "height": 844},
    {"class": "tablet",  "width": 834,  "height": 1112},
    {"class": "desktop", "width": 1440, "height": 900},
    {"class": "wide",    "width": 1920, "height": 1080}
  ],
  "supported_width_range": [320, 1920]
}
```

Rules:

- classes are `narrow`, `mobile`, `tablet`, `desktop`, `wide`;
- width, height and scale must be plausible and unique;
- a responsive claim with no matrix is refused rather than given an invented
  ladder;
- a declared matrix missing a class is reported, not silently filled in;
- a project with no responsive claim and no matrix gets no ladder (the existing
  AR-222 behaviour is preserved).

The plan records the matrix and every target's viewport class. A capture at
390px can never satisfy a query for 1440px; `render.strongest` filters by width.

## 3. Deterministic accessibility checks

The browser inspection script now returns a rendered accessibility report in
addition to the existing focus/size checks:

| Check | What is measured | What it does **not** establish |
|---|---|---|
| contrast | computed foreground and composited ancestor background, AA threshold (4.5 normal / 3 large) | contrast over images, gradients or canvas (counted `unverified`) |
| focus-visible | each visible focusable control after keyboard-intent focus | focus order appropriateness |
| target-size | visible interactive targets against 24×24 CSS px | platform-specific larger-target guidance |
| accessible-name | visible controls with no accessible name | screen-reader announcement order |
| dialog-focus | an open dialog contains `document.activeElement` | full focus-trap correctness over time |
| form-errors | `aria-invalid` controls name an error message | error wording quality |
| reduced-motion | `prefers-reduced-motion` plus computed transition duration | animation quality or every media query |
| landmarks/status | recorded for review, not treated as a pass | WCAG conformance |

A passing automated audit is **not** WCAG conformance. Every report states the
checks it did not establish. A hidden or disabled control is excluded from the
keyboard path; it is not a ringless control the user can reach.

## 4. Interaction-state verification

A capture target may declare deterministic post-interaction assertions:

```json
{"kind": "visible", "selector": "#feedback"}
{"kind": "aria", "selector": "#duration", "attribute": "aria-invalid", "equals": "true"}
{"kind": "focus", "selector": "#dialog-close"}
```

Supported kinds: `visible`, `absent`, `text`, `value`, `focus`, `aria`, `count`.
A `sequence` action performs bounded steps (for example fill then submit). A
failed assertion is recorded as `FAILED` on the capture; it is not dropped and
does not silently become a skip. An adapter that cannot evaluate returns
`UNVERIFIED`, never a pass. The evidence set reports
`verification_status=INTERACTION_FAILED` when any assertion failed.

A screenshot of a static component still proves nothing about behaviour; the
assertions are what make the state checkable.

## 5. Visual regression

`ariadne_engine.visual_diff` decodes the PNG bytes the browser produced
(non-interlaced 8-bit RGB/RGBA) and compares them per channel at a declared
threshold. It reports:

- changed pixels vs total;
- changed-pixel ratio;
- maximum channel delta;
- the bounding box of the changed region;
- explicit masks and the reason they were justified;
- incompatible dimensions as `INCOMPATIBLE`, not as a visual difference.

`rendered_critique/visual_regression.py` binds the comparison to two validated
evidence sets, the same route/state/viewport, different source digests and a
task identity. A changed render sets `requires_review=true`.
`quality_judgement` is always `none`: pixel similarity never approves a design.

Known false-positive sources remain font rasterisation, animation phase,
dynamic content, browser/device scale and timing. Controlled captures,
`settle_ms`, deterministic fixtures and justified masks reduce them; they do not
make the measurement a taste score.

## 6. Independent qualitative review

The existing rendered critique is unchanged in its independence rules: the
reviewer is a different engine execution from the implementer, the direction is
the approved revision, findings cite captures and the review is isolated from
implementation rationale.

2.4C adds an optional `qualitative` block to a rendered critique:

- `screens_reviewed` — validated capture ids;
- `factual_failures` — recorded deterministic finding ids;
- `subjective_recommendations` — `{screen, dimension, text}` and always
  non-blocking;
- `technically_correct_but_visually_weak` — a reviewer may say this;
- `overall_note`;
- `scoring: none` — no numeric taste score is recorded or accepted.

A subjective recommendation must name a screen and a design dimension. A
technically correct but visually weak page is representable; a bare adjective
or a fabricated score is not.

## 7. Real qualification

The disposable qualification project and evidence are under
`validation/runs/2.4c/design/`:

| Item | Result |
|---|---|
| Declared matrix | 320, 390, 834, 1440 and 1920 CSS px |
| Captures per phase | 7 (five viewports plus dialog-focus and invalid-input interactions) |
| Before defects | 15 deterministic findings across contrast, focus, overflow, target size, dialog focus and form feedback |
| Correction | bounded CSS/JS changes in the three permitted files |
| After deterministic findings | 0 |
| Interaction assertions | passed |
| Accessibility report | 0 contrast failures, 0 unringed visible controls, 0 small targets |
| Visual regression | 7 comparisons; changed regions recorded and reviewed |
| Independent visual review | no visible factual defect after correction; one non-blocking hierarchy recommendation |
| Fresh proof | `VP-0001` ACCEPTED with the creative S5 review bound |

The visual reviewer inspected the rendered images only; it did not inspect the
source or claim WCAG conformance from screenshots. The review's factual defect
(About-section gutter) and its clipping defect (settings panel below the
viewport) were both found in rendered evidence, corrected, and re-verified.

## 8. Limitations

- Static captures cannot establish keyboard traversal over time, screen-reader
  announcement order or complete WCAG conformance.
- Contrast over images, gradients and canvas is `unverified`, not passed.
- The PNG comparator is pixel-based; it is not a perceptual quality model.
- Masks can hide a regression if misused; a mask requires a recorded reason and
  the comparison always requires review when pixels changed.
- The qualification is one Windows machine with the installed Chromium-family
  browser. macOS, Linux, Safari and Firefox were not executed.
- A passing automated audit and a passing visual review are evidence, not a
  substitute for a human usability study.

## 9. Evidence

- `src/ariadne_engine/rendered_critique/viewports.py`
- `src/ariadne_engine/rendered_critique/evidence.py`
- `src/ariadne_engine/visual_diff.py`
- `src/ariadne_engine/rendered_critique/visual_regression.py`
- `src/ariadne_engine/rendered_critique/critique.py`
- `scripts/qualify-design-2.4c.py`
- `scripts/test-ar24c.py`
- `validation/runs/2.4c/design/report-before.json`
- `validation/runs/2.4c/design/report-after.json`
- `validation/runs/2.4c/design/visual-review.json`
