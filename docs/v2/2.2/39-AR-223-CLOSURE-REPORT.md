# AR-223: Closure Report

> **A milestone closes when its promises are met, its failures are recorded, and somebody
> reading later can tell which was which.**

## What was promised, and what is delivered

AR-223 asked two questions and made a specific set of promises. Each is answered with what
exists, not with an intention.

### Acceptance intelligence

| Promise | Delivered |
| --- | --- |
| six verdicts with defined semantics | `acceptance/decisions.py`, all six, each with a named derivation |
| a contract bound to its source, versioned, not retroactively rewritten | `acceptance/contract.py`; a revision requires a material-change reason |
| requirements with per-requirement evidence policies | `acceptance/requirements.py`; derived from kind, overridable |
| claims that are never evidence | `acceptance/claims.py`; a claim is assessed against verdicts and can be `CONTRADICTED` |
| evidence with provenance and recomputed freshness | `acceptance/evidence.py`; freshness is derived, never read from the row |
| one gate, clause-by-clause | `acceptance/gates.py`; seven clauses, each reporting its own verdict |
| selective re-verification | `acceptance/invalidation.py`; `PROVEN_UNAFFECTED` by declared fingerprint |
| independent review, refused structurally | `acceptance/security.py`; three refusals including the engine |

### Verified intelligence

| Promise | Delivered |
| --- | --- |
| a reviewed corpus | 406 cases, four families, four splits, every label with a reviewer |
| leakage guards | by projection digest, not case id; caught 3 real duplicates |
| the real engine measured | per family, on held-out and real-world splits, at development-fitted thresholds |
| the 2.1 pathology looked for | answer collapse, flat confidence, confident errors, counted directly |
| calibration bound to an identity | six dimensions; any movement invalidates |
| promotion on measured merit | real AR-206 lifecycle; 2 of 4 families `ACTIVE` |
| automatic removal | `enforce_health` suspends on measured degradation |
| cheapest sufficient intelligence | deterministic, then a proven slice in scope, then escalation |
| confidence never permission | `ContractError` on request; every record `authorization_effect: none` |

### The slices

| Promise | Delivered |
| --- | --- |
| a real proof pass over preserved history | Beacon, from `20-AR-222-RESULTS.md`, `NOT_ACCEPTED` |
| `FAILED` → repair → `PROVEN` | repair slice, separate fixture, `ACCEPTED`, selective |
| history not falsified | the results document is read-only and marker-checked |

## The three answers, stated plainly

**Which parts of a claimed completion are established?** For Beacon: three of six, with one
`FAILED`, one `UNPROVEN` because nobody looked, and one `NEEDS_HUMAN` because the requirement is
subjective. A fixture-supplied worker claim of completion is `CONTRADICTED` by the measurement
that already existed.

**Does the bounded engine deserve its authority?** Two of four families. `REVIEW_ESCALATION` and
`ROUTE_FAMILY` answer at 1.000 accuracy with zero selective error and zero confident errors.
`FAILURE_CLASSIFICATION` answers at 0.314 and `EVIDENCE_RELEVANCE` at 0.339, and both were
refused with named reasons and recorded at `EVALUATED` rather than deleted.

**Is confidence permission?** No, and the milestone spends more code proving it than proving the
opposite.

## What went wrong along the way

Three real defects, all found by running rather than reading:

1. **`test-ar222d-mutations.py` had a restoration check that could never fire.** It read
   `report["restoration"]` inside the `with` block, before the ledger's `finally` wrote it, so the
   per-mutation restoration proof had never run. Fixed in both harnesses.

2. **The corpus builder validated neither the answer space nor the agreement vocabulary.** Found
   by the adversarial suite rather than by reading it. A mislabelled row, or one claiming an
   agreement level that does not exist, could have entered through the front door. Both are
   refused at construction now.

3. **The AR-223 interruption classification treated every `CONDITIONAL` one way**, so "the icon
   set is a coin flip" and "this might reword the onboarding copy" were treated alike. The second
   is a meaning change. `risk_sensitive_tier` now escalates the second and proceeds on the
   first.

## What was not done

- No frontier model was evaluated. Every number is the seeded naive-Bayes reference.
- The corpus is authored and reviewed, not production traffic; `REAL_WORLD` is 98 of 406 rows.
- No latency under concurrency or on other hardware.
- The promotion policy's bounds are a declared judgement, authored alongside the work they judge.
- No gate, grant, release, or protected acceptance. `authorization_effect` is `none` everywhere.

## State of the repository

```text
VERSION                       2.1.0        unchanged
default branch                main          unchanged
Boreal                        untouched
AR-223 suites                 78 / 43 / 30  all green
ar223-regression.py           3 groups, strictly serial
named guarantees              10 in 2 new groups
recorded floors               75 / 40 / 25
mutation ledger               inactive, no entries
```

## The sentence this milestone leaves behind

> An engine that has not been measured may not answer. An engine that has been measured badly may
> not answer either. A claim is not evidence, an absence is not a failure, and a confidence is
> not a permission — and the only acceptable way to hold any of those is to make the engine
> refuse.

**Next milestone:** the two refused families, or the humans those refusals are waiting on.
