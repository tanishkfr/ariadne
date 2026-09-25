# AR-204 — Baseline Economics

The measured starting point, before any optimisation is enabled.

## 1. What could be measured, and what could not

AR-203 built the usage seam and deliberately left it unpopulated because no paid
provider was called. AR-204 keeps that honesty and adds the task-level accounting
around it. The current state of a run in this repository is therefore:

| Dimension | State |
| --- | --- |
| request bytes per stage | measured, from real packet files |
| context composition per source | measured for bytes; tokens only when a provider reports them |
| provider token usage | `UNKNOWN` — no provider was invoked |
| monetary cost | `UNKNOWN` — no provider billing and no configured price profile |
| task tree | measured from engine execution records |
| tool-schema bytes | measured from repository files |
| local operation latency | measured with warm-up and repeats |

An absent figure stays absent. `economics.task_cost` states
`usage_complete: false` and lists the executions with no measurement rather than
reporting a smaller total.

## 2. Packet bytes per stage

Four real packets assembled under the benchmark fixture
(`harness-metrics.packet-economics`), rendered by `harness.packet_map`:

| Stage | Packet bytes | Sections | Stable prefix | Volatile | Stable share |
| --- | ---: | ---: | ---: | ---: | ---: |
| S1 | 21,444 | 3 | 21,046 | 398 | 98.1% |
| S3 | 50,309 | 8 | 37,548 | 12,761 | 74.6% |
| S4A | 16,682 | 6 | 16,296 | 386 | 97.7% |
| S4B | 45,844 | 10 | 34,138 | 11,706 | 74.5% |
| **total** | **134,279** | 27 | **109,028** | **25,251** | **81.2%** |

The AR-203 baseline recorded S1 at 21,889 bytes and S3 at 51,451 bytes for the
same fixture; the difference is the fixture's rendered content, not a change in
the compiler.

## 3. Context composition by source

Bucket totals across the four packets, from the same run:

| Bucket | Bytes | Share |
| --- | ---: | ---: |
| PROJECT_FACTS | 47,901 | 35.7% |
| DESIGN_CONTEXT | 31,581 | 23.5% |
| POLICY | 19,233 | 14.3% |
| SYSTEM | 35,564 | 26.5% |
| four buckets together | 134,279 | 100.0% |
| TOOL_SCHEMAS | 2,896 | measured separately from repository files |

Project facts and design context together are 59.2% of the delivered bytes, while
policy documents and the stage prompt plus scaffolding are 40.8%. The per-stage
rows are in the measurement artifact:

```text
docs/v2/AR-204/measurements/ar-204-measurement-summary.json
```

## 4. Task-level accounting

`economics.task_cost` and `economics.verified_completion_cost` define the primary
metric of the milestone:

```text
verified_completion_cost =
      coordinator spend
    + decision batch spend
    + worker spend
    + repair spend            (failed attempts are included)
    + validation spend
    + review spend
```

Rules the implementation enforces:

* a failed or abandoned execution is part of the task's cost;
* a task that never reached an AR-203 verification at `VERIFIED` reports
  `cost_of_unverified_attempt` instead, so the two numbers are never conflated;
* billing is monetary only when a provider reported it, or when a registered
  price profile is supplied and the result is labelled `DERIVED`;
* node shares are computed from measured output tokens only, and are `UNKNOWN`
  when output tokens were never measured.

## 5. The baseline task tree

The benchmark's verified-completion fixture builds one task with an observer, a
verifier and a reviewer. Its measured shape:

| Node | Executions | Measured usage |
| --- | ---: | --- |
| worker / observer | 1 | input and output tokens, request count |
| validation / verifier | 1 | input and output tokens, request count |
| review / reviewer | 1 | input and output tokens, request count |
| decision batches | 0 | — |

Because the fixture records usage through the engine seam with a named observer,
the metric is `MEASURED` for that task. A real run with no provider reports no
monetary figure at all, which is the state this milestone documents rather than
hides.

## 6. Local baseline performance

Twelve operations from the AR-204 surface, warmed up and repeated on the S1 packet
(`harness-metrics.local-performance`), taken from the final run of this worktree;
medians in milliseconds:

| Operation | Median | p90 |
| --- | ---: | ---: |
| history_compact (9 entries) | 0.83 | 1.27 |
| render_request (warm) | 0.91 | 1.10 |
| packet_map (warm) | 0.62 | 0.75 |
| pack_sizes (whole repository) | 0.20 | 0.27 |
| history_economics (60 entries) | 0.12 | 0.14 |
| compact_packet_text | 0.12 | 0.12 |
| raw source hash (16 KB) | 0.060 | 0.089 |
| memoised source hash (same file) | 0.008 | 0.009 |
| canonical_json | 0.036 | 0.054 |
| stable_prefix | 0.044 | 0.073 |
| path_plan | 0.003 | 0.003 |
| task_tree | 0.002 | 0.011 |
| packet_map (cold, memo cleared) | 6.90 | — |
| render_request (cold, memo cleared) | 8.90 | — |

The memo row is comparable work on the same file: the memoised repeat is more than
seven times faster than re-hashing. The cold rows show what a first render
genuinely costs, and they are reported because a warm-only figure would overstate
the saving. Across the four measurement runs of this milestone the same operations
varied by host contention — `packet_map` warm ran 0.32 to 0.75 ms and cold 5.8 to
9.6 ms — so the committed artifact's values are quoted rather than the best one.

## 7. What the baseline says

* Reusable bytes already dominate a rendered packet, but the *order* puts the
  per-request values first, so a provider that caches a byte prefix can reuse
  nothing above the scaffolding.
* Tool declarations are a small share of a packet; deferring unused packs is a
  real saving only for stages that never touch them.
* No token or monetary baseline exists, because no provider was called.
  Every figure that requires one is `UNKNOWN` in this milestone.
