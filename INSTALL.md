# INSTALL BUILDER OS

Builder OS uses a small dependency-free Python launcher and a self-contained
runtime wheel. Installation is user-local and does not copy Builder OS policies,
templates, tests or source code into a project.

## Requirements

- Python 3.8 or newer.
- Codex for the `$builderos` interface.
- Internet access to download the initial wheel. The runtime installation from
  that wheel is offline; later updates need internet access.

Node.js, pnpm, hosting accounts and implementation providers are project
requirements, not installation requirements. Builder OS asks before any project
dependency is installed.

## Public release install

Once `v1.4.0` is published, run these as your normal user:

```bash
python -m pip install --user "https://github.com/tanishkfr/builder-os/releases/download/v1.4.0/builder_os-1.4.0-py3-none-any.whl"
python -m builderos install
python -m builderos doctor
```

No administrator account is required. `python -m builderos` is used here so the
instructions work even when the user scripts directory is not on `PATH`.

The first command installs the launcher. The second verifies the wheel's
embedded runtime, creates a versioned user-local installation, and registers the
managed Codex skill. A separate activation command is intentional: Python
packages have no safe portable post-install hook for writing Codex skills.

## Locations

| Platform | Default runtime location |
|---|---|
| Windows | `%LOCALAPPDATA%\BuilderOS` |
| macOS | `~/Library/Application Support/BuilderOS` |
| Linux | `$XDG_DATA_HOME/builderos`, otherwise `~/.local/share/builderos` |

The managed skill is placed in the active Codex skill home. The installer finds
that location; normal users do not configure it manually.

## First use

Open Codex in an empty directory or an existing project, invoke `$builderos`,
and state the outcome you want. Existing files are inspected before adoption;
`PROJECT.md`, `AGENTS.md`, configuration and source are never silently replaced.

## Developer mode

Maintainers working from a checkout may build a local release with:

```bash
python scripts/build-release.py --allow-dirty --output dist
python -m pip wheel . --no-deps --no-build-isolation --wheel-dir dist
```

`scripts/install-builderos-skill.py` remains a checkout-only compatibility tool.
It is not the public installation path.

Next: run `python -m builderos doctor`.
