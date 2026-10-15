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

## Platforms

| Platform | Status |
|---|---|
| Windows | **Verified live** (development platform: runtime bundle, distribution lifecycle, wheel install, rollback, all suites). |
| macOS | Not executed here. No platform-specific code paths are known; run `python scripts/test-distribution.py`, `python scripts/test-wheel-install.py`, `python scripts/release-check.py`. |
| Linux | Not executed here. Same procedure as macOS. Nothing in this release claims native macOS/Linux verification. |

## Known limitations (2.3C acceptance run)

1. **S4B scope contracts are hand-derived.** The project pipeline derives a
   worker's permitted-files scope from the handoff's table. If the table
   under-declares files the plan names, the independent validation classifies the
   boundary out-of-scope; blocked results cannot enter routine repair, and
   escalation needs an external provider. The acceptance run hit exactly this and
   reports it rather than relaxing the rule.
2. **Proof Pass needs engine-rerun TEST evidence at project level.** A project
   whose S4B validation did not pass shows `PARTIAL / TEST outstanding` even when
   the site is built and browser-verified. That is the correct conservative
   reading, not a bug.
3. **Review independence is mechanical, not organisational.** The engine binds
   reviewer identities to separate executions parented onto the implementer's,
   but when one agent plays both roles the independence is protocol-level. Record
   that limitation when it applies.
4. **External skill bodies are scanned, not sandboxed.** The trust scan refuses
   known dangerous classes; a sufficiently creative hostile document could still
   be misleading prose. That is why approval is per-digest, per-identity, and
   per-family rather than open.
5. **Memory is per-run.** Approvals, memory, and rendered evidence live in a
   project's run state; separate projects are separate trust domains by design.
