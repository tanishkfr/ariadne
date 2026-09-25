# 08 — Decision economics

`ariadne_engine.decisions.economics` measures the decision plane from records the
engine wrote. Nothing is estimated and nothing is converted into money: without
live provider usage there is no comparable billing to convert, and the module
says so instead of inventing a saving.

## What is measured

| Metric | Source |
|---|---|
| plans, fast-path plans | compiled `DecisionPlan` records |
| deterministic facts / bounded questions / generative needs | plan contents |
| `model_calls_avoided_by_deterministic` | facts whose value code already knew |
| `model_calls_avoided_by_bounded_decision` | bounded questions with a closed answer space |
| `generative_calls_required` | compiled generative needs |
| provider calls / questions per batch | decision batches not served from cache |
| cache-served batches and reuses | reuse batch records and `cached` decision records |
| escalations | decisions not accepted, or answered with a refusal |
| second opinions | consensus comparison records |
| state bytes | the projection characters actually sent |
| decision-plane overhead | serialized size of every decision-intelligence record |

The avoidance counters are *structural*: a bounded question has a closed answer
space and is a cheaper mechanism than generation, and a known fact is cheaper
still. The module's note states plainly that no monetary saving is claimed
without measured comparable usage.

## Compiled plan versus old execution plan

`compiled_plan_comparison` compares an execution plan with and without decision
compilation on six structural axes: model calls, decision calls, state bytes,
generative stages, verification stages and worker count. It reports the deltas
and a claim boundary: the comparison is structural, no live model was invoked,
and **no quality parity is claimed** because that would require model-backed
evidence this milestone deliberately does not purchase.

## Measured local overhead

`measurements/decision-intelligence-perf.json` records the median and p95 wall
time of the layer's operations on this machine (Windows, CPython 3.11.9, 200
iterations except the trace, which used 50):

| Operation | Median | p95 |
|---|---|---|
| state projection (build + digest) | 13.4 µs | 25.1 µs |
| trace generation (explain) | 16.7 µs | 31.0 µs |
| cache lookup (hit) | 20.4 µs | 37.5 µs |
| batch planning (4 questions, one dependency) | 27.0 µs | 49.3 µs |
| compile plan (3 requirements, one known fact) | 33.1 µs | 69.5 µs |
| build decision graph from a plan | 52.6 µs | 137.0 µs |

The overhead is proportional to the decision, not to the run: every operation is
sub-millisecond and the fastest paths are the ones that decide *not* to ask
anything. These are structural overheads of the decision layer, not provider
latency and not a measure of model quality.

## Why no dollar figure

AR-204's economics infrastructure already separates measured usage from unknown.
Decision Intelligence inherits that discipline: `generative_calls` is reported
as `UNKNOWN - no generative provider usage was recorded` unless usage was
actually reported, and a cache reuse is never counted as a provider call because
no provider was called. When a real decision provider is configured and bills
calls, the same counters will be the numerator for a real cost, and the
calibration data in [12 — Release delta](12-RELEASE-DELTA.md) will be the
denominator.
