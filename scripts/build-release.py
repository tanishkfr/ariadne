#!/usr/bin/env python3
"""Build a deterministic Builder OS runtime release bundle.

The repository remains canonical. This script copies an explicit runtime
allowlist into a generated immutable transport artifact and records every hash.
It never packages validation runs, fixtures, operations logs, readiness reports,
or maintainer-only release tooling.
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import time
import uuid
import zipfile
from pathlib import Path, PurePosixPath


ROOT = Path(__file__).resolve().parent.parent
VERSION_PATH = ROOT / "VERSION"
RELEASE_NOTES_PATH = ROOT / "RELEASE-NOTES.md"
PYPROJECT_PATH = ROOT / "pyproject.toml"
LICENSE_PATH = ROOT / "LICENSE"
REPOSITORY_URL = "https://github.com/tanishkfr/builder-os"
RUNTIME_TOP_LEVEL = [
    "VERSION", "LICENSE", "ROUTER.md", "WORKFLOW.md", "DESIGN-TASTE.md", "DESIGN-MOTION.md",
    "DESIGN-ASSETS.md", "QA-POLICY.md", "EVALUATION-RUBRICS.md",
    "LIBRARY-POLICY.md", "RESEARCH-POLICY.md", "PRIVACY-POLICY.md",
    "MODEL-ROUTING.md", "BUDGET-POLICY.md", "CONTENT-SYSTEM.md",
]
RUNTIME_TREES = ["prompts", "templates", "modes", "skills", "adapters", "references"]
RUNTIME_SCRIPTS = [
    "scripts/builderos.py", "scripts/prepare-stage.py",
    "scripts/creative-intelligence.py", "scripts/creative-operations.py",
    "scripts/reasoners.py",
    "scripts/install-builderos-skill.py", "scripts/install-claude-reasoner-skill.py",
]
RUNTIME_SKILL = ".agents/skills/builderos"
FIXED_ZIP_TIME = (2020, 1, 1, 0, 0, 0)


class ReleaseError(RuntimeError):
    pass


def digest_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def digest(path: Path) -> str:
    return digest_bytes(path.read_bytes())


def version() -> str:
    value = VERSION_PATH.read_text(encoding="utf-8").strip()
    if not value or not __import__("re").fullmatch(r"\d+\.\d+\.\d+(?:(?:a|b|rc)\d+)?", value):
        raise ReleaseError(f"VERSION is not a supported release version: {value!r}")
    return value


def git_head() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True
    )
    return result.stdout.strip() if result.returncode == 0 else "unknown"


def publication_state() -> dict:
    metadata = PYPROJECT_PATH.read_text(encoding="utf-8")
    if 'license = "Apache-2.0"' not in metadata or not LICENSE_PATH.is_file():
        return {
            "status": "blocked",
            "reason": "public licence not selected",
        }
    return {
        "status": "candidate",
        "reason": "licence files are present; human release authority is still required",
    }


def tracked_dirty() -> list[str]:
    result = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=no"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    return [line for line in result.stdout.splitlines() if line.strip()]


def runtime_sources() -> list[tuple[str, Path]]:
    rows: list[tuple[str, Path]] = []
    for relative in RUNTIME_TOP_LEVEL + RUNTIME_SCRIPTS:
        path = ROOT / relative
        if not path.is_file():
            raise ReleaseError(f"runtime source is missing: {relative}")
        rows.append((PurePosixPath(relative).as_posix(), path))
    for tree in RUNTIME_TREES + [RUNTIME_SKILL]:
        root = ROOT / tree
        if not root.is_dir():
            raise ReleaseError(f"runtime source tree is missing: {tree}")
        for path in sorted(root.rglob("*")):
            if path.is_file() and path.name != "installation.json":
                rows.append((path.relative_to(ROOT).as_posix(), path))
    names = [name for name, _ in rows]
    if len(names) != len(set(names)):
        raise ReleaseError("runtime allowlist contains duplicate paths")
    return sorted(rows)


def runtime_manifest(source_commit: str | None = None) -> dict:
    files = {relative: digest(path) for relative, path in runtime_sources()}
    return {
        "schema_version": 1,
        "product": "Builder OS",
        "version": version(),
        "source_commit": source_commit or git_head(),
        "minimum_bootstrap_version": "1.4.0",
        "project_state_schema": {"min": 1, "max": 1},
        "files": files,
    }


def zip_entry(archive: zipfile.ZipFile, name: str, content: bytes) -> None:
    info = zipfile.ZipInfo(name, FIXED_ZIP_TIME)
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = 0o100644 << 16
    archive.writestr(info, content)


def build_launcher(output: Path) -> Path:
    backend_path = ROOT / "build_backend" / "builderos_backend.py"
    spec = importlib.util.spec_from_file_location("builderos_release_backend", backend_path)
    if spec is None or spec.loader is None:
        raise ReleaseError(f"could not load launcher build backend: {backend_path}")
    backend = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(backend)
    return output / backend.build_wheel(str(output))


def build(output: Path, allow_dirty: bool = False, source_commit: str | None = None) -> dict:
    dirty = tracked_dirty()
    if dirty and not allow_dirty:
        raise ReleaseError("refusing to build a public release from tracked uncommitted changes")
    output.mkdir(parents=True, exist_ok=True)
    manifest = runtime_manifest(source_commit)
    release_version = manifest["version"]
    artifact_name = f"builder-os-runtime-{release_version}.zip"
    artifact = output / artifact_name
    manifest_bytes = (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode("utf-8")
    with zipfile.ZipFile(artifact, "w") as archive:
        for relative, path in runtime_sources():
            zip_entry(archive, relative, path.read_bytes())
        zip_entry(archive, "RELEASE-MANIFEST.json", manifest_bytes)
    artifact_sha = digest(artifact)
    launcher = build_launcher(output)
    launcher_sha = digest(launcher)
    release_notes_name = f"builder-os-{release_version}-release-notes.md"
    release_notes = output / release_notes_name
    release_notes.write_bytes(RELEASE_NOTES_PATH.read_bytes())
    release_notes_sha = digest(release_notes)
    descriptor = {
        "schema_version": 1,
        "product": "Builder OS",
        "version": release_version,
        "artifact": f"{REPOSITORY_URL}/releases/download/v{release_version}/{artifact_name}",
        "sha256": artifact_sha,
        "launcher": {
            "artifact": f"{REPOSITORY_URL}/releases/download/v{release_version}/{launcher.name}",
            "sha256": launcher_sha,
        },
        "release_notes": {
            "artifact": f"{REPOSITORY_URL}/releases/download/v{release_version}/{release_notes_name}",
            "sha256": release_notes_sha,
        },
        "source_commit": manifest["source_commit"],
        "requires_python": ">=3.8",
        "project_state_schema": manifest["project_state_schema"],
        "publication": publication_state(),
    }
    descriptor_path = output / "builder-os-release.json"
    descriptor_path.write_text(json.dumps(descriptor, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (output / f"{artifact_name}.sha256").write_text(
        f"{artifact_sha}  {artifact_name}\n", encoding="utf-8"
    )
    (output / f"{launcher.name}.sha256").write_text(
        f"{launcher_sha}  {launcher.name}\n", encoding="utf-8"
    )
    checksum_inventory = output / "SHA256SUMS.txt"
    checksum_inventory.write_text(
        "".join(
            f"{digest(path)}  {path.name}\n"
            for path in (artifact, launcher, descriptor_path, release_notes)
        ),
        encoding="utf-8",
    )
    return {
        "artifact": artifact,
        "launcher": launcher,
        "descriptor": descriptor_path,
        "release_notes": release_notes,
        "checksums": checksum_inventory,
        "manifest": manifest,
    }


@contextlib.contextmanager
def self_test_workspace():
    path = ROOT / "validation" / f"release-self-test-{uuid.uuid4().hex}"
    path.mkdir()
    try:
        yield path
    finally:
        if path.exists():
            last_error = None
            for attempt in range(5):
                try:
                    shutil.rmtree(path)
                    last_error = None
                    break
                except OSError as exc:
                    last_error = exc
                    time.sleep(0.05 * (attempt + 1))
            if last_error is not None:
                raise last_error


def self_test() -> int:
    cases = []

    def case(name: str, passed: bool) -> None:
        cases.append((name, passed))

    with self_test_workspace() as first, self_test_workspace() as second:
        one = build(first, allow_dirty=True, source_commit="fixture-commit")
        two = build(second, allow_dirty=True, source_commit="fixture-commit")
        case("runtime release builds (positive control)", one["artifact"].is_file())
        case("runtime release is deterministic", digest(one["artifact"]) == digest(two["artifact"]))
        case("launcher wheel is deterministic", digest(one["launcher"]) == digest(two["launcher"]))
        descriptor = json.loads(one["descriptor"].read_text(encoding="utf-8"))
        case("release description authenticates the exact bundle", descriptor["sha256"] == digest(one["artifact"]))
        case("release description authenticates the launcher", descriptor["launcher"]["sha256"] == digest(one["launcher"]))
        case("release description authenticates the release notes", descriptor["release_notes"]["sha256"] == digest(one["release_notes"]))
        case(
            "release description preserves the repository publication boundary",
            descriptor["publication"] == publication_state(),
        )
        checksum_rows = {
            name: value
            for value, name in (
                line.split("  ", 1)
                for line in one["checksums"].read_text(encoding="utf-8").splitlines()
            )
        }
        case(
            "aggregate checksums authenticate every publishable input",
            len(checksum_rows) == 4
            and all(checksum_rows.get(one[key].name) == digest(one[key]) for key in (
                "artifact", "launcher", "descriptor", "release_notes"
            )),
        )
        with zipfile.ZipFile(one["artifact"]) as archive:
            names = set(archive.namelist())
            embedded = json.loads(archive.read("RELEASE-MANIFEST.json"))
            runtime_bytes = b"\n".join(
                archive.read(name) for name in sorted(names) if not name.endswith("/")
            ).lower()
        case("release carries its internal file manifest", embedded["source_commit"] == "fixture-commit")
        case(
            "runtime includes managed skill, controller, and optional reasoner adapter",
            ".agents/skills/builderos/SKILL.md" in names
            and "scripts/builderos.py" in names
            and "scripts/reasoners.py" in names
            and "adapters/reasoners.json" in names,
        )
        with zipfile.ZipFile(one["launcher"]) as wheel:
            wheel_names = set(wheel.namelist())
        case("launcher wheel carries seed runtime and command", "builderos/seed-runtime.zip" in wheel_names and any(name.endswith("/entry_points.txt") for name in wheel_names))
        case("runtime carries the approved licence", "LICENSE" in names)
        case(
            "launcher wheel carries the approved licence",
            any(name.endswith(".dist-info/licenses/LICENSE") for name in wheel_names),
        )
        case("runtime excludes developer validation and operations", not any(name.startswith(("validation/", "operations/", "tests/")) for name in names))
        case("runtime excludes maintainer machine paths", all("snprasad" not in archive_name.lower() and "testbed" not in archive_name.lower() for archive_name in names))
        case(
            "runtime content excludes maintainer-specific paths and private test data",
            not any(token in runtime_bytes for token in (
                b"snprasad", b"c:\\testbed", b"builder os tests",
            ))
            and not any(
                part in name.lower()
                for name in names
                for part in ("transcript", "validation/runs", ".env", "credential")
            ),
        )
        case("VERSION is the release authority", descriptor["version"] == VERSION_PATH.read_text(encoding="utf-8").strip())
        case(
            "release notes name the authoritative version",
            f"Builder OS {descriptor['version']}" in one["release_notes"].read_text(encoding="utf-8"),
        )

    print("BUILDER OS RELEASE SELF-TEST\n")
    for name, passed in cases:
        print(("ok    " if passed else "FAIL  ") + name)
    failed = [name for name, passed in cases if not passed]
    print(f"\n{'FAILED' if failed else 'PASS'}  {len(cases) - len(failed)}/{len(cases)}")
    return 1 if failed else 0


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description=__doc__)
    value.add_argument("--output", default=str(ROOT / "dist"))
    value.add_argument("--allow-dirty", action="store_true", help="build a local test artifact from uncommitted sources")
    value.add_argument("--self-test", action="store_true")
    return value


def main() -> int:
    args = parser().parse_args()
    if args.self_test:
        return self_test()
    try:
        result = build(Path(args.output).resolve(), args.allow_dirty)
    except ReleaseError as exc:
        print(f"STOPPED: {exc}")
        return 2
    print(f"BUILT  {result['artifact']}")
    print(f"WHEEL  {result['launcher']}")
    print(f"INDEX  {result['descriptor']}")
    print(f"NOTES  {result['release_notes']}")
    print(f"SHA256 {result['checksums']}")
    publication = publication_state()
    if publication["status"] == "blocked":
        print("STATUS PACKAGING CANDIDATE - public release blocked: " + publication["reason"])
        print("NEXT   obtain explicit human licence selection; do not publish these files")
    else:
        print("STATUS RELEASE CANDIDATE - not published")
        print("NEXT   obtain explicit human tag and GitHub release authority")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
