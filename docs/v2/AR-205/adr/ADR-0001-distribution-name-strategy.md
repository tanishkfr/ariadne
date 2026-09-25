# AR-205 — ADR 0001 — distribution name strategy

Status: accepted for v2.0.0rc1

## Context

Ariadne distributes a Python launcher wheel from immutable GitHub release
artifacts. The wheel and the import package are both named `ariadne`, and the
release builder enforces that name (`ariadne-<version>-py3-none-any.whl`,
`ariadne/seed-runtime.zip`, entry point `ariadne = ariadne.cli:main`).

`ariadne` is also the name of an unrelated, widely used GraphQL server
implementation on PyPI. Two consequences are already observable:

- `pip install ariadne` resolves to the GraphQL package, not to this project;
- both packages install an import package called `ariadne`, so they cannot
  coexist in one Python environment.

AR-200 recorded this collision as a risk. AR-205 had to decide the release
strategy consciously and ground it in actual packaging behaviour rather than
rename the project by reflex.

## Decision

**DEFER_WITH_EXPLICIT_WARNING.** For v2.0.0rc1 the distribution keeps the
`ariadne` name and continues to install from immutable GitHub release wheels.
PyPI publication is explicitly out of scope, and the release gate treats any
PyPI publication metadata as a disconnect.

The warning and the coexistence rule are documented in `README.md`,
`INSTALL.md`, `RELEASE-NOTES.md` and this ADR. `release-metadata.distribution-name-decision-recorded`
pins the presence of the warning, and `release.canonical` keeps the wheel URL
version-locked.

## Consequences

- The GitHub-release channel is unaffected: it installs a URL, never a name.
- `pip install --user <wheel URL>` and `python -m pip show ariadne` behave as
  documented for Ariadne users; on a machine that also has GraphQL Ariadne in
  the same environment, `pip show ariadne` identifies the other project, which
  the README states.
- Future PyPI publication requires a distribution rename
  (`RENAME_DISTRIBUTION_ONLY`) plus a decision about the import package. That is
  a deliberate follow-up, not a silent change in this candidate.
- Nothing in the release candidate performs automatic update checks, so the
  collision cannot break installed users at runtime.

## Alternatives considered

| Option | Why not now |
|---|---|
| KEEP_FOR_V2 | Hides a known publication hazard instead of recording it |
| TRANSITION_WITH_ALIAS | Needs a second distribution name and alias metadata that no user needs yet |
| RENAME_DISTRIBUTION_ONLY | Would invalidate every published v1 wheel URL and the documented install path for zero current benefit |
| Publish to PyPI under another name | Requires the same rename decision plus a public release this milestone forbids |
