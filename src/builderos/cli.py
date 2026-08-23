"""Install, diagnose, update, roll back, and remove Builder OS.

The launcher is deliberately dependency-free. Canonical Builder OS sources are
delivered as immutable release bundles, not copied into user projects. A small
current.json pointer activates one verified user-local runtime at a time.
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import importlib.resources
import json
import os
import platform
import re
import runpy
import shutil
import stat
import sys
import tempfile
import types
import urllib.parse
import urllib.request
import uuid
import zipfile
from datetime import datetime
from pathlib import Path, PurePosixPath

from . import package_version


PRODUCT = "Builder OS"
INSTALL_SCHEMA = 1
RELEASE_SCHEMA = 1
MIN_PYTHON = (3, 8)
DEFAULT_RELEASE_MANIFEST = (
    "https://github.com/tanishkfr/builder-os/releases/latest/download/"
    "builder-os-release.json"
)
CURRENT_NAME = "current.json"
RUNTIME_MANIFEST = "RELEASE-MANIFEST.json"
SKILL_RELATIVE = Path(".agents") / "skills" / "builderos"
SKILL_MARKER = ".builderos-managed.json"
SKILL_INSTALLATION = Path("references") / "installation.json"
CLAUDE_SKILL_MARKER = ".builderos-managed-claude-reasoner.json"
VERSION_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)(?:(a|b|rc)(\d+))?$")
BASE_REQUIRED_RUNTIME_FILES = {
    "VERSION",
    "ROUTER.md",
    "WORKFLOW.md",
    "prompts/project-start.md",
    "prompts/design-direction.md",
    "prompts/build-kickoff.md",
    "prompts/project-review.md",
    "templates/PROJECT.md",
    "templates/DESIGN.md",
    "templates/HANDOFF.md",
    "templates/QA.md",
    "scripts/builderos.py",
    "scripts/prepare-stage.py",
    "scripts/creative-intelligence.py",
    "scripts/creative-operations.py",
    ".agents/skills/builderos/SKILL.md",
    ".agents/skills/builderos/agents/openai.yaml",
}
V151_REQUIRED_RUNTIME_FILES = {
    "scripts/reasoners.py",
    "scripts/install-claude-reasoner-skill.py",
    "adapters/reasoners.json",
    "adapters/claude-reasoner-skill/SKILL.md",
}


class ProductError(RuntimeError):
    pass


def now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_json(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ProductError(f"Could not read {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ProductError(f"Expected a JSON object in {path}")
    return value


def replace_with_retry(
    source: Path,
    target: Path,
    *,
    attempts: int = 10,
    replace=None,
    sleep=None,
) -> None:
    """Complete one atomic replace despite short Windows sharing violations."""
    replace = replace or (lambda old, new: old.replace(new))
    sleep = sleep or __import__("time").sleep
    last_error = None
    for attempt in range(attempts):
        try:
            replace(source, target)
            return
        except (PermissionError, OSError) as exc:
            last_error = exc
            if attempt + 1 < attempts:
                sleep(0.05 * (attempt + 1))
    if last_error is not None:
        raise last_error


def atomic_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        replace_with_retry(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def append_history(home: Path, event: str, details: dict) -> None:
    home.mkdir(parents=True, exist_ok=True)
    record = {"at": now(), "event": event, **details}
    with (home / "install-history.jsonl").open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(record, sort_keys=True) + "\n")


def version_key(value: str) -> tuple:
    match = VERSION_RE.fullmatch(value)
    if not match:
        raise ProductError(f"Unsupported Builder OS version: {value}")
    major, minor, patch = (int(match.group(index)) for index in (1, 2, 3))
    label = match.group(4)
    number = int(match.group(5) or 0)
    prerelease_order = {"a": 0, "b": 1, "rc": 2, None: 3}
    return major, minor, patch, prerelease_order[label], number


def user_data_home(
    system: str | None = None,
    environ: dict[str, str] | None = None,
    home: Path | None = None,
) -> Path:
    environ = os.environ if environ is None else environ
    home = Path.home() if home is None else home
    override = environ.get("BUILDER_OS_DATA_HOME")
    if override:
        return Path(override).expanduser().resolve()
    system = platform.system() if system is None else system
    if system == "Windows":
        base = Path(environ.get("LOCALAPPDATA", home / "AppData" / "Local"))
        return (base / "BuilderOS").resolve()
    if system == "Darwin":
        return (home / "Library" / "Application Support" / "BuilderOS").resolve()
    base = Path(environ.get("XDG_DATA_HOME", home / ".local" / "share"))
    return (base / "builderos").resolve()


def skill_target(
    environ: dict[str, str] | None = None,
    home: Path | None = None,
) -> Path:
    environ = os.environ if environ is None else environ
    home = Path.home() if home is None else home
    override = environ.get("BUILDER_OS_SKILL_HOME")
    if override:
        return (Path(override).expanduser().resolve() / "builderos")
    codex_home = environ.get("CODEX_HOME")
    if codex_home:
        return (Path(codex_home).expanduser().resolve() / "skills" / "builderos")
    legacy = home / ".agents" / "skills"
    standard = home / ".codex" / "skills"
    for parent in (legacy, standard):
        candidate = parent / "builderos"
        if (candidate / SKILL_MARKER).is_file():
            return candidate.resolve()
    if legacy.is_dir():
        return (legacy / "builderos").resolve()
    return (standard / "builderos").resolve()


def is_within(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def current_install(home: Path) -> dict | None:
    path = home / CURRENT_NAME
    if not path.is_file():
        return None
    value = read_json(path)
    if value.get("schema_version") != INSTALL_SCHEMA:
        raise ProductError("The Builder OS installation pointer uses an unsupported schema")
    root = Path(str(value.get("runtime_root", ""))).resolve()
    if not is_within(root, home / "versions"):
        raise ProductError("The Builder OS installation pointer escapes its version directory")
    return value


def claude_skill_target() -> Path:
    return Path.home() / ".claude" / "skills" / "builderos"


def load_claude_skill_installer(runtime: Path):
    path = runtime / "scripts" / "install-claude-reasoner-skill.py"
    if not path.is_file():
        raise ProductError("This Builder OS runtime has no optional Claude reasoner adapter")
    try:
        return types.SimpleNamespace(**runpy.run_path(str(path), run_name="builder_os_optional_claude_installer"))
    except (OSError, RuntimeError) as exc:
        raise ProductError(f"The optional Claude reasoner installer could not be loaded: {exc}") from exc


def configure_claude_reasoner(
    home: Path, target: Path, action: str, require_cli: bool = True
) -> None:
    current = current_install(home)
    if current is None:
        raise ProductError("Builder OS is not installed yet")
    runtime = Path(current["runtime_root"])
    problems = runtime_problems(runtime)
    if problems:
        raise ProductError("The active runtime is damaged: " + "; ".join(problems))
    installer = load_claude_skill_installer(runtime)
    try:
        if action == "install":
            installer.install(target, require_cli=require_cli)
        elif action == "uninstall":
            installer.uninstall(target)
        else:
            raise ProductError(f"Unknown Claude reasoner action: {action}")
    except installer.InstallError as exc:
        raise ProductError(str(exc)) from exc


def validate_release_manifest(value: dict) -> list[str]:
    problems = []
    if value.get("schema_version") != RELEASE_SCHEMA:
        problems.append("unsupported release-manifest schema")
    if value.get("product") != PRODUCT:
        problems.append("release manifest names a different product")
    release_version = str(value.get("version", ""))
    try:
        version_key(release_version)
    except ProductError as exc:
        problems.append(str(exc))
    files = value.get("files")
    if not isinstance(files, dict) or not files:
        problems.append("release manifest has no files")
    elif any(
        not isinstance(name, str)
        or not isinstance(digest, str)
        or not re.fullmatch(r"[0-9a-f]{64}", digest)
        for name, digest in files.items()
    ):
        problems.append("release manifest has malformed file hashes")
    else:
        required = set(BASE_REQUIRED_RUNTIME_FILES)
        try:
            if version_key(release_version) >= version_key("1.5.1"):
                required.update(V151_REQUIRED_RUNTIME_FILES)
        except ProductError:
            pass
        missing = sorted(required - set(files))
        if missing:
            problems.append("release manifest omits required runtime files: " + ", ".join(missing))
    compatibility = value.get("project_state_schema")
    if not isinstance(compatibility, dict) or not all(
        isinstance(compatibility.get(key), int) for key in ("min", "max")
    ):
        problems.append("release manifest has no project-state compatibility range")
    return problems


def runtime_problems(runtime: Path) -> list[str]:
    manifest_path = runtime / RUNTIME_MANIFEST
    if not manifest_path.is_file():
        return [f"runtime manifest is missing: {manifest_path}"]
    try:
        manifest = read_json(manifest_path)
    except ProductError as exc:
        return [str(exc)]
    problems = validate_release_manifest(manifest)
    files = manifest.get("files", {}) if isinstance(manifest.get("files"), dict) else {}
    expected = set(files) | {RUNTIME_MANIFEST}
    for relative, expected_digest in files.items():
        pure = PurePosixPath(relative)
        if pure.is_absolute() or ".." in pure.parts or "\\" in relative:
            problems.append(f"unsafe runtime path in manifest: {relative}")
            continue
        path = runtime.joinpath(*pure.parts)
        if not path.is_file():
            problems.append(f"runtime file is missing: {relative}")
        elif sha256(path) != expected_digest:
            problems.append(f"runtime file changed: {relative}")
    actual = {
        path.relative_to(runtime).as_posix()
        for path in runtime.rglob("*")
        if path.is_file()
    }
    extras = sorted(actual - expected)
    if extras:
        problems.append("runtime contains files outside its manifest: " + ", ".join(extras))
    version_path = runtime / "VERSION"
    if version_path.is_file() and version_path.read_text(encoding="utf-8").strip() != manifest.get("version"):
        problems.append("runtime VERSION does not match its manifest")
    return problems


def safe_extract(bundle: Path, destination: Path) -> None:
    with zipfile.ZipFile(bundle) as archive:
        for info in archive.infolist():
            name = info.filename
            pure = PurePosixPath(name)
            mode = info.external_attr >> 16
            if (
                not name
                or pure.is_absolute()
                or ".." in pure.parts
                or "\\" in name
                or stat.S_ISLNK(mode)
            ):
                raise ProductError(f"Release bundle contains an unsafe path: {name}")
            target = destination.joinpath(*pure.parts)
            if not is_within(target, destination):
                raise ProductError(f"Release bundle path escapes staging: {name}")
        archive.extractall(destination)


def bundle_manifest(bundle: Path) -> dict:
    try:
        with zipfile.ZipFile(bundle) as archive:
            if archive.namelist().count(RUNTIME_MANIFEST) != 1:
                raise ProductError("Release bundle must contain exactly one runtime manifest")
            value = json.loads(archive.read(RUNTIME_MANIFEST).decode("utf-8"))
    except (zipfile.BadZipFile, KeyError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ProductError(f"Release bundle is malformed: {exc}") from exc
    problems = validate_release_manifest(value)
    if problems:
        raise ProductError("Release bundle manifest is invalid: " + "; ".join(problems))
    return value


def skill_source(runtime: Path) -> Path:
    return runtime / SKILL_RELATIVE


def skill_expected(runtime: Path) -> dict[str, str]:
    source = skill_source(runtime)
    if not (source / "SKILL.md").is_file():
        raise ProductError("The runtime does not contain the managed $builderos skill")
    return {
        path.relative_to(source).as_posix(): sha256(path)
        for path in sorted(source.rglob("*"))
        if path.is_file() and path.name != "installation.example.json"
    }


def skill_problems(runtime: Path, target: Path) -> list[str]:
    problems = []
    marker_path = target / SKILL_MARKER
    installation_path = target / SKILL_INSTALLATION
    if not marker_path.is_file():
        return ["managed $builderos skill marker is missing"]
    try:
        marker = read_json(marker_path)
        installation = read_json(installation_path)
    except ProductError as exc:
        return [str(exc)]
    if marker.get("owner") != PRODUCT:
        problems.append("$builderos skill is not owned by Builder OS")
    expected = skill_expected(runtime)
    if marker.get("managed_files") != expected:
        problems.append("$builderos skill metadata does not match the active runtime")
    if Path(str(installation.get("builder_os_root", ""))).resolve() != runtime.resolve():
        problems.append("$builderos skill points to a different runtime")
    if installation.get("version") != read_json(runtime / RUNTIME_MANIFEST).get("version"):
        problems.append("$builderos skill version does not match the active runtime")
    allowed = set(expected) | {SKILL_MARKER, SKILL_INSTALLATION.as_posix()}
    actual = {
        path.relative_to(target).as_posix()
        for path in target.rglob("*")
        if path.is_file()
    }
    extras = sorted(actual - allowed)
    if extras:
        problems.append("$builderos skill contains unmanaged files: " + ", ".join(extras))
    for relative, digest_value in expected.items():
        path = target.joinpath(*PurePosixPath(relative).parts)
        if not path.is_file():
            problems.append(f"$builderos skill file is missing: {relative}")
        elif sha256(path) != digest_value:
            problems.append(f"$builderos skill file changed: {relative}")
    return problems


def _existing_skill_extras(runtime: Path, target: Path) -> list[str]:
    if not target.exists():
        return []
    marker_path = target / SKILL_MARKER
    if not marker_path.is_file():
        raise ProductError(f"Refusing to overwrite an unmanaged skill: {target}")
    marker = read_json(marker_path)
    if marker.get("owner") != PRODUCT:
        raise ProductError(f"Refusing to overwrite a skill owned by another tool: {target}")
    managed = marker.get("managed_files")
    if isinstance(managed, dict):
        allowed = set(managed) | {SKILL_MARKER, SKILL_INSTALLATION.as_posix()}
    else:
        # V1.3's legacy managed marker did not record a file list. Compare it
        # with the current canonical skill and preserve any unknown file.
        allowed = set(skill_expected(runtime)) | {SKILL_MARKER, SKILL_INSTALLATION.as_posix()}
    actual = {
        path.relative_to(target).as_posix()
        for path in target.rglob("*")
        if path.is_file()
    }
    return sorted(actual - allowed)


def prepare_skill(runtime: Path, target: Path, install_home: Path) -> Path:
    extras = _existing_skill_extras(runtime, target)
    if extras:
        raise ProductError(
            "The existing managed skill contains user files; move them before repair: "
            + ", ".join(extras)
        )
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.parent / f".{target.name}.builderos-{uuid.uuid4().hex}"
    shutil.copytree(skill_source(runtime), temporary)
    example = temporary / "references" / "installation.example.json"
    if example.exists():
        example.unlink()
    manifest = read_json(runtime / RUNTIME_MANIFEST)
    atomic_json(
        temporary / SKILL_INSTALLATION,
        {
            "schema_version": INSTALL_SCHEMA,
            "builder_os_root": str(runtime.resolve()),
            "install_home": str(install_home.resolve()),
            "version": manifest["version"],
        },
    )
    expected = {
        path.relative_to(temporary).as_posix(): sha256(path)
        for path in sorted(temporary.rglob("*"))
        if path.is_file() and path.relative_to(temporary).as_posix() != SKILL_INSTALLATION.as_posix()
    }
    atomic_json(
        temporary / SKILL_MARKER,
        {
            "schema_version": INSTALL_SCHEMA,
            "owner": PRODUCT,
            "runtime_root": str(runtime.resolve()),
            "version": manifest["version"],
            "managed_files": expected,
        },
    )
    problems = skill_problems(runtime, temporary)
    if problems:
        shutil.rmtree(temporary, ignore_errors=True)
        raise ProductError("Prepared skill failed verification: " + "; ".join(problems))
    return temporary


def activate_skill(temporary: Path, target: Path) -> Path | None:
    backup = None
    if target.exists():
        backup = target.parent / f".{target.name}.backup-{uuid.uuid4().hex}"
        target.replace(backup)
    try:
        temporary.replace(target)
    except Exception:
        if backup is not None and backup.exists() and not target.exists():
            backup.replace(target)
        raise
    return backup


def finish_skill_swap(target: Path, backup: Path | None, success: bool) -> None:
    if success:
        if backup is not None and backup.exists():
            shutil.rmtree(backup)
        return
    if target.exists():
        shutil.rmtree(target)
    if backup is not None and backup.exists():
        backup.replace(target)


def _install_extracted(
    extracted: Path,
    home: Path,
    target: Path,
    expected_bundle_sha: str | None = None,
    failure_at: str | None = None,
) -> dict:
    problems = runtime_problems(extracted)
    if problems:
        raise ProductError("Release verification failed: " + "; ".join(problems))
    manifest = read_json(extracted / RUNTIME_MANIFEST)
    version = manifest["version"]
    minimum = str(manifest.get("minimum_bootstrap_version", "1.4.0"))
    if version_key(package_version()) < version_key(minimum):
        raise ProductError(
            f"This release needs Builder OS launcher {minimum} or newer; update the launcher first"
        )
    versions = home / "versions"
    versions.mkdir(parents=True, exist_ok=True)
    destination = versions / version
    if destination.exists():
        existing_problems = runtime_problems(destination)
        if existing_problems:
            quarantine = versions / f"{version}.corrupt-{uuid.uuid4().hex}"
            destination.replace(quarantine)
            extracted.replace(destination)
        else:
            shutil.rmtree(extracted)
    else:
        extracted.replace(destination)
    if failure_at == "after-runtime":
        raise ProductError("simulated interrupted installation")
    previous = current_install(home)
    prepared = prepare_skill(destination, target, home)
    backup = activate_skill(prepared, target)
    try:
        if failure_at == "after-skill":
            raise ProductError("simulated pointer-write failure")
        pointer = {
            "schema_version": INSTALL_SCHEMA,
            "version": version,
            "runtime_root": str(destination.resolve()),
            "previous_version": previous.get("version") if previous else None,
            "installed_at": now(),
            "bundle_sha256": expected_bundle_sha,
        }
        atomic_json(home / CURRENT_NAME, pointer)
        finish_skill_swap(target, backup, True)
    except Exception:
        finish_skill_swap(target, backup, False)
        raise
    append_history(
        home,
        "activate",
        {
            "version": version,
            "previous_version": previous.get("version") if previous else None,
            "runtime_root": str(destination.resolve()),
        },
    )
    return pointer


def install_bundle(
    bundle: Path,
    home: Path,
    target: Path,
    expected_sha: str | None = None,
    failure_at: str | None = None,
) -> dict:
    bundle = bundle.resolve()
    if not bundle.is_file():
        raise ProductError(f"Release bundle is missing: {bundle}")
    actual_sha = sha256(bundle)
    if expected_sha and actual_sha != expected_sha:
        raise ProductError("Downloaded release checksum does not match its release manifest")
    staging_parent = home / ".staging"
    staging_parent.mkdir(parents=True, exist_ok=True)
    staging = staging_parent / uuid.uuid4().hex
    staging.mkdir()
    try:
        bundle_manifest(bundle)
        safe_extract(bundle, staging)
        return _install_extracted(staging, home, target, actual_sha, failure_at)
    finally:
        if staging.exists():
            shutil.rmtree(staging, ignore_errors=True)


def _open_bytes(source: str) -> bytes:
    parsed = urllib.parse.urlparse(source)
    if parsed.scheme in ("http", "https"):
        if parsed.scheme != "https":
            raise ProductError("Builder OS downloads require HTTPS")
        request = urllib.request.Request(source, headers={"User-Agent": "Builder-OS-installer"})
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return response.read()
        except OSError as exc:
            raise ProductError(f"Could not download {source}: {exc}") from exc
    path = Path(source).expanduser().resolve()
    try:
        return path.read_bytes()
    except OSError as exc:
        raise ProductError(f"Could not read release source {path}: {exc}") from exc


def release_descriptor(source: str) -> tuple[dict, str]:
    try:
        value = json.loads(_open_bytes(source).decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ProductError(f"Release description is malformed: {exc}") from exc
    if not isinstance(value, dict):
        raise ProductError("Release description must be a JSON object")
    required = ("version", "artifact", "sha256")
    if any(not str(value.get(key, "")).strip() for key in required):
        raise ProductError("Release description is missing version, artifact, or checksum")
    version_key(str(value["version"]))
    if not re.fullmatch(r"[0-9a-f]{64}", str(value["sha256"])):
        raise ProductError("Release description checksum is malformed")
    parsed = urllib.parse.urlparse(source)
    if parsed.scheme in ("http", "https"):
        artifact_source = urllib.parse.urljoin(source, str(value["artifact"]))
    else:
        artifact_source = str((Path(source).expanduser().resolve().parent / str(value["artifact"])).resolve())
    return value, artifact_source


def download_release(descriptor_source: str, home: Path) -> tuple[Path, dict]:
    descriptor, artifact_source = release_descriptor(descriptor_source)
    downloads = home / ".downloads"
    downloads.mkdir(parents=True, exist_ok=True)
    target = downloads / f"{descriptor['version']}-{uuid.uuid4().hex}.zip"
    data = _open_bytes(artifact_source)
    target.write_bytes(data)
    if sha256(target) != descriptor["sha256"]:
        target.unlink(missing_ok=True)
        raise ProductError("Downloaded release checksum does not match")
    return target, descriptor


def install_from_descriptor(source: str, home: Path, target: Path) -> tuple[dict, str]:
    bundle, descriptor = download_release(source, home)
    try:
        pointer = install_bundle(bundle, home, target, descriptor["sha256"])
    finally:
        bundle.unlink(missing_ok=True)
    return pointer, str(descriptor["version"])


@contextlib.contextmanager
def seed_runtime_bundle():
    resource = importlib.resources.files("builderos").joinpath("seed-runtime.zip")
    if not resource.is_file():
        yield None
        return
    with importlib.resources.as_file(resource) as bundle:
        yield bundle


def install_seed_runtime(home: Path, target: Path) -> dict | None:
    """Install the canonical runtime generated into a release wheel, if present."""
    with seed_runtime_bundle() as bundle:
        return install_bundle(bundle, home, target) if bundle is not None else None


def repair_damaged_runtime(current: dict, home: Path, target: Path, descriptor: str) -> dict:
    """Repair the active version without silently replacing it with an older seed."""
    with seed_runtime_bundle() as seed:
        if seed is not None and bundle_manifest(seed)["version"] == current["version"]:
            return install_bundle(seed, home, target)
    available, _ = release_descriptor(descriptor)
    if available["version"] != current["version"]:
        raise ProductError(
            f"Repair source provides {available['version']}, but damaged active version is "
            f"{current['version']}; use update or rollback explicitly"
        )
    pointer, _ = install_from_descriptor(descriptor, home, target)
    return pointer


def repair_current(home: Path, target: Path) -> dict:
    current = current_install(home)
    if current is None:
        raise ProductError("Builder OS is not installed yet")
    runtime = Path(current["runtime_root"])
    problems = runtime_problems(runtime)
    if problems:
        raise ProductError("The active runtime is damaged: " + "; ".join(problems))
    prepared = prepare_skill(runtime, target, home)
    backup = activate_skill(prepared, target)
    finish_skill_swap(target, backup, True)
    append_history(home, "repair", {"version": current["version"]})
    return current


def rollback(home: Path, target: Path, requested: str | None = None) -> dict:
    current = current_install(home)
    if current is None:
        raise ProductError("Builder OS is not installed yet")
    version = requested or current.get("previous_version")
    if not version:
        raise ProductError("No previous Builder OS version is available")
    version_key(str(version))
    if version == current.get("version"):
        raise ProductError("The requested rollback version is already active")
    runtime = home / "versions" / str(version)
    problems = runtime_problems(runtime)
    if problems:
        raise ProductError("Rollback target is not healthy: " + "; ".join(problems))
    prepared = prepare_skill(runtime, target, home)
    backup = activate_skill(prepared, target)
    try:
        pointer = {
            "schema_version": INSTALL_SCHEMA,
            "version": str(version),
            "runtime_root": str(runtime.resolve()),
            "previous_version": current["version"],
            "installed_at": now(),
            "bundle_sha256": None,
        }
        atomic_json(home / CURRENT_NAME, pointer)
        finish_skill_swap(target, backup, True)
    except Exception:
        finish_skill_swap(target, backup, False)
        raise
    append_history(home, "rollback", {"from": current["version"], "to": str(version)})
    return pointer


def codex_state() -> tuple[str, str]:
    executable = shutil.which("codex")
    if executable:
        return "detected", executable
    return "not-detected", "Codex was not found on PATH; the desktop app may still be installed"


def project_compatibility(project: Path, manifest: dict) -> tuple[str, str]:
    project = project.resolve()
    if not project.exists():
        return "problem", "Project path does not exist"
    run_files = sorted(project.parent.glob("*/builderos-run.json"))
    matching = []
    for path in run_files:
        try:
            state = read_json(path)
            if Path(str(state.get("project", ""))).resolve() == project:
                matching.append((path, state))
        except ProductError:
            continue
    if not matching:
        return "ok", "No existing Builder OS run; the project can be started or safely adopted"
    if len(matching) > 1:
        return "problem", "More than one Builder OS history names this project"
    schema = matching[0][1].get("schema_version")
    compatibility = manifest["project_state_schema"]
    if not isinstance(schema, int) or not compatibility["min"] <= schema <= compatibility["max"]:
        return "problem", f"Project state schema {schema!r} is not supported by this runtime"
    return "ok", f"Existing Builder OS project state is compatible (schema {schema})"


def doctor(home: Path, target: Path, project: Path | None = None) -> tuple[int, list[tuple[str, str, str]]]:
    checks: list[tuple[str, str, str]] = []
    if sys.version_info >= MIN_PYTHON:
        checks.append(("ok", "Python", f"{sys.version_info.major}.{sys.version_info.minor}"))
    else:
        checks.append(("problem", "Python", f"{MIN_PYTHON[0]}.{MIN_PYTHON[1]} or newer is required"))
    current = None
    try:
        current = current_install(home)
    except ProductError as exc:
        checks.append(("problem", "Installation", str(exc)))
    if current is None and not any(label == "Installation" for _, label, _ in checks):
        checks.append(("problem", "Installation", "Builder OS is not installed"))
    manifest = None
    if current is not None:
        runtime = Path(current["runtime_root"])
        problems = runtime_problems(runtime)
        if problems:
            checks.append(("problem", "Runtime", "; ".join(problems)))
        else:
            manifest = read_json(runtime / RUNTIME_MANIFEST)
            checks.append(("ok", "Runtime", f"Builder OS {manifest['version']}"))
        skill_issues = skill_problems(runtime, target) if not problems else ["runtime must be repaired first"]
        checks.append(("problem" if skill_issues else "ok", "Codex skill", "; ".join(skill_issues) or "managed and current"))
    codex_status, codex_detail = codex_state()
    checks.append(("ok" if codex_status == "detected" else "warning", "Codex", codex_detail))
    if project is not None and manifest is not None:
        status_value, detail = project_compatibility(project, manifest)
        checks.append((status_value, "Project", detail))
    elif project is None:
        checks.append(("ok", "Project", "No project requested; installed product only"))
    return (2 if any(status_value == "problem" for status_value, _, _ in checks) else 0), checks


def uninstall(home: Path, target: Path) -> list[str]:
    current = current_install(home)
    if current is None:
        raise ProductError("Builder OS is not installed")
    if target.exists():
        marker = target / SKILL_MARKER
        if not marker.is_file() or read_json(marker).get("owner") != PRODUCT:
            raise ProductError(f"Refusing to remove an unmanaged skill: {target}")
        shutil.rmtree(target)
    resolved_home = home.resolve()
    if resolved_home in (Path.home().resolve(), Path(resolved_home.anchor)) or len(resolved_home.parts) < 3:
        raise ProductError(f"Refusing to remove unsafe installation path: {resolved_home}")
    tombstone = resolved_home.parent / f".{resolved_home.name}.uninstall-{uuid.uuid4().hex}"
    resolved_home.replace(tombstone)
    shutil.rmtree(tombstone)
    return [str(target), str(resolved_home)]


def print_doctor(checks: list[tuple[str, str, str]]) -> None:
    print("Builder OS health\n")
    symbols = {"ok": "[OK]", "warning": "[!]", "problem": "[X]"}
    for status_value, label, detail in checks:
        print(f"{symbols[status_value]} {label}: {detail}")
    if any(status_value == "problem" for status_value, _, _ in checks):
        print("\nAction needed: repair the failed item before starting a project.")
    elif any(status_value == "warning" for status_value, _, _ in checks):
        print("\nBuilder OS is healthy. One optional environment check needs attention.")
    else:
        print("\nBuilder OS is healthy. No action needed right now.")


def first_run_message(pointer: dict, codex_available: bool) -> None:
    print(f"Builder OS {pointer['version']} is installed.\n")
    print(
        "Builder OS can take a project from an idea through research, design, "
        "implementation and review. It handles the workflow and asks only when "
        "your judgement or permission is needed."
    )
    print("\nYou remain in control of creative direction, dependencies, shipping and publishing.")
    if codex_available:
        print("\nNext: open Codex in your project, type $builderos, and describe what you want to make.")
    else:
        print("\nNext: install or open Codex, then type $builderos in your project.")


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(prog="builderos", description="Install and maintain Builder OS.")
    value.add_argument("--version", action="store_true", help="show the active Builder OS version")
    value.add_argument("--data-home", help=argparse.SUPPRESS)
    value.add_argument("--skill-home", help=argparse.SUPPRESS)
    value.add_argument("--claude-skill-home", help=argparse.SUPPRESS)
    sub = value.add_subparsers(dest="command")
    install = sub.add_parser("install", help="install or repair Builder OS for this user")
    install.add_argument("--bundle", help="use a local verified runtime bundle")
    install.add_argument("--manifest", default=DEFAULT_RELEASE_MANIFEST, help=argparse.SUPPRESS)
    update = sub.add_parser("update", help="install the latest verified Builder OS release")
    update.add_argument("--manifest", default=DEFAULT_RELEASE_MANIFEST, help=argparse.SUPPRESS)
    rollback_parser = sub.add_parser("rollback", help="return to the previous installed version")
    rollback_parser.add_argument("--to", dest="rollback_to", help="activate a specific installed version")
    doctor_parser = sub.add_parser("doctor", help="check installation health in plain language")
    doctor_parser.add_argument("--project", help="also check one project's compatibility")
    uninstall_parser = sub.add_parser("uninstall", help="remove Builder OS while preserving projects")
    uninstall_parser.add_argument("--yes", action="store_true", help="confirm removal without a prompt")
    sub.add_parser("enable-claude", help="enable the optional Claude reasoner entry")
    sub.add_parser("disable-claude", help="remove the optional Claude reasoner entry")
    sub.add_parser("paths", help=argparse.SUPPRESS)
    return value


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    home = Path(args.data_home).expanduser().resolve() if args.data_home else user_data_home()
    target = Path(args.skill_home).expanduser().resolve() if args.skill_home else skill_target()
    claude_target = (
        Path(args.claude_skill_home).expanduser().resolve()
        if args.claude_skill_home else claude_skill_target().resolve()
    )
    if args.version:
        current = current_install(home)
        print(f"Builder OS {current['version'] if current else package_version()}")
        return 0
    try:
        if args.command == "install":
            existing = current_install(home)
            if args.bundle:
                pointer = install_bundle(Path(args.bundle), home, target)
            elif existing is not None:
                runtime = Path(existing["runtime_root"])
                if runtime_problems(runtime):
                    pointer = repair_damaged_runtime(existing, home, target, args.manifest)
                else:
                    pointer = repair_current(home, target)
            else:
                pointer = install_seed_runtime(home, target)
                if pointer is None:
                    pointer, _ = install_from_descriptor(args.manifest, home, target)
            first_run_message(pointer, codex_state()[0] == "detected")
            return 0
        if args.command == "update":
            current = current_install(home)
            if current is None:
                raise ProductError("Builder OS is not installed; run builderos install first")
            descriptor, _ = release_descriptor(args.manifest)
            if version_key(str(descriptor["version"])) < version_key(str(current["version"])):
                raise ProductError("The available release is older than the active installation")
            if descriptor["version"] == current["version"]:
                repair_current(home, target)
                print(f"Builder OS {current['version']} is current and verified.")
                print("Next: use $builderos in your project.")
                return 0
            pointer, available = install_from_descriptor(args.manifest, home, target)
            print(f"Updated Builder OS {current['version']} → {available}.")
            print(f"Rollback available: builderos rollback returns to {current['version']}.")
            print("Next: use $builderos in your project.")
            return 0
        if args.command == "rollback":
            before = current_install(home)
            pointer = rollback(home, target, args.rollback_to)
            print(f"Rolled back Builder OS {before['version']} → {pointer['version']}.")
            print("Projects and project evidence were not changed.")
            print("Next: run builderos doctor.")
            return 0
        if args.command == "doctor":
            code, checks = doctor(home, target, Path(args.project) if args.project else None)
            print_doctor(checks)
            return code
        if args.command == "enable-claude":
            configure_claude_reasoner(home, claude_target, "install")
            print("Optional Claude reasoner entry enabled.")
            print("Codex remains the default; projects and gates were not changed.")
            print("Next: open Claude Code in a project and invoke $builderos.")
            return 0
        if args.command == "disable-claude":
            configure_claude_reasoner(home, claude_target, "uninstall", require_cli=False)
            print("Optional Claude reasoner entry removed.")
            print("Builder OS, Codex support, projects, and evidence were not changed.")
            print("Next: continue with Codex, or run builderos rollback if restoring V1.5.")
            return 0
        if args.command == "uninstall":
            if not args.yes:
                answer = input("Remove Builder OS runtime and its managed Codex skill? Projects remain untouched. [y/N] ")
                if answer.strip().lower() not in ("y", "yes"):
                    print("No changes made.")
                    return 0
            removed = uninstall(home, target)
            print("Builder OS runtime and managed Codex skill were removed.")
            print("Your projects, project documents, evidence and source files remain untouched.")
            print("The small Python launcher remains managed by pip/pipx and may be removed there if desired.")
            print("Removed: " + ", ".join(removed))
            return 0
        if args.command == "paths":
            print(json.dumps({"data_home": str(home), "skill": str(target)}, indent=2))
            return 0
        parser().print_help()
        return 0
    except ProductError as exc:
        print(f"Builder OS stopped safely: {exc}")
        print("No project files were changed.")
        return 2
    except (PermissionError, OSError) as exc:
        print(f"Builder OS stopped safely: a permission or filesystem error occurred: {exc}")
        print("The active installation and project files were not intentionally changed.")
        return 2
