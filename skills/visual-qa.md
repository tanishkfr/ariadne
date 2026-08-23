# SKILL: visual-qa

**Trigger** — an approved direction has been implemented and a rendered target can be inspected. Post-S4B, before independent S5.
**Owner** — Builder / orchestrator
**Inputs** — locked `DESIGN.md`, `HANDOFF.md`, `PROJECT.md`, `AGENTS.md`, rendered target, `.builderos/creative-operations.json`
**Output** — hashed visual evidence and drift findings in `.builderos/creative-operations.json`; mechanical results remain in `QA.md`

This skill applies [QA-POLICY.md](../QA-POLICY.md) to the project-specific
requirements derived from the approved direction. It does not replace that
policy, grant G3, or enter the independent S5 review context.

## Method

1. Run `builderos.py operations-plan` if the creative-operations ledger does
   not exist. Stop if `DESIGN.md` is not locked at G1 or its required sources
   are missing.
2. Read `visual_qa_plan.targets` in priority order. Inspect the signature
   moment and thesis-critical behaviour first; do not substitute a generic
   viewport checklist.
3. For each target, use the named viewports and state transitions. Add a width
   immediately below and above a critical breakpoint when the requirement
   describes a composition change.
4. Exercise the real rendered state. Capture a screenshot, browser observation,
   DOM/state record, measurement, or interaction observation. A media query or
   source inspection is only `code-suggests` evidence.
5. Record one `visual-evidence` event per observation. Use `unverified` with a
   concrete environmental blocker when the state cannot be reached. `verified`
   requires a prior rendered or observed positive control plus the verification
   method.
6. Compare the observation with the approved requirement and record `approved`,
   `allowed`, `drift`, or `unknown`. Harmless implementation differences are
   allowed; protect the thesis, not pixel identity.
7. Stop when the signature moment, thesis-critical behaviour, major responsive
   transformations, major interactions, accessibility-critical states, and
   obvious defects have evidence or an explicit blocker. Secondary spacing
   polish does not justify an endless pass.

## Evidence event

```json
{
  "type": "visual-evidence",
  "id": "visual-signature-375",
  "requirement_id": "signature-moment",
  "level": "observed",
  "kind": "interaction",
  "viewport": 375,
  "observation": "The approved mobile transformation remains recognisable after interaction.",
  "evidence_path": "<real screenshot, browser record, or measurement>"
}
```

Record with `builderos.py record-operations --input <events.json>`, then run
`builderos.py operations-check --require visual` before creative review.

## Stop conditions

- No rendered target: record `unverified`; do not claim responsive or interaction behaviour.
- Required state cannot be reached: record the environmental blocker; do not infer a defect.
- A material deviation is intentional but not approved: record `unknown` and present the decision to the human.
- Independent S5 has begun: do not add project context to that reviewer.
