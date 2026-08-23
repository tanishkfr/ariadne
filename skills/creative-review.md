# SKILL: creative-review

**Trigger** — project-specific rendered or observed evidence exists after implementation. Post-S4B, before independent S5.
**Owner** — Creative director / orchestrator
**Inputs** — approved requirement trace and recorded visual evidence in `.builderos/creative-operations.json`
**Output** — one actionable `creative-review` event in the same ledger

This is an internal creative-direction pass, not independent S5 and not a gate.
It may conclude that technically complete work is not yet strong enough, but it
cannot approve its own work or silently change the approved direction.

## Method

1. Review only what rendered or observed evidence supports. Code suggestions
   cannot establish visual quality.
2. Judge thesis, distinctiveness, memorability, visual craft, interaction,
   narrative, implementation quality, design fidelity, portfolio value, and
   genericness. Each judgement cites evidence IDs; an unevidenced dimension is
   explicitly unknown.
3. State the strongest aspect, weakest aspect, biggest risk, and single
   highest-value improvement.
4. Decide whether another iteration is `yes`, `no`, or `conditional`. Name what
   should not change so a focused correction does not become a visual restart.
5. If the improvement changes the thesis or a G1-locked decision, stop for the
   human. Otherwise return it to the builder within the approved handoff scope.

## Done when

The review cites rendered evidence, gives one prioritised action, distinguishes
unknowns from defects, and records whether iteration is justified. It does not
change `DESIGN.md`, grant G3, or enter the isolated reviewer packet.
Run `builderos.py operations-check --require review` before presenting its
result as complete.
