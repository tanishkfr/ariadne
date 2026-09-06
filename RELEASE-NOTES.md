# Ariadne 1.6.3.2

Ariadne 1.6.3.2 is a packaging correction for the 1.6.3.1 writing release.
It adds the omitted `WRITING-POLICY.md` file to the runtime allowlist so the
installed writing skill and its referenced policy travel together.

The existing immutable 1.6.3.1 release is preserved unchanged.

## Fixed

- Fresh wheel and runtime artifacts now include `WRITING-POLICY.md` alongside
  the writing skills and `scripts/prepare-stage.py`.
- Development-only tests, validation fixtures and maintainer-only files remain
  excluded from the runtime release surface.

## Evidence limits

- The correction changes packaging only; it does not change the writing
  architecture or claim live provider equivalence.

---

## Ariadne 1.6.3.1

Ariadne 1.6.3.1 adds a writing architecture and executable writing packet
workflow. It is a focused release and does not change the existing workflow
stage model or social strategy system.

## Added

- Writing intent distinguishes CREATIVE, ACADEMIC, SCIENTIFIC,
  HUMAN-DRAFT TRANSFORMATION and SOCIAL within the existing workflow.
- `WRITING-POLICY.md` defines genre methods, general anti-generic quality
  principles, Evidence Ladder reuse, transformation provenance and independent
  editorial review lenses.
- The existing transport now prepares `draft`, `review` and `revise` writing
  packets with provider/model identity, source hashes and explicit S4/S5
  boundaries.
- Human-draft transformation packets preserve the original draft for reviewer
  comparison, while review packets exclude drafting rationale and implementation
  history.
- A twelve-case writing benchmark and deterministic architecture self-test
  cover routing, genre methods, evidence boundaries, transformation and review
  independence.
- General writing no longer requires SOCIAL-only voice profiles, content
  pillars or `CONTENT-LEARNINGS.md`; those remain conditional on SOCIAL.

## Evidence limits

- Existing social behavior, including Contract v2 compatibility and Contract v3
  strictness, remains covered by the existing social suite.
- Structural and packet-level tests pass. The release does not claim live
  provider equivalence or a live independent-review session.

Ariadne 1.6.3 is a focused social-creative contract patch. It strengthens
strategy quality before drafting without changing the general workflow or
legacy Contract v2 behavior.

## Added

- Contract v3 requires two to four genuinely distinct creative angles with
  differentiation fields, selected-angle consistency and qualitative rationale.
- Contract v3 requires a reason-to-exist decision that rejects generic social
  content.
- Social post concepts record a 1–5 hook score; scores below 4 are a hard
  drafting failure requiring revision.
- Social strategy guidance and the conditional template document the new
  angle-selection and hook-evaluation method.

## Compatibility and evidence limits

- Contract v2 remains supported without Contract v3's angle and hook fields.
- No semantic-similarity subsystem, AI-detector integration, humanizer or
  detector-evasion heuristic was added.
- Social strategy remains optional and does not publish, authenticate,
  schedule or alter build gates.

Ariadne 1.6.2 was a narrow model-routing patch for the 1.6.1 release. It did not
change stages, gates, capability classes, provider boundaries or project-state
compatibility.

## Fixed

- `R1` model selection no longer escalates on a single elevated signal. Model
  and effort are decided by two orthogonal gates -- difficulty (complexity,
  ambiguity, context requirements) and stakes (consequence, reversibility,
  visual value) -- and escalation now requires both.
- A task marked `novel` no longer implies the highest-cost model on its own.
  Novelty is an operator's assessment of a task, not evidence that the largest
  model is required, so novel work that is cheap to retry stays on a cheaper
  tier.
- Reasoning effort no longer rises merely because a stronger model was chosen.
  When being wrong is cheap to detect and cheap to undo, effort is held at
  medium however difficult the problem looks.
- The routing recommendation reported its model-landscape evidence as a
  constant. It is now a real classification -- `unverified`, `operator-reported`
  or omitted -- and never claims verification, since Ariadne performs no live
  capability lookup.
- The routing self-test printed non-ASCII test names and crashed on consoles
  using a legacy code page. Runtime output is ASCII and is exercised under
  `cp1252`.

## Added

- `python scripts/ariadne.py route ...` recommends capability class, model,
  effort and session strategy, with the reasoning behind each.
- `--visual-importance` and `--context-requirements` expose the two remaining
  per-task judgements that materially change a routing decision.
- Decision-boundary and cost tests, including an invariant that no single
  elevated dimension alone reaches the highest model or effort, and a check
  that no input combination recommends an effort its model cannot run.

## Compatibility and evidence limits

- Python 3.10 or newer; Windows is directly exercised.
- Existing project-state schema 1 remains supported; no migration is required.
- Codex remains the default. Claude remains optional.
- The routing tier boundaries are argued from cost reasoning, not measured
  against outcomes. Nothing here establishes that a cheaper model matches a
  more expensive one on the work now routed to it; treat the recommendation as
  a default to override, not a verdict.
- The model-landscape mapping is dated source knowledge, not a live lookup.
- Native macOS/Linux behaviour, live Claude or Cursor execution and
  first-time-user comprehension remain unverified.
- The Python distribution/import name `ariadne` is also used by Ariadne
  GraphQL; use a separate interpreter or virtual environment when needed.
