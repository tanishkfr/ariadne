# QUICKSTART

Requires Python 3.8 or newer and Codex.

## Install

After the `v1.5.3` release is published:

```bash
python -m pip install --user "https://github.com/tanishkfr/builder-os/releases/download/v1.5.3/builder_os-1.5.3-py3-none-any.whl"
python -m builderos install
python -m builderos doctor
```

## Start

Open Codex in your project and type:

```text
$builderos
```

## Describe

Tell Builder OS what you want to make in ordinary language. It handles setup,
context and continuation. You keep control of direction, dependencies and
release decisions.

The general Codex baseline is optional. Install it with
`python -m builderos codex-baseline install`; Builder OS leaves any existing
Codex instructions untouched.

For a finished project, you can later say: `Help me launch this project on
social.` Builder OS reads the project first, prepares a small evidence-labelled
plan and drafts, and waits for you to approve or publish anything.

Next: read [INSTALL.md](INSTALL.md) only if installation needs more detail.
