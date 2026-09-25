# AR-200 / 07 — RISKS

Severity is the risk to the v2 programme, not to a single milestone. Each risk names its evidence and its mitigation, plus a tripwire that would show the mitigation has failed.

## 1. Overengineering risk (highest, because it is self-inflicted)

| Risk | Why it is real here | Mitigation | Tripwire |
|---|---|---|---|
| Building a new engine instead of extracting from working code | 125 + 50 + 15 + 55 + 18 + 29 + 68 deterministic cases already pass on 5 modules with zero dependencies; rewriting discards that evidence | AR-201 moves *existing functions* behind new seams; no module may be rewritten without a failing benchmark case that the rewrite fixes | Any AR-201 commit that deletes working logic and adds more lines than it moves |
| Introducing infrastructure with no measured need | No profiling evidence exists for queues, brokers, databases, or schedulers; Boreal declares decomposition unavailable and runs one worker at a time | 04 §E defers D1–D6 explicitly; a new dependency requires a G2 approval and a benchmark case that fails without it | A PR adding a service, daemon, or datastore without a measured bottleneck |
| Extracting Boreal modules wholesale | `agent/opencode.py` is 1 108 lines pinned to CLI 1.18.31; `coordinator/server.py` is 2 447 lines of application | Extraction is limited to the artifacts in 04 §D with their coupling named; live adapters stay behind a protocol implemented later | v2 gaining an OpenCode/Tauri/React import |
| Design subsystem becoming a second product | The design brief is large; the existing ledgers already cover traceability | AR-202D ships adapters + records + one offline capture fixture; browser tooling stays optional | A rendered-QA implementation that requires a paid service or a bundled browser |
| Architecture-as-artefact | Contracts and invariants are cheap to write and easy to leave unenforced | Every invariant in 03 §6 carries a benchmark case id; AR-201 acceptance requires them to be executable | An invariant with no case, or a case that cannot fail |

## 2. Security and authorization risk

| Risk | Evidence (today) | Mitigation | Residual risk |
|---|---|---|---|
| Agent-writable documents satisfy human gates | TEST_VERIFIED: `security.gate-forgery-in-agents-md` prepares S4A after two document writes; the runtime marks the human decision resolved | `Approval` records bound to revision hashes, `human-cli` channel only, approve-only log (03 §4) | A process running as the same OS user can still write the approval log. **Authority is not containment.** |
| Review independence is unverifiable | TEST_VERIFIED: `security.review-attestation-unverified` — the only enforced difference is one text line | Evidence-bound verdict: reviewer identity, session evidence, context digest, worker-identity comparison (03 §R3) | A self-hosted reviewer running as the same user can be impersonated by anything with write access |
| Path-dependent enforcement | TEST_VERIFIED: `security.creative-gate-bypass` — stage result presence changes whether a gate is applied | One transition choke point + one policy module (03 §3) | Any future command that mutates state outside the choke point must be blocked by review |
| No OS-level isolation; no sandboxing claimed | Neither system has job objects, AppContainer, ACLs or containers (Boreal's own `ENGINE-AUDIT.md` job-object claim is contradicted by its source; Boreal's `V1-SUPPORTED-CONFIGURATIONS.md` says so plainly) | Keep authorization, transaction safety, filesystem reach and process isolation as four separate concepts in all v2 documentation; never describe approval dialogs or worktrees as containment | A malicious worker with write access to the project can still edit files outside the contract until transactions (X5) exist and are enabled |
| Evidence integrity is content-hash only | Ledgers hash artifacts; no signatures, no hash chaining, no append-only proof; absolute paths make ledgers machine-local | Keep hash binding; add the approve-only log and (later) optional signing of approval records | An attacker with write access can rewrite evidence and the hashes that reference it |
| Supply chain of the distribution path | No signature, no TLS pinning, descriptor checksum travels with the artifact, unbounded download buffering, artifact host unconstrained; `dependencies = []` and no third-party imports in shipped tooling (TEST_VERIFIED `distribution.release-tooling-offline`) | H10 hardening; keep zero dependencies; publish signatures when a key exists | Release-account compromise remains reachable |
| Distribution-name collision | `name = "ariadne"` collides with the unrelated GraphQL package; an accidental publish would break environments; the `Private :: Do Not Upload` guard is no longer present in `pyproject.toml` | Do not publish from this worktree; keep the rename decision for AR-205 with a migration plan | Someone publishes anyway; treat as an operational control, not a code control |

## 3. Compatibility and migration risk

| Risk | Evidence | Mitigation | Tripwire |
|---|---|---|---|
| Run-state schema bump strands existing runs | `RUNTIME_SCHEMA = 1` hard-refused (`ariadne.py:269-270`); test `lifecycle.state-schema-mismatch-refused` passes, i.e. refusal works and *migration does not exist* | H5 must land before any schema change (X2 approvals change the schema); `readable_schemas` + explicit migration + pre-migration backup | Any v2 commit that writes a state file with a new schema while `readable_schemas` is absent |
| Installed runtimes pin a frozen seed runtime | Wheel embeds `seed-runtime.zip`; a 1.6.7 launcher installs a 1.6.7 runtime even if `update` would find newer | Do not change the manifest contract; `minimum_bootstrap_version` remains the one-way gate | A v2 runtime requiring a launcher that existing installs do not have |
| Project documents are an implicit API | Packet verification, gate parsing and `handoff_context_problems` all read project markdown structure/sections; packet headers are a stable format | Freeze the documented stable surface (03 §10); keep parsers permissive about extra content, strict about required tokens | A v2 change that rejects a previously valid project document |
| Existing CLI contract is asserted by tests and docs | 26 subcommands, exit codes 0/1/2, calm-token output; `check.py` asserts install URLs and command names in four documents | CLI becomes a thin presentation layer; no command renames in v2; new flags only | A renamed subcommand or a changed exit code without a compatibility note |
| Creative ledger schema evolution | `SUPPORTED_SCHEMA_VERSIONS = (1, 2)` already demonstrates the dual-read pattern for design ledgers | Extend with a third version using the same pattern; never rewrite existing ledgers | A design change that rewrites `creative-evidence.json` in place |
| No rollback for *projects* | `rollback` only restores runtime versions; project state is explicitly untouched (`cli.py:1186` message, and behaviour) | Transactions (X5) give project-level rollback; until then, state the limitation wherever rollback is offered | Documenting v2 rollback as project rollback |

## 4. Performance risk

| Risk | Evidence | Mitigation | Measurement plan |
|---|---|---|---|
| Verification cost grows with delivered context | `current_packet` re-hashes every source and the packet on every CLI call; S3 already delivers 6 sources / 39 KB (measured) | Content-addressed digest cache keyed by (path, size, mtime_ns) that still re-verifies on write; never trust the cache for a *changed* file | Profile `status`/`advance` on a fixture with 50 project documents before/after; benchmark case `perf.verify-packet-cache` |
| Repeated repository traversal | `discover_run_roots` scans the project's parent directory on every project-addressed command; `handoff_context_problems` re-reads four documents per call | Bound the scan to direct children (already) and memoise per invocation | Count `iterdir` calls per command |
| Context duplication | `DESIGN-TASTE.md` and `skills/design-direction.md` are both delivered at S3 and overlap in subject matter; overlap not measured | Measure overlap (token/line diff) before acting; dedupe only if material | `context.overlap-report` measurement case |
| Workspace copying | Boreal copies whole trees including `node_modules` by design (its own status doc); Ariadne does not copy workspaces at all today | If v2 adds workspace isolation, use the bounded-thread-pool pattern with exclusions and measure | Only after the need exists |
| Slow recovery | Not implemented yet in Ariadne; Boreal resolves from destination bytes | Recovery must be O(changed files), not O(repository) | Include in the recovery case timing |
| Theoretical-vs-measured claims | No profiling has been done in AR-200; this document must not be read as a performance report | Any performance claim in v2 requires a before/after measurement on the frozen fixture | A perf claim without numbers is rejected in review |

## 5. Dependency risk

| Risk | Evidence | Mitigation |
|---|---|---|
| Adding browser/tooling dependencies for rendered QA | Ariadne ships `dependencies = []` and its own build backend; the rendered-QA gap is the most tempting place to add Playwright | Fixture capture adapter first (offline, deterministic); real browser tooling is an *operator-approved* optional dependency behind a G2 gate |
| Paid design services | The brief names Mobbin-class services as optional | Never bundle; licence-interface only; `inaccessible` is a valid recorded outcome |
| Porting Boreal's OpenCode coupling | Pinned CLI version, Windows ctypes, process spawn, localhost HTTP | Keep the adapter protocol; implement a live adapter only when a user need is demonstrated and the pinning strategy is decided |
| Python version | `requires-python = ">=3.10"`; code uses `X | Y` unions and `match`-free syntax | Keep 3.10 compatibility; do not adopt 3.12-only syntax without a launcher decision |
| Build backend coupling | Custom backend reads `VERSION`, embeds `seed-runtime.zip`; `check.py` asserts many tokens in `pyproject.toml`/backend/CLI | Any build change must keep `check.py` green; that check is the compatibility contract |

## 6. Boreal-integration risk

| Risk | Evidence | Mitigation |
|---|---|---|
| Two canonical implementations of the same engine | Boreal's engine is a parallel implementation on a product branch; the public Ariadne is the reusable one | Ariadne is canonical for *engine* semantics; Boreal keeps its application layer. Any shared logic moves to Ariadne and Boreal consumes it — never the reverse |
| Accidentally coupling Ariadne to Boreal's persistence | Boreal's store is app-scoped (`<state_root>/engine.json`, per-project dirs) | The Boreal adapter translates between independently versioned contracts; no shared schema module, no shared state directory |
| Contract drift | Boreal's protocol id is `opencode-http-v1` and its JSON-RPC surface is internal | Version-negotiate an engine contract; expose only the Python API/CLI; test the adapter against a fixture, not against a live Boreal |
| Extracting Boreal code that carries app assumptions | Boreal's `transactions.py` imports Boreal's store and knows about Ariadne data homes; `store.py` carries an Ariadne-specific isolation guard | Extraction checklist per artifact (04 §D) names the exact coupling that must be removed; port tests as well as code |
| Reading Boreal results as verified Ariadne behaviour | Many Boreal guarantees are SOURCE_CONFIRMED only, and several reports are stale or contradicted (`ENGINE-AUDIT.md` job-object claim; `STATUS.md` "applying changes … not built" is contradicted by source) | Every Boreal-derived claim in v2 documents must carry its evidence level and its file:line; doc claims are never promoted to verified |

## 7. Programme risks

| Risk | Mitigation |
|---|---|
| Scope creep into AR-201 before AR-200 findings are accepted | AR-200 stops at the handoff; no AR-201 code was written |
| Losing the baseline evidence | Benchmark results, manifests and the two Boreal hash manifests are recorded outside the repositories (`%TEMP%\kilo\ar200\`) and referenced in the deliverables; the benchmark itself is committed in the v2 worktree |
| Silent drift of the untouched checkouts | `the public export checkout` verified clean at `67361f1`; `the private canonical repository` verified clean at `5819dae`; Boreal's concurrent DH-011 session was detected and documented rather than assumed absent |
| Treating one run as a comparison | 06 §5 rule 6: stochastic comparisons need ≥5 runs and identical conditions |
| Documentation outliving its truth | Every v2 document states a scope and an evidence level; a claim that cannot name its evidence is marked INFERRED or NOT_VERIFIED rather than omitted |

## 8. The one risk to re-check first

If AR-201's transition choke point (H2) and approval binding (H1) are not landed before anything else, the two confirmed authorization defects remain reachable while the codebase grows around them, making the eventual fix both larger and riskier. Order matters more than scope here: H5 → H2 → H1/H3 → X4 → X5.
