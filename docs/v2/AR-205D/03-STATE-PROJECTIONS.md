# 03 — State projections

A bounded decision must receive the smallest defensible state projection, never
the whole project. `ariadne_engine.decisions.projections` turns that principle
into four reusable contracts, each declaring exactly which evidence slices a
decision family may see.

## Field marks

Every field of a projection contract is one of:

| Mark | Meaning |
|---|---|
| `REQUIRED` | The decision cannot be made safely without it. A missing required field raises `InsufficientState`, whose structured reason is `INSUFFICIENT_STATE`. |
| `OPTIONAL` | It sharpens the decision; its absence is recorded, not fabricated. |
| `FORBIDDEN` | It must never be projected: authorization material, credentials, prompt text, or anything that could widen the closed answer space. |

Two additional rules make the projection *closed* rather than merely filtered:
an undeclared field is refused instead of shipped, and caller-supplied evidence
enters under one declared `supplied_evidence` slice rather than spreading across
arbitrary keys. Extending a projection is therefore a deliberate contract edit.

## The four contracts

### failure-classification

```
REQUIRED   failure                     the failure source and its detail
OPTIONAL   validator_outcome           what the validator recorded
OPTIONAL   changed_scope               the scope the attempt touched
OPTIONAL   previous_attempt            the prior attempt's result
OPTIONAL   environment                 environment observations
OPTIONAL   supplied_evidence           caller slices, explicitly named
FORBIDDEN  authorization, credentials, allowed, prompt
```

### review-escalation

```
REQUIRED   stakes                      the consequence class
REQUIRED   affected_scope              what the change touches
REQUIRED   verification_result         what verification established
REQUIRED   protected                   whether a protected operation is involved
OPTIONAL   review_findings             structured findings so far
OPTIONAL   implementation_evidence     engine evidence behind the change
OPTIONAL   supplied_evidence
FORBIDDEN  authorization, approval, prompt
```

Stakes, scope, verification and protection are required on purpose: an escalation
judgement must never be made blind to risk, and a protected operation must be
visible to the projection even when no answer is requested.

### evidence-relevance

```
REQUIRED   requirement                 the stated requirement
REQUIRED   evidence_claim              the claim under judgement
REQUIRED   evidence_provenance         where the evidence came from
REQUIRED   freshness                   its engine-computed freshness
OPTIONAL   verification_level          how it was established
OPTIONAL   supplied_evidence
FORBIDDEN  authorization, review_verdict, prompt
```

Freshness and provenance are required because relevance can never override them:
the deterministic checks run first and a stale claim answers `IRRELEVANT`
whatever any provider would prefer.

### route-family

```
REQUIRED   task_kind                   the declared task kind
REQUIRED   difficulty                  the characterised difficulty, or UNKNOWN
REQUIRED   stakes                      the characterised stakes
REQUIRED   available_capabilities      what is available now
REQUIRED   required_capabilities       what the task needs
OPTIONAL   stage, protected, supplied_evidence
FORBIDDEN  authorization, prompt
```

## Digests and bounds

Every projection is bounded by the AR-203 projection limits (entry count and
character count) and carries a sha256 digest over exactly the entries it
contains. The digest is what the decision record stores as its `state_digest`,
what the cache binds to its key, and what the decision graph records for the
node that consumed it. If the evidence changes, the digest changes, and no
cached answer can silently attach to the new state.

`projections.describe()` returns the declared contracts for inspection, and
`contract_problems` is used by the release tests to prove that no field is both
required and forbidden and that every contract declares required fields at all.
