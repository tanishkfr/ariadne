# AR-202 — Executable routing

Module: `src/ariadne_engine/routing.py`
Tests: `scripts/test-engine-core.py` (`routing_checks`), benchmark group `routing`

## 1. Task characterisation (T3)

Deterministic, evidence-named, no model call, no numeric scores. Every
characteristic is `{value, source, evidence}` where `source ∈ {user-declared,
rule-derived, runtime-observed, not-observed}` and the value is ordinal.

| Characteristic | Values | Derived from |
|---|---|---|
| `task_type` | brief / research / design-direction / implementation-planning / implementation / review / retrospective | the boundary stage |
| `difficulty` | LOW / MEDIUM / HIGH / UNKNOWN | declared high/medium-difficulty request tokens, recorded failures, repairs spent, declared worker role, unusually wide (>5 rows MEDIUM, >8 HIGH) permitted scope |
| `stakes` | LOW / MEDIUM / HIGH / UNKNOWN | sensitive subsystems in permitted scope, declared high-stakes tokens, dependencies requiring G2, external targets |
| `required_capabilities` | capability ids | the stage, plus implementation-repair/escalation when difficulty/stakes/failures demand them |
| `expected_change_scope` | bounded / multi-file / UNKNOWN | permitted scope rows |
| `subsystem` | sensitive subsystem or "handoff-declared scope" | sensitive scope rows |
| `validation_needs` | HIGH / MEDIUM / UNKNOWN | number of declared validation commands |
| `review_needs` | REQUIRED / STAGE-DEFAULT | stage |
| `context_sensitivity` | HIGH / MEDIUM / LOW | stage (isolated/creative boundaries are higher) |
| `uncertainty` | LOW / MEDIUM / HIGH | recorded failures, missing contract |

`UNKNOWN` is used whenever the evidence is absent; equivalent inputs produce
identical output (checked in the engine suite). A characterisation informs
strategy only — it never authorizes a protected action.

## 2. Routing rules

Executed in order; the decision names the rule that decided it
(`contracts.ROUTING_RULES`).

1. **`capability-required`** — eliminate candidates missing a required
   capability. Required capabilities come from `stage_requirements(stage,
   characterisation)`, which is derived from the stage itself so a stale or
   foreign characterisation cannot ask a reasoner for implementation capability.
2. **`policy-excluded`** — eliminate candidates the policy does not allow: an
   unselectable reasoner, an unsupported worker role, an escalation that is not
   stronger than the recorded role, or *any* continuation after an
   authorization refusal (`NEVER_ROUTE_AROUND`).
3. **`sufficient-capability` / `declared-default`** — among the remaining
   candidates prefer the lightest sufficient one; an operator-declared worker
   role is honoured and its capability verdict recorded (`sufficient` /
   `insufficient` with the missing capabilities).
4. **`escalation-required`** — on escalation, choose the lightest *stronger*
   sufficient role (or `senior-reasoning` when the `escalation` capability is
   required), never merely the next index.
5. **`repeat-failure-avoided`** — a failure class that means "do not simply
   repeat this runtime" (`TIMEOUT`, `PROVIDER_FAILURE`, `ENVIRONMENT_FAILURE`,
   `CAPABILITY_FAILURE`, `STALE_REVISION`) blocks the strategy that produced it
   and prefers a different sufficient candidate. The failed strategy is the one
   recorded on the failure record (`strategy`), not a guess: an unrecorded
   strategy is not assumed to be a repeat.
6. **`strategy-continuity`** — a reasoning reasoner stays selected until
   `select-reasoner` or `record-reasoner-failure` records a change; the route
   validates that the recorded selection satisfies the stage capability.
7. **`no-authorized-candidate`** — no candidate remains: the route is `no-route`
   and the caller pauses *before* any packet directory is created.

An authorization refusal and a human gate are stops, not inputs: routing may
only choose how authorized work is performed.

## 3. The record

```json
{
  "schema_version": 1,
  "decision_id": "rte_...", "stage": "S4B", "task_id": "…-S4B",
  "characterisation_id": "tsk_...",
  "required_capabilities": ["implementation", "implementation-repair"],
  "candidates": [{"id": "bulk", "capability_evidence": "declared", "satisfies": false, "exclusions": [...]}],
  "exclusions": [{"id": "bulk", "reasons": ["missing required capability: implementation-repair"]}],
  "chosen": {"id": "strong", "kind": "worker-role", "capability_verdict": "sufficient", "missing_capabilities": []},
  "fallbacks": [...], "status": "selected", "rule": "escalation-required", "reason": "...",
  "policy_version": "ar-202-policy-1",
  "requested": {"provider": "Cursor", "model": "", "effort": "", "worker_role": "strong"},
  "prior_attempts": [{"task_id": "…", "class": "TIMEOUT", "strategy": "bulk"}],
  "failure_evidence": {"class": "TIMEOUT", "retry_allowed": true, "strategy_change_allowed": true},
  "strategy_change_required": true, "identity_pinned": false, "recorded_at": "..."
}
```

Statuses: `selected`, `fallback`, `no-route`, `blocked`.

## 4. What routing actually changes

* The worker role written into the S4B packet is the router's chosen candidate
  (verified by `routing.escalation-chooses-stronger-candidate` and
  `routing.heavy-task-marks-declared-role-insufficient`).
* A boundary whose route is `no-route`/`blocked` pauses, names the rule and
  reason, records the decision, and creates no packet.
* The reasoner's capability evidence for the stage is validated before a
  reasoning packet is prepared.
* A blocking failure class prevents a blind repeat; a routine validation failure
  still permits bounded routine repair unchanged.

## 5. Requested vs observed runtime

* `requested` comes from the chosen candidate plus the packet/preflight
  declaration; it is also written into the execution record.
* `observed` is `UNKNOWN` on this runtime (`observed.source = unavailable`).
* `reported` (worker claim) is compared with `requested`; the mismatch is always
  recorded and emitted. It refuses only when `identity_pinned` is true — a
  concrete declared model (`declared_identity_pin` ignores placeholders). A
  pinned mismatch is recorded as `PROVIDER_FAILURE` and the return is *not*
  written.
* Model identity is never inferred from output style or from a transcript.

## 6. Fallbacks

| Failure class | Response |
|---|---|
| `ENVIRONMENT_FAILURE`, `PROVIDER_FAILURE`, `TIMEOUT` | a different sufficient candidate is preferred; if the run pins no identity, a reasoning stage may fall back to an alternate capable reasoner and the decision is recorded as `fallback` with rule `repeat-failure-avoided` |
| `CAPABILITY_FAILURE` | another candidate with the capability, or `no-route` |
| `VALIDATION_FAILURE`, `IMPLEMENTATION_FAILURE` | routine repair remains available (bounded by the unchanged two-repair budget); the model is not switched automatically |
| `AUTHORIZATION_FAILURE` | stop and escalate; never routed around |
| Human gate | stop; never routed around |
| No authorized candidate | `no-route`, pause, no packet |

## 7. Limitations

* Capability evidence is the adapter matrix's declared quality (`verified` /
  `externally-unverified`); an `externally-unverified` capability is recorded as
  a caveat, not treated as absent, because the operator opted in.
* Difficulty/stakes heuristics read declared text and evidence; they are
  ordinals with named sources, not measurements.
* Routing does not observe the provider. A route can therefore be *requested*
  correctly and fail on contact; that failure is classified and recorded.
