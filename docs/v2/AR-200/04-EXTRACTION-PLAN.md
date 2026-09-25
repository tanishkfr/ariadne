# AR-200 / 04 — EXTRACTION PLAN

All Boreal paths are under
`<path>`
(read-only reference; nothing was copied during AR-200).

Extraction rules applied throughout: (1) copy *design and small pure functions*, never app-coupled modules; (2) anything copied is re-tested inside Ariadne's own deterministic harness before it can affect a release; (3) Boreal's persistence schema is never imported; (4) no extraction may make Ariadne depend on Boreal, OpenCode, Tauri, React, a GUI or a paid API.

## A. KEEP as-is (no work)

| Asset | Location | Why |
|---|---|---|
| Stage/packet compiler | `scripts/prepare-stage.py` (whole file) | Verified: conditional resolution, hash-stamped sections, staleness detection, parent provenance, S5 isolation. Nothing in Boreal is better. |
| Worker lifecycle + repair bounds | `scripts/ariadne.py:203-247`, `2332-2665`, `3569-3619` | Verified by 125 self-tests + 4 new lifecycle cases. |
| Creative/design ledgers | `scripts/creative-intelligence.py`, `scripts/creative-operations.py` | Strict schemas, transition replay, artifact hashing, anchor checks, G2 authority string. Keep the discipline; extend the states (05). |
| Reasoner contract + detection | `scripts/reasoners.py`, `adapters/reasoners.json` | Provider-neutral, evidence-classed, CLI detection with timeouts. |
| Distribution pipeline | `build_backend/ariadne_backend.py`, `scripts/build-release.py`, `src/ariadne/cli.py` | Offline stdlib build, seed runtime, sha256 manifest, atomic skill swap, rollback, doctor, uninstall guards. Verified 55/55 + 18/18. |
| Deterministic test corpora | `scripts/*-self-test` suites, `validation/fixtures/*.json`, `validation/runs/B1` | 15 fixture archetypes (real projects, reasoner flows, social flows) reusable as benchmark inputs. |
| Operator CLI surface | 26 subcommands, exit codes 0/1/2 | Public, documented, asserted. Do not churn. |

## B. HARDEN (existing design, proven gap)

| # | Target | Exact location | Gap (evidence) | Work |
|---|---|---|---|---|
| H1 | Gate enforcement input | `ariadne.py:905-915` (`project_runtime`), `2810`, `3363-3365`, `3495-3500` | Gates read `AGENTS.md`/`DESIGN.md` fields that any project writer can set. TEST_VERIFIED `security.gate-forgery-in-agents-md` = accepted. | Replace with `Approval` records + revision binding (03 §4). Keep the document field as a mirror only. |
| H2 | Single transition choke point | `ariadne.py:3265-3478` (`advance`), `3539-3750` (`prepare_next`), `2332-2412` | Preconditions are re-derived per path; the creative-evidence requirement is enforced by `advance` only when no stage result exists. TEST_VERIFIED `security.creative-gate-bypass` = inconsistent. | One table + one `apply_transition` (03 §3); port Boreal's `model.py:59-69` table shape. |
| H3 | Review independence | `ariadne.py:2668-2694`, `2705-2792` | Independence is a self-written line; no identity, session or context evidence. TEST_VERIFIED. | Require `reviewer_identity`, `review_session_evidence`, `context_digest`; compare reviewer identity to the worker identity in run state. |
| H4 | Packet verification cost | `prepare-stage.py:1657-1747` | Every CLI call re-hashes every source and the whole packet (`current_packet` → `verify_packet`). S3 delivers 6 sources today (39 KB); cost grows linearly with project docs. INFERRED (no profiling yet). | Content-addressed digest cache keyed by (path, size, mtime_ns, inode) with source-hash re-check; measure before/after. Do **not** weaken the hash check — cache only the read. |
| H5 | Run-state schema evolution | `ariadne.py:40`, `261-271`; `build-release.py:119-129` | Hard refusal of any `schema_version != 1`; manifest declares `{min:1,max:1}` but the runtime never consults it on load; no migration exists. TEST_VERIFIED (`lifecycle.state-schema-mismatch-refused`). | Add `readable_schemas`, explicit ordered migrations, pre-migration backup, migration recorded in the event log. |
| H6 | Provider/model identity | `ariadne.py:2237-2301` (ingest of self-reported provider/model) | Provider and model are taken from the worker's own return text; nothing cross-checks them. | Adopt Boreal's requested-vs-reported comparison (`agent/worker.py:429-445`) with an explicit "no report ⇒ not verified" rule. |
| H7 | Capability matrix is dead data | `adapters/reasoners.json:9-26` validated at `reasoners.py:47-91`, never read by a selector | A design stage can run on a provider whose `design-direction` capability is `externally-unverified`. | Make strategy selection consult it; allow override only as a recorded human intervention. |
| H8 | Component registry freshness/verification | `references/capabilities.json`, `creative-intelligence.py:270-309` | Registry is dated and hash-bound but its freshness flag is advisory; no licence/revision verification; `install_authority` enforced by a doc check (`check.py:169-207`), not by code. | Enforce staleness in code; add licence/acquisition verification fields; keep "never installation authority". |
| H9 | Recovery of interrupted engine work | `ariadne.py:261-271`, `3265-3478` | An orphan packet (written but not appended to state) is invisible; there is no repair command. INFERRED from the write order in `prepare_next`. | Add `recover` (orphan packet, interrupted evidence write, interrupted transaction) with a typed report; never invent success. |
| H10 | Distribution integrity | `src/ariadne/cli.py:445-483`, `809-849`, `791-806` | No signature; descriptor checksum travels with the artifact; no TLS pinning; unbounded download buffering; no descriptor↔manifest version equality check. | Add descriptor/manifest version equality + `schema_version`/`product` checks; bound download size; publish detached signature when a key exists. Do not break the current descriptor format. |
| H11 | Telemetry aggregation | `ariadne.py:173-200`, `978-1025` | Usage/cost are unknown unless the provider reports them; nothing aggregates runs, so "cost per verified success" cannot be computed. | Add optional provider-reported usage aggregation and a per-run summary record; keep `unknown` semantics. |

## C. REDESIGN (mechanism changes)

| # | Target | From | To | Justification |
|---|---|---|---|---|
| R1 | Human gates | Document-field parsing | `Approval` records bound to revision fingerprints, `channel` gating, approve-only log | Proven forgery (H1) |
| R2 | Continuation policy | Four ad-hoc preconditions across `advance`/`prepare_next`/`validate_worker`/`ingest_review` | One transition table + one policy module | Proven inconsistency (H2) |
| R3 | Independent review ingestion | Structural text validation | Evidence-bound verdict (identity + session evidence + context digest + worker-identity comparison) | Proven unverifiable independence (H3) |
| R4 | Project mutation | Worker edits project directly; Ariadne detects afterwards | Optional transaction path: propose → approve → apply → rollback with per-file journal | Detect-after is inherently destructive on failure; Boreal's journaled per-file model is strictly safer and already proven by its own tests |
| R5 | "Verified" design evidence | A level label asserted by the author, hashed | Level validated against *instruments*: `code-suggests` (source only), `rendered` (capture artifact with digest + viewport), `observed` (interaction/measurement artifact), `verified` (independent re-run evidence) | Today a worker can label its own JSON `rendered: true` and satisfy the check (Boreal `model.py:129-143`, `draft_worker.py:150-166`) |

R4 and R5 are the only redesigns that change what users do; both are additive (opt-in transaction path, opt-in rendered QA). Everything else is internal.

## D. EXTRACT (from Boreal, with exact locations and adaptation cost)

| # | Boreal artifact | Location | What to take | Coupling to remove | Cost | Compatibility risk |
|---|---|---|---|---|---|---|
| X1 | Transition table + choke point | `model.py:47-69` (`TASK_STATES`, `TASK_TRANSITIONS`), `model.py:383-389` (`assert_transition`), `engine.py:321-335` (`_transition`) | The declarative table and the single-validator pattern | None material: pure data + a 20-line function; drop Boreal state names, keep Ariadne's | S | None (internal) |
| X2 | Revision-fingerprint approvals | `model.py:264-278` (`task_revision_hash`, `direction_revision_hash`), `engine.py:770-880` (`authorization_status`, `approve`), `model.py:183-187` (`REVISION_FIELDS`) | Hash-over-declared-fields binding and `missing/stale/satisfied` liveness | Drop `Engine.` wiring; re-implement against the run state; keep the `identity: asserted-by-caller-not-verified` honesty label | M | Medium: adds `approvals` to run state → schema bump (H5 must land first) |
| X3 | Scope/immutability/sensitive classification | `model.py:291-322` (`normalise_scope`, `scope_problems`, `path_matches`), `model.py:368-380` (`is_sensitive_path`), `validator.py:97-135` (`scope_check`) | Path normalisation and the three-way classification (`repository-conflict` / `dangerous-action` / `out-of-scope`) | Replace Boreal task dicts with Ariadne's contract rows; Ariadne already has an equivalent (`prepare-stage.py:451-589`) — take only the normalisation edge cases (backslashes, `./`) and `fnmatch` caveat documentation | S | None |
| X4 | Fingerprint-pair validation | `validator.py:52-84` (`workspace_fingerprint`), `engine.py:1220-1243` (post-worker equality gate) | "The bytes I validated are the bytes produced" | None; Ariadne's git snapshot is coarser | S | None |
| X5 | Journaled transactions + rollback | `transactions.py` (whole file, 793 lines: `propose` 242-394, `approve` 493-505, `apply` 508-565, `rollback` 568-639, `recover` 642-680, blobs 234-239, `_guard_destination` 152-168, `_preserve_user_versions` 755-763) | Per-file before/after blobs, journal-before-mutation, per-file conflict detection at apply and rollback, `partial-*` states, user-version preservation, destination guard | `store.write_json/read_json` (replace with Ariadne persistence), `_ariadne_data_homes` (Boreal's guard already detects Ariadne homes — keep as data), `git rev-parse HEAD` for `base_revision` (already available) | L | Medium: new on-disk area under the run root; must not touch the project unless the operator opts in |
| X6 | Reference-retrieval adapter (opt-in) | `references.py:323-359` (`HttpsTransport.fetch`), `361-414` (robots), `607-692` (`retrieve`), `440-539` (consent), `232-238` (digest-verified excerpts) | HTTPS-only, consent + domain accumulation, robots respect, size/content-type caps, digest-verified excerpts, `request_contains_project_content == False` | Drop direction/Ariadne store coupling; keep it a pure adapter with an injected transport | M | Low: additive, disabled by default, no new dependencies |
| X7 | Bounded context package for chat continuity | `conversation.py:31-43` (caps 5/18/4000), `162-331` | Cap discipline + untrusted labelling for *continuation* context | Not needed for stage packets; useful if v2 adds a conversational operator surface | S | None (defer unless needed) |
| X8 | Permission broker fail-closed rules | `agent/permissions.py:41-47`, `398-456` (failure codes), `165-266` (truncation ⇒ unsupported) | The rule that a truncated/unsupported request can never be approved, plus stable refusal codes | Drop OpenCode event shapes | M | None (only needed once a live agent adapter exists) |
| X9 | Adapter protocol shape | `agent/opencode.py:323-373` (serve argv/cwd/env), `agent/transport.py:92-155` (SSE reader with poll timeout), `agent/opencode.py:586-611` (reported model), `429-445` (comparison) | The *shape* of a live adapter: launch, health, session, event stream, cancel, identity read-back | Full protocol is pinned to OpenCode CLI 1.18.31; do not port it. Take the interface and the identity-compare rule only. | M | Only if/when a live agent adapter is added; keep behind the `WorkerAdapter` protocol |

**Not to be extracted (with reasons):** `coordinator/server.py` (2 447 lines, the Boreal application itself), `desktop/**` (Tauri/React/Puck), `preview.py`/`gateway.py` (app preview + proxy, product-specific), `drafts.py` (Puck-shaped vocabulary), `visual_edits.py` (useful but Boreal-specific single-element JSX patching; revisit only if v2 owns edits), `routing.py` (Boreal profiles; Ariadne's mode/stage model already covers selection), `worker.py`/`draft_worker.py`/`fixture_agent.py` (test fixtures for Boreal).

## E. DEFER (real gaps, wrong time)

| # | Gap | Why defer | Revisit when |
|---|---|---|---|
| D1 | Distribution/import rename (`ariadne` → something unambiguous) | Breaking change with an installed base; touches console script, backend `NAME`, marker files, skill dir, user-data dir, `product` gate. Product decision, explicitly out of AR-200 scope. | AR-205 (release prep) with a migration plan and a reinstall path |
| D2 | Multi-file atomic apply | Boreal itself does not have it; per-file + journal + conflict preservation is sufficient and honest. | Only with a filesystem snapshot primitive that works on Windows without elevation |
| D3 | Task decomposition / parallel stage execution | No evidence of need; Boreal declares `multi_stage_decomposition=False`; sequential stages are cheap (measured 1.3–15 s per deterministic case; model time dominates real usage). | After model-backed benchmarks show decomposition would reduce cost per verified success |
| D4 | Cross-process locking | Single-writer is currently assumed by both systems and no multi-writer use case exists. Detect concurrent writers and refuse first. | When a server/daemon mode appears |
| D5 | Vector database / semantic retrieval for references | Would add a dependency and a new failure mode for a problem not yet shown to exist; the registry + ledger already provide traceability. | After the design-intelligence benchmark shows recall failures attributable to keyword/registry limits |
| D6 | Cryptographically signed releases | Needs key management and a publish pipeline decision; hardening H10 covers the concrete defects. | AR-205 with a release-signing decision |

## F. Ordering constraints

1. **H5 before X2.** Binding approvals into run state changes the schema; migration support must exist first, otherwise every existing run is stranded (current behaviour: hard refusal).
2. **H2 before H1.** Replacing gate inputs while four separate paths still re-derive preconditions would leave the bypass in place; the choke point must land first.
3. **H3 depends on X4.** Evidence-bound review needs the fingerprint discipline to state *what* was reviewed.
4. **X5 (transactions) after H9 (recovery)** so a partially applied transaction is resolvable from the first day it exists.
5. **R5 (rendered evidence) after H8** so instrument-based evidence can be tied to a verified component/library record.
6. **Nothing in D/E may be started while any invariant I-1…I-12 lacks a passing benchmark case.**
