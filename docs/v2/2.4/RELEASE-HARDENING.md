# Ariadne 2.4A-R — Release Hardening and Independent Qualification

Status: release-candidate hardening record for `2.4.0rc1`. Not published.
Branch: `release/2.4a-r-hardening`. Baseline: `226fb045722ec9207687ef7225ab5c74da224bf6`.

This note records what was attacked, what broke, what was corrected, and what is
still not claimed. It is deliberately narrower than a release announcement.

## 1. Full-benchmark closure

The 2.4A report recorded 331 pass, 4 fail, 3 error, 5 observed and 2 skip across
345 cases. Seven cases were red. A clean v2.3.0 worktree at `853d827` reproduced
all seven with the same statuses and causes, so none was a 2.4A regression and
none was dismissed as harmless without a cause.

| Case | Baseline status | Cause | Correction | Fresh status |
|---|---|---|---|---|
| `suite.validation-guards` | error | `validation/run-template.md` was required by `validate.py --self-test` and `setup-test-a.py` but had never been tracked. The self-test crashed before it could report a verdict. | Restored the template as a tracked canonical artefact; made a missing template a clean failure; added it to `check.py`'s required files. | pass — 29 guards |
| `suite.validation-run-benchmark` | fail | The case read the operator's gitignored `validation/runs/` tree, so a clean checkout had no runs. | Added `validate.py --benchmark --runs-dir <dir>`; the case now derives a real run record from the tracked template inside its own sandbox. | pass — 1 run read |
| `suite.writing-contracts` | fail | `test-writing-architecture.py` read `WRITING-POLICY.md` and `ROUTER.md` at the repository root after both moved under `docs/policies/`. | Resolve through `check.py`'s one layout-aware resolver; fail by name if a document is genuinely missing. | pass — 15/15 |
| `lifecycle.s5-isolation` | fail | The runtime already delivered `docs/policies/EVALUATION-RUBRICS.md` and the packet verified clean; the expectation still named the bare filename. | Follow the resolved canonical path in the expectation. | pass |
| `adaptive-context.forbidden-source-never-delivered` | fail | Same stale bare-filename expectation. | Same resolution. | pass |
| `context.conditional-inclusion-hashed` | error | A real runtime defect: S3 looked for `DESIGN-MOTION.md` and `DESIGN-ASSETS.md` at the root, so `--motion yes` delivered nothing after the move. The benchmark crashed on the missing canonical file. | Point the S3 conditional sources at `docs/policies/`; keep the declared bare names stable for labels and omission messages. | pass — hash matches canonical |
| `release-metadata.notes-and-install-docs-name-version` | error | The case read `QUICKSTART.md`, `INSTALL.md` and `GETTING-STARTED.md` at the root; they live under `docs/guides/`. | Resolve each install document by name. | pass |

Fresh full benchmark (Windows, Python 3.11.9):

```text
summary: {'pass': 338, 'fail': 0, 'observed': 5, 'error': 0, 'skip': 2} in 508.984s
```

338 pass is the previous 331 plus the seven restored cases. No result was
converted to a skip, and no expected value was weakened. The five observed
cases and two declared skips are unchanged and separately accounted for.
Release subset: 90 pass, 0 fail, 0 error, 0 skip.

Evidence: `validation/runs/2.4a-r/bench-full.txt`,
`validation/runs/2.4a-r/bench-release.txt`,
`validation/runs/2.4a-r/bench-baseline-853d827.txt`.

## 2. Mutation qualification

The new harness is `scripts/test-ar24a-mutations.py`. It runs in a disposable
worktree, applies controlled defects transactionally through
`scripts/harness/mutation_ledger.py`, runs the test that owns the invariant,
and proves digest-based restoration before and after the run.

Result: **17 attempted, 17 valid, 17 killed, 0 survived, 0 invalid.** Restoration
and the post-mutation baseline were both proven.

| ID | Boundary attacked | Test that killed it |
|---|---|---|
| M01 | Validation revision binding — accept a pass from an earlier implementation revision | `stale_validation_is_refused_by_review_and_proof` |
| M02 | Cross-attempt evidence isolation — accept a copied validation record | `cross_attempt_validation_evidence_is_refused` |
| M03 | Reviewer independence — the implementer's own identity reviews | `forged_reviewer_identity_is_refused_without_leaving_an_open_execution` |
| M04 | Review freshness — ingest a review against a stale revision | `stale_validation_is_refused_by_review_and_proof` |
| M05 | Scope containment — a correction widens the declared scope | `out_of_scope_correction_is_refused_before_a_packet_is_prepared` |
| M06 | T1 review-correction budget — corrections never exhaust | `two_sequential_review_corrections_are_bounded_and_reviewable` |
| M07 | Parent/child linkage — a correction loses its parent identity | `failed_review_produces_a_linked_correction_and_fresh_validation` |
| M08 | S4B review authorization — a passing review authorizes a correction | `s4b_review_correction_contract_is_bounded_and_review_authorized` |
| M09 | S4B correction budget — the count is always zero | same S4B contract case |
| M10 | Reported freshness — stale evidence is reported as validated | `stale_validation_is_refused_by_review_and_proof` |
| M11 | Interrupted worker — an open worker is reported as validated | `real_subprocess_interruption_during_worker_execution_recovers_safely` |
| M12 | Failed validation — a failed attempt is reported as validated | `correction_that_fails_validation_cannot_become_accepted` |
| M13 | Proof receipt integrity — a tampered digest is accepted | `tampered_proof_receipt_cannot_mint_acceptance` |
| M14 | Proof store authority — a receipt id absent from the store resolves | `forged_proof_receipt_in_task_state_cannot_mint_acceptance` |
| M15 | Recovery idempotency — resume mints a second proof | `unchanged_passing_attempt_is_not_rerun_or_repaired` |
| M16 | Reviewer independence — reviewer and implementer share an engine execution | `test-engine-core.py` (585/586 on the mutant) |
| M17 | Human acceptance authority — the engine supplies the human identity | `acceptance_cannot_be_minted_without_a_human_identity` |

Two survivors in the first pass were investigated rather than excused:

- **M02** initially hit the settled-file digest guard before the cross-attempt
  checks. The mutation now disables the digest, the record's packet identity and
  the attempt binding together; that is one boundary, not three independent
  claims. The case then fails.
- **M13** exposed a real defect: `task-accept` checked that a proof receipt
  existed and belonged to the task, but never re-ran `receipt_problems` on the
  stored bytes. A receipt edited in run state kept its old digest and was
  accepted. The product now re-verifies schema and digest at acceptance, and a
  red-first regression (`tampered_proof_receipt_cannot_mint_acceptance`) was
  added. The mutant is killed by the public CLI path.

Evidence: `validation/runs/2.4a-r/mutations.json`,
`validation/runs/2.4a-r/mutations.log`,
`validation/runs/2.4a-r/mutations-attempt1.json` (the two-survivor run, kept).

## 3. Live S4B correction and independent S5 re-review

This is the part the deterministic benchmark could not establish.

### Environment and workers

- Implementation and corrections: **Command Code 1.88.5**, model
  **DeepSeek V4.1 Flash** (`deepseek/deepseek-v4.1-flash`), invoked with the
  adapter's exact headless argv and the packet on stdin.
- Independent review: **OpenCode 2.2.5** driving **GitHub Copilot**, observed
  model **`gpt-5.6-luna`**. A separate empty review directory received only the
  S5 packet; no `PROJECT.md`, `DESIGN.md`, `HANDOFF.md`, `AGENTS.md`, `QA.md` or
  build history was supplied.
- Codex 0.166.0 and OpenAI direct were probed but returned a ChatGPT usage-limit
  error. They did not perform the review. Claude Code 2.1.245 is installed but
  unauthenticated; Cursor is absent.
- The engine records the review independence as `DISTINCT_RUNTIME`, not
  `DISTINCT_PROVIDER`: the harnesses and models are distinct in fact, but the
  engine did not have a provider-observed difference it could certify. The
  conservative label is the correct one.

### Disposable project

`C:\Users\User\AppData\Local\Temp\opencode\ariadne-live-s4b` (copied to
`validation/runs/2.4a-r/live-s4b/`). A dependency-free Python/HTML countdown
with a code-only baseline `d4c9e8f`, a declared scope, and the validation
contract `git diff --check` + `python -m pytest -q`.

The pre-S4B G1 record was created by the fixture baseline identity
`baseline-fixture`; it is **not** reported as a live human decision. The live
qualification starts at the prepared S4B packet.

### Sequence

1. **S4B implementation** (Command Code): added pause/resume, and, while
   checking the success criteria, also corrected the duration formatter to
   `H:MM:SS` above one hour. Scope `within-contract`.
2. **First return rejected by the engine**: `Scope status` was
   `within-contract, with one disclosed transport addition`, which is not one of
   the schema's exact values. The rejected bytes are preserved as
   `return-rejected-1.md`; the same worker was asked to correct only that field
   and move the disclosure into `Unexpected actions or conflicts`.
3. **First validation failed for an environment reason**: the engine's
   validation child resolved `python` to a pyenv interpreter without pytest.
   The recorded stderr digest was reproduced byte-for-byte as
   `...python.exe: No module named pytest`. This was not treated as a code
   failure or a pass. A routine repair re-ran the real worker; the corrected
   validation passed. The environment fix was `PYTHONPATH` pointing at the
   existing Hermes site-packages; nothing was installed.
4. **First S5 review** (fresh OpenCode/GitHub Copilot session): a genuine
   **failed** review with **Fix and re-review**. Findings:
   - Major: invalid or negative duration input is silently ignored, with no
     visible recovery guidance.
   - Major: the quiet-instrument idea is materially shallow.
   - Minor: every tick fetches `/api/format`, making the core display depend on
     a network request.
5. **Correction** (Command Code, packet `live-s4b-S4B-C3`, parent `live-s4b-S5`,
   review-finding retry context): added inline text validation with
   `aria-invalid`/`role="alert"` and the accepted range, preserved the last valid
   duration, added a local browser formatter with a Node parity test
   (`tests/test_format_parity.py`), and added a restrained pause detent to the
   drain rule. New attempt identity; the earlier packets, returns and
   validations remain on disk.
6. **Fresh validation**: `within-contract`, both declared checks passed
   (`git diff --check`, `python -m pytest -q` — 18 tests). The validation record
   is bound to the corrected revision's implementation fingerprint.
7. **Second S5 review** (new S5 packet `live-s4b-S5-C1`, new OpenCode session,
   new review id and reviewer execution): **passed, Present G3, no findings.**
8. **Proof Pass**: `ariadne.py verify` produced **VP-0001, ACCEPTED**, with
   three requirements PROVEN and the corrected `live-s4b-S4B-C3` validation
   mapped as current. The receipt explicitly refused the first validation and
   `C1` (failed status) and `C2` (stale implementation fingerprint).
9. **Human gate**: `record-acceptance --outcome accepted` was refused:
   “Accepted requires the human G3 decision to already be recorded.” No G3 was
   recorded and no acceptance exists. The task stops at the human gate.

### Negative checks

- **Old validation cannot satisfy the corrected revision**: the Proof Pass
  validation mapping refused `C2` with “the validated implementation fingerprint
  does not match the current implementation; the recorded commands ran against a
  different revision and the result is stale.” The first and `C1` validations
  were refused as failed.
- **Old review cannot satisfy the new gate**: the two review records are
  `rev_...fbea81fa` on packet `live-s4b-S5` (failed, Fix and re-review) and
  `rev_...8daddc17` on packet `live-s4b-S5-C1` (passed, Present G3), with
  distinct reviewer executions `exe_...60f980a5` and `exe_...9ffb9acb`.
  Acceptance before G3 now refuses at the G3 gate, not by reusing the old
  review.
- **Scope containment**: the corrected validation's changed files are the
  permitted application/test files only; scope is `within-contract`.
- **Rejected return is not complete**: the engine refused the malformed return
  and did not ingest it; the rejected bytes are preserved. The first validation
  failure was recorded as failed and repaired, never promoted.
- **Recovery idempotency**: two `advance` calls against a copy of the run left
  the packet and review counts unchanged (9 packets, 2 reviews) and stopped at
  G3.
- **No fabricated human approval**: no G3 record exists; `worker.acceptance_state`
  remains `UNKNOWN`.

### Proof Receipt boundary

VP-0001 is a real engine receipt for the corrected implementation and its
engine-run validation. The creative S4B/S5 boundary's native final gate is the
G3 approval plus the passed S5 review; the `verify` CLI does not bind the S5
review into the receipt. This is recorded as a limitation, not hidden: the
receipt proves the work and validation, while the independent review is the
separate S5 record and the human decision is still outstanding.

Evidence: `validation/runs/2.4a-r/live-s4b/run/` (packets, returns,
validations, review records, proof receipt), `review-1/` and `review-2/`
(judgement blocks), and the copied project under `project/`.

## 4. Regression and compatibility

| Suite | Result |
|---|---|
| `scripts/test-engine-core.py` | 586/586 |
| `scripts/test-ar23b.py` | 27/29 (2 declared opt-in skips) |
| `scripts/test-ar23c.py` | 22/22 |
| `scripts/test-ar23d.py` | 25/25 |
| `scripts/test-ar225.py` | 51/51 |
| `scripts/test-ar24a.py` | 21/21 (19 original + 2 hardening regressions) |
| `scripts/test-ar24a-adapters.py` | 2/6 (4 live cases require `ARIADNE_LIVE_ADAPTERS=1`) |
| `scripts/test-release.py` | 97/97 |
| `scripts/test-distribution.py` | 55/55 |
| `scripts/test-wheel-install.py` | 14/14 |
| `benchmarks/run_benchmarks.py` | 338 pass, 0 fail, 0 error, 5 observed, 2 skip |
| `benchmarks/run_benchmarks.py --release` | 90/90 |
| `scripts/check.py` | PASS |

No new dependency, paid API, tag, push, publication or deployment was created.
The live work used existing authenticated sessions only. Windows was executed;
macOS and Linux were not. The live adapter suite's four opt-in cases were not
re-run; the live S4B qualification used Command Code's exact headless argv and a
fresh GitHub Copilot review session instead.

## 5. Remaining limitations

1. **Creative S5 proof receipt binding.** `verify` does not include the S5
   review in VP-0001. The creative boundary's final evidence is the G3 approval
   plus the passed S5 review; a native S5-bound receipt is not part of 2.4A.
2. **Validation interpreter selection.** A contract that says `python -m pytest`
   depends on the ambient `PATH`. If `python` resolves to an interpreter without
   pytest, the validation fails honestly but for an environment reason. This was
   observed live and worked around with `PYTHONPATH`; no global install was done.
3. **Provider independence recording.** The engine records
   `DISTINCT_RUNTIME` when it cannot certify a provider-observed difference. The
   live review was a distinct harness/provider in fact (OpenCode/GitHub Copilot
   versus Command Code/DeepSeek), but the record is deliberately conservative.
4. **Model availability.** Codex and OpenAI direct were quota-blocked during
   this run; Claude Code is unauthenticated; Cursor is absent. The live review
   used the strongest available authenticated distinct provider at the time.
5. **Platform coverage.** Windows only. macOS and Linux remain unexecuted.
6. **Local state.** Run-state files are not cryptographically attested; the
   proof receipt and review records are engine records, not external signatures.
7. **Live adapter suite.** The four `ARIADNE_LIVE_ADAPTERS=1` cases were not
   re-run in this hardening pass. The live S4B implementation and review were
   real external sessions, but they did not use the T1 adapter runner.

## 6. Commit map

| Commit | Purpose |
|---|---|
| `a051ab3` | Close the seven benchmark cases at their causes; restore the validation template; fix S3 moved-policy delivery; resolve documents by name |
| `cf241d2` | Add the 17-mutation lifecycle harness and the human-identity negative test |
| `498f8ca` | Acceptance re-verifies the stored proof receipt; add the tampered-receipt and S4B outcome regressions |
| `97a63db` | Make the mutation tests name the specific gate they own; strengthen cross-attempt and store-authority assertions |
| final docs commit | This report and the release/host/test documentation updates |

The working branch is local. Nothing was pushed, tagged or published.
