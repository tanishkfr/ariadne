# AR-223: Acceptance Intelligence

> **Which parts of a worker's claimed completion are actually established by the evidence that
> exists right now?**

AR-222 collected and preserved trustworthy evidence. It did not decide anything about the work,
because deciding is harder than collecting. AR-223 closes that gap, and the gap has four edges
that a system either separates or gets wrong:

```text
a claim is not evidence
missing evidence is not failure
a passing check for one requirement says nothing about unrelated requirements
worker-produced evidence does not automatically become independent acceptance
```

Every one of these is a way a system can produce a confident, wrong, *finished*-looking
verdict. None of them is exotic. They are what a system does when it is asked for a single
number and the honest answer is a set.

## The model

```text
TASK
 └─ CONTRACT                    a versioned interpretation bound to the exact request
     ├─ REQUIREMENTS            independently verifiable obligations, stable ids
     ├─ CLAIMS                  what workers say they did -- never evidence
     ├─ EVIDENCE                what was observed, by whom, about which revision
     └─ VERIFICATION DECISIONS   one of six verdicts per requirement, per pass
              ↓
         ACCEPTANCE STATE       explicit, countable, never a percentage
```

A **contract** is bound to its own source digest. Rewriting the request after the work begins
creates a revision with a stated material-change reason, and the old revision stays readable
with its decisions attached to it. Nothing is retroactively reinterpreted.

**Requirements** carry an evidence *policy*: which kinds of evidence are authoritative, which
are required, which merely support, and which are insufficient alone. The policy is derived
from the requirement's kind when not declared. A requirement nobody has examined is
`UNPROVEN`, never `FAILED` — nothing observed a violation, and reporting failure for an absence
is the cheapest way for an acceptance engine to become dishonest.

**Claims** are prose, extracted or structured, sanitised, and stored as data. They are never
promoted. A claim's own text cannot satisfy its own requirement, and re-reading it does not
change that. Claims are assessed *against* verdicts, which is how a worker's assertion of
completion becomes `CONTRADICTED` when the measurement says otherwise.

**Evidence** must name its producer, its producer's role, the requirements it concerns, the
work revision it observed, and either a re-readable artefact or the record it was derived from.
Evidence that points at nothing is refused as the assertion it is. Freshness is recomputed on
every pass from the digest and the contract revision, never read from the row, so a stale
screenshot cannot be laundered into a current claim by copying its metadata forward.

## The six verdicts

| Verdict | Means |
| --- | --- |
| `PROVEN` | established by current evidence under the requirement's own policy |
| `PARTIAL` | some of it is established and some is not |
| `FAILED` | observed violated |
| `CONTRADICTED` | evidence disagrees with itself |
| `NEEDS_HUMAN` | a human decision is required and has not been given |
| `UNPROVEN` | not established, and nothing observed a violation |

`UNPROVEN` and `FAILED` are different states and conflating them is the central error this
milestone removes. A report that says "4 of 6 requirements are failing" when three of them have
never been looked at is a report that will be believed.

## The gate

Acceptance is decided in exactly one place, from explicit clauses, each of which closes a
different failure:

```text
every blocking requirement is PROVEN
no blocking requirement is FAILED
no blocking requirement carries a contradicted required claim
required independent review occurred
the evidence relied on is current
required human and authorisation gates are satisfied
no protected human acceptance is outstanding
```

Each clause reports its own verdict with its own detail, so a reader sees *which* rule stopped
acceptance rather than being told only that it was not accepted. `NOT_ACCEPTED` is a normal,
useful outcome: it is what AR-222 recorded about itself, and it is what the Beacon slice in
`34-AR-223-RESULTS.md` produces from real preserved history.

Non-blocking requirements that are not `PROVEN` are carried in an advisory section rather than
hidden. Accepting around them is permitted; saying nothing about them is not.

## Selective re-verification

A change invalidates by impact, not by proximity. A requirement whose declared scope matches
the change is `POTENTIALLY_AFFECTED`. A requirement that declares a dependency fingerprint
which did not move is `PROVEN_UNAFFECTED`. A requirement that declares nothing is `UNKNOWN` —
because "obviously unrelated" is exactly the judgement that was wrong last time.

`UNKNOWN` is not a failure to invalidate, and it is not a licence to skip. It means nobody
recorded enough to prove independence, so the re-verification planner must cover it. Evidence
about a requirement proven unaffected stays weighable at the new work digest, and every row
admitted that way is named in the pass record rather than quietly merged.

## Independent review

Three refusals, all structural:

* the reviewer is the party whose work is under review;
* the reviewer produced the evidence being weighed;
* the reviewer is the engine, where independent review is required — an engine verdict is a
  determination from recorded evidence, which is a different act.

## Where bounded intelligence fits

A requirement may declare `verification_mode` of `BOUNDED` or `GENERATIVE`. Then, and only then,
a bounded runtime's advice is consulted — **after** the deterministic rules left the question
open, never to override them. The answer and its `confidence_kind` are recorded in the decision
trace with the note that they were recorded rather than obeyed. Provider probability is never
recorded as calibrated, and no confidence of any kind reaches a gate.

The ordering is the whole boundary: deterministic rules first, bounded advice second,
generative last, human where the requirement says so. See
[Verified Intelligence](31-AR-223-VERIFIED-INTELLIGENCE.md) for what makes the bounded rung
eligible to be consulted at all.

## What this milestone does not do

It does not grant authority, satisfy a human gate, accept protected work, or issue a release.
Those are separate authorities with separate owners. Every record written here carries
`authorization_effect: none`, and the adversarial suite attacks the boundary directly rather
than trusting the docstring.

**Next:** [Evidence Sufficiency](30-AR-223-EVIDENCE-SUFFICIENCY.md) ·
[Verified Intelligence](31-AR-223-VERIFIED-INTELLIGENCE.md)
