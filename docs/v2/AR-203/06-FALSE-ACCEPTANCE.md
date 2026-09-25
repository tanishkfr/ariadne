# AR-203 — False Acceptance

The AR-203 benchmark does not only ask *"does a valid workflow pass?"* It asks
*"does plausible fabricated success fail?"* Every case in the `false-acceptance`
group, and the adversarial pass recorded below, attempts to fabricate success
through a real surface and requires the engine to refuse it.

## 1. Threat model

The adversary is not a remote attacker. It is a plausible-but-untrue claim
arriving through a surface Ariadne already accepts: worker output, a validator
result, a review document, a design event, a recovery attempt, or a caller using
the Python API instead of the CLI. The properties under attack are exactly the
AR-203 distinctions:

| Attack family | Fabrication | Defence |
|---|---|---|
| Execution | worker claims a different runtime | provider-observation channel refuses worker sources; `reported` stays unverified prose |
| Execution | a well-formed `exe_…` id that the engine never created | `provenance.require_engine_execution` |
| Execution | another execution's result, or a replay | role/task/revision binding; terminal-state replay refusal |
| Execution | one provider request id claimed twice | `provenance.provider_request_problems` |
| Validation | output says PASS but the process failed | the engine records the process result, not the prose (existing validation seam) |
| Validation | historical passing evidence on a changed revision | revision-bound `verify_result`, `render.stale_records`, verification freshness |
| Validation | a fabricated log path | `verification._artifact_evidence` re-hashes every artifact and refuses a missing one |
| Validation | the correct hash of the wrong artifact | digest equality is required *and* the artifact must differ from the observed one |
| Review | implementer relabels itself reviewer | `review.independence_problems` identity + engine-execution checks |
| Review | the same execution submits the review | same-execution refusal; `independence_level = NONE` |
| Review | a review against a changed revision | `critique.prepare_review` evidence currentness |
| Design | declared reference presented as inspected | lifecycle + evidence-anchor requirements (AR-202D, preserved) |
| Design | stale screenshot presented as current | `render.verification_currentness` |
| Design | external artifact re-hashed and called verified | declared-observer ceiling; reproduction must be a new artifact |
| Design | requirement closed by irrelevant evidence | evidence-kind matching (AR-202D, preserved) |
| Recovery | ambiguous state converted into success | `recovery.proposal` refuses duplicate/ambiguous findings; interrupted work is abandoned as `INTERRUPTED` with no result |
| Recovery | an orphan result attached to a new execution | `execution.verify_result` role/task/revision checks |
| Decision | confidence converted into authority | `policy.authorization_effect = none`; `PROTECTED` always refused |
| Decision | an invalid bounded answer coerced to a valid one | `validate_answer` records `invalid` with the raw value |
| Decision | a decision replayed against another state | `state_digest` on every record; projections are digested |
| Surface | CLI accepts what the API refuses (or the reverse) | one engine implementation behind both surfaces; parity case |

## 2. The adversarial pass

Performed once, after the implementation was green, against the working tree.
Each attack was attempted through the surface named, and the observed result is
recorded.

| # | Attack attempted | Surface | Result |
|---|---|---|---|
| 1 | Fake execution identity: `render.verify` with an invented `exe_…` id | engine | refused — *"this engine did not create for this run"* |
| 2 | Fake execution identity through the CLI | `provenance --execution exe_…deadbeef` | refused, exit 1, same reason |
| 3 | Fake provider/model identity: worker reports `gpt-x`, then a provider observation with `source=worker-output` | engine | worker claim recorded as `worker_claim`; provider channel refused |
| 4 | Reuse old verification: verify a capture, then change the revision | engine | `verification_currentness` returns `STALE`; `stale_records` reports it |
| 5 | Relabel implementer as reviewer (new identity string, same execution) | engine | refused — *"independence cannot be established from the same execution"* |
| 6 | Treat a declared capability as verified | engine | `observe(status=VERIFIED)` refused — no verification record exists |
| 7 | Elevate declared render evidence | engine | refused — the declared-observer ceiling is named |
| 8 | Elevate a declared locator to retrieval | engine | asserted digest refused; `remote_origin_proven` stays `False` |
| 9 | Exploit stale evidence to close a requirement | engine | stale verification answers as `STALE`; the requirement stays unverified |
| 10 | Submit an invalid bounded decision (`AUTHORIZATION_FAILURE` outside the declared set) | engine | recorded `invalid`, raw value preserved, no policy verdict |
| 11 | Convert self-reported confidence into authority (consequence `PROTECTED`) | engine | refused regardless of confidence; `mark_acted_on` refused |
| 12 | Bypass the same rule through CLI vs API | CLI + API | both delegate to `decisions.batch.evaluate`; identical refusals |
| 13 | Duplicate provider request id across two executions | engine | reported as a provenance conflict |
| 14 | Replayed execution result | engine | refused by the terminal state machine |
| 15 | Recovery of a duplicate-result state | engine | `proposal` returns `safe: false`, no action |

No genuine bypass was found in the pass. Four hardening repairs came out of the
implementation itself and are recorded as decisions rather than silently applied:

* `render.verify` originally accepted a digest-only reproduction; it now requires
  the artifact, because a digest can be asserted without re-producing anything
  (ADR-003).
* Reference retrieval verification has no engine execution for the *original*
  retrieval, so the record uses an `observed_anchor` and still requires an
  engine-created verifier — instead of pretending the adapter observation was an
  execution (ADR-004).
* `capabilities.observe` accepted `AVAILABLE` and above from any mechanism,
  including a bare claim. It now requires a deterministic probe or an engine
  execution/verification, so a status above `DECLARED` always names the mechanism
  that established it.
* `verification.refresh` could leave a record with `freshness: CURRENT` and
  `level: STALE` after its dependencies matched again. Restoration is now
  explicit and recorded (`restored_at`), so the two fields cannot disagree
  (ADR-005).

## 3. Benchmark cases

Group `false-acceptance` (six cases, all passing):

| Case | Fabrication attempted |
|---|---|
| `false-acceptance.fabricated-verification-evidence-refused` | a verification citing a log that does not exist |
| `false-acceptance.self-attested-verification-refused` | "tests passed" with no execution and no evidence |
| `false-acceptance.stale-passing-evidence-does-not-close` | a passing verification from a changed revision |
| `false-acceptance.orphan-result-cannot-attach` | another execution's result attached to a fresh execution |
| `false-acceptance.recovery-never-converts-ambiguity-into-success` | recovery asked to resolve an ambiguous state |
| `false-acceptance.cli-and-engine-refuse-the-same-claim` | the same fabricated id through CLI and engine |

Adjacent groups carry the rest of the threat model: `execution-provenance`
(identity fabrication), `capability-registry` (declaration elevation),
`review-independence` (self-review), `render-verification` and
`reference-verification` (evidence elevation).

## 4. Mutation testing

Five critical protections were broken in memory, one at a time, and the specific
test was re-run to confirm it fails. Files were restored byte-exact afterwards
(sha256 verified) and no mutation was committed. Results are in
`08-TEST-RESULTS.md` §6.

## 5. What is not covered

* A caller with direct write access to `ariadne-run.json` can fabricate any
  record. That is the documented trust boundary (see `02-EXECUTION-PROVENANCE.md`
  §3); cryptographic process attestation is out of scope and recorded as
  `NOT_EXECUTED`.
* No live provider was attacked, because no live provider was called. A malicious
  *provider* (as opposed to a malicious worker) is not in the threat model of this
  milestone; what the engine defends against is a provider answer that is
  unverifiable, out of the declared space, or carrying confidence it did not
  calibrate.
* Prompt-level attacks on a generative model (jailbreaks, instruction injection)
  are out of scope; AR-203 defends the boundary *after* the model answers.
