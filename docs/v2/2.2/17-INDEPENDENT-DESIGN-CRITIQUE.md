# 17 — Independent Design Critique

> The implementation worker does not get to decide whether its work looks right.

## The isolation boundary

What the reviewer receives:

- the requirements it is judging
- the approved direction, and the principles relevant to these captures
- the BORROW / ADAPT / AVOID decisions the reference layer already made
- the rendered captures, curated, each with route/state/viewport/source digest
- interaction, responsive and accessibility evidence

What it does **not** receive:

- the implementation worker's rationale
- the repair rationale from a previous cycle
- any statement of what the worker was trying to achieve
- the source, for the primary experience critique

The reason is not politeness about the worker's feelings. The failure mode this phase
exists to catch is *specific*: a reviewer shown the intent reads the render charitably
and confirms it. Reading the CSS, assuming the intended result, then approving the
screenshot is not a review — it is a rubber stamp with extra steps.

## A whitelist, not a blacklist

```python
REVIEWER_WHITELIST = (
    "task", "requirements", "approved_direction", "direction_revision", "principles",
    "reference_decisions", "captures", "interaction_evidence", "responsive_evidence",
    "accessibility_evidence", "dimensions", "questions", "prohibited_actions",
)
```

`reviewer_packet()` returns `{k: v for k, v in packet.items() if k in REVIEWER_WHITELIST}`.

The alternative — build a full context and strip the implementation fields out — fails
the moment a new field appears somewhere, which is precisely the accidental leak this
boundary exists to prevent. Default-deny survives someone adding a field to run state
next year; default-allow does not.

`assert_isolated()` runs on the path that actually reaches a reviewer, and again on the
critique record before it is stored, because both ends of a boundary are places it can be
crossed: a caller can smuggle a field into the packet, or can write a record claiming
isolation it did not have.

`critique.py` attaches a real leakage field to the packet on purpose — the whitelist is
the only thing keeping it out, which is what makes that line the boundary worth testing.

### What the isolation record is and is not

```python
"isolation": {
    "withheld": ["implementation rationale", "repair rationale", ...],
    "implementation_rationale_transported": False,
    "packet_fields": [...whitelist...],
}
```

This is a *record* of what was withheld, not a claim about the reviewer's reading. It is
checkable; the reviewer's state of mind is not, and pretending otherwise would be the
exact impersonation this phase exists to prevent.

## RenderedCritique

```text
drc_<stamp>_<hash>
  evidence_set_id  render_source_digest
  direction_id  direction_revision  reference_set_id

  reviewer_identity  reviewer_execution  implementing_execution
  independence_level
  isolation{withheld[], implementation_rationale_transported, packet_fields[]}

  requirements[]  captures[]
  findings[]      coverage{}     unknowns[]
  reference_alignment{}           counter_reference_review{}
  overall_status  severity_definitions  recorded_at
```

### Independence is a fact, not a label

`review.independence_problems()` requires both executions to resolve to engine-created
records *in this run*. A well-formed `exe_…` string a caller invented is not an
execution, so it cannot establish independence.

### Findings must point at the render

```python
FINDING_BASES = ("DETERMINISTIC", "BOUNDED_JUDGEMENT")
```

Every finding carries dimension, severity, basis, observation, expected_basis,
`capture_ids[]`, `requirement_ids[]`, `direction_principle_ids[]`, materiality,
repairability, and state.

Three refusals matter:

- a finding citing no capture — *a judgement about a render that points at nothing in
  particular cannot be repaired or dismissed*
- a finding citing a capture absent from the set
- a finding whose basis is neither `DETERMINISTIC` nor `BOUNDED_JUDGEMENT`

Separating the two bases is not pedantry. A reproducible fact and a bounded qualitative
judgement both belong in the record, but collapsing them lets taste acquire the authority
of arithmetic. `hierarchy reads flat` and `focus indicator absent` are both findings;
they are not the same kind of claim.

## Coverage instead of a score

```text
Layout                 REVIEWED
Typography             NOT_REVIEWED
Motion                 NOT_APPLICABLE
Accessibility states   PARTIAL
```

`CRITIQUE_COVERAGE_STATES = ("REVIEWED", "PARTIAL", "NOT_APPLICABLE", "NOT_REVIEWED")`,
plus a rule the validator enforces: a `REVIEWED` dimension must cite captures.

A number would be easier to read and would mean nothing. "8/17 dimensions" says nothing
about whether the interface is right and invites optimising the count rather than the
surface. `NOT_APPLICABLE` is a real answer and is preferred over inventing criticism.

There is no global design score and no `looks good`. `RENDER_OUTCOMES` is:

```text
RENDERED_DIRECTION_CONFORMANT
RENDERED_WITH_KNOWN_FINDINGS
DIRECTION_REVISION_REQUIRED
RENDER_VALIDATION_BLOCKED
```

## Reference-aware, not pixel-matching

Permanent rule:

```
reference alignment != pixel similarity
```

`reference_alignment()` reports satisfaction of an approved principle:

```python
{
  "method": "principle-satisfaction",
  "reference_images_compared": 0,
  "similarity_scores": [],
  "principles": [{"principle_id": ..., "assessment": "CONTRADICTED" | "NO_FINDING",
                  "basis": "approved-principle-satisfaction",
                  "pixel_similarity_computed": False}],
}
```

Two surfaces can express one principle very differently, and two can look nearly
identical while expressing opposite ones. What is checkable is whether an approved
principle is satisfied. A mutation replaces the basis with `"pixel-similarity"` and adds
`{"reference": "linear", "score": 0.87}`; a test asserts it is caught.

### Worked example

Approved principle:

> Maintain persistent workspace context with restrained, low-noise boundaries between
> navigation and work surface.

Rendered evidence shows three floating cards, heavy shadows, workspace context
disappearing inside a modal. The critique says:

```text
HIGH — persistent workspace principle is not satisfied
```

Legitimate reference-aware critique. What it would not say is "83% similar to Linear".

## Project identity still outranks references

```python
"project_identity_precedence": {
    "identity_sources": [...],
    "rule": "project identity outranks every reference: a reference's colour, typeface or
             treatment is never a requirement on this project",
}
```

If reference imagery uses purple and the project accent is blue, the critique must not
complain that the interface is not purple. Recorded on every alignment record and
asserted by a benchmark case.

## Counter-reference review

`COUNTER_REFERENCE_PATTERNS` is a **literal** pattern list and nothing more:

```text
glassmorphism     backdrop-filter
pill-overload     border-radius: 999
generic-card-grid glass-card, card-grid
gradient-hero     linear-gradient(, radial-gradient(
excessive-glow    box-shadow: 0 0 , filter: blur(
```

Both outcomes are recorded — absence is a success worth reporting:

```text
ABSENT   "the forbidden literal treatment is absent from the implementation bytes"
PRESENT  a finding
```

And the limit is stated rather than hidden:

> absence of a literal token is not proof of absence of the treatment; these are byte-level
> checks and the qualitative patterns above are offered to the reviewer as questions.

`VISUALLY_JUDGED_AVOIDS` carries the patterns with no byte signature —
*"surface treatment feels card-heavy"*, *"the workspace does not feel persistent behind the
overlay"*. They are questions for a reviewer, never verdicts from a substring search.

## The default reviewer

`deterministic_review()` reports only what a render can *prove*: horizontal overflow,
content beyond the viewport, per-element focus indication, accessible names, target size,
reduced-motion behaviour, runtime errors, duplicate headings.

It explicitly refuses to guess at hierarchy or density, and marks the dimensions it did
not judge:

```python
"hierarchy": {"state": "NOT_REVIEWED", "capture_ids": [], "note":
    "a bounded qualitative judgement a deterministic reviewer must not fabricate"}
```

A model or human reviewer receives the same isolated packet through `review_with()` and
may add `BOUNDED_JUDGEMENT` findings, recorded as judgement.

`reports what it does not establish` is part of the contract, not a disclaimer.

See `18-BOUNDED-DESIGN-REFINEMENT.md`.
