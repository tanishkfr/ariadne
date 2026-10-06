# AR-223: Architecture and Integration

> **Where the new code sits, what it depends on, and how it reaches the rest of the engine.**

## The package layout

```text
src/ariadne_engine/
├── acceptance/                    AR-223, first half
│   ├── contract.py                the request, bound to its digest, versioned
│   ├── requirements.py            obligations, provenance, per-requirement evidence policies
│   ├── claims.py                  what was said, by whom, never evidence
│   ├── evidence.py                what was observed, whose it is, whether it is current
│   ├── decisions.py               the six verdicts, their derivation, bounded-advice hook
│   ├── gates.py                   the only place acceptance is decided and explained
│   ├── invalidation.py            selective re-verification planning
│   ├── security.py                what an outside party may put in a record
│   ├── integrations.py            joining all of it to the AR-220..222 records
│   └── beacon.py                  the two proof-pass slices
│
├── intelligence/                  AR-223, second half
│   ├── corpus.py                  splits, leakage guards, what a corpus must declare
│   ├── corpus_data.py             406 reviewed labels with provenance
│   ├── evaluation.py              the real engine over the real corpus
│   ├── calibration.py             thresholds and temperatures, six-way binding
│   ├── promotion.py               measured merit as the second gate, and its removal
│   └── scheduler.py               cheapest sufficient intelligence
│
└── design_reference/specificity/interruption.py
                                   AR-223 correction: risk-sensitive escalation
```

## Dependency direction

```text
corpus  ->  (nothing but the contracts vocabulary)
corpus_data  ->  corpus
evaluation  ->  corpus, decisions.runtime
calibration  ->  corpus, evaluation, decisions.runtime.profiles
promotion  ->  corpus, calibration, evaluation, decisions.runtime.promotion
scheduler  ->  corpus, decisions.runtime.{promotion,selection}
acceptance.*  ->  contracts, and each other in dependency order
```

No module in `intelligence/` imports from `acceptance/`, and no module in `acceptance/` imports
from `intelligence/`. They meet only at `gates.run_pass(bounded_advice=...)`, which is a
keyword argument carrying a mapping. That is the whole integration surface, and it is one
argument wide.

## What was extended rather than written

The runtime already existed and was good. Nothing here reimplements it:

| Needed | Provided by |
| --- | --- |
| the engine under test | `decisions.runtime.reference.ReferenceBoundedEngine` |
| the runtime session | `decisions.runtime.session.DecisionRuntime.in_process` |
| the four question records | `decisions.runtime.seeds.seed_families` |
| ECE and Brier | `decisions.runtime.evaluation` |
| calibration profile construction and validation | `decisions.runtime.profiles.build_profile` |
| the adoption lifecycle | `decisions.runtime.promotion` |
| scope matching | `decisions.runtime.promotion.scope_matches` |
| provider selection | `decisions.runtime.selection.select_bounded_provider` |

`promote` is thirty lines around `runtime_promotion.transition`. That is deliberate: the
lifecycle, its states, its `ACTIVE`-only-from-`ELIGIBLE` rule and its evaluation-id requirement
are all AR-206's, and duplicating them would create a second answer to "is this slice
authoritative".

## Two additions to existing modules

Both small, both in the acceptance package, both found by testing rather than by design review.

**`requirements.create(dependencies=...)`** — a requirement may declare dependency
fingerprints. `invalidation.declared_dependencies` already read this field and treated its
absence as `UNKNOWN`; the record simply had no way to set it. Without it, `PROVEN_UNAFFECTED`
was unreachable and every unrelated requirement would have been re-verified after every change.

**`gates.run_pass(unaffected=...)` and `evaluate(exempt_evidence_ids=...)`** — evidence about a
requirement proven unaffected stays weighable at the new work digest. Every admitted row is
listed in `admitted_by_dependency_proof`, and the staleness clause skips exactly those rows and
nothing else. The one exception to freshness is named in the signature rather than buried in the
code that computes it.

Both were added because the repair slice could not otherwise be honest. Without the second,
selective re-verification is theoretical: the unrelated requirement gets re-checked anyway,
because its evidence is bound to the old digest.

## State, and where records live

Acceptance state is a plain dict with these keys, all written by the modules above and all
validated on the way in:

```text
acceptance_contracts   acceptance_requirements   acceptance_claims
acceptance_evidence    acceptance_decisions      acceptance_passes
decision_adoption      calibration_profiles      (the AR-206 runtime collections)
```

Nothing in AR-223 wrote a bespoke file format. The acceptance records join AR-206's collections
so one run state carries acceptance decisions, adoption slices and calibration profiles
together — and so `gates.problems(state)` can validate the whole thing at once.

## The bounded-advice boundary, precisely

```python
gates.run_pass(state, ..., bounded_advice={
    requirement_id: {"answer": "SUPPORTS", "confidence": 0.97,
                     "confidence_kind": "PROVIDER_PROBABILITY"},
})
```

Three things happen to that mapping:

1. **The rung decides whether it is read at all.** Only `verification_mode` of `BOUNDED` or
   `GENERATIVE` consults it. A `DETERMINISTIC` requirement never sees it — there is a test that
   asserts the string `SUPPORTS` does not appear anywhere in such a decision.
2. **It is consulted only after the deterministic rules left the question open.** It cannot
   override a `FAILED`; the Beacon slice passes a `SUPPORTS` answer at 0.99 for the requirement
   whose measurement says `FAILED`, and the verdict stays `FAILED`.
3. **It is recorded with its `confidence_kind` and the note that it was not treated as
   authority.** The trace line reads
   `bounded advice SUPPORTS (confidence_kind=PROVIDER_PROBABILITY); recorded, not treated as
   authority`.

There is no fourth thing, and that is the design: no code path converts a confidence into a
verdict.

## How a caller uses this

```python
import ariadne_engine
from ariadne_engine.intelligence import promotion, scheduler

# measure, then let the policy decide
result = promotion.run_and_promote(ariadne_engine, state, corpus=None)
state = result["state"]
# result["promoted"] -> ['REVIEW_ESCALATION', 'ROUTE_FAMILY']

# then, per decision
choice = scheduler.for_family(state, "ROUTE_FAMILY", model_revision=result["model_revision"])
# choice["level"] -> 'BOUNDED_LOCAL' | 'DETERMINISTIC' | 'GENERATIVE' | 'HUMAN'
# choice["authorization_effect"] -> 'none'
```

Nothing in that flow can produce a grant, an acceptance, or a release. A caller that wants one
goes to a human, which is the point.

## Cost

```text
one decide() call                    0.038 ms
406-case corpus evaluation           19 ms per 250 cases
fit + measure + promote, 4 families  0.19 s
```

The bounded path is cheap enough that "don't spend model inference on what rules determine"
costs nothing to obey. That is a design constraint, not an accident: if the bounded rung were
expensive, the scheduler would be under pressure to skip it, and a scheduler under pressure is a
scheduler that reaches for the rung it has not measured.

**Next:** [Test Inventory](37-AR-223-TEST-INVENTORY.md) ·
[Performance](38-AR-223-PERFORMANCE.md)
