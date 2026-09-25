# AR-200 / 10 — AR-200 REPORT

Milestone: AR-200 — Baseline, architecture audit and implementation preparation.
Date: 2026-09-22. Runtime audited: Ariadne v1.6.7. Model: deepseek/deepseek-v4.1-flash (this agent). No paid evaluation, no publication, no push.

## 1. What was actually done

| Phase | Result |
|---|---|
| A — Environment discovery | Located all four checkouts (two public, one maintainer, one maintainer dev tree containing Boreal). Verified branches, HEADs, working-tree states, worktrees, remotes, Python and tools. Created the dedicated v2 worktree `<path>` on `v2/ar-200-baseline` from maintainer `5819dae`. |
| B — Public v1.6.7 audit | Read the implementation: `scripts/ariadne.py` (structure + state/gates/validation/review/acceptance/routing, 1 400+ lines read directly), `scripts/prepare-stage.py` (stage table, source resolution, packet build, `verify_packet`, `load_parent`), `scripts/reasoners.py` (all 406 lines), the creative modules' interfaces and ledgers, the distribution surface, and the policy documents. |
| C — Maintainer audit | Byte-level tree comparison: 95 published files, all identical; 42 maintainer-only files, all verification/process assets. No private feature divergence. |
| D — Boreal audit (read-only) | 20-module engine inventory with file:line evidence: models, persistence, state machines, worker/OpenCode adapter, model identity, authorization/permissions, transactions/rollback, review/validation, design subsystem, dependency surface, tests, and doc-vs-code gaps. No Boreal file was modified; its pre-existing uncommitted work was preserved. |
| E — Capability matrix | 22 capabilities across public/maintainer/Boreal/v2 with per-item justification. |
| F — Benchmark | Built a 51-case offline benchmark harness, ran it (270 s), captured machine-readable results, generated a manifest, and measured context sizes. |
| G/H — Architecture + design intelligence | Module map with ownership, contracts, invariants I-1…I-12, error semantics, stability classification; full design-intelligence subsystem specification. |
| I/J — Performance, compatibility, roadmap, handoff | Explicit deferrals with reasons; migration and compatibility risks; AR-201…AR-205 roadmap; implementation-ready AR-201 handoff with stop conditions. |

## 2. Executive findings

1. **v1.6.7 is substantially more real than the brief assumed.** The stage chain, gate checks, hash-stamped context packets, independent command-executing validation, bounded repair budget, evidence immutability, design-evidence ledgers, and the install/update/rollback lifecycle are all implemented and are now TEST_VERIFIED by execution (300+ existing deterministic cases plus 51 new benchmark cases).
2. **The public release is the maintainer product.** All 95 published files are byte-identical to the maintainer tree; the unpublished 42 files are verification assets, not hidden capability.
3. **Three authorization/verification defects are real and reproducible**, and they are the highest-value work for v2:
   - human gates are read from agent-writable documents (G1 forgery succeeds);
   - gate enforcement depends on which continuation path is used;
   - review independence rests solely on a self-written attestation.
4. **Boreal's engine is a credible source of four specific patterns** — a single transition choke point, revision-fingerprint approvals, fingerprint-pair validation, and journaled per-file transactions with rollback — and of nothing else worth porting wholesale. Its application layers (2 447-line coordinator, Tauri/React/Puck front end, OpenCode adapter) are strongly app-coupled.
5. **No infrastructure is needed.** Both systems store JSON files with atomic replace and run one worker at a time; the measured deterministic cost is dominated by subprocess validation, not storage or traversal.
6. **Design intelligence is the largest genuine gap**: provenance, tracing and claim-discipline are implemented, but nothing researches, renders, captures or measures anything, in either system.

## 3. Confirmed capabilities already present (do not rebuild)

Stage chain and legal-transition enforcement; hash-verified context packets with conditional inclusion and recorded omissions; S5 isolation as a verifiable property; independent validation that executes and hashes real commands and classifies scope/immutability/sensitive violations; bounded repairs with blocked-vs-routine classification; evidence non-overwrite; provider-neutral reasoner contracts with capability evidence classes and CLI detection; difficulty×stakes routing recommendations with boundary tests; creative/design ledgers with transition replay, artifact hashing, anchor checks and a deliberately non-installable dependency authority; offline stdlib distribution with a verified manifest, seed runtime, atomic skill swap, rollback, doctor and uninstall guards; unknown-preserving telemetry.

## 4. Important differences between public, maintainer and Boreal

| Dimension | Public v1.6.7 | Maintainer v1.6.7 | Boreal engine |
|---|---|---|---|
| Engine code | 95 files, identical to maintainer | same + 42 verification/process files | separate implementation on `dh/design-harness-*` |
| Stage/state enforcement | four paths re-derive preconditions | same | one transition table + one validator |
| Human gates | document-field parsing | same | typed approval records bound to revision hashes (still self-asserted) |
| Validation | executes commands, git scope check | same | declarative in-process checks, fingerprint equality |
| Transactions/rollback | absent | absent | journaled per-file with conflict preservation |
| Model identity | self-reported in the return text | same | requested-vs-reported comparison from the runtime record |
| Rendered QA | absent | absent | absent (a worker-written `rendered` flag only) |
| Extras | — | validation fixtures, 7 extra suites, readiness records | permissions broker, preview/gateway, references adapter, Puck drafts |

## 5. Capabilities that genuinely need implementation

In priority order: (a) approval binding + a single transition choke point (AR-201); (b) evidence-bound review verdicts (AR-201/AR-203); (c) explicit state-schema migration (AR-201); (d) content-addressed context verification and an omission report (AR-202); (e) executable routing/identity verification and interrupted-work recovery (AR-202); (f) rendered QA instruments and reference retrieval with the extended provenance states (AR-202D); (g) transactions/rollback extraction (later, after recovery); (h) distribution integrity hardening and the rename/signing decision (AR-205).

## 6. Proposed v2 architecture (summary)

`contracts · statemachine · policy · events · context · routing · worker · recovery · validation · review · provenance · design/ · workspace · adapters/ · api · cli · persistence`, with the existing scripts preserved as the canonical runtime and the new package built by moving logic behind those seams. Stable: on-disk paths, CLI commands and exit codes, packet headers and manifest keys, stage and gate names. Provisional: the Python API, adapter protocols, design records, any Boreal contract. Invariants I-1…I-12 each carry a benchmark case id. Full detail in `03-ARCHITECTURE.md`.

## 7. Design-intelligence architecture (summary)

Five-state provenance (`FOUND → ACCESSIBLE → INSPECTED → ANALYSED → USED`, with `INACCESSIBLE` terminal and blocker-required), with visual-vs-interaction inspection as a typed distinction; opt-in, consent-gated reference adapters (local, project document, approved URL, official API, MCP, paid library) that never scrape gated sources and never install; component evaluation records covering compatibility, accessibility, licence, dependencies, maintenance and design fit against the existing minimum-solution ladder; requirement → decision → implementation → evidence closure; four separated QA activities (functional, accessibility, visual regression, independent judgement) with an offline fixture capture adapter and `rendered`/`observed`/`verified` bound to artifacts rather than labels; bounded, defect-scoped refinement with regression re-runs and a shared repair budget. Full detail in `05-DESIGN-INTELLIGENCE.md`.

## 8. Benchmark implementation and results

`benchmarks/` (51 cases, 7 groups; stdlib only; offline). AR-200 run: **45 pass, 3 fail, 1 observed, 0 error, 2 declared-skip, 270 s, 0 model calls, cost 0.00**. The three failures are the confirmation of §2.3. Measured context: S1 21 889 bytes / 2 sources; S3 39 252 bytes / 6 sources. Twelve runtime-backed and eight design-runtime cases are specified but NOT executed (they require provider budget and, for some, network); they are enumerated in `06-BENCHMARKS.md` §6 with their comparability limits.

## 9. Compatibility and migration risks (summary)

Run-state schema is hard-refused outside version 1 with no migration ⇒ any schema bump strands existing runs (mitigate: `readable_schemas` + explicit, reversible, backed-up migration before the approvals schema lands). The public CLI/paths/packet format are an implicit API and are frozen. Installed runtimes pin a frozen seed runtime, so launcher/runtime version pairing matters. Distribution has no signature, no TLS pinning, no descriptor↔manifest version equality check, and a name collision with an unrelated PyPI package (deferred rename). Approval binding is authorization, not isolation — no OS containment exists and none may be claimed. Full detail in `07-RISKS.md`.

## 10. Refined milestones

AR-201 executable orchestration core (transitions, approval binding, schema migration, evidence-bound review, Python API) → AR-202 adaptive context/routing/recovery → AR-202D design intelligence → AR-203 independent-verification hardening → AR-204 measurement-driven performance → AR-205 integration and release preparation. Each milestone has objective, dependencies, exact scope, reuse, deliverables, acceptance tests, required evidence, risks and out-of-scope stated in `08-ROADMAP.md`.

## 11. Exact AR-201 starting point

Worktree `<path>`, branch `v2/ar-200-baseline` (or `v2/ar-201-core` from it), base commit `5819dae3cb8f216dac3abc77bd8429a4a73a4343`. Seven ordered tasks, four new benchmark cases, eight stop conditions and an explicit anti-goal list are in `09-AR-201-HANDOFF.md`. The three failing security cases define success; they must flip to `pass` without weakening any hash, scope or evidence check.

## 12. Files created or modified by AR-200

Created in the v2 worktree (all new; no existing file was modified except the worktree registration in the maintainer repository):

```
docs/v2/AR-200/01-BASELINE.md
docs/v2/AR-200/02-CAPABILITY-MATRIX.md
docs/v2/AR-200/03-ARCHITECTURE.md
docs/v2/AR-200/04-EXTRACTION-PLAN.md
docs/v2/AR-200/05-DESIGN-INTELLIGENCE.md
docs/v2/AR-200/06-BENCHMARKS.md
docs/v2/AR-200/07-RISKS.md
docs/v2/AR-200/08-ROADMAP.md
docs/v2/AR-200/09-AR-201-HANDOFF.md
docs/v2/AR-200/10-AR-200-REPORT.md
docs/v2/AR-200/adr/ADR-0001-evolve-from-baseline.md
docs/v2/AR-200/adr/ADR-0002-approval-records.md
docs/v2/AR-200/adr/ADR-0003-evidence-bound-review.md
docs/v2/AR-200/adr/ADR-0004-journaled-transactions.md
docs/v2/AR-200/adr/ADR-0005-instrument-backed-design-evidence.md
docs/v2/AR-200/adr/ADR-0006-no-new-infrastructure.md
benchmarks/README.md
benchmarks/run_benchmarks.py
benchmarks/manifest.json
benchmarks/arbench/__init__.py
benchmarks/arbench/driver.py
benchmarks/arbench/fixtures.py
benchmarks/arbench/cases.py
benchmarks/results/<timestamped runs + LATEST.json>
```

Outside the repositories (evidence only): `%TEMP%\kilo\ar200\{public-tree.txt, maintainer-tree.txt, cmp_trees.py, boreal-manifest-start.tsv, boreal-manifest-end.tsv, boreal-git-status-{start,end}.txt}`.

## 13. Tests executed and results

Existing suites, all re-run in this worktree and passing: `check.py --self-test` (18 embedded suites), `ariadne.py --self-test` 125/125, `prepare-stage.py --self-test` 50/50, `reasoners.py` 15/15, `check.py` 18 ok/0 fail, `validate.py --self-test` 29/29, `test-distribution.py` 55/55, `build-release.py --self-test` 18/18, `test-real-projects.py` 29/29, `test-social-intelligence.py` 68/68, `test-writing-architecture.py`, `test-writing-execution.py` (exit 0), `validate.py --benchmark` (1 recorded run).

New benchmark: 45 pass / 3 fail / 1 observed / 0 error / 2 skip (see §8). Not executed and reported as such: `test-reasoner-rollback.py` (requires two built release bundles), `test-wheel-install.py` (requires pip/venv), all 20 planned model-backed/design-runtime cases, and every Boreal test (read-only constraint).

## 14. Known limitations and unverified claims

- **Boreal is SOURCE_CONFIRMED only.** No Boreal test, build or workflow was executed. Its live OpenCode round-trip, packaging/sidecar behaviour, and the DH-011 work in progress are NOT_VERIFIED.
- **Boreal changed during the AR-200 window without AR-200 doing it.** A concurrent DH-011 session modified files and added screenshots throughout the window (git status 43 → 81 entries by the final check; `cargo`/`node` processes started 18:54 local). The pre-existing-work check passed: no status entry from the start snapshot disappeared, `HEAD` is still `b2fe0e0`, the branch is unchanged, the reflog shows no new commits, and `.git/index` mtime predates this session. The two hash manifests are retained as evidence.
- **No model-backed measurement exists.** Success rate, cost per verified success, token usage and model-selection accuracy are UNKNOWN for v2, v1 and Boreal. The three defects were reproduced with deterministic fixtures, not with model workers; the same behaviours still need confirmation against a real provider run (AR-202).
- **No profiling was performed.** Performance statements are structural observations plus one measured packet size, not measurements of runtime cost.
- The Boreal `ENGINE-AUDIT.md` claim that Windows Job Objects bound the process tree is contradicted by Boreal's source and by its own status document; it must not be repeated as fact.
- The `test-wheel-install` path (wheel build + isolated install) was not executed, so the published wheel's build is REPORTED (from readiness documents), not re-verified here.

## 15. Git status and local commits

- v2 worktree: all changes are new files; exact `git status` and the commit hash are recorded in the final response section below and in the commit message.
- `the public export checkout`: unmodified, `67361f1`, clean.
- `the private canonical repository`: unmodified at `5819dae`; the only change is the added worktree registration (`git worktree list`), which is intended and reversible.
- `<worktree>` (Boreal): unmodified by AR-200; concurrent DH-011 work preserved and documented.
- No push, no tag, no release, no remote interaction of any kind.

## 16. Next action

Accept or amend AR-200, then execute AR-201 from `09-AR-201-HANDOFF.md` starting with T1 (`contracts.py` + `persistence.py` + explicit migration), because the approvals schema change depends on it. Do not start AR-201 inside AR-200: it was not begun.
