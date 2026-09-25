# ADR-0008 — Run-state file schema stays 1; the record contract is versioned instead

Status: accepted (AR-201) — supersedes the "schema version bump" consequence of ADR-0002
Deciders: AR-201 implementation
Evidence: `benchmarks/results/ar-200-20260922T185718.json` (AR-200 baseline),
`ar-200-20260922T201711.json` (AR-201 final), `benchmarks/arbench/cases.py`
(`lifecycle.start-creates-verified-s1`, `lifecycle.state-schema-mismatch-refused`),
`scripts/cli.py:project_compatibility`, `scripts/build-release.py:runtime_manifest`

## Context

ADR-0002 concluded that adding an `approvals` array implies a run-state schema bump, and
the AR-201 handoff specified `SCHEMA_RUN = 2` ("the schema this runtime WRITES") with
`READABLE_RUN_SCHEMAS = (1, 2)`.

Implementing that literally breaks two original benchmark cases that the same handoff
claims still pass:

* `lifecycle.start-creates-verified-s1` asserts the persisted
  `ariadne-run.json["schema_version"] == 1` after `start`.
* `lifecycle.state-schema-mismatch-refused` rewrites a fresh state with
  `schema_version = 2` and asserts the runtime refuses it with "schema is unsupported".
  If `2` is the version this runtime writes, the mutated state is readable and both the
  refusal and the case's premise disappear.

It also strands existing runs: the published v1.6.7 runtime
(`src/ariadne/cli.py`, `project_compatibility`) and the release manifest declare
`project_state_schema {min: 1, max: 1}`, and the runtime's reader hard-refuses any other
version. AR-200's own risk register lists "run-state schema is hard-refused outside version
1 with no migration ⇒ any schema bump strands existing runs".

## Decision

* `ariadne-run.json` keeps `schema_version = 1` (`contracts.SCHEMA_RUN`). AR-201 adds
  fields; it does not replace the format. The declared release range stays `min 1, max 1`.
* The new authority lives in **records** inside the state, versioned separately:
  `contracts.SCHEMA_RECORD = 2`, carried by every approval, review, transition and
  migration entry as `schema_version`. Readers accept `1..2`
  (`READABLE_RECORD_SCHEMAS`) and refuse anything else, so an unknown record can never be
  interpreted leniently.
* A state without the engine contract marker is refused until the operator runs an explicit
  `--migrate`; migration is additive, backed up (`ariadne-run.v<n>.bak`), recorded in
  `migration_history`, idempotent and never creates an approval.

## Consequences

* Existing runs stay readable by both this runtime and published v1.6.7 (which ignores the
  added fields). No user state has to be migrated to keep working.
* Authorization still fails closed for legacy runs: their document gate fields are not
  converted, so a migrated run must re-obtain any human gate it still needs.
* A future format change that genuinely cannot be expressed additively needs its own ADR,
  a reader plan and a migration whose `READABLE_RUN_SCHEMAS` change is explicit.
* `--migrate` is an optional flag on run-selecting commands; no existing argument, exit code
  or output text changes.
