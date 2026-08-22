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
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
STATE_NAME = "builderos-run.json"
LOG_NAME = "OPERATIONS.md"
PREFLIGHT_NAME = "provider-preflight.json"
RUNTIME_SCHEMA = 1


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


def git_head() -> str:
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

## Timeline
"""


def ensure_fresh_project(project: Path) -> None:
    project.mkdir(parents=True, exist_ok=True)
    allowed = {".git", ".gitignore"}
    unexpected = sorted(item.name for item in project.iterdir() if item.name not in allowed)
    if unexpected:
        raise RuntimeError_(
            "A new Builder OS run needs a fresh project. Existing files found: "
            + ", ".join(unexpected)
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


def current_packet(state: dict) -> tuple[dict, Path]:
    packets = state.get("packets", [])
    if not packets:
        raise RuntimeError_("Run state has no prepared packet")
    entry = packets[-1]
    path = Path(entry["path"])
    problems = TRANSPORT.verify_packet(path)
    if problems:
        raise RuntimeError_("Current packet is stale or damaged: " + "; ".join(problems))
    return entry, path


def start(args: argparse.Namespace) -> int:
    project = Path(args.project).resolve()
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
    ensure_fresh_project(project)
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
        "evidence_state": "verified-transport; provider stage not yet observed",
        "packets": [{"id": packet_id, "stage": "S1", "path": str(output)}],
        "provider_preflight": None,
        "next": "Run the project brief stage from the prepared packet.",
    }
    write_json(run_root / STATE_NAME, state)
    append_log(
        run_root,
        "Project started",
        "A fresh ordinary-language brief needs a verified intake boundary.",
        "Verified: fresh project shell and S1 packet prepared.",
        [str(project / ".gitignore"), str(output / "packet.txt"), str(output / "manifest.json")],
        "Packet source parity passed; no provider stage has run.",
        "Builder OS should read and run the prepared project-brief packet.",
    )
    print("Done. The project is ready for its brief and discovery pass.")
    print(f"RUN_ROOT  {run_root}")
    print(f"PACKET    {output / 'packet.txt'}")
    print("USER      Nothing else to locate or assemble.")
    return 0


def state_field(text: str, name: str) -> str:
    match = re.search(rf"(?m)^\|\s*\*\*{re.escape(name)}\*\*\s*\|\s*`?([^|`]+)", text)
    return match.group(1).strip() if match else ""


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


def status(args: argparse.Namespace) -> int:
    run_root = Path(args.run_root).resolve()
    state = load_state(run_root)
    entry, packet = current_packet(state)
    manifest = json.loads(read(packet / TRANSPORT.MANIFEST_NAME))
    evidence_options = []
    transcript = packet / manifest.get("expected_transcript", "evidence/transcript.md")
    if transcript.is_file():
        evidence_options.append("verbatim transcript")
    if (packet / "evidence" / "stage-result.json").is_file():
        evidence_options.append("structural stage result")
    if (packet / "evidence" / "return-handoff.md").is_file():
        evidence_options.append("structured return handoff")
    runtime = project_runtime(Path(state["project"]))
    payload = {
        "run_id": state["run_id"],
        "project": state["project"],
        "status": state["status"],
        "current_boundary": entry["stage"],
        "packet": str(packet / "packet.txt"),
        "packet_verified": True,
        "evidence": evidence_options or ["not yet recorded"],
        "project_state": runtime,
        "provider_preflight": state.get("provider_preflight") or "not run",
        "next": state.get("next"),
        "operations_log": str(run_root / LOG_NAME),
    }
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(f"Project: {Path(state['project']).name}")
        print(f"Current work: {entry['stage']} ({', '.join(payload['evidence'])})")
        print(f"Project state: {runtime['stage']}, last gate {runtime['gate']}")
        print(f"Next: {state.get('next')}")
        print(f"Operations log: {run_root / LOG_NAME}")
    return 0


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


def provider_preflight(args: argparse.Namespace) -> int:
    run_root = Path(args.run_root).resolve()
    state = load_state(run_root)
    decision, reason = preflight_decision(args.availability, args.quota, args.workload)
    record = {
        "schema_version": 1,
        "checked_at": now(),
        "provider": args.provider,
        "model": args.model,
        "effort": args.effort,
        "workload": args.workload,
        "availability": args.availability,
        "quota": args.quota,
        "decision": decision,
        "reason": reason,
        "fallback": args.fallback or "not supplied",
    }
    write_json(run_root / PREFLIGHT_NAME, record)
    state["provider_preflight"] = record
    state["updated_at"] = now()
    state["next"] = (
        "Prepare the verified external build handoff."
        if decision in ("verified", "reasonably-assumed")
        else reason
    )
    write_json(run_root / STATE_NAME, state)
    append_log(
        run_root,
        "Provider preflight",
        "External implementation should not discover preventable availability limits mid-build.",
        f"{decision}: {reason}",
        [str(run_root / PREFLIGHT_NAME)],
        f"provider={args.provider}; model={args.model}; effort={args.effort}; workload={args.workload}; availability={args.availability}; quota={args.quota}",
        state["next"],
    )
    print(f"Provider preflight: {decision.upper()}")
    print(reason)
    return 0 if decision in ("verified", "reasonably-assumed") else 2


def structural_result(args: argparse.Namespace) -> int:
    run_root = Path(args.run_root).resolve()
    state = load_state(run_root)
    entry, packet = current_packet(state)
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
    run_root = Path(args.run_root).resolve()
    state = load_state(run_root)
    _entry, packet = current_packet(state)
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
    run_root = Path(args.run_root).resolve()
    state = load_state(run_root)
    entry, packet = current_packet(state)
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
    if destination.exists():
        raise RuntimeError_(f"Refusing to overwrite existing return handoff: {destination}")
    destination.write_text(text, encoding="utf-8")
    status_match = re.search(r"(?im)^\*\*Status:\*\*\s*(.+?)\s*$", text)
    return_status = status_match.group(1).strip().lower()
    state["updated_at"] = now()
    state["evidence_state"] = "structured external return; transcript remains separate"
    state["next"] = (
        "Prepare independent review after verifying QA evidence."
        if return_status == "complete"
        else "Resume from the incomplete-work section or route the blocker."
    )
    write_json(run_root / STATE_NAME, state)
    append_log(
        run_root,
        "Implementation return ingested",
        "Builder OS needs durable implementation state without relying on provider conversation history.",
        f"Validated structured return with status {return_status}.",
        [str(destination)],
        "Structured provider report; not a verbatim transcript and not independent QA.",
        state["next"],
    )
    print(f"Done. The {return_status} implementation return is recorded and ready for continuity.")
    return 0


def infer_next_stage(state: dict) -> tuple[str | None, str]:
    entry, _packet = current_packet(state)
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
        preflight = state.get("provider_preflight") or {}
        if preflight.get("decision") not in ("verified", "reasonably-assumed"):
            return None, "Provider preflight must clear before the external build handoff."
        return "S4B", "The handoff is complete and provider preflight cleared."
    if stage == "S4B":
        if not (project / "QA.md").is_file():
            return None, "Implementation or mechanical QA is incomplete."
        return "S5", "Mechanical QA exists; independent review can be isolated."
    if stage == "S5":
        return None, "The human must decide G3, then explicitly authorise any G4 ship action."
    if stage == "S6":
        return None, "The project retrospective is complete."
    return None, f"No production transition is defined for {stage}."


def prepare_next(args: argparse.Namespace) -> int:
    run_root = Path(args.run_root).resolve()
    state = load_state(run_root)
    _entry, parent = current_packet(state)
    stage, reason = infer_next_stage(state)
    if args.stage:
        stage = args.stage
        reason = "An explicit stage was requested; canonical parent and boundary checks still apply."
    if not stage:
        state["next"] = reason
        state["updated_at"] = now()
        write_json(run_root / STATE_NAME, state)
        append_log(run_root, "Continuation paused", reason, "No packet created.", next_action=reason)
        print(f"Paused: {reason}")
        return 2
    packet_id, output = allocate_packet(run_root, state["run_id"], stage)
    kwargs = dict(
        stage=stage,
        project=state["project"],
        output=str(output),
        packet_id=packet_id,
        parent=str(parent),
        retry=args.retry,
        provider=args.provider,
        references_file=args.references_file,
        motion=args.motion,
        assets=args.assets,
        target=args.target,
        lenses=args.lenses,
        synthetic_validation=args.synthetic_validation,
    )
    TRANSPORT.prepare(transport_namespace(**kwargs))
    state["packets"].append({"id": packet_id, "stage": stage, "path": str(output)})
    state["updated_at"] = now()
    state["evidence_state"] = "verified-transport; stage not yet observed"
    state["next"] = f"Run the prepared {stage} boundary."
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
    print("Done. Builder OS prepared and verified the next boundary.")
    print(f"PACKET  {output / 'packet.txt'}")
    print("USER    Nothing to assemble. Open an external session only when Builder OS says it is required.")
    return 0


def operations_log_problems(text: str) -> list[str]:
    problems = []
    for token in ("# Builder OS operations", "## Brief", "## Evidence language", "## Timeline"):
        if token not in text:
            problems.append(f"operations log missing: {token}")
    return problems


def repository_contract_problems() -> list[str]:
    problems = []
    required = [
        ROOT / ".agents" / "skills" / "builderos" / "SKILL.md",
        ROOT / "templates" / "RETURN-HANDOFF.md",
        ROOT / "templates" / "HANDOFF.md",
        ROOT / "prompts" / "build-kickoff.md",
    ]
    for path in required:
        if not path.is_file():
            problems.append(f"runtime contract source missing: {path.relative_to(ROOT)}")
    if problems:
        return problems
    skill = read(required[0])
    for token in ("scripts/builderos.py", "provider preflight", "ingest-return", "Never grant a gate"):
        if token not in skill:
            problems.append(f"builderos skill missing runtime boundary: {token}")
    return_template = read(required[1])
    for heading in TRANSPORT.RETURN_HANDOFF_HEADINGS:
        if f"## {heading}" not in return_template:
            problems.append(f"return-handoff template missing section: {heading}")
    handoff = read(required[2])
    for token in ("## Implementation routing", "## Return handoff", "provider preflight"):
        if token not in handoff:
            problems.append(f"HANDOFF template missing runtime contract: {token}")
    build = read(required[3])
    for token in ("templates/RETURN-HANDOFF.md", "BEGIN/END markers", "provider availability"):
        if token not in build:
            problems.append(f"S4 prompt missing runtime contract: {token}")
    if "templates/RETURN-HANDOFF.md" not in TRANSPORT.STAGES["S4B"]["canonical_inputs"]:
        problems.append("S4B packet does not deliver the return-handoff template")
    return problems


@contextlib.contextmanager
def self_test_workspace():
    path = ROOT / "validation" / "builderos-self-test-work"
    if path.exists():
        raise RuntimeError_(f"Self-test workspace already exists: {path}")
    path.mkdir()
    try:
        yield path
    finally:
        if path.exists():
            shutil.rmtree(path)


def filled_return(status_value: str = "complete") -> str:
    sections = "\n\n".join(f"## {heading}\n\nnone" for heading in TRANSPORT.RETURN_HANDOFF_HEADINGS)
    return (
        "# IMPLEMENTATION RETURN HANDOFF: Fixture\n\n"
        f"**Status:** {status_value}\n**Provider:** fixture\n**Model:** fixture-model\n"
        "**Effort:** medium\n**Started:** 2026-08-23\n**Ended:** 2026-08-23\n\n"
        + sections
        + "\n"
    )


def self_test() -> int:
    cases = []

    def case(name: str, passed: bool) -> None:
        cases.append((name, passed))

    case("repository runtime contracts pass (positive control)", not repository_contract_problems())
    case("available sufficient provider passes", preflight_decision("available", "sufficient", "large")[0] == "verified")
    case("insufficient quota blocks", preflight_decision("available", "insufficient", "medium")[0] == "blocked")
    case("unknown quota blocks a large handoff", preflight_decision("available", "unknown", "large")[0] == "human-check-required")
    case("bounded unknown provider is a recorded assumption", preflight_decision("unknown", "unknown", "small")[0] == "reasonably-assumed")
    case("complete return handoff passes (positive control)", not TRANSPORT.return_handoff_problems(filled_return()))
    case("missing return section fails", bool(TRANSPORT.return_handoff_problems(filled_return().replace("## Known issues", "## Notes"))))
    case("invalid return status fails", bool(TRANSPORT.return_handoff_problems(filled_return("done"))))

    with self_test_workspace() as workspace:
        project = workspace / "project"
        run_root = workspace / "run"
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
        (project / "PROJECT.md").write_text(
            "# PROJECT\n\n## Goal\n\nTest.\n\n## Open questions\n\nNone.\n", encoding="utf-8"
        )
        (project / "AGENTS.md").write_text(
            "## Current state\n\n| **Stage** | `S1` |\n| **Last gate passed** | `none` |\n",
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
        (project / "PROJECT.md").write_text("# PROJECT\n\n## Goal\n\nTest.\n\n## Open questions\n\nNone.\n", encoding="utf-8")
        structural.write_text(before, encoding="utf-8")

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

    status_p = sub.add_parser("status", help="show the current project state and next action")
    status_p.add_argument("--run-root", required=True)
    status_p.add_argument("--json", action="store_true")

    preflight_p = sub.add_parser("preflight", help="record provider/model/effort readiness before external work")
    preflight_p.add_argument("--run-root", required=True)
    preflight_p.add_argument("--provider", required=True)
    preflight_p.add_argument("--model", required=True)
    preflight_p.add_argument("--effort", required=True, choices=["low", "medium", "high"])
    preflight_p.add_argument("--workload", required=True, choices=["small", "medium", "large"])
    preflight_p.add_argument("--availability", required=True, choices=["available", "limited", "unavailable", "unknown"])
    preflight_p.add_argument("--quota", required=True, choices=["sufficient", "insufficient", "unknown"])
    preflight_p.add_argument("--fallback")

    result_p = sub.add_parser("record-result", help="record structurally verified same-session outputs")
    result_p.add_argument("--run-root", required=True)
    result_p.add_argument("--status", required=True, choices=["complete", "partial", "blocked"])
    result_p.add_argument("--provider", required=True)
    result_p.add_argument("--model", required=True)
    result_p.add_argument("--summary", required=True)
    result_p.add_argument("--file", action="append", required=True)

    transcript_p = sub.add_parser("record-transcript", help="preserve a provider transcript without manual path handling")
    transcript_p.add_argument("--run-root", required=True)
    transcript_p.add_argument("--input", required=True)

    return_p = sub.add_parser("ingest-return", help="validate and store an external implementation return handoff")
    return_p.add_argument("--run-root", required=True)
    return_p.add_argument("--input", required=True)

    next_p = sub.add_parser("prepare-next", help="discover and prepare the next valid project boundary")
    next_p.add_argument("--run-root", required=True)
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
            "status": status,
            "preflight": provider_preflight,
            "record-result": structural_result,
            "record-transcript": record_transcript,
            "ingest-return": ingest_return,
            "prepare-next": prepare_next,
        }
        if args.command in commands:
            return commands[args.command](args)
        parser().print_help()
        return 0
    except (RuntimeError_, TRANSPORT.PacketError) as exc:
        print(f"STOPPED: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
