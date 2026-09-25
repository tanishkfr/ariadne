# AR-202D — Test results

Host: Windows 10.0.26200 (AMD64), Python 3.11.9. Every run offline:
`model_calls: 0`, `cost: 0.0`, no network, no model provider, no package install.
Harness: `benchmarks/run_benchmarks.py`; sandboxes under the OS temp directory,
never in a repository.
Artifacts: `benchmarks/results/AR-202D-H-final.json` (the final AR-202D-H run),
`benchmarks/results/AR-202D-H-baseline-reproduced.json` (the 145-case baseline
reproduced at `1fe8aa0` before the hardening pass),
`benchmarks/results/AR-202D-final.json` (the pre-hardening AR-202D final, unchanged),
`benchmarks/results/AR-202-final.json` (the AR-202 baseline, unchanged),
`benchmarks/results/LATEST.json`, `benchmarks/manifest.json` (157 cases).

## 1. Baseline reproduction

The comparison baseline is the reported AR-202 result, not a re-measured one:
the frozen AR-202 worktree at `8e1a2fd` reported **83 PASS / 0 FAIL / 2 OBSERVED /
0 ERROR / 2 DECLARED_SKIP** across **87** cases.

In the final AR-202D run, the same 87 cases (identified by group) reported:

| Classification | AR-202 | AR-202D final |
|---|---|---|
| PASS | 83 | 83 |
| FAIL | 0 | 0 |
| OBSERVED | 2 | 2 |
| ERROR | 0 | 0 |
| DECLARED_SKIP | 2 | 2 |
| **Cases** | **87** | **87** |

**No AR-202 case regressed and no assertion was weakened.** Two AR-202 cases are
group `suites` (they execute the repository's own self-tests), so this includes
re-running every repository suite from inside the benchmark.

The hardening pass (AR-202D-H) first reproduced the same 145-case result at
`1fe8aa0` before changing anything — **140 PASS / 0 FAIL / 3 OBSERVED / 0 ERROR /
2 DECLARED_SKIP**, wall clock 288.2 s — and the same 87-case AR-202 subset
(83 / 0 / 2 / 0 / 2). The artifact is
`benchmarks/results/AR-202D-H-baseline-reproduced.json`.

## 2. Final AR-202D result

| Classification | Count |
|---|---|
| PASS | 152 |
| FAIL | 0 |
| OBSERVED | 3 |
| ERROR | 0 |
| DECLARED_SKIP | 2 |
| **Cases** | **156** |

Wall clock **256.6 s** for all 157 cases; 462 checks with pass/fail semantics
(415 passed), 39.5 s of measured case metrics.

**New cases:** 70 in 12 groups, **69 PASS / 1 OBSERVED / 0 FAIL / 0 ERROR**.

| Group | Cases | Result | Group time |
|---|---|---|---|
| `design-characterisation` | 6 | 6 pass | 0.1 s |
| `reference-provenance` | 8 | 8 pass | 11.0 s |
| `reference-adapters` | 4 | 4 pass | 0.0 s |
| `component-intelligence` | 5 | 5 pass | 0.0 s |
| `design-direction` | 5 | 5 pass | 4.9 s |
| `requirement-closure` | 4 | 4 pass | 0.1 s |
| `rendered-evidence` | 7 | 7 pass | 0.1 s |
| `design-critique` | 5 | 5 pass | 0.1 s |
| `design-refinement` | 6 | 6 pass | 0.1 s |
| `design-invariants` | 7 | 7 pass | 1.6 s |
| `design-measurements` | 1 | 1 observed | 0.0 s |
| `design-hardening` (AR-202D-H) | 12 | 12 pass | 3.8 s |

Unchanged AR-202 groups (all preserved): `suites` 16 (14 pass, 2 declared skip),
`lifecycle` 22, `security` 12, `context` 5 (4 pass, 1 observed), `design` 3,
`distribution` 4, `adaptive-context` 6 (5 pass, 1 observed), `routing` 7,
`execution-identity` 4, `recovery` 4, `evidence-continuation` 4.

## 3. Repository suites, exactly as executed

| Command | Result |
|---|---|
| `scripts/ariadne.py --self-test` | `PASS 125/125` |
| `scripts/prepare-stage.py --self-test` | `PASS 50/50` |
| `scripts/check.py` | exit 0, `PASS` (18 sections, 0 duplicated sentences) |
| `scripts/check.py --self-test` | exit 0, `SELF-TEST PASS` |
| `scripts/test-distribution.py` | `PASS 55/55` |
| `scripts/build-release.py --self-test` | `PASS 18/18` |
| `scripts/reasoners.py` | `PASS 15/15` |
| `scripts/test-real-projects.py` | `PASS 29/29` |
| `scripts/test-social-intelligence.py` | `PASS 68/68` |
| `scripts/validate.py --self-test` | exit 0; 29 guards, each one refusing its broken input |
| `scripts/validate.py --benchmark` | 1 recorded validation run read |
| `scripts/test-writing-architecture.py` | `PASS 15/15` |
| `scripts/test-writing-execution.py` | `PASS 14/14` |
| `scripts/test-engine-core.py` | `PASS 246/246` (was 205; +41 hardening checks) |
| `benchmarks/run_benchmarks.py` | 157 cases, 152/0/3/0/2 |

**0 FAIL, 0 ERROR** across every command above.

### One environmental flake, found, fixed and recorded

On two earlier full-suite runs, `suite.repo-self-test` failed because
`check.py --self-test` hit `PermissionError: [WinError 5]` renaming a
distribution self-test staging directory
(`validation/distribution-self-test-*/user-data/.staging` → `versions/1.4.1`).
The same command passed standalone every time (5/5 for `test-distribution.py`,
3/3 for `check.py --self-test`), so the cause was a Windows file-handle lock on a
directory the test creates and removes — under sustained load (the suite writing
many small files quickly) a scanner or indexer can briefly hold a handle inside a
freshly extracted directory, and `os.replace` then reports access denied for the
directory swap itself.

**Fix applied** (`src/ariadne/cli.py`): the two directory swaps in
`_install_extracted` now go through the file's existing
`replace_with_retry` helper, which the launcher already used for the atomic
pointer and state writes. It is the same bounded retry (10 attempts, increasing
backoff), it changes no outcome, and it re-raises the last error rather than
hiding one — so no assertion was weakened. Two further full-suite runs after the
change reported 140 / 0 / 3 / 0 / 2 in each of two runs.

This is a product robustness fix discovered by AR-202D's own testing, not a test
adjustment: the underlying install contract and its assertions are unchanged.

## 4. Skips, observations and unverified claims

Declared skips (unchanged from AR-200, both environmental):

* `suite.reasoner-rollback` — needs two built release bundles; the
  reasoner-switch path itself is covered by `suite.runtime-self-test`.
* `suite.wheel-install` — requires an installable pip/venv environment and is slow.

Observations (recorded, never judged):

* `context.packet-size-baseline` — unchanged from AR-202.
* `adaptive-context.preparation-measurements` — unchanged from AR-202.
* `design-measurements.deterministic-counters` — see §6.

Claims that remain unverified here (recorded as unknown, never as a pass):

* **No live web reference was fetched.** The approved-URL and paid-provider
  adapters are verified as contracts and refusals only. Reference intelligence is
  verified against local files, project documents and deterministic fixtures.
* **No browser was started.** Rendered evidence is verified through the offline
  fixture adapter and the declared-observer contract. `LIVE_VERIFIED` is empty
  for rendering; see `09-AR-203-HANDOFF.md`.
* **No design database was consulted** (no Mobbin-class request was made).
* **No model provider was contacted**; token usage and cost are `UNKNOWN`, not
  estimated.
* **Offline fixtures do not measure human aesthetic quality.** They measure
  whether the engine's evidence logic holds. No case asserts that a design is
  good.
* AR-204 owns performance; the timings in §6 are overhead measurements, not a
  performance claim.

Evidence classification for this milestone:

| Class | Meaning | What AR-202D has |
|---|---|---|
| `DETERMINISTIC_VERIFIED` | proven offline, reproducibly | 145 benchmark cases, 205 engine-core checks, 14 repository suites |
| `LIVE_VERIFIED` | proven against a live external system | **nothing** |
| `NOT_EXECUTED` | defined but not run here | live web reference retrieval, live browser capture, licensed provider access |

## 5. Refusal paths proven

Every one of these is a case, and each asserts the *refusal* rather than
describing it:

**Reference provenance**
* `FOUND → ANALYSED` refused ("must be INSPECTED before it can be ANALYSED");
* an inaccessible reference can never become inspected; the record stays
  `INACCESSIBLE` with its blocker;
* an inspection with no evidence artifact refused; one with evidence accepted and
  its digest matched against the file;
* an analysis citing an inspection that does not exist refused;
* `USED` before `ANALYSED` refused; a usage whose anchor does not occur in the
  artifact refused;
* an appearance claim from a content inspection refused;
* a behaviour claim from a visual inspection refused, and then accepted from an
  interaction inspection;
* a changed artifact invalidates the inspection recorded from it.

**Adapters**
* an adapter asked for an undeclared capability refused;
* the approved-URL and paid-provider adapters report unavailable with a reason and
  return inaccessible results with blockers;
* a title asserting a claim ("best practice …") refused at registration, and no
  record written.

**Components**
* a dependency with unknown licence or compatibility blocked, both findings named;
* a dependency selected *with* an approval id records a human-only install
  authority and the project file set is byte-identical afterwards;
* an evaluation with no alternative refused; an unrecorded existing-equivalent
  check refused;
* the component module contains no process launcher and no install path.

**Direction**
* an implementer identity approving its own direction refused, no approval written;
* a non-human channel refused (`UnauthorizedApproval`), status stays `candidate`;
* a material edit invalidates the approval ("stale"); a cosmetic edit does not;
* `G1D` never satisfies `G1`, and `G1` never satisfies `G1D`;
* a generic mood statement refused as unactionable;
* a bounded repair selects `DIRECT: OPTIONAL` and is never blocked by the
  direction workflow.

**Rendered evidence**
* a bare file with a matching digest refused — no capture manifest, no evidence;
* a mismatched digest refused;
* the capturing execution verifying itself refused;
* evidence for another revision reported stale;
* a 375 px capture does not answer for 1280 px;
* a declared-observer artifact capped at `RENDERED`, promotion to `OBSERVED`
  refused;
* an unconfigured browser adapter reports unavailable and its capture is refused;
* a design evidence need with no declared adapter blocks the route with
  `design-evidence-unavailable`.

**Critique and refinement**
* a self-review refused on identity *and* execution, no review written;
* a critique without rendered evidence refused when the task requires rendering;
* a critique against a changed direction refused;
* a finding without evidence or without a repair scope refused;
* a refinement that changes artifacts outside its scope refused, state unchanged;
* a third refinement attempt refused with `REFINEMENT_LIMIT_REACHED`;
* a regressing repair recorded as `failed`, its finding `unresolved`, both visible
  in the summary;
* a minor finding cannot authorize "the entire interface".

## 6. First hardening pass after independent review

An independent review of this branch found that several guarantees were enforced
in only one of two entry points: the engine modules checked them, but the
`record-design` ingest path reaches the engine directly and could supply the very
value being checked. The fixes are in the engine rather than in the callers, so
both paths enforce the same rule.

| Gap | Fix | Test |
|---|---|---|
| `render.verify` let a `declared-observer` artifact reach `VERIFIED`, contradicting its documented ceiling | `verify` refuses the promotion, exactly as `observe` does | `rendered-evidence.declared-observer-cannot-be-verified` (new), plus an engine-core check |
| `critique.build_review` did not validate review-level evidence ids, and ingest skipped every `prepare_review` precondition | one `_evidence_preconditions` used by preparation **and** ingest; unknown, stale and never-captured evidence refused | engine-core: a critique cannot record a passing review citing invented evidence |
| A component candidate became `selected` on a caller-supplied `approval_id` | the id must match an approval the run recorded; `approval_source` is recorded and validated | `component-intelligence.dependency-cannot-self-install` (strengthened: a fabricated id is now `blocked`) |
| A usage or source claim could cite an empty anchor, which skipped the anchor check | an empty anchor is refused in `mark_used` and `record_source_suggests`, and `USED` requires the anchor in the contract | engine-core: a usage record needs an anchor, not prose |
| `mark_accessible` accepted a caller-supplied digest | a local locator is re-read and hashed; `content.digest_source` records `local-verified` or `declared` | engine-core: a local source digest cannot be asserted |
| A refinement could close `verified` with no expected evidence, because `str([])` is not empty | the contract requires a non-empty list and `propose_refinement` refuses an empty one | engine-core: a refinement must declare the evidence it will re-take |
| The closure path re-implemented evidence currentness and disagreed with `render`, letting an `UNVERIFIED` record close a `source` requirement | one `render.currentness_problems` rule used by both; `UNVERIFIED` closes nothing and the source minimum is `SOURCE_SUGGESTS` | engine-core: an uncaptured record cannot close a requirement |

Two further defects were found by driving the new CLI ingest path end to end, and
neither was visible to the engine-level cases:

* a `review` event crashed with `TypeError` because the handler passed `None`
  where a packet path was expected. The implementing task is now resolved
  explicitly, and a run with no implementer execution gets a clear `STOPPED`
  message instead of a traceback;
* `design-check` reported two false structural problems on a valid run
  (`design record schema is unsupported: None`, `reference analysis names no
  reference`) because the nested analysis record was validated as if it were a
  standalone record. The analysis now carries the same identifying fields, so one
  validator describes one shape, and `reference-provenance.used-requires-analysis`
  asserts that a valid run reports no structural problems.

None of the fixes weakens an assertion: each replaces a caller-supplied value with
a value the engine checks, and the cases that previously demonstrated the
permissive behaviour now assert the refusal instead.

## 7. Measurements


Deterministic overheads measured on this host (medians of repeated runs, single
process, no I/O caching tricks):

| Measurement | Value |
|---|---|
| `design.characterize` (200 samples, real project) | 1.166 ms |
| `reference.register` + `mark_accessible` + `inspect` (per reference) | ≈ 1.05 ms |
| `references.provenance_problems` over 200 references | 1.25 ms |
| `references.summarise` over 200 references | 0.30 ms |
| `render.record` (one artifact, re-hashed on acceptance) | 0.637 ms |
| `render.stale_records` over 100 artifacts (re-hashes every artifact) | 9.198 ms |
| `OfflineFixtureAdapter.capture` (one screenshot) | 1.908 ms |

Record size, measured, not estimated:

* a fully inspected reference record is **≈ 1.5 KB** of run state (100
  references → 152 935 bytes);
* the closure/critique/refinement records are smaller than a reference record;
* `render.stale_records` is linear in the number of artifacts and re-hashes each
  file, which is the dominant cost and is deliberate: a stale artifact must be
  detected, not assumed current. AR-204 can add a content-addressed fast path
  without changing the contract.

From `design-measurements.deterministic-counters`, two measurements of the same
state are identical, every counter equals its collection size, and no key or value
contains a "score". The measurement vocabulary is counters only — references
found/inspected/analysed/used/inaccessible, inspection types, component candidates
by rung, dependencies avoided, requirements tracked/observed/verified, rendered
evidence states and artifacts, critique reviews and findings, refinement attempts,
resolved, remaining, regressions.

**Honest reading:** these are single-host overhead numbers for small collections.
They show that recorder overhead is sub-millisecond per event and that nothing in
AR-202D is quadratic in the number of records; they are not a scalability claim.
AR-204 owns performance.

### AR-202D-H overheads

Measured on the same host, medians of repeated runs, on a synthetic project with
2 000 dependency stylesheets, 50 VCS stylesheets and 5 project stylesheets:

| Measurement | Before (glob + filter) | After (pruned walk) |
|---|---|---|
| stylesheet scan | 25.5–32.3 ms, 55 stylesheets (`.git` was **not** excluded) | 0.45–0.73 ms, 5 stylesheets |
| `design_system_maturity` end to end | — | 2.5 ms |

| Measurement | Value |
|---|---|
| `contracts.resolved_within` (per call) | ≈ 0.4–0.7 ms (a `Path.resolve()` on Windows; it runs once per artifact, alongside the file read it protects) |
| `reference.register` + `mark_accessible` + `inspect` (per reference) | 1.22 ms median, 1.73 ms p90 (≈ 1.05 ms before containment; the delta is the containment check) |

The scan is ~40–70× faster on the dependency-heavy fixture and, more importantly,
now excludes `.git` and other build/runtime trees that the old filter enumerated
and sometimes counted. The ranges are repeated single-host medians, reported as a
range rather than a single figure because the host varies between runs. The
containment cost is bounded and sub-dominant against the file hashing it
protects; no broad optimisation was attempted (AR-204 owns performance).

## 8. Second hardening pass (AR-202D-H) after the review of the ingest boundary

The first pass (§6) closed seven ingest-boundary gaps. The review recorded seven
further findings as open; this pass reproduced each one against `1fe8aa0`,
classified it, fixed the reproducible ones and added adversarial coverage. Every
fix is in the engine, so the CLI and the Python API enforce the same rule.

| Finding | Initial status | Reproduction | Fix | Tests | Final status |
|---|---|---|---|---|---|
| 4 — usage/source/observation artifacts can live outside the project | reproduced defect | `mark_used`, `record_source_suggests` and `observe` hashed an arbitrary absolute path from event JSON and stored it as provenance | `contracts.resolved_within` / `contained_evidence_path` / `contained_evidence_path_any` canonicalise (`..`, separators, drive letters, symlinks) and check membership; `mark_used`/`record_source_suggests` are confined to the project, `observe` to the project **or** the run's capture root, and a fixture `record` to the capture root. `mark_accessible` contains the caller-supplied local locator before re-reading it, so a local source outside the project cannot be re-hashed as engine-verified provenance. `declared-observer` remains the one explicit external-reference method and still carries its declaration | engine-core: sibling prefix, `..` traversal, Windows case, outside usage/source/observation/fixture, out-of-project local locator; benchmark `design-hardening.traversal-escape-refused`, `design-hardening.cli-traversal-escape-refused` | FIXED |
| 7 — refused transitions left the record partially mutated | reproduced defect | `mark_accessible`/`mark_inaccessible`/`inspect`/`analyse`/`mark_used` wrote their payload before `_transition` validated, so a refused move left inspection evidence, a retrieval digest or a blocker behind | one atomic commit: the intended payload is validated as a candidate record and only then applied; the history is bounded at `MAX_REFERENCE_HISTORY` | engine-core: five byte-identical refusal checks; benchmark `design-hardening.refused-operation-leaves-state-unchanged` | FIXED |
| 8 — direction sections the docs call required passed when empty | reproduced defect | `findings_rejected: []` was accepted and `reference_findings_adopted` / `approved_deviations` were not checked at all | one `contracts.DIRECTION_SECTIONS` tuple (all twelve) drives validation; every section must be a non-empty list of non-empty strings; `DIRECTION_FINGERPRINT_SECTIONS` names the subset an approval binds to | engine-core: each of the four sections refused when empty, plus an identity check that the vocabulary has one definition; benchmark `design-hardening.missing-direction-section-refused`, `design-hardening.empty-direction-section-refused` | FIXED |
| 11 — the refinement scope check used a substring rule | reproduced defect | permitted `src` admitted `srcx/evil.py`; permitted `src/app.py` admitted `vendor/src/app.py`; `src/**` never matched | `contracts.path_matches` (exact, `fnmatch` glob, `/**` prefix) is the runtime's own rule and is now used by `critique._within_scope` | engine-core: near-match pairs and an end-to-end refinement refusal driven by the reproduction pair (`styles` vs `srcx/styles/landing.css`); benchmark `design-hardening.near-match-scope-refused`, `design-hardening.exact-scope-accepted` (the `src/styles/**` vocabulary) | FIXED |
| 12 — every characterisation globbed the whole project | reproduced defect | `project.glob("**/*.css")` enumerated `node_modules` and `.git` before filtering, on every `design-plan` call | a deterministic pruned walk: excluded directories (matched case-insensitively) are removed from `dirnames` before descent, reparse-point directories are not followed, results are sorted, and directories **and** entries are counted against hard bounds before any listing is sorted (`MAX_STYLESHEET_SCAN_DIRECTORIES`, `MAX_STYLESHEET_SCAN_ENTRIES`, `MAX_STYLESHEETS`) | engine-core: dependency/VCS exclusion, case-variant exclusion, directory bound, stylesheet bound, symlink refusal when creatable; benchmark `design-hardening.excluded-tree-omitted` | FIXED |
| 13 — seven authoritative collections grew without bound | reproduced weakness | `design_references`, `rendered_evidence`, `design_requirements`, `design_directions`, `component_candidates`, `design_reviews` and `design_refinements` accepted unlimited appends | `contracts.require_design_capacity` refuses the append past `MAX_DESIGN_RECORDS` (10 000) with an explicit error and never truncates, and refuses a key that is not in `DESIGN_COLLECTION_KEYS` so a typo cannot silently skip the bound; the lifecycle history is bounded too. Indexing/caching of the stale-evidence pass is deferred to AR-204 (it is linear and bounded now) | engine-core: oversized collection refused with the length unchanged, every declared collection bounded, undeclared key refused, history bound; benchmark `design-hardening.oversized-collection-refused`, `design-hardening.normal-collection-accepted` | MITIGATED (hard bound in place; the per-call re-hash cost remains linear by design) |
| 14 — declared capability vocabulary was unused and inconsistent | reproduced defect | `DESIGN_CAPABILITY_IDS` was referenced only at its definition and omitted two ids the routing tables used; `render` kind tuples were never consulted | the two missing ids are declared, `routing.evidence_vocabulary_problems` checks the tables against the vocabulary and `route_evidence` refuses an inconsistent one; the unused `render` tuples were removed | engine-core: vocabulary consistency; benchmark `design-hardening.capability-vocabulary-enforced` | FIXED |

### Regression of the first pass

`design-hardening.previous-fixes-still-hold` re-attempts four of the first-pass
bypasses (declared-observer verification, a fabricated component approval, an
empty usage anchor, an empty expected-evidence list) and asserts each refusal;
the other three remain covered by their original engine-core checks. No first-pass
assertion was weakened.

### What the fixes changed for existing fixtures

The direction contract now matches `04-DESIGN-DIRECTION.md` §1: every constraining
section is required and non-empty. Seven existing fixtures that omitted
`reference_findings_adopted` or `approved_deviations` were completed with truthful
entries (an explicit "no reference findings were adopted" / "no deviation is
approved" decision), not by relaxing the validator. `mark_accessible` now refuses
a local source whose file does not exist **or** whose locator resolves outside the
project (a local reference that cannot be read is `INACCESSIBLE`, not
`ACCESSIBLE`). No benchmark assertion was removed or softened.

**Compatibility position.** The stricter direction validation is also applied
when a persisted direction is re-read on a continuation. There is no legacy
design record to migrate: the design-record family ships first in AR-202D, which
is unreleased (no tag, no push), the published v1.6.7 runtime does not read design
records, and the run-state schema, the design-record schema and the approval
fingerprint are all unchanged. A direction approved under the weaker validator
could only exist inside an AR-202D development run, and re-recording it with the
missing sections named is the honest repair.

### Additional defects found by the adversarial pass

Two defects outside the seven findings were found by reproducing them and are
fixed in this pass:

* **A local reference whose file does not exist could become `ACCESSIBLE`.**
  `mark_accessible` only re-read and re-hashed a local locator when the file was
  present; with a missing file it silently recorded the caller's digest as
  `declared`. A local source that cannot be read is now refused, because the
  honest outcome is `INACCESSIBLE`. Engine-core check "a local reference whose
  file does not exist cannot become ACCESSIBLE".
* **`.git` was not excluded from the stylesheet scan.** The old filter excluded
  only `.ariadne` and `node_modules`, so version-control and other build/runtime
  trees contributed design-system evidence. The pruned walk excludes them
  (finding 12); the measurement in §7 shows the old scan counting 55 stylesheets
  where the project owns 5.

### Final review of this pass, and mutation checks

A subsequent independent review of the AR-202D-H diff (base `1fe8aa0`) found and
fixed four further issues, all in this pass's own code, plus two coverage gaps:

* `mark_accessible` re-read the caller-supplied local locator without containment
  (a file-existence/content oracle over arbitrary host files). It is now
  contained against the project and read failures become refusals.
* The scan bound counted files, not directories, and was applied after sorting a
  directory listing; it now counts directories and entries *before* sorting, so a
  pathological tree cannot make the scan do unbounded work.
* The exclusion set was compared case-sensitively, so `NODE_MODULES` was not
  pruned on case-insensitive filesystems; names are now matched case-insensitively.
* `DESIGN_COLLECTION_KEYS` was declared but never read; `require_design_capacity`
  now refuses a key outside it, so a typo fails closed.
* The end-to-end near-match scope case used a pair the old substring rule also
  refused (it could not detect a reintroduction); it now uses the reproduction
  pair, and the accepted twin exercises the `src/styles/**` vocabulary.
* The "one definition" vocabulary check compared an alias to itself; it is now an
  identity check.

Each of the four code fixes was verified by mutation: the fix was reverted in
memory, the corresponding guard was re-run, and the guard failed in every case
(scope matcher → `design-hardening.near-match-scope-refused` fails; case-sensitive
exclusion, removed locator containment and removed collection-vocabulary guard →
`test-engine-core.py` reports 245/246). Files were restored byte-exact after each
mutation.

One bounded final review then drove the CLI and the Python API with adversarial
input against the new boundaries. No further real defect was found. Recorded as
remaining limitations, not defects: execution ids are shape-checked at the engine
level (the CLI creates them through `execution_for_task`), a capture artifact's
byte size is unbounded, and `FixtureReferenceAdapter.fixture_root` is an
explicitly declared external reference root (recorded on each candidate through
its adapter id). AR-203 owns stronger execution identity and live verification.
