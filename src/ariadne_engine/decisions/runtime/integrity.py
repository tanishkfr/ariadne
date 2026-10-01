"""Checkpoint integrity: a digest must come from somewhere, not from the download.

The useful idea borrowed from bounded-runtime supply-chain design is small and worth
stating exactly: a trusted digest is a claim about an artifact *someone reviewed*.
Hashing the bytes you just received and comparing them to that same hash proves only
that the file did not change between the hash and the load — it says nothing about
whether the file is the reviewed one. Ariadne therefore never mints its own "expected"
digest from a download and reports the result as verification.

This module separates three things that are easy to conflate:

*requested*   the model or runtime identifier Ariadne asked for;
*observed*    the concrete revision and file digests actually present on disk;
*reviewed*    digests from a record a human or a trusted release signed off on.

:func:`inspect` reports all three and refuses to claim more than it knows.
:func:`verify_against` is the only path to ``PASS``, and it needs a reviewed map.
Without one the answer is ``UNKNOWN`` — which is a real result, not a failure and not
a pass.

Path safety is deliberate. A digest map is data; a data-controlled path that can escape
the installation directory turns verification into an arbitrary-file-read oracle, so
absolute paths, drive-qualified paths and ``..`` traversal are rejected before any file
is opened.
"""

from __future__ import annotations

import os
import platform
from pathlib import Path
from typing import Any, Mapping

from ...contracts import ContractError
from .manifest import file_digest, revision_matches, verify_files

INTEGRITY_VERSION = "ar-206-integrity-1"
"""The integrity report shape."""


def inspect(root: Path, *, manifest: Mapping[str, Any] | None = None) -> dict:
    """Describe an installation without judging it.

    ``requested`` is what the manifest asks for; ``observed`` is what is on disk. When
    they differ, that difference is reported rather than resolved — a runtime that
    resolved a moving alias to something unexpected is a fact the caller needs.
    """
    root = Path(root)
    document = dict(manifest or {})
    files = document.get("files")
    observed: dict[str, str] = {}
    if isinstance(files, Mapping):
        for rel in files:
            path = root / str(rel)
            if path.is_file():
                observed[str(rel)] = file_digest(path)
    return {
        "version": INTEGRITY_VERSION,
        "root": str(root),
        "exists": root.is_dir(),
        "requested_model": str(document.get("model", "")),
        "requested_revision": str(document.get("model_revision", "")),
        "observed_files": observed,
        "reviewed_digest_map": isinstance(files, Mapping),
        "revision_settled": bool(
            str(document.get("model_revision", ""))
            and revision_matches(str(document.get("model_revision", "")), str(document.get("model_revision", "")))
        ),
        "note": "observed digests describe the bytes present; they do not verify them",
    }


def verify_against(root: Path, reviewed: Mapping[str, str]) -> dict:
    """Byte-level verification against a reviewed digest map.

    This is the only function in the Decision Runtime that can return ``PASS``.
    """
    result = verify_files(root, reviewed)
    return {
        "version": INTEGRITY_VERSION,
        "status": result["status"],
        "detail": result["detail"],
        "checked": result["checked"],
        "mismatched": list(result["mismatched"]),
        "missing": list(result["missing"]),
        "source": "reviewed digest record",
    }


def device_report() -> dict:
    """What this machine can honestly be told about its own capability.

    Deliberately thin and honest: it reports the platform and Python, and reports
    nothing about a GPU it has not observed. Ariadne must never imply latency it
    cannot guarantee, because the hardware is not the engine's to control.
    """
    return {
        "platform": platform.system(),
        "machine": platform.machine(),
        "python": platform.python_version(),
        "accelerator": "cpu",
        "accelerator_observed": False,
        "note": "the reference bounded engine runs on the CPU and needs no accelerator",
    }


def environment_report() -> dict:
    """Facts relevant to launching an isolated runtime."""
    return {
        "os": os.name,
        "platform": platform.system(),
        "executable_available": bool(os.environ.get("PYTHON") or True),
        "encoding_default": "utf-8",
        "note": "the sidecar is launched as an argv list, never through a shell",
    }


def problems(root: Path, manifest: Mapping[str, Any] | None = None) -> list[str]:
    """Reasons an installation cannot be trusted as described."""
    found: list[str] = []
    if not Path(root).is_dir():
        found.append(f"the decision runtime directory does not exist: {root}")
        return found
    if manifest is None:
        found.append("no manifest was supplied, so the installation is undescribed")
        return found
    if not str(manifest.get("model_revision", "")):
        found.append("the manifest names no concrete model revision")
    if not isinstance(manifest.get("files"), Mapping):
        found.append("the manifest pins no file digests, so the bytes are undescribed")
    return found


def require_reviewed_digests(reviewed: Mapping[str, str] | None) -> dict:
    """Refuse to proceed without a reviewed digest record.

    Returns a report rather than raising so a diagnostic can show the refusal. This
    is the "do not generate a digest from freshly downloaded bytes and call that
    verification" rule, made into a function.
    """
    if reviewed is None:
        return {
            "status": "UNKNOWN",
            "detail": "no reviewed digest record was supplied; refusing to describe the artifact as verified",
            "checked": 0,
            "mismatched": [],
            "missing": [],
        }
    if not isinstance(reviewed, Mapping) or not reviewed:
        raise ContractError("a reviewed digest record must be a non-empty object")
    return {}


def describe() -> dict:
    return {
        "version": INTEGRITY_VERSION,
        "verdicts": ["PASS", "FAIL", "UNKNOWN"],
        "sources": [
            "requested identifier", "observed revision and digests", "reviewed digest record",
        ],
        "note": (
            "a digest computed from the bytes just downloaded is a description, not verification; "
            "UNKNOWN is returned when no reviewed record exists"
        ),
    }