# ADR-0005 — Rendered QA is instrument-backed and optional; core stays dependency-free

Status: accepted (AR-200) — drives AR-202D
Deciders: AR-200 audit
Evidence: 05-DESIGN-INTELLIGENCE.md §5; repository-wide search for browser/automation imports returned no matches

## Context
Neither Ariadne nor Boreal captures or inspects rendered output. Ariadne's `visual-qa` skill and QA policy describe what a human should check; the ledger's `rendered`/`observed`/`verified` levels are labels attached to files the *worker* supplies, and Boreal's design profile accepts a `rendered: true` JSON field that the same deterministic worker writes. Meanwhile Ariadne's product promise is "works offline, no paid API, no cloud account, `dependencies = []`".

## Decision
Rendered QA is implemented as an adapter interface (`CaptureAdapter`: `available`, `capture`, `compare`) with a deterministic fixture implementation shipping in-repo so the discipline is testable offline. Real browser automation is an operator-approved optional dependency behind the existing G2 gate, never installed automatically and never required. `rendered` requires a capture artifact with digest, viewport, DPR and route; `observed` requires an interaction/measurement artifact; `verified` requires independent re-execution reproducing the evidence within a declared tolerance. A self-declared field can never satisfy any level.

## Alternatives considered
- **Bundle Playwright (or similar) into the core.** Rejected: adds a heavyweight dependency and installation surface to a zero-dependency engine, and would be unavailable in the offline deterministic mode the product promises.
- **Leave rendered QA as documentation.** Rejected: the brief requires separated functional/a11y/visual/judgement QA, and source code cannot prove rendered quality.
- **Require a paid service for visual comparison.** Rejected: paid services must stay optional (`Mobbin-class` rule, 05 §1).

## Consequences
- The offline path can prove the *discipline* (levels, evidence requirements, refusals) but not the *rendering*; documents must state that distinction.
- Functional and accessibility QA reuse the existing validator, which already executes and hashes real commands.
- Design-runtime benchmark cases can run offline via the fixture adapter; only genuine browser capture requires the optional dependency.
