# AR-202D → AR-203 handoff

Purpose: hand the AR-202D design-intelligence milestone to an independent
verification-hardening milestone, with everything needed to start and nothing that
requires re-deriving.

## 1. Starting point

| | |
|---|---|
| Worktree | `<path>` |
| Branch | `v2/ar-202d-hardening` |
| Base | AR-202D at `1fe8aa0` (the reviewed closure candidate); AR-202 at `8e1a2fd` |
| Version | `1.6.7` (unchanged) |
| Run-state file schema | `1` (unchanged; design records use their own family) |
| Record contract | `SCHEMA_RECORD = 2`; `SCHEMA_ADAPTIVE = 1`; `SCHEMA_DESIGN = 1` |
| Engine contract | `ariadne-engine-1`, `ariadne-adaptive-1`, `ariadne-design-1` |
| Benchmark suite | 157 cases in 23 groups; `benchmarks/results/AR-202D-H-final.json` |
| Engine suite | `scripts/test-engine-core.py` 246/246 |

Suggested AR-203 branch: `v2/ar-203-verification-hardening`.
Suggested worktree: `<path>`.
Suggested base: the AR-202D final commit on `v2/ar-202d-design-intelligence`.

## 2. AR-203's scope (proposed, not started)

AR-202D proved the design workflow **deterministically**. What remains is
**independently verified** against live systems, without weakening any invariant
that already holds. Three workstreams:

### W1 — Live capability registry bound to declared adapters

AR-202D routes design evidence from *adapter declarations*
(`routing._adapter_candidates` reads `capabilities()`/`enabled()`/`available()`).
Today those declarations come from the configuration the runtime constructs.

AR-203 should:

* publish a per-run capability registry (adapter id, declared capabilities,
  availability, reason, and the probe that established it) as an artifact;
* verify each declaration with a *probe* whose result is recorded, so a claim of
  availability is evidence rather than configuration;
* keep the AR-202D rule intact: capability is never inferred from a model or
  vendor name, and an unavailable capability blocks the route rather than being
  papered over;
* make `routing.route_evidence` consume the registry, so the live and offline
  paths share one decision.

Entry points: `routing.route_evidence`, `routing._adapter_candidates`,
`references.default_adapters`, `render.default_adapters`,
`render.capability_matrix`, `references.capability_matrix`.

### W2 — Live rendered verification, without weakening the contract

AR-202D ships `LocalBrowserAdapter` reporting itself unavailable, and verifies
rendering through `OfflineFixtureAdapter`. AR-203 should make a real browser a
*declared, authorized, probed* capability:

* a capture adapter that can attach a real browser, producing
  `capture-method`-specific provenance that satisfies the existing
  `render._provenance_problems` obligation (a manifest naming the artifact,
  digest, adapter, viewport, environment and revision);
* `render.verify` unchanged: a *different* engine-created execution must
  re-produce the same evidence. The new adapter must not need the rule relaxed;
* a deterministic-vs-live separation in the benchmark suite, so fixture evidence
  can never be reported as browser evidence (the existing
  `rendered-evidence.*` cases already assert the fixture's honesty; AR-203 adds
  the live counterparts as `LIVE_VERIFIED`).

If a browser cannot be attached safely, the correct AR-203 outcome is a recorded
`NOT_EXECUTED` with the reason — never a weaker contract.

### W3 — Independent verification of reference intelligence against a live provider

AR-202D implements the approved-URL and paid-provider adapters as contracts and
refusals. AR-203 should:

* attach one authorized, free, public reference source through
  `ApprovedUrlAdapter` (HTTPS, allowlist, robots respected, byte caps) and verify
  the full lifecycle `FOUND → ACCESSIBLE → INSPECTED → ANALYSED → USED` against
  real retrieved content;
* verify that a *gated* source stays `INACCESSIBLE` with an honest blocker,
  including with a licensed interface configured but returning an error;
* keep the paid provider optional and unrequired.

## 3. Invariants AR-203 must not weaken

These are proven offline today and must hold afterwards. Each is a benchmark case
in `benchmarks/arbench/design_cases.py`; AR-203 should keep every one of them
passing unchanged.

1. A found reference is not an inspected reference
   (`reference-provenance.found-is-not-inspected`).
2. An inaccessible reference can never become inspected
   (`reference-provenance.inaccessible-never-becomes-inspected`).
3. An inspection requires real evidence and observable content
   (`reference-provenance.inspection-requires-evidence`).
4. An analysis derives from a real inspection
   (`reference-provenance.analysis-requires-inspection`).
5. Usage traces to an analysed reference and a real artifact anchor
   (`reference-provenance.used-requires-analysis`).
6. A content inspection cannot support a visual claim, and a visual inspection
   cannot support a behavioural one
   (`reference-provenance.content-inspection-cannot-satisfy-visual`,
   `reference-provenance.visual-inspection-cannot-satisfy-interaction`).
7. An adapter supplies only declared capabilities
   (`reference-adapters.unsupported-capability-stays-unsupported`).
8. A gated source is not bypassed and a claim in a title is not provenance
   (`reference-adapters.gated-source-is-not-bypassed`).
9. Component research cannot install or change the project
   (`design-invariants.component-research-cannot-install`).
10. A design direction cannot self-approve, and only the human channel approves
    (`design-direction.worker-cannot-self-approve`,
    `design-invariants.only-the-human-channel-approves`).
11. A material direction edit invalidates its approval
    (`design-direction.stale-approval-rejected-after-material-edit`).
12. `G1D` never substitutes for `G1`
    (`design-invariants.direction-gate-is-separate`).
13. A bare file is not rendered evidence
    (`rendered-evidence.capture-provenance-required`).
14. Evidence is revision- and viewport-bound
    (`rendered-evidence.wrong-revision-rejected`,
    `rendered-evidence.wrong-viewport-detected`).
15. A declared observer cannot exceed `RENDERED`
    (`rendered-evidence.declared-observer-cannot-exceed-rendered`).
16. A source suggestion can never prove rendered quality
    (`design-invariants.source-suggestion-is-not-rendered-quality`,
    `requirement-closure.rendered-requirement-cannot-close-from-source`).
17. An implementer cannot review its own work, and a critique needs rendered
    evidence and a current direction
    (`design-critique.implementer-cannot-review-own-work`,
    `design-critique.review-without-rendered-evidence-refused`,
    `design-critique.review-against-stale-direction-refused`).
18. Refinement is scoped, re-evidenced and bounded
    (`design-refinement.unrelated-artifact-unchanged`,
    `design-refinement.repair-limit-enforced`,
    `design-refinement.unresolved-finding-remains-visible`).
19. Design evidence routing never guesses
    (`design-invariants.evidence-routing-never-guesses`).
20. Design context never weakens role isolation
    (`design-invariants.context-isolation-preserved`).
21. Design events join the one canonical chain
    (`design-invariants.events-join-the-canonical-chain`).
22. Project-scoped evidence resolves inside its permitted root: traversal,
    absolute, prefix-collision and symlink escapes are refused before anything is
    hashed or stored (`design-hardening.traversal-escape-refused`).
23. A refused lifecycle move leaves the reference byte-identical
    (`design-hardening.refused-operation-leaves-state-unchanged`).
24. Every required direction section is present and non-empty, and the refinement
    scope matcher is the runtime's own rule
    (`design-hardening.missing-direction-section-refused`,
    `design-hardening.empty-direction-section-refused`,
    `design-hardening.near-match-scope-refused`,
    `design-hardening.exact-scope-accepted`).
25. The project scan is pruned and bounded, and authoritative collections refuse
    past their safety bound instead of truncating
    (`design-hardening.excluded-tree-omitted`,
    `design-hardening.oversized-collection-refused`,
    `design-hardening.normal-collection-accepted`).

## 4. Extension points AR-203 will need

* **A capture adapter**: implement `render.CaptureAdapter` (`id`, `available()`,
  `capabilities()`, `capture(spec)`, `compare`, `capability_record`) and register
  it in `render.default_adapters`. `render.record` must accept its artifacts
  without any change to `_provenance_problems` — if that function needs editing,
  the adapter is not satisfying the contract.
* **A reference adapter**: implement `references.ReferenceAdapter` and register in
  `references.default_adapters`. `FixtureReferenceAdapter` is the reference
  implementation of the interface; `ApprovedUrlAdapter` is the one to complete for
  live use (`fetcher` is the injection point).
* **A capability probe**: new; no existing surface. It should produce an artifact
  the run state can point at, and `routing.route_evidence` should consume its
  result rather than the raw configuration.
* **Benchmark layering**: `benchmarks/arbench/design_cases.py` for deterministic
  cases; add `benchmarks/arbench/live_cases.py` with `executable=False` and an
  explicit environment requirement for live cases so a live case can never be
  silently counted as a deterministic pass. Extend the manifest via
  `python benchmarks/run_benchmarks.py --write-manifest`.

## 5. Known limitations to carry forward

* No live web retrieval, no live browser, no licensed provider access was verified
  in AR-202D. `LIVE_VERIFIED` is empty.
* `references.ApprovedUrlAdapter` has a `fetcher` seam but no shipped fetcher: the
  discipline (HTTPS, allowlist, no credentials, byte caps, robots) is documented
  and enforced on the adapter, not yet exercised.
* `OptionalProviderAdapter` is contract-only; a licensed interface object is the
  only way to enable it and there is deliberately no scraping path.
* `render.stale_records` re-hashes every artifact on every call. Correct, and
  linear; AR-204 can add a content-addressed fast path without changing the
  contract.
* The characteriser's depth is deterministic but depends on the request text and
  the handoff's declared scope rows. There is a `declared` override channel
  (`design.characterize(declared=...)`) for a human to correct it, and every
  characteristic records which evidence decided it.
* One environmental flake (a Windows directory-swap lock in the installer) was
  found by these suite runs and fixed with the launcher's existing
  `replace_with_retry`; if a similar lock appears elsewhere in the distribution
  path, that bounded retry is the pattern to reuse.
* **Execution ids are shape-checked at the engine level.** `render.verify` and
  `critique.build_review` require an `exe_…` id and distinct executions, but the
  engine API accepts any well-formed id from a direct caller; only the CLI creates
  them through `execution_for_task`. Stronger execution identity is AR-203 work.
* **A capture artifact's byte size is unbounded.** Records are bounded
  (`MAX_DESIGN_RECORDS`), collections are bounded, and the scan is bounded, but a
  single very large artifact is re-hashed and stored whole. AR-204 owns a byte-cap
  or content-addressed fast path.
* **Scope matching is case-sensitive** (`fnmatch.fnmatchcase`), matching the
  runtime's existing `worker_path_matches`; on a case-insensitive filesystem two
  spellings of one path can compare unequal. Keeping the engine and the runtime on
  one rule was chosen over changing the runtime in a hardening pass.
* **`FixtureReferenceAdapter.fixture_root` is an explicitly external root.** A
  declared fixture may point outside the project; every candidate it returns
  carries its adapter id, so the provenance says which adapter supplied it. It is
  the reference-side analogue of `declared-observer` and is never used outside
  deterministic fixtures. Local *source* types (`local-file`,
  `project-screenshot`, `project-document`) are contained to the project even for
  a fixture.
* **The stricter direction validation applies to persisted records too.** There is
  no legacy design record: the family ships first in AR-202D (unreleased), the
  published v1.6.7 runtime does not read design records, and the run-state and
  design-record schemas are unchanged. A direction approved under the weaker
  validator can only exist in an AR-202D development run, and re-recording it with
  the missing sections named is the honest repair.

## 6. How to reproduce AR-202D's result

```text
python scripts/ariadne.py --self-test
python scripts/prepare-stage.py --self-test
python scripts/check.py
python scripts/check.py --self-test
python scripts/test-engine-core.py
python scripts/test-distribution.py
python scripts/build-release.py --self-test
python scripts/reasoners.py
python scripts/test-real-projects.py
python scripts/test-social-intelligence.py
python scripts/validate.py --self-test
python scripts/validate.py --benchmark
python scripts/test-writing-architecture.py
python scripts/test-writing-execution.py
python benchmarks/run_benchmarks.py --label ar-202d-final
```

Expected: `0 FAIL, 0 ERROR`; the benchmark suite reports 157 cases with
152 PASS / 0 FAIL / 3 OBSERVED / 0 ERROR / 2 DECLARED_SKIP, the 87-case AR-202
subset reports exactly 83 / 0 / 2 / 0 / 2, and `test-engine-core.py` reports
246/246.

## 7. First task list for AR-203

1. Create the AR-203 worktree from the AR-202D final commit; re-run the
   reproduction block above and confirm the baseline before changing anything.
2. Build the capability-probe artifact and make `routing.route_evidence` consume
   it; add a deterministic case that a probe result of `unavailable` still blocks
   the route.
3. Complete one authorized `ApprovedUrlAdapter` fetcher against a public,
   allowlisted source; add live cases as `executable=False` and record the result
   honestly, including "not executed".
4. Bring up a browser capture adapter satisfying `render._provenance_problems`
   unchanged; add `LIVE_VERIFIED` cases for screenshot, DOM and interaction at two
   viewports, and verify `render.verify` against real re-production.
5. Add the AR-203 report, the AR-204 handoff, and an ADR for the capability-probe
   decision.
6. Do not weaken any of the 21 invariants in §3; do not bump `VERSION`, push, or
   change the run-state schema.
