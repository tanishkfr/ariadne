# Evaluation and comparability

The failure this exists to prevent is quiet. Two reports of different datasets,
different question schemas and different model revisions produce perfectly
well-formed arithmetic, and a delta between them looks exactly like an improvement.
Printing that delta would be inventing evidence.

So every report binds an identity, and every comparison checks it. **The refusal is
the feature.**

## The identity keys

`EVALUATION_COMPARABILITY_KEYS` (mirrored as `evaluation.EVALUATION_IDENTITY_KEYS`):

```
dataset_digest
question_schema_digest
decision_definition_digest
runtime_version
implementation_revision
model_revision
```

Every report's `identity` block carries all six, plus four fields that are recorded
but **not** compared:

| Field | Compared | What it pins |
|---|---|---|
| `dataset_digest` | yes | the dataset bytes, not its path |
| `question_schema_digest` | yes | the shape of what was asked |
| `decision_definition_digest` | yes | the shape plus the wording |
| `runtime_version` | yes | which runtime answered |
| `implementation_revision` | yes | which engine code answered |
| `model_revision` | yes | which checkpoint answered |
| `calibration_profile_id` | no | which profile was applied |
| `threshold_policy_version` | no | which threshold policy was applied |

The last two are recorded so the report is reproducible and so the *gap* between
two reports on them is visible in the reports themselves. They are deliberately
not comparison keys: a run measured with a different calibration profile is still
the same experiment if the six keys match, and refusing on the seventh would
teach everyone to bypass the gate. Note the asymmetry with `profile_for`, where
the calibration profile *must* match for a probability to be relabelled - there
the point is to prevent a claim, here the point is to prevent a false delta.

## The dataset digest

`evaluation.dataset_digest(records)` canonicalises each row with sorted keys,
sorts the canonical strings, and hashes the joined result.

**Order-independent, on purpose.** Shuffling a dataset does not change what it
contains. Refusing to compare two shuffled runs of the same data would train
everyone to ignore the gate, and a gate that is routinely ignored is not a gate.
The suite asserts
`dataset_digest(records) == dataset_digest(list(reversed(records)))`.

The digest is of the rows themselves - `{"case_id", "expected", "projection"}` -
not of a path. Two datasets share a path across a rebase, a CI cache or a
colleague's checkout.

## The metrics

`evaluation.evaluate(records, rows=rows, ...)` takes cases
(`{"case_id", "expected", "projection"}`) and the runtime's answers for the same
cases (`rows`, matched by `case_id`). It reports:

| Metric | Definition | `None` when |
|---|---|---|
| `accuracy` | `correct / grounded` | no case had both an answer and an expected label |
| `coverage` | `answered / cases` | there were no cases |
| `abstention_rate` | `abstained / cases` | there were no cases |
| `failure_rate` | `failed / cases` | there were no cases |
| `ece` | expected calibration error over 15 equal-width bins | nothing bin-able |
| `ece_bins` | 15 (`DEFAULT_ECE_BINS`) | never |
| `brier` | multi-class Brier over the observed distributions | no case had a distribution |
| `latency_p50_ms`, `latency_p95_ms` | nearest-rank percentiles of the per-row `latency_ms` | no latency was recorded |

`confusion` sits beside that block rather than inside it:
`{expected: {predicted: count}}`, empty unless something was both answered and
labelled.

Plus `totals` (`cases`, `answered`, `abstained`, `failed`, `ground_truth`,
`correct`), a per-case `cases` list, `elapsed_ms`, `measured_on_this_machine: True`,
a `limitations` list, and `authorization_effect: "none"`.

### Unknown stays unknown

Every metric that cannot be measured is `None`, never `0.0`. This is not
fastidiousness: a zero error on an empty set is a claim about quality, and there is
none. `ece()` returns `None` when there is nothing to bin. `brier_over()` returns
`None` when nothing was scored. `accuracy` is `None` when no case had ground truth.

Two consequences the suite pins:

- **A case with no expected label contributes to nothing.** It counts in
  `cases`, in `coverage`, in `abstention_rate` and in latency - and not in
  `ground_truth`, `correct` or `accuracy`. It is never scored as a loss.
- **A case with no answer counts against coverage, not against accuracy.** A run
  in which every case errored has `accuracy: None` and `answered: 0`, and therefore
  cannot pass a gate by having nothing left to compare.

### ECE and the bin count

`DEFAULT_ECE_BINS = 15`. The value is recorded in the report (`ece_bins`) so two
reports using different bin counts are visibly different experiments rather than
silently different measurements. The final bin includes `c == 1.0`.

### Latency percentiles

`_percentile` is nearest-rank, not interpolated:
`rank = (p * n + 99) // 100`, then the value at index `rank - 1`, clamped into
range, rounded to three places. An interpolated p95 of five samples invents a
measurement that was not taken, and a performance claim should not be able to do
that.

Latency is local wall-clock for one run on one machine, and the report says so in
its `limitations`. `assert_regression` therefore takes an explicit tolerance per
metric, and the suite asserts that a 0.0001 ms tolerance on `latency_p50_ms` does
not fail a comparison of a report with itself - otherwise every quality gate would
fail on a quiet machine.

## Where the metrics live in the report

`evaluate()` returns a document whose shape is worth knowing before you write a
script against it:

```
schema_version, evaluation_id, evaluation_version, recorded_at
identity      the eight identity fields
metrics       accuracy, coverage, abstention_rate, failure_rate, ece,
              ece_bins, brier, latency_p50_ms, latency_p95_ms
totals        cases, answered, abstained, failed, ground_truth, correct
confusion     {expected: {predicted: count}}
cases         the per-case list
elapsed_ms, measured_on_this_machine
limitations   the three statements below
authorization_effect  "none"
```

`limitations` reads, verbatim: "accuracy, ECE and Brier are reported only where
explicit ground truth exists"; "latency is local wall-clock for this run and
depends on the machine"; "an evaluation report is evidence about a run, never an
authorisation".

## The refusal rules

`comparable_to(baseline, candidate, keys=...)` returns `(ok, reasons)`. Every
reason names the key, what it means, and both values:

```
dataset bytes (dataset_digest): baseline is <a>, this run is <b>
model revision (model_revision): baseline is <a>, this run is <b>
```

`compare(baseline, candidate)` returns:

```
comparable        bool
reasons           the named causes, or []
deltas            {metric: {baseline, candidate, delta, improved}}
missing_metrics   metrics the baseline reports and the candidate does not
note              the refusal, in words
```

`_improved` knows the direction of each metric: `LOWER_IS_BETTER = ("ece",
"brier", "abstention_rate", "failure_rate", "latency_p50_ms", "latency_p95_ms")`,
higher is better for `accuracy` and `coverage`, and an **unknown metric is
reported, not scored** - `improved` is `False` rather than a guess about which way
is up. A new metric does not silently become a regression or a success.

### Missing metrics

Two different ways to stop measuring are caught, and both are reported rather
than treated as "no change".

**The key is gone.** A metric the baseline reports and the candidate does not
appear in `missing_metrics` - reported as missing, not as unchanged.
`assert_regression` turns that into a failure. This closes the most comfortable
escape from a gate: stop emitting the inconvenient number.

**The key is present but empty.** A metric whose baseline value is a number and
whose candidate value is `None` is *also* added to `missing_metrics`, with the
delta recorded as `delta: None`, `improved: False` and the note "the candidate
stopped reporting this metric, so the change is unknown". This is the subtler
version of the same escape: a run that answers everything and reports no
confidence has an `ece` and a `brier` of `None`, and treating those as merely
"not comparable on this metric" would let a calibration regression pass the gate
with nothing measured.

### A key absent on either side is unknown, not a conflict

If a single key is `None` on either side, `comparable_to` skips it. Reports written
before an identity key existed stay comparable to themselves rather than refusing
everything, which would also train everyone to ignore the gate. The cost of that
choice is honest: a comparison across two reports that both omit a key cannot
detect a difference in it. `UNKNOWN` is not the same as `equal`.

**But an absent identity block is a refusal.** Skipping missing *keys* is right
when two identified runs differ on which fields they carry; it is not right when
the whole block is absent, because that is the shape of "someone passed two
arbitrary dicts". So `comparable_to` returns immediately with:

> <the baseline / the candidate / neither report> carries no experiment identity,
> so this is not a comparison of the same experiment; run the evaluation rather
> than assembling a report by hand

A hand-assembled report cannot be compared to anything, including itself.

### The gate

`assert_regression(baseline, candidate, tolerances=None)`:

- raises `AssertionError` immediately if the baseline is not comparable, with
  "not comparable" and the reasons - it refuses to gate a run it cannot compare;
- otherwise fails on any shared metric that regressed beyond an explicit
  tolerance, or that did not improve and did not stay equal;
- fails on any `missing_metrics`.

The suite asserts a changed dataset, a reworded question and a changed model
revision all refuse; that two runs of the same experiment - records reversed - are
comparable; that a genuine accuracy regression inside a comparable identity is
measurable and fails; and that the latency tolerance prevents a timing-noise
failure.

## What the CLI reads

The `eval` action reads the identity from the runtime that **actually loaded**
rather than from anything typed by the operator:

```python
observed = session.status()
...
runtime_version=str(document.get("runtime_version", "") or observed.get("runtime_version", "")),
implementation_revision=str(document.get("implementation_revision", "") or observed.get("implementation_revision", "")),
model_revision=str(document.get("model_revision", "") or observed.get("model_revision", "")),
```

A hand-entered revision that disagrees with what loaded is precisely the mistake
the comparability gate exists to catch, and inviting the operator to type one would
be asking them to defeat the check. The document may supply overrides; the default
is what loaded.

The input is a JSON file, either a bare list of cases or an object with `records`,
optional `questions`, optional `rows` (the runtime's answers for those cases) and
optional identity overrides. `--baseline` takes a previous report and adds a
`comparison` block. When the comparison is refused the action prints
`comparability  : REFUSED` with each reason and **exits 2**; without a baseline it
exits 0.

One thing the `eval` action does not do: run the runtime over the cases for you.
It scores `rows` you supply. Scoring the engine on its own dataset is the
exercise of a test suite, not of an evaluation - an evaluation whose answers were
produced by the same process that produced the baseline has one less independent
thing in it.

## The report is not an authorisation

Every evaluation report carries `authorization_effect: "none"` and states its own
limits in `limitations`, including "an evaluation report is evidence about a run,
never an authorisation". The `eval` action emits a
`decision_runtime_completed` engine event carrying the evaluation id and whether
the comparison was comparable, so the act of measuring is itself in the record.

## Export, and where the loop stops

`export.collect(state, definition=...)` turns reviewed shadow records into a
bounded dataset. Only records carrying ground truth with a named source are
exported by default; `require_ground_truth=False` is an explicit opt-in. Each row
carries the question identity, the projection digest, the prediction, the reviewed
outcome, the ground-truth source, the agreement, the confidence with its kind and
the model revision - so a fitted weight file can be checked against the question it
was fitted for rather than applied by name.

`export.write` refuses an empty dataset: "an empty file invites a pipeline to
train on nothing and report success".

And then it stops. Writing the dataset fits nothing. Ariadne 2.1 has no
self-training path at all, and the reason is written into the module: a system that
retrains on its own decisions closes a feedback loop in which the only thing that
gets better is agreement with itself. The suite asserts the runtime package ships
no trainer and that only `seeds.py` writes a weight file.

The loop, with its deliberate gaps:

```
shadow records -> reviewed outcomes -> export a bounded dataset
                                           -> (separately authorised) fit
                                           -> evaluate -> shadow again
```
