# AR-205 — 02 — Migration architecture and results

## Design

Migration lives in `src/ariadne_engine/migration.py` and is exposed three ways:
as engine functions (`plan`, `apply`, `rollback`, `report_view`), as runtime CLI
operations (`ariadne migrate --dry-run|--apply|--rollback`), and as API
operations (`plan_migration`, `apply_migration`, `rollback_migration`,
`migration_report`). All three call the same functions, so a consumer cannot
obtain weaker behaviour than an operator.

The transformation itself was already owned by `persistence.migrate_file` from
AR-201: additive record-contract upgrade, backup first, atomic write, no
authority invented. AR-205 adds the release-engineering layer around it:

| Layer | Responsibility |
|---|---|
| `inventory()` | classify every persisted object as `READ_DIRECTLY`, `MIGRATE`, `LEGACY_READ_ONLY` or `UNSUPPORTED` |
| `plan()` | dry run: source/target, transformations, preserved legacy, backup plan, expected post state, blockers |
| `apply()` | refuse on unsupported data, then delegate the write to `persistence.migrate_file`, then record evidence |
| `rollback()` | restore the preserved bytes only while the migrated state is unchanged; preserve the v2 state first |
| `migration-report.json` | durable apply/rollback records with digests and the backup path |

## Classification of persisted objects

| Object | Classification | Action |
|---|---|---|
| `ariadne-run.json` without the engine marker | MIGRATE | additive marker plus one history record |
| `ariadne-run.json` with the marker | READ_DIRECTLY | none |
| `.ariadne/creative-evidence.json` schema 1 or 2 | READ_DIRECTLY | none |
| `.ariadne/creative-operations.json` schema 1 | READ_DIRECTLY | none |
| `.ariadne/**/*.md` evidence | LEGACY_READ_ONLY | none |
| `PROJECT.md`, `AGENTS.md`, `DESIGN.md`, `HANDOFF.md`, `QA.md`, `RESEARCH.md` | LEGACY_READ_ONLY | none; gate mirrors grant nothing |
| packet `manifest.json` | READ_DIRECTLY | none |
| `OPERATIONS.md` | LEGACY_READ_ONLY | none |
| `engine-events.jsonl`, `worker-telemetry.jsonl` | READ_DIRECTLY | none |
| `ariadne-run.v*.bak` | LEGACY_READ_ONLY | never overwritten |
| unknown JSON with a schema marker | UNSUPPORTED | blocks apply until resolved |
| unknown JSON without a marker | LEGACY_READ_ONLY | preserved |
| unreadable ledger | UNSUPPORTED | blocks apply |

## Guarantees and their tests

The AR-205 release suite (`scripts/test-release.py`) and the benchmark cases in
group `migration` cover:

1. dry run writes nothing (file digests compared before and after);
2. classification of run state, ledger, packet manifest and document mirror;
3. apply preserves the pre-migration bytes and the legacy approval list exactly;
4. apply creates no approval, review, validation, capability or transition;
5. repeated apply is a no-op and adds no evidence record;
6. an existing backup is never overwritten (sentinel bytes survive);
7. an unsupported schema is refused before any write;
8. a malformed state is refused before any write;
9. rollback restores the original bytes and preserves the migrated state;
10. rollback after v2-only work is refused and changes nothing;
11. the report contains one apply and one rollback record in order;
12. the runtime CLI exposes all three actions and documents the default.

## Interrupted migration

Writes use the runtime's existing temp-file plus atomic-replace discipline with
retry. A kill between write and replace leaves the previous state intact; the
leftover temporary file is reported by `persistence.recovery_report` as
`interrupted-write` and is never silently deleted. The release tests assert the
report rather than simulating a process kill, which is the honest bound of what
this environment can prove.

## Results

- Migration CLI help, dry run, apply, rollback and refusal paths: **PASS**
  (release suite, 12 cases; benchmark group `migration`, 10 cases).
- Ledger schema lists are compared against `scripts/creative-intelligence.py`
  and `scripts/creative-operations.py` at test time, so they cannot drift.
- No real user project was migrated; all fixtures are synthetic.
