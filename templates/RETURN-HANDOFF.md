# IMPLEMENTATION RETURN HANDOFF: <project>

> Transport output from an external implementer back to Ariadne. This is an
> evidence summary, not a substitute for a verbatim provider transcript or an
> independent review. Fill every section; use `none` or `not run` rather than
> leaving a blank.

**Status:** complete / partial / blocked
**Task ID:** <packet ID>
**Worker role:** bulk / strong / senior-reasoning
**Provider:** <>
**Model:** <>
**Effort:** low / medium / high / unrecorded
**Started:** <>
**Ended:** <>
**Usage:** provider-reported usage, or unknown
**Cost:** provider-reported cost, or unknown

> `IMPLEMENTED` means the worker reports a complete implementation. Ariadne
> records `VALIDATED` only after independently rerunning the required checks and
> confirming scope. `REVIEWED` and `ACCEPTED` belong to later boundaries.

## What was built

<Concrete completed behaviour. Separate completed from attempted.>

## Files changed

| Path | Change | Why |
|---|---|---|
| | | |

## Architecture decisions

| Decision | Reason | Reversibility |
|---|---|---|
| | | easy / moderate / hard |

## Design deviations

| Specified | Implemented | Reason | Approval state |
|---|---|---|---|
| none | none | n/a | n/a |

## Dependencies

| Package | Exact version | Approved at G2? | Purpose |
|---|---|---|---|
| none | n/a | n/a | n/a |

## Tests

| Check | Result | Evidence |
|---|---|---|
| Production build | pass / fail / not run | |
| Typecheck | pass / fail / not run | |
| Lint | pass / fail / not run | |
| Automated tests | pass / fail / not run | |
| Browser QA | pass / fail / not run | |

## Evidence

<Commit, command outputs, screenshots, QA.md path, or `none captured`.>

## Worker validation

| Check | Worker result | Ariadne result | Evidence |
|---|---|---|---|
| <required or optional check> | pass / fail / not run | pending | <path or reason> |

Do not mark Ariadne result as passed. Ariadne fills that state from its
independent validation record.

## Safety and scope

**Scope status:** within-contract / out-of-scope / dangerous-action / repository-conflict / not checked

**Unexpected actions or conflicts:** <none, or the exact path/action and why it needs escalation>

## Known issues

<Numbered list, or `none known`.>

## Incomplete work

<Numbered list, or `none`. A partial/blocked return must name the exact resume point.>

## Accessibility and performance

<What was checked, results, concerns, and explicit not-run items.>

## Assumptions

<Implementation assumptions not already owned by PROJECT.md, DESIGN.md, or HANDOFF.md.>

## Next inspection

<The first thing Ariadne should verify, and why.>

---

End the provider response with this complete document between exact markers:

`BEGIN ARIADNE RETURN HANDOFF`

`END ARIADNE RETURN HANDOFF`
