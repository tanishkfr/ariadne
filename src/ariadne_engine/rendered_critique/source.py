"""Exact source binding for rendered evidence (AR-222).

AR-221 proved the code came from the right evidence. It could not say anything
about whether the code that *rendered* was the code that was reviewed, because a
screenshot carries no statement about what produced it. A file called
``screenshot.png`` next to a passing test suite is a claim, not evidence.

This module makes that claim checkable. Every capture is bound to a
``render_source_digest``: a deterministic fingerprint over the exact implementation
bytes that produced the render. Not the branch, not the commit message, not the
timestamp -- the bytes.

Dirty worktrees are a first-class case, not an excuse. During refinement the target
is *intentionally* dirty, and faking a commit per repair would turn provenance into
theatre. So the digest is derived from tracked and untracked implementation bytes
alike, and a later edit to any relevant file immediately invalidates every capture
bound to the old digest. That transition has a name -- ``STALE_RENDER_EVIDENCE`` --
and it is refusal, not a warning.

Why a digest over *relevant* bytes rather than the whole repository: a capture
proves something about what the user saw. A change to a test fixture, a changelog
or a benchmark result does not alter what the user saw, and binding captures to
those would make staleness fire on every unrelated commit and train everyone to
ignore it. A stale warning nobody believes is worse than no warning.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
from pathlib import Path
from typing import Mapping, Sequence

from .. import contracts
from ..contracts import ContractError

#: Directory names never contributing implementation bytes to a render.
EXCLUDED_DIRS = frozenset({
    ".git", "node_modules", "dist", "build", "coverage", "__pycache__", ".next",
    ".ariadne", ".venv", "venv", ".pytest_cache", ".mypy_cache", ".turbo",
})

#: File suffixes that *can* reach the screen and therefore bind a capture.
RENDERED_SUFFIXES = frozenset({
    ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".css", ".scss", ".sass",
    ".less", ".html", ".svg", ".json", ".vue", ".svelte", ".astro", ".woff2",
    ".woff", ".ttf",
})

#: Filenames that reach the screen without a suffix that says so.
RENDERED_NAMES = frozenset({
    "index.html", "sw.js", "service-worker.js", "manifest.json",
})

#: Files that configure the build rather than the interface. A change here can change
#: what renders, so they bind -- but they are listed so the reason is visible.
RENDERED_CONFIG_NAMES = frozenset({
    "vite.config.ts", "vite.config.js", "vite.config.mjs",
    "next.config.js", "next.config.mjs", "astro.config.mjs",
    "tailwind.config.js", "tailwind.config.ts", "postcss.config.js",
    "package.json", "tsconfig.json",
})

MAX_SOURCE_FILES = 2000
"""Bounded scan. A project larger than this is reported, not silently truncated:
an incomplete digest would be worse than no digest, because it would look exact."""

MAX_FILE_BYTES = 4 * 1024 * 1024
"""Per-file cap. A 40 MB vendored bundle inside ``src`` is a packaging problem."""


def relevant_files(root: Path) -> list[str]:
    """The repository-relative implementation files that can change what renders.

    Returned sorted so the digest is a function of content and path set, never of
    filesystem enumeration order.
    """
    base = Path(root)
    found: list[str] = []
    for dirpath, dirnames, filenames in os.walk(base):
        dirnames[:] = sorted(d for d in dirnames if d not in EXCLUDED_DIRS)
        for name in sorted(filenames):
            path = Path(dirpath) / name
            relative = path.relative_to(base).as_posix()
            suffix = path.suffix.lower()
            if suffix in RENDERED_SUFFIXES or name in RENDERED_NAMES or name in RENDERED_CONFIG_NAMES:
                found.append(relative)
    found.sort()
    return found


def file_digests(root: Path, relatives: Sequence[str]) -> dict[str, str]:
    """Per-file digests. A file that cannot be read is a refusal, not an omission.

    Silently skipping an unreadable file would let the digest stay stable while the
    implementation it claims to describe is not fully known.
    """
    base = Path(root)
    digests: dict[str, str] = {}
    for relative in relatives:
        path = base / relative
        try:
            payload = path.read_bytes()
        except OSError as exc:
            raise ContractError(
                f"the implementation file {relative} cannot be read, so no exact source digest "
                f"can be established for this render: {exc}"
            ) from exc
        if len(payload) > MAX_FILE_BYTES:
            raise ContractError(
                f"the implementation file {relative} is {len(payload)} bytes, above the "
                f"{MAX_FILE_BYTES}-byte bound; a render cannot be bound to an unbounded bundle"
            )
        digests[relative] = hashlib.sha256(payload).hexdigest()
    return digests


def render_source_digest(root: Path, relatives: Sequence[str] | None = None) -> str:
    """The deterministic fingerprint of the exact implementation bytes.

    Built from ``(path, digest)`` pairs so that renaming a file with identical
    content changes the digest -- which is correct, because a rename can change a
    route, an import graph or an asset URL, and therefore what renders.
    """
    files = list(relatives) if relatives is not None else relevant_files(root)
    if len(files) > MAX_SOURCE_FILES:
        raise ContractError(
            f"this project has {len(files)} implementation files, above the {MAX_SOURCE_FILES} bound; "
            "a render source digest over an unbounded tree is not a digest of anything"
        )
    digests = file_digests(root, files)
    payload = "\n".join(f"{relative} {digests[relative]}" for relative in sorted(digests))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _git(root: Path, *args: str, timeout: int = 30) -> tuple[int, str, str]:
    """Run one read-only git command. Never a shell string, never a mutation.

    ``shell=False`` with an argv list is the whole security argument: a repository
    path or a revision string that reached a shell here would be remote code
    execution, and the read-only verbs below make the blast radius smaller still.
    """
    argv = ["git", "-C", str(root), *args]
    try:
        completed = subprocess.run(
            argv, capture_output=True, text=True, timeout=timeout,
            shell=False, stdin=subprocess.DEVNULL, check=False,
        )
    except FileNotFoundError as exc:
        return 127, "", f"git is not available: {exc}"
    except subprocess.TimeoutExpired:
        return 124, "", "git timed out"
    except OSError as exc:  # pragma: no cover - platform-specific
        return 1, "", f"git could not be run: {exc}"
    return completed.returncode, (completed.stdout or "").strip(), (completed.stderr or "").strip()


def repository_revision(root: Path) -> dict:
    """Commit and dirty-diff identity for the rendered project.

    Recorded because a commit is a *useful* label, not because it is sufficient. The
    load-bearing field is ``render_source_digest``, which holds for a dirty worktree
    where no commit exists at all.
    """
    base = Path(root)
    if not base.is_dir():
        raise ContractError(f"the rendered project root does not exist: {base}")
    code, head, _ = _git(base, "rev-parse", "HEAD")
    inside, _, _ = _git(base, "rev-parse", "--is-inside-work-tree")
    commit = head if (code == 0 and _is_sha(head)) else ""
    code, status, _ = _git(base, "status", "--porcelain=v1", "--untracked-files=all")
    dirty = bool(status) if code == 0 else False
    diff = ""
    if code == 0 and dirty:
        _, diff, _ = _git(base, "diff", "HEAD")
        if not diff:
            _, diff, _ = _git(base, "diff")
    return {
        "is_git_repository": inside == "0" and inside.strip() == "true",
        "source_commit": commit,
        "dirty": dirty,
        "tracked_diff_sha256": hashlib.sha256(diff.encode("utf-8")).hexdigest() if diff else "",
        "tracked_diff_bytes": len(diff.encode("utf-8")),
        "note": (
            "a commit is a label, not the binding. The binding is render_source_digest, which "
            "holds for a dirty worktree where no commit exists."
        ),
    }


def _is_sha(value: str) -> bool:
    return bool(value) and len(value) == 40 and all(char in "0123456789abcdef" for char in value.lower())


def bind(root: Path, *, scope: Sequence[str] | None = None) -> dict:
    """Everything a capture must record to identify the implementation it shows."""
    base = Path(root)
    files = list(scope) if scope is not None else relevant_files(base)
    digests = file_digests(base, files)
    revision = repository_revision(base)
    return {
        "render_source_digest": render_source_digest(base, files),
        "file_count": len(digests),
        "file_digests": digests,
        "excluded": sorted(EXCLUDED_DIRS),
        "suffixes": sorted(RENDERED_SUFFIXES),
        "capture_bytes": sum(len(str(value)) for value in digests.values()),
        **revision,
        "build_identity": _build_identity(base),
        "bound_at": contracts.utc_now(),
    }


def _build_identity(base: Path) -> dict:
    """How the render was produced. Best-effort, and honest about being so."""
    identity: dict = {}
    package = base / "package.json"
    if package.is_file():
        try:
            parsed = json.loads(package.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            parsed = {}
        if isinstance(parsed, Mapping):
            identity["package_name"] = str(parsed.get("name", ""))
            identity["package_version"] = str(parsed.get("version", ""))
            scripts = parsed.get("scripts") if isinstance(parsed.get("scripts"), Mapping) else {}
            identity["build_script"] = str((scripts or {}).get("build", ""))
            identity["dev_script"] = str((scripts or {}).get("dev", ""))
    return identity


def digest_of(binding: Mapping) -> str:
    return str(binding.get("render_source_digest", ""))


def staleness(binding: Mapping, current_digest: str) -> list[str]:
    """Why a capture bound to ``binding`` can no longer describe ``current_digest``.

    Empty list means current. This is the single implementation of the staleness
    rule; the render, critique and refinement layers all ask it rather than each
    re-deriving "has the source moved", which is how a rule ends up enforced in one
    place and assumed in three.
    """
    recorded = str(binding.get("render_source_digest", ""))
    if not recorded:
        return [
            "this capture names no render source digest; a screenshot without source identity is "
            "not rendered evidence"
        ]
    if not current_digest:
        return [
            "no current render source digest could be established, so this capture cannot be shown "
            "to still describe the implementation"
        ]
    if recorded != current_digest:
        recorded_files = binding.get("file_digests") if isinstance(binding.get("file_digests"), Mapping) else {}
        return [
            "STALE_RENDER_EVIDENCE: this capture was bound to render source digest "
            f"{recorded[:12]} but the implementation is now {current_digest[:12]}; "
            f"{len(recorded_files)} implementation file(s) were fingerprinted at capture time and "
            "at least one has changed"
        ]
    return []


def changed_files(previous: Mapping, current: Mapping) -> list[str]:
    """Which implementation files differ between two bindings.

    Named rather than inferred, so a repair plan can say what it actually changed
    instead of a reviewer guessing from a digest prefix.
    """
    before = previous.get("file_digests") if isinstance(previous.get("file_digests"), Mapping) else {}
    after = current.get("file_digests") if isinstance(current.get("file_digests"), Mapping) else {}
    changed: list[str] = []
    for name in sorted(set(before) | set(after)):
        if str(before.get(name, "")) != str(after.get(name, "")):
            changed.append(name)
    return changed


def describe(binding: Mapping) -> str:
    commit = str(binding.get("source_commit", "")) or "uncommitted"
    return (
        f"render_source_digest={str(binding.get('render_source_digest', ''))[:12]} "
        f"commit={commit[:12]} dirty={binding.get('dirty')} "
        f"files={binding.get('file_count')}"
    )


__all__ = [
    "EXCLUDED_DIRS",
    "RENDERED_SUFFIXES",
    "RENDERED_NAMES",
    "RENDERED_CONFIG_NAMES",
    "MAX_SOURCE_FILES",
    "MAX_FILE_BYTES",
    "relevant_files",
    "file_digests",
    "render_source_digest",
    "repository_revision",
    "bind",
    "digest_of",
    "staleness",
    "changed_files",
    "describe",
]
