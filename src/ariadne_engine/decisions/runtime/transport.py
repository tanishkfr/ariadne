"""How Ariadne reaches a bounded engine without importing its dependencies.

The whole reason the Decision Runtime is a separate process is that answering a
closed question well may need a machine-learning stack Ariadne must never make its
users install. PyTorch alone is ~118 MiB of wheel on Windows CPU and 800 MiB to
2.5 GiB on Linux with the default CUDA build. That is not a dependency decision to
make silently inside ``pip install ariadne``.

So the engine lives behind a transport. Three exist:

:class:`InProcessTransport`
    runs an engine object in Ariadne's own interpreter. Used by the deterministic
    fixture and by tests. Never used for anything heavy.
:class:`SubprocessTransport`
    launches a sidecar executable and exchanges one JSON document per line over its
    standard streams. This is the shipping route. The engine's dependencies are
    loaded in the child's interpreter; a crash there is a failed call, not a dead
    Ariadne.
:class:`UnavailableTransport`
    the honest default. Nothing installed, nothing to load, and the caller falls
    back.

Three properties the subprocess route has to hold, because they are the difference
between a sidecar and a liability:

*Isolation.* Ariadne never imports the engine. A segfault in a native operator
takes down the sidecar, which Ariadne records as ``DECISION_FAILED`` and routes to
the normal fallback.

*Bounded cost.* Every call has a deadline. A wedged engine becomes a failed call,
not a hung task. On Windows the child is started in its own process group so the
whole tree can be terminated rather than leaking a child of a child.

*No shell.* The command is a list, never a string. A path containing spaces — which
on Windows is most paths — works, and nothing in a manifest or environment variable
is ever interpreted by a shell.

Only the :class:`RuntimeTransport` methods below cross the boundary, and every
crossing value is JSON. That keeps the wire surface small enough to be the
contract rather than an API to mirror.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
from pathlib import Path
from typing import Any, Mapping, Protocol

from ..contracts import ContractError
from .manifest import MANIFEST_NAME, load_manifest

WIRE_SCHEMA = "ariadne-decision-runtime-wire/1"
"""The sidecar wire protocol version, sent on every request and echoed on every reply.

A sidecar that speaks a different version is not usable. Bumping the engine without
bumping this string is how a stale process silently answers with another engine's
semantics.
"""

DEFAULT_CALL_TIMEOUT_SECONDS = 30.0
"""A single decide call. A bounded judgement that has not returned in half a minute is
not going to return usefully, and the caller has a fallback to take."""

DEFAULT_STARTUP_TIMEOUT_SECONDS = 120.0
"""Loading a checkpoint. Generous because it is genuinely slow the first time, and
bounded because an unbounded wait would hang the whole task."""


class RuntimeTransportError(RuntimeError):
    """The transport could not complete a call. Never converted into a decision."""


class RuntimeTransport(Protocol):
    """The narrow boundary between Ariadne and a bounded engine."""

    def describe(self) -> dict:
        """Identity and capability facts. Must not raise."""

    def available(self) -> tuple[bool, str]:
        """Whether a call could succeed now, and why not if not."""

    def call(self, method: str, payload: Mapping[str, Any], *, timeout: float | None = None) -> Mapping[str, Any]:
        """One request, one response. Must raise rather than return a partial answer."""

    def close(self) -> None:
        """Release the engine. Must be safe to call more than once."""


class UnavailableTransport:
    """No engine installed. The honest default, and a complete implementation."""

    def __init__(self, reason: str = "no decision runtime is installed") -> None:
        self.reason = str(reason)

    def describe(self) -> dict:
        return {
            "transport": "none",
            "available": False,
            "reason": self.reason,
            "runtime_version": "",
            "implementation": "",
            "model": "",
            "model_revision": "",
            "primitives": (),
        }

    def available(self) -> tuple[bool, str]:
        return False, self.reason

    def call(self, method: str, payload: Mapping[str, Any], *, timeout: float | None = None) -> Mapping[str, Any]:
        raise RuntimeTransportError(self.reason)

    def close(self) -> None:
        return None


class InProcessTransport:
    """Wraps an engine object that already lives in this interpreter.

    The engine must expose the four sidecar methods as plain callables:
    ``status()``, ``decide(request)``, ``decide_batch(request)``, ``warm()``.
    Errors are re-raised as :class:`RuntimeTransportError` so an in-process engine
    failure is indistinguishable from a subprocess failure to the caller.
    """

    def __init__(self, engine: Any, *, description: Mapping[str, Any] | None = None) -> None:
        self._engine = engine
        self._description = dict(description or {})
        self._lock = threading.Lock()

    def describe(self) -> dict:
        described = dict(self._description)
        described.setdefault("transport", "in-process")
        described.setdefault("available", True)
        return described

    def available(self) -> tuple[bool, str]:
        return True, "in-process engine is loaded"

    def call(self, method: str, payload: Mapping[str, Any], *, timeout: float | None = None) -> Mapping[str, Any]:
        handler = getattr(self._engine, method, None)
        if not callable(handler):
            raise RuntimeTransportError(f"the decision runtime does not implement {method!r}")
        # One call at a time. A sidecar is single-threaded, and letting two calls
        # interleave inside one engine would make batch results order-dependent.
        with self._lock:
            try:
                result = handler(dict(payload))
            except Exception as exc:  # noqa: BLE001 - a provider failure is recorded, never answered
                raise RuntimeTransportError(f"decision runtime {method} failed: {exc}") from exc
        if not isinstance(result, Mapping):
            raise RuntimeTransportError(f"decision runtime {method} did not return an object")
        return result

    def close(self) -> None:
        return None


class SubprocessTransport:
    """Runs a sidecar executable and speaks newline-delimited JSON over stdio.

    The protocol is deliberately one line per message with no framing tricks: the
    sidecar reads a line, answers a line. Nothing here interprets a shell, and the
    child's exit is never silently ignored.
    """

    def __init__(
        self,
        command: list[str],
        *,
        description: Mapping[str, Any] | None = None,
        cwd: str | Path | None = None,
        env: Mapping[str, str] | None = None,
    ) -> None:
        if not command:
            raise ContractError("a subprocess decision runtime needs a non-empty command")
        self.command = [str(part) for part in command]
        self._description = dict(description or {})
        self._cwd = str(cwd) if cwd else None
        self._env = dict(env) if env else None
        self._process: subprocess.Popen[str] | None = None
        self._stderr: _StderrBuffer | None = None
        self._disposed = False
        self._lock = threading.Lock()
        self._status: dict[str, Any] = {}
        self._failure = ""

    # -- lifecycle ---------------------------------------------------------

    def _ensure_started(self, timeout: float) -> subprocess.Popen[str]:
        if self._disposed:
            # close() is a final state, not a hint. A transport that silently respawns
            # after being closed would turn a deliberate shutdown into a live process,
            # which is the opposite of what every caller that closes one intends.
            raise RuntimeTransportError("the decision runtime transport is closed")
        if self._process is not None and self._process.poll() is None:
            return self._process
        self._process = None
        creation: dict[str, Any] = {}
        if sys.platform == "win32":
            # CREATE_NO_WINDOW so a sidecar never flashes a console on Windows.
            creation["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            creation["startupinfo"] = subprocess.STARTUPINFO()
            creation["startupinfo"].dwFlags |= subprocess.STARTF_USESHOWWINDOW
        else:
            # Its own process group, so terminate() can take down the whole tree
            # rather than orphaning a grandchild holding the pipes open.
            creation["start_new_session"] = True
        try:
            self._process = subprocess.Popen(  # noqa: S603 - list argv, no shell
                self.command,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                cwd=self._cwd,
                env=self._env,
                bufsize=1,
                **creation,
            )
        except OSError as exc:
            self._failure = f"the decision runtime could not be started: {exc}"
            raise RuntimeTransportError(self._failure) from exc
        # Start draining stderr before anything else can block. A child that fills the
        # pipe would stop reading stdin and wedge every caller of this transport.
        stderr_buffer = _StderrBuffer(self._process.stderr).start()
        try:
            status = self._call("status", {}, timeout=timeout)
        except Exception:
            self.close()
            raise
        self._status = dict(status)
        self._stderr = stderr_buffer
        return self._process

    def close(self) -> None:
        self._disposed = True
        process, self._process = self._process, None
        buffer, self._stderr = self._stderr, None
        if buffer is not None:
            buffer.close()
        if process is None:
            return
        # Kill first, then close the pipes. Closing before killing would make the child
        # write into a closed pipe; killing after a blocking read would be too late.
        if process.poll() is None:
            try:
                if sys.platform == "win32":
                    process.kill()
                else:
                    import signal

                    os.killpg(os.getpgid(process.pid), signal.SIGTERM)
            except (OSError, ProcessLookupError, AttributeError):
                process.kill()
        for stream in (process.stdin, process.stdout):
            try:
                if stream is not None:
                    stream.close()
            except (OSError, ValueError):
                pass
        # process.stderr is left to the reader thread: closing it here would block on the
        # lock that thread is holding. Killing the child ends the pipe instead.
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:  # pragma: no cover - only a wedged child
            process.kill()

    def __enter__(self) -> SubprocessTransport:
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()

    # -- calls -------------------------------------------------------------

    def _call(self, method: str, payload: Mapping[str, Any], *, timeout: float) -> Mapping[str, Any]:
        process = self._ensure_started(timeout)
        request = {"schema": WIRE_SCHEMA, "method": method, "payload": dict(payload)}
        assert process.stdin is not None and process.stdout is not None
        try:
            process.stdin.write(json.dumps(request, sort_keys=True, default=str) + "\n")
            process.stdin.flush()
        except (BrokenPipeError, OSError) as exc:
            self.close()
            raise RuntimeTransportError(f"the decision runtime closed its input before {method}: {exc}") from exc
        line = _read_line(process.stdout, timeout)
        if line is None:
            # The deadline has passed. Read the buffered detail first -- that is an
            # in-memory read and cannot block -- then close. Reading the child's stderr
            # pipe instead would block until the child exits, which a wedged child never
            # does, turning a bounded timeout into an unbounded hang.
            detail = _drain(self._stderr)
            self.close()
            raise RuntimeTransportError(
                f"the decision runtime did not answer {method} within {timeout:g}s"
                + (f"; stderr: {detail}" if detail else "")
            )
        try:
            response = json.loads(line)
        except ValueError as exc:
            self.close()
            raise RuntimeTransportError(f"the decision runtime answered {method} with unreadable JSON: {exc}") from exc
        if not isinstance(response, Mapping):
            self.close()
            raise RuntimeTransportError(f"the decision runtime answered {method} with a non-object")
        if str(response.get("schema", "")) != WIRE_SCHEMA:
            self.close()
            raise RuntimeTransportError(
                f"the decision runtime speaks {response.get('schema')!r}, not {WIRE_SCHEMA!r}"
            )
        if response.get("error"):
            raise RuntimeTransportError(str(response["error"]))
        result = response.get("result")
        if not isinstance(result, Mapping):
            raise RuntimeTransportError(f"the decision runtime answered {method} with no result object")
        return result

    def call(self, method: str, payload: Mapping[str, Any], *, timeout: float | None = None) -> Mapping[str, Any]:
        limit = DEFAULT_CALL_TIMEOUT_SECONDS if timeout is None else float(timeout)
        with self._lock:
            result = self._call(method, payload, timeout=limit)
            if method == "warm":
                # Refresh the cached capability facts. Without this, status keeps
                # reporting the `cold` it saw at process start, so a user who just paid
                # the load cost is told the runtime is still not ready.
                self._status = dict(self._call("status", {}, timeout=limit))
            return result

    def describe(self) -> dict:
        described = dict(self._description)
        described.update(self._status)
        described["transport"] = "subprocess"
        described.setdefault("command", list(self.command))
        return described

    def available(self) -> tuple[bool, str]:
        if self._failure:
            return False, self._failure
        return True, "the decision runtime sidecar is installed"

    def status(self, *, timeout: float | None = None) -> dict:
        """Ask the sidecar for its capability facts, starting it if needed."""
        limit = DEFAULT_STARTUP_TIMEOUT_SECONDS if timeout is None else float(timeout)
        with self._lock:
            self._status = dict(self._call("status", {}, timeout=limit))
        return self._status


def _read_line(stream: Any, timeout: float) -> str | None:
    """Read one line with a deadline.

    ``readline`` on a pipe has no timeout of its own, so a reader thread does the
    blocking read and the caller decides whether to wait. The thread is a daemon:
    if the child is wedged forever the thread leaks one blocked reader per call
    rather than hanging the whole process. That is the lesser evil, and it is why
    the child is terminated on every timeout.
    """
    box: dict[str, Any] = {}

    def _read() -> None:
        try:
            box["line"] = stream.readline()
        except Exception as exc:  # noqa: BLE001
            box["error"] = exc

    thread = threading.Thread(target=_read, name="ariadne-runtime-read", daemon=True)
    thread.start()
    thread.join(timeout)
    if thread.is_alive():
        return None
    if "error" in box:
        raise RuntimeTransportError(f"the decision runtime stream failed: {box['error']}")
    line = box.get("line", "")
    if not line:
        return None
    return line


def _drain(buffer: "_StderrBuffer") -> str:
    """Whatever the child wrote to stderr, for the failure record.

    Reads the *buffer*, never the pipe. A blocking read of the pipe returns only at EOF
    -- which for a child that is still alive is never -- so a wedged engine turned a
    bounded timeout into an unbounded hang. The buffer is fed continuously by a reader
    thread, so anything the child wrote before it stalled is already here.
    """
    if buffer is None:
        return ""
    return buffer.text()


class _StderrBuffer:
    """A bounded, continuously-drained record of what the sidecar wrote to stderr.

    A piped stderr that nobody reads is a deadlock waiting to happen: the child blocks
    in write() once the OS pipe buffer fills, stops reading stdin, and the parent
    blocks in readline. On Windows that buffer is about 4 KiB, which a chatty sidecar
    reaches in a few progress lines. So the pipe is drained from the moment the child
    starts, into a ring buffer that keeps only the last few kilobytes.
    """

    def __init__(self, stream: Any, *, limit: int = 8192) -> None:
        self._stream = stream
        self._limit = limit
        self._chunks: list[str] = []
        self._size = 0
        self._thread: threading.Thread | None = None

    def start(self) -> "_StderrBuffer":
        if self._stream is None or self._thread is not None:
            return self
        self._thread = threading.Thread(target=self._pump, name="ar206-stderr", daemon=True)
        self._thread.start()
        return self

    def _pump(self) -> None:
        try:
            for line in iter(self._stream.readline, ""):
                self._append(line)
        except (ValueError, OSError):
            # The pipe closed, which is the normal end of a child's stderr.
            pass

    def _append(self, line: str) -> None:
        self._chunks.append(line)
        self._size += len(line)
        while self._size > self._limit and len(self._chunks) > 1:
            self._size -= len(self._chunks.pop(0))

    def text(self) -> str:
        return "".join(self._chunks).strip()[-400:]

    def close(self) -> None:
        # Deliberately does not close the stream. The reader thread is blocked inside
        # readline() holding that object's lock, so closing it from here would wait for
        # the reader to finish -- which for a wedged child is never. Dropping the
        # reference is enough: killing the child closes the pipe, the reader sees EOF
        # and exits, and it is a daemon thread besides.
        self._chunks = []
        self._stream = None


def sidecar_command(runtime_root: Path, *, python: str | None = None) -> list[str]:
    """The argv for the sidecar entry point.

    The *code* lives with the engine, inside the Ariadne source tree; the *data*
    (manifest and weights) lives in the installation directory. That split is why a
    runtime can be updated by replacing a data directory without replacing a program,
    and why Ariadne can ship the sidecar in the wheel while the runtime stays
    separately manageable.

    The command is a list, so a path with spaces needs no quoting and no shell ever
    sees it.
    """
    entry = Path(__file__).with_name("sidecar.py")
    if not entry.is_file():  # pragma: no cover - the module ships with the engine
        raise ContractError(f"no decision runtime sidecar entry point at {entry}")
    source_root = str(Path(__file__).resolve().parents[3])
    return [python or sys.executable, str(entry), "--root", str(Path(runtime_root))]


def sidecar_environment(python: str | None = None) -> dict[str, str]:
    """The environment the sidecar needs so its ``ariadne_engine`` import resolves.

    The sidecar imports the reference engine from Ariadne's own source. Prepending
    that root keeps the child self-contained without requiring Ariadne to be pip
    installed into the interpreter that happens to launch it.
    """
    source_root = str(Path(__file__).resolve().parents[3])
    existing = os.environ.get("PYTHONPATH", "")
    parts = [source_root] + ([existing] if existing else [])
    return {"PYTHONPATH": os.pathsep.join(parts)}


def resolve_installation(runtime_root: Path) -> dict:
    """Load and describe a runtime installation on disk.

    Returns the manifest plus the integrity verdict. A missing manifest is reported
    as ``UNAVAILABLE`` with a reason rather than raising, because "not installed" is
    a state Ariadne must handle, not an error.
    """
    root = Path(runtime_root)
    manifest_path = root / MANIFEST_NAME
    if not manifest_path.is_file():
        return {
            "installed": False,
            "reason": f"no {MANIFEST_NAME} under {root}",
            "root": str(root),
            "manifest": None,
        }
    try:
        manifest = load_manifest(manifest_path)
    except ContractError as exc:
        return {"installed": False, "reason": str(exc), "root": str(root), "manifest": None}
    return {
        "installed": True,
        "reason": "a decision runtime manifest was found",
        "root": str(root),
        "manifest": manifest,
    }