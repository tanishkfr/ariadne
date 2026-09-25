# AR-201 — 03 MIGRATION

Schema changes, legacy compatibility, migration behaviour, failure handling and rollback
for the AR-201 orchestration core.

## 1. What changed, and what deliberately did not

AR-201 adds fields to the run state and a set of versioned **records** inside it. The
run-state **file** version does not change.

| Item | Before (v1.6.7 / AR-200 baseline) | AR-201 |
|---|---|---|
| `ariadne-run.json` `schema_version` | `1` | `1` (unchanged) |
| Reader accepts | `1` only | `1` only |
| New fields | – | `approvals[]`, `reviews[]`, `transitions[]`, `migration_history[]`, `engine{contract,run_schema,record_schema,readable_run_schemas,written_at}`, `last_transition` |
| Record contract version | – | `2` (`contracts.SCHEMA_RECORD`), carried by each record as `schema_version` |
| Gate authorization | document fields (`DESIGN.md`, `AGENTS.md`) | bound approval records; document fields are mirrors |
| Writes | `write_json` per call site | `persistence.write_state` (atomic, normalising) |

Why the file version was not bumped (deviation 1 in `01-IMPLEMENTATION.md`): bumping it
would (a) break `lifecycle.start-creates-verified-s1`, which asserts the persisted
`schema_version == 1`, (b) break `lifecycle.state-schema-mismatch-refused`, which asserts
that a state claiming `2` is refused, and (c) strand every existing run for the published
runtime, whose reader hard-refuses any version other than `1`. Keeping the file version and
versioning the records preserves "state that cannot be read under the running schema is
refused, never silently migrated" (AR-200 invariant I-10) while remaining additive for
existing users.

## 2. Read policy (`persistence.load_state`)

| Input | Behaviour |
|---|---|
| version not in `READABLE_RUN_SCHEMAS` | refuse: `Run state schema is unsupported` (exit 1). No guessing, no migration |
| version readable, structurally invalid (`run_id`, `project`, `packets` missing; malformed packet entry; wrong list type) | refuse: `Run state is malformed: …` (exit 1) |
| version readable, no `engine` marker or an older record schema (a pre-AR-201 or migrated-only-later state) | refuse until `--migrate` is given explicitly: `Run state was written before the ariadne-engine-1 record contract; … Re-run with --migrate` (exit 1) |
| version readable and current | load; nothing is written |

Malformed *records* do not brick a run: an approval that fails `contracts.approval_problems`
is ignored at gate time and named in the refusal, so authorization fails closed without
making the run unreadable. Reviews are validated at ingestion and on use.

## 3. Write policy

`persistence.write_state(run_root, state)`:

1. normalises the fields the engine owns (`approvals`, `migration_history`, `transitions`,
   `engine` with the contract name, file schema, record schema and readable set);
2. serialises to a unique temp file in the same directory;
3. replaces atomically with retry (Windows sharing violations), then removes the temp file.

An interrupted write therefore leaves either the previous state or the new state, never a
partial one.

## 4. Migration

**Boundary.** Migration happens only during an explicit operation: any run-selecting
command with `--migrate` (`status --migrate`, `prepare-next --migrate`, …). Reads never
migrate; nothing migrates on import; no project, installation or published runtime is
migrated automatically.

**Steps** (`persistence.migrate_file`):

1. read and validate the file (unreadable schema refuses before anything is written);
2. if the state already carries the current contract, return unchanged (idempotent);
3. copy the original to `ariadne-run.v<version>.bak` — an existing backup is never
   overwritten, so the earliest pre-migration bytes are preserved;
4. `persistence.migrate(state, from, to)` returns a *copy* with the additive fields and
   appends one `migration_history` entry (record schema, kind, source file schema, source
   and target record schema, engine contract, timestamp, approvals preserved, approvals
   created = 0, and the note that document gates are not converted);
5. validate the result and write it atomically;
6. append an operator log entry and a `state-migration` telemetry event.

**What migration does not do.** It never converts a `DESIGN.md`/`AGENTS.md` gate field into
an approval; it never deletes or renames a key; it never changes the run-state file
version; it never creates a review record or a validation record. A migrated run therefore
begins with `approvals: []` and must re-obtain any human gate it still needs
(`security.migrated-legacy-gate-refused` asserts this).

**Idempotency.** A second `--migrate` on an already-current state writes nothing
(`migrated: false`), and the history keeps exactly one entry per real migration
(`lifecycle.schema-migration-explicit` asserts both).

**Failure handling.**

| Failure | Result |
|---|---|
| unreadable schema version | refused before any write; no backup, no change |
| malformed state | refused before any write |
| interruption between backup and replace | the live file is still the legacy one; re-running `--migrate` completes (the existing backup is kept) |
| interruption during the replace | the atomic replace leaves the legacy or the migrated file, never a partial file |
| the migrated state would be invalid | `ContractError` before writing; the live file is untouched |

## 5. Rollback

Migration is reversible by restoring the preserved backup:

```
copy /Y <run-root>\ariadne-run.v1.bak <run-root>\ariadne-run.json
```

The restored state is the exact pre-migration bytes (asserted by
`lifecycle.schema-migration-explicit`, which compares the backup byte-for-byte with what it
wrote). Because the file version did not change, a rollback does not require an older
runtime; it only removes the new records. Removing the new records cannot grant authority:
approvals are additive evidence, and their absence denies a gate rather than opening one.

## 6. Recovery

`persistence.recovery_report(run_root)` (also reachable as
`ENGINE_API.recovery_report`) reports the persisted state without inferring success:

* `interrupted-write` — a leftover `.<state>.*.tmp`; the live state is the previous one;
* `orphan-packet` — a packet directory the state does not list (for example a crash between
  writing the packet and appending it to state). It is **not** adopted: the packet may
  belong to an abandoned attempt, and adopting it would record a transition that never
  happened;
* `missing-packet` — the state names a packet that is not on disk.

`status: "diverged"` and exit code 2 in the API when anything is found; `"clean"` otherwise.
The report is read-only. `lifecycle.recovery-reports-interrupted-work` asserts the report,
the absence of adoption and that the run keeps working afterwards.
