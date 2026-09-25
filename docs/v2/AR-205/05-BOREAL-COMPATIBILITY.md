# AR-205 — 05 — Boreal compatibility (read-only)

## Boundary

Boreal was to be inspected, never modified. In this environment no Boreal
checkout was present at the usual development locations (`<repository>`), so this
milestone could not re-read its current source. The analysis below therefore
rests on the recorded read-only audit performed during AR-200, quoted in
`docs/v2/AR-200/03-ARCHITECTURE.md`, and on the Ariadne-side contract that AR-205
implemented.

**No Boreal file was created, modified, deleted or tested. No Boreal process was
started, and no Boreal configuration or Git state was touched.** If a future
milestone needs to prove live compatibility, the Boreal checkout must be
supplied and a separate write authorization granted; until then this document
remains `CONTRACT_VERIFIED` only.

## What the recorded audit says Boreal expects

| Concern | Recorded Boreal source | Ariadne v2 answer |
|---|---|---|
| Single transition choke point | `model.py:59-69`, `engine.py:321-335` | `ariadne_engine.statemachine.apply_transition`; all continuations route through it |
| Approval binding | `Approval` model with `subject{type,id,revision,hash}` and liveness | Approval records bind gate, target, revision, identity and channel; stale revisions refuse |
| Review independence | Boreal's review model separates reviewer from implementer | `review` and `verification` bind distinct execution identities |
| Validation fingerprints | `validator.py` fingerprint model | Worker validation records commands, return codes, stdout digests and scope status |
| Journaled transactions | `transactions.py` | Standalone workspace transactions were reviewed; v2 exposes atomic state writes, explicit recovery and per-packet revision binding rather than porting Boreal's journal |
| Reference provenance | `references.py` (EXTRACT candidate) | Reference evidence chain: found → inspected → analysed → used, with stale-artifact detection |
| Agent transport shape | `agent/opencode.py` (1,108 lines, app-coupled) | Deliberately not ported; Ariadne defines a provider-neutral adapter boundary and a versioned consumer protocol instead |

## Ariadne-side adapter

`ariadne_engine.integration.ConsumerAdapter` is the Ariadne-side translation
layer. It offers fourteen operations (see
[04-INTEGRATION-CONTRACT.md](04-INTEGRATION-CONTRACT.md)), refuses an
incompatible protocol up front, and cannot bypass the transition authority: every
mutating operation calls the same engine function the CLI uses.

A Boreal-side adapter would be a thin mapping from Boreal's task/run identifiers
onto `open_project`, `start_task`, `inspect_task`, `approve`, `execute`,
`validate`, `review`, `recover`, `get_events` and `get_evidence`. None of it is
built or required here.

## Compatibility status

| Statement | Status |
|---|---|
| Protocol versioned, range-checked, discoverable | CONTRACT_VERIFIED |
| Unknown fields not treated as authority | CONTRACT_VERIFIED |
| Missing capability refused explicitly | CONTRACT_VERIFIED |
| Adapter cannot fabricate validation, review or approval | CONTRACT_VERIFIED |
| Migration boundary visible to a consumer | CONTRACT_VERIFIED |
| Boreal runtime executes against v2 | BOREAL_LIVE_VERIFIED: NO — not attempted |
| Boreal source unmodified by AR-205 | confirmed by absence of any Boreal path in this worktree and repository |
