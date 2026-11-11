#!/usr/bin/env python3
"""Ariadne 2.4A: execution-reliability regression suite.

Covers the review-directed correction lifecycle, evidence freshness, recovery
from real subprocess interruptions, and the refusals that keep a correction from
inheriting or forging authority. It reuses the AR-230 fixture project and drives
the real command line (in-process for normal cases, a real killed subprocess for
the interruption cases).
"""

from __future__ import annotations

import importlib.util
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

_spec = importlib.util.spec_from_file_location("ar23b_support", ROOT / "scripts" / "test-ar23b.py")
BASE = importlib.util.module_from_spec(_spec)
sys.modules["ar23b_support"] = BASE
_spec.loader.exec_module(BASE)

from ariadne_engine import policy as policy_module  # noqa: E402
from ariadne_engine import review as review_module  # noqa: E402
from ariadne_engine import statemachine  # noqa: E402
from ariadne_engine import api as api_module  # noqa: E402
from ariadne_engine import mcp as mcp_module  # noqa: E402

CASES: list = []
SKIPS: list[tuple[str, str]] = []


def case(fn):
    CASES.append(fn)
    return fn


class SkipCase(Exception):
    pass


def require_pytest() -> None:
    BASE.require_pytest()


def workspace():
    return BASE.workspace()


def state_of(run_root: Path) -> dict:
    return BASE.state_of(run_root)


def current_task(state: dict) -> dict:
    return BASE.current_task(state)


def review_fail(project: Path, base: Path, *, recommendation: str = "fix and re-review", identity: str = "reviewer-bob"):
    judgement = base / f"judgement-{time.time_ns()}.md"
    judgement.write_text(BASE.judgement_block(recommendation), encoding="utf-8")
    return BASE.run_cli(
        "task-review", "--project", str(project),
        "--input", str(judgement), "--identity", identity,
    )


def review_pass(project: Path, base: Path, *, identity: str = "reviewer-carol"):
    judgement = base / f"judgement-{time.time_ns()}.md"
    judgement.write_text(BASE.judgement_block("present g3"), encoding="utf-8")
    return BASE.run_cli(
        "task-review", "--project", str(project),
        "--input", str(judgement), "--identity", identity,
    )


def high_stakes_task() -> tuple[Path, Path]:
    base = Path(tempfile.mkdtemp(prefix="ariadne-ar24a-"))
    project = BASE.make_project(base)
    code, text = BASE.start_task(project, request=BASE.HIGH_STAKES_REQUEST)
    assert code == 0, text
    run_root = BASE.run_root_for(project)
    code, text = BASE.run_task(project, base, "fix")
    assert code == 0, text
    return project, run_root


def prepare_review_correction(project: Path, base: Path, run_root: Path) -> dict:
    code, text = review_fail(project, base)
    assert code == 2, text
    code, text = BASE.run_cli("task-repair", "--project", str(project))
    assert code == 0, text
    state = state_of(run_root)
    task = current_task(state)
    assert len(task["attempts"]) == 2, task["attempts"]
    assert task["attempts"][-1]["repair_kind"] == "review", task["attempts"][-1]
    assert task["attempts"][-1]["parent_attempt_id"] == task["attempts"][0]["attempt_id"]
    return task


# ------------------------------------------------------------------ lifecycle

@case
def s4b_review_correction_contract_is_bounded_and_review_authorized():
    with workspace() as base:
        run_root = base / "run"
        s4b = run_root / "S4B"
        s5 = run_root / "S5"
        (s4b / "evidence").mkdir(parents=True)
        (s5 / "evidence").mkdir(parents=True)
        assert ("S5", "S4B") in statemachine.STAGE_TRANSITIONS
        # The transport accepts an S5 parent for a corrective S4B packet.
        assert "S5" in BASE.RUNTIME.TRANSPORT.STAGES["S4B"]["allowed_parents"]
        review_record = {
            "schema_version": 1,
            "review_id": "rev_test_s4b",
            "packet_id": "S5",
            "outcome": "failed",
            "recommendation": "fix and re-review",
            "findings": ["the primary action has no visible response"],
            "reviewer_identity": "reviewer-a",
            "recorded_at": "2026-01-01T00:00:00Z",
        }
        (s5 / "evidence" / "review-record.json").write_text(
            json.dumps(review_record), encoding="utf-8"
        )
        state = {
            "packets": [
                {"id": "S4B", "stage": "S4B", "path": str(s4b)},
                {"id": "S5", "stage": "S5", "path": str(s5)},
            ],
            "worker": {},
            "reviews": [review_record],
        }
        problems = policy_module.failed_review_problems(state, s5)
        assert not problems, problems
        evidence_path, evidence_kind = BASE.RUNTIME.TRANSPORT.parent_evidence(
            {"stage": "S5", "packet_id": "S5"}, s5
        )
        assert evidence_kind == "review-finding", evidence_kind
        context = BASE.RUNTIME.TRANSPORT.worker_retry_context(
            {"stage": "S5", "packet_id": "S5"}, evidence_path, evidence_kind
        )
        assert context["failure_kind"] == "review-finding", context
        assert context["review_findings"] == ["the primary action has no visible response"], context
        assert "permitted scope" in context["directive"], context
        # A passing review or another recommendation does not authorize a correction.
        passed = {**review_record, "outcome": "passed", "recommendation": "present g3"}
        (s5 / "evidence" / "review-record.json").write_text(json.dumps(passed), encoding="utf-8")
        state["reviews"] = [passed]
        assert policy_module.failed_review_problems(state, s5), "a passing review cannot authorize a correction"
        (s5 / "evidence" / "review-record.json").write_text(json.dumps(review_record), encoding="utf-8")
        state["reviews"] = [review_record]
        # The correction budget is separate and bounded.
        for index in range(policy_module.MAX_REVIEW_CORRECTIONS):
            packet = run_root / f"S4B-C{index + 1}"
            packet.mkdir()
            (packet / "manifest.json").write_text(
                json.dumps({"packet_id": packet.name, "stage": "S4B", "parent_id": "S5"}),
                encoding="utf-8",
            )
            state["packets"].append({"id": packet.name, "stage": "S4B", "path": str(packet)})
        problems = policy_module.failed_review_problems(state, s5)
        assert any("budget" in problem for problem in problems), problems


@case
def cli_api_and_mcp_report_the_same_durable_task_state():
    require_pytest()
    with workspace() as base:
        project = BASE.make_project(base)
        assert BASE.start_task(project, request=BASE.HIGH_STAKES_REQUEST)[0] == 0
        run_root = BASE.run_root_for(project)
        assert BASE.run_task(project, base, "fix")[0] == 0
        state = state_of(run_root)
        cli_view = json.loads(BASE.run_cli("task-status", "--project", str(project), "--json")[1])["task"]
        api_view = api_module.task_status_state(state)
        mcp_view = mcp_module.dispatch(state, tool="task_status", params={})
        for view in (api_view, mcp_view):
            assert view["task_id"] == cli_view["task_id"], view
            assert view["status"] == cli_view["status"], view
            assert view["current_attempt"]["attempt_id"] == cli_view["current_attempt"]["attempt_id"], view
            assert view["evidence_freshness"] == cli_view["evidence_freshness"], view
            assert view["recovery"]["safe_continuation"] == cli_view["recovery"]["safe_continuation"], view


@case
def failed_review_produces_a_linked_correction_and_fresh_validation():
    require_pytest()
    with workspace() as base:
        project = BASE.make_project(base)
        assert BASE.start_task(project, request=BASE.HIGH_STAKES_REQUEST)[0] == 0
        run_root = BASE.run_root_for(project)
        assert BASE.run_task(project, base, "fix")[0] == 0
        task = prepare_review_correction(project, base, run_root)
        original_validation = task["attempts"][0]["validation"]
        assert original_validation["status"] == "passed"
        assert original_validation["validated_revision"]["implementation_fingerprint"]
        assert not task.get("review"), "a failed review cannot keep the current gate slot"
        assert any(row["review_id"] for row in task.get("reviews") or ()), task.get("reviews")
        code, text = BASE.run_task(project, base, "repair")
        assert code == 0, text
        task = current_task(state_of(run_root))
        corrected = task["attempts"][-1]
        assert corrected["state"] == "validated", corrected
        assert corrected["attempt_id"] != task["attempts"][0]["attempt_id"]
        assert corrected["validation"]["path"] != original_validation["path"]
        assert corrected["validation"]["validation_sha256"] != original_validation["validation_sha256"]
        # The first attempt's evidence is preserved, not overwritten.
        assert Path(original_validation["path"]).is_file()
        assert Path(corrected["validation"]["path"]).is_file()
        # The review was superseded in history; the corrected revision needs re-review.
        assert not task.get("review"), task.get("review")
        code, text = BASE.run_cli("task-verify", "--project", str(project))
        assert code == 2, text
        assert "review" in text.lower()


@case
def correction_that_fails_validation_cannot_become_accepted():
    require_pytest()
    with workspace() as base:
        project = BASE.make_project(base)
        assert BASE.start_task(project, request=BASE.HIGH_STAKES_REQUEST)[0] == 0
        run_root = BASE.run_root_for(project)
        assert BASE.run_task(project, base, "fix")[0] == 0
        prepare_review_correction(project, base, run_root)
        code, text = BASE.run_task(project, base, "break", extra=("--no-auto",))
        assert code == 2, text
        state = state_of(run_root)
        task = current_task(state)
        latest = task["attempts"][-1]
        assert latest["state"] == "failed", latest
        assert latest["validation"]["status"] == "failed"
        assert latest["validation"]["validation_sha256"], latest["validation"]
        assert Path(latest["validation"]["path"]).is_file()
        report = json.loads(BASE.run_cli("task-status", "--project", str(project), "--json")[1])
        assert report["task"]["status"] == "repair-pending", report["task"]["status"]
        assert report["task"]["evidence_freshness"] == "stale-or-unproven"
        code, text = BASE.run_cli("task-verify", "--project", str(project))
        assert code == 2, text
        code, text = BASE.run_cli(
            "task-accept", "--project", str(project),
            "--identity", "operator", "--outcome", "accepted",
        )
        assert code == 1, text
        assert "proof" in text.lower() or "validated" in text.lower(), text


@case
def corrected_revision_receives_a_new_independent_review_and_proof():
    require_pytest()
    with workspace() as base:
        project = BASE.make_project(base)
        assert BASE.start_task(project, request=BASE.HIGH_STAKES_REQUEST)[0] == 0
        run_root = BASE.run_root_for(project)
        assert BASE.run_task(project, base, "fix")[0] == 0
        task = prepare_review_correction(project, base, run_root)
        assert BASE.run_task(project, base, "repair")[0] == 0
        task = current_task(state_of(run_root))
        first_review = (task.get("reviews") or [{}])[0]
        assert first_review.get("outcome") == "failed"
        code, text = review_pass(project, base)
        assert code == 0, text
        state = state_of(run_root)
        task = current_task(state)
        assert task["review"]["outcome"] == "passed"
        assert task["review"]["packet_id"] == task["attempts"][-1]["packet_id"]
        assert task["review"]["attempt_id"] == task["attempts"][-1]["attempt_id"]
        assert task["review"]["validation_sha256"] == task["attempts"][-1]["validation"]["validation_sha256"]
        assert task["proof"]["attempt_id"] == task["attempts"][-1]["attempt_id"]
        assert task["proof"]["review_id"] == task["review"]["review_id"]
        assert state["worker"]["lifecycle"] == "reviewed"
        code, text = BASE.run_cli(
            "task-accept", "--project", str(project),
            "--identity", "operator", "--outcome", "accepted",
        )
        assert code == 0, text
        task = current_task(state_of(run_root))
        assert task["acceptance"]["outcome"] == "accepted"
        assert task["acceptance"]["identity"] == "operator"


@case
def two_sequential_review_corrections_are_bounded_and_reviewable():
    require_pytest()
    with workspace() as base:
        project = BASE.make_project(base)
        assert BASE.start_task(project, request=BASE.HIGH_STAKES_REQUEST)[0] == 0
        run_root = BASE.run_root_for(project)
        assert BASE.run_task(project, base, "fix")[0] == 0
        prepare_review_correction(project, base, run_root)
        assert BASE.run_task(project, base, "repair")[0] == 0
        # A second independent review of the corrected revision also fails.
        code, text = review_fail(project, base, identity="reviewer-dana")
        assert code == 2, text
        code, text = BASE.run_cli("task-repair", "--project", str(project))
        assert code == 0, text
        task = current_task(state_of(run_root))
        assert task["review_corrections"] == 2, task.get("review_corrections")
        assert task["attempts"][-1]["repair_kind"] == "review"
        assert BASE.run_task(project, base, "fix")[0] == 0
        code, text = review_fail(project, base, identity="reviewer-erin")
        assert code == 2, text
        code, text = BASE.run_cli("task-repair", "--project", str(project))
        assert code == 1, text
        assert "budget" in text.lower(), text
        assert len(current_task(state_of(run_root))["attempts"]) == 3


@case
def unchanged_passing_attempt_is_not_rerun_or_repaired():
    require_pytest()
    with workspace() as base:
        project = BASE.make_project(base)
        assert BASE.start_task(project)[0] == 0
        run_root = BASE.run_root_for(project)
        assert BASE.run_task(project, base, "fix")[0] == 0
        before = current_task(state_of(run_root))
        proof_id = before["proof"]["proof_id"]
        assert BASE.run_cli("task-run", "--project", str(project))[0] == 0
        code, text = BASE.run_cli("task-repair", "--project", str(project))
        assert code == 1, text
        assert "not after a validated" in text or "not after" in text, text
        code, text = BASE.run_cli("task-validate", "--project", str(project))
        assert code == 0, text
        after = current_task(state_of(run_root))
        assert len(after["attempts"]) == len(before["attempts"])
        assert after["proof"]["proof_id"] == proof_id


# ------------------------------------------------------------------- evidence

@case
def stale_validation_is_refused_by_review_and_proof():
    require_pytest()
    with workspace() as base:
        project = BASE.make_project(base)
        assert BASE.start_task(project, request=BASE.HIGH_STAKES_REQUEST)[0] == 0
        run_root = BASE.run_root_for(project)
        assert BASE.run_task(project, base, "fix")[0] == 0
        # Move the implementation after the engine validated it.
        export = project / "export.py"
        export.write_text(export.read_text(encoding="utf-8") + "\n# moved after validation\n", encoding="utf-8")
        code, text = review_pass(project, base)
        assert code == 1, text
        assert "no longer current" in text or "stale" in text, text
        code, text = BASE.run_cli("task-verify", "--project", str(project))
        assert code == 2, text
        assert "stale" in text or "no longer" in text, text
        report = json.loads(BASE.run_cli("task-status", "--project", str(project), "--json")[1])
        assert report["task"]["status"] == "stale-evidence", report["task"]["status"]
        assert report["task"]["recovery"]["safe_continuation"] == "stop-stale-evidence"


@case
def cross_attempt_validation_evidence_is_refused():
    require_pytest()
    with workspace() as base:
        project = BASE.make_project(base)
        assert BASE.start_task(project, request=BASE.HIGH_STAKES_REQUEST)[0] == 0
        run_root = BASE.run_root_for(project)
        assert BASE.run_task(project, base, "fix")[0] == 0
        task = prepare_review_correction(project, base, run_root)
        assert BASE.run_task(project, base, "repair")[0] == 0
        task = current_task(state_of(run_root))
        first = Path(task["attempts"][0]["validation"]["path"])
        second = Path(task["attempts"][1]["validation"]["path"])
        preserved = second.read_bytes()
        try:
            shutil.copyfile(first, second)
            code, text = BASE.run_cli("task-validate", "--project", str(project))
            assert code == 1, text
            assert (
                "another attempt" in text or "not bound" in text
                or "wrong packet ID" in text or "changed after" in text
            ), text
        finally:
            second.write_bytes(preserved)


@case
def forged_reviewer_identity_is_refused_without_leaving_an_open_execution():
    require_pytest()
    with workspace() as base:
        project = BASE.make_project(base)
        assert BASE.start_task(project, request=BASE.HIGH_STAKES_REQUEST)[0] == 0
        run_root = BASE.run_root_for(project)
        assert BASE.run_task(project, base, "fix")[0] == 0
        for identity in ("custom", "fixture-worker"):
            judgement = base / f"forged-{identity}.md"
            judgement.write_text(BASE.judgement_block("present g3"), encoding="utf-8")
            code, text = BASE.run_cli(
                "task-review", "--project", str(project),
                "--input", str(judgement), "--identity", identity,
            )
            assert code == 1, text
            assert "identity" in text.lower(), text
        state = state_of(run_root)
        task = current_task(state)
        assert not task.get("review"), task.get("review")
        open_reviewers = [
            row for row in state["executions"]
            if row.get("role") == "reviewer" and row.get("state") not in ("COMPLETED", "FAILED")
        ]
        assert not open_reviewers, open_reviewers


@case
def out_of_scope_correction_is_refused_before_a_packet_is_prepared():
    require_pytest()
    with workspace() as base:
        project = BASE.make_project(base)
        assert BASE.start_task(project, request=BASE.HIGH_STAKES_REQUEST)[0] == 0
        run_root = BASE.run_root_for(project)
        assert BASE.run_task(project, base, "fix")[0] == 0
        prepare_review_correction(project, base, run_root)
        # The task record is the authorization boundary. Changing it without a
        # new human decision must not widen the correction.
        state = state_of(run_root)
        task = current_task(state)
        task["scope"]["declared"].append("bystander.txt")
        (run_root / "ariadne-run.json").write_text(
            json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        # The current attempt is already prepared; refuse to execute a widened
        # scope rather than sending it to a worker.
        code, text = BASE.run_cli("task-run", "--project", str(project), "--no-auto")
        assert code == 1, text
        assert "scope" in text.lower(), text


# ------------------------------------------------------------------- recovery

def _wait_for(predicate, timeout: float = 45.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return
        time.sleep(0.15)
    raise AssertionError("the expected durable state did not appear in time")


def _kill_pid(pid: int) -> None:
    try:
        os.kill(pid, signal.SIGTERM)
    except Exception:
        pass


@case
def real_subprocess_interruption_during_worker_execution_recovers_safely():
    require_pytest()
    with workspace() as base:
        project = BASE.make_project(base)
        assert BASE.start_task(project, request=BASE.HIGH_STAKES_REQUEST)[0] == 0
        run_root = BASE.run_root_for(project)
        hang = base / "hang-worker.py"
        pid_file = base / "hang.pid"
        hang.write_text(
            "import os, sys, time\n"
            "from pathlib import Path\n"
            f"Path({str(pid_file)!r}).write_text(str(os.getpid()), encoding='utf-8')\n"
            "sys.stdin.read()\n"
            "time.sleep(120)\n",
            encoding="utf-8",
        )
        env = dict(os.environ)
        env["PYTHONPATH"] = BASE.PYTEST_SITE + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
        process = subprocess.Popen(
            [sys.executable, str(ROOT / "scripts" / "ariadne.py"), "task-run",
             "--project", str(project), "--worker-command", f"{sys.executable} {hang}"],
            cwd=str(ROOT), env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        )
        try:
            _wait_for(lambda: pid_file.is_file() and state_of(run_root)["tasks"][-1]["attempts"][-1]["state"] == "running")
            process.terminate()
            process.wait(timeout=15)
        finally:
            if process.poll() is None:
                process.kill()
            if pid_file.is_file():
                _kill_pid(int(pid_file.read_text(encoding="utf-8").strip()))
        state = state_of(run_root)
        task = current_task(state)
        assert task["attempts"][-1]["state"] == "running", task["attempts"][-1]
        assert task["operations"][-1]["kind"] == "execute", task["operations"][-1]
        assert task["operations"][-1]["state"] == "started", task["operations"][-1]
        code, text = BASE.run_cli("task-recover", "--project", str(project), "--json")
        assert code == 0, text
        view = json.loads(text)
        assert view["interrupted"] is True, view
        assert view["safe_continuation"] == "wait-or-abandon-open", view
        assert "abandon-open" in view["required_human_action"], view
        # A repeated resume without the operator's declaration refuses rather
        # than guessing that the worker is gone.
        code, text = BASE.run_cli("task-recover", "--project", str(project), "--apply")
        assert code == 2, text
        code, text = BASE.run_cli(
            "task-run", "--project", str(project), "--abandon-open",
            "--worker-command", f"{sys.executable} {BASE.write_fixture(base)}",
        )
        assert code == 0, text
        state = state_of(run_root)
        task = current_task(state)
        assert task["attempts"][0]["state"] == "failed", task["attempts"][0]
        assert task["attempts"][0]["validation"]["failure_kind"] == "interrupted"
        assert task["attempts"][-1]["state"] == "validated", task["attempts"][-1]
        assert any(row.get("kind") == "execute" and row.get("state") == "failed" for row in task["operations"]), task["operations"][-4:]


@case
def recorded_validation_is_recovered_without_rerunning_checks():
    require_pytest()
    with workspace() as base:
        project = BASE.make_project(base)
        counter = base / "validation-runs.txt"
        test_file = project / "test_counter.py"
        test_file.write_text(
            "from pathlib import Path\n"
            f"COUNTER = Path({str(counter)!r})\n"
            "def test_counts_a_validation_run():\n"
            "    n = int(COUNTER.read_text()) if COUNTER.exists() else 0\n"
            "    COUNTER.write_text(str(n + 1), encoding='utf-8')\n"
            "    assert True\n",
            encoding="utf-8",
        )
        subprocess.run(["git", "add", "-A"], cwd=project, capture_output=True, text=True)
        subprocess.run(
            ["git", "-c", "user.email=fixture@example.com", "-c", "user.name=Fixture",
             "commit", "-qm", "counter test"],
            cwd=project, capture_output=True, text=True,
        )
        assert BASE.start_task(
            project, validate="python -m pytest -q test_counter.py", request=BASE.HIGH_STAKES_REQUEST,
        )[0] == 0
        run_root = BASE.run_root_for(project)
        # Produce a real return through the same transport the worker uses, then
        # ingest it without validation so the state is exactly "returned".
        from ariadne_engine import task_execution as taskx
        state = state_of(run_root)
        task = current_task(state)
        packet = Path(task["attempts"][-1]["packet_path"])
        packet_text = (packet / "packet.txt").read_text(encoding="utf-8")
        import re
        target = re.search(r"(?m)^Write the complete marked return handoff verbatim to: (.+)$", packet_text)
        assert target, "the packet names its return target"
        fixture = BASE.write_fixture(base)
        env = dict(os.environ)
        env.update({"FIXTURE_MODE": "fix", "FIXTURE_PROJECT": str(project)})
        subprocess.run(
            [sys.executable, str(fixture)], input=packet_text, cwd=str(project),
            env=env, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120,
        )
        source = Path(target.group(1).strip())
        assert source.is_file(), source
        code, text = BASE.run_cli(
            "task-return", "--project", str(project), "--input", str(source), "--no-validate",
        )
        assert code == 0, text
        state_after_return = state_of(run_root)
        assert current_task(state_after_return)["attempts"][-1]["state"] == "returned"
        assert not (packet / "evidence" / "validation.json").exists()
        # Normal validation writes the durable record and the state together.
        code, text = BASE.run_cli("task-validate", "--project", str(project))
        assert code == 0, text
        assert counter.read_text(encoding="utf-8") == "1"
        # Simulate the crash window: evidence is durable, the state write was lost.
        (run_root / "ariadne-run.json").write_text(
            json.dumps(state_after_return, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        assert (packet / "evidence" / "validation.json").is_file()
        code, text = BASE.run_cli("task-recover", "--project", str(project), "--json")
        assert code == 0, text
        view = json.loads(text)
        assert view["safe_continuation"] in ("recover-validation", "validate"), view
        code, text = BASE.run_cli("task-recover", "--project", str(project), "--apply")
        assert code == 0, text
        task = current_task(state_of(run_root))
        assert task["attempts"][-1]["state"] == "validated", task["attempts"][-1]
        assert counter.read_text(encoding="utf-8") == "1", "the recorded validation must not be rerun"


@case
def interrupted_return_ingestion_reconciles_existing_evidence_without_duplication():
    require_pytest()
    with workspace() as base:
        project = BASE.make_project(base)
        assert BASE.start_task(project, request=BASE.HIGH_STAKES_REQUEST)[0] == 0
        run_root = BASE.run_root_for(project)
        # Bind the invoking-session worker so the attempt is durable and running.
        code, text = BASE.run_cli("task-run", "--project", str(project), "--adapter", "host-session")
        assert code == 0, text
        state = state_of(run_root)
        task = current_task(state)
        assert task["attempts"][-1]["state"] == "running"
        packet = Path(task["attempts"][-1]["packet_path"])
        packet_text = (packet / "packet.txt").read_text(encoding="utf-8")
        import re
        target = re.search(r"(?m)^Write the complete marked return handoff verbatim to: (.+)$", packet_text)
        assert target
        fixture = BASE.write_fixture(base)
        env = dict(os.environ)
        env.update({"FIXTURE_MODE": "fix", "FIXTURE_PROJECT": str(project)})
        subprocess.run(
            [sys.executable, str(fixture)], input=packet_text, cwd=str(project),
            env=env, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120,
        )
        source = Path(target.group(1).strip())
        assert source.is_file()
        # Simulate the crash after the return bytes were written but before the
        # state was updated.
        (packet / "evidence").mkdir(parents=True, exist_ok=True)
        (packet / "evidence" / "return-handoff.md").write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
        code, text = BASE.run_cli("task-recover", "--project", str(project), "--json")
        assert code == 0, text
        view = json.loads(text)
        assert view["safe_continuation"] == "ingest-return", view
        code, text = BASE.run_cli("task-recover", "--project", str(project), "--apply")
        assert code == 0, text
        task = current_task(state_of(run_root))
        assert len(task["attempts"]) == 1, task["attempts"]
        assert task["attempts"][-1]["state"] == "validated", task["attempts"][-1]
        # A second resume is a no-op for the attempt and the proof.
        before = json.dumps(task["attempts"], sort_keys=True, default=str)
        code, text = BASE.run_cli("task-recover", "--project", str(project), "--apply")
        assert code == 0, text
        task = current_task(state_of(run_root))
        assert json.dumps(task["attempts"], sort_keys=True, default=str) == before


@case
def changed_repository_state_blocks_recovery_instead_of_reusing_the_old_pass():
    require_pytest()
    with workspace() as base:
        project = BASE.make_project(base)
        assert BASE.start_task(project, request=BASE.HIGH_STAKES_REQUEST)[0] == 0
        run_root = BASE.run_root_for(project)
        assert BASE.run_task(project, base, "fix")[0] == 0
        before = current_task(state_of(run_root))
        export = project / "export.py"
        export.write_text(export.read_text(encoding="utf-8") + "\n# changed after validation\n", encoding="utf-8")
        code, text = BASE.run_cli("task-recover", "--project", str(project), "--json")
        assert code == 0, text
        view = json.loads(text)
        assert view["safe_continuation"] == "stop-stale-evidence", view
        assert "changed" in view["required_human_action"].lower() or "stale" in view["required_human_action"].lower(), view
        code, text = BASE.run_cli("task-recover", "--project", str(project), "--apply")
        assert code == 2, text
        after = current_task(state_of(run_root))
        assert len(after["attempts"]) == len(before["attempts"])
        assert (after.get("proof") or {}).get("proof_id") == (before.get("proof") or {}).get("proof_id")


@case
def repeated_resume_does_not_duplicate_writes_or_approvals():
    require_pytest()
    with workspace() as base:
        project = BASE.make_project(base)
        assert BASE.start_task(project, request=BASE.HIGH_STAKES_REQUEST)[0] == 0
        run_root = BASE.run_root_for(project)
        assert BASE.run_task(project, base, "fix")[0] == 0
        assert review_pass(project, base)[0] == 0
        before = current_task(state_of(run_root))
        before_approvals = len(state_of(run_root).get("approvals") or [])
        for _ in range(3):
            code, text = BASE.run_cli("task-recover", "--project", str(project), "--apply")
            assert code == 0, text
        after = current_task(state_of(run_root))
        assert len(after["attempts"]) == len(before["attempts"])
        assert (after.get("proof") or {}).get("proof_id") == (before.get("proof") or {}).get("proof_id")
        assert len(state_of(run_root).get("approvals") or []) == before_approvals


@case
def tampered_validation_record_is_refused_at_every_gate():
    require_pytest()
    with workspace() as base:
        project = BASE.make_project(base)
        assert BASE.start_task(project, request=BASE.HIGH_STAKES_REQUEST)[0] == 0
        run_root = BASE.run_root_for(project)
        assert BASE.run_task(project, base, "fix")[0] == 0
        task = current_task(state_of(run_root))
        validation_path = Path(task["attempts"][-1]["validation"]["path"])
        record = json.loads(validation_path.read_text(encoding="utf-8"))
        record["failure_reason"] = "tampered after validation"
        validation_path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        code, text = BASE.run_cli("task-validate", "--project", str(project))
        assert code == 1, text
        assert "changed after" in text or "stale" in text, text
        code, text = BASE.run_cli("task-verify", "--project", str(project))
        assert code == 2, text
        assert "stale" in text or "changed" in text or "no longer" in text, text


@case
def forged_proof_receipt_in_task_state_cannot_mint_acceptance():
    require_pytest()
    with workspace() as base:
        project = BASE.make_project(base)
        assert BASE.start_task(project, request=BASE.HIGH_STAKES_REQUEST)[0] == 0
        run_root = BASE.run_root_for(project)
        assert BASE.run_task(project, base, "fix")[0] == 0
        assert review_pass(project, base)[0] == 0
        state = state_of(run_root)
        task = current_task(state)
        task["proof"]["proof_id"] = "VP-9999"
        (run_root / "ariadne-run.json").write_text(
            json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        code, text = BASE.run_cli(
            "task-accept", "--project", str(project),
            "--identity", "operator", "--outcome", "accepted",
        )
        assert code == 1, text
        assert "receipt" in text.lower(), text
        assert not current_task(state_of(run_root)).get("acceptance")


@case
def real_subprocess_interruption_during_validation_recovers_without_a_fake_pass():
    require_pytest()
    with workspace() as base:
        project = BASE.make_project(base)
        pid_file = base / "slow.pid"
        slow = project / "test_slow.py"
        slow.write_text(
            "import os, time\n"
            "from pathlib import Path\n"
            "def test_slow_check():\n"
            f"    Path({str(pid_file)!r}).write_text(str(os.getpid()), encoding='utf-8')\n"
            "    time.sleep(8)\n"
            "    assert True\n",
            encoding="utf-8",
        )
        (project / ".gitignore").write_text("__pycache__/\n.pytest_cache/\n*.pyc\n", encoding="utf-8")
        subprocess.run(["git", "add", "-A"], cwd=project, capture_output=True, text=True)
        subprocess.run(
            ["git", "-c", "user.email=fixture@example.com", "-c", "user.name=Fixture",
             "commit", "-qm", "add slow validation"],
            cwd=project, capture_output=True, text=True,
        )
        assert BASE.start_task(project, validate="python -m pytest -q test_slow.py", request=BASE.HIGH_STAKES_REQUEST)[0] == 0
        run_root = BASE.run_root_for(project)
        pid_file = base / "slow.pid"
        env = dict(os.environ)
        env["SLOW_PID_FILE"] = str(pid_file)
        env["FIXTURE_PROJECT"] = str(project)
        env["FIXTURE_MODE"] = "fix"
        env["PYTHONPATH"] = BASE.PYTEST_SITE + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
        fixture = BASE.write_fixture(base)
        process = subprocess.Popen(
            [sys.executable, str(ROOT / "scripts" / "ariadne.py"), "task-run",
             "--project", str(project), "--worker-command", f"{sys.executable} {fixture}"],
            cwd=str(ROOT), env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        )
        try:
            _wait_for(lambda: pid_file.is_file() and state_of(run_root)["tasks"][-1]["attempts"][-1]["state"] == "returned")
            _wait_for(lambda: any(
                row.get("kind") == "validate" and row.get("state") == "started"
                for row in current_task(state_of(run_root)).get("operations") or ()
            ))
            process.terminate()
            process.wait(timeout=15)
        finally:
            if process.poll() is None:
                process.kill()
            if pid_file.is_file():
                _kill_pid(int(pid_file.read_text(encoding="utf-8").strip()))
        assert not (run_root / current_task(state_of(run_root))["attempts"][-1]["packet_id"] / "evidence" / "validation.json").exists()
        code, text = BASE.run_cli("task-recover", "--project", str(project), "--json")
        assert code == 0, text
        view = json.loads(text)
        assert view["interrupted_operation"]["kind"] == "validate", view
        assert view["safe_continuation"] in ("validate", "recover-validation"), view
        code, text = BASE.run_cli("task-recover", "--project", str(project), "--apply")
        assert code == 0, text
        task = current_task(state_of(run_root))
        assert task["attempts"][-1]["state"] == "validated", task["attempts"][-1]
        assert task["attempts"][-1]["validation"]["status"] == "passed"
        # Repeated resume does not duplicate the attempt or the proof.
        before = len(task["attempts"])
        code, text = BASE.run_cli("task-recover", "--project", str(project), "--apply")
        assert code == 0, text
        task = current_task(state_of(run_root))
        assert len(task["attempts"]) == before


# ------------------------------------------------------------------ harness

def main(argv: list[str]) -> int:
    selected = [item for item in argv if not item.startswith("-")]
    failures = 0
    executed = 0
    for fn in CASES:
        if selected and fn.__name__ not in selected:
            continue
        executed += 1
        try:
            fn()
        except SkipCase as exc:
            SKIPS.append((fn.__name__, str(exc)))
            print(f"skip {fn.__name__}: {exc}")
        except AssertionError as exc:
            failures += 1
            import traceback
            print(f"FAIL {fn.__name__}: {exc}")
            traceback.print_exc()
        except Exception as exc:  # noqa: BLE001
            failures += 1
            import traceback
            print(f"ERROR {fn.__name__}: {type(exc).__name__}: {exc}")
            traceback.print_exc()
        else:
            print(f"ok   {fn.__name__}")
    total = executed
    print()
    print(f"{'PASS' if failures == 0 else 'FAIL'}  {total - failures - len(SKIPS)}/{total} ({len(SKIPS)} skipped)")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
