#!/usr/bin/env python3
"""Offline wheel-to-project stranger test for the public Builder OS product."""

from __future__ import annotations

import contextlib
import json
import os
import shutil
import subprocess
import sys
import time
import uuid
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


class StrangerTestError(RuntimeError):
    pass


def run(
    command: list[str],
    cwd: Path,
    expected: int = 0,
    environment: dict[str, str] | None = None,
) -> subprocess.CompletedProcess:
    result = subprocess.run(
        command, cwd=cwd, capture_output=True, text=True, env=environment
    )
    if result.returncode != expected:
        raise StrangerTestError(
            f"command returned {result.returncode}, expected {expected}: {' '.join(command)}\n"
            f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        )
    return result


@contextlib.contextmanager
def workspace():
    path = ROOT / "validation" / f"wheel-self-test-{uuid.uuid4().hex}"
    path.mkdir()
    try:
        yield path
    finally:
        if path.exists():
            last_error = None
            for attempt in range(8):
                try:
                    shutil.rmtree(path)
                    last_error = None
                    break
                except OSError as exc:
                    last_error = exc
                    time.sleep(0.1 * (attempt + 1))
            if last_error is not None:
                raise last_error


def self_test() -> int:
    cases: list[tuple[str, bool]] = []

    def case(name: str, passed: bool) -> None:
        cases.append((name, bool(passed)))

    with workspace() as root:
        temporary = root / "temporary"
        temporary.mkdir()
        environment_vars = os.environ.copy()
        environment_vars.update({"TEMP": str(temporary), "TMP": str(temporary)})
        wheel_dir = root / "wheel"
        wheel_dir.mkdir()
        run(
            [
                sys.executable, "-m", "pip", "wheel", ".", "--no-deps",
                "--no-build-isolation", "--wheel-dir", str(wheel_dir),
            ],
            ROOT,
            environment=environment_vars,
        )
        wheels = list(wheel_dir.glob("builder_os-*.whl"))
        case("source builds one platform-neutral wheel", len(wheels) == 1 and "py3-none-any" in wheels[0].name)
        with zipfile.ZipFile(wheels[0]) as wheel:
            metadata_name = next(name for name in wheel.namelist() if name.endswith("/METADATA"))
            wheel_metadata = wheel.read(metadata_name).decode("utf-8")
        case(
            "package manager receives the minimum Python contract",
            "Requires-Python: >=3.8" in wheel_metadata,
        )

        environment = root / "clean-python"
        run([sys.executable, "-m", "venv", str(environment)], ROOT, environment=environment_vars)
        python = environment / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
        run(
            [str(python), "-m", "pip", "install", "--no-index", "--no-deps", str(wheels[0])],
            root,
            environment=environment_vars,
        )
        version_result = run(
            [str(python), "-m", "builderos", "--version"],
            root,
            environment=environment_vars,
        )
        case("fresh Python environment exposes Builder OS version", version_result.stdout.strip() == "Builder OS 1.5.0")

        data_home = root / "person-data"
        skill = root / "person-codex-skills" / "builderos"
        install_result = run(
            [
                str(python), "-m", "builderos", "--data-home", str(data_home),
                "--skill-home", str(skill), "install",
            ],
            root,
            environment=environment_vars,
        )
        case("stranger install gives one plain next action", "type $builderos" in install_result.stdout and "S1" not in install_result.stdout)
        current = json.loads((data_home / "current.json").read_text(encoding="utf-8"))
        runtime = Path(current["runtime_root"])
        installation = json.loads((skill / "references" / "installation.json").read_text(encoding="utf-8"))
        expected_runtime = (data_home / "versions" / "1.5.0").resolve()
        case(
            "wheel carries a canonical runtime with no source-checkout dependency",
            runtime.resolve() == expected_runtime
            and Path(installation["builder_os_root"]).resolve() == expected_runtime
            and runtime != ROOT,
        )

        doctor_result = run(
            [str(python), "-m", "builderos", "--data-home", str(data_home), "--skill-home", str(skill), "doctor"],
            root,
            environment=environment_vars,
        )
        case("doctor verifies the isolated installed product", "[OK] Runtime" in doctor_result.stdout and "[OK] Codex skill" in doctor_result.stdout)

        (runtime / "ROUTER.md").unlink()
        repair_result = run(
            [
                str(python), "-m", "builderos", "--data-home", str(data_home),
                "--skill-home", str(skill), "install",
            ],
            root,
            environment=environment_vars,
        )
        repaired_doctor = run(
            [str(python), "-m", "builderos", "--data-home", str(data_home), "--skill-home", str(skill), "doctor"],
            root,
            environment=environment_vars,
        )
        case(
            "reinstall repairs a damaged runtime from the self-contained wheel",
            (runtime / "ROUTER.md").is_file()
            and "Builder OS 1.5.0 is installed" in repair_result.stdout
            and "[OK] Runtime" in repaired_doctor.stdout,
        )

        project = root / "ordinary-project"
        start_result = run(
            [
                str(python), str(runtime / "scripts" / "builderos.py"), "start",
                "--project", str(project), "--request",
                "Make a small editorial site about neighbourhood signs.",
            ],
            root,
            environment=environment_vars,
        )
        case("installed runtime starts an ordinary-language project", project.is_dir() and "ready for its brief" in start_result.stdout)
        runs = list(root.glob("ordinary-project-builderos"))
        case("project start creates durable external run state", len(runs) == 1 and (runs[0] / "builderos-run.json").is_file())

        project_sentinel = project / "person-owned.txt"
        project_sentinel.write_text("keep\n", encoding="utf-8")
        uninstall_result = run(
            [
                str(python), "-m", "builderos", "--data-home", str(data_home),
                "--skill-home", str(skill), "uninstall", "--yes",
            ],
            root,
            environment=environment_vars,
        )
        case("uninstall preserves project and run history", project_sentinel.is_file() and (runs[0] / "builderos-run.json").is_file())
        case("uninstall explains the remaining launcher", "launcher remains" in uninstall_result.stdout)

    print("BUILDER OS WHEEL STRANGER SELF-TEST\n")
    for name, passed in cases:
        print(("ok    " if passed else "FAIL  ") + name)
    failed = [name for name, passed in cases if not passed]
    print(f"\n{'FAILED' if failed else 'PASS'}  {len(cases) - len(failed)}/{len(cases)}")
    return 1 if failed else 0


if __name__ == "__main__":
    try:
        raise SystemExit(self_test())
    except StrangerTestError as exc:
        print(f"FAILED: {exc}")
        raise SystemExit(1)
