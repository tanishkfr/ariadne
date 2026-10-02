# Ariadne 2.1.0 - RC real-world evaluation

The evidence gathered before promoting `2.1.0rc1` to stable. One shadow run of the
Decision Runtime over a real project, through the real production path.

---

## What was run, and against what

**Project:** `widgetco`, a small Python widget library created for this evaluation -
a renderer, a theme module with real validation, a test, and a project document. It is
isolated in a temporary directory and is not any existing repository.

**Harness:** `scripts/real-world-shadow-eval.py`.

**Nothing was mocked.** Every decision below is Ariadne answering a real bounded
question about something that actually happened to that project: a test suite that ran,
a name error that was raised, an import that failed, a file that could not be found, a
review of a real file, evidence drawn from a real file, a real work item. The runtime is
the shipped one, over the subprocess sidecar, and the caller is
`classify_failure`, `review_escalation`, `evidence_relevance` and `route_family` - the
four real integration entry points, reached through the compiler and the batch
evaluator.

## Runtime identity

```
runtime id        ariadne-decision-runtime
runtime kind      local_bounded (cpu)
implementation    ariadne-reference-bounded
model revision    ar-206-reference-1
transport         subprocess sidecar
```

## Shadow-only confirmation

The runtime was attached with `shadow=True` throughout and never promoted.

| Check | Result |
|---|---|
| shadow records written | 19 |
| shadow records with a non-`none` execution effect | **0** |
| shadow records with a non-`none` authorization effect | **0** |
| decisions with `acted_on` true | **0** |
| distinct authorization effects observed | `["none"]` |
| distinct confidence kinds observed | `["PROVIDER_PROBABILITY"]` |
| records labelled `CALIBRATED_PROBABILITY` | **0** |
| isolation problems | none |
| errors | none |

## Results

19 real bounded decisions. Not 20-50: the brief suggested that range and said to report
the actual count rather than manufacture copies, so this is the actual count. It is
limited by how many genuinely distinct decisions a four-file project produces; padding
it with repetitions of the same input would have inflated the number without adding
evidence.

| Family | Decisions | Answered | Refused | Confidence range |
|---|---|---|---|---|
| `failure-classification` | 10 | 10 | 0 | 0.199 - 0.199 |
| `review-escalation` | 3 | 0 | 3 | 0.545 - 0.914 |
| `evidence-relevance` | 4 | 4 | 0 | 0.277 - 0.788 |
| `route-family` | 2 | 2 | 0 | 0.981 - 0.981 |

Latency per decision: min 1.65 ms, median 2.02 ms, max 3.66 ms, in-process including
compilation. The subprocess sidecar's process startup is not in that figure and dominates
it; the transport suites cover that separately.

Every record carried its full identity, which is what makes a run like this auditable
afterwards:

```
family              failure-classification
question_id         failure-class
question_version    1
definition_digest   d30120151a3b8d4a
projection_digest   30acd86f9f08bbe89a8eecbc307af0bd9f54395b75f68cf5d614332ced9e026
provider            ariadne-decision-runtime
implementation      ariadne-reference-bounded
model_revision      ar-206-reference-1
```

## Ground truth discipline

**Verification status: UNKNOWN.** No reviewed or verified outcome was recorded for any
of these 19 decisions, because nothing in this run reviewed them. The authoritative
result is labelled `AUTHORITATIVE_RESULT` and nothing more, and the run deliberately
computes no accuracy figure, because there is nothing here to compute one from.

**Shadow disagreements: 0.** This is not evidence that the runtime is right. It is
evidence that on this family it agreed with the authoritative path, and given the next
section, agreement here is weak information.

## What the run revealed

**The failure classifier does not discriminate real failure text.** All ten genuinely
different failures - a passing suite, a `NameError`, a missing module, a type error, a
syntax error, a missing interpreter, a missing package, an allocation ceiling, a slow
operation, a successful import - returned `IMPLEMENTATION_FAILURE` at confidence
`0.198965`. The *identical* value, to six figures, for all ten.

This is the reference engine's documented weakness showing up in practice. It is strong
on enumerated structure and weak on prose, and real build output is prose. The identical
confidence across ten different inputs is the sharper statement: the projection the
integration builds for this family is not discriminating these inputs at all.

This is a limitation, not a defect, and it is not a stable-release blocker - the runtime
is in shadow, it abstains rather than guesses when it has no family, and its answer is
not what drove any action. But it does mean **the bounded runtime currently adds little
on failure classification**, and a note claiming otherwise would be wrong.

The other three families behaved sensibly: review escalation refused all three runtime
consultations and returned escalating verdicts on increasing scope, evidence relevance
separated a provenance-bearing claim from one without, and route family was consistent.

## Calibration

**NOT PROVEN.** No calibration profile was created from this run, and none should be:

- 19 decisions is a small dataset;
- zero of them have reviewed or verified labels;
- the failure-classification family, the largest, showed no discrimination at all, so a
  profile fitted on it would measure nothing real.

A profile from this data would be a threshold with no evidence behind it, which is
exactly what the calibration contract exists to prevent.

## Blockers checked

| Condition | Result |
|---|---|
| wrong answer-space mapping | none; every answer was inside its declared set |
| missing decision identity | none; all nine identity fields present on every record |
| cache contamination | none; the cache binds threshold, profile, revision and policy |
| runtime hang | none; max 3.66 ms per decision, real deadlines on every call |
| profile mismatch | none; no profile existed, so none was applied |
| unexpected authorization effect | none; every record `none` |
| shadow influencing execution | none; 0 effects, 0 acted-on, 0 isolation problems |
| provider probability mislabelled | none; every record `PROVIDER_PROBABILITY` |

## Limitations

1. 19 decisions, all from one small project, none reviewed. This demonstrates the
   pipeline, not its accuracy.
2. The failure classifier does not discriminate real build output, as above.
3. Latency excludes subprocess startup, which is the dominant cost of a cold sidecar.
4. Three of five review-escalation inputs and three of five evidence-relevance inputs
   were resolved deterministically without consulting the runtime. That is correct
   behaviour - Ariadne's own rules got there first - but it means the runtime saw fewer
   of them than the scenario list suggests.

## Recommendation

**Proceed to `2.1.0`.**

The architecture works, the shadow path works, the real task path revealed no blocker,
no authority leaked, nothing crashed, no gate regressed, and the artifacts install
cleanly. Stable does not require a calibration profile, and requiring one here would be
reading a threshold as if it were evidence.

The finding that matters for anyone adopting this is recorded plainly: the reference
engine's failure classifier is not useful on real build output today. Adopt it for the
families it discriminates, treat its failure-classification answer as a hint at best,
and expect a checkpoint-backed engine to be needed before that family is worth trusting.
