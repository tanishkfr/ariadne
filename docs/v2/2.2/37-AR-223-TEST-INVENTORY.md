# AR-223: Test Inventory

> **151 cases, 43 attacks, 30 mutations, and two named guarantees that must exist for this
> milestone to count as delivered.**

AR-222 watched a real test disappear while the suite reported green, and AR-222D built a named
inventory and a per-suite floor because of it. The same machinery is used here, with AR-223's
own entries added.

## The three suites

```text
test-ar223.py                  78 cases   the model, and the properties it must refuse
test-ar223-adversarial.py      43 cases   attacks against every guard above
test-ar223-mutations.py        30 cases   each rule removed in turn, suite must notice
```

All three are registered in `scripts/ar223-regression.py` — the two functional suites in the
FUNCTIONAL group, the mutation harness in the MUTATION group — and run strictly serially,
because a mutation harness edits engine source and any cleanliness-sensitive suite reading
that source at the same moment observes a tree that does not exist.

## Named guarantees

Added to `CRITICAL_CASES` in `scripts/harness/test_inventory.py`. Each must be findable by name
somewhere in `scripts/` or `src/`, and the adversarial suite is written to attack every one:

```text
acceptance-intelligence
    a claim is not evidence
    missing evidence is not failure
    acceptance state
    independent review
    re-verification

verified-intelligence
    confidence is not permission
    provider probability
    answer space
    false-confidence
    held-out
```

```python
missing = test_inventory.missing_critical_cases(set(), corpus=corpus_text([scripts, src]))
assert missing == {}
```

A guarantee that loses its phrase stops the gate, which is the failure mode the inventory
exists to catch.

## Recorded floors

```python
"scripts/test-ar223.py": 75,
"scripts/test-ar223-adversarial.py": 40,
"scripts/test-ar223-mutations.py": 25,
```

Floors, not targets. A count below its floor is a loss even when every named guarantee is
present, because a manifest cannot list every case that matters. A count can also fall from a
rename or a merge, which is why both nets exist and neither replaces the other.

Observed: 78, 43, 30. All above floor.

## How the functional suite is shaped

Most cases are refusals, because an engine that accepts everything is easy to write and tells
nobody anything. The shape is "this must be refused" or "this must abstain", and the cases
shaped as "this must succeed" exist to prove the refusal is specific rather than universal:

```text
corpus          no projection leaks across splits; no label is out of space; every label names
                a reviewer; every adjudicated label keeps both positions and the ruling;
                tuning on anything but development is reported unclean
evaluation      the real engine runs over every family; provider probability is never called
                calibrated; no accuracy over zero answers; nothing is authorised;
                the 2.1 collapse and flat-confidence patterns are detected, and a *pattern* is
                not reported as an error
calibration     thresholds fitted on development and measured elsewhere; the adversarial split
                never licenses; all six identity dimensions are named; a moved model revision,
                a moved corpus and a self-granted calibration each invalidate
promotion       a profile with enough cases is not enough to be acted on; a collapsing
                adversarial accuracy refuses; the real lifecycle stops where it must; a refused
                family is recorded rather than deleted; promotion without an evaluation raises;
                degradation suspends and the suspension has a reason
scheduling      a protected operation is HUMAN before any profile is read; a deterministic rule
                beats an active slice; a refused family escalates; a slice never widens its risk;
                an unmeasured revision is not answered; confidence cannot promote a level;
                asking for authority raises
proof pass      the Beacon mix is produced; it is NOT_ACCEPTED; the claim is CONTRADICTED; the
                repair is selective; the unaffected requirement is never re-checked; lineage
                keeps both passes
```

## The adversarial suite

43 attacks, each aimed at a specific guard and each required to be refused *for the stated
reason*. A pass on any refusal is not enough: an attack satisfied by the wrong refusal means the
guard it was testing is gone and something else caught it.

```text
THE CLAIM        injected instructions; a claim told to accept; a claim re-extracted to try to
                 acquire an evidence id; the engine as its own reviewer
THE EVIDENCE     an artifact whose bytes changed; evidence pointing at nothing; evidence about
                 a nonexistent requirement; a superseded row returning as current; freshness
                 taken from the row instead of recomputed
THE VERDICT      absent evidence read as failure; a human gate settled by evidence; an explicit
                 requirement made advisory; a contract silently rewritten
THE CORPUS       one projection in two splits; a label out of space; an unreviewed label; an
                 invented agreement level; an answer key inside a projection
THE PROMOTION    ACTIVE without ELIGIBLE; a slice with no pinned revision; an unvalidated scope;
                 a profile marked PROVEN by hand; an invented calibration method; one family's
                 profile handed to another; hidden degradation
THE SCHEDULER    a grant request; a protected operation with a 1.0 confidence; a widened scope
THE HISTORY      a rewritten AR-222 results document; the repair fixture reusing Beacon
```

Two real gaps were found this way rather than by reading: `corpus.case()` checked neither the
label nor the agreement level, and both are now refused at construction.

## The mutation suite

Thirty mutations, each removing one refusal and requiring the functional suite to notice.

```text
M01-M04   corpus: out-of-space label, unreviewed label, duplicate across splits, any agreement
M05-M07   evaluation: selective error unreported, collapse undetected, leaky corpus evaluated
M08-M10   calibration: threshold fitted on the measured split, stale profile served, floor removed
M11-M15   promotion: accuracy bound, confidently-wrong budget, adversarial floor, evaluation
          requirement, suspension
M16-M20   scheduler: protected operation, PROTECTED risk, deterministic bypass, scope widening,
          authority request
M21-M26   acceptance: human gate by evidence, absence as failure, superseded row current,
          invalidation skipped, UNKNOWN as unaffected, engine as reviewer
M27       calibration: the engine grants itself calibration
M28-M30   interruption: risky uncertainty proceeds, confidence lowers escalation, elevated
          consequence does not override a decisive reading
```

A surviving mutation is a failure to *investigate*, not a boundary to move. Three causes, and
the correct response to all three is the same: missing coverage, a broken mutation, or a wrong
assumption in the code. Weakening a mutation to make it die, or deleting the case that caught
it, destroys the only evidence that one of the three is true.

## A check that could not fire

Found while writing the AR-223 harness, in AR-222D's:

```python
with mutation_ledger.mutation_transaction(...) as opened:
    path.write_text(mutated, encoding="utf-8")
    passed, output = run_suite()
    ledger_report = dict(opened)          # <- read before the ledger writes restoration
```

The ledger populates `report["restoration"]` in its own `finally`, *after* the yield. Reading it
inside the block always found nothing, so `HARNESS RESTORATION NOT PROVEN` never printed and
the per-mutation restoration proof had never actually run. Fixed in both harnesses, with the
reason recorded at the fix.

This is worth more than the two lines it took. A check that cannot fire is indistinguishable
from a check that is satisfied, and that is precisely the failure AR-222D was built to end —
found in the harness built to catch it, one milestone later.

## Running everything

```text
python scripts/test-ar223.py
python scripts/test-ar223-adversarial.py
python scripts/test-ar223-mutations.py

python scripts/ar223-regression.py --suite test-ar223 --suite test-ar223-adversarial
python scripts/ar223-regression.py --group mutation          # every mutation harness, serial
python scripts/check.py                                       # whole repository
```

## Coverage, honestly

Not measured. There is no line-coverage number in this milestone and there should not be one:
AR-222D's findings were that coverage percentages were uninformative and that *named* guarantees
plus *recorded floors* were what actually caught losses. What is measured here is that 30
specific removals of behaviour are each noticed.

**Next:** [Performance](38-AR-223-PERFORMANCE.md) ·
[Closure Report](39-AR-223-CLOSURE-REPORT.md)
