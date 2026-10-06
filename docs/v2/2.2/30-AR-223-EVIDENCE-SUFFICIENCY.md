# AR-223: Evidence Sufficiency

> **What is enough evidence, for this requirement, to say this thing is done?**

The acceptance engine has six verdicts and refuses to move between them without a reason. This
document is the reason-generating layer underneath: the policies, the rule for when evidence
*conflicts*, and the rule for when it is merely *absent*.

## The four parts of a sufficiency policy

```text
AUTHORITATIVE      sufficient on its own to establish the requirement
REQUIRED           at least one is needed before anything can be established
SUPPORTING         adds weight, establishes nothing alone
INSUFFICIENT_ALONE never sufficient by itself, whatever else agrees
```

The policy is derived from the requirement's kind when it is not declared, so the common case
needs no ceremony:

| Kind | Authoritative | Also required |
| --- | --- | --- |
| `FUNCTIONAL` | `TEST` | — |
| `REGRESSION` | `TEST` | — |
| `INTERACTION` | `INTERACTION` | — |
| `VISUAL` | `RENDER` | — |
| `CONSTRAINT` | `BUILD` | — |
| `PERFORMANCE` | `PERFORMANCE` | — |
| `SECURITY` | `STATIC_ANALYSIS` | — |
| `COMPATIBILITY` | `BUILD` | — |
| `SUBJECTIVE` | `REVIEW` | human gate |

Two consequences worth stating plainly, because both were learned the hard way in this
repository's own history:

**A build result does not establish a visual requirement.** The AR-222 Beacon fixture built
cleanly and still had a table reaching 568px inside a 390px viewport. `BUILD` is authoritative
for `CONSTRAINT` and supporting everywhere else, because a successful compile is evidence about
compilation.

**A screenshot does not establish an interaction requirement.** The same fixture has render
captures of a navigation it never drove. `SCREENSHOT` is in `INSUFFICIENT_ALONE` for exactly
this reason: it shows a state, and an interaction is a transition between states.

## Absent is not violated

The single most important distinction in this milestone:

```text
no evidence of kind K        ->  UNPROVEN, and the reason names the missing kind
evidence of kind K that
  contradicts the requirement ->  FAILED
```

The engine reports the absence with its kind named — `missing: INTERACTION. Absent evidence is
not a defect and is never reported as one` — so a reader can tell the difference between "we
did not look" and "we looked and it is wrong" without opening the evidence.

Turning absence into failure is tempting because it makes a report feel decisive. It is also how
an acceptance engine ends up condemning work nobody examined.

## Conflicting evidence

Two current, non-superseded rows of the same kind disagree about the same requirement. That is
`CONTRADICTS`, and it is not resolved by preferring the newer row, the more confident row, or
the one whose producer sounds more senior. A contradiction between two honest observations is
information about the requirement, not a tie to be broken silently.

Contradiction is distinct from the evidence-concerns vocabulary: an *ignored* row is one the
policy excludes (`INSUFFICIENT_ALONE`), a *conflicting* row is one that disagrees with another
current row of the same kind. Both are named in the decision, so the reader sees what was set
aside and why.

## Staleness

Freshness is recomputed, never trusted:

```text
the artifact's bytes no longer hash to the recorded digest   -> STALE
the observed work digest is not the one being accepted       -> STALE
the contract revision moved and the row predates it          -> STALE
the row was superseded by a newer observation                -> SUPERSEDED
an artifact cannot be re-read at all                         -> MISSING
```

A superseded row never comes back. `MISSING` is not a warning about an old file; it is the
end of a chain of custody, and the decision that relied on it is no longer current.

Supersession is how a second observation replaces a first without erasing it. The first pass
stays readable, because a repair lineage whose first record was overwritten proves that a
repair happened and nothing about what it repaired.

## Binding, and why it is the whole mechanism

Every evidence row is bound to:

```text
producer, producer_role, producer_execution   who observed it and in what run
work_digest                                     which revision they observed
contract_revision                               under which interpretation
artifact path + sha256, or source_record_id    what it actually is
requirement_ids                                 what it concerns
```

Remove any one of these and the row cannot be weighed. Evidence with no artifact and no source
record is refused outright, which sounds pedantic until you consider what a benchmark becomes
when every row is "trust me".

## Reading a decision

Every decision carries its own reasoning, in the record, in this shape:

```text
verdict          FAILED
rationale        rqm_... is violated by current evidence: at 880px the toggle was pressed
                 and the sidebar stayed open at its full width
uncertainty      FAILED describes the work. Whether any worker claimed otherwise is a
                 separate record, because a worker that made no claim at all is the common case
decision_path    DETERMINISTIC:contradicted-evidence
deterministic    policy_met []  policy_outstanding []  contradicting [evd_...]
trace            DETERMINISTIC: policy met []      -> FAILED
```

`uncertainty` is separate from `rationale` on purpose. The rationale says what the evidence
shows. The uncertainty says what the engine does *not* know — and the sentence above it is the
one that stops a verdict from being read as a judgement on anybody's honesty.

**Next:** [Verified Intelligence](31-AR-223-VERIFIED-INTELLIGENCE.md) ·
[LabelLED Corpus](32-AR-223-LABELLED-CORPUS.md)
