# ADR-0002 — Human gates are approval records bound to revision fingerprints

Status: accepted (AR-200) — drives AR-201
Deciders: AR-200 audit
Evidence: 01-BASELINE.md §7 defect 1; 06-BENCHMARKS.md (`security.gate-forgery-in-agents-md` = fail)

## Context
G1 and G3 are currently enforced by reading `**Last gate passed:** G1` out of `AGENTS.md` and `**Status:** locked at G1` out of `DESIGN.md` (`ariadne.py:905-915`, `3363-3365`, `3498`, `2810`). Both files are written by the same actors that implement the work. A benchmark case proved that writing those two fields plus one `record-result` call prepares S4A and causes the runtime to record the human creative decision as *resolved*.

Boreal's engine binds approvals to a hash over declared revision fields and re-checks liveness (`missing|stale|satisfied`), while honestly labelling the record `identity: asserted-by-caller-not-verified`.

## Decision
Introduce `Approval` records: `{gate, subject{type,id,revision_hash}, identity, channel, note, recorded_at}`, appended to an approve-only log in the run root. Only `channel == "human-cli"` satisfies a gate, and a gate is satisfied only when `revision_hash` matches the current subject. `AGENTS.md`/`DESIGN.md` gate fields become human-readable mirrors written after approval and are never read for enforcement.

## Known limitation (explicit)
This is *authorization*, not *isolation*. A process running as the same OS user can still write the approval log. OS-level containment (job objects, AppContainer, containers) is out of scope and must not be claimed anywhere in v2 documentation.

## Consequences
- Run state gains an `approvals` array ⇒ schema version bump; AR-201 must land migration support first.
- Editing an approved direction invalidates G1 instead of silently inheriting it.
- The CLI gains one command (`approve-gate`); no existing command or exit code changes.
