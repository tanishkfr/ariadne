"""The runtime manifest: what the Decision Runtime is, and whether it is intact.

A bounded engine is code that answers questions on the user's machine, so the
question "which one, and is it the one we reviewed?" has to have a durable answer
that survives a restart. That is what the manifest is: a small, hashable
description of a runtime installation, resolved from disk before any engine is
loaded.

The manifest records:

* ``runtime_version`` and ``implementation_revision`` — which engine code;
* ``model`` and ``model_revision`` — which checkpoint, pinned;
* ``files`` — expected SHA-256 per relative path, when a reviewed digest exists;
* ``primitives``, ``languages``, ``context_limits`` — what it can honestly do;
* ``calibration_profiles`` — which calibration records were measured against it.

Two rules make the manifest worth something:

``observed`` beats ``requested``
    An installation may be asked for ``latest`` and be handed something else. The
    manifest reports what was actually found, and :func:`revision_matches` refuses
    to call a moving alias equal to a concrete revision. A calibration profile bound
    to one revision therefore cannot be satisfied by a different one.

A digest is a claim about a *reviewed* artifact
    :func:`verify_files` compares against digests supplied by a record the operator
    reviewed. Ariadne never mints a digest from the bytes it just downloaded and
    calls that independent verification; doing so would make the check a tautology.
    When no trusted digest exists the result is ``UNKNOWN``, never ``PASS``.

There is no signature here. Ariadne has no signing infrastructure, and inventing a
verifier without a key hierarchy would be theatre. Digests plus a pinned revision
plus an honest ``UNKNOWN`` is what 2.1 can actually stand behind.
"""

from __future__ import annotations

import hashlib
import json
import ntpath
from pathlib import Path
from typing import Any, Mapping

from ...contracts import ContractError, MOVING_ALIAS_REVISIONS

MANIFEST_SCHEMA = "ariadne-decision-runtime-manifest/1"
"""The manifest document shape."""

MANIFEST_NAME = "runtime-manifest.json"
"""The manifest file name inside a runtime installation directory."""

INTEGRITY_RESULTS = ("PASS", "FAIL", "UNKNOWN")
"""Integrity verdict.

``UNKNOWN`` means no trusted digest record was supplied. It is a real outcome, not
a pass: the runtime may still load, but nothing here can claim the bytes were
reviewed.
"""

DIGEST_CHUNK_BYTES = 1 << 20
"""Read size for byte-level digesting. Large enough to be fast, small enough to be
bounded on memory."""

DEFAULT_CONTEXT_LIMITS = {
    "max_state_chars": 16_000,
    "max_options": 32,
    "max_questions_per_batch": 32,
    "max_question_chars": 2_000,
}
"""Bounds the engine agrees to before it is asked anything.

These are engine-side limits, independent of the engine's projection contract. The
tighter of the two always applies: Ariadne's projection contract is the authority,
and these are only what the implementation will not exceed.
"""


def file_digest(path: Path) -> str:
    """SHA-256 of one file's bytes, streamed.

    Used to *describe* an artifact. Never used on its own to verify one — see
    :func:`verify_files` for why that distinction matters.
    """
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        while True:
            chunk = handle.read(DIGEST_CHUNK_BYTES)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def verify_files(root: Path, expected: Mapping[str, str] | None) -> dict:
    """Verify files under ``root`` against a reviewed digest map.

    ``expected`` must be digests from a record a human or a trusted release reviewed.
    Passing ``None`` returns ``UNKNOWN``: the artifact is undescribed, not verified.

    Path handling is deliberately hostile. Absolute paths, drive-qualified paths and
    ``..`` traversal are refused before any file is opened, so a digest map cannot be
    turned into an arbitrary-file-read oracle.
    """
    root = Path(root)
    if expected is None:
        return {
            "status": "UNKNOWN",
            "detail": "no reviewed digest record was supplied; the runtime is undescribed, not verified",
            "checked": 0,
            "mismatched": [],
            "missing": [],
        }
    mismatched: list[str] = []
    missing: list[str] = []
    checked = 0
    for raw_rel, raw_want in sorted(expected.items()):
        rel = str(raw_rel).strip().replace("\\", "/")
        if not rel or rel == ".." or rel.startswith("../") or "/../" in rel:
            raise ContractError(f"decision runtime digest map names an unsafe path: {raw_rel!r}")
        if rel.startswith("/") or Path(rel).is_absolute() or ntpath.isabs(raw_rel):
            raise ContractError(f"decision runtime digest map names an absolute path: {raw_rel!r}")
        path = root / rel
        if not path.is_file():
            missing.append(rel)
            continue
        got = file_digest(path)
        want = str(raw_want).strip().lower()
        checked += 1
        if got.lower() != want:
            mismatched.append(rel)
    if mismatched or missing:
        detail_parts = []
        if mismatched:
            detail_parts.append("digest mismatch: " + ", ".join(mismatched))
        if missing:
            detail_parts.append("missing: " + ", ".join(missing))
        return {
            "status": "FAIL",
            "detail": "; ".join(detail_parts),
            "checked": checked,
            "mismatched": mismatched,
            "missing": missing,
        }
    return {
        "status": "PASS",
        "detail": f"{checked} file(s) match the reviewed digest record",
        "checked": checked,
        "mismatched": [],
        "missing": [],
    }


def manifest_problems(manifest: Mapping[str, Any]) -> list[str]:
    """Structural validation of a runtime manifest. Unknown shapes fail closed."""
    problems: list[str] = []
    if not isinstance(manifest, Mapping):
        return ["runtime manifest is not an object"]
    if str(manifest.get("schema", "")) != MANIFEST_SCHEMA:
        problems.append(f"runtime manifest schema is unsupported: {manifest.get('schema')!r}")
    for name in ("runtime_version", "implementation", "implementation_revision"):
        if not str(manifest.get(name, "")).strip():
            problems.append(f"runtime manifest has no {name}")
    if not str(manifest.get("model", "")).strip():
        problems.append("runtime manifest names no model")
    revision = str(manifest.get("model_revision", "")).strip()
    if not revision:
        problems.append("runtime manifest names no model revision")
    elif not revision_matches(revision, revision):
        problems.append(f"runtime manifest model revision is a moving alias: {revision!r}")
    files = manifest.get("files")
    if files is not None and not isinstance(files, Mapping):
        problems.append("runtime manifest files are not an object")
    primitives = manifest.get("primitives")
    if not isinstance(primitives, (list, tuple)):
        problems.append("runtime manifest names no primitives")
    return list(dict.fromkeys(problems))


def revision_matches(expected: str, observed: str) -> bool:
    """Whether a recorded revision is satisfied by what the runtime actually loaded.

    Two moving aliases never match each other, and neither matches a concrete
    revision. A moving alias therefore cannot satisfy a calibration profile bound to
    a concrete revision — which is the point: a model that moves under a recorded
    decision must invalidate it.
    """
    want = str(expected or "").strip()
    got = str(observed or "").strip()
    if not want or not got:
        return False
    if want == got:
        return not _is_alias(want)
    return False


def _is_alias(value: str) -> bool:
    lowered = str(value or "").strip().lower()
    return any(lowered == alias or lowered.endswith(f"-{alias}") for alias in MOVING_ALIAS_REVISIONS)


def default_manifest(
    *,
    runtime_version: str,
    implementation: str,
    implementation_revision: str,
    model: str,
    model_revision: str,
    primitives: tuple[str, ...],
    languages: tuple[str, ...] = ("en",),
    context_limits: Mapping[str, int] | None = None,
    calibration_profiles: tuple[str, ...] = (),
) -> dict:
    """Build the manifest for a runtime whose files are not digest-pinned.

    ``files`` is omitted rather than filled in from the installation. Ariadne will
    describe its own reference engine with a digest in the release record, but an
    installation that cannot name a reviewed digest must not pretend to have one.
    """
    return {
        "schema": MANIFEST_SCHEMA,
        "runtime_version": str(runtime_version),
        "implementation": str(implementation),
        "implementation_revision": str(implementation_revision),
        "model": str(model),
        "model_revision": str(model_revision),
        "primitives": tuple(str(item) for item in primitives),
        "languages": tuple(str(item) for item in languages),
        "context_limits": dict(context_limits or DEFAULT_CONTEXT_LIMITS),
        "calibration_profiles": tuple(str(item) for item in calibration_profiles),
        "files": None,
    }


def load_manifest(path: Path) -> dict:
    """Read and validate a manifest file. A malformed manifest refuses the install."""
    path = Path(path)
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ContractError(f"decision runtime manifest is unreadable at {path}: {exc}") from exc
    problems = manifest_problems(manifest)
    if problems:
        raise ContractError("decision runtime manifest is invalid: " + "; ".join(problems))
    return manifest


def write_manifest(path: Path, manifest: Mapping[str, Any]) -> Path:
    """Write a manifest deterministically, so an installation is reproducible."""
    problems = manifest_problems(manifest)
    if problems:
        raise ContractError("refusing to write an invalid decision runtime manifest: " + "; ".join(problems))
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def describe(manifest: Mapping[str, Any] | None) -> dict:
    """A read-only description used by diagnostics.

    ``available`` is False for a missing manifest. Everything else is reported as
    observed rather than assumed, so a diagnostic can distinguish "installed" from
    "installed and pinned".
    """
    if manifest is None:
        return {
            "available": False,
            "detail": "no decision runtime manifest was found",
            "runtime_version": "",
            "implementation": "",
            "model_revision": "",
            "primitives": (),
        }
    return {
        "available": True,
        "detail": "a decision runtime manifest was found",
        "runtime_version": str(manifest.get("runtime_version", "")),
        "implementation": str(manifest.get("implementation", "")),
        "implementation_revision": str(manifest.get("implementation_revision", "")),
        "model": str(manifest.get("model", "")),
        "model_revision": str(manifest.get("model_revision", "")),
        "primitives": tuple(str(item) for item in manifest.get("primitives", ()) or ()),
        "languages": tuple(str(item) for item in manifest.get("languages", ()) or ()),
        "context_limits": dict(manifest.get("context_limits", {}) or {}),
        "digest_pinned": isinstance(manifest.get("files"), Mapping),
        "schema": str(manifest.get("schema", "")),
    }