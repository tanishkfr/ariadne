#!/usr/bin/env python3
"""
Ariadne -- Test A setup.

Prepares one controlled validation run. Creates a clean project OUTSIDE this
repository, a run record from the existing template, and the exact prompt to
paste into Codex.

    python scripts/setup-test-a.py
    python scripts/setup-test-a.py --dry-run

It prepares and measures an experiment. It never runs the experiment, and it
never claims the provider did anything. Safe to run twice: an existing project
or run is never overwritten -- a new run ID is allocated instead.
"""

import os
import re
import sys
import shutil
import subprocess
import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUNS_DIR = os.path.join(ROOT, "validation", "runs")
TEMPLATE = os.path.join(ROOT, "validation", "run-template.md")
PROTOCOL = os.path.join(ROOT, "tests", "validation-protocol.md")
START_PROMPT = os.path.join(ROOT, "prompts", "project-start.md")
PERSONAL_FIXTURE = os.path.join(ROOT, "validation", "fixtures", "codex-personal-AGENTS.md")

PROJECTS_ROOT = os.path.join(os.path.expanduser("~"), "Ariadne Tests")
CODEX_HOME = os.path.join(os.path.expanduser("~"), ".codex")

DRY = "--dry-run" in sys.argv

# Windows consoles default to a codepage that mangles the em-dashes in the
# prompt. The user copies this text into Codex, so a mangled character would
# travel into the experiment.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

BAR = "-" * 64


def say(msg=""):
    print(msg)


def die(msg):
    print(f"\nSTOPPED: {msg}\n")
    sys.exit(1)


def read(p):
    with open(p, encoding="utf-8") as f:
        return f.read()


# ------------------------------------------------------------------ checks

def confirm_repo():
    """Refuse to run from anywhere that is not the Ariadne repository."""
    markers = ["ROUTER.md", "WORKFLOW.md", "scripts/check.py", "scripts/validate.py"]
    missing = [m for m in markers if not os.path.exists(os.path.join(ROOT, m))]
    if missing:
        die(f"this does not look like the Ariadne repository (missing {missing}). "
            f"Run from the repo root: python scripts/setup-test-a.py")
    return "OK"


def core_checks():
    r = subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "check.py")],
                       capture_output=True, text=True, cwd=ROOT)
    if r.returncode != 0:
        say(r.stdout)
        die("Ariadne structural checks FAILED. Fix the repository before validating "
            "with it -- a run against a broken core proves nothing.")
    return "PASS"


def frozen_state():
    """
    Confirm the repo is at the frozen V1-candidate state. Not a lock -- a
    warning, so a run is never silently recorded against an unknown version.
    """
    changelog = read(os.path.join(ROOT, "CHANGELOG.md"))
    m = re.search(r"##\s+(0\.\d+\.\d+)", changelog)
    version = f"v{m.group(1)}" if m else "unknown"
    frozen = "CORE FROZEN" in changelog or "V1 CANDIDATE" in changelog

    commit, dirty = "unknown", False
    try:
        commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                                capture_output=True, text=True, cwd=ROOT).stdout.strip()
        dirty = bool(subprocess.run(["git", "status", "--porcelain"],
                                    capture_output=True, text=True, cwd=ROOT).stdout.strip())
    except Exception:
        pass
    return version, commit, frozen, dirty


def prereqs():
    out = {}
    out["Python"] = f"{sys.version_info.major}.{sys.version_info.minor}"
    if sys.version_info < (3, 8):
        die("Python 3.10+ required.")
    try:
        g = subprocess.run(["git", "--version"], capture_output=True, text=True)
        out["Git"] = g.stdout.strip().replace("git version ", "") if g.returncode == 0 else None
    except FileNotFoundError:
        out["Git"] = None
    if not out["Git"]:
        die("Git not found on PATH. Install Git, then re-run.")
    return out


# ------------------------------------------------------------------ inputs

def test_a_prompt():
    """
    Canonical source is tests/validation-protocol.md. Read it rather than
    hardcode, so the wording cannot drift away from the protocol.
    """
    text = read(PROTOCOL)
    m = re.search(r'>\s*"([^"]*type that reacts to sound[^"]*)"', text)
    if not m:
        die("could not find the Test A prompt in tests/validation-protocol.md. "
            "The protocol is canonical -- fix it there, not here.")
    return m.group(1).strip()


def build_paste_block(request):
    """
    The existing project-start prompt, with the request substituted into its
    final line. No hints about expected confidence, mode, or answer -- those
    would contaminate the test.
    """
    text = read(START_PROMPT)
    blocks = re.findall(r"```(.*?)```", text, re.S)
    if not blocks:
        die("prompts/project-start.md has no fenced block to paste.")
    block = blocks[0].strip("\n")
    if "MY REQUEST:" not in block:
        die("prompts/project-start.md no longer ends with 'MY REQUEST:'. "
            "The prompt changed -- update this script deliberately, do not guess.")
    block = re.sub(r"MY REQUEST:.*$", f"MY REQUEST: {request}", block, flags=re.M)
    return block


# ------------------------------------------------------------------ create

def next_run_id():
    os.makedirs(RUNS_DIR, exist_ok=True)
    n = 1
    while os.path.exists(os.path.join(RUNS_DIR, f"A{n}")):
        n += 1
    return f"A{n}"


def make_project(run_id):
    """
    Clean and EMPTY. Ariadne generates PROJECT.md and AGENTS.md itself --
    pre-creating them would rig the very thing the run measures.
    """
    path = os.path.join(PROJECTS_ROOT, f"type-sound-{run_id}")
    if os.path.exists(path):
        die(f"project already exists: {path}\nNothing was destroyed. "
            f"Move or delete it, or let the next run ID be used.")
    if not DRY:
        os.makedirs(path)
        subprocess.run(["git", "init", "-q"], cwd=path, capture_output=True)
        with open(os.path.join(path, ".gitignore"), "w", encoding="utf-8") as f:
            f.write("node_modules/\n.env*\n.DS_Store\ndist/\nbuild/\n.next/\n")
    return path


def make_run_record(run_id, version, commit, project, prompt):
    run_dir = os.path.join(RUNS_DIR, run_id)
    if os.path.exists(run_dir):
        die(f"run already exists: {run_dir}")
    run_file = os.path.join(run_dir, "run.md")
    if DRY:
        return run_dir, run_file

    os.makedirs(os.path.join(run_dir, "evidence"))
    t = read(TEMPLATE)
    # The template lives in validation/; the record lives two levels deeper in
    # validation/runs/<id>/, so its relative links need the extra hops.
    t = t.replace("](../", "](../../../")
    now = datetime.datetime.now()

    def setfield(text, name, value):
        # Replace the WHOLE row. The old version stopped at the first "|", but
        # the template's placeholders contain escaped pipes, so it left the
        # tail behind: "| **Run ID** | `A2` | B1 \| B2 …>` |".
        return re.sub(r"^(\|\s*\*\*" + re.escape(name) + r"\*\*\s*\|).*$",
                      lambda m: f"{m.group(1)} `{value}` |", text, count=1, flags=re.M)

    t = setfield(t, "Run ID", run_id)
    t = setfield(t, "Date", now.strftime("%Y-%m-%d"))
    t = setfield(t, "Ariadne version", f"{version} / {commit}")
    t = setfield(t, "Test", "A")
    t = setfield(t, "Provider", "Codex")
    t = setfield(t, "Project type", "audio-reactive typography -- object deliberately unresolved")

    t = t.replace("**Raw evidence kept at:** `<paths to transcripts, screenshots, the project repo>`",
                  f"**Raw evidence kept at:** `validation/runs/{run_id}/evidence/` and `{project}`")

    t += TEST_A_CAPTURE.format(prompt=prompt, project=project, run_id=run_id)
    with open(run_file, "w", encoding="utf-8") as f:
        f.write(t)
    with open(os.path.join(run_dir, "evidence", "_README.md"), "w", encoding="utf-8") as f:
        f.write("# Raw evidence\n\nPaste the Codex transcript here as `transcript.md`, plus any "
                "screenshots.\n\n**Keep client or project material out of the Ariadne "
                "repository** (PRIVACY-POLICY.md). For Test A there is none, so the transcript "
                "is safe to keep here.\n")
    return run_dir, run_file


TEST_A_CAPTURE = """
---

## Test A capture

> Fill these in as they happen. The **routing behaviour is the measurement** —
> the final artifact is secondary. Paste the raw transcript into
> `validation/runs/{run_id}/evidence/transcript.md`.

**The prompt that was pasted** (verbatim, unmodified):

```
{prompt}
```

### First Codex response

> Paste the Routing Block exactly as it came back, before you answer anything.

```
<paste here>
```

### Routing result

| Captured | What actually happened |
|---|---|
| `ACTION` | `<>` |
| `OBJECT` | `<>` |
| `DESTINATION` | `<>` |
| Confidence | `<>` |
| Mode chosen? | `<yes — which / no, it asked>` |
| Clarifying question asked | `<the question, verbatim>` |
| Number of questions | `<>` |
| NEXT emitted? | `<yes, pointing at … / no>` |

**Your answer to the clarifying question:** `<verbatim>`

### Documents Ariadne created

| Document | Created? | Should it have been? |
|---|---|---|
| `PROJECT.md` | `<>` | required |
| `DESIGN.md` | `<>` | required |
| `AGENTS.md` | `<>` | runtime file |
| anything else | `<list>` | **each one is a finding** |

### Runtime state after the run

| Field | Value found in AGENTS.md |
|---|---|
| Stage | `<>` |
| Last gate passed | `<>` |
| Next prompt | `<>` |

### Deviations from documented behaviour

> Anything the written rules did not predict. Empty is a valid result.

`<>`

### The comparison

| | Baseline (written first) | Ariadne |
|---|---|---|
| Direction | | |
| What it refused | | |
| Signature idea | | |

**Which mechanism caused the difference** — name the rule, or write "nothing changed":

`<>`

**Was the Ariadne version actually better?** `<better / the same / worse>` — "the same" is
an important result, not a failure to report.

> Project: `{project}`
"""


def personal_agents():
    """Never silently overwrite. Back up, or leave alone and tell the user."""
    target = os.path.join(CODEX_HOME, "AGENTS.md")
    fixture = read(PERSONAL_FIXTURE)
    if DRY:
        return "dry-run", target

    os.makedirs(CODEX_HOME, exist_ok=True)
    if os.path.exists(target):
        existing = read(target)
        if existing.strip() == fixture.strip():
            return "already matches", target
        stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        backup = f"{target}.backup-{stamp}"
        shutil.copy2(target, backup)
        with open(target, "w", encoding="utf-8") as f:
            f.write(fixture)
        return f"replaced (yours backed up to {os.path.basename(backup)})", target

    with open(target, "w", encoding="utf-8") as f:
        f.write(fixture)
    return "created", target


def verify_personal(path):
    if DRY or not os.path.exists(path):
        return False
    t = read(path)
    return "Preferences only" in t and len(t.split()) > 30


# ------------------------------------------------------------------ main

def main():
    say()
    say(BAR)
    say("ARIADNE  --  TEST A SETUP")
    say(BAR)
    say()

    repo = confirm_repo()
    version, commit, frozen, dirty = frozen_state()
    pre = prereqs()
    checks = core_checks()

    say(f"  Version         {version}  ({commit})")
    say(f"  Repository      {repo}")
    say(f"  Core checks     {checks}")
    say(f"  Frozen state    {'V1 candidate, core frozen' if frozen else 'NOT MARKED FROZEN'}")
    say(f"  Python          {pre['Python']}")
    say(f"  Git             {pre['Git']}")
    if dirty:
        say()
        say("  WARNING  the repository has uncommitted changes. The run will be recorded")
        say("           against a commit that does not match what you are running.")
    say()

    request = test_a_prompt()
    paste = build_paste_block(request)
    run_id = next_run_id()
    project = make_project(run_id)
    run_dir, run_file = make_run_record(run_id, version, commit, project, paste)
    status, personal = personal_agents()
    ok = verify_personal(personal)

    say(f"  Run ID          {run_id}")
    say(f"  Codex personal  {personal}  ({status})"
        + ("  [structure OK]" if ok else "  [DRY RUN]" if DRY else "  [CHECK IT]"))
    say()
    say(BAR)
    say("CLEAN TEST PROJECT")
    say(BAR)
    say(f"  {project}")
    say("  Empty by design. Ariadne generates PROJECT.md and AGENTS.md itself --")
    say("  pre-creating them would rig the thing this run measures.")
    say()
    say(BAR)
    say("RUN RECORD")
    say(BAR)
    say(f"  {run_file}")
    say()

    say("=" * 64)
    say("STOP.  DO THIS BEFORE YOU OPEN CODEX.")
    say("=" * 64)
    say()
    say("  Write your baseline. In the run record, under '## Baseline', answer")
    say("  this WITHOUT opening any Ariadne file and WITHOUT Codex:")
    say()
    say(f'      "{request}"')
    say()
    say("      - what would you normally make?")
    say("      - what is the obvious visual solution?")
    say("      - what is the obvious interaction?")
    say("      - why would you make it that way?")
    say()
    say("  This is the only step that cannot be done afterwards. Once you have seen")
    say("  the Ariadne direction, the control is gone and the run proves nothing.")
    say()
    say("  Do NOT paste your baseline into Codex.")
    say()

    say(BAR)
    say("THEN PASTE THIS INTO CODEX  (everything between the lines)")
    say(BAR)
    say()
    print(paste)
    say()
    say(BAR)
    say(f"  Also saved to: {os.path.join(run_dir, 'PASTE-INTO-CODEX.txt')}")
    say()

    if not DRY:
        with open(os.path.join(run_dir, "PASTE-INTO-CODEX.txt"), "w", encoding="utf-8") as f:
            f.write(paste + "\n")

    say("WHILE YOU RUN IT")
    say("  - Log events in the run record as they happen. You will not remember them.")
    say("  - Do NOT modify Ariadne during the experiment.")
    say()
    say("  REQUIRED before you finish -- save the raw Codex reply to:")
    say()
    say(f"      {os.path.join(run_dir, 'evidence', 'transcript.md')}")
    say()
    say("  The routing frame, the confidence, the question and the NEXT block are")
    say("  read out of that file automatically. Without it there is no routing")
    say("  measurement and Test A has nothing to report.")
    say()
    say(BAR)
    say("WHEN CODEX HAS FINISHED")
    say(BAR)
    say()
    say("      python scripts/finish-test-a.py")
    say()
    say("  That validates the project and the record, generates RESULT.md, and")
    say("  updates the benchmark. It does not judge whether the work is good.")
    say()
    if DRY:
        say("  (dry run -- nothing was written)")
        say()
    return 0


if __name__ == "__main__":
    sys.exit(main())
