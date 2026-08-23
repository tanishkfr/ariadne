#!/usr/bin/env python3
"""Install, verify, or remove the optional Claude reasoner entry skill."""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import shutil
import subprocess
import sys
import uuid
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "adapters" / "claude-reasoner-skill"
INSTALLATION = Path("references") / "installation.json"
MARKER = ".ariadne-managed-claude-reasoner.json"


class InstallError(RuntimeError):
    pass


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git_head() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True
    )
    return result.stdout.strip() if result.returncode == 0 else "unknown"


def source_files() -> list[Path]:
    return sorted(path for path in SOURCE.rglob("*") if path.is_file())


def expected_hashes() -> dict[str, str]:
    return {path.relative_to(SOURCE).as_posix(): digest(path) for path in source_files()}


def cli_available(which=shutil.which) -> bool:
    return which("claude") is not None


def verify(target: Path) -> list[str]:
    problems = []
    marker = target / MARKER
    installation = target / INSTALLATION
    if not marker.is_file():
        problems.append("managed Claude reasoner marker is missing")
    if not installation.is_file():
        problems.append("Ariadne runtime location is missing")
    else:
        try:
            value = json.loads(installation.read_text(encoding="utf-8"))
            if Path(value.get("ariadne_root", "")).resolve() != ROOT.resolve():
                problems.append("Claude reasoner skill points at a different Ariadne runtime")
        except (json.JSONDecodeError, OSError):
            problems.append("Ariadne runtime location is malformed")
    for relative, expected in expected_hashes().items():
        path = target / relative
        if not path.is_file():
            problems.append(f"installed Claude reasoner skill file missing: {relative}")
        elif digest(path) != expected:
            problems.append(f"installed Claude reasoner skill file drifted: {relative}")
    allowed = set(expected_hashes()) | {INSTALLATION.as_posix(), MARKER}
    if target.exists():
        extras = sorted(
            path.relative_to(target).as_posix()
            for path in target.rglob("*")
            if path.is_file() and path.relative_to(target).as_posix() not in allowed
        )
        if extras:
            problems.append("installed Claude reasoner skill contains unmanaged files: " + ", ".join(extras))
    return problems


def install(target: Path, require_cli: bool = True) -> None:
    if require_cli and not cli_available():
        raise InstallError("Claude Code is not detected on PATH; nothing was installed")
    if not SOURCE.is_dir():
        raise InstallError(f"optional Claude reasoner skill source is missing: {SOURCE}")
    if target.exists() and not (target / MARKER).is_file():
        raise InstallError(f"refusing to overwrite an unmanaged Claude skill: {target}")
    target.mkdir(parents=True, exist_ok=True)
    for source in source_files():
        destination = target / source.relative_to(SOURCE)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
    installation = target / INSTALLATION
    installation.parent.mkdir(parents=True, exist_ok=True)
    installation.write_text(
        json.dumps(
            {"schema_version": 1, "ariadne_root": str(ROOT), "installed_from_commit": git_head()},
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    (target / MARKER).write_text(
        json.dumps({"owner": "Ariadne", "capability": "optional Claude reasoner"}, indent=2)
        + "\n",
        encoding="utf-8",
    )
    problems = verify(target)
    if problems:
        raise InstallError("Claude reasoner skill verification failed: " + "; ".join(problems))


def uninstall(target: Path) -> None:
    if not target.exists():
        return
    if not (target / MARKER).is_file():
        raise InstallError(f"refusing to remove an unmanaged Claude skill: {target}")
    resolved = target.resolve()
    if resolved in (Path.home().resolve(), Path(resolved.anchor)) or len(resolved.parts) < 3:
        raise InstallError(f"refusing to remove an unsafe Claude skill path: {resolved}")
    shutil.rmtree(resolved)


@contextlib.contextmanager
def self_test_workspace():
    path = ROOT / "validation" / f"claude-skill-self-test-{uuid.uuid4().hex}"
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

    with self_test_workspace() as workspace:
        target = workspace / "skill-self-test-target" / "ariadne"
        install(target, require_cli=False)
        case("optional Claude skill installs and verifies (positive control)", not verify(target))
        skill = target / "SKILL.md"
        skill.write_text(skill.read_text(encoding="utf-8") + "drift\n", encoding="utf-8")
        case("optional skill drift is detected", any("drifted" in item for item in verify(target)))
        install(target, require_cli=False)
        uninstall(target)
        case("optional skill can be removed without touching Ariadne", not target.exists() and ROOT.is_dir())

        unavailable = workspace / "unavailable" / "ariadne"
        original = cli_available
        try:
            globals()["cli_available"] = lambda which=shutil.which: False
            try:
                install(unavailable)
                missing_cli_blocked = False
            except InstallError:
                missing_cli_blocked = True
        finally:
            globals()["cli_available"] = original
        case("missing Claude CLI blocks the optional install", missing_cli_blocked and not unavailable.exists())

        unmanaged = workspace / "unmanaged" / "ariadne"
        unmanaged.mkdir(parents=True)
        (unmanaged / "SKILL.md").write_text("personal skill\n", encoding="utf-8")
        try:
            install(unmanaged, require_cli=False)
            unmanaged_blocked = False
        except InstallError:
            unmanaged_blocked = True
        case("unmanaged Claude skill is never overwritten", unmanaged_blocked)

    print("CLAUDE REASONER SKILL SELF-TEST\n")
    for name, passed in cases:
        print(("ok    " if passed else "FAIL  ") + name)
    failed = [name for name, passed in cases if not passed]
    print(f"\n{'FAILED' if failed else 'PASS'}  {len(cases) - len(failed)}/{len(cases)}")
    return 1 if failed else 0


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description=__doc__)
    value.add_argument("command", choices=["install", "verify", "uninstall"], nargs="?")
    value.add_argument("--target", default=str(Path.home() / ".claude" / "skills" / "ariadne"))
    value.add_argument("--self-test", action="store_true")
    return value


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
            print("PASS       optional Claude entry matches the active Ariadne runtime")
            return 0
        if args.command == "uninstall":
            uninstall(target)
            print(f"REMOVED  {target}")
            print("Ariadne, Codex support, projects, and evidence were not changed.")
            return 0
        problems = verify(target)
        if problems:
            print("FAIL")
            for problem in problems:
                print(f"  {problem}")
            return 1
        print(f"PASS  optional Claude reasoner skill matches {SOURCE}")
        return 0
    except InstallError as exc:
        print(f"STOPPED: {exc}")
        return 2


if __name__ == "__main__":
    sys.exit(main())
