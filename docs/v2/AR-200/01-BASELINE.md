# AR-200 / 01 — BASELINE

Status: complete for AR-200. Every statement carries an evidence level and a source.
Evidence levels: SOURCE_CONFIRMED · TEST_VERIFIED · LIVE_VERIFIED · DOCUMENTED · REPORTED · INFERRED · NOT_VERIFIED · MISSING.

## 1. Repositories and worktrees (Phase A)

Discovered by direct inspection on 2026-09-22 (no names assumed from reports).

| Role | Path | Git HEAD | Branch | State |
|---|---|---|---|---|
| Public Ariadne (canonical v1.6.7 checkout) | `<path>` | `67361f18cc8d6c205e69b2cfeb852a3708875960` | `master` (tracking `origin/master`) | clean; `git describe` = `v1.6.7` |
| Public Ariadne (stale export) | `<path>` | `aa5ed1e` ("release: Ariadne 1.6.3 social creative contract") | `master` | clean, **one release behind**; not used |
| Maintainer Ariadne | `<path>` | `5819dae3cb8f216dac3abc77bd8429a4a73a4343` | `master` | clean, no extra worktrees |
| Maintainer DH dev + Boreal (read-only) | `<path>` | `b2fe0e0` (29 commits beyond `master`) | `dh/design-harness-2026-09-19` | **dirty by design**: DH-011 work in progress (see §5) |
| **ARIADNE V2 WORKTREE (created by AR-200)** | `<path>` | `5819dae…` | `v2/ar-200-baseline` | this deliverable set |

- EV source: `git status --short --branch`, `git log --oneline`, `git worktree list`, `git rev-parse` in each path. SOURCE_CONFIRMED.
- The private/maintainer repository is a *separate clone* with divergent commit hashes for the same release label: `master`/`v1.6.7` = `5819dae` in maintainer vs `67361f1` in public. Neither repository's object database contains the other's commit (`git cat-file -t` fails in both directions). SOURCE_CONFIRMED.
- The `dh-dev` checkout shares maintainer history (`merge-base master HEAD` = `5819dae`), so it is a normal clone, not an independent repository. SOURCE_CONFIRMED.
- Remotes (informational only; nothing was fetched or pushed): maintainer `origin=https://github.com/tanishkfr/the private canonical repository`, `public=https://github.com/tanishkfr/ariadne.git`; public `origin=https://github.com/tanishkfr/ariadne`. SOURCE_CONFIRMED.
- Existing v2 branches: none in any repository (`git branch -a`). The new branch `v2/ar-200-baseline` was chosen because it did not exist. SOURCE_CONFIRMED.
- No repository overlaps, shared worktrees, or cross-repository path dependencies were found. `<path>` is **not** a git repository (empty directory). SOURCE_CONFIRMED.

### Starting point

```
v2 baseline commit : 5819dae3cb8f216dac3abc77bd8429a4a73a4343  (maintainer "Release Ariadne v1.6.7")
v2 branch          : v2/ar-200-baseline
worktree           : <path>   (created with `git worktree add -b`)
```

The public release was not modified: `the public export checkout` remains at `67361f1`, working tree clean, tags untouched. The maintainer checkout remains at `5819dae` on `master`; the only change to it is the added worktree registration (expected and reversible with `git worktree remove`).

## 2. Public v1.6.7 — what it actually is

95 tracked files (`git ls-tree -r --long HEAD`), all byte-identical to the same paths in the maintainer tree. SOURCE_CONFIRMED.

- **Runtime controller**: `scripts/ariadne.py` (5 785 lines, 259 KB) — one module holding the state machine, gate checks, packet verification, worker lifecycle, validation, review ingestion, acceptance, routing recommendations, telemetry and a 125-case self-test.
- **Context transport**: `scripts/prepare-stage.py` (2 600 lines, 123 KB) — stage specification table, conditional source resolution, hash-stamped packet build, manifest, verification, `worker` contract extraction, scope checking, 50-case self-test.
- **Reasoner adapters**: `scripts/reasoners.py` (406 lines) + `adapters/reasoners.json` — provider-neutral contract, capability evidence classes, CLI detection, 15-case self-test.
- **Design/creative ledgers**: `scripts/creative-intelligence.py`, `scripts/creative-operations.py` (~83 KB each) — strict schema/state/hash validation of design evidence. Neither performs research, rendering, or any network call.
- **Product launcher/distribution**: `src/ariadne/{__init__,__main__,cli}.py` (~53 KB), `build_backend/ariadne_backend.py`, `scripts/build-release.py`.
- **Knowledge layer**: 34 markdown policy/prompt/skill/template documents, `references/capabilities.json`, `references/ui-libraries.md`, `references/visual-references.md`.

### State and persistence (SOURCE_CONFIRMED)

```
<project>/                          PROJECT.md AGENTS.md DESIGN.md HANDOFF.md QA.md RESEARCH.md
                                    .ariadne/{creative-evidence.json, creative-operations.json, returns/<packet>.md}
<sibling>/<project>-ariadne/        ariadne-run.json (STATE_NAME, schema_version = 1)
                                    OPERATIONS.md (append-only human log)
                                    provider-preflight.json
                                    worker-telemetry.jsonl (append-only JSONL, schema_version 1)
                                    <run_id>-<S#>[-C<n>]/{packet.txt, manifest.json, evidence/*}
```

- `load_state` hard-rejects any `schema_version != 1` with "Run state schema is unsupported" (`scripts/ariadne.py:261-271`). There is no migration path anywhere in the product. SOURCE_CONFIRMED.
- State writes are atomic-ish: temp file + `replace_with_retry` (10 attempts, linear backoff) (`scripts/ariadne.py:140-171`). There is no lock file and no journal. SOURCE_CONFIRMED.
- Telemetry defaults every unknown field to the literal string `unknown`; usage/cost are only ever recorded when the provider reports them (`scripts/ariadne.py:173-200`). TEST_VERIFIED (`lifecycle.telemetry-keeps-unknowns`).

### Gate model (SOURCE_CONFIRMED)

Five human gates G1–G5 are defined in `WORKFLOW.md`; the runtime enforces two of them mechanically, both by **parsing project documents**:

| Gate | Enforcement | Code |
|---|---|---|
| G1 direction | `DESIGN.md` contains `**Status:** … locked at G1` **and** `AGENTS.md` `**Last gate passed**` matches `G1` | `ariadne.py:3363-3365`, `3495-3500`, `handoff_context_problems` `ariadne.py:809-812` |
| G2 dependency install | documentation/prompt contract only (`NO NEW DEPENDENCY without asking me (G2)`); `references/capabilities.json` carries `"install_authority": "none — human G2 required"` and `check.py` asserts those strings exist | `check.py:169-207` |
| G3 review acceptance | `record-acceptance --outcome accepted` requires `AGENTS.md` gate field `G3`; the command states "No gate was granted or inferred" | `ariadne.py:2795-2852` |
| G4 ship / G5 publish | prompt sequencing enforced by text contracts in `prompts/project-review.md`; `check.py` asserts ordering tokens | `check.py:1320-1350`, `904-912` |

Because the G1/G3 gate fields live in `AGENTS.md`/`DESIGN.md` — files any project-writing actor can write — gate enforcement is not bound to an independent approval record. That is confirmed by benchmark case `security.gate-forgery-in-agents-md` (TEST_VERIFIED, see §7).

### Verification model (SOURCE_CONFIRMED, TEST_VERIFIED)

- Independent worker validation is **real**: `validate_worker` (`ariadne.py:2415-2665`) re-derives the validation command list from `HANDOFF.md`, executes each command with `subprocess.run(shell=False, timeout≤600)`, hashes stdout/stderr, compares git snapshots (`project_git_snapshot`) against the packet's baseline, refuses if `HANDOFF.md` or `DESIGN.md` changed since preparation, and classifies the worker's own reported scope. Tested end-to-end by `lifecycle.independent-validation-executes`.
- Review independence is **asserted, not verified**: `ingest_review` (`ariadne.py:2705-2792`) accepts a human-supplied file whose only independence evidence is the literal line `**Reviewed independently:** yes`, rejects `<placeholders>`, and rewrites the `QA.md` Judgement region. There is no reviewer identity, session, or isolation evidence. TEST_VERIFIED (`security.review-attestation-unverified`).
- Repair budget is bounded: `MAX_ROUTINE_REPAIRS = 2` (`prepare-stage.py:46`), re-validated on every packet read (`prepare-stage.py:1698-1703`); blocked returns cannot enter routine repair (`ariadne.py:3446-3460`, `3575-3581`). TEST_VERIFIED (`lifecycle.repair-budget-bounded`, `lifecycle.blocked-return-halts`).
- Evidence immutability: return handoff, transcript, validation, review evidence and stage results all refuse to overwrite (`ariadne.py:2233-2234`, `2340-2341`, `2424-2425`, `2722-2723`, `2142-2143`). TEST_VERIFIED (`security.evidence-not-overwritable`).

### Context compiler (SOURCE_CONFIRMED, TEST_VERIFIED)

`prepare-stage.py` already contains a genuine compiler:

- `STAGES` table (`prepare-stage.py:75-181`) declares per stage: prompt, project inputs, optional runtime inputs, canonical policy inputs, conditional inputs, allowed parents, forbidden inputs, provider.
- Conditional resolution is real: `--motion yes|no` and `--assets yes|no` gate `DESIGN-MOTION.md`/`DESIGN-ASSETS.md`; selected creative skills gate `skills/reference-analysis.md`, `skills/component-research.md` and the capability registry (`prepare-stage.py:1193-1226`). Declined inputs are recorded in `manifest["omitted_conditionals"]`.
- Every delivered source is hash-stamped with `SOURCE-SHA256` and `CONTENT-SHA256` in the packet header and re-verified on every read (`prepare-stage.py:1348-1356`, `1657-1747`). A changed project input makes the packet stale (`stale source: …`). TEST_VERIFIED (`context.delivered-source-hashes-match`, `lifecycle.stale-project-input-detected`).
- Tampering with `packet.txt` is detected (`packet hash mismatch — packet changed after preparation`). TEST_VERIFIED (`security.packet-tamper-detected`).
- S5 isolation is enforced structurally: the review packet may deliver only `{canonical-prompt, canonical}` sources and exactly `["current S5 prompt block", "EVALUATION-RUBRICS.md"]` (`prepare-stage.py:1749-1758`). TEST_VERIFIED (`lifecycle.s5-isolation`).
- Measured sizes (deterministic fixture, `context.packet-size-baseline`): **S1 = 21 889 bytes / 2 sources; S3 = 39 252 bytes / 6 sources**. These are measurements, not estimates.

### Capability routing (SOURCE_CONFIRMED)

- `reasoners.py` implements provider selection, capability classification with evidence classes (`verified`, `reasonably-assumed`, `externally-unverified`, `blocked`), and a CLI detection probe (`shutil.which` + `--version`, 10 s timeout). Codex is "embedded" (always available, no CLI); Claude is opt-in and detected.
- `ariadne.py:1707-1940` implements a difficulty × stakes routing recommendation (capability class, concrete model family, effort, session strategy) with 25+ boundary self-tests.
- **Routing is advice, not enforcement.** No function consults the reasoner capability matrix (`design-direction`, `visual-qa`, …) when choosing a provider for design work; the matrix is schema-validated data only. INFERRED from exhaustive call-site reading of `capabilities` in `reasoners.py`/`ariadne.py` (no reader found).
- Provider preflight (`ariadne.py:2022-2098`) gates the S4A→S4B transition and records `provider`, `model`, `effort`, `decision` in `provider-preflight.json`. The transport provider label is carried, not verified: the worker's reported `provider`/`model` are ingested from its own return text and recorded as-is (`ariadne.py:2237-2301`).

### Design intelligence (SOURCE_CONFIRMED)

Executable part: two ledger engines (~3 300 lines) enforcing skill selection/state transitions, reference provenance (`found`/`inspected`/`inaccessible`), resource claims with mandatory alternatives and inspected sources, decisions anchored to artifact substrings, registry hash binding, and design-quality checks on `DESIGN.md` (non-generic thesis, tension, concrete signature + mobile equivalent, ≥3 rejections, a 10-row G1 direction check). **None of it researches, renders, screenshots, or measures anything.** Rendered visual QA, browser capture and DOM/contrast inspection are MISSING in the entire repository (repo-wide search for `playwright|puppeteer|selenium|webdriver|chrome.launch` returns two string literals and no imports). Evidence-ladder disciplines (`code-suggests` → `rendered` → `observed` → `verified`) exist as schema, and `verified` requires citing prior rendered/observed evidence — so the ladder is enforced on *claims*, not on *instruments*.

### Distribution (SOURCE_CONFIRMED)

- Distribution/import name is `ariadne` (`pyproject.toml:7`), which collides with the unrelated GraphQL `ariadne` package. The product documents the collision (`INSTALL.md:18-32`, `README.md:29-31`, `TROUBLESHOOTING.md:17-22`) and `V1.6-READINESS.md:231-234` calls a rename "a breaking 2.0 candidate". No mitigation exists in code.
- `dependencies = []`, `requires-python = ">=3.10"`, custom stdlib build backend, wheel embeds `ariadne/seed-runtime.zip`. TEST_VERIFIED (`distribution.release-tooling-offline`, `distribution.version-and-schema-coupling`).
- Update path: HTTPS-only descriptor download, sha256 of the artifact verified, release manifest validated field-by-field (`cli.py:445-483`) including a version-graded required-file set and `project_state_schema.min/max`. TEST_VERIFIED (`distribution.manifest-rejects-incomplete`: 7/7 mutations rejected, positive control clean).
- **Not** validated: no signature anywhere; the descriptor's checksum travels beside the artifact; no TLS pinning; no descriptor↔manifest version equality check (a descriptor may advertise version X while the bundle is version Y); artifact host is not constrained beyond `https://`. SOURCE_CONFIRMED (gaps enumerated in the distribution audit).
- `project_state_schema` is declared `{min: 1, max: 1}`; the runtime hard-rejects any other run-state schema, and there is no migration mechanism (MISSING within the searched scope: `MIGRATION-CHECKLIST.md` documents tool adoption, not state migration). TEST_VERIFIED (`lifecycle.state-schema-mismatch-refused`).

## 3. Maintainer vs public (Phase C)

Mechanical comparison of `ls-tree -r --long` output at the two release commits:

```
public files: 95    maintainer files: 137
shared: 95   identical blobs: 95   differing: 0   public-only: 0
maintainer-only: 42
```

SOURCE_CONFIRMED. The published 95 files are byte-identical to the maintainer's; the maintainer adds 42 files that were never distributed:

- 11 readiness/release docs (`V1-READINESS.md` … `V1.6-READINESS.md`, `RELEASING.md`, `HANDOFF-TO-CODEX.md`)
- 8 `operations/V1.*-PRODUCTIONIZATION|PRODUCTIZATION|…` delivery records
- 12 extra test/validation scripts (`scripts/check.py`, `scripts/validate.py`, `test-distribution.py`, `test-real-projects.py`, `test-social-intelligence.py`, `test-reasoner-rollback.py`, `test-wheel-install.py`, `test-writing-*.py`, `test-social-intelligence.py`, `finish-test-a.py`, `setup-test-a.py`)
- the `tests/` protocol documents and the `validation/` fixture+run harness (11 files incl. `validation/fixtures/*.json`, `validation/runs/B1/*`)

Implications for v2:

1. **The public product is the maintainer product** — no private feature divergence, no hidden code. Unpublished material is *verification and process*, not capability. INFERRED from byte-identical trees.
2. The unpublished 42 files are the strongest existing deterministic evidence base (see 06-BENCHMARKS). No legitimate reason was found to keep them private as *engine* assets; whether they are republished is a product decision, not an AR-200 change.
3. Canonical development source: the maintainer `master` (release-tracking). The `dh/design-harness-*` branch is a *product* branch (Boreal), not an Ariadne engine branch. SOURCE_CONFIRMED.

### Duplication and coupling (searched, measured)

- `scripts/ariadne.py` is a single 5 785-line module; `prepare-stage.py` 2 600; `creative-intelligence.py` ~1 669; `creative-operations.py` ~1 653. Cross-module coupling is by **dynamic import of sibling scripts** (`importlib.util.spec_from_file_location`, `ariadne.py:75-125`), which forces `sys.dont_write_bytecode = True` to avoid writing `__pycache__` beside immutable runtime files. SOURCE_CONFIRMED.
- Real duplication (not merely size): stage lists exist in three places — `TRANSPORT.STAGES` (authoritative), `ariadne.FRIENDLY_STAGES`/`EXPECTED_STAGE_OUTPUTS`, and prompt text; gate semantics are re-expressed in `handoff_context_problems`, `infer_next_stage`, `advance`, and prompt documents. Gate/report logic re-parses the same markdown in four functions. SOURCE_CONFIRMED.
- Boundaries that would genuinely improve testability/reuse: (a) stage specification + packet compiler, (b) state/gate policy, (c) worker validation, (d) evidence ledger, (e) distribution. These map to the proposed v2 module boundaries (§03) and are already separated *by file* except for the state/gate logic inside `ariadne.py`.

## 4. Test infrastructure already available

All deterministic and offline. Counts verified by this run (TEST_VERIFIED, see 06-BENCHMARKS for commands and results):

| Suite | Command | Result |
|---|---|---|
| Repository aggregate (18 named suites) | `python scripts/check.py --self-test` | PASS |
| Runtime controller | `python scripts/ariadne.py --self-test` | PASS 125/125 |
| Context transport | `python scripts/prepare-stage.py --self-test` | PASS 50/50 |
| Reasoner adapters | `python scripts/reasoners.py` | PASS 15/15 |
| Repository contracts | `python scripts/check.py` | 18 ok / 0 fail |
| Validation-instrument guards | `python scripts/validate.py --self-test` | PASS 29/29 |
| Installed-product lifecycle | `python scripts/test-distribution.py` | PASS 55/55 |
| Release bundle | `python scripts/build-release.py --self-test` | PASS 18/18 |
| Real-project fixtures | `python scripts/test-real-projects.py` | PASS 29/29 |
| Social fixtures | `python scripts/test-social-intelligence.py` | PASS 68/68 |
| Writing contracts / execution | `test-writing-architecture.py`, `test-writing-execution.py` | exit 0 |
| Validation-run measurement | `python scripts/validate.py --benchmark` | 1 recorded run read |

Not executable without extra inputs: `scripts/test-reasoner-rollback.py` (requires two built release bundles) and `scripts/test-wheel-install.py` (requires pip/venv; build + isolated install). Both are recorded as declared-not-executed, not as passing.

Not present at all: pytest, `conftest.py`, CI configuration, coverage tooling, any lint/typecheck configuration. VERIFIED ABSENT by repository-wide file search.

## 5. Boreal (read-only) — state at audit time

Location: `<path>` (Python engine at `design_harness/*.py`, `agent/`, `coordinator/`, `tests/`, `tools/`; Tauri+React+TypeScript app under `design_harness/desktop/`).

- Boreal is not a separate repository: it is tracked on branch `dh/design-harness-2026-09-19` of the maintainer clone, 29 commits beyond `master` (`b2fe0e0` head at start). SOURCE_CONFIRMED.
- At AR-200 start, DH-011 was **uncommitted and in progress**: 17 modified tracked files and 26 untracked files (icons, `App.tsx`, brand assets, `DH011-UX-AUDIT.md`, 14 before-screenshots). `git status` = 43 entries. SOURCE_CONFIRMED.
- **Boreal changed during the AR-200 window, not because of AR-200.** A concurrent DH-011 development session was active in that worktree (evidence: `cargo` and `node` processes started 2026-09-22 18:54 local; git status grew 43 → 70 entries during the audit and 43 → 81 by the final check; 17+ new files including `desktop/tools/dh011/{capture.mjs,contrast.mjs}` and 25 `dh011-after-*.png` screenshots; further modified files including `index.html`, `ErrorBoundary.tsx`, `DesignWorkspace.tsx`, `ContextRail.tsx`, `ConversationPanel.tsx`, `*css`, `tauri.conf.json`, `commands.rs`, `BRAND-GUIDE.md`).
- Verification that AR-200 did not write to Boreal: (a) every AR-200 command touching that path was a read (`Get-ChildItem`, `Get-FileHash`, `rg`, `git status|log|ls-files|ls-tree|cat-file`); (b) all pre-existing uncommitted entries are still present (no status line present at start disappeared); (c) `HEAD` is still `b2fe0e0`, branch unchanged, `git reflog` shows no new commits; (d) `.git/index` mtime is 2026-09-22 17:31:47 local — *before* AR-200 began (18:52 local), so not even index metadata was rewritten by the read-only git calls. SOURCE_CONFIRMED.
- A 478-file hash manifest of Boreal source (path/size/mtime/sha256, excluding `node_modules`, `target`, `dist`, `__pycache__`, `build`, `coverage`, `.vite`, `.next`) was captured at start and re-captured at end; all 30 deltas correspond to the concurrent DH-011 session listed above. The two manifests are retained as evidence at `%TEMP%\kilo\ar200\boreal-manifest-{start,end}.tsv`.
- Boreal tests were never executed; Boreal source, documentation, configuration, packaging and state were never modified. NOT_VERIFIED items caused by this constraint are listed in 02-CAPABILITY-MATRIX.

## 6. Environment

- Python `3.11.9` (a venv on PATH: `<path>`), `py` launcher present. Ariadne requires ≥3.10 and has no dependencies, so this is sufficient. SOURCE_CONFIRMED.
- `git` available and used read-only. `rg` (ripgrep 15.2.0) available. No pytest installed; none needed.
- All AR-200 writes are confined to `<path>` and `%TEMP%\kilo\ar200` (manifests, fixtures) / `%TEMP%\ariadne-bench-*` (benchmark sandboxes, deleted on completion).
- No paid model evaluation, no network installation, no dependency installation was performed.

## 7. Known limitations of the baseline (measured, not asserted)

Confirmed defects by execution (details and evidence in 06-BENCHMARKS):

1. **Gate forgery.** An actor with project write access plus CLI access grants G1 by writing two document fields and recording a stage result; the runtime then records the human creative decision as resolved and prepares S4A. (`security.gate-forgery-in-agents-md` — FAIL against the integrity expectation.)
2. **G1/creative-evidence enforcement is path-dependent.** At S3 `advance` refuses (exit 2) while no stage result is recorded, but after `record-result` the same command proceeds to S4A; the creative plan is therefore optional in practice. (`security.creative-gate-bypass` — FAIL.)
3. **Review independence is a self-written attestation.** A review containing `**Reviewed independently:** yes` is accepted with no identity, session, or isolation evidence; removing that line is the only thing that changes the outcome. (`security.review-attestation-unverified` — FAIL.)
4. **Structural review ingestion has no content quality floor** beyond section presence, field presence, and a valid recommendation enum (`review_judgement_problems`, `ariadne.py:2668-2694`).
5. **No state-schema migration** and no dual-read for run state (`RUNTIME_SCHEMA = 1`); a v2 schema bump strands every existing run unless migration is built. (`lifecycle.state-schema-mismatch-refused` — correct refusal, but the compatibility cost is real.)
6. **Distribution trust is TLS-only** with no signature and no descriptor↔manifest version equality check; the package name collides with an unrelated PyPI project.
7. **`scripts/ariadne.py` holds policy, state, gates, and reporting in one module**, so gate semantics are re-implemented in several functions; this is the main source of the inconsistency in defect 2.

Everything else in the v1.6.7 baseline that the brief asked about was found present and working, and is recorded in 02-CAPABILITY-MATRIX rather than here.
