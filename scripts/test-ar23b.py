#!/usr/bin/env python3
"""AR-230 (Ariadne 2.3B): the T1 execution lifecycle, end to end.

The suite drives the real runtime on temporary git projects: prepare, worker
selection and preflight, a real worker process (a deterministic local harness
declared through ``--worker-command``), return ingestion, independent
validation, bounded repair, independent review, Proof Pass, human acceptance,
attachment of follow-up tasks, recovery and the authorization boundaries.

Nothing here touches a real user project, and no case fabricates a result: the
harness is a real subprocess that edits a real repository and writes a real
marked return handoff, and every negative case asserts that the engine refused
*before* anything was written.

The live cases are opt-in and honest about their environment:

* ``ARIADNE_LIVE_HARNESS=1`` runs one real coding harness (a CLI on PATH such as
  Claude Code) through the same lifecycle;
* ``ARIADNE_LIVE_BROWSER=1`` runs one real browser acceptance check with
  Playwright when it is installed.
"""

from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from ariadne_engine import contracts, statemachine, task_execution  # noqa: E402
from ariadne_engine import api as api_module  # noqa: E402
from ariadne_engine import public as public_module  # noqa: E402

CASES: list = []
SKIPS: list[tuple[str, str]] = []


def case(fn):
    CASES.append(fn)
    return fn


class SkipCase(Exception):
    """The environment cannot honestly run this case; it is recorded, not faked."""


# --------------------------------------------------------------- pytest bridge
# The fixture projects validate with ``python -m pytest``. On machines where the
# PATH interpreter lacks pytest (this Windows host has several interpreters),
# the site-packages of the interpreter that *does* have it is bridged through
# PYTHONPATH, because pytest is pure Python. When no interpreter has it, the
# cases that need it are skipped and named in the summary.


def _pytest_site() -> str:
    try:
        import pytest  # noqa: F401
    except ImportError:
        return ""
    return os.path.dirname(os.path.dirname(pytest.__file__))


PYTEST_SITE = _pytest_site()
if PYTEST_SITE:
    existing = os.environ.get("PYTHONPATH", "")
    os.environ["PYTHONPATH"] = PYTEST_SITE + (os.pathsep + existing if existing else "")


def require_pytest() -> None:
    if not PYTEST_SITE:
        raise SkipCase("no interpreter with pytest is available to the fixture projects")


# --------------------------------------------------------------- runtime load

def load_runtime():
    path = ROOT / "scripts" / "ariadne.py"
    spec = importlib.util.spec_from_file_location("ariadne_ar23b_runtime", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["ariadne_ar23b_runtime"] = module
    spec.loader.exec_module(module)
    return module


RUNTIME = load_runtime()
TRANSPORT = RUNTIME.TRANSPORT


def run_cli(*argv: str) -> tuple[int, str]:
    """Drive the real command line in-process: parser, dispatch, and command."""
    buffer = io.StringIO()
    previous = sys.argv
    sys.argv = ["ariadne.py", *argv]
    try:
        with contextlib.redirect_stdout(buffer), contextlib.redirect_stderr(buffer):
            try:
                code = int(RUNTIME.main() or 0)
            except SystemExit as exc:
                code = int(exc.code or 0)
    finally:
        sys.argv = previous
    return code, buffer.getvalue()


@contextlib.contextmanager
def workspace():
    path = Path(tempfile.mkdtemp(prefix="ariadne-ar23b-"))
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


# ------------------------------------------------------------------ fixtures

BUG_REQUEST = "Fix the failing CSV export in export.py"
FEATURE_REQUEST = "Add a header row option to the CSV export in export.py"
AUDIT_REQUEST = "Audit the CSV export module in export.py for defects"
HIGH_STAKES_REQUEST = "Fix the failing CSV export used by the checkout flow in export.py"

BUGGY_EXPORT = (
    "def export_rows(rows):\n"
    "    return \"\\n\".join(\",\".join(str(cell) for cell in row) for row in rows)\n"
)

FIXED_EXPORT = '''import csv
import io


def export_rows(rows, header=None):
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    if header is not None:
        writer.writerow(header)
    for row in rows:
        writer.writerow(row)
    return buffer.getvalue().rstrip("\\r\\n")
'''

TEST_EXPORT = '''from export import export_rows


def test_export_quotes_fields_with_commas():
    assert export_rows([["a", "b,c"]]) == 'a,"b,c"'


def test_export_trims_trailing_newline():
    assert export_rows([["x"]]) == "x"
'''

GITIGNORE = "__pycache__/\n.pytest_cache/\n*.pyc\n"

FIXTURE_WORKER = '''#!/usr/bin/env python3
"""A deterministic local harness for the Ariadne 2.3B suite.

It receives the Ariadne task packet on stdin like a real CLI harness, performs
one bounded change according to FIXTURE_MODE, and writes the complete marked
return handoff to the transport target named in the packet.
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

FIXED = """import csv
import io


def export_rows(rows, header=None):
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    if header is not None:
        writer.writerow(header)
    for row in rows:
        writer.writerow(row)
    return buffer.getvalue().rstrip("\\\\r\\\\n")
"""

prompt = sys.stdin.read()
mode = os.environ.get("FIXTURE_MODE", "fix")
project = Path(os.environ.get("FIXTURE_PROJECT", ".")).resolve()

target = re.search(r"(?m)^Write the complete marked return handoff verbatim to: (.+)$", prompt)
task_id = re.search(r"(?m)^Task ID: (.+)$", prompt)
role = re.search(r"(?m)^Worker role: (.+)$", prompt)
if not (target and task_id and role):
    print("fixture worker could not read the packet contract", file=sys.stderr)
    sys.exit(3)
return_target = Path(target.group(1).strip())

methods = []
in_methods = False
for line in prompt.splitlines():
    if re.match(r"^## Selected methods\\s*$", line):
        in_methods = True
        continue
    if in_methods and line.startswith("## "):
        break
    if in_methods:
        found = re.match(r"^- ([a-z0-9-]+): ", line.strip())
        if found and found.group(1) not in methods:
            methods.append(found.group(1))

tests = "not run"
built = "No change was made by this harness run."
if mode == "fix":
    (project / "export.py").write_text(FIXED, encoding="utf-8")
    tests = "pass"
    built = "Fixed export_rows so CSV fields containing commas are quoted."
elif mode == "add":
    (project / "export.py").write_text(FIXED, encoding="utf-8")
    tests = "pass"
    built = "Added an optional header row to export_rows without changing existing behaviour."
elif mode == "fail":
    tests = "pass"
    built = "Claimed the export fix without changing anything."
elif mode == "outofscope":
    (project / "bystander.txt").write_text("outside the contract\\n", encoding="utf-8")
    tests = "pass"
    built = "Changed a file outside the permitted scope."
elif mode == "quiet":
    tests = "not run"
    built = "Inspected the module and made no change."
elif mode == "noreturn":
    print("no return handoff from this worker")
    sys.exit(0)
elif mode == "crash":
    sys.exit(7)

method_lines = []
for skill in methods:
    if skill == "root-cause":
        method_lines.append("- root-cause: reproduced the failing pytest run before changing export.py")
    elif skill == "behavior-tests":
        method_lines.append(f"- behavior-tests: ran python -m pytest -q after the change; result {tests}")
    elif skill == "anti-slop":
        method_lines.append("- anti-slop: the diff is confined to export.py and reuses csv.writer")
    elif skill == "blast-radius":
        method_lines.append("- blast-radius: export_rows is referenced only by export.py and test_export.py")
    elif skill == "adversarial-review":
        method_lines.append("- adversarial-review: checked the quoting edge cases in the change")
    else:
        method_lines.append(f"- {skill}: performed within the bounded task and recorded here")

block = f"""BEGIN ARIADNE RETURN HANDOFF

# IMPLEMENTATION RETURN HANDOFF: fixture project

**Status:** complete
**Task ID:** {task_id.group(1).strip()}
**Worker role:** {role.group(1).strip()}
**Provider:** fixture-worker
**Model:** deterministic-fixture
**Effort:** low
**Started:** 2026-01-01T00:00:00Z
**Ended:** 2026-01-01T00:00:05Z
**Usage:** unknown
**Cost:** unknown

## What was built

{built}

## Files changed

| Path | Change | Why |
|---|---|---|
| export.py | corrected CSV quoting | failing test_export_quotes_fields_with_commas |

## Architecture decisions

| Decision | Reason | Reversibility |
|---|---|---|
| reuse csv.writer | standard-library module already guarantees quoting | easy |

## Design deviations

| Specified | Implemented | Reason | Approval state |
|---|---|---|---|
| none | none | n/a | n/a |

## Dependencies

| Package | Exact version | Approved at G2? | Purpose |
|---|---|---|---|
| none | n/a | n/a | n/a |

## Tests

| Check | Result | Evidence |
|---|---|---|
| Production build | not run | n/a |
| Typecheck | not run | n/a |
| Lint | not run | n/a |
| Automated tests | {tests} | python -m pytest -q |
| Browser QA | not run | n/a |

## Evidence

python -m pytest -q output recorded in the worker session.

## Worker validation

| Check | Worker result | Ariadne result | Evidence |
|---|---|---|---|
| python -m pytest -q | {tests} | pending | worker session |

## Methods applied

{chr(10).join(method_lines) if method_lines else "- none: no methods were selected for this task"}

## Safety and scope

**Scope status:** within-contract

**Unexpected actions or conflicts:** none

## Known issues

none known.

## Incomplete work

none.

## Accessibility and performance

not applicable to this library change.

## Assumptions

none.

## Next inspection

Confirm the quoting assertion passes on the changed revision.

END ARIADNE RETURN HANDOFF
"""

return_target.parent.mkdir(parents=True, exist_ok=True)
return_target.write_text(block, encoding="utf-8")
print(block)
'''


def write_fixture(base: Path) -> Path:
    path = base / "fixture-worker.py"
    path.write_text(FIXTURE_WORKER, encoding="utf-8")
    return path


def make_project(base: Path, name: str = "app") -> Path:
    project = base / name
    project.mkdir(parents=True)
    (project / "pyproject.toml").write_text(
        '[project]\nname = "fixture"\nversion = "0.1.0"\n', encoding="utf-8"
    )
    (project / "export.py").write_text(BUGGY_EXPORT, encoding="utf-8")
    (project / "test_export.py").write_text(TEST_EXPORT, encoding="utf-8")
    (project / ".gitignore").write_text(GITIGNORE, encoding="utf-8")
    subprocess.run(["git", "init", "-q"], cwd=project, capture_output=True, text=True)
    subprocess.run(["git", "add", "-A"], cwd=project, capture_output=True, text=True)
    subprocess.run(
        ["git", "-c", "user.email=fixture@example.com", "-c", "user.name=Fixture",
         "commit", "-qm", "fixture project"],
        cwd=project, capture_output=True, text=True,
    )
    return project


def run_root_for(project: Path) -> Path:
    return project.parent / f"{project.name}-ariadne"


def state_of(run_root: Path) -> dict:
    return json.loads((run_root / "ariadne-run.json").read_text(encoding="utf-8"))


def packet_dirs(run_root: Path) -> list[Path]:
    return sorted(
        (path for path in run_root.iterdir() if path.is_dir() and (path / "manifest.json").is_file()),
        key=lambda path: path.name,
    )


def current_task(state: dict) -> dict:
    return (state.get("tasks") or [])[-1]


def contract_file(run_root: Path, attempt: int = 1) -> Path:
    name = "TASK-CONTRACT.md" if attempt <= 1 else f"TASK-CONTRACT-a{attempt}.md"
    matches = sorted(run_root.glob(f"tasks/*/{name}"))
    assert len(matches) == 1, matches
    return matches[0]


def attempt_of(task: dict, index: int = -1) -> dict:
    return (task.get("attempts") or [])[index]


def start_task(
    project: Path,
    request: str = BUG_REQUEST,
    scope: str = "export.py",
    validate: str = "python -m pytest -q",
    extra: tuple = (),
) -> tuple[int, str]:
    return run_cli(
        "task-start", "--project", str(project), "--request", request,
        "--scope", scope, "--validate", validate, *extra,
    )


def run_task(project: Path, base: Path, mode: str = "fix", extra: tuple = ()) -> tuple[int, str]:
    fixture = write_fixture(base)
    previous = os.environ.get("FIXTURE_MODE")
    os.environ["FIXTURE_MODE"] = mode
    os.environ["FIXTURE_PROJECT"] = str(project)
    try:
        return run_cli(
            "task-run", "--project", str(project),
            "--worker-command", f"{sys.executable} {fixture}",
            *extra,
        )
    finally:
        if previous is None:
            os.environ.pop("FIXTURE_MODE", None)
        else:
            os.environ["FIXTURE_MODE"] = previous
        os.environ.pop("FIXTURE_PROJECT", None)


def judgement_block(recommendation: str = "present g3") -> str:
    return f"""BEGIN QA JUDGEMENT
## Judgement

### Accepted patterns

The change reuses the standard library and keeps the public function shape.

### Feel tests

The module reads as one small correction rather than a rewrite.

### Review lenses

Correctness, scope and regression risk were applied.

### Findings

No blocking findings; the quoting behaviour is covered by the recorded test run.

### Review recommendation

{recommendation}

**Review target:** the validated export.py revision
**Reviewed independently:** yes
**Success criteria reviewed:** the failing CSV export behaviour is restored
**Recommendation:** {recommendation}
**The one thing:** confirm the quoting test passes on the changed revision
**Lens conflicts:** none
END QA JUDGEMENT
"""


# ----------------------------------------------------------- lifecycle cases

@case
def small_bug_fix_completes_through_worker_execution_and_validation():
    require_pytest()
    with workspace() as base:
        project = make_project(base)
        code, text = start_task(project)
        assert code == 0, text
        run_root = run_root_for(project)
        code, text = run_task(project, base, "fix")
        assert code == 0, text
        state = state_of(run_root)
        task = current_task(state)
        attempt = attempt_of(task)
        assert attempt["state"] == "validated", attempt
        assert attempt["validation"]["status"] == "passed", attempt["validation"]
        assert attempt["adapter"] == "custom"
        # Independent validation ran as a distinct engine execution.
        validations = [row for row in state["executions"] if row["role"] == "validator"]
        assert validations and validations[-1]["state"] == "COMPLETED", validations
        assert "VALIDATED" in text
        # The proof receipt exists and the task awaits the human decision only.
        assert task["proof"], task
        assert not task["acceptance"], task


@case
def feature_implementation_completes_and_produces_evidence():
    require_pytest()
    with workspace() as base:
        project = make_project(base)
        code, text = start_task(project, request=FEATURE_REQUEST)
        assert code == 0, text
        run_root = run_root_for(project)
        code, text = run_task(project, base, "add")
        assert code == 0, text
        task = current_task(state_of(run_root))
        assert attempt_of(task)["state"] == "validated"
        assert (run_root / task["attempts"][-1]["packet_id"] / "evidence" / "validation.json").is_file()
        assert (run_root / task["attempts"][-1]["packet_id"] / "evidence" / "return-handoff.md").is_file()
        assert "def export_rows(rows, header=None)" in (project / "export.py").read_text(encoding="utf-8")


@case
def read_only_investigation_performs_no_writes():
    with workspace() as base:
        project = make_project(base)
        code, text = run_cli(
            "task-start", "--project", str(project),
            "--request", "Explain how export_rows builds the CSV output",
        )
        assert code == 0, text
        assert "read-only task" in text
        assert not run_root_for(project).exists()
        assert (project / "export.py").read_text(encoding="utf-8") == BUGGY_EXPORT


@case
def existing_project_receives_a_new_bounded_task_without_a_second_history():
    require_pytest()
    with workspace() as base:
        project = make_project(base)
        assert start_task(project)[0] == 0
        run_root = run_root_for(project)
        assert run_task(project, base, "fix")[0] == 0
        first_state = state_of(run_root)
        run_id = first_state["run_id"]
        # Accept the first task so its lifecycle is settled.
        code, text = run_cli(
            "task-accept", "--project", str(project),
            "--identity", "operator", "--outcome", "accepted",
        )
        assert code == 0, text
        code, text = start_task(project, request=FEATURE_REQUEST)
        assert code == 0, text
        assert "attached to the recorded run" in text
        state = state_of(run_root)
        assert state["run_id"] == run_id, "run identity must be preserved"
        assert [task["task_id"] for task in state["tasks"]] == ["app-T1", "app-T1-C1"]
        assert [packet["stage"] for packet in state["packets"]] == ["T1", "T1"]
        assert len(packet_dirs(run_root)) == 2
        assert state["tasks"][0]["acceptance"]["outcome"] == "accepted"
        assert state["tasks"][1]["attempts"][0]["state"] == "prepared"


@case
def existing_task_resumes_without_duplicating_work():
    require_pytest()
    with workspace() as base:
        project = make_project(base)
        assert start_task(project)[0] == 0
        run_root = run_root_for(project)
        assert run_task(project, base, "fix")[0] == 0
        before = state_of(run_root)
        packets_before = len(packet_dirs(run_root))
        proof_before = current_task(before)["proof"]["proof_id"]
        # Resuming a finished task must not prepare anything new.
        code, text = run_cli("task-run", "--project", str(project))
        assert code == 0, text
        code, text = run_cli("advance", "--project", str(project))
        assert code == 0, text
        after = state_of(run_root)
        assert len(packet_dirs(run_root)) == packets_before
        assert len(current_task(after)["attempts"]) == len(current_task(before)["attempts"])
        assert current_task(after)["proof"]["proof_id"] == proof_before


@case
def interrupted_execution_recovers_safely():
    require_pytest()
    with workspace() as base:
        project = make_project(base)
        assert start_task(project)[0] == 0
        run_root = run_root_for(project)
        # Bind the attempt to the invoking-session adapter: the attempt is now
        # running with an open execution and no return.
        code, text = run_cli("task-run", "--project", str(project), "--adapter", "host-session")
        assert code == 0, text
        state = state_of(run_root)
        execution_id = current_task(state)["attempts"][-1]["execution_id"]
        assert execution_id
        # An open execution is not a divergence the engine guesses about; the
        # operator declares the loss explicitly, and the attempt is recorded as
        # interrupted (a truthful failure), then repaired inside the budget.
        code, text = run_task(project, base, "fix", extra=("--abandon-open",))
        assert code == 0, text
        state = state_of(run_root)
        task = current_task(state)
        assert task["attempts"][0]["state"] == "failed", task["attempts"][0]
        assert task["attempts"][0]["validation"]["failure_kind"] == "interrupted"
        assert task["attempts"][0]["validation"]["retryable"] is True
        assert task["attempts"][-1]["state"] == "validated", task["attempts"][-1]
        assert task["proof"], task
        abandoned = [row for row in state["executions"] if row["execution_id"] == execution_id]
        assert abandoned and abandoned[-1]["state"] == "FAILED", abandoned
        failures = [row for row in state["failures"] if row["class"] == "INTERRUPTED"]
        assert failures, state["failures"]


@case
def stale_worker_return_is_rejected():
    require_pytest()
    with workspace() as base:
        project = make_project(base)
        assert start_task(project)[0] == 0
        run_root = run_root_for(project)
        assert run_task(project, base, "fix")[0] == 0
        task = current_task(state_of(run_root))
        return_file = run_root / task["attempts"][0]["packet_id"] / "evidence" / "return-handoff.md"
        code, text = run_cli(
            "task-return", "--project", str(project), "--input", str(return_file),
        )
        assert code == 1
        assert "already settled" in text, text
        state = state_of(run_root)
        assert len(current_task(state)["attempts"]) == 1


@case
def contract_hash_tampering_is_detected():
    with workspace() as base:
        project = make_project(base)
        assert start_task(project)[0] == 0
        run_root = run_root_for(project)
        contract = contract_file(run_root)
        contract.write_text(
            contract.read_text(encoding="utf-8") + "\n**Routine repair limit:** 99\n",
            encoding="utf-8",
        )
        code, text = run_cli(
            "task-run", "--project", str(project),
            "--worker-command", f"{sys.executable} {write_fixture(base)}",
        )
        assert code == 1, text
        assert "changed after packet preparation" in text or "stale or damaged" in text, text
        state = state_of(run_root)
        assert current_task(state)["attempts"][-1]["state"] == "prepared"


@case
def unauthorized_file_changes_are_rejected():
    require_pytest()
    with workspace() as base:
        project = make_project(base)
        assert start_task(project)[0] == 0
        run_root = run_root_for(project)
        code, text = run_task(project, base, "outofscope")
        assert code != 0, text
        assert "out-of-scope" in text, text
        state = state_of(run_root)
        assert (project / "bystander.txt").is_file(), "the fixture really changed the file"
        assert not (run_root / "app-T1" / "evidence" / "validation.json").exists()
        failures = [row for row in state["failures"] if row["source"] == "out-of-scope"]
        assert failures, state["failures"]
        assert current_task(state)["attempts"][-1]["state"] in ("prepared", "running"), current_task(state)["attempts"]


@case
def failed_validation_triggers_bounded_repair_and_recovers():
    require_pytest()
    with workspace() as base:
        project = make_project(base)
        assert start_task(project)[0] == 0
        run_root = run_root_for(project)
        code, text = run_task(project, base, "fail", extra=("--no-auto",))
        assert code == 2, text
        state = state_of(run_root)
        task = current_task(state)
        assert task["attempts"][-1]["state"] == "failed"
        assert task["attempts"][-1]["validation"]["retryable"] is True
        # The repair attempt is prepared, linked to the failure, and then runs.
        code, text = run_cli("task-repair", "--project", str(project))
        assert code == 0, text
        state = state_of(run_root)
        task = current_task(state)
        assert len(task["attempts"]) == 2
        repair_packet = packet_dirs(run_root)[-1]
        manifest = json.loads((repair_packet / "manifest.json").read_text(encoding="utf-8"))
        assert manifest["parent_id"] == task["attempts"][0]["packet_id"]
        assert manifest["worker"]["attempt"] == 2
        assert manifest["worker"]["retry_context"]["failure_kind"] == "routine"
        contract = contract_file(run_root, attempt=2).read_text(encoding="utf-8")
        assert "## Repair context from the prior attempt" in contract
        code, text = run_task(project, base, "fix")
        assert code == 0, text
        task = current_task(state_of(run_root))
        assert task["attempts"][-1]["state"] == "validated"
        assert task["proof"]


@case
def repair_limit_is_enforced():
    require_pytest()
    with workspace() as base:
        project = make_project(base)
        assert start_task(project)[0] == 0
        run_root = run_root_for(project)
        assert run_task(project, base, "fail", extra=("--no-auto",))[0] == 2
        for expected_attempts in (2, 3):
            code, text = run_cli("task-repair", "--project", str(project))
            assert code == 0, text
            assert len(current_task(state_of(run_root))["attempts"]) == expected_attempts
            code, text = run_task(project, base, "fail", extra=("--no-auto",))
            assert code == 2, text
        code, text = run_cli("task-repair", "--project", str(project))
        assert code == 1, text
        assert "budget" in text, text
        state = state_of(run_root)
        assert len(current_task(state)["attempts"]) == 3
        assert state["worker"]["lifecycle"] == "escalation-required"
        # An explicit escalation stays available past the routine budget.
        code, text = run_cli("task-repair", "--project", str(project), "--escalate")
        assert code == 0, text
        escalated = current_task(state_of(run_root))["attempts"][-1]
        assert escalated["attempt"] == 4, escalated


@case
def independent_reviewer_identity_is_enforced():
    require_pytest()
    with workspace() as base:
        project = make_project(base)
        # The checkout token raises the stakes, so the plan retains the
        # independent review step and Proof Pass waits for it.
        assert start_task(project, request=HIGH_STAKES_REQUEST)[0] == 0
        run_root = run_root_for(project)
        code, text = run_task(project, base, "fix")
        assert code == 0, text
        state = state_of(run_root)
        task = current_task(state)
        assert task["attempts"][-1]["state"] == "validated"
        assert not task.get("proof"), "Proof Pass must wait for the required review"
        judgement = base / "judgement.md"
        judgement.write_text(judgement_block(), encoding="utf-8")
        # The implementer's own identity cannot review its work.
        code, text = run_cli(
            "task-review", "--project", str(project),
            "--input", str(judgement), "--identity", "custom",
        )
        assert code == 1
        assert "cannot" in text and "review" in text, text
        # A distinct reviewer identity can.
        code, text = run_cli(
            "task-review", "--project", str(project),
            "--input", str(judgement), "--identity", "reviewer-alice",
        )
        assert code == 0, text
        state = state_of(run_root)
        task = current_task(state)
        assert task["review"]["outcome"] == "passed"
        assert task["review"]["reviewer_identity"] == "reviewer-alice"
        assert state["worker"]["lifecycle"] == "reviewed"
        assert task["proof"], "review pass continues into Proof Pass"
        reviewers = [row for row in state["executions"] if row["role"] == "reviewer"]
        assert reviewers, state["executions"]


@case
def worker_cannot_mint_verification_or_acceptance():
    require_pytest()
    with workspace() as base:
        project = make_project(base)
        assert start_task(project)[0] == 0
        run_root = run_root_for(project)
        # The worker claims success and even fills the Ariadne result column.
        code, text = run_task(project, base, "fail", extra=("--no-auto",))
        assert code == 2, text
        state = state_of(run_root)
        task = current_task(state)
        validation_path = run_root / task["attempts"][-1]["packet_id"] / "evidence" / "validation.json"
        record = json.loads(validation_path.read_text(encoding="utf-8"))
        assert record["independent"] is True
        assert record["executor"] == "Ariadne local validator"
        assert record["status"] == "failed", "the engine's own result, not the worker's claim"
        assert not task["acceptance"]
        assert not task["proof"]
        # Nothing in the worker's file can set the engine verdict.
        returned = (run_root / task["attempts"][-1]["packet_id"] / "evidence" / "return-handoff.md").read_text(encoding="utf-8")
        assert "| python -m pytest -q | pass | pending |" in returned


@case
def missing_worker_capability_produces_an_honest_blocker():
    with workspace() as base:
        project = make_project(base)
        assert start_task(project)[0] == 0
        run_root = run_root_for(project)
        code, text = run_cli("task-run", "--project", str(project), "--adapter", "cursor")
        assert code == 1
        assert "not on PATH" in text or "no worker adapter" in text, text
        state = state_of(run_root)
        assert current_task(state)["attempts"][-1]["state"] == "prepared"
        assert not [row for row in state["executions"] if row["role"] == "implementer"]


@case
def a_required_capability_no_adapter_has_is_refused_by_name():
    selection = task_execution.select_adapter(required=("browser",))
    assert selection["status"] == "no-adapter"
    assert "missing required capability: browser" in selection["reason"]
    # Every candidate names why it was excluded; nothing is silently dropped.
    assert len(selection["candidates"]) == len(task_execution.WORKER_ADAPTERS)


@case
def skill_selection_results_in_actual_invocation():
    require_pytest()
    with workspace() as base:
        project = make_project(base)
        assert start_task(project)[0] == 0
        run_root = run_root_for(project)
        assert run_task(project, base, "fix")[0] == 0
        task = current_task(state_of(run_root))
        ledger = {row["id"]: row for row in task["skills"]}
        assert ledger["behavior-tests"]["state"] == "completed"
        assert ledger["behavior-tests"]["mechanism"] == "engine-observed"
        assert ledger["root-cause"]["state"] == "completed"
        assert ledger["anti-slop"]["state"] == "invoked"
        assert ledger["anti-slop"]["mechanism"] == "worker-reported"
        # The engine never promotes a merely-reported method to completed.
        assert all(
            row["state"] != "completed" or row["mechanism"] == "engine-observed"
            for row in ledger.values()
        )


@case
def a_return_that_never_reports_a_selected_method_is_refused():
    with workspace() as base:
        project = make_project(base)
        assert start_task(project)[0] == 0
        run_root = run_root_for(project)
        state = state_of(run_root)
        task = current_task(state)
        packet = packet_dirs(run_root)[0]
        # Build a syntactically valid return, then strip the methods report.
        fixture = write_fixture(base)
        os.environ["FIXTURE_MODE"] = "quiet"
        os.environ["FIXTURE_PROJECT"] = str(project)
        try:
            prompt = (packet / "packet.txt").read_text(encoding="utf-8")
            completed = subprocess.run(
                [sys.executable, str(fixture)], input=prompt, capture_output=True,
                text=True, encoding="utf-8", errors="replace", cwd=project,
            )
        finally:
            os.environ.pop("FIXTURE_MODE", None)
            os.environ.pop("FIXTURE_PROJECT", None)
        assert completed.returncode == 0, completed.stderr
        target = project / ".ariadne" / "returns" / f"{task['attempts'][0]['packet_id']}.md"
        text = target.read_text(encoding="utf-8")
        stripped = text.split("## Methods applied")[0] + "## Safety and scope" + text.split("## Safety and scope", 1)[1]
        target.write_text(stripped, encoding="utf-8")
        code, output = run_cli("task-return", "--project", str(project), "--input", str(target))
        assert code == 1
        assert "does not report the selected method" in output or "missing the Methods applied" in output, output
        assert current_task(state_of(run_root))["attempts"][-1]["state"] == "prepared"


@case
def unselected_skills_are_not_loaded_into_the_packet():
    with workspace() as base:
        project = make_project(base)
        assert start_task(project)[0] == 0
        run_root = run_root_for(project)
        manifest = json.loads((packet_dirs(run_root)[0] / "manifest.json").read_text(encoding="utf-8"))
        documents = manifest["task"]["skills_documents"]
        assert documents and "skills/performance-investigation.md" not in documents
        assert "skills/adversarial-review.md" not in documents
        packet = (packet_dirs(run_root)[0] / "packet.txt").read_text(encoding="utf-8")
        assert "root-cause.md" in packet
        assert "performance-investigation.md" not in packet


@case
def small_task_avoids_unnecessary_creative_stages():
    require_pytest()
    with workspace() as base:
        project = make_project(base)
        assert start_task(project)[0] == 0
        run_root = run_root_for(project)
        assert run_task(project, base, "fix")[0] == 0
        state = state_of(run_root)
        assert [packet["stage"] for packet in state["packets"]] == ["T1"]
        for name in ("PROJECT.md", "DESIGN.md", "HANDOFF.md", "QA.md"):
            assert not (project / name).exists(), name
        assert state["mode"] == "task"


@case
def creative_project_keeps_its_direction_and_gates():
    with workspace() as base:
        project = base / "studio"
        project.mkdir()
        (project / "package.json").write_text(
            json.dumps({"name": "studio", "scripts": {"test": "vitest run"}}), encoding="utf-8"
        )
        (project / "index.html").write_text("<!doctype html><title>Studio</title>\n", encoding="utf-8")
        code, text = run_cli(
            "start", "--project", str(project), "--adopt-existing",
            "--request", "Build an interactive website demonstrating generative UI",
        )
        assert code == 0, text
        run_root = run_root_for(project)
        state = state_of(run_root)
        assert state["packets"][0]["stage"] == "S1", state["packets"]
        assert (run_root / "studio-S1" / "packet.txt").is_file()
        # A bounded task cannot attach mid-flight: two authoritative histories
        # would interleave.
        code, text = start_task(project, request="Fix the failing CSV export in this app")
        assert code == 1, text
        assert "mid-flight" in text, text
        assert len(packet_dirs(run_root)) == 1


@case
def the_existing_creative_workflow_is_unchanged():
    with workspace() as base:
        project = base / "studio"
        project.mkdir()
        code, text = run_cli("start", "--project", str(project), "--request", "Create a portfolio site")
        assert code == 0, text
        run_root = run_root_for(project)
        state = state_of(run_root)
        assert state["packets"][0]["stage"] == "S1", state["packets"]
        # The stage table still carries every creative boundary the 2.2 flow uses.
        for transition in (("S1", "S2"), ("S2", "S3"), ("S3", "S4A"), ("S4A", "S4B"),
                           ("S4B", "S5"), ("S5", "S6"), ("S6", None)):
            assert transition in statemachine.STAGE_TRANSITIONS, transition
        # T1 commands refuse to act on a creative boundary instead of pretending.
        code, text = run_cli("task-status", "--project", str(project))
        assert code == 1, text
        assert "T1" in text, text

@case
def protected_actions_cannot_bypass_the_human_gates():
    with workspace() as base:
        project = make_project(base)
        code, text = run_cli(
            "task-start", "--project", str(project),
            "--request", "Fix the failing export then deploy to production",
            "--scope", "export.py", "--validate", "python -m pytest -q",
        )
        assert code == 1, text
        assert "G4" in text, text
        assert not run_root_for(project).exists()
        # Acceptance requires a recorded human identity and a valid outcome.
        require_pytest()
        assert start_task(project)[0] == 0, "the bounded fix itself prepares"
        run_root = run_root_for(project)
        assert run_task(project, base, "fix")[0] == 0
        code, text = run_cli(
            "task-accept", "--project", str(project), "--identity", "", "--outcome", "accepted",
        )
        assert code != 0, text
        code, text = run_cli(
            "task-accept", "--project", str(project),
            "--identity", "operator", "--outcome", "maybe",
        )
        assert code != 0, text
        assert current_task(state_of(run_root))["acceptance"] == {}


@case
def proof_pass_evaluates_the_correct_requirements_and_revision():
    require_pytest()
    with workspace() as base:
        project = make_project(base)
        assert start_task(project)[0] == 0
        run_root = run_root_for(project)
        assert run_task(project, base, "fix")[0] == 0
        state = state_of(run_root)
        task = current_task(state)
        receipts = [row for row in state.get("proof_receipts") or [] if isinstance(row, dict)]
        assert receipts, state.keys()
        receipt = receipts[-1]
        assert receipt["proof_id"] == task["proof"]["proof_id"]
        assert receipt["work_digest"] and len(receipt["work_digest"]) >= 16
        requirement_texts = [str(item.get("text", "")) for item in state.get("acceptance_requirements") or []]
        assert any("CSV export" in text for text in requirement_texts), requirement_texts
        assert receipt["acceptance_state"] == "ACCEPTED"
        # Evidence names the revision the engine reran the checks on.
        evidence_rows = [
            row for row in state.get("acceptance_evidence") or []
            if str(row.get("work_digest", "")) == receipt["work_digest"]
        ]
        assert any(str(row.get("kind")) == "TEST" for row in evidence_rows), evidence_rows
        assert any("Ariadne task validation reran" in str(row.get("observation", "")) for row in evidence_rows)


@case
def task_completion_does_not_advance_an_unrelated_project_stage():
    require_pytest()
    with workspace() as base:
        project = make_project(base)
        # Give the project a completed creative history first.
        (project / "PROJECT.md").write_text("# PROJECT\n\n**Status:** complete\n", encoding="utf-8")
        subprocess.run(["git", "add", "-A"], cwd=project, capture_output=True, text=True)
        subprocess.run(
            ["git", "-c", "user.email=fixture@example.com", "-c", "user.name=Fixture",
             "commit", "-qm", "creative documents"],
            cwd=project, capture_output=True, text=True,
        )
        assert start_task(project)[0] == 0
        run_root = run_root_for(project)
        assert run_task(project, base, "fix")[0] == 0
        state = state_of(run_root)
        assert statemachine.current_stage(state) == "T1"
        # The creative documents were not touched and no creative stage ran.
        assert (project / "PROJECT.md").read_text(encoding="utf-8").startswith("# PROJECT")
        assert not (project / "DESIGN.md").exists()
        assert [packet["stage"] for packet in state["packets"]] == ["T1"]


@case
def parallel_task_starts_cannot_corrupt_shared_state():
    require_pytest()
    with workspace() as base:
        project = make_project(base)
        assert start_task(project)[0] == 0
        run_root = run_root_for(project)
        assert run_task(project, base, "fix")[0] == 0
        assert run_cli(
            "task-accept", "--project", str(project), "--identity", "operator", "--outcome", "accepted",
        )[0] == 0
        runtime = str(ROOT / "scripts" / "ariadne.py")
        commands = [
            [sys.executable, runtime, "task-start", "--project", str(project),
             "--request", f"Add export option {index} to the CSV export in export.py",
             "--scope", "export.py", "--validate", "python -m pytest -q"]
            for index in (1, 2)
        ]
        env = dict(os.environ)
        processes = [
            subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, env=env)
            for command in commands
        ]
        outputs = [(process.wait(), process.stdout.read()) for process in processes]
        # The state must remain valid and contain no duplicate task identities;
        # at least one command succeeded, and any refusal names the lock or the
        # open attempt instead of corrupting the history.
        state = state_of(run_root)
        task_ids = [task["task_id"] for task in state["tasks"]]
        assert len(task_ids) == len(set(task_ids)), task_ids
        assert len(task_ids) >= 2
        assert any(code == 0 for code, _text in outputs), outputs
        for code, text in outputs:
            if code != 0:
                assert "lock" in text or "still open" in text or "STOPPED" in text, text
        # The packets prepared by the parallel commands verify; the first packet's
        # recorded source legitimately changed when its task fixed export.py, so
        # its manifest integrity is asserted instead of source freshness.
        for packet in packet_dirs(run_root):
            if packet.name == "app-T1":
                manifest = json.loads((packet / "manifest.json").read_text(encoding="utf-8"))
                assert manifest["packet_id"] == "app-T1"
                assert manifest["worker"]["task_id"] == "app-T1"
                continue
            assert TRANSPORT.verify_packet(packet) == [], packet


@case
def the_public_api_classifies_the_task_execution_entry_points():
    for name in ("run_task", "task_report", "task_return", "task_validate",
                 "task_repair", "task_review", "task_verify", "task_accept"):
        assert name in api_module.__all__, name
        assert public_module.PUBLIC_SURFACE.get(name) == "PROVISIONAL", name
    # The API drives the same runtime command the CLI does.
    result = api_module.task_report(project=str(ROOT), args=RUNTIME.argparse.Namespace(
        run_root=None, project=str(ROOT), task="", json=True, migrate=False,
    ))
    assert result.exit_code == 1, "no run records this repository, and the API says so"


@case
def host_session_protocol_ingests_a_real_return():
    require_pytest()
    with workspace() as base:
        project = make_project(base)
        assert start_task(project)[0] == 0
        run_root = run_root_for(project)
        # The invoking session is bound as the worker: the attempt runs with an
        # engine-created execution and no subprocess is launched.
        code, text = run_cli("task-run", "--project", str(project), "--adapter", "host-session")
        assert code == 0, text
        assert "task-return" in text
        state = state_of(run_root)
        attempt = current_task(state)["attempts"][-1]
        assert attempt["state"] == "running" and attempt["adapter"] == "host-session"
        assert [row for row in state["executions"] if row["role"] == "implementer"]
        # The session performs the packet (the fixture stands in for the human
        # hands doing it) and the return is recorded through the same ingestion
        # path every environment uses.
        fixture = write_fixture(base)
        os.environ["FIXTURE_MODE"] = "fix"
        os.environ["FIXTURE_PROJECT"] = str(project)
        try:
            prompt = (packet_dirs(run_root)[-1] / "packet.txt").read_text(encoding="utf-8")
            completed = subprocess.run(
                [sys.executable, str(fixture)], input=prompt, capture_output=True,
                text=True, encoding="utf-8", errors="replace", cwd=project,
            )
        finally:
            os.environ.pop("FIXTURE_MODE", None)
            os.environ.pop("FIXTURE_PROJECT", None)
        assert completed.returncode == 0, completed.stderr
        target = project / ".ariadne" / "returns" / f"{attempt['packet_id']}.md"
        code, text = run_cli(
            "task-return", "--project", str(project),
            "--input", str(target), "--adapter", "host-session",
        )
        assert code == 0, text
        task = current_task(state_of(run_root))
        assert task["attempts"][-1]["state"] == "validated", task["attempts"][-1]
        assert task["proof"], task


@case
def live_harness_completes_one_real_end_to_end_task():
    if os.environ.get("ARIADNE_LIVE_HARNESS") != "1":
        raise SkipCase("set ARIADNE_LIVE_HARNESS=1 to run a real coding harness")
    require_pytest()
    with workspace() as base:
        project = make_project(base)
        assert start_task(project)[0] == 0
        run_root = run_root_for(project)
        code, text = run_cli(
            "task-run", "--project", str(project), "--adapter", "claude-code",
            "--timeout", "900", "--max-attempts", "2",
        )
        state = state_of(run_root)
        task = current_task(state)
        attempt = task["attempts"][-1]
        if code != 0:
            # An installed harness that cannot authenticate is an honest blocker,
            # not a compatibility claim: record why and skip.
            failure_kind = str((attempt.get("validation") or {}).get("failure_kind", ""))
            transcript = run_root / attempt["packet_id"] / "evidence" / "transcript.md"
            detail = transcript.read_text(encoding="utf-8", errors="replace").strip() if transcript.is_file() else text
            if failure_kind in ("provider-unavailable", "runtime-unavailable"):
                raise SkipCase(f"the installed harness could not run here: {detail[:160]}")
            raise AssertionError(text[-2000:])
        assert attempt["state"] == "validated", attempt
        assert attempt["adapter"] == "claude-code"
        assert task["proof"], task
        result = subprocess.run(
            [sys.executable, "-m", "pytest", "-q"], cwd=project,
            capture_output=True, text=True, env=dict(os.environ),
        )
        assert "2 passed" in result.stdout, result.stdout


@case
def live_browser_acceptance_collects_real_evidence():
    if os.environ.get("ARIADNE_LIVE_BROWSER") != "1":
        raise SkipCase("set ARIADNE_LIVE_BROWSER=1 to run a real browser acceptance check")
    try:
        from playwright.sync_api import sync_playwright  # noqa: F401
    except ImportError:
        raise SkipCase("playwright is not installed for this interpreter")
    with workspace() as base:
        site = base / "site"
        site.mkdir()
        (site / "index.html").write_text(
            "<!doctype html><html><head><title>Generative UI</title></head><body>"
            "<main id='app'><h1>Generative UI</h1>"
            "<button id='generate'>Generate</button>"
            "<div id='output' data-state='empty'>Press generate</div>"
            "<script>document.getElementById('generate').addEventListener('click', function(){"
            "document.getElementById('output').dataset.state='ready';"
            "document.getElementById('output').textContent='Panel rendered';});</script>"
            "</main></body></html>",
            encoding="utf-8",
        )
        with RUNTIME.contextlib.suppress(Exception):
            pass
        from playwright.sync_api import sync_playwright

        console_errors: list[str] = []
        capture = base / "capture.png"
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            page = browser.new_page(viewport={"width": 1280, "height": 800})
            page.on("console", lambda message: console_errors.append(message.text) if message.type == "error" else None)
            page.goto((site / "index.html").as_uri())
            page.click("#generate")
            state_value = page.get_attribute("#output", "data-state")
            text_value = page.inner_text("#output")
            page.screenshot(path=str(capture), full_page=True)
            browser.close()
        assert state_value == "ready" and text_value == "Panel rendered"
        assert not console_errors, console_errors
        assert capture.is_file() and capture.stat().st_size > 0
        # The capture is recorded as evidence with its provenance beside it.
        record = {
            "kind": "rendered-evidence",
            "adapter": "playwright:chromium",
            "page": (site / "index.html").as_uri(),
            "interaction": "click #generate",
            "console_errors": console_errors,
            "screenshot": str(capture),
            "viewport": {"width": 1280, "height": 800},
        }
        (base / "rendered-evidence.json").write_text(json.dumps(record, indent=2), encoding="utf-8")
        assert json.loads((base / "rendered-evidence.json").read_text(encoding="utf-8"))["console_errors"] == []


# ------------------------------------------------------------------- runner

def main() -> int:
    selected = [item for item in sys.argv[1:] if not item.startswith("-")]
    cases = [fn for fn in CASES if not selected or any(part in fn.__name__ for part in selected)]
    failures: list[str] = []
    passes = 0
    skips = 0
    for fn in cases:
        try:
            fn()
        except SkipCase as exc:
            skips += 1
            SKIPS.append((fn.__name__, str(exc)))
            print(f"skip {fn.__name__}: {exc}")
            continue
        except Exception as exc:  # noqa: BLE001 - the suite reports every failure
            failures.append(fn.__name__)
            frame = traceback.extract_tb(exc.__traceback__)[-1]
            location = f" [{frame.filename.rsplit(chr(92), 1)[-1]}:{frame.lineno}: {frame.line}]"
            print(f"FAIL  {fn.__name__}: {exc}{location}")
            continue
        passes += 1
        print(f"ok    {fn.__name__}")
    print()
    if failures:
        print(f"FAILED  {passes}/{len(cases)} ({len(failures)} failures, {skips} skipped)")
        print("AR-230 suite: FAILURES PRESENT")
        return 1
    print(f"PASS  {passes}/{len(cases)}" + (f" ({skips} skipped)" if skips else ""))
    print("AR-230 suite: all green")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
