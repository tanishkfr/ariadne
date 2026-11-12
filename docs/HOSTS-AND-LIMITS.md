# Hosts, platforms, and known limitations

> Ariadne 2.4.0. This file states only what has been verified, and where. It is
> deliberately conservative: a host it lists as "declared" has an adapter and a
> discovery probe but no recorded live execution here.

## 2.4C surfaces

| Surface | Status | Boundary |
|---|---|---|
| Rendered design verification | Verified on a disposable surface: declared 320/390/834/1440/1920 matrix, 7 captures per phase, interaction assertions, contrast/focus/target/dialog/form checks | One Chromium-family browser on Windows; not WCAG conformance and not a human usability study |
| Visual regression | Verified by synthetic and real before/after captures | Pixel comparison, not a quality score; masks require a reason |
| Creative proof binding | Verified on the qualification lifecycle: packet/review/execution/revision/evidence digests bound into `VP-0001` | G3 remains human-owned and was not recorded |
| Host contract `ariadne-host-1` | Verified through CLI, API, MCP and an external consumer fixture across a simulated restart | Read-only; no Juno integration claimed; no daemon or remote transport added |

The 2.4C live matrix is 16 cells across Command Code and OpenCode (same model
family, different harnesses): 16/16 passed independent validation, 10 produced
an ACCEPTED Proof Receipt, 6 stopped at a required review boundary without a
proof, and no provider supplied token/cost usage. No model ranking or efficiency
promotion is claimed. Evidence:
[docs/v2/2.4/LIVE-INTELLIGENCE-QUALIFICATION.md](v2/2.4/LIVE-INTELLIGENCE-QUALIFICATION.md).

## 2.4B provider evidence

The 2.4B qualification re-probed the installed surfaces and ran a bounded live
sample. Versions are observations from this machine, not permanent guarantees.

| Surface | Observed version | Authentication observation | 2.4B live sample |
|---|---|---|---|
| Command Code CLI | 1.88.5 | prior 2.4A-R Command Code subscription; not re-authenticated by the probe | one isolated T1 bug fix: validated, `VP-0001` ACCEPTED, 169.4s |
| OpenCode CLI | v2.2.5 | stored provider entries include GitHub Copilot; no credential value was read | one isolated T1 bug fix: validated, `VP-0001` ACCEPTED, 94.0s |
| Codex CLI | 0.166.0 | `codex login status` reports ChatGPT | not executed in this pass |
| Claude Code | 2.1.245 | `claude auth status` reports `loggedIn: false` | not executable here |
| Cursor agent CLI | not installed | `UNKNOWN` | not executable here |

Both live tasks used the existing T1 adapter path and produced an engine
validation and Proof Pass. Neither adapter supplied token usage or cost, so the
measurement rows report those fields as `UNKNOWN`. The model-performance registry
therefore has **no benchmark-qualified live record**; the 2.4B routing evidence
is shadow-only. See
[docs/v2/2.4/MODEL-ROUTING-EVALUATION.md](v2/2.4/MODEL-ROUTING-EVALUATION.md).


## Worker hosts (task execution)

A T1 task names a worker adapter; the engine discovers, preflights, invokes,
ingests and validates through one pipeline (`ariadne_engine/task_execution.py`).
Adapter presets and their status:

| Adapter | What it is | Status in this release |
|---|---|---|
| `command-code` | Command Code CLI (`command-code -p ...`) | **Verified live** (2.4A and 2.4A-R): executable 1.88.5, authenticated Command Code subscription, model `deepseek/deepseek-v4.1-flash`; an isolated bug-fix task changed only `export.py`, passed Ariadne's independent validation and produced an ACCEPTED Proof Receipt. A live 30s timeout was classified `TIMEOUT` and recovered into a second, validated attempt. In 2.4A-R it performed the S4B implementation and the linked corrective attempt on the disposable Sandglass project; the engine refused one return whose `Scope status` carried a qualifier, and accepted the same worker's repaired return. |
| `opencode` | OpenCode CLI (`opencode run --auto`) | **Verified live** (2.4A and 2.4A-R): v2.2.5, authenticated, model `deepseek/deepseek-v4.1-flash` in the original T1 qualification; in 2.4A-R it was the review harness driving GitHub Copilot (`gpt-5.6-luna` observed) for the failed first S5 review and the fresh passing re-review. It is a distinct harness from the Command Code implementer. |
| `codex` | OpenAI Codex CLI (`codex exec --sandbox workspace-write ...`) | **Verified live with one recorded format variance** (2.4A): codex-cli 0.166.0, ChatGPT-authenticated, model `gpt-6.1-terra`; one live run wrote a return whose `Status` field the strict schema refused, then a subsequent run completed the same task and produced an ACCEPTED receipt after the prompt was made explicit about the three allowed status values. In 2.4A-R it was probed at 0.166.0 but a ChatGPT usage limit returned an error before any review; no execution is claimed for that attempt. |
| `claude-code` | Claude Code CLI (`claude --print ...`) | **Declared.** Executable discovery verified (`2.1.245`), but this host is unauthenticated; preflight refuses honestly. |
| `cursor` | Cursor agent CLI | **Declared / unavailable.** Not installed here; discovery reports `not found`. |
| `host-session` | The invoking assistant session performs the packet and records the return (`task-return`) | **Verified live** (2.3 and 2.4A): the real bug-fix and review-correction tasks were bound, performed, returned, validated, reviewed and proved end to end. |
| `manual` | A human performs the packet | Declared; the host-session path is the same protocol with a person. |
| custom CLI | `--worker-command "<argv>"` | Verified in the suites with a real subprocess fixture worker, including timeout/process-tree termination. |

"Executable present" is never treated as "integration working". The shared
`adapter-conformance` matrix separates structural declarations from observed
checks (discovery, version, authentication, argument compatibility, working
directory, prompt delivery, edit permission, structured return, cancellation,
timeout, nonzero exit, interrupted-session recovery, scope enforcement and
independent validation). A check this environment did not execute is
`not-observed` or `declared`, never `pass`.

Live qualification procedure (reproducible; existing sessions only, no new keys):

```bash
# structural checks, offline
python scripts/test-ar24a-adapters.py adapter_registry_is_structurally_conformant \
  custom_adapter_timeout_terminates_the_whole_process_tree

# live execution, uses the already-authenticated CLI
ARIADNE_LIVE_ADAPTERS=1 python scripts/test-ar24a-adapters.py \
  live_command_code_executes_a_real_task live_opencode_executes_a_real_task \
  live_codex_executes_a_real_task \
  live_command_code_timeout_is_classified_and_recovered_into_a_new_attempt
```

The 2.4A-R live S4B/S5 qualification is a separate path: Command Code performed
the implementation and the linked correction, and fresh OpenCode/GitHub Copilot
sessions performed the failed review and the passing re-review. It did not use
the T1 adapter runner, so the four opt-in cases above remain a separate,
unexecuted part of this hardening pass. Evidence:
`validation/runs/2.4a-r/live-s4b/` and
[docs/v2/2.4/RELEASE-HARDENING.md](v2/2.4/RELEASE-HARDENING.md).


## Rendered (browser) acceptance

- Engine capture adapter: the AR-222 `ChromiumRenderAdapter` (Playwright +
  Chromium). **Verified live on Windows** in this release: T1 UI tasks captured
  viewport and interaction evidence, a staged interaction defect failed the
  capture, the bounded repair fixed it, and the recapture bound fresh evidence to
  the new revision.
- `ariadne doctor` reports the capture capability before a task starts. When a
  browser is unavailable, UI tasks record the rendered requirement as unresolved
  instead of claiming visual success; no silent downgrade exists.

### Design captures can use that same pipeline (2.3C-R)

The design workflow's own capture events (`record-design` `rendered-evidence`
and `rendered-verify`) can use **`chromium-render`**: the same AR-222 Chromium
pipeline the task flow uses, serving the project's own surface (`dist/` when it
exists, otherwise the project root). A capture happens only when an operator
names the adapter in an explicit event — nothing starts a browser implicitly —
and the artifact carries the manifest provenance browser-render evidence
demands, bound to the project's render-source digest. `rendered-verify`
re-captures the recorded spec in an independent engine execution and requires
byte-for-byte equality, so a rendered requirement can close as `verified` only
when the browser genuinely reproduces the artifact. An operator-supplied
declared observer still exists and is still capped at RENDERED by design.

## Platforms

| Platform | Status |
|---|---|
| Windows | **Verified live** (development platform: runtime bundle, distribution lifecycle, wheel install, rollback, all suites). |
| macOS | Not executed here. No platform-specific code paths are known; run `python scripts/test-distribution.py`, `python scripts/test-wheel-install.py`, `python scripts/release-check.py`. |
| Linux | Not executed here. Same procedure as macOS. Nothing in this release claims native macOS/Linux verification. |

## Known limitations (2.4A execution-reliability closure)

1. **S4B scope contracts are checked against the plan before a worker runs, and
   an authorization refusal is resolved only by a human.** Preparation refuses a
   handoff whose own plan declarations or stage-required outputs (`QA.md`,
   `AGENTS.md`) are not covered by the permitted-files table; approval can no
   longer be under-declared into a blocked worker. Routing still never continues
   around an authorization refusal; `ariadne.py resolve-authorization` records
   the human's identity-bound decision once the reconciled contract provably
   covers every refused path and the repository's current deviation, and it
   permits exactly one new attempt. Without a human decision the boundary stays
   blocked by design.
2. **Post-review correction is now a linked lifecycle, not a dead end (2.4A).**
   A failed review of the current validated attempt authorizes one bounded
   corrective attempt, which names its parent attempt and the review finding,
   preserves the earlier evidence, re-runs the required checks on the corrected
   revision, records a fresh revision-bound validation, and requires a new
   independent review. Routine repair and review-directed correction have
   separate budgets. T1 implements this end to end; S4B re-enters the
   implementation boundary from S5 with a review-finding retry context and the
   deterministic benchmark case `lifecycle.s4b-review-correction` drives a full
   failed-review -> corrected S4B -> fresh validation -> second S5 review ->
   G3 acceptance path. In 2.4A-R the live external path was exercised: a fresh
   OpenCode 2.2.5 / GitHub Copilot session reviewed the served page, found a
   real invalid-input defect (plus a material-depth and a per-tick network
   finding), the linked corrective attempt was freshly validated, and a second
   fresh session passed the corrected revision. The engine records
   `DISTINCT_RUNTIME` rather than `DISTINCT_PROVIDER` because it did not certify
   a provider-observed difference; the harnesses were Command Code/DeepSeek and
   OpenCode/GitHub Copilot. The creative final gate remains the human G3. At
   the 2.4A-R boundary the `verify` VP receipt bound the corrected validation
   but not the S5 review; 2.4C binds the current review into the receipt and
   refuses a stale, failed, substituted or non-independent one. Stale
   validation, cross-attempt evidence, forged reviewer identity, stale or
   forged proof receipts, out-of-scope corrections and exhausted budgets are
   refused by name.

   The 2.3C-R history is retained rather than rewritten: a validation recorded
   before the revision-binding wiring is still refused, not guessed at (the
   `VP-0005` generative-UI record remains `PARTIAL / TEST outstanding`), and the
   recorded 2.3C acceptance record still stands as history. 2.4A changes the
   *future* lifecycle; it does not retroactively convert an old record.

   **Recovery limitation.** `task-recover` reports and resumes interruptions
   whose effect can be established from durable evidence. A worker that never
   produced a return and whose execution is still open requires the operator to
   declare it lost with `--abandon-open`; the engine does not infer death from a
   process that disappeared. An orphan packet whose state write was lost is
   preserved and reported; the safe continuation may still need a human
   inspection rather than automatic adoption. Local run-state files are not
   cryptographically attested.
3. **Review independence is mechanical, plus whatever the environment offers.**
   The engine binds reviewer identities to separate executions parented onto the
   implementer's, and the independence ladder is honest about what a record can
   prove (2.3C-R acceptance pass): `DISTINCT_PROVIDER` is granted only when the
   *provider-observed* provider/model differs on both sides, so two executions
   on the same provider carrying different requested or declared labels stay
   `DISTINCT_RUNTIME` instead of being mislabelled as distinct providers. The
   2.3C-R S5 review ran in a fresh isolated external Codex CLI session with no
   build context — a genuinely separate execution — and the review's own
   limitation (its sandbox could not launch a browser, so rendered behaviour
   remains unverified *by the reviewer*) is recorded in its judgement; the
   later engagements were supplied revision-bound engine captures and stated
   what they could verify firsthand. When one agent plays both roles,
   independence is protocol-level; record that limitation when it applies.
4. **External skill bodies are scanned, not sandboxed.** The trust scan refuses
   known dangerous classes; a sufficiently creative hostile document could still
   be misleading prose. That is why approval is per-digest, per-identity, and
   per-family rather than open.
5. **Memory is per-run.** Approvals, memory, and rendered evidence live in a
   project's run state; separate projects are separate trust domains by design.
6. **The design capture bridge reproduces only what the environment
   reproduces.** `chromium-render` needs a working Playwright + Chromium; where
   none exists, capture events refuse with the probe's reason and nothing
   degrades to fixture bytes. Byte-for-byte re-production is verified on this
   platform; a platform whose Chromium renders text differently would honestly
   fail verification rather than pass it.
7. **A validation command inherits the ambient interpreter.** The engine runs
   the contract's command with the process environment; `python -m pytest`
   therefore depends on which `python` the host resolves. The live 2.4A-R run
   hit an interpreter without pytest and recorded the failure honestly; the
   repaired attempt used `PYTHONPATH` to the existing site-packages rather than
   installing anything. A contract that names `python` should ensure the test
   runner is importable, or name the interpreter explicitly.
