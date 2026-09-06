# INSTALL ARIADNE

Ariadne uses a small dependency-free Python launcher and a self-contained
runtime wheel. Installation is user-local and does not copy Ariadne policies,
templates, tests or source code into a project.

## Requirements

- Python 3.10 or newer.
- Codex for the `$ariadne` interface.
- Internet access to download the initial wheel. The runtime installation from
  that wheel is offline; later updates need internet access.

Node.js, pnpm, hosting accounts and implementation providers are project
requirements, not installation requirements. Ariadne asks before any project
dependency is installed.

### Python package-name compatibility

This product currently shares the Python distribution and import name
`ariadne` with the unrelated [Ariadne GraphQL package](https://pypi.org/project/ariadne/)
(verified 2026-09-05). They cannot coexist in one Python environment. Before a
first install, run:

```bash
python -m pip show ariadne
```

If the result describes a GraphQL library, stop and use a separate Python
interpreter or virtual environment for this product. Do not let pip replace an
existing application dependency. This limitation does not affect the product
name, `$ariadne` skill or user-local runtime after installation.

## Install from GitHub

Run these as your normal user:

```bash
python -m pip install --user "https://github.com/tanishkfr/ariadne/releases/download/v1.6.3/ariadne-1.6.3-py3-none-any.whl"
python -m ariadne install
python -m ariadne doctor
```

No administrator account is required. `python -m ariadne` is used here so the
instructions work even when the user scripts directory is not on `PATH`.

The first command installs the launcher. The second verifies the wheel's
embedded runtime, creates a versioned user-local installation, and registers the
managed Codex skill. A separate activation command is intentional: Python
packages have no safe portable post-install hook for writing Codex skills.

Fresh installs place the skill under `~/.agents/skills/ariadne`, the current
documented Codex user-skill location. An earlier Ariadne-managed skill under
`$CODEX_HOME/skills` or `~/.codex/skills` is reused in place so update does not
create a duplicate.

Social intelligence needs no additional installation or account connection.
It remains dormant until the user explicitly asks for distribution help.

## Optional recommended Codex baseline

Normal installation does not change your global Codex instructions. To opt in
to a short set of generic working defaults, use either:

```bash
python -m ariadne install --codex-baseline
python -m ariadne codex-baseline install
```

The command states what it changes. It will not overwrite or merge an existing
`AGENTS.md` or `AGENTS.override.md`. Project instructions remain separate and
closer to the project. Inspect or remove the managed baseline with:

```bash
python -m ariadne codex-baseline status
python -m ariadne codex-baseline remove
```

If you edit an installed baseline, update and uninstall preserve it and give up
ownership rather than deleting your work. Restart Codex after changing the
baseline. See [CODEX-ENVIRONMENT.md](CODEX-ENVIRONMENT.md) for the verified
instruction hierarchy.

## Optional Claude reasoner

Claude Code is not a dependency and is never enabled by normal installation.
If its CLI is already available and you explicitly want the experimental
reasoner entry, run:

```bash
python -m ariadne enable-claude
```

The command feature-detects the CLI and installs one managed user skill; it
does not authenticate, add a project `CLAUDE.md`, change the default provider,
or alter projects. Remove it with `python -m ariadne disable-claude`. To
restore the V1.5 baseline, disable Claude first and then use the existing
`ariadne rollback` command.

## Locations

| Platform | Default runtime location |
|---|---|
| Windows | `%LOCALAPPDATA%\Ariadne` |
| macOS | `~/Library/Application Support/Ariadne` |
| Linux | `$XDG_DATA_HOME/ariadne`, otherwise `~/.local/share/ariadne` |

The managed skill is placed in the active Codex skill home. The installer finds
that location; normal users do not configure it manually.

## First use

Open Codex in an empty directory or an existing project, invoke `$ariadne`,
and state the outcome you want. Existing files are inspected before adoption;
`PROJECT.md`, `AGENTS.md`, configuration and source are never silently replaced.

## Developer mode

Maintainers working from a checkout may build a local release with:

```bash
python scripts/build-release.py --allow-dirty --output dist
python -m pip wheel . --no-deps --no-build-isolation --wheel-dir dist
```

`scripts/install-ariadne-skill.py` remains a checkout-only compatibility tool.
It is not the public installation path.

Next: run `python -m ariadne doctor`.
