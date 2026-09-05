# Ariadne 1.6.1

Ariadne 1.6.1 is a narrow correctness and documentation patch for the 1.6.0
release. It does not change routing, stages, policies, gates, provider
boundaries or project-state compatibility.

## Fixed

- S4B can continue to S5 only after the current packet's structured
  `return-handoff.md` exists and records a complete implementation return.
- An S4B transcript plus `QA.md` can no longer substitute for that return.
- Deterministic negative and positive controls preserve both the blocked and
  successful continuation paths.

## Documentation

- Public installation guidance uses the immutable 1.6.1 wheel rather than a
  moving source-branch archive.
- The README documents version discovery, user-local data locations, update,
  rollback, uninstall and preservation of project and user-created files.
- Installed-user recovery guidance no longer depends on commands available
  only in a maintainer checkout.

## Compatibility and evidence limits

- Python 3.10 or newer; Windows is directly exercised.
- Existing project-state schema 1 remains supported; no migration is required.
- Codex remains the default. Claude remains optional.
- Native macOS/Linux behaviour, live Claude or Cursor execution and
  first-time-user comprehension remain unverified.
- The Python distribution/import name `ariadne` is also used by Ariadne
  GraphQL; use a separate interpreter or virtual environment when needed.
