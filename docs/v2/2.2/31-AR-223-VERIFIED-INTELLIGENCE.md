# AR-223: Verified Intelligence

> **A bounded engine that has not been measured may not answer. A bounded engine that has been
> measured badly may not answer either. And no measurement of any engine may grant permission.**

AR-206 built the Native Decision Runtime, its profiles, its calibration machinery and its
adoption lifecycle. What it could not do was show the reference engine was *good*, because
nothing in this repository had ever measured it against reviewed labels. AR-223 does that
measurement, and then draws the small amount of policy that follows from it.

## The two halves

```text
ACCEPTANCE                      what is established about this work?
  contract  requirements  claims  evidence  decisions  gates
        |
        |  bounded advice, which may inform and can never promote
        v
VERIFIED INTELLIGENCE            what has been measured, and what may therefore answer?
  corpus  evaluation  calibration  promotion  scheduler
```

The two meet in one place and the boundary is enforced, not documented.

## The six modules

`corpus`
    The splits, the leakage guards, and what a corpus must declare before it may be scored.
`corpus_data`
    Several hundred reviewed labels, with reviewers, second reviews, and kept disagreements.
`evaluation`
    The real seeded engine over the real corpus, per family, with the 2.1 pathology looked for
    by name.
`calibration`
    Thresholds and temperatures fitted on development only, bound to an identity that
    invalidates them when any dimension moves.
`promotion`
    Measured merit as the second gate to authority, and the only automatic removal of it.
`scheduler`
    The cheapest intelligence that has earned enough quality for this decision, and nothing
    above it.

## The metric that matters

Plain accuracy is the wrong headline, because an engine that abstains on everything has perfect
selective error and answers nothing. So every family reports, side by side:

```text
accuracy                  correct / answered
coverage                  answered / cases
abstention_rate           abstained / cases
selective_error_rate      wrong / answered
ece, brier                how far the confidence is from reality
high_confidence_errors    answered at >= 0.8 and wrong
latency p50, p95          local wall clock, which is a property of this machine
```

The one to read first is `selective_error_rate`, because it is the number that bounds harm. An
engine at 92% accuracy answering everything is a different risk from an engine at 92% accuracy
that abstains on the 8% it cannot see.

`METRICS` returns `None` rather than a convenient zero wherever a metric is undefined. Latency
without cases, ECE without a probability for the answered set, accuracy without ground truth —
each is `None`, because a zero there is indistinguishable from a good result.

## The 2.1 pathology, looked for directly

2.1 shipped a milestone that looked finished. Different inputs received the same classification
at the same confidence. That failure is invisible in an average and obvious in a collision
count, so it is counted directly:

```text
distinct_labels             how many different truths were in the batch
distinct_answers            how many answers the engine gave
answer_collapse             one answer covered three or more different truths
confidence_spread           max confidence - min confidence across the batch
confidence_flat             that spread <= 0.02 across three or more different truths
high_confidence_errors      answered at >= 0.8 and wrong
```

`answer_collapse` and `confidence_flat` are *patterns*, not errors; `high_confidence_errors` is
the only one of the three that is a mistake. The output says so in its own `note` field,
because a detector that called every uniform answer a failure would be ignored within a week.

## Fitting, and the line between fitted and measured

```text
threshold    fitted on DEVELOPMENT, reported on HELD_OUT + REAL_WORLD
temperature  fitted on DEVELOPMENT, reported as before -> after ECE
quality      measured out-of-sample, never on the rows the fit saw
```

`ADVERSARIAL` is excluded from the measured splits on purpose. It is deliberately
unrepresentative, and a corpus that let a stress set license production authority would be
measuring its own construction. Its findings are reported; it grants nothing.

The temperature fit is a grid over eight values, chosen because it is reproducible and cannot
quietly converge on something extreme. `1.0` is always in the grid so the fit can report that
no temperature beat not calibrating. A temperature rescales a distribution; it cannot separate
cases the engine cannot already separate, and the output says that too.

## The six-dimensional identity

A calibration profile is bound to:

```text
runtime    implementation_revision    model_revision
question_schema_digest    decision_definition_digest    corpus_revision
```

If any one moves, the profile does not degrade into the new world — it stops applying.
`stale_reasons` names each dimension that moved, because "calibration is stale" is
unfalsifiable and "the model revision moved from X to Y" is a sentence somebody can fix.

`calibration_self_granted` is refused on sight. A runtime reports `PROVIDER_PROBABILITY` and
may not describe its own output as calibrated.

## Measured merit as the second gate

AR-206 sets `PROVEN` from evidence *volume*: the dataset was big enough and a method really
ran. That is a statement about evidence, not merit — a profile over seventy cases of a
31%-accurate classifier is thoroughly measured and completely undeserving.

`promotion.POLICY` is the second gate, with a stated bound and a stated reason for each:

| Bound | Value | Why |
| --- | --- | --- |
| `min_accuracy` | 0.90 | a classifier that cannot name the class nine times in ten should escalate |
| `max_ece` | 0.10 | provider probability off by more than a tenth is not calibrated confidence |
| `max_selective_error_rate` | 0.10 | the same bound on the errors among what it chose to answer |
| `min_coverage` | 0.40 | below that the bounded path is ceremony and escalation is the honest one |
| `max_high_confidence_errors` | 0 | confidently wrong is the failure a bounded authority cannot absorb |
| `min_adversarial_accuracy` | 0.60 | authority has to survive the cases written to break it |
| `min_measured_cases` | 50 | a small measurement is an anecdote with a decimal point |

`assess` returns *every* failing reason rather than the first. A gate that stops explaining
after the first objection gets that objection relaxed.

Promotion walks the **real** AR-206 lifecycle — `UNTESTED -> SHADOW -> EVALUATED -> ELIGIBLE ->
ACTIVE` — through `decisions.runtime.promotion`, so every status change is an adoption event
with a reason and an evaluation id. `ACTIVE` is reachable only from `ELIGIBLE`, and a promotion
with nothing to cite is refused. A refused family is recorded at `EVALUATED` with its reasons:
*we measured it and it was not good enough* is a finding, and deleting it would lose the only
honest thing this milestone produced.

## Removal

`enforce_health` compares a new run against the baseline a slice was promoted on, using the same
policy numbers read in the same direction, and **suspends** the `ACTIVE` slice when quality has
degraded. Unconditional by design: if the evidence degrades, stopping must not require passing
a condition. Reversible by re-promotion under the same policy, and recorded as an adoption
event like every other status change.

## Scheduling

```text
protected operation, or PROTECTED risk      -> HUMAN        (before any profile is read)
a deterministic rule resolves it           -> DETERMINISTIC
an ACTIVE slice covers this scope           -> BOUNDED_LOCAL
everything else                             -> GENERATIVE
```

Deterministic first, always: spending model inference on a question a table already answers is
pure cost whatever the model's quality. Scope matching only ever narrows, so a slice proven for
`LOW` risk cannot answer a `HIGH` request however brilliant it is at it, and a slice measured
under one model revision cannot serve another.

The scheduler cannot grant authority, and that is enforced rather than documented. A request to
treat a probability as a permission raises `ContractError`, because a boolean somebody might
ignore is a weaker guarantee than an exception nobody can route around. Every record it writes
carries `authorization_effect: none` and `confidence_grants_nothing: true`.

## What a reader should distrust here

The promotion policy was authored alongside the work it judges. Two families pass and two fail,
and it would be convenient to conclude the bounds were chosen to produce that split. The bounds
are argued individually above and the arguments do not reference the outcome — but a reader who
wants to check that can move one number in `POLICY` and re-run `promotion.run_and_promote`, and
the honest answer is that this is a declared judgement with stated reasons rather than a
discovered fact.

The corpus is authored and reviewed, not scraped production traffic, because this repository has
none to scrape. The `REAL_WORLD` split is real documented history and real executed scenarios,
and it is small. Document
[32-AR-223-LABELLED-CORPUS.md](32-AR-223-LABELLED-CORPUS.md) is explicit about which rows
claim what.

**Next:** [LabelLED Corpus](32-AR-223-LABELLED-CORPUS.md) ·
[Measured Intelligence](33-AR-223-MEASURED-INTELLIGENCE.md)
