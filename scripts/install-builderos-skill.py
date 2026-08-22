#!/usr/bin/env python3
"""Install or verify the personal Builder OS Codex entry skill.

The repository copy remains canonical. The installed copy carries only one
machine-local file, references/installation.json, so it can locate this Builder
OS checkout from projects elsewhere on disk.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / ".agents" / "skills" / "builderos"
INSTALLATION = "references/installation.json"
MANAGED_MARKER = ".builderos-managed.json"


class InstallError(RuntimeError):
    pass


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_files() -> list[Path]:
    return sorted(
        path for path in SOURCE.rglob("*")
        if path.is_file() and path.relative_to(SOURCE).as_posix() != "references/installation.example.json"
    )


def expected_hashes() -> dict[str, str]:
    return {path.relative_to(SOURCE).as_posix(): digest(path) for path in source_files()}


def verify(target: Path) -> list[str]:
    problems = []
    marker = target / MANAGED_MARKER
    installation = target / INSTALLATION
    if not marker.is_file():
        problems.append("managed-install marker is missing")
    if not installation.is_file():
        problems.append("installation location is missing")
    else:
        try:
            location = json.loads(installation.read_text(encoding="utf-8"))
            if Path(location.get("builder_os_root", "")).resolve() != ROOT.resolve():
                problems.append("installed skill points at a different Builder OS checkout")
        except (json.JSONDecodeError, OSError):
            problems.append("installation location is malformed")
    for relative, expected in expected_hashes().items():
        installed = target / relative
        if not installed.is_file():
            problems.append(f"installed skill file missing: {relative}")
        elif digest(installed) != expected:
            problems.append(f"installed skill file drifted: {relative}")
    allowed = set(expected_hashes()) | {INSTALLATION, MANAGED_MARKER}
    if target.exists():
        extras = sorted(
            path.relative_to(target).as_posix()
            for path in target.rglob("*")
            if path.is_file() and path.relative_to(target).as_posix() not in allowed
        )
        if extras:
            problems.append("installed skill contains unmanaged files: " + ", ".join(extras))
    return problems


def install(target: Path) -> None:
    if not SOURCE.is_dir():
        raise InstallError(f"canonical Builder OS skill is missing: {SOURCE}")
    if target.exists() and not (target / MANAGED_MARKER).is_file():
        raise InstallError(f"refusing to overwrite an unmanaged skill: {target}")
    target.mkdir(parents=True, exist_ok=True)
    for source in source_files():
        relative = source.relative_to(SOURCE)
        destination = target / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
    installation = {
        "builder_os_root": str(ROOT),
        "installed_from_commit": git_head(),
    }
    location_path = target / INSTALLATION
    location_path.parent.mkdir(parents=True, exist_ok=True)
    location_path.write_text(json.dumps(installation, indent=2) + "\n", encoding="utf-8")
    (target / MANAGED_MARKER).write_text(
        json.dumps({"owner": "Builder OS", "source": str(SOURCE)}, indent=2) + "\n",
        encoding="utf-8",
    )
    problems = verify(target)
    if problems:
        raise InstallError("installation verification failed: " + "; ".join(problems))


def git_head() -> str:
    import subprocess

    result = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True
    )
    return result.stdout.strip() if result.returncode == 0 else "unknown"


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("command", choices=["install", "verify"])
    p.add_argument("--target", default=str(Path.home() / ".agents" / "skills" / "builderos"))
    return p


def main() -> int:
    args = parser().parse_args()
    target = Path(args.target).resolve()
    try:
        if args.command == "install":
            install(target)
            print(f"INSTALLED  {target}")
            print("PASS       canonical skill copy and Builder OS location verified")
            return 0
        problems = verify(target)
        if problems:
            print("FAIL")
            for problem in problems:
                print(f"  {problem}")
            return 1
        print(f"PASS  installed Builder OS skill matches {SOURCE}")
        return 0
    except InstallError as exc:
        print(f"STOPPED: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
