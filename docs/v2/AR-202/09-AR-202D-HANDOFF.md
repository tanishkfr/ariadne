# AR-202 → AR-202D handoff (Design Intelligence)

AR-202 is complete at the level this document describes. AR-202D — design
intelligence — is **not started**. Nothing below was implemented; it is the
starting point for the next milestone.

## 1. What AR-202 leaves you

| Surface | Where | Use for design intelligence |
|---|---|---|
| Task characterisation | `routing.characterize`, `state["characterisations"]`, event `task_characterized` | extend with design-specific characteristics (surface, medium, brand constraints, asset needs) as new fields or a subtype record; keep the "source + evidence + ordinal" shape and the no-LLM-classification rule |
| Routing decision | `routing.route`, `state["routing_decisions"]`, event `route_selected` | add design capabilities (e.g. `design-systems`, `motion-spec`, `visual-qa-planning`) to the adapter matrix and `WORKER_ROLE_CAPABILITIES`; add rules, not scores |
| Context decision | `context.decide`/`plan`/`finalise`, `plan_sources` in the transport, event `context_decided` | a design source (references, brand kit, component registry export) becomes another declared candidate with a reason; the plan may omit/reuse, never add |
| Execution identity | `execution.py`, groups `execution-identity` | bind design-reference inspection and visual QA runs to identities the same way; keep `observed` honest |
| Failure taxonomy | `failure.classify`/`FAILURE_SOURCES` | add design-specific mapping entries (e.g. an unreadable reference image) rather than new classes where a class already fits |
| Recovery | `recovery.py`, groups `recovery` | add a detector/action pair only for a genuinely new, safely decidable shape |
| Events | `events.EVENT_TYPES` | add design event types to the vocabulary deliberately; the projector needs no change |
| Benchmarks | `benchmarks/arbench/adaptive_cases.py` | add groups the same way; deterministic fixtures only, no image tooling required |
| ADRs | `docs/v2/AR-202/adr/` | follow the same form |

## 2. Explicit non-goals carried forward

AR-202 did **not** build and AR-202D should not assume: a Mobbin integration, a
shadcn/Radix registry integration, visual QA execution, component discovery, a
design-reference system, image generation, or a browser. The brief's non-goal
list (AR-202 §6) otherwise still applies.

## 3. Unfinished business AR-202 handed over

1. **Live provider execution remains unverified.** No paid or free provider was
   contacted (`suite.reasoner-rollback` and `suite.wheel-install` remain
   `DECLARED_SKIP`; model-backed cases remain unexecuted). Provider routing is
   verified deterministically against the adapter contract only.
2. **Observed runtime identity is unavailable.** `observed.*` is `UNKNOWN`
   until a runtime can report it. Do not invent it.
3. **Context savings are narrow.** The measured wins are optional-source
   omission, duplicate suppression and hash reuse. Changed-file awareness
   (`RELEVANT_CHANGED_FILE`) is declared in the reason vocabulary but has no
   rule; a design milestone with many reference files is the natural place to
   add one, with measurement.
4. **Recovery covers four shapes.** Anything else is refused by design. Every
   added shape needs: detection, evidence, proposed action, required
   authorization, transition, rollback.
5. **Approval expiry** is still policy-based (revision/subject/operation/scope/
   consumption/revocation), not time-based; a design milestone that introduces
   long-lived approvals should re-open the question with evidence.
6. **`plan_sources` is the only selection implementation.** Any new context rule
   goes there and is exposed through the same decision record; do not add a
   second selector.
7. **AR-204 owns performance.** Do not restructure for speed; measure first.

## 4. Suggested first AR-202D work, in order

1. Read `docs/v2/AR-200/05-DESIGN-INTELLIGENCE.md` (the AR-200 deferral record)
   and `04-EXTRACTION-PLAN.md` for the D-series decisions.
2. Inventory the design inputs that exist today (`references/capabilities.json`,
   skill files, DESIGN.md sections) and decide which are sources, which are
   evidence, and which are decisions — before writing code.
3. Extend the characterisation vocabulary with design signals *as data*
   (source + evidence + ordinal), then add one routing rule that consumes them.
4. Add reference material as context candidates with reasons, and extend the
   benchmark `adaptive-context` group with a case that proves a design source is
   omitted when irrelevant and never resurrected when forbidden.
5. Only then design the design-specific execution strategy (which design work an
   agent may perform) with the same engine boundary: identity, plan, decision,
   event, refusal test.
