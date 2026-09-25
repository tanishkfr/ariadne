# ADR-0004 — Project changes go through journaled per-file transactions

Status: accepted (AR-200) — drives AR-202/AR-205 (not AR-201)
Deciders: AR-200 audit, from Boreal's implementation
Evidence: 04-EXTRACTION-PLAN.md §D X5; Boreal `transactions.py:242-680`, `755-763`

## Context
Ariadne has no transaction layer: the worker edits the project directly and Ariadne can only detect out-of-scope or immutable changes afterwards. On failure there is nothing to undo. Boreal implements propose → approve → apply → rollback with before/after content blobs, a journal entry written *before* every mutation, per-file conflict detection at apply *and* rollback, first-class `partial-apply`/`partial-rollback` states, and conflict preservation that never clobbers user edits. Boreal explicitly documents that multi-file writes are not atomic and does not pretend otherwise.

## Decision
Extract Boreal's per-file transactional model into `workspace.py`, adapted to Ariadne's persistence: content-addressed blobs under the run root, `journal.jsonl` written before each mutation, per-path scope/immutability/sensitivity re-checks at apply, `tx_hash` bound to the approval, per-file conflict detection, and preservation of unrecognized destination state in a `conflict/` directory. No git-based undo (git remains read-only and is used only for the `base_revision` label, as Boreal does). Multi-file atomicity is explicitly not promised.

## Alternatives considered
- **Git-based rollback (stash/checkout).** Rejected: it can destroy unrelated user work, depends on the destination being a clean repository, and Boreal already rejected it with a recorded ADR.
- **Whole-tree snapshot copies.** Rejected: Boreal measured/rejected tree copies as expensive, and Ariadne must not copy `node_modules`-scale trees.
- **No transactions (status quo).** Rejected: detect-after is destructive on failure, and the extraction cost is moderate because the algorithm is already implemented and tested elsewhere.

## Consequences
- AR-201 excludes this work deliberately (handoff §7) so gates and transitions land first.
- Recovery must exist before or with transactions so a partially applied transaction is resolvable from day one (`04 §F` ordering).
- The project is only touched when the operator opts into the transactional path.
