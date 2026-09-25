# AR-205 — 01 — Public surfaces

Every externally observable surface is classified before packaging changed.
Classes:

- **FROZEN** — published v1 behaviour that v2 must not break.
- **COMPATIBLE_EXTENSION** — additive, published in v2, safe to rely on.
- **PROVISIONAL_V2** — product surface in v2 that may still evolve within v2.
- **INTERNAL** — implementation detail; not a contract.
- **DEPRECATED** — still honoured, documented as going away.

| Surface | Value at v2.0.0rc1 | Class |
|---|---|---|
| Distribution name | `ariadne` (GitHub release channel) | FROZEN, with a recorded publication hazard (ADR 0001) |
| Wheel filename | `ariadne-2.0.0rc1-py3-none-any.whl` | FROZEN pattern |
| Import package (launcher) | `ariadne` | FROZEN |
| Console entry point | `ariadne = ariadne.cli:main` | FROZEN |
| `python -m ariadne` invocations | `install`, `doctor`, `update`, `rollback`, `uninstall`, `enable-claude`, `disable-claude`, `codex-baseline`, `paths` | FROZEN |
| `python -m ariadne --version` | one line, `Ariadne <version>` | FROZEN |
| Runtime CLI | `scripts/ariadne.py` with its v1 command set | FROZEN; new commands are extensions |
| `migrate` command | `--dry-run` (default), `--apply`, `--rollback` | COMPATIBLE_EXTENSION |
| Runtime `--version` | `Ariadne <version>` plus one contract line | COMPATIBLE_EXTENSION |
| `python -m ariadne_engine` API | `ariadne_engine.public` stability table | PROVISIONAL_V2 (STABLE_V2 names) |
| Consumer protocol | `ariadne-consumer` version 1 | PROVISIONAL_V2 |
| Engine contract marker | `ariadne-engine-1` | STABLE_V2 |
| Run-state file schema | `schema_version: 1` | FROZEN |
| Run-state record schema | `2` (`engine.record_schema`) | STABLE_V2 |
| Migration report | `migration-report.json`, schema 1 | STABLE_V2 |
| Project files | `PROJECT.md`, `AGENTS.md`, `DESIGN.md`, `HANDOFF.md`, `QA.md` | FROZEN |
| Project ledger schemas | `creative-evidence.json` 1–2, `creative-operations.json` 1 | FROZEN |
| Packet manifest | `manifest.json` schema 1 | FROZEN |
| Stage names | `S1`, `S3`, `S4A`, `S4B`, `S5`, `S6` | FROZEN |
| Gate names | `G1`–`G5` | FROZEN |
| Lifecycle states | `NOT_STARTED`, `IMPLEMENTED`, `VALIDATED`, `FAILED`, `BLOCKED`, `REVIEWED`, `ACCEPTED`, `REJECTED` | FROZEN |
| Exit codes | `0` success, `1` stopped/refused, `2` paused or needs-human | FROZEN |
| Install pointer | `install-home/current.json`, schema 1 | FROZEN |
| Release descriptor | `ariadne-release.json` with `version`, `sha256`, `launcher`, `release_notes` | COMPATIBLE_EXTENSION |
| Release manifest inside the runtime | `RELEASE-MANIFEST.json` schema 1 | FROZEN |
| Installed runtime layout | `<home>/versions/<version>/` plus the managed skill | FROZEN |
| Update flow | verified download, validate, switch pointer | FROZEN |
| Rollback flow | `python -m ariadne rollback [--to]` | FROZEN |
| Environment variables | the v1 set only; no new required variable | FROZEN |
| Config | run-state `efficiency` block plus existing stage settings | COMPATIBLE_EXTENSION; unknown efficiency keys are refused |
| Experimental flags | seven behavior-sensitive settings behind `efficiency` | PROVISIONAL_V2, default off |
| Public API mechanism | `ariadne_engine.api.bind`, `runtime` | INTERNAL |
| Provider moderation helpers | `PROVENANCE`, `DECISIONS` internals | INTERNAL |
| Reasoner adapters | Codex default, Claude opt-in | FROZEN |
| Boreal side of the integration | not shipped here | out of scope; read-only audit only |

## Rules applied

- No internal module name was promoted to a contract merely because a consumer
  might find it convenient.
- Every additive surface ships with a test that fails if the surface disappears
  (`scripts/test-release.py`, `scripts/check.py`).
- The `ariadne` import package remains shared with the GraphQL project only on
  paper; the README states the coexistence rule.
