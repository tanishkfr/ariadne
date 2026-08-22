# HANDOFF: <name>

> Template. Owner: Architect · Written at the end of S3, consumed at S4.
> **This is the compression layer of the whole system.** It exists so the implementer never re-derives what the director already decided.
> Re-deriving context is the single largest waste of subscription usage — see [MODEL-ROUTING.md](../MODEL-ROUTING.md) section 8.
>
> Write it so a tool that has never seen this project can start work from this file alone.

**To:** Implementer on <runner> · **From:** Architect · **Date:** <> · **G1 approved:** <date>

---

## Project summary

> Three sentences maximum. What it is, who it is for, what makes it different.

## Outcome and acceptance criteria

> Copy the goal and numbered success criteria from `PROJECT.md` without
> weakening or reinterpreting them. The fresh implementer does not receive
> `PROJECT.md`; this is its testable definition of the intended outcome.

**Outcome:** <verbatim goal from PROJECT.md>

1. <verbatim success criterion>

## Content readiness

> Name the source of every piece of user-visible copy or data. Use `ready`,
> `provided fixture`, or `not applicable`. Placeholder content is an unresolved
> input, not an implementation detail.

**Status:** <ready | provided fixture | not applicable>

**Source and constraints:** <paths, supplied copy/data, or why content is not applicable>

## Design thesis

> Verbatim from `DESIGN.md`. **Do not paraphrase.** The wording is the constraint.

**<the sentence>**

**Signature moment:** <what, where, and its mobile equivalent> — **build this first**

## Decisions that are fixed

> Settled. **Not to be relitigated.** If one of these is wrong, that is a finding, not a licence to change it.

| Decision | Value |
|---|---|
| Typography | <faces, scale ratio, size range> |
| Palette | <tokens> |
| Grid | <columns, gutters, margins, where it breaks> |
| Motion | <purpose, timing set, easing token> |
| Stack | <deviations from default, if any> |
| State | <where state lives> |
| CMS / backend | <decision> |

## Implementer discretion

> Keep small execution choices with the implementer; keep the approved
> direction out of reach. If a forbidden choice becomes necessary, raise a
> `BUILD FINDING` rather than silently changing it.

**May decide:** <implementation details that do not change outcome or direction>

**Must not reinterpret:** <thesis, signature moment, non-goals, content, and other fixed decisions>

## Implementation sequence

> Exact order. Dependencies first, signature moment early, polish last.

1. **Token system** — every value from `DESIGN.md` as CSS custom properties. Nothing else starts until this exists.
2. **<signature moment>** — built early so it cannot be cut for schedule.
3. <>
4. <>

## Files to create

| Path | Purpose |
|---|---|
| | |

## Components to build

| Component | Responsibility | Client? | Notes |
|---|---|---|---|
| | | server / client | |

## Dependencies to install

> Only pre-approved packages. Anything not on this list needs a **G2** request before installing — not after.

| Package | Version | Approved on |
|---|---|---|
| | | <date> |

**Nothing else may be installed without asking.**

## Implementation routing

> Provider choice is an execution decision, not a design decision. Route by the
> capability classes in `MODEL-ROUTING.md`; record provider facts only when
> observable and mark unknowns honestly.

| Field | Recommendation |
|---|---|
| Capability needed | `R2` / `R3` / `R4` / split with `R1` |
| Provider | <recommended provider or `retain in orchestrator`> |
| Model | <exact model if known, otherwise `provider default — unverified`> |
| Effort | low / medium / high |
| Workload | small / medium / large |
| Split | <what stays with the orchestrator, or `none`> |
| Reason | <why this route fits the work> |

Before an external build packet is created, Builder OS runs provider preflight.
Availability and quota are runtime facts; do not invent them in this document.

## Motion requirements

| Element | Purpose | Trigger | Duration | Easing | Reduced-motion state |
|---|---|---|---|---|---|
| | orientation / feedback / continuity / hierarchy / character | | | | |

## Asset requirements

| Asset | Status | Path | Blocking? |
|---|---|---|---|
| | ready / generating / substituted | | |

> **Nothing on the critical path may be unresolved.** If it is, S4 does not start.

## QA requirements

> What "done" means for this project, beyond the standard checklist in [QA-POLICY.md](../QA-POLICY.md).

- Production build passes, zero type errors, zero console errors
- Responsive at 375, 768, 900, 1280, 1920
- Keyboard-operable, visible focus, reduced-motion designed
- Every value from the token system — no hardcoded literals
- Project-specific: <>

## Known risks

| Risk | Likelihood | If it happens |
|---|---|---|
| | | |

## Definition of done

- [ ] Every task in `TASKS.md` meets its acceptance criterion
- [ ] Production build passes
- [ ] Zero type errors, zero console errors, zero React warnings
- [ ] Every value from the token system
- [ ] Signature moment built and working on mobile
- [ ] All mechanical QA checks run and recorded (including *not run*, with reasons)
- [ ] Scorecard >= 35, no criterion at 1
- [ ] Zero anti-generic patterns present
- [ ] Screenshots captured **and inspected**
- [ ] `QA.md` complete with a non-empty Known gaps list
- [ ] G3 presented

## Return handoff

At completion, interruption, or provider exhaustion, return the filled canonical
`templates/RETURN-HANDOFF.md` block. A partial return is valid only when it names
completed work, incomplete work, evidence, and the exact resume point. Do not
claim checks that were not run.

## If the design cannot be built as specified

Raise a `BUILD FINDING` ([WORKFLOW.md](../WORKFLOW.md) step 7) and wait for a decision. **Never substitute silently.**
