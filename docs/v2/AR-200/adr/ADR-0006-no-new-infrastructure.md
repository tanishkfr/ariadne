# ADR-0006 — No new infrastructure; deterministic offline core

Status: accepted (AR-200)
Deciders: AR-200 audit
Evidence: 06-BENCHMARKS.md (270 s for 51 cases, 0 model calls, 0 network); 07-RISKS.md §1

## Context
v1.6.7 is five stdlib modules with no dependencies, no daemon, no database and no network use outside the installer's HTTPS download. Boreal, the more recent system, also runs one worker at a time, declares `multi_stage_decomposition` unavailable, performs no inter-process locking, and stores everything as JSON files with atomic replace. The measured costs that exist today are millisecond-scale file work next to second-scale subprocess validation and (in real use) model latency.

## Decision
v2 adds no database, message broker, scheduler, vector store, service, or daemon. Persistence stays versioned JSON plus append-only logs, with the content-addressed blobs and journal that the transaction work (ADR-0004) requires. Any future infrastructure addition must be justified by a measured bottleneck from a benchmark case, and must not break the offline deterministic mode.

## Alternatives considered
- **SQLite for state.** Rejected for now: it would add a migration and locking surface without a measured need, and current state files are tiny. Reconsider only if a measured case shows file-scan or atomicity limits.
- **A vector database for reference retrieval.** Deferred (04 §E D5): the registry + ledger already provide traceability; recall failures attributable to the current model have not been demonstrated.
- **Parallel stage execution / decomposition.** Deferred (04 §E D3): no evidence of need; sequential stages are cheap relative to model time.

## Consequences
- Recovery, transactions and telemetry must all work as plain file operations.
- Performance work in AR-204 must be measurement-driven, never structural speculation.
- The engine remains embeddable and usable with no external service, which is also what makes a future Boreal adapter low-risk.
