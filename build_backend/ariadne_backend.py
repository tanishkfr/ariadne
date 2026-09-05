"""Dependency-free PEP 517 backend for the small Ariadne launcher wheel."""

from __future__ import annotations

import base64
import hashlib
import importlib.util
import io
import json
import tarfile
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
PACKAGE_ROOT = ROOT / "src" / "ariadne"
FIXED_ZIP_TIME = (2020, 1, 1, 0, 0, 0)
NAME = "ariadne"
NORMALISED = "ariadne"


def _version() -> str:
    return (ROOT / "VERSION").read_text(encoding="utf-8").strip()


def _dist_info() -> str:
    return f"{NORMALISED}-{_version()}.dist-info"


def _metadata() -> bytes:
    value = f"""Metadata-Version: 2.4
Name: {NAME}
Version: {_version()}
Summary: Creative-production workflow runtime and managed Codex skill
Requires-Python: >=3.10
License-Expression: Apache-2.0
Classifier: Development Status :: 4 - Beta
Classifier: Environment :: Console
Classifier: Operating System :: OS Independent
Classifier: Programming Language :: Python :: 3
Classifier: Programming Language :: Python :: 3 :: Only
Classifier: Programming Language :: Python :: 3.10
Classifier: License :: OSI Approved :: Apache Software License
Project-URL: Homepage, https://github.com/tanishkfr/ariadne
Project-URL: Repository, https://github.com/tanishkfr/ariadne
Project-URL: Changelog, https://github.com/tanishkfr/ariadne/blob/main/CHANGELOG.md

Ariadne installs and maintains a user-local creative-production runtime and managed Codex skill.
"""
    return value.encode("utf-8")


def _wheel_metadata() -> bytes:
    return b"Wheel-Version: 1.0\nGenerator: ariadne-backend-1\nRoot-Is-Purelib: true\nTag: py3-none-any\n"


def _entry_points() -> bytes:
    return b"[console_scripts]\nariadne = ariadne.cli:main\n"


def _package_files() -> dict[str, bytes]:
    files = {
        path.relative_to(PACKAGE_ROOT.parent).as_posix(): path.read_bytes()
        for path in sorted(PACKAGE_ROOT.rglob("*.py"))
    }
    files["ariadne/seed-runtime.zip"] = _seed_runtime()
    return files


def _release_module():
    path = ROOT / "scripts" / "build-release.py"
    spec = importlib.util.spec_from_file_location("ariadne_release_builder", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load the canonical release builder: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _seed_runtime() -> bytes:
    """Generate the wheel's immutable first-install transport artifact."""
    release = _release_module()
    manifest = release.runtime_manifest()
    content = io.BytesIO()
    with zipfile.ZipFile(content, "w") as archive:
        for relative, path in release.runtime_sources():
            release.zip_entry(archive, relative, path.read_bytes())
        release.zip_entry(
            archive,
            "RELEASE-MANIFEST.json",
            (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode("utf-8"),
        )
    return content.getvalue()


def _hash(content: bytes) -> str:
    encoded = base64.urlsafe_b64encode(hashlib.sha256(content).digest()).rstrip(b"=")
    return "sha256=" + encoded.decode("ascii")


def _write_zip(archive: zipfile.ZipFile, name: str, content: bytes) -> None:
    info = zipfile.ZipInfo(name, FIXED_ZIP_TIME)
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = 0o100644 << 16
    archive.writestr(info, content)


def get_requires_for_build_wheel(config_settings=None):
    return []


def prepare_metadata_for_build_wheel(metadata_directory, config_settings=None):
    directory = Path(metadata_directory) / _dist_info()
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "METADATA").write_bytes(_metadata())
    (directory / "WHEEL").write_bytes(_wheel_metadata())
    (directory / "entry_points.txt").write_bytes(_entry_points())
    return directory.name


def build_wheel(wheel_directory, config_settings=None, metadata_directory=None):
    wheel_name = f"{NORMALISED}-{_version()}-py3-none-any.whl"
    destination = Path(wheel_directory)
    destination.mkdir(parents=True, exist_ok=True)
    files = _package_files()
    dist_info = _dist_info()
    files.update(
        {
            f"{dist_info}/METADATA": _metadata(),
            f"{dist_info}/WHEEL": _wheel_metadata(),
            f"{dist_info}/entry_points.txt": _entry_points(),
            f"{dist_info}/licenses/LICENSE": (ROOT / "LICENSE").read_bytes(),
        }
    )
    record_path = f"{dist_info}/RECORD"
    records = [f"{name},{_hash(content)},{len(content)}" for name, content in sorted(files.items())]
    records.append(f"{record_path},,")
    files[record_path] = ("\n".join(records) + "\n").encode("utf-8")
    with zipfile.ZipFile(destination / wheel_name, "w") as archive:
        for name, content in sorted(files.items()):
            _write_zip(archive, name, content)
    return wheel_name


def get_requires_for_build_sdist(config_settings=None):
    return []


def build_sdist(sdist_directory, config_settings=None):
    """Build a source archive for maintainer testing; releases prefer wheels."""
    name = f"{NORMALISED}-{_version()}"
    destination = Path(sdist_directory)
    destination.mkdir(parents=True, exist_ok=True)
    archive_path = destination / f"{name}.tar.gz"
    release = _release_module()
    paths = [
        ROOT / "VERSION",
        ROOT / "LICENSE",
        ROOT / "README.md",
        ROOT / "pyproject.toml",
        ROOT / "scripts" / "build-release.py",
    ]
    paths.extend(sorted(PACKAGE_ROOT.rglob("*.py")))
    paths.extend(sorted((ROOT / "build_backend").glob("*.py")))
    paths.extend(path for _, path in release.runtime_sources())
    paths = sorted(set(paths))
    with tarfile.open(archive_path, "w:gz") as archive:
        for path in paths:
            relative = path.relative_to(ROOT)
            archive.add(path, arcname=(Path(name) / relative).as_posix(), recursive=False)
    return archive_path.name
