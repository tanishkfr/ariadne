#!/usr/bin/env python3
"""Calm runtime controller for Ariadne.

This script hides packet IDs, parent discovery, evidence paths, provider
preflight, and continuation mechanics from the operator. It delegates canonical
transport to prepare-stage.py and never owns routing or gate policy.

Run `python scripts/ariadne.py --self-test` for deterministic positive and
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


# Installed runtimes are immutable and hash-verified. Dynamic helper imports
# must never create __pycache__ files beside canonical runtime sources.
sys.dont_write_bytecode = True


ROOT = Path(__file__).resolve().parent.parent
STATE_NAME = "ariadne-run.json"
LOG_NAME = "OPERATIONS.md"
PREFLIGHT_NAME = "provider-preflight.json"
TELEMETRY_NAME = "worker-telemetry.jsonl"
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
    spec = importlib.util.spec_from_file_location("ariadne_transport", path)
    if spec is None or spec.loader is None:
        raise RuntimeError_("Ariadne transport helper could not be loaded")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


TRANSPORT = load_transport()
WORKER_ROLE_ORDER = {role: index for index, role in enumerate(TRANSPORT.WORKER_ROLES)}


def load_engine():
    """Load the AR-201 orchestration core from the same checkout (no installation required)."""
    package = ROOT / "src" / "ariadne_engine" / "__init__.py"
    if not package.is_file():
        raise RuntimeError_(
            "The Ariadne orchestration core is missing from this runtime: " + str(package)
        )
    spec = importlib.util.spec_from_file_location(
        "ariadne_engine", package, submodule_search_locations=[str(package.parent)]
    )
    if spec is None or spec.loader is None:
        raise RuntimeError_("Ariadne orchestration core could not be loaded")
    module = importlib.util.module_from_spec(spec)
    sys.modules["ariadne_engine"] = module
    spec.loader.exec_module(module)
    return module


ENGINE = load_engine()
CONTRACTS = ENGINE.contracts
STATEMACHINE = ENGINE.statemachine
POLICY = ENGINE.policy
REVIEWS = ENGINE.review
PERSISTENCE = ENGINE.persistence
ENGINE_API = ENGINE.api
EXECUTION = ENGINE.execution
ROUTING = ENGINE.routing
CONTEXT = ENGINE.context
RECOVERY = ENGINE.recovery
EVENTS = ENGINE.events
DESIGN = ENGINE.design
REFERENCES = ENGINE.references
COMPONENTS = ENGINE.components
RENDER = ENGINE.render
CRITIQUE = ENGINE.critique
CAPABILITIES = ENGINE.capabilities
VERIFICATION = ENGINE.verification
PROVENANCE = ENGINE.provenance
DECISIONS = ENGINE.decisions
# AR-204 harness economics. The runtime exposes the same engine functions the API
# and the benchmark drive, so no optimisation rule is duplicated on a surface.
ECONOMICS = ENGINE.economics
EFFICIENCY = ENGINE.efficiency
HARNESS = ENGINE.harness
TOOLING = ENGINE.tooling
ARTIFACTS = ENGINE.artifacts
HISTORY = ENGINE.history
ORCHESTRATION = ENGINE.orchestration
PROMPTING = ENGINE.prompting
SERIALIZATION = ENGINE.serialization
MIGRATION = ENGINE.migration

# The run-state *file* schema is unchanged in AR-201: new authority lives in
# versioned records inside the state, so published runtimes keep reading it.
RUNTIME_SCHEMA = CONTRACTS.SCHEMA_RUN
ENGINE_ERRORS = (CONTRACTS.EngineError,)
def _runtime_module():
    """The loaded runtime module, resolved when the API is actually used."""
    return sys.modules.get(__name__)


ENGINE_API.bind(_runtime_module)
PERSISTENCE.bind_logger(
    lambda run_root, report: (
        append_log(
            run_root,
            "Run state migrated",
            "A readable run state written before the AR-201 engine contract was upgraded explicitly.",
            (
                f"schema {report.get('from_version')} -> record contract {report.get('to_version')}; "
                f"backup {report.get('backup') or 'already present'}; "
                "no approval was created and no gate was granted."
            ),
            [str(run_root / STATE_NAME)],
            "Explicit, additive, reversible by restoring the preserved pre-migration file.",
            "Re-check any human gate this run still needs.",
        ),
        append_worker_telemetry(
            run_root,
            "state-migration",
            provider=str(report.get("engine_contract", "ariadne-engine-1")),
            model=f"schema {report.get('from_version')} -> {report.get('to_version')}",
            failure_reason="none",
        ),
    )
)



def load_reasoners():
    path = ROOT / "scripts" / "reasoners.py"
    spec = importlib.util.spec_from_file_location("ariadne_reasoners", path)
    if spec is None or spec.loader is None:
        raise RuntimeError_("Ariadne reasoner helper could not be loaded")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


REASONERS = load_reasoners()


def load_creative_intelligence():
    path = ROOT / "scripts" / "creative-intelligence.py"
    spec = importlib.util.spec_from_file_location("ariadne_creative_intelligence", path)
    if spec is None or spec.loader is None:
        raise RuntimeError_("Ariadne creative-intelligence helper could not be loaded")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


CREATIVE = load_creative_intelligence()


def load_creative_operations():
    path = ROOT / "scripts" / "creative-operations.py"
    spec = importlib.util.spec_from_file_location("ariadne_creative_operations", path)
    if spec is None or spec.loader is None:
        raise RuntimeError_("Ariadne creative-operations helper could not be loaded")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


OPERATIONS = load_creative_operations()

# The engine owns gate policy and continuation preconditions; the transport and
# the two creative ledgers stay where they are and are injected, never re-implemented.
POLICY.bind(transport=TRANSPORT, creative=CREATIVE, operations=OPERATIONS)



def now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def replace_with_retry(
    source: Path,
    target: Path,
    *,
    attempts: int = 10,
    replace=None,
    sleep=None,
) -> None:
    """Complete one atomic replace despite short Windows sharing violations."""
    replace = replace or (lambda old, new: old.replace(new))
    sleep = sleep or time.sleep
    last_error = None
    for attempt in range(attempts):
        try:
            replace(source, target)
            return
        except (PermissionError, OSError) as exc:
            last_error = exc
            if attempt + 1 < attempts:
                sleep(0.05 * (attempt + 1))
    if last_error is not None:
        raise last_error


def write_json(path: Path, value: dict) -> None:
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        replace_with_retry(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def append_worker_telemetry(run_root: Path, event: str, **values) -> None:
    """Append a small provider-neutral event; absent provider usage stays unknown."""
    record = {
        "schema_version": 1,
        "event": event,
        "recorded_at": now(),
        "task_id": "unknown",
        "worker_role": "unknown",
        "provider": "unknown",
        "model": "unknown",
        "start": "unknown",
        "end": "unknown",
        "duration_seconds": None,
        "attempt": 0,
        "validation_attempts": 0,
        "files_changed": [],
        "tests_result": "not run",
        "escalation_count": 0,
        "review_outcome": "not reviewed",
        "accepted": "unknown",
        "usage": "unknown",
        "cost": "unknown",
        "failure_reason": "none",
    }
    record.update(values)
    path = run_root / TELEMETRY_NAME
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(record, sort_keys=True) + "\n")


def project_engine_event(run_root: Path, event: dict) -> None:
    """Compatibility projection: one legacy telemetry row per canonical engine event.

    ``engine-events.jsonl`` is the structured source of truth; this keeps the
    AR-201 telemetry row schema working for existing consumers without asking
    them to understand the new event contract.
    """
    data = event.get("data") if isinstance(event.get("data"), dict) else {}
    append_worker_telemetry(
        run_root,
        f"engine:{event.get('type', 'unknown')}",
        task_id=str(event.get("task_id") or "unknown"),
        worker_role=str(data.get("worker_role") or data.get("role") or "unknown"),
        provider=str(data.get("provider") or data.get("requested_provider") or "unknown"),
        model=str(data.get("model") or data.get("requested_model") or "unknown"),
        review_outcome=str(data.get("review_outcome") or "not reviewed"),
        failure_reason=str(data.get("failure_class") or "none"),
        usage="unknown",
        cost="unknown",
        execution=str(event.get("execution") or ""),
    )


EVENTS.bind_projector(project_engine_event)


def emit_event(
    run_root: Path,
    event_type: str,
    *,
    state: dict | None = None,
    task_id: str = "",
    stage: str = "",
    execution: str = "",
    actor: str = "",
    **data,
) -> dict:
    """Append one canonical engine event and return it. Never rewrites the log."""
    state = state or {}
    return EVENTS.emit(
        Path(run_root),
        event_type,
        run_id=str(state.get("run_id", "")),
        task_id=str(task_id or ""),
        stage=str(stage or ""),
        execution=str(execution or ""),
        actor=str(actor or ""),
        **data,
    )


def worker_outcome(
    status_value: str,
    failure_kind: str = "none",
    repair_attempts: int = 0,
    repair_limit: int = TRANSPORT.MAX_ROUTINE_REPAIRS,
) -> dict:
    """Classify one independent validation result without selecting a provider.

    The classification itself lives in the engine's transition table so the
    runtime cannot invent a lifecycle value the table does not permit.
    """
    outcome = STATEMACHINE.worker_transition_for(status_value, failure_kind, repair_attempts, repair_limit)
    return {
        "implementation_state": outcome["fields"].get("implementation_state", "IMPLEMENTED"),
        "validation_state": outcome["fields"].get("validation_state", "UNKNOWN"),
        "lifecycle": outcome["to"],
        "retryable": outcome["retryable"],
        "escalation_required": outcome["escalation_required"],
        "next": outcome["next"],
    }


def iso_duration(started: str | None, ended: str | None) -> float | None:
    if not started or not ended:
        return None
    try:
        start_value = datetime.fromisoformat(started)
        end_value = datetime.fromisoformat(ended)
    except ValueError:
        return None
    return max(0.0, (end_value - start_value).total_seconds())


def load_state(run_root: Path, *, migrate: bool | None = None) -> dict:
    """Read run state through the engine (schema gate, explicit migration, no implicit writes)."""
    return PERSISTENCE.load_state(Path(run_root), migrate_state=bool(migrate))


def write_state(run_root: Path, state: dict) -> None:
    """Persist run state through the engine (atomic replace, engine contract marker)."""
    PERSISTENCE.write_state(Path(run_root), state)


def resolve_and_load(args: argparse.Namespace) -> tuple[Path, dict]:
    """Resolve the run root and read state, honouring an explicit --migrate."""
    run_root = resolve_run_root(args)
    return run_root, load_state(run_root, migrate=getattr(args, "migrate", False))



def slug(value: str) -> str:
    result = re.sub(r"[^A-Za-z0-9]+", "-", value.strip()).strip("-").lower()
    return result or "project"


def default_run_root(project: Path) -> Path:
    return project.parent / f"{project.name}-ariadne"


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
        raise RuntimeError_(f"No Ariadne run records this project: {project}")
    if len(matches) > 1:
        raise RuntimeError_(
            "More than one Ariadne run records this project; choose one explicitly: "
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
    return f"""# Ariadne operations — {run_id}

**Project:** `{project}`
**Started:** {now()}
**Ariadne:** `{git_head()}`

This log answers what happened, why, what changed, what was verified, and what
happens next. Canonical policies remain in Ariadne; this is project history.

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
- **Avoidable:** routine work Ariadne should have handled.
- **Unacceptable:** the human had to repair Ariadne machinery.

Each intervention also records what kind of effort it was: manual setup, file
movement, prompt discovery, routine confirmation, creative decision, external
provider launch, or review decision. Mechanical work and human authority stay
separate even when both are unavoidable in a particular environment.

Structured counts and pending decisions live in `{STATE_NAME}`. The purpose is
to reduce interruption, not to turn it into a score.

Implementation worker events are appended to `{TELEMETRY_NAME}`. Provider usage
and cost are recorded only when exposed by the worker; otherwise they remain
`unknown`.

## Timeline
"""


def ensure_project(project: Path, adopt_existing: bool = False) -> list[str]:
    project.mkdir(parents=True, exist_ok=True)
    allowed = {".git", ".gitignore"}
    unexpected = sorted(item.name for item in project.iterdir() if item.name not in allowed)
    if unexpected and not adopt_existing:
        raise RuntimeError_(
            "A new Ariadne run needs a fresh project. Existing files found: "
            + ", ".join(unexpected)
            + ". Use --adopt-existing only when preserving this repository is intentional."
        )
    if adopt_existing:
        owned = sorted(name for name in ("PROJECT.md", "AGENTS.md") if (project / name).exists())
        if owned:
            raise RuntimeError_(
                "Existing project already has Ariadne entry documents: "
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
        worker_role=None,
        packet_id=None,
        parent=None,
        retry=False,
        synthetic_validation=False,
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


def reasoner_output_baseline(project: Path, stage: str) -> dict | None:
    relative = MATERIAL_REASONER_OUTPUT.get(stage)
    if not relative:
        return None
    path = project / relative
    return {
        "path": relative,
        "exists": path.is_file(),
        "sha256": sha256(path) if path.is_file() else None,
    }


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
    reasoner_id = getattr(args, "reasoner", None) or REASONERS.load_contract()["default"]
    capability = REASONERS.detect(reasoner_id)
    if not REASONERS.selectable(capability):
        raise RuntimeError_(
            f"The requested {reasoner_id} reasoner is unavailable: "
            f"{capability.get('execution', 'not observed')}. Nothing was created."
        )
    reasoner = REASONERS.selection_record(
        reasoner_id,
        "Explicit project-start selection." if getattr(args, "reasoner", None) else "V1.5 default.",
        capability,
        now(),
    )
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
            provider=reasoner_id,
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
        "packets": [],
        "provider_preflight": None,
        "reasoner": reasoner,
        "reasoner_history": [reasoner],
        "notes": [],
        "human_interventions": [],
        "creative_evidence_required": True,
        "next": "Complete the project brief from the prepared context.",
    }
    STATEMACHINE.apply_transition(
        state,
        CONTRACTS.TransitionRequest(
            kind="stage",
            to="S1",
            reason="A new run starts at the prepared brief boundary.",
            evidence=(str(output), packet_id),
            packet={
                "id": packet_id,
                "stage": "S1",
                "path": str(output),
                "reasoner_output_baseline": reasoner_output_baseline(project, "S1"),
            },
            actor="human",
            operation="start",
        ),
        permitted=True,
    )
    write_state(run_root, state)
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
        f"Packet source parity passed; reasoner selected: {reasoner_id}; no provider stage has run.",
        "Ariadne should read and run the prepared project-brief packet.",
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
    """The design thesis line. Single implementation lives in the engine (used by fingerprints)."""
    return POLICY.design_thesis(text)


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
    problems.extend(TRANSPORT.worker_contract_problems(handoff_text))
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
    if (packet / "evidence" / "validation.json").is_file():
        evidence.append("independent worker validation")
    if (packet / "evidence" / "review-judgement.md").is_file():
        evidence.append("independent review judgement")
    return evidence


def latest_evidence_path(state: dict, name: str) -> Path | None:
    for entry in reversed(state.get("packets", [])):
        candidate = Path(entry["path"]) / "evidence" / name
        if candidate.is_file():
            return candidate
    return None


def current_or_latest_evidence_path(state: dict, name: str) -> Path | None:
    """Do not let a completed parent make a fresh S4B retry look complete."""
    packets = state.get("packets", [])
    if not packets:
        return None
    current = packets[-1]
    candidate = Path(current["path"]) / "evidence" / name
    if candidate.is_file():
        return candidate
    if current.get("stage") == "S4B":
        return None
    return latest_evidence_path(state, name)


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


def worker_state(state: dict) -> dict:
    return state.setdefault("worker", {})


def worker_manifest(packet: Path) -> dict:
    try:
        manifest = json.loads(read(packet / TRANSPORT.MANIFEST_NAME))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError_(f"Worker packet manifest is unavailable: {exc}") from exc
    value = manifest.get("worker")
    if not isinstance(value, dict):
        raise RuntimeError_("Current S4B packet has no worker contract manifest")
    return manifest


def update_worker_state(
    state: dict,
    manifest: dict,
    preflight: dict | None = None,
    escalation_increment: int = 0,
    execution: dict | None = None,
) -> dict:
    value = manifest.get("worker") or {}
    previous = worker_state(state)
    previous_lifecycle = STATEMACHINE.lifecycle_of(state)
    preflight = preflight or state.get("provider_preflight") or {}
    execution = execution or {}
    row = {
        "task_id": value.get("task_id", manifest.get("packet_id")),
        "worker_role": value.get("role", "unknown"),
        "provider": manifest.get("provider") or preflight.get("provider", "unknown"),
        "model": preflight.get("model", previous.get("model", "unknown")),
        "attempt": value.get("attempt", 1),
        "repair_limit": value.get("repair_limit", TRANSPORT.MAX_ROUTINE_REPAIRS),
        "repair_attempts": max(0, int(value.get("attempt", 1)) - 1),
        "validation_attempts": int(previous.get("validation_attempts", 0)),
        "escalation_count": int(previous.get("escalation_count", 0)) + escalation_increment,
        "baseline": manifest.get("project_baseline", {}),
        "telemetry": TELEMETRY_NAME,
        "lifecycle": previous_lifecycle,
        "execution_id": str(execution.get("execution_id", "")),
        "execution_binding": str(execution.get("adapter", "")),
    }
    state["worker"] = row
    STATEMACHINE.apply_transition(
        state,
        CONTRACTS.TransitionRequest(
            kind="worker-lifecycle",
            to="baseline",
            reason="A new worker attempt starts from the recorded baseline.",
            evidence=(str(row.get("task_id", "")),),
            fields={
                "implementation_state": "NOT_STARTED",
                "validation_state": "NOT_RUN",
                "review_state": "NOT_REVIEWED",
                "acceptance_state": "UNKNOWN",
            },
            actor="runtime",
            operation="worker-attempt",
        ),
        permitted=True,
    )
    return row


def provider_evidence(run_root: Path, state: dict, return_record: dict) -> dict:
    """Project selected, executed, and successful-return states without inference."""
    preflight = state.get("provider_preflight") or {}
    selected_provider = preflight.get("provider")
    selected = {
        "state": "selected" if selected_provider else "not-selected",
        "provider": selected_provider or "not recorded",
        "evidence": str(run_root / PREFLIGHT_NAME) if selected_provider else "none",
    }
    transcript = current_or_latest_evidence_path(state, "transcript.md")
    returned = current_or_latest_evidence_path(state, "return-handoff.md")
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
    validation_path = current_or_latest_evidence_path(state, "validation.json")
    validation = {}
    if validation_path:
        try:
            validation = json.loads(read(validation_path))
        except (OSError, json.JSONDecodeError):
            validation = {}
    validation_status = validation.get("status")
    independent_validation = {
        "state": (
            "validated" if validation_status == "passed"
            else f"{validation_status}" if validation_status in ("failed", "blocked")
            else "not-run"
        ),
        "evidence": str(validation_path) if validation_path else "none",
    }
    return {
        "selected": selected,
        "executed": executed,
        "returned_successfully": successful_return,
        "independent_validation": independent_validation,
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

    returned = current_or_latest_evidence_path(state, "return-handoff.md")
    machine_return = current_or_latest_evidence_path(state, "return-handoff.json")
    validation_path = current_or_latest_evidence_path(state, "validation.json")
    validation_record = {}
    if validation_path:
        try:
            validation_record = json.loads(read(validation_path))
        except (OSError, json.JSONDecodeError):
            validation_record = {}
    return_record = {}
    if machine_return:
        try:
            return_record = json.loads(read(machine_return))
        except json.JSONDecodeError:
            return_record = {}
    worker_row = state.get("worker") or {}
    if returned and returned.is_file() and TRANSPORT.return_handoff_status(read(returned)) == "complete":
        add("implementation", "ready", "A complete structured implementation return is recorded.")
    elif stage == "S4B":
        add("implementation", "in-progress", "Implementation has not returned complete evidence yet.")
    elif stage in ("S5", "S6"):
        add("implementation", "ready", "Implementation reached verification.")
    else:
        add("implementation", "pending", "Implementation has not started.")

    if validation_record.get("status") == "passed":
        add("worker validation", "ready", "Ariadne independently reran the required checks and confirmed scope.")
    elif validation_record.get("status") in ("failed", "blocked"):
        outcome = worker_outcome(
            validation_record["status"],
            validation_record.get("failure_kind", "routine"),
            int((state.get("worker") or {}).get("repair_attempts", 0)),
        )
        add("worker validation", "attention", outcome["next"])
    elif stage == "S4B" and returned:
        add("worker validation", "attention", "The implementation is reported; Ariadne independent validation is still pending.")

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
    elif stage == "S4B" and validation_record.get("status") == "failed":
        human_need = worker_outcome(
            "failed", validation_record.get("failure_kind", "routine"),
            int((state.get("worker") or {}).get("repair_attempts", 0)),
        )["next"]
    elif stage == "S4B" and validation_record.get("status") == "blocked":
        human_need = "Escalate the blocked worker result with the recorded conflict or safety finding."
    elif stage == "S4B" and returned and validation_record.get("status") != "passed":
        human_need = "Run Ariadne's independent worker validation before continuing to review."
    elif stage == "S5" and review_recorded:
        human_need = "Decide whether the combined build and review evidence is acceptable at G3."
    else:
        human_need = "Nothing right now; Ariadne can continue the current work."

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
            "provider": worker_row.get(
                "provider", return_record.get("metadata", {}).get("provider", "not yet selected")
            ),
            "model": worker_row.get(
                "model", return_record.get("metadata", {}).get("model", "not yet selected")
            ),
            "completed_work": completed_work,
            "known_issues": known_issues,
            "files_changed": return_record.get("sections", {}).get("files-changed", "not recorded"),
            "task_id": worker_row.get("task_id", "not assigned"),
            "worker_role": worker_row.get("worker_role", "not assigned"),
            "attempt": worker_row.get("attempt", 0),
            "validation_attempts": worker_row.get("validation_attempts", 0),
            "implementation_state": worker_row.get("implementation_state", "UNKNOWN"),
            "validation_state": worker_row.get("validation_state", "UNKNOWN"),
            "review_state": worker_row.get("review_state", "UNKNOWN"),
            "acceptance_state": worker_row.get("acceptance_state", "UNKNOWN"),
            "escalation_count": worker_row.get("escalation_count", 0),
            "telemetry": str(run_root / TELEMETRY_NAME),
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
    run_root, state = resolve_and_load(args)
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
        "reasoner": REASONERS.selected(state),
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
        print(f"Reasoner: {REASONERS.selected(state)['id']}.")
        worker_info = intelligence["implementation"]
        if worker_info["task_id"] != "not assigned":
            print(
                f"Worker: {worker_info['worker_role']} via {worker_info['provider']} "
                f"(attempt {worker_info['attempt']})."
            )
            print(
                "Worker state: "
                f"{worker_info['implementation_state']} / "
                f"{worker_info['validation_state']} / "
                f"{worker_info['review_state']} / "
                f"{worker_info['acceptance_state']}."
            )
            if worker_info["files_changed"] not in ("not recorded", "none"):
                print(f"Files changed: {worker_info['files_changed']}")
            if worker_info["completed_work"] not in ("not yet recorded", "none"):
                print(f"Worker report: {worker_info['completed_work']}")
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


def reasoner_status(args: argparse.Namespace) -> int:
    run_root, state = resolve_and_load(args)
    contract = REASONERS.load_contract()
    selection = REASONERS.selected(state, contract)
    identifier = args.reasoner or selection["id"]
    capability = REASONERS.detect(identifier, contract)
    payload = {
        "default": contract["default"],
        "selected": selection,
        "checked": capability,
        "workflow_capabilities": contract["providers"][identifier]["capabilities"],
        "reasoning_stages": contract["reasoning_stages"],
        "implementation_boundary": "S4B remains controlled by HANDOFF.md, the worker contract, independent validation, and provider preflight",
    }
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(f"Selected reasoner: {selection['id']} ({selection.get('classification', 'unverified')})")
        print(f"Checked reasoner: {identifier} — {capability['availability']}")
        print(f"Version: {capability['version']}")
        print(f"Execution evidence: {capability['execution']}")
        print("Next: keep the selected reasoner, or use select-reasoner for an explicit switch.")
    return 0 if REASONERS.selectable(capability) else 2


MATERIAL_REASONER_OUTPUT = {
    "S1": "PROJECT.md",
    "S2": "RESEARCH.md",
    "S3": "DESIGN.md",
    "S4A": "HANDOFF.md",
    "S6": "RETROSPECTIVE.md",
}


def material_reasoner_output(state: dict, entry: dict, packet: Path) -> Path | None:
    if stage_has_evidence(packet):
        return packet / "evidence"
    relative = MATERIAL_REASONER_OUTPUT.get(entry["stage"])
    candidate = Path(state["project"]) / relative if relative else None
    if not candidate:
        return None
    baseline = entry.get("reasoner_output_baseline")
    if isinstance(baseline, dict) and baseline.get("path") == relative:
        exists = candidate.is_file()
        if exists != bool(baseline.get("exists")):
            return candidate
        if exists and sha256(candidate) != baseline.get("sha256"):
            return candidate
        return None
    return candidate if candidate.is_file() and candidate.stat().st_size else None


def preserved_s5_parameters(packet: Path) -> tuple[str, str]:
    text = read(packet / TRANSPORT.PACKET_NAME)
    target = re.search(r"(?m)^TARGET:\s+(.+?)\s*$", text)
    lenses = re.search(r"(?m)^LENSES:\s+(.+?)\s*$", text)
    if not target or not lenses or "<" in target.group(1) or "<" in lenses.group(1):
        raise RuntimeError_("Current S5 packet has no preserved target/lens parameters")
    return target.group(1).strip(), lenses.group(1).strip()


def reasoner_retry_args(run_root: Path, entry: dict, packet: Path) -> argparse.Namespace:
    values = dict(
        run_root=str(run_root), project=None, stage=entry["stage"], retry=True,
        provider=None, references_file=None, references_text=None, restart_context=None,
        motion=None, assets=None, target=None, lenses=None,
        synthetic_validation=TRANSPORT.is_within(packet, ROOT),
    )
    if entry["stage"] == "S3":
        references, motion, assets = preserved_s3_parameters(packet)
        manifest = json.loads(read(packet / TRANSPORT.MANIFEST_NAME))
        restart = next(
            (
                item.get("path")
                for item in manifest.get("sources", [])
                if item.get("kind") == "continuation-restart-context"
            ),
            None,
        )
        values.update(
            references_text=references,
            motion=motion,
            assets=assets,
            restart_context=restart,
        )
    elif entry["stage"] == "S5":
        target, lenses = preserved_s5_parameters(packet)
        values.update(target=target, lenses=lenses)
    return argparse.Namespace(**values)


def select_reasoner(args: argparse.Namespace) -> int:
    run_root, state = resolve_and_load(args)
    entry, packet = current_packet(state, allow_project_drift=True)
    contract = REASONERS.load_contract()
    capability = REASONERS.detect(args.reasoner, contract)
    current = REASONERS.selected(state, contract)
    if not REASONERS.selectable(capability):
        blocked = REASONERS.selection_record(
            args.reasoner, args.reason, capability, now(), status="blocked"
        )
        state.setdefault("reasoner_history", []).append(blocked)
        state["updated_at"] = now()
        write_state(run_root, state)
        append_log(
            run_root,
            "Reasoner selection blocked",
            args.reason,
            f"{args.reasoner} remains unavailable; {current['id']} remains selected.",
            evidence=capability.get("execution", "not observed"),
            next_action="Keep the current reasoner or make the external provider available.",
        )
        print(f"Stopped. {args.reasoner} is unavailable; {current['id']} remains selected.")
        return 2

    selection = REASONERS.selection_record(args.reasoner, args.reason, capability, now())
    if current["id"] == args.reasoner:
        state["reasoner"] = selection
        state.setdefault("reasoner_history", []).append(selection)
        state["updated_at"] = now()
        write_state(run_root, state)
        print(f"Done. {args.reasoner} remains the selected reasoner; capability evidence was refreshed.")
        return 0

    material = material_reasoner_output(state, entry, packet)
    if entry["stage"] not in contract["reasoning_stages"] or material:
        state["reasoner"] = selection
        state.setdefault("reasoner_history", []).append(selection)
        state["updated_at"] = now()
        state["next"] = (
            f"Finish the current {entry['stage']} boundary; {args.reasoner} applies at the next reasoning stage."
        )
        write_state(run_root, state)
        append_log(
            run_root,
            "Reasoner switch queued",
            args.reason,
            f"{current['id']} -> {args.reasoner}; current material state was preserved.",
            [str(material)] if material else [],
            "No gate or current implementation boundary changed.",
            state["next"],
        )
        print(f"Done. {args.reasoner} will be used at the next reasoning boundary.")
        return 0

    retry_args = reasoner_retry_args(run_root, entry, packet)
    evidence = packet / "evidence" / "reasoner-switch.json"
    if evidence.exists():
        raise RuntimeError_(f"Refusing to overwrite reasoner switch evidence: {evidence}")
    record = REASONERS.continuity_record(
        "reasoner-switch", entry["id"], entry["stage"], current["id"], args.reasoner,
        args.reason, "verified", now(),
    )
    write_json(evidence, record)
    state["reasoner"] = selection
    state.setdefault("reasoner_history", []).append(selection)
    state["updated_at"] = now()
    write_state(run_root, state)
    append_log(
        run_root,
        "Reasoner switched",
        args.reason,
        f"{current['id']} -> {args.reasoner}; a linked same-stage child will use canonical state.",
        [str(evidence)],
        "Verified selection and immutable parent continuity; no gate changed.",
        f"Prepare the linked {entry['stage']} child.",
    )
    return prepare_next(retry_args)


def record_reasoner_failure(args: argparse.Namespace) -> int:
    run_root, state = resolve_and_load(args)
    entry, packet = current_packet(state, allow_project_drift=True)
    manifest = json.loads(read(packet / TRANSPORT.MANIFEST_NAME))
    contract = REASONERS.load_contract()
    if entry["stage"] not in contract["reasoning_stages"]:
        raise RuntimeError_("Reasoner failure recovery does not own the S4B implementation boundary")
    from_reasoner = manifest.get("provider")
    if from_reasoner not in contract["providers"]:
        raise RuntimeError_(f"Current packet has no supported reasoner provider: {from_reasoner}")
    destination = packet / "evidence" / "reasoner-failure.json"
    if destination.exists():
        raise RuntimeError_(f"Refusing to overwrite reasoner failure evidence: {destination}")
    material = material_reasoner_output(state, entry, packet)
    safe_fallback = from_reasoner != "codex" and material is None
    record = REASONERS.continuity_record(
        "reasoner-failure", entry["id"], entry["stage"], from_reasoner,
        "codex" if safe_fallback else None, args.summary, args.evidence, now(),
    )
    write_json(destination, record)
    state.setdefault("reasoner_history", []).append({"event": "failure", **record})
    if not safe_fallback:
        state["updated_at"] = now()
        state["next"] = (
            "Decide how to preserve or continue the material partial output."
            if material
            else "Resolve the Codex failure before continuing; no unverified automatic fallback is selected."
        )
        write_state(run_root, state)
        append_log(
            run_root,
            "Reasoner failure recorded",
            "A provider failure must not become completion or silently replace material creative work.",
            args.summary,
            [str(destination)] + ([str(material)] if material else []),
            f"{args.evidence}; no gate changed and no fallback packet was created.",
            state["next"],
        )
        print(f"Paused. The {from_reasoner} failure was preserved; no automatic fallback was safe.")
        return 2

    retry_args = reasoner_retry_args(run_root, entry, packet)
    capability = REASONERS.detect("codex", contract)
    fallback = REASONERS.selection_record(
        "codex", f"Safe fallback after {from_reasoner} failure: {args.summary}",
        capability, now(), status="fallback",
    )
    state["reasoner"] = fallback
    state.setdefault("reasoner_history", []).append(fallback)
    state["updated_at"] = now()
    write_state(run_root, state)
    append_log(
        run_root,
        "Reasoner fallback prepared",
        "No material stage output existed, so retrying from canonical state cannot erase a creative decision.",
        f"{from_reasoner} -> codex after: {args.summary}",
        [str(destination)],
        f"{args.evidence}; no gate changed.",
        f"Prepare the linked {entry['stage']} Codex retry.",
    )
    return prepare_next(retry_args)


def discover(args: argparse.Namespace) -> int:
    project = Path(args.project).resolve()
    matches = discover_run_roots(project)
    if not matches:
        raise RuntimeError_(f"No Ariadne run records this project: {project}")
    payload = {"project": str(project), "runs": [str(path) for path in matches]}
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        if len(matches) == 1:
            print(f"Found Ariadne run for {project.name}: {matches[0]}")
        else:
            print(f"Found {len(matches)} Ariadne runs for {project.name}:")
            for path in matches:
                print(f"  {path}")
            print("Choose the intended run explicitly; Ariadne will not guess between histories.")
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


# The mapping from an R1 capability class to a concrete vendor model is dated
# runtime knowledge held in this file. It is a source-edit contract, not a live
# lookup: when the model landscape changes, edit these two lines and the matrix in
# recommend_task_routing. Nothing here is ever reported as verified.
MODEL_LANDSCAPE_DATED = "2026-09-05"
MODEL_LANDSCAPE_MODELS = (
    "GPT-5.6 Luna", "GPT-5.6 Terra", "GPT-5.6 Sol", "GPT-6 Astra",
)


def recommend_task_routing(task: dict) -> dict:
    """Recommend capability class, concrete model, effort, session strategy, and rationale.

    TASK -> CAPABILITY CLASS -> MODEL/PROVIDER -> EFFORT -> SESSION STRATEGY

    Dimensions read from the task:
    1. Task complexity                  -> difficulty gate
    2. Ambiguity                        -> difficulty gate
    3. Consequence of error             -> stakes gate
    4. Reversibility                    -> stakes gate
    5. Visual / creative importance     -> stakes gate
    6. Context requirements             -> difficulty gate
    7. Expected iterations (operator judgement; accepted but not automated)
    8. Primary nature (reasoning vs execution vs mechanical) -> capability class
    9. Reliable cost vs expected quality threshold -> the two gates together

    Within R1 the dimensions are not summed or weighted. They collapse into two
    ordinal gates, difficulty and stakes, and escalation requires both. This is a
    judgement aid, not a calibrated model: the tier boundaries are argued, not
    measured, and an operator who disagrees should override the recommendation.
    """
    task_type = task.get("task_type")
    stage = task.get("stage")
    complexity = task.get("complexity", "medium")
    ambiguity = task.get("ambiguity", "medium")
    consequence = task.get("consequence", "medium")
    reversibility = task.get("reversibility", "medium")
    visual_importance = task.get("visual_creative_importance", task.get("visual_importance", "low"))
    context_requirements = task.get("context_requirements", "medium")

    context_state = task.get("context_state", "useful")
    same_objective = task.get("same_objective", True)
    independence_required = (
        task.get("independence_required", False)
        or context_state == "independent_required"
        or stage == "S5"
        or task.get("independent_review", False)
    )

    explicit_provider = str(task.get("provider") or "").strip()
    provider = explicit_provider or "implementation-worker"
    provider_available = task.get("provider_available", True)
    if isinstance(provider_available, str):
        provider_available = provider_available.lower() in ("yes", "true", "available")
    quota_sufficient = task.get("quota_sufficient", True)
    if isinstance(quota_sufficient, str):
        quota_sufficient = quota_sufficient.lower() in ("yes", "true", "sufficient")
    runtime_model = task.get("runtime_model")
    escalated = task.get("escalated", False)

    # 1. Capability class selection (R1-R6)
    if not task_type:
        if stage in ("S5_mechanical", "S6_ship"):
            task_type = "mechanical"
        elif stage in ("S4", "S4B"):
            task_type = "implementation"
        elif stage == "S5":
            task_type = "reasoning"
        elif stage in ("S0", "S1", "S2", "S3", "S4A", "S6_retro"):
            task_type = "reasoning"
        else:
            task_type = "reasoning"

    # Escalation: bugs surviving multiple attempts, conflicting requirements, or core design changes
    if task_type == "implementation" and escalated:
        task_type = "reasoning"
        reversibility = "low"
        consequence = "high"
        ambiguity = "high"

    if task_type == "mechanical":
        cap_class = "R6"
        cap_desc = "R6 Local / free"
        model = "Terminal / Local tools"
        effort = "none"
        cap_why = (
            "Deterministic checks and commands (build, lint, test, git) are free and fast in R6; "
            "reasoning models must never run mechanical builds or checks."
        )
    elif task_type == "browser":
        cap_class = "R4"
        cap_desc = "R4 Browser / visual"
        model = f"{provider} browser tools or Playwright" if explicit_provider else "browser tools or Playwright"
        effort = "low"
        cap_why = "DOM verification and visual interaction QA belong in R4 browser tooling."
    elif task_type == "generative":
        cap_class = "R5"
        cap_desc = "R5 Generative visual"
        model = "Subscription image tooling"
        effort = "medium"
        cap_why = "Generative visual assets and concepts belong in R5."
    elif task_type == "reading":
        cap_class = "R3"
        cap_desc = "R3 Long-context reading"
        model = f"{provider} (codebase indexing)" if explicit_provider else "codebase indexing tools"
        effort = "medium"
        cap_why = "Codebase indexing and cross-file search belong in R3; never paste full codebases into R1."
    elif task_type == "implementation":
        cap_class = "R2"
        cap_desc = "R2 Fast implementation"
        if not provider_available or not quota_sufficient:
            model = task.get("fallback_provider") or "another configured implementation worker"
            effort = "medium"
            cap_why = f"Implementation spec is locked; primary provider {provider} constrained, falling back to {model} without weakening capability."
        else:
            if runtime_model:
                model = f"{provider} ({runtime_model})" if explicit_provider else str(runtime_model)
            elif task.get("interactive_iteration") and explicit_provider:
                model = f"{provider} (interactive implementation model)"
            else:
                model = f"{provider} (default implementation model)"
            effort = "medium"
            cap_why = "The design and handoff are already locked; this is execution rather than new reasoning."
    else:  # reasoning (R1)
        cap_class = "R1"
        cap_desc = "R1 Deep reasoning"

        # Two orthogonal gates decide how much reasoning capability is worth buying.
        #
        #   difficulty -- how hard is this to get right (complexity, ambiguity, context)
        #   stakes     -- how expensive is it to be wrong (consequence, reversibility, value)
        #
        # Escalation requires both axes, never one alone. A hard task whose answer is
        # cheap to check and cheap to undo is better retried on a cheaper model than
        # escalated; an easy task with high stakes needs care and verification rather
        # than a larger model. Neither axis is a score: each is a small ordinal gate.
        if complexity in ("novel", "extreme"):
            difficulty = "exceptional"
        elif complexity == "high" or ambiguity == "high":
            difficulty = "high"
        elif complexity == "low" and ambiguity == "low" and context_requirements != "high":
            difficulty = "low"
        else:
            difficulty = "medium"

        if consequence == "high" or reversibility == "low" or visual_importance == "high":
            stakes = "high"
        elif consequence == "low" and reversibility == "high":
            stakes = "low"
        else:
            stakes = "medium"

        # difficulty x stakes -> concrete R1 model. Read this table as the routing policy.
        r1_matrix = {
            ("low", "low"): "GPT-5.6 Luna",
            ("low", "medium"): "GPT-5.6 Luna",
            ("low", "high"): "GPT-5.6 Terra",
            ("medium", "low"): "GPT-5.6 Luna",
            ("medium", "medium"): "GPT-5.6 Terra",
            ("medium", "high"): "GPT-5.6 Sol",
            ("high", "low"): "GPT-5.6 Terra",
            ("high", "medium"): "GPT-5.6 Sol",
            ("high", "high"): "GPT-5.6 Sol",
            ("exceptional", "low"): "GPT-5.6 Terra",
            ("exceptional", "medium"): "GPT-5.6 Sol",
            ("exceptional", "high"): "GPT-6 Astra",
        }
        r1_reasons = {
            "GPT-5.6 Luna": "Bounded reasoning with limited downside; a stronger model is unlikely to change the answer.",
            "GPT-5.6 Terra": "Balanced analysis where moderate capability is justified without Sol expenditure.",
            "GPT-5.6 Sol": "Difficult and consequential reasoning where a wrong answer is expensive to detect or undo.",
            "GPT-6 Astra": "Exceptional difficulty combined with high stakes; the extra capability is justified here.",
        }

        if not provider_available or not quota_sufficient:
            model = task.get("fallback_provider") or "configured reasoning fallback"
            cap_why = "Primary reasoning provider is constrained; using the configured reasoning fallback without weakening the R1 deep reasoning requirement."
        else:
            model = r1_matrix[(difficulty, stakes)]
            cap_why = f"{r1_reasons[model]} (difficulty {difficulty} / stakes {stakes})"
            if model == "GPT-5.6 Terra" and not task.get("terra_available", True):
                model = "GPT-5.6 Sol"
                cap_why = (
                    "Terra is unavailable in this runtime; escalating rather than under-routing "
                    f"preserves the reasoning capability this task needs (difficulty {difficulty} / stakes {stakes})."
                )

        # Effort follows the same two gates, not the chosen model.
        if difficulty == "exceptional" and stakes == "high":
            effort = "xhigh"
        elif difficulty in ("exceptional", "high") or stakes == "high":
            effort = "high"
        elif difficulty == "low" and stakes == "low":
            effort = "low"
        else:
            effort = "medium"

        # Same damping rule as model selection: when a wrong answer is cheap to detect
        # and cheap to undo, deep deliberation is not worth buying either.
        if stakes == "low" and effort in ("high", "xhigh", "max"):
            effort = "medium"

        # Model compatibility guard. The gates above should not produce these, but the
        # recommendation must never name an effort the target model does not support.
        if model == "GPT-5.6 Luna" and effort in ("high", "xhigh", "max"):
            effort = "medium"
        elif model in ("GPT-5.6 Terra", "GPT-5.6 Sol") and effort in ("xhigh", "max"):
            effort = "high"

    # Session Strategy: Context Value vs Independence
    if independence_required:
        session = "New"
        session_why = "Independent judgement is required; the session must not inherit the author's prior reasoning or justifications."
    elif context_state in ("noisy", "stale") or task.get("drifted", False):
        session = "New"
        session_why = "Accumulated conversation context has drifted or become noisy; fresh context clears stale assumptions."
    elif not same_objective or task.get("project_changed", False) or task.get("major_phase_change", False):
        session = "New"
        session_why = "Changing major objectives or phases; the value of clean context exceeds continuity."
    elif same_objective and context_state == "useful":
        session = "Continue"
        session_why = "The same objective remains active and existing context materially aids continuity."
    else:
        session = "New"
        session_why = "Fresh context is recommended to avoid carrying unnecessary conversation overhead."

    # Staleness: model capabilities, quotas, and pricing drift over time, so every
    # recommendation says where its model name came from. "evidence_class" is not
    # used here: that key already carries two different validated vocabularies
    # elsewhere in Ariadne (reasoners.py, creative-operations.py).
    if runtime_model:
        # The operator read this model out of their own runtime; Ariadne did not check it.
        model_landscape_evidence = "operator-reported"
        model_landscape_dated = None
    elif model in MODEL_LANDSCAPE_MODELS:
        model_landscape_evidence = "unverified"
        model_landscape_dated = MODEL_LANDSCAPE_DATED
    else:
        # Local tooling, provider defaults, and fallbacks name no dated vendor model.
        model_landscape_evidence = "not-applicable"
        model_landscape_dated = None

    return {
        "capability_class": cap_class,
        "capability": cap_desc,
        "model": model,
        "effort": effort,
        "session": session,
        "why": f"{cap_why} {session_why}".strip(),
        "task_why": cap_why,
        "session_why": session_why,
        "model_landscape_dated": model_landscape_dated,
        "model_landscape_evidence": model_landscape_evidence,
    }


def format_routing_recommendation(rec: dict) -> str:
    effort_str = rec["effort"].capitalize() if rec["effort"] != "none" else "None"
    lines = [
        "RECOMMENDED",
        f"- Capability: {rec['capability']}",
        f"- Model: {rec['model']}",
        f"- Effort: {effort_str}",
        f"- Session: {rec['session']}",
        f"- Why: {rec['why']}",
    ]
    evidence = rec.get("model_landscape_evidence")
    if rec.get("model_landscape_dated"):
        lines.append(
            f"- Model landscape: dated {rec['model_landscape_dated']}, {evidence} "
            "(check the model still exists and still fits before relying on it)"
        )
    elif evidence == "operator-reported":
        lines.append("- Model landscape: operator-reported runtime model; Ariadne did not check it")
    return "\n".join(lines)


def route_command(args: argparse.Namespace) -> int:
    task = {
        "task_type": args.task_type,
        "stage": args.stage,
        "complexity": args.complexity,
        "ambiguity": args.ambiguity,
        "consequence": args.consequence,
        "reversibility": args.reversibility,
        "visual_creative_importance": args.visual_importance,
        "context_requirements": args.context_requirements,
        "context_state": args.context_state,
        "same_objective": args.same_objective,
        "provider_available": args.provider_available,
        "quota_sufficient": args.quota_sufficient,
        "runtime_model": args.runtime_model,
        "escalated": getattr(args, "escalated", False),
    }
    rec = recommend_task_routing(task)
    if getattr(args, "json", False):
        print(json.dumps(rec, indent=2, sort_keys=True))
    else:
        print(format_routing_recommendation(rec))
    return 0


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
    contract = TRANSPORT.worker_contract(read(handoff))
    if contract["worker_role"] not in TRANSPORT.WORKER_ROLES:
        raise RuntimeError_("HANDOFF.md has no supported Worker role in its execution contract")
    values["worker role"] = contract["worker_role"]
    return values


def provider_preflight(args: argparse.Namespace) -> int:
    run_root, state = resolve_and_load(args)
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
    if effort not in ("low", "medium", "high", "xhigh", "max"):
        raise RuntimeError_(f"HANDOFF.md has unsupported effort: {effort}")
    if workload not in ("small", "medium", "large"):
        raise RuntimeError_(f"HANDOFF.md has unsupported workload: {workload}")
    retained = provider.strip().lower() in ("retain in orchestrator", "orchestrator")
    if retained:
        decision = "not-required"
        reason = "Implementation remains in the orchestrator; no external worker preflight is required."
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
        "worker_role": routing["worker role"],
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
    write_state(run_root, state)
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
    run_root, state = resolve_and_load(args)
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
    run_root, state = resolve_and_load(args)
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
    # AR-202 T2: a same-session stage result is still bound to an engine-created
    # execution, so later validation and review can name what produced it.
    reasoner_execution, _execution_problems = execution_for_task(
        state, task_id=entry["id"], role="reasoner",
        adapter=f"scripts/ariadne.py:record-result ({args.provider})",
        invocation=f"record-result --status {args.status}",
        requested={"provider": str(args.provider or ""), "model": str(args.model or "")},
        packet=packet,
        reason=f"recorded {entry['stage']} stage outputs",
    )
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
        "execution": str((reasoner_execution or {}).get("execution_id", "")),
    }
    write_json(destination, result)
    if reasoner_execution is not None:
        EXECUTION.report(
            state, str(reasoner_execution["execution_id"]),
            provider=str(args.provider or ""), model=str(args.model or ""),
            evidence=f"stage-result {entry['id']}",
        )
        EXECUTION.complete(
            state, str(reasoner_execution["execution_id"]),
            result={"packet_id": entry["id"], "status": args.status, "artifact": str(destination)},
            evidence=tuple(item["path"] for item in files),
        )
        emit_event(
            run_root, "execution_completed", state=state, task_id=entry["id"], stage=entry["stage"],
            execution=str(reasoner_execution["execution_id"]), role="reasoner", status=args.status,
            provider=str(args.provider or ""), model=str(args.model or ""),
        )
    state["updated_at"] = now()
    state["evidence_state"] = result["evidence_class"]
    state["next"] = "Discover and prepare the next valid boundary."
    write_state(run_root, state)
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
    run_root, state = resolve_and_load(args)
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
    write_state(run_root, state)
    print("Done. The transcript was preserved verbatim.")
    return 0


def ingest_return(args: argparse.Namespace) -> int:
    run_root, state = resolve_and_load(args)
    entry, packet = current_packet(state, allow_project_drift=True)
    if entry["stage"] != "S4B":
        raise RuntimeError_("Implementation return handoffs belong to the current S4B boundary")
    source = Path(args.input).resolve()
    if not source.is_file():
        raise RuntimeError_(f"Return handoff input is missing: {source}")
    text = read(source)
    begin = "BEGIN ARIADNE RETURN HANDOFF"
    end = "END ARIADNE RETURN HANDOFF"
    if text.count(begin) == 1 and text.count(end) == 1:
        text = text.split(begin, 1)[1].split(end, 1)[0].strip() + "\n"
    problems = TRANSPORT.return_handoff_problems(text)
    if problems:
        raise RuntimeError_("Return handoff rejected: " + "; ".join(problems))
    manifest = worker_manifest(packet)
    destination = packet / "evidence" / "return-handoff.md"
    machine_destination = packet / "evidence" / "return-handoff.json"
    if destination.exists() or machine_destination.exists():
        raise RuntimeError_(f"Refusing to overwrite existing return handoff: {destination}")
    # AR-202 T2: this result must belong to an execution the engine created. A
    # caller-supplied id is verified, never quietly replaced by an adopted one.
    supplied_execution = str(getattr(args, "execution", "") or "").strip()
    implementer, execution_problems = (None, [])
    if supplied_execution:
        implementer, execution_problems = named_execution(
            state, supplied_execution, role="implementer", task_id=entry["id"]
        )
    if implementer is None and not supplied_execution:
        implementer, execution_problems = execution_for_task(
            state, task_id=entry["id"], role="implementer",
            adapter="scripts/ariadne.py:ingest-return",
            invocation="ingest-return (adopted: the packet predates execution binding)",
            requested={
                "provider": str(manifest.get("provider", "")),
                "model": str((state.get("provider_preflight") or {}).get("model", "") or ""),
                "worker_role": str((manifest.get("worker") or {}).get("role", "")),
            },
            packet=packet,
            reason="the return arrived for a packet prepared before execution binding; an engine identity is adopted",
        )
    if execution_problems or implementer is None:
        raise RuntimeError_(
            "Return handoff rejected: "
            + "; ".join(execution_problems or ["no engine-created execution matches this result"])
        )
    verification = execution_verify_result(state, implementer, entry, packet)
    if verification:
        record_failure(
            state,
            source="stale-revision" if any("revision" in item for item in verification) else "duplicate-result",
            operation=f"ingest-return:{entry['id']}",
            evidence=[str(source)] + verification,
            execution_id=str(implementer.get("execution_id", "")),
            task_id=entry["id"],
            revision_hash=str((implementer.get("revision") or {}).get("revision_hash", "")),
            detail="the submitted return does not belong to the open execution for this boundary",
        )
        write_state(run_root, state)
        raise RuntimeError_("Return handoff rejected: " + "; ".join(verification))
    metadata = {}
    for field in (
        "Status", "Task ID", "Worker role", "Provider", "Model", "Effort",
        "Started", "Ended", "Usage", "Cost",
    ):
        match = re.search(rf"(?im)^\*\*{re.escape(field)}:\*\*\s*(.+?)\s*$", text)
        metadata[field.lower()] = match.group(1).strip() if match else "unrecorded"
    expected_worker = manifest.get("worker", {})
    if metadata.get("task id") != entry["id"]:
        raise RuntimeError_("Return handoff Task ID does not match the current packet")
    if metadata.get("worker role", "").lower() != str(expected_worker.get("role", "")).lower():
        raise RuntimeError_("Return handoff Worker role does not match the current packet")
    return_status = metadata["status"].lower()
    sections = {
        slug(heading): safe_section(text, heading).strip()
        for heading in TRANSPORT.RETURN_HANDOFF_HEADINGS
    }
    # AR-202 T14: the worker's runtime claim is recorded as *reported* identity.
    # Only the runtime can observe identity, and this runtime cannot, so observed
    # stays UNKNOWN rather than being manufactured from the claim.
    reported_provider = str(metadata.get("provider", "") or "")
    reported_model = str(metadata.get("model", "") or "")
    EXECUTION.report(
        state, str(implementer["execution_id"]),
        provider=reported_provider, model=reported_model,
        evidence=f"return handoff {machine_destination.name}",
    )
    identity = EXECUTION.identity_view(state, str(implementer["execution_id"]))
    handoff_routing_declared = {}
    if (Path(state["project"]) / "HANDOFF.md").is_file():
        try:
            handoff_routing_declared = handoff_routing(Path(state["project"]))
        except RuntimeError_:
            handoff_routing_declared = {}
    pinned_model = ROUTING.declared_identity_pin(
        state, {"routing": handoff_routing_declared}
    )
    decision, identity_reason = EXECUTION.mismatch_decision(identity, pinned=bool(pinned_model))
    if decision == "refused":
        record_failure(
            state,
            source="provider-mismatch",
            operation=f"ingest-return:{entry['id']}",
            evidence=[str(destination), identity_reason],
            execution_id=str(implementer["execution_id"]),
            task_id=entry["id"],
            revision_hash=str((implementer.get("revision") or {}).get("revision_hash", "")),
            detail=identity_reason,
        )
        write_state(run_root, state)
        raise RuntimeError_("Return handoff rejected: " + identity_reason)
    # Every refusal above happens before the artifact is written, so a rejected
    # return never leaves evidence behind that a later ingest would refuse to replace.
    destination.write_text(text, encoding="utf-8")
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
            "implementation_state": "IMPLEMENTED" if return_status == "complete" else return_status.upper(),
            "execution": {
                "execution_id": str(implementer["execution_id"]),
                "role": str(implementer.get("role", "")),
                "requested": identity["requested"],
                "reported": identity["reported"],
                "observed": identity["observed"],
                "mismatch": identity["mismatch"],
                "identity_note": identity_reason,
            },
        },
    )
    EXECUTION.complete(
        state, str(implementer["execution_id"]),
        result={
            "packet_id": entry["id"],
            "status": return_status,
            "artifact": str(machine_destination),
            "sha256": sha256(machine_destination),
        },
        evidence=(str(destination),),
    )
    emit_event(
        run_root, "execution_completed", state=state, task_id=entry["id"], stage="S4B",
        execution=str(implementer["execution_id"]), role="implementer",
        status=return_status, mismatch=bool(identity["mismatch"]),
        provider=reported_provider, model=reported_model,
    )
    if identity["mismatch"]:
        emit_event(
            run_root, "execution_observed", state=state, task_id=entry["id"], stage="S4B",
            execution=str(implementer["execution_id"]),
            requested_provider=str(identity["requested"].get("provider", "")),
            reported_provider=reported_provider,
            note=identity_reason,
        )
    worker = worker_state(state)
    worker.update({
        "task_id": entry["id"],
        "worker_role": expected_worker.get("role", "unknown"),
        "provider": metadata.get("provider", "unknown"),
        "model": metadata.get("model", "unknown"),
        "started_at": metadata.get("started", "unknown"),
        "ended_at": metadata.get("ended", "unknown"),
        "execution_id": str(implementer["execution_id"]),
        "reported_provider": reported_provider,
        "reported_model": reported_model,
    })
    STATEMACHINE.apply_transition(
        state,
        CONTRACTS.TransitionRequest(
            kind="worker-lifecycle",
            to=str(
                STATEMACHINE.validation_pending if return_status == "complete"
                else STATEMACHINE.repair_or_escalation
            ),
            reason=f"Worker returned a structured handoff with status {return_status}.",
            evidence=(str(machine_destination),),
            fields={
                "implementation_state": "IMPLEMENTED" if return_status == "complete" else return_status.upper(),
                "validation_state": "NOT_RUN",
            },
            actor="worker",
            operation=f"ingest-return:{entry['id']}",
        ),
        permitted=True,
    )
    worker.update({
        "review_state": worker.get("review_state", "NOT_REVIEWED"),
        "acceptance_state": worker.get("acceptance_state", "UNKNOWN"),
    })
    append_worker_telemetry(
        run_root,
        "worker-run",
        task_id=entry["id"],
        worker_role=expected_worker.get("role", "unknown"),
        provider=metadata.get("provider", "unknown"),
        model=metadata.get("model", "unknown"),
        start=metadata.get("started", "unknown"),
        end=metadata.get("ended", "unknown"),
        duration_seconds=iso_duration(metadata.get("started"), metadata.get("ended")),
        attempt=expected_worker.get("attempt", 1),
        validation_attempts=worker.get("validation_attempts", 0),
        files_changed=sections.get("files-changed", "none"),
        tests_result=sections.get("tests", "not recorded"),
        escalation_count=worker.get("escalation_count", 0),
        review_outcome="not reviewed",
        accepted="unknown",
        usage=metadata.get("usage", "unknown"),
        cost=metadata.get("cost", "unknown"),
        failure_reason="none" if return_status == "complete" else return_status,
    )
    state["updated_at"] = now()
    state["evidence_state"] = "structured external return; transcript remains separate"
    state["next"] = (
        "Run Ariadne's independent worker validation before preparing review."
        if return_status == "complete"
        else "Resume from the incomplete-work section or route the blocker."
    )
    ensure_intervention(
        state,
        "necessary",
        "Start the selected external implementation worker.",
        "The current worker boundary cannot execute without the human opening or authorising that external environment.",
        "external-provider-launch",
        status="resolved",
        evidence=str(destination),
    )
    write_state(run_root, state)
    append_log(
        run_root,
        "Implementation return ingested",
        "Ariadne needs durable implementation state without relying on provider conversation history.",
        f"Validated structured return with status {return_status}.",
        [str(destination), str(machine_destination)],
        "Structured provider report; not a verbatim transcript and not independent QA.",
        state["next"],
    )
    print(f"Done. The {return_status} implementation return is recorded and ready for continuity.")
    return 0


def externalize_validation_output(
    run_root: Path,
    state: dict,
    *,
    command: dict,
    stdout: str,
    stderr: str,
) -> dict:
    """Preserve a large validation output as an artifact instead of dropping it.

    AR-204 T6: today only a digest of the output survives. With the threshold
    profile enabled, a large stdout/stderr stream is written *in full* to
    ``evidence/artifacts`` and the command result keeps the digest, the measured
    size and a bounded excerpt plus a retrieval reference. Small output is
    untouched, so nothing changes for the ordinary case.
    """
    if EFFICIENCY.setting(state, "output_externalization") != "threshold":
        return {}
    threshold = ARTIFACTS.DEFAULT_EXTERNALIZE_AT_BYTES
    fields: dict = {}
    for name, text in (("stdout", stdout), ("stderr", stderr)):
        if len(str(text).encode("utf-8")) <= threshold:
            continue
        record = ARTIFACTS.externalize(
            run_root,
            data=str(text),
            tool=f"validation-{name}",
            command=str(command.get("command", "")),
            task_id="",
            run_id=str(state.get("run_id", "")),
        )
        CONTRACTS.require_collection_capacity(state, "artifacts")
        state.setdefault("artifacts", []).append(record)
        fields[f"{name}_artifact"] = {
            "artifact_id": record["artifact_id"],
            "relative_path": record["relative_path"],
            "sha256": record["sha256"],
            "size": record["size"],
            "status": record["status"],
            "excerpt": record["excerpt"],
            "summary": record["summary"],
        }
    if fields:
        fields["output_externalized"] = True
    return fields


def finish_worker_validation(
    run_root: Path,
    state: dict,
    entry: dict,
    packet: Path,
    record: dict,
) -> int:
    destination = packet / "evidence" / "validation.json"
    if destination.exists():
        raise RuntimeError_(f"Refusing to overwrite existing worker validation: {destination}")
    problems = TRANSPORT.worker_validation_problems(record, entry["id"])
    if problems:
        raise RuntimeError_("Worker validation record is malformed: " + "; ".join(problems))
    # AR-202 T2: validation is its own engine-created execution. It is a fresh
    # identity per attempt and its parent is the implementation it validated, so
    # implementation and validation can never collapse into one provenance.
    implementer = find_implementer_execution(state, task_id=entry["id"])
    validator, execution_problems = execution_for_task(
        state, task_id=entry["id"], role="validator",
        adapter="scripts/ariadne.py:validate-worker",
        invocation="validate-worker",
        requested={
            "provider": str(record.get("executor", "")),
            "model": "local-independent-validator",
        },
        packet=packet,
        reason="independent worker validation of the recorded implementation",
        reuse=False,
        parent=str(implementer.get("execution_id", "")) if implementer else "",
    )
    if execution_problems:
        raise RuntimeError_("Worker validation rejected: " + "; ".join(execution_problems))
    record = {**record, "execution": {
        "execution_id": str(validator["execution_id"]),
        "role": "validator",
        "parent_execution": str(validator.get("parent_execution", "")),
        "implementing_execution": str(implementer.get("execution_id", "")) if implementer else "",
    }}
    write_json(destination, record)
    if record.get("status") == "passed":
        EXECUTION.complete(
            state, str(validator["execution_id"]),
            result={"packet_id": entry["id"], "status": "passed", "artifact": str(destination)},
            evidence=(str(destination),),
        )
        emit_event(
            run_root, "execution_completed", state=state, task_id=entry["id"], stage="S4B",
            execution=str(validator["execution_id"]), role="validator", status="passed",
        )
    else:
        update_record, failure_record = EXECUTION.fail(
            state,
            str(validator["execution_id"]),
            source=str(record.get("failure_kind", "routine")),
            evidence=[str(destination), str(record.get("failure_reason", ""))],
            detail=str(record.get("failure_reason", "")),
        )
        record["execution"]["failure"] = dict(update_record.get("failure") or {})
        write_json(destination, record)
        emit_event(
            run_root, "execution_failed", state=state, task_id=entry["id"], stage="S4B",
            execution=str(validator["execution_id"]), role="validator",
            failure_class=failure_record["class"], status=str(record.get("status", "")),
        )
    emit_event(
        run_root, "validation_recorded", state=state, task_id=entry["id"], stage="S4B",
        execution=str(validator["execution_id"]),
        status=str(record.get("status", "")),
        scope=str((record.get("scope") or {}).get("status", "")),
    )
    manifest = worker_manifest(packet)
    manifest_worker = manifest.get("worker", {})
    row = worker_state(state)
    if row.get("task_id") != entry["id"]:
        row = update_worker_state(state, manifest)
    try:
        repair_attempts = int(manifest_worker.get("attempt", 1)) - 1
        repair_limit = int(manifest_worker.get("repair_limit", TRANSPORT.MAX_ROUTINE_REPAIRS))
    except (TypeError, ValueError):
        repair_attempts = 0
        repair_limit = TRANSPORT.MAX_ROUTINE_REPAIRS
    outcome = worker_outcome(
        record["status"], record.get("failure_kind", "routine"), repair_attempts, repair_limit
    )
    escalation_increment = int(outcome["escalation_required"] and row.get("lifecycle") != "escalation-required")
    row.update({
        "validation_attempts": int(row.get("validation_attempts", 0)) + 1,
        "escalation_count": int(row.get("escalation_count", 0)) + escalation_increment,
    })
    STATEMACHINE.apply_transition(
        state,
        CONTRACTS.TransitionRequest(
            kind="worker-lifecycle",
            to=str(outcome["lifecycle"]),
            reason=f"Independent validation result: {record['status']}",
            evidence=(str(destination),),
            fields={
                "implementation_state": outcome["implementation_state"],
                "validation_state": outcome["validation_state"],
                "last_validation": str(destination),
            },
            actor="runtime",
            operation="independent-validation",
        ),
        permitted=True,
    )
    state["updated_at"] = now()
    state["evidence_state"] = f"independent worker validation: {outcome['validation_state']}"
    state["next"] = outcome["next"]
    write_state(run_root, state)
    command_results = record.get("commands", [])
    append_worker_telemetry(
        run_root,
        "worker-validation",
        task_id=entry["id"],
        worker_role=row.get("worker_role", manifest_worker.get("role", "unknown")),
        provider=row.get("provider", manifest.get("provider", "unknown")),
        model=row.get("model", "unknown"),
        start=record.get("started", "unknown"),
        end=record.get("ended", "unknown"),
        duration_seconds=record.get("duration_seconds"),
        attempt=manifest_worker.get("attempt", 1),
        validation_attempts=row["validation_attempts"],
        files_changed=record.get("changed_files", []),
        tests_result={item.get("id", "unknown"): item.get("status", "not-run") for item in command_results},
        escalation_count=row["escalation_count"],
        review_outcome="not reviewed",
        accepted="unknown",
        failure_reason=record.get("failure_reason", "none"),
    )
    append_log(
        run_root,
        "Independent worker validation",
        "A worker self-report is not acceptance; Ariadne reran the bounded checks and inspected repository scope.",
        f"{outcome['validation_state']}: {record.get('failure_reason', 'none')}",
        [str(destination)],
        f"Scope={record.get('scope', {}).get('status', 'unknown')}; commands={len(command_results)}; provider usage and cost remain unknown for this local validation.",
        state["next"],
    )
    print(f"Ariadne worker validation: {outcome['validation_state']}")
    print(f"Scope: {record.get('scope', {}).get('status', 'unknown')}")
    scope_value = record.get("scope", {})
    if scope_value.get("status") != "within-contract":
        changed_text = ", ".join(scope_value.get("changed", [])) or "none"
        outside_text = ", ".join(scope_value.get("outside", [])) or "none"
        print("Changed paths: " + changed_text)
        print("Outside scope: " + outside_text)
    print(f"Checks recorded: {len(command_results)}")
    print(f"Next: {state['next']}")
    return 0 if record["status"] == "passed" else 2


def validate_worker(args: argparse.Namespace) -> int:
    """Independently validate one S4B result and contain failures before S5."""
    run_root, state = resolve_and_load(args)
    entry, packet = current_packet(state, allow_project_drift=True)
    if entry["stage"] != "S4B":
        raise RuntimeError_("Independent worker validation belongs to the current S4B boundary")
    manifest = worker_manifest(packet)
    validation_path = packet / "evidence" / "validation.json"
    if validation_path.exists():
        raise RuntimeError_(f"Worker validation is already recorded: {validation_path}")
    return_path = packet / "evidence" / "return-handoff.md"
    if not return_path.is_file():
        target = structured_return_target(packet)
        if target is not None and target.is_file():
            ingest_return(argparse.Namespace(run_root=str(run_root), project=None, input=str(target)))
            state = load_state(run_root)
            entry, packet = current_packet(state, allow_project_drift=True)
            manifest = worker_manifest(packet)
            return_path = packet / "evidence" / "return-handoff.md"
    if not return_path.is_file():
        raise RuntimeError_("Cannot validate S4B before the worker return handoff is recorded")

    started = now()
    project = Path(state["project"])
    handoff_path = project / "HANDOFF.md"
    handoff_text = read(handoff_path) if handoff_path.is_file() else ""
    commands = TRANSPORT.validation_commands(handoff_text)
    worker = manifest.get("worker", {})
    baseline = manifest.get("project_baseline")
    current = TRANSPORT.project_git_snapshot(project)
    scope_rows = TRANSPORT.worker_contract(handoff_text).get("scope_rows", [])
    patterns = [row[0].strip("`") for row in scope_rows if row]
    patterns.append(f".ariadne/returns/{entry['id']}.md")
    # A retry at the same boundary inherits the earlier attempt's baseline, so the
    # earlier attempt's engine-written return file is present on disk but absent
    # from that baseline. It is Ariadne's own evidence, not this worker's change.
    for recorded in state.get("packets") or []:
        if isinstance(recorded, dict) and recorded.get("id"):
            patterns.append(f".ariadne/returns/{recorded['id']}.md")
    # Ariadne's own evidence ledgers are written by Ariadne commands, not by the
    # worker. Treating them as in-contract keeps the runtime from blocking the
    # evidence that its own continuation preconditions require; it does not widen
    # the worker's implementation scope.
    patterns.extend(TRANSPORT.RUNTIME_EVIDENCE_PATTERNS)

    base_record = {
        "schema_version": TRANSPORT.WORKER_VALIDATION_SCHEMA,
        "kind": "worker-validation",
        "packet_id": entry["id"],
        "stage": "S4B",
        "independent": True,
        "executor": "Ariadne local validator",
        "started": started,
        "ended": now(),
        "duration_seconds": 0.0,
        "scope": {"status": "not-run", "changed": [], "outside": [], "sensitive": [], "immutable": [], "head_changed": False},
        "changed_files": [],
        "commands": [],
        "usage": "unknown",
        "cost": "unknown",
    }

    if TRANSPORT.return_handoff_status(read(return_path)) != "complete":
        base_record.update({
            "status": "blocked",
            "failure_kind": "worker-blocked",
            "failure_reason": "The worker returned partial or blocked evidence; repair or escalate before validation.",
        })
        base_record["ended"] = now()
        base_record["duration_seconds"] = iso_duration(base_record["started"], base_record["ended"]) or 0.0
        return finish_worker_validation(run_root, state, entry, packet, base_record)

    contract_problems = TRANSPORT.worker_contract_problems(handoff_text)
    if contract_problems:
        base_record.update({
            "status": "blocked",
            "failure_kind": "contract",
            "failure_reason": "; ".join(contract_problems),
        })
        base_record["ended"] = now()
        base_record["duration_seconds"] = iso_duration(base_record["started"], base_record["ended"]) or 0.0
        return finish_worker_validation(run_root, state, entry, packet, base_record)

    if not isinstance(baseline, dict):
        base_record.update({
            "status": "blocked",
            "failure_kind": "repository-conflict",
            "failure_reason": "The packet has no repository baseline to contain worker changes.",
        })
        base_record["ended"] = now()
        base_record["duration_seconds"] = iso_duration(base_record["started"], base_record["ended"]) or 0.0
        return finish_worker_validation(run_root, state, entry, packet, base_record)

    scope = TRANSPORT.worker_scope_check(baseline, current, patterns, project)
    base_record["scope"] = scope
    base_record["changed_files"] = scope.get("changed", [])
    contract_hash = worker.get("contract_sha256")
    if contract_hash and sha256(handoff_path) != contract_hash:
        scope = dict(scope)
        scope["status"] = "repository-conflict"
        scope["immutable"] = sorted(set(scope.get("immutable", [])) | {"HANDOFF.md"})
        base_record["scope"] = scope
        base_record.update({
            "status": "blocked",
            "failure_kind": "repository-conflict",
            "failure_reason": "HANDOFF.md changed after packet preparation; the worker contract is immutable for this attempt.",
        })
        base_record["ended"] = now()
        base_record["duration_seconds"] = iso_duration(base_record["started"], base_record["ended"]) or 0.0
        return finish_worker_validation(run_root, state, entry, packet, base_record)

    immutable_sources = {"HANDOFF.md", "DESIGN.md"}
    for source in manifest.get("sources", []):
        source_path = Path(source.get("path", ""))
        if source_path.name.upper() in immutable_sources and source_path.is_file():
            if sha256(source_path) != source.get("source_sha256"):
                scope = dict(scope)
                scope["status"] = "repository-conflict"
                scope["immutable"] = sorted(set(scope.get("immutable", [])) | {source_path.name})
                base_record["scope"] = scope
                base_record.update({
                    "status": "blocked",
                    "failure_kind": "repository-conflict",
                    "failure_reason": f"{source_path.name} changed after packet preparation.",
                })
                base_record["ended"] = now()
                base_record["duration_seconds"] = iso_duration(base_record["started"], base_record["ended"]) or 0.0
                return finish_worker_validation(run_root, state, entry, packet, base_record)

    if scope["status"] != "within-contract":
        failure_kind = scope["status"]
        base_record.update({
            "status": "blocked",
            "failure_kind": failure_kind,
            "failure_reason": (
                f"Worker changes are {scope['status']}: "
                + ", ".join(scope.get("outside") or scope.get("sensitive") or scope.get("immutable") or ["repository state changed"])
            ),
        })
        base_record["ended"] = now()
        base_record["duration_seconds"] = iso_duration(base_record["started"], base_record["ended"]) or 0.0
        return finish_worker_validation(run_root, state, entry, packet, base_record)

    reported_scope = re.search(r"(?im)^\*\*Scope status:\*\*\s*(.+?)\s*$", read(return_path))
    reported_scope = reported_scope.group(1).strip().lower() if reported_scope else "not checked"
    if reported_scope in ("out-of-scope", "dangerous-action", "repository-conflict"):
        scope = dict(scope)
        scope["status"] = reported_scope
        scope["reported_by_worker"] = True
        base_record["scope"] = scope
        base_record.update({
            "status": "blocked",
            "failure_kind": reported_scope,
            "failure_reason": f"Worker reported {reported_scope} in the return handoff; inspect and escalate instead of guessing past the boundary.",
        })
        base_record["ended"] = now()
        base_record["duration_seconds"] = iso_duration(base_record["started"], base_record["ended"]) or 0.0
        return finish_worker_validation(run_root, state, entry, packet, base_record)

    timeout = min(max(int(getattr(args, "timeout", 120)), 1), 600)
    command_results = []
    required_failures = []
    optional_failures = []
    for command in commands:
        result = {
            "id": command["id"],
            "check": command["check"],
            "command": command["command"],
            "required": command["required"],
            "expected": command["expected"],
            "status": "not-run",
            "returncode": None,
            "duration_seconds": None,
            "stdout_sha256": None,
            "stderr_sha256": None,
            "error": command.get("error"),
        }
        if command.get("error"):
            result["status"] = "failed"
            (required_failures if command["required"] else optional_failures).append(command["id"])
            command_results.append(result)
            continue
        command_started = time.monotonic()
        try:
            completed = subprocess.run(
                command["argv"], cwd=project, capture_output=True, text=True,
                timeout=timeout, shell=False,
            )
            result.update({
                "status": "passed" if completed.returncode == 0 else "failed",
                "returncode": completed.returncode,
                "duration_seconds": round(time.monotonic() - command_started, 3),
                "stdout_sha256": hashlib.sha256((completed.stdout or "").encode("utf-8")).hexdigest(),
                "stderr_sha256": hashlib.sha256((completed.stderr or "").encode("utf-8")).hexdigest(),
            })
            result.update(externalize_validation_output(
                run_root, state, command=command, stdout=completed.stdout or "",
                stderr=completed.stderr or "",
            ))
        except subprocess.TimeoutExpired as exc:
            result.update({
                "status": "failed",
                "duration_seconds": round(time.monotonic() - command_started, 3),
                "stdout_sha256": hashlib.sha256((str(exc.stdout or "")).encode("utf-8")).hexdigest(),
                "stderr_sha256": hashlib.sha256((str(exc.stderr or "")).encode("utf-8")).hexdigest(),
                "error": f"timed out after {timeout}s",
            })
            result.update(externalize_validation_output(
                run_root, state, command=command, stdout=str(exc.stdout or ""),
                stderr=str(exc.stderr or ""),
            ))
        except OSError as exc:
            result.update({
                "status": "failed",
                "duration_seconds": round(time.monotonic() - command_started, 3),
                "error": f"could not run validation command: {exc}",
            })
        if result["status"] == "failed":
            (required_failures if command["required"] else optional_failures).append(command["id"])
        command_results.append(result)

    post_validation_scope = TRANSPORT.worker_scope_check(
        baseline,
        TRANSPORT.project_git_snapshot(project),
        patterns,
        project,
    )
    base_record["scope"] = post_validation_scope
    base_record["changed_files"] = post_validation_scope.get("changed", [])
    if post_validation_scope["status"] != "within-contract":
        scope_paths = (
            post_validation_scope.get("outside")
            or post_validation_scope.get("sensitive")
            or post_validation_scope.get("immutable")
            or ["repository state changed during validation"]
        )
        validation_ended = now()
        base_record.update({
            "status": "blocked",
            "failure_kind": post_validation_scope["status"],
            "failure_reason": (
                "Validation commands changed repository scope: "
                + ", ".join(scope_paths)
            ),
            "commands": command_results,
            "ended": validation_ended,
            "duration_seconds": iso_duration(base_record["started"], validation_ended) or 0.0,
            "optional_failures": optional_failures,
        })
        return finish_worker_validation(run_root, state, entry, packet, base_record)

    ended = now()
    failure_reason = "none"
    if required_failures:
        failure_reason = "Required validation failed: " + ", ".join(required_failures)
        if optional_failures:
            failure_reason += "; optional failures: " + ", ".join(optional_failures)
    elif optional_failures:
        failure_reason = "Required validation passed; optional checks failed: " + ", ".join(optional_failures)
    base_record.update({
        "status": "failed" if required_failures else "passed",
        "failure_kind": "routine" if required_failures else "none",
        "failure_reason": failure_reason,
        "commands": command_results,
        "ended": ended,
        "duration_seconds": iso_duration(base_record["started"], ended) or 0.0,
        "optional_failures": optional_failures,
    })
    return finish_worker_validation(run_root, state, entry, packet, base_record)


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
    run_root, state = resolve_and_load(args)
    entry, packet = current_packet(state, allow_project_drift=True)
    if entry["stage"] != "S5":
        raise RuntimeError_("Independent review judgements belong to the current S5 boundary")
    source = Path(args.input).resolve()
    if not source.is_file() or source.stat().st_size == 0:
        raise RuntimeError_(f"Independent review input is missing or empty: {source}")
    reviewer_identity = str(getattr(args, "reviewer_identity", "") or "").strip()
    review_kind = str(getattr(args, "kind", "") or "experience").strip().lower()
    if review_kind not in CONTRACTS.REVIEW_KINDS:
        raise RuntimeError_(f"Unsupported review kind: {review_kind}")
    # AR-202 T2: the review names two engine-created executions. The implementer
    # is the execution that produced the reviewed revision; the reviewer is a
    # fresh identity for this review, so review and implementation can never be
    # the same execution.
    implementing_task = reviewed_implementation_task(state, packet)
    implementer = find_implementer_execution(state, task_id=implementing_task) if implementing_task else None
    if implementer is None:
        raise RuntimeError_(
            "Independent review rejected: the reviewed implementation has no engine-created "
            "execution record, so review independence cannot be established"
        )
    supplied_execution = str(getattr(args, "execution", "") or "").strip()
    reviewer_execution, execution_problems = named_execution(
        state, supplied_execution, role="reviewer", task_id=entry["id"]
    )
    if supplied_execution and execution_problems:
        raise RuntimeError_("Independent review execution rejected: " + "; ".join(execution_problems))
    if reviewer_execution is None:
        reviewer_execution, execution_problems = execution_for_task(
            state, task_id=entry["id"], role="reviewer",
            adapter="scripts/ariadne.py:ingest-review",
            invocation=f"ingest-review --kind {review_kind}",
            requested={"provider": reviewer_identity, "model": "review-session"},
            packet=packet,
            reason=f"independent {review_kind} review of {implementing_task or entry['id']}",
            reuse=False,
            parent=str(implementer["execution_id"]),
        )
    if execution_problems:
        raise RuntimeError_("Independent review execution rejected: " + "; ".join(execution_problems))
    identity_problems = REVIEWS.independence_problems(
        state,
        reviewer_identity,
        reviewer_execution=str(reviewer_execution.get("execution_id", "")),
        implementing_execution=str(implementer.get("execution_id", "")),
    )
    if identity_problems:
        record_failure(
            state,
            source="out-of-scope",
            operation=f"ingest-review:{entry['id']}",
            evidence=[str(source)] + identity_problems,
            execution_id=str(reviewer_execution.get("execution_id", "")),
            task_id=entry["id"],
            revision_hash=str((reviewer_execution.get("revision") or {}).get("revision_hash", "")),
            detail="; ".join(identity_problems),
        )
        write_state(run_root, state)
        raise RuntimeError_("Independent review identity rejected: " + "; ".join(identity_problems))
    raw = read(source)
    block = extract_marked_block(raw, "BEGIN QA JUDGEMENT", "END QA JUDGEMENT", "Review response")
    problems = review_judgement_problems(block)
    if problems:
        raise RuntimeError_("Review judgement rejected: " + "; ".join(problems))
    evidence_problems = REVIEWS.review_evidence_problems(
        state, packet, review_kind, pending=("recorded review judgement",)
    )
    if evidence_problems:
        raise RuntimeError_("Independent review rejected: " + "; ".join(evidence_problems))
    evidence_dir = packet / "evidence"
    raw_destination = evidence_dir / "review-response.md"
    block_destination = evidence_dir / "review-judgement.md"
    if raw_destination.exists() or block_destination.exists():
        raise RuntimeError_("Refusing to overwrite existing independent review evidence")
    if REVIEWS.current_review(state, packet_id=entry["id"]) is not None:
        raise RuntimeError_("Refusing to overwrite the recorded independent review for this revision")
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
    recommendation = re.search(r"(?im)^\*\*Recommendation:\*\*\s*(.+?)\s*$", block)
    recommendation = recommendation.group(1).strip() if recommendation else "unknown"
    review_record = REVIEWS.build_record(
        state,
        packet,
        reviewer_identity=reviewer_identity,
        review_kind=review_kind,
        reviewer_role=str(getattr(args, "reviewer_role", "") or "independent-reviewer"),
        block=block,
        recommendation=recommendation,
        reviewer_execution=str(reviewer_execution.get("execution_id", "")),
        implementing_execution=str(implementer.get("execution_id", "")),
    )
    review_destination = REVIEWS.store(state, packet, review_record)
    EXECUTION.complete(
        state, str(reviewer_execution["execution_id"]),
        result={
            "packet_id": entry["id"], "outcome": review_record["outcome"],
            "artifact": str(block_destination), "sha256": sha256(block_destination),
        },
        evidence=(str(block_destination), str(review_destination)),
    )
    # The review boundary's own session execution (created when the packet was
    # prepared) ends with the recorded review, so it is never left open and
    # reported later as an interruption.
    for session in EXECUTION.open_executions(state, role="reasoner", task_id=entry["id"]):
        EXECUTION.complete(
            state, str(session["execution_id"]),
            result={"packet_id": entry["id"], "outcome": review_record["outcome"],
                    "artifact": str(review_destination)},
            evidence=(str(review_destination),),
        )
    emit_event(
        run_root, "execution_completed", state=state, task_id=entry["id"], stage="S5",
        execution=str(reviewer_execution["execution_id"]), role="reviewer",
        status=str(review_record["outcome"]),
    )
    emit_event(
        run_root, "review_recorded", state=state, task_id=entry["id"], stage="S5",
        execution=str(reviewer_execution["execution_id"]),
        review_outcome=str(review_record["outcome"]),
        review_kind=review_kind,
        implementing_execution=str(implementer.get("execution_id", "")),
        reviewer_identity=reviewer_identity,
    )
    worker = worker_state(state)
    worker["review_outcome"] = recommendation
    STATEMACHINE.apply_transition(
        state,
        CONTRACTS.TransitionRequest(
            kind="worker-lifecycle",
            to="reviewed",
            reason=f"Recorded {review_kind} review by {reviewer_identity}",
            evidence=(str(block_destination), str(review_destination)),
            fields={"review_state": "REVIEWED"},
            actor="reviewer",
            operation=f"review:{entry['id']}",
        ),
        permitted=True,
    )
    append_worker_telemetry(
        run_root,
        "worker-review",
        task_id=worker.get("task_id", "unknown"),
        worker_role=worker.get("worker_role", "unknown"),
        provider=worker.get("provider", "unknown"),
        model=worker.get("model", "unknown"),
        attempt=worker.get("attempt", 0),
        validation_attempts=worker.get("validation_attempts", 0),
        files_changed=[],
        tests_result="not applicable",
        escalation_count=worker.get("escalation_count", 0),
        review_outcome=worker["review_outcome"],
        accepted="unknown",
        usage="unknown",
        cost="unknown",
    )
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
    write_state(run_root, state)
    append_log(
        run_root,
        "Independent review ingested",
        "The reviewer output must be preserved and applied without manual rewriting or loss of independence.",
        (
            f"Verified marked judgement block; raw response preserved; QA judgement region replaced; "
            f"reviewer {reviewer_identity} recorded on the {review_kind} channel."
        ),
        [str(raw_destination), str(block_destination), str(qa_path), str(review_destination)],
        (
            f"Raw SHA-256 {sha256(raw_destination)}; judgement SHA-256 {sha256(block_destination)}; "
            f"context digest {review_record['context_digest']}"
        ),
        state["next"],
    )
    print("Done. Independent review evidence is recorded without changing its judgement.")
    print("Next: present the combined evidence for the human G3 decision.")
    return 0
    append_worker_telemetry(
        run_root,
        "worker-review",
        task_id=worker.get("task_id", "unknown"),
        worker_role=worker.get("worker_role", "unknown"),
        provider=worker.get("provider", "unknown"),
        model=worker.get("model", "unknown"),
        attempt=worker.get("attempt", 0),
        validation_attempts=worker.get("validation_attempts", 0),
        files_changed=[],
        tests_result="not applicable",
        escalation_count=worker.get("escalation_count", 0),
        review_outcome=worker["review_outcome"],
        accepted="unknown",
        usage="unknown",
        cost="unknown",
    )
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
    write_state(run_root, state)
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


def approve_gate(args: argparse.Namespace) -> int:
    """Record a human gate decision as an engine approval bound to the current revision.

    This is the only path that satisfies a gate. It is an operator command: it is
    not part of the worker's packet contract, and the runtime never grants a gate
    on the worker's behalf. The record binds the gate to the operation, the
    subject, the current revision fingerprint and the recorded identity, so an
    approval for one revision, target or operation cannot authorize another.
    """
    run_root, state = resolve_and_load(args)
    entry, packet = current_packet(state, allow_project_drift=True)
    gate = str(getattr(args, "gate", "") or "").upper()
    if gate not in CONTRACTS.GATE_SUBJECT_TYPES:
        raise RuntimeError_(
            f"{gate or 'that gate'} is not enforced by the orchestration core; "
            "G4 ship and G5 publish stay human/operator actions outside the engine"
        )
    identity = str(getattr(args, "identity", "") or "").strip()
    note = str(getattr(args, "note", "") or "").strip()
    project = Path(state["project"])
    try:
        if gate == "G1":
            subject = POLICY.design_direction_subject(project)
        elif gate == "G2":
            subject = POLICY.handoff_subject(project)
        else:
            subject = POLICY.review_subject(state, packet)
            if subject is None:
                raise RuntimeError_(
                    "G3 approves a recorded review of the current revision, and no review record exists yet; "
                    "ingest the independent review first"
                )
        record = POLICY.approve(
            state, gate, subject, identity, note, stage=entry["stage"], packet_id=entry["id"],
        )
    except CONTRACTS.EngineError as exc:
        raise RuntimeError_(str(exc)) from exc
    mirror_gate_written = mirror_agents_gate(project, POLICY.highest_gate(state))
    emit_event(
        run_root, "approval_recorded", state=state, task_id=str(record.get("packet_id", entry["id"])),
        stage=entry["stage"], gate=gate, approval=str(record.get("approval_id", "")),
        identity=str(record.get("identity", "")), channel=str(record.get("channel", "")),
        revision=str(record.get("revision_hash", ""))[:12],
    )
    state["updated_at"] = now()
    state["next"] = (
        f"Continue from the {gate}-approved boundary."
        if gate != "G1"
        else "Prepare the implementation plan from the approved direction."
    )
    write_state(run_root, state)
    append_worker_telemetry(
        run_root,
        "gate-approval",
        task_id=str(record.get("packet_id", "unknown")),
        provider=record["identity"],
        model=record["gate"],
        tests_result="not applicable",
        review_outcome=str(record.get("subject_type", "unknown")),
        accepted="unknown",
        usage="unknown",
        cost="unknown",
        failure_reason="none",
    )
    append_log(
        run_root,
        f"{gate} approval recorded",
        "A gate is a human decision; the engine records it as a bound approval instead of reading a document field.",
        (
            f"{record['approval_id']}: {gate} on {subject.subject_id} "
            f"at revision {subject.revision_hash[:12]} by {record['identity']} on channel {record['channel']}."
        ),
        [str(run_root / STATE_NAME)],
        f"Subject detail: {subject.detail or 'not recorded'}; document gate fields remain human-readable mirrors.",
        state["next"],
    )
    print(f"Recorded. {gate} approval {record['approval_id']} is bound to this revision.")
    if gate == "G1" and not mirror_gate_written:
        print("Note: AGENTS.md already recorded that gate; the mirror was left unchanged.")
    print(f"From you: nothing right now. Next: {state['next']}")
    return 0


def mirror_agents_gate(project: Path, gate: str | None) -> bool:
    """Write the human-readable gate mirror into AGENTS.md. Never an enforcement input.

    DESIGN.md is deliberately not rewritten: it is a hash-anchored artifact of the
    recorded direction work, and editing it after the fact would invalidate the
    creative evidence the engine just verified.
    """
    if not gate:
        return False
    path = project / "AGENTS.md"
    if not path.is_file():
        return False
    text = read(path)
    pattern = r"(?m)^(\|\s*\*\*Last gate passed\*\*\s*\|\s*)`?[^|`]+`?(\s*\|)\s*$"
    if not re.search(pattern, text):
        return False
    updated = re.sub(pattern, rf"\g<1>`{gate}`\g<2>", text, count=1)
    if updated == text:
        return False
    path.write_text(updated, encoding="utf-8")
    return True


def record_acceptance(args: argparse.Namespace) -> int:
    """Record the human acceptance outcome without silently granting a gate."""
    run_root, state = resolve_and_load(args)
    entry, packet = current_packet(state, allow_project_drift=True)
    if entry["stage"] != "S5":
        raise RuntimeError_("Acceptance belongs to the current independent-review boundary")
    review_path = packet / "evidence" / "review-judgement.md"
    if not review_path.is_file():
        raise RuntimeError_("Acceptance requires recorded independent review evidence")
    outcome = args.outcome.lower()
    if outcome not in ("accepted", "rejected"):
        raise RuntimeError_("Acceptance outcome must be accepted or rejected")
    review_record = REVIEWS.current_review(state, packet_id=entry["id"])
    consumed_approval = ""
    if outcome == "accepted":
        subject = POLICY.review_subject(state, packet)
        if review_record is None:
            raise RuntimeError_(
                "Acceptance requires a recorded review bound to this revision; "
                "ingest the independent review with --reviewer-identity first"
            )
        operation = f"acceptance:{entry['id']}:{subject.revision_hash[:12]}"
        satisfied, reason = POLICY.gate_satisfied(
            state, "G3", subject, consume=operation, operation=operation
        )
        if not satisfied:
            raise RuntimeError_(
                "Accepted requires the human G3 decision to already be recorded: " + reason
            )
        latest = POLICY.approvals(state, "G3")[-1] if POLICY.approvals(state, "G3") else {}
        consumed_approval = str(latest.get("approval_id", ""))
    else:
        # AR-202 approval policy: a rejection is a human decision recorded on its
        # own terms. It is not an acceptance, so it does not consume a G3
        # approval and it can never be reused as future acceptance authority.
        notes = state.setdefault("notes", [])
        notes.append({
            "recorded_at": now(),
            "kind": "recovery",
            "summary": f"Human rejected the reviewed revision at packet {entry['id']}.",
            "evidence_state": "verified",
            "approval_effect": "none: a rejection is not an acceptance and consumes no G3 approval",
        })
    worker = worker_state(state)
    STATEMACHINE.apply_transition(
        state,
        CONTRACTS.TransitionRequest(
            kind="worker-lifecycle",
            to="accepted" if outcome == "accepted" else "rejected",
            reason=f"Human acceptance outcome: {outcome}",
            evidence=(str(review_path),),
            fields={
                "acceptance_state": "ACCEPTED" if outcome == "accepted" else "REJECTED",
                "acceptance_evidence": str(review_path),
            },
            actor="human",
            operation=f"acceptance:{entry['id']}",
        ),
        permitted=True,
    )
    state["updated_at"] = now()
    state["next"] = (
        "Continue with the human-authorised release workflow."
        if outcome == "accepted"
        else "Record the rejection reason and prepare a bounded corrective implementation loop."
    )
    append_worker_telemetry(
        run_root,
        "worker-acceptance",
        task_id=worker.get("task_id", "unknown"),
        worker_role=worker.get("worker_role", "unknown"),
        provider=worker.get("provider", "unknown"),
        model=worker.get("model", "unknown"),
        attempt=worker.get("attempt", 0),
        validation_attempts=worker.get("validation_attempts", 0),
        files_changed=[],
        tests_result="not applicable",
        escalation_count=worker.get("escalation_count", 0),
        review_outcome=worker.get("review_outcome", "unknown"),
        accepted=outcome,
        usage="unknown",
        cost="unknown",
        failure_reason="none" if outcome == "accepted" else "human rejected the reviewed result",
    )
    if outcome == "accepted" and consumed_approval:
        emit_event(
            run_root, "approval_consumed", state=state, task_id=entry["id"], stage="S5",
            approval=consumed_approval, gate="G3", operation=f"acceptance:{entry['id']}",
        )
    elif outcome == "rejected":
        emit_event(
            run_root, "approval_recorded", state=state, task_id=entry["id"], stage="S5",
            gate="G3", decision="rejected",
            note="rejection recorded separately; no G3 approval was consumed",
        )
    write_state(run_root, state)
    append_log(
        run_root,
        "Worker result acceptance recorded",
        "Acceptance is a separate human decision after implementation, validation, and review.",
        f"{outcome}: worker lifecycle is {worker['lifecycle']}.",
        [str(review_path), str(run_root / TELEMETRY_NAME)],
        "No gate was granted or inferred by this command.",
        state["next"],
    )
    print(f"Worker result: {worker['acceptance_state']}")
    print(f"Next: {state['next']}")
    return 0


def creative_plan(args: argparse.Namespace) -> int:
    """Create the hidden skill/research plan after S1 has produced the brief."""
    run_root, state = resolve_and_load(args)
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
    write_state(run_root, state)
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
    run_root, state = resolve_and_load(args)
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
    write_state(run_root, state)
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
    run_root, state = resolve_and_load(args)
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
    run_root, state = resolve_and_load(args)
    project = Path(state["project"])
    if OPERATIONS.ledger_path(project).exists():
        raise RuntimeError_("Creative operations planning is already recorded; do not replace its evidence")
    try:
        ledger = OPERATIONS.create_ledger(project)
        destination = OPERATIONS.save_ledger(project, ledger)
    except OPERATIONS.OperationsError as exc:
        raise RuntimeError_(str(exc)) from exc
    state["updated_at"] = now()
    write_state(run_root, state)
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
    run_root, state = resolve_and_load(args)
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
    write_state(run_root, state)
    append_log(
        run_root,
        "Creative operations evidence recorded",
        "Implementation, rendered evidence, drift, creative judgement, social strategy, user-provided results, and learning must remain separate claims.",
        (
            f"{result['implemented']}/{result['requirements']} requirement(s) implemented; "
            f"{result['observed']} observed/verified visual result(s); "
            f"{result['creative_reviews']} actionable creative review(s); "
            f"{result['social_strategies']} optional social strategy record(s); "
            f"{result['social_results']} user-provided result(s); "
            f"{result['social_learnings']} bounded learning record(s)."
        ),
        [str(source), str(destination)],
        f"Input SHA-256 {sha256(source)}; ledger validation passed.",
        state.get("next", "Continue from the current verified boundary."),
    )
    print("Done. I recorded the post-G1 evidence without promoting assumptions to observations.")
    print("From you: nothing right now.")
    return 0


def operations_check(args: argparse.Namespace) -> int:
    run_root, state = resolve_and_load(args)
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


# ---------------------------------------------------- AR-202D design intelligence


def load_design_input(path_value) -> dict | list:
    """Read one design-workflow input file: an event list or a declaration document."""
    source = Path(str(path_value)).resolve()
    if not source.is_file() or source.stat().st_size == 0:
        raise RuntimeError_(f"Design input is missing or empty: {source}")
    try:
        return json.loads(read(source))
    except json.JSONDecodeError as exc:
        raise RuntimeError_(f"Design input is not valid JSON: {exc}") from exc


def design_fixture(value: dict | None) -> dict:
    """The declared deterministic adapters an operator may point design work at.

    Nothing here reaches the network. The only adapters that can *produce*
    evidence are the offline fixture, the project's own reference directory and a
    declared observer; every other adapter reports its own unavailability.
    """
    value = value if isinstance(value, dict) else {}
    return {
        "references": value.get("references_fixture") if isinstance(value.get("references_fixture"), dict) else None,
        "capture": value.get("capture_fixture") if isinstance(value.get("capture_fixture"), dict) else None,
        "declared_observer": value.get("declared_observer") if isinstance(value.get("declared_observer"), dict) else None,
        "fixture_root": str(value.get("fixture_root", "") or ""),
    }


def design_adapters(state: dict, project: Path, fixture: dict) -> tuple[dict, dict]:
    """Build the declared reference and capture adapters for this run."""
    fixture_root = Path(fixture["fixture_root"]) if fixture.get("fixture_root") else None
    run_root = Path(state.get("run_root", "") or project)
    reference_adapters = REFERENCES.default_adapters(
        project, fixture=fixture.get("references"), fixture_root=fixture_root,
    )
    capture_adapters = RENDER.default_adapters(
        run_root,
        fixture=fixture.get("capture"),
        declared_observer=fixture.get("declared_observer"),
    )
    return reference_adapters, capture_adapters


def design_revision_hash(state: dict, packet: Path | None) -> str:
    """The revision a design record binds to: the boundary's own task revision."""
    return str((EXECUTION.task_revision(state, packet) or {}).get("revision_hash", ""))


def design_capture_adapter(capture_adapters: dict, adapter_id: str):
    adapter = capture_adapters.get(str(adapter_id))
    if adapter is None:
        raise RuntimeError_(
            f"no capture adapter named {adapter_id!r} is configured here; available: "
            + (", ".join(sorted(capture_adapters)) or "none")
        )
    available, reason = adapter.available()
    if not available:
        raise RuntimeError_(
            f"capture adapter {adapter_id!r} reports itself unavailable: {reason or 'no reason recorded'}. "
            "A capability that is not configured cannot produce rendered evidence."
        )
    return adapter


def design_plan_command(args: argparse.Namespace) -> int:
    """Characterise one task for design, select the pipeline, and route its evidence needs."""
    run_root, state = resolve_and_load(args)
    entry, packet = current_packet(state, allow_project_drift=True)
    project = Path(state["project"])
    state["run_root"] = str(run_root)
    payload = load_design_input(args.input) if getattr(args, "input", None) else {}
    fixture = design_fixture(payload)
    reference_adapters, capture_adapters = design_adapters(state, project, fixture)
    stage = str(getattr(args, "stage", "") or entry["stage"])
    request = str(getattr(args, "request", "") or state.get("request", "") or "")
    characterisation = DESIGN.characterize(
        state, project=project, stage=stage, request=request, task_id=entry["id"],
        transport=TRANSPORT, characterisation=ROUTING.latest(state, "characterisations"),
        reference_adapters=reference_adapters, capture_adapters=capture_adapters,
        declared=payload.get("declared"),
    )
    DESIGN.record_characterisation(state, characterisation)
    plan = DESIGN.plan(state, characterisation, task_id=entry["id"])
    characteristics = characterisation["characteristics"]
    emit_event(
        run_root, "design_task_characterized", state=state, task_id=entry["id"], stage=stage,
        characterisation=str(characterisation["characterisation_id"]),
        depth=str(plan.get("depth", "")),
        design=str(characteristics["design_task"]["value"]),
        reference_research=str(characteristics["reference_research"]["value"]),
        rendered_qa=str(characteristics["rendered_qa"]["value"]),
    )
    emit_event(
        run_root, "design_plan_selected", state=state, task_id=entry["id"], stage=stage,
        plan=str(plan.get("plan_id", "")), depth=str(plan.get("depth", "")),
        skipped=",".join(
            name for name, row in (plan.get("stages") or {}).items() if row.get("selection") == "SKIPPED"
        ),
    )
    evidence_route = ROUTING.route_evidence(
        state, stage=stage, design_characterisation=characterisation,
        reference_adapters=reference_adapters, capture_adapters=capture_adapters,
        task_id=entry["id"],
        evidence_policy=str(getattr(args, "evidence_policy", "") or "declared"),
    )
    ROUTING.record(state, evidence_route)
    emit_event(
        run_root, "route_selected", state=state, task_id=entry["id"], stage=stage,
        decision=str(evidence_route.get("decision_id", "")),
        route_kind="design-evidence", status=str(evidence_route.get("status", "")),
        rule=str(evidence_route.get("rule", "")), reason=str(evidence_route.get("reason", "")),
    )
    state["updated_at"] = now()
    blocked = evidence_route.get("status") != "selected"
    state["next"] = (
        "Record the design evidence the plan requires, then implement."
        if not blocked
        else "Reference or capture capability is unavailable; record the blocker instead of the evidence."
    )
    write_state(run_root, state)
    if getattr(args, "json", False):
        print(json.dumps({
            "characterisation": characterisation, "plan": plan, "evidence_route": evidence_route,
        }, indent=2, sort_keys=True, default=str))
        return 0 if not blocked else 2
    print(
        f"Design task: {characteristics['design_task']['value']} (depth {plan.get('depth')}); "
        f"visual {characteristics['visual_design']['value']}, "
        f"reference research {characteristics['reference_research']['value']}, "
        f"rendered QA {characteristics['rendered_qa']['value']}."
    )
    selected = [
        f"{name}:{row['selection']}" for name, row in (plan.get("stages") or {}).items()
        if row.get("selection") != "SKIPPED"
    ]
    print("Pipeline: " + (", ".join(selected) or "no design stages selected"))
    if blocked:
        print("Evidence route blocked: " + str(evidence_route.get("reason")))
        print("Next: record the blocker honestly; do not describe evidence that was never produced.")
        return 2
    print("Next: record the evidence this plan requires before implementing.")
    print("From you: nothing right now.")
    return 0


def design_capture_event(
    state: dict, entry: dict, event: dict, run_root: Path, capture_adapters: dict, revision: str,
) -> dict:
    """Run one declared capture adapter and record the artifact as rendered evidence."""
    spec = dict(event.get("capture") or {})
    if not spec:
        raise RuntimeError_("a rendered-evidence event must declare the capture it performed")
    adapter_id = str(spec.get("adapter", "offline-fixture") or "offline-fixture")
    adapter = design_capture_adapter(capture_adapters, adapter_id)
    kind = str(spec.get("kind", "screenshot") or "screenshot")
    if kind not in adapter.capabilities():
        raise RuntimeError_(
            f"capture adapter {adapter_id!r} does not declare the {kind!r} capability; "
            "evidence cannot come from a capability that was never declared"
        )
    capture_execution, execution_problems = execution_for_task(
        state, task_id=entry["id"], role="validator",
        adapter=f"scripts/ariadne.py:design-capture:{adapter_id}",
        invocation=f"record-design capture {kind}",
        requested={"provider": adapter_id, "model": kind},
        packet=None,
        reason=f"design capture for {entry['id']}",
        reuse=False,
    )
    if execution_problems:
        raise RuntimeError_("design capture execution rejected: " + "; ".join(execution_problems))
    artifact = adapter.capture(spec)
    extra = dict(artifact.extra)
    extra["capture_spec"] = spec
    record_value = RENDER.record(
        state,
        task_id=entry["id"],
        revision_hash=str(event.get("revision_hash", "") or revision),
        artifact=RENDER.CaptureArtifact(
            kind=artifact.kind, path=artifact.path, sha256=artifact.sha256,
            viewport=artifact.viewport, environment=artifact.environment,
            method=artifact.method, observation=artifact.observation, extra=extra,
        ),
        adapter=adapter_id,
        adapter_available=True,
        capture_execution=str(capture_execution.get("execution_id", "")),
        requirement_id=str(event.get("requirement_id", "")),
        direction_id=str(event.get("direction_id", "")),
    )
    emit_event(
        run_root, "rendered_evidence_recorded", state=state, task_id=entry["id"],
        stage=entry["stage"], evidence=str(record_value["evidence_id"]),
        evidence_kind=kind, evidence_state=str(record_value["state"]), adapter=adapter_id,
        viewport=str((record_value.get("viewport") or {}).get("width", "")),
        execution=str(capture_execution.get("execution_id", "")),
    )
    return record_value


def design_implementing_task(state: dict, entry: dict) -> str:
    """The task whose implementation a design critique reviews.

    Never guesses from a missing packet: the recorded worker row wins, then the
    most recent packet for this stage, then the current task itself.
    """
    worker_task = str((state.get("worker") or {}).get("task_id", "") or "")
    packets = [item for item in (state.get("packets") or []) if isinstance(item, dict)]
    if worker_task and any(str(item.get("id", "")) == worker_task for item in packets):
        return worker_task
    for stage in ("S4B", str(entry.get("stage", ""))):
        rows = [str(item.get("id", "")) for item in packets if str(item.get("stage", "")) == stage]
        if rows:
            return rows[-1]
    return str(entry.get("id", ""))


def design_review_event(
    state: dict, entry: dict, event: dict, run_root: Path, revision: str = "",
) -> dict:
    """Ingest an independent critique bound to engine-created executions."""
    reviewer_identity = str(event.get("reviewer_identity", "") or "").strip()
    implementing_task = design_implementing_task(state, entry)
    implementer = find_implementer_execution(state, task_id=implementing_task)
    if implementer is None:
        raise RuntimeError_(
            "design review rejected: the reviewed implementation has no engine-created execution, "
            "so review independence cannot be established (DESIGN_REVIEW_FAILURE). A critique binds "
            "to an implementer execution and a separate reviewer execution; it cannot be recorded "
            "before the implementation it judges exists."
        )
    reviewer_execution, execution_problems = execution_for_task(
        state, task_id=entry["id"], role="reviewer",
        adapter="scripts/ariadne.py:record-design:review",
        invocation="record-design review",
        requested={"provider": reviewer_identity, "model": "design-critique"},
        packet=None,
        reason=f"independent design critique of {implementing_task}",
        reuse=False,
        parent=str(implementer["execution_id"]),
    )
    if execution_problems:
        raise RuntimeError_("design review execution rejected: " + "; ".join(execution_problems))
    direction = DESIGN.direction(state, str(event.get("direction_id", ""))) or DESIGN.active_direction(
        state, task_id=entry["id"],
    )
    if not direction:
        raise RuntimeError_(
            "a design critique needs the approved direction it judges against; none is recorded"
        )
    emit_event(
        run_root, "design_review_started", state=state, task_id=entry["id"], stage=entry["stage"],
        direction=str(direction.get("direction_id", "")),
        reviewer_execution=str(reviewer_execution.get("execution_id", "")),
        implementing_execution=str(implementer["execution_id"]),
    )
    record_value = CRITIQUE.build_review(
        state,
        task_id=entry["id"],
        direction_id=str(direction.get("direction_id", "")),
        findings=event.get("findings") or [],
        reviewer_identity=reviewer_identity,
        reviewer_execution=str(reviewer_execution.get("execution_id", "")),
        implementing_execution=str(implementer["execution_id"]),
        requirement_ids=event.get("requirement_ids") or [],
        evidence_ids=event.get("evidence_ids") or [],
        outcome=str(event.get("outcome", "passed") or "passed"),
        differential=str(event.get("differential", "")),
        qa_records=event.get("qa") or {},
        reviewer_role=str(event.get("reviewer_role", "independent-reviewer")),
        revision_hash=str(event.get("revision_hash", "") or revision),
    )
    emit_event(
        run_root, "review_recorded", state=state, task_id=entry["id"], stage=entry["stage"],
        review=str(record_value["review_id"]), outcome=str(record_value["outcome"]),
        findings=len(record_value.get("findings") or []),
        direction_revision=str(record_value.get("direction_revision", "")),
    )
    for finding in record_value.get("findings") or []:
        emit_event(
            run_root, "design_finding_recorded", state=state, task_id=entry["id"], stage=entry["stage"],
            finding=str(finding.get("finding_id")), dimension=str(finding.get("dimension")),
            severity=str(finding.get("severity")), finding_state=str(finding.get("state", "open")),
        )
    return record_value


def _design_reference_event(
    state: dict, entry: dict, event: dict, kind: str, project: Path, run_root: Path,
) -> dict:
    if kind in ("reference", "reference-discovered"):
        record_value = REFERENCES.register(
            state,
            source=str(event.get("source", "")),
            locator=str(event.get("locator", "")),
            title=str(event.get("title", "") or event.get("source", "")),
            source_type=str(event.get("source_type", "local-file")),
            adapter=str(event.get("adapter", "")),
            task_id=entry["id"], query=str(event.get("query", "")),
        )
        emit_event(
            run_root, "reference_found", state=state, task_id=entry["id"], stage=entry["stage"],
            reference=str(record_value["reference_id"]), source=str(record_value["source"]),
            source_type=str(record_value["source_type"]), adapter=str(record_value["adapter"]),
        )
        return record_value
    if kind == "reference-accessible":
        record_value = REFERENCES.mark_accessible(
            state, str(event.get("reference_id", "")),
            content_sha256=str(event.get("content_sha256", "")),
            size=int(event.get("size", 0) or 0),
            mime=str(event.get("mime", "")),
            licence_note=str(event.get("licence_note", "")),
            adapter=str(event.get("adapter", "")),
        )
        emit_event(
            run_root, "reference_accessed", state=state, task_id=entry["id"], stage=entry["stage"],
            reference=str(record_value["reference_id"]),
            digest=str((record_value.get("content") or {}).get("sha256", ""))[:12],
        )
        return record_value
    if kind == "reference-inaccessible":
        record_value = REFERENCES.mark_inaccessible(
            state, str(event.get("reference_id", "")), blocker=str(event.get("blocker", "")),
        )
        emit_event(
            run_root, "reference_inspected", state=state, task_id=entry["id"], stage=entry["stage"],
            reference=str(record_value["reference_id"]), inspection_outcome="inaccessible",
            blocker=str(event.get("blocker", "")),
        )
        return record_value
    if kind == "reference-inspection":
        record_value = REFERENCES.inspect(
            state, str(event.get("reference_id", "")),
            inspection_type=str(event.get("inspection_type", "")),
            observations=[str(item) for item in (event.get("observations") or [])],
            evidence_path=Path(str(event.get("evidence_path", ""))),
            project=project,
            claim_kinds=[str(item) for item in (event.get("claim_kinds") or [])],
            viewport=event.get("viewport") if isinstance(event.get("viewport"), dict) else None,
            mechanisms=[str(item) for item in (event.get("mechanisms") or [])],
        )
        latest = (record_value.get("inspections") or [{}])[-1]
        emit_event(
            run_root, "reference_inspected", state=state, task_id=entry["id"], stage=entry["stage"],
            reference=str(record_value["reference_id"]), inspection_type=str(latest.get("type", "")),
            observations=len(latest.get("observations") or []),
            artifact=str((latest.get("evidence") or {}).get("sha256", ""))[:12],
        )
        return record_value
    if kind == "reference-analysis":
        record_value = REFERENCES.analyse(
            state, str(event.get("reference_id", "")), findings=event.get("findings") or [],
        )
        emit_event(
            run_root, "reference_analysed", state=state, task_id=entry["id"], stage=entry["stage"],
            reference=str(record_value["reference_id"]),
            findings=len(((record_value.get("analysis") or {}).get("findings")) or []),
        )
        return record_value
    if kind == "reference-used":
        record_value = REFERENCES.mark_used(
            state, str(event.get("reference_id", "")),
            decision=str(event.get("decision", "")), principle=str(event.get("principle", "")),
            artifact_path=Path(str(event.get("artifact_path", ""))),
            artifact_anchor=str(event.get("artifact_anchor", "")),
            requirement_id=str(event.get("requirement_id", "")),
            direction_id=str(event.get("direction_id", "")),
            claim_kind=str(event.get("claim_kind", "")),
        )
        emit_event(
            run_root, "reference_used", state=state, task_id=entry["id"], stage=entry["stage"],
            reference=str(record_value["reference_id"]), decision=str(event.get("decision", "")),
        )
        return record_value
    raise RuntimeError_(f"unsupported design reference event: {kind!r}")


REFERENCE_EVENT_TYPES = (
    "reference", "reference-discovered", "reference-accessible", "reference-inaccessible",
    "reference-inspection", "reference-analysis", "reference-used",
)


def record_design(args: argparse.Namespace) -> int:
    """Apply one batch of design-intelligence events through the engine's own enforcement."""
    run_root, state = resolve_and_load(args)
    entry, packet = current_packet(state, allow_project_drift=True)
    project = Path(state["project"])
    state["run_root"] = str(run_root)
    value = load_design_input(args.input)
    events = value.get("events") if isinstance(value, dict) else value
    if isinstance(events, dict):
        events = [events]
    if not isinstance(events, list) or not events:
        raise RuntimeError_("record-design needs at least one event")
    fixture = design_fixture(value if isinstance(value, dict) else {})
    reference_adapters, capture_adapters = design_adapters(state, project, fixture)
    revision = design_revision_hash(state, packet)
    applied = 0
    for event in events:
        if not isinstance(event, dict):
            raise RuntimeError_("every design event must be an object")
        kind = str(event.get("type", "") or "")
        if kind in REFERENCE_EVENT_TYPES:
            _design_reference_event(state, entry, event, kind, project, run_root)
        elif kind == "component":
            record_value = COMPONENTS.evaluate(
                state,
                need=str(event.get("need", "")), task_id=entry["id"],
                rung=str(event.get("rung", "")), name=str(event.get("name", "")),
                capability=str(event.get("capability", "")),
                alternatives=event.get("alternatives") or [],
                existing_equivalent=event.get("existing_equivalent") or {},
                findings=event.get("findings") or {},
                approved_dependencies=[str(item) for item in (event.get("approved_dependencies") or [])],
                registry=COMPONENTS.default_registry(ROOT),
                registry_entry=str(event.get("registry_entry", "")),
                project_paths=[str(item) for item in (event.get("project_paths") or [])],
                approval_id=str(event.get("approval_id", "")),
                note=str(event.get("note", "")),
            )
            emit_event(
                run_root, "component_candidate_evaluated", state=state, task_id=entry["id"], stage=entry["stage"],
                candidate=str(record_value["candidate_id"]),
                name=str((record_value.get("candidate") or {}).get("name", "")),
                rung=str(record_value["rung"]), decision=str(record_value["decision"]),
                approval_required=bool(record_value["approval_required"]),
            )
        elif kind == "direction":
            record_value = DESIGN.create_direction(
                state,
                task_id=entry["id"],
                goal=str(event.get("goal", "")),
                scope=str(event.get("scope", "")),
                product_context=event.get("product_context") or [],
                key_hierarchy=event.get("key_hierarchy") or [],
                interaction_principles=event.get("interaction_principles") or [],
                visual_principles=event.get("visual_principles") or [],
                content_principles=event.get("content_principles") or [],
                constraints=event.get("constraints") or [],
                existing_system=event.get("existing_system") or [],
                reference_findings_adopted=event.get("reference_findings_adopted") or [],
                findings_rejected=event.get("findings_rejected") or [],
                accessibility_requirements=event.get("accessibility_requirements") or [],
                responsive_requirements=event.get("responsive_requirements") or [],
                approved_deviations=event.get("approved_deviations") or [],
                revision_hash=revision,
            )
            emit_event(
                run_root, "design_direction_created", state=state, task_id=entry["id"], stage=entry["stage"],
                direction=str(record_value["direction_id"]), direction_status=str(record_value["status"]),
                revision=str(record_value["revision_hash"])[:12],
            )
        elif kind == "requirement":
            record_value = DESIGN.record_requirement(
                state,
                requirement_id=str(event.get("requirement_id", "")),
                evidence_kind=str(event.get("evidence_kind", "")),
                task_id=entry["id"],
                decision=event.get("decision") or {},
                implementation=event.get("implementation") or {},
                evidence_ids=event.get("evidence_ids") or [],
                state_name=str(event.get("state_name", "")),
                rejection_reason=str(event.get("rejection_reason", "")),
                viewport=str(event.get("viewport", "")),
                revision_hash=str(event.get("revision_hash", "") or revision),
                note=str(event.get("note", "")),
            )
            emit_event(
                run_root, "design_requirement_recorded", state=state, task_id=entry["id"], stage=entry["stage"],
                record=str(record_value["record_id"]), requirement=str(record_value["requirement_id"]),
                requirement_state=str(record_value["state"]), evidence_kind=str(record_value["evidence_kind"]),
            )
        elif kind == "source-suggests":
            record_value = RENDER.record_source_suggests(
                state, task_id=entry["id"],
                revision_hash=str(event.get("revision_hash", "") or revision),
                source_path=Path(str(event.get("source_path", ""))),
                source_anchor=str(event.get("source_anchor", "")),
                observation=str(event.get("observation", "")),
                requirement_id=str(event.get("requirement_id", "")),
            )
            emit_event(
                run_root, "rendered_evidence_recorded", state=state, task_id=entry["id"], stage=entry["stage"],
                evidence=str(record_value["evidence_id"]), evidence_kind="source",
                evidence_state="SOURCE_SUGGESTS",
            )
        elif kind == "rendered-evidence":
            design_capture_event(state, entry, event, run_root, capture_adapters, revision)
        elif kind == "rendered-observe":
            record_value = RENDER.observe(
                state, str(event.get("evidence_id", "")),
                artifact={
                    "path": str(event.get("artifact_path", "")),
                    "sha256": str(event.get("artifact_sha256", "")),
                },
                observation=str(event.get("observation", "")),
                kind=str(event.get("kind", "interaction") or "interaction"),
            )
            emit_event(
                run_root, "rendered_evidence_recorded", state=state, task_id=entry["id"], stage=entry["stage"],
                evidence=str(record_value["evidence_id"]), evidence_kind=str(event.get("kind", "interaction")),
                evidence_state="OBSERVED",
            )
        elif kind == "rendered-verify":
            evidence_id = str(event.get("evidence_id", ""))
            original = RENDER.by_id(state, evidence_id)
            if original is None:
                raise RuntimeError_(f"no rendered evidence matches {evidence_id!r}")
            spec = dict(((original.get("extra") or {}).get("capture_spec")) or {})
            if not spec:
                raise RuntimeError_(
                    "this rendered evidence records no capture spec, so it cannot be re-produced by an "
                    "independent execution; verification is refused rather than declared"
                )
            adapter = design_capture_adapter(capture_adapters, str(original.get("adapter", "")))
            verification_execution, execution_problems = execution_for_task(
                state, task_id=entry["id"], role="validator",
                adapter=f"scripts/ariadne.py:design-verify:{adapter.id}",
                invocation="record-design verify",
                requested={"provider": adapter.id, "model": "reproduction"},
                packet=None,
                reason=f"independent re-production of {evidence_id}",
                reuse=False,
            )
            if execution_problems:
                raise RuntimeError_("design verification execution rejected: " + "; ".join(execution_problems))
            reproduced = adapter.capture(spec)
            record_value = RENDER.verify(
                state, evidence_id,
                verification_execution=str(verification_execution.get("execution_id", "")),
                reproduced_sha256=reproduced.sha256,
                method=f"independent re-capture by {adapter.id}",
                tolerance=str(event.get("tolerance", "exact") or "exact"),
            )
            emit_event(
                run_root, "rendered_evidence_verified", state=state, task_id=entry["id"], stage=entry["stage"],
                evidence=str(record_value["evidence_id"]),
                execution=str(verification_execution.get("execution_id", "")),
                digest=str(reproduced.sha256)[:12],
            )
        elif kind == "rendered-unverified":
            record_value = RENDER.mark_unverified(
                state, task_id=entry["id"],
                revision_hash=str(event.get("revision_hash", "") or revision),
                requirement_id=str(event.get("requirement_id", "")),
                blocker=str(event.get("blocker", "")),
                viewport=event.get("viewport") if isinstance(event.get("viewport"), dict) else None,
            )
            emit_event(
                run_root, "rendered_evidence_recorded", state=state, task_id=entry["id"], stage=entry["stage"],
                evidence=str(record_value["evidence_id"]), evidence_state="UNVERIFIED",
                blocker=str(event.get("blocker", "")),
            )
        elif kind == "review":
            design_review_event(state, entry, event, run_root, revision)
        elif kind == "refinement":
            record_value = CRITIQUE.propose_refinement(
                state, str(event.get("finding_id", "")), task_id=entry["id"],
                artifact=str(event.get("artifact", "")),
                intended_change=str(event.get("intended_change", "")),
                permitted_scope=event.get("permitted_scope") or [],
                expected_evidence=event.get("expected_evidence") or [],
                regression_checks=event.get("regression_checks") or [],
                revision_hash=str(event.get("revision_hash", "") or revision),
            )
            emit_event(
                run_root, "refinement_started", state=state, task_id=entry["id"], stage=entry["stage"],
                refinement=str(record_value["refinement_id"]), finding=str(record_value["finding_id"]),
                scope=",".join(str(item) for item in record_value["permitted_scope"]),
            )
        elif kind == "refinement-result":
            record_value = CRITIQUE.record_refinement(
                state, str(event.get("refinement_id", "")),
                applied=bool(event.get("applied", True)),
                changed_artifacts=event.get("changed_artifacts") or [],
                revalidated=event.get("revalidated") or {},
                recaptured=event.get("recaptured") or [],
                regressions=event.get("regressions") or [],
                notes=str(event.get("notes", "")),
            )
            CRITIQUE.resolve_findings(
                state, str(event.get("refinement_id", "")),
                resolved=event.get("resolved") or [],
                still_open=event.get("still_open") or [],
            )
            emit_event(
                run_root, "refinement_completed", state=state, task_id=entry["id"], stage=entry["stage"],
                refinement=str(record_value["refinement_id"]), refinement_state=str(record_value["state"]),
                regressions=len(record_value.get("regressions") or []),
                resolved=bool(record_value.get("resolved")),
            )
        else:
            raise RuntimeError_(f"unsupported design event type: {kind!r}")
        applied += 1
    state["updated_at"] = now()
    state["next"] = "Review the recorded design evidence for gaps before continuing."
    write_state(run_root, state)
    print(f"Recorded {applied} design event(s).")
    print("Evidence states were enforced: a claim the recorded evidence cannot support was refused.")
    print("From you: nothing right now.")
    return 0


def design_check_command(args: argparse.Namespace) -> int:
    run_root, state = resolve_and_load(args)
    project = Path(state["project"])
    report = DESIGN.report(state)
    problems = list(report["problems"])
    requirement = POLICY.design_evidence_requirement(state, project, "S5")
    if requirement.get("required") and requirement.get("state") != "satisfied":
        problems.append(str(requirement.get("detail", "")))
    payload = {
        "status": "blocked" if problems else "tracked",
        "project": str(project),
        "report": report,
        "problems": list(dict.fromkeys(problems)),
    }
    if getattr(args, "json", False):
        print(json.dumps(payload, indent=2, sort_keys=True, default=str))
        return 0 if not problems else 2
    if problems:
        print("I found design-evidence gaps:")
        for problem in payload["problems"]:
            print(f"- {problem}")
        print("Next: record the missing evidence, or record the blocker honestly.")
        return 2
    print(
        "Tracked. References, component choices, direction, requirements, rendered evidence and "
        "critique remain traceable."
    )
    print("From you: nothing right now.")
    return 0


def design_report_command(args: argparse.Namespace) -> int:
    run_root, state = resolve_and_load(args)
    report = DESIGN.report(state)
    if getattr(args, "json", False):
        print(json.dumps(report, indent=2, sort_keys=True, default=str))
        return 0
    measurements = report["measurements"]
    references = measurements["references"]
    print(
        f"Design depth {report['depth'] or 'not characterised'}; "
        f"references found {references['found']}, inspected {references['inspected']}, "
        f"analysed {references['analysed']}, used {references['used']}, "
        f"inaccessible {references['inaccessible']}."
    )
    print(
        f"Requirements tracked {measurements['requirements']['tracked']} "
        f"(observed {measurements['requirements']['observed']}, "
        f"verified {measurements['requirements']['verified']}); "
        f"rendered evidence {measurements['rendered_evidence']['records']}; "
        f"critique findings {measurements['critique']['findings']} "
        f"({measurements['critique']['resolved']} resolved, "
        f"{measurements['critique']['remaining']} remaining)."
    )
    print(
        f"Component candidates {measurements['components']['candidates']} "
        f"({measurements['components']['dependencies_avoided']} needs solved without a new dependency); "
        f"refinement cycles {measurements['refinement']['attempts']} "
        f"(regressions {measurements['refinement']['regressions']})."
    )
    print("From you: nothing right now.")
    return 0


def approve_design_direction(args: argparse.Namespace) -> int:
    """Record the human G1D approval of one engine design-direction record."""
    run_root, state = resolve_and_load(args)
    entry, packet = current_packet(state, allow_project_drift=True)
    direction_id = str(getattr(args, "direction", "") or "").strip()
    if not direction_id:
        direction = DESIGN.latest_direction(state, task_id=entry["id"]) or DESIGN.active_direction(state, task_id=entry["id"])
        direction_id = str(direction.get("direction_id", ""))
    if not direction_id:
        raise RuntimeError_("no design-direction record exists to approve")
    identity = str(getattr(args, "identity", "") or "").strip()
    if DESIGN.direction(state, direction_id) is None:
        raise RuntimeError_(f"no design-direction record matches {direction_id!r}")
    try:
        approval = DESIGN.approve_direction(
            state, direction_id, identity=identity,
            note=str(getattr(args, "note", "") or ""),
            stage=entry["stage"], packet_id=entry["id"],
        )
    except CONTRACTS.EngineError as exc:
        raise RuntimeError_(str(exc)) from exc
    emit_event(
        run_root, "design_direction_approved", state=state, task_id=entry["id"], stage=entry["stage"],
        direction=direction_id, approval=str(approval.get("approval_id", "")),
        identity=str(approval.get("identity", "")), channel=str(approval.get("channel", "")),
        revision=str(approval.get("revision_hash", ""))[:12],
    )
    state["updated_at"] = now()
    state["next"] = "Implement within the approved design direction."
    write_state(run_root, state)
    print(
        f"Approved design direction {direction_id} for revision "
        f"{str(approval.get('revision_hash', ''))[:12]} as {identity}."
    )
    print("The approval is invalidated automatically if the direction changes materially.")
    print("From you: nothing right now.")
    return 0


def record_intervention(args: argparse.Namespace) -> int:
    run_root, state = resolve_and_load(args)
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
    write_state(run_root, state)
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
    run_root, state = resolve_and_load(args)
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
    write_state(run_root, state)
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


def preserved_s3_parameters(packet: Path) -> tuple[str, str, str]:
    manifest = json.loads(read(packet / TRANSPORT.MANIFEST_NAME))
    delivered_paths = {
        str(item.get("path", ""))
        for item in manifest.get("sources", [])
        if item.get("delivered", True)
    }
    packet_text = read(packet / TRANSPORT.PACKET_NAME)
    match = re.search(
        r"(?ms)^===== BEGIN current S3 prompt block \|.*? =====\r?\n"
        r"(.*?)^===== END current S3 prompt block =====\s*$",
        packet_text,
    )
    if not match:
        raise RuntimeError_("Current S3 packet has no readable prompt block")
    references = re.search(
        r"(?ms)^REFERENCES:\s*(.*?)(?=\r?\n\r?\nSTEP 1 - REFERENCES)",
        match.group(1),
    )
    if not references or not references.group(1).strip():
        raise RuntimeError_("Current S3 packet has no preserved reference parameter")
    motion = "yes" if "DESIGN-MOTION.md" in delivered_paths else "no"
    assets = "yes" if "DESIGN-ASSETS.md" in delivered_paths else "no"
    return references.group(1).strip(), motion, assets


def restart_direction(args: argparse.Namespace) -> int:
    """Archive a rejected S3 direction and prepare its verified same-stage child."""
    run_root, state = resolve_and_load(args)
    entry, packet = current_packet(state, allow_project_drift=True)
    if entry["stage"] != "S3":
        raise RuntimeError_("A design-direction restart belongs to the current S3 boundary")
    project = Path(state["project"])
    design_path = project / "DESIGN.md"
    if not design_path.is_file() or design_path.stat().st_size == 0:
        raise RuntimeError_("A design-direction restart needs the rejected DESIGN.md")
    design = read(design_path)
    if re.search(r"(?im)^\*\*Status:\*\*.*locked at G1", design):
        raise RuntimeError_("A G1-locked direction cannot use the pre-G1 restart path")
    reason = args.reason.strip()
    if not reason:
        raise RuntimeError_("A design-direction restart needs the human's concrete reason")
    thesis = design_thesis(design) or "thesis not extractable; rejected DESIGN.md preserved verbatim"
    context_path = packet / "evidence" / "rejected-direction.md"
    if context_path.exists():
        raise RuntimeError_(f"Refusing to overwrite rejected-direction evidence: {context_path}")
    context_path.write_text(
        "# Rejected S3 direction context\n\n"
        f"**Parent packet:** `{entry['id']}`  \n"
        f"**Restart layer:** `design direction`  \n"
        f"**Human reason:** {reason}  \n"
        f"**Rejected thesis:** {thesis}\n\n"
        "The following DESIGN.md is preserved verbatim as rejected evidence. "
        "It is context for a materially different S3 proposal, not an approved direction.\n\n"
        "===== BEGIN REJECTED DESIGN.md =====\n"
        + design.rstrip()
        + "\n===== END REJECTED DESIGN.md =====\n",
        encoding="utf-8",
    )
    if not stage_has_evidence(packet):
        files = ["DESIGN.md"] + (["AGENTS.md"] if (project / "AGENTS.md").is_file() else [])
        structural_result(argparse.Namespace(
            run_root=str(run_root), project=None, status="complete",
            provider="orchestrator", model="not recorded",
            summary="Design direction was presented and rejected before G1.",
            file=files,
        ))
    record_note(argparse.Namespace(
        run_root=str(run_root), project=None, kind="rejected-direction",
        summary=f"Rejected thesis: {thesis}. Human reason: {reason}",
        evidence="verified",
    ))
    references, motion, assets = preserved_s3_parameters(packet)
    append_log(
        run_root,
        "Design direction restart prepared",
        "The human rejected the pre-G1 direction; Ariadne must preserve it without making them reconstruct context.",
        "Rejected DESIGN.md and the human reason were preserved verbatim; G1 remains unresolved.",
        [str(context_path)],
        f"SHA-256 {sha256(context_path)}",
        "Prepare a materially different S3 direction from the verified restart context.",
    )
    return prepare_next(argparse.Namespace(
        run_root=str(run_root), project=None, stage="S3", retry=True,
        provider=None, references_file=None, references_text=references,
        restart_context=str(context_path), motion=motion, assets=assets,
        target=None, lenses=None, synthetic_validation=args.synthetic_validation,
    ))


def stage_has_evidence(packet: Path) -> bool:
    evidence = packet / "evidence"
    return any(
        (evidence / name).is_file()
        for name in (
            "transcript.md", "stage-result.json", "return-handoff.md",
            "validation.json", "review-judgement.md",
        )
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
        project / ".ariadne" / "returns" / f"{manifest.get('packet_id')}.md"
    ).resolve()
    if target != expected:
        raise RuntimeError_("The S4B structured return target does not match this packet")
    return target


def advance(args: argparse.Namespace) -> int:
    """Record obvious same-session outputs and continue through routine boundaries."""
    run_root, state = resolve_and_load(args)
    entry, packet = current_packet(state, allow_project_drift=True)
    stage = entry["stage"]
    project = Path(state["project"])

    if stage == "S4B" and not (packet / "evidence" / "return-handoff.md").is_file():
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

    if stage == "S4B":
        returned = packet / "evidence" / "return-handoff.md"
        validation = packet / "evidence" / "validation.json"
        if returned.is_file() and TRANSPORT.return_handoff_status(read(returned)) == "complete" and not validation.is_file():
            result = validate_worker(argparse.Namespace(run_root=str(run_root), project=None, timeout=120))
            if result != 0:
                state = load_state(run_root)
                try:
                    validation_value = json.loads(read(packet / "evidence" / "validation.json"))
                except (OSError, json.JSONDecodeError):
                    return result
                outcome = worker_outcome(
                    validation_value.get("status", "blocked"),
                    validation_value.get("failure_kind", "routine"),
                    int((state.get("worker") or {}).get("repair_attempts", 0)),
                )
                if outcome["retryable"]:
                    return prepare_next(argparse.Namespace(
                        run_root=str(run_root), project=None, stage=None, retry=True,
                        provider=None, worker_role=None, escalate=False,
                        references_file=None, references_text=None, restart_context=None,
                        motion=None, assets=None, target=None, lenses=None,
                        synthetic_validation=getattr(args, "synthetic_validation", False),
                    ))
                return result
            state = load_state(run_root)
            entry, packet = current_packet(state, allow_project_drift=True)
        if validation.is_file():
            try:
                validation_value = json.loads(read(validation))
            except (OSError, json.JSONDecodeError) as exc:
                raise RuntimeError_(f"Worker validation evidence is malformed: {exc}") from exc
            if validation_value.get("status") != "passed":
                outcome = worker_outcome(
                    validation_value.get("status", "blocked"),
                    validation_value.get("failure_kind", "routine"),
                    int((state.get("worker") or {}).get("repair_attempts", 0)),
                )
                if outcome["retryable"]:
                    return prepare_next(argparse.Namespace(
                        run_root=str(run_root), project=None, stage=None, retry=True,
                        provider=None, worker_role=None, escalate=False,
                        references_file=None, references_text=None, restart_context=None,
                        motion=None, assets=None, target=None, lenses=None,
                        synthetic_validation=getattr(args, "synthetic_validation", False),
                    ))
                print("Paused. " + outcome["next"])
                return 2

    if not stage_has_evidence(packet):
        expected = EXPECTED_STAGE_OUTPUTS.get(stage)
        if stage == "S3":
            design = read(project / "DESIGN.md") if (project / "DESIGN.md").is_file() else ""
            if design:
                creative_problems = POLICY.creative_evidence_problems(state, project)
                if creative_problems:
                    state["next"] = "Resolve the unsupported creative evidence before asking for G1."
                    state["updated_at"] = now()
                    write_state(run_root, state)
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
            gate_problems = POLICY.g1_problems(state, project)
            if gate_problems:
                ensure_intervention(
                    state,
                    "necessary",
                    "Decide the G1 creative direction.",
                    "Only the human can approve, reject, or redirect the proposed thesis.",
                    "creative-decision",
                )
                state["next"] = (
                    "Only the human can grant G1: approve the proposed design direction with the operator "
                    "approval command, or redirect it."
                )
                state["updated_at"] = now()
                write_state(run_root, state)
                append_log(
                    run_root,
                    "Creative decision requested",
                    "The design direction exists, but Ariadne cannot grant G1 for the human.",
                    "No continuation or stage evidence was created. " + "; ".join(gate_problems),
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
            write_state(run_root, state)
            print(f"Paused. {state['next']}")
            return 2

    retry = False
    if stage == "S4B":
        returned = packet / "evidence" / "return-handoff.md"
        retry = returned.is_file() and TRANSPORT.return_handoff_status(read(returned)) != "complete"
        if retry and TRANSPORT.return_handoff_status(read(returned)) == "blocked":
            state["next"] = "Worker returned BLOCKED; inspect the recorded conflict or safety finding and use --escalate for a stronger worker."
            state["updated_at"] = now()
            write_state(run_root, state)
            append_log(
                run_root,
                "Blocked worker return held",
                "A blocked worker report is a boundary signal, not a routine repair request.",
                "No automatic retry was created.",
                [str(returned)],
                "Use an explicit stronger worker or senior reasoning escalation after inspecting the return.",
                state["next"],
            )
            print("Paused. " + state["next"])
            return 2

    return prepare_next(
        argparse.Namespace(
            run_root=str(run_root),
            project=None,
            stage=None,
            retry=retry,
            provider=args.transport_provider,
            worker_role=None,
            escalate=False,
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
        if not returned.is_file():
            return None, "The structured implementation return is missing; complete or recover it before independent review."
        if TRANSPORT.return_handoff_status(read(returned)) != "complete":
            return None, "Implementation returned partial or blocked; resume it before independent review."
        if not (project / "QA.md").is_file():
            return None, "Implementation or mechanical QA is incomplete."
        validation_path = _packet / "evidence" / "validation.json"
        if not validation_path.is_file():
            return None, "Ariadne's independent worker validation is missing; do not trust the worker self-report."
        try:
            validation = json.loads(read(validation_path))
        except (OSError, json.JSONDecodeError) as exc:
            return None, f"Independent worker validation is malformed: {exc}"
        problems = TRANSPORT.worker_validation_problems(validation, entry["id"])
        if problems:
            return None, "Independent worker validation is malformed: " + "; ".join(problems)
        if validation.get("status") != "passed":
            return None, "Independent worker validation did not pass; repair or escalate before review."
        return "S5", "Mechanical QA exists and Ariadne independently validated the worker result; review can be isolated."
    if stage == "S5":
        return None, "The human must decide G3, then explicitly authorise any G4 ship action."
    if stage == "S6":
        return None, "The project retrospective is complete."
    return None, f"No production transition is defined for {stage}."


def execution_for_task(
    state: dict,
    *,
    task_id: str,
    role: str,
    adapter: str = "",
    invocation: str = "",
    requested: dict | None = None,
    packet: Path | None = None,
    reason: str = "",
    create_if_missing: bool = True,
    reuse: bool = True,
    parent: str = "",
) -> tuple[dict | None, list[str]]:
    """The engine-owned execution identity for one task and role.

    Reuses the open execution the engine already created for this boundary, or
    creates one. A caller never chooses the id; ``--execution`` only ever names
    an execution the engine created. ``reuse=False`` creates a fresh identity
    for a role that legitimately repeats (each independent validation attempt is
    its own execution).
    """
    if reuse:
        existing = EXECUTION.latest_execution(state, role=role, task_id=str(task_id))
        if existing is not None:
            if str(existing.get("state")) in EXECUTION.TERMINAL_EXECUTION_STATES:
                return existing, [
                    f"execution {existing.get('execution_id')} already finished as {existing.get('state')}; "
                    "a finished execution cannot accept another result"
                ]
            return existing, []
    if not create_if_missing:
        return None, [
            f"no engine-created {role} execution exists for task {task_id}; "
            "the engine creates execution identities at the boundary, they are not supplied"
        ]
    record = EXECUTION.create(
        state,
        task_id=str(task_id),
        role=role,
        adapter=adapter,
        invocation=invocation,
        requested=requested or {},
        revision=EXECUTION.task_revision(state, packet),
        reason=reason,
        parent=parent,
    )
    EXECUTION.mark_started(state, record["execution_id"])
    return record, []


def named_execution(state: dict, execution_id: str, *, role: str = "", task_id: str = "") -> tuple[dict | None, list[str]]:
    """Resolve a caller-supplied execution id against the engine's own records."""
    execution_id = str(execution_id or "").strip()
    if not execution_id:
        return None, []
    record = EXECUTION.execution(state, execution_id)
    if record is None:
        return None, [
            f"execution {execution_id!r} was not created by this engine; a result must name a "
            "recorded execution, and the engine never accepts a caller-chosen id"
        ]
    problems = CONTRACTS.execution_problems(record)
    if problems:
        return record, ["the named execution record is not usable: " + "; ".join(problems)]
    if role and str(record.get("role", "")) != role:
        problems.append(
            f"execution {execution_id} is a {record.get('role')} execution, not a {role} execution"
        )
    if task_id and str(record.get("task_id", "")) != str(task_id):
        problems.append(
            f"execution {execution_id} was created for task {record.get('task_id')}, not {task_id}"
        )
    return record, problems


def execution_verify_result(state: dict, execution: dict, entry: dict, packet: Path) -> list[str]:
    """Preconditions for accepting a result for one execution, bound to this revision."""
    revision = EXECUTION.task_revision(state, packet)["revision_hash"]
    return EXECUTION.verify_result(
        state,
        str(execution.get("execution_id", "")),
        role=str(execution.get("role", "implementer")),
        task_id=str(entry.get("id", "")),
        revision_hash=revision,
    )


def record_failure(
    state: dict,
    *,
    source: str,
    operation: str,
    evidence: tuple[str, ...] | list[str],
    execution_id: str = "",
    task_id: str = "",
    revision_hash: str = "",
    detail: str = "",
) -> dict:
    """Classify and record one failure, naming the strategy that produced it."""
    strategy = ""
    if execution_id:
        record_value = EXECUTION.execution(state, str(execution_id))
        if record_value is not None:
            strategy = EXECUTION.strategy_id(record_value)
    return EXECUTION.record_failure(
        state,
        source=source,
        operation=operation,
        evidence=evidence,
        execution_id=execution_id,
        task_id=task_id,
        revision_hash=revision_hash,
        detail=detail,
        strategy=strategy,
    )


def find_implementer_execution(state: dict, *, task_id: str) -> dict | None:
    """The execution that produced the implementation for a task (any state)."""
    return EXECUTION.latest_execution(state, role="implementer", task_id=str(task_id))


def reviewed_implementation_task(state: dict, packet: Path) -> str:
    """The implementation task a review boundary reviews.

    The recorded worker row is authoritative when it exists. Otherwise the most
    recent S4B packet in the recorded chain is used, so a linked S5 -> S5 retry
    (which parents the previous *review* packet, not the build) still names the
    build it reviews.
    """
    worker_task = str((state.get("worker") or {}).get("task_id", "") or "")
    packets = [item for item in (state.get("packets") or []) if isinstance(item, dict)]
    if worker_task and any(str(item.get("id", "")) == worker_task for item in packets):
        return worker_task
    s4b = [str(item.get("id", "")) for item in packets if item.get("stage") == "S4B"]
    if s4b:
        return s4b[-1]
    manifest = {}
    manifest_path = Path(packet) / TRANSPORT.MANIFEST_NAME
    if manifest_path.is_file():
        try:
            manifest = json.loads(read(manifest_path))
        except (OSError, json.JSONDecodeError):
            manifest = {}
    return str((manifest or {}).get("parent_id", "") or "")


def prepare_next(args: argparse.Namespace) -> int:
    run_root, state = resolve_and_load(args)
    entry, parent = current_packet(state, allow_project_drift=True)
    escalate = bool(getattr(args, "escalate", False))
    if escalate:
        if entry["stage"] != "S4B":
            raise RuntimeError_("Escalation is currently defined for the implementation worker boundary only")
        if args.stage and args.stage != entry["stage"]:
            raise RuntimeError_("Worker escalation must remain at the current S4B boundary")
        args.retry = True
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
        write_state(run_root, state)
        append_log(run_root, "Continuation paused", reason, "No packet created.", next_action=reason)
        print(f"Paused: {reason}")
        return 2
    # One precondition set for every continuation path (advance delegates here too).
    continuation = POLICY.continuation_problems(state, stage, project=Path(state["project"]))
    if continuation:
        reason = "; ".join(continuation)
        state["next"] = reason
        state["updated_at"] = now()
        write_state(run_root, state)
        append_log(
            run_root,
            "Continuation paused",
            "The requested boundary does not satisfy its preconditions; no packet was created.",
            reason,
            "No stage transition was applied.",
            next_action=reason,
        )
        print(f"Paused: {reason}")
        return 2
    worker_role = getattr(args, "worker_role", None)
    project = Path(state["project"])
    handoff_path = project / "HANDOFF.md"
    handoff_contract = TRANSPORT.worker_contract(read(handoff_path)) if handoff_path.is_file() else {}
    packet_id, output = allocate_packet(run_root, state["run_id"], stage)
    # AR-202 T3: deterministic task characterisation from the evidence that exists.
    characterisation = ROUTING.characterize(
        state,
        project=project,
        stage=stage,
        task_id=packet_id,
        transport=TRANSPORT,
        request=state.get("request"),
        dependencies=tuple(POLICY.declared_dependencies(project)),
    )
    ROUTING.record_characterisation(state, characterisation)
    emit_event(
        run_root, "task_characterized", state=state, task_id=packet_id, stage=stage,
        characterisation_id=characterisation["characterisation_id"],
        difficulty=characterisation["difficulty"]["value"],
        stakes=characterisation["stakes"]["value"],
        required_capabilities=[item["id"] for item in characterisation["required_capabilities"]],
    )
    requested_provider = args.provider
    routing_decision: dict = {}
    if stage == "S4B":
        current_manifest = json.loads(read(parent / TRANSPORT.MANIFEST_NAME))
        current_worker = current_manifest.get("worker") or {}
        current_role = current_worker.get("role") or handoff_contract.get("worker_role")
        if args.retry and entry["stage"] == "S4B" and not escalate:
            retry_problems = POLICY.retry_problems(state, parent)
            if retry_problems:
                raise RuntimeError_(" ".join(retry_problems))
        # AR-202 T5: the worker role is an executable routing decision, not an index lookup.
        routing_decision = ROUTING.route(
            state, stage=stage, characterisation=characterisation, task_id=packet_id,
            declared_role=str(current_role or ""), escalate=escalate,
            requested_role=str(worker_role or ""),
        )
        ROUTING.record(state, routing_decision)
        emit_event(
            run_root, "route_selected", state=state, task_id=packet_id, stage=stage,
            status=routing_decision["status"], rule=routing_decision["rule"],
            reason=routing_decision["reason"],
            requested_provider=str((routing_decision.get("requested") or {}).get("provider", "")),
            worker_role=str((routing_decision.get("chosen") or {}).get("id", "")),
        )
        if routing_decision["status"] in ("no-route", "blocked"):
            return pause_continuation(
                run_root, state, routing_decision["reason"],
                why="No authorized execution strategy satisfies this boundary; no packet was created.",
            )
        worker_role = str(routing_decision["chosen"]["id"])
        packet_provider = requested_provider or transport_provider(state.get("provider_preflight"))
    elif stage in REASONERS.load_contract()["reasoning_stages"]:
        chosen = REASONERS.selected(state)["id"]
        if requested_provider and requested_provider != chosen:
            raise RuntimeError_(
                f"Reasoner override {requested_provider!r} does not match the recorded selection "
                f"{chosen!r}; use select-reasoner so the switch is preserved."
            )
        capability = REASONERS.detect(chosen)
        if not REASONERS.selectable(capability):
            raise RuntimeError_(
                f"Selected reasoner {chosen} is unavailable: "
                f"{capability.get('execution', 'not observed')}. No packet was created."
            )
        routing_decision = ROUTING.route(
            state, stage=stage, characterisation=characterisation, task_id=packet_id,
            reasoner_selection=REASONERS.selected(state),
            reasoner_contract=REASONERS.load_contract(),
            reasoner_capability=capability,
        )
        ROUTING.record(state, routing_decision)
        emit_event(
            run_root, "route_selected", state=state, task_id=packet_id, stage=stage,
            status=routing_decision["status"], rule=routing_decision["rule"],
            reason=routing_decision["reason"],
            requested_provider=str((routing_decision.get("requested") or {}).get("provider", "")),
        )
        if routing_decision["status"] in ("no-route", "blocked"):
            return pause_continuation(
                run_root, state, routing_decision["reason"],
                why="No authorized reasoning candidate satisfies this boundary; no packet was created.",
            )
        packet_provider = str(routing_decision["chosen"]["id"])
    else:
        packet_provider = requested_provider or transport_provider(state.get("provider_preflight"))
    if entry["stage"] == "S3" and stage == "S4A":
        g1_record = next(
            (
                record for record in reversed(POLICY.approvals(state, "G1"))
                if record.get("channel") == CONTRACTS.APPROVAL_CHANNEL_HUMAN
            ),
            None,
        )
        ensure_intervention(
            state,
            "necessary",
            "Decide the G1 creative direction.",
            "Only the human can approve, reject, or redirect the proposed thesis.",
            "creative-decision",
            status="resolved",
            evidence=(
                f"Recorded G1 approval {g1_record['approval_id']} by {g1_record['identity']} "
                f"bound to revision {str(g1_record['revision_hash'])[:12]}."
                if g1_record else "G1 approval recorded."
            ),
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
    kwargs = dict(
        stage=stage,
        project=state["project"],
        output=str(output),
        packet_id=packet_id,
        parent=str(parent),
        retry=args.retry,
        provider=packet_provider,
        worker_role=worker_role,
        references_file=args.references_file,
        references_text=getattr(args, "references_text", None),
        restart_context=getattr(args, "restart_context", None),
        motion=args.motion,
        assets=args.assets,
        target=args.target,
        lenses=args.lenses,
        synthetic_validation=args.synthetic_validation,
        request=state.get("request"),
    )
    transport_args = transport_namespace(**kwargs)
    # AR-202 T4: one recorded decision per candidate source, then a plan that can
    # only omit a source the transport declared removable (never add one).
    # The cache is guarded by the *project* revision (the baseline head) rather
    # than the parent packet id, so a same-stage retry reuses unchanged source
    # hashes while a moved project revision invalidates them conservatively.
    parent_revision = EXECUTION.task_revision(state, parent)
    revision_hash = str(parent_revision.get("baseline") or parent_revision.get("revision_hash", ""))
    candidates = TRANSPORT.plan_sources(stage, project, transport_args)
    context_decision = CONTEXT.decide(
        state,
        stage=stage,
        candidates=candidates,
        characterisation=characterisation,
        run_root=run_root,
        revision_hash=revision_hash,
    )
    context_plan = CONTEXT.plan(context_decision)
    TRANSPORT.prepare(transport_args, context_plan=context_plan)
    prepared_manifest = json.loads(read(output / TRANSPORT.MANIFEST_NAME))
    final_context = CONTEXT.finalise(context_decision, prepared_manifest)
    CONTEXT.record(state, final_context)
    CONTEXT.update_cache(run_root, state, final_context, prepared_manifest, revision_hash=revision_hash)
    context_metrics = CONTEXT.summarise(final_context)
    emit_event(
        run_root, "context_decided", state=state, task_id=packet_id, stage=stage,
        decision=final_context["decision_id"], **context_metrics,
    )
    for invalidation in (final_context.get("cache") or {}).get("invalidated", []) or []:
        emit_event(
            run_root, "context_invalidated", state=state, task_id=packet_id, stage=stage,
            path=str(invalidation.get("path", "")), reason=str(invalidation.get("reason", "")),
        )
    if context_metrics["cache_hits"]:
        emit_event(
            run_root, "context_cache_hit", state=state, task_id=packet_id, stage=stage,
            hits=context_metrics["cache_hits"],
        )
    STATEMACHINE.apply_transition(
        state,
        CONTRACTS.TransitionRequest(
            kind="stage",
            to=stage,
            reason=reason or f"Prepare {FRIENDLY_STAGES.get(stage, stage)}.",
            evidence=(str(output), packet_id),
            packet={
                "id": packet_id,
                "stage": stage,
                "path": str(output),
                "reasoner_output_baseline": reasoner_output_baseline(Path(state["project"]), stage),
            },
            actor="runtime",
            operation=f"prepare:{stage}",
        ),
        permitted=True,
    )
    # AR-202 T2: the engine creates the execution identity for the boundary it
    # just prepared, before any worker or session can claim one.
    requested_identity = {
        "provider": str(packet_provider or ""),
        "model": str((state.get("provider_preflight") or {}).get("model", "") or ""),
        "effort": str((state.get("provider_preflight") or {}).get("effort", "") or ""),
        "worker_role": str(worker_role or ""),
    }
    boundary_execution = None
    execution_problems = []
    if stage == "S4B":
        boundary_role = "implementer"
        boundary_adapter = "scripts/prepare-stage.py:worker"
        boundary_reason = "prepared S4B implementation boundary"
        boundary_invocation = f"prepare-next --stage S4B (attempt from {entry['id']})"
    elif stage in REASONERS.load_contract()["reasoning_stages"]:
        boundary_role = "reasoner"
        boundary_adapter = f"reasoners.py:{packet_provider}"
        boundary_reason = f"prepared {stage} reasoning boundary"
        boundary_invocation = f"prepare-next --stage {stage}"
    else:
        boundary_role = ""
        boundary_adapter = boundary_reason = boundary_invocation = ""
    if boundary_role:
        boundary_execution, execution_problems = execution_for_task(
            state, task_id=packet_id, role=boundary_role,
            adapter=boundary_adapter, invocation=boundary_invocation,
            requested=requested_identity, packet=output, reason=boundary_reason,
        )
        if execution_problems:
            # A finished identity is never reused for a boundary that has not run
            # yet: create the fresh one instead of proceeding with a closed record.
            boundary_execution, execution_problems = execution_for_task(
                state, task_id=packet_id, role=boundary_role,
                adapter=boundary_adapter, invocation=boundary_invocation,
                requested=requested_identity, packet=output, reason=boundary_reason,
                reuse=False,
            )
        if execution_problems and boundary_execution is None:
            raise RuntimeError_(" ".join(execution_problems))
    if boundary_execution is not None:
        emit_event(
            run_root, "execution_created", state=state, task_id=packet_id, stage=stage,
            execution=boundary_execution["execution_id"], role=boundary_execution["role"],
            adapter=boundary_execution["adapter"],
            requested_provider=str(requested_identity["provider"]),
            requested_model=str(requested_identity["model"]),
        )
        emit_event(
            run_root, "execution_started", state=state, task_id=packet_id, stage=stage,
            execution=boundary_execution["execution_id"], role=boundary_execution["role"],
        )
    if stage == "S4B":
        worker = update_worker_state(
            state,
            prepared_manifest,
            state.get("provider_preflight"),
            escalation_increment=1 if escalate else 0,
            execution=boundary_execution or {},
        )
        append_worker_telemetry(
            run_root,
            "worker-prepared",
            task_id=worker.get("task_id", packet_id),
            worker_role=worker.get("worker_role", worker_role),
            provider=worker.get("provider", packet_provider or "unknown"),
            model=worker.get("model", "unknown"),
            attempt=worker.get("attempt", 1),
            validation_attempts=worker.get("validation_attempts", 0),
            files_changed=[],
            tests_result="not run",
            escalation_count=worker.get("escalation_count", 0),
            review_outcome="not reviewed",
            accepted="unknown",
            usage="unknown",
            cost="unknown",
            execution=str(worker.get("execution_id", "")),
        )
    state["updated_at"] = now()
    state["evidence_state"] = "verified-transport; stage not yet observed"
    state["next"] = f"Continue with {FRIENDLY_STAGES.get(stage, stage)}."
    if stage == "S4B":
        ensure_intervention(
            state,
            "necessary",
            "Start the selected external implementation worker.",
            "The current worker boundary cannot execute without the human opening or authorising that external environment.",
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
    write_state(run_root, state)
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
        print(f"Worker task: {worker_role}; start the selected implementation worker when you are ready.")
    elif stage == "S5":
        print("From you: open one fresh independent review session with the prepared context.")
    else:
        print("From you: nothing right now.")
    return 0


def pause_continuation(run_root: Path, state: dict, reason: str, *, why: str = "") -> int:
    """Record why no packet was created and pause. Nothing is transitioned."""
    state["next"] = reason
    state["updated_at"] = now()
    write_state(run_root, state)
    append_log(
        run_root,
        "Continuation paused",
        why or "The requested boundary does not satisfy its preconditions; no packet was created.",
        reason,
        "No stage transition was applied.",
        next_action=reason,
    )
    print(f"Paused: {reason}")
    return 2


def transport_provider(preflight: dict | None) -> str | None:
    if not preflight:
        return None
    value = str(preflight.get("provider", "")).strip()
    return value or None


def operations_log_problems(text: str) -> list[str]:
    problems = []
    for token in ("# Ariadne operations", "## Brief", "## Evidence language", "## Timeline"):
        if token not in text:
            problems.append(f"operations log missing: {token}")
    return problems


def skill_contract_problems(
    skill_text: str | None = None,
    interface_text: str | None = None,
    installation_example: str | None = None,
) -> list[str]:
    skill_path = ROOT / ".agents" / "skills" / "ariadne" / "SKILL.md"
    interface_path = ROOT / ".agents" / "skills" / "ariadne" / "agents" / "openai.yaml"
    example_path = ROOT / ".agents" / "skills" / "ariadne" / "references" / "installation.example.json"
    if skill_text is None:
        skill_text = read(skill_path)
    if interface_text is None:
        interface_text = read(interface_path)
    if installation_example is None:
        installation_example = read(example_path)
    problems = []
    frontmatter = re.match(r"(?s)^---\s*\n(.*?)\n---\s*\n", skill_text)
    if not frontmatter:
        problems.append("ariadne skill has no YAML frontmatter")
    else:
        header = frontmatter.group(1)
        name = re.search(r"(?m)^name:\s*(.+?)\s*$", header)
        description = re.search(r"(?m)^description:\s*(.+?)\s*$", header)
        if not name or name.group(1).strip() != "ariadne":
            problems.append("ariadne skill name must be ariadne")
        if not description or not all(
            token in description.group(1).lower() for token in ("ariadne", "start", "resume")
        ):
            problems.append("ariadne skill description must advertise start and resume triggers")
    for token in ("display_name:", "short_description:", "default_prompt:", "Ariadne"):
        if token not in interface_text:
            problems.append(f"ariadne skill interface missing: {token}")
    try:
        example = json.loads(installation_example)
        if not example.get("ariadne_root"):
            problems.append("ariadne installation example has no ariadne_root")
    except json.JSONDecodeError:
        problems.append("ariadne installation example is malformed")
    for token in (
        "scripts/ariadne.py", "discover --project", "provider preflight",
        "handoff-readiness", "ariadne.py advance", "record-note",
        "restart-direction",
        "ingest-return", "validate-worker", "ingest-review", "record-acceptance",
        "worker-telemetry.jsonl", "same-stage retry", "--adopt-existing",
        "creative-plan", "record-creative", "creative-check",
        "operations-plan", "record-operations", "operations-check",
        "skill-activation",
        "reasoner-status", "select-reasoner", "record-reasoner-failure",
        "references/creative-operations.md",
        "Never grant a gate",
    ):
        if token not in skill_text:
            problems.append(f"ariadne skill missing runtime boundary: {token}")
    return problems


def repository_contract_problems() -> list[str]:
    problems = []
    required = [
        ROOT / ".agents" / "skills" / "ariadne" / "SKILL.md",
        ROOT / "templates" / "RETURN-HANDOFF.md",
        ROOT / "templates" / "HANDOFF.md",
        ROOT / "prompts" / "build-kickoff.md",
        ROOT / ".agents" / "skills" / "ariadne" / "agents" / "openai.yaml",
        ROOT / ".agents" / "skills" / "ariadne" / "references" / "installation.example.json",
        ROOT / "scripts" / "install-ariadne-skill.py",
        ROOT / "prompts" / "project-review.md",
        ROOT / "scripts" / "creative-intelligence.py",
        ROOT / ".agents" / "skills" / "ariadne" / "references" / "creative-intelligence.md",
        ROOT / "scripts" / "creative-operations.py",
        ROOT / ".agents" / "skills" / "ariadne" / "references" / "creative-operations.md",
        ROOT / "skills" / "visual-qa.md",
        ROOT / "skills" / "creative-review.md",
        ROOT / "skills" / "social-strategy.md",
        ROOT / "templates" / "SOCIAL-STRATEGY.md",
        ROOT / "scripts" / "reasoners.py",
        ROOT / "adapters" / "reasoners.json",
        ROOT / "adapters" / "reasoner-contract.md",
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
        "## Worker execution contract",
        "## Validation commands",
        "Routine repair limit",
        "Permitted files and systems",
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
        "bounded contract",
        "routine repair",
        "independent validation",
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
    problems.extend(REASONERS.contract_problems())
    return problems


@contextlib.contextmanager
def self_test_workspace():
    path = ROOT / "validation" / f"ariadne-self-test-{uuid.uuid4().hex}"
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


def filled_return(status_value: str = "complete", task_id: str = "fixture-S4B") -> str:
    sections = "\n\n".join(f"## {heading}\n\nnone" for heading in TRANSPORT.RETURN_HANDOFF_HEADINGS)
    return (
        "# IMPLEMENTATION RETURN HANDOFF: Fixture\n\n"
        f"**Status:** {status_value}\n**Task ID:** {task_id}\n**Worker role:** bulk\n"
        "**Provider:** fixture\n**Model:** fixture-model\n"
        "**Effort:** medium\n**Started:** 2026-08-23\n**Ended:** 2026-08-23\n"
        "**Usage:** unknown\n**Cost:** unknown\n"
        "**Scope status:** within-contract\n**Unexpected actions or conflicts:** none\n\n"
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

A small typographic interaction for testing the Ariadne runtime.

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
| Provider | Cursor |
| Model | provider default — unverified |
| Effort | medium |
| Workload | medium |
| Split | none |
| Reason | Normal visual implementation. |

## Worker execution contract

**Worker role:** bulk

**Objective:** Test a typographic interaction.

**Relevant context:** HANDOFF.md, locked DESIGN.md, project AGENTS.md, permitted files, and directly relevant repository files.

**Invariants:** Preserve the approved thesis, signature interaction, and acceptance criterion.

**Permitted actions:** Read relevant repository files; edit permitted files; create required files; run tests and validation; inspect git status and diff; repair routine validation failures.

**Prohibited actions:** git push, force operations, git reset or git clean, deleting significant data, reading or writing secrets or .env files, deployment or production changes, destructive migrations, unapproved dependencies, unrelated systems.

**Stop conditions:** Missing context, packet/repository conflict, invariant risk, out-of-scope or dangerous action, or exhausted repair budget.

**Escalation conditions:** Repeated routine failure, architecture conflict or uncertainty, high-risk change, or invariant conflict.

**Lifecycle:** baseline -> implementation -> validation -> routine repair -> validation -> result/checkpoint

**Routine repair limit:** 2

### Permitted files and systems

| Path / glob | Actions | Reason |
|---|---|---|
| src/** | read / edit / create | implementation fixture |
| QA.md | read / edit / create | mechanical evidence |
| AGENTS.md | read / edit | stage state |
| .ariadne/creative-operations.json | read / edit | implementation and visual evidence |
| status-observation.txt | read / create | fixture observation evidence |

## Validation commands

| Check | Command | Required | Expected |
|---|---|---|---|
| diff hygiene | `git diff --check` | yes | exit code 0 |

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

    replace_attempts = []

    def transient_replace(_source: Path, _target: Path) -> None:
        replace_attempts.append(1)
        if len(replace_attempts) < 3:
            raise PermissionError("fixture sharing violation")

    replace_with_retry(
        Path("fixture.tmp"), Path("fixture.json"), attempts=3,
        replace=transient_replace, sleep=lambda _delay: None,
    )
    case("atomic state write retries transient sharing violations", len(replace_attempts) == 3)
    try:
        replace_with_retry(
            Path("fixture.tmp"), Path("fixture.json"), attempts=2,
            replace=lambda _source, _target: (_ for _ in ()).throw(
                PermissionError("fixture persistent denial")
            ),
            sleep=lambda _delay: None,
        )
        persistent_replace_failed = False
    except PermissionError:
        persistent_replace_failed = True
    case("atomic state write does not hide persistent denial", persistent_replace_failed)

    case("repository runtime contracts pass (positive control)", not repository_contract_problems())
    with self_test_workspace() as first_workspace, self_test_workspace() as second_workspace:
        case(
            "independent runtime self-test workspaces do not collide",
            first_workspace != second_workspace and first_workspace.exists() and second_workspace.exists(),
        )
    canonical_skill = read(ROOT / ".agents" / "skills" / "ariadne" / "SKILL.md")
    canonical_interface = read(ROOT / ".agents" / "skills" / "ariadne" / "agents" / "openai.yaml")
    canonical_install = read(ROOT / ".agents" / "skills" / "ariadne" / "references" / "installation.example.json")
    case("skill discovery contract passes (positive control)", not skill_contract_problems(canonical_skill, canonical_interface, canonical_install))
    case("skill trigger drift is detected", bool(skill_contract_problems(canonical_skill.replace("resume", "continue", 1), canonical_interface, canonical_install)))
    case("skill name drift is detected", bool(skill_contract_problems(canonical_skill.replace("name: ariadne", "name: wrong-name", 1), canonical_interface, canonical_install)))
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
    case(
        "Claude Code retains an explicit implementation transport identity",
        transport_provider({"provider": "Claude Code"}) == "Claude Code",
    )
    case(
        "a model name is not relabelled as the Cursor provider",
        transport_provider({"provider": "Grok"}) == "Grok",
    )
    case("complete return handoff passes (positive control)", not TRANSPORT.return_handoff_problems(filled_return()))
    case("missing return section fails", bool(TRANSPORT.return_handoff_problems(filled_return().replace("## Known issues", "## Notes"))))
    case("invalid return status fails", bool(TRANSPORT.return_handoff_problems(filled_return("done"))))
    case(
        "worker lifecycle A: routine implementation can validate immediately",
        worker_outcome("passed")["validation_state"] == "VALIDATED"
        and not worker_outcome("passed")["escalation_required"],
    )
    first_failure = worker_outcome("failed", "routine", 0, 2)
    repaired = worker_outcome("passed", "none", 1, 2)
    case(
        "worker lifecycle B: one routine validation failure has a bounded repair path",
        first_failure["retryable"] and first_failure["lifecycle"] == "routine-repair"
        and repaired["validation_state"] == "VALIDATED",
    )
    exhausted = worker_outcome("failed", "routine", 2, 2)
    case(
        "worker lifecycle C: repeated routine failure stops and escalates",
        not exhausted["retryable"] and exhausted["escalation_required"]
        and exhausted["lifecycle"] == "escalation-required",
    )
    conflict = worker_outcome("blocked", "repository-conflict", 0, 2)
    case(
        "worker lifecycle D: repository conflict escalates without speculative repair",
        conflict["escalation_required"] and not conflict["retryable"],
    )
    blocked_routine = worker_outcome("blocked", "routine", 0, 2)
    case(
        "worker lifecycle D2: any blocked result cannot enter routine repair",
        blocked_routine["escalation_required"] and not blocked_routine["retryable"],
    )
    dangerous_scope = TRANSPORT.worker_scope_check(
        {"state": "clean", "head": "fixture", "entries": []},
        {"state": "dirty", "head": "fixture", "entries": [{"path": ".env", "status": "??", "exists": True, "sha256": "x"}]},
        ["src/**"],
    )
    case(
        "worker lifecycle E: sensitive or out-of-scope changes are blocked",
        dangerous_scope["status"] == "dangerous-action",
    )
    validation_unknowns = {
        "schema_version": TRANSPORT.WORKER_VALIDATION_SCHEMA,
        "kind": "worker-validation", "packet_id": "fixture", "stage": "S4B",
        "status": "passed", "independent": True,
        "scope": {"status": "within-contract"}, "failure_kind": "none",
        "commands": [], "usage": "unknown", "cost": "unknown",
    }
    case(
        "worker lifecycle F: unavailable usage and cost remain explicitly unknown",
        not TRANSPORT.worker_validation_problems(validation_unknowns, "fixture"),
    )
    case(
        "worker lifecycle G: provider/model swaps preserve the same role contract",
        transport_provider({"provider": "Command Code GOAT"}) == "Command Code GOAT"
        and transport_provider({"provider": "OpenCode"}) == "OpenCode"
        and TRANSPORT.worker_contract(filled_handoff())["worker_role"] == "bulk",
    )
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
                references_file=None, references_text=None, restart_context=None,
                motion=None, assets=None, target=None,
                lenses=None, synthetic_validation=True,
                reasoner=None, reason="fixture reason", summary="fixture failure",
                evidence="blocked", json=False, migrate=False,
                reviewer_identity="self-test-independent-reviewer", reviewer_role=None,
                kind=None, gate=None, identity=None, note=None, outcome=None, role=None,
                escalate=False, worker_role=None, input=None, status=None, file=None,
                timeout=120,
            )
            defaults.update(values)
            return argparse.Namespace(**defaults)

        real_detect = REASONERS.detect

        def fixture_detect(identifier: str, contract: dict | None = None) -> dict:
            if identifier == "claude":
                return {
                    "id": "claude", "availability": "detected",
                    "classification": "reasonably-assumed", "version": "fixture-cli",
                    "executable": "fixture/claude", "execution": "fixture only; live execution unverified",
                }
            return real_detect(identifier, contract)

        blocked_project = workspace / "claude-unavailable-project"
        blocked_run = workspace / "claude-unavailable-run"
        REASONERS.detect = lambda identifier, contract=None: (
            {
                "id": identifier, "availability": "unavailable", "classification": "blocked",
                "version": "not observed", "executable": "not found", "execution": "fixture unavailable",
            }
            if identifier == "claude" else real_detect(identifier, contract)
        )
        try:
            start(argparse.Namespace(
                project=str(blocked_project), run_root=str(blocked_run), run_id="blocked",
                request="Fixture Claude start.", request_file=None, reasoner="claude",
                adopt_existing=False, synthetic_validation=True,
            ))
            unavailable_start_blocked = False
        except RuntimeError_:
            unavailable_start_blocked = True
        finally:
            REASONERS.detect = real_detect
        case(
            "unavailable Claude start leaves no project or run",
            unavailable_start_blocked and not blocked_project.exists() and not blocked_run.exists(),
        )

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
        case("runtime refuses to overwrite existing Ariadne entry documents", protected_entry_refused)

        start(
            argparse.Namespace(
                project=str(project), run_root=str(run_root), run_id="fixture",
                request="Build a small typographic experiment.", request_file=None,
                synthetic_validation=True,
            )
        )
        state = load_state(run_root)
        case("start creates one verified S1 packet", len(state["packets"]) == 1 and not TRANSPORT.verify_packet(Path(state["packets"][0]["path"])))
        case("legacy-compatible start records Codex as the default reasoner", REASONERS.selected(state)["id"] == "codex")
        REASONERS.detect = fixture_detect
        try:
            select_reasoner(runtime_args(reasoner="claude", reason="Explicit fixture switch to Claude."))
            claude_state = load_state(run_root)
            claude_entry, claude_packet = current_packet(claude_state)
            claude_manifest = json.loads(read(claude_packet / TRANSPORT.MANIFEST_NAME))
            codex_to_claude = (
                claude_manifest["provider"] == "claude"
                and claude_manifest["parent_evidence_kind"] == "reasoner-switch"
                and not (project / "CLAUDE.md").exists()
            )
            select_reasoner(runtime_args(reasoner="codex", reason="Explicit fixture switch back to Codex."))
            codex_state = load_state(run_root)
            _codex_entry, codex_packet = current_packet(codex_state)
            codex_manifest = json.loads(read(codex_packet / TRANSPORT.MANIFEST_NAME))
            claude_to_codex = (
                codex_manifest["provider"] == "codex"
                and codex_manifest["parent_id"] == claude_entry["id"]
                and codex_manifest["parent_evidence_kind"] == "reasoner-switch"
            )
        finally:
            REASONERS.detect = real_detect
        case("Codex to Claude creates a linked provider-neutral S1 child", codex_to_claude)
        case("Claude to Codex continues from durable S1 state", claude_to_codex)
        fallback_project = workspace / "fallback-project"
        fallback_run = workspace / "fallback-run"
        REASONERS.detect = fixture_detect
        try:
            start(argparse.Namespace(
                project=str(fallback_project), run_root=str(fallback_run), run_id="fallback",
                request="Test safe reasoner fallback.", request_file=None, reasoner="claude",
                adopt_existing=False, synthetic_validation=True,
            ))
            fallback_result = record_reasoner_failure(argparse.Namespace(
                run_root=str(fallback_run), project=None,
                summary="Fixture Claude session stopped before writing output.", evidence="blocked",
            ))
            fallback_state = load_state(fallback_run)
            _fallback_entry, fallback_packet = current_packet(fallback_state)
            fallback_manifest = json.loads(read(fallback_packet / TRANSPORT.MANIFEST_NAME))
        finally:
            REASONERS.detect = real_detect
        case(
            "empty Claude failure falls back to a linked Codex retry",
            fallback_result == 0
            and fallback_manifest["provider"] == "codex"
            and fallback_manifest["parent_evidence_kind"] == "reasoner-failure"
            and REASONERS.selected(fallback_state)["id"] == "codex",
        )

        material_project = workspace / "material-failure-project"
        material_run = workspace / "material-failure-run"
        REASONERS.detect = fixture_detect
        try:
            start(argparse.Namespace(
                project=str(material_project), run_root=str(material_run), run_id="material",
                request="Test material reasoner failure.", request_file=None, reasoner="claude",
                adopt_existing=False, synthetic_validation=True,
            ))
            (material_project / "PROJECT.md").write_text(
                "# PROJECT\n\nPartial provider output.\n", encoding="utf-8"
            )
            material_result = record_reasoner_failure(argparse.Namespace(
                run_root=str(material_run), project=None,
                summary="Fixture Claude stopped after writing a partial brief.", evidence="blocked",
            ))
            material_state = load_state(material_run)
        finally:
            REASONERS.detect = real_detect
        case(
            "material Claude failure pauses without automatic creative replacement",
            material_result == 2
            and len(material_state["packets"]) == 1
            and REASONERS.selected(material_state)["id"] == "claude"
            and (Path(material_state["packets"][0]["path"]) / "evidence" / "reasoner-failure.json").is_file(),
        )
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
        self_test_creative_assessment = workspace / "fixture-assessment.json"
        write_json(self_test_creative_assessment, CREATIVE.low_assessment())
        creative_plan(argparse.Namespace(
            run_root=str(run_root), project=None, input=str(self_test_creative_assessment)
        ))
        # The fixture records the S3 direction work here, with real project-local
        # artifacts, so the ledger the S3 packet delivers is stable for the rest of
        # the fixture. A live project records these events during the S3 session;
        # what matters for policy is that the creative-evidence contract is
        # satisfied before G1 on every continuation path.
        direction_note = project / ".ariadne" / "creative" / "design-direction.md"
        direction_note.parent.mkdir(parents=True, exist_ok=True)
        direction_note.write_text(
            "# Direction note\n\nA speaking line makes sound visible through one typographic gesture.\n",
            encoding="utf-8",
        )
        direction_invocation = project / ".ariadne" / "creative" / "design-direction-invocation.md"
        direction_invocation.write_text(
            "# Design direction work log\n\nFixture record of the S3 direction work.\n",
            encoding="utf-8",
        )
        direction_events = workspace / "direction-events.json"
        write_json(direction_events, {"events": [
            {"type": "skill", "skill": "design-direction", "state": "invoked",
             "evidence_path": str(direction_invocation)},
            {"type": "skill", "skill": "design-direction", "state": "completed",
             "output_path": str(direction_note),
             "result": "Direction selected and recorded for the G1 decision.",
             "usefulness": "useful"},
            {"type": "direction", "id": "direction-a",
             "thesis": "A speaking line makes sound visible through one typographic gesture.",
             "mechanism": "A single line crosses a listening boundary.",
             "experience": "The page answers only while someone speaks.",
             "status": "selected"},
        ]})
        record_creative(argparse.Namespace(
            run_root=str(run_root), project=None, input=str(direction_events)
        ))

        def fixture_skill_evidence(events_name, skill, output_path, result):
            """Record one selected skill's execution exactly as a live session would."""
            invocation = Path(output_path)
            path = workspace / events_name
            write_json(path, {"events": [
                {"type": "skill", "skill": skill, "state": "invoked",
                 "evidence_path": str(invocation)},
                {"type": "skill", "skill": skill, "state": "completed",
                 "output_path": str(output_path), "result": result, "usefulness": "useful"},
            ]})
            return record_creative(argparse.Namespace(
                run_root=str(run_root), project=None, input=str(path)
            ))

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

        rejected_design = read(project / "DESIGN.md")
        rejected_reason = "The speaking line is decorative; replace the organising concept."
        rejected_entry = _entry
        restart_direction(runtime_args(reason=rejected_reason))
        state = load_state(run_root)
        retry_entry, retry_packet = current_packet(state, allow_project_drift=True)
        retry_manifest = json.loads(read(retry_packet / TRANSPORT.MANIFEST_NAME))
        restart_source = next(
            (
                source for source in retry_manifest["sources"]
                if source["kind"] == "continuation-restart-context"
            ),
            None,
        )
        restart_path = Path(restart_source["path"]) if restart_source else None
        restart_text = read(restart_path) if restart_path and restart_path.is_file() else ""
        case(
            "rejected direction restart creates a linked same-stage child",
            retry_entry["stage"] == "S3"
            and retry_manifest["retry"] is True
            and retry_manifest["parent_id"] == rejected_entry["id"],
        )
        case(
            "rejected direction and human reason are preserved verbatim",
            rejected_reason in restart_text
            and rejected_design.rstrip() in restart_text
            and restart_text.count("===== BEGIN REJECTED DESIGN.md =====") == 1
            and restart_text.count("===== END REJECTED DESIGN.md =====") == 1,
        )
        case(
            "restart context is delivered with verified provenance",
            restart_source is not None
            and not TRANSPORT.verify_packet(retry_packet)
            and "rejected S3 direction and human restart reason" in read(
                retry_packet / TRANSPORT.PACKET_NAME
            ),
        )
        case(
            "restart keeps G1 unresolved and records the rejection",
            not re.search(r"(?im)^\*\*Status:\*\*.*locked at G1", read(project / "DESIGN.md"))
            and not any(
                row.get("category") == "creative-decision" and row.get("status") == "resolved"
                for row in state["human_interventions"]
            )
            and any(note["kind"] == "rejected-direction" for note in state["notes"]),
        )
        REASONERS.detect = fixture_detect
        try:
            select_reasoner(runtime_args(
                reasoner="claude",
                reason="Continue the rejected-direction retry with the alternate reasoner.",
            ))
            state = load_state(run_root)
            switched_restart_entry, switched_restart_packet = current_packet(
                state, allow_project_drift=True
            )
            switched_restart_manifest = json.loads(
                read(switched_restart_packet / TRANSPORT.MANIFEST_NAME)
            )
            restart_switch_preserved = (
                switched_restart_manifest["provider"] == "claude"
                and switched_restart_manifest["parent_id"] == retry_entry["id"]
                and any(
                    source.get("kind") == "continuation-restart-context"
                    for source in switched_restart_manifest["sources"]
                )
            )
            select_reasoner(runtime_args(
                reasoner="codex", reason="Return the fixture to its default reasoner."
            ))
            state = load_state(run_root)
        finally:
            REASONERS.detect = real_detect
        case(
            "reasoner switch preserves rejected-direction context and restart boundary",
            restart_switch_preserved,
        )

        (project / "DESIGN.md").write_text(
            "# DESIGN\n\n**Status:** locked at G1 on 2026-08-23\n\n"
            "## Design thesis\n\n"
            "**A speaking line makes sound visible through one typographic gesture.**\n\n"
            "**The tension:** archival but immediate.\n\n"
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
            "| none | yes | no asset required | no |\n\n"
            "## Anti-patterns for this project\n\n"
            "1. Do not add a waveform visualiser; it is the generic shorthand for sound.\n"
            "2. Do not animate the whole line; the gesture is the boundary crossing only.\n"
            "3. Do not introduce a second accent colour; one gesture carries the meaning.\n\n"
            "## G1 direction check\n\n"
            "| # | Check | Y/N | If no, why not |\n|---|---|---|---|\n"
            "| 1 | Thesis tells you what to do about a hero image | y | |\n"
            "| 2 | No banned mood words | y | |\n"
            "| 3 | Type ratio at least 4x | y | |\n"
            "| 4 | Palette has a stated source | y | |\n"
            "| 5 | Motion has one of the five purposes | y | |\n"
            "| 6 | Signature moment named, with a mobile equivalent | y | |\n"
            "| 7 | Three or more specific rejections | y | |\n"
            "| 8 | All asset dependencies resolved | y | |\n"
            "| 9 | Survives the swap test | y | |\n"
            "| 10 | Closest anti-generic row named, and why it is not that | y | |\n",
            encoding="utf-8",
        )
        (project / "AGENTS.md").write_text(
            "## Current state\n\n| **Stage** | `S3` |\n| **Last gate passed** | `G1` |\n"
            "| **Next prompt** | `prompts/build-kickoff.md` |\n",
            encoding="utf-8",
        )
        # The direction work is recorded with real, project-local artifacts before
        # the human decision, because the approval binds to the evaluated revision.
        approve_gate(argparse.Namespace(
            run_root=str(run_root), project=None, gate="G1", identity="self-test-operator",
            note="Fixture: the human operator locks the direction.", migrate=False,
        ))
        state = load_state(run_root)
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
        # AR-202 T1: entering S4B requires evidence that the S4A implementation
        # planning actually ran, so the fixture records it where an S4A session would.
        fixture_skill_evidence(
            "planning-events.json", "implementation-planning", project / "HANDOFF.md",
            "The handoff became the bounded build context.",
        )
        provider_preflight(runtime_args(availability="available", quota="sufficient"))
        state = load_state(run_root)
        case(
            "provider routing is read from HANDOFF.md",
            state["provider_preflight"]["provider"] == "Cursor"
            and state["provider_preflight"]["decision"] == "verified",
        )
        prepare_next(runtime_args())
        state = load_state(run_root)
        s4b_entry, s4b_packet = current_packet(state)
        s4b_manifest = json.loads(read(s4b_packet / TRANSPORT.MANIFEST_NAME))
        case(
            "cleared preflight prepares a Cursor-labelled S4B packet",
            s4b_entry["stage"] == "S4B" and s4b_manifest["provider"] == "Cursor",
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

        transcript_only = s4b_packet / "evidence" / "transcript.md"
        transcript_only.write_text("S4B fixture transcript without a structured return.\n", encoding="utf-8")
        (project / "QA.md").write_text(
            "# QA\n\n## Mechanical\n\n| # | Check | Result | Evidence |\n|---|---|---|---|\n"
            "| 1 | Build | pass | fixture |\n\n## Judgement\n\nPending.\n\n"
            "## Screenshots\n\n| View | Path |\n|---|---|\n| Fixture | none |\n",
            encoding="utf-8",
        )
        case(
            "S4B transcript and QA cannot replace the structured implementation return",
            infer_next_stage(load_state(run_root))[0] is None,
        )
        transcript_only.unlink()

        partial_path = s4b_packet / "evidence" / "return-handoff.md"
        partial_path.write_text(filled_return("blocked", s4b_entry["id"]), encoding="utf-8")
        blocked_advance_result = advance(runtime_args())
        case(
            "blocked worker return stops without an automatic retry",
            blocked_advance_result == 2
            and current_packet(load_state(run_root), allow_project_drift=True)[0]["id"] == s4b_entry["id"],
        )
        partial_path.write_text(filled_return("partial", s4b_entry["id"]), encoding="utf-8")
        (project / "QA.md").write_text(
            "# QA\n\n## Mechanical\n\n| # | Check | Result | Evidence |\n|---|---|---|---|\n"
            "| 1 | Build | pass | fixture |\n\n## Judgement\n\nPending.\n\n"
            "## Screenshots\n\n| View | Path |\n|---|---|\n| Fixture | none |\n",
            encoding="utf-8",
        )
        partial_hash = sha256(partial_path)
        REASONERS.detect = fixture_detect
        try:
            select_reasoner(runtime_args(
                reasoner="claude",
                reason="Use Claude for the next reasoning boundary after the partial build returns.",
            ))
        finally:
            REASONERS.detect = real_detect
        queued_state = load_state(run_root)
        queued_entry, queued_packet = current_packet(queued_state, allow_project_drift=True)
        queued_manifest = json.loads(read(queued_packet / TRANSPORT.MANIFEST_NAME))
        case(
            "reasoner switch cannot rewrite a partial Cursor implementation boundary",
            queued_entry["id"] == s4b_entry["id"]
            and queued_manifest["provider"] == "Cursor"
            and sha256(partial_path) == partial_hash
            and REASONERS.selected(queued_state)["id"] == "claude",
        )
        REASONERS.detect = fixture_detect
        try:
            select_reasoner(runtime_args(
                reasoner="codex", reason="Return the next reasoning boundary to Codex."
            ))
        finally:
            REASONERS.detect = real_detect
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
        unexpected_return = project / ".ariadne" / "returns" / "wrong-packet.md"
        unexpected_return.parent.mkdir(parents=True, exist_ok=True)
        unexpected_return.write_text(filled_return(task_id="wrong-packet"), encoding="utf-8")
        advance_result = advance(runtime_args())
        case(
            "an unrelated project return cannot be ingested as the current packet",
            advance_result == 2
            and not (retry_packet / "evidence" / "return-handoff.md").exists(),
        )
        unexpected_return.unlink()
        expected_return = Path(retry_manifest["return_target"])
        expected_return.write_text(filled_return(task_id=retry_entry["id"]), encoding="utf-8")
        # AR-202 T1: entering S5 requires evidence that the S4B QA work ran and
        # that the approved requirements carry an implementation trace. The
        # fixture records both of them before the build boundary closes.
        fixture_skill_evidence(
            "qa-events.json", "QA", project / "QA.md",
            "Mechanical QA evidence was recorded for the reviewed revision.",
        )
        fixture_operations = OPERATIONS.load_ledger(project)
        fixture_implementation_events = workspace / "implementation-events.json"
        write_json(fixture_implementation_events, {"events": [
            {
                "type": "implementation", "requirement_id": item["id"], "status": "implemented",
                "summary": f"Fixture recorded the implementation of {item['id']} in the build.",
                "source_path": str(project / "HANDOFF.md"),
            }
            for item in fixture_operations["requirements"]
        ]})
        record_operations(argparse.Namespace(
            run_root=str(run_root), project=None, input=str(fixture_implementation_events)
        ))
        advance(
            runtime_args(
                target="http://127.0.0.1:3000",
                lenses="creative-director (light)",
            )
        )
        state = load_state(run_root)
        external = next(
            (
                item for item in state["human_interventions"]
                if item["need"] in {
                    "Start the selected external implementation worker.",
                    "Start the selected external implementation provider.",
                }
            ),
            {"status": "missing"},
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
        telemetry_path = run_root / TELEMETRY_NAME
        telemetry_rows = [
            json.loads(line) for line in read(telemetry_path).splitlines()
        ] if telemetry_path.is_file() else []
        case(
            "worker telemetry records validation and preserves unavailable usage as unknown",
            any(
                row.get("event") == "worker-validation"
                and row.get("usage") == "unknown"
                and row.get("cost") == "unknown"
                for row in telemetry_rows
            ),
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
        REASONERS.detect = fixture_detect
        try:
            select_reasoner(runtime_args(
                reasoner="claude", reason="Run the isolated review with the alternate reasoner."
            ))
            state = load_state(run_root)
            _s5_entry, s5_packet = current_packet(state)
            s5_manifest = json.loads(read(s5_packet / TRANSPORT.MANIFEST_NAME))
            delivered = [
                source["label"] for source in s5_manifest["sources"]
                if source.get("delivered", True)
            ]
            s5_claude_isolated = (
                s5_manifest["provider"] == "claude"
                and delivered == ["current S5 prompt block", "EVALUATION-RUBRICS.md"]
            )
        finally:
            REASONERS.detect = real_detect
        case("Claude S5 retry preserves independent-review isolation", s5_claude_isolated)
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
        auto_run = workspace / "ordinary-idea-ariadne"
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

        # Model routing intelligence scenarios
        rec_s1 = recommend_task_routing({
            "task_type": "reasoning",
            "complexity": "low",
            "ambiguity": "low",
            "consequence": "low",
            "reversibility": "high",
        })
        case(
            "routing scenario 1: simple reasoning selects cheap R1 with bounded effort",
            rec_s1["capability_class"] == "R1"
            and rec_s1["model"] == "GPT-5.6 Luna"
            and rec_s1["effort"] in ("low", "medium"),
        )

        rec_s2 = recommend_task_routing({
            "task_type": "reasoning",
            "stage": "S3",
            "complexity": "high",
            "ambiguity": "high",
            "consequence": "high",
            "reversibility": "low",
        })
        case(
            "routing scenario 2: complex architecture selects stronger R1 with high effort",
            rec_s2["capability_class"] == "R1"
            and rec_s2["model"] == "GPT-5.6 Sol"
            and rec_s2["effort"] == "high",
        )

        rec_s3 = recommend_task_routing({
            "task_type": "reasoning",
            "complexity": "novel",
            "ambiguity": "high",
            "consequence": "high",
        })
        case(
            "routing scenario 3: novel high-consequence reasoning selects strongest model",
            rec_s3["capability_class"] == "R1"
            and rec_s3["model"] == "GPT-6 Astra"
            and rec_s3["effort"] in ("high", "xhigh", "max"),
        )

        rec_s4 = recommend_task_routing({
            "task_type": "implementation",
            "stage": "S4B",
        })
        case(
            "routing scenario 4: clear implementation selects R2 not R1",
            rec_s4["capability_class"] == "R2"
            and rec_s4["model"] == "implementation-worker (default implementation model)",
        )

        rec_s5 = recommend_task_routing({
            "task_type": "mechanical",
        })
        case(
            "routing scenario 5: mechanical check selects R6 not R1",
            rec_s5["capability_class"] == "R6",
        )

        rec_s6 = recommend_task_routing({
            "task_type": "reasoning",
            "same_objective": True,
            "context_state": "useful",
        })
        case(
            "routing scenario 6: same objective with useful context recommends continue",
            rec_s6["session"] == "Continue",
        )

        rec_s7 = recommend_task_routing({
            "task_type": "reasoning",
            "stage": "S5",
            "context_state": "independent_required",
        })
        case(
            "routing scenario 7: independent review recommends new session",
            rec_s7["session"] == "New",
        )

        rec_s8 = recommend_task_routing({
            "task_type": "reasoning",
            "context_state": "noisy",
        })
        case(
            "routing scenario 8: context drift and noise recommends new session",
            rec_s8["session"] == "New",
        )

        rec_s9 = recommend_task_routing({
            "task_type": "reasoning",
            "complexity": "high",
            "provider_available": False,
        })
        case(
            "routing scenario 9: provider unavailable falls back without weakening capability",
            rec_s9["capability_class"] == "R1"
            and rec_s9["model"] == "configured reasoning fallback",
        )

        rec_s10 = recommend_task_routing({
            "task_type": "implementation",
            "runtime_model": "Grok",
        })
        case(
            "routing scenario 10: implementation supports runtime model selection",
            rec_s10["capability_class"] == "R2"
            and "Grok" in rec_s10["model"],
        )

        rec_s11 = recommend_task_routing({
            "task_type": "reasoning",
            "complexity": "medium",
            "ambiguity": "medium",
            "consequence": "medium",
        })
        case(
            "routing scenario 11: standard task avoids over-routing to maximum effort",
            rec_s11["effort"] == "medium",
        )

        rec_s12 = recommend_task_routing({
            "task_type": "implementation",
            "escalated": True,
        })
        case(
            "routing scenario 12: unsafe or failing implementation escalates to R1 deep reasoning",
            rec_s12["capability_class"] == "R1"
            and rec_s12["model"] == "GPT-5.6 Sol"
            and rec_s12["effort"] == "high",
        )

        # Decision boundary tests: each pair differs in exactly one dimension,
        # and that single change must flip the routing output.

        # Boundary A: consequence medium -> high flips model from Terra to Sol
        boundary_base_a = {
            "task_type": "reasoning", "complexity": "medium",
            "ambiguity": "low", "consequence": "medium", "reversibility": "medium",
        }
        boundary_flip_a = dict(boundary_base_a, consequence="high")
        rec_ba_base = recommend_task_routing(boundary_base_a)
        rec_ba_flip = recommend_task_routing(boundary_flip_a)
        case(
            "boundary: consequence medium->high flips from cheaper to Sol",
            rec_ba_base["model"] == "GPT-5.6 Terra"
            and rec_ba_flip["model"] == "GPT-5.6 Sol",
        )

        # Boundary B: context_state useful -> noisy flips session Continue -> New
        boundary_base_b = {
            "task_type": "reasoning", "same_objective": True,
            "context_state": "useful",
        }
        boundary_flip_b = dict(boundary_base_b, context_state="noisy")
        rec_bb_base = recommend_task_routing(boundary_base_b)
        rec_bb_flip = recommend_task_routing(boundary_flip_b)
        case(
            "boundary: context_state useful->noisy flips session Continue->New",
            rec_bb_base["session"] == "Continue"
            and rec_bb_flip["session"] == "New",
        )

        # Boundary C: complexity high -> novel flips model from Sol to Astra
        boundary_base_c = {
            "task_type": "reasoning", "complexity": "high",
            "ambiguity": "high", "consequence": "high", "reversibility": "low",
        }
        boundary_flip_c = dict(boundary_base_c, complexity="novel")
        rec_bc_base = recommend_task_routing(boundary_base_c)
        rec_bc_flip = recommend_task_routing(boundary_flip_c)
        case(
            "boundary: complexity high->novel flips model from Sol to Astra",
            rec_bc_base["model"] == "GPT-5.6 Sol"
            and rec_bc_flip["model"] == "GPT-6 Astra",
        )

        # Boundary D: escalated False -> True flips capability R2 -> R1
        boundary_base_d = {"task_type": "implementation", "escalated": False}
        boundary_flip_d = dict(boundary_base_d, escalated=True)
        rec_bd_base = recommend_task_routing(boundary_base_d)
        rec_bd_flip = recommend_task_routing(boundary_flip_d)
        case(
            "boundary: escalated false->true flips capability R2->R1",
            rec_bd_base["capability_class"] == "R2"
            and rec_bd_flip["capability_class"] == "R1",
        )

        # Boundary E: same_objective True -> False flips session Continue -> New
        boundary_base_e = {
            "task_type": "reasoning", "same_objective": True,
            "context_state": "useful",
        }
        boundary_flip_e = dict(boundary_base_e, same_objective=False)
        rec_be_base = recommend_task_routing(boundary_base_e)
        rec_be_flip = recommend_task_routing(boundary_flip_e)
        case(
            "boundary: same_objective true->false flips session Continue->New",
            rec_be_base["session"] == "Continue"
            and rec_be_flip["session"] == "New",
        )

        # Boundary F: reversibility medium -> low flips model from cheaper to Sol
        boundary_base_f = {
            "task_type": "reasoning", "complexity": "medium",
            "ambiguity": "low", "consequence": "medium", "reversibility": "medium",
        }
        boundary_flip_f = dict(boundary_base_f, reversibility="low")
        rec_bf_base = recommend_task_routing(boundary_base_f)
        rec_bf_flip = recommend_task_routing(boundary_flip_f)
        case(
            "boundary: reversibility medium->low flips from cheaper to Sol",
            rec_bf_base["model"] == "GPT-5.6 Terra"
            and rec_bf_flip["model"] == "GPT-5.6 Sol",
        )

        # Cost boundaries: the two gates must not escalate on one elevated signal alone.

        # A. Normal bounded reasoning stays on the cheapest R1 model at low effort.
        rec_cheap = recommend_task_routing({
            "task_type": "reasoning", "complexity": "low",
            "ambiguity": "low", "consequence": "low", "reversibility": "high",
        })
        case(
            "cost: bounded low-stakes reasoning stays on Luna at low effort",
            rec_cheap["model"] == "GPT-5.6 Luna" and rec_cheap["effort"] == "low",
        )

        # B. Moderate complexity reaches Terra, not Sol.
        rec_moderate = recommend_task_routing({
            "task_type": "reasoning", "complexity": "medium",
            "ambiguity": "medium", "consequence": "medium", "reversibility": "medium",
        })
        case(
            "cost: moderate reasoning reaches Terra and not Sol",
            rec_moderate["model"] == "GPT-5.6 Terra"
            and rec_moderate["effort"] == "medium",
        )

        # C. Genuinely exceptional AND high-stakes work is the only route to Astra.
        rec_exceptional = recommend_task_routing({
            "task_type": "reasoning", "complexity": "novel",
            "ambiguity": "high", "consequence": "high", "reversibility": "low",
        })
        case(
            "cost: exceptional high-stakes work reaches Astra at xhigh effort",
            rec_exceptional["model"] == "GPT-6 Astra"
            and rec_exceptional["effort"] == "xhigh",
        )

        # E. Novel but cheap and reversible must NOT buy Astra or maximum effort.
        rec_novel_cheap = recommend_task_routing({
            "task_type": "reasoning", "complexity": "novel",
            "ambiguity": "low", "consequence": "low", "reversibility": "high",
        })
        case(
            "cost: novel but cheap and reversible work does not reach Astra or xhigh",
            rec_novel_cheap["model"] not in ("GPT-6 Astra", "GPT-5.6 Sol")
            and rec_novel_cheap["effort"] in ("low", "medium"),
        )

        # Boundary G: with difficulty held at exceptional, stakes alone decides Astra.
        boundary_base_g = {
            "task_type": "reasoning", "complexity": "novel",
            "ambiguity": "high", "consequence": "medium", "reversibility": "medium",
        }
        boundary_flip_g = dict(boundary_base_g, consequence="high")
        rec_bg_base = recommend_task_routing(boundary_base_g)
        rec_bg_flip = recommend_task_routing(boundary_flip_g)
        case(
            "boundary: exceptional difficulty needs high stakes before Astra is chosen",
            rec_bg_base["model"] == "GPT-5.6 Sol"
            and rec_bg_flip["model"] == "GPT-6 Astra",
        )

        # Boundary H: with stakes held high, difficulty alone decides Terra vs Sol.
        boundary_base_h = {
            "task_type": "reasoning", "complexity": "low",
            "ambiguity": "low", "consequence": "high", "reversibility": "medium",
        }
        boundary_flip_h = dict(boundary_base_h, ambiguity="high")
        rec_bh_base = recommend_task_routing(boundary_base_h)
        rec_bh_flip = recommend_task_routing(boundary_flip_h)
        case(
            "boundary: an isolated high consequence on a trivial task stops at Terra",
            rec_bh_base["model"] == "GPT-5.6 Terra"
            and rec_bh_flip["model"] == "GPT-5.6 Sol",
        )

        # Boundary I: cheap retry damps effort; one step of stakes restores it.
        boundary_base_i = {
            "task_type": "reasoning", "complexity": "high",
            "ambiguity": "low", "consequence": "low", "reversibility": "high",
        }
        boundary_flip_i = dict(boundary_base_i, reversibility="medium")
        rec_bi_base = recommend_task_routing(boundary_base_i)
        rec_bi_flip = recommend_task_routing(boundary_flip_i)
        case(
            "boundary: cheap-retry damping holds effort at medium until stakes rise",
            rec_bi_base["model"] == "GPT-5.6 Terra"
            and rec_bi_base["effort"] == "medium"
            and rec_bi_flip["model"] == "GPT-5.6 Sol"
            and rec_bi_flip["effort"] == "high",
        )

        # A missing middle tier escalates rather than silently under-routing.
        rec_no_terra = recommend_task_routing({
            "task_type": "reasoning", "complexity": "medium",
            "ambiguity": "medium", "consequence": "medium", "reversibility": "medium",
            "terra_available": False,
        })
        case(
            "cost: an unavailable middle tier escalates instead of under-routing",
            rec_no_terra["model"] == "GPT-5.6 Sol",
        )

        # No input combination may produce an effort the target model cannot run.
        effort_supported = {
            "GPT-5.6 Luna": ("low", "medium"),
            "GPT-5.6 Terra": ("low", "medium", "high"),
            "GPT-5.6 Sol": ("low", "medium", "high"),
            "GPT-6 Astra": ("low", "medium", "high", "xhigh", "max"),
        }
        surface = [
            recommend_task_routing({
                "task_type": "reasoning", "complexity": cx, "ambiguity": am,
                "consequence": cq, "reversibility": rv,
                "visual_creative_importance": vi, "context_requirements": cr,
            })
            for cx in ("low", "medium", "high", "novel", "extreme")
            for am in ("low", "medium", "high")
            for cq in ("low", "medium", "high")
            for rv in ("low", "medium", "high")
            for vi in ("low", "high")
            for cr in ("low", "medium", "high")
        ]
        case(
            "cost: no routing combination recommends an unsupported effort level",
            all(
                item["effort"] in effort_supported[item["model"]]
                for item in surface
                if item["model"] in effort_supported
            ),
        )
        # The anti-regression invariant for the two gates: starting from a minimal task,
        # raising exactly one dimension to its most elevated value must never reach the
        # top tier or maximum effort. Restoring any single-signal OR escalation (such as
        # "novel implies Astra") makes this fail.
        single_signal_base = {
            "task_type": "reasoning", "complexity": "low", "ambiguity": "low",
            "consequence": "low", "reversibility": "high",
            "visual_creative_importance": "low", "context_requirements": "low",
        }
        single_signal = [
            recommend_task_routing(dict(single_signal_base, **{key: value}))
            for key, value in (
                ("complexity", "extreme"), ("ambiguity", "high"),
                ("consequence", "high"), ("reversibility", "low"),
                ("visual_creative_importance", "high"), ("context_requirements", "high"),
            )
        ]
        case(
            "cost: no single elevated dimension alone reaches the top model or effort",
            all(
                item["model"] in ("GPT-5.6 Luna", "GPT-5.6 Terra")
                and item["effort"] not in ("xhigh", "max")
                for item in single_signal
            ),
        )
        case(
            "cost: two elevated dimensions are required before Astra is reachable",
            any(item["model"] == "GPT-6 Astra" for item in surface)
            and recommend_task_routing(dict(
                single_signal_base, complexity="extreme", consequence="high",
            ))["model"] == "GPT-6 Astra",
        )

        # Staleness: the model landscape marker classifies where the name came from
        # and never claims verification.
        case(
            "staleness: model landscape evidence distinguishes dated, reported, and n/a",
            rec_s1.get("model_landscape_dated") == MODEL_LANDSCAPE_DATED
            and rec_s1.get("model_landscape_evidence") == "unverified"
            and rec_s5.get("model_landscape_evidence") == "not-applicable"
            and rec_s5.get("model_landscape_dated") is None
            and rec_s10.get("model_landscape_evidence") == "operator-reported"
            and rec_s10.get("model_landscape_dated") is None
            and all(
                item.get("model_landscape_evidence") != "verified" for item in surface
            ),
        )

    print("ARIADNE RUNTIME SELF-TEST\n")
    for name, passed in cases:
        print(("ok    " if passed else "FAIL  ") + name)
    failed = [name for name, passed in cases if not passed]
    print(f"\n{'FAILED' if failed else 'PASS'}  {len(cases) - len(failed)}/{len(cases)}")
    return 1 if failed else 0


def execution_status_command(args: argparse.Namespace) -> int:
    """Show what the engine created, routed, decided and failed. Read-only."""
    run_root, state = resolve_and_load(args)
    report = EXECUTION.status_report(state)
    context_decision = ROUTING.latest(state, "context_decisions")
    payload = {
        "run_id": state.get("run_id"),
        "executions": report["executions"],
        "open_executions": report["open"],
        "rows": report["rows"],
        "failures": report["failures"],
        "failure_classes": report["failure_classes"],
        "characterisation": ROUTING.latest(state, "characterisations"),
        "routing": ROUTING.latest(state, "routing_decisions"),
        "context": CONTEXT.summarise(context_decision) if context_decision else {},
        "context_policy_version": CONTRACTS.POLICY_VERSION,
        "events": EVENTS.summarise(run_root),
        "recoveries": [item for item in (state.get("recoveries") or []) if isinstance(item, dict)],
    }
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0
    print(f"Executions: {report['executions']} recorded, {report['open']} open.")
    for row in report["rows"][-8:]:
        mismatch = " (requested/reported mismatch)" if row.get("mismatch") else ""
        print(f"  {row['execution_id']} {row['role']} {row['state']} task={row['task_id']}{mismatch}")
    characterisation = payload["characterisation"]
    if characterisation:
        print(
            f"Task: {characterisation['task_type']['value']}; difficulty "
            f"{characterisation['difficulty']['value']}; stakes {characterisation['stakes']['value']}."
        )
    routing = payload["routing"]
    if routing:
        print(f"Route: {ROUTING.describe(routing)}")
    if payload["context"]:
        print("Context: " + CONTEXT.describe(context_decision))
    if report["failure_classes"]:
        print("Failure classes recorded: " + ", ".join(report["failure_classes"]))
    print(f"Engine events: {payload['events']['events']} in {payload['events']['path']}")
    return 0


def engine_events_command(args: argparse.Namespace) -> int:
    """Print the canonical append-only engine event log."""
    run_root = resolve_run_root(args)
    events = EVENTS.read(run_root, limit=int(getattr(args, "limit", 50) or 50))
    payload = {
        "path": str(EVENTS.log_path(run_root)),
        "integrity_problems": EVENTS.integrity_problems(run_root),
        "events": events,
    }
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0
    print(f"Engine events ({len(events)} shown) — {payload['path']}")
    for event in events:
        execution = f" execution={event.get('execution')}" if event.get("execution") else ""
        print(f"  {event.get('seq')}. {event.get('type')} {event.get('task_id')}{execution}")
    if payload["integrity_problems"]:
        print("Integrity: " + "; ".join(payload["integrity_problems"]))
    return 0


def capability_probe_from_spec(
    spec: dict, *, run_root: Path, reference_adapters: dict, capture_adapters: dict,
):
    """Build one deterministic capability probe from a declared input object."""
    kind = str(spec.get("kind", "") or "")
    family = str(spec.get("family", "tool") or "tool")
    capability_id = str(spec.get("capability_id", "") or "")
    adapter = str(spec.get("adapter", "") or "")
    if kind == "executable":
        return CAPABILITIES.ExecutableProbe(
            str(spec.get("command", "") or capability_id), capability_id=capability_id,
            adapter=adapter, family=family,
        )
    if kind == "fixture-command":
        argv = [str(item) for item in (spec.get("argv") or [])]
        if not argv:
            raise RuntimeError_("a fixture-command probe needs argv")
        probe_root = Path(run_root) / "capability-probes" / (slug(capability_id or argv[0]) or "probe")
        return CAPABILITIES.FixtureCommandProbe(
            argv, cwd=probe_root, capability_id=capability_id or argv[0],
            adapter=adapter, family=family,
            timeout=int(spec.get("timeout", CAPABILITIES.DEFAULT_PROBE_TIMEOUT) or CAPABILITIES.DEFAULT_PROBE_TIMEOUT),
            expect_returncode=int(spec.get("expect_returncode", 0) or 0),
        )
    if kind == "adapter-method":
        pool = {**dict(reference_adapters or {}), **dict(capture_adapters or {})}
        adapter_id = adapter or str(spec.get("adapter_id", "") or "")
        target = pool.get(adapter_id)
        if target is None:
            raise RuntimeError_(
                f"no declared adapter matches {adapter_id!r}; a probe cannot invent an adapter surface"
            )
        return CAPABILITIES.AdapterMethodProbe(target, capability_id, family=family)
    raise RuntimeError_(f"unsupported capability probe kind: {kind!r}")


def capabilities_command(args: argparse.Namespace) -> int:
    """Declare, probe and inspect capability evidence. Read-only unless --input is given."""
    run_root, state = resolve_and_load(args)
    state["run_root"] = str(run_root)
    project = Path(state["project"])
    payload = load_design_input(args.input) if getattr(args, "input", None) else {}
    if payload and not isinstance(payload, dict):
        raise RuntimeError_("capability input must be a JSON object")
    fixture = design_fixture(payload if isinstance(payload, dict) else None)
    reference_adapters, capture_adapters = design_adapters(state, project, fixture)
    declared_rows: list[dict] = []
    probe_rows: list[dict] = []
    for item in (payload.get("declarations") or []) if isinstance(payload, dict) else []:
        record = CAPABILITIES.declare(
            state,
            capability_id=str(item.get("capability_id", "")),
            adapter=str(item.get("adapter", "")),
            family=str(item.get("family", "tool")),
            available=bool(item.get("available", True)),
            reason=str(item.get("reason", "")),
            version=str(item.get("version", "")),
            provider=str(item.get("provider", "")),
            model=str(item.get("model", "")),
            runtime=str(item.get("runtime", "")),
        )
        declared_rows.append(record)
        emit_event(
            run_root, "capability_declared", state=state, task_id=str(item.get("task_id", "") or ""),
            capability=str(record["capability_id"]), adapter=str(record["adapter"]),
            family=str(record["family"]), status=str(record["status"]),
        )
    for item in (payload.get("probes") or []) if isinstance(payload, dict) else []:
        probe = capability_probe_from_spec(
            dict(item), run_root=run_root, reference_adapters=reference_adapters,
            capture_adapters=capture_adapters,
        )
        outcome = CAPABILITIES.run_probe(state, probe)
        probe_rows.append(outcome)
        event_type = "capability_verified" if outcome["status"] == "VERIFIED" else "capability_observed"
        emit_event(
            run_root, event_type, state=state, task_id=str(item.get("task_id", "") or ""),
            capability=str(probe.capability_id), adapter=str(probe.adapter),
            family=str(probe.family), status=str(outcome["status"]),
            mechanism=str(probe.mechanism()), reason=str(outcome.get("reason", "")),
        )
    if declared_rows or probe_rows:
        state["updated_at"] = now()
        write_state(run_root, state)
    family_filter = str(getattr(args, "family", "") or "")
    adapter_filter = str(getattr(args, "adapter", "") or "")
    registry_rows = [
        dict(row) for row in CAPABILITIES.records(state)
        if (not family_filter or str(row.get("family", "")) == family_filter)
        and (not adapter_filter or str(row.get("adapter", "")) == adapter_filter)
    ]
    report = {
        "summary": CAPABILITIES.summarise(state),
        "records": registry_rows,
        "declared": declared_rows,
        "probes": probe_rows,
        "reference_capabilities": REFERENCES.capability_matrix(reference_adapters),
        "capture_capabilities": RENDER.capability_matrix(capture_adapters),
    }
    if getattr(args, "json", False):
        print(json.dumps(report, indent=2, sort_keys=True, default=str))
        return 0
    print(
        f"Capabilities: {report['summary']['records']} observation(s); "
        f"declared {report['summary']['statuses'].get('declared', 0)}, "
        f"available {report['summary']['statuses'].get('available', 0)}, "
        f"exercised {report['summary']['statuses'].get('exercised', 0)}, "
        f"verified {report['summary']['statuses'].get('verified', 0)}, "
        f"unavailable {report['summary']['statuses'].get('unavailable', 0)}."
    )
    for row in registry_rows[-10:]:
        print("  " + CAPABILITIES.describe(row))
    if probe_rows:
        for outcome in probe_rows:
            print(f"  probe {outcome['probe']['probe']} -> {outcome['status']} {outcome.get('reason', '')}".rstrip())
    return 0


def verify_command(args: argparse.Namespace) -> int:
    """Record or inspect a verification claim. A declaration never verifies itself."""
    run_root, state = resolve_and_load(args)
    state["run_root"] = str(run_root)
    if getattr(args, "status", False):
        current = None
        dependency_values = getattr(args, "dependency", None) or []
        if dependency_values:
            current = {}
            for item in dependency_values:
                name, _, value = str(item).partition("=")
                current[name.strip()] = value.strip()
        report = VERIFICATION.status(state, subject=str(getattr(args, "subject", "") or ""), current=current)
        payload = {"status": report, "summary": VERIFICATION.summarise(state)}
        if getattr(args, "json", False):
            print(json.dumps(payload, indent=2, sort_keys=True, default=str))
        else:
            print(f"Verification: {report['level']} across {report['records']} record(s).")
            for row in report["details"][-8:]:
                print(f"  {row['verification_id']} {row['level']} {row['subject']}: {row['claim']}")
        return 0
    payload = load_design_input(args.input) if getattr(args, "input", None) else {}
    if not isinstance(payload, dict) or not payload:
        raise RuntimeError_("verify needs --input with the claim to record, or --status to inspect")
    emit_event(
        run_root, "verification_started", state=state, task_id=str(payload.get("task_id", "") or ""),
        subject=str(payload.get("subject", "")), level=str(payload.get("level", "")),
        execution=str(payload.get("execution", "") or ""),
    )
    try:
        record = VERIFICATION.create(
            state,
            subject=str(payload.get("subject", "")),
            claim=str(payload.get("claim", "")),
            level=str(payload.get("level", "OBSERVED")),
            method=str(payload.get("method", "")),
            execution_id=str(payload.get("execution", "") or ""),
            verifier_execution_id=str(payload.get("verifier_execution", "") or ""),
            revision=str(payload.get("revision", "") or ""),
            evidence=payload.get("evidence") or [],
            reproduced_artifact=payload.get("reproduced_artifact") or None,
            dependencies=payload.get("dependencies") or {},
            limitations=payload.get("limitations") or [],
            task_id=str(payload.get("task_id", "") or ""),
            subject_type=str(payload.get("subject_type", "") or ""),
            observed_anchor=str(payload.get("observed_anchor", "") or ""),
        )
    except CONTRACTS.ContractError as exc:
        emit_event(
            run_root, "verification_failed", state=state, task_id=str(payload.get("task_id", "") or ""),
            subject=str(payload.get("subject", "")), reason=str(exc),
        )
        write_state(run_root, state)
        raise
    event_type = {
        "OBSERVED": "verification_observed",
        "REPRODUCED": "verification_reproduced",
        "INDEPENDENTLY_REPRODUCED": "verification_reproduced",
        "VERIFIED": "verification_reproduced",
    }.get(str(record.get("level", "")), "verification_observed")
    emit_event(
        run_root, event_type, state=state, task_id=str(payload.get("task_id", "") or ""),
        subject=str(record["subject"]), verification=str(record["verification_id"]),
        level=str(record["level"]), execution=str(record.get("execution_id", "")),
    )
    state["updated_at"] = now()
    write_state(run_root, state)
    if getattr(args, "json", False):
        print(json.dumps({"record": record, "summary": VERIFICATION.summarise(state)}, indent=2, sort_keys=True, default=str))
        return 0
    print(f"Recorded {VERIFICATION.describe(record)}")
    return 0


def decision_provider_from_spec(provider_spec: dict | None):
    """Build a decision provider from an offline JSON spec (never a live service)."""
    spec = dict(provider_spec or {"kind": "unavailable"})
    kind = str(spec.get("kind", "unavailable") or "unavailable")
    if kind == "deterministic":
        return DECISIONS.providers.DeterministicProvider(
            script=spec.get("script") or {},
            provider=str(spec.get("provider", "deterministic-fixture") or "deterministic-fixture"),
            model=str(spec.get("model", "scripted-answers") or "scripted-answers"),
            model_version=str(spec.get("model_version", "1") or "1"),
            fail=tuple(str(item) for item in (spec.get("fail") or [])),
            unavailable_reason=str(spec.get("unavailable_reason", "") or ""),
            request_id=str(spec.get("request_id", "req_fixture_00000000") or "req_fixture_00000000"),
            usage=spec.get("usage") or {},
        )
    if kind == "optional":
        return DECISIONS.providers.OptionalProviderAdapter(
            name=str(spec.get("provider", "optional") or "optional"),
            version=str(spec.get("model_version", "") or ""),
        )
    if kind == "jev-shaped-fixture":
        class OfflineFixtureInterface:
            def __init__(self, value):
                self.value = dict(value)

            def describe(self):
                return {
                    "provider": str(self.value.get("provider", "jev-fixture")),
                    "model": str(self.value.get("model", "jev-decision")),
                    "model_version": str(self.value.get("model_version", "0.0.0-fixture")),
                }

            def capabilities(self):
                return {
                    "capabilities": list(self.value.get("capabilities") or []),
                    "max_questions": self.value.get("max_questions", 8),
                }

            def answer(self, request):
                answers = {}
                for question in request.get("questions") or []:
                    scripted = dict(self.value.get("answers") or {}).get(str(question.get("question_id", "")))
                    if scripted is not None:
                        answers[str(question.get("question_id", ""))] = scripted
                return {"answers": answers}

        return DECISIONS.providers.JevShapedAdapter(interface=OfflineFixtureInterface(spec))
    return DECISIONS.providers.UnavailableProvider()


def decide_command(args: argparse.Namespace) -> int:
    """Evaluate, compile, inspect or explain bounded decisions. Never grants authorization."""
    run_root, state = resolve_and_load(args)
    state["run_root"] = str(run_root)
    json_output = bool(getattr(args, "json", False))
    task_id = str(getattr(args, "task_id", "") or "")

    if getattr(args, "explain", False):
        payload = DECISIONS.trace.explain(state, task_id=task_id)
        if json_output:
            print(json.dumps(payload, indent=2, sort_keys=True, default=str))
            return 0
        print(f"Decision trace for task {task_id or '(run)'}:")
        for line in payload["lines"]:
            print("  " + line)
        for reason in payload["answers"]["escalations"]:
            print(f"  escalation: {reason['question_id']} {reason['reason']} -> {reason['next']}")
        if not payload["lines"]:
            print("  (no decision records for this task)")
        return 0

    if getattr(args, "providers", False):
        catalog = {
            "classifications": list(CONTRACTS.DECISION_CLASSIFICATIONS),
            "escalation_reasons": list(CONTRACTS.ESCALATION_REASONS),
            "generation_reasons": list(CONTRACTS.GENERATION_REASONS),
            "projections": DECISIONS.projections.describe(),
            "escalation": DECISIONS.escalation.describe(),
            "integrations": DECISIONS.integrations.describe(),
            "provider_contract": {
                "requirements": DECISIONS.providers.OptionalProviderAdapter().requirements(),
                "capability_shape": sorted(DECISIONS.providers.DEFAULT_CAPABILITIES),
                "jev_shaped": DECISIONS.providers.JEV_SHAPED_CAPABILITIES,
            },
            "configured": DECISIONS.providers.describe(DECISIONS.providers.UnavailableProvider()),
            "note": (
                "provider status is declared capability, not observed quality; no provider is "
                "configured by default and no paid call is ever required"
            ),
        }
        if json_output:
            print(json.dumps(catalog, indent=2, sort_keys=True, default=str))
            return 0
        print("Decision intelligence catalog:")
        for name, values in sorted(catalog["provider_contract"]["jev_shaped"].items()):
            print(f"  provider capability {name}: {values}")
        for contract in catalog["projections"]["contracts"]:
            print(f"  projection {contract['contract_id']} v{contract['version']}: required={contract['required']}")
        for integration in catalog["integrations"]["integrations"]:
            print(f"  integration {integration['name']}: {integration['entry_point']}")
        print(f"  escalation ladder: {' -> '.join(catalog['escalation']['ladder'])}")
        print("  " + catalog["note"])
        return 0

    if getattr(args, "inspect", False):
        payload = {
            "summary": DECISIONS.batch.summarise(state),
            "trace": DECISIONS.batch.trace(state, task_id=task_id),
        }
        if json_output:
            print(json.dumps(payload, indent=2, sort_keys=True, default=str))
        else:
            print(
                f"Decisions: {payload['summary']['decisions']} record(s) in "
                f"{payload['summary']['batches']} batch(es)."
            )
            for row in payload["trace"][-8:]:
                verdict = (row.get("policy_verdict") or {}).get("reason", "")
                print(f"  {row['decision_id']} {row['question_id']} {row['status']} answer={row['answer']!r} {verdict}")
        return 0

    payload = load_design_input(args.input) if getattr(args, "input", None) else {}
    if not isinstance(payload, dict) or not payload:
        raise RuntimeError_("decide needs --input with the work to perform, or --inspect/--explain")
    document = payload.get("input", payload) if isinstance(payload.get("input"), dict) else payload
    provider = decision_provider_from_spec(document.get("provider"))

    if getattr(args, "compile", False):
        plan = DECISIONS.compiler.compile_plan(
            state,
            requirements=document.get("requirements") or [],
            facts=document.get("facts") or {},
            task_id=str(document.get("task_id", "") or task_id),
            stage=str(document.get("stage", "") or ""),
            stakes=str(document.get("stakes", "LOW") or "LOW"),
            protected_actions=document.get("protected_actions") or (),
            generative_available=bool(document.get("generative_available", False)),
            decision_provider=provider,
        )
        emit_event(
            run_root, "decision_plan_compiled", state=state,
            task_id=str(plan.get("task_id", "")), plan=str(plan.get("plan_id", "")),
            classifications=dict(plan.get("classifications") or {}),
            bounded_questions=len(plan.get("bounded_questions") or []),
            generative_needs=len(plan.get("generative_needs") or []),
        )
        if plan.get("fast_path", {}).get("applies"):
            emit_event(
                run_root, "decision_fast_path", state=state,
                task_id=str(plan.get("task_id", "")), plan=str(plan.get("plan_id", "")),
                reason=str(plan["fast_path"].get("reason", "")),
            )
        graph_record = {}
        if getattr(args, "graph", False):
            graph_record = DECISIONS.graph.from_plan(state, plan)
            emit_event(
                run_root, "decision_graph_created", state=state,
                task_id=str(plan.get("task_id", "")), graph=str(graph_record.get("graph_id", "")),
                nodes=len(graph_record.get("nodes") or []),
            )
        state["updated_at"] = now()
        write_state(run_root, state)
        output = {"plan": plan, "graph": graph_record}
        if json_output:
            print(json.dumps(output, indent=2, sort_keys=True, default=str))
            return 0
        print(
            f"Decision plan {plan['plan_id']}: "
            + ", ".join(f"{key}={value}" for key, value in sorted(plan["classifications"].items()))
        )
        for question in plan["bounded_questions"]:
            print(f"  bounded: {question['question_id']} ({question['projection_contract']})")
        for need in plan["generative_needs"]:
            print(f"  generative: {need['requirement_id']} ({need['reason']})")
        for item in plan["protected_actions"]:
            print(f"  human gate: {item['statement']}")
        if graph_record:
            print(f"Decision graph {graph_record['graph_id']}: {len(graph_record['nodes'])} node(s)")
        return 0

    if getattr(args, "advise", ""):
        family = str(args.advise)
        handler = {
            "failure-classification": DECISIONS.integrations.classify_failure,
            "review-escalation": DECISIONS.integrations.review_escalation,
            "evidence-relevance": DECISIONS.integrations.evidence_relevance,
            "route-family": DECISIONS.integrations.route_family,
        }.get(family)
        if handler is None:
            raise RuntimeError_(f"unknown decision advice family: {family}")
        arguments = dict(document.get("args") or {})
        arguments.setdefault("provider", provider)
        arguments.setdefault("task_id", task_id)
        required = {
            "failure-classification": ("source",),
            "review-escalation": (),
            "evidence-relevance": ("requirement", "claim", "provenance", "freshness"),
            "route-family": ("task_kind",),
        }[family]
        missing = [name for name in required if name not in arguments]
        if missing:
            raise RuntimeError_(
                f"decision advice {family!r} needs argument(s): {', '.join(missing)}; "
                'supply them under "args" in the --input document'
            )
        try:
            advice = handler(state, **arguments)
        except TypeError as exc:
            raise RuntimeError_(f"decision advice {family!r} rejected its arguments: {exc}") from exc
        emit_event(
            run_root, "decision_recorded", state=state,
            task_id=str(arguments.get("task_id", "")),
            advice=family, decision=str(advice.get("decision_id", "")),
            status=str(advice.get("source", "")),
        )
        state["updated_at"] = now()
        write_state(run_root, state)
        if json_output:
            print(json.dumps(advice, indent=2, sort_keys=True, default=str))
            return 0
        summary = {
            key: advice.get(key)
            for key in ("class", "escalation", "answer", "family", "source", "reason")
            if advice.get(key) not in (None, "")
        }
        print(f"Decision advice ({family}): " + json.dumps(summary, default=str))
        print("Decision confidence is not authorization; no gate, scope or acceptance is granted here.")
        return 0

    if getattr(args, "justify", False):
        record = DECISIONS.generation.justify(
            state,
            reason=str(document.get("reason", "")),
            task_id=str(document.get("task_id", "") or task_id),
            stage=str(document.get("stage", "") or ""),
            detail=str(document.get("detail", "") or ""),
            requirement_id=str(document.get("requirement_id", "") or ""),
            decision_id=str(document.get("decision_id", "") or ""),
            plan_id=str(document.get("plan_id", "") or ""),
        )
        emit_event(
            run_root, "generation_justified", state=state,
            task_id=str(record.get("task_id", "")), justification=str(record.get("justification_id", "")),
            reason=str(record.get("reason", "")),
        )
        state["updated_at"] = now()
        write_state(run_root, state)
        print(f"Generation justified: {record['reason']} ({record['justification_id']})")
        return 0

    if getattr(args, "outcome", False):
        record = DECISIONS.calibration.record_outcome(
            state,
            decision_id=str(document.get("decision_id", "")),
            category=str(document.get("category", "")),
            evidence=document.get("evidence") or (),
            downstream=document.get("downstream") or {},
            source=str(document.get("source", "engine-observation") or "engine-observation"),
            note=str(document.get("note", "") or ""),
        )
        emit_event(
            run_root, "decision_outcome_recorded", state=state,
            task_id=str(record.get("task_id", "")), outcome=str(record.get("outcome_id", "")),
            decision=str(record.get("decision_id", "")), category=str(record.get("category", "")),
        )
        state["updated_at"] = now()
        write_state(run_root, state)
        print(f"Decision outcome recorded: {record['category']} ({record['outcome_id']})")
        return 0

    if getattr(args, "invalidate_cache", False):
        touched = DECISIONS.cache.invalidate(
            state,
            reason=str(document.get("reason", "")),
            question_id=str(document.get("question_id", "") or ""),
            cache_id=str(document.get("cache_id", "") or ""),
            key=str(document.get("key", "") or ""),
            model_version=str(document.get("model_version", "") or ""),
            superseded_by=str(document.get("superseded_by", "") or ""),
        )
        for cache_id in touched:
            emit_event(
                run_root, "decision_cache_invalidated", state=state,
                task_id=task_id, cache=cache_id, reason=str(document.get("reason", "")),
            )
        state["updated_at"] = now()
        write_state(run_root, state)
        print(f"Invalidated {len(touched)} cached decision(s).")
        return 0

    if payload.get("act"):
        action = dict(payload["act"])
        record = DECISIONS.batch.mark_acted_on(
            state, str(action.get("decision_id", "")), action=str(action.get("action", "")),
            verification_id=str(action.get("verification_id", "") or ""),
        )
        state["updated_at"] = now()
        write_state(run_root, state)
        print(f"Recorded action {record['resulting_action']!r} for {record['decision_id']}.")
        return 0
    questions = [
        DECISIONS.contracts.DecisionQuestion(
            question_id=str(item.get("question_id", "")),
            instructions=str(item.get("instructions", "")),
            primitive=str(item.get("primitive", "ChoiceDecision") or "ChoiceDecision"),
            options=tuple(str(value) for value in (item.get("options") or [])),
            scale=tuple(str(value) for value in (item.get("scale") or [])),
            positive=str(item.get("positive", "yes") or "yes"),
            negative=str(item.get("negative", "no") or "no"),
            max_selections=int(item.get("max_selections", 1) or 1),
            consequence=str(item.get("consequence", "LOW") or "LOW"),
            definition_version=str(item.get("definition_version", "1") or "1"),
        )
        for item in (payload.get("questions") or [])
    ]
    entries = payload.get("projection_entries")
    if entries is None:
        entries = payload.get("projection") or {}
    projection = DECISIONS.batch.project(entries=entries)
    batch = DECISIONS.batch.evaluate(
        state,
        questions=questions,
        projection=projection,
        provider=provider,
        task_id=str(payload.get("task_id", "") or ""),
        stage=str(payload.get("stage", "") or ""),
        execution_id=str(payload.get("execution", "") or ""),
    )
    emit_event(
        run_root, "decision_batch_created", state=state, task_id=str(payload.get("task_id", "") or ""),
        batch=str(batch["batch_id"]), status=str(batch["status"]),
        questions=len(batch["questions"]), provider=str(batch.get("provider", "")),
        model_version=str(batch.get("model_version", "")), state_digest=str(batch.get("state_digest", "")),
    )
    for result in batch.get("results") or []:
        emit_event(
            run_root, "decision_recorded", state=state, task_id=str(payload.get("task_id", "") or ""),
            batch=str(batch["batch_id"]), decision=str(result.get("decision_id", "")),
            question=str(result.get("question_id", "")), status=str(result.get("status", "")),
            answer=str(result.get("answer", "")), confidence_kind=str(result.get("confidence_kind", "")),
        )
        record = DECISIONS.batch.decision(state, str(result.get("decision_id", "")))
        if record is not None and str(record.get("status")) == "refused":
            emit_event(
                run_root, "decision_low_confidence", state=state, task_id=str(payload.get("task_id", "") or ""),
                decision=str(record.get("decision_id", "")), question=str(record.get("question_id", "")),
                reason=str((record.get("policy_verdict") or {}).get("reason", "")),
            )
    if batch.get("status") in ("failed", "unavailable"):
        emit_event(
            run_root, "decision_failed", state=state, task_id=str(payload.get("task_id", "") or ""),
            batch=str(batch["batch_id"]), status=str(batch["status"]),
            reason=str(batch.get("provider_reason", "")),
        )
    state["updated_at"] = now()
    write_state(run_root, state)
    if json_output:
        print(json.dumps(batch, indent=2, sort_keys=True, default=str))
        return 0 if batch.get("status") in ("answered", "partial") else 2
    print(f"Decision batch {batch['batch_id']}: {batch['status']} ({batch.get('provider')} {batch.get('model_version')})")
    for result in batch.get("results") or []:
        print(
            f"  {result['question_id']}: {result['status']} answer={result['answer']!r} "
            f"confidence={result['confidence']} ({result['confidence_kind']})"
        )
    if batch.get("provider_reason"):
        print("  reason: " + str(batch["provider_reason"]))
    print("Decision confidence is not authorization; no gate, scope or acceptance is granted here.")
    return 0 if batch.get("status") in ("answered", "partial") else 2


def decision_trace_command(args: argparse.Namespace) -> int:
    """The read-only why-did-Ariadne view, derived from records. Never writes."""
    run_root, state = resolve_and_load(args)
    state["run_root"] = str(run_root)
    task_id = str(getattr(args, "task_id", "") or "")
    payload = DECISIONS.trace.explain(state, task_id=task_id)
    if getattr(args, "json", False):
        print(json.dumps(payload, indent=2, sort_keys=True, default=str))
        return 0
    print(f"Decision trace for task {task_id or '(run)'}:")
    for line in payload["lines"]:
        print("  " + line)
    if not payload["lines"]:
        print("  (no decision records for this task)")
    for reason in payload["answers"]["escalations"]:
        print(f"  escalation: {reason['question_id']} {reason['reason']} -> {reason['next']}")
    return 0


def provenance_command(args: argparse.Namespace) -> int:
    """Inspect engine-bound execution provenance. Read-only unless an observation is recorded."""
    run_root, state = resolve_and_load(args)
    execution_id = str(getattr(args, "execution", "") or "")
    source = str(getattr(args, "provider_source", "") or "")
    if source:
        if not execution_id:
            raise RuntimeError_("recording a provider observation needs --execution")
        observation = PROVENANCE.record_provider_observation(
            state, execution_id,
            provider=str(getattr(args, "provider_name", "") or ""),
            model=str(getattr(args, "provider_model", "") or ""),
            request_id=str(getattr(args, "provider_request_id", "") or ""),
            run_id=str(getattr(args, "provider_run_id", "") or ""),
            source=source,
        )
        emit_event(
            run_root, "execution_identity_observed", state=state, execution=execution_id,
            provider=str(observation.get("provider", "")), model=str(observation.get("model", "")),
            observer=str(observation.get("source", "")), request_id=str(observation.get("request_id", "")),
        )
        state["updated_at"] = now()
        write_state(run_root, state)
    if execution_id:
        payload = {
            "provenance": PROVENANCE.execution_provenance(state, execution_id),
            "observation_check": PROVENANCE.verify_observation_chain(state, execution_id),
            "usage": EXECUTION.usage_view(state, execution_id),
        }
    else:
        task_id = str(getattr(args, "task_id", "") or "")
        rows = [
            PROVENANCE.execution_provenance(state, str(record.get("execution_id", "")))
            for record in PROVENANCE.executions(state)
            if not task_id or str(record.get("task_id", "")) == task_id
        ]
        payload = {"executions": rows, "telemetry": EXECUTION.telemetry_summary(state)}
    if getattr(args, "json", False):
        print(json.dumps(payload, indent=2, sort_keys=True, default=str))
        return 0
    if execution_id:
        view = payload["provenance"]
        print(f"{view['execution_id']} {view['role']} {view['state']} task={view['task_id']}")
        for field in ("provider", "model"):
            claim = view["claims"][field]
            print(f"  {field}: {claim['value']} ({claim['level']})")
        if view["provider_request_id"]:
            print(f"  provider request: {view['provider_request_id']}")
        print(f"  provenance digest: {view['provenance_digest'][:16]}")
        if not payload["observation_check"]["ok"]:
            print("  observation problems: " + "; ".join(payload["observation_check"]["problems"]))
        return 0
    print(f"Executions: {len(payload['executions'])}")
    for row in payload["executions"][-10:]:
        claims = row["claims"]
        print(
            f"  {row['execution_id']} {row['role']} {row['state']} "
            f"provider={claims['provider']['value']} ({claims['provider']['level']}) "
            f"model={claims['model']['value']} ({claims['model']['level']})"
        )
    return 0


def recover_command(args: argparse.Namespace) -> int:
    """Inspect divergences and, where a safe action exists, apply it explicitly."""
    run_root, state = resolve_and_load(args)
    apply_action = str(getattr(args, "apply", "") or "")
    if not apply_action:
        proposals = RECOVERY.propose(run_root, state, target=str(getattr(args, "target", "") or ""))
        if args.json:
            print(json.dumps(proposals, indent=2, sort_keys=True))
            return 0 if proposals.get("status") == "clean" else 2
        if proposals["status"] == "clean":
            print("Clean. No divergence is recorded.")
            return 0
        print("Divergences found:")
        for item in proposals["proposals"]:
            safe = "safe" if item.get("safe") else "REFUSED"
            print(f"- {item.get('finding')} [{safe}] {item.get('target')}: {item.get('reason')}")
            if item.get("action"):
                print(f"  apply: --apply {item['action']} --target {item['target']}")
        return 2
    identity = str(getattr(args, "identity", "") or "")
    reason = str(getattr(args, "reason", "") or "")
    if not identity or not reason:
        raise RuntimeError_("--apply requires --identity and --reason so the recovery is attributable")
    target = str(getattr(args, "target", "") or "")
    proposals = RECOVERY.propose(run_root, state, target=target, action=apply_action)
    if not proposals["proposals"]:
        raise RuntimeError_("No current divergence matches that recovery request")
    if len(proposals["proposals"]) > 1 and not target:
        raise RuntimeError_("Several divergences match; name one with --target")
    proposal = proposals["proposals"][0]
    emit_event(
        run_root, "recovery_proposed", state=state, task_id=proposal.get("target", ""),
        action=apply_action, safe=bool(proposal.get("safe")), reason=str(proposal.get("reason", "")),
    )
    packet_entry = None
    if apply_action == "adopt-packet":
        packet_id = str(proposal["target"])
        packet_dir = run_root / packet_id
        manifest_path = packet_dir / TRANSPORT.MANIFEST_NAME
        if not manifest_path.is_file():
            raise RuntimeError_("The orphan packet directory has no manifest; nothing was changed")
        orphan_manifest = json.loads(read(manifest_path))
        stage = str(orphan_manifest.get("stage", ""))
        packet_entry = {
            "id": packet_id,
            "stage": stage,
            "path": str(packet_dir),
            "reasoner_output_baseline": reasoner_output_baseline(Path(state["project"]), stage),
        }
    state, record = RECOVERY.apply(
        run_root, state, action=apply_action, target=str(proposal["target"]),
        identity=identity, reason=reason, project=Path(state["project"]),
        packet_entry=packet_entry, policy=POLICY,
    )
    state["updated_at"] = now()
    state["next"] = f"Recovery applied: {apply_action} on {record['target']}."
    write_state(run_root, state)
    emit_event(
        run_root, "recovery_applied", state=state, task_id=str(record["target"]),
        action=apply_action, recovery=str(record["recovery_id"]), identity=identity,
        outcome="applied", reason=reason,
    )
    append_log(
        run_root,
        f"Recovery {apply_action} applied",
        "An operator resolved a known interruption state through the engine's own transition boundary.",
        f"{record['recovery_id']}: {record['reason']}",
        [str(record.get("before", "")), str(record.get("after", ""))],
        "; ".join(str(item) for item in record.get("evidence", [])) or "no additional evidence",
        state["next"],
    )
    print(f"Done. {apply_action} was applied to {record['target']} and recorded as {record['recovery_id']}.")
    return 0


def runtime_version() -> str:
    """The release version this runtime tree carries (VERSION is canonical)."""
    path = ROOT / "VERSION"
    return read(path).strip() if path.is_file() else "unknown"


def migrate_command(args: argparse.Namespace) -> int:
    """Inspect, apply or roll back the explicit v1 -> v2 run-state migration."""
    run_root = resolve_run_root(args)
    if getattr(args, "rollback", False):
        action = "rollback"
    elif getattr(args, "apply", False):
        action = "apply"
    else:
        action = "plan"
    try:
        if action == "plan":
            value = MIGRATION.plan(run_root)
        elif action == "apply":
            value = MIGRATION.apply(run_root)
        else:
            value = MIGRATION.rollback(run_root)
    except CONTRACTS.ContractError as exc:
        print(f"STOPPED: {exc}")
        return 1
    sys.stdout.write(MIGRATION.render(value))
    if action != "plan":
        evidence = value.get("evidence") or value.get("rollback") or {}
        append_log(
            run_root,
            f"Migration {action}",
            "The operator ran the explicit v1 -> v2 run-state migration.",
            "migrated" if action == "apply" else "rolled back to the preserved pre-migration bytes",
            [str(evidence.get("backup") or evidence.get("restored_from") or "")],
            json.dumps(evidence, sort_keys=True),
            "Continue with the normal Ariadne commands." if action == "apply"
            else "The migrated state is preserved if it is needed again.",
        )
    return 0


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--self-test", action="store_true")
    p.add_argument("--version", action="store_true", help="print the runtime version and engine contract")
    sub = p.add_subparsers(dest="command")

    start_p = sub.add_parser("start", help="start a new Ariadne project and prepare its brief")
    start_p.add_argument("--project", required=True)
    start_p.add_argument("--run-root")
    start_p.add_argument("--run-id")
    start_p.add_argument(
        "--reasoner", choices=list(REASONERS.load_contract()["providers"]),
        help="explicit reasoning provider; Codex is the default",
    )
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
        command.add_argument(
            "--migrate", action="store_true",
            help=(
                "explicitly upgrade a run state written before the AR-201 engine contract "
                "(the pre-migration file is preserved; no approval is ever created)"
            ),
        )

    discover_p = sub.add_parser("discover", help="find the run that records a project")
    discover_p.add_argument("--project", required=True)
    discover_p.add_argument("--json", action="store_true")

    status_p = sub.add_parser("status", help="show the current project state and next action")
    run_selector(status_p)
    status_p.add_argument("--json", action="store_true")

    reasoner_status_p = sub.add_parser(
        "reasoner-status", help="show selected reasoner and current capability evidence"
    )
    run_selector(reasoner_status_p)
    reasoner_status_p.add_argument("--reasoner", choices=list(REASONERS.load_contract()["providers"]))
    reasoner_status_p.add_argument("--json", action="store_true")

    select_reasoner_p = sub.add_parser(
        "select-reasoner", help="record an explicit provider choice and prepare a safe linked retry when needed"
    )
    run_selector(select_reasoner_p)
    select_reasoner_p.add_argument("--reasoner", required=True, choices=list(REASONERS.load_contract()["providers"]))
    select_reasoner_p.add_argument("--reason", required=True)

    failure_p = sub.add_parser(
        "record-reasoner-failure", help="preserve a reasoner failure and fall back only when no material output exists"
    )
    run_selector(failure_p)
    failure_p.add_argument("--summary", required=True)
    failure_p.add_argument("--evidence", required=True, choices=list(REASONERS.EVIDENCE_CLASSES))

    readiness_p = sub.add_parser(
        "handoff-readiness", help="check implementation context before provider launch"
    )
    run_selector(readiness_p)
    readiness_p.add_argument("--json", action="store_true")

    preflight_p = sub.add_parser("preflight", help="record provider/model/effort readiness before external work")
    run_selector(preflight_p)
    preflight_p.add_argument("--provider")
    preflight_p.add_argument("--model")
    preflight_p.add_argument("--effort", choices=["low", "medium", "high", "xhigh", "max"])
    preflight_p.add_argument("--workload", choices=["small", "medium", "large"])
    preflight_p.add_argument("--availability", default="unknown", choices=["available", "limited", "unavailable", "unknown"])
    preflight_p.add_argument("--quota", default="unknown", choices=["sufficient", "insufficient", "unknown"])
    preflight_p.add_argument("--fallback")

    route_p = sub.add_parser(
        "route",
        help="recommend capability class, concrete model, effort, session strategy, and rationale",
    )
    route_p.add_argument(
        "--task-type",
        choices=["reasoning", "implementation", "mechanical", "reading", "browser", "generative"],
    )
    route_p.add_argument("--stage", choices=list(TRANSPORT.STAGES) + ["S0", "S4_browser"])
    route_p.add_argument("--complexity", choices=["low", "medium", "high", "novel"], default="medium")
    route_p.add_argument("--ambiguity", choices=["low", "medium", "high"], default="medium")
    route_p.add_argument("--consequence", choices=["low", "medium", "high"], default="medium")
    route_p.add_argument("--reversibility", choices=["high", "medium", "low"], default="medium")
    route_p.add_argument("--visual-importance", choices=["low", "high"], default="low")
    route_p.add_argument(
        "--context-requirements", choices=["low", "medium", "high"], default="medium"
    )
    route_p.add_argument(
        "--context-state",
        choices=["useful", "stale", "noisy", "independent_required"],
        default="useful",
    )
    route_p.add_argument("--same-objective", action="store_true", default=True)
    route_p.add_argument("--new-objective", dest="same_objective", action="store_false")
    route_p.add_argument("--provider-available", choices=["yes", "no"], default="yes")
    route_p.add_argument("--quota-sufficient", choices=["yes", "no"], default="yes")
    route_p.add_argument("--runtime-model")
    route_p.add_argument("--escalated", action="store_true")
    route_p.add_argument("--json", action="store_true")

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
    return_p.add_argument(
        "--execution",
        help=(
            "the engine-created implementer execution this return belongs to; omit to use the open "
            "execution for this boundary (a caller-chosen id is refused)"
        ),
    )

    validate_worker_p = sub.add_parser(
        "validate-worker", help="independently validate the current implementation result before review"
    )
    run_selector(validate_worker_p)
    validate_worker_p.add_argument("--timeout", type=int, default=120)

    review_p = sub.add_parser("ingest-review", help="preserve and apply a marked independent-review judgement")
    run_selector(review_p)
    review_p.add_argument("--input", required=True)
    review_p.add_argument(
        "--reviewer-identity",
        help=(
            "who performed the review, recorded verbatim; required, and it must not be the "
            "implementation worker's recorded identity"
        ),
    )
    review_p.add_argument(
        "--kind", choices=list(CONTRACTS.REVIEW_KINDS),
        help="review lens: experience (default) or technical; each requires its own evidence set",
    )
    review_p.add_argument(
        "--execution",
        help=(
            "a reviewer execution the engine already created; it must be a reviewer execution for "
            "this task, never the implementing execution"
        ),
    )

    approve_p = sub.add_parser(
        "approve-gate", help="record a human gate decision as an engine approval bound to the current revision"
    )
    run_selector(approve_p)
    approve_p.add_argument("--gate", required=True, choices=["G1", "G2", "G3", "g1", "g2", "g3"])
    approve_p.add_argument("--identity", required=True, help="who granted the gate, recorded verbatim")
    approve_p.add_argument("--note", help="optional reason or context for the record")

    acceptance_p = sub.add_parser(
        "record-acceptance", help="record the human acceptance outcome after independent review"
    )
    run_selector(acceptance_p)
    acceptance_p.add_argument("--outcome", required=True, choices=["accepted", "rejected"])

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
        choices=["plan", "implementation", "visual", "review", "social", "social-learning"],
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

    restart_p = sub.add_parser(
        "restart-direction",
        help="preserve a rejected pre-G1 direction and prepare its linked S3 child",
    )
    run_selector(restart_p)
    restart_p.add_argument("--reason", required=True)
    restart_p.add_argument("--synthetic-validation", action="store_true", help=argparse.SUPPRESS)

    advance_p = sub.add_parser(
        "advance", help="record obvious same-session outputs and continue routine work"
    )
    run_selector(advance_p)
    advance_p.add_argument("--provider", default="orchestrator")
    advance_p.add_argument("--model", default="not recorded")
    advance_p.add_argument("--transport-provider", help="provider or worker environment label")
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
    next_p.add_argument("--provider", help="provider or worker environment label")
    next_p.add_argument("--worker-role", choices=list(TRANSPORT.WORKER_ROLES))
    next_p.add_argument(
        "--escalate", action="store_true",
        help="prepare a stronger worker role at the same bounded implementation boundary",
    )
    next_p.add_argument("--references-file")
    next_p.add_argument("--motion", choices=["yes", "no"])
    next_p.add_argument("--assets", choices=["yes", "no"])
    next_p.add_argument("--target")
    next_p.add_argument("--lenses")
    next_p.add_argument("--synthetic-validation", action="store_true", help=argparse.SUPPRESS)

    executions_p = sub.add_parser(
        "execution-status",
        help="show engine-created executions, the last characterisation, route and context decision, and failures",
    )
    run_selector(executions_p)
    executions_p.add_argument("--json", action="store_true")

    events_p = sub.add_parser(
        "engine-events",
        help="print the canonical append-only engine event log with its integrity check",
    )
    run_selector(events_p)
    events_p.add_argument("--limit", type=int, default=50)
    events_p.add_argument("--json", action="store_true")

    recover_p = sub.add_parser(
        "recover",
        help="inspect a divergence and, where a safe action exists, apply it through the engine boundary",
    )
    run_selector(recover_p)
    recover_p.add_argument("--apply", choices=list(CONTRACTS.RECOVERY_ACTIONS))
    recover_p.add_argument("--target")
    recover_p.add_argument("--identity", help="operator identity recorded on the recovery")
    recover_p.add_argument("--reason", help="why the recovery is safe for this divergence")
    recover_p.add_argument("--json", action="store_true")

    migrate_p = sub.add_parser(
        "migrate",
        help="explicitly migrate a v1-era run state to the v2 engine contract (dry run by default)",
    )
    migrate_selection = migrate_p.add_mutually_exclusive_group(required=True)
    migrate_selection.add_argument("--run-root")
    migrate_selection.add_argument("--project")
    migrate_action = migrate_p.add_mutually_exclusive_group()
    migrate_action.add_argument("--dry-run", action="store_true", help="show the plan without writing (the default)")
    migrate_action.add_argument("--apply", action="store_true", help="apply the migration after writing a backup")
    migrate_action.add_argument("--rollback", action="store_true", help="restore the preserved pre-migration state")

    capabilities_p = sub.add_parser(
        "capabilities",
        help="declare, probe and inspect capability evidence (a declaration is never a verification)",
    )
    run_selector(capabilities_p)
    capabilities_p.add_argument("--input", help="JSON declaring capability declarations and deterministic probes")
    capabilities_p.add_argument("--family", help="filter the registry view to one adapter family")
    capabilities_p.add_argument("--adapter", help="filter the registry view to one adapter")
    capabilities_p.add_argument("--json", action="store_true")

    verify_p = sub.add_parser(
        "verify",
        help="record a verification claim or inspect verification status (stale evidence never satisfies)",
    )
    run_selector(verify_p)
    verify_p.add_argument("--input", help="JSON with the claim, level, evidence and reproduction")
    verify_p.add_argument("--status", action="store_true", help="inspect verification status instead of recording")
    verify_p.add_argument("--subject", help="limit the status view to one subject")
    verify_p.add_argument("--dependency", action="append", help="name=value current dependency fingerprint")
    verify_p.add_argument("--json", action="store_true")

    decide_p = sub.add_parser(
        "decide",
        help="compile, evaluate, inspect or explain bounded decisions (never an authorization)",
    )
    run_selector(decide_p)
    decide_p.add_argument("--input", help="JSON with the work to perform, the projection and an offline provider")
    decide_p.add_argument("--compile", action="store_true", help="compile a decision plan from declared requirements")
    decide_p.add_argument("--graph", action="store_true", help="also build the decision graph for the compiled plan")
    decide_p.add_argument(
        "--advise",
        choices=["failure-classification", "review-escalation", "evidence-relevance", "route-family"],
        help="ask one real engine integration for bounded advice",
    )
    decide_p.add_argument("--explain", action="store_true", help="print the record-derived decision trace")
    decide_p.add_argument("--inspect", action="store_true", help="inspect the decision record trace instead")
    decide_p.add_argument("--providers", action="store_true", help="print the declared provider and projection contracts")
    decide_p.add_argument("--justify", action="store_true", help="record why generative execution is justified")
    decide_p.add_argument("--outcome", action="store_true", help="record raw outcome evidence for one decision")
    decide_p.add_argument("--invalidate-cache", action="store_true", help="revoke or supersede cached decisions")
    decide_p.add_argument("--task-id", help="limit the trace to one task")
    decide_p.add_argument("--json", action="store_true")
    trace_p = sub.add_parser(
        "decision-trace",
        help="print the read-only decision trace for a task (why Ariadne chose each action)",
    )
    run_selector(trace_p)
    trace_p.add_argument("--task-id", help="limit the trace to one task")
    trace_p.add_argument("--json", action="store_true")

    provenance_p = sub.add_parser(
        "provenance",
        help="inspect engine-bound execution provenance and record provider observations",
    )
    run_selector(provenance_p)
    provenance_p.add_argument("--execution", help="the engine-created execution to inspect")
    provenance_p.add_argument("--task-id", help="limit the list view to one task")
    provenance_p.add_argument("--provider-source", help="engine-side observer recording a provider observation")
    provenance_p.add_argument("--provider-name")
    provenance_p.add_argument("--provider-model")
    provenance_p.add_argument("--provider-request-id")
    provenance_p.add_argument("--provider-run-id")
    provenance_p.add_argument("--json", action="store_true")

    design_plan_p = sub.add_parser(
        "design-plan",
        help="characterise a task for design intelligence and select the pipeline and evidence it needs",
    )
    run_selector(design_plan_p)
    design_plan_p.add_argument("--stage", help="the boundary to characterise (defaults to the current packet)")
    design_plan_p.add_argument("--request", help="the task request text to characterise")
    design_plan_p.add_argument("--input", help="optional JSON declaring characteristics and adapter fixtures")
    design_plan_p.add_argument(
        "--evidence-policy", choices=["declared", "observed", "strict"],
        help="how much capability evidence this route requires (default: declared)",
    )
    design_plan_p.add_argument("--json", action="store_true")

    design_record_p = sub.add_parser(
        "record-design",
        help="record reference, component, direction, requirement, rendered-evidence and critique events",
    )
    run_selector(design_record_p)
    design_record_p.add_argument("--input", required=True, help="JSON file with one event or an events list")

    design_check_p = sub.add_parser(
        "design-check", help="check whether design evidence is traceable and current",
    )
    run_selector(design_check_p)
    design_check_p.add_argument("--json", action="store_true")

    design_report_p = sub.add_parser(
        "design-report", help="print deterministic design-intelligence measurements",
    )
    run_selector(design_report_p)
    design_report_p.add_argument("--json", action="store_true")

    design_approve_p = sub.add_parser(
        "approve-design-direction",
        help="record the human approval of one engine design-direction record (gate G1D)",
    )
    run_selector(design_approve_p)
    design_approve_p.add_argument("--direction", help="the design-direction record id (defaults to the active one)")
    design_approve_p.add_argument("--identity", required=True, help="who approved it, recorded verbatim")
    design_approve_p.add_argument("--note", help="optional reason or context for the record")

    economics_p = sub.add_parser(
        "economics",
        help="show task-level harness economics and set the efficiency flags (AR-204)",
    )
    run_selector(economics_p)
    economics_p.add_argument("--task-id", help="report one task's tree, cost and verified completion cost")
    economics_p.add_argument("--price-profile", help="a registered price profile id (never invented)")
    economics_p.add_argument("--json", action="store_true")
    for _name, _values in EFFICIENCY.SETTING_VALUES.items():
        economics_p.add_argument(
            f"--{_name.replace('_', '-')}", choices=list(_values),
            help=f"set the {_name} efficiency setting (default {EFFICIENCY.DEFAULT_FLAGS[_name]})",
        )

    request_map_p = sub.add_parser(
        "request-map",
        help="render the actual request structure of a prepared packet (offline, redacted)",
    )
    request_map_p.add_argument("--packet", required=True, help="path to a prepared packet.txt")
    request_map_p.add_argument("--provider")
    request_map_p.add_argument("--model")
    request_map_p.add_argument("--prompt-profile", choices=list(PROMPTING.PROMPT_PROFILES), default="legacy")
    request_map_p.add_argument("--json", action="store_true")

    tool_packs_p = sub.add_parser(
        "tool-packs",
        help="show measured tool-schema economics and the deterministic capability-pack selection",
    )
    tool_packs_p.add_argument("--stage", choices=list(TRANSPORT.STAGES))
    tool_packs_p.add_argument("--skill", action="append", help="a selected skill (repeatable)")
    tool_packs_p.add_argument("--capability", action="append", help="a required capability (repeatable)")
    tool_packs_p.add_argument("--json", action="store_true")
    return p


def economics_command(args: argparse.Namespace) -> int:
    """Print task-level economics, or configure the efficiency flags (AR-204)."""
    run_root, state = resolve_and_load(args)
    flags = {
        name: str(getattr(args, name.replace("-", "_"), "") or "")
        for name in EFFICIENCY.SETTING_VALUES
    }
    flags = {name: value for name, value in flags.items() if value}
    if flags:
        record = ENGINE_API.set_efficiency(state, **flags)
        emit_event(
            run_root, "efficiency_configured", state=state,
            digest=str(record.get("digest", "")),
            settings={name: record.get(name, "") for name in sorted(flags)},
        )
        state["updated_at"] = now()
        write_state(run_root, state)
    task_id = str(getattr(args, "task_id", "") or "")
    profile_id = str(getattr(args, "price_profile", "") or "")
    if task_id:
        payload = {
            "efficiency": ENGINE_API.efficiency_report(state),
            "task": ENGINE_API.task_economics(state, task_id, profile_id=profile_id),
        }
    else:
        payload = {
            "efficiency": ENGINE_API.efficiency_report(state),
            "economics": ENGINE_API.economics_report(state, profile_id=profile_id),
        }
    if getattr(args, "json", False):
        print(json.dumps(payload, indent=2, sort_keys=True, default=str))
        return 0
    print(EFFICIENCY.describe(state))
    if task_id:
        cost = payload["task"]["cost"]
        verified = payload["task"]["verified_completion"]
        print(f"Task {task_id}: {cost['executions']} execution(s), {cost['failed_executions']} failed, "
              f"{cost['decision_batches']} decision batch(es)")
        print(f"  measured totals: {json.dumps(cost['totals'], sort_keys=True)}")
        print(f"  monetary: {cost['monetary'].get('monetary')} "
              f"({cost['monetary'].get('reason', cost['monetary'].get('basis', ''))})")
        print(f"  verified completion: {verified['verified']} ({verified['cost_label']})")
        return 0
    context = payload["economics"]["context"]
    print(f"Context decisions {context['decisions']}: {context['sources_included']} included, "
          f"{context['sources_omitted']} omitted, cache {context['cache']['hits']} hit(s)")
    summary = payload["economics"]["summary"]
    print(f"Executions {summary['executions']} "
          f"({summary['executions_with_measured_usage']} with measured usage)")
    return 0


def request_map_command(args: argparse.Namespace) -> int:
    """Render the actual request structure of a prepared packet (offline)."""
    packet = Path(str(getattr(args, "packet", "") or "")).resolve()
    if not packet.is_file():
        raise RuntimeError_(f"no packet file to map: {packet}")
    payload = ENGINE_API.inspect_request(
        packet=packet,
        provider=str(getattr(args, "provider", "") or ""),
        model=str(getattr(args, "model", "") or ""),
        profile=str(getattr(args, "prompt_profile", "") or "legacy"),
    )
    if getattr(args, "json", False):
        print(json.dumps(payload, indent=2, sort_keys=True, default=str))
        return 0
    mapping = payload["harness_map"]
    print(f"Prompt profile {payload['prompt_profile']}"
          + (f" (removed {payload['profile_removed_bytes']} bytes)" if payload["profile_removed_bytes"] else ""))
    print(f"{'SECTION'.ljust(46)} {'BUCKET'.ljust(16)} {'BYTES'.rjust(8)}  STABILITY")
    for section in mapping["sections"]:
        label = str(section["label"])[:44]
        print(f"{label.ljust(46)} {str(section['bucket']).ljust(16)} "
              f"{int(section['bytes']):8d}  {section['stability']}"
              + (f"  volatile={','.join(section['volatile'])}" if section["volatile"] else ""))
    prefix = mapping["stable_prefix"]
    print(f"stable prefix {prefix['stable_prefix_bytes']} bytes "
          f"(digest {prefix['stable_prefix_digest'][:12]}), volatile {prefix['volatile_bytes']} bytes")
    return 0


def tool_packs_command(args: argparse.Namespace) -> int:
    """Show measured tool-schema economics and the deterministic pack selection."""
    payload = ENGINE_API.inspect_tool_packs(
        root=ROOT,
        stage=str(getattr(args, "stage", "") or ""),
        selected_skills=[item for item in (getattr(args, "skill", None) or [])],
        required_capabilities=[item for item in (getattr(args, "capability", None) or [])],
    )
    if getattr(args, "json", False):
        print(json.dumps(payload, indent=2, sort_keys=True, default=str))
        return 0
    sizes = payload["sizes"]
    for pack_id, entry in sizes["packs"].items():
        marker = "core " if entry["always_loaded"] else "     "
        print(f"{marker}{pack_id.ljust(14)} {entry['bytes']:8d} bytes  {entry['members']} member(s)")
    print(f"deferrable {sizes['deferrable_bytes']} bytes; core {sizes['core_bytes']} bytes")
    selection = payload["selection"]
    print(f"selected for {selection['stage'] or '(no stage)'}: {', '.join(selection['packs'])}")
    for pack_id, reason in selection["reasons"].items():
        print(f"  {pack_id}: {reason}")
    return 0


def main() -> int:
    args = parser().parse_args()
    try:
        if args.self_test:
            return self_test()
        if args.version:
            print(f"Ariadne {runtime_version()}")
            print(f"runtime schema {RUNTIME_SCHEMA}; engine contract {CONTRACTS.ENGINE_CONTRACT}")
            return 0
        commands = {
            "start": ENGINE_API.start_run,
            "discover": discover,
            "status": ENGINE_API.status,
            "reasoner-status": reasoner_status,
            "select-reasoner": select_reasoner,
            "record-reasoner-failure": record_reasoner_failure,
            "handoff-readiness": handoff_readiness_command,
            "preflight": provider_preflight,
            "route": route_command,
            "record-result": ENGINE_API.record_result,
            "record-transcript": record_transcript,
            "ingest-return": ENGINE_API.ingest_return,
            "validate-worker": ENGINE_API.validate_worker,
            "ingest-review": ENGINE_API.ingest_review,
            "record-acceptance": ENGINE_API.record_acceptance,
            "approve-gate": ENGINE_API.approve_gate,
            "creative-plan": creative_plan,
            "record-creative": record_creative,
            "creative-check": creative_check,
            "operations-plan": operations_plan,
            "record-operations": record_operations,
            "operations-check": operations_check,
            "record-intervention": record_intervention,
            "record-note": record_note,
            "restart-direction": restart_direction,
            "advance": advance,
            "prepare-next": ENGINE_API.prepare_next,
            "execution-status": execution_status_command,
            "engine-events": engine_events_command,
            "recover": recover_command,
            "migrate": migrate_command,
            "capabilities": capabilities_command,
            "verify": verify_command,
            "decide": decide_command,
            "decision-trace": decision_trace_command,
            "provenance": provenance_command,
            "design-plan": design_plan_command,
            "record-design": record_design,
            "design-check": design_check_command,
            "design-report": design_report_command,
            "approve-design-direction": approve_design_direction,
            "economics": economics_command,
            "request-map": request_map_command,
            "tool-packs": tool_packs_command,
        }
        if args.command in commands:
            entry = commands[args.command]
            if entry is ENGINE_API.start_run or getattr(entry, "__module__", "") == ENGINE_API.__name__:
                result = entry(args=args)
                text = ENGINE_API.format_result(result)
                if text:
                    sys.stdout.write(text)
                return result.exit_code
            return entry(args)
        parser().print_help()
        return 0
    except (RuntimeError_, *ENGINE_ERRORS, TRANSPORT.PacketError, CREATIVE.CreativeError, OPERATIONS.OperationsError) as exc:
        print(f"STOPPED: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
