# ADR-0212 — Routing is an executed decision under explicit ordered rules

Status: accepted (AR-202)
Deciders: AR-202 implementation
Evidence: `src/ariadne_engine/routing.py`, `04-ROUTING.md`, benchmark group `routing`

## Context
AR-201 exposed routing as advice: a reasoner was selected and recorded, a worker role was looked up from the handoff or by an index into a role list on escalation, and an unavailable provider produced an error message. None of it was a decision the engine could explain, and none of it reacted to what actually happened on the previous attempt.

## Decision
Routing becomes an executable, recorded decision:

1. **Characterisation first.** A deterministic, evidence-named characterisation (`task_type`, `difficulty`, `stakes`, `required_capabilities`, change scope, validation/review needs, context sensitivity, uncertainty) is derived from the request, the handoff contract, the creative/operations ledgers and the failure history. No model call classifies a task; unknown inputs stay `UNKNOWN`; ordinals only, no invented scores.
2. **Required capabilities decide the candidate set**, not taste: reasoning stages require the stage's declared capability from the adapter matrix; the implementation boundary requires `implementation`, plus `implementation-repair` when difficulty or stakes demand it, plus `escalation` when the recorded lifecycle says escalation is required.
3. **Ordered rules**: eliminate capability-missing candidates; eliminate policy-disallowed candidates; prefer the lightest sufficient candidate; escalate when difficulty, stakes or failure evidence requires it; do not repeat the exact strategy that already failed; stop when no authorized candidate remains.
4. **Authority is not routable.** An authorization refusal and a human gate are explicit stops. Routing may only choose *how* authorized work is done.
5. **The decision is recorded** (`RoutingDecision`) and mirrored into the canonical event log, including candidates, exclusions, rule, fallbacks, prior attempts, requested provider/model and the pinned-identity flag.

## Alternatives considered
- **A numeric score per candidate.** Rejected: there is no justified scoring model, and a score would hide the rule that actually decided.
- **Silently overriding the handoff's declared worker role when the characterisation disagrees.** Rejected: the role is a human/creative decision recorded in the build contract. The engine records the insufficiency, and only blocks when failure evidence says the same strategy already failed.
- **Auto-switching the reasoner when the selected one is unavailable.** Rejected: reasoner continuity is an operator decision (`select-reasoner`); the engine records the fallback candidates and pauses.
- **Letting routing decide authorization.** Rejected: capability sufficiency is not permission.

## Consequences
- Every route is explainable by one rule id and one reason string.
- Escalation now selects the lightest *sufficient* stronger role instead of the next index, and refuses when nothing stronger is sufficient.
- A timeout/provider/environment failure requires a genuinely different strategy to be chosen; a routine validation failure still permits bounded routine repair, so the two-repair rule is unchanged.
