# QUICKSTART

Requires Python 3.10 or newer and Codex.

If `python -m pip show ariadne` already describes Ariadne GraphQL, use a
separate Python environment; the two packages cannot coexist. Details:
[INSTALL.md](INSTALL.md).

## Install

Install the current public version directly from GitHub:

```bash
python -m pip install --user "https://github.com/tanishkfr/ariadne/releases/download/v1.6.1/ariadne-1.6.1-py3-none-any.whl"
python -m ariadne install
python -m ariadne doctor
```

## Start

Open Codex in your project and type:

```text
$ariadne
```

## Describe

Tell Ariadne what you want to make in ordinary language. It handles setup,
context and continuation. You keep control of direction, dependencies and
release decisions.

The general Codex baseline is optional. Install it with
`python -m ariadne codex-baseline install`; Ariadne leaves any existing
Codex instructions untouched.

For a finished project, you can later say: `Help me launch this project on
social.` Ariadne reads the project first, prepares a small evidence-labelled
plan and drafts, and waits for you to approve or publish anything.

Next: read [INSTALL.md](INSTALL.md) only if installation needs more detail.
