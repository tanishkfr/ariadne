# ADR-0001 — v2 evolves from the maintainer baseline in place

Status: accepted (AR-200)
Deciders: AR-200 audit
Evidence: 01-BASELINE.md §2, §3; 04-EXTRACTION-PLAN.md §A

## Context
The public v1.6.7 tree is byte-identical to the maintainer tree for all 95 published files; the maintainer adds 42 verification/process files. The runtime is five stdlib-only modules with 300+ passing deterministic cases. The published layout (`scripts/ariadne.py`, `<project>/.ariadne/*`, sibling run root, 26 CLI subcommands) is already a compatibility surface asserted by tests and documentation.

## Decision
v2 evolves from the maintainer `master` baseline inside the existing repository layout. New engine modules are added under `src/ariadne_engine/`; existing scripts keep their paths, subcommands and exit codes and delegate to the new modules.

## Alternatives considered
- **New isolated engine package alongside v1.** Rejected: creates two canonical implementations, forces every fix to be made twice, and discards 300+ passing cases. Would be justified only if the existing layout could not carry the new contracts, which the audit did not support.
- **Fork the runtime under a new name.** Rejected for AR-201: a rename is a breaking change for installed runtimes and projects; deferred to AR-205 (04 §E D1).

## Consequences
- Every moved function must keep its tests; behaviour change is limited to the two hardened gates.
- The on-disk paths, packet format and CLI remain stable contracts.
- v2 must keep 3.10 compatibility and zero dependencies.
