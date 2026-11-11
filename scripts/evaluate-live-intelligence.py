#!/usr/bin/env python3
"""Ariadne 2.4C: bounded live intelligence qualification.

This script runs the *real* T1 task path against authenticated CLI harnesses on
this host. It is deliberately small: six comparable workloads, two execution
routes, one trial per cell, plus a matched ``context_reduction`` comparison on
two context-heavy workloads. It never invents usage, never ranks a model from
one run, and never promotes a route.

Everything it can establish is recorded as a row:

    provider, model, harness, identity provenance, starting revision,
    execution configuration, context profile, packet bytes, duration,
    validation, repair count, review, proof, usage, evidence location

A missing provider is an environment blocker, not a skip presented as success.
A failed task is a real outcome. ``UNKNOWN`` is never written as zero.

Run:
    python scripts/evaluate-live-intelligence.py --routes command-code,opencode
    python scripts/evaluate-live-intelligence.py --routes command-code --tasks simple
    python scripts/evaluate-live-intelligence.py --resume
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
VERSION = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
SCHEMA = "ariadne-24c-live-qualification-1"

DEFAULT_TASKS = ("simple", "multi", "feature", "refactor", "context-heavy", "ui")
ADAPTIVE_TASKS = ("context-heavy", "ui")

# The validation command is part of the workload definition and must be the
# same on every route. Naming the interpreter absolutely avoids a host PATH
# difference becoming a fake task failure; it is the same interpreter the
# harness runs under, and the task still reruns the project's own pytest.
PYTEST = sys.executable.replace("\\", "/") + " -m pytest -q"

ROUTE_CONFIG = {
    "command-code": {
        "command": "command-code",
        "model": "deepseek/deepseek-v4.1-flash",
        "model_source": "ADAPTER_ARGV",
        "provider": "Command Code",
    },
    "opencode": {
        "command": "opencode",
        "model": "commandcode/deepseek/deepseek-v4.1-flash",
        "model_source": "OPENCODE_CONFIG",
        "provider": "Command Code (via OpenCode)",
    },
    "codex": {
        "command": "codex",
        "model": "gpt-6.1-terra",
        "model_source": "CODEX_CONFIG",
        "provider": "OpenAI",
    },
}

GITIGNORE = "__pycache__/\n.pytest_cache/\n*.pyc\n.venv/\n"

SIMPLE_FILES = {
    "export.py": (
        "def export_rows(rows):\n"
        "    return \"\\n\".join(\",\".join(str(cell) for cell in row) for row in rows)\n"
    ),
    "test_export.py": (
        "from export import export_rows\n\n\n"
        "def test_export_quotes_fields_with_commas():\n"
        "    assert export_rows([[\"a\", \"b,c\"]]) == 'a,\"b,c\"'\n\n\n"
        "def test_export_trims_trailing_newline():\n"
        "    assert export_rows([[\"x\"]]) == \"x\"\n"
    ),
}

MULTI_FILES = {
    "pricing.py": (
        "def line_total(price, quantity):\n"
        "    return price\n\n\n"
        "def order_total(items):\n"
        "    return sum(line_total(price, quantity) for price, quantity in items)\n"
    ),
    "orders.py": (
        "from pricing import order_total\n\n\n"
        "def summarize(items):\n"
        "    return {\"total\": order_total(items), \"count\": len(items)}\n"
    ),
    "test_orders.py": (
        "from orders import summarize\n\n\n"
        "def test_order_total_multiplies_quantity():\n"
        "    assert summarize([(10, 2), (5, 1)]) == {\"total\": 25, \"count\": 2}\n\n\n"
        "def test_empty_order_is_zero():\n"
        "    assert summarize([]) == {\"total\": 0, \"count\": 0}\n"
    ),
}

FEATURE_FILES = {
    "export.py": (
        "def export_rows(rows):\n"
        "    return \"\\n\".join(\",\".join(str(cell) for cell in row) for row in rows)\n"
    ),
    "test_export.py": (
        "from export import export_rows\n\n\n"
        "def test_existing_output_is_unchanged():\n"
        "    assert export_rows([[\"a\", \"b\"]]) == \"a,b\"\n\n\n"
        "def test_optional_header_is_written_first():\n"
        "    assert export_rows([[\"a\", \"b\"]], header=[\"x\", \"y\"]) == \"x,y\\na,b\"\n\n\n"
        "def test_header_is_optional():\n"
        "    assert export_rows([[\"a\"]]) == \"a\"\n"
    ),
}

REFACTOR_FILES = {
    "report.py": (
        "def render_people(rows):\n"
        "    lines = []\n"
        "    for row in rows:\n"
        "        lines.append(\",\".join(str(cell) for cell in row))\n"
        "    return \"\\n\".join(lines)\n\n\n"
        "def render_totals(rows):\n"
        "    lines = []\n"
        "    for row in rows:\n"
        "        lines.append(\",\".join(str(cell) for cell in row))\n"
        "    return \"\\n\".join(lines)\n"
    ),
    "test_report.py": (
        "from report import render_people, render_totals\n\n\n"
        "def test_people_output_is_stable():\n"
        "    assert render_people([[\"Ada\", 2], [\"Bo\", 3]]) == \"Ada,2\\nBo,3\"\n\n\n"
        "def test_totals_output_is_stable():\n"
        "    assert render_totals([[1, 2], [3, 4]]) == \"1,2\\n3,4\"\n"
    ),
}


def _context_files() -> dict[str, str]:
    files = {
        "src/app/__init__.py": "",
        "tests/test_report.py": (
            "from src.app.report import summarize\n\n\n"
            "def test_report_totals_values_not_rows():\n"
            "    assert summarize([{\"amount\": 2}, {\"amount\": 5}]) == {\"total\": 7, \"rows\": 2}\n\n\n"
            "def test_empty_report_is_zero():\n"
            "    assert summarize([]) == {\"total\": 0, \"rows\": 0}\n"
        ),
        "src/app/report.py": (
            "def summarize(rows):\n"
            "    return {\"total\": len(rows), \"rows\": len(rows)}\n"
        ),
    }
    for index in range(1, 25):
        files[f"src/app/module_{index:02d}.py"] = (
            f"\"\"\"Support module {index:02d}; unchanged by this task.\"\"\"\n\n"
            f"def transform_{index:02d}(value):\n"
            f"    return value + {index}\n"
        )
    files["src/__init__.py"] = ""
    files["tests/__init__.py"] = ""
    return files


CONTEXT_FILES = _context_files()

UI_FILES = {
    "index.html": """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Focus Countdown</title>
  <link rel="stylesheet" href="styles.css">
</head>
<body>
  <header class="site-header">
    <a class="brand" href="/">Focus</a>
    <nav aria-label="Primary">
      <a href="#timer">Timer</a>
      <a href="#about">About</a>
      <a href="#settings">Settings</a>
    </nav>
  </header>
  <main id="timer">
    <h1>Quiet countdown</h1>
    <p class="lede">Set a duration and let the timer hold the room.</p>
    <form id="timer-form" novalidate>
      <label for="duration">Minutes</label>
      <input id="duration" name="duration" type="text" inputmode="numeric" value="25">
      <button type="submit">Start</button>
      <p id="feedback" class="feedback" aria-live="polite"></p>
    </form>
    <output id="clock" aria-live="polite">25:00</output>
  </main>
  <section id="about">
    <h2>About</h2>
    <p>A small instrument for a single uninterrupted block.</p>
  </section>
  <section id="settings">
    <h2>Settings</h2>
    <p>Nothing to configure yet.</p>
  </section>
  <script src="app.js"></script>
</body>
</html>
""",
    "styles.css": """* { box-sizing: border-box; }
body {
  margin: 0;
  font-family: Georgia, serif;
  background: #f7f4ee;
  color: #9a948b;
}
.site-header {
  display: flex;
  gap: 24px;
  align-items: center;
  padding: 20px 48px;
}
.site-header nav { display: flex; gap: 18px; }
.site-header a { color: inherit; text-decoration: none; }
main { width: 980px; margin: 0 auto; padding: 48px 0; }
h1 { font-size: 56px; margin: 0 0 16px; }
.lede { font-size: 20px; }
form { display: flex; gap: 12px; align-items: end; margin-top: 40px; }
input {
  width: 120px;
  padding: 10px;
  border: 1px solid #cfc8bd;
  background: #ffffff;
  color: #9a948b;
}
button {
  padding: 10px 18px;
  border: 0;
  background: #1f2937;
  color: #ffffff;
  cursor: pointer;
}
button:focus { outline: none; }
input:focus { outline: none; }
#clock { display: block; font-size: 96px; margin-top: 40px; }
.feedback { min-height: 24px; }
""",
    "app.js": """(function () {
  const form = document.getElementById('timer-form');
  const input = document.getElementById('duration');
  const feedback = document.getElementById('feedback');
  const clock = document.getElementById('clock');

  function render(minutes) {
    const safe = Math.max(0, Number(minutes) || 0);
    const whole = Math.floor(safe);
    const seconds = Math.round((safe - whole) * 60);
    clock.textContent = String(whole).padStart(2, '0') + ':' + String(seconds).padStart(2, '0');
  }

  form.addEventListener('submit', function (event) {
    event.preventDefault();
    const value = Number(input.value);
    if (!Number.isFinite(value) || value <= 0 || value > 180) {
      feedback.textContent = '';
      return;
    }
    feedback.textContent = 'Timer set for ' + value + ' minute(s).';
    render(value);
  });

  render(input.value);
})();
""",
    "tests/test_ui_contract.py": """import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / 'index.html').read_text(encoding='utf-8')
CSS = (ROOT / 'styles.css').read_text(encoding='utf-8')
JS = (ROOT / 'app.js').read_text(encoding='utf-8')


def _rgb(value):
    value = value.strip().lower()
    if value.startswith('#'):
        hex_value = value[1:]
        if len(hex_value) == 3:
            hex_value = ''.join(ch * 2 for ch in hex_value)
        return tuple(int(hex_value[i:i + 2], 16) for i in (0, 2, 4))
    match = re.match(r'rgba?\\(([^)]+)\\)', value)
    if match:
        parts = [p.strip() for p in match.group(1).split(',')]
        return tuple(int(float(p)) for p in parts[:3])
    raise AssertionError('unsupported colour: ' + value)


def _luminance(rgb):
    def channel(value):
        value = value / 255
        return value / 12.92 if value <= 0.03928 else ((value + 0.055) / 1.055) ** 2.4
    r, g, b = (channel(v) for v in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _contrast(a, b):
    la, lb = _luminance(_rgb(a)), _luminance(_rgb(b))
    lighter, darker = max(la, lb), min(la, lb)
    return (lighter + 0.05) / (darker + 0.05)


def test_body_text_meets_aa_contrast():
    body = re.search(r'(?s)body\\s*\\{(.*?)\\}', CSS).group(1)
    colour = re.search(r'(?m)^\\s*color:\\s*([^;]+);', body).group(1)
    background = re.search(r'(?m)^\\s*background:\\s*([^;]+);', body).group(1)
    assert _contrast(colour, background) >= 4.5


def test_keyboard_focus_is_visible():
    assert ':focus-visible' in CSS
    focus_block = CSS[CSS.index(':focus-visible'):]
    assert re.search(r'outline:\\s*(?!none)[^;]+;', focus_block), focus_block[:200]


def test_input_has_an_accessible_name():
    assert re.search(r'<label[^>]+for="duration"', HTML)
    assert 'id="duration"' in HTML


def test_invalid_input_gets_inline_feedback():
    assert 'role="alert"' in HTML or 'role="alert"' in JS
    assert 'aria-invalid' in JS
    assert 'Enter a duration' in JS


def test_mobile_layout_does_not_overflow():
    assert 'flex-wrap: wrap' in CSS
    assert re.search(r'@media\\s*\\(max-width:\\s*(480|600)px\\)', CSS)
""",
}

TASKS: dict[str, dict[str, Any]] = {
    "simple": {
        "request": "Fix the failing CSV export in export.py so fields containing commas are quoted.",
        "object": "CSV export in export.py",
        "intent": "bug",
        "scope": ["export.py"],
        "files": SIMPLE_FILES,
        "validation": PYTEST,
    },
    "multi": {
        "request": (
            "Fix the order-total defect across pricing.py and orders.py. A line total must "
            "multiply price by quantity, and the public functions must keep their signatures."
        ),
        "object": "order totals in pricing.py and orders.py",
        "intent": "bug",
        "scope": ["pricing.py", "orders.py"],
        "files": MULTI_FILES,
        "validation": PYTEST,
    },
    "feature": {
        "request": (
            "Add an optional header row argument to export_rows in export.py without changing "
            "existing callers or their output."
        ),
        "object": "CSV export header option in export.py",
        "intent": "feature",
        "scope": ["export.py"],
        "files": FEATURE_FILES,
        "validation": PYTEST,
    },
    "refactor": {
        "request": (
            "Refactor report.py so both render functions share one CSV formatting helper while "
            "preserving every public output byte-for-byte."
        ),
        "object": "CSV formatting in report.py",
        "intent": "refactor",
        "scope": ["report.py"],
        "files": REFACTOR_FILES,
        "validation": PYTEST,
    },
    "context-heavy": {
        "request": (
            "Audit the src/app package and fix the report summary bug in src/app/report.py. "
            "The total must add the row amounts, not count rows. Do not change the other modules."
        ),
        "object": "report summary in src/app/report.py",
        "intent": "bug",
        # Explicit paths are deliberate: adaptive reduction only has an
        # optional unchanged source to omit when the scope contains more than
        # the one file the request names, and the task planner expands declared
        # scope paths per file rather than expanding a glob here.
        "scope": (
            ["src/app/report.py", "src/app/__init__.py", "src/__init__.py", "tests/test_report.py"]
            + [f"src/app/module_{index:02d}.py" for index in range(1, 25)]
        ),
        "files": CONTEXT_FILES,
        "validation": PYTEST,
    },
    "ui": {
        "request": (
            "Repair the countdown page's accessibility and narrow-layout defects: AA text "
            "contrast, visible keyboard focus, an accessible duration field, inline invalid-input "
            "feedback with aria-invalid and a role=alert message, and no horizontal overflow on a "
            "narrow phone. Keep the existing timer behaviour. Do not edit the tests."
        ),
        "object": "countdown page accessibility in index.html, styles.css and app.js",
        "intent": "bug",
        "scope": ["index.html", "styles.css", "app.js"],
        "files": UI_FILES,
        "validation": PYTEST,
    },
}


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def run(command: list[str], *, cwd: Path, timeout: int, env: dict | None = None) -> dict:
    started = time.perf_counter()
    merged = dict(os.environ)
    if env:
        merged.update(env)
    try:
        completed = subprocess.run(
            command, cwd=str(cwd), capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=timeout, env=merged,
        )
        return {
            "command": command,
            "exit_code": completed.returncode,
            "stdout": completed.stdout[-12000:],
            "stderr": completed.stderr[-12000:],
            "duration_seconds": round(time.perf_counter() - started, 3),
            "timed_out": False,
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "command": command,
            "exit_code": None,
            "stdout": str(exc.stdout or "")[-12000:],
            "stderr": str(exc.stderr or "")[-12000:],
            "duration_seconds": round(time.perf_counter() - started, 3),
            "timed_out": True,
        }
    except OSError as exc:
        return {
            "command": command,
            "exit_code": None,
            "stdout": "",
            "stderr": f"{type(exc).__name__}: {exc}",
            "duration_seconds": round(time.perf_counter() - started, 3),
            "timed_out": False,
            "environment_error": True,
        }


def git(project: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", *args], cwd=str(project), capture_output=True, text=True,
        encoding="utf-8", errors="replace",
    )
    return (completed.stdout or completed.stderr).strip()


def make_project(root: Path, task: dict) -> Path:
    project = root / "project"
    if project.exists():
        # A previous failed cell may have left a locked project directory. A
        # fresh directory keeps the run comparable and never reuses mutated bytes.
        project = root / f"project-{uuid.uuid4().hex[:8]}"
    project.mkdir(parents=True)
    for relative, text in task["files"].items():
        path = project / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8", newline="\n")
    (project / ".gitignore").write_text(GITIGNORE, encoding="utf-8")
    (project / "README.md").write_text(
        "# Live qualification fixture\n\n"
        "A disposable project for Ariadne 2.4C. It is generated by\n"
        "`scripts/evaluate-live-intelligence.py` and is not a user project.\n",
        encoding="utf-8",
    )
    git(project, "init", "-q")
    git(project, "add", "-A")
    git(project, "-c", "user.email=fixture@example.invalid", "-c", "user.name=Fixture",
        "commit", "-qm", "fixture baseline")
    return project


def probe_route(route: str) -> dict:
    config = ROUTE_CONFIG[route]
    command = shutil.which(str(config["command"]))
    row: dict[str, Any] = {
        "route": route,
        "provider": config["provider"],
        "declared_model": config["model"],
        "model_source": config["model_source"],
        "command": str(config["command"]),
        "executable": command or "",
        "version": "",
        "authentication": "UNKNOWN",
    }
    if not command:
        row["version"] = "not found"
        row["authentication"] = "ABSENT"
        return row
    version = run([command, "--version"], cwd=ROOT, timeout=60)
    first = (version["stdout"] or version["stderr"]).strip().splitlines()
    row["version"] = first[0][:160] if first else f"exit {version['exit_code']}"
    if route == "codex":
        status = run([command, "login", "status"], cwd=ROOT, timeout=60)
        text = (status["stdout"] + status["stderr"]).lower()
        row["authentication"] = "AUTHENTICATED" if "logged in" in text else "UNCONFIRMED"
    elif route == "opencode":
        config_path = Path(os.environ.get("USERPROFILE", "")) / ".config" / "opencode" / "opencode.jsonc"
        if config_path.is_file():
            text = config_path.read_text(encoding="utf-8")
            match = re.search(r'"model"\s*:\s*"([^"]+)"', text)
            if match:
                row["declared_model"] = match.group(1)
        row["authentication"] = "CONFIGURED"
    elif route == "command-code":
        row["authentication"] = "OBSERVED_ON_RUN" if command else "ABSENT"
    return row


def read_state(run_root: Path) -> dict:
    path = run_root / "ariadne-run.json"
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def execution_identity(state: dict, task: dict) -> dict:
    execution_ids = []
    for attempt in (task.get("attempts") or []):
        if isinstance(attempt, dict):
            execution_ids.append(str(attempt.get("execution_id", "")))
            worker = attempt.get("worker") if isinstance(attempt.get("worker"), dict) else {}
            execution_ids.append(str(worker.get("execution_id", "")))
    rows = []
    for record in state.get("executions") or []:
        if not isinstance(record, dict):
            continue
        if execution_ids and str(record.get("execution_id", "")) not in execution_ids:
            continue
        rows.append({
            "execution_id": str(record.get("execution_id", "")),
            "adapter": str(record.get("adapter", "")),
            "state": str(record.get("state", "")),
            "requested": dict(record.get("requested") or {}),
            "reported": dict(record.get("reported") or {}),
            "observed": dict(record.get("observed") or {}),
            "provider_observed": dict(record.get("provider_observed") or {}),
        })
    return {
        "records": rows,
        "provider_observed_identity": next(
            (row["provider_observed"] for row in rows if row["provider_observed"]), {}
        ),
        "observed_identity": next((row["observed"] for row in rows if row["observed"]), {}),
        "requested_identity": next((row["requested"] for row in rows if row["requested"]), {}),
    }


def context_row(state: dict, packet: Path | None) -> dict:
    decisions = state.get("context_decisions") or []
    last = decisions[-1] if decisions and isinstance(decisions[-1], dict) else {}
    packet_bytes = 0
    if packet is not None and (packet / "packet.txt").is_file():
        packet_bytes = (packet / "packet.txt").stat().st_size
    return {
        "decision_id": str(last.get("decision_id", "")),
        "reduction": str(last.get("reduction", "")),
        "candidates": int(last.get("candidates", 0) or 0),
        "included_bytes": int(last.get("included_bytes", 0) or 0),
        "omitted_bytes": int(last.get("omitted_bytes", 0) or 0),
        "delivered": len([row for row in last.get("decisions") or []
                          if isinstance(row, dict) and row.get("decision") == "included"]),
        "omitted": len([row for row in last.get("decisions") or []
                        if isinstance(row, dict) and row.get("decision") == "omitted"]),
        "required_omitted": [
            str(row.get("label", "")) for row in last.get("decisions") or []
            if isinstance(row, dict) and row.get("decision") == "omitted"
            and str(row.get("reason", "")) not in (
                "OPTIONAL_NOT_SELECTED", "SUPERSEDED", "EMPTY_SOURCE", "DUPLICATE_CONTENT",
            )
        ],
        "packet_bytes": int(packet_bytes),
    }


def attempt_row(task: dict) -> dict:
    attempts = [row for row in (task.get("attempts") or []) if isinstance(row, dict)]
    last = attempts[-1] if attempts else {}
    validation = dict(last.get("validation") or {})
    return {
        "attempt_id": str(last.get("attempt_id", "")),
        "state": str(last.get("state", "")),
        "adapter": str(last.get("adapter", "")),
        "validation_status": str(validation.get("status", "")),
        "failure_kind": str(validation.get("failure_kind", "")),
        "scope_status": str((validation.get("scope") or {}).get("status", "")),
        "changed_files": list(validation.get("changed", []) or []),
        "implementation_fingerprint": str(
            (validation.get("validated_revision") or {}).get("implementation_fingerprint", "")
        ),
        "repair_count": max(0, len(attempts) - 1),
        "review": dict(task.get("review") or {}),
        "proof": dict(task.get("proof") or {}),
    }


def usage_from_output(text: str) -> dict:
    """Only explicit provider-reported usage is recorded; prose is not a metric."""
    patterns = (
        r"(?im)^\s*total tokens?\s*[:=]\s*([0-9][0-9,]*)\s*$",
        r"(?im)^\s*input tokens?\s*[:=]\s*([0-9][0-9,]*)\s*$",
        r"(?im)^\s*output tokens?\s*[:=]\s*([0-9][0-9,]*)\s*$",
    )
    found = {}
    for index, pattern in enumerate(patterns):
        match = re.search(pattern, text)
        if match:
            found[("total", "input", "output")[index]] = int(match.group(1).replace(",", ""))
    if found:
        return {"classification": "REPORTED", "source": "adapter output", "tokens": found}
    return {
        "classification": "UNKNOWN",
        "source": "no provider token report was present in the adapter output",
        "tokens": {},
    }


def run_cell(
    *,
    route: str,
    task_name: str,
    reduction: str,
    trial: int,
    cell_root: Path,
    timeout: int,
) -> dict:
    task = TASKS[task_name]
    if cell_root.exists():
        try:
            cell_root.rename(cell_root.with_name(f"{cell_root.name}.stale-{int(time.time())}"))
        except OSError:
            shutil.rmtree(cell_root, ignore_errors=True)
    cell_root.mkdir(parents=True, exist_ok=True)
    project = make_project(cell_root, task)
    run_root = cell_root / "ariadne-run"
    if run_root.exists():
        run_root = cell_root / f"ariadne-run-{uuid.uuid4().hex[:8]}"
    starting_revision = git(project, "rev-parse", "HEAD")
    row: dict[str, Any] = {
        "schema_version": SCHEMA,
        "cell_id": f"{route}-{task_name}-{reduction}-t{trial}",
        "route": route,
        "task": task_name,
        "trial": trial,
        "context_profile": reduction,
        "provider": ROUTE_CONFIG[route]["provider"],
        "declared_model": ROUTE_CONFIG[route]["model"],
        "model_source": ROUTE_CONFIG[route]["model_source"],
        "harness": str(ROUTE_CONFIG[route]["command"]),
        "starting_revision": starting_revision,
        "starting_tree_digest": hashlib.sha256(
            json.dumps(task["files"], sort_keys=True).encode("utf-8")
        ).hexdigest(),
        "request": task["request"],
        "scope": list(task["scope"]),
        "validation_command": task["validation"],
        "started_at": now(),
        "evidence_root": str(cell_root),
        "status": "STARTED",
    }
    prepare_command = [
        sys.executable, str(ROOT / "scripts" / "ariadne.py"), "task-start",
        "--project", str(project), "--request", task["request"],
        "--object", task["object"], "--intent", task["intent"],
        "--validate", task["validation"],
        "--rendered", "off", "--context-reduction", reduction,
        "--model-routing", "shadow", "--run-root", str(run_root), "--run-id", row["cell_id"],
    ]
    for scope in task["scope"]:
        prepare_command.extend(["--scope", scope])
    start = run(prepare_command, cwd=ROOT, timeout=600)
    row["prepare"] = {
        "exit_code": start["exit_code"],
        "duration_seconds": start["duration_seconds"],
        "stdout": start["stdout"][-4000:],
        "stderr": start["stderr"][-4000:],
    }
    state = read_state(run_root)
    packets = state.get("packets") or []
    packet_id = str(packets[-1].get("id", "")) if packets else ""
    packet = Path(str(packets[-1].get("path", ""))) if packets else None
    row["task_id"] = packet_id
    row["context"] = context_row(state, packet)
    if start["exit_code"] != 0:
        row["status"] = "PREPARE_REFUSED"
        row["completed_at"] = now()
        return row
    execute = run([
        sys.executable, str(ROOT / "scripts" / "ariadne.py"), "task-run",
        "--run-root", str(run_root), "--adapter", route,
        "--timeout", str(timeout), "--max-attempts", "1", "--json",
    ], cwd=ROOT, timeout=timeout + 900)
    row["run"] = {
        "exit_code": execute["exit_code"],
        "duration_seconds": execute["duration_seconds"],
        "timed_out": bool(execute.get("timed_out")),
        "stdout_tail": execute["stdout"][-12000:],
        "stderr_tail": execute["stderr"][-4000:],
    }
    state = read_state(run_root)
    tasks = [item for item in (state.get("tasks") or []) if isinstance(item, dict)]
    current = tasks[-1] if tasks else {}
    row["attempt"] = attempt_row(current)
    row["identity"] = execution_identity(state, current)
    row["usage"] = usage_from_output(execute["stdout"] + "\n" + execute["stderr"])
    row["context_after"] = context_row(state, packet)
    row["proof_state"] = {
        "proof_id": str((current.get("proof") or {}).get("proof_id", "")),
        "acceptance_state": str((current.get("proof") or {}).get("acceptance_state", "")),
        "review_id": str((current.get("review") or {}).get("review_id", "")),
        "review_outcome": str((current.get("review") or {}).get("outcome", "")),
        "human_acceptance": str((state.get("worker") or {}).get("acceptance_state", "")),
    }
    validation = row["attempt"]["validation_status"]
    if execute.get("timed_out"):
        row["status"] = "TIMEOUT"
    elif validation == "passed":
        row["status"] = "VALIDATED" if row["proof_state"]["proof_id"] else "VALIDATED_NO_PROOF"
    elif validation in ("failed", "blocked"):
        row["status"] = "VALIDATION_FAILED"
    else:
        row["status"] = "RUN_INCOMPLETE"
    row["completed_at"] = now()
    return row


def summarize(rows: list[dict]) -> dict:
    cells = []
    for row in rows:
        cells.append({
            "cell_id": row.get("cell_id"),
            "route": row.get("route"),
            "task": row.get("task"),
            "profile": row.get("context_profile"),
            "status": row.get("status"),
            "duration_seconds": row.get("run", {}).get("duration_seconds"),
            "packet_bytes": row.get("context", {}).get("packet_bytes"),
            "included_bytes": row.get("context", {}).get("included_bytes"),
            "omitted_bytes": row.get("context", {}).get("omitted_bytes"),
            "validation": row.get("attempt", {}).get("validation_status"),
            "repairs": row.get("attempt", {}).get("repair_count"),
            "review": row.get("proof_state", {}).get("review_outcome"),
            "proof": row.get("proof_state", {}).get("acceptance_state"),
            "usage": row.get("usage", {}).get("classification"),
            "identity": {
                "provider_observed": bool(row.get("identity", {}).get("provider_observed_identity")),
                "observed": row.get("identity", {}).get("observed_identity"),
                "requested": row.get("identity", {}).get("requested_identity"),
            },
        })
    by_route: dict[str, dict] = {}
    for cell in cells:
        route = str(cell["route"])
        entry = by_route.setdefault(route, {"cells": 0, "validated": 0, "proofed": 0, "failed": 0})
        entry["cells"] += 1
        entry["validated"] += 1 if cell["validation"] == "passed" else 0
        entry["proofed"] += 1 if cell["proof"] == "ACCEPTED" else 0
        entry["failed"] += 1 if cell["status"] in ("VALIDATION_FAILED", "TIMEOUT") else 0
    pairs = []
    for route in sorted({str(row.get("route")) for row in rows}):
        for task in sorted({str(row.get("task")) for row in rows}):
            off = next((row for row in rows if row.get("route") == route
                        and row.get("task") == task and row.get("context_profile") == "off"), None)
            adaptive = next((row for row in rows if row.get("route") == route
                             and row.get("task") == task and row.get("context_profile") == "adaptive"), None)
            if not off or not adaptive:
                continue
            if not (off.get("context", {}).get("packet_bytes") or 0) or not (
                adaptive.get("context", {}).get("packet_bytes") or 0
            ):
                continue
            pairs.append({
                "route": route,
                "task": task,
                "off_packet_bytes": off.get("context", {}).get("packet_bytes"),
                "adaptive_packet_bytes": adaptive.get("context", {}).get("packet_bytes"),
                "bytes_saved": (off.get("context", {}).get("packet_bytes", 0)
                                - adaptive.get("context", {}).get("packet_bytes", 0)),
                "off_validation": off.get("attempt", {}).get("validation_status"),
                "adaptive_validation": adaptive.get("attempt", {}).get("validation_status"),
                "off_proof": off.get("proof_state", {}).get("acceptance_state"),
                "adaptive_proof": adaptive.get("proof_state", {}).get("acceptance_state"),
                "off_required_omitted": off.get("context", {}).get("required_omitted"),
                "adaptive_required_omitted": adaptive.get("context", {}).get("required_omitted"),
            })
    return {
        "cells": cells,
        "by_route": by_route,
        "adaptive_pairs": pairs,
        "limitations": [
            "One trial per cell is a bounded comparison, not a model ranking.",
            "Token and cost savings are UNKNOWN unless a provider reported them.",
            "Packet bytes are a request-size measurement, not a billed-token count.",
            "Provider/model identity is recorded at the level the engine observed; a "
            "configuration value is not a provider attestation.",
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--routes", default="command-code,opencode")
    parser.add_argument("--tasks", default=",".join(DEFAULT_TASKS))
    parser.add_argument("--adaptive-tasks", default=",".join(ADAPTIVE_TASKS))
    parser.add_argument("--timeout", type=int, default=900)
    parser.add_argument("--out-root", default=str(ROOT / "validation" / "runs" / "2.4c" / "live"))
    parser.add_argument("--resume", action="store_true")
    parser.add_argument(
        "--retry-failed", action="store_true",
        help="with --resume, re-run cells whose preparation or execution did not settle",
    )
    parser.add_argument("--no-adaptive", action="store_true")
    args = parser.parse_args(argv)

    routes = [item.strip() for item in args.routes.split(",") if item.strip()]
    tasks = [item.strip() for item in args.tasks.split(",") if item.strip()]
    adaptive_tasks = [] if args.no_adaptive else [
        item.strip() for item in args.adaptive_tasks.split(",") if item.strip()
    ]
    unknown = [item for item in routes if item not in ROUTE_CONFIG]
    if unknown:
        raise SystemExit(f"unknown route(s): {', '.join(unknown)}")
    unknown = [item for item in tasks + adaptive_tasks if item not in TASKS]
    if unknown:
        raise SystemExit(f"unknown task(s): {', '.join(unknown)}")

    out_root = Path(args.out_root)
    out_root.mkdir(parents=True, exist_ok=True)
    results_path = out_root / "results.json"
    rows: list[dict] = []
    if args.resume and results_path.is_file():
        try:
            rows = [row for row in json.loads(results_path.read_text(encoding="utf-8")).get("cells", [])
                    if isinstance(row, dict)]
        except (OSError, json.JSONDecodeError):
            rows = []
    retry_statuses = {"PREPARE_REFUSED", "RUN_INCOMPLETE", "ENVIRONMENT_BLOCKER"}
    if args.resume and args.retry_failed:
        rows = [row for row in rows if str(row.get("status")) not in retry_statuses]
    completed = {str(row.get("cell_id")) for row in rows}

    probes = {route: probe_route(route) for route in routes}
    (out_root / "environment.json").write_text(
        json.dumps({"schema_version": SCHEMA, "recorded_at": now(), "ariadne_version": VERSION,
                    "routes": probes}, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    cells = [(route, task, "off") for route in routes for task in tasks]
    cells.extend((route, task, "adaptive") for route in routes for task in adaptive_tasks)
    for route, task, reduction in cells:
        cell_id = f"{route}-{task}-{reduction}-t1"
        if cell_id in completed:
            print(f"skip {cell_id}: already recorded")
            continue
        probe = probes[route]
        if probe.get("authentication") == "ABSENT" or not probe.get("executable"):
            rows.append({
                "schema_version": SCHEMA, "cell_id": cell_id, "route": route, "task": task,
                "context_profile": reduction, "status": "ENVIRONMENT_BLOCKER",
                "reason": f"{ROUTE_CONFIG[route]['command']} is not installed or not executable",
                "completed_at": now(),
            })
            print(f"blocked {cell_id}: executable absent")
            continue
        print(f"run {cell_id} ...", flush=True)
        row = run_cell(
            route=route, task_name=task, reduction=reduction, trial=1,
            cell_root=out_root / "cells" / cell_id, timeout=args.timeout,
        )
        rows.append(row)
        results_path.write_text(
            json.dumps({"schema_version": SCHEMA, "ariadne_version": VERSION,
                        "updated_at": now(), "routes": probes, "cells": rows,
                        "summary": summarize(rows)}, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(f"  {row['status']}  validation={row.get('attempt', {}).get('validation_status')} "
              f"proof={row.get('proof_state', {}).get('acceptance_state')} "
              f"duration={row.get('run', {}).get('duration_seconds')}s "
              f"packet={row.get('context', {}).get('packet_bytes')}B", flush=True)

    report = {
        "schema_version": SCHEMA,
        "ariadne_version": VERSION,
        "generated_at": now(),
        "routes": probes,
        "cells": rows,
        "summary": summarize(rows),
        "note": (
            "This is a bounded live comparison. It does not rank models globally, does not "
            "claim token savings without a provider report, and does not authorize a route change."
        ),
    }
    results_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report["summary"]["by_route"], indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
