# AR-204 — Context Economics

Where delivered context comes from, what it costs, and what AR-204 does *not*
claim about it.

## 1. Attributable by construction

Every rendered section lands in one of fifteen source buckets. The classification
comes from the transport's own `kind` label plus a small path override table, so
an unrecognised section becomes `OTHER` with the reason recorded instead of a
plausible guess.

```text
SYSTEM  TOOL_SCHEMAS  TASK  PROJECT_FACTS  PROJECT_SOURCE  RETRIEVED_SOURCE
POLICY  SKILLS  DESIGN_CONTEXT  EVIDENCE  HISTORY  SUMMARY  PREVIOUS_ATTEMPTS
DECISION_CONTEXT  OTHER
```

`economics.source_accounting` reports, per bucket, the source count, measured
bytes and measured tokens, and separately the duplicate bytes, the cacheable
bytes, the volatile bytes and the byte share that could not be classified. Bytes
and tokens never convert into one another.

## 2. AR-203 composition, mapped not replaced

The AR-203 `context_composition` buckets stay the record format. They map onto the
AR-204 vocabulary without renaming anything:

| AR-203 bucket | AR-204 bucket |
| --- | --- |
| `static_system` | `SYSTEM` |
| `tool_schemas` | `TOOL_SCHEMAS` |
| `project_context` | `PROJECT_FACTS` |
| `retrieved_source` | `RETRIEVED_SOURCE` |
| `evidence` | `EVIDENCE` |
| `history` | `HISTORY` |
| `summaries` | `SUMMARY` |

That mapping is asserted by an engine check, so a future rename in either family
fails the suite rather than silently splitting the accounting.

## 3. Adaptive-context decisions, measured

AR-202's decision layer already records, for every candidate source, whether it
was included or omitted and why. AR-204 aggregates that:

* included and omitted counts;
* a histogram of the decision reasons (`REQUIRED_BY_STAGE`,
  `UNCHANGED_CACHED_INPUT`, `IRRELEVANT_TO_TASK`, `FORBIDDEN_FOR_STAGE`, …);
* cache hits, misses and invalidations;
* duplicate rows where a source was delivered twice under two labels.

The benchmark's adaptive-context and context-economics groups drive real
decisions, so the aggregate fields are populated by real records: considered
versus included sources, cache hits, misses, invalidations and duplicate rows. The
per-decision numbers live in each benchmark result document, and the totals of the
final AR-204 run are reported in [11-TEST-RESULTS.md](11-TEST-RESULTS.md) rather
than restated here.

## 4. Terminology that forbids a causal claim

The milestone brief is explicit that appearing in a successful run is not
usefulness. The vocabulary is therefore:

| Term | Meaning |
| --- | --- |
| `INCLUDED` | the source was delivered |
| `ACCESSED` | a later record names it as read |
| `REFERENCED` | a later record names it as used for a decision or claim |
| `REQUIRED_BY_POLICY` | a deterministic rule demands it |
| `OMITTED` | it was deliberately withheld, with a reason |
| `UNKNOWN_VALUE` | the run cannot say |

`economics.context_economics` returns this list with its own output so a reader
cannot mistake an inclusion count for a value measurement.

## 5. Reduction experiments and their state

Six reductions were specified; each is implemented behind a flag and each stays
off by default, because removing context changes what a model sees:

| Experiment | Flag | Default | Measured effect |
| --- | --- | --- | --- |
| omit irrelevant policy files | `context_reduction` | off | not enabled; AR-202 omission rules already cover declared-removable sources |
| omit unrelated directory trees | transport exclusion rules | active | already enforced by the transport's forbidden inputs |
| omit stale or redundant history | `compaction` | off | structural byte saving measured, quality `NOT_EXECUTED` |
| avoid repeated identical source | duplicate detection | measurement only | duplicate bytes reported, nothing removed |
| load stage-specific context only | capability packs | `legacy` | deferrable bytes measured at 97.4% of pack bytes |
| keep exact evidence external until needed | `output_externalization` | threshold | full evidence preserved, model view bounded |

Nothing protected is ever omitted: a forbidden source stays forbidden, a required
source stays delivered, and an authorization-relevant record is never a
candidate for removal in the first place.

## 6. What is deliberately not claimed

* No token attribution exists per source, because no tokenizer or provider
  measured one. Byte shares are byte shares.
* No source is labelled useful. The strongest statement available is that a
  source was included for a declared reason and, if a later record named it,
  accessed.
* The reduction experiments have no model-quality evidence. `10-EXPERIMENTS.md`
  records each control-versus-candidate figure that *was* measured and marks the
  rest as not executed.
