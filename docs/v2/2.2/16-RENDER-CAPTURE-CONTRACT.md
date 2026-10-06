# 16 — Render Capture Contract

> What to render, why, and what it costs.
>
> The instinct behind a visual QA tool is to screenshot everything: every route, every
> viewport, every hover state, light and dark. That produces fifty images, and a reviewer
> who looks at fifty images finds nothing, because there is no longer any question the
> images are asking.

## RenderCapturePlan

```text
rcp_<stamp>_<hash>
  implementation_plan_id      the plan whose code this renders
  direction_id                the approved direction it is judged against
  render_source_digest        the exact implementation bytes

  target_surface              what is being rendered
  launch_command              argv, never a shell string
  routes[]

  targets[]                   each with a kind, a viewport, and a BASIS
    rct_<stamp>_<hash>
      kind                    viewport-state | interaction-state
                              | responsive-state | theme-variant
      route  state  viewport  theme  interaction
      reduced_motion          emulate prefers-reduced-motion before capture
      required_regions[]      structural regions this surface must contain
      materiality_basis[]     why this capture exists
      notes

  required_evidence[]
  browser_requirements
  capture_budget
  status                      PLANNED | CAPTURED | PARTIAL | ABANDONED
```

## Capture selection must be intentional

Every target names a basis drawn from `CAPTURE_TARGET_BASES`:

| Basis | Meaning |
| --- | --- |
| `REQUIREMENT` | a requirement says this surface must be seen |
| `DIRECTION_PRINCIPLE` | an approved principle is only checkable on this surface |
| `MATERIALITY` | the surface carries a material category that can break |
| `REGRESSION` | a prior finding means a re-capture of this exact state |

A target with no basis is refused. This is the entire anti-matrix mechanism, and it is
enforced in the contract validator as well as in the constructor — a plan built by a
caller that skipped the helper must not smuggle in a capture nobody asked for.

### Deriving viewports rather than defaulting

```python
def responsive_viewports(direction, implementation=None) -> list[dict]:
```

Reads the direction's own claims and the implementation's declared breakpoints. A
desktop-only tool with no responsive claim and no breakpoints gets **zero** responsive
captures — guessing a responsive ladder for a desktop-only product spends budget proving
nothing. Claim keys count as much as claim values, because a claim *labelled* responsive
is one even when its prose avoids the word.

## Capture budget

```python
DEFAULT_CAPTURE_BUDGET = {
    "primary_viewport_states": 3,
    "interaction_states":      6,
    "responsive_captures":     3,
    "theme_variants":          2,
    "repair_capture_cycles":   2,
}
```

These are **defaults, not limits**. A plan may exceed any of them by recording a reason:

```python
budget=capture_budget(expansions=[{
    "name": "interaction_states",
    "reason": "seven keyboard states are named by the approved interaction model",
}])
```

Exceeding one *silently* is refused. The distinction is the whole point: "these defaults
did not fit this task" is a normal answer, and a run that quietly captured everything is
not.

`repair_capture_cycles` is deliberately the same number as the refinement budget
(`MAX_REPAIR_ATTEMPTS = 2`), so one stage cannot claim a fresh allowance at each layer.
A benchmark case asserts they agree.

### Measured economics

```python
plan.summarise(plan, captured=[...], capture_bytes=..., duration_seconds=...)
```

reports planned, actual, bytes, seconds, counts by kind, states skipped with reasons, and
says plainly:

> counts and bytes are measured. They are capture economics, not a measure of design
> quality: a cheap run is not a good run.

`PARTIAL` and `CAPTURED` are distinguishable only because a skipped target carries its
reason.

## The RenderAdapter contract

Vendor-neutral, eight operations:

```text
probe()          is a rendering capability available, and how was that established
launch()         start it
navigate(url)    go somewhere, refusing the route first
set_viewport(v)  size
set_theme(t)     apply a project theme
perform_state(d) actually perform an interaction
capture(path)    produce the artifact
inspect()        measure the page
shutdown()       stop it, on every path including failures
```

Everything above this line speaks only in those terms. Swapping Chromium for anything
else is a new adapter, not a rewrite, and a plan saying "1440x900 at /workspace with a
focus state" does not change.

### Three decisions that make it trustworthy

**Playwright is optional and never imported at module load.** Ariadne ships
`dependencies = []` and that is not negotiable. The probe is a `find_spec` plus a version
string; if it is not importable the adapter reports `RENDER_CAPABILITY_UNAVAILABLE` and
the run says so. Nothing degrades to source inspection while still reporting a visual
review as complete.

**A failed capture is a named refusal, never a fallback.**

```text
RenderCapabilityUnavailable   no rendering capability exists here
CaptureFailed                 one existed and the capture did not succeed
```

Distinct classes, because the caller must answer "the environment could not render"
differently from "the page did not render".

**Every navigation is validated before the browser is told anything.** A route is
attacker-influenced input arriving from a capture plan. The adapter routes it through
`safety.safe_route` first, so an adapter author cannot forget.

### The unavailable adapter is a real object

```python
class UnavailableRenderAdapter(RenderAdapter):
```

It exists so the failure path is exercised on every run rather than only on machines
lacking a browser, and so a run without one reports *why* rather than reporting nothing.
Its operations are written out explicitly rather than synthesised in `__getattr__`,
because the base class already defines them — attribute lookup finds the base method and
`__getattr__` never runs, which would leave a caller holding a method that raises
`TypeError` instead of the named refusal it is supposed to get. That was a real bug.

## Exact source binding

Mandatory on every capture: source commit if clean, tracked diff digest if dirty,
relevant file digests, build identity, route, viewport, device scale, theme, browser and
runtime identity, capture timestamp, capture digest.

### `render_source_digest`

A deterministic fingerprint over the exact implementation bytes that produced the render —
not the branch, not the commit message, not the timestamp. Built from `(path, digest)`
pairs, so renaming a file with identical content changes the digest, which is correct: a
rename can change a route, an import graph or an asset URL.

### Scope, and why it is narrow

Bound: `.ts .tsx .js .jsx .mjs .cjs .css .scss .sass .less .html .svg .json .vue .svelte .astro`,
font files, `index.html`, and build config.

Unbound: `node_modules`, `dist`, `coverage`, `__pycache__`, `.git`, and — importantly —
**`.md`, `.txt`, and anything else that cannot reach the screen.**

A stale warning nobody believes is worse than no warning. A change to a changelog does
not alter what the user saw; binding captures to it would make staleness fire on every
unrelated commit and train reviewers to ignore it. A test asserts this both ways: a
`.md` does not move the digest, and a `.json` the application may import does.

## Dirty worktree semantics

During refinement the target is *intentionally* dirty. Faking a commit per repair would
turn provenance into theatre. So:

```text
render_source_digest = sha256 over sorted "path sha256" lines
```

over tracked and untracked implementation bytes alike. A later edit to any relevant file
immediately invalidates every capture bound to the old digest.

## Stale capture detection

```text
capture implementation
  -> edit relevant stylesheet
  -> old screenshot
```

becomes `STALE_RENDER_EVIDENCE`, naming both digests and the file count fingerprinted at
capture time. It is a refusal, not a warning, and it cannot close a visual review.

`source.staleness()` is the single implementation. Render, critique and refinement all
ask it rather than each re-deriving "has the source moved", which is how a rule ends up
enforced in one place and assumed in three.

Re-running a capture plan whose own binding has gone stale is refused before a browser
launches: re-running it would bind fresh captures to implementation bytes that are not
the implementation.

See `17-INDEPENDENT-DESIGN-CRITIQUE.md` for what happens next.
