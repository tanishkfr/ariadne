# Migrating a v1 project to Ariadne v2

Ariadne v2 reads v1 projects. It does not rewrite one until you ask, and it never
invents authority while doing it.

- **v1 project documents stay where they are.** `PROJECT.md`, `DESIGN.md`,
  `AGENTS.md`, `HANDOFF.md`, `QA.md` and `RESEARCH.md` are read as legacy
  material. A gate note written inside a document remains a note.
- **Legacy project ledgers stay readable.** `.ariadne/creative-evidence.json`
  (schema 1 or 2) and `.ariadne/creative-operations.json` (schema 1) are read
  directly and are not transformed.
- **A pre-engine run state is refused, not guessed at.** If
  `ariadne-run.json` has no `ariadne-engine-1` contract marker, every command
  that would continue the run stops and asks for migration.
- **Nothing is migrated implicitly.** Opening a project, reading status or
  preparing a packet never converts an old file.

## Before you migrate

```bash
python -m ariadne migrate --dry-run --project /path/to/project
```

The dry run prints, without writing anything:

- the run root and the source schema/contract;
- the target record contract;
- every persisted object it found, classified as `READ_DIRECTLY`, `MIGRATE`,
  `LEGACY_READ_ONLY` or `UNSUPPORTED`;
- the transformations an apply would perform;
- the preserved legacy objects;
- the backup path and whether a backup already exists;
- the expected post-migration state, including `approvals created 0`.

If any object is `UNSUPPORTED`, the dry run still succeeds, but an apply refuses
until you resolve it. Nothing is written in that case.

## Apply

```bash
python -m ariadne migrate --apply --project /path/to/project
```

What apply does, in order:

1. verifies the source state and that the plan is still current;
2. copies the pre-migration state to `ariadne-run.v<schema>.bak` (an existing
   backup is never overwritten);
3. writes the migrated state to a temporary file and replaces the state
   atomically;
4. verifies the written state;
5. appends a record to `migration-report.json` beside the run state;
6. writes an operator log entry.

What apply does not do:

- it does not create an approval, a review, a validation, a capability
  observation or an execution;
- it does not promote a document gate mirror into an approval;
- it does not raise the evidence level of anything;
- it does not change the run-state file schema or delete a key.

A migrated run therefore starts with the approvals it already had — and with any
old gate it still needs to be re-granted by a human.

## Rollback

```bash
python -m ariadne migrate --rollback --project /path/to/project
```

Rollback restores the preserved pre-migration bytes while that is honest:

- it succeeds only while the migrated state is byte-identical to what migration
  produced;
- it copies the migrated state aside first as `ariadne-run.v2.bak`, so nothing
  is destroyed;
- it refuses once further v2 work exists, because approvals or transitions
  recorded under v2 cannot meaningfully exist in the v1 file. The refusal names
  what it would discard and leaves both states in place.

There is no rollback for an install upgrade and a project migration at the same
time; those are separate operations. Install rollback is
`python -m ariadne rollback`.

## Legacy evidence

| Object | v2 treatment |
|---|---|
| `.ariadne/creative-evidence.json` schema 1 or 2 | read directly |
| `.ariadne/creative-operations.json` schema 1 | read directly |
| `.ariadne/returns/*.md` | legacy evidence, read-only |
| `PROJECT.md` / `AGENTS.md` / `DESIGN.md` gate notes | mirrors only; never approvals |
| packet `manifest.json` | immutable transport evidence |
| `OPERATIONS.md` | append-only history |
| `ariadne-run.v*.bak` | preserved pre-migration bytes |

Legacy absence stays absence: an unrecorded review is not a review, and an
unrecorded validation is not a validation.

## Decision Plane and economics after migration

The deterministic decision provider works offline immediately; no migration
step is needed for it. Economic records that did not exist in v1 stay unknown —
migration does not backfill invented usage or cost.

The seven behavior-sensitive optimizations from AR-204 are not turned on for a
migrated run or a new one. They stay opt-in until a measured quality comparison
exists, and the release gate fails if a default moves.

## If something goes wrong

```bash
python -m ariadne migrate --dry-run --project /path/to/project
```

The dry run is safe to repeat; it reports the current classification without
writing. `migration-report.json` lists every apply and rollback with the state
digests. If the run state is malformed or has an unsupported schema, migration
refuses and the original file remains byte-identical.
