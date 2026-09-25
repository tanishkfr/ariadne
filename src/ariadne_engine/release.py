"""AR-205 release consistency: one place where the release gates read the facts.

The functions here answer three questions without building or installing
anything:

* :func:`version_problems` -- do the repository's version surfaces agree?
* :func:`public_surface_problems` -- is the public API table complete and
  accidental-export-free?
* :func:`artifact_problems` -- do locally built artifacts match their manifest,
  their checksums and the version surfaces?

They return problem lists (empty means consistent) so a caller decides whether a
finding is fatal, and they never write.
"""

from __future__ import annotations

import hashlib
import json
import re
import zipfile
from pathlib import Path

from . import contracts, efficiency, integration, migration, package_version, public

VERSION_RE = re.compile(r"\d+\.\d+\.\d+(?:\.\d+)?(?:(?:a|b|rc)\d+)?")
INSTALL_DOCS = ("README.md", "QUICKSTART.md", "INSTALL.md", "GETTING-STARTED.md")
PRIVATE_PATH_TOKENS = (
    "validation/", "operations/", "tests/", "private/", ".env", "client-assets/",
)


def version(root: Path) -> str:
    return (Path(root) / "VERSION").read_text(encoding="utf-8").strip()


def version_problems(root: Path) -> list[str]:
    root = Path(root)
    problems: list[str] = []
    canonical = version(root)
    if not VERSION_RE.fullmatch(canonical):
        problems.append(f"VERSION is not a supported release version: {canonical!r}")
        return problems
    pyproject = (root / "pyproject.toml").read_text(encoding="utf-8")
    if re.search(r"(?m)^version\s*=", pyproject):
        problems.append("pyproject.toml duplicates the canonical VERSION value")
    if 'dynamic = ["version"]' not in pyproject:
        problems.append("pyproject.toml does not take its version from VERSION")
    release_notes = (root / "RELEASE-NOTES.md").read_text(encoding="utf-8")
    if not re.search(rf"(?m)^# Ariadne {re.escape(canonical)}\s*$", release_notes):
        problems.append("RELEASE-NOTES.md does not start with the canonical version heading")
    wheel_url = (
        "https://github.com/tanishkfr/ariadne/releases/download/"
        f"v{canonical}/ariadne-{canonical}-py3-none-any.whl"
    )
    for name in INSTALL_DOCS:
        text = (root / name).read_text(encoding="utf-8")
        if wheel_url not in text:
            problems.append(f"{name} does not carry the canonical release wheel URL")
    example_path = root / ".agents" / "skills" / "ariadne" / "references" / "installation.example.json"
    try:
        example = json.loads(example_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        problems.append(f"installation example is unreadable: {exc}")
    else:
        if example.get("version") != canonical:
            problems.append("installation example version does not match VERSION")
        if not str(example.get("ariadne_root", "")).endswith(f"versions\\{canonical}") and not str(
            example.get("ariadne_root", "")
        ).endswith(f"versions/{canonical}"):
            problems.append("installation example root does not match VERSION")
    try:
        source_version = package_version()
        tree_version = (root / "VERSION").read_text(encoding="utf-8").strip()
        if source_version != tree_version:
            problems.append(
                f"the engine reports version {source_version} while the tree VERSION is {tree_version}"
            )
    except OSError as exc:
        problems.append(f"the engine version could not be read: {exc}")
    if integration.PROTOCOL_VERSION != migration.REPORT_SCHEMA:
        problems.append("the integration protocol version and the migration report schema disagree")
    if not (
        integration.MIN_SUPPORTED_VERSION
        <= integration.PROTOCOL_VERSION
        <= integration.MAX_SUPPORTED_VERSION
    ):
        problems.append("the advertised protocol version is outside its own supported range")
    if integration.describe()["engine"]["contract"] != contracts.ENGINE_CONTRACT:
        problems.append("the integration description disagrees with the engine contract")
    return problems


def public_surface_problems() -> list[str]:
    problems: list[str] = []
    from . import api

    exported = set(api.__all__)
    classified = set(public.PUBLIC_SURFACE)
    unclassified = sorted(exported - classified)
    if unclassified:
        problems.append("exported operations have no stability class: " + ", ".join(unclassified))
    own_surface = set(public.__all__)
    unknown = sorted(classified - exported - own_surface)
    if unknown:
        problems.append("stability classes name operations that are not exported: " + ", ".join(unknown))
    duplicates = sorted(
        name
        for name in classified
        if [label for label in (public.STABLE_V2, public.PROVISIONAL, public.INTERNAL) if name in label][1:]
    )
    if duplicates:
        problems.append("operations carry more than one stability class: " + ", ".join(duplicates))
    if "connect" not in public.PUBLIC_SURFACE or public.PUBLIC_SURFACE.get("connect") != "STABLE_V2":
        problems.append("the embedding entry point is not a stable v2 operation")
    return problems


def experimental_defaults_problems() -> list[str]:
    problems: list[str] = []
    if not efficiency.BEHAVIOUR_SENSITIVE:
        problems.append("the behavior-sensitive flag list is empty; the release must classify the AR-204 experiments")
    for name in efficiency.BEHAVIOUR_SENSITIVE:
        if name in efficiency.SAFE_DEFAULTS:
            problems.append(f"behavior-sensitive flag {name} is declared a safe default")
        conservative = efficiency.SETTING_VALUES[name][0]
        if efficiency.DEFAULT_FLAGS.get(name) != conservative:
            problems.append(
                f"behavior-sensitive flag {name} defaults to {efficiency.DEFAULT_FLAGS.get(name)!r} "
                f"instead of {conservative!r}"
            )
    if efficiency.DEFAULT_FLAGS.get("output_externalization") != "threshold":
        problems.append("the evidence-preserving externalization default changed")
    return problems


def _sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def artifact_problems(directory: Path) -> list[str]:
    """Verify a locally built release directory against its own manifest and checksums."""
    directory = Path(directory)
    manifest_path = directory / "ariadne-release.json"
    if not manifest_path.is_file():
        return [f"no release descriptor at {manifest_path}"]
    problems: list[str] = []
    try:
        descriptor = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return [f"release descriptor is malformed: {exc}"]
    canonical = version(_repo_root())
    if descriptor.get("version") != canonical:
        problems.append("release descriptor version does not match VERSION")
    if descriptor.get("product") != "Ariadne":
        problems.append("release descriptor names a different product")
    artifact = directory / f"ariadne-runtime-{descriptor.get('version')}.zip"
    launcher = directory / f"ariadne-{descriptor.get('version')}-py3-none-any.whl"
    notes = directory / f"ariadne-{descriptor.get('version')}-release-notes.md"
    for label, path, expected in (
        ("runtime artifact", artifact, descriptor.get("sha256")),
        ("launcher", launcher, (descriptor.get("launcher") or {}).get("sha256")),
        ("release notes", notes, (descriptor.get("release_notes") or {}).get("sha256")),
    ):
        if not path.is_file():
            problems.append(f"the {label} is missing: {path.name}")
        elif _sha256(path) != expected:
            problems.append(f"the {label} digest does not match the release descriptor")
    checksums = directory / "SHA256SUMS.txt"
    if not checksums.is_file():
        problems.append("SHA256SUMS.txt is missing")
    else:
        rows = {}
        for line in checksums.read_text(encoding="utf-8").splitlines():
            if "  " in line:
                digest, name = line.split("  ", 1)
                rows[name] = digest
        for path in (artifact, launcher, manifest_path, notes):
            if path.is_file() and rows.get(path.name) != _sha256(path):
                problems.append(f"SHA256SUMS.txt does not authenticate {path.name}")
    if artifact.is_file():
        try:
            with zipfile.ZipFile(artifact) as archive:
                names = set(archive.namelist())
                embedded = json.loads(archive.read("RELEASE-MANIFEST.json"))
                content_problems = []
                for name, digest in (embedded.get("files") or {}).items():
                    if name not in names:
                        content_problems.append(f"the manifest names a missing file: {name}")
                    elif hashlib.sha256(archive.read(name)).hexdigest() != digest:
                        content_problems.append(f"the manifest digest does not match the artifact content: {name}")
        except (KeyError, json.JSONDecodeError, zipfile.BadZipFile) as exc:
            problems.append(f"the runtime artifact is unreadable: {exc}")
        else:
            private = sorted(name for name in names if name.startswith(PRIVATE_PATH_TOKENS))
            if private:
                problems.append("the runtime artifact includes private paths: " + ", ".join(private))
            if embedded.get("version") != descriptor.get("version"):
                problems.append("the embedded manifest version disagrees with the descriptor")
            if embedded.get("source_commit") != descriptor.get("source_commit"):
                problems.append("the embedded manifest source commit disagrees with the descriptor")
            problems.extend(content_problems)
    if launcher.is_file():
        with zipfile.ZipFile(launcher) as wheel:
            wheel_names = set(wheel.namelist())
        if "ariadne/seed-runtime.zip" not in wheel_names:
            problems.append("the launcher wheel does not carry the seed runtime")
        if not any(name.endswith("licenses/LICENSE") for name in wheel_names):
            problems.append("the launcher wheel does not carry the approved licence")
    return problems


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]
