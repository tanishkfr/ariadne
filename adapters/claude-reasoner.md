# Adapter: Claude Code reasoner (experimental)

Claude Code is an optional reasoning/orchestration surface for S1, S2, S3,
S4A, isolated S5 and S6. Codex remains the default. This adapter does not make
Claude the S4B implementation provider and does not replace the existing V1.5
implementation-fallback adapter in [claude-code.md](claude-code.md).

## Entry contract

1. Claude Code must be explicitly selected for the run and detected on `PATH`.
2. Its thin user-scoped Builder OS skill locates the installed runtime and runs
   `discover` then `status` for the active project.
3. It verifies and reads the current `packet.txt`; the packet delivers every
   canonical policy, template and project input needed for that stage.
4. It writes only the canonical stage outputs named by the packet.
5. It uses `builderos.py advance` for normal evidence and continuation.
6. It never creates `CLAUDE.md`, provider-specific project state or a second
   handoff format.

Claude Code does not automatically read `AGENTS.md`. Current official guidance
says it reads `CLAUDE.md`; Builder OS deliberately avoids adding that
provider-specific file to projects. Required `AGENTS.md` content reaches Claude
through the verified stage packet instead.

## Current verified interface

Official documentation dated 2026-08-23 verifies interactive and `-p`
non-interactive operation, JSON/stream-JSON/JSON-Schema output, explicit model
selection, bounded turns, permission modes, user skills and session resume.
The local validation machine has no `claude` executable, so authentication,
models, tool behaviour, output shape and stage execution remain externally
unverified.

Sources: [CLI](https://code.claude.com/docs/en/cli-usage),
[non-interactive operation](https://code.claude.com/docs/en/headless),
[memory](https://code.claude.com/docs/en/memory),
[skills](https://code.claude.com/docs/en/slash-commands),
[permissions](https://code.claude.com/docs/en/permissions), and
[sessions](https://code.claude.com/docs/en/sessions).

## Permissions

- Never use bypass-permissions mode.
- Do not read `.env`, credentials or provider configuration.
- Read and write only the project plus the external Builder OS run directory
  named by the installed skill.
- Installs, pushes, deployments and publishing retain their existing gates.
- A provider permission prompt never becomes gate approval.

## Failure and fallback

Record a provider failure through the Builder OS controller. When no material
stage output exists, the controller may create a linked Codex retry from the
same canonical state. When any material output exists—especially a design or
handoff—it preserves the failure and pauses. The human decides whether to keep,
discard or continue that work.

Session resume is an optional provider convenience. Builder OS packet evidence
and canonical project files remain authoritative; a missing Claude session must
not lose the project.

## Unsupported claims

Until live validation, do not claim creative parity, successful Builder OS
skill discovery, authenticated non-interactive use, canonical handoff output,
provider switching execution or end-to-end completion.
