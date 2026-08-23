# Codex environment contract

Evidence checked: 2026-08-23.

Ariadne uses two separate Codex mechanisms: a managed `$ariadne` skill for
the product workflow, and an optional generic user instruction baseline. The
baseline never owns Ariadne stages, gates, policies, provider choices or
project decisions.

## Verified instruction order

Codex first reads at most one user-level instruction file from its home:
`AGENTS.override.md`, otherwise `AGENTS.md`. It then walks from the project root
to the current working directory and reads at most one instruction file per
directory. Instructions nearer the current directory appear later and take
precedence. Codex discovers this chain when a task starts, so a task must be
restarted after instruction files change.

Sources: [AGENTS.md guide](https://developers.openai.com/codex/guides/agents-md)
and [customisation overview](https://developers.openai.com/codex/concepts/customization).

This means the runtime is not literally the five-layer conceptual diagram from
the product brief. In practice:

```text
user AGENTS instructions
  -> project and directory AGENTS instructions
  -> current user request

$ariadne skill
  -> locates the installed Ariadne runtime
  -> loads canonical workflow context only when invoked

project documents
  -> durable state read by that invoked workflow
```

The optional baseline supplies only the first line. Project `AGENTS.md` remains
project-owned and is closer to the work. Ariadne policy remains in the
versioned runtime and reaches a task through the skill and generated stage
context.

## Verified skill discovery

Current Codex documentation lists personal skills under
`$HOME/.agents/skills` and repository skills under `.agents/skills`. Skills use
progressive disclosure: metadata is discovered first, while full instructions
and referenced resources load when selected. Skills can be invoked explicitly
or selected from their description. Same-named skills are not merged, so the
installer reuses a recognised older managed location instead of creating a
duplicate and otherwise installs fresh users under `.agents/skills`.

Source: [Codex skills](https://developers.openai.com/codex/skills).

## Optional baseline lifecycle

Normal `ariadne install` does not change global instructions. A user opts in
with either:

```bash
python -m ariadne install --codex-baseline
python -m ariadne codex-baseline install
```

Ariadne refuses to overwrite an existing `AGENTS.md`, an existing
`AGENTS.override.md`, or an edited managed baseline. Ownership is recorded in a
separate hash-bearing marker. Update and rollback refresh only an unchanged
managed copy. Removal deletes only an unchanged managed copy; an edited copy is
preserved and becomes user-owned.

Status and removal:

```bash
python -m ariadne codex-baseline status
python -m ariadne codex-baseline remove
```

Restart Codex after installing or removing the baseline.

## Evidence classification

- **VERIFIED:** documented instruction traversal, user and project instruction
  scope, current skill directories, progressive skill loading, explicit and
  implicit skill invocation, and deterministic isolated install/update/
  rollback/remove controls.
- **REASONABLY ASSUMED:** a fresh supported Codex version will apply the same
  published discovery rules to the generated files.
- **EXTERNALLY UNVERIFIED:** a genuinely new person's first external Codex task
  discovering `$ariadne` and applying both user and project instructions.
- **BLOCKED:** no current blocker to packaging; live fresh-task evidence needs a
  human-opened external Codex task after publication or isolated candidate
  installation.

