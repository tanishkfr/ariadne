# AR-224 Verified Intelligence Release State

Preserve the actual AR-223 measured result. At release two families were
ACTIVE from the seeded naive-Bayes reference runtime and its reviewed
bounded-decision corpus:

- REVIEW_ESCALATION accuracy 1.000 ECE 0.053 ACTIVE
- ROUTE_FAMILY accuracy 1.000 ECE 0.031 ACTIVE

Two deliberately not promoted:

- FAILURE_CLASSIFICATION accuracy 0.314 EVALUATED
- EVIDENCE_RELEVANCE accuracy 0.339 EVALUATED

1.000 applies only to the specific decision family, corpus revision, split,
runtime identity and evaluation. It is not general model accuracy.
Release docs must say so. No 100 percent accurate AI claim.

For every promoted profile authorization_effect remains none. Promotion
grants decision eligibility, never action authority. Regression tested.
Before release, re-run the canonical evaluator if release policy requires
fresh measurement. Never silently copy docs if the measured identity
changes. Do not promote weak families to make release numbers look better.
