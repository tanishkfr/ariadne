#!/usr/bin/env python3
"""Ariadne 2.4A: worker-adapter conformance and live qualification.

The structural cases run offline. The live cases are opt-in with
``ARIADNE_LIVE_ADAPTERS=1`` and use only CLIs already installed and authenticated
on this host. They record executable versions, the task outcome, the files the
worker changed, the independent validation result, and the proof receipt. A
missing or unauthenticated adapter is skipped with the exact environment reason;
it is never reported as a pass.
"""

from __future__ import annotations

import importlib.util
import json
import os
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

from ariadne_engine import task_execution  # noqa: E402

CASES: list = []
SKIPS: list[tuple[str, str]] = []


def case(fn):
    CASES.append(fn)
    return fn


class SkipCase(Exception):
    pass


def live_enabled() -> bool:
    return os.environ.get("ARIADNE_LIVE_ADAPTERS") == "1"


def executable_version(command: str) -> str:
    resolved = BASE.shutil.which(command) if hasattr(BASE, "shutil") else None
    if not resolved:
        import shutil
        resolved = shutil.which(command)
    if not resolved:
        return "not found"
    try:
        completed = subprocess.run(
            [resolved, "--version"], capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=30, shell=False,
        )
        text = (completed.stdout or completed.stderr or "").strip().splitlines()
        return text[0][:160] if text else f"exit {completed.returncode}"
    except Exception as exc:  # noqa: BLE001
        return f"version probe failed: {type(exc).__name__}: {exc}"


def live_adapter_case(adapter_id: str):
    def run():
        if not live_enabled():
            raise SkipCase("set ARIADNE_LIVE_ADAPTERS=1 to run real CLI adapters")
        BASE.require_pytest()
        adapter = task_execution.WORKER_ADAPTERS.get(adapter_id)
        assert adapter is not None
        available, reason = task_execution.executable_available(str(adapter["command"]))
        if not available:
            raise SkipCase(f"{adapter_id} is not installed: {reason}")
        with BASE.workspace() as base:
            project = BASE.make_project(base)
            assert BASE.start_task(project)[0] == 0
            run_root = BASE.run_root_for(project)
            started = time.time()
            code, text = BASE.run_cli(
                "task-run", "--project", str(project),
                "--adapter", adapter_id, "--timeout", "1200", "--max-attempts", "1",
            )
            elapsed = round(time.time() - started, 1)
            state = BASE.state_of(run_root)
            task = BASE.current_task(state)
            attempt = task["attempts"][-1]
            version = executable_version(str(adapter["command"]))
            evidence = {
                "schema_version": "ar-24a-live-adapter-1",
                "adapter": adapter_id,
                "executable": str(adapter["command"]),
                "version": version,
                "elapsed_seconds": elapsed,
                "exit_code": code,
                "attempt_state": attempt["state"],
                "validation": attempt.get("validation", {}).get("status"),
                "failure_kind": attempt.get("validation", {}).get("failure_kind"),
                "proof": (task.get("proof") or {}).get("proof_id", ""),
                "acceptance_state": (task.get("proof") or {}).get("acceptance_state", ""),
                "changed_files": attempt.get("validation", {}).get("validated_revision", {}),
                "output_tail": text[-3000:],
            }
            print(json.dumps(evidence, indent=2, sort_keys=True, default=str))
            assert code == 0, f"{adapter_id} did not complete: {text[-2000:]}"
            assert attempt["state"] == "validated", attempt
            assert attempt.get("validation", {}).get("status") == "passed", attempt.get("validation")
            assert task.get("proof"), "the engine's Proof Pass must follow independent validation"
            assert (project / "export.py").read_text(encoding="utf-8") != BASE.BUGGY_EXPORT
            status = subprocess.run(
                ["git", "status", "--porcelain"], cwd=project, capture_output=True,
                text=True, encoding="utf-8", errors="replace",
            ).stdout.splitlines()
            changed = [line[3:].strip() for line in status if line[:2].strip() and not line[3:].strip().startswith(".ariadne/")]
            assert changed == ["export.py"], changed
    run.__name__ = f"live_{adapter_id.replace('-', '_')}_executes_a_real_task"
    return run


@case
def adapter_registry_is_structurally_conformant():
    problems = task_execution.registry_problems()
    assert not problems, problems
    matrix = task_execution.conformance_matrix()
    assert matrix["declared"] == len(task_execution.WORKER_ADAPTERS)
    assert "command-code" in [row["adapter"] for row in matrix["adapters"]]
    assert "opencode" in [row["adapter"] for row in matrix["adapters"]]
    for row in matrix["adapters"]:
        assert not row["failed"], row
        assert row["verdict"] in ("declared-not-live", "conformant-live", "unavailable"), row


@case
def custom_adapter_timeout_terminates_the_whole_process_tree():
    with BASE.workspace() as base:
        marker = base / "child-survived.txt"
        spawner = base / "spawner.py"
        spawner.write_text(
            "import subprocess, sys, time\n"
            "from pathlib import Path\n"
            "child = [sys.executable, '-c', "
            f"\"import time; from pathlib import Path; time.sleep(3); Path({str(marker)!r}).write_text('alive')\"]\n"
            "subprocess.Popen(child)\n"
            "time.sleep(60)\n",
            encoding="utf-8",
        )
        adapter = task_execution.custom_adapter("timeout-probe", f"{sys.executable} {spawner}")
        result = BASE.RUNTIME.invoke_cli_adapter(adapter, "prompt", base, 1)
        assert result["returncode"] == 124, result
        assert "timed out" in result["error"], result
        time.sleep(5)
        assert not marker.exists(), "the timed-out harness's child process survived and wrote after the timeout"


@case
def live_command_code_executes_a_real_task():
    live_adapter_case("command-code")()


@case
def live_opencode_executes_a_real_task():
    live_adapter_case("opencode")()


@case
def live_codex_executes_a_real_task():
    live_adapter_case("codex")()


@case
def live_command_code_timeout_is_classified_and_recovered_into_a_new_attempt():
    if not live_enabled():
        raise SkipCase("set ARIADNE_LIVE_ADAPTERS=1 to run the live timeout/recovery case")
    BASE.require_pytest()
    with BASE.workspace() as base:
        project = BASE.make_project(base)
        assert BASE.start_task(project)[0] == 0
        run_root = BASE.run_root_for(project)
        code, text = BASE.run_cli(
            "task-run", "--project", str(project),
            "--adapter", "command-code", "--timeout", "1", "--max-attempts", "1",
        )
        assert code == 2, text
        state = BASE.state_of(run_root)
        task = BASE.current_task(state)
        first = task["attempts"][-1]
        assert first["state"] == "failed", first
        assert first["validation"]["failure_kind"] == "validation-timeout", first["validation"]
        assert not [row for row in state["executions"] if row.get("state") not in ("COMPLETED", "FAILED")], state["executions"]
        code, text = BASE.run_cli("task-recover", "--project", str(project), "--json")
        assert code == 0, text
        view = json.loads(text)
        assert view["safe_continuation"] == "repair", view
        code, text = BASE.run_cli(
            "task-recover", "--project", str(project), "--apply",
            "--adapter", "command-code", "--escalate", "--timeout", "600", "--max-attempts", "2",
        )
        assert code in (0, 2), text
        state = BASE.state_of(run_root)
        task = BASE.current_task(state)
        assert len(task["attempts"]) == 2, task["attempts"]
        assert task["attempts"][-1]["state"] in ("validated", "failed"), task["attempts"][-1]
        if task["attempts"][-1]["state"] == "failed":
            # An honest failed correction is allowed; a fabricated pass is not.
            assert task["attempts"][-1]["validation"]["status"] in ("failed", "blocked")
            assert not task.get("proof"), task.get("proof")
        print(json.dumps({
            "adapter": "command-code",
            "first_failure": first["validation"]["failure_kind"],
            "second_attempt": task["attempts"][-1]["state"],
            "second_validation": task["attempts"][-1].get("validation", {}).get("status"),
        }, indent=2, sort_keys=True))


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
    print()
    print(f"{'PASS' if failures == 0 else 'FAIL'}  {executed - failures - len(SKIPS)}/{executed} ({len(SKIPS)} skipped)")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
