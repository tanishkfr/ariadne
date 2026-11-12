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
python -m pip install --user "https://github.com/tanishkfr/ariadne/releases/download/v2.4.0/ariadne-2.4.0-py3-none-any.whl"
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

## Install the agent skill through skills.sh

`npx skills add` installs the skill's instructions. It does not install the
Python runtime, and Ariadne does not treat the skill's presence as proof that
the runtime exists.

Recommended order:

1. Install the runtime above and confirm `python -m ariadne doctor` is healthy.
2. Inside a project, run:

```bash
npx skills add tanishkfr/ariadne --skill ariadne
```

This writes the project-local `.agents/skills/ariadne` and records
`skills-lock.json`. It leaves the user-global managed skill at
`~/.agents/skills/ariadne` untouched. The repository's skills.sh page is
<https://www.skills.sh/tanishkfr/ariadne>.

### Do not use a global install for Codex or OpenCode

The skills CLI maps both Codex and OpenCode global installs to
`~/.agents/skills/ariadne`, the path Ariadne's installer owns. A global install
(`-g`) replaces that directory, removes the managed marker, and makes
`ariadne doctor` report `managed $ariadne skill marker is missing`. The
installer then correctly refuses to overwrite the unmanaged copy.

A global install is supported only when Ariadne has no managed skill at that
path, for example a machine that wants the instructions without the engine.
If you installed that way before the runtime, remove the skill with
`npx skills remove ariadne -g -a codex` before you run `python -m ariadne install`.
Claude Code and Cursor have separate global paths, but project-local installation
remains the tested default.

### If a skills.sh copy already occupies the managed path

Do not delete a copy you may have edited, and do not bypass doctor.

1. Run `python -m ariadne doctor` and keep the failure text.
2. If the copy came from the skills CLI and has no `.ariadne-managed.json`,
   remove it with the skills CLI before restoring the runtime:
   `npx skills remove ariadne -g -a codex`.
3. If you already moved the directory aside, run the same remove command anyway
   to clear the global skills lock, then run `python -m ariadne install` and
   `python -m ariadne doctor`.
4. Reinstall the skill project-locally if you still want the instructions there.

Moving the directory aside without clearing the lock is not enough. That lock
still owns `~/.agents/skills/ariadne`, so a later `npx skills update -g` can
overwrite the managed skill, and `npx skills remove -g ariadne` deletes it even
when the managed marker is present. Never run a global skills CLI update or
remove after the managed runtime is restored.

Never edit the runtime manifest, delete a user-owned skill, or force the managed
installer over an unmanaged directory.

### Update and remove

- Skill: `npx skills update ariadne` in the project, or `npx skills remove ariadne`.
- Runtime: `python -m ariadne update`; rollback and uninstall are in
  [UPDATE.md](UPDATE.md).

`ariadne-verify` is a legacy internal note. It has no skills.sh frontmatter, is
not part of the runtime manifest, and is not installed by either path. Use the
`ariadne` skill.

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
