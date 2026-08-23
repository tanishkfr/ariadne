#!/usr/bin/env python3
"""Calm runtime controller for Builder OS.

This script hides packet IDs, parent discovery, evidence paths, provider
preflight, and continuation mechanics from the operator. It delegates canonical
transport to prepare-stage.py and never owns routing or gate policy.

Run `python scripts/builderos.py --self-test` for deterministic positive and
negative controls.
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
STATE_NAME = "builderos-run.json"
LOG_NAME = "OPERATIONS.md"
PREFLIGHT_NAME = "provider-preflight.json"
RUNTIME_SCHEMA = 1
FRIENDLY_STAGES = {
    "S1": "project brief",
    "S2": "focused research",
    "S3": "design direction",
    "S4A": "implementation plan",
    "S4B": "implementation and mechanical QA",
    "S5": "independent review",
    "S6": "retrospective",
}
EXPECTED_STAGE_OUTPUTS = {
    "S1": ["PROJECT.md", "AGENTS.md"],
    "S2": ["RESEARCH.md"],
    "S3": ["DESIGN.md", "AGENTS.md"],
    "S4A": ["HANDOFF.md", "AGENTS.md"],
    "S6": ["RETROSPECTIVE.md", "AGENTS.md"],
}
REVIEW_HEADINGS = [
    "Judgement",
    "Accepted patterns",
    "Feel tests",
    "Review lenses",
    "Findings",
    "Review recommendation",
]
HUMAN_INTERVENTION_CATEGORIES = (
    "manual-setup", "file-movement", "prompt-discovery", "routine-confirmation",
    "creative-decision", "external-provider-launch", "review-decision", "unclassified",
)


class RuntimeError_(RuntimeError):
    pass


def load_transport():
    path = ROOT / "scripts" / "prepare-stage.py"
    spec = importlib.util.spec_from_file_location("builder_os_transport", path)
    if spec is None or spec.loader is None:
        raise RuntimeError_("Builder OS transport helper could not be loaded")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


TRANSPORT = load_transport()


def load_creative_intelligence():
    path = ROOT / "scripts" / "creative-intelligence.py"
    spec = importlib.util.spec_from_file_location("builder_os_creative_intelligence", path)
    if spec is None or spec.loader is None:
        raise RuntimeError_("Builder OS creative-intelligence helper could not be loaded")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


CREATIVE = load_creative_intelligence()


def load_creative_operations():
    path = ROOT / "scripts" / "creative-operations.py"
    spec = importlib.util.spec_from_file_location("builder_os_creative_operations", path)
    if spec is None or spec.loader is None:
        raise RuntimeError_("Builder OS creative-operations helper could not be loaded")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


OPERATIONS = load_creative_operations()


def now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value: dict) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


def load_state(run_root: Path) -> dict:
    path = run_root / STATE_NAME
    if not path.is_file():
        raise RuntimeError_(f"No Builder OS run found at {run_root}")
    try:
        state = json.loads(read(path))
    except json.JSONDecodeError as exc:
        raise RuntimeError_(f"Run state is malformed: {exc}") from exc
    if state.get("schema_version") != RUNTIME_SCHEMA:
        raise RuntimeError_("Run state schema is unsupported")
    return state


def slug(value: str) -> str:
    result = re.sub(r"[^A-Za-z0-9]+", "-", value.strip()).strip("-").lower()
    return result or "project"


def default_run_root(project: Path) -> Path:
    return project.parent / f"{project.name}-builderos"


def discover_run_roots(project: Path) -> list[Path]:
    """Find direct-child runtime directories that explicitly name this project."""
    project = project.resolve()
    candidates = []
    try:
        children = list(project.parent.iterdir())
    except OSError as exc:
        raise RuntimeError_(f"Could not inspect the project parent directory: {exc}") from exc
    for child in children:
        state_path = child / STATE_NAME
        if not state_path.is_file():
            continue
        try:
            value = json.loads(read(state_path))
            recorded = Path(value.get("project", "")).resolve()
        except (json.JSONDecodeError, OSError, RuntimeError):
            continue
        if recorded == project:
            candidates.append(child.resolve())
    return sorted(candidates, key=lambda path: str(path).lower())


def resolve_run_root(args: argparse.Namespace) -> Path:
    explicit = getattr(args, "run_root", None)
    if explicit:
        return Path(explicit).resolve()
    project_arg = getattr(args, "project", None)
    if not project_arg:
        raise RuntimeError_("Supply the project or run location")
    project = Path(project_arg).resolve()
    matches = discover_run_roots(project)
    if not matches:
        raise RuntimeError_(f"No Builder OS run records this project: {project}")
    if len(matches) > 1:
        raise RuntimeError_(
            "More than one Builder OS run records this project; choose one explicitly: "
            + ", ".join(str(path) for path in matches)
        )
    return matches[0]


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


def append_log(
    run_root: Path,
    action: str,
    why: str,
    result: str,
    files: list[str] | None = None,
    evidence: str = "",
    next_action: str = "",
) -> None:
    path = run_root / LOG_NAME
    files_text = ", ".join(f"`{item}`" for item in (files or [])) or "none"
    entry = (
        f"\n### {now()} — {action}\n\n"
        f"**Why:** {why}\n\n"
        f"**Result:** {result}\n\n"
        f"**Files:** {files_text}\n\n"
        f"**Evidence:** {evidence or 'none'}\n\n"
        f"**Next:** {next_action or 'none'}\n"
    )
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(entry)


def intervention_summary(state: dict) -> dict:
    rows = state.get("human_interventions", [])
    counts = {
        classification: sum(
            item.get("classification") == classification and item.get("status") != "prevented"
            for item in rows
        )
        for classification in OPERATIONS.INTERVENTION_CLASSES
    }
    def recorded_category(item: dict) -> str | None:
        if item.get("category") in HUMAN_INTERVENTION_CATEGORIES:
            return item["category"]
        need = str(item.get("need", "")).lower()
        if "decide the g1" in need:
            return "creative-decision"
        if "decide g3" in need:
            return "review-decision"
        if need.startswith("start the "):
            return "external-provider-launch"
        if "confirm the external provider" in need:
            return "routine-confirmation"
        return None

    category_counts = {
        category: sum(
            recorded_category(item) == category and item.get("status") != "prevented"
            for item in rows
        )
        for category in HUMAN_INTERVENTION_CATEGORIES
    }
    return {
        "total": sum(item.get("status") != "prevented" for item in rows),
        "necessary_decisions": counts["necessary"],
        "valuable_creative_choices": counts["valuable"],
        "avoidable_interruptions": counts["avoidable"],
        "system_maintenance_interruptions": counts["unacceptable"],
        "by_category": category_counts,
        "mechanical_work": sum(
            category_counts[category]
            for category in ("manual-setup", "file-movement", "prompt-discovery", "routine-confirmation")
        ),
        "external_actions": category_counts["external-provider-launch"],
        "creative_authority": (
            category_counts["creative-decision"] + category_counts["review-decision"]
        ),
        "prevented_interruptions": sum(item.get("status") == "prevented" for item in rows),
        "pending": [item for item in rows if item.get("status") == "pending"],
    }


def ensure_intervention(
    state: dict,
    classification: str,
    need: str,
    reason: str,
    category: str = "unclassified",
    status: str = "pending",
    evidence: str = "",
) -> dict:
    if classification not in OPERATIONS.INTERVENTION_CLASSES:
        raise RuntimeError_(f"Unsupported human intervention classification: {classification}")
    if status not in ("pending", "resolved", "observed", "prevented"):
        raise RuntimeError_(f"Unsupported human intervention status: {status}")
    if category not in HUMAN_INTERVENTION_CATEGORIES:
        raise RuntimeError_(f"Unsupported human intervention category: {category}")
    need = need.strip()
    reason = reason.strip()
    if not need or not reason:
        raise RuntimeError_("A human intervention needs the decision/action and why it matters")
    matches = [
        item for item in state.setdefault("human_interventions", [])
        if item.get("classification") == classification and item.get("need") == need
    ]
    if matches:
        row = matches[-1]
        if not row.get("category"):
            row["category"] = category
        elif row.get("category") != category:
            raise RuntimeError_("That intervention already has a different effort category")
        if row.get("status") == "pending" and status == "resolved":
            row.update({"status": "resolved", "resolved_at": now(), "evidence": evidence})
        return row
    row = {
        "id": f"human-{len(state['human_interventions']) + 1}",
        "classification": classification,
        "category": category,
        "need": need,
        "reason": reason,
        "status": status,
        "recorded_at": now(),
        "evidence": evidence,
    }
    state["human_interventions"].append(row)
    return row


def initial_log(run_id: str, project: Path, request: str) -> str:
    return f"""# Builder OS operations — {run_id}

**Project:** `{project}`  
**Started:** {now()}  
**Builder OS:** `{git_head()}`

This log answers what happened, why, what changed, what was verified, and what
happens next. Canonical policies remain in Builder OS; this is project history.

## Brief

{request.strip()}

## Evidence language

- **Verified:** directly checked or structurally proven.
- **Reasonably assumed:** supported but not directly observed; reason recorded.
- **Externally unverified:** requires a provider or environment that was not run.
- **Blocked:** missing information materially prevents safe continuation.

## Human intervention budget

- **Necessary:** human authority or an unavoidable external action.
- **Valuable:** a creative choice where human judgement materially improves the work.
- **Avoidable:** routine work Builder OS should have handled.
- **Unacceptable:** the human had to repair Builder OS machinery.

Each intervention also records what kind of effort it was: manual setup, file
movement, prompt discovery, routine confirmation, creative decision, external
provider launch, or review decision. Mechanical work and human authority stay
separate even when both are unavoidable in a particular environment.

Structured counts and pending decisions live in `{STATE_NAME}`. The purpose is
to reduce interruption, not to turn it into a score.

## Timeline
"""


def ensure_project(project: Path, adopt_existing: bool = False) -> list[str]:
    project.mkdir(parents=True, exist_ok=True)
    allowed = {".git", ".gitignore"}
    unexpected = sorted(item.name for item in project.iterdir() if item.name not in allowed)
    if unexpected and not adopt_existing:
        raise RuntimeError_(
            "A new Builder OS run needs a fresh project. Existing files found: "
            + ", ".join(unexpected)
            + ". Use --adopt-existing only when preserving this repository is intentional."
        )
    if adopt_existing:
        owned = sorted(name for name in ("PROJECT.md", "AGENTS.md") if (project / name).exists())
        if owned:
            raise RuntimeError_(
                "Existing project already has Builder OS entry documents: "
                + ", ".join(owned)
                + ". Resume its recorded run or migrate those files deliberately; they will not be overwritten."
            )
    ignore = project / ".gitignore"
    if not ignore.exists():
        ignore.write_text(".env\n.env.*\nnode_modules/\n.next/\n", encoding="utf-8")
    if not (project / ".git").exists():
        result = subprocess.run(
            ["git", "init", "-b", "main"], cwd=project, capture_output=True, text=True
        )
        if result.returncode != 0:
            raise RuntimeError_("Could not initialise the project repository: " + result.stderr.strip())
    return unexpected


def transport_namespace(**values) -> argparse.Namespace:
    defaults = dict(
        provider=None,
        packet_id=None,
        parent=None,
        retry=False,
        synthetic_validation=False,
        request=None,
        request_file=None,
        references_file=None,
        motion=None,
        assets=None,
        target=None,
        lenses=None,
    )
    defaults.update(values)
    return argparse.Namespace(**defaults)


def allocate_packet(run_root: Path, run_id: str, stage: str) -> tuple[str, Path]:
    base = f"{run_id}-{stage}"
    candidate = run_root / base
    if not candidate.exists():
        return base, candidate
    index = 1
    while True:
        packet_id = f"{base}-C{index}"
        candidate = run_root / packet_id
        if not candidate.exists():
            return packet_id, candidate
        index += 1


def current_packet(state: dict, allow_project_drift: bool = False) -> tuple[dict, Path]:
    packets = state.get("packets", [])
    if not packets:
        raise RuntimeError_("Run state has no prepared packet")
    entry = packets[-1]
    path = Path(entry["path"])
    problems = TRANSPORT.verify_packet(path)
    if allow_project_drift and problems:
        manifest = json.loads(read(path / TRANSPORT.MANIFEST_NAME))
        expected_project_drift = {
            f"stale source: {source['path']}"
            for source in manifest.get("sources", [])
            if str(source.get("kind", "")).startswith("project")
        }
        problems = [problem for problem in problems if problem not in expected_project_drift]
    if problems:
        raise RuntimeError_("Current packet is stale or damaged: " + "; ".join(problems))
    return entry, path


def start(args: argparse.Namespace) -> int:
    project = Path(args.project).resolve()
    adopt_existing = bool(getattr(args, "adopt_existing", False))
    run_root = Path(args.run_root).resolve() if args.run_root else default_run_root(project)
    if run_root.exists():
        raise RuntimeError_(
            f"A run directory already exists at {run_root}. Resume it instead of starting over."
        )
    request = args.request
    if args.request_file:
        request = read(Path(args.request_file).resolve()).strip()
    if not request or not request.strip():
        raise RuntimeError_("A new run needs an ordinary-language request")
    existing_entries = ensure_project(project, adopt_existing)
    run_root.mkdir(parents=True)
    run_id = args.run_id or slug(project.name)
    (run_root / LOG_NAME).write_text(initial_log(run_id, project, request), encoding="utf-8")

    packet_id, output = allocate_packet(run_root, run_id, "S1")
    TRANSPORT.prepare(
        transport_namespace(
            stage="S1",
            project=str(project),
            output=str(output),
            packet_id=packet_id,
            request=request,
            adopt_existing=adopt_existing,
            synthetic_validation=args.synthetic_validation,
        )
    )
    state = {
        "schema_version": RUNTIME_SCHEMA,
        "run_id": run_id,
        "project": str(project),
        "run_root": str(run_root),
        "created_at": now(),
        "updated_at": now(),
        "status": "active",
        "request": request.strip(),
        "adopt_existing": adopt_existing,
        "evidence_state": "verified-transport; provider stage not yet observed",
        "packets": [{"id": packet_id, "stage": "S1", "path": str(output)}],
        "provider_preflight": None,
        "notes": [],
        "human_interventions": [],
        "creative_evidence_required": True,
        "next": "Complete the project brief from the prepared context.",
    }
    write_json(run_root / STATE_NAME, state)
    append_log(
        run_root,
        "Project started",
        (
            "An existing project needs a non-destructive verified intake boundary."
            if adopt_existing
            else "A fresh ordinary-language brief needs a verified intake boundary."
        ),
        (
            "Verified: existing project preserved and S1 adoption packet prepared; "
            + f"top-level entries observed: {', '.join(existing_entries) or 'none'}."
            if adopt_existing
            else "Verified: fresh project shell and S1 packet prepared."
        ),
        [str(project / ".gitignore"), str(output / "packet.txt"), str(output / "manifest.json")],
        "Packet source parity passed; no provider stage has run.",
        "Builder OS should read and run the prepared project-brief packet.",
    )
    print("Done. The project is ready for its brief and discovery pass.")
    print("From you: nothing to locate or assemble; describe the project normally.")
    return 0


def state_field(text: str, name: str) -> str:
    match = re.search(rf"(?m)^\|\s*\*\*{re.escape(name)}\*\*\s*\|\s*`?([^|`]+)", text)
    return match.group(1).strip() if match else ""


def safe_section(text: str, heading: str) -> str:
    try:
        return TRANSPORT.markdown_section(text, heading)
    except TRANSPORT.PacketError:
        return ""


def plain_markdown(value: str) -> str:
    value = re.sub(r"[`*_]", "", value.strip())
    value = re.sub(r"\[([^]]+)]\([^)]+\)", r"\1", value)
    return re.sub(r"\s+", " ", value).strip()


def first_meaningful_line(section: str) -> str:
    for raw in section.splitlines():
        line = raw.strip()
        if (
            not line
            or line.startswith((">", "|", "#", "```", "~~~"))
            or re.fullmatch(r"[-: ]+", line)
        ):
            continue
        line = re.sub(r"^(?:[-*+] |\d+\.\s+)", "", line)
        value = plain_markdown(line)
        if value and not value.startswith("<"):
            return value
    return "not yet recorded"


def first_meaningful_paragraph(section: str) -> str:
    lines: list[str] = []
    for raw in section.splitlines():
        line = raw.strip()
        if not line:
            if lines:
                break
            continue
        if line.startswith((">", "|", "#", "```", "~~~")) or re.fullmatch(r"[-: ]+", line):
            if lines:
                break
            continue
        if re.match(r"^(?:[-*+] |\d+\.\s+)", line):
            if lines:
                break
            continue
        value = plain_markdown(line)
        if value and not value.startswith("<"):
            lines.append(value)
    return " ".join(lines) if lines else "not yet recorded"


def numbered_items(section: str) -> list[str]:
    items = []
    for line in section.splitlines():
        match = re.match(r"^\s*\d+\.\s+(.+?)\s*$", line)
        if match:
            value = plain_markdown(match.group(1))
            if value and "<" not in value:
                items.append(value)
    return items


def markdown_table_rows(section: str) -> list[list[str]]:
    rows = []
    for line in section.splitlines():
        if not line.strip().startswith("|"):
            continue
        cells = [plain_markdown(cell) for cell in line.strip().strip("|").split("|")]
        if not cells or all(re.fullmatch(r"[-: ]*", cell) for cell in cells):
            continue
        rows.append(cells)
    return rows[1:] if len(rows) > 1 else []


def project_mode(project_text: str) -> str:
    match = re.search(r"(?im)^\*\*Mode:\*\*\s*([^·\n]+)", project_text)
    return plain_markdown(match.group(1)) if match else "not yet recorded"


def design_thesis(text: str) -> str:
    section = safe_section(text, "Design thesis")
    for line in section.splitlines():
        match = re.match(r"^\s*\*\*(.+?)\*\*\s*$", line)
        if match and "<" not in match.group(1):
            return plain_markdown(match.group(1))
    return ""


def canonical_handoff_headings() -> list[str]:
    template = read(ROOT / "templates" / "HANDOFF.md")
    return [
        heading.strip()
        for heading in re.findall(r"(?m)^##\s+(.+?)\s*$", template)
        if heading.strip() != "If the design cannot be built as specified"
    ]


def handoff_context_problems(project: Path) -> list[str]:
    """Validate implementation context without owning the handoff's policy."""
    problems = []
    required = ["PROJECT.md", "DESIGN.md", "AGENTS.md", "HANDOFF.md"]
    missing = [name for name in required if not (project / name).is_file()]
    if missing:
        return ["missing implementation input: " + ", ".join(missing)]

    project_text = read(project / "PROJECT.md")
    design_text = read(project / "DESIGN.md")
    agents_text = read(project / "AGENTS.md")
    handoff_text = read(project / "HANDOFF.md")

    if not re.search(r"(?im)^\*\*Status:\*\*.*locked at G1", design_text):
        problems.append("DESIGN.md does not record a human-locked G1 direction")
    if not re.match(r"G1\b", state_field(agents_text, "Last gate passed")):
        problems.append("AGENTS.md does not record human G1 approval")

    for heading in canonical_handoff_headings():
        if not re.search(rf"(?im)^##\s+{re.escape(heading)}\s*$", handoff_text):
            problems.append(f"HANDOFF.md is missing canonical section: {heading}")
    placeholders = sorted(set(re.findall(r"<[^>\n]+>", handoff_text)))
    if placeholders:
        problems.append("HANDOFF.md still contains placeholders: " + ", ".join(placeholders[:5]))

    design_value = design_thesis(design_text)
    handoff_value = design_thesis(handoff_text)
    if not design_value or not handoff_value:
        problems.append("the approved design thesis is missing from DESIGN.md or HANDOFF.md")
    elif handoff_value != design_value:
        problems.append("HANDOFF.md does not carry the approved design thesis verbatim")

    project_criteria = numbered_items(safe_section(project_text, "Success criteria"))
    handoff_criteria = numbered_items(safe_section(handoff_text, "Outcome and acceptance criteria"))
    if not project_criteria:
        problems.append("PROJECT.md has no concrete success criteria")
    elif handoff_criteria != project_criteria:
        problems.append("HANDOFF.md does not carry PROJECT.md success criteria verbatim")

    if first_meaningful_line(safe_section(handoff_text, "Content readiness")) == "not yet recorded":
        problems.append("HANDOFF.md does not resolve content readiness")
    if first_meaningful_line(safe_section(handoff_text, "Implementer discretion")) == "not yet recorded":
        problems.append("HANDOFF.md does not define implementation judgement boundaries")

    dependencies = markdown_table_rows(safe_section(handoff_text, "Dependencies to install"))
    for row in dependencies:
        if not row or row[0].lower() in ("none", "n/a"):
            continue
        if len(row) < 3 or not row[1] or not row[2] or row[2].lower() in ("pending", "unapproved"):
            problems.append(f"dependency is not versioned and G2-approved: {row[0]}")

    assets = markdown_table_rows(safe_section(handoff_text, "Asset requirements"))
    for row in assets:
        if not row or row[0].lower() in ("none", "n/a"):
            continue
        status = row[1].lower() if len(row) > 1 else ""
        blocking = row[3].lower() if len(row) > 3 else ""
        if blocking in ("yes", "true", "blocking") and status not in ("ready", "substituted"):
            problems.append(f"critical asset is unresolved: {row[0]} ({status or 'unknown'})")

    try:
        handoff_routing(project)
    except RuntimeError_ as exc:
        problems.append(str(exc))
    if not (ROOT / "templates" / "RETURN-HANDOFF.md").is_file():
        problems.append("canonical implementation return contract is missing")
    problems.extend(CREATIVE.project_problems(project))
    return problems


def packet_evidence(packet: Path, manifest: dict) -> list[str]:
    evidence = []
    transcript = packet / manifest.get("expected_transcript", "evidence/transcript.md")
    if transcript.is_file():
        evidence.append("verbatim transcript")
    if (packet / "evidence" / "stage-result.json").is_file():
        evidence.append("structural stage result")
    if (packet / "evidence" / "return-handoff.md").is_file():
        evidence.append("structured return handoff")
    if (packet / "evidence" / "review-judgement.md").is_file():
        evidence.append("independent review judgement")
    return evidence


def latest_evidence_path(state: dict, name: str) -> Path | None:
    for entry in reversed(state.get("packets", [])):
        candidate = Path(entry["path"]) / "evidence" / name
        if candidate.is_file():
            return candidate
    return None


def project_runtime(project: Path) -> dict:
    agents = project / "AGENTS.md"
    result = {"stage": "unrecorded", "gate": "unrecorded", "next_prompt": "unrecorded"}
    if agents.is_file():
        text = read(agents)
        result = {
            "stage": state_field(text, "Stage") or "unrecorded",
            "gate": state_field(text, "Last gate passed") or "unrecorded",
            "next_prompt": state_field(text, "Next prompt") or "unrecorded",
        }
    return result


def retry_count(state: dict, stage: str) -> int:
    count = 0
    for entry in state.get("packets", []):
        if entry.get("stage") != stage:
            continue
        manifest = Path(entry["path"]) / TRANSPORT.MANIFEST_NAME
        if manifest.is_file():
            try:
                count += int(bool(json.loads(read(manifest)).get("retry")))
            except (json.JSONDecodeError, OSError):
                continue
    return count


def provider_evidence(run_root: Path, state: dict, return_record: dict) -> dict:
    """Project selected, executed, and successful-return states without inference."""
    preflight = state.get("provider_preflight") or {}
    selected_provider = preflight.get("provider")
    selected = {
        "state": "selected" if selected_provider else "not-selected",
        "provider": selected_provider or "not recorded",
        "evidence": str(run_root / PREFLIGHT_NAME) if selected_provider else "none",
    }
    transcript = None
    for entry in reversed(state.get("packets", [])):
        if entry.get("stage") != "S4B":
            continue
        candidate = Path(entry["path"]) / "evidence" / "transcript.md"
        if candidate.is_file():
            transcript = candidate
            break
    returned = latest_evidence_path(state, "return-handoff.md")
    if transcript:
        executed = {"state": "observed-in-transcript", "evidence": str(transcript)}
    elif returned:
        executed = {"state": "reported-by-provider-return", "evidence": str(returned)}
    else:
        executed = {"state": "not-observed", "evidence": "none"}
    return_status = str(return_record.get("metadata", {}).get("status", "")).strip().lower()
    if not returned:
        successful_return = {"state": "not-returned", "evidence": "none"}
    elif return_status == "complete":
        successful_return = {"state": "reported-complete", "evidence": str(returned)}
    else:
        successful_return = {
            "state": f"reported-{return_status or 'unknown'}", "evidence": str(returned)
        }
    return {
        "selected": selected,
        "executed": executed,
        "returned_successfully": successful_return,
    }


def project_intelligence(
    run_root: Path, state: dict, entry: dict, packet: Path, manifest: dict
) -> dict:
    project = Path(state["project"])
    project_text = read(project / "PROJECT.md") if (project / "PROJECT.md").is_file() else ""
    design_text = read(project / "DESIGN.md") if (project / "DESIGN.md").is_file() else ""
    handoff_text = read(project / "HANDOFF.md") if (project / "HANDOFF.md").is_file() else ""
    qa_text = read(project / "QA.md") if (project / "QA.md").is_file() else ""
    runtime = project_runtime(project)
    stage = entry["stage"]
    creative_ledger = CREATIVE.load_ledger(project)
    creative_summary = CREATIVE.summary(creative_ledger)
    creative_problems = CREATIVE.project_problems(project)
    operations_ledger = OPERATIONS.load_ledger(project)
    operations_summary = OPERATIONS.summary(operations_ledger)
    operations_problems = OPERATIONS.project_problems(project)
    creative_quality = {
        "state": "not-reviewed",
        "strongest": "not yet observed",
        "weakest": "not yet observed",
        "highest_value_improvement": "not yet identified",
        "iteration": "not reviewed",
    }
    if operations_ledger and operations_ledger.get("creative_reviews"):
        latest_review = operations_ledger["creative_reviews"][-1]
        creative_quality = {
            "state": (
                "ready"
                if latest_review.get("iteration") == "no"
                else "needs-human"
                if latest_review.get("iteration") == "conditional"
                else "needs-iteration"
            ),
            "strongest": latest_review.get("strongest", "not recorded"),
            "weakest": latest_review.get("weakest", "not recorded"),
            "highest_value_improvement": latest_review.get(
                "highest_value_improvement", "not recorded"
            ),
            "iteration": latest_review.get("iteration", "not recorded"),
            "review_id": latest_review.get("id", "not recorded"),
        }

    open_rows = markdown_table_rows(safe_section(project_text, "Open questions"))
    blocking_questions = [
        row[1] if len(row) > 1 else row[0]
        for row in open_rows
        if row and row[-1].lower() in ("yes", "true", "blocking") and "<" not in " ".join(row)
    ]
    reference_rows = [
        row for row in markdown_table_rows(safe_section(project_text, "References"))
        if row and "<" not in " ".join(row)
    ]
    constraint_rows = [
        row for row in markdown_table_rows(safe_section(project_text, "Constraints"))
        if row and "<" not in " ".join(row)
    ]
    fixed_decisions = [
        row for row in markdown_table_rows(safe_section(handoff_text, "Decisions that are fixed"))
        if row and "<" not in " ".join(row)
    ]
    design_value = design_thesis(design_text)
    g1_locked = bool(re.search(r"(?im)^\*\*Status:\*\*.*locked at G1", design_text))

    health = []

    def add(area: str, status_value: str, detail: str) -> None:
        health.append({"area": area, "state": status_value, "detail": detail})

    brief_ready = bool(project_text and (project / "AGENTS.md").is_file())
    add("brief", "ready" if brief_ready else "pending", "Goal and project runtime state are recorded." if brief_ready else "The project brief is still being developed.")

    if (project / "RESEARCH.md").is_file():
        add("research", "ready", "Focused research evidence is recorded.")
    elif blocking_questions:
        add("research", "attention", f"{len(blocking_questions)} blocking question(s) need evidence.")
    else:
        add("research", "not-needed", "No blocking research question is recorded.")

    if creative_ledger is None:
        if state.get("creative_evidence_required"):
            add("creative evidence", "attention", "Skill and research planning has not been recorded yet.")
        else:
            add("creative evidence", "not-needed", "Legacy run: creative provenance was not required when it started.")
    elif creative_problems:
        add("creative evidence", "attention", creative_problems[0])
    else:
        references = creative_summary["references"]
        add(
            "creative evidence",
            "ready",
            (
                f"{creative_summary['completed']}/{creative_summary['selected']} selected capabilities completed or used; "
                f"{references['inspected']} inspected reference(s), {creative_summary['decisions']} traced decision(s)."
            ),
        )

    if operations_ledger is None:
        if g1_locked and stage in ("S4A", "S4B", "S5", "S6"):
            add("design trace", "attention", "The approved direction has no generated implementation/visual-QA trace yet.")
        else:
            add("design trace", "not-needed", "Post-G1 trace begins only after the direction is human-approved.")
    elif operations_problems:
        add("design trace", "attention", operations_problems[0])
    else:
        add(
            "design trace",
            "ready",
            (
                f"{operations_summary['requirements']} approved requirement(s); "
                f"{operations_summary['implemented']} implemented and "
                f"{operations_summary['observed']} directly observed."
            ),
        )

    if stage in ("S4B", "S5", "S6"):
        review_problems = OPERATIONS.project_problems(project, "review")
        if review_problems:
            add("creative quality", "attention", review_problems[0])
        else:
            add(
                "creative quality",
                "ready",
                "Rendered evidence, drift classification, and the latest internal review are complete.",
            )
    else:
        add("creative quality", "not-needed", "Rendered creative review begins during implementation.")

    if g1_locked and design_value:
        add("direction", "ready", "The human-approved thesis is locked at G1.")
    elif design_text:
        add("direction", "needs-human", "A direction exists and needs human judgement at G1.")
    else:
        add("direction", "pending", "No design direction has been written yet.")

    design_assets = markdown_table_rows(safe_section(design_text, "Asset direction"))
    unresolved_assets = [
        row[0] for row in design_assets
        if row and len(row) > 3 and row[3].lower() in ("yes", "true", "blocking")
        and len(row) > 1 and row[1].lower() not in ("yes", "ready", "substituted")
    ]
    if unresolved_assets:
        add("assets", "attention", "Critical assets unresolved: " + ", ".join(unresolved_assets))
    elif design_text:
        add("assets", "ready", "No unresolved critical asset is recorded.")
    else:
        add("assets", "pending", "Asset needs are decided with the design direction.")

    dependency_rows = [
        row for row in markdown_table_rows(safe_section(handoff_text, "Dependencies to install"))
        if row and row[0].lower() not in ("none", "n/a")
    ]
    unapproved = [
        row[0] for row in dependency_rows
        if len(row) < 3 or not row[2] or row[2].lower() in ("pending", "unapproved")
    ]
    if unapproved:
        add("dependencies", "attention", "G2 approval missing: " + ", ".join(unapproved))
    elif handoff_text:
        add("dependencies", "ready", f"{len(dependency_rows)} approved dependency item(s); no unresolved G2 item." if dependency_rows else "No external dependency is required.")
    else:
        add("dependencies", "pending", "Dependencies are decided in the implementation plan.")

    if handoff_text:
        readiness = handoff_context_problems(project)
        add("handoff", "attention" if readiness else "ready", readiness[0] if readiness else "Implementation context is complete and internally consistent.")
    else:
        add("handoff", "pending", "The implementation plan has not been written yet.")

    preflight = state.get("provider_preflight") or {}
    decision = preflight.get("decision")
    if decision in ("verified", "reasonably-assumed", "not-required"):
        add("provider", "ready", preflight.get("reason", "Provider route is ready."))
    elif decision in ("blocked", "human-check-required"):
        add("provider", "attention", preflight.get("reason", "Provider route needs attention."))
    else:
        add("provider", "pending", "Provider readiness is checked immediately before implementation.")

    returned = latest_evidence_path(state, "return-handoff.md")
    machine_return = latest_evidence_path(state, "return-handoff.json")
    return_record = {}
    if machine_return:
        try:
            return_record = json.loads(read(machine_return))
        except json.JSONDecodeError:
            return_record = {}
    if returned and returned.is_file() and TRANSPORT.return_handoff_status(read(returned)) == "complete":
        add("implementation", "ready", "A complete structured implementation return is recorded.")
    elif stage == "S4B":
        add("implementation", "in-progress", "Implementation has not returned complete evidence yet.")
    elif stage in ("S5", "S6"):
        add("implementation", "ready", "Implementation reached verification.")
    else:
        add("implementation", "pending", "Implementation has not started.")

    review_recorded = (packet / "evidence" / "review-judgement.md").is_file()
    if review_recorded or ("**Reviewed independently:** yes" in qa_text):
        add("QA", "needs-human", "Mechanical and independent evidence are ready for human G3 judgement.")
    elif qa_text:
        add("QA", "attention", "Mechanical QA exists; independent review is not yet recorded.")
    else:
        add("QA", "pending", "QA evidence is created during and after implementation.")

    add("continuity", "ready", "The current packet, parent provenance, and evidence boundary verify.")
    attention = [item for item in health if item["state"] in ("attention", "needs-human")]
    if any(item["state"] == "attention" for item in attention):
        overall = "attention"
    elif any(item["state"] == "needs-human" for item in attention):
        overall = "needs-human"
    else:
        overall = "on-track"

    if stage == "S3" and design_text and not g1_locked:
        human_need = "Review the proposed design direction and approve, reject, or redirect it."
    elif decision == "human-check-required":
        human_need = "Confirm the selected provider's current availability and usable quota."
    elif stage == "S4B" and not returned:
        human_need = "Start the selected implementation provider with the prepared handoff."
    elif stage == "S5" and review_recorded:
        human_need = "Decide whether the combined build and review evidence is acceptable at G3."
    else:
        human_need = "Nothing right now; Builder OS can continue the current work."

    notes = state.get("notes", [])
    return_sections = return_record.get("sections", {})
    completed_work = first_meaningful_line(return_sections.get("what-was-built", ""))
    known_issues = first_meaningful_line(return_sections.get("known-issues", ""))
    if known_issues.lower() in ("none", "none known"):
        known_issues = "none known"
    lessons = [item["summary"] for item in notes if item.get("kind") == "lesson"]
    risks = [
        item["summary"] for item in notes
        if item.get("kind") in ("risk", "evidence-gap")
    ]
    return {
        "project_name": project.name,
        "mode": project_mode(project_text),
        "goal": first_meaningful_paragraph(safe_section(project_text, "Goal")),
        "current_work": FRIENDLY_STAGES.get(stage, stage),
        "approved_direction": design_value if g1_locked else "not yet approved",
        "proposed_direction": design_value if design_value and not g1_locked else "none",
        "rejected_direction_attempts": retry_count(state, "S3"),
        "blocking_questions": blocking_questions,
        "open_questions": [row[1] if len(row) > 1 else row[0] for row in open_rows if row],
        "constraints": [dict(name=row[0], detail=row[1] if len(row) > 1 else "") for row in constraint_rows],
        "references": [row[0] for row in reference_rows],
        "important_decisions": [dict(name=row[0], value=row[1] if len(row) > 1 else "") for row in fixed_decisions],
        "implementation": {
            "status": return_record.get("metadata", {}).get("status", "not returned"),
            "provider": return_record.get("metadata", {}).get("provider", "not yet selected"),
            "completed_work": completed_work,
            "known_issues": known_issues,
        },
        "provider_evidence": provider_evidence(run_root, state, return_record),
        "risks_and_evidence_gaps": risks,
        "lessons": lessons,
        "runtime_state": runtime,
        "creative": creative_summary,
        "creative_operations": operations_summary,
        "creative_quality": creative_quality,
        "human_effort": intervention_summary(state),
        "health": health,
        "overall_health": overall,
        "notes": notes,
        "next_recommended_action": state.get("next", "Continue from the current verified boundary."),
        "needs_from_human": human_need,
        "evidence": packet_evidence(packet, manifest) or ["not yet recorded"],
        "operations_log": str(run_root / LOG_NAME),
    }


def status(args: argparse.Namespace) -> int:
    run_root = resolve_run_root(args)
    state = load_state(run_root)
    entry, packet = current_packet(state, allow_project_drift=True)
    manifest = json.loads(read(packet / TRANSPORT.MANIFEST_NAME))
    intelligence = project_intelligence(run_root, state, entry, packet, manifest)
    payload = {
        "run_id": state["run_id"],
        "project": state["project"],
        "status": state["status"],
        "current_boundary": entry["stage"],
        "packet": str(packet / "packet.txt"),
        "packet_verified": True,
        "intelligence": intelligence,
        "provider_preflight": state.get("provider_preflight") or "not run",
    }
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        attention = [
            item for item in intelligence["health"]
            if item["state"] in ("attention", "needs-human")
        ]
        print(f"{intelligence['project_name']}")
        print(f"Goal: {intelligence['goal']}")
        print(f"Where we left off: {intelligence['current_work']}.")
        if intelligence["approved_direction"] != "not yet approved":
            print(f"Approved direction: {intelligence['approved_direction']}")
        elif intelligence["proposed_direction"] != "none":
            print(f"Proposed direction (G1 pending): {intelligence['proposed_direction']}")
        else:
            print("Direction: not yet proposed")
        print(f"Project health: {intelligence['overall_health'].replace('-', ' ')}")
        quality = intelligence["creative_quality"]
        if quality["state"] != "not-reviewed":
            print(f"Strongest observed: {quality['strongest']}")
            print(f"Weakest observed: {quality['weakest']}")
            print(f"Creative iteration: {quality['iteration']}")
        effort = intelligence["human_effort"]
        print(
            "Human effort: "
            f"{effort['creative_authority']} creative/review decision(s), "
            f"{effort['external_actions']} external action(s), "
            f"{effort['mechanical_work']} mechanical interruption(s)."
        )
        if attention:
            print("Attention: " + "; ".join(item["detail"] for item in attention))
        print(f"Next: {intelligence['next_recommended_action']}")
        print(f"From you: {intelligence['needs_from_human']}")
    return 0


def discover(args: argparse.Namespace) -> int:
    project = Path(args.project).resolve()
    matches = discover_run_roots(project)
    if not matches:
        raise RuntimeError_(f"No Builder OS run records this project: {project}")
    payload = {"project": str(project), "runs": [str(path) for path in matches]}
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        if len(matches) == 1:
            print(f"Found the Builder OS run for {project.name}: {matches[0]}")
        else:
            print(f"Found {len(matches)} Builder OS runs for {project.name}:")
            for path in matches:
                print(f"  {path}")
            print("Choose the intended run explicitly; Builder OS will not guess between histories.")
    return 0 if len(matches) == 1 else 2


def preflight_decision(availability: str, quota: str, workload: str) -> tuple[str, str]:
    if availability == "unavailable":
        return "blocked", "The provider is unavailable. Use a fallback or wait."
    if quota == "insufficient":
        return "blocked", "Available usage is insufficient. Split, switch provider, or wait."
    if availability == "limited" and workload == "large":
        return "blocked", "Limited availability is not suitable for one large implementation task."
    if workload == "large" and (availability == "unknown" or quota == "unknown"):
        return "human-check-required", "A large external task needs an observable availability/quota check."
    if availability == "available" and quota == "sufficient":
        return "verified", "Provider and available usage were explicitly confirmed."
    return "reasonably-assumed", "No blocking provider signal is known; the bounded workload may proceed."


def preflight_recommendation(
    decision: str, provider: str, workload: str, fallback: str | None
) -> str:
    if decision in ("verified", "reasonably-assumed", "not-required"):
        return f"Proceed with {provider}; keep the structured return handoff as the continuity boundary."
    if fallback:
        return f"Use {fallback} after recording it in HANDOFF.md and rerunning preflight."
    if decision == "human-check-required":
        return f"Check {provider} once before launch; if capacity is limited, split the work or use the recorded fallback."
    if workload == "large":
        return "Split the implementation into independently returnable tasks or choose an available fallback."
    return "Choose an available provider with the same capability class, then rerun preflight."


def handoff_routing(project: Path) -> dict[str, str]:
    handoff = project / "HANDOFF.md"
    if not handoff.is_file():
        raise RuntimeError_("Provider preflight requires the completed HANDOFF.md")
    section = TRANSPORT.markdown_section(read(handoff), "Implementation routing")
    values = {}
    for line in section.splitlines():
        if not line.lstrip().startswith("|") or "---" in line:
            continue
        cells = [cell.strip().strip("`") for cell in line.strip().strip("|").split("|")]
        if len(cells) >= 2 and cells[0].lower() != "field":
            values[cells[0].lower()] = cells[1]
    required = ("capability needed", "provider", "model", "effort", "workload", "split", "reason")
    missing = [name for name in required if not values.get(name) or "<" in values[name]]
    if missing:
        raise RuntimeError_("HANDOFF.md has incomplete implementation routing: " + ", ".join(missing))
    return values


def provider_preflight(args: argparse.Namespace) -> int:
    run_root = resolve_run_root(args)
    state = load_state(run_root)
    project = Path(state["project"])
    context_problems = handoff_context_problems(project)
    if context_problems:
        raise RuntimeError_(
            "Implementation handoff is not ready: " + "; ".join(context_problems)
        )
    routing = handoff_routing(project)
    provider = args.provider or routing["provider"]
    model = args.model or routing["model"]
    effort = args.effort or routing["effort"].lower()
    workload = args.workload or routing["workload"].lower()
    if effort not in ("low", "medium", "high"):
        raise RuntimeError_(f"HANDOFF.md has unsupported effort: {effort}")
    if workload not in ("small", "medium", "large"):
        raise RuntimeError_(f"HANDOFF.md has unsupported workload: {workload}")
    retained = provider.strip().lower() in ("retain in orchestrator", "orchestrator")
    if retained:
        decision = "not-required"
        reason = "Implementation remains in the orchestrator; no external provider preflight is required."
    else:
        decision, reason = preflight_decision(args.availability, args.quota, workload)
    recommendation = preflight_recommendation(
        decision, provider, workload, args.fallback
    )
    record = {
        "schema_version": 1,
        "checked_at": now(),
        "capability": routing["capability needed"],
        "provider": provider,
        "model": model,
        "effort": effort,
        "workload": workload,
        "availability": args.availability,
        "quota": args.quota,
        "decision": decision,
        "reason": reason,
        "split": routing["split"],
        "routing_reason": routing["reason"],
        "fallback": args.fallback or "not supplied",
        "recommendation": recommendation,
    }
    write_json(run_root / PREFLIGHT_NAME, record)
    state["provider_preflight"] = record
    state["updated_at"] = now()
    state["next"] = (
        "Prepare the verified external build handoff."
        if decision in ("verified", "reasonably-assumed", "not-required")
        else recommendation
    )
    if decision == "human-check-required":
        ensure_intervention(
            state,
            "necessary",
            "Confirm the external provider's available quota.",
            "A large external task cannot safely proceed from an unobserved capacity assumption.",
            "routine-confirmation",
        )
    write_json(run_root / STATE_NAME, state)
    append_log(
        run_root,
        "Provider preflight",
        "External implementation should not discover preventable availability limits mid-build.",
        f"{decision}: {reason}",
        [str(run_root / PREFLIGHT_NAME)],
        f"provider={provider}; model={model}; effort={effort}; workload={workload}; availability={args.availability}; quota={args.quota}",
        state["next"],
    )
    print(f"Provider readiness: {decision.replace('-', ' ')}")
    print(reason)
    print(f"Recommendation: {recommendation}")
    return 0 if decision in ("verified", "reasonably-assumed", "not-required") else 2


def handoff_readiness_command(args: argparse.Namespace) -> int:
    run_root = resolve_run_root(args)
    state = load_state(run_root)
    project = Path(state["project"])
    problems = handoff_context_problems(project)
    preflight = state.get("provider_preflight") or {}
    decision = preflight.get("decision", "not-run")
    if problems:
        status_value = "blocked"
        next_action = "Complete the named implementation-plan gaps before provider launch."
    elif decision not in ("verified", "reasonably-assumed", "not-required"):
        status_value = "provider-check-needed"
        next_action = "Check the selected provider's current suitability and availability."
    else:
        status_value = "ready"
        next_action = "Start the selected implementation provider with the verified handoff."
    payload = {
        "status": status_value,
        "project": str(project),
        "context_problems": problems,
        "provider_preflight": preflight or "not run",
        "next": next_action,
    }
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        if status_value == "ready":
            print("Ready. The implementation agent has complete, consistent context.")
        elif problems:
            print("Not ready. The implementation plan still has gaps:")
            for problem in problems:
                print(f"- {problem}")
        else:
            print("The implementation plan is complete. Provider readiness still needs one check.")
        print(f"Next: {next_action}")
    return 0 if status_value == "ready" else 2


def structural_result(args: argparse.Namespace) -> int:
    run_root = resolve_run_root(args)
    state = load_state(run_root)
    entry, packet = current_packet(state, allow_project_drift=True)
    destination = packet / "evidence" / "stage-result.json"
    if destination.exists():
        raise RuntimeError_(f"Refusing to overwrite existing stage evidence: {destination}")
    project = Path(state["project"])
    files = []
    for value in args.file:
        path = (project / value).resolve() if not Path(value).is_absolute() else Path(value).resolve()
        try:
            path.relative_to(project.resolve())
        except ValueError as exc:
            raise RuntimeError_(f"Stage output is outside the project: {path}") from exc
        if not path.is_file():
            raise RuntimeError_(f"Stage output does not exist: {path}")
        files.append({"path": str(path), "sha256": sha256(path)})
    result = {
        "schema_version": 1,
        "packet_id": entry["id"],
        "stage": entry["stage"],
        "status": args.status,
        "recorded_at": now(),
        "provider": args.provider,
        "model": args.model,
        "summary": args.summary,
        "evidence_class": "structurally-verified; provider transcript not captured",
        "files": files,
    }
    write_json(destination, result)
    state["updated_at"] = now()
    state["evidence_state"] = result["evidence_class"]
    state["next"] = "Discover and prepare the next valid boundary."
    write_json(run_root / STATE_NAME, state)
    append_log(
        run_root,
        f"{entry['stage']} result recorded",
        "The project outputs are available but a verbatim transcript is not required for safe structural continuation.",
        f"{args.status}: {args.summary}",
        [item["path"] for item in files] + [str(destination)],
        result["evidence_class"],
        state["next"],
    )
    print("Done. Project outputs were hashed and recorded without fabricating a transcript.")
    return 0


def record_transcript(args: argparse.Namespace) -> int:
    run_root = resolve_run_root(args)
    state = load_state(run_root)
    _entry, packet = current_packet(state, allow_project_drift=True)
    source = Path(args.input).resolve()
    if not source.is_file() or source.stat().st_size == 0:
        raise RuntimeError_("Transcript input is missing or empty")
    destination = packet / "evidence" / "transcript.md"
    if destination.exists():
        raise RuntimeError_(f"Refusing to overwrite existing transcript: {destination}")
    shutil.copyfile(source, destination)
    append_log(
        run_root,
        "Verbatim transcript recorded",
        "Provider evidence was available and should be preserved exactly.",
        "Verified byte-for-byte copy.",
        [str(destination)],
        f"SHA-256 {sha256(destination)}",
        "Discover and prepare the next valid boundary.",
    )
    state["evidence_state"] = "verbatim transcript recorded"
    state["updated_at"] = now()
    state["next"] = "Discover and prepare the next valid boundary."
    write_json(run_root / STATE_NAME, state)
    print("Done. The transcript was preserved verbatim.")
    return 0


def ingest_return(args: argparse.Namespace) -> int:
    run_root = resolve_run_root(args)
    state = load_state(run_root)
    entry, packet = current_packet(state, allow_project_drift=True)
    if entry["stage"] != "S4B":
        raise RuntimeError_("Implementation return handoffs belong to the current S4B boundary")
    source = Path(args.input).resolve()
    if not source.is_file():
        raise RuntimeError_(f"Return handoff input is missing: {source}")
    text = read(source)
    begin = "BEGIN BUILDER OS RETURN HANDOFF"
    end = "END BUILDER OS RETURN HANDOFF"
    if text.count(begin) == 1 and text.count(end) == 1:
        text = text.split(begin, 1)[1].split(end, 1)[0].strip() + "\n"
    problems = TRANSPORT.return_handoff_problems(text)
    if problems:
        raise RuntimeError_("Return handoff rejected: " + "; ".join(problems))
    destination = packet / "evidence" / "return-handoff.md"
    machine_destination = packet / "evidence" / "return-handoff.json"
    if destination.exists() or machine_destination.exists():
        raise RuntimeError_(f"Refusing to overwrite existing return handoff: {destination}")
    destination.write_text(text, encoding="utf-8")
    metadata = {}
    for field in ("Status", "Provider", "Model", "Effort", "Started", "Ended"):
        match = re.search(rf"(?im)^\*\*{re.escape(field)}:\*\*\s*(.+?)\s*$", text)
        metadata[field.lower()] = match.group(1).strip() if match else "unrecorded"
    return_status = metadata["status"].lower()
    sections = {
        slug(heading): safe_section(text, heading).strip()
        for heading in TRANSPORT.RETURN_HANDOFF_HEADINGS
    }
    write_json(
        machine_destination,
        {
            "schema_version": 1,
            "recorded_at": now(),
            "packet_id": entry["id"],
            "source": str(destination),
            "source_sha256": sha256(destination),
            "metadata": metadata,
            "sections": sections,
            "evidence_class": "structured provider report; not a transcript or independent review",
        },
    )
    state["updated_at"] = now()
    state["evidence_state"] = "structured external return; transcript remains separate"
    state["next"] = (
        "Prepare independent review after verifying QA evidence."
        if return_status == "complete"
        else "Resume from the incomplete-work section or route the blocker."
    )
    ensure_intervention(
        state,
        "necessary",
        "Start the selected external implementation provider.",
        "The current provider boundary cannot execute without the human opening or authorising that external environment.",
        "external-provider-launch",
        status="resolved",
        evidence=str(destination),
    )
    write_json(run_root / STATE_NAME, state)
    append_log(
        run_root,
        "Implementation return ingested",
        "Builder OS needs durable implementation state without relying on provider conversation history.",
        f"Validated structured return with status {return_status}.",
        [str(destination), str(machine_destination)],
        "Structured provider report; not a verbatim transcript and not independent QA.",
        state["next"],
    )
    print(f"Done. The {return_status} implementation return is recorded and ready for continuity.")
    return 0


def review_judgement_problems(text: str) -> list[str]:
    problems = []
    for heading in REVIEW_HEADINGS:
        level = "##" if heading == "Judgement" else "###"
        matches = re.findall(rf"(?im)^{re.escape(level)}\s+{re.escape(heading)}\s*$", text)
        if not matches:
            problems.append(f"review judgement missing section: {heading}")
        elif len(matches) > 1:
            problems.append(f"review judgement duplicates section: {heading}")
    level_two = re.findall(r"(?im)^##\s+(.+?)\s*$", text)
    if level_two != ["Judgement"]:
        problems.append("review judgement contains an unexpected level-two section")
    for field in (
        "Review target", "Reviewed independently", "Success criteria reviewed",
        "Recommendation", "The one thing", "Lens conflicts",
    ):
        if len(re.findall(rf"(?im)^\*\*{re.escape(field)}:\*\*\s*(.+?)\s*$", text)) != 1:
            problems.append(f"review judgement has missing or duplicate field: {field}")
    if not re.search(r"(?im)^\*\*Reviewed independently:\*\*\s*yes\b", text):
        problems.append("review judgement does not attest independent review")
    if re.search(r"<[^>]+>", text):
        problems.append("review judgement still contains placeholders")
    recommendation = re.search(r"(?im)^\*\*Recommendation:\*\*\s*(.+?)\s*$", text)
    allowed = ("fix and re-review", "restart the direction", "present g3")
    if not recommendation or recommendation.group(1).strip().lower() not in allowed:
        problems.append("review judgement has an invalid recommendation")
    return problems


def extract_marked_block(text: str, begin: str, end: str, label: str) -> str:
    if text.count(begin) != 1 or text.count(end) != 1:
        raise RuntimeError_(f"{label} must contain exactly one {begin}/{end} marker pair")
    _before, remainder = text.split(begin, 1)
    block, _after = remainder.split(end, 1)
    return block.strip() + "\n"


def ingest_review(args: argparse.Namespace) -> int:
    run_root = resolve_run_root(args)
    state = load_state(run_root)
    entry, packet = current_packet(state, allow_project_drift=True)
    if entry["stage"] != "S5":
        raise RuntimeError_("Independent review judgements belong to the current S5 boundary")
    source = Path(args.input).resolve()
    if not source.is_file() or source.stat().st_size == 0:
        raise RuntimeError_(f"Independent review input is missing or empty: {source}")
    raw = read(source)
    block = extract_marked_block(raw, "BEGIN QA JUDGEMENT", "END QA JUDGEMENT", "Review response")
    problems = review_judgement_problems(block)
    if problems:
        raise RuntimeError_("Review judgement rejected: " + "; ".join(problems))
    evidence_dir = packet / "evidence"
    raw_destination = evidence_dir / "review-response.md"
    block_destination = evidence_dir / "review-judgement.md"
    if raw_destination.exists() or block_destination.exists():
        raise RuntimeError_("Refusing to overwrite existing independent review evidence")
    project = Path(state["project"])
    qa_path = project / "QA.md"
    if not qa_path.is_file():
        raise RuntimeError_("Independent review ingestion requires the existing mechanical QA.md")
    qa = read(qa_path)
    pattern = r"(?ms)^## Judgement\s*$.*?(?=^## Screenshots\s*$)"
    if not re.search(pattern, qa):
        raise RuntimeError_("QA.md has no replaceable Judgement-to-Screenshots region")
    updated = re.sub(pattern, block.rstrip() + "\n\n", qa, count=1)
    shutil.copyfile(source, raw_destination)
    block_destination.write_text(block, encoding="utf-8")
    qa_path.write_text(updated, encoding="utf-8")
    state["updated_at"] = now()
    state["evidence_state"] = "independent review response and judgement recorded"
    state["next"] = "Present mechanical and independent evidence for the human G3 decision."
    ensure_intervention(
        state,
        "necessary",
        "Start the isolated independent review session.",
        "Creative judgement must remain separate from the build context.",
        "external-provider-launch",
        status="resolved",
        evidence=str(raw_destination),
    )
    ensure_intervention(
        state,
        "necessary",
        "Decide G3 from mechanical and independent review evidence.",
        "Only the human can accept the build and any recorded evidence exception.",
        "review-decision",
    )
    write_json(run_root / STATE_NAME, state)
    append_log(
        run_root,
        "Independent review ingested",
        "The reviewer output must be preserved and applied without manual rewriting or loss of independence.",
        "Verified marked judgement block; raw response preserved; QA judgement region replaced.",
        [str(raw_destination), str(block_destination), str(qa_path)],
        f"Raw SHA-256 {sha256(raw_destination)}; judgement SHA-256 {sha256(block_destination)}",
        state["next"],
    )
    print("Done. Independent review evidence is recorded without changing its judgement.")
    print("Next: present the combined evidence for the human G3 decision.")
    return 0


def creative_plan(args: argparse.Namespace) -> int:
    """Create the hidden skill/research plan after S1 has produced the brief."""
    run_root = resolve_run_root(args)
    state = load_state(run_root)
    entry, packet = current_packet(state, allow_project_drift=True)
    project = Path(state["project"])
    if entry["stage"] != "S1":
        raise RuntimeError_("Creative planning belongs immediately after the project brief")
    if CREATIVE.ledger_path(project).exists():
        raise RuntimeError_("Creative planning is already recorded; update evidence instead of replacing it")
    for name in ("PROJECT.md", "AGENTS.md"):
        if not (project / name).is_file():
            raise RuntimeError_(f"Creative planning needs the completed project brief: {name}")
    source = Path(args.input).resolve()
    if not source.is_file() or source.stat().st_size == 0:
        raise RuntimeError_("Creative assessment input is missing or empty")
    try:
        assessment = json.loads(read(source))
        ledger = CREATIVE.create_ledger(project, assessment)
        CREATIVE.record_skill_event(ledger, {
            "skill": "intake",
            "state": "invoked",
            "evidence_path": str(packet / TRANSPORT.MANIFEST_NAME),
        })
        CREATIVE.record_skill_event(ledger, {
            "skill": "intake",
            "state": "completed",
            "output_path": str(project / "PROJECT.md"),
            "result": "The completed brief supplied the creative assessment.",
            "usefulness": "useful",
        })
        destination = CREATIVE.save_ledger(project, ledger)
    except (json.JSONDecodeError, CREATIVE.CreativeError) as exc:
        raise RuntimeError_(str(exc)) from exc
    selected = [item for item in ledger["skills"] if item.get("selected")]
    optional = [item for item in selected if not item.get("mandatory")]
    state["updated_at"] = now()
    state["next"] = "Continue with the focused creative work selected for this project."
    write_json(run_root / STATE_NAME, state)
    append_log(
        run_root,
        "Creative work planned",
        "The project brief now contains enough information to select useful methods without invoking every skill.",
        (
            f"Research depth {ledger['research_depth']}; {len(selected)} capabilities selected, "
            f"including {len(optional)} optional project-specific method(s)."
        ),
        [str(destination)],
        "Selection reasons and intended outputs are recorded; no selected skill is claimed invoked except intake.",
        state["next"],
    )
    reference = next(item for item in ledger["skills"] if item["name"] == "reference-analysis")
    component = next(item for item in ledger["skills"] if item["name"] == "component-research")
    choices = []
    if reference["selected"]:
        choices.append("a focused reference pass")
    if component["selected"]:
        choices.append("targeted interaction research")
    print("Done. I chose the creative work this project actually needs.")
    print("Plan: " + (" and ".join(choices) if choices else "no extra research beyond the brief and direction work" ) + ".")
    print("From you: nothing right now.")
    return 0


def record_creative(args: argparse.Namespace) -> int:
    """Apply structured skill, source, conflict, direction, or decision evidence."""
    run_root = resolve_run_root(args)
    state = load_state(run_root)
    project = Path(state["project"])
    ledger = CREATIVE.load_ledger(project)
    if ledger is None:
        raise RuntimeError_("Creative planning has not been recorded for this project")
    source = Path(args.input).resolve()
    if not source.is_file() or source.stat().st_size == 0:
        raise RuntimeError_("Creative evidence input is missing or empty")
    try:
        value = json.loads(read(source))
        CREATIVE.apply_events(ledger, value)
        problems = CREATIVE.ledger_problems(project, ledger)
        if problems:
            raise CREATIVE.CreativeError("; ".join(problems))
        destination = CREATIVE.save_ledger(project, ledger)
    except (json.JSONDecodeError, CREATIVE.CreativeError) as exc:
        raise RuntimeError_(str(exc)) from exc
    creative_summary = CREATIVE.summary(ledger)
    state["updated_at"] = now()
    write_json(run_root / STATE_NAME, state)
    append_log(
        run_root,
        "Creative evidence recorded",
        "Skill execution, source inspection, and downstream use are distinct states and must survive conversation loss.",
        (
            f"{creative_summary['completed']}/{creative_summary['selected']} selected capabilities completed or used; "
            f"{creative_summary['references']['inspected']} reference(s) carry inspection artifacts; "
            f"{creative_summary['decisions']} traced decision(s)."
        ),
        [str(source), str(destination)],
        f"Input SHA-256 {sha256(source)}; ledger validation passed.",
        state.get("next", "Continue from the current verified boundary."),
    )
    print("Done. I recorded what actually ran and what it influenced.")
    print("From you: nothing right now.")
    return 0


def creative_check(args: argparse.Namespace) -> int:
    run_root = resolve_run_root(args)
    state = load_state(run_root)
    entry, _packet = current_packet(state, allow_project_drift=True)
    project = Path(state["project"])
    ledger = CREATIVE.load_ledger(project)
    problems = CREATIVE.project_problems(project, entry["stage"])
    payload = {
        "status": "ready" if not problems else "blocked",
        "project": str(project),
        "stage": entry["stage"],
        "summary": CREATIVE.summary(ledger),
        "problems": problems,
    }
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    elif problems:
        print("I found creative claims that are not supported yet:")
        for problem in problems:
            print(f"- {problem}")
        print("Next: record the missing execution or inspection evidence; do not rewrite the claim as a pass.")
    else:
        print("Ready. Skill execution, source inspection, and design use are traceable.")
        print("From you: nothing right now.")
    return 0 if not problems else 2


def operations_plan(args: argparse.Namespace) -> int:
    """Derive post-G1 implementation and visual-QA targets from locked documents."""
    run_root = resolve_run_root(args)
    state = load_state(run_root)
    project = Path(state["project"])
    if OPERATIONS.ledger_path(project).exists():
        raise RuntimeError_("Creative operations planning is already recorded; do not replace its evidence")
    try:
        ledger = OPERATIONS.create_ledger(project)
        destination = OPERATIONS.save_ledger(project, ledger)
    except OPERATIONS.OperationsError as exc:
        raise RuntimeError_(str(exc)) from exc
    state["updated_at"] = now()
    write_json(run_root / STATE_NAME, state)
    append_log(
        run_root,
        "Design-to-implementation trace generated",
        "Approved design decisions need explicit implementation and project-specific visual-QA targets.",
        f"Verified: {len(ledger['requirements'])} approved requirement(s) and {len(ledger['visual_qa_plan']['targets'])} QA target(s) generated.",
        [str(destination)],
        "Inputs are hashed; this evidence does not approve implementation or a gate.",
        state.get("next", "Continue from the current verified boundary."),
    )
    print("Done. The approved direction now has a traceable implementation and visual-QA plan.")
    print("From you: nothing right now.")
    return 0


def record_operations(args: argparse.Namespace) -> int:
    run_root = resolve_run_root(args)
    state = load_state(run_root)
    project = Path(state["project"])
    ledger = OPERATIONS.load_ledger(project)
    if ledger is None:
        raise RuntimeError_("Post-G1 creative operations planning has not been recorded")
    source = Path(args.input).resolve()
    if not source.is_file() or source.stat().st_size == 0:
        raise RuntimeError_("Creative operations input is missing or empty")
    try:
        value = json.loads(read(source))
        OPERATIONS.apply_events(project, ledger, value)
        problems = OPERATIONS.ledger_problems(project, ledger)
        if problems:
            raise OPERATIONS.OperationsError("; ".join(problems))
        destination = OPERATIONS.save_ledger(project, ledger)
    except (json.JSONDecodeError, OPERATIONS.OperationsError) as exc:
        raise RuntimeError_(str(exc)) from exc
    result = OPERATIONS.summary(ledger)
    state["updated_at"] = now()
    write_json(run_root / STATE_NAME, state)
    append_log(
        run_root,
        "Creative operations evidence recorded",
        "Implementation, rendered evidence, drift, creative judgement, and social strategy must remain separate claims.",
        (
            f"{result['implemented']}/{result['requirements']} requirement(s) implemented; "
            f"{result['observed']} observed/verified visual result(s); "
            f"{result['creative_reviews']} actionable creative review(s); "
            f"{result['social_strategies']} optional social strategy record(s)."
        ),
        [str(source), str(destination)],
        f"Input SHA-256 {sha256(source)}; ledger validation passed.",
        state.get("next", "Continue from the current verified boundary."),
    )
    print("Done. I recorded the post-G1 evidence without promoting assumptions to observations.")
    print("From you: nothing right now.")
    return 0


def operations_check(args: argparse.Namespace) -> int:
    run_root = resolve_run_root(args)
    state = load_state(run_root)
    project = Path(state["project"])
    ledger = OPERATIONS.load_ledger(project)
    problems = OPERATIONS.project_problems(project, args.require)
    payload = {
        "status": "ready" if ledger is not None and not problems else "blocked",
        "project": str(project),
        "summary": OPERATIONS.summary(ledger),
        "required_evidence": args.require,
        "problems": problems if ledger is not None else ["post-G1 creative operations are not recorded"],
    }
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    elif payload["problems"]:
        print("I found post-G1 evidence gaps:")
        for problem in payload["problems"]:
            print(f"- {problem}")
        print("Next: record the missing implementation or observation evidence; do not rewrite it as verified.")
    else:
        print("Ready. Approved decisions, implementation mappings, visual evidence, and creative review remain traceable.")
        print("From you: nothing right now.")
    return 0 if not payload["problems"] else 2


def record_intervention(args: argparse.Namespace) -> int:
    run_root = resolve_run_root(args)
    state = load_state(run_root)
    before = len(state.get("human_interventions", []))
    row = ensure_intervention(
        state,
        args.classification,
        args.need,
        args.reason,
        args.category,
        status=args.status,
        evidence=args.evidence or "",
    )
    if len(state.get("human_interventions", [])) == before and row.get("status") != "resolved":
        raise RuntimeError_("That human intervention is already recorded")
    state["updated_at"] = now()
    write_json(run_root / STATE_NAME, state)
    append_log(
        run_root,
        f"Human intervention classified {args.classification.upper()}",
        args.reason,
        f"{args.status}: {args.need}",
        evidence=args.evidence or "classification recorded in runtime state",
        next_action=state.get("next", "Continue from the current verified boundary."),
    )
    print(f"Done. Human intervention recorded as {args.classification.upper()} ({args.status}).")
    return 0


def record_note(args: argparse.Namespace) -> int:
    run_root = resolve_run_root(args)
    state = load_state(run_root)
    note = {
        "recorded_at": now(),
        "kind": args.kind,
        "summary": args.summary.strip(),
        "evidence_state": args.evidence,
    }
    if not note["summary"]:
        raise RuntimeError_("A project note needs a concrete summary")
    notes = state.setdefault("notes", [])
    if any(
        item.get("kind") == note["kind"] and item.get("summary") == note["summary"]
        for item in notes
    ):
        raise RuntimeError_("That project note is already recorded")
    notes.append(note)
    state["updated_at"] = now()
    write_json(run_root / STATE_NAME, state)
    append_log(
        run_root,
        f"Project {args.kind.replace('-', ' ')} recorded",
        "Project continuity needs durable facts that should not be reconstructed from chat.",
        note["summary"],
        evidence=note["evidence_state"],
        next_action=state.get("next", "Continue from the current verified boundary."),
    )
    print("Done. I added that fact to the project's durable history.")
    return 0


def stage_has_evidence(packet: Path) -> bool:
    evidence = packet / "evidence"
    return any(
        (evidence / name).is_file()
        for name in ("transcript.md", "stage-result.json", "return-handoff.md", "review-judgement.md")
    )


def structured_return_target(packet: Path) -> Path | None:
    manifest_path = packet / TRANSPORT.MANIFEST_NAME
    if not manifest_path.is_file():
        return None
    manifest = json.loads(read(manifest_path))
    value = manifest.get("return_target")
    if not value:
        return None
    target = Path(value).resolve()
    project = Path(manifest.get("project", "")).resolve()
    expected = (
        project / ".builderos" / "returns" / f"{manifest.get('packet_id')}.md"
    ).resolve()
    if target != expected:
        raise RuntimeError_("The S4B structured return target does not match this packet")
    return target


def advance(args: argparse.Namespace) -> int:
    """Record obvious same-session outputs and continue through routine boundaries."""
    run_root = resolve_run_root(args)
    state = load_state(run_root)
    entry, packet = current_packet(state, allow_project_drift=True)
    stage = entry["stage"]
    project = Path(state["project"])

    if stage == "S4B" and not stage_has_evidence(packet):
        target = structured_return_target(packet)
        if target is not None and target.is_file():
            ingest_return(
                argparse.Namespace(
                    run_root=str(run_root),
                    project=None,
                    input=str(target),
                )
            )
            state = load_state(run_root)
            entry, packet = current_packet(state, allow_project_drift=True)

    if not stage_has_evidence(packet):
        expected = EXPECTED_STAGE_OUTPUTS.get(stage)
        if stage == "S3":
            design = read(project / "DESIGN.md") if (project / "DESIGN.md").is_file() else ""
            agents = read(project / "AGENTS.md") if (project / "AGENTS.md").is_file() else ""
            if design and state.get("creative_evidence_required"):
                creative_problems = (
                    CREATIVE.project_problems(project, "S3")
                    if CREATIVE.load_ledger(project) is not None
                    else ["the project has no creative plan or skill-execution record"]
                )
                if creative_problems:
                    state["next"] = "Resolve the unsupported creative evidence before asking for G1."
                    state["updated_at"] = now()
                    write_json(run_root / STATE_NAME, state)
                    append_log(
                        run_root,
                        "Creative evidence blocked G1 presentation",
                        "A design claim cannot prove its own research or skill execution by assertion alone.",
                        "; ".join(creative_problems),
                        [str(CREATIVE.ledger_path(project))] if CREATIVE.ledger_path(project).is_file() else [],
                        "No G1 request or continuation was created.",
                        state["next"],
                    )
                    print("I found creative claims that are not supported yet.")
                    print("First issue: " + creative_problems[0])
                    print("From you: nothing; I need to resolve or honestly downgrade that claim first.")
                    return 2
            if not re.search(r"(?im)^\*\*Status:\*\*.*locked at G1", design) or not re.match(
                r"G1\b", state_field(agents, "Last gate passed")
            ):
                ensure_intervention(
                    state,
                    "necessary",
                    "Decide the G1 creative direction.",
                    "Only the human can approve, reject, or redirect the proposed thesis.",
                    "creative-decision",
                )
                state["next"] = "Review the proposed design direction at G1."
                state["updated_at"] = now()
                write_json(run_root / STATE_NAME, state)
                append_log(
                    run_root,
                    "Creative decision requested",
                    "The design direction exists, but Builder OS cannot grant G1 for the human.",
                    "No continuation or stage evidence was created.",
                    next_action=state["next"],
                )
                print("I have a design direction ready for your judgement.")
                print("From you: approve it, reject it, or redirect it.")
                return 2
        if expected:
            missing = [name for name in expected if not (project / name).is_file()]
            if missing:
                print(f"Paused. {FRIENDLY_STAGES.get(stage, stage).capitalize()} is not complete yet.")
                print("Missing: " + ", ".join(missing))
                return 2
            creative = CREATIVE.load_ledger(project)
            if state.get("creative_evidence_required") and creative is None:
                state["next"] = "Finish the internal creative plan from the completed brief."
                state["updated_at"] = now()
                write_json(run_root / STATE_NAME, state)
                print("Paused. I need to finish the project's internal creative plan.")
                print("From you: nothing right now.")
                return 2
            creative_problems = CREATIVE.project_problems(project, stage) if creative is not None else []
            if creative_problems:
                state["next"] = "Resolve the named creative evidence gap before continuing."
                state["updated_at"] = now()
                write_json(run_root / STATE_NAME, state)
                append_log(
                    run_root,
                    "Creative continuation paused",
                    "Selected skill work and source claims need evidence before the stage can complete.",
                    "; ".join(creative_problems),
                    [str(CREATIVE.ledger_path(project))],
                    "No stage result or continuation was created.",
                    state["next"],
                )
                print("Paused. Creative evidence is incomplete.")
                print("First issue: " + creative_problems[0])
                return 2
            recorded_files = list(expected)
            if CREATIVE.ledger_path(project).is_file():
                recorded_files.append(CREATIVE.LEDGER_RELATIVE.as_posix())
            structural_result(
                argparse.Namespace(
                    run_root=str(run_root),
                    project=None,
                    status="complete",
                    provider=args.provider,
                    model=args.model,
                    summary=f"{FRIENDLY_STAGES.get(stage, stage).capitalize()} complete.",
                    file=recorded_files,
                )
            )
        elif stage in ("S4B", "S5"):
            state["next"] = (
                "Return the complete implementation handoff."
                if stage == "S4B"
                else "Complete the independent review and return its marked judgement."
            )
            state["updated_at"] = now()
            write_json(run_root / STATE_NAME, state)
            print(f"Paused. {state['next']}")
            return 2

    retry = False
    if stage == "S4B":
        returned = packet / "evidence" / "return-handoff.md"
        retry = returned.is_file() and TRANSPORT.return_handoff_status(read(returned)) != "complete"

    return prepare_next(
        argparse.Namespace(
            run_root=str(run_root),
            project=None,
            stage=None,
            retry=retry,
            provider=args.transport_provider,
            references_file=args.references_file,
            motion=args.motion,
            assets=args.assets,
            target=args.target,
            lenses=args.lenses,
            synthetic_validation=args.synthetic_validation,
        )
    )


def infer_next_stage(state: dict) -> tuple[str | None, str]:
    entry, _packet = current_packet(state, allow_project_drift=True)
    stage = entry["stage"]
    project = Path(state["project"])
    if stage == "S1":
        if not (project / "PROJECT.md").is_file() or not (project / "AGENTS.md").is_file():
            return None, "The project brief is not complete yet."
        try:
            TRANSPORT.extract_blocking_questions(read(project / "PROJECT.md"))
            return "S2", "Blocking research questions are recorded in PROJECT.md."
        except TRANSPORT.PacketError:
            return "S3", "The project brief is complete and no blocking research question is recorded."
    if stage == "S2":
        return ("S3", "Research evidence is ready.") if (project / "RESEARCH.md").is_file() else (None, "Research is incomplete.")
    if stage == "S3":
        design = read(project / "DESIGN.md") if (project / "DESIGN.md").is_file() else ""
        agents = read(project / "AGENTS.md") if (project / "AGENTS.md").is_file() else ""
        if re.search(r"(?im)^\*\*Status:\*\*.*locked at G1", design) and re.match(r"G1\b", state_field(agents, "Last gate passed")):
            return "S4A", "The human-approved direction is locked at G1."
        return None, "A human must approve the creative direction at G1."
    if stage == "S4A":
        if not (project / "HANDOFF.md").is_file():
            return None, "The implementation handoff is incomplete."
        context_problems = handoff_context_problems(project)
        if context_problems:
            return None, "The implementation handoff is incomplete: " + "; ".join(context_problems)
        preflight = state.get("provider_preflight") or {}
        if preflight.get("decision") not in ("verified", "reasonably-assumed", "not-required"):
            return None, "Provider preflight must clear before the external build handoff."
        return "S4B", "The handoff is complete and provider preflight cleared."
    if stage == "S4B":
        returned = _packet / "evidence" / "return-handoff.md"
        if returned.is_file() and TRANSPORT.return_handoff_status(read(returned)) != "complete":
            return None, "Implementation returned partial or blocked; resume it before independent review."
        if not (project / "QA.md").is_file():
            return None, "Implementation or mechanical QA is incomplete."
        return "S5", "Mechanical QA exists; independent review can be isolated."
    if stage == "S5":
        return None, "The human must decide G3, then explicitly authorise any G4 ship action."
    if stage == "S6":
        return None, "The project retrospective is complete."
    return None, f"No production transition is defined for {stage}."


def prepare_next(args: argparse.Namespace) -> int:
    run_root = resolve_run_root(args)
    state = load_state(run_root)
    entry, parent = current_packet(state, allow_project_drift=True)
    stage, reason = infer_next_stage(state)
    if args.retry:
        requested = args.stage or entry["stage"]
        if requested != entry["stage"]:
            raise RuntimeError_("A retry must repeat the current boundary")
        stage = requested
        reason = "The current boundary is being retried without overwriting prior evidence."
    elif args.stage and args.stage != stage:
        raise RuntimeError_(
            f"Requested {args.stage}, but the current project state permits only {stage or 'no continuation'}"
        )
    if not stage:
        state["next"] = reason
        state["updated_at"] = now()
        write_json(run_root / STATE_NAME, state)
        append_log(run_root, "Continuation paused", reason, "No packet created.", next_action=reason)
        print(f"Paused: {reason}")
        return 2
    if entry["stage"] == "S3" and stage == "S4A":
        ensure_intervention(
            state,
            "necessary",
            "Decide the G1 creative direction.",
            "Only the human can approve, reject, or redirect the proposed thesis.",
            "creative-decision",
            status="resolved",
            evidence="DESIGN.md locked at G1 and AGENTS.md records G1.",
        )
    if stage == "S4B" and OPERATIONS.load_ledger(Path(state["project"])) is None:
        try:
            operations_ledger = OPERATIONS.create_ledger(Path(state["project"]))
            operations_destination = OPERATIONS.save_ledger(Path(state["project"]), operations_ledger)
        except OPERATIONS.OperationsError as exc:
            raise RuntimeError_(str(exc)) from exc
        append_log(
            run_root,
            "Design-to-implementation trace generated",
            "The approved direction needs project-specific implementation and visual-QA targets before the build starts.",
            f"Verified: {len(operations_ledger['requirements'])} approved requirement(s) and a prioritised visual-QA plan generated.",
            [str(operations_destination)],
            "Derived from locked DESIGN.md, HANDOFF.md, PROJECT.md, and AGENTS.md; no gate was granted.",
            "Prepare the verified implementation packet.",
        )
    packet_id, output = allocate_packet(run_root, state["run_id"], stage)
    kwargs = dict(
        stage=stage,
        project=state["project"],
        output=str(output),
        packet_id=packet_id,
        parent=str(parent),
        retry=args.retry,
        provider=args.provider or transport_provider(state.get("provider_preflight")),
        references_file=args.references_file,
        motion=args.motion,
        assets=args.assets,
        target=args.target,
        lenses=args.lenses,
        synthetic_validation=args.synthetic_validation,
        request=state.get("request"),
    )
    TRANSPORT.prepare(transport_namespace(**kwargs))
    state["packets"].append({"id": packet_id, "stage": stage, "path": str(output)})
    state["updated_at"] = now()
    state["evidence_state"] = "verified-transport; stage not yet observed"
    state["next"] = f"Continue with {FRIENDLY_STAGES.get(stage, stage)}."
    if stage == "S4B":
        ensure_intervention(
            state,
            "necessary",
            "Start the selected external implementation provider.",
            "The current provider boundary cannot execute without the human opening or authorising that external environment.",
            "external-provider-launch",
        )
    elif stage == "S5":
        ensure_intervention(
            state,
            "necessary",
            "Start the isolated independent review session.",
            "Creative judgement must remain separate from the build context.",
            "external-provider-launch",
        )
    write_json(run_root / STATE_NAME, state)
    append_log(
        run_root,
        f"Prepared {stage}",
        reason,
        "Verified packet, source parity, parent provenance, and continuation structure.",
        [str(output / "packet.txt"), str(output / "manifest.json")],
        "Transport verified; provider behaviour not yet observed.",
        state["next"],
    )
    print(f"Done. I prepared everything needed for {FRIENDLY_STAGES.get(stage, stage)}.")
    if stage == "S4B":
        print("From you: start the selected implementation provider when you are ready.")
    elif stage == "S5":
        print("From you: open one fresh independent review session with the prepared context.")
    else:
        print("From you: nothing right now.")
    return 0


def transport_provider(preflight: dict | None) -> str | None:
    if not preflight:
        return None
    value = str(preflight.get("provider", "")).lower()
    if "cursor" in value or "grok" in value:
        return "cursor"
    if "codex" in value or "orchestrator" in value:
        return "codex"
    return "other" if value else None


def operations_log_problems(text: str) -> list[str]:
    problems = []
    for token in ("# Builder OS operations", "## Brief", "## Evidence language", "## Timeline"):
        if token not in text:
            problems.append(f"operations log missing: {token}")
    return problems


def skill_contract_problems(
    skill_text: str | None = None,
    interface_text: str | None = None,
    installation_example: str | None = None,
) -> list[str]:
    skill_path = ROOT / ".agents" / "skills" / "builderos" / "SKILL.md"
    interface_path = ROOT / ".agents" / "skills" / "builderos" / "agents" / "openai.yaml"
    example_path = ROOT / ".agents" / "skills" / "builderos" / "references" / "installation.example.json"
    if skill_text is None:
        skill_text = read(skill_path)
    if interface_text is None:
        interface_text = read(interface_path)
    if installation_example is None:
        installation_example = read(example_path)
    problems = []
    frontmatter = re.match(r"(?s)^---\s*\n(.*?)\n---\s*\n", skill_text)
    if not frontmatter:
        problems.append("builderos skill has no YAML frontmatter")
    else:
        header = frontmatter.group(1)
        name = re.search(r"(?m)^name:\s*(.+?)\s*$", header)
        description = re.search(r"(?m)^description:\s*(.+?)\s*$", header)
        if not name or name.group(1).strip() != "builderos":
            problems.append("builderos skill name must be builderos")
        if not description or not all(
            token in description.group(1).lower() for token in ("builder os", "start", "resume")
        ):
            problems.append("builderos skill description must advertise start and resume triggers")
    for token in ("display_name:", "short_description:", "default_prompt:", "Builder OS"):
        if token not in interface_text:
            problems.append(f"builderos skill interface missing: {token}")
    try:
        example = json.loads(installation_example)
        if not example.get("builder_os_root"):
            problems.append("builderos installation example has no builder_os_root")
    except json.JSONDecodeError:
        problems.append("builderos installation example is malformed")
    for token in (
        "scripts/builderos.py", "discover --project", "provider preflight",
        "handoff-readiness", "builderos.py advance", "record-note",
        "ingest-return", "ingest-review", "same-stage retry", "--adopt-existing",
        "creative-plan", "record-creative", "creative-check",
        "operations-plan", "record-operations", "operations-check",
        "references/creative-operations.md",
        "Never grant a gate",
    ):
        if token not in skill_text:
            problems.append(f"builderos skill missing runtime boundary: {token}")
    return problems


def repository_contract_problems() -> list[str]:
    problems = []
    required = [
        ROOT / ".agents" / "skills" / "builderos" / "SKILL.md",
        ROOT / "templates" / "RETURN-HANDOFF.md",
        ROOT / "templates" / "HANDOFF.md",
        ROOT / "prompts" / "build-kickoff.md",
        ROOT / ".agents" / "skills" / "builderos" / "agents" / "openai.yaml",
        ROOT / ".agents" / "skills" / "builderos" / "references" / "installation.example.json",
        ROOT / "scripts" / "install-builderos-skill.py",
        ROOT / "prompts" / "project-review.md",
        ROOT / "scripts" / "creative-intelligence.py",
        ROOT / ".agents" / "skills" / "builderos" / "references" / "creative-intelligence.md",
        ROOT / "scripts" / "creative-operations.py",
        ROOT / ".agents" / "skills" / "builderos" / "references" / "creative-operations.md",
        ROOT / "skills" / "visual-qa.md",
        ROOT / "skills" / "creative-review.md",
        ROOT / "skills" / "social-strategy.md",
        ROOT / "templates" / "SOCIAL-STRATEGY.md",
    ]
    for path in required:
        if not path.is_file():
            problems.append(f"runtime contract source missing: {path.relative_to(ROOT)}")
    if problems:
        return problems
    problems.extend(skill_contract_problems())
    return_template = read(required[1])
    for heading in TRANSPORT.RETURN_HANDOFF_HEADINGS:
        if f"## {heading}" not in return_template:
            problems.append(f"return-handoff template missing section: {heading}")
    handoff = read(required[2])
    for token in (
        "## Outcome and acceptance criteria",
        "## Content readiness",
        "## Implementer discretion",
        "## Implementation routing",
        "## Return handoff",
        "provider preflight",
    ):
        if token not in handoff:
            problems.append(f"HANDOFF template missing runtime contract: {token}")
    build = read(required[3])
    for token in (
        "success criterion VERBATIM",
        "content readiness",
        "implementer discretion",
        "templates/RETURN-HANDOFF.md",
        "BEGIN/END markers",
        "provider availability",
    ):
        if token not in build:
            problems.append(f"S4 prompt missing runtime contract: {token}")
    if "templates/RETURN-HANDOFF.md" not in TRANSPORT.STAGES["S4B"]["canonical_inputs"]:
        problems.append("S4B packet does not deliver the return-handoff template")
    review = read(required[7])
    for token in ("BEGIN QA JUDGEMENT", "END QA JUDGEMENT", "## Judgement"):
        if token not in review:
            problems.append(f"S5 prompt missing review-ingestion contract: {token}")
    problems.extend(OPERATIONS.repository_contract_problems())
    return problems


@contextlib.contextmanager
def self_test_workspace():
    path = ROOT / "validation" / f"builderos-self-test-{uuid.uuid4().hex}"
    path.mkdir()
    try:
        yield path
    finally:
        if path.exists():
            last_error = None
            for attempt in range(10):
                try:
                    shutil.rmtree(path)
                    last_error = None
                    break
                except PermissionError as exc:
                    last_error = exc
                    time.sleep(0.1 * (attempt + 1))
            if last_error is not None:
                raise last_error


def filled_return(status_value: str = "complete") -> str:
    sections = "\n\n".join(f"## {heading}\n\nnone" for heading in TRANSPORT.RETURN_HANDOFF_HEADINGS)
    return (
        "# IMPLEMENTATION RETURN HANDOFF: Fixture\n\n"
        f"**Status:** {status_value}\n**Provider:** fixture\n**Model:** fixture-model\n"
        "**Effort:** medium\n**Started:** 2026-08-23\n**Ended:** 2026-08-23\n\n"
        + sections
        + "\n"
    )


def filled_review() -> str:
    return """Reviewer summary.

BEGIN QA JUDGEMENT
## Judgement

**Review target:** http://127.0.0.1:3000
**Reviewed independently:** yes - no project or build context was supplied
**Success criteria reviewed:** 1. The interaction has a clear response.

### Accepted patterns

none

### Feel tests

- **Five-second:** specific
- **Swap:** passes
- **Recall:** clear

### Review lenses

| Lens | Score | Verdict | Blocking | The one thing |
|---|---|---|---|---|
| creative-director | 40/50 | Ship | none | none |

### Findings

none

### Review recommendation

**Recommendation:** Present G3
**The one thing:** none
**Lens conflicts:** none
END QA JUDGEMENT

NEXT: Present G3.
"""


def filled_handoff() -> str:
    return """# HANDOFF: Fixture

**To:** Implementer on fixture · **From:** Architect · **Date:** 2026-08-23 · **G1 approved:** 2026-08-23

## Project summary

A small typographic interaction for testing the Builder OS runtime.

## Outcome and acceptance criteria

**Outcome:** Test a typographic interaction.

1. The interaction has a clear response.

## Content readiness

**Status:** not applicable

**Source and constraints:** The fixture has no user-visible editorial copy.

## Design thesis

**A speaking line makes sound visible through one typographic gesture.**

**Signature moment:** the line expands with input and remains legible on mobile — **build this first**

## Decisions that are fixed

| Decision | Value |
|---|---|
| Typography | system sans, 6x ratio |
| Palette | off-black, warm white |
| Grid | one responsive column |
| Motion | feedback, 180ms linear |
| Stack | default |
| State | session only |
| CMS / backend | none |

## Implementer discretion

**May decide:** internal component names and test-file organisation.

**Must not reinterpret:** thesis, signature gesture, non-goals, or success criterion.

## Implementation sequence

1. Token system.
2. Speaking-line interaction.

## Files to create

| Path | Purpose |
|---|---|
| src/app/page.tsx | interaction |

## Components to build

| Component | Responsibility | Client? | Notes |
|---|---|---|---|
| SpeakingLine | render response | client | fixture |

## Dependencies to install

| Package | Version | Approved on |
|---|---|---|
| none | n/a | n/a |

## Implementation routing

| Field | Recommendation |
|---|---|
| Capability needed | `R2` |
| Provider | Cursor / Grok |
| Model | provider default — unverified |
| Effort | medium |
| Workload | medium |
| Split | none |
| Reason | Normal visual implementation. |

## Motion requirements

| Element | Purpose | Trigger | Duration | Easing | Reduced-motion state |
|---|---|---|---|---|---|
| line | feedback | input | 180ms | linear | discrete levels |

## Asset requirements

| Asset | Status | Path | Blocking? |
|---|---|---|---|
| none | ready | n/a | no |

## QA requirements

- Production build, typecheck, console, responsive, keyboard, and reduced-motion checks.

## Known risks

| Risk | Likelihood | If it happens |
|---|---|---|
| input unavailable | low | use explicit blocked state |

## Definition of done

- [ ] Success criterion observed.

## Return handoff

Return the filled canonical implementation handoff on every exit.
"""


def self_test() -> int:
    cases = []

    def case(name: str, passed: bool) -> None:
        cases.append((name, passed))

    case("repository runtime contracts pass (positive control)", not repository_contract_problems())
    with self_test_workspace() as first_workspace, self_test_workspace() as second_workspace:
        case(
            "independent runtime self-test workspaces do not collide",
            first_workspace != second_workspace and first_workspace.exists() and second_workspace.exists(),
        )
    canonical_skill = read(ROOT / ".agents" / "skills" / "builderos" / "SKILL.md")
    canonical_interface = read(ROOT / ".agents" / "skills" / "builderos" / "agents" / "openai.yaml")
    canonical_install = read(ROOT / ".agents" / "skills" / "builderos" / "references" / "installation.example.json")
    case("skill discovery contract passes (positive control)", not skill_contract_problems(canonical_skill, canonical_interface, canonical_install))
    case("skill trigger drift is detected", bool(skill_contract_problems(canonical_skill.replace("resume", "continue", 1), canonical_interface, canonical_install)))
    case("skill name drift is detected", bool(skill_contract_problems(canonical_skill.replace("name: builderos", "name: builder-os", 1), canonical_interface, canonical_install)))
    case("skill UI drift is detected", bool(skill_contract_problems(canonical_skill, canonical_interface.replace("default_prompt:", "prompt:"), canonical_install)))
    case(
        "skill adoption boundary drift is detected",
        bool(skill_contract_problems(canonical_skill.replace("--adopt-existing", "--migrate-existing", 1), canonical_interface, canonical_install)),
    )
    case("available sufficient provider passes", preflight_decision("available", "sufficient", "large")[0] == "verified")
    case("insufficient quota blocks", preflight_decision("available", "insufficient", "medium")[0] == "blocked")
    case("unknown quota blocks a large handoff", preflight_decision("available", "unknown", "large")[0] == "human-check-required")
    case("bounded unknown provider is a recorded assumption", preflight_decision("unknown", "unknown", "small")[0] == "reasonably-assumed")
    case(
        "blocked provider recommends the supplied fallback",
        "Claude Code" in preflight_recommendation("blocked", "Cursor", "large", "Claude Code"),
    )
    case("complete return handoff passes (positive control)", not TRANSPORT.return_handoff_problems(filled_return()))
    case("missing return section fails", bool(TRANSPORT.return_handoff_problems(filled_return().replace("## Known issues", "## Notes"))))
    case("invalid return status fails", bool(TRANSPORT.return_handoff_problems(filled_return("done"))))
    review_block = extract_marked_block(
        filled_review(), "BEGIN QA JUDGEMENT", "END QA JUDGEMENT", "Review response"
    )
    case("review judgement contract passes (positive control)", not review_judgement_problems(review_block))
    case("review placeholder is detected", bool(review_judgement_problems(review_block.replace("none", "<pending>", 1))))
    case("review independence omission is detected", bool(review_judgement_problems(review_block.replace("yes -", "no -", 1))))
    case("review section injection is detected", bool(review_judgement_problems(review_block + "\n## Screenshots\n\nnone\n")))
    case("duplicate return section is detected", bool(TRANSPORT.return_handoff_problems(filled_return() + "\n## Known issues\n\nnone\n")))
    try:
        extract_marked_block(
            filled_review().replace("BEGIN QA JUDGEMENT", "BEGIN REVIEW"),
            "BEGIN QA JUDGEMENT", "END QA JUDGEMENT", "Review response",
        )
        missing_review_marker = False
    except RuntimeError_:
        missing_review_marker = True
    case("missing review marker is detected", missing_review_marker)

    with self_test_workspace() as workspace:
        project = workspace / "project"
        run_root = workspace / "run"

        def runtime_args(**values) -> argparse.Namespace:
            defaults = dict(
                run_root=str(run_root), project=None, stage=None, retry=False,
                provider=None, model=None, effort=None, workload=None,
                transport_provider=None,
                availability="unknown", quota="unknown", fallback=None,
                references_file=None, motion=None, assets=None, target=None,
                lenses=None, synthetic_validation=True,
            )
            defaults.update(values)
            return argparse.Namespace(**defaults)

        adopted_project = workspace / "adopted-project"
        adopted_project.mkdir()
        adopted_readme = adopted_project / "README.md"
        adopted_readme.write_text("# Existing app\n", encoding="utf-8")
        adopted_run = workspace / "adopted-run"
        start(
            argparse.Namespace(
                project=str(adopted_project), run_root=str(adopted_run), run_id="adopted",
                request="Adopt this existing app without changing it.", request_file=None,
                adopt_existing=True, synthetic_validation=True,
            )
        )
        adopted_state = load_state(adopted_run)
        adopted_entry, adopted_packet = current_packet(adopted_state)
        case(
            "runtime adopts an existing project without destructive overwrite",
            adopted_state["adopt_existing"] is True
            and adopted_entry["stage"] == "S1"
            and read(adopted_readme) == "# Existing app\n"
            and "EXISTING-PROJECT ADOPTION CONTEXT" in read(adopted_packet / "packet.txt"),
        )

        protected_project = workspace / "protected-project"
        protected_project.mkdir()
        (protected_project / "PROJECT.md").write_text("existing brief\n", encoding="utf-8")
        try:
            start(
                argparse.Namespace(
                    project=str(protected_project), run_root=str(workspace / "protected-run"),
                    run_id="protected", request="Adopt it.", request_file=None,
                    adopt_existing=True, synthetic_validation=True,
                )
            )
            protected_entry_refused = False
        except RuntimeError_ as exc:
            protected_entry_refused = "PROJECT.md" in str(exc)
        case("runtime refuses to overwrite existing Builder OS entry documents", protected_entry_refused)

        start(
            argparse.Namespace(
                project=str(project), run_root=str(run_root), run_id="fixture",
                request="Build a small typographic experiment.", request_file=None,
                synthetic_validation=True,
            )
        )
        state = load_state(run_root)
        case("start creates one verified S1 packet", len(state["packets"]) == 1 and not TRANSPORT.verify_packet(Path(state["packets"][0]["path"])))
        case("start creates a readable operations log", not operations_log_problems(read(run_root / LOG_NAME)))
        try:
            start(
                argparse.Namespace(
                    project=str(project), run_root=str(run_root), run_id="fixture",
                    request="duplicate", request_file=None, synthetic_validation=True,
                )
            )
            duplicate_blocked = False
        except RuntimeError_:
            duplicate_blocked = True
        case("duplicate run is refused", duplicate_blocked)
        project_text = (
            "# PROJECT\n\n## Goal\n\nTest a typographic interaction.\n\n"
            "## Accepted patterns\n\n| Pattern | Reason | Rationale type |\n|---|---|---|\n\n"
            "## Success criteria\n\n1. The interaction has a clear response.\n\n"
            "## Open questions\n\nNone.\n"
        )
        (project / "PROJECT.md").write_text(project_text, encoding="utf-8")
        (project / "AGENTS.md").write_text(
            "## Current state\n\n| **Stage** | `S1` |\n| **Last gate passed** | `none` |\n"
            "| **Next prompt** | `prompts/design-direction.md` |\n",
            encoding="utf-8",
        )
        structural_result(
            argparse.Namespace(
                run_root=str(run_root), status="complete", provider="fixture",
                model="fixture", summary="S1 complete", file=["PROJECT.md", "AGENTS.md"],
            )
        )
        state = load_state(run_root)
        _entry, packet = current_packet(state)
        structural = packet / "evidence" / "stage-result.json"
        parent_manifest = json.loads(read(packet / TRANSPORT.MANIFEST_NAME))
        case("structural result passes (positive control)", not TRANSPORT.stage_result_problems(structural, parent_manifest))
        before = read(structural)
        (project / "PROJECT.md").write_text(read(project / "PROJECT.md") + "changed\n", encoding="utf-8")
        case("changed structural output is stale", bool(TRANSPORT.stage_result_problems(structural, parent_manifest)))
        (project / "PROJECT.md").write_text(project_text, encoding="utf-8")
        structural.write_text(before, encoding="utf-8")

        case("run is discoverable from the project (positive control)", discover_run_roots(project) == [run_root.resolve()])
        duplicate_run = workspace / "run-duplicate"
        duplicate_run.mkdir()
        shutil.copyfile(run_root / STATE_NAME, duplicate_run / STATE_NAME)
        try:
            resolve_run_root(argparse.Namespace(run_root=None, project=str(project)))
            ambiguous_history_blocked = False
        except RuntimeError_:
            ambiguous_history_blocked = True
        case("ambiguous run history is never guessed", ambiguous_history_blocked)
        shutil.rmtree(duplicate_run)
        prepare_next(runtime_args(motion="no", assets="no"))
        state = load_state(run_root)
        case("automatic progression selects S3", state["packets"][-1]["stage"] == "S3")
        try:
            prepare_next(runtime_args(stage="S4A"))
            stage_bypass_blocked = False
        except RuntimeError_:
            stage_bypass_blocked = True
        case("explicit stage cannot bypass G1", stage_bypass_blocked)

        _entry, s3_packet = current_packet(state)
        manifest_path = s3_packet / TRANSPORT.MANIFEST_NAME
        manifest_original = read(manifest_path)
        manifest = json.loads(manifest_original)
        canonical = next(source for source in manifest["sources"] if source["kind"] == "canonical")
        canonical["source_sha256"] = "0" * 64
        manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        try:
            current_packet(state, allow_project_drift=True)
            canonical_drift_blocked = False
        except RuntimeError_:
            canonical_drift_blocked = True
        case("post-stage tolerance still rejects canonical drift", canonical_drift_blocked)
        manifest_path.write_text(manifest_original, encoding="utf-8")

        (project / "DESIGN.md").write_text(
            "# DESIGN\n\n**Status:** draft — awaiting G1\n\n"
            "## Design thesis\n\n"
            "**A speaking line makes sound visible through one typographic gesture.**\n",
            encoding="utf-8",
        )
        pending_intelligence = project_intelligence(
            run_root, state, _entry, s3_packet, json.loads(manifest_original)
        )
        case(
            "a proposed thesis is never reported as human-approved",
            pending_intelligence["approved_direction"] == "not yet approved"
            and pending_intelligence["proposed_direction"].startswith("A speaking line"),
        )

        (project / "DESIGN.md").write_text(
            "# DESIGN\n\n**Status:** locked at G1 on 2026-08-23\n\n"
            "## Design thesis\n\n"
            "**A speaking line makes sound visible through one typographic gesture.**\n\n"
            "## Signature moment\n\n"
            "- **What / where:** A speaking line crosses the listening boundary.\n"
            "- **Why memorable:** Sound becomes a typographic gesture.\n"
            "- **Mobile equivalent:** The line becomes a vertical sound trace.\n\n"
            "## Responsive behaviour\n\n"
            "| Width | Composition |\n|---|---|\n"
            "| 375 | The line becomes a vertical sound trace. |\n"
            "| 1280 | The line crosses the listening boundary. |\n\n"
            "## Asset direction\n\n"
            "| Asset | Exists? | Plan | Blocking? |\n|---|---|---|---|\n"
            "| none | yes | no asset required | no |\n",
            encoding="utf-8",
        )
        (project / "AGENTS.md").write_text(
            "## Current state\n\n| **Stage** | `S3` |\n| **Last gate passed** | `G1` |\n"
            "| **Next prompt** | `prompts/build-kickoff.md` |\n",
            encoding="utf-8",
        )
        try:
            current_packet(state)
            strict_project_drift = False
        except RuntimeError_:
            strict_project_drift = True
        try:
            current_packet(state, allow_project_drift=True)
            expected_project_drift = True
        except RuntimeError_:
            expected_project_drift = False
        case("new stage outputs do not invalidate delivered inputs", not strict_project_drift and expected_project_drift)
        structural_result(runtime_args(
            status="complete", provider="fixture", model="fixture",
            summary="Direction approved at G1", file=["DESIGN.md", "AGENTS.md"],
        ))
        prepare_next(runtime_args())
        state = load_state(run_root)
        case("G1 approval automatically prepares S4A", state["packets"][-1]["stage"] == "S4A")

        (project / "HANDOFF.md").write_text(filled_handoff(), encoding="utf-8")
        (project / "AGENTS.md").write_text(
            "## Current state\n\n| **Stage** | `S4` |\n| **Last gate passed** | `G1` |\n"
            "| **Next prompt** | `prompts/build-kickoff.md` |\n",
            encoding="utf-8",
        )
        try:
            current_packet(load_state(run_root))
            s4a_strict_drift = False
        except RuntimeError_:
            s4a_strict_drift = True
        try:
            current_packet(load_state(run_root), allow_project_drift=True)
            s4a_expected_drift = True
        except RuntimeError_:
            s4a_expected_drift = False
        case(
            "expected project-state updates remain recordable",
            s4a_strict_drift and s4a_expected_drift,
        )
        structural_result(runtime_args(
            status="complete", provider="fixture", model="fixture",
            summary="Implementation handoff complete", file=["HANDOFF.md", "AGENTS.md"],
        ))
        case("complete implementation handoff passes readiness", not handoff_context_problems(project))
        (project / "HANDOFF.md").write_text(
            filled_handoff().replace("## Implementer discretion", "## Execution notes", 1),
            encoding="utf-8",
        )
        case(
            "missing handoff readiness section is detected",
            any("Implementer discretion" in problem for problem in handoff_context_problems(project)),
        )
        (project / "HANDOFF.md").write_text(
            filled_handoff().replace("system sans, 6x ratio", "<pending typography>", 1),
            encoding="utf-8",
        )
        case(
            "handoff placeholder is detected",
            any("placeholders" in problem for problem in handoff_context_problems(project)),
        )
        (project / "HANDOFF.md").write_text(
            filled_handoff().replace(
                "| none | n/a | n/a |",
                "| motion | 13.1.1 | pending |",
                1,
            ),
            encoding="utf-8",
        )
        case(
            "unapproved handoff dependency is detected",
            any("G2-approved" in problem for problem in handoff_context_problems(project)),
        )
        (project / "HANDOFF.md").write_text(
            filled_handoff().replace(
                "| none | ready | n/a | no |",
                "| hero still | generating | n/a | yes |",
                1,
            ),
            encoding="utf-8",
        )
        case(
            "unresolved critical handoff asset is detected",
            any("critical asset" in problem for problem in handoff_context_problems(project)),
        )
        incomplete = filled_handoff().replace(
            "1. The interaction has a clear response.",
            "1. A different criterion.",
            1,
        )
        (project / "HANDOFF.md").write_text(incomplete, encoding="utf-8")
        case(
            "handoff success-criteria drift is detected",
            any("success criteria verbatim" in problem for problem in handoff_context_problems(project)),
        )
        (project / "HANDOFF.md").write_text(filled_handoff(), encoding="utf-8")
        provider_preflight(runtime_args(availability="available", quota="sufficient"))
        state = load_state(run_root)
        case(
            "provider routing is read from HANDOFF.md",
            state["provider_preflight"]["provider"] == "Cursor / Grok"
            and state["provider_preflight"]["decision"] == "verified",
        )
        prepare_next(runtime_args())
        state = load_state(run_root)
        s4b_entry, s4b_packet = current_packet(state)
        s4b_manifest = json.loads(read(s4b_packet / TRANSPORT.MANIFEST_NAME))
        case(
            "cleared preflight prepares a Cursor-labelled S4B packet",
            s4b_entry["stage"] == "S4B" and s4b_manifest["provider"] == "cursor",
        )
        operations_ledger = OPERATIONS.load_ledger(project)
        case(
            "S4B preparation derives project-specific visual QA without another human task",
            operations_ledger is not None
            and not OPERATIONS.ledger_problems(project, operations_ledger)
            and any(item["id"] == "signature-moment" for item in operations_ledger["requirements"]),
        )
        status_observation = project / "status-observation.txt"
        status_observation.write_text(
            "Observed signature selection remains legible in the fixture.\n",
            encoding="utf-8",
        )
        OPERATIONS.record_visual_evidence(operations_ledger, {
            "id": "status-signature-observed", "requirement_id": "signature-moment",
            "level": "observed", "kind": "interaction", "viewport": 375,
            "observation": "The signature selection remained legible at the narrow fixture width.",
            "evidence_path": str(status_observation),
        })
        status_dimensions = {
            name: {
                "judgement": f"Fixture judgement for {name}.",
                "evidence_ids": ["status-signature-observed"],
            }
            for name in OPERATIONS.REVIEW_DIMENSIONS
        }
        OPERATIONS.record_creative_review(operations_ledger, {
            "id": "status-review-1", "evidence_ids": ["status-signature-observed"],
            "strongest": "The signature selection remains legible.",
            "weakest": "The desktop state is not yet observed.",
            "biggest_risk": "A narrow-only conclusion would overstate the result.",
            "highest_value_improvement": "Observe the desktop state before independent review.",
            "iteration": "yes", "do_not_change": "The approved signature mechanism.",
            "dimensions": status_dimensions,
        })
        OPERATIONS.save_ledger(project, operations_ledger)
        status_intelligence = project_intelligence(
            run_root, load_state(run_root), s4b_entry, s4b_packet, s4b_manifest
        )
        case(
            "project status exposes evidence-backed strongest and weakest aspects",
            status_intelligence["creative_quality"]["strongest"]
            == "The signature selection remains legible."
            and status_intelligence["creative_quality"]["weakest"]
            == "The desktop state is not yet observed."
            and status_intelligence["creative_quality"]["iteration"] == "yes",
        )
        effort = intervention_summary(state)
        case(
            "human effort separates authority from routine machinery",
            effort["necessary_decisions"] >= 1
            and effort["avoidable_interruptions"] == 0
            and effort["system_maintenance_interruptions"] == 0
            and effort["by_category"]["creative-decision"] >= 1
            and effort["by_category"]["external-provider-launch"] >= 1
            and effort["mechanical_work"] == 0,
        )
        legacy_effort_state = {
            "human_interventions": [{
                "id": "human-1", "classification": "necessary",
                "need": "Decide the G1 creative direction.",
                "reason": "Historical runtime row without the V1.5 category field.",
                "status": "pending",
            }]
        }
        legacy_summary = intervention_summary(legacy_effort_state)
        ensure_intervention(
            legacy_effort_state, "necessary", "Decide the G1 creative direction.",
            "Only the human can approve the creative direction.", "creative-decision",
            status="resolved",
        )
        case(
            "legacy human-effort rows remain classifiable and migrate on update",
            legacy_summary["by_category"]["creative-decision"] == 1
            and legacy_effort_state["human_interventions"][0]["category"]
            == "creative-decision",
        )
        try:
            ensure_intervention(
                state, "routine", "Locate a packet.", "Fixture invalid class.",
                "prompt-discovery",
            )
            bad_intervention_allowed = True
        except RuntimeError_:
            bad_intervention_allowed = False
        case("unknown human intervention class is rejected", not bad_intervention_allowed)
        try:
            ensure_intervention(
                state, "necessary", "Do an unknown thing.", "Fixture invalid category.",
                "unknown-category",
            )
            bad_category_allowed = True
        except RuntimeError_:
            bad_category_allowed = False
        case("unknown human intervention category is rejected", not bad_category_allowed)
        before_return_provider = project_intelligence(
            run_root, state, s4b_entry, s4b_packet, s4b_manifest
        )["provider_evidence"]
        case(
            "provider selection does not imply execution or successful return",
            before_return_provider["selected"]["state"] == "selected"
            and before_return_provider["executed"]["state"] == "not-observed"
            and before_return_provider["returned_successfully"]["state"] == "not-returned",
        )

        partial_path = s4b_packet / "evidence" / "return-handoff.md"
        partial_path.write_text(filled_return("partial"), encoding="utf-8")
        (project / "QA.md").write_text(
            "# QA\n\n## Mechanical\n\n| # | Check | Result | Evidence |\n|---|---|---|---|\n"
            "| 1 | Build | pass | fixture |\n\n## Judgement\n\nPending.\n\n"
            "## Screenshots\n\n| View | Path |\n|---|---|\n| Fixture | none |\n",
            encoding="utf-8",
        )
        case("partial implementation return blocks review", infer_next_stage(load_state(run_root))[0] is None)
        advance(runtime_args())
        state = load_state(run_root)
        retry_entry, retry_packet = current_packet(state)
        retry_manifest = json.loads(read(retry_packet / TRANSPORT.MANIFEST_NAME))
        case(
            "public advance resumes a partial implementation in a non-overwriting S4B child",
            retry_entry["stage"] == "S4B"
            and retry_manifest["parent_id"] == s4b_entry["id"]
            and retry_manifest["parent_evidence_kind"] == "structured-return-handoff",
        )
        unexpected_return = project / ".builderos" / "returns" / "wrong-packet.md"
        unexpected_return.parent.mkdir(parents=True, exist_ok=True)
        unexpected_return.write_text(filled_return(), encoding="utf-8")
        advance_result = advance(runtime_args())
        case(
            "an unrelated project return cannot be ingested as the current packet",
            advance_result == 2
            and not (retry_packet / "evidence" / "return-handoff.md").exists(),
        )
        expected_return = Path(retry_manifest["return_target"])
        expected_return.write_text(filled_return(), encoding="utf-8")
        advance(
            runtime_args(
                target="http://127.0.0.1:3000",
                lenses="creative-director (light)",
            )
        )
        state = load_state(run_root)
        external = next(
            item for item in state["human_interventions"]
            if item["need"] == "Start the selected external implementation provider."
        )
        case("provider return resolves the external human action", external["status"] == "resolved")
        return_record_path = retry_packet / "evidence" / "return-handoff.json"
        case(
            "implementation return produces deterministic machine state",
            return_record_path.is_file()
            and json.loads(read(return_record_path))["metadata"]["status"] == "complete"
            and json.loads(read(return_record_path))["source_sha256"]
            == sha256(retry_packet / "evidence" / "return-handoff.md"),
        )
        state = load_state(run_root)
        returned_entry, returned_packet = retry_entry, retry_packet
        returned_manifest = retry_manifest
        after_return_provider = project_intelligence(
            run_root, state, returned_entry, returned_packet, returned_manifest
        )["provider_evidence"]
        case(
            "provider return reports execution separately from a successful return",
            after_return_provider["executed"]["state"] == "reported-by-provider-return"
            and after_return_provider["returned_successfully"]["state"] == "reported-complete",
        )
        _s5_entry, s5_packet = current_packet(state)
        s5_manifest = json.loads(read(s5_packet / TRANSPORT.MANIFEST_NAME))
        delivered = [source["label"] for source in s5_manifest["sources"] if source.get("delivered", True)]
        case(
            "complete return automatically reaches isolated S5",
            state["packets"][-1]["stage"] == "S5"
            and delivered == ["current S5 prompt block", "EVALUATION-RUBRICS.md"],
        )
        review_source = workspace / "review.md"
        review_source.write_text(filled_review(), encoding="utf-8")
        ingest_review(runtime_args(input=str(review_source)))
        qa_after_review = read(project / "QA.md")
        case(
            "independent review ingestion preserves mechanics and judgement",
            "| 1 | Build | pass | fixture |" in qa_after_review
            and "**Recommendation:** Present G3" in qa_after_review
            and read(s5_packet / "evidence" / "review-response.md") == filled_review(),
        )
        try:
            ingest_review(runtime_args(input=str(review_source)))
            duplicate_review_blocked = False
        except RuntimeError_:
            duplicate_review_blocked = True
        case("independent review evidence cannot be overwritten", duplicate_review_blocked)
        case("operations log remains readable after full dry run", not operations_log_problems(read(run_root / LOG_NAME)))

        auto_project = workspace / "ordinary-idea"
        auto_run = workspace / "ordinary-idea-builderos"
        start(
            argparse.Namespace(
                project=str(auto_project), run_root=str(auto_run), run_id="ordinary-idea",
                request="Make a small browser piece where a sentence changes with the time of day.",
                request_file=None, synthetic_validation=True,
            )
        )
        (auto_project / "PROJECT.md").write_text(
            "# PROJECT: Day Sentence\n\n**Mode:** game-experiment · **Status:** locked\n\n"
            "## Goal\n\nMake time feel visible through one changing\n"
            "sentence across a normal day.\n\n"
            "## Success criteria\n\n1. A visitor sees the sentence change across two fixture times.\n\n"
            "## Open questions\n\nNone.\n",
            encoding="utf-8",
        )
        (auto_project / "AGENTS.md").write_text(
            "## Current state\n\n| **Stage** | `S1` |\n| **Last gate passed** | `none` |\n"
            "| **Next prompt** | `prompts/design-direction.md` |\n",
            encoding="utf-8",
        )
        auto_assessment = workspace / "ordinary-idea-assessment.json"
        write_json(auto_assessment, CREATIVE.low_assessment(motion_dependence="high"))
        creative_plan(
            argparse.Namespace(
                run_root=str(auto_run), project=None, input=str(auto_assessment)
            )
        )
        auto_ledger = CREATIVE.load_ledger(auto_project)
        case(
            "creative planning records intake execution without claiming later skills ran",
            auto_ledger is not None
            and next(item for item in auto_ledger["skills"] if item["name"] == "intake")["state"] == "completed"
            and next(item for item in auto_ledger["skills"] if item["name"] == "design-direction")["state"] == "recommended",
        )
        advance(
            argparse.Namespace(
                run_root=str(auto_run), project=None, provider="orchestrator",
                model="fixture", transport_provider=None, references_file=None,
                motion="yes", assets="no", target=None,
                lenses=None, synthetic_validation=True,
            )
        )
        auto_state = load_state(auto_run)
        auto_entry, auto_packet = current_packet(auto_state)
        auto_manifest = json.loads(read(auto_packet / TRANSPORT.MANIFEST_NAME))
        case(
            "public advance records routine outputs and prepares the next work",
            auto_entry["stage"] == "S3"
            and (Path(auto_state["packets"][0]["path"]) / "evidence" / "stage-result.json").is_file(),
        )
        auto_intelligence = project_intelligence(
            auto_run, auto_state, auto_entry, auto_packet, auto_manifest
        )
        case(
            "project briefing derives goal and human-level current work",
            auto_intelligence["goal"] == "Make time feel visible through one changing sentence across a normal day."
            and auto_intelligence["current_work"] == "design direction",
        )
        record_note(
            argparse.Namespace(
                run_root=str(auto_run), project=None, kind="evidence-gap",
                summary="Live sunrise timing is externally unverified; fixture times cover deterministic behaviour.",
                evidence="externally-unverified",
            )
        )
        case(
            "non-blocking evidence gap remains durable without stopping progress",
            load_state(auto_run)["notes"][-1]["evidence_state"] == "externally-unverified"
            and load_state(auto_run)["packets"][-1]["stage"] == "S3",
        )
        case(
            "two project histories remain isolated",
            discover_run_roots(project) == [run_root.resolve()]
            and discover_run_roots(auto_project) == [auto_run.resolve()],
        )

    print("BUILDER OS RUNTIME SELF-TEST\n")
    for name, passed in cases:
        print(("ok    " if passed else "FAIL  ") + name)
    failed = [name for name, passed in cases if not passed]
    print(f"\n{'FAILED' if failed else 'PASS'}  {len(cases) - len(failed)}/{len(cases)}")
    return 1 if failed else 0


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--self-test", action="store_true")
    sub = p.add_subparsers(dest="command")

    start_p = sub.add_parser("start", help="start a new Builder OS project and prepare its brief")
    start_p.add_argument("--project", required=True)
    start_p.add_argument("--run-root")
    start_p.add_argument("--run-id")
    request = start_p.add_mutually_exclusive_group(required=True)
    request.add_argument("--request")
    request.add_argument("--request-file")
    start_p.add_argument("--synthetic-validation", action="store_true", help=argparse.SUPPRESS)
    start_p.add_argument(
        "--adopt-existing", action="store_true",
        help="start a non-destructive intake for an existing project",
    )

    def run_selector(command: argparse.ArgumentParser) -> None:
        selection = command.add_mutually_exclusive_group(required=True)
        selection.add_argument("--run-root")
        selection.add_argument("--project")

    discover_p = sub.add_parser("discover", help="find the run that records a project")
    discover_p.add_argument("--project", required=True)
    discover_p.add_argument("--json", action="store_true")

    status_p = sub.add_parser("status", help="show the current project state and next action")
    run_selector(status_p)
    status_p.add_argument("--json", action="store_true")

    readiness_p = sub.add_parser(
        "handoff-readiness", help="check implementation context before provider launch"
    )
    run_selector(readiness_p)
    readiness_p.add_argument("--json", action="store_true")

    preflight_p = sub.add_parser("preflight", help="record provider/model/effort readiness before external work")
    run_selector(preflight_p)
    preflight_p.add_argument("--provider")
    preflight_p.add_argument("--model")
    preflight_p.add_argument("--effort", choices=["low", "medium", "high"])
    preflight_p.add_argument("--workload", choices=["small", "medium", "large"])
    preflight_p.add_argument("--availability", default="unknown", choices=["available", "limited", "unavailable", "unknown"])
    preflight_p.add_argument("--quota", default="unknown", choices=["sufficient", "insufficient", "unknown"])
    preflight_p.add_argument("--fallback")

    result_p = sub.add_parser("record-result", help="record structurally verified same-session outputs")
    run_selector(result_p)
    result_p.add_argument("--status", required=True, choices=["complete", "partial", "blocked"])
    result_p.add_argument("--provider", required=True)
    result_p.add_argument("--model", required=True)
    result_p.add_argument("--summary", required=True)
    result_p.add_argument("--file", action="append", required=True)

    transcript_p = sub.add_parser("record-transcript", help="preserve a provider transcript without manual path handling")
    run_selector(transcript_p)
    transcript_p.add_argument("--input", required=True)

    return_p = sub.add_parser("ingest-return", help="validate and store an external implementation return handoff")
    run_selector(return_p)
    return_p.add_argument("--input", required=True)

    review_p = sub.add_parser("ingest-review", help="preserve and apply a marked independent-review judgement")
    run_selector(review_p)
    review_p.add_argument("--input", required=True)

    creative_plan_p = sub.add_parser(
        "creative-plan", help="select project-specific skills and research depth from a structured assessment"
    )
    run_selector(creative_plan_p)
    creative_plan_p.add_argument("--input", required=True)

    creative_record_p = sub.add_parser(
        "record-creative", help="record skill execution, source inspection, and downstream design use"
    )
    run_selector(creative_record_p)
    creative_record_p.add_argument("--input", required=True)

    creative_check_p = sub.add_parser(
        "creative-check", help="check creative claims against execution and source artifacts"
    )
    run_selector(creative_check_p)
    creative_check_p.add_argument("--json", action="store_true")

    operations_plan_p = sub.add_parser(
        "operations-plan", help="derive post-G1 implementation and project-specific visual-QA targets"
    )
    run_selector(operations_plan_p)

    operations_record_p = sub.add_parser(
        "record-operations", help="record implementation, rendered evidence, drift, review, or social provenance"
    )
    run_selector(operations_record_p)
    operations_record_p.add_argument("--input", required=True)

    operations_check_p = sub.add_parser(
        "operations-check", help="check post-G1 claims against implementation and rendered evidence"
    )
    run_selector(operations_check_p)
    operations_check_p.add_argument(
        "--require",
        choices=["plan", "implementation", "visual", "review", "social"],
        default="plan",
    )
    operations_check_p.add_argument("--json", action="store_true")

    intervention_p = sub.add_parser(
        "record-intervention", help="classify a human interruption in the run operations record"
    )
    run_selector(intervention_p)
    intervention_p.add_argument("--classification", required=True, choices=list(OPERATIONS.INTERVENTION_CLASSES))
    intervention_p.add_argument(
        "--category",
        choices=list(HUMAN_INTERVENTION_CATEGORIES),
        default="unclassified",
    )
    intervention_p.add_argument("--status", required=True, choices=["pending", "resolved", "observed", "prevented"])
    intervention_p.add_argument("--need", required=True)
    intervention_p.add_argument("--reason", required=True)
    intervention_p.add_argument("--evidence")

    note_p = sub.add_parser("record-note", help="add a durable project decision, risk, or evidence note")
    run_selector(note_p)
    note_p.add_argument(
        "--kind",
        required=True,
        choices=["decision", "rejected-direction", "risk", "lesson", "evidence-gap", "recovery"],
    )
    note_p.add_argument("--summary", required=True)
    note_p.add_argument(
        "--evidence",
        required=True,
        choices=["verified", "reasonably-assumed", "externally-unverified", "blocked"],
    )

    advance_p = sub.add_parser(
        "advance", help="record obvious same-session outputs and continue routine work"
    )
    run_selector(advance_p)
    advance_p.add_argument("--provider", default="orchestrator")
    advance_p.add_argument("--model", default="not recorded")
    advance_p.add_argument("--transport-provider", choices=["codex", "cursor", "other"])
    advance_p.add_argument("--references-file")
    advance_p.add_argument("--motion", choices=["yes", "no"])
    advance_p.add_argument("--assets", choices=["yes", "no"])
    advance_p.add_argument("--target")
    advance_p.add_argument("--lenses")
    advance_p.add_argument("--synthetic-validation", action="store_true", help=argparse.SUPPRESS)

    next_p = sub.add_parser("prepare-next", help="discover and prepare the next valid project boundary")
    run_selector(next_p)
    next_p.add_argument("--stage", choices=list(TRANSPORT.STAGES))
    next_p.add_argument("--retry", action="store_true")
    next_p.add_argument("--provider", choices=["codex", "cursor", "other"])
    next_p.add_argument("--references-file")
    next_p.add_argument("--motion", choices=["yes", "no"])
    next_p.add_argument("--assets", choices=["yes", "no"])
    next_p.add_argument("--target")
    next_p.add_argument("--lenses")
    next_p.add_argument("--synthetic-validation", action="store_true", help=argparse.SUPPRESS)
    return p


def main() -> int:
    args = parser().parse_args()
    try:
        if args.self_test:
            return self_test()
        commands = {
            "start": start,
            "discover": discover,
            "status": status,
            "handoff-readiness": handoff_readiness_command,
            "preflight": provider_preflight,
            "record-result": structural_result,
            "record-transcript": record_transcript,
            "ingest-return": ingest_return,
            "ingest-review": ingest_review,
            "creative-plan": creative_plan,
            "record-creative": record_creative,
            "creative-check": creative_check,
            "operations-plan": operations_plan,
            "record-operations": record_operations,
            "operations-check": operations_check,
            "record-intervention": record_intervention,
            "record-note": record_note,
            "advance": advance,
            "prepare-next": prepare_next,
        }
        if args.command in commands:
            return commands[args.command](args)
        parser().print_help()
        return 0
    except (RuntimeError_, TRANSPORT.PacketError, CREATIVE.CreativeError, OPERATIONS.OperationsError) as exc:
        print(f"STOPPED: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
