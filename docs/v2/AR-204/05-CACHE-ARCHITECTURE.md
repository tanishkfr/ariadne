# AR-204 — Cache Architecture

What is reusable, what is not, and how the difference is proven rather than
assumed.

## 1. Determinism first

A reusable prefix is only reusable when the same logical content renders the same
bytes twice. `ariadne_engine.serialization` supplies the primitives the rest of
the harness builds on:

| Primitive | Guarantee |
| --- | --- |
| `canonical_json` | sorted keys, tight separators, no NaN, refusal rather than stringification |
| `stable_digest` | a labelled digest whose parts cannot collide across boundaries |
| `deep_sorted` | recursively key-sorted values, with list order preserved as data |
| `normalise_text` | LF endings and no trailing whitespace, used for hashing only |
| `stable_prefix` | an ordered segment plan with an explicit boundary index |
| `Memo` | a keyed cache whose entries are bytes or digests, never authority |

Two engine checks pin the contract: two identical renders must produce the same
prefix digest and bytes, and changing a stable segment must change the digest.
A third asserts that a volatile segment carries no authority over the prefix,
which is invariance 49 expressed as a test.

## 2. Ordering: measured, then planned

The measurement (see `02-BASELINE-ECONOMICS.md`) is that the packet's per-request
values come first: packet id, provider, source commit, parent packet, worker
contract. The stable-first plan puts declarations and engine context above a cache
boundary, project setup below it, and the task plus evidence last.

```text
stable tool and capability declarations
stable engine and policy context
==================== cache boundary ====================
project and session setup
==================== cache boundary ====================
volatile task, history and evidence
```

The packets themselves are not re-ordered. A worker reads a packet in the order
the transport produces it, and re-arranging that is a behaviour change the
milestone does not make silently. The plan is available to any adapter that can
place a breakpoint, and the measurement tells an operator what the current order
costs.

## 3. What "stable" means here

Two different questions were separated, because conflating them produced a
misleading split in the first implementation:

* **per-request volatility** — the value changes between two renders of the same
  revision: a run, packet or execution id, a timestamp, a parent reference. These
  three kinds make a delivered section unusable as a reused prefix.
* **revision volatility** — the value changes when the content changes: a content
  digest, a commit, a machine path inside project text. Two renders of the same
  revision are still byte-identical, so a delivered section is reusable *for that
  revision* and the transport's own content digest is what proves it.

A delivered section is therefore classified stable when its header carries a
content digest and no per-request value was detected, and volatile when either
condition fails. The volatility scan is bounded and reports `scanned_bytes`
against `total_bytes`, so a bounded scan is never quoted as a complete one.

## 4. Cache telemetry, split honestly

`economics.record_cache_observation` keeps two channels apart:

| Channel | Content | Meaning |
| --- | --- | --- |
| measured | `cache_hit`, cached and uncached tokens, cache read/write | a provider reported it |
| structural | prefix digest, prefix bytes, volatile bytes, boundary index | the request *could* be cached |

Structural data never sets `cache_hit`. The record's own note says so, and a
mutation that made it report a hit from structural data was detected by the engine
suite. This is invariance 42 in practice: reuse may not manufacture a measurement.

## 5. Provider neutrality

No adapter is assumed to support explicit cache breakpoints. The stable-first
ordering is useful either way: a provider with automatic prefix caching benefits
from ordering alone, and one with breakpoints can read `boundary_index`. Nothing
in the engine requires a provider that reports cache fields; a run without them
records structural cacheability and says `UNKNOWN` for hits.

## 6. Reuse safety

The AR-202 context cache already refuses an entry whose stage, policy version,
revision, size or modification time has moved. AR-204 adds two rules around it:

* a memo entry is keyed by the digest of what it analyses, so a changed text is a
  different key and the worst case is recomputation;
* no cache, memo or structural observation can satisfy a verification or grant an
  authorization. Those paths read engine records, not caches.

## 7. Measured position after the milestone

The stable share of the four fixture packets is 81.2%, and the section rows say
exactly where the rest goes. Every volatile byte is accounted for by two things:
the transport scaffolding itself, and two project-runtime ledgers delivered whole
at S3 and S4B.

| Stage | Volatile bytes | Composition |
| --- | ---: | --- |
| S1 | 398 | scaffolding only |
| S3 | 12,761 | 808 scaffolding + 11,953 `creative-evidence.json` |
| S4A | 386 | scaffolding only |
| S4B | 11,706 | 1,408 scaffolding + 10,298 `creative-operations.json` |

Both ledgers are JSON documents that record a timestamp per entry, so a repeated
render of the same revision is not byte-identical and the whole ledger is
correctly classified volatile. That is a real, specific opportunity: delivering a
deterministic projection of a ledger (stable ordering, timestamps moved to a
single recorded summary) would make roughly 22 KB reusable. AR-204 does not
implement it, because dropping per-entry timestamps from a delivered artifact
removes audit information from what a worker sees; it is recorded as a ranked
opportunity in [14-ADR.md](14-ADR.md) and in the AR-205 handoff.
