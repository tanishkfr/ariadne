# 07 — Reference Economics (AR-220)

> **Ariadne should retrieve enough reference evidence to justify the design — then
> stop searching.**

Bounded research is not a cost optimisation. It is what makes the difference
between a reference *set* and a pile of things someone once looked at.

## Context Economics integration

Context Economics is already Ariadne's existing mechanism: measurements plus
deterministic verdicts plus bounds, so a reader can see whether a limit was
respected. AR-220 joins it rather than inventing a parallel accounting system.

`DesignReference` records extend the existing reference family, so reference
acquisition contributes to the AR-202D design measurements that
`design-report` already aggregates. The economics record adds reference-specific
lines:

| Line | Meaning |
|------|---------|
| `sources_queried` | which adapters were asked |
| `candidates_found` | deterministic search results |
| `references_inspected` | documents actually fetched and parsed |
| `references_selected` | members admitted to the set |
| `bytes_retrieved` | retrieved document bytes |
| `time_spent` | wall clock |
| `reference_budget` | limits, spent, verdict |
| `cache_hits` | satisfied from the frozen corpus without retrieval |
| `failures` | rejected candidates with reasons |

**No monetary savings are invented.** There is no token price, no API cost and no
"hours saved" figure anywhere in the AR-220 code, because none of them are
measurable here. The measured quantities are bytes, counts and verdicts.

## The budget

Defaults in `contracts.REFERENCE_BUDGET_DEFAULTS`:

```text
candidate retrieval:  ≤ 12
deep inspection:      ≤  5
primary references:   ≤  3
counter references:   ≤  2
```

**These are defaults, not truths.** `sets.resolve_budget` accepts larger limits but
refuses an expansion that carries no reason:

```text
budget limit 'deep_inspection' is expanded from 5 to 9 with no recorded reason;
expanding a research budget has to say why
```

An accepted expansion is recorded with the reason and both values:

```json
{
  "limit": "candidate_retrieval",
  "from": 12, "to": 24,
  "reason": "the request asks both for a direction and for an explicit
             anti-pattern, which are two searches. One search already spends the
             default candidate budget of 12, and the default deep-inspection budget
             of 5 cannot cover both searches within the recorded corpus"
}
```

### Enforcement

`sets.spend` refuses **before** incrementing, so a rejected spend leaves the
budget byte-identical:

```text
reference budget line 'deep_inspection' is exhausted (5/5); reference research
stops here rather than exceeding a bound that was set to be a bound
```

`candidate_retrieval` is cumulative and is spent **per search**, not once at the
end. Spending once at the end would let the first search quietly consume the whole
budget before the counter-reference search ran, and the overspend would only be
discovered after the retrieval the budget was meant to bound.

## No search-until-satisfied loop

There is no code path that searches again because the results were unsatisfactory.
Sufficiency is a caller decision, because only the caller knows what would satisfy
it. The acquisition records why it stopped:

```text
the reference budget was applied; Ariadne retrieved enough evidence to justify a
direction and stopped rather than continuing to search
```

This is deliberate. A loop that keeps researching until the model is satisfied has
no bound, and the bound is the feature.

## Acquisition order

```text
1. current project
2. approved local DESIGN.md
3. connected/available Figma or design source
4. approved component registries
5. curated design references (getdesign.md)
6. source repositories
7. broader live web inspection
```

The order encodes a priority, and it is enforced as a *gate*, not a preference:

```text
NO: project-local design evidence has not been examined; run the local probes
    first, because the project's own identity constrains the design before any
    reference informs it
```

and, when the project is already sufficient:

```text
NO: the project already establishes design evidence of its own; external
    references would supplement that identity, and supplementing is optional
    rather than automatic
```

**Project identity comes before external inspiration.** Looking at a catalogue
before looking at the repository is how a project ends up styled like somebody
else's brand.

### One bug this ordering exposed

The slice judged external research `YES` while acquisition independently re-judged
it `NO` and silently overrode the caller. The justification is now a **parameter**
(`project_sufficient`) rather than a re-decision, because two honest evaluations
of the same question disagreeing with no explanation is worse than either answer.

### The counter-search is inspected separately

The anti-pattern search is ranked and budgeted apart from the primary search.
Ranking them together let a high-scoring entry from the anti-pattern search crowd
out the primary references — inverting the request, since the point of the counter
search is to find what to avoid, and letting it displace what to emulate means the
direction is built *on* the anti-pattern.

## Diversity as an economic signal

An expensive set of near-identical references is wasted context. The diversity
check exists partly for that reason, but it is deliberately modest about what it
claims:

> *this measures recorded classification, not aesthetic similarity. Five references
> with different industries and the same dark palette still read as homogeneous to a
> person, and this check will not catch that.*

| Verdict | Meaning |
|---------|---------|
| `DIVERSE_ENOUGH` | no informative voting axis is dominated by one value |
| `TOO_HOMOGENEOUS` | a voting axis holds > 80 % of classified members |
| `UNKNOWN` | fewer than 3 members, or too few axes classified to judge |

`UNKNOWN` is preferred to a confident answer the evidence cannot support.

**Voting axes** (decide): `industry`, `light-dark`, `emphasis`, `role`.
**Provenance axes** (reported, do not vote): `surface`, `source-kind`.

The split is not cosmetic. Every getdesign.md entry analyses a website, so
`surface=website` is uniform for *any* selection from that catalogue, and a
single-provider set is uniform in `source-kind` by construction. Letting those vote
reported every such set as `TOO_HOMOGENEOUS` on an axis nobody chose — a false
signal that would have trained operators to ignore the check.

## Caching and freshness

Cache key: **source identity + URL + retrieval policy**, with the content digest
recorded on every hit.

Freshness is explicit and never assumed:

| Field | Meaning |
|-------|---------|
| `retrieved_at` | always recorded for an external reference |
| `source_revision` | e.g. `VoltAgent/awesome-design-md@main` |
| `source_date` | a date the source itself exposes |
| `freshness` | `CURRENT` / `STALE` / `CHANGED` / `HISTORICAL` / `UNKNOWN` |

**Cached web content is never treated as current forever.** Cached content carries
the retrieval timestamp it was retrieved at, and change detection re-reads the
digest rather than the clock:

| Situation | Verdict |
|-----------|---------|
| same identity, same digest | `CURRENT` |
| same identity, different digest | `CHANGED` |
| different identity | `UNKNOWN` — a different source, not a changed one |
| no prior digest | `UNKNOWN` |

A deliberately historical reference is valid: `HISTORICAL` exists so a 1996 design
selected to be a 1996 design is not reported as stale.

Full drift monitoring is deferred to a later phase. What exists is the ability to
detect *same source identity, different content digest* and mark the prior evidence
according to the existing AR-202D vocabulary.

## Offline economics

The shipped build has `external_reference_capability = AVAILABLE` with
`mode = offline-fixture`. That is honest rather than generous: candidates are
searched across the full 73-row recorded index, and a candidate whose document is
not in the frozen corpus is reported as `SKIPPED` with the reason. In the slice,
five documents were retrieved and one high-ranking candidate was skipped for
exactly that reason.

Offline mode also reorders each batch to prefer recorded documents — before the cap
is applied, not after. Relevance still decides the order within each group, and
unrecorded candidates stay in the report. Ranking first and reordering afterwards
could not recover anything: with a counter-query cap of 2, the two highest-scoring
entries might both be unrecorded and the recording would yield nothing at all.

## Measured slice economics

Full numbers in [08-AR-220-RESULTS.md](08-AR-220-RESULTS.md). Summary:

| Measure | Value |
|---------|-------|
| Sources queried | 1 external adapter + 4 project-local probes |
| Candidates found | 12 primary + 12 counter-query |
| Deep inspections attempted | 8 |
| References retrieved | 4 external + 1 project-local |
| Bytes retrieved | 107 634 |
| Cached (frozen corpus) | 4 documents, 0 network requests |
| Budget verdict | `WITHIN_BUDGET`, 2 recorded expansions |
| Injection attempts found | none — the recorded corpus contains none |
| Failures | 1 candidate skipped: no recording, no authorized fetch capability |

## What is not built

- **No embeddings, no vector database.** Search is deterministic lexical matching.
  An unauditable relevance function is a worse answer than an honest lexical one.
- **No cost model, no currency figures.** Measured quantities are counts, bytes and
  verdicts.
- **No automated cache refresh.** Fixtures are refreshed by running the recorder by
  hand, so no background job can quietly change what the tests assert.
- **No scheduling of research across a run.** One direction, one bounded
  acquisition.