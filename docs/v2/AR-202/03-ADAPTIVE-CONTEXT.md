# AR-202 — Adaptive context

Module: `src/ariadne_engine/context.py` · Transport hook: `scripts/prepare-stage.py`
Tests: `scripts/test-engine-core.py` (`context_checks`), benchmark group `adaptive-context`

## 1. Shape of the decision

The existing compiler keeps working; the engine decides *around* it.

```
STAGES + project + operator arguments
        │
        ▼
plan_sources(stage, project, args)         ← one implementation of the selection rules
        │  candidates: label, path, kind, bucket, required, removable,
        │              exists (declared deliverable), absent/selection reasons
        ▼
CONTEXT.decide(...)                        ← engine: cache + rules + characterisation
        │  ContextDecision: one entry per candidate, machine-readable reason
        ▼
CONTEXT.plan(decision)                     ← {omit: {path: reason}, reuse: {path: hashes}, deduplicate}
        │  may only omit removable candidates and reuse hashes; never adds
        ▼
TRANSPORT.prepare(args, context_plan=…)    ← materialises the packet
        │  manifest.context_decision records the applied plan; each source row
        │  carries context_reason (and hashed_from: cache when reused)
        ▼
CONTEXT.finalise(decision, manifest)       ← reconcile intent with what was delivered
CONTEXT.record(state, final)               ← the stored decision is the observed outcome
CONTEXT.update_cache(run_root, state, final, manifest)
```

`runtime.execution-status` prints the latest decision; the canonical event log
records `context_decided`, `context_cache_hit` and `context_invalidated`.

## 2. Reasons

Every entry carries one code from `contracts.CONTEXT_REASONS`:

`REQUIRED_BY_STAGE` · `REQUIRED_BY_TASK_TYPE` · `RELEVANT_CHANGED_FILE` ·
`REQUIRED_BY_VALIDATOR` · `REQUIRED_BY_REVIEW` · `UNCHANGED_CACHED_INPUT` ·
`IRRELEVANT_TO_TASK` · `FORBIDDEN_FOR_STAGE` · `MISSING` · `STALE` ·
`SUPERSEDED` · `OPTIONAL_NOT_SELECTED` · `DEPENDENCY_OF_INCLUDED_SOURCE` ·
`UNAVAILABLE`

Codes that are declared for future use (`RELEVANT_CHANGED_FILE`,
`REQUIRED_BY_VALIDATOR`, `REQUIRED_BY_REVIEW`, `STALE`, `UNAVAILABLE`) are
listed in the vocabulary but are not emitted by any current rule; a decision
entry can never carry an undocumented reason.

## 3. What adaptive context may and may not do

**May:**

* omit a candidate the transport declared `removable` (optional project inputs,
  conditional sources that were not selected);
* reuse the recorded hashes of a candidate it still delivers;
* suppress a byte-identical duplicate delivery, recorded as `SUPERSEDED` with
  `duplicate_of`;
* omit an optional source the characterisation says the task does not need
  (`IRRELEVANT_TO_TASK`, e.g. a creative ledger on a run with
  `creative_evidence_required: false`).

**May not:**

* omit a required project or canonical source — a plan that tries is refused by
  the transport with `PacketError: the adaptive context plan may not omit a
  required source: <path>`;
* add a source (there is no include list), so a cache entry can never resurrect
  a forbidden source or introduce anything the stage does not allow;
* replace a source with a summary (no lossy reduction exists in AR-202);
* alter a deferred decision: `--motion`/`--assets` remain operator-declared and
  are never overridden.

## 4. Caching

Cache file: `<run_root>/context-cache.json`, `schema_version: 1`, entries keyed
by absolute source path.

An entry stores `source_sha256`, `content_sha256`, size, `mtime_ns`, stage,
`policy_version`, the delivering packet's project revision and the decision id.

A cached hash is reused only when **all** hold:

1. the source is not forbidden;
2. the entry's stage equals the stage being prepared;
3. `policy_version` matches the running policy;
4. the entry's project revision equals the parent boundary's project revision;
5. the file exists and its `size` and `mtime_ns` are identical;
6. the entry carries a source digest.

Only sources that were actually **delivered** are cached, and an entry is dropped
when its source is omitted. A miss is not a silent recomputation: the decision
records `invalidated: [{path, reason}]` and the engine emits
`context_invalidated`.

The source is always read and delivered verbatim; reuse skips re-hashing only,
which is observable as `hashed_from: cache` on the manifest source row.

## 5. Measured effect

Measured in the sandbox, deterministic fixtures, no model calls
(`benchmarks/results`, group `adaptive-context`):

| Case | Observation |
|---|---|
| `required-sources-and-reasons` | 7 sources included / 6 omitted, each with a reason; the decision is bound to the packet (`manifest.context_decision.decision_id`) |
| `omitted-optional-source` | the optional creative ledger is omitted (`IRRELEVANT_TO_TASK`); every required source is still delivered; the packet no longer contains the ledger section |
| `cache-reuse-on-unchanged-retry` | a same-stage retry reused **8** recorded source hashes, the packet still verifies, and `context_cache_hit` is recorded |
| `semantic-edit-invalidates-cache` | an edited project source produced an explicit invalidation, and the packet carries the freshly derived hash (equal to the current file hash) |
| `forbidden-source-never-delivered` | the isolated S5 packet still delivers only the canonical pair; no cached project source appears |

Honest limits: the fixtures are small, so the byte saving comes from omitted
optional sources and duplicate suppression, not from large-file reuse. The hash
reuse saves one read-hash pass per unchanged source; preparation-time medians are
reported in `07-TEST-RESULTS.md` with their ranges, and host contention is noted
where it made a comparison inconclusive.

## 6. Invariants

1. Forbidden context stays forbidden: the plan cannot add, and the transport's
   forbidden rules are unchanged.
2. Cache entries cannot validate a stale revision: the revision guard above plus
   the `size`/`mtime` identity, with invalidation recorded.
3. Packet semantics are frozen: required sources are always delivered, and
   without a plan the compiler output is byte-identical to AR-201.
