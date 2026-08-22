# Builder OS V1 productionization — operations log

**Started:** 2026-08-23  
**Branch:** `codex/v1-productionization`  
**Baseline:** `06d290655cd5e0e575b59fc0354591a94260d2bc`  
**Rollback point:** the baseline commit above; historical untracked validation evidence is preserved

This log explains the hardening run in operator language. Runtime project logs
use the same principles but are generated per project outside the project
repository.

## Baseline

- Tracked Builder OS source was clean.
- Historical validation directories A1, A2, A3, A3R1, and B1 were untracked and
  intentionally preserved.
- `python scripts/check.py`: PASS.
- `python scripts/check.py --self-test`: PASS.
- `python scripts/validate.py --self-test`: PASS, 29 guards.
- `python scripts/prepare-stage.py --self-test`: PASS, 20/20.
- Test B closure: PASS WITH PROVIDER-QUOTA EVIDENCE EXCEPTION.

## Prioritised V1 backlog

| Priority | Problem | Evidence | Smallest owner |
|---|---|---|---|
| P0 | No calm entry point or controller; the operator still runs stage commands and tracks paths | Test B transport ceremony | repo-scoped `builderos` skill plus `scripts/builderos.py` |
| P0 | No structured external return handoff or deterministic ingestion | Test B stopped before Cursor-to-Codex return | return template, S4B transport, runtime validator |
| P0 | External provider availability/quota is not checked before a large handoff | Cursor Hobby quota ended B1 mid-build | runtime provider preflight, recorded in operations state |
| P1 | Transcript and parent lineage are correct but operator-facing | repeated B1 continuation work | runtime state discovery and automatic parent selection |
| P1 | Operations history is split across chat, continuation files, and run records | Test B closure reconstruction | generated human-readable per-run operations log |
| P1 | S4A tells the operator to construct S4B manually | B1 handoff/transport friction | calm S4A transition through the runtime controller |
| P2 | Existing checks do not cover runtime routing, preflight, return ingestion, or log integrity | no runtime existed | negative-tested runtime self-test plus repository guard |
| P3 | Getting-started and daily docs expose internal stage machinery | operator fatigue in Test B | document the implemented controller workflow |

## Decisions and boundaries

- `ROUTER.md` semantics and `WORKFLOW.md` gate semantics remain unchanged.
- The packet generator remains the transport and provenance owner.
- The runtime controller is an operator convenience layer, not a second policy
  system.
- Creative direction, dependency approval, external account actions, shipping,
  and publishing remain human decisions.
- Provider behaviour that was not observed will remain labelled externally
  unverified.

## Work log

### 2026-08-23 — baseline and runtime design

**Why:** Test B proved the packet contract but exposed deterministic operator
friction and a missing provider-return boundary.

**Action:** Established the green baseline, created the isolated V1 branch, set
the repository-local commit identity to `tanishkfr`, and selected a thin runtime
controller as the smallest owner.

**Next:** implement and negative-test the controller, entry skill, provider
preflight, return handoff, and generated operations state.
