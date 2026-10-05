"""Shared mutation ledger: transactional mutation, and a sentinel anything can read.

AR-222 found two integrity failures that both come from the same place:

1. Each mutation harness had its **own** restore marker, and neither was queryable by
   anything that was not that harness. The AR-222 fix for a collision between two
   harnesses sharing a marker path was to give them *different* paths -- which solved the
   crash and left the real problem untouched: **no other process could ask whether the
   repository was mid-mutation.**

2. Restoration was verified by re-reading the mutated file. That proves the file came
   back. It does not prove untracked fixtures came back, and it cannot prove the sentinel
   itself is clear.

This module is the shared answer. One registry, many harnesses, one query:

```text
.ariadne-mutation-active.json     which harnesses currently hold the tree mutated
```

A harness registers before it edits and deregisters after it restores, in a ``finally``,
and writes its stash *before* the edit so a killed process is recoverable. Any other
operation -- a commit, a release, a gate, a suite that asserts the repository is clean --
calls :func:`assert_no_active_mutation` and **fails closed**.

Why fail closed rather than warn. The concrete failure this was built for is real and was
observed during AR-222D's own baseline: a suite asserting "the suite writes nothing into
the repository" failed because a *different* harness was mid-mutation. It failed with an
accurate assertion and a **misleading diagnosis**. A sentinel turns that into "a
mutation was active, here is which one", and refuses to let a mutated tree be committed
at all.

Restoration is verified against :func:`expected_state` -- digests of the files that were
touched, the untracked/ignored inventory that matters, and the sentinel itself -- rather
than against ``git diff == empty``, because an empty diff is equally consistent with
"restored", "never mutated", and "the mutation was to an untracked file git does not
track".
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, Mapping, Sequence

LEDGER_NAME = ".ariadne-mutation-active.json"
"""The one registry every harness registers into.

Deliberately a *list of entries with owner keys* rather than one harness's shape. The
AR-222 lesson was that two harnesses cannot share a single-object marker: whoever
assumes it owns the file misreads the other one's record and crashes. A keyed registry
has no such failure mode -- an entry nobody recognises is simply another harness's
business.
"""

LEDGER_SCHEMA = "ariadne-mutation-ledger-1"


class MutationStateError(RuntimeError):
    """Raised when the repository's mutation state cannot be trusted."""


# --------------------------------------------------------------- the ledger file

def ledger_path(repo: Path | str) -> Path:
    return Path(repo) / LEDGER_NAME


def _read_ledger(repo: Path | str) -> list[dict]:
    path = ledger_path(repo)
    if not path.is_file():
        return []
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise MutationStateError(
            f"the mutation ledger at {path} is unreadable ({exc}). Its state is UNKNOWN, and an "
            "unknown mutation state is treated as an active mutation: the tree may be mid-edit and "
            "nothing may assume otherwise. Inspect the file and delete it once you have confirmed "
            "the tree is clean."
        ) from exc
    if not isinstance(raw, list):
        raise MutationStateError(
            f"the mutation ledger at {path} is not a list of entries. Its state is UNKNOWN and is "
            "treated as active. Inspect the file before deleting it."
        )
    return [row for row in raw if isinstance(row, dict)]


def _write_ledger(repo: Path | str, entries: Sequence[Mapping]) -> None:
    path = ledger_path(repo)
    rows = [dict(row) for row in entries]
    payload = json.dumps(rows, indent=2, sort_keys=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(payload + "\n", encoding="utf-8")
    temporary.replace(path)


def active_mutations(repo: Path | str) -> list[dict]:
    """Every harness currently holding the tree mutated, including other harnesses'.

    Raises rather than returning empty on a corrupt ledger. An unreadable ledger means
    the state is *unknown*, and this module's whole contribution is that unknown and
    empty are different answers.
    """
    rows = _read_ledger(repo)
    return [
        row for row in rows
        if not row.get("cleared_at") or _entry_is_stale(row)
    ]


def _entry_is_stale(row: Mapping) -> bool:
    """An entry whose owning process is gone is reported, not silently dropped.

    Dropping it would be the convenient answer and the wrong one: a killed harness leaves
    an entry behind by definition, and a stale entry is exactly the case the ledger
    exists to surface. It is marked so the caller can tell "someone is editing" from
    "someone was killed while editing" -- both block a commit, and the second one also
    tells you to run recovery.
    """
    pid = row.get("pid")
    if not isinstance(pid, int) or pid <= 0:
        return False
    if pid == os.getpid():
        return False
    return not _process_alive(pid)


def _process_alive(pid: int) -> bool:
    """Whether a recorded pid is still running.

    On Windows, ``OpenProcess`` succeeding is not sufficient: it succeeds for a pid whose
    process has exited but whose handle is still openable, and it can succeed shortly after
    a kill before the handle is released. The only reliable test is the exit code, so
    ``GetExitCodeProcess`` is consulted and ``STILL_ACTIVE`` (259) is the answer that means
    alive. Getting this wrong in the permissive direction means a killed harness looks live,
    its entry is never reported as stale, and recovery is never offered -- which is the exact
    failure this module exists to prevent.
    """
    if os.name == "nt":  # pragma: no cover - platform branch
        try:
            import ctypes
            from ctypes import wintypes

            STILL_ACTIVE = 259
            kernel32 = ctypes.windll.kernel32
            handle = kernel32.OpenProcess(0x1000, False, pid)
            if not handle:
                return False
            try:
                code = wintypes.DWORD()
                if not kernel32.GetExitCodeProcess(handle, ctypes.byref(code)):
                    return True
                return int(code.value) == STILL_ACTIVE
            finally:
                kernel32.CloseHandle(handle)
        except (AttributeError, OSError, ValueError):
            return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:  # pragma: no cover - alive, just not ours
        return True
    except OSError:  # pragma: no cover - undecidable
        return True
    return True


def mutation_state(repo: Path | str) -> dict:
    """One answer about mutation state, for anything that needs to make a decision."""
    try:
        entries = active_mutations(repo)
        known = True
        reason = ""
    except MutationStateError as exc:
        entries = []
        known = False
        reason = str(exc)
    return {
        "active": bool(entries) or not known,
        "known": known,
        "reason": reason,
        "entries": entries,
        "count": len(entries),
        "ledger": str(ledger_path(repo)),
        "stale_entries": [
            row for row in entries if known and _entry_is_stale(row)
        ],
        "invariant": "an unknown mutation state is an active mutation state",
    }


def assert_no_active_mutation(repo: Path | str, *, operation: str = "repository operation") -> None:
    """Fail closed when the tree is mid-mutation.

    Called by commit, release and gate paths. ``git diff`` is not a substitute: untracked
    files and gitignored fixtures do not appear in it, and this repository has both.
    """
    state = mutation_state(repo)
    if not state["active"]:
        return
    owners = sorted({str(row.get("harness", "unknown")) for row in state["entries"]})
    stale = sorted({str(row.get("harness", "unknown")) for row in state["stale_entries"]})
    detail = (
        f"the mutation ledger is unreadable, so mutation state is unknown and unknown is treated "
        f"as active ({state['reason']})"
        if not state["known"]
        else (
            f"{state['count']} mutation(s) are currently applied by: {', '.join(owners)}"
            + (f". Stale (owning process is gone, recovery required): {', '.join(stale)}" if stale else "")
        )
    )
    raise MutationStateError(
        f"refusing to {operation}: {detail}. A commit or release over a mutated tree records a "
        "corrupted engine as though it were the real one, and the corruption is then invisible to "
        "git because the file may be untracked. Wait for the harness to finish, or run its "
        f"recovery, then retry. Ledger: {state['ledger']}"
    )


# ------------------------------------------------------------- expected state

def digest_of(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def expected_state(
    paths: Sequence[Path | str],
    *,
    root: Path | str | None = None,
    untracked_globs: Sequence[str] = (),
) -> dict:
    """The state that must be true after a mutation is undone.

    Three components, all of them necessary:

    * **tracked file digests** for every file a harness may have touched;
    * **an untracked/ignored inventory** for the fixture areas that ``git diff`` cannot
      see -- the node_modules tree and the rendered-evidence directories are exactly the
      places a mutation harness or a render cycle leaves something behind;
    * **the sentinel itself**, recorded as "must be clear".

    ``git diff == empty`` satisfies none of these independently: it is equally consistent
    with restored, never-mutated, and a mutation to an untracked path.
    """
    base = Path(root) if root is not None else None
    tracked: dict[str, str] = {}
    for path in paths or ():
        candidate = Path(path)
        key = candidate.relative_to(base).as_posix() if base else str(candidate)
        tracked[key] = digest_of(candidate) if candidate.is_file() else "MISSING"
    untracked: dict[str, str] = {}
    if untracked_globs:
        seen: set[str] = set()
        for pattern in untracked_globs:
            for match in sorted(base.glob(pattern)) if base else sorted(Path().glob(pattern)):
                if not match.is_file() or match in seen:
                    continue
                seen.add(match)
                key = match.relative_to(base).as_posix() if base else str(match)
                untracked[key] = digest_of(match)
    return {
        "tracked_digests": tracked,
        "untracked_inventory": untracked,
        "untracked_count": len(untracked),
        "mutation_state": "clear",
        "basis": (
            "restoration is verified against recorded digests and an untracked inventory, not "
            "against an empty git diff. An empty diff is equally consistent with restored, "
            "never-mutated, and a mutation to a path git does not track. The inventory is digested "
            "rather than sized, because a mutated fixture of exactly the same length is the "
            "easiest corruption to miss and it is invisible to a size check."
        ),
    }


def verify_restoration(
    expected: Mapping,
    *,
    root: Path | str | None = None,
    ledger_repo: Path | str | None = None,
) -> dict:
    """Whether the recorded state was actually restored. Says ``UNKNOWN`` when it cannot tell."""
    base = Path(root) if root is not None else None
    problems: list[str] = []
    unknown: list[str] = []
    actual: dict[str, str] = {}
    for key, digest in (expected.get("tracked_digests") or {}).items():
        path = (base / key) if base else Path(key)
        if not path.is_file():
            problems.append(f"{key}: expected file is missing")
            continue
        current = digest_of(path)
        actual[key] = current
        if current != str(digest):
            problems.append(
                f"{key}: content differs from the pre-mutation digest "
                f"(expected {str(digest)[:12]}, found {current[:12]})"
            )
    inventory_diff: dict[str, list[str]] = {}
    for key, digest in (expected.get("untracked_inventory") or {}).items():
        path = (base / key) if base else Path(key)
        if not path.is_file():
            inventory_diff.setdefault("missing", []).append(key)
            continue
        if digest_of(path) != str(digest):
            inventory_diff.setdefault("changed", []).append(key)
    for label, keys in inventory_diff.items():
        problems.append(f"untracked fixture {label}: {', '.join(sorted(keys))}")
    if ledger_repo is not None:
        state = mutation_state(ledger_repo)
        if state["active"]:
            # An unreadable ledger is *unknown*, which is not the same as *broken*, and the two
            # deserve different answers: broken says "run recovery", unknown says "find out what
            # happened". Collapsing them into one word loses exactly the information needed to
            # choose between them.
            if not state["known"]:
                unknown.append(
                    "the mutation sentinel could not be read, so restoration cannot be confirmed"
                )
            else:
                problems.append(
                    "the mutation sentinel is not clear after restoration "
                    f"({state['count']} entr{'y' if state['count'] == 1 else 'ies'} still registered)"
                )
    restored = not problems and not unknown
    return {
        "restored": restored,
        "verified": "YES" if restored else ("UNKNOWN" if unknown else "NO"),
        "problems": problems,
        "unknowns": unknown,
        "digests_compared": len(actual),
        "untracked_compared": len(expected.get("untracked_inventory") or {}),
    }


# ------------------------------------------------------------ the transaction

@contextmanager
def mutation_transaction(
    repo: Path | str,
    *,
    harness: str,
    mutation_id: str,
    targets: Sequence[Path | str],
    untracked_globs: Sequence[str] = (),
    stash_dir: Path | str | None = None,
) -> Iterator[dict]:
    """Apply a mutation transactionally, and prove it was undone afterwards.

    Lifecycle, in this order, and the order is the whole point:

    ```text
    capture bytes and record the expected state   -> before anything is edited
    write the stash to disk                        -> so a killed process is recoverable
    register in the ledger                         -> so anything else can see the state
    apply the mutation                             -> the only mutating step
    yield
    restore bytes, clear stash, deregister         -> in a finally
    verify restoration                             -> and report it
    ```

    ``finally`` covers success, failure, exception and timeout. It does **not** cover a
    process killed from outside, which is why the stash is on disk and the ledger entry
    names the owning pid: the next run can recover, and a stale entry is detectable
    because the process is gone.

    The context manager yields a report dict. Restoration happens on exit, so
    ``report["restoration"]`` is only populated once the ``with`` block has exited.
    """
    base = Path(repo)
    paths = [Path(item) for item in targets or ()]
    missing = [str(item) for item in paths if not item.is_file()]
    if missing:
        raise MutationStateError(
            "mutation targets must exist before the transaction opens: " + ", ".join(missing)
        )
    report: dict = {
        "harness": str(harness),
        "mutation_id": str(mutation_id),
        "targets": [str(item) for item in paths],
        "opened_at": time.time(),
        "restoration": {},
        "error": "",
    }
    stash_root = Path(stash_dir) if stash_dir is not None else base / f".ariadne-mutation-stash-{harness}"
    payloads: dict[Path, bytes] = {path: path.read_bytes() for path in paths}
    expected = expected_state(paths, root=base, untracked_globs=untracked_globs)

    try:
        if stash_root.exists():
            shutil.rmtree(stash_root, ignore_errors=True)
        stash_root.mkdir(parents=True, exist_ok=True)
        for index, (path, payload) in enumerate(payloads.items()):
            backup = stash_root / f"{index:03d}-{path.name}"
            backup.write_bytes(payload)
        _write_stash_manifest(stash_root, base, payloads, expected, mutation_id=str(mutation_id))
        _register(base, harness=str(harness), mutation_id=str(mutation_id),
                  targets=[str(item) for item in paths], stash=str(stash_root))
    except Exception as exc:  # pragma: no cover - the tree is untouched here
        shutil.rmtree(stash_root, ignore_errors=True)
        report["error"] = f"could not establish a recoverable mutation state: {exc}"
        raise MutationStateError(report["error"]) from exc

    try:
        yield report
    except BaseException as exc:
        report["error"] = f"{type(exc).__name__}: {exc}"
        raise
    finally:
        for path, payload in payloads.items():
            try:
                path.write_bytes(payload)
            except OSError as exc:  # pragma: no cover - unwritable target
                report["error"] = report["error"] or f"could not restore {path}: {exc}"
        _deregister(base, harness=str(harness), mutation_id=str(mutation_id))
        report["restoration"] = verify_restoration(
            expected, root=base, ledger_repo=base,
        )
        if report["restoration"].get("restored"):
            shutil.rmtree(stash_root, ignore_errors=True)
        report["closed_at"] = time.time()


def _write_stash_manifest(
    stash_root: Path,
    base: Path,
    payloads: Mapping[Path, bytes],
    expected: Mapping,
    *,
    mutation_id: str,
) -> None:
    rows = []
    for index, (path, payload) in enumerate(payloads.items()):
        rows.append({
            "path": str(path),
            "backup": f"{index:03d}-{path.name}",
            "sha256": hashlib.sha256(payload).hexdigest(),
            "bytes": len(payload),
        })
    (stash_root / "stash.json").write_text(
        json.dumps({
            "schema": LEDGER_SCHEMA,
            "mutation_id": mutation_id,
            "repo": str(base),
            "files": rows,
            "expected_state": expected,
        }, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _register(repo: Path, *, harness: str, mutation_id: str, targets: Sequence[str], stash: str) -> None:
    rows = [
        row for row in _read_ledger(repo)
        if not (str(row.get("harness")) == harness and str(row.get("mutation_id")) == mutation_id)
    ]
    rows.append({
        "harness": str(harness),
        "mutation_id": str(mutation_id),
        "pid": os.getpid(),
        "targets": list(targets),
        "stash": str(stash),
        "opened_at": time.time(),
        "cleared_at": 0,
    })
    _write_ledger(repo, rows)


def _deregister(repo: Path, *, harness: str, mutation_id: str) -> None:
    rows = _read_ledger(repo)
    remaining = [
        row for row in rows
        if not (str(row.get("harness")) == harness and str(row.get("mutation_id")) == mutation_id)
    ]
    _write_ledger(repo, remaining)


# ----------------------------------------------------------------- recovery

def recover(repo: Path | str, *, stash_glob: str = ".ariadne-mutation-stash-*") -> dict:
    """Restore anything a killed harness left mutated, from whatever stash it wrote.

    Reads every stash directory rather than one known path, because the AR-222 failure
    was precisely that a harness could not find another's stash. Recovery is verified,
    not assumed, and a stash whose bytes disagree with its recorded digest is reported
    rather than applied.
    """
    base = Path(repo)
    report: dict = {"restored": [], "unreadable": [], "stale_stashes": [], "problems": []}
    for stash_root in sorted(base.glob(stash_glob)):
        manifest_path = stash_root / "stash.json"
        if not manifest_path.is_file():
            continue
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            report["unreadable"].append({"stash": str(stash_root), "problem": str(exc)})
            continue
        for row in manifest.get("files") or []:
            if not isinstance(row, Mapping):
                continue
            target = Path(str(row.get("path", "")))
            backup = stash_root / str(row.get("backup", ""))
            if not target.is_file() or not backup.is_file():
                report["problems"].append(f"cannot restore {target}: target or backup is missing")
                continue
            payload = backup.read_bytes()
            if hashlib.sha256(payload).hexdigest() != str(row.get("sha256", "")):
                report["problems"].append(
                    f"refusing to restore {target}: the stashed bytes do not match their digest"
                )
                continue
            if target.read_bytes() != payload:
                target.write_bytes(payload)
                report["restored"].append(str(target))
    for entry in active_mutations(base):
        if _entry_is_stale(entry):
            _deregister(base, harness=str(entry.get("harness", "")),
                        mutation_id=str(entry.get("mutation_id", "")))
            report["stale_stashes"].append(str(entry.get("mutation_id", "")))
    state = mutation_state(base)
    report["ledger_clear"] = not state["active"]
    report["verified"] = verify_restoration(
        expected_state([], root=base), root=base, ledger_repo=base
    )
    return report


__all__ = [
    "LEDGER_NAME",
    "LEDGER_SCHEMA",
    "MutationStateError",
    "active_mutations",
    "assert_no_active_mutation",
    "digest_of",
    "expected_state",
    "mutation_state",
    "mutation_transaction",
    "recover",
    "verify_restoration",
]