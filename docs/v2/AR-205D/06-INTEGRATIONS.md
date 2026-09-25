# 06 — Integrations

Decision Intelligence is an execution mechanism, not a library that happens to
exist. Four real engine paths consume it through one shared route — compiler,
projection contract, batch planner, policy, escalation:

| Path | Entry point | Question | Projection |
|---|---|---|---|
| Failure classification | `execution.classify_with_decision` (via `decisions.integrations.classify_failure`) | `failure-class` | `failure-classification` |
| Review escalation | `review.escalation_advice` | `review-escalation` | `review-escalation` |
| Evidence relevance | `verification.relevance_advice` | `evidence-relevance` | `evidence-relevance` |
| Route family | `routing.family_advice` | `route-family` | `route-family` |

Each integration follows the same invariant chain, and the chain is what makes
the path meaningful rather than decorative:

1. deterministic facts are checked first and win;
2. a bounded question is built from the declared projection contract;
3. the planner batches independent questions and stages dependent ones;
4. policy judges the answer; confidence is never authorization;
5. when no accepted answer exists, the result is a structured escalation, never
   a plausible default and never a silently invoked generative call.

## Failure classification

The declared failure vocabulary is consulted before anything else; a mapped
source is classified deterministically and the fact is recorded in a compiled
plan. Only an unmapped source may become a bounded question, and even then only
inside the safe class subset — authorization, revision, conflict and design
failures are deterministic facts that a model may never supply. When the
provider is unavailable, fails, answers outside the set, or the policy refuses
the confidence, the class stays `UNKNOWN`, the decision record is kept as
evidence, and the caller is told to escalate.

## Review escalation

The advice answers `routine`, `independent_review`, `enhanced_review` or
`human_attention`, and deterministic rules come first: a protected operation
always suggests human attention, low stakes with independently reproduced
evidence suggests routine review, and high stakes without current verification
suggests enhanced review. Only the remaining cases become a bounded question.
The advice is an input to policy: the review the engine *requires* is still
decided by `review.required_review_problems`, and
`policy_still_controls: true` records that boundary.

## Evidence relevance

The answer space is `SUPPORTS`, `PARTIALLY_SUPPORTS`, `IRRELEVANT`, `CONTRADICTS`
or `UNKNOWN`. Freshness and provenance are checked deterministically *before*
anything is asked and can never be overridden: stale evidence answers
`IRRELEVANT` with source `deterministic` whatever a provider would prefer, and
evidence without provenance answers `UNKNOWN`. `may_override_freshness` is
always `false` in the result, so a caller cannot mistake the judgement for a
freshness verdict.

## Route family

`mechanical`, `implementation`, `design`, `research`, `recovery` or `unknown`.
A declared task kind maps to a family deterministically and no provider is
consulted. A protected operation routes through human policy and returns
`unknown` with `policy_authority: deterministic`. The family is an input to
routing, never a replacement for it: the worker-role policy in `routing.route`
always wins.

## What this is not

No integration calls a provider when a deterministic fact already answers the
question, none lets a bounded answer grant authority, and none exists merely to
increase the count of integrations. `decisions.integrations.describe()` lists
the four paths and their invariant, and the benchmark group
`decision-integrations` exercises each one, including the refusal paths.
