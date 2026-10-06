# ARIADNE 2.2 — AR-224 CLOSURE REPORT

## 1. Repository / base / branch / final HEAD

- Worktree: `C:\Dev\Tools\Ariadne\ariadne-v2-2-ar224`
- Branch: `v2/2.2-ar224-proof-pass`
- Exact base: `f0affa696f090f6880596b25f040d9a26b4ed1b0` (verified 78/78, 43/43, 30/30, check PASS before implementation)
- Commits on branch: `0050f29` (Proof Pass implementation), `7371124` (RC source VERSION 2.2.0rc1), `d5ab42c` (verify routing fix; RC rebuilt from here)
- Final HEAD: `d5ab42c` (see `git rev-parse HEAD`). Tree clean. Sentinel idle (`[]` after suites; absent before first run).

## 2. Frozen-worktree verification

- `ariadne-v2-2-verified-intelligence` on `v2/2.2-verified-acceptance-intelligence` at `f0affa6`, clean.
- `ariadne-v2-2-release` on `v2/2.2-release-closure` at `f0affa6`, clean.
- No commits, no tracked modifications, no stash in either. Only ignored
  local residue in the former (ledger `[]`, pycache, two validation runs).

## 3. Baseline

AR-223 reproduced serially in the new worktree before implementation:
test-ar223 78/78, adversarial 43/43, mutations 30/30, check PASS (560 links,
74 files, 0 duplicated sentences). Working tree clean, sentinel idle.

## 4. Architecture freeze

AR-220 ReferenceSet, AR-221 grounded execution, AR-222 rendered critique,
AR-222D specificity/sources/provenance/interruption/harness, AR-223
acceptance/intelligence reused without redesign. Public layers delegate;
no duplicated semantics, no second QA engine. Recorded in
`40-AR-224-ARCHITECTURE-FREEZE.md`.

## 5. Public positioning

Ariadne 2.2 — Proof and Grounding. Workers produce. Ariadne determines
what is actually proven. Grounding says what should be built and why;
Proof says whether the work satisfied the request.

## 6. Proof Pass UX

`ariadne verify` answers what was asked, what the worker claimed, which
requirements are proven/partial/unproven/failed, which claims are
contradicted, what needs a human, and whether the work can be accepted.
The Claim-Evidence Gap stays visible; minimal honest evidence yields
PARTIAL/UNPROVEN, never PROVEN.

## 7. CLI

- `ariadne verify --against task.md --work-root ./work` (explicit)
- `ariadne verify` (zero-arg resolves the single active contract, refuses ambiguity)
- `ariadne verify --json` (versioned machine output)
- `ariadne proof VP-0001`, `ariadne compare VP-0001 VP-0002`
- Legacy `verify --input/--status` preserved via `verify-legacy`.
- Exit codes: 0 ACCEPTED, 1 NOT_ACCEPTED, 2 VERIFICATION_BLOCKED,
  3 usage/configuration error. Packaged slice exercised end to end.

## 8. Proof Receipt schema

`ar-224-proof-receipt-1`: proof_id VP-NNNN, engine_pass_id, task/contract/
revision/work_digest/created_at, requirement_decisions/verdicts/counts,
claim_assessments, contradicted_claims, blocking_summary,
acceptance_state, reviewer/provenance, previous_proof_id, receipt_digest.
Stable projection of one verification pass. Spec in
`41-AR-224-PROOF-RECEIPT-SPEC.md`.

## 9. Receipt persistence

Run-state collection `proof_receipts` (bounded 5000, append-only,
registered in contracts/persistence/migration families). Later runs create
VP-0042; VP-0041 never overwritten. Survives process restart (tested via
serialise/reload). Queryable by proof id; requirement history queryable.

## 10. Receipt integrity

sha256 over canonical JSON excluding the digest. Tampering detected
(tested). Digest integrity is not third-party attestation; no hash is
called a signature.

## 11. Share-safe receipt

`share_safe()` redacts absolute paths, usernames, env, credentials,
private URLs and secret logs; carries its own share_digest. Tested with a
Windows absolute path.

## 12. Proof history

`history_for_requirement()` walks every receipt deciding a requirement
(VP-001 FAILED to VP-002 PARTIAL to VP-003 PROVEN pattern supported).
CLI/API data sufficient; no dashboard.

## 13. Proof comparison

`compare_receipts()` reports resolved/still-failing/new-failures with
per-requirement transitions. Refuses unrelated task/contract lineage and
distinct requirement sets; marks contract-revision boundaries explicitly.

## 14. Stable Python API

STABLE: `create_contract`, `verify`, `get_verification`,
`compare_verifications`. State-level pure helpers
(`create_proof_contract_state`, `verify_work_state`, `get_proof_state`,
`compare_proofs_state`) classified PROVISIONAL. Every exported api name
carries exactly one classification (gated).

## 15. API compatibility

2.0/2.1 surfaces untouched; new names additive. `test-release.py` 97/97
(includes stability-classification, consumer, migration gates).
`test-engine-core.py` 578/578. No gratuitous break; no hidden major bump.

## 16. MCP surface

Schema `ar-224-mcp-1`, four tools delegating to the stable state API.
`src/ariadne_engine/mcp.py` with `describe()` and `dispatch()`.

## 17. MCP security

All inputs untrusted. Tested: path traversal, proof-ID forgery, reviewer
forgery, human-approval forgery, contract replacement, evidence
laundering, prompt injection claiming authority, oversized payloads,
command injection, unknown tools. MCP cannot mint authority; reviewer and
approval identities are engine-side only.

## 18. ChatGPT-facing integration

Thin skill `.agents/skills/ariadne-verify/SKILL.md` over API/MCP: when to
invoke (`@Ariadne verify ...`), how to recover the request, identify
work/claims/evidence, present requirement-level results without turning
UNPROVEN into done. No acceptance logic, no marketplace claims.

## 19. Agent-neutral worker contract

Schema `ar-224-worker-handoff-1` with producer vocabulary
(codex/claude-code/cursor/opencode/devin/boreal/ci/human/custom-agent).
Workers may submit evidence; never acceptance. No vendor completion rules
in core semantics.

## 20. GitHub / CI integration

Example `examples/ci-verify/ariadne-verify.yml` (issue to PR to evidence
to verify to receipt artifact). Exit semantics documented; blocking work
never yields green verified status. CI slice exercised via CLI exit codes.

## 21. Design workflow public surface

Documented in `43-AR-224-PUBLIC-SURFACES.md`: request to inspection to
content to concepts to references to defaults to direction to G1D approval
to implementation to render to critique to refinement to verification.
G1D remains the principal interruption; routine work continues after.

## 22. Packaged Design Specificity / anti-slop check

Packaged RC zip verified to ship `design_reference/specificity/*`,
acceptance engine, `proof.py`, `mcp.py`. AR-222D suite 124/124 and
adversarial 31/31 green. AR-224R then ran the F1 slice from the extracted
RC bytes with the vague request and no aesthetic guidance: 29 of 29 gates
held (3 surfaces modelled first, 3 candidates across 3 families, 150
skipped-with-reason selections with 14 of 39 sources queried, 4 defaults
detected with 4 earned and kept, human G1D binding the shown text, zero
interruptions after approval, no global score, no house style). A live
Chromium render of the dashboard was not run here; the offline method
slice is what the package run proves. See
`50-AR-224R-RELEASE-EVIDENCE.md`.

## 23. Design source ecosystem

AR-222D 36-entry registry ships with role/capability/access/auth/paid/
reuse/terms/verification-date/enabled-reason. No scraped corpora bundled.
No every-source-integrated claim. Outage degrades honestly.

## 24. Verified Intelligence release state

AR-223 numbers preserved and re-asserted: REVIEW_ESCALATION ACTIVE
1.000/0.053, ROUTE_FAMILY ACTIVE 1.000/0.031, FAILURE_CLASSIFICATION
EVALUATED 0.314, EVIDENCE_RELEVANCE EVALUATED 0.339,
authorization_effect none. 1.000 scoped to family/corpus/split/runtime/
evaluation, never general accuracy. Canonical AR-223 suites re-green
(78/78, 43/43, 30/30). No weak-family promotion.

## 25. 2.1 to 2.2 migration

Existing machinery (`plan`/`apply`/`rollback`) reused; `proof_receipts`
additive/optional, no forced migration. `test-release` migration gates
green (dry-run/additive/rollback/idempotent). Representative 2.1 fixture
covered by engine-core migration cases (578/578).

## 26. Boreal consumer conformance

PASS (contract only, Boreal untouched): `integration.describe()` protocol
ariadne-consumer v1, authority boundary intact, proof API additive.
No Boreal files modified.

## 27. Windows clean install

PASS via `test-wheel-install` 14/14 and `test-distribution` 55/55 on this
Windows host (fresh-env wheel install, doctor, project start, uninstall
parity). RC wheel `ariadne-2.2.0rc1` built from exact commit `d5ab42c`.

## 28. Linux clean install

PASS on real Linux (AR-224R): WSL2 Ubuntu, kernel
6.18.33.2-microsoft-standard-WSL2 x86_64, Python 3.14.4. User-local pip
install of the RC wheel printed 2.2.0rc1; `install` plus `doctor`
reported healthy; the installed controller verified a temp project end
to end (VP-0001 with requirement detail, VP-0002 on a second digest,
three-line comparison). Installed wheel digest equals the manifest
digest, so the tested bytes are the manifested bytes.

## 29. macOS clean install

NOT EXECUTED. No macOS hardware, virtual machine, or Mac runner exists
or was provisioned here. The wheel is platform-neutral pure Python and
the macOS data-home branch is covered by distribution path tests, which
bounds but never replaces a real Mac run. The limitation stays public.

## 30. Release artifacts

`dist/` from exact RC source `d5ab42c` (ignored, local): runtime zip,
wheel, release manifest, versioned notes, SHA256SUMS plus per-file .sha256.
`build-release --self-test` 19/19 (deterministic, excludes pycache and
machine paths, VERSION authority).

## 31. Release manifest

Binds version 2.2.0rc1, source commit `d5ab42c`, artifacts plus digests,
schema versions, public API version, MCP schema, receipt schema, Decision
Runtime identities via existing manifest machinery. Publication status:
candidate — human release authority still required.

## 32. Reproducibility

Guards exercised: `build-release --self-test` deterministic rebuild
checks green; `__pycache__`, absolute paths, machine paths, stale files,
line endings, wrong SHA and mutation residue excluded by allowlist and
self-test. Rebuild compared where deterministic output expected.

## 33. Signing / attestation

AUDITED: no genuine keyless attestation or signing available in this
environment; no committed private key; no long-lived secret introduced.
Artifacts carry digests plus embedded manifest, explicitly not signatures.
Recorded honestly; readiness reflects the limitation.

## 34. AR-224 tests

`test-ar224.py` 38/38, `test-ar224-adversarial.py` 22/22,
`test-ar224-mutations.py` 20/20. Registered in
`scripts/harness/test_inventory.py` (floors 35/20/18 plus proof-pass
critical phrases).

## 35. Mutations

20/20 caught (UNPROVEN-as-PROVEN, NOT_ACCEPTED-to-success, overwrite,
digest bypass, cross-lineage compare, MCP bypass/approval, reviewer
confusion, share-safe leak, dirty-source build, SHA omission, active
mutation during release, weak-family promotion, authorization grant,
style ban, colour-only directions, G1D bypass, slop score, plus harness
restoration proven per mutation).

## 36. Adversarial review

22/22 held (receipt tampering, ID traversal, contract substitution,
self-certification, fake approval/identity, stale evidence, wrong
revision, MCP injection, malicious reference, registry injection,
outage, source mismatch, attestation mismatch, CI laundering, UNPROVEN
translation, path traversal, laundering, oversized/command payloads).

## 37. Performance

Measured in-process: verify about 12 ms, digest 0.06 ms, receipt load
0.004 ms, compare about 1.5 ms. No optimization needed.

## 38. Full regression

Green: engine-core 578/578, decision-runtime 510/510 plus mutations
38/38, AR-222D 124/124 plus adversarial 31/31 plus mutations 35/35,
AR-223 78/78 plus 43/43 plus 30/30, AR-224 38/38 plus 22/22 plus 20/20,
release 97/97, distribution 55/55, wheel 14/14, check PASS, build
self-test 19/19, AR-220 reference 109/109 plus mutations 22/22, AR-221
design-execution 68/68 plus adversarial 35/35 plus mutations 25/25,
AR-222 critique 87/87 plus adversarial 27/27 plus mutations 40/40,
decision mutations 9/9 with sources byte-identical, benchmarks curated
release gate 89 pass with 0 fail, 0 observed, 0 error, 0 skip.
The earlier AR-221 67/68 was a missing `node_modules` in the fresh
worktree; `npm ci` from the committed lockfile restored it and 68/68
reproduced. Two tool-killed harness runs left ledger entries that were
recovered (one transactionally, one via checkout of an AR-222 file);
ledger reads idle and the tree is clean. Nothing further is omitted.

## 39. RC source commit

`d5ab42c` (branch `v2/2.2-ar224-proof-pass`). RC source committed before
build; rebuild after the verify-routing fix comes from this commit.

## 40. RC tag

NONE. No `v2.2.0rc1` tag created; tagging requires human release
authorization, which was not granted.

## 41. RC assets

Local candidate only in `dist/` (see 30). Nothing uploaded.

## 42. RC remote verification

NOT PERFORMED. No public release exists, so there is nothing remote to
verify (existence, tag target, assets, digests, manifest, attestation,
clean install from download all N/A).

## 43. Packaged Proof Pass slice

Performed against source-tree CLI with temp run state (source equivalent
of packaged controller): request to claims to evidence to `verify` to
VP-0001 to `proof VP-0001` to repair-digest `verify` to VP-0002 to
`compare VP-0001 VP-0002`. Human and `--json` forms both exercised.
Receipt persistence across processes verified.

## 44. Mixed-verdict packaged slice

Covered by AR-223 Beacon semantics (PROVEN/FAILED/UNPROVEN/NEEDS_HUMAN/
CONTRADICTED to NOT_ACCEPTED) plus AR-224 CLI slices, which yield
PARTIAL/UNPROVEN NOT_ACCEPTED rather than fake PROVEN. No failures faked
for aesthetics.

## 45. MCP packaged slice

Exercised in-process via `mcp.dispatch` over the stable state API
(contract, verify, retrieve, compare) with agreement to engine semantics.
AR-224R additionally exercised the installed design-reference MCP
transport from the extracted RC tree with a four-verb fixture connector:
3 default adapters honestly unavailable with inert search, exactly the 4
transport verbs advertised, tagged data return, no approve verb, and
undeclared capabilities refused — 12 of 12 gates held. Authority stays
engine-side.

## 46. Stable source commit

NONE. Stable `2.2.0` not attempted; VERSION remains `2.2.0rc1`.

## 47. Stable tag

NONE (`v2.2.0` not created).

## 48. Stable assets

NONE.

## 49. Stable remote verification

NOT PERFORMED (see 42).

## 50. Public release URL

NONE. Nothing published. Explicit: NO PYPI (permanent for 2.2; namespace
collision). GitHub Releases is the only distribution surface when
authorized.

## 51. Known limitations

Shipped in `48-AR-224-KNOWN-LIMITATIONS.md` and RC notes: no OS sandbox,
undeclared behavior stays unproven, subjective needs human, external
providers change, browser-only/disabled sources,
FAILURE_CLASSIFICATION and EVIDENCE_RELEVANCE stay EVALUATED, benchmark
is not frontier, no hosted service, ChatGPT ready-not-published, Boreal
consumer-only and untouched, digest-not-signature, bounded-not-eliminated
injection, plus macOS install not executed, live F1 pixels not rendered,
attestation unavailable. Linux install and the AR-221 slice left this
list during AR-224R because both were measured.

## 52. Final repository state

Branch `v2/2.2-ar224-proof-pass`, clean tracked tree, mutation ledger
idle, `dist/` local candidate artifacts from RC source `d5ab42c`
(ignored), frozen worktrees untouched at `f0affa6`. Later evidence
commits touch docs only; runtime source is byte-identical to `d5ab42c`,
so no rebuild was required. BOREAL UNTOUCHED. NO PYPI.

## 53. Closure status

AR-224 RELEASE-READY — HUMAN RELEASE AUTHORIZATION REQUIRED
