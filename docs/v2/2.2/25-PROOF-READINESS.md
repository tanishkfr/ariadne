# 25 — Proof Readiness

## Scope: what this phase deliberately does not build

AR-223 will introduce **Acceptance Intelligence**. This document introduces **none of it**:

```text
Contract · Requirement · Worker Claim · Evidence · VerificationDecision
PROVEN · PARTIAL · UNPROVEN · FAILED · CONTRADICTED · NEEDS_HUMAN
evidence sufficiency · claim/evidence gap · selective invalidation · re-verification
trained bounded intelligence · calibration · drift/degradation · intelligence scheduling
acceptance policy
```

`proof.py` returns `"verdicts": []` and says so in its own report. No threshold is hard-coded,
because a threshold encoded here would be inherited by the future engine as though somebody
had agreed to it.

What AR-222D owes AR-223 is narrower and is the thing that makes the next phase possible
without migration pain:

> **Could AR-223 later evaluate this requirement without reconstructing missing provenance?**

## The chain

```text
requirement -> implementation revision -> evidence -> finding
            -> repair attempt -> resulting revision -> new evidence
```

Every link already existed somewhere in AR-220 to AR-222. What did *not* exist was a way to
ask whether the chain was **complete at a point in time**, and a way to follow one requirement
across two passes. So `proof.py` joins existing records and reports gaps.

## Nine fields per requirement path

`proof.PROOF_FIELDS` — availability, not correctness:

```text
requirement_id · current_work_digest · evidence_identity · producer_identity ·
reviewer_identity · finding_identity · repair_identity · resulting_work_digest ·
new_evidence_identity
```

Each must exist *somewhere in the joined record*, so an AR-223 evaluation never reads prose to
work out who produced what or which revision it observed.

## Actor identity

Six roles, recorded so *the worker cannot independently certify itself* can be enforced later:

```text
user_or_human_approver · implementation_worker · evidence_producer ·
independent_reviewer · repair_worker · engine
```

`actor_table()` **derives** each role from the records that exist rather than asserting it. A
role nobody recorded simply does not appear, and `proof_problems()` reports it missing instead
of the chain quietly claiming a reviewer existed.

`SELF_CERTIFICATION_PAIRS` names the role pairs that may not be the same actor:

```text
implementation_worker / independent_reviewer     repair_worker / independent_reviewer
implementation_worker / evidence_producer        repair_worker / evidence_producer
```

`self_certification_findings()` reports collisions as **findings**, not refusals. AR-222D
records the provenance AR-223 will need; AR-223 enforces. The engine row is deliberately
exempt — the engine produced the evidence records, and saying "the engine reviewed its own
work" because it wrote both records would be true and useless.

## Three things it refuses to do

**It does not infer a missing link.** A finding with no requirement id is a gap, not a
requirement AR-223 could reasonably attribute. Fabricating the attribution is how a proof
system ends up proving the wrong thing:

```text
req-live-timing-wall / rfd-...: the finding does not carry its requirement id. AR-223 would
have to guess which requirement this finding is about
```

**It does not judge sufficiency.** Enough evidence is an AR-223 policy question.

**It does not overwrite history.** `assert_append_only()` requires before-evidence, the
original finding, the repair attempt and after-evidence to *still be present*. A pass that
lost its before-capture has broken the chain permanently, and saying so is more useful than
quietly reporting the surviving half:

```text
rfp-...: the pre-repair work digest is gone. Before-evidence is history and must survive the
repair; a proof that cannot compare before to after proves nothing
```

## Lineage states

```text
COMPLETE     every link is PRESENT. Nothing more.
INCOMPLETE   a link is missing
UNKNOWN      not determinable
```

`COMPLETE` is not "the requirement is met". It means AR-223 can *walk* the path. Collapsing
those two meanings would put a false green into the foundation of the acceptance engine.

## Fixtures carry their gaps

`fixture_lineage()` is usable even when incomplete — a fixture that only worked on a perfect
state would never exercise the gap path, which is the path that matters:

```python
lineage = proof.fixture_lineage(state, requirement_id="req-1")
lineage["state"]                            # "INCOMPLETE"
lineage["available"]["new_evidence_identity"]  # False
lineage["gaps"]                              # carried, not hidden
```

## The F1 slice at this depth

The slice stops at implementation planning, so there is no evidence yet and the report is
honest about it:

```text
requirements:   3        (one per surface, derived from the content model)
gaps:           0
orphans:        0
absent roles:   evidence_producer, independent_reviewer, repair_worker
verdicts:       []
```

`absent_roles` naming those three is the correct answer: nothing has been rendered and nobody
has reviewed it, and a report claiming otherwise would be the false green this module exists
to prevent.

## Critic continuity, the sibling concern

Continuity (`rendered_critique/continuity.py`) gives a review round a `review_session_id` and a
memory of prior findings, requested repairs, **declined requests and reasons**, and
before-captures — so round 2 asks whether round 1's repair landed.

The difficulty is that continuity must not become familiarity:

> **Continuity must not become familiarity.**

The memory carries findings, requests and reasons. It never carries the implementer's
rationale. `MEMORY_FORBIDDEN_FIELDS` refuses ten such field names by name, because
continuity creates a **second channel** into the reviewer's packet and a second channel is a
second opportunity to leak:

```text
critic memory carries 'implementation_rationale'. Continuity is not familiarity: a reviewer
who knows how the work was done is no longer fresh eyes
```

A declined recommendation must carry a **canonical** reason from the seven recognised ones.
`decline()` matches structurally — word-boundary matched, stopwords removed — because an
earlier substring version matched *"exceeds approved scope"* against *"reintroduces a
deliberately avoided default"*, whose second word is `"a"`, and `"a"` occurs inside
`"approved"`. A decline recorded against the wrong reason is worse than no decline, because
the reason is what the next round reads.

## See also

- [26 — Harness Integrity](26-HARNESS-INTEGRITY.md)
- [28 — AR-222D Results](28-AR-222D-RESULTS.md)
