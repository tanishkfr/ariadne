# AR-223: Performance

> **The bounded path has to be cheap, or the scheduler is under pressure to skip it.**

## Why performance is an architecture constraint here

AR-205D built a ladder: deterministic rules, then a bounded runtime, then generation. The rule
"do not spend model inference on what deterministic rules determine" is easy to state and easy
to erode. It erodes the moment the cheap rung is slow, because then every scheduling decision
becomes a judgement call, and a judgement call under time pressure is a judgement made in
favour of the rung that is *more* capable rather than the one that is *measured*.

So the bounded rung has to be fast enough that obeying the ladder costs nothing. It is.

## Measured

Local wall clock, this machine, warm interpreter, the seeded naive-Bayes reference engine:

```text
one decide() call                       0.038 ms
one family evaluation (250 cases)       19 ms
full fit + measure + promote, 4 families  0.19 s
Beacon proof pass                       7.5 ms
repair and re-verification slices       0.7 ms
corpus build (406 cases)                < 1 ms
```

Per-case latency reported inside the evaluation, from the rows themselves:

| Family | p50 | p95 |
| --- | --- | --- |
| REVIEW_ESCALATION | 0.067 ms | 0.103 ms |
| EVIDENCE_RELEVANCE | 0.076 ms | 0.113 ms |
| FAILURE_CLASSIFICATION | 0.064 ms | 0.087 ms |
| ROUTE_FAMILY | 0.037 ms | 0.052 ms |

## What the whole milestone costs

The full vertical slice — sweep the development split, fit thresholds and temperatures, evaluate
four families out-of-sample, evaluate them adversarially, build a canonical AR-206 evaluation
report per family, walk four adoption lifecycles — is **0.19 seconds**.

That number matters more than it looks. It means the promotion decision is cheap enough to
re-run on every release, which is the only way `enforce_health` can be a real control rather
than a procedure somebody runs when they remember.

## What was not measured

**No concurrency.** Every figure is single-threaded and sequential. Nothing here says what
happens with fifty evaluations in parallel, and the corpus evaluation is embarrassingly
parallel in shape (one `decide` per case, no shared state) if that ever matters.

**No cold start.** The interpreter is warm. First-call import cost for
`ariadne_engine.intelligence` is not in these numbers.

**No other hardware.** This is one machine on one platform. Latency in the evaluation reports is
labelled as a property of this machine in the report's own `limitations` field, because a p95
from a developer's laptop is not a latency budget.

**No model provider.** Every figure is the local seeded engine. A provider-attached run would
be dominated by network time, and the scheduler's cost ordering — deterministic, then bounded,
then generation — is exactly what that makes worth having.

**No memory profile.** The corpus is 406 cases and the run state is small; neither was
instrumented.

## The conclusion that matters

The bounded rung is three to four orders of magnitude cheaper than a model call and fast enough
that the ladder is not worth arguing about. That is the performance result: not a benchmark
number, but a constraint satisfied so that the architecture's cheapest-first rule survives
contact with a deadline.

**Next:** [Closure Report](39-AR-223-CLOSURE-REPORT.md)
