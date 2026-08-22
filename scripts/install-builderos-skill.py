#!/usr/bin/env python3
"""Install or verify the personal Builder OS Codex entry skill.

The repository copy remains canonical. The installed copy carries only one
machine-local file, references/installation.json, so it can locate this Builder
OS checkout from projects elsewhere on disk.
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import shutil
import sys
import uuid
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
    p.add_argument("command", nargs="?", choices=["install", "verify"])
    p.add_argument("--target", default=str(Path.home() / ".agents" / "skills" / "builderos"))
    p.add_argument("--self-test", action="store_true")
    return p


@contextlib.contextmanager
def self_test_workspace():
    path = ROOT / "validation" / f"skill-install-self-test-{uuid.uuid4().hex}"
    path.mkdir()
    try:
        yield path
    finally:
        if path.exists():
            shutil.rmtree(path)


def self_test() -> int:
    cases = []

    def case(name: str, passed: bool) -> None:
        cases.append((name, passed))

    with self_test_workspace() as first_workspace, self_test_workspace() as second_workspace:
        case(
            "independent installer self-test workspaces do not collide",
            first_workspace != second_workspace and first_workspace.exists() and second_workspace.exists(),
        )

    with self_test_workspace() as workspace:
        target = workspace / "managed-skill"
        install(target)
        case("managed skill installs and verifies (positive control)", not verify(target))
        skill = target / "SKILL.md"
        skill.write_text(skill.read_text(encoding="utf-8") + "drift\n", encoding="utf-8")
        case("installed source drift is detected", any("drifted" in item for item in verify(target)))
        install(target)
        extra = target / "unexpected.txt"
        extra.write_text("unexpected\n", encoding="utf-8")
        case("unmanaged installed files are detected", any("unmanaged" in item for item in verify(target)))
        extra.unlink()
        location = json.loads((target / INSTALLATION).read_text(encoding="utf-8"))
        case("installed skill records the canonical checkout", Path(location["builder_os_root"]).resolve() == ROOT.resolve())

        unmanaged = workspace / "unmanaged-skill"
        unmanaged.mkdir()
        (unmanaged / "SKILL.md").write_text("personal work\n", encoding="utf-8")
        try:
            install(unmanaged)
            unmanaged_refused = False
        except InstallError:
            unmanaged_refused = True
        case("unmanaged skill is never overwritten", unmanaged_refused)

    print("BUILDER OS SKILL INSTALL SELF-TEST\n")
    for name, passed in cases:
        print(("ok    " if passed else "FAIL  ") + name)
    failed = [name for name, passed in cases if not passed]
    print(f"\n{'FAILED' if failed else 'PASS'}  {len(cases) - len(failed)}/{len(cases)}")
    return 1 if failed else 0


def main() -> int:
    args = parser().parse_args()
    if args.self_test:
        return self_test()
    if not args.command:
        parser().error("command is required unless --self-test is used")
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
