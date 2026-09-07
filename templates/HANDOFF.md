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
| Effort | low / medium / high / xhigh / max |
| Workload | small / medium / large |
| Split | <what stays with the orchestrator, or `none`> |
| Reason | <why this route fits the work> |

Before an external build packet is created, Ariadne runs provider preflight.
Availability and quota are runtime facts; do not invent them in this document.

## Worker execution contract

> This is the bounded contract between the planning layer and the implementation
> worker. It is canonical project context, not provider memory. A worker may use
> normal implementation judgement inside these boundaries, but must stop when a
> boundary conflicts with the repository or the approved direction.

**Worker role:** <bulk | strong | senior-reasoning>

**Objective:** <repeat the outcome above in one testable sentence>

**Relevant context:** `HANDOFF.md`, locked `DESIGN.md`, project `AGENTS.md`, the
permitted files below, and directly relevant repository files discovered while
implementing. No earlier chat history is required.

**Invariants:** <approved thesis, acceptance criteria, compatibility rules, and
anything that must remain true>

**Permitted actions:** Read relevant repository files; edit permitted files;
create required files; run the listed validation commands; inspect git status and
diff; and repair routine validation failures within the stated limit.

**Prohibited actions:** `git push`; force operations; `git reset`, `git clean`, or
discarding unrelated changes; deleting significant data; reading or writing
secrets or `.env` files unnecessarily; deployment or production changes;
destructive migrations; installing unapproved dependencies; and changes to
unrelated systems.

**Stop conditions:** Missing required context; a packet/repository conflict; an
invariant at risk; an out-of-scope or dangerous action; or the routine repair
budget is exhausted.

**Escalation conditions:** Repeated routine failure; architecture conflict or
uncertainty; a high-risk change; or any invariant conflict.

**Lifecycle:** baseline → implementation → validation → routine repair →
validation → result/checkpoint

**Routine repair limit:** 2

### Permitted files and systems

| Path / glob | Actions | Reason |
|---|---|---|
| <relative path or narrow glob> | read / edit / create | <why this scope is needed> |

The worker may discover directly relevant files, but must add any newly needed
path to the return handoff and stop for an out-of-scope decision when it is not
covered by this table. Broad roots, secrets, environment files, and repository
control directories are never permitted here.

## Validation commands

> These are task-specific commands Ariadne can independently rerun from the
> project root. Use shell-free, bounded commands only. A worker report is not
> evidence of validation; Ariadne runs the required rows again before S5.

| Check | Command | Required | Expected |
|---|---|---|---|
| <unique check> | `<command>` | yes / no | <exit code or observable result> |

Use `not run` in the return handoff when an optional check is unavailable. A
required command that fails is a validation failure, not an acceptance.

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

> This is the S4B implementation-return boundary. Independent judgement and
> human gate decisions happen afterwards and cannot be claimed here.

- [ ] Every task in `TASKS.md` meets its acceptance criterion
- [ ] Production build passes
- [ ] Zero type errors, zero console errors, zero React warnings
- [ ] Every value from the token system
- [ ] Signature moment built and working on mobile
- [ ] All mechanical QA checks run and recorded (including *not run*, with reasons)
- [ ] Screenshots captured **and inspected**
- [ ] `QA.md` mechanical evidence is complete with a non-empty Known gaps list
- [ ] The complete marked implementation return is ready

### Downstream evidence — explicitly not part of S4B completion

The fresh independent reviewer supplies the scorecard and judgement. The human
then decides G3. Neither may be fabricated, predicted, or checked off by the
builder.

## Return handoff

At completion, interruption, or provider exhaustion, return the filled canonical
`templates/RETURN-HANDOFF.md` block. A partial return is valid only when it names
completed work, incomplete work, evidence, and the exact resume point. Do not
claim checks that were not run.

## If the design cannot be built as specified

Raise a `BUILD FINDING` ([WORKFLOW.md](../WORKFLOW.md) step 7) and wait for a decision. **Never substitute silently.**
