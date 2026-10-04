# 18 — Bounded Design Refinement

> Critique may repair an approved direction; it may not secretly invent a new one.

## Critique does not mutate source

Findings survive triage; repairable ones compile into a `RefinementPlan`; the plan goes to
an ordinary implementation worker; the result is mechanically validated, re-rendered, and
independently re-reviewed.

```text
RENDER -> CRITIQUE -> REFINE #1 -> MECHANICAL VALIDATION
       -> RE-RENDER -> RE-CRITIQUE -> REFINE #2 if justified
       -> MECHANICAL VALIDATION -> RE-RENDER -> FINAL REVIEW / ESCALATE
```

Two attempts maximum. An unbounded repair loop on a visual judgement converges by talking
itself into whatever it was already doing.

## RefinementPlan

```text
rfp_<stamp>_<hash>
  critique_id  evidence_set_id
  render_source_digest_before  render_source_digest_after
  direction_id

  finding_ids[]  escalated_findings[]
  allowed_scope[]  forbidden_scope[]
  authorising_principles[]     {principle_id, statement, direction_id, outcome}
  required_outcomes[]  constraints[]  validation[]

  context{ captures_transported, principles_transported, references_transported: 0 }
  attempt  status  introduces_new_direction
```

The plan is the artefact that keeps refinement from becoming redesign. The validator
refuses a plan that names no authorising principle:

> a refinement plan names no authorising approved principle; a change with no authorising
> principle is a redesign in a plan's clothing.

## No new design direction during repair

If the honest conclusion from looking at a render is *"this needs a different visual
language"*, that is not a repair. It is `DIRECTION_REVISION_REQUIRED`, returned to design
direction and a human. Letting the repair phase redesign the product would make the whole
approval chain decorative — the direction would stop being a constraint and become a
suggestion.

```python
DIRECTION_BOUNDED_REPAIRS = (
    "increase hierarchy contrast", "reduce excessive spacing", "restore project accent",
    "fix panel proportions", "remove forbidden surface treatment",
    "correct typography scale", "improve focus visibility", "fix responsive overflow",
)
```

A repair outside this vocabulary is not automatically forbidden — a blocking accessibility
failure is not cosmetic — but it must be justified by a cited principle, and one that
would introduce a new visual language is refused with `DIRECTION_REVISION_REQUIRED`.

### Scope is checked, not trusted

```python
FORBIDDEN_SCOPE_TOKENS = ("package.json", "tsconfig.json", "node_modules",
                          "vite.config", "tailwind.config", "next.config",
                          ".ariadne", "docs/", "references/")
```

A visual repair may not change the toolchain, the build config or the reference corpus.
Changing what can be *expressed* is a design-system decision, not a bug fix.

`record_change()` re-checks each changed path against `allowed_scope` and refuses:

> the repair changed files outside its allowed scope: … a bounded repair that expands its
> own scope is not a bounded repair.

A repair that changed **no** file is also refused — otherwise a worker consumes the budget
by attempting nothing.

## The worker does not review itself

The worker may mark a finding `REPAIRED_CANDIDATE`, which is a claim about its own work.
Only an independent re-review of fresh rendered evidence moves it to `VERIFIED_RESOLVED`.

```text
OPEN -> ACCEPTED_FOR_REPAIR -> REPAIRED_CANDIDATE -> VERIFIED_RESOLVED
                                        |                |
                                   STILL_PRESENT    ESCALATED / WAIVED_BY_HUMAN
```

`resolve()` refuses:

- a re-review by the repair execution — *the worker that made the change does not get to
  certify that its own change worked*
- a re-review of a different source digest
- a re-review that is the same critique that raised the finding
- a resolution listing nothing — `'no change' is an answer only when it is said explicitly`
- a finding resolved that the re-review still reports

### Resolution must be attributable

Absence from an unreviewed capture is not resolution:

```python
original_captures = set(finding["capture_ids"])
uninspected = original_captures - captures_the_re_review_actually_inspected
if original_captures and uninspected:
    raise ContractError("absence from an unreviewed capture is not resolution")
```

Without this, *"resolved"* means *"nobody mentioned it"*, which is indistinguishable from
nobody looking. An adversarial attack closes a cycle from a re-review that inspected 2 of
the 4 captures that evidenced the finding; it is refused.

The check re-derives independence from the stored critique record rather than trusting
it, because the record is what a forged or buggy caller would control. A test forges
`reviewer_execution` and asserts the closure is still refused.

## Stable defect identity

A critique mints fresh `rfd_*` ids every time — correct for the records, useless for
tracking. Without a stable key the same defect looks *resolved* in one cycle and *new* in
the next, and a cycle that changed nothing reports progress.

```python
def _defect_key(row) -> str:
    # sha256 over dimension | severity | expected_basis | repair_scope | viewport
```

Fixed during the vertical slice, after the bookkeeping was observed producing
`resolved: 2, new: 2` for a defect that had merely gone from 12 clipped elements to 5.

## Regression detection

A repair may fix one finding and introduce another. The closing re-review therefore
receives **every materially affected capture**, not a crop around the change, and reports
three lists:

```text
resolved findings
persistent findings
new findings
```

`resolution()` counts all three. It never reports a verdict.

## Before and after are both evidence

```python
def assert_no_collision(path, *, preserve_existing=True):
```

> a capture already exists at …; rendered evidence is append-only, because overwriting a
> before-image destroys the only proof of what the repair changed

Artifacts are written under `attempt-1/`, `attempt-2/`, and the before-set at the root. A
mutation flips the default to `False` and is caught.

Traceability per repaired finding:

```text
finding -> before capture -> refinement plan -> code change
        -> after capture -> re-review result
```

## Minimal repair context

```python
worker = refinement.packet(plan_record, captures=[...])
```

Transporting: the accepted findings, the authorising principles, the allowed and
forbidden scope, the validation commands, the target files, and **only the captures that
support the selected findings**.

```python
"context": {"captures_transported": 1, "captures_available_but_not_transported": 7,
            "packet_bytes": 3141}
```

Every capture description crosses the boundary through `safety.as_data()`, because a
capture description is still untrusted content. No reference imagery is transported at
all — `references_transported: 0`.

The packet carries `stop_conditions` and `escalation_conditions`:

```text
STOP if satisfying the outcome would require a change outside allowed_scope.
STOP if satisfying the outcome would need a different visual language.
STOP if any validation command fails.
ESCALATE if two bounded attempts have been used.
```

## Mechanical validation before every recapture

```text
typecheck   build   tests
```

A visually promising change with a broken build is not progress. `record_validation()`
marks the plan `REJECTED` when a declared command is missing or fails, and
`mark_rerendered()` refuses a plan that is not `VALIDATED`. A failing repair produces no
capture at all.

## Repair uses the normal implementation path

There is no magic CSS-repair function outside Ariadne. The worker edits an allowed file
with an ordinary edit and `design_execution.execution.ValidationRunner` re-runs the
declared commands. What AR-222 adds is the *record*: who changed what, under which plan,
with which findings — so the change is attributable and its scope checkable.

### Idempotence

The vertical slice's bounded CSS repair guards on a marker:

```python
NARROW_MARKER = "AR-222: narrow-workspace"
```

An earlier version guarded on a string the emitted comment did not contain, so each cycle
appended a second copy of the rule. Every duplicate surfaced as a fresh finding and the
loop spent its whole allowance chasing its own output. The guard must be compared against
the exact token the repair emits.

## Visual acceptance semantics

AR-222 may produce `RENDERED`, `CRITIQUED`, `REFINED`, `REVIEWED`. It does **not** grant
human acceptance:

```python
{"visual_acceptance": "VERIFIED_BY_RENDERED_CHECK",
 "rendered_check_id": "drc_...",
 "human_acceptance": "NOT_GRANTED"}
```

A render with known findings is *reviewed*, not *accepted*. AR-221's
`implementation_run_problems` requires `rendered_check_id` for this claim precisely
because "source inspection cannot stand in for one".

See `19-RENDER-SECURITY.md` for the attack surface, and `20-AR-222-RESULTS.md` for what
actually happened on Beacon.
