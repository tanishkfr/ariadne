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
import hashlib
import json
import os
import re
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
        "canonical_inputs": ["RESEARCH-POLICY.md", "templates/RESEARCH.md"],
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
        "canonical_inputs": ["DESIGN-TASTE.md", "templates/DESIGN.md"],
        "conditional_inputs": [
            "project:RESEARCH.md",
            "canonical:DESIGN-MOTION.md",
            "canonical:DESIGN-ASSETS.md",
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
        "provider": "cursor",
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
    for field in ("Status", "Provider", "Model", "Effort", "Started", "Ended"):
        matches = re.findall(rf"(?im)^\*\*{field}:\*\*\s*(.+?)\s*$", text)
        if len(matches) != 1 or re.search(r"<[^>]+>|\bcomplete / partial / blocked\b", matches[0] if matches else ""):
            problems.append(f"return handoff has unfilled field: {field}")
    status = re.search(r"(?im)^\*\*Status:\*\*\s*(.+?)\s*$", text)
    if status and status.group(1).strip().lower() not in ("complete", "partial", "blocked"):
        problems.append("return handoff Status must be complete, partial, or blocked")
    return problems


def return_handoff_status(text: str) -> str:
    match = re.search(r"(?im)^\*\*Status:\*\*\s*(.+?)\s*$", text)
    return match.group(1).strip().lower() if match else ""


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
            if kind.startswith(("project", "continuation"))
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
        + (" or ingest the S4B return handoff" if parent.get("stage") == "S4B" else "")
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
    if stage == "S5" and evidence_kind == "structured-return-handoff":
        status = return_handoff_status(read(evidence))
        if status != "complete":
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


def build_packet(stage: str, packet_id: str, provider: str, prompt: dict, sources: list[dict],
                 parent: dict | None, omitted: list[str], return_target: Path | None = None) -> str:
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
        if return_target is None:
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

    provider = args.provider or STAGES[stage]["provider"]
    if stage == "S4B" and provider == "claude":
        raise PacketError("Claude reasoner cannot be used as the S4B implementation provider")
    return_target = (
        (project / ".ariadne" / "returns" / f"{packet_id}.md").resolve()
        if stage == "S4B"
        else None
    )
    packet_text = build_packet(
        stage, packet_id, provider, prompt, sources, parent, omitted, return_target
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
    if entry["kind"].startswith(("project", "continuation")):
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
            json.dumps({"schema_version": 1, "project": str(project), "research_depth": "standard"}, indent=2) + "\n",
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
            "# HANDOFF\n\n**G1 approved:** 2026-08-22\n\n## Dependencies to install\n\nNone.\n",
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
            "Cursor S4B packet verifies with trace and unique return target (positive control)",
            not verify_packet(s4b_dir)
            and s4b_manifest["provider"] == "cursor"
            and s4b_manifest["return_target"] == str(expected_return_target)
            and any(
                item["label"] == ".ariadne/creative-operations.json"
                for item in s4b_manifest["sources"]
            ),
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
            "**Status:** complete\n**Provider:** fixture\n**Model:** fixture\n"
            "**Effort:** medium\n**Started:** 2026-08-23\n**Ended:** 2026-08-23\n\n"
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
            partial_return_blocked = "requires a complete implementation return" in str(exc)
        case("partial S4B return cannot advance to S5", partial_return_blocked)
        return_path.write_text(returned, encoding="utf-8")
        s5_dir = sandbox / "R1-S5"
        prepare(ns(stage="S5", project=str(project), output=str(s5_dir), parent=str(s4b_dir), target="http://127.0.0.1:3000", lenses="creative-director (light)"))
        case("isolated S5 packet verifies (positive control)", not verify_packet(s5_dir))
        s5_manifest = json.loads(read(s5_dir / MANIFEST_NAME))
        case("S4B return handoff supports continuation without a fabricated transcript", s5_manifest.get("parent_evidence_kind") == "structured-return-handoff")
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
    prepare_parser.add_argument("--provider", choices=["codex", "claude", "cursor", "other"])
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
        parser().print_help()
        return 0
    except PacketError as exc:
        print(f"STOPPED: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
