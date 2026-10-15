# Hosts, platforms, and known limitations

> Ariadne 2.3C. This file states only what has been verified, and where. It is
> deliberately conservative: a host it lists as "declared" has an adapter and a
> discovery probe but no recorded live execution here.

## Worker hosts (task execution)

A T1 task names a worker adapter; the engine discovers, preflights, invokes,
ingests and validates through one pipeline (`ariadne_engine/task_execution.py`).
Adapter presets and their status:

| Adapter | What it is | Status in this release |
|---|---|---|
| `claude-code` | Claude Code CLI (`claude --print ...`) | **Declared.** Executable discovery verified live (`claude --version` → 2.1.245 on Windows). Live execution blocked in this environment: the CLI is installed but unauthenticated; the engine's preflight correctly refuses and classifies the failure rather than claiming success. |
| `codex` | OpenAI Codex CLI | **Declared.** Not installed here; discovery reports `not found` honestly. |
| `cursor` | Cursor agent CLI | **Declared.** Not installed here. |
| `opencode` | OpenCode CLI | **Declared.** Not installed here. |
| `host-session` | The invoking assistant session performs the packet and records the return (`task-return`) | **Verified live** (this release): a real bug-fix task was bound, performed, returned, validated, reviewed by policy and proved end to end (see the 2.3C acceptance record). |
| `manual` | A human performs the packet | Declared; the host-session path is the same protocol with a person. |
| custom CLI | `--worker-command "<argv>"` | Verified in the test suites with a real subprocess fixture worker. |

"Executable present" is never treated as "integration working": the engine
requires a preflight, a real invocation, source modification, ingestion,
independent validation, and accurate failure classification before a run counts.
Where a harness is unavailable, the suite records the limitation and
`scripts/test-ar23c.py` carries the reproducible procedure (point `--adapter
claude-code` at a repository with a failing test after authenticating the CLI).

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

## Known limitations (2.3C-R closure)

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
2. **Proof Pass needs engine-rerun TEST evidence at project level.** The engine
   does not yet record its own S4B validation reruns as project-level acceptance
   evidence, so a project that built and validated cleanly still shows
   `PARTIAL / TEST outstanding` (`VP-0004` over the generative-UI original
   request is the live example). That is the correct conservative reading, not a
   bug, and it is the largest remaining wiring gap.
3. **Review independence is mechanical, plus whatever the environment offers.**
   The engine binds reviewer identities to separate executions parented onto the
   implementer's. The 2.3C-R S5 review ran in a fresh isolated external Codex CLI
   session with no build context — a genuinely separate execution — and the
   review's own limitation (its sandbox could not launch a browser, so rendered
   behaviour remains unverified *by the reviewer*) is recorded in its judgement.
   When one agent plays both roles, independence is protocol-level; record that
   limitation when it applies.
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
