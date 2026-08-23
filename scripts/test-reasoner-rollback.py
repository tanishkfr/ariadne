#!/usr/bin/env python3
"""Exercise V1.5 -> optional reasoner -> disable -> V1.5 rollback."""

from __future__ import annotations

import argparse
import contextlib
import json
import shutil
import subprocess
import sys
import uuid
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from builderos import cli  # noqa: E402


@contextlib.contextmanager
def workspace():
    path = ROOT / "validation" / f"reasoner-rollback-self-test-{uuid.uuid4().hex}"
    path.mkdir()
    try:
        yield path
    finally:
        if path.exists():
            shutil.rmtree(path)


def exercise(baseline_bundle: Path, current_bundle: Path) -> list[tuple[str, bool]]:
    cases = []

    def case(name: str, passed: bool) -> None:
        cases.append((name, bool(passed)))

    with workspace() as root:
        home = root / "user-data"
        codex_skill = root / "codex-skills" / "builderos"
        claude_skill = root / "claude-skills" / "builderos"
        project = root / "project"
        run_root = root / "project-builderos"

        baseline = cli.install_bundle(baseline_bundle, home, codex_skill)
        case(
            "exact baseline bundle installs first",
            baseline["version"] == "1.5.0"
            and not cli.runtime_problems(Path(baseline["runtime_root"])),
        )

        current = cli.install_bundle(current_bundle, home, codex_skill)
        current_runtime = Path(current["runtime_root"])
        case(
            "V1.5.1 experiment activates without damaging the baseline",
            current["version"] == "1.5.1"
            and (home / "versions" / "1.5.0").is_dir()
            and not cli.runtime_problems(current_runtime),
        )

        cli.configure_claude_reasoner(
            home, claude_skill, "install", require_cli=False
        )
        case(
            "optional Claude entry exists only after explicit enable",
            (claude_skill / cli.CLAUDE_SKILL_MARKER).is_file()
            and not (project / "CLAUDE.md").exists(),
        )

        start = subprocess.run(
            [
                sys.executable,
                str(current_runtime / "scripts" / "builderos.py"),
                "start",
                "--project", str(project),
                "--run-root", str(run_root),
                "--run-id", "rollback-fixture",
                "--request", "Create a small provider-neutral website.",
                "--synthetic-validation",
            ],
            capture_output=True,
            text=True,
        )
        state = json.loads((run_root / "builderos-run.json").read_text(encoding="utf-8"))
        case(
            "Codex default still starts a project while Claude support exists",
            start.returncode == 0
            and state["reasoner"]["id"] == "codex"
            and not (project / "CLAUDE.md").exists(),
        )

        cli.configure_claude_reasoner(
            home, claude_skill, "uninstall", require_cli=False
        )
        case(
            "optional Claude entry disables cleanly",
            not claude_skill.exists() and run_root.is_dir() and project.is_dir(),
        )

        rolled_back = cli.rollback(home, codex_skill, "1.5.0")
        baseline_runtime = Path(rolled_back["runtime_root"])
        case(
            "rollback restores the exact V1.5 runtime and Codex skill",
            rolled_back["version"] == "1.5.0"
            and not cli.runtime_problems(baseline_runtime)
            and not cli.skill_problems(baseline_runtime, codex_skill),
        )

        status = subprocess.run(
            [
                sys.executable,
                str(baseline_runtime / "scripts" / "builderos.py"),
                "status",
                "--run-root", str(run_root),
                "--json",
            ],
            capture_output=True,
            text=True,
        )
        status_payload = json.loads(status.stdout) if status.stdout.strip().startswith("{") else {}
        compatible = (
            status.returncode == 0
            and status_payload.get("current_boundary") == "S1"
            and not (project / "CLAUDE.md").exists()
            and (run_root / "builderos-run.json").is_file()
        )
        if not compatible:
            print(
                "ROLLBACK STATUS DIAGNOSTIC "
                + json.dumps(
                    {
                        "returncode": status.returncode,
                        "stdout": status.stdout,
                        "stderr": status.stderr,
                        "claude_file": (project / "CLAUDE.md").exists(),
                        "run_state": (run_root / "builderos-run.json").is_file(),
                    },
                    sort_keys=True,
                )
            )
        case(
            "V1.5 reads the existing project without Claude files or migration",
            compatible,
        )
    return cases


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description=__doc__)
    value.add_argument("--baseline-bundle", required=True)
    value.add_argument("--current-bundle", required=True)
    return value


def main() -> int:
    args = parser().parse_args()
    cases = exercise(Path(args.baseline_bundle).resolve(), Path(args.current_bundle).resolve())
    print("BUILDER OS REASONER ROLLBACK TEST\n")
    for name, passed in cases:
        print(("ok    " if passed else "FAIL  ") + name)
    failed = [name for name, passed in cases if not passed]
    print(f"\n{'FAILED' if failed else 'PASS'}  {len(cases) - len(failed)}/{len(cases)}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
