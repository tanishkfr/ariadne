"""Sandboxed subprocess driver for the real Ariadne runtime."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path


RUNTIME_SCRIPTS = ("ariadne.py", "prepare-stage.py", "reasoners.py", "creative-intelligence.py",
                   "creative-operations.py", "check.py", "validate.py", "build-release.py")


@dataclass
class Result:
    argv: list[str]
    returncode: int
    stdout: str
    stderr: str
    duration_seconds: float
    timed_out: bool = False

    @property
    def ok(self) -> bool:
        return self.returncode == 0 and not self.timed_out

    @property
    def combined(self) -> str:
        return (self.stdout or "") + (self.stderr or "")

    def tail(self, lines: int = 6) -> str:
        text = [line for line in self.combined.splitlines() if line.strip()]
        return " | ".join(text[-lines:])


class Repo:
    """The runtime-under-test repository (a v2 worktree, writable but untouched)."""

    def __init__(self, root: Path, python: str | None = None):
        self.root = Path(root).resolve()
        self.python = python or sys.executable
        self._modules: dict[str, object] = {}

    # ------------------------------------------------------------------ paths
    def script(self, name: str) -> Path:
        path = self.root / "scripts" / name
        if not path.is_file():
            raise FileNotFoundError(path)
        return path

    # --------------------------------------------------------------- commands
    def run(self, argv: list[str], *, cwd: Path | None = None, timeout: int = 300,
            env_extra: dict[str, str] | None = None) -> Result:
        env = dict(os.environ)
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        env["GIT_TERMINAL_PROMPT"] = "0"
        env["NO_COLOR"] = "1"
        if env_extra:
            env.update(env_extra)
        started = time.monotonic()
        timed_out = False
        try:
            completed = subprocess.run(
                argv, cwd=str(cwd or self.root), capture_output=True, text=True,
                timeout=timeout, env=env, shell=False,
            )
            returncode = completed.returncode
            stdout, stderr = completed.stdout, completed.stderr
        except subprocess.TimeoutExpired as exc:
            timed_out = True
            returncode = -1
            stdout = str(exc.stdout or "")
            stderr = str(exc.stderr or "") + f"\n[harness] timed out after {timeout}s"
        return Result(argv, returncode, stdout, stderr, round(time.monotonic() - started, 3), timed_out)

    def cli(self, *args: str, cwd: Path | None = None, timeout: int = 300) -> Result:
        """Invoke scripts/ariadne.py with the given arguments."""
        return self.run([self.python, str(self.script("ariadne.py")), *map(str, args)],
                        cwd=cwd, timeout=timeout)

    def script_run(self, name: str, *args: str, cwd: Path | None = None, timeout: int = 600) -> Result:
        return self.run([self.python, str(self.script(name)), *map(str, args)], cwd=cwd, timeout=timeout)

    # ---------------------------------------------------------------- modules
    def module(self, name: str):
        """Import a runtime script as a module (read-only, no bytecode written).

        The module is registered in ``sys.modules`` before execution, exactly like
        the runtime's own internal loaders, so a module that binds itself (the
        orchestration API) resolves correctly instead of failing at import time.
        """
        if name in self._modules:
            return self._modules[name]
        import importlib.util

        sys.dont_write_bytecode = True
        key = f"ar_bench_{name.replace('.', '_')}"
        spec = importlib.util.spec_from_file_location(key, self.script(name))
        if spec is None or spec.loader is None:
            raise ImportError(name)
        module = importlib.util.module_from_spec(spec)
        sys.modules[key] = module
        try:
            spec.loader.exec_module(module)
        except BaseException:
            sys.modules.pop(key, None)
            raise
        self._modules[name] = module
        return module

    # ----------------------------------------------------------------- git
    def git(self, *args: str) -> str:
        result = self.run(["git", *args], timeout=60)
        return result.stdout.strip()

    def commit(self) -> str:
        return self.git("rev-parse", "HEAD")

    def status_porcelain(self) -> list[str]:
        return [line for line in self.git("status", "--porcelain").splitlines() if line.strip()]


@dataclass
class Sandbox:
    """One isolated case workspace: a project repository and its run directory."""

    root: Path
    project: Path
    run_root: Path
    notes: list[str] = field(default_factory=list)
    repo: "Repo | None" = None

    @classmethod
    def create(cls, work_root: Path, case_id: str, repo: "Repo | None" = None) -> "Sandbox":
        safe = case_id.replace(".", "-").replace("/", "-")
        root = Path(work_root) / safe
        if root.exists():
            shutil.rmtree(root)
        project = root / "project"
        run_root = root / "run"
        project.mkdir(parents=True)
        return cls(root=root, project=project, run_root=run_root, repo=repo)

    # ---------------------------------------------------------------- helpers
    def path(self, relative: str) -> Path:
        return self.project / relative

    def write(self, relative: str, text: str) -> Path:
        path = self.path(relative)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def append(self, relative: str, text: str) -> Path:
        path = self.path(relative)
        path.write_text(path.read_text(encoding="utf-8") + text, encoding="utf-8")
        return path

    def read(self, relative: str) -> str:
        return self.path(relative).read_text(encoding="utf-8")

    def exists(self, relative: str) -> bool:
        return self.path(relative).is_file()

    def sha256(self, relative: str) -> str:
        return hashlib.sha256(self.path(relative).read_bytes()).hexdigest()

    def state(self) -> dict:
        return json.loads((self.run_root / "ariadne-run.json").read_text(encoding="utf-8"))

    def packets(self) -> list[dict]:
        return self.state().get("packets", [])

    def current_packet(self) -> Path:
        entries = self.packets()
        if not entries:
            raise AssertionError("no packet prepared")
        return Path(entries[-1]["path"])

    def manifest(self) -> dict:
        return json.loads((self.current_packet() / "manifest.json").read_text(encoding="utf-8"))

    def packet_text(self) -> str:
        return (self.current_packet() / "packet.txt").read_text(encoding="utf-8")

    def telemetry(self) -> list[dict]:
        path = self.run_root / "worker-telemetry.jsonl"
        if not path.is_file():
            return []
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]

    def operations_log(self) -> str:
        path = self.run_root / "OPERATIONS.md"
        return path.read_text(encoding="utf-8") if path.is_file() else ""

    def rel_root(self, path: Path) -> str:
        try:
            return str(Path(path).resolve().relative_to(self.root.resolve()))
        except ValueError:
            return str(path)
