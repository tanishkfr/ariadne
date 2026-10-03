# 02 — The Reference Contract (AR-220)

How a `DESIGN.md` becomes an Ariadne `DesignReference`, and what every record is
required to carry.

## Extending, not duplicating

Ariadne 2.1 already owned a reference record family with a provenance lifecycle.
AR-220 **extends** it rather than creating a second store for "things a design
looked at":

```text
┌─ AR-202D reference record (unchanged) ───────────────────────────────┐
│ reference_id, run_id, adapter, source, locator, title, query        │
│ state, history, inspections, analysis, usage, content digest        │
├─ AR-220 classification ──────────────────────────────────────────────┤
│ source_kind, evidence_level, access_mode, freshness                 │
│ source_provider, source_identity, source_uri                       │
│ retrieved_at, content_digest, source_revision, source_date         │
│ brand, product, surface, reference_type                             │
├─ AR-220 observations ────────────────────────────────────────────────┤
│ observed_patterns — what was seen, on a controlled vocabulary       │
│ treatments        — BORROW / ADAPT / AVOID per pattern              │
├─ AR-220 boundaries ──────────────────────────────────────────────────┤
│ reuse_constraints, limitations, license_status, attribution         │
│ injection_scan, raw_artifact_refs, capture_refs, normalized_digest  │
└─────────────────────────────────────────────────────────────────────┘
```

The lifecycle still governs *how* evidence was reached. Nothing here can shortcut
it: normalisation produces a `FOUND` record, and reaching `INSPECTED` still
requires a real hashed evidence artifact under the AR-202D rules.

## `source_kind` — ten values, never equal trust

| Value | Means | Relative weight |
|-------|-------|-----------------|
| `FIRST_PARTY_DESIGN_MD` | published by the brand itself | highest |
| `LOCAL_DESIGN_FILE` | a design document already inside this project | high; it is a **constraint** |
| `FIGMA_DOCUMENT` | a design-tool document | high when directly inspected |
| `LIVE_SITE_INSPECTION` | a rendering or live page that was looked at | medium-high |
| `SOURCE_REPOSITORY` | tokens/components read from code | medium |
| `MCP_RESULT` | arrived over MCP | transport only; weight comes from evidence level |
| `COMPONENT_REGISTRY` | a published registry entry | implementation evidence |
| `CLI_RESULT` | arrived over a CLI | transport only |
| `CURATED_DESIGN_ANALYSIS` | a third party's analysis of public design | medium; **not** the vendor's docs |
| `SECONDARY_DESCRIPTION` | prose describing a design, nothing inspected | lowest |

The two distinctions that carry the weight:

> `CURATED_DESIGN_ANALYSIS` ≠ `FIRST_PARTY_DESIGN_MD`

A description of Apple's design language is useful evidence about how Apple looks.
It is not Apple's design system. getdesign.md's own entry pages say so: *"Independent
analysis of publicly observable patterns... Not affiliated with or endorsed by"*
the brand, and its Terms repeat that these are *"not official design systems from
the listed companies."* Ariadne records that as a **constant** in the adapter, so
no code path can reclassify it.

> `LOCAL_DESIGN_FILE` is a constraint, not a suggestion

Project tokens are what the design must be, not what it might be. See §30 of the
brief: external references *supplement* project identity; they never override it.

## `evidence_level` — how it was actually obtained

| Value | Means |
|-------|-------|
| `DIRECTLY_INSPECTED` | the source itself was read or looked at |
| `SOURCE_INSPECTED` | primary source code/design inspected |
| `CAPTURED` | a rendered artifact was captured and hashed |
| `CURATED_ANALYSIS` | a third party's published analysis was read |
| `SECONDARY_DESCRIPTION` | prose only; nothing inspected |
| `UNVERIFIED` | a claim exists with no supporting retrieval |

These echo the existing `RENDERED_EVIDENCE_STATES` deliberately: a claim is never
recorded above the strength of what was performed, and `UNVERIFIED` is a valid
recorded answer rather than an absence.

**A transport is not an evidence level.** An MCP result is `DIRECTLY_INSPECTED`
only if the document behind it was actually inspected. That is the whole point of
`MCP and CLI are transports, not trust`.

## `access_mode` — including a valid refusal

| Value | Meaning |
|-------|---------|
| `PUBLIC` | retrieved from a public endpoint |
| `ACCESS_RESTRICTED` | **terminal.** Sign-in, paywall or entitlement required — stop |
| `DECLARED_LOCAL` | a project file inside the permitted root |
| `UNREACHABLE` | the source could not be reached |

`ACCESS_RESTRICTED` carries no observations and is a legitimate, complete answer.
Bypassing a login, a paywall, an entitlement, a robots rule or a rate limit is
out of scope for this system, and private cookies are never read.

**This is a live finding, not a hypothetical.** getdesign.md's catalog entry pages
expose title, summary, analysis prose and `best_for`, but the **Download DESIGN.md**
button is sign-in gated behind Catalog Pass. Ariadne records that boundary and reads
the documents from the maintainers' public MIT-licensed repository instead.

## `observed_patterns` — extraction, not judgement

Sixteen controlled dimensions:

```text
information-hierarchy   navigation          density
layout-grid              spacing             typography
color-roles              surface-treatment   borders
radii                    depth               component-geometry
interaction              motion              responsive-behavior
imagery-media
```

Each row records **what the document states**, cites the artifact it was read from,
and stops there:

```json
{
  "dimension": "component-geometry",
  "observation": "21 named component styles, 18 of which declare explicit padding",
  "source": "frontmatter.components",
  "observed_at": "2026-10-04T00:00:00Z",
  "basis": "",
  "detail": {"count": 21, "with_padding": 18}
}
```

Three rules make this trustworthy:

1. **Absent groups produce no rows.** A document with no token block yields no
   observations, never a synthesised default.
2. **Motion and interaction require a declared `basis`.** A static token table
   cannot establish how something moves, so the row is only written when the
   document itself names the basis it was read from.
3. **`observation` may not be phrased as an instruction.**
   `sets.assert_observation_not_recommendation` refuses "you should use …" — an
   observation states what the source records, not what the design should do.

## `treatments` — the structural anti-cloning device

Every extracted characteristic lands in exactly one of:

| Treatment | Meaning |
|-----------|---------|
| `BORROW` | use the principle as observed |
| `ADAPT` | use the principle, changed for this project |
| `AVOID` | the observed characteristic is the anti-pattern here |

There is no "untreated" state: an undecided dimension defaults to `ADAPT`, so a
pattern nobody classified is never a silent default of "copy it". A dimension
named in two buckets is refused rather than resolved by precedence.

This is why reference acquisition cannot decay into reference cloning — the
direction has to say, per pattern, what it is doing with it.

## `limitations` — what the evidence cannot support

Recorded per reference and aggregated onto the set. Sources:

- structural problems from the DESIGN.md validator (dangling token references,
  missing rationale sections, no token block);
- parser warnings (unrecognised frontmatter fields);
- access-boundary facts (the catalog's own download is gated);
- an explicit fallback: *"no structured token or rationale observation could be
  extracted from this source"*.

A reference that produced nothing says so rather than looking like a reference
that produced a little.

## Digests and change detection

| Field | Binds |
|-------|-------|
| `classification.content_digest` | the retrieved **bytes** |
| `normalized_digest` | the **normalised record**, excluding `retrieved_at` |

`normalized_digest` deliberately excludes the timestamp, so re-retrieving identical
bytes later produces the same digest while any change in classification or
observations produces a different one. That makes `normalize.detect_change`
meaningful rather than a comparison of two clocks:

| Situation | Verdict |
|-----------|---------|
| Same identity, same content digest | `CURRENT` |
| Same identity, different content digest | `CHANGED` |
| Different identity | `UNKNOWN` — a different source, not a changed one |
| No prior digest | `UNKNOWN` |

`STALE`/`CHANGED` reuse the existing AR-202D freshness vocabulary rather than
forking it, and `HISTORICAL` is a legitimate deliberate choice — a 1996 design is
not stale if it was selected to be a 1996 design.

## `ReferenceSet`

```text
reference_set_id   requirement_scope   created_at
members[]          each with: reference_id, roles[], treatments?,
                   counter_pattern?, note?
coverage           deterministic: READY | INSUFFICIENT + named holes
diversity          deterministic: DIVERSE_ENOUGH | TOO_HOMOGENEOUS | UNKNOWN
budget             limits, spent, expansions[], verdict
limitations        every member's limitations, attributed
approved_direction_id
```

### Roles

`PRIMARY_DIRECTION`, `INTERACTION_REFERENCE`, `LAYOUT_REFERENCE`,
`TYPOGRAPHY_REFERENCE`, `COMPONENT_REFERENCE`, `IMPLEMENTATION_REFERENCE`,
`COUNTER_REFERENCE`. A reference may hold several.

`IMPLEMENTATION_REFERENCE` is deliberately distinct from the aesthetic roles:

> `Linear` → hierarchy reference.
> `shadcn resizable-panel` → implementation reference.
>
> Conflating them is how a reference turns into a clone instruction.

### Counter-references

A counter-reference records **what the design must not become**, and must name the
anti-pattern. "Not like a generic AI dashboard" is not executable; "a generic AI
dashboard: a glassmorphic card grid with gradient glows, a centred hero and no
information hierarchy" is. Disliking something is not a counter-reference.

In the shipped vertical slice the counter-reference is the reference the
counter-search actually retrieved, not one chosen by a heuristic — an earlier
version picked the first reference mentioning surfaces and selected a *positive*
exemplar, which turned the direction's "do not become" clause into a description of
what it emulated.

### Structural refusals

A reference set is refused when it has no `PRIMARY_DIRECTION` member; when a
counter-reference names no anti-pattern; when a member names an unknown role, no
role, or a reference that does not exist; when a member is duplicated; and when it
records no coverage, diversity or budget verdict.

### Diversity

Six axes: `industry`, `surface`, `source-kind`, `light-dark`, `emphasis`, `role`.

Split into **voting** axes (`industry`, `light-dark`, `emphasis`, `role`) and
**provenance** axes (`surface`, `source-kind`). This split is load-bearing: every
getdesign.md entry analyses a website, so `surface=website` is uniform for *any*
selection from that catalogue, and a single-provider set is uniform in `source-kind`
by construction. Letting those vote reported every such set as `TOO_HOMOGENEOUS` on
an axis nobody chose. They are still reported — they are real evidence about the set.

The check states plainly what it does **not** measure:

> *classification, not taste. References spanning several industries but sharing one
> dark palette look monotonous to a human reviewer, and no axis-based check here
> detects that.*

Below three members the verdict is `UNKNOWN`, never a confident answer.

## Reuse and licence boundary

Every external reference carries Ariadne's standing constraints:

```text
extract principles; do not reproduce a branded composition
do not copy exact brand colour values into this project's identity
do not copy brand-specific iconography, wordmarks or imagery
the source's own identity remains the property of its owner
```

These are *Ariadne's* constraints. The source's actual licence and attribution
travel separately in `license_status` and `attribution`.

## Where each rule lives

| Rule | Enforced in |
|-------|-------------|
| Source kind and evidence level are valid | `contracts.reference_problems` → `design_reference_classification_problems` |
| Patterns use the controlled vocabulary | `design_reference_classification_problems` |
| Motion/interaction need a basis | `design_reference_classification_problems` |
| Treatments are well-formed | `design_reference_classification_problems` |
| Set structure and sufficiency | `contracts.reference_set_problems` |
| Members support their roles | `contracts.reference_set_member_problems` |
| Budget bounds | `sets.spend` |
| Observations are not instructions | `sets.assert_observation_not_recommendation` |
| Direction grounding is complete | `direction.grounding_problems` |