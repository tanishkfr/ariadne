#!/usr/bin/env python3
"""Prepare and verify paste-ready Ariadne stage packets.

This is transport tooling, not a policy owner. Canonical prompts, policies,
templates, and project documents remain the sources recorded in manifest.json.

Examples:
  python scripts/prepare-stage.py prepare --stage S1 --project ../project \
      --output ../runs/P1-S1 --request-file brief.txt
  python scripts/prepare-stage.py prepare --stage S3 --project ../project \
      --output ../runs/P1-S3 --parent ../runs/P1-S1 \
      --motion yes --assets no
  python scripts/prepare-stage.py verify --packet-dir ../runs/P1-S3
  python scripts/prepare-stage.py --self-test
"""

from __future__ import annotations

import argparse
import contextlib
import copy
import fnmatch
import hashlib
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import uuid
from pathlib import Path


# Installed runtimes are immutable and hash-verified. Loading the optional
# reasoner helper must not create a file outside the release manifest.
sys.dont_write_bytecode = True


ROOT = Path(__file__).resolve().parent.parent
SCHEMA_VERSION = 1
PACKET_NAME = "packet.txt"
MANIFEST_NAME = "manifest.json"
RECORD_NAME = "continuation.md"
WORKER_ROLES = ("bulk", "strong", "senior-reasoning")
MAX_ROUTINE_REPAIRS = 2
WORKER_VALIDATION_SCHEMA = 1
VALIDATION_COMMAND_LIMIT = 8
WRITING_INTENTS = (
    "CREATIVE", "ACADEMIC", "SCIENTIFIC", "HUMAN-DRAFT TRANSFORMATION", "SOCIAL"
)
WRITING_GUIDANCE = {
    "CREATIVE": "skills/writing-creative.md",
    "ACADEMIC": "skills/writing-academic.md",
    "SCIENTIFIC": "skills/writing-scientific.md",
    "HUMAN-DRAFT TRANSFORMATION": "skills/writing-transformation.md",
}


def load_reasoners():
    path = ROOT / "scripts" / "reasoners.py"
    spec = __import__("importlib.util").util.spec_from_file_location(
        "ariadne_reasoners", path
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("Ariadne reasoner helper could not be loaded")
    module = __import__("importlib.util").util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


REASONERS = load_reasoners()


STAGES = {
    "S1": {
        "prompt": "prompts/project-start.md",
        "block": 0,
        "project_inputs": [],
        "optional_project_inputs": [],
        "canonical_inputs": ["skills/intake.md"],
        "conditional_inputs": [],
        "allowed_parents": ["S1"],
        "forbidden_inputs": [],
        "provider": "codex",
    },
    "S2": {
        "prompt": "prompts/research.md",
        "block": 0,
        "project_inputs": [],
        "optional_project_inputs": [".ariadne/creative-evidence.json"],
        "canonical_inputs": ["RESEARCH-POLICY.md", "PRIVACY-POLICY.md", "templates/RESEARCH.md"],
        "conditional_inputs": [],
        "allowed_parents": ["S1", "S2"],
        "forbidden_inputs": ["unrelated PROJECT.md content", "design context", "source code"],
        "provider": "codex",
        "derived_from_project": ["blocking open questions"],
    },
    "S3": {
        "prompt": "prompts/design-direction.md",
        "block": 0,
        "project_inputs": ["PROJECT.md"],
        "optional_project_inputs": [".ariadne/creative-evidence.json"],
        "canonical_inputs": [
            "DESIGN-TASTE.md", "PRIVACY-POLICY.md", "templates/DESIGN.md",
            "skills/design-direction.md",
        ],
        "conditional_inputs": [
            "project:RESEARCH.md",
            "canonical:DESIGN-MOTION.md",
            "canonical:DESIGN-ASSETS.md",
            "selected-skill:skills/reference-analysis.md",
            "selected-skill:skills/component-research.md",
            "selected-capability-registry:references/capabilities.json",
        ],
        "allowed_parents": ["S1", "S2", "S3"],
        "forbidden_inputs": ["source code", "build history"],
        "provider": "codex",
    },
    "S4A": {
        "prompt": "prompts/build-kickoff.md",
        "block": 0,
        "project_inputs": ["PROJECT.md", "DESIGN.md", "AGENTS.md"],
        "optional_project_inputs": [],
        "canonical_inputs": ["templates/HANDOFF.md"],
        "conditional_inputs": [],
        "allowed_parents": ["S3", "S4A"],
        "forbidden_inputs": ["Part B", "QA-POLICY.md", "templates/QA.md"],
        "provider": "codex",
    },
    "S4B": {
        "prompt": "prompts/build-kickoff.md",
        "block": 1,
        "project_inputs": [
            "HANDOFF.md", "DESIGN.md", "AGENTS.md",
            ".ariadne/creative-operations.json",
        ],
        "optional_project_inputs": [],
        "canonical_inputs": [
            "QA-POLICY.md",
            "templates/QA.md",
            "templates/RETURN-HANDOFF.md",
            "skills/visual-qa.md",
        ],
        "conditional_inputs": [],
        "allowed_parents": ["S4A", "S4B"],
        "forbidden_inputs": ["earlier reasoning conversation"],
        "provider": "implementation-worker",
    },
    "S5": {
        "prompt": "prompts/project-review.md",
        "block": 0,
        "project_inputs": [],
        "optional_project_inputs": [],
        "canonical_inputs": ["EVALUATION-RUBRICS.md"],
        "conditional_inputs": [],
        "allowed_parents": ["S4B", "S5"],
        "forbidden_inputs": [
            "PROJECT.md",
            "DESIGN.md",
            "HANDOFF.md",
            "AGENTS.md",
            "QA.md",
            "source code",
            "build history",
        ],
        "provider": "codex",
        "derived_from_project": ["intent", "criteria", "accepted patterns"],
    },
    "S6": {
        "prompt": "prompts/retrospective.md",
        "block": 0,
        "project_inputs": ["PROJECT.md", "QA.md", "AGENTS.md"],
        "optional_project_inputs": [],
        "canonical_inputs": ["templates/RETROSPECTIVE.md"],
        "conditional_inputs": [],
        "allowed_parents": ["S5", "S6"],
        "forbidden_inputs": ["source code", "old conversations"],
        "provider": "codex",
    },
}


class PacketError(RuntimeError):
    pass


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def sha256_text(text: str) -> str:
    return sha256_bytes(text.encode("utf-8"))


def is_within(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def git_head() -> str:
    release = ROOT / "RELEASE-MANIFEST.json"
    if release.is_file():
        try:
            value = json.loads(read(release))
            source_commit = str(value.get("source_commit", "")).strip()
            if source_commit:
                return source_commit
        except (OSError, json.JSONDecodeError):
            pass
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True
    )
    return result.stdout.strip() if result.returncode == 0 else "unknown"


def fenced_blocks(text: str) -> list[str]:
    return re.findall(r"(?ms)^```[^\r\n]*\r?\n(.*?)^```\s*$", text)


def prompt_block(stage: str) -> tuple[str, Path]:
    spec = STAGES[stage]
    path = ROOT / spec["prompt"]
    blocks = fenced_blocks(read(path))
    index = spec["block"]
    if len(blocks) <= index:
        raise PacketError(f"{spec['prompt']} has no fenced block {index + 1}")
    return blocks[index].strip(), path


def markdown_section(text: str, heading: str) -> str:
    match = re.search(
        rf"(?ms)^##\s+{re.escape(heading)}\s*$\r?\n(.*?)(?=^##\s|\Z)", text
    )
    return match.group(1).strip() if match else ""


def markdown_subsection(text: str, heading: str) -> str:
    match = re.search(
        rf"(?ms)^###\s+{re.escape(heading)}\s*$\r?\n(.*?)(?=^###\s|\Z)", text
    )
    return match.group(1).strip() if match else ""


def markdown_table_rows(section: str) -> list[list[str]]:
    rows = []
    for raw in section.splitlines():
        if not raw.lstrip().startswith("|") or re.match(r"^\s*\|?\s*:?-{3,}", raw):
            continue
        cells = [cell.strip().replace("\\|", "|") for cell in re.split(r"(?<!\\)\|", raw.strip().strip("|"))]
        if cells and not all(not cell for cell in cells):
            rows.append(cells)
    return rows


def bold_field(section: str, label: str) -> str:
    match = re.search(rf"(?im)^\*\*{re.escape(label)}:\*\*\s*(.+?)\s*$", section)
    return match.group(1).strip() if match else ""


def safe_validation_argv(command: str) -> tuple[list[str] | None, str | None]:
    """Return an argv for a bounded read/check command, never a shell command."""
    value = command.strip().strip("`").strip()
    if not value:
        return None, "validation command is empty"
    if re.search(r"[;&|><`$()\r\n]", value):
        return None, "validation command contains shell control syntax"
    try:
        argv = shlex.split(value, posix=True)
    except ValueError as exc:
        return None, f"validation command has invalid quoting: {exc}"
    if not argv:
        return None, "validation command is empty"
    executable = Path(argv[0]).name.lower()
    if executable.endswith((".cmd", ".exe", ".bat")):
        executable = Path(executable).stem
    blocked_tokens = {"-c", "--command", "--dir", "-c", "--cwd", "--prefix", "-C", "--rootdir"}
    if any(token in blocked_tokens or token.startswith(("--rootdir=", "--cwd=", "--prefix=")) for token in argv[1:]):
        return None, "validation command may not redirect execution or run arbitrary code"

    if executable in ("pnpm", "npm", "yarn", "bun"):
        args = argv[1:]
        if args and args[0] == "run":
            args = args[1:]
        if not args or args[0] not in {"build", "test", "lint", "typecheck", "check", "validate", "verify", "tsc"}:
            return None, "package-manager validation is limited to build/test/lint/typecheck/check/validate/verify"
        return argv, None
    if executable in ("pytest", "vitest", "playwright", "eslint", "tsc"):
        return argv, None
    if executable in ("python", "python3", "py") or executable.startswith("python3."):
        python_args = argv[1:]
        if executable == "py" and python_args and re.fullmatch(r"-\d+(?:\.\d+)?(?:-32)?", python_args[0]):
            python_args = python_args[1:]
        if len(python_args) < 2 or python_args[0] != "-m" or python_args[1] not in {"pytest", "unittest", "compileall", "py_compile"}:
            return None, "Python validation must use pytest, unittest, compileall, or py_compile modules"
        return argv, None
    if executable == "git":
        if len(argv) < 2 or argv[1] not in {"status", "diff"}:
            return None, "git validation is limited to status and diff checks"
        if argv[1] == "diff" and not any(token in {"--check", "--name-only", "--stat"} for token in argv[2:]):
            return None, "git diff validation must request --check, --name-only, or --stat"
        return argv, None
    if executable == "cargo":
        if len(argv) < 2 or argv[1] not in {"test", "check", "clippy"}:
            return None, "cargo validation is limited to test/check/clippy"
        return argv, None
    if executable == "go":
        if len(argv) < 2 or argv[1] != "test":
            return None, "go validation is limited to test"
        return argv, None
    if executable == "dotnet":
        if len(argv) < 2 or argv[1] not in {"test", "build"}:
            return None, "dotnet validation is limited to test/build"
        return argv, None
    if executable == "make":
        targets = [token for token in argv[1:] if not token.startswith("-")]
        if not targets or any(target not in {"build", "test", "check", "lint", "typecheck", "validate"} for target in targets):
            return None, "make validation is limited to build/test/check/lint/typecheck/validate"
        return argv, None
    if executable == "node" and "--check" in argv[1:]:
        return argv, None
    return None, f"unsupported validation executable: {executable}"


def worker_contract(handoff_text: str) -> dict:
    section = markdown_section(handoff_text, "Worker execution contract")
    scope = markdown_table_rows(markdown_subsection(section, "Permitted files and systems"))
    validation = markdown_table_rows(markdown_section(handoff_text, "Validation commands"))
    return {
        "section": section,
        "worker_role": bold_field(section, "Worker role").strip("`").strip().lower(),
        "objective": bold_field(section, "Objective"),
        "relevant_context": bold_field(section, "Relevant context"),
        "invariants": bold_field(section, "Invariants"),
        "permitted_actions": bold_field(section, "Permitted actions"),
        "prohibited_actions": bold_field(section, "Prohibited actions"),
        "stop_conditions": bold_field(section, "Stop conditions"),
        "escalation_conditions": bold_field(section, "Escalation conditions"),
        "lifecycle": bold_field(section, "Lifecycle"),
        "routine_repair_limit": bold_field(section, "Routine repair limit"),
        "scope_rows": scope[1:] if scope and scope[0][0].lower() in ("path / glob", "path", "file / glob") else scope,
        "validation_rows": validation[1:] if validation and validation[0][0].lower() in ("check", "id") else validation,
    }


def worker_contract_problems(handoff_text: str) -> list[str]:
    contract = worker_contract(handoff_text)
    problems = []
    if not contract["section"]:
        return ["HANDOFF.md is missing the Worker execution contract section"]
    required_fields = (
        "objective", "relevant_context", "invariants", "permitted_actions",
        "prohibited_actions", "stop_conditions", "escalation_conditions",
        "lifecycle", "routine_repair_limit",
    )
    for field in required_fields:
        value = contract[field]
        if not value or re.search(r"<[^>]+>|not yet recorded|not decided", value, re.I):
            problems.append(f"worker contract has an incomplete {field.replace('_', ' ')}")
    if contract["worker_role"] not in WORKER_ROLES:
        problems.append(f"worker contract has unsupported Worker role: {contract['worker_role'] or 'missing'}")
    try:
        repair_limit = int(contract["routine_repair_limit"].strip("` "))
    except ValueError:
        repair_limit = -1
    if repair_limit < 0 or repair_limit > MAX_ROUTINE_REPAIRS:
        problems.append(f"worker contract routine repair limit must be 0-{MAX_ROUTINE_REPAIRS}")
    lifecycle = contract["lifecycle"].lower()
    for token in ("baseline", "implementation", "validation", "repair", "result", "checkpoint"):
        if token not in lifecycle:
            problems.append(f"worker contract lifecycle omits {token}")
    for token in ("read", "edit", "test"):
        if token not in contract["permitted_actions"].lower():
            problems.append(f"worker contract permitted actions omit {token}")
    for token in ("push", "reset", "secret", ".env", "deploy"):
        if token not in contract["prohibited_actions"].lower():
            problems.append(f"worker contract prohibited actions omit {token}")
    for token in ("conflict", "invariant", "out-of-scope", "budget"):
        if token not in contract["stop_conditions"].lower():
            problems.append(f"worker contract stop conditions omit {token}")
    for token in ("repeated", "architecture", "high-risk"):
        if token not in contract["escalation_conditions"].lower():
            problems.append(f"worker contract escalation conditions omit {token}")

    scope_rows = contract["scope_rows"]
    if not scope_rows:
        problems.append("worker contract has no permitted file/system rows")
    for row in scope_rows:
        if len(row) < 3 or not row[0] or re.search(r"<[^>]+>", " ".join(row)):
            problems.append("worker contract has an incomplete permitted file/system row")
            continue
        path = row[0].strip("`").replace("\\", "/")
        if path in ("*", "**", "**/*", ".", "./") or Path(path).is_absolute() or ".." in Path(path).parts:
            problems.append(f"worker contract scope is too broad or unsafe: {path}")
        if worker_sensitive_path(path):
            problems.append(f"worker contract may not permit sensitive path: {path}")

    validation_rows = contract["validation_rows"]
    if not validation_rows:
        problems.append("worker contract has no validation commands")
    elif len(validation_rows) > VALIDATION_COMMAND_LIMIT:
        problems.append(f"worker contract has more than {VALIDATION_COMMAND_LIMIT} validation commands")
    required_validation = False
    for row in validation_rows:
        if len(row) < 4 or not row[0] or not row[1] or re.search(r"<[^>]+>", " ".join(row)):
            problems.append("worker contract has an incomplete validation command row")
            continue
        argv, error = safe_validation_argv(row[1])
        if error:
            problems.append(f"unsafe validation command {row[0]}: {error}")
        required_value = row[2].strip().lower()
        if required_value in ("yes", "y", "true", "required"):
            required_validation = True
        elif required_value not in ("no", "n", "false", "optional"):
            problems.append(f"validation command {row[0]} has invalid required value: {row[2]}")
    if validation_rows and not required_validation:
        problems.append("worker contract needs at least one required validation command")
    return problems


def validation_commands(handoff_text: str) -> list[dict]:
    contract = worker_contract(handoff_text)
    commands = []
    for row in contract["validation_rows"]:
        if len(row) < 4:
            continue
        argv, error = safe_validation_argv(row[1])
        commands.append({
            "id": re.sub(r"[^a-z0-9]+", "-", row[0].strip().lower()).strip("-") or "check",
            "check": row[0].strip(),
            "command": row[1].strip().strip("`"),
            "required": row[2].strip().lower() in ("yes", "y", "true", "required"),
            "expected": row[3].strip(),
            "argv": argv,
            "error": error,
        })
    return commands


def worker_sensitive_path(path: str) -> bool:
    normalised = path.replace("\\", "/").lower().strip("/")
    name = normalised.rsplit("/", 1)[-1]
    return (
        name == ".env" or name.startswith(".env.") or name in {"id_rsa", "credentials.json"}
        or name.endswith((".pem", ".key", ".p12", ".pfx")) or "secret" in name or "credential" in name
    )


def worker_path_matches(path: str, pattern: str) -> bool:
    path = path.replace("\\", "/").lstrip("./")
    pattern = pattern.replace("\\", "/").lstrip("./")
    return fnmatch.fnmatchcase(path, pattern) or (
        pattern.endswith("/**") and path.startswith(pattern[:-3].rstrip("/") + "/")
    )


def project_git_snapshot(project: Path) -> dict:
    project = project.resolve()
    head_result = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=project, capture_output=True, text=True
    )
    status_result = subprocess.run(
        ["git", "status", "--porcelain=v1", "--untracked-files=all"],
        cwd=project, capture_output=True, text=True,
    )
    if status_result.returncode != 0:
        return {
            "state": "unknown", "head": head_result.stdout.strip() or "unknown",
            "entries": [], "error": status_result.stderr.strip() or "git status failed",
        }
    entries_by_path = {}

    def record_entry(relative: str, status: str, candidate: Path) -> None:
        exists = candidate.is_file()
        sensitive = worker_sensitive_path(relative)
        entry = {
            "path": relative,
            "status": status,
            "exists": exists,
            # Never read a sensitive file merely to fingerprint repository scope.
            "sha256": sha256_file(candidate) if exists and not sensitive else None,
        }
        if sensitive and exists:
            try:
                stat = candidate.stat()
                entry.update({"size": stat.st_size, "mtime_ns": stat.st_mtime_ns})
            except OSError:
                entry.update({"size": None, "mtime_ns": None})
        entries_by_path[relative] = entry

    for raw in status_result.stdout.splitlines():
        if len(raw) < 4:
            continue
        status = raw[:2]
        value = raw[3:].strip().strip('"')
        paths = [item.strip().strip('"') for item in value.split(" -> ")] if " -> " in value else [value]
        for relative in paths:
            relative = relative.replace("\\", "/")
            record_entry(relative, status, project / relative)
    # Git intentionally hides ignored files. Track root-level environment and
    # credential files by metadata so a worker cannot silently add one while
    # Ariadne avoids reading its contents.
    try:
        for candidate in project.iterdir():
            if candidate.is_file() and worker_sensitive_path(candidate.name):
                relative = candidate.name.replace("\\", "/")
                if relative not in entries_by_path:
                    record_entry(relative, "ignored", candidate)
    except OSError:
        return {
            "state": "unknown", "head": head_result.stdout.strip() or "unknown",
            "entries": [], "error": "could not inspect sensitive root files",
        }
    entries = [entries_by_path[path] for path in sorted(entries_by_path)]
    return {
        "state": "dirty" if entries else "clean",
        "head": head_result.stdout.strip() or "unborn",
        "entries": entries,
    }


def worker_scope_check(
    baseline: dict,
    current: dict,
    patterns: list[str],
    project: Path | None = None,
) -> dict:
    if baseline.get("state") == "unknown" or current.get("state") == "unknown":
        return {"status": "repository-conflict", "changed": [], "outside": [], "sensitive": [], "immutable": [], "head_changed": False}
    baseline_entries = {item.get("path"): item for item in baseline.get("entries", [])}
    current_entries = {item.get("path"): item for item in current.get("entries", [])}
    changed = []
    for path in sorted(set(baseline_entries) | set(current_entries)):
        if baseline_entries.get(path) != current_entries.get(path):
            changed.append(path)
    head_changed = (
        baseline.get("head") not in (None, "", "unknown")
        and current.get("head") not in (None, "", "unknown")
        and baseline.get("head") != current.get("head")
    )
    committed = []
    commit_error = None
    if head_changed and project is not None:
        comparison = subprocess.run(
            ["git", "diff", "--name-only", baseline.get("head", ""), current.get("head", "")],
            cwd=project, capture_output=True, text=True,
        )
        if comparison.returncode == 0:
            committed = [line.strip().replace("\\", "/") for line in comparison.stdout.splitlines() if line.strip()]
        else:
            commit_error = comparison.stderr.strip() or "could not inspect committed changes"
    all_changed = sorted(set(changed) | set(committed))
    sensitive = [path for path in all_changed if worker_sensitive_path(path)]
    immutable = [path for path in all_changed if path.replace("\\", "/").lower() in {"handoff.md", "design.md"}]
    outside = [
        path for path in all_changed
        if not any(worker_path_matches(path, pattern) for pattern in patterns)
    ]
    if commit_error or immutable:
        status = "repository-conflict"
    elif sensitive:
        status = "dangerous-action"
    elif outside:
        status = "out-of-scope"
    else:
        status = "within-contract"
    return {
        "status": status,
        "changed": all_changed,
        "committed": committed,
        "outside": outside,
        "sensitive": sensitive,
        "immutable": immutable,
        "head_changed": head_changed,
        "commit_error": commit_error,
    }


def worker_validation_problems(value: dict, packet_id: str | None = None) -> list[str]:
    problems = []
    if not isinstance(value, dict):
        return ["worker validation evidence is not an object"]
    if value.get("schema_version") != WORKER_VALIDATION_SCHEMA:
        problems.append("worker validation evidence has wrong schema version")
    if value.get("kind") != "worker-validation":
        problems.append("worker validation evidence has wrong kind")
    if packet_id and value.get("packet_id") != packet_id:
        problems.append("worker validation evidence has wrong packet ID")
    if value.get("stage") != "S4B":
        problems.append("worker validation evidence has wrong stage")
    if value.get("status") not in ("passed", "failed", "blocked"):
        problems.append("worker validation evidence has invalid status")
    if value.get("independent") is not True:
        problems.append("worker validation evidence is not marked independent")
    scope = value.get("scope") if isinstance(value.get("scope"), dict) else {}
    if scope.get("status") not in (
        "within-contract", "out-of-scope", "dangerous-action", "repository-conflict", "not-run"
    ):
        problems.append("worker validation evidence has invalid scope status")
    if value.get("failure_kind") not in (
        "none", "routine", "contract", "out-of-scope", "dangerous-action",
        "repository-conflict", "worker-blocked", "validation-timeout", "validation-command",
    ):
        problems.append("worker validation evidence has invalid failure kind")
    commands = value.get("commands")
    if not isinstance(commands, list) or len(commands) > VALIDATION_COMMAND_LIMIT:
        problems.append("worker validation evidence has an invalid command list")
    else:
        for command in commands:
            if not isinstance(command, dict) or not command.get("id") or command.get("status") not in ("passed", "failed", "not-run"):
                problems.append("worker validation evidence has an invalid command result")
    for field in ("usage", "cost"):
        if field not in value:
            problems.append(f"worker validation evidence is missing {field}; unknown must be explicit")
    return problems


def meaningful_lines(section: str) -> list[str]:
    lines = []
    for raw in section.splitlines():
        line = raw.strip()
        if not line or line.startswith((">", "#", "|")):
            continue
        if "<>" in line or re.search(r"<[^>]+>", line):
            continue
        lines.append(line)
    return lines


def extract_review_values(project_text: str) -> dict[str, str]:
    goal_lines = meaningful_lines(markdown_section(project_text, "Goal"))
    if not goal_lines:
        raise PacketError("PROJECT.md has no filled ## Goal for S5 intent")
    intent = " ".join(goal_lines)

    criteria_section = markdown_section(project_text, "Success criteria")
    criteria = []
    for line in criteria_section.splitlines():
        match = re.match(r"^\s*(\d+)\.\s+(.+?)\s*$", line)
        if match and "<>" not in match.group(2):
            criteria.append(f"{match.group(1)}. {match.group(2)}")
    if not criteria:
        raise PacketError("PROJECT.md has no filled success criteria for S5")

    accepted_section = markdown_section(project_text, "Accepted patterns")
    accepted = []
    for line in accepted_section.splitlines():
        if not line.lstrip().startswith("|") or "---" in line:
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) < 3 or cells[0].lower() == "pattern" or "<" in cells[0]:
            continue
        accepted.append(f"- {cells[0]} — {cells[1]} ({cells[2]})")

    return {
        "intent": intent,
        "criteria": "\n".join(criteria),
        "accepted": "\n".join(accepted) if accepted else "none",
    }


def extract_blocking_questions(project_text: str) -> str:
    section = markdown_section(project_text, "Open questions")
    questions = []
    for line in section.splitlines():
        if not line.lstrip().startswith("|") or "---" in line:
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) < 4 or cells[0] == "#" or "<" in cells[1]:
            continue
        if cells[3].lower() in ("yes", "y", "blocking"):
            questions.append(f"- {cells[1]} (needed by {cells[2]})")
    if not questions:
        raise PacketError("S2 requires at least one blocking PROJECT.md open question")
    return "\n".join(questions)


RETURN_HANDOFF_HEADINGS = [
    "What was built",
    "Files changed",
    "Architecture decisions",
    "Design deviations",
    "Dependencies",
    "Tests",
    "Evidence",
    "Worker validation",
    "Safety and scope",
    "Known issues",
    "Incomplete work",
    "Accessibility and performance",
    "Assumptions",
    "Next inspection",
]


def return_handoff_problems(text: str) -> list[str]:
    """Validate continuation evidence without treating it as a transcript."""
    problems = []
    if not text.strip():
        return ["return handoff is empty"]
    for heading in RETURN_HANDOFF_HEADINGS:
        matches = re.findall(rf"(?im)^##\s+{re.escape(heading)}\s*$", text)
        if not matches:
            problems.append(f"return handoff missing section: {heading}")
        elif len(matches) > 1:
            problems.append(f"return handoff duplicates section: {heading}")
    for field in (
        "Status", "Task ID", "Worker role", "Provider", "Model", "Effort", "Started", "Ended", "Usage", "Cost",
        "Scope status", "Unexpected actions or conflicts",
    ):
        matches = re.findall(rf"(?im)^\*\*{field}:\*\*\s*(.+?)\s*$", text)
        if len(matches) != 1 or re.search(r"<[^>]+>|\bcomplete / partial / blocked\b", matches[0] if matches else ""):
            problems.append(f"return handoff has unfilled field: {field}")
    status = re.search(r"(?im)^\*\*Status:\*\*\s*(.+?)\s*$", text)
    if status and status.group(1).strip().lower() not in ("complete", "partial", "blocked"):
        problems.append("return handoff Status must be complete, partial, or blocked")
    worker_role = re.search(r"(?im)^\*\*Worker role:\*\*\s*(.+?)\s*$", text)
    if worker_role and worker_role.group(1).strip().lower() not in WORKER_ROLES:
        problems.append("return handoff Worker role is unsupported")
    scope_status = re.search(r"(?im)^\*\*Scope status:\*\*\s*(.+?)\s*$", text)
    if scope_status and scope_status.group(1).strip().lower() not in (
        "within-contract", "out-of-scope", "dangerous-action", "repository-conflict", "not checked"
    ):
        problems.append("return handoff Scope status is unsupported")
    return problems


def return_handoff_status(text: str) -> str:
    match = re.search(r"(?im)^\*\*Status:\*\*\s*(.+?)\s*$", text)
    return match.group(1).strip().lower() if match else ""


def compact_worker_text(value: object, limit: int = 800) -> str:
    text = re.sub(r"\s+", " ", str(value or "").strip())
    if not text:
        return "not recorded"
    return text if len(text) <= limit else text[: limit - 3].rstrip() + "..."


def worker_retry_context(
    parent: dict | None, evidence_path: Path | None, evidence_kind: str | None
) -> dict | None:
    """Carry only bounded repair clues forward; never replay an old transcript."""
    if (
        not parent
        or parent.get("stage") != "S4B"
        or evidence_path is None
        or not evidence_path.is_file()
    ):
        return None
    context = {
        "parent_task_id": parent.get("packet_id", "unknown"),
        "source": evidence_kind or "unknown",
    }
    if evidence_kind == "worker-validation":
        try:
            validation = json.loads(read(evidence_path))
        except (OSError, json.JSONDecodeError):
            return {**context, "status": "unreadable", "failure_reason": "prior validation evidence could not be read"}
        scope = validation.get("scope") if isinstance(validation.get("scope"), dict) else {}
        changed_paths = scope.get("changed") if isinstance(scope.get("changed"), list) else []
        outside_paths = scope.get("outside") if isinstance(scope.get("outside"), list) else []
        failed_checks = []
        for command in validation.get("commands", []):
            if not isinstance(command, dict) or command.get("status") == "passed":
                continue
            detail = command.get("error") or command.get("returncode") or command.get("status")
            failed_checks.append(
                compact_worker_text(f"{command.get('id', 'check')}: {detail}", 300)
            )
        return {
            **context,
            "status": validation.get("status", "unknown"),
            "failure_kind": validation.get("failure_kind", "unknown"),
            "failure_reason": compact_worker_text(validation.get("failure_reason")),
            "failed_checks": failed_checks[:VALIDATION_COMMAND_LIMIT],
            "changed": [compact_worker_text(path, 240) for path in changed_paths[:20]],
            "outside": [compact_worker_text(path, 240) for path in outside_paths[:20]],
        }
    if evidence_kind == "structured-return-handoff":
        try:
            text = read(evidence_path)
        except OSError:
            return {**context, "status": "unreadable", "failure_reason": "prior return evidence could not be read"}
        return {
            **context,
            "status": return_handoff_status(text) or "unknown",
            "known_issues": compact_worker_text(markdown_section(text, "Known issues")),
            "incomplete_work": compact_worker_text(markdown_section(text, "Incomplete work")),
            "next_inspection": compact_worker_text(markdown_section(text, "Next inspection")),
            "safety_and_scope": compact_worker_text(markdown_section(text, "Safety and scope")),
        }
    return {
        **context,
        "status": "transcript-only",
        "note": "A prior transcript exists, but its conversation is intentionally not replayed; inspect the current repository and packet.",
    }


def stage_result_problems(path: Path, parent: dict) -> list[str]:
    """Validate structural evidence without pretending it is a transcript."""
    try:
        result = json.loads(read(path))
    except (json.JSONDecodeError, OSError) as exc:
        return [f"invalid structural stage result: {exc}"]
    problems = []
    if result.get("schema_version") != 1:
        problems.append("structural stage result has wrong schema version")
    if result.get("packet_id") != parent.get("packet_id"):
        problems.append("structural stage result has wrong packet ID")
    if result.get("stage") != parent.get("stage"):
        problems.append("structural stage result has wrong stage")
    if result.get("status") != "complete":
        problems.append("structural stage result is not complete")
    files = result.get("files")
    if not isinstance(files, list) or not files:
        problems.append("structural stage result has no output files")
    else:
        for entry in files:
            file_path = Path(entry.get("path", ""))
            if not file_path.is_file():
                problems.append(f"structural stage output missing: {file_path}")
            elif sha256_file(file_path) != entry.get("sha256"):
                problems.append(f"structural stage output changed: {file_path}")
    return problems


def replace_line(block: str, label: str, value: str) -> str:
    pattern = rf"(?m)^{re.escape(label)}\s*.*$"
    replacement = f"{label} {value}"
    if not re.search(pattern, block):
        raise PacketError(f"prompt block is missing parameter line: {label}")
    return re.sub(pattern, lambda _m: replacement, block, count=1)


def parameterise_prompt(stage: str, block: str, args: argparse.Namespace) -> tuple[str, list[dict]]:
    derived = []
    if stage == "S1":
        request = args.request
        if args.request_file:
            request = read(Path(args.request_file).resolve()).strip()
        if not request:
            raise PacketError("S1 requires --request or --request-file")
        if getattr(args, "adopt_existing", False):
            existing = sorted(
                item.name for item in Path(args.project).resolve().iterdir()
                if item.name not in {".git", ".gitignore"}
            )
            request = (
                request.strip()
                + "\n\nARIADNE EXISTING-PROJECT ADOPTION CONTEXT\n"
                + "This is an opt-in adoption of an existing project, not a fresh build. "
                + "Inspect the live project repository read-only before asking questions. "
                + "Preserve current behaviour and every pre-existing file. Do not rewrite, "
                + "delete, rename, or implement anything during S1. Create only PROJECT.md "
                + "and AGENTS.md after the intake is resolved. Existing top-level entries at "
                + "packet preparation: "
                + (", ".join(existing) if existing else "none")
                + "."
            )
        if "MY REQUEST:" not in block:
            raise PacketError("S1 prompt has no MY REQUEST parameter")
        block = re.sub(
            r"(?ms)^MY REQUEST:.*\Z", lambda _m: f"MY REQUEST: {request.strip()}", block
        )
    elif stage == "S2":
        project_path = Path(args.project).resolve() / "PROJECT.md"
        if not project_path.is_file():
            raise PacketError("S2 requires PROJECT.md containing blocking open questions")
        questions = extract_blocking_questions(read(project_path))
        block = replace_line(block, "QUESTIONS:", "\n" + questions)
        derived.append(
            {
                "label": "S2 blocking questions extracted from PROJECT.md",
                "path": str(project_path),
                "kind": "project-derived",
                "source_sha256": sha256_file(project_path),
                "content_sha256": sha256_text(read(project_path)),
                "delivered": False,
            }
        )
    elif stage == "S3":
        references = "none yet"
        references_text = getattr(args, "references_text", None)
        if args.references_file and references_text:
            raise PacketError("S3 references must come from one transport source")
        if references_text:
            references = str(references_text).strip()
            if not references:
                raise PacketError("S3 preserved references are empty")
        elif args.references_file:
            references = read(Path(args.references_file).resolve()).strip()
            if not references:
                raise PacketError("--references-file is empty")
        block = replace_line(block, "REFERENCES:", references)
    elif stage == "S5":
        if not args.target:
            raise PacketError("S5 requires --target")
        if not args.lenses:
            raise PacketError("S5 requires --lenses; lens selection is a judgement, not a transport default")
        project_path = Path(args.project).resolve() / "PROJECT.md"
        project_text = read(project_path)
        values = extract_review_values(project_text)
        block = replace_line(block, "TARGET:", args.target)
        block = replace_line(block, "INTENT:", values["intent"])
        block = replace_line(block, "CRITERIA:", "\n" + values["criteria"])
        block = replace_line(block, "ACCEPTED PATTERNS:", values["accepted"])
        block = replace_line(block, "LENSES:", args.lenses)
        derived.append(
            {
                "label": "S5 permitted values extracted from PROJECT.md",
                "path": str(project_path),
                "kind": "project-derived",
                "source_sha256": sha256_file(project_path),
                "content_sha256": sha256_text(read(project_path)),
                "delivered": False,
            }
        )
    return block, derived


def state_field(text: str, name: str) -> str:
    match = re.search(
        rf"(?m)^\|\s*\*\*{re.escape(name)}\*\*\s*\|\s*`?([^|`]+)", text
    )
    return match.group(1).strip() if match else ""


def check_project_boundary(stage: str, project: Path, adopt_existing: bool = False) -> None:
    if not project.is_dir():
        raise PacketError(f"project directory does not exist: {project}")
    if stage == "S1":
        allowed = {".git", ".gitignore"}
        unexpected = sorted(p.name for p in project.iterdir() if p.name not in allowed)
        if adopt_existing:
            owned = sorted(name for name in ("PROJECT.md", "AGENTS.md") if (project / name).exists())
            if owned:
                raise PacketError(
                    "existing project already contains Ariadne-owned entry documents: "
                    + ", ".join(owned)
                    + "; resume its run or migrate those files deliberately"
                )
            return
        if unexpected:
            raise PacketError(
                "S1 requires a fresh project containing only .git/.gitignore; "
                f"found: {unexpected}"
            )
        return

    if stage in ("S4A", "S4B"):
        design = read(project / "DESIGN.md") if (project / "DESIGN.md").exists() else ""
        agents = read(project / "AGENTS.md") if (project / "AGENTS.md").exists() else ""
        if not re.search(r"(?im)^\*\*Status:\*\*.*locked at G1", design):
            raise PacketError(f"{stage} requires DESIGN.md recorded as locked at G1")
        gate = state_field(agents, "Last gate passed")
        if not re.match(r"G[1-5]\b", gate):
            raise PacketError(f"{stage} requires AGENTS.md to record a passed gate; found {gate!r}")

    if stage == "S4B":
        handoff = project / "HANDOFF.md"
        if not handoff.exists():
            raise PacketError("S4B requires HANDOFF.md produced by S4A")
        if re.search(r"G1 approved:\s*<", read(handoff)):
            raise PacketError("HANDOFF.md still has an unfilled G1 approval field")

    if stage == "S5":
        qa = project / "QA.md"
        if not qa.exists():
            raise PacketError("S5 requires QA.md with S4B mechanical evidence")
        mechanical = markdown_section(read(qa), "Mechanical")
        filled_rows = re.findall(r"(?im)^\|\s*\d+\s*\|.*\|\s*(?:pass|fail|not run)\s*\|", mechanical)
        if not filled_rows:
            raise PacketError("QA.md has no recorded pass/fail/not run mechanical evidence")

    if stage == "S6":
        qa = project / "QA.md"
        if not qa.exists():
            raise PacketError("S6 requires completed QA.md")
        judgement = markdown_section(read(qa), "Judgement")
        if not re.search(r"(?i)\b(verdict|score|judgement)\b", judgement):
            raise PacketError("QA.md has no recognisable independent judgement evidence")


def source_entry(label: str, path: Path, kind: str, content: str, delivered: bool = True) -> dict:
    delivered_content = content.rstrip()
    return {
        "label": label,
        "path": (
            str(path.resolve())
            if kind.startswith(("project", "continuation", "writing"))
            else path.relative_to(ROOT).as_posix()
        ),
        "kind": kind,
        "source_sha256": sha256_file(path),
        # `content_sha256` is the backward-compatible, newline-normalised hash
        # of the complete source file. Older runtimes use it when raw checkout
        # bytes differ only by line endings.
        "content_sha256": sha256_text(read(path)),
        "delivered_content_sha256": sha256_text(delivered_content),
        "delivered": delivered,
        "content": delivered_content,
    }


def writing_source(label: str, path: Path, kind: str = "writing-input") -> dict:
    path = path.resolve()
    if not path.is_file() or path.stat().st_size == 0:
        raise PacketError(f"writing input is missing or empty: {path}")
    return source_entry(label, path, kind, read(path))


def writing_packet_sources(args: argparse.Namespace) -> list[dict]:
    if args.intent == "SOCIAL":
        raise PacketError("SOCIAL remains owned by the existing social/content system")
    guidance_path = ROOT / WRITING_GUIDANCE[args.intent]
    sources = [
        source_entry("writing root method", ROOT / "skills" / "writing.md", "canonical", read(ROOT / "skills" / "writing.md")),
        source_entry(f"{args.intent} writing guidance", guidance_path, "canonical", read(guidance_path)),
        writing_source("original user request", Path(args.request_file), "writing-request"),
    ]
    for index, value in enumerate(args.source_file or [], start=1):
        sources.append(writing_source(f"source material {index}", Path(value)))
    if args.intent == "HUMAN-DRAFT TRANSFORMATION" and args.phase == "draft":
        if not args.draft_file:
            raise PacketError("human-draft transformation requires --draft-file")
        sources.append(writing_source("original draft", Path(args.draft_file), "writing-original-draft"))
    if args.intent == "HUMAN-DRAFT TRANSFORMATION" and args.phase in ("review", "revise"):
        if not args.original_draft_file:
            raise PacketError(f"human-draft transformation {args.phase} packet requires --original-draft-file")
        sources.append(writing_source("original draft", Path(args.original_draft_file), "writing-original-draft"))
    if args.phase in ("review", "revise"):
        sources.append(writing_source("final writing draft", Path(args.draft_file), "writing-draft"))
    if args.phase == "revise":
        sources.append(writing_source("independent editorial review", Path(args.review_file), "writing-review"))
    return sources


def build_writing_packet(args: argparse.Namespace) -> tuple[str, list[dict]]:
    sources = writing_packet_sources(args)
    criteria = args.criteria.strip()
    if not criteria:
        raise PacketError("writing packet requires --criteria")
    phase = args.phase
    lines = [
        f"ARIADNE WRITING {phase.upper()} PACKET",
        f"Packet ID: {args.packet_id}",
        f"Provider: {args.provider}",
        f"Model: {args.model or 'not specified'}",
        f"Writing intent: {args.intent}",
        f"Workflow boundary: {'S5 independent review' if phase == 'review' else 'S4 writing work'}",
        f"Artifact kind: {'writing-review' if phase == 'review' else 'writing-revision' if phase == 'revise' else 'writing-draft'}",
        "Status: PREPARED ONLY - THE PROVIDER HAS NOT RUN",
        "",
        "EXECUTION CONTRACT",
        "Use the existing provider/session boundary. This packet proves transport, not live model execution.",
        "Return the requested writing artifact and preserve the stated evidence boundary.",
    ]
    if phase == "review":
        lines.extend([
            "",
            "INDEPENDENCE BOUNDARY",
            "Review only the request, supplied sources, final draft, intent, and criteria.",
            "Do not receive or infer drafting rationale, hidden reasoning, self-justification, or implementation history.",
            "Return PASS, REVISE, or FUNDAMENTALLY RECONSIDER with concise evidence.",
        ])
    lines.extend(["", "EVALUATION CRITERIA", criteria])
    for entry in sources:
        lines.extend(["", section_header(entry), entry["content"].rstrip(), section_footer(entry)])
    return "\n".join(lines).rstrip() + "\n", sources


def verify_writing_packet(packet_dir: Path) -> list[str]:
    packet_dir = packet_dir.resolve()
    manifest_path = packet_dir / MANIFEST_NAME
    packet_path = packet_dir / PACKET_NAME
    if not manifest_path.is_file() or not packet_path.is_file():
        return ["writing packet is missing manifest.json or packet.txt"]
    manifest = json.loads(read(manifest_path))
    packet = read(packet_path)
    problems = []
    if manifest.get("packet_kind") != "writing":
        problems.append("packet is not classified as writing")
    if manifest.get("intent") not in WRITING_INTENTS or manifest.get("intent") == "SOCIAL":
        problems.append("writing packet has an unsupported or isolated intent")
    if manifest.get("phase") not in ("draft", "review", "revise"):
        problems.append("writing packet has an unsupported phase")
    if sha256_file(packet_path) != manifest.get("packet_sha256"):
        problems.append("writing packet hash mismatch")
    if manifest.get("phase") == "review":
        if not manifest.get("independent_review"):
            problems.append("review packet is not marked independent")
        if manifest.get("excluded_inputs") != ["drafting rationale", "hidden reasoning", "implementation history"]:
            problems.append("review packet exclusion contract is incomplete")
        delivered = [item["label"] for item in manifest.get("sources", [])]
        if "original user request" not in delivered or "final writing draft" not in delivered:
            problems.append("review packet is missing request or final draft")
        if manifest.get("intent") == "HUMAN-DRAFT TRANSFORMATION" and "original draft" not in delivered:
            problems.append("transformation review packet is missing the original draft")
    for entry in manifest.get("sources", []):
        source_path = resolve_source_path(entry, manifest)
        if not source_path.is_file():
            problems.append(f"writing source missing: {entry['path']}")
            continue
        if sha256_file(source_path) != entry.get("source_sha256"):
            problems.append(f"writing source changed: {entry['path']}")
        if entry.get("delivered", True):
            if packet.count(section_header(entry)) != 1 or packet.count(section_footer(entry)) != 1:
                problems.append(f"writing source section missing or duplicated: {entry['label']}")
    return problems


def prepare_writing(args: argparse.Namespace) -> Path:
    if args.intent == "SOCIAL":
        raise PacketError("SOCIAL remains isolated in the existing social/content system")
    validate_packet_id(args.packet_id)
    output = Path(args.output).resolve()
    if output.exists():
        raise PacketError(f"refusing to overwrite existing writing packet: {output}")
    packet, sources = build_writing_packet(args)
    output.mkdir(parents=True)
    packet_path = output / PACKET_NAME
    packet_path.write_text(packet, encoding="utf-8")
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "packet_kind": "writing",
        "packet_id": args.packet_id,
        "phase": args.phase,
        "intent": args.intent,
        "provider": args.provider,
        "model": args.model or "not specified",
        "packet_file": PACKET_NAME,
        "packet_sha256": sha256_file(packet_path),
        "sources": [{key: value for key, value in entry.items() if key != "content"} for entry in sources],
        "independent_review": args.phase == "review",
        "excluded_inputs": ["drafting rationale", "hidden reasoning", "implementation history"] if args.phase == "review" else [],
        "workflow_stages": ["S4"] if args.phase in ("draft", "revise") else ["S5"],
        "live_execution": False,
    }
    (output / MANIFEST_NAME).write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (output / RECORD_NAME).write_text(
        f"# {args.packet_id} - writing {args.phase} packet\n\n"
        "**Status:** `PREPARED - NOT RUN`\n\n"
        "Packet construction proves transport only; no provider/model execution is claimed.\n",
        encoding="utf-8",
    )
    (output / "evidence").mkdir()
    (output / "evidence" / "_README.md").write_text(
        "Save the provider transcript here only after a live provider session runs.\n",
        encoding="utf-8",
    )
    problems = verify_writing_packet(output)
    if problems:
        raise PacketError("generated writing packet failed verification: " + "; ".join(problems))
    return output


def resolve_sources(stage: str, project: Path, args: argparse.Namespace) -> tuple[list[dict], list[str]]:
    spec = STAGES[stage]
    sources = []
    omitted = []

    for name in spec["project_inputs"]:
        path = project / name
        if not path.is_file():
            raise PacketError(f"{stage} required project input is missing: {name}")
        sources.append(source_entry(name, path, "project", read(path)))

    for name in spec.get("optional_project_inputs", []):
        path = project / name
        if path.is_file():
            sources.append(source_entry(name, path, "project-runtime", read(path)))
        else:
            omitted.append(f"{name} absent — legacy creative provenance remains explicitly untracked")

    for name in spec["canonical_inputs"]:
        path = ROOT / name
        if not path.is_file():
            raise PacketError(f"{stage} canonical input is missing: {name}")
        sources.append(source_entry(name, path, "canonical", read(path)))

    selected_skills = set()
    creative_path = project / ".ariadne" / "creative-evidence.json"
    if creative_path.is_file():
        try:
            creative = json.loads(read(creative_path))
            if Path(str(creative.get("project", ""))).resolve() != project.resolve():
                raise PacketError("creative evidence belongs to a different project")
            selected_skills = {
                str(item.get("name"))
                for item in creative.get("skills", [])
                if isinstance(item, dict) and item.get("selected")
            }
        except json.JSONDecodeError as exc:
            raise PacketError("creative evidence is malformed") from exc

    if stage == "S3":
        selected_sources = {
            "reference-analysis": "skills/reference-analysis.md",
            "component-research": "skills/component-research.md",
        }
        for skill_name, name in selected_sources.items():
            if skill_name in selected_skills:
                path = ROOT / name
                sources.append(source_entry(name, path, "canonical-selected-skill", read(path)))
            else:
                omitted.append(f"{name} not selected by the project creative plan")
        if "component-research" in selected_skills:
            path = ROOT / "references" / "capabilities.json"
            sources.append(source_entry(
                "references/capabilities.json", path, "canonical-selected-capability", read(path)
            ))
        else:
            omitted.append("references/capabilities.json not needed — component research was not selected")

    if stage == "S3":
        if args.motion not in ("yes", "no") or args.assets not in ("yes", "no"):
            raise PacketError("S3 requires explicit --motion yes|no and --assets yes|no")
        research = project / "RESEARCH.md"
        if research.exists():
            sources.append(source_entry("RESEARCH.md", research, "project", read(research)))
        else:
            omitted.append("RESEARCH.md absent — no S2 output to carry")
        for choice, name in ((args.motion, "DESIGN-MOTION.md"), (args.assets, "DESIGN-ASSETS.md")):
            if choice == "yes":
                path = ROOT / name
                sources.append(source_entry(name, path, "canonical", read(path)))
            else:
                omitted.append(f"{name} not triggered — explicitly declared no")
        restart_context = getattr(args, "restart_context", None)
        if restart_context:
            if not args.retry:
                raise PacketError("S3 restart context is valid only on a same-stage retry")
            path = Path(restart_context).resolve()
            if not path.is_file() or path.stat().st_size == 0:
                raise PacketError("S3 restart context is missing or empty")
            sources.append(source_entry(
                "rejected S3 direction and human restart reason",
                path,
                "continuation-restart-context",
                read(path),
            ))

    return sources, omitted


def parent_evidence(parent: dict, parent_dir: Path) -> tuple[Path, str]:
    if parent.get("stage") == "S4B":
        validation = parent_dir / "evidence" / "validation.json"
        if validation.is_file():
            try:
                value = json.loads(read(validation))
            except (json.JSONDecodeError, OSError) as exc:
                raise PacketError(f"parent worker validation is malformed: {exc}") from exc
            problems = worker_validation_problems(value, parent.get("packet_id"))
            if problems:
                raise PacketError("parent worker validation is malformed: " + "; ".join(problems))
            return validation, "worker-validation"
    transcript = parent_dir / parent.get("expected_transcript", "evidence/transcript.md")
    if transcript.is_file():
        return transcript, "verbatim-transcript"
    if parent.get("stage") == "S4B":
        returned = parent_dir / "evidence" / "return-handoff.md"
        if returned.is_file():
            problems = return_handoff_problems(read(returned))
            if problems:
                raise PacketError("parent return handoff is malformed: " + "; ".join(problems))
            return returned, "structured-return-handoff"
    structural = parent_dir / "evidence" / "stage-result.json"
    if structural.is_file():
        problems = stage_result_problems(structural, parent)
        if problems:
            raise PacketError("parent structural evidence is malformed: " + "; ".join(problems))
        return structural, "structural-stage-result"
    continuity = [
        parent_dir / "evidence" / f"{kind}.json"
        for kind in REASONERS.CONTINUITY_KINDS
        if (parent_dir / "evidence" / f"{kind}.json").is_file()
    ]
    if len(continuity) > 1:
        raise PacketError("parent has ambiguous reasoner continuity evidence")
    if continuity:
        problems = REASONERS.continuity_problems(continuity[0], parent)
        if problems:
            raise PacketError("parent reasoner continuity evidence is malformed: " + "; ".join(problems))
        return continuity[0], continuity[0].stem
    raise PacketError(
        f"parent evidence is missing: {transcript}; save the transcript"
        + (" or record the S4B worker validation" if parent.get("stage") == "S4B" else "")
        + " or record a structurally verified stage result or reasoner continuity event"
        + " before preparing the continuation"
    )


def load_parent(
    parent_arg: str | None, stage: str, retry: bool
) -> tuple[dict | None, Path | None, Path | None, str | None]:
    if stage == "S1" and not parent_arg:
        return None, None, None, None
    if stage == "S1" and parent_arg and not retry:
        raise PacketError("an S1 continuation requires --retry")
    if not parent_arg:
        raise PacketError(f"{stage} requires --parent pointing at a prepared parent packet")

    parent_dir = Path(parent_arg).resolve()
    manifest_path = parent_dir / MANIFEST_NAME if parent_dir.is_dir() else parent_dir
    if manifest_path.name != MANIFEST_NAME or not manifest_path.is_file():
        raise PacketError("parent must be a packet directory containing manifest.json")
    parent_dir = manifest_path.parent
    parent = json.loads(read(manifest_path))
    parent_stage = parent.get("stage")
    allowed = STAGES[stage]["allowed_parents"]
    if parent_stage not in allowed:
        raise PacketError(f"wrong parent stage for {stage}: {parent_stage}; expected one of {allowed}")
    if parent_stage == stage and not retry:
        raise PacketError(f"same-stage parent requires --retry for {stage}")

    evidence, evidence_kind = parent_evidence(parent, parent_dir)
    if stage == "S5" and parent_stage == "S4B":
        if evidence_kind != "worker-validation":
            raise PacketError(
                "S5 requires Ariadne's independent worker validation evidence; "
                "a worker return or transcript alone is not acceptance"
            )
        validation = json.loads(read(evidence))
        if validation.get("status") != "passed":
            raise PacketError("S5 requires a passed independent worker validation")
        returned = parent_dir / "evidence" / "return-handoff.md"
        if not returned.is_file() or return_handoff_status(read(returned)) != "complete":
            status = return_handoff_status(read(returned)) if returned.is_file() else "missing"
            raise PacketError(
                f"S5 requires a complete implementation return; current status is {status or 'unknown'}"
            )
    return parent, parent_dir, evidence, evidence_kind


def section_header(entry: dict) -> str:
    return (
        f"===== BEGIN {entry['label']} | SOURCE {entry['path']} | "
        f"SOURCE-SHA256 {entry['source_sha256']} | CONTENT-SHA256 {entry['content_sha256']} ====="
    )


def section_footer(entry: dict) -> str:
    return f"===== END {entry['label']} ====="


def build_packet(
    stage: str,
    packet_id: str,
    provider: str,
    prompt: dict,
    sources: list[dict],
    parent: dict | None,
    omitted: list[str],
    return_target: Path | None = None,
    worker: dict | None = None,
    project_baseline: dict | None = None,
) -> str:
    independent = stage == "S5"
    lines = [
        f"ARIADNE {stage} STAGE PACKET",
        f"Packet ID: {packet_id}",
        f"Provider: {provider}",
        "Status: PREPARED ONLY — THE STAGE HAS NOT RUN",
        "",
        "TRANSPORT NOTICE",
        "This packet is a generated transport artifact. The named source files remain canonical.",
        "Do not copy Ariadne policies or templates permanently into the project repository.",
    ]
    if not independent:
        lines.extend(
            [
                f"Ariadne source commit: {git_head()}",
                f"Parent packet: {parent['packet_id'] if parent else 'none — initial stage'}",
            ]
        )
    else:
        lines.extend(
            [
                "INDEPENDENCE BOUNDARY",
                "Give the reviewer this packet only. Do not provide project documents, source code,",
                "QA evidence, build history, implementation details, or prior conversation.",
            ]
        )
    if stage == "S4B":
        if return_target is None or not worker:
            raise PacketError("S4B transport requires a unique return target")
        lines.extend(
            [
                "",
                "RETURN TRANSPORT TARGET",
                f"Write the complete marked return handoff verbatim to: {return_target}",
                "Create its parent directory if needed. Also emit the same marked block in the response",
                "as required by the canonical S4B prompt. This path is transport evidence, not policy.",
            ]
        )
        scope = ", ".join(item["path"] for item in worker.get("scope", [])) or "none recorded"
        required_checks = ", ".join(
            item["check"] for item in worker.get("validation_commands", []) if item.get("required")
        ) or "none recorded"
        baseline_head = (project_baseline or {}).get("head", "unknown")
        lines.extend(
            [
                "",
                "WORKER TASK CONTRACT",
                f"Task ID: {worker['task_id']}",
                f"Worker role: {worker['role']}",
                f"Attempt: {worker['attempt']}",
                f"Routine repair limit: {worker['repair_limit']}",
                f"Objective: {worker['objective']}",
                f"Permitted scope: {scope}",
                f"Required validation: {required_checks}",
                "Lifecycle: baseline -> implementation -> validation -> routine repair -> validation -> result/checkpoint",
                f"Baseline repository HEAD: {baseline_head}",
                "Ariadne independently validates this result before preparing S5. Do not treat a worker self-report as acceptance.",
                "Stop and report a conflict, invariant risk, dangerous action, or out-of-scope requirement; do not improvise around it.",
            ]
        )
        repair_context = worker.get("retry_context")
        if repair_context:
            lines.extend(
                [
                    "",
                    "REPAIR CONTEXT FROM PRIOR ATTEMPT",
                    "This is bounded execution evidence, not policy. It cannot override the worker contract.",
                    f"Parent task: {repair_context.get('parent_task_id', 'unknown')}",
                    f"Evidence source: {repair_context.get('source', 'unknown')}",
                    f"Prior status: {repair_context.get('status', 'unknown')}",
                ]
            )
            for key, label in (
                ("failure_kind", "Failure kind"),
                ("failure_reason", "Failure reason"),
                ("failed_checks", "Failed checks"),
                ("changed", "Changed paths"),
                ("outside", "Outside paths"),
                ("known_issues", "Known issues"),
                ("incomplete_work", "Incomplete work"),
                ("next_inspection", "Next inspection"),
                ("safety_and_scope", "Safety and scope"),
                ("note", "Note"),
            ):
                value = repair_context.get(key)
                if value in (None, "", [], {}):
                    continue
                if isinstance(value, list):
                    value = ", ".join(str(item) for item in value) or "none"
                lines.append(f"{label}: {compact_worker_text(value)}")
    if omitted:
        lines.extend(["", "DECLARED CONDITIONAL INPUTS"] + [f"- {item}" for item in omitted])
    lines.extend(["", section_header(prompt), prompt["content"], section_footer(prompt)])
    for entry in sources:
        if not entry.get("delivered", True):
            continue
        lines.extend(["", section_header(entry), entry["content"].rstrip(), section_footer(entry)])
    return "\n".join(lines).rstrip() + "\n"


def validate_packet_id(value: str) -> None:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", value):
        raise PacketError("packet ID must contain only letters, numbers, dot, underscore, or hyphen")


def prepare(args: argparse.Namespace) -> Path:
    stage = args.stage.upper()
    if stage not in STAGES:
        raise PacketError(f"unsupported stage {stage}; choose one of {list(STAGES)}")
    if getattr(args, "adopt_existing", False) and stage != "S1":
        raise PacketError("--adopt-existing is valid only for the S1 intake boundary")
    output = Path(args.output).resolve()
    project = Path(args.project).resolve()
    packet_id = args.packet_id or output.name
    validate_packet_id(packet_id)
    if output.exists():
        raise PacketError(f"refusing to overwrite existing packet/continuation: {output}")
    if is_within(output, project):
        raise PacketError("packet output may not live inside the project repository")
    if is_within(output, ROOT) and not args.synthetic_validation:
        raise PacketError(
            "project transport may contain private material; output inside Ariadne requires "
            "--synthetic-validation and is reserved for synthetic validation"
        )

    check_project_boundary(stage, project, getattr(args, "adopt_existing", False))
    parent, parent_dir, parent_evidence_path, parent_evidence_kind = load_parent(
        args.parent, stage, args.retry
    )
    block, prompt_path = prompt_block(stage)
    block, derived = parameterise_prompt(stage, block, args)
    prompt = source_entry(
        f"current {stage} prompt block", prompt_path, "canonical-prompt", block
    )
    sources, omitted = resolve_sources(stage, project, args)
    sources.extend(derived)

    provider = str(args.provider or STAGES[stage]["provider"]).strip()
    if not provider or re.search(r"[\r\n]", provider):
        raise PacketError("implementation provider identity must be a non-empty single line")
    worker = None
    project_baseline = None
    if stage == "S4B":
        handoff_path = project / "HANDOFF.md"
        handoff_text = read(handoff_path)
        contract_problems = worker_contract_problems(handoff_text)
        if contract_problems:
            raise PacketError("HANDOFF.md worker contract is incomplete: " + "; ".join(contract_problems))
        contract = worker_contract(handoff_text)
        role = (getattr(args, "worker_role", None) or contract["worker_role"]).strip().lower()
        if role not in WORKER_ROLES:
            raise PacketError(f"unsupported implementation worker role: {role or 'missing'}")
        previous_worker = parent.get("worker", {}) if parent and parent.get("stage") == "S4B" else {}
        try:
            attempt = int(previous_worker.get("attempt", 0)) + 1
        except (TypeError, ValueError):
            attempt = 1
        inherited_baseline = parent.get("project_baseline") if parent and parent.get("stage") == "S4B" else None
        project_baseline = inherited_baseline if isinstance(inherited_baseline, dict) else project_git_snapshot(project)
        commands = validation_commands(handoff_text)
        retry_context = worker_retry_context(
            parent, parent_evidence_path, parent_evidence_kind
        )
        worker = {
            "task_id": packet_id,
            "role": role,
            "attempt": attempt,
            "repair_limit": MAX_ROUTINE_REPAIRS,
            "contract_sha256": sha256_file(handoff_path),
            "objective": contract["objective"],
            "scope": [
                {"path": row[0].strip("`"), "actions": row[1], "reason": row[2]}
                for row in contract["scope_rows"] if len(row) >= 3
            ],
            "validation_commands": [
                {key: value for key, value in command.items() if key != "argv"}
                for command in commands
            ],
            "retry_context": retry_context,
        }
    return_target = (
        (project / ".ariadne" / "returns" / f"{packet_id}.md").resolve()
        if stage == "S4B"
        else None
    )
    packet_text = build_packet(
        stage, packet_id, provider, prompt, sources, parent, omitted, return_target,
        worker, project_baseline,
    )

    output.mkdir(parents=True)
    evidence = output / "evidence"
    evidence.mkdir()
    packet_path = output / PACKET_NAME
    packet_path.write_text(packet_text, encoding="utf-8")

    serial_sources = []
    for entry in [prompt] + sources:
        serial_sources.append({key: value for key, value in entry.items() if key != "content"})
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "packet_id": packet_id,
        "stage": stage,
        "provider": provider,
        "worker": worker,
        "project_baseline": project_baseline,
        "ariadne_commit": git_head(),
        "project": str(project),
        "parent_id": parent.get("packet_id") if parent else None,
        "parent_manifest": str((parent_dir / MANIFEST_NAME).resolve()) if parent_dir else None,
        "parent_manifest_sha256": sha256_file(parent_dir / MANIFEST_NAME) if parent_dir else None,
        "parent_evidence": str(parent_evidence_path.resolve()) if parent_evidence_path else None,
        "parent_evidence_kind": parent_evidence_kind,
        "parent_evidence_sha256": sha256_file(parent_evidence_path) if parent_evidence_path else None,
        "retry": bool(args.retry),
        "adopt_existing": bool(getattr(args, "adopt_existing", False)),
        "packet_file": PACKET_NAME,
        "packet_sha256": sha256_file(packet_path),
        "expected_transcript": "evidence/transcript.md",
        "return_target": str(return_target) if return_target else None,
        "sources": serial_sources,
        "omitted_conditionals": omitted,
        "forbidden_inputs": STAGES[stage]["forbidden_inputs"],
    }
    (output / MANIFEST_NAME).write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    source_rows = []
    for entry in serial_sources:
        delivery = "derived only" if not entry.get("delivered", True) else "yes"
        source_rows.append(
            f"| `{entry['label']}` | {delivery} | `{entry['source_sha256']}` | `{entry['path']}` |"
        )
    record = f"""# {packet_id} — {stage} prepared continuation

**Packet ID:** `{packet_id}`
**Stage:** `{stage}`
**Provider:** `{provider}`
**Parent:** `{manifest['parent_id'] or 'none — initial stage'}`
**Ariadne commit:** `{manifest['ariadne_commit']}`
**Project:** `{project}`
**Status:** `PREPARED — NOT RUN`
**Result:** `unfilled until the stage actually runs`

## Prepared transport

- Paste packet: [`{PACKET_NAME}`]({PACKET_NAME})
- Machine-readable provenance: [`{MANIFEST_NAME}`]({MANIFEST_NAME})
- Expected verbatim transcript: `evidence/transcript.md`
{f'- Structured return target: `{return_target}`' if return_target else ''}

| Input | Delivered? | Source SHA-256 | Source |
|---|---|---|---|
{os.linesep.join(source_rows)}

## Boundaries

- Canonical sources remain canonical; this directory is transport and evidence only.
- The parent record and evidence are not overwritten.
- Missing inputs must use the stage prompt's same-stage retry path.
- No gate is approved by preparation.

## Events

No stage events have been recorded. Preparation is not execution.
"""
    (output / RECORD_NAME).write_text(record, encoding="utf-8")
    (evidence / "_README.md").write_text(
        f"# {packet_id} evidence\n\nThe stage has not run. Save the provider's verbatim "
        "transcript as `transcript.md` here. Do not rewrite parent evidence.\n",
        encoding="utf-8",
    )

    problems = verify_packet(output)
    if problems:
        raise PacketError("generated packet failed verification: " + "; ".join(problems))
    return output


def resolve_source_path(entry: dict, manifest: dict) -> Path:
    if entry["kind"].startswith(("project", "continuation", "writing")):
        return Path(entry["path"])
    return ROOT / entry["path"]


def verify_packet(packet_dir: Path) -> list[str]:
    packet_dir = packet_dir.resolve()
    problems = []
    manifest_path = packet_dir / MANIFEST_NAME
    if not manifest_path.is_file():
        return [f"missing {MANIFEST_NAME}"]
    try:
        manifest = json.loads(read(manifest_path))
    except (json.JSONDecodeError, OSError) as exc:
        return [f"invalid manifest: {exc}"]

    stage = manifest.get("stage")
    if manifest.get("schema_version") != SCHEMA_VERSION:
        problems.append("wrong manifest schema version")
    if stage not in STAGES:
        problems.append(f"wrong or unknown stage: {stage}")
        return problems
    packet_path = packet_dir / manifest.get("packet_file", PACKET_NAME)
    if not packet_path.is_file():
        problems.append(f"missing packet file: {packet_path.name}")
        return problems
    packet = read(packet_path)
    if sha256_file(packet_path) != manifest.get("packet_sha256"):
        problems.append("packet hash mismatch — packet changed after preparation")
    if f"ARIADNE {stage} STAGE PACKET" not in packet.splitlines()[:2]:
        problems.append("packet stage header does not match manifest stage")
    if stage == "S4B":
        worker = manifest.get("worker")
        if not isinstance(worker, dict):
            problems.append("S4B packet is missing its worker contract manifest")
        else:
            if worker.get("task_id") != manifest.get("packet_id"):
                problems.append("S4B worker task ID does not match packet ID")
            if worker.get("role") not in WORKER_ROLES:
                problems.append("S4B worker role is unsupported or missing")
            try:
                attempt = int(worker.get("attempt"))
            except (TypeError, ValueError):
                attempt = 0
            if attempt < 1:
                problems.append("S4B worker attempt must be a positive integer")
            try:
                repair_limit = int(worker.get("repair_limit"))
            except (TypeError, ValueError):
                repair_limit = -1
            if repair_limit < 0 or repair_limit > MAX_ROUTINE_REPAIRS:
                problems.append("S4B worker repair limit is outside the safe bound")
            if not isinstance(manifest.get("project_baseline"), dict):
                problems.append("S4B packet is missing its repository baseline")
            project_path = Path(manifest.get("project", ""))
            handoff_path = project_path / "HANDOFF.md"
            if handoff_path.is_file():
                problems.extend(worker_contract_problems(read(handoff_path)))
    adopt_existing = manifest.get("adopt_existing", False)
    if not isinstance(adopt_existing, bool):
        problems.append("adopt_existing manifest field must be boolean")
    elif adopt_existing:
        if stage != "S1":
            problems.append("existing-project adoption is valid only at S1")
        if "ARIADNE EXISTING-PROJECT ADOPTION CONTEXT" not in packet:
            problems.append("S1 adoption packet is missing its non-destructive context")

    expected_labels = []
    for entry in manifest.get("sources", []):
        source_path = resolve_source_path(entry, manifest)
        if not source_path.is_file():
            problems.append(f"source missing: {entry['path']}")
            continue
        current = sha256_file(source_path)
        if current != entry.get("source_sha256"):
            expected_content = entry.get("content_sha256")
            current_content = sha256_text(read(source_path)) if expected_content else None
            if not expected_content or current_content != expected_content:
                problems.append(f"stale source: {entry['path']}")
        if entry.get("delivered", True):
            expected_labels.append(entry["label"])
            header = (
                f"===== BEGIN {entry['label']} | SOURCE {entry['path']} | "
                f"SOURCE-SHA256 {entry['source_sha256']} | CONTENT-SHA256 {entry['content_sha256']} ====="
            )
            footer = f"===== END {entry['label']} ====="
            if packet.count(header) != 1 or packet.count(footer) != 1:
                problems.append(f"missing or duplicate packet section: {entry['label']}")
            elif entry.get("delivered_content_sha256"):
                body = packet.split(header + "\n", 1)[1].split("\n" + footer, 1)[0]
                if sha256_text(body) != entry["delivered_content_sha256"]:
                    problems.append(f"packet section content hash mismatch: {entry['label']}")

    actual_labels = re.findall(r"(?m)^===== BEGIN (.*?) \| SOURCE ", packet)
    if actual_labels != expected_labels:
        problems.append("packet sections do not exactly match the manifest source order")

    if stage == "S5":
        delivered = [entry for entry in manifest.get("sources", []) if entry.get("delivered", True)]
        allowed = {"canonical-prompt", "canonical"}
        if any(entry.get("kind") not in allowed for entry in delivered):
            problems.append("S5 packet delivers forbidden project/build context")
        if [entry["label"] for entry in delivered] != [
            "current S5 prompt block",
            "EVALUATION-RUBRICS.md",
        ]:
            problems.append("S5 packet source set is not the canonical isolated pair")

    return_target = manifest.get("return_target")
    if stage == "S4B":
        expected_target = (
            Path(manifest.get("project", ""))
            / ".ariadne"
            / "returns"
            / f"{manifest.get('packet_id')}.md"
        ).resolve()
        if not return_target:
            problems.append("S4B packet is missing its structured return target")
        else:
            actual_target = Path(return_target).resolve()
            if actual_target != expected_target:
                problems.append("S4B structured return target does not match its packet ID")
            if not is_within(actual_target, Path(manifest.get("project", "")) / ".ariadne" / "returns"):
                problems.append("S4B structured return target escapes the project return directory")
            target_line = f"Write the complete marked return handoff verbatim to: {actual_target}"
            if packet.count(target_line) != 1:
                problems.append("S4B packet return target is missing or duplicated")
    elif return_target is not None:
        problems.append("non-S4B packet declares an unexpected structured return target")

    parent_manifest = manifest.get("parent_manifest")
    if parent_manifest:
        parent_path = Path(parent_manifest)
        if not parent_path.is_file():
            problems.append("parent manifest is missing")
        else:
            if sha256_file(parent_path) != manifest.get("parent_manifest_sha256"):
                problems.append("parent manifest changed after continuation preparation")
            parent = json.loads(read(parent_path))
            if parent.get("packet_id") != manifest.get("parent_id"):
                problems.append("wrong continuation parent ID")
            if parent.get("stage") not in STAGES[stage]["allowed_parents"]:
                problems.append("wrong continuation parent stage")
        parent_evidence = Path(manifest.get("parent_evidence", ""))
        if not parent_evidence.is_file():
            problems.append("parent transcript evidence is missing")
        elif sha256_file(parent_evidence) != manifest.get("parent_evidence_sha256"):
            problems.append("parent transcript changed after continuation preparation")
        evidence_kind = manifest.get("parent_evidence_kind")
        if evidence_kind in REASONERS.CONTINUITY_KINDS and parent_path.is_file():
            parent = json.loads(read(parent_path))
            problems.extend(REASONERS.continuity_problems(parent_evidence, parent))
        if evidence_kind == "worker-validation":
            try:
                validation = json.loads(read(parent_evidence))
            except (json.JSONDecodeError, OSError) as exc:
                problems.append(f"parent worker validation is malformed: {exc}")
            else:
                problems.extend(worker_validation_problems(validation))
    return problems


def repository_contract_problems(stages: dict | None = None) -> list[str]:
    specs = stages or STAGES
    problems = []
    expected = ["S1", "S2", "S3", "S4A", "S4B", "S5", "S6"]
    if list(specs) != expected:
        problems.append(f"packet stage list drift: expected {expected}, found {list(specs)}")
    for stage, spec in specs.items():
        prompt_path = ROOT / spec.get("prompt", "")
        if not prompt_path.is_file():
            problems.append(f"{stage} packet prompt missing: {spec.get('prompt')}")
            continue
        blocks = fenced_blocks(read(prompt_path))
        if len(blocks) <= spec.get("block", -1):
            problems.append(f"{stage} packet prompt block is unavailable")
        for source in spec.get("canonical_inputs", []):
            if not (ROOT / source).is_file():
                problems.append(f"{stage} packet canonical source missing: {source}")
    if specs.get("S6", {}).get("canonical_inputs") != ["templates/RETROSPECTIVE.md"]:
        problems.append("S6 packet must deliver the canonical retrospective template")
    s5 = specs.get("S5", {})
    forbidden = {"PROJECT.md", "DESIGN.md", "HANDOFF.md", "AGENTS.md", "QA.md", "source code", "build history"}
    if not forbidden.issubset(set(s5.get("forbidden_inputs", []))):
        problems.append("S5 packet isolation list is incomplete")
    if s5.get("project_inputs"):
        problems.append("S5 packet must not deliver project documents")
    if s5.get("optional_project_inputs"):
        problems.append("S5 packet must not deliver optional project runtime context")
    if specs.get("S4B", {}).get("allowed_parents") != ["S4A", "S4B"]:
        problems.append("S4B packet parent contract drifted from S4A -> S4B")
    if specs.get("S4B", {}).get("provider") != "implementation-worker":
        problems.append("S4B packet provider default must remain worker-agnostic")
    if specs.get("S1", {}).get("allowed_parents") != ["S1"]:
        problems.append("S1 packet must support a linked same-stage resume")
    if "templates/RETURN-HANDOFF.md" not in specs.get("S4B", {}).get("canonical_inputs", []):
        problems.append("S4B packet must deliver the canonical return-handoff template")
    if ".ariadne/creative-operations.json" not in specs.get("S4B", {}).get(
        "project_inputs", []
    ):
        problems.append("S4B packet must carry the generated creative-operations plan")
    if "skills/visual-qa.md" not in specs.get("S4B", {}).get("canonical_inputs", []):
        problems.append("S4B packet must deliver the selected visual-QA method")
    handoff_template = read(ROOT / "templates" / "HANDOFF.md") if (ROOT / "templates" / "HANDOFF.md").is_file() else ""
    for token in ("## Worker execution contract", "## Validation commands", "Routine repair limit", "Permitted files and systems"):
        if token not in handoff_template:
            problems.append(f"HANDOFF template is missing worker contract element: {token}")
    return_template = read(ROOT / "templates" / "RETURN-HANDOFF.md") if (ROOT / "templates" / "RETURN-HANDOFF.md").is_file() else ""
    for token in ("**Task ID:**", "**Worker role:**", "## Worker validation", "## Safety and scope"):
        if token not in return_template:
            problems.append(f"return handoff template is missing worker evidence element: {token}")
    if specs.get("S2", {}).get("canonical_inputs") != [
        "RESEARCH-POLICY.md", "PRIVACY-POLICY.md", "templates/RESEARCH.md"
    ]:
        problems.append("S2 packet must deliver research, privacy, and output contracts")
    s3 = specs.get("S3", {})
    for source in (
        "DESIGN-TASTE.md", "PRIVACY-POLICY.md", "templates/DESIGN.md",
        "skills/design-direction.md",
    ):
        if source not in s3.get("canonical_inputs", []):
            problems.append(f"S3 packet must deliver canonical source: {source}")
    for source in (
        "selected-skill:skills/reference-analysis.md",
        "selected-skill:skills/component-research.md",
        "selected-capability-registry:references/capabilities.json",
    ):
        if source not in s3.get("conditional_inputs", []):
            problems.append(f"S3 packet conditional transport is missing: {source}")
    return problems


@contextlib.contextmanager
def self_test_workspace():
    """A unique writable fixture root under validation for Windows ACL safety."""
    path = ROOT / "validation" / f"packet-self-test-{uuid.uuid4().hex}"
    path.mkdir()
    try:
        yield path
    finally:
        if path.exists():
            shutil.rmtree(path)


def self_test() -> int:
    cases = []

    def case(name: str, passed: bool) -> None:
        cases.append((name, passed))

    py_validation, py_error = safe_validation_argv("py -3 -m pytest")
    case(
        "Windows py validation syntax is accepted",
        py_error is None and py_validation == ["py", "-3", "-m", "pytest"],
    )
    _shell_validation, shell_error = safe_validation_argv("pytest; git reset --hard")
    case("shell validation syntax is rejected", shell_error is not None)

    with self_test_workspace() as first_workspace, self_test_workspace() as second_workspace:
        case(
            "independent packet self-test workspaces do not collide",
            first_workspace != second_workspace and first_workspace.exists() and second_workspace.exists(),
        )

    case("repository packet contracts pass (positive control)", not repository_contract_problems())
    changed = copy.deepcopy(STAGES)
    changed["S6"]["canonical_inputs"] = []
    case("missing S6 canonical template fails", bool(repository_contract_problems(changed)))
    changed = copy.deepcopy(STAGES)
    changed["S5"]["project_inputs"] = ["QA.md"]
    case("S5 project-context delivery fails", bool(repository_contract_problems(changed)))
    changed = copy.deepcopy(STAGES)
    changed["S4B"]["allowed_parents"] = ["S3"]
    case("wrong S4A to S4B parent contract fails", bool(repository_contract_problems(changed)))
    changed = copy.deepcopy(STAGES)
    changed["S1"]["allowed_parents"] = []
    case("missing S1 resume parent contract fails", bool(repository_contract_problems(changed)))
    changed = copy.deepcopy(STAGES)
    changed["S2"]["canonical_inputs"].remove("PRIVACY-POLICY.md")
    case("missing S2 privacy boundary fails", bool(repository_contract_problems(changed)))
    changed = copy.deepcopy(STAGES)
    changed["S3"]["conditional_inputs"].remove(
        "selected-skill:skills/component-research.md"
    )
    case("missing selected S3 skill transport fails", bool(repository_contract_problems(changed)))

    with self_test_workspace() as sandbox:
        project = sandbox / "project"
        project.mkdir()
        (project / ".gitignore").write_text(".env*\n", encoding="utf-8")

        common = dict(
            provider=None,
            packet_id=None,
            parent=None,
            retry=False,
            adopt_existing=False,
            synthetic_validation=True,
            request=None,
            request_file=None,
            references_file=None,
            references_text=None,
            restart_context=None,
            motion=None,
            assets=None,
            target=None,
            lenses=None,
        )

        def ns(**kwargs):
            values = dict(common)
            values.update(kwargs)
            return argparse.Namespace(**values)

        s1_dir = sandbox / "R1-S1"
        prepare(ns(stage="S1", project=str(project), output=str(s1_dir), request="Build a small type experiment."))
        case("fresh S1 packet verifies (positive control)", not verify_packet(s1_dir))

        existing_project = sandbox / "existing-project"
        existing_project.mkdir()
        existing_readme = existing_project / "README.md"
        existing_readme.write_text("# Existing fixture\n", encoding="utf-8")
        try:
            prepare(ns(
                stage="S1", project=str(existing_project), output=str(sandbox / "existing-refused"),
                request="Adopt this existing site.",
            ))
            default_existing_refused = False
        except PacketError as exc:
            default_existing_refused = "fresh project" in str(exc)
        case("existing project requires explicit adoption", default_existing_refused)

        adopted_s1 = sandbox / "existing-S1"
        prepare(ns(
            stage="S1", project=str(existing_project), output=str(adopted_s1),
            request="Adopt this existing site.", adopt_existing=True,
        ))
        adopted_manifest = json.loads(read(adopted_s1 / MANIFEST_NAME))
        case(
            "existing project adoption preserves files and declares its boundary",
            not verify_packet(adopted_s1)
            and read(existing_readme) == "# Existing fixture\n"
            and adopted_manifest["adopt_existing"] is True
            and "EXISTING-PROJECT ADOPTION CONTEXT" in read(adopted_s1 / PACKET_NAME),
        )
        adopted_manifest_text = read(adopted_s1 / MANIFEST_NAME)
        malformed_adoption = json.loads(adopted_manifest_text)
        malformed_adoption["adopt_existing"] = "yes"
        (adopted_s1 / MANIFEST_NAME).write_text(
            json.dumps(malformed_adoption, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        case(
            "non-boolean adoption provenance is detected",
            any("must be boolean" in problem for problem in verify_packet(adopted_s1)),
        )
        (adopted_s1 / MANIFEST_NAME).write_text(adopted_manifest_text, encoding="utf-8")
        (existing_project / "AGENTS.md").write_text("existing rules\n", encoding="utf-8")
        try:
            prepare(ns(
                stage="S1", project=str(existing_project), output=str(sandbox / "owned-refused"),
                request="Adopt this existing site.", adopt_existing=True,
            ))
            owned_entry_refused = False
        except PacketError as exc:
            owned_entry_refused = "AGENTS.md" in str(exc)
        case("adoption refuses to overwrite an existing AGENTS.md", owned_entry_refused)

        (s1_dir / "evidence" / "transcript.md").write_text("S1 transcript\n", encoding="utf-8")
        s1_retry = sandbox / "R1-S1-C1"
        prepare(ns(
            stage="S1", project=str(project), output=str(s1_retry), parent=str(s1_dir),
            retry=True, request="Build a small type experiment.",
        ))
        s1_retry_manifest = json.loads(read(s1_retry / MANIFEST_NAME))
        case(
            "S1 resume creates a linked non-overwriting child",
            not verify_packet(s1_retry)
            and s1_retry_manifest["parent_id"] == json.loads(read(s1_dir / MANIFEST_NAME))["packet_id"],
        )

        reasoner_parent = sandbox / "reasoner-S1"
        prepare(ns(
            stage="S1", project=str(project), output=str(reasoner_parent),
            request="Build a provider-neutral fixture.", provider="codex",
        ))
        reasoner_parent_manifest = json.loads(read(reasoner_parent / MANIFEST_NAME))
        switch_path = reasoner_parent / "evidence" / "reasoner-switch.json"
        switch = REASONERS.continuity_record(
            "reasoner-switch", reasoner_parent_manifest["packet_id"], "S1",
            "codex", "claude", "Fixture switch.", "verified",
            "2026-08-23T00:00:00+05:30",
        )
        switch_path.write_text(json.dumps(switch, indent=2) + "\n", encoding="utf-8")
        reasoner_child = sandbox / "reasoner-S1-C1"
        prepare(ns(
            stage="S1", project=str(project), output=str(reasoner_child),
            parent=str(reasoner_parent), retry=True,
            request="Build a provider-neutral fixture.", provider="claude",
        ))
        case(
            "reasoner continuity creates a verified same-stage child (positive control)",
            not verify_packet(reasoner_child)
            and json.loads(read(reasoner_child / MANIFEST_NAME))["parent_evidence_kind"]
            == "reasoner-switch",
        )
        switch_original = read(switch_path)
        malformed_switch = dict(switch)
        malformed_switch["packet_id"] = "wrong-parent"
        switch_path.write_text(json.dumps(malformed_switch, indent=2) + "\n", encoding="utf-8")
        case(
            "wrong reasoner continuity parent makes the child stale",
            any("wrong packet ID" in problem for problem in verify_packet(reasoner_child)),
        )
        switch_path.write_text(switch_original, encoding="utf-8")

        (project / "PROJECT.md").write_text(
            "# PROJECT\n\n**Mode:** game-experiment\n\n## Goal\n\nMake type respond to sound.\n\n"
            "## Accepted patterns\n\n| Pattern | Because | Rationale type |\n|---|---|---|\n\n"
            "## Success criteria\n\n1. Sound changes type.\n2. Silence is distinct.\n\n"
            "## Open questions\n\n| # | Question | Needed by | Blocking? |\n|---|---|---|---|\n"
            "| 1 | Which browser microphone API is current? | S3 | yes |\n",
            encoding="utf-8",
        )
        (project / "AGENTS.md").write_text(
            "## Current state\n\n| **Stage** | `S1` |\n| **Last gate passed** | `none` |\n",
            encoding="utf-8",
        )
        creative_dir = project / ".ariadne"
        creative_dir.mkdir()
        creative_path = creative_dir / "creative-evidence.json"
        creative_path.write_text(
            json.dumps({
                "schema_version": 2,
                "project": str(project),
                "research_depth": "standard",
                "skills": [
                    {"name": "reference-analysis", "selected": True},
                    {"name": "component-research", "selected": True},
                ],
            }, indent=2) + "\n",
            encoding="utf-8",
        )
        s2_dir = sandbox / "R1-S2"
        prepare(ns(stage="S2", project=str(project), output=str(s2_dir), parent=str(s1_dir)))
        s2_manifest = json.loads(read(s2_dir / MANIFEST_NAME))
        case(
            "conditional S2 packet carries current creative plan",
            not verify_packet(s2_dir)
            and any(item["label"] == ".ariadne/creative-evidence.json" for item in s2_manifest["sources"]),
        )
        (s2_dir / "evidence" / "transcript.md").write_text("S2 transcript\n", encoding="utf-8")
        (project / "RESEARCH.md").write_text(
            "# RESEARCH\n\n## Findings\n\n| Claim | Date | Confidence | Source |\n",
            encoding="utf-8",
        )

        s3_dir = sandbox / "R1-S3"
        prepare(ns(stage="S3", project=str(project), output=str(s3_dir), parent=str(s2_dir), motion="yes", assets="no"))
        s3_manifest = json.loads(read(s3_dir / MANIFEST_NAME))
        case(
            "fresh S3 continuation carries creative provenance",
            not verify_packet(s3_dir)
            and any(item["label"] == ".ariadne/creative-evidence.json" for item in s3_manifest["sources"]),
        )
        delivered_s3 = {item["label"] for item in s3_manifest["sources"]}
        case(
            "selected S3 methods and registry are delivered (positive control)",
            {
                "skills/reference-analysis.md", "skills/component-research.md",
                "references/capabilities.json",
            }.issubset(delivered_s3),
        )

        (s3_dir / "evidence" / "transcript.md").write_text(
            "S3 direction proposed and rejected before G1\n", encoding="utf-8"
        )
        restart_context = s3_dir / "evidence" / "rejected-direction.md"
        restart_context.write_text(
            "# Rejected S3 direction context\n\n"
            "**Human reason:** The organising concept is too generic.\n\n"
            "===== BEGIN REJECTED DESIGN.md =====\n"
            "# DESIGN\n\n**Status:** draft — awaiting G1\n"
            "===== END REJECTED DESIGN.md =====\n",
            encoding="utf-8",
        )
        s3_retry_dir = sandbox / "R1-S3-C1"
        prepare(ns(
            stage="S3", project=str(project), output=str(s3_retry_dir),
            parent=str(s3_dir), retry=True,
            references_text="one preserved reference", restart_context=str(restart_context),
            motion="yes", assets="no",
        ))
        s3_retry_manifest = json.loads(read(s3_retry_dir / MANIFEST_NAME))
        restart_sources = [
            source for source in s3_retry_manifest["sources"]
            if source["kind"] == "continuation-restart-context"
        ]
        case(
            "S3 restart carries rejected direction and reason in a linked child",
            not verify_packet(s3_retry_dir)
            and s3_retry_manifest["parent_id"] == s3_manifest["packet_id"]
            and s3_retry_manifest["retry"] is True
            and len(restart_sources) == 1
            and "one preserved reference" in read(s3_retry_dir / PACKET_NAME),
        )
        restart_original = read(restart_context)
        restart_context.write_text(restart_original + "changed\n", encoding="utf-8")
        case(
            "changed restart context makes the child packet stale",
            any("stale source" in problem for problem in verify_packet(s3_retry_dir)),
        )
        restart_context.write_text(restart_original, encoding="utf-8")
        try:
            prepare(ns(
                stage="S3", project=str(project), output=str(sandbox / "invalid-restart"),
                parent=str(s2_dir), retry=False, restart_context=str(restart_context),
                motion="yes", assets="no",
            ))
            non_retry_restart_refused = False
        except PacketError as exc:
            non_retry_restart_refused = "same-stage retry" in str(exc)
        case("restart context is rejected outside a same-stage retry", non_retry_restart_refused)
        try:
            prepare(ns(
                stage="S3", project=str(project), output=str(sandbox / "missing-restart"),
                parent=str(s3_dir), retry=True,
                restart_context=str(sandbox / "missing-rejected-direction.md"),
                motion="yes", assets="no",
            ))
            missing_restart_refused = False
        except PacketError as exc:
            missing_restart_refused = "missing or empty" in str(exc)
        case("missing restart evidence blocks the child packet", missing_restart_refused)

        parent_transcript = s2_dir / "evidence" / "transcript.md"
        parent_transcript.write_text("changed parent evidence\n", encoding="utf-8")
        case("changed parent transcript is detected", any("parent transcript changed" in p for p in verify_packet(s3_dir)))
        parent_transcript.write_text("S2 transcript\n", encoding="utf-8")

        original_project = read(project / "PROJECT.md")
        (project / "PROJECT.md").write_bytes(
            original_project.replace("\n", "\r\n").encode("utf-8")
        )
        case(
            "line-ending-only source changes preserve content parity",
            not verify_packet(s3_dir),
        )
        (project / "PROJECT.md").write_text(original_project + "\nchanged\n", encoding="utf-8")
        case("changed project input is stale", any("stale source" in p for p in verify_packet(s3_dir)))
        (project / "PROJECT.md").write_text(original_project, encoding="utf-8")

        manifest_path = s3_dir / MANIFEST_NAME
        manifest_original = read(manifest_path)
        packet_path = s3_dir / PACKET_NAME
        packet_original = read(packet_path)
        registry_entry = next(
            source for source in json.loads(manifest_original)["sources"]
            if source["path"] == "references/capabilities.json"
        )
        registry_header = section_header(registry_entry)
        registry_tampered = packet_original.replace(
            '"name": "Base UI"', '"name": "Tampered UI"', 1
        )
        packet_path.write_text(registry_tampered, encoding="utf-8")
        registry_manifest = json.loads(manifest_original)
        registry_manifest["packet_sha256"] = sha256_file(packet_path)
        manifest_path.write_text(
            json.dumps(registry_manifest, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        case(
            "changed delivered capability registry cannot pass as current",
            registry_header in packet_original
            and any("section content hash mismatch" in problem for problem in verify_packet(s3_dir)),
        )
        packet_path.write_text(packet_original, encoding="utf-8")
        manifest_path.write_text(manifest_original, encoding="utf-8")
        broken_packet = re.sub(r"(?ms)^===== BEGIN DESIGN-TASTE.md.*?^===== END DESIGN-TASTE.md =====\n?", "", packet_original)
        packet_path.write_text(broken_packet, encoding="utf-8")
        manifest = json.loads(manifest_original)
        manifest["packet_sha256"] = sha256_file(packet_path)
        manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        case("missing packet section fails despite refreshed packet hash", any("section" in p for p in verify_packet(s3_dir)))
        packet_path.write_text(packet_original, encoding="utf-8")
        manifest_path.write_text(manifest_original, encoding="utf-8")

        manifest = json.loads(manifest_original)
        canonical = next(source for source in manifest["sources"] if source["path"] == "DESIGN-TASTE.md")
        canonical["source_sha256"] = "0" * 64
        manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        case(
            "tampered canonical source declaration is detected",
            any("section" in problem for problem in verify_packet(s3_dir)),
        )
        manifest_path.write_text(manifest_original, encoding="utf-8")

        manifest = json.loads(manifest_original)
        canonical = next(source for source in manifest["sources"] if source["path"] == "DESIGN-TASTE.md")
        original_header = section_header(canonical)
        canonical["source_sha256"] = "0" * 64
        fallback_header = section_header(canonical)
        fallback_packet = packet_original.replace(original_header, fallback_header, 1)
        packet_path.write_text(fallback_packet, encoding="utf-8")
        manifest["packet_sha256"] = sha256_file(packet_path)
        manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        case(
            "normalised full-source hash tolerates raw checkout byte drift (positive control)",
            not verify_packet(s3_dir),
        )

        canonical["content_sha256"] = "f" * 64
        stale_packet = fallback_packet.replace(fallback_header, section_header(canonical), 1)
        packet_path.write_text(stale_packet, encoding="utf-8")
        manifest["packet_sha256"] = sha256_file(packet_path)
        manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        case("changed normalised canonical source is stale", any("stale source" in p for p in verify_packet(s3_dir)))

        packet_path.write_text(packet_original, encoding="utf-8")
        manifest = json.loads(manifest_original)
        canonical = next(source for source in manifest["sources"] if source["path"] == "DESIGN-TASTE.md")
        canonical["delivered_content_sha256"] = "0" * 64
        manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        case(
            "delivered packet section hash cannot be ignored",
            any("section content hash mismatch" in p for p in verify_packet(s3_dir)),
        )
        manifest_path.write_text(manifest_original, encoding="utf-8")

        manifest = json.loads(manifest_original)
        manifest["stage"] = "S4A"
        manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        case("wrong stage fails", any("stage header" in p or "parent stage" in p for p in verify_packet(s3_dir)))
        manifest_path.write_text(manifest_original, encoding="utf-8")

        try:
            prepare(ns(stage="S3", project=str(project), output=str(s3_dir), parent=str(s1_dir), motion="yes", assets="no"))
            duplicate_failed = False
        except PacketError:
            duplicate_failed = True
        case("duplicate continuation is refused", duplicate_failed)

        missing_evidence_parent = sandbox / "R2-S1"
        # Clone the valid parent manifest without its transcript to isolate the evidence guard.
        missing_evidence_parent.mkdir()
        (missing_evidence_parent / MANIFEST_NAME).write_text(read(s1_dir / MANIFEST_NAME), encoding="utf-8")
        try:
            prepare(ns(stage="S3", project=str(project), output=str(sandbox / "R2-S3"), parent=str(missing_evidence_parent), motion="yes", assets="no"))
            evidence_failed = False
        except PacketError as exc:
            evidence_failed = "parent evidence is missing" in str(exc)
        case("missing parent evidence blocks continuation", evidence_failed)

        (project / "DESIGN.md").write_text("**Status:** locked at G1 on 2026-08-22\n", encoding="utf-8")
        (project / "AGENTS.md").write_text(
            "## Current state\n\n| **Stage** | `S4` |\n| **Last gate passed** | `G1` |\n",
            encoding="utf-8",
        )
        try:
            prepare(ns(stage="S4A", project=str(project), output=str(sandbox / "wrong-parent"), parent=str(s1_dir)))
            parent_failed = False
        except PacketError as exc:
            parent_failed = "wrong parent stage" in str(exc)
        case("wrong continuation parent blocks preparation", parent_failed)

        (s3_dir / "evidence" / "transcript.md").write_text("S3 transcript and human G1 approval\n", encoding="utf-8")
        s4a_dir = sandbox / "R1-S4A"
        prepare(ns(stage="S4A", project=str(project), output=str(s4a_dir), parent=str(s3_dir)))
        case("S4A packet verifies (positive control)", not verify_packet(s4a_dir))
        (s4a_dir / "evidence" / "transcript.md").write_text("S4A transcript\n", encoding="utf-8")

        (project / "HANDOFF.md").write_text(
            "# HANDOFF\n\n**G1 approved:** 2026-08-22\n\n"
            "## Dependencies to install\n\nNone.\n\n"
            "## Worker execution contract\n\n"
            "**Worker role:** bulk\n\n"
            "**Objective:** Build the approved fixture.\n\n"
            "**Relevant context:** HANDOFF.md, DESIGN.md, AGENTS.md, and permitted files.\n\n"
            "**Invariants:** Preserve the approved direction and acceptance criteria.\n\n"
            "**Permitted actions:** Read files; edit permitted files; create required files; run tests; inspect git status and diff.\n\n"
            "**Prohibited actions:** git push, force operations, git reset, git clean, secrets, .env files, deploy, production changes, destructive migrations, unrelated systems.\n\n"
            "**Stop conditions:** Missing context, packet/repository conflict, invariant risk, out-of-scope or dangerous action, exhausted budget.\n\n"
            "**Escalation conditions:** Repeated routine failure, architecture conflict or uncertainty, high-risk change, invariant conflict.\n\n"
            "**Lifecycle:** baseline -> implementation -> validation -> routine repair -> validation -> result/checkpoint\n\n"
            "**Routine repair limit:** 2\n\n"
            "### Permitted files and systems\n\n"
            "| Path / glob | Actions | Reason |\n|---|---|---|\n"
            "| src/** | read / edit / create | fixture implementation |\n\n"
            "## Validation commands\n\n"
            "| Check | Command | Required | Expected |\n|---|---|---|---|\n"
            "| diff hygiene | `git diff --check` | yes | exit code 0 |\n",
            encoding="utf-8",
        )
        operations_dir = project / ".ariadne"
        operations_dir.mkdir(exist_ok=True)
        operations_path = operations_dir / "creative-operations.json"
        operations_path.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "project": str(project),
                    "requirements": [{"id": "DES-001", "claim": "Signature overlap"}],
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        s4b_dir = sandbox / "R1-S4B"
        prepare(ns(stage="S4B", project=str(project), output=str(s4b_dir), parent=str(s4a_dir)))
        s4b_manifest = json.loads(read(s4b_dir / MANIFEST_NAME))
        expected_return_target = (
            project / ".ariadne" / "returns" / f"{s4b_manifest['packet_id']}.md"
        ).resolve()
        case(
            "generic S4B packet verifies with trace and unique return target (positive control)",
            not verify_packet(s4b_dir)
            and s4b_manifest["provider"] == "implementation-worker"
            and s4b_manifest["return_target"] == str(expected_return_target)
            and any(
                item["label"] == ".ariadne/creative-operations.json"
                for item in s4b_manifest["sources"]
            ),
        )
        claude_code_dir = sandbox / "R1-S4B-CLAUDE-CODE"
        prepare(ns(
            stage="S4B", project=str(project), output=str(claude_code_dir),
            parent=str(s4a_dir), provider="claude-code",
        ))
        case(
            "Claude Code S4B transport retains its provider identity",
            not verify_packet(claude_code_dir)
            and json.loads(read(claude_code_dir / MANIFEST_NAME))["provider"]
            == "claude-code",
        )
        try:
            prepare(ns(
                stage="S4B", project=str(project),
                output=str(sandbox / "R1-S4B-REASONER-MISROUTE"),
                parent=str(s4a_dir), provider="claude",
            ))
            claude_reasoner_misroute_blocked = False
        except PacketError as exc:
            claude_reasoner_misroute_blocked = "reasoner" in str(exc)
        case(
            "provider identity is not used as a core implementation policy",
            claude_reasoner_misroute_blocked is False,
        )
        s4b_manifest_path = s4b_dir / MANIFEST_NAME
        s4b_manifest_original = read(s4b_manifest_path)
        malformed_return_target = json.loads(s4b_manifest_original)
        malformed_return_target["return_target"] = str(project / "QA.md")
        s4b_manifest_path.write_text(
            json.dumps(malformed_return_target, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        case(
            "S4B return target cannot escape its unique transport path",
            any("return target" in problem for problem in verify_packet(s4b_dir)),
        )
        s4b_manifest_path.write_text(s4b_manifest_original, encoding="utf-8")
        operations_original = read(operations_path)
        operations_path.write_text(operations_original + "\n", encoding="utf-8")
        case(
            "changed creative-operations input makes the S4B packet stale",
            any("stale source" in problem for problem in verify_packet(s4b_dir)),
        )
        operations_path.write_text(operations_original, encoding="utf-8")
        returned = (
            "# IMPLEMENTATION RETURN HANDOFF: fixture\n\n"
            f"**Status:** complete\n**Task ID:** {s4b_manifest['packet_id']}\n"
            "**Worker role:** bulk\n**Provider:** fixture\n**Model:** fixture\n"
            "**Effort:** medium\n**Started:** 2026-08-23\n**Ended:** 2026-08-23\n\n"
            "**Usage:** unknown\n**Cost:** unknown\n"
            "**Scope status:** within-contract\n"
            "**Unexpected actions or conflicts:** none\n\n"
            + "\n\n".join(f"## {heading}\n\nnone" for heading in RETURN_HANDOFF_HEADINGS)
            + "\n"
        )
        return_path = s4b_dir / "evidence" / "return-handoff.md"
        return_path.write_text(returned.replace("**Status:** complete", "**Status:** partial"), encoding="utf-8")

        (project / "QA.md").write_text(
            "# QA\n\n## Mechanical\n\n| 1 | Build | pass | output |\n\n## Judgement\n\nVerdict: Ship\nScore: 40/50\n",
            encoding="utf-8",
        )
        try:
            prepare(ns(stage="S5", project=str(project), output=str(sandbox / "partial-S5"), parent=str(s4b_dir), target="http://127.0.0.1:3000", lenses="creative-director (light)"))
            partial_return_blocked = False
        except PacketError as exc:
            partial_return_blocked = (
                "requires Ariadne's independent worker validation" in str(exc)
                or "requires a complete implementation return" in str(exc)
            )
        case("partial S4B return cannot advance to S5", partial_return_blocked)
        return_path.write_text(returned, encoding="utf-8")
        validation = {
            "schema_version": WORKER_VALIDATION_SCHEMA,
            "kind": "worker-validation",
            "packet_id": s4b_manifest["packet_id"],
            "stage": "S4B",
            "status": "passed",
            "recorded_at": "2026-08-23T00:00:00+05:30",
            "independent": True,
            "scope": {"status": "within-contract", "changed": [], "outside": [], "sensitive": [], "immutable": [], "head_changed": False},
            "failure_kind": "none",
            "failure_reason": "none",
            "commands": [{"id": "diff-hygiene", "status": "passed", "returncode": 0}],
            "usage": "unknown",
            "cost": "unknown",
        }
        (s4b_dir / "evidence" / "validation.json").write_text(
            json.dumps(validation, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        failed_validation = copy.deepcopy(validation)
        failed_validation.update({
            "status": "failed",
            "failure_kind": "routine",
            "failure_reason": "Required validation failed: diff-hygiene",
        })
        failed_validation["commands"][0].update({"status": "failed", "returncode": 1})
        (s4b_dir / "evidence" / "validation.json").write_text(
            json.dumps(failed_validation, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        repair_dir = sandbox / "R1-S4B-REPAIR"
        prepare(ns(
            stage="S4B", project=str(project), output=str(repair_dir),
            parent=str(s4b_dir), retry=True,
        ))
        repair_manifest = json.loads(read(repair_dir / MANIFEST_NAME))
        repair_context = repair_manifest["worker"]["retry_context"]
        case(
            "routine repair packet carries bounded prior failure context",
            repair_context["failure_kind"] == "routine"
            and "REPAIR CONTEXT FROM PRIOR ATTEMPT" in read(repair_dir / PACKET_NAME)
            and "diff-hygiene" in read(repair_dir / PACKET_NAME),
        )
        (s4b_dir / "evidence" / "validation.json").write_text(
            json.dumps(validation, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        s5_dir = sandbox / "R1-S5"
        prepare(ns(stage="S5", project=str(project), output=str(s5_dir), parent=str(s4b_dir), target="http://127.0.0.1:3000", lenses="creative-director (light)"))
        case("isolated S5 packet verifies (positive control)", not verify_packet(s5_dir))
        s5_manifest = json.loads(read(s5_dir / MANIFEST_NAME))
        case("S4B validation supports continuation without a fabricated transcript", s5_manifest.get("parent_evidence_kind") == "worker-validation")
        delivered_kinds = {s["kind"] for s in s5_manifest["sources"] if s.get("delivered", True)}
        case("S5 delivered sources exclude project context (positive control)", delivered_kinds == {"canonical-prompt", "canonical"})
        (s5_dir / "evidence" / "transcript.md").write_text("Independent S5 transcript\n", encoding="utf-8")

        s6_dir = sandbox / "R1-S6"
        prepare(ns(stage="S6", project=str(project), output=str(s6_dir), parent=str(s5_dir)))
        case("S6 packet verifies with canonical template (positive control)", not verify_packet(s6_dir))

    print("STAGE PACKET SELF-TEST\n")
    for name, passed in cases:
        print(("ok    " if passed else "FAIL  ") + name)
    failed = [name for name, passed in cases if not passed]
    print(f"\n{'FAILED' if failed else 'PASS'}  {len(cases) - len(failed)}/{len(cases)}")
    return 1 if failed else 0


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--self-test", action="store_true")
    sub = p.add_subparsers(dest="command")

    prepare_parser = sub.add_parser("prepare", help="prepare a new packet and continuation")
    prepare_parser.add_argument("--stage", required=True, choices=list(STAGES))
    prepare_parser.add_argument("--project", required=True)
    prepare_parser.add_argument("--output", required=True)
    prepare_parser.add_argument("--packet-id")
    prepare_parser.add_argument("--parent")
    prepare_parser.add_argument("--retry", action="store_true")
    prepare_parser.add_argument("--provider", help="provider or worker environment label; recorded without normalization")
    prepare_parser.add_argument("--worker-role", choices=list(WORKER_ROLES))
    prepare_parser.add_argument("--request")
    prepare_parser.add_argument("--request-file")
    prepare_parser.add_argument("--references-file")
    prepare_parser.add_argument("--motion", choices=["yes", "no"])
    prepare_parser.add_argument("--assets", choices=["yes", "no"])
    prepare_parser.add_argument("--target")
    prepare_parser.add_argument("--lenses")
    prepare_parser.add_argument("--synthetic-validation", action="store_true")
    prepare_parser.add_argument(
        "--adopt-existing", action="store_true",
        help="allow an opt-in, non-destructive S1 intake for an existing project",
    )

    verify_parser = sub.add_parser("verify", help="verify source parity and packet structure")
    verify_parser.add_argument("--packet-dir", required=True)
    writing_parser = sub.add_parser("prepare-writing", help="prepare a minimal writing draft, review, or revision packet")
    writing_parser.add_argument("--phase", required=True, choices=["draft", "review", "revise"])
    writing_parser.add_argument("--intent", required=True, choices=list(WRITING_INTENTS))
    writing_parser.add_argument("--request-file", required=True)
    writing_parser.add_argument("--output", required=True)
    writing_parser.add_argument("--packet-id", required=True)
    writing_parser.add_argument("--provider", default="codex", choices=["codex", "claude"])
    writing_parser.add_argument("--model")
    writing_parser.add_argument("--criteria", required=True)
    writing_parser.add_argument("--source-file", action="append")
    writing_parser.add_argument("--draft-file")
    writing_parser.add_argument("--original-draft-file")
    writing_parser.add_argument("--review-file")
    return p


def main() -> int:
    args = parser().parse_args()
    try:
        if args.self_test:
            return self_test()
        if args.command == "prepare":
            output = prepare(args)
            print(f"PREPARED  {output}")
            print(f"PACKET    {output / PACKET_NAME}")
            print(f"MANIFEST  {output / MANIFEST_NAME}")
            print(f"EVIDENCE  {output / 'evidence' / 'transcript.md'}")
            print("NEXT      Open the required fresh provider session and paste packet.txt only.")
            return 0
        if args.command == "verify":
            problems = verify_packet(Path(args.packet_dir))
            if problems:
                print(f"FAIL  {len(problems)} packet problem(s)")
                for problem in problems:
                    print(f"      {problem}")
                return 1
            print("PASS  packet structure, parent, and source parity verified")
            return 0
        if args.command == "prepare-writing":
            if args.phase in ("review", "revise") and not args.draft_file:
                raise PacketError(f"writing {args.phase} packet requires --draft-file")
            if args.phase == "revise" and not args.review_file:
                raise PacketError("writing revise packet requires --review-file")
            if args.intent == "HUMAN-DRAFT TRANSFORMATION" and args.phase in ("review", "revise") and not args.original_draft_file:
                raise PacketError(f"human-draft transformation {args.phase} packet requires --original-draft-file")
            output = prepare_writing(args)
            print(f"PREPARED  {output}")
            print(f"PACKET    {output / PACKET_NAME}")
            print(f"MANIFEST  {output / MANIFEST_NAME}")
            print("NEXT      Open the selected provider session and paste packet.txt only.")
            return 0
        parser().print_help()
        return 0
    except PacketError as exc:
        print(f"STOPPED: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
