# 09 — Security

The adversarial model for Decision Intelligence is simple: every attack tries to
either spend intelligence where code could know the answer, let judgement
masquerade as authority, or let a cached/conflicting/self-reported result slip
past policy. Each family fails safely, and each is exercised by a named test.

## Classification attacks

* **A deterministic fact is routed to a model.** The compiler checks `known`
  before the rule table, so a fact with a value classifies `DETERMINISTIC` and
  creates no question. Covered by
  `decision-compiler.deterministic-fact-wins` and the mutation
  `remove the deterministic-first guard`.
* **A bounded problem is treated as deterministic.** A bounded kind produces a
  question with a closed option set; the provider still answers it, and the
  decision record records the class. A `PROTECTED` consequence on a bounded
  question is refused outright — protection is a human gate, not a judgement.
* **A human decision is downgraded.** `HUMAN_KINDS` classify `HUMAN` even when a
  provider is configured, and the plan records a protected action.

## Cache attacks

| Attack | Defence |
|---|---|
| Same question id, different definition | The definition digest is in the key; the lookup misses with `QUESTION_DEFINITION_CHANGED`. |
| Same state text, different policy | The policy version is in the key; the miss reason is `POLICY_VERSION_CHANGED`. |
| Model version changed | The concrete version is in the key; the miss reason is `MODEL_VERSION_CHANGED`. A moving alias cannot even form a key. |
| Stale or superseded evidence | Fingerprints and expiry are checked on lookup; the entry is refused. |
| Provider alias moved | Alias-shaped model versions are refused at key construction. |
| Wrong task reuses a cached result | The key binds the projected state digest, not the task text, so a different task cannot present the same digest without presenting the same evidence. |
| Revoked decision served again | `freshness: REVOKED` is checked before anything else. |

## Batching attacks

* **A hidden answer dependency inside one batch.** The planner proves every step
  independent with the AR-204 dependency check; a dependent question is staged
  into a later step, and a cycle is refused.
* **A result mapped to the wrong question.** Results carry the question id, the
  planner accounts for every question, and an unanswered question is recorded
  `failed` rather than mapped to a neighbour.
* **A missing answer silently accepted.** The decision record for an unanswered
  question is `failed` with no answer, and the batch rollup reports `partial`.

## Escalation attacks

* **Low confidence treated as high.** Policy decides acceptance from the
  confidence *kind* and the consequence class; `LOW_CONFIDENCE` and
  `NO_CONFIDENCE` escalate.
* **`NONE` treated as zero.** A missing confidence is its own reason and is
  accepted only where the consequence permits an advisory.
* **Self-reported confidence treated as calibrated.** Only
  `CALIBRATED_PROBABILITY`, `PROVIDER_PROBABILITY` and Ariadne's own
  `DERIVED_CONFIDENCE` satisfy medium consequence; a model's self-report does
  not.
* **Generation bypasses policy.** Generation requires a recorded justification,
  and a protected requirement never reaches generation as a decision.
* **A cheap provider selected despite missing capability.** `supports()` checks
  declared capabilities; nothing in the engine orders providers by price.

## Authority attacks

All of the following fail, and are asserted by tests in the engine core suite
and the `golden-workflows` benchmark group:

* a decision tries to grant an approval — `policy.protected_action_problems`
  always reports the attempt, and no API accepts a decision as authorization;
* a decision tries to close verification — verification is an execution-bound
  record, and a graph node claiming `SUCCEEDED` without its output contract is
  refused;
* a high confidence causes acceptance of a protected operation — the
  confidence verdict returns `accepted: false` for `PROTECTED` regardless of
  value, and mutation testing confirms both the confidence and evidence guards
  are load-bearing;
* evidence relevance elevates stale evidence — the freshness check runs first
  and the answer is `IRRELEVANT` with `may_override_freshness: false`.

## Prompt-in-state resilience

Decision state can contain untrusted text. The projection is closed, so state
content cannot add fields, cannot add options to a question, cannot change the
policy and cannot grant authorization; an answer outside the declared option set
is refused as `invalid`, never coerced. What this does **not** claim is
resistance to semantic prompt manipulation inside the projected text: a hostile
evidence claim could still influence a provider's *judgement* within the allowed
answer space. That limitation is recorded honestly, and the mitigations are
structural — provenance, freshness, policy and the human gate do not depend on
the provider's good behaviour.

## Post-review repairs

The first adversarial pass found six genuine defects (cache reuse not bound to the
question definition, trusted projection entries, zero-confidence acceptance,
`known` with a null value, forbidden-key smuggling through `projection_entries`,
verification output checked by key presence only). All six were repaired and now
have permanent regression coverage; the before/after evidence is in
[10 — Test results](10-TEST-RESULTS.md). The review's probe scripts were re-run
after the repairs and show the safe behaviour for every finding.

## Known limits

* No live decision provider has been calibrated; no threshold is registered and
  no calibration quality is claimed. See [08 — Economics](08-DECISION-ECONOMICS.md).
* The deterministic provider is a fixture, not a quality signal.
* Provider-internal reasoning is never exposed, so the trace proves what the
  engine recorded, not how a provider reached an answer.
