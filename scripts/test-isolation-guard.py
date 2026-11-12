#!/usr/bin/env python3
"""Reject destructive test destinations outside an explicitly marked test root.

This is a test-safety helper, not a security sandbox. It exists because a manual
skills.sh test once resolved a path into the real Windows profile. A disposable
root must contain the marker file ``.ariadne-test-root``; the destination must
resolve inside that root and must not resolve into a known user configuration
directory even if a marker is present.

Usage:
    python scripts/test-isolation-guard.py --self-test
    python scripts/test-isolation-guard.py --root <root> --check <path>
"""

from __future__ import annotations

import argparse
import os
import shutil
import sys
import tempfile
from pathlib import Path

MARKER = ".ariadne-test-root"
PROTECTED_NAMES = (
    ".agents",
    ".codex",
    ".claude",
    ".config",
    ".cursor",
    ".local",
    "Library",
)


class IsolationError(RuntimeError):
    """A path is not safe for a destructive test."""


def _protected_roots() -> tuple[Path, ...]:
    home = Path.home().resolve()
    roots = [home / name for name in PROTECTED_NAMES]
    for variable in ("LOCALAPPDATA", "APPDATA", "XDG_CONFIG_HOME", "XDG_DATA_HOME"):
        value = os.environ.get(variable)
        if value:
            roots.append(Path(value) / "Ariadne")
    return tuple(path.resolve() for path in roots)


def require_isolated(path: str | os.PathLike[str], root: str | os.PathLike[str]) -> Path:
    """Return the resolved path only when it is inside a marked disposable root."""
    resolved_root = Path(root).expanduser().resolve()
    resolved_path = Path(path).expanduser().resolve()
    if not (resolved_root / MARKER).is_file():
        raise IsolationError(f"test root is not marked disposable: {resolved_root}")
    if resolved_path != resolved_root and resolved_root not in resolved_path.parents:
        raise IsolationError(f"destination resolves outside the test root: {resolved_path}")
    for protected in _protected_roots():
        if resolved_path == protected or protected in resolved_path.parents:
            raise IsolationError(f"destination resolves into a user configuration directory: {resolved_path}")
    return resolved_path


def _self_test() -> int:
    root = Path(tempfile.mkdtemp(prefix="ariadne-isolation-")).resolve()
    failures = 0
    try:
        (root / MARKER).write_text("disposable\n", encoding="utf-8")
        cases = []
        try:
            cases.append(("accepts a path inside a marked root", require_isolated(root / "project", root) == (root / "project").resolve()))
        except IsolationError:
            cases.append(("accepts a path inside a marked root", False))
        try:
            require_isolated(root.parent, root)
        except IsolationError:
            cases.append(("rejects a path outside the marked root", True))
        else:
            cases.append(("rejects a path outside the marked root", False))
        unmarked = root / "unmarked"
        unmarked.mkdir()
        try:
            require_isolated(unmarked / "project", unmarked)
        except IsolationError:
            cases.append(("rejects an unmarked root", True))
        else:
            cases.append(("rejects an unmarked root", False))
        try:
            require_isolated(Path.home() / ".agents" / "ariadne", root)
        except IsolationError:
            cases.append(("rejects the real managed-skill path", True))
        else:
            cases.append(("rejects the real managed-skill path", False))
        try:
            require_isolated(root / "project", root)
        except IsolationError:
            cases.append(("accepts the marked test root itself", False))
        else:
            cases.append(("accepts the marked test root itself", True))
    finally:
        if (root / MARKER).is_file() and Path(tempfile.gettempdir()).resolve() in root.parents:
            shutil.rmtree(root, ignore_errors=True)

    print("ARIADNE TEST-ISOLATION GUARD\n")
    for name, passed in cases:
        print(("ok    " if passed else "FAIL  ") + name)
        failures += 0 if passed else 1
    print(f"\n{'FAILED' if failures else 'PASS'}  {len(cases) - failures}/{len(cases)}")
    return 1 if failures else 0


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--root")
    parser.add_argument("--check", metavar="PATH")
    args = parser.parse_args(argv)
    if args.check:
        if not args.root:
            parser.error("--check requires --root")
        try:
            print(require_isolated(args.check, args.root))
        except IsolationError as exc:
            print(f"UNSAFE: {exc}", file=sys.stderr)
            return 2
        return 0
    return _self_test()


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
