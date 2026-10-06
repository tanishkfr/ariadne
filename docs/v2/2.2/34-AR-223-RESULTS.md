# AR-223: Results

> **What this milestone established, and what it did not.** Both halves, with the failures given
> the same space as the successes.

## What was asked, and what was delivered

AR-223 asked two questions.

**Acceptance intelligence** — which parts of a worker's claimed completion are actually
established by the evidence that exists right now?

**Verified intelligence** — prove that the bounded reference engine deserves the authority the
2.1 runtime gave it by construction.

| Deliverable | State |
| --- | --- |
| Acceptance model: contract, requirements, claims, evidence, six verdicts, gate | shipped |
| Selective invalidation with `PROVEN_UNAFFECTED` by dependency fingerprint | shipped |
| Real proof pass over preserved AR-222 history | shipped, `NOT_ACCEPTED` |
| Repair → stale → targeted re-verification → `ACCEPTED` slice | shipped |
| 406-case reviewed corpus in four splits with provenance | shipped |
| Evaluation of the real seeded engine, per family | shipped |
| Calibration fitted on development, bound to a six-way identity | shipped |
| Evidence-backed promotion through the real AR-206 lifecycle | shipped, 2 of 4 families |
| Risk-aware intelligence scheduler | shipped |
| Confidence-never-permission enforcement | shipped, tested by 43 attacks |

## The two headline findings

**1. Half the runtime's families do not deserve the authority 2.1 gave them.**

```
promoted   REVIEW_ESCALATION (accuracy 1.000, selective error 0.000)
           ROUTE_FAMILY      (accuracy 1.000, selective error 0.000)

refused    FAILURE_CLASSIFICATION  (accuracy 0.314, 2 confidently wrong answers)
           EVIDENCE_RELEVANCE     (accuracy 0.339, adversarial accuracy 0.143)
```

2.1 gave every family a profile and a promotion path because nothing had ever measured them.
AR-223 measured them, and half of them cannot answer. The runtime worked; the assumption that
"it runs, therefore it may answer" did not.

**2. The Beacon fixture is still not accepted, and now that is a computed result rather than a
remembered one.**

## The Beacon slice, over real history

`scripts/ar223-beacon.py` reads `docs/v2/2.2/20-AR-222-RESULTS.md`, checks that the phrases it
depends on are still there, and decides six requirements from the evidence that document
records:

```
PROVEN        the Beacon surface renders at the default viewport and the capture is bound to
              the observed work digest
PROVEN        the project typechecks and builds
PROVEN        the project's own test suite passes
FAILED        the log table does not clip or overflow below 768px
UNPROVEN      the navigation is reachable and dismissible with the keyboard alone
NEEDS_HUMAN   the heading hierarchy reads coherently to a human reviewer
CONTRADICTED  claim by ar221-implementer: "The responsive layout is fixed: the log table no
              longer clips below 768px."

state         NOT_ACCEPTED
```

Four things worth reading twice:

The **FAILED** verdict is the 568px-at-390px measurement, which the AR-222 results document
preserves verbatim. Nothing here improves it, and the document is not edited.

The **UNPROVEN** verdict is the important one. History holds a build result and screenshots for
keyboard behaviour and nothing else. No observation of a violation exists. Reporting failure
would be a lie with a decimal point.

The **CONTRADICTED** claim is a controlled fixture, and says so on its face:
`source_label="controlled fixture claim: AR-222 recorded no such claim"`. AR-222 recorded
"Visual acceptance NOT_CLAIMED; human acceptance NOT_GRANTED" about itself. The fixture supplies
the claim a real worker might have made, so the engine can be seen contradicting it.

The **NEEDS_HUMAN** verdict exists because AR-222 states its own critique does not judge
hierarchy, density or composition. The engine agrees with its predecessor about the limits.

The work digest is the sha256 of the results document itself, so editing the history changes the
digest and every evidence row stops being current rather than quietly continuing to support a
verdict.

## The repair slice, on a separate fixture

AR-222's own repair improved its defect from 12 clipped elements to 5 and did not eliminate it.
That is the honest ending and it is not a demonstration of `FAILED -> PROVEN`. So the
demonstration runs on a separate, labelled fixture:

```
pass 1   FAILED  the sidebar collapses below 900px
         PROVEN  the parser still accepts a bare list argument
         -> NOT_ACCEPTED

edit     src/components/Sidebar.tsx changes; the work digest moves
         4b19c0a7e52d3f68 -> 9c05ae31d74b8620

invalidation
         POTENTIALLY_AFFECTED  the sidebar (its scope matched the change)
         PROVEN_UNAFFECTED     the parser (its declared fingerprint did not move)

plan     1 targeted check, cost 1, instead of re-running all evidence
         the parser check is NOT selected again

pass 2   PROVEN  the sidebar collapses below 900px
         PROVEN  the parser still accepts a bare list argument
         -> ACCEPTED

lineage  FAILED -> PROVEN, both passes readable
```

The parser's pass-one evidence is readmitted at the new work digest on the strength of a
declared dependency fingerprint, and the pass record names the row that was admitted:

```
admitted_by_dependency_proof  ['evd_20261005T150235Z_…']
unaffected_requirements       ['rqm_20261005T150235Z_…']
```

Without that, a requirement whose file did not change would have been re-checked for no reason,
and a repair demonstration that re-runs everything proves nothing about context economics.

And the inverse: a requirement that declares *nothing* comes back `UNKNOWN`, not
"probably fine". That case is in the suite, because it is the one that would let unrelated work
skip re-verification indefinitely.

## Test results

```
test-ar223.py                  78/78 passed
test-ar223-adversarial.py      43/43 passed
test-ar223-mutations.py        30/30 mutations caught
```

Thirty mutations across eight categories: corpus validation, evaluation honesty, calibration
fitting, promotion gates, scheduler ordering, acceptance verdicts, and the interruption
classification. Each removes one refusal and requires the suite to notice.

## Defects this milestone found in existing code

**A restoration check in `test-ar222d-mutations.py` that could never fire.** The harness read
`report["restoration"]` from inside the `with` block, where the ledger has not yet written it,
so `HARNESS RESTORATION NOT PROVEN` never appeared and the check had been reporting nothing.
Fixed there and corrected in the new harness. A check that cannot fire is indistinguishable from
a check that is satisfied — the same failure AR-222D was built to end, found in the harness that
was built to catch it.

**`corpus.case()` checked neither the label nor the agreement level.** Found by the adversarial
suite, not by reading. A mislabelled row, or one claiming `EVERYONE_ AGREED`, could have entered
the corpus through the front door. Both are refused at build time now.

**`interruption.classify` treated every `CONDITIONAL` one way.** AR-222D's lexical classifier
returned `CONDITIONAL` for both "the icon set for the empty state is a coin flip" and "this
might reword the onboarding copy", and AR-223 added `risk_sensitive_tier`, which escalates the
second and proceeds on the first. The second is the same class of consequence as changing the
brand.

## What was not done

**No frontier model was evaluated.** Every number is the seeded naive-Bayes reference engine. A
language model would score differently and the promotion decisions would change.

**The corpus is not production traffic.** It is authored and reviewed, because this repository
has no production traffic. `REAL_WORLD` is 98 of 406 rows and is the only split that claims to
describe anything that happened.

**No latency under load, and no concurrency measurement.**

**The promotion policy's bounds are a declared judgement**, authored alongside the work they
judge. Two families pass and two fail; the reasoning for each bound is in
[Verified Intelligence](31-AR-223-VERIFIED-INTELLIGENCE.md) and none of it references the
outcome, but a reader who wants to check can move one number in `POLICY` and re-run.

**No gate, grant, release or protected acceptance was performed.** `authorization_effect` is
`none` on every record written by this milestone.

## The invariant, stated once

> A claim is not evidence. Missing evidence is not failure. A confidence is not a permission.
> An unmeasured engine may not answer; a badly-measured one may not either.

Everything in this milestone is an attempt to make those four sentences mechanical rather than
aspirational, and the tests are mostly shaped as "this must be refused", because an engine that
refuses nothing tells nobody anything.

**Next:** [Security and Anti-Gaming](35-AR-223-SECURITY-AND-ANTI-GAMING.md) ·
[Architecture and Integration](36-AR-223-ARCHITECTURE-AND-INTEGRATION.md)
