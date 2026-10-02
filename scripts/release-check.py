#!/usr/bin/env python3
"""AR-205 release gate: one local command that decides whether the candidate ships.

Usage:
    python scripts/release-check.py                    # full gate against the working tree
    python scripts/release-check.py --allow-dirty      # development run (clean-tree check becomes OBSERVED)
    python scripts/release-check.py --dist dist        # also verify locally built artifacts
    python scripts/release-check.py --skip-benchmarks  # skip the release benchmark subset
    python scripts/release-check.py --json             # machine-readable result

Statuses are the AR-205 readiness vocabulary and are never silently upgraded:

    PASS             the check ran and satisfied its expectation
    FAIL             the check ran and found a problem (the gate exits 1)
    OBSERVED         the check ran but this run does not judge it (for example a dirty development tree)
    DECLARED_SKIP    this repository explicitly declares the check not executable here
    NOT_EXECUTED     the check could not run in this environment (for example no pip/venv)
    BLOCKED          the check could not run because an earlier dependency failed

Nothing is published, installed globally, or sent anywhere.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from ariadne_engine import release  # noqa: E402

STATUSES = ("PASS", "FAIL", "OBSERVED", "DECLARED_SKIP", "NOT_EXECUTED", "BLOCKED")


def run(argv: list[str], *, timeout: int = 1800) -> subprocess.CompletedProcess:
    return subprocess.run(argv, cwd=str(ROOT), capture_output=True, text=True, timeout=timeout)


def tail(text: str, lines: int = 4) -> str:
    rows = [row for row in (text or "").splitlines() if row.strip()]
    return " | ".join(rows[-lines:]) if rows else "(no output)"


def python_script(name: str) -> list[str]:
    return [sys.executable, str(ROOT / "scripts" / name)]


def check_tree(*, allow_dirty: bool) -> dict:
    result = run(["git", "status", "--porcelain"])
    entries = [row for row in result.stdout.splitlines() if row.strip()]
    if result.returncode != 0:
        return {"status": "FAIL", "detail": tail(result.stderr) or "git status failed"}
    if entries:
        if allow_dirty:
            return {"status": "OBSERVED", "detail": f"{len(entries)} uncommitted entries (development run)"}
        return {"status": "FAIL", "detail": f"{len(entries)} uncommitted entries"}
    return {"status": "PASS", "detail": "clean worktree"}


def check_versions() -> dict:
    problems = release.version_problems(ROOT)
    return {
        "status": "FAIL" if problems else "PASS",
        "detail": "; ".join(problems) if problems else f"all surfaces name {release.version(ROOT)}",
    }


def check_public_api() -> dict:
    problems = release.public_surface_problems()
    if problems:
        return {"status": "FAIL", "detail": "; ".join(problems)}
    module = __import__("ariadne_engine.public", fromlist=["describe_public_api"])
    description = module.describe_public_api()
    return {
        "status": "PASS",
        "detail": f"{len(description['stable_v2'])} stable, {len(description['provisional'])} provisional",
    }


def check_private_material() -> dict:
    result = run(python_script("build-release.py") + ["--self-test"])
    if result.returncode == 0 and "PASS" in result.stdout:
        return {"status": "PASS", "detail": tail(result.stdout, 2)}
    return {"status": "FAIL", "detail": tail(result.stdout + result.stderr, 4)}


def check_repository_contract() -> dict:
    result = run(python_script("check.py"))
    return {
        "status": "PASS" if result.returncode == 0 else "FAIL",
        "detail": tail(result.stdout, 2),
    }


def check_release_suite() -> dict:
    result = run(python_script("test-release.py"))
    return {
        "status": "PASS" if result.returncode == 0 else "FAIL",
        "detail": tail(result.stdout, 2),
    }


def check_distribution_lifecycle() -> dict:
    result = run(python_script("test-distribution.py"))
    return {
        "status": "PASS" if result.returncode == 0 else "FAIL",
        "detail": tail(result.stdout, 2),
    }


def check_engine_suites() -> dict:
    """The engine's own functional suites, run in full.

    These were maintainer-run only through 2.0, which meant a 2.0 release could be
    declared green on a tree whose engine core had never been executed. A gate that
    does not run the engine cannot honestly say the engine works. Both suites restore
    the source tree to its committed bytes afterwards, so running them leaves no trace.
    """
    detail = []
    for name, script in (
        ("engine core", "test-engine-core.py"),
        ("decision runtime", "test-decision-runtime.py"),
        ("decision mutations", "test-decision-mutations.py"),
        ("runtime mutations", "test-decision-runtime-mutations.py"),
    ):
        result = run(python_script(script), timeout=1800)
        if result.returncode != 0:
            return {
                "status": "FAIL",
                "detail": f"{name} failed: {tail(result.stdout + result.stderr, 4)}",
            }
        for line in reversed(result.stdout.splitlines()):
            if line.startswith("PASS "):
                detail.append(f"{name} {line[5:].strip()}")
                break
    return {"status": "PASS", "detail": "; ".join(detail)}


def check_experiments() -> dict:
    problems = release.experimental_defaults_problems()
    return {
        "status": "FAIL" if problems else "PASS",
        "detail": "; ".join(problems) if problems else "all AR-204 experiments keep their conservative defaults",
    }


def check_benchmarks(*, skip: bool) -> dict:
    if skip:
        return {"status": "DECLARED_SKIP", "detail": "release benchmark subset skipped by --skip-benchmarks"}
    import shutil
    import tempfile

    results_dir = Path(tempfile.mkdtemp(prefix="ariadne-release-gate-"))
    try:
        result = run(
            [
                sys.executable, str(ROOT / "benchmarks" / "run_benchmarks.py"),
                "--release", "--label", "release-check", "--results-dir", str(results_dir),
            ],
            timeout=3600,
        )
        summary_line = ""
        for row in result.stdout.splitlines():
            if row.startswith("summary:"):
                summary_line = row
        if result.returncode == 0 and "'fail': 0" in summary_line:
            return {"status": "PASS", "detail": summary_line or tail(result.stdout, 2)}
        return {"status": "FAIL", "detail": summary_line or tail(result.stdout + result.stderr, 4)}
    finally:
        shutil.rmtree(results_dir, ignore_errors=True)


def check_wheel_install() -> dict:
    probe = run([sys.executable, "-m", "pip", "--version"])
    if probe.returncode != 0:
        return {"status": "NOT_EXECUTED", "detail": "pip is not available in this interpreter"}
    result = run(python_script("test-wheel-install.py"), timeout=1800)
    text = result.stdout + result.stderr
    if result.returncode != 0:
        return {"status": "FAIL", "detail": tail(text, 4)}
    if "SKIP" in result.stdout or "not available" in text.lower():
        return {"status": "NOT_EXECUTED", "detail": tail(text, 2)}
    return {"status": "PASS", "detail": tail(text, 2)}


def check_artifacts(dist: Path) -> dict:
    if not dist.is_dir() or not (dist / "ariadne-release.json").is_file():
        return {"status": "NOT_EXECUTED", "detail": f"no built artifacts under {dist}"}
    problems = release.artifact_problems(dist)
    if problems:
        return {"status": "FAIL", "detail": "; ".join(problems)}
    files = sorted(path.name for path in dist.iterdir() if path.is_file())
    return {"status": "PASS", "detail": f"{len(files)} artifacts verified against the manifest: {', '.join(files[:3])}"}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--allow-dirty", action="store_true", help="development run on an uncommitted tree")
    parser.add_argument("--dist", default=str(ROOT / "dist"), help="release artifact directory to verify")
    parser.add_argument("--skip-benchmarks", action="store_true", help="skip the release benchmark subset")
    parser.add_argument("--json", action="store_true", help="print the result as JSON")
    args = parser.parse_args(argv)

    checks: list[tuple[str, dict]] = []

    def add(name: str, value: dict) -> None:
        checks.append((name, value))

    add("clean worktree", check_tree(allow_dirty=args.allow_dirty))
    add("version consistency", check_versions())
    add("public API surface", check_public_api())
    add("experimental defaults", check_experiments())
    add("repository contract", check_repository_contract())
    add("engine suites", check_engine_suites())
    add("release tests", check_release_suite())
    add("distribution lifecycle", check_distribution_lifecycle())
    add("runtime bundle and private material", check_private_material())
    add("release benchmark subset", check_benchmarks(skip=args.skip_benchmarks))
    add("wheel install", check_wheel_install())
    add("release artifacts", check_artifacts(Path(args.dist)))

    failures = [name for name, value in checks if value["status"] == "FAIL"]
    document = {
        "schema_version": 1,
        "kind": "ariadne-release-check",
        "version": release.version(ROOT),
        "checks": {name: value for name, value in checks},
        "failed": failures,
    }
    if args.json:
        print(json.dumps(document, indent=2, sort_keys=True))
    else:
        print(f"ARIADNE RELEASE CHECK - version {release.version(ROOT)}\n")
        width = max(len(name) for name, _ in checks)
        for name, value in checks:
            print(f"{value['status'].ljust(13)} {name.ljust(width)}  {value['detail']}")
        print()
        if failures:
            print(f"FAILED: {len(failures)} check(s): {', '.join(failures)}")
        else:
            skipped = [name for name, value in checks if value["status"] in ("DECLARED_SKIP", "NOT_EXECUTED", "BLOCKED")]
            print(
                "PASS: the release gate is green"
                + (f" ({len(skipped)} check(s) not executed: {', '.join(skipped)})" if skipped else "")
            )
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
