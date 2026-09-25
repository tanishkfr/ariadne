# AR-202D — Rendered evidence

Source: `src/ariadne_engine/render.py`. Contract:
`contracts.rendered_evidence_problems`.

Rendering is the one place where Ariadne could most easily fool itself: a file
called `screenshot.png` looks like evidence and proves nothing. This document
describes the contract that makes a rendered claim checkable, and the honest
limits of what AR-202D verified.

## 1. Evidence states

| State | Meaning | Never |
|---|---|---|
| `SOURCE_SUGGESTS` | source text suggests the behaviour (a declaration, a tag) | treated as a rendering |
| `RENDERED` | a capture adapter produced an artifact at a declared viewport/revision | treated as behaviour |
| `OBSERVED` | a behaviour was observed over time (interaction or measurement artifact) | treated as independent |
| `VERIFIED` | a *different* engine execution re-produced the evidence | treated as human acceptance |
| `UNVERIFIED` | explicitly not captured, with a recorded blocker | treated as a pass |

`render.EVIDENCE_ORDER` gives them an ordinal strength used for comparisons
(`SOURCE_SUGGESTS < RENDERED < OBSERVED < VERIFIED`, with `UNVERIFIED` below a
source claim). The ordinal is a comparison of evidence, never a quality score.

Worked example, exactly as the contract treats it:

| Claim | Evidence | State |
|---|---|---|
| CSS contains `position: sticky` | source anchor present | `SOURCE_SUGGESTS` |
| a screenshot shows the element at the top | capture artifact | `RENDERED` |
| scrolling kept it at the top | interaction transcript | `OBSERVED` |
| an independent execution re-produced the same digest | re-capture | `VERIFIED` |

## 2. What a record must contain

* `task_id`, `revision_hash` (a real fingerprint, not a label);
* `kind` — `source`, `screenshot`, `dom`, `browser`, `measurement`,
  `interaction`, `accessibility`, `console`, `video`;
* `capture_method` — `offline-fixture` or `declared-observer`;
* `adapter` — the adapter id that produced it;
* `viewport` — width required; height, DPR and orientation optional;
* `environment` — what actually produced the bytes;
* `artifact` — path and digest, re-hashed by the engine on acceptance, on
  staleness checks, and on closure;
* `captured_at`, `capture_execution` (engine-created), `provenance`.

## 3. Provenance is a property of the method

A digest only proves the file has not changed since somebody hashed it. It does
not prove that a capture happened. So each method carries an obligation the
engine checks without trusting the caller:

| Method | Obligation | Consequence |
|---|---|---|
| `offline-fixture` | the capture manifest the adapter writes beside the artifact must name *this* artifact, *this* digest and *this* adapter | a hand-written record claiming `offline-fixture` is refused ("a file that merely exists is not rendered evidence") |
| `declared-observer` | the artifact must carry the observer's explicit method declaration (`extra.trust = "declared"`) | accepted, recorded honestly, and capped at `RENDERED`. `observe` refuses the promotion to `OBSERVED` and `verify` refuses the promotion to `VERIFIED`, because re-hashing the same external file in a second execution is not independent re-production |

An `adapter_available: false` capture is refused outright: a capability that is
not configured cannot produce evidence.

## 4. Capture adapters

| Adapter | Produces | Availability |
|---|---|---|
| `offline-fixture` | screenshot (deterministic bytes), DOM, accessibility rules, console lines, interaction/measurement transcript, each materialised under the run root and hashed | whenever a fixture is declared |
| `declared-observer` | whatever an operator already recorded itself | when a method declaration is configured |
| `local-browser` | screenshot, DOM, interaction, measurement, accessibility, console | **reported unavailable** unless an authorized local capability is configured; nothing in AR-202D installs or starts a browser |

`render.capability_matrix` publishes each adapter's declared capabilities and its
own availability with a reason, and the design evidence route consumes exactly
that (`routing.route_evidence`). A missing capture capability produces a `blocked`
route, never a fabricated artifact.

Capture artifacts are contained too. A `record` whose method is `offline-fixture`
must resolve inside the run's capture directory (`<run root>/design-captures`), and
an `observe` artifact must resolve inside the project or that same capture root.
The one deliberate external case is `declared-observer`, which must carry the
observer's declaration and is capped at `RENDERED`. Containment is checked after
the provenance obligation would otherwise pass, so a fixture capture can only ever
be recorded from the run's own capture root. A refused promotion writes nothing:
`observe` and `verify` validate the intended record before applying it.

### The offline fixture is not a browser

`OfflineFixtureAdapter` materialises deterministic bytes from a declared scene.
Its artifacts are recorded with `environment = {"kind": "offline-fixture",
"browser": "none"}`, and the screenshot bytes are deliberately prefixed
`ARIADNE-OFFLINE-FIXTURE` and marked `encoding: fixture-bytes` so no reviewer can
mistake them for a browser screenshot. **The fixture proves the workflow, not a
browser**, and AR-202D makes no browser claim (see `09-AR-203-HANDOFF.md`).

## 5. Revision and viewport binding

* Evidence is revision-bound. `render.stale_records` reports "rendered evidence
  was captured for a different revision" when queried at another revision, and
  every closure and critique path re-checks it.
* Evidence is viewport-bound. `render.strongest(state, requirement,
  viewport_width=...)` returns nothing for a viewport that was never captured, so
  a 375 px capture cannot satisfy a 1280 px claim.
* `render.for_requirement` and `render.strongest` are the only sanctioned ways to
  answer "what evidence do we have for this requirement", so no caller has to
  guess from a file listing.

## 6. Verification by re-production

`render.verify` requires:

* an engine-created verification execution id;
* a verification execution **different** from the capturing execution (the
  capturing execution verifying itself is refused);
* a capture method that can actually be re-produced: a `declared-observer`
  artifact is refused, because the only thing the engine can re-produce is a hash
  of the same external file;
* the re-produced digest to equal the captured digest — a mismatch is a finding,
  not a verification;
* a recorded method and tolerance.

`VERIFIED` therefore means "an independent execution re-produced this evidence",
which is the strongest claim the contract supports. It never means "a human
approved the design" — that is `G3`, and AR-202D does not touch it.

## 7. Honest failure

`render.mark_unverified` records that a required observation was **not** made,
with the blocker that prevented it. It is a first-class record, not an omission:
`design-measurements` counts it, `design-check` reports it, and no closure can use
it. Where a rendered requirement is required and no capture capability exists,
`design.characterize` adds a note to the characterisation saying the requirement
must be recorded unverified with its blocker rather than assumed satisfied.
