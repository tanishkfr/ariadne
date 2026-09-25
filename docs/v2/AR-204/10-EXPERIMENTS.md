# AR-204 — Experiments

Control versus candidate for every optimisation this milestone built. One change
per experiment, both sides measured with the same fixture and the same host.

## 0. Reading rule

A structural result is not a quality result. Every row below separates the figure
that was measured from the claim that was not tested. Where a live model would be
required to establish quality parity, the row says `NOT_EXECUTED` and no
equivalence is inferred.

## E1 — Compact transport scaffolding

| | Control | Candidate |
| --- | --- | --- |
| Profile | `legacy` | `compact_v2` |
| Rendered bytes, four packets | 134,279 | 133,626 |
| Removed | — | 653 bytes (0.49%) |
| Source sections | 27 | 27, byte-identical |
| Prompt block | delivered | byte-identical |

Blocks dropped: the Ariadne source commit, the provider line, the parent packet
line. Blocks rewritten: the transport notice and the independent-validation
reminder. The candidate is behind `prompt_profile`; the control remains the
default. Model-quality comparison: `NOT_EXECUTED`.

## E2 — Capability-pack deferral

| | Control | Candidate |
| --- | --- | --- |
| Declared pack bytes | 110,673 | 2,896 |
| Deferrable share | — | 97.4% |
| Packs loaded at S4B | every declared pack | core only |
| Required-capability guard | — | refuses a missing capability |

The saving is real for a backend task and irrelevant for a design task, which is
why the selector is a function of the stage rather than a global switch. The
candidate is behind `tool_loading`; model-quality comparison: `NOT_EXECUTED`.

## E3 — Large-output externalization

| | Control | Candidate |
| --- | --- | --- |
| Small output (1 line) | inline, digest only | inline, unchanged |
| Large output (61,779 bytes) | digest only, bytes discarded | artifact kept, excerpt in the model view |
| Bytes recoverable after the run | 0 | 61,779 |
| Model-facing bytes for the large case | 0 | 3,072 + reference |

The control is the pre-AR-204 runtime, which kept `stdout_sha256` and nothing
else. The candidate is default-on behind `output_externalization` because it only
adds storage. This experiment has no quality trade-off to test: the model sees
strictly more than zero bytes plus a handle, and the full evidence is intact.

## E4 — History compaction

| | Control | Candidate |
| --- | --- | --- |
| History bytes, 9 entries | 8,707 | 8,707 archived |
| Active view bytes | 8,707 | 1,159 |
| Protected entries | 9 | 6 verbatim, 3 structured |
| Full history | active only | archived (10,808 bytes), digest recorded, retrievable |
| Duplicate entries | repeated in place | marked once |

Structural saving only. The candidate is behind `compaction`, default `off`, and
the loss question — whether a compacted transcript still produces the same worker
behaviour — is `NOT_EXECUTED`. What *is* tested is that nothing protected can be
dropped and that the complete original survives.

## E5 — Deterministic serialization and the render memo

| | Control | Candidate |
| --- | --- | --- |
| `packet_map`, median | 8.26 ms per call (no memo, unbounded scan) | 0.62 ms warm (0.32-0.75 across runs) |
| `packet_map`, cold | 8.26 ms (equal by construction) | 6.90 ms (5.8-9.6 across runs) |
| `render_request`, median | 11.72 ms | 0.91 ms warm, 8.90 ms cold |
| Source hash, 16 KB | 0.060 ms per call | 0.008 ms memoised |

Two changes are bundled here because they are inseparable in practice: the bounded
volatility scan and the pure analysis memo. The cold row is included precisely
because a warm-only number would overstate the result: the first render of a packet
is now somewhat slower than before and every repeat render is more than an order of
magnitude faster. Comparable work, same host, same packet, warm-up plus repeats
with medians. Both changes are default-on because neither alters what is sent.

## E6 — Cache-prefix classification

| | Control (first implementation) | Candidate |
| --- | --- | --- |
| Stable share, four packets | 73.4% | 81.2% |
| Stability rule | "any volatile value makes the section volatile" | "content-addressed unless a per-request value is present" |
| False claims | a project path in delivered text made content look volatile | the reason is recorded per section |

This is a measurement correction, not a byte reduction: nothing a worker receives
changed. The corrected rule is tested by a dedicated case and by a mutation that
makes structural cacheability masquerade as a cache hit.

## E7 — Ledger projection (proposed, not implemented)

The measurement found that 22,251 of the 25,251 volatile bytes are two project
ledgers whose entries carry timestamps. A deterministic projection would make them
reusable. It is **not** implemented, because a delivered artifact with its
per-entry timestamps removed has lost audit information, and the milestone's own
rules forbid trading evidence for bytes. Recorded for AR-205 with the measured
number attached.

## E8 — Decision batching against a generative call

| | Control | Candidate |
| --- | --- | --- |
| Shape | one generative call per judgement | one bounded batch of independent questions |
| Requests, fixture | n/a | 1 for 2 questions |
| Usage measured | no provider | no provider |
| Cost comparison | `NOT_EXECUTED` | `NOT_EXECUTED` |

The correctness of batching is tested offline with the deterministic provider. The
economic comparison needs measured usage from both shapes, which needs an
authorized provider, which this milestone did not use.

## Summary of what may move

| Experiment | Default | Measured saving | Quality tested |
| --- | --- | --- | --- |
| E1 prompt profile | legacy | 653 bytes | no |
| E2 pack deferral | legacy | up to 107,777 bytes | no |
| E3 output externalization | threshold | 61,779 bytes recovered | not applicable |
| E4 compaction | off | 7,548 active bytes | no |
| E5 serialization and memo | on | 7.2x on hashing, 13x on repeated renders | not applicable |
| E6 classification | on | none (correctness) | yes, by test |
| E7 ledger projection | not built | 22,251 bytes | no |
| E8 decision batching | measurement only | unknown | partially, offline |
