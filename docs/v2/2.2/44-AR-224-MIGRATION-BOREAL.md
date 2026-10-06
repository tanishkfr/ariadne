# AR-224 Migration and Boreal Conformance

## 2.1 to 2.2 migration

Uses existing v2 migration machinery (`plan`/`apply`/`rollback`).

Covers existing state compatibility, new acceptance state, receipt store
(`proof_receipts`, additive/optional, no forced migration), new schemas,
Decision Runtime profiles, design/reference records, API additions.

Supports dry run, apply, rollback where the existing contract supports
rollback. Migration never destroys 2.1 state silently; representative
2.1 fixture/state is tested and the exact result recorded in the closure
report.

## Boreal consumer contract

Boreal is untouched. Validation checks the existing Ariadne consumer
contract against 2.2 and returns PASS or specific incompatibilities.
A later Boreal phase can consume 2.2.
