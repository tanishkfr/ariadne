# 28 — AR-222D Results

**AR-222D — Design Specificity, Proof Readiness & Source Ecosystem Hardening.**

Starting point: `d5a081fda2960298ac802bf9dc4ddb4cf6f562d2` (AR-222 HEAD)
Branch: `v2/2.2-design-proof-hardening`
`VERSION` unchanged at **2.1.0**. No tag, no release, no publish.
Beacon: **UNTOUCHED** — historical AR-222 evidence preserved.
Boreal: **UNTOUCHED**.

---

## The F1 vertical slice

One sentence in:

```text
Make me a cool F1 dashboard.
```

No aesthetic instruction, no reference sites, no provider, no design system, no fonts, no
component library, no spacing system, no capture dimensions, no critique strategy.

### 1. Content understanding, before any layout

Three surfaces modelled from the domain. Nothing about the final content is hardcoded in the
test; the *structure* is derived and the values are plausible rather than round.

```text
live-timing-wall    a race engineer reads this during a live session to answer one question
                    first: is the race on schedule, and whose strategy does this session affect
                    rows 6..20, names 4..26 chars, values 0..189, 6 edge cases

stint-and-tyre-wall a strategy engineer compares stints across compounds to decide the next
                    pit window
                    rows 4..60, names 4..26 chars, values -8..62, 4 edge cases

session-setup       a team confirms the session setup before the cars go out
                    rows 8..34, names 6..28 chars, values 0..110, 3 edge cases
```

The edge cases are the interesting part, because they are what break a naive timing layout: a
pit stop in progress with a stationary lap time, a safety-car period where positions are
provisional, a penalty, a retirement that must not renumber the cars still running, a negative
undercut where the newer compound is slower.

Ranges, not samples — including a **negative** range on the stint surface, because degradation
deltas and lap times share a column.

Six layout constraints derived from the model and carried into the plan:

```text
the surface must remain usable at 20 rows of live-timing-wall
name content must not be truncated at 26 characters; truncation needs an affordance
numeric content must remain aligned across a range of 0 to 189.4
the empty state must be designed, not defaulted
the loading state must be designed, not defaulted
the error state must be designed, not defaulted
```

### 2. Concept candidates — materially divergent

Three candidates across **three concept families**, divergent on **all seven** axes.

```text
Race Engineering Workstation
  family            domain_native_artifacts
  source thing      the timing screen a race engineer has open on the pit wall during a session
  hierarchy model   dense_operational
  richness source   REAL_CONTENT
  own failure mode  every dense surface turning into a terminal cosplay, monospace used as a costume

Broadcast Timing Environment
  family            media
  source thing      a broadcast race timing graphic rather than a screen a person operates
  hierarchy model   reading_oriented
  richness source   TYPOGRAPHY
  own failure mode  generic dark fintech treatment, neon accent on near-black with no semantic load

Physical Racing Instrument
  family            instruments
  source thing      a dash-mounted instrument cluster on a race car
  hierarchy model   instrument_like
  richness source   DATA_VISUALISATION
  own failure mode  neon HUD with fake speed lines, decoration standing in for instrumentation
```

```text
palette_only: false          convergence risk: DIVERSE (0%)
```

The F1-specific names live in the *fixture*, not in production code. The grammar could just as
easily have arrived at three others.

### 3. Internal evaluation and one recommendation

Nine named axes — product fit, project identity, requirement coverage, specificity, reference
support, category-default dependence, implementation feasibility, accessibility constraints,
coherence.

**`aggregate_score: None` for every candidate.** No composite "design quality: 92%". A single
number is uninterpretable, invites gaming, and destroys exactly the trade-off the choice turns
on: two candidates strong on different axes.

```text
RECOMMENDED  Race Engineering Workstation
alternatives  Broadcast Timing Environment, Physical Racing Instrument  (secondary)
```

The two rejections are recorded rather than hidden:

```text
the broadcast-graphics candidate: strong typography but a weak product fit for an operating surface
the cockpit-instrument candidate: not supportable at the required accessibility constraints
```

`recommend()` returns `UNASSESSED` when nothing was evaluated, rather than defaulting to the
first candidate — which would silently turn list order into authority.

### 4. Reference acquisition — need-driven and bounded

Five evidence needs, each mapped to the roles that can answer it:

```text
COMPLETE_VISUAL_DIRECTION    -> DESIGN_SYSTEM, VISUAL_REFERENCE
REAL_PRODUCT_FLOW_PATTERN    -> PRODUCT_PATTERN
DATA_TABLE_PATTERNS          -> COMPONENT_PATTERN, PRODUCT_PATTERN
IMPLEMENTATION_PRIMITIVE     -> IMPLEMENTATION_REGISTRY
LANDING_MOTION               -> MOTION_REFERENCE
```

```text
sources considered   39
source selections    14
deep inspections      5
bytes transported     18,432
seconds              ~12
```

27 selections were *skipped with a recorded reason* — wrong role, disabled, no adapter, or
paid-requires-authorization. Consulting every source is not diligence; it is the absence of a
question.

### 5. Anti-default analysis — detected, then earned

```text
detected      7  dashboard-reflex, everything-is-a-card, generic-greeting, random-glass,
                 generic-ai-gradient, default-font-palette-combo, motion-on-load-without-state-change
earned        6  kept, each with a recorded reason
contradicted  1  generic-ai-gradient -- the direction's own failure mode is the neon-on-near-black
                 treatment this rejects
unexamined    0
```

This is the result that distinguishes this phase from a blocklist. **Six detected defaults were
kept on purpose.** Three of them are the exact patterns a naive anti-slop pass removes:

```text
dashboard-reflex   a race timing surface genuinely is a set of monitored readings a person
                   watches while something else happens, and the domain supplies the
                   arrangement. This is the case where the category reflex is the right answer

everything-is-a-card   rows are grouped by stint and running order, which is a semantic
                      grouping rather than a visual one

random-glass      the accent is scoped to three semantic roles and no surface is translucent.
                  Glare readability under pit-lane lighting is the reason
```

`UNEXAMINED` is the only actionable state, and a recommended direction that left six detected
defaults unexamined would have reported its own incompleteness as a pass.

### 6. Roles, richness, motion intent

Eight role bindings, each with the **meaning** recorded before the value:

```text
colour/background        the ground the instrument housing is cut from; never a brand colour
colour/accent_purpose    exactly three meanings: live flag, position gain, penalty. Nothing else
colour/separator         no separator colour; spacing carries it
type/data_metric         a value read for its number, not its label
```

Two motion declarations, both `STATE_CONFIRMATION`, both with the evidence that makes the claim
a claim:

```text
position-change   a driver changes position, so the row order changes
safety-car        the session state changes, so provisional positions must be visibly provisional
```

Zero platform leaks.

### 7. What the user actually saw

```text
Ariadne has a recommended direction.

RACE CONTROL

A dense, precise Formula 1 workspace based on race engineering rather than a generic
analytics dashboard.

A race engineer reads this during a live session, under time pressure, and needs to know
first whether the race is on schedule and whose strategy this session affects.

Content: race state, timing, telemetry and circuit information at the volumes a real session
produces, including the awkward cases: a pit stop, a safety car, a penalty.
Hierarchy: timing and live race state first; every number carries its unit and no number is
decoration
Colour: neutral instrument surfaces, so that team and race colour only appears where it means
something -- a flag, a penalty, a position change
Layout: a fixed timing rail that does not reflow, with a persistent strategy column, because a
reading that moves between states costs a glance
Richness: real content
Motion: state confirmation

Principles:
- the schedule question is answerable in one glance from anywhere on the surface
- every numeric value carries its unit and its provenance
- a retired or missing car never renumbers the cars still running
- no reading moves position between states

Avoiding:
- generic dark-fintech cards
- neon cyberpunk treatment
- random glass surfaces
- decorative speed effects
- a grid of identical stat cards

Approve direction, adjust, or show alternatives?

[approve]  [adjust]  [show-alternatives]

Ariadne chose this itself: the references, the concepts it compared, the type and colour
candidates and the component choices were all decided internally.
```

**25 lines.** Zero internal provider, source, adapter, transport or digest identifiers leaked —
checked against `INTERNAL_ONLY_FIELDS` and re-checked against the rendered text for `adapter`,
`transport`, `mcp`, `http`, `sha`, `digest`, `res_`, `rfd_`.

The `Avoiding:` block is placed **last** on purpose: it is the cheapest possible check on
whether the system understood the request, and a person who recognises a cliché there can
reject the direction in three seconds without reading the rest.

### 8. G1D approval — not bypassed

```text
before approval   planning refused: the design direction is not approved for its current
                  revision (DESIGN_DIRECTION_UNAPPROVED or DESIGN_DIRECTION_STALE)
approval          apv_... via the real G1D gate, identity ar222d-fixture-operator
approved text     byte-identical to the text shown
proposal digest   matches the shown text
```

The status was **not** written directly. A test that sets `status: approved` would pass with no
human in the loop at all, and the thing being tested is that *a human decision* is the only
interruption.

### 9. Continuation — seven decisions, zero interruptions

```text
implementation planning          AUTOMATIC
component and primitive choice   AUTOMATIC
source provider choice           AUTOMATIC
capture planning                 AUTOMATIC
content-model refinement         AUTOMATIC
responsive mechanics             AUTOMATIC
typography candidate evaluation  AUTOMATIC
```

```text
plan dip_... compiled with 31 constraints, all derived from the approved direction and the
content models -- 6 from CONTENT_MODEL, 8 from DIRECTION_ROLE, 5 from AVOIDED_DEFAULT
```

### 10. Proof readiness at this depth

```text
requirements   3        one per surface, derived from the content model
gaps           0
orphans        0
verdicts       []
absent roles   evidence_producer, independent_reviewer, repair_worker
```

`absent roles` naming those three is the **correct** answer: nothing has been rendered and
nobody has reviewed it.

---

## The internal trace versus the interface

| Step | Internal | What the user saw |
|---|---|---|
| content model | 3 surfaces, 13 edge cases, 6 layout constraints | — |
| concept exploration | 3 candidates, 3 families, 7 divergent axes, 0 convergence | — |
| reference needs | 5 needs, 14 selections of 39, 5 deep inspections | — |
| anti-default | 7 detected, 6 earned, 1 contradicted | 5 items in `Avoiding:` |
| evaluation | 9 axes per candidate, no composite score | — |
| recommendation | 1 recommended, 2 secondary | "Ariadne has a recommended direction." |
| roles and motion | 8 role bindings, 2 motion intents | 6 short intent lines |
| — | — | **one question: approve / adjust / show alternatives** |

Twelve internal steps, one interruption.

---

## Tests

```text
scripts/test-ar222d.py                    124/124 passed
scripts/test-ar222d-mutations.py           35/35 mutations caught, 0 skipped
scripts/test-ar222d-adversarial.py          31/31 attacks held
```

Baseline before AR-222D, all measured on the clean worktree:

```text
Engine core                  PASS  578/578
Decision Runtime             PASS  510/510
Decision mutations           PASS    9/9
Decision runtime mutations   PASS   38/38
AR-220 design-reference      109/109
AR-220 mutations             22/22
AR-221 design-execution       68/68
AR-221 mutations             25/25
AR-221 adversarial            35/35 attacks held
AR-222 rendered-critique      87/87
AR-222 mutations             40/40
AR-222 adversarial            27/27 attacks held
Release tests                PASS   97/97
Distribution                 PASS   55/55
```

## Nine survivors, all real

The AR-222D mutation suite found **nine survivors and three bad anchors** on its first pass.
Every one was investigated, and every one turned out to be a **coverage gap in the new test
suite**, not a mutation to soften:

| Survivor | Real cause |
|---|---|
| pattern with no valid case | only the prohibited-*phrasing* case was tested, not the empty-`valid_when` case |
| three directions differ only by colour | the removal of one axis from the divergence set did not change any candidate's verdict |
| browser-only provider marked API-capable | no live source violates it, so only a synthetic profile could bite |
| registry entry stops being an integration | every shipped row has an `adapter_id`, so only a synthetic row could bite |
| scope enforcement becomes a no-op | **the test reimplemented the check locally — a test of the test file** |
| restored with mutated untracked state | the mutation was a no-op: it added a variable without disabling the loop |
| critical test removed, count gate green | the mutation targeted a regex whose flag did not matter for that function |
| routine refinement interrupts | asserted only "did not interrupt"; `CONDITIONAL` also doesn't interrupt, so the tier was unchecked |
| internal identity leaks into the proposal | a second, independent check caught the same leak, so the mutation was redundant |

Six synthetic cases were added, the scope test was rewritten against the engine's own
`refinement.record_change`, and three mutations were retargeted. Two of the rewritten tests are
named for what they catch, so the gap cannot be reopened silently:

```text
every divergence axis is load bearing, not decorative
a browser only source claiming an adapter is refused by the registry itself
a source claiming an adapter without naming it is refused
an adapter without visible licence terms is refused
a proposal carrying an internal identifier is refused
an unparseable summary is an unenforced floor, not a satisfied one
```

## Findings fixed that were not in the brief's list

The adversarial review and the gate each found a real defect beyond the required mutations:

**Untracked-inventory verification compared sizes, not digests.** A mutated gitignored fixture
of identical length was invisible to both the inventory and `git diff`. Now digested.

**Windows process liveness used `OpenProcess`.** A killed mutation harness looked alive, so its
entry was never reported stale and recovery was never offered. Now `GetExitCodeProcess` +
`STILL_ACTIVE`.

**An edit accidentally replaced Refero's ML-training prohibition** while adding an
access-control prohibition. Caught immediately by the reuse tests. Restored; the entry now
carries five prohibitions.

**The inventory could not parse two suites' summaries.** They print `N/N passed` without a
`PASS` prefix, so they reported `0/0` — which read as *"no floor violation"* and passed
silently. Found by the gate reporting `0/0` in its own output, which is the only reason anyone
would have noticed.

**Four sources had prohibitions recorded only as prose, or not at all** — aceternity,
shadcnblocks, mobbin, threejs-journey. Now structural, so `reuse_check()` can consult them.

## Beacon — preserved

```text
AR-222 Results doc: unread, unmodified
Final status: RENDERED_WITH_KNOWN_FINDINGS -- 0 resolved, 2 persistent, 0 new
  minor    hierarchy
  major    responsiveness   at 390px the log table reaches 568px
```

Beacon remains AR-222's negative/partial case: mechanically valid, rendered and reviewed, with
a known responsive contradiction still standing. An adversarial case asserts the marker text is
still present, so the history cannot be rewritten to look conformant.

Beacon was **not** re-run. AR-222D adds no repair to it; a new revision would be a new evidence
set, and nothing in this phase derived one.

## Known limitations

1. **The F1 slice stops at implementation planning.** No render, no capture, no critique. That
   is a scope boundary — AR-222D proves the method and the UX, and re-running AR-221/AR-222's
   renderer for a demo would be a second rewrite. `absent_roles` reports the consequence
   honestly.

2. **The source registry is verified, not exercised.** Every surface was inspected live on
   2026-10-05, but no adapter is *invoked* in the suite, which runs offline. The registry
   encodes what verification found; it is a record, not an integration test.

3. **The F1 concepts are one fixture.** The grammar is generic; the concepts are not a
   demonstration that it would produce these three for a different prompt. The adversarial
   review covers the *method* with six target styles, not the output space.

4. **Interruption classification is lexical.** Meaning-change detection is structural over a
   curated cue vocabulary, not semantic. A paraphrase outside that vocabulary lands in
   `CONDITIONAL`, which proceeds automatically — safe in the "asked too little" direction, but a
   genuinely meaning-bearing change phrased unusually would not stop.

5. **The named inventory is a floor, not an exhaustive manifest.** 37 guarantees are named.
   Losses outside that list are caught only by the recorded count floors.

6. **The AR-222 mutation suite still takes ~90 minutes.** AR-222D did not reduce it; the
   transactional ledger and the registry are added around it.

## See also

- [21 — Design Specificity Grammar](21-DESIGN-SPECIFICITY-GRAMMAR.md)
- [22 — Minimal Creative Interruption](22-MINIMAL-CREATIVE-INTERRUPTION.md)
- [23 — Design Source Ecosystem](23-DESIGN-SOURCE-ECOSYSTEM.md)
- [24 — Platform Design Profiles](24-PLATFORM-DESIGN-PROFILES.md)
- [25 — Proof Readiness](25-PROOF-READINESS.md)
- [26 — Harness Integrity](26-HARNESS-INTEGRITY.md)
- [27 — Adversarial Review](27-ADVERSARIAL-REVIEW.md)
