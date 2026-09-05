# Changelog

## 1.6.1 — 2026-09-05

- Required the current packet's structured implementation return before S4B
  can continue to independent review.
- Prevented an implementation transcript plus `QA.md` from substituting for
  that return boundary.
- Corrected public installation, version discovery, data-location, update,
  rollback and uninstall guidance.
- Switched public installation examples from a moving branch archive to the
  immutable 1.6.1 wheel.

Routing, stage order, design policy, gate semantics, provider isolation and
human approval authority are unchanged.

## 1.6.0 — 2026-09-05

- Made fresh-stage packets carry their required canonical inputs, source hashes,
  parent identity and continuation boundary.
- Separated observed, supported, inferred, hypothetical and assumed claims from
  source confidence.
- Added a dated advisory capability registry that compares project-specific
  options without authorising dependencies or overriding `DESIGN.md`.
- Preserved implementation-provider identity and aligned S4B completion with
  the isolated S5 review boundary.
- Guarded the distinction between external data, untrusted instructions and
  human authorisation.
- Added bounded retry and persistent-denial handling for Windows creative-ledger
  replacement.
- Raised the documented Python minimum to 3.10 and corrected public metadata
  links.
- Documented the Python package-name collision with Ariadne GraphQL. The two
  packages require separate Python environments.

Routing, stage order, design policy, gate semantics, canonical ownership and
human approval authority are unchanged.

## 1.5.3 — 2026-08-23

- Published the project under the name **Ariadne**.
- Added a dependency-free user-local launcher and managed `$ariadne` Codex skill.
- Added deterministic stage packets, continuation provenance and stale-input checks.
- Preserved human approval for direction, dependencies, build completion, shipping and publishing.
- Added optional Claude reasoning and social-planning boundaries without making either a dependency.
- Adopted the Apache License 2.0.
