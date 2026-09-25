"""Versioned persistence for run state: explicit reads, atomic writes, migration.

Rules implemented here (AR-201 T1):

* A run state whose ``schema_version`` is not readable is refused with the
  historic message. It is never guessed at and never migrated.
* A run state written before this engine contract existed (no ``engine``
  marker) is *readable in principle* but must not be continued silently: it is
  refused until the operator asks for the migration explicitly with
  ``--migrate``. That is the difference between "we can parse it" and "we know
  the authorization model it was produced under".
* Migration is additive and never invents authority: legacy gate mirrors in
  ``AGENTS.md`` / ``DESIGN.md`` are *not* converted into approval records,
  because the document fields were never an authorization channel. A migrated
  run therefore starts with no approvals and re-obtains any human gate it still
  needs. Nothing is deleted, no key is renamed, and the pre-migration file is
  preserved beside the state as ``<name>.v<n>.bak``.
* Writes are temp-file + atomic replace with retry (the pattern the runtime
  already used on Windows), so an interrupted write leaves the previous state
  intact. A failed migration or a failed transition therefore changes nothing.
"""

from __future__ import annotations

import json
import shutil
import time
import uuid
from pathlib import Path
from typing import Callable

from . import contracts
from .contracts import ContractError, ENGINE_CONTRACT, READABLE_RUN_SCHEMAS, SCHEMA_RECORD, SCHEMA_RUN, StaleSchema

STATE_NAME = "ariadne-run.json"
BACKUP_TEMPLATE = "ariadne-run.v{version}.bak"

SCHEMA_REFUSAL = "Run state schema is unsupported"

DESIGN_COLLECTIONS = (
    "design_characterisations",
    "design_plans",
    "design_references",
    "component_candidates",
    "design_directions",
    "design_requirements",
    "rendered_evidence",
    "design_reviews",
    "design_refinements",
)
"""AR-202D record collections kept in the run state.

Additive and optional in exactly the way the AR-202 collections are: a run state
written by an earlier milestone has none of them and stays readable and
continuable, which is why the design records carry their own schema family
(``contracts.SCHEMA_DESIGN``) instead of forcing a run-state migration.
"""

ADAPTIVE_COLLECTIONS = (
    "executions",
    "failures",
    "characterisations",
    "routing_decisions",
    "context_decisions",
    "recoveries",
    *DESIGN_COLLECTIONS,
    *contracts.AR203_COLLECTIONS,
    *contracts.AR205D_COLLECTIONS,
)
"""AR-202, AR-202D, AR-203 and AR-205D record collections kept in the run state.

They are additive and optional: a state written by an earlier milestone has none
of them and stays readable and continuable, which is why the records carry their
own schema families instead of forcing a run-state migration. Legacy data that
lacks these records remains legacy/unverified; absence is never converted into
success.
"""

ECONOMICS_COLLECTIONS = (
    "artifacts",
    "compaction_records",
)
"""AR-204 record collections kept in the run state.

Additive and optional in exactly the way the AR-202/AR-203 collections are: a run
state written by an earlier milestone has none of them, and one written with them
stays readable by any reader that ignores unknown keys. An artifact record is a
*reference* to durable evidence, never the evidence itself.
"""

MIGRATION_HISTORY_LIMIT = 20

_LOGGER: Callable[[Path, dict], None] | None = None


def bind_logger(logger: Callable[[Path, dict], None] | None) -> None:
    """Register the runtime's operator-log writer (keeps log formatting in one place)."""
    global _LOGGER
    _LOGGER = logger


def state_path(run_root: Path) -> Path:
    return Path(run_root) / STATE_NAME


def read_json(path: Path) -> dict:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ContractError(f"Run state is malformed: {exc}") from exc
    except OSError as exc:
        raise ContractError(f"Run state is unreadable: {exc}") from exc
    if not isinstance(value, dict):
        raise ContractError("Run state is malformed: the file does not contain an object")
    return value


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
    path = Path(path)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        replace_with_retry(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def write_state(run_root: Path, state: dict) -> None:
    """Persist run state atomically, normalising the fields this engine owns."""
    if not isinstance(state, dict):
        raise ContractError("run state must be an object")
    state.setdefault("approvals", [])
    state.setdefault("migration_history", [])
    state.setdefault("transitions", [])
    for name in ADAPTIVE_COLLECTIONS:
        state.setdefault(name, [])
    for name in ECONOMICS_COLLECTIONS:
        state.setdefault(name, [])
    engine = state.setdefault("engine", {})
    if isinstance(engine, dict):
        engine.update({
            "contract": ENGINE_CONTRACT,
            "run_schema": SCHEMA_RUN,
            "record_schema": SCHEMA_RECORD,
            "readable_run_schemas": list(READABLE_RUN_SCHEMAS),
            "adaptive_contract": contracts.ADAPTIVE_CONTRACT,
            "adaptive_schema": contracts.SCHEMA_ADAPTIVE,
            "design_contract": contracts.DESIGN_CONTRACT,
            "design_schema": contracts.SCHEMA_DESIGN,
            "capability_contract": contracts.CAPABILITY_CONTRACT,
            "capability_schema": contracts.SCHEMA_CAPABILITY,
            "verification_contract": contracts.VERIFICATION_CONTRACT,
            "verification_schema": contracts.SCHEMA_VERIFICATION,
            "decision_contract": contracts.DECISION_CONTRACT,
            "decision_schema": contracts.SCHEMA_DECISION,
            "decision_intelligence_contract": contracts.DECISION_INTELLIGENCE_CONTRACT,
            "decision_intelligence_schema": contracts.SCHEMA_DECISION_INTELLIGENCE,
            "written_at": contracts.utc_now(),
        })
    write_json(state_path(run_root), state)


def state_problems(state: dict) -> list[str]:
    """Structural validation that must hold before a state may be used."""
    problems: list[str] = []
    if not isinstance(state, dict):
        return ["run state is not an object"]
    if state.get("schema_version") not in READABLE_RUN_SCHEMAS:
        problems.append("run state has an unsupported schema version")
    for name in ("run_id", "project"):
        if not str(state.get(name, "")).strip():
            problems.append(f"run state has no {name}")
    packets = state.get("packets")
    if not isinstance(packets, list) or not packets:
        problems.append("run state has no prepared packets")
    else:
        for entry in packets:
            if not isinstance(entry, dict) or not entry.get("id") or not entry.get("stage") or not entry.get("path"):
                problems.append("run state has a malformed packet entry")
                break
    for name in (
        "approvals", "migration_history", "transitions", "notes", "human_interventions",
        *ADAPTIVE_COLLECTIONS, *ECONOMICS_COLLECTIONS,
    ):
        value = state.get(name)
        if value is not None and not isinstance(value, list):
            problems.append(f"run state field {name} must be a list")
    return problems


def engine_marker(state: dict) -> dict:
    value = state.get("engine")
    return value if isinstance(value, dict) else {}


def needs_migration(state: dict) -> bool:
    """True for a readable state written before this engine contract existed."""
    marker = engine_marker(state)
    return marker.get("contract") != ENGINE_CONTRACT or marker.get("record_schema") != SCHEMA_RECORD


def migrate(state: dict, from_version: int, to_version: int) -> dict:
    """Return an additive, recorded migration. Pure: the input is not modified.

    ``from_version`` is the run-state *file* version that was read; ``to_version``
    is the record contract to write. The file version is not changed by AR-201,
    so a migrated run stays readable by the published runtime.
    """
    if from_version not in READABLE_RUN_SCHEMAS:
        raise StaleSchema(SCHEMA_REFUSAL)
    if to_version not in contracts.READABLE_RECORD_SCHEMAS:
        raise ContractError(f"unknown record contract version: {to_version}")
    migrated = json.loads(json.dumps(state))
    if not needs_migration(migrated):
        return migrated
    previous = migrated.get("approvals") if isinstance(migrated.get("approvals"), list) else []
    migrated["approvals"] = previous
    migrated.setdefault("migration_history", [])
    migrated["migration_history"].append({
        "schema_version": SCHEMA_RECORD,
        "kind": "run-state-migration",
        "from_schema_version": from_version,
        "from_record_schema": engine_marker(migrated).get("record_schema") or 1,
        "to_record_schema": to_version,
        "run_schema": migrated.get("schema_version", from_version),
        "engine_contract": ENGINE_CONTRACT,
        "recorded_at": contracts.utc_now(),
        "approvals_preserved": len(previous),
        "approvals_created": 0,
        "note": (
            "Additive migration: no approval is created from document fields. "
            "Human gates recorded only in AGENTS.md/DESIGN.md remain unapproved and must be re-granted "
            "with the operator approval command."
        ),
    })
    if len(migrated["migration_history"]) > MIGRATION_HISTORY_LIMIT:
        migrated["migration_history"] = migrated["migration_history"][-MIGRATION_HISTORY_LIMIT:]
    migrated["engine"] = {
        "contract": ENGINE_CONTRACT,
        "run_schema": migrated.get("schema_version", from_version),
        "record_schema": to_version,
        "readable_run_schemas": list(READABLE_RUN_SCHEMAS),
        "written_at": contracts.utc_now(),
    }
    problems = state_problems(migrated)
    if problems:
        raise ContractError("Migration would produce an invalid run state: " + "; ".join(problems))
    return migrated


def migration_record(state: dict) -> dict:
    history = state.get("migration_history")
    if isinstance(history, list) and history:
        return history[-1]
    return {}


def backup_state(run_root: Path, version: int) -> Path | None:
    """Preserve the pre-migration state. An existing backup is never overwritten."""
    source = state_path(run_root)
    if not source.is_file():
        raise ContractError(f"No Ariadne run found at {run_root}")
    destination = Path(run_root) / BACKUP_TEMPLATE.format(version=version)
    if destination.exists():
        return None
    shutil.copyfile(source, destination)
    return destination


def migrate_file(run_root: Path, *, to_version: int = SCHEMA_RECORD) -> tuple[dict, dict]:
    """Perform the explicit migration and return (state, report)."""
    run_root = Path(run_root)
    state = read_json(state_path(run_root))
    version = state.get("schema_version")
    if version not in READABLE_RUN_SCHEMAS:
        raise StaleSchema(SCHEMA_REFUSAL)
    if not needs_migration(state):
        return state, {"migrated": False, "reason": "run state already carries this engine contract"}
    backup = backup_state(run_root, int(version))
    migrated = migrate(state, int(version), to_version)
    write_state(run_root, migrated)
    report = {
        "migrated": True,
        "from_version": int(version),
        "to_version": to_version,
        "backup": str(backup) if backup else None,
        "record": migration_record(migrated),
    }
    if _LOGGER is not None:
        _LOGGER(run_root, report)
    return migrated, report


def recovery_report(run_root: Path) -> dict:
    """Report the actual persisted state after an interruption. Never repairs, never infers success.

    Findings are stated as divergences an operator can act on:

    ``orphan-packet``
        a prepared packet directory that run state does not list (for example a
        crash between writing the packet and appending it to state). It is not
        adopted automatically: the packet may belong to an abandoned attempt.
    ``missing-packet``
        run state lists a packet whose directory or manifest is gone.
    ``interrupted-write``
        a leftover temporary state file. The live state is intact (writes are
        atomic); the temporary file is reported so it can be inspected.
    """
    run_root = Path(run_root)
    findings: list[dict] = []
    try:
        state = load_state(run_root, migrate_state=False)
    except (ContractError, StaleSchema):
        state = read_json(state_path(run_root))
    recorded = {
        str(entry.get("id")): entry
        for entry in (state.get("packets") or [])
        if isinstance(entry, dict)
    }
    # Real packets are direct children of the run root; the historical
    # ``packets/`` location is kept because a run may have been started by a
    # runtime that used it. A directory only counts as a packet if it carries a
    # manifest, so logs, telemetry and quarantine directories are not mistaken
    # for unrecorded work.
    recorded_paths = {
        str(Path(str(entry.get("path", ""))).resolve())
        for entry in recorded.values()
        if str(entry.get("path", ""))
    }
    seen_orphans: set[str] = set()
    for base in (run_root / "packets", run_root):
        if not base.is_dir():
            continue
        for path in sorted(base.iterdir()):
            if not path.is_dir() or path.name in recorded or path.name in seen_orphans:
                continue
            if str(path.resolve()) in recorded_paths:
                continue
            if (path / "manifest.json").is_file():
                seen_orphans.add(path.name)
                findings.append({
                    "kind": "orphan-packet",
                    "packet": path.name,
                    "path": str(path),
                    "effect": "not adopted: no successful transition was recorded for it",
                })
    for packet_id, entry in recorded.items():
        path = Path(str(entry.get("path", "")))
        if not path.is_dir() or not (path / "manifest.json").is_file():
            findings.append({
                "kind": "missing-packet",
                "packet": packet_id,
                "path": str(path),
                "effect": "state names a packet that is not on disk; no completion is inferred",
            })
    for leftover in sorted(run_root.glob(f".{STATE_NAME}.*.tmp")):
        findings.append({
            "kind": "interrupted-write",
            "path": str(leftover),
            "effect": "state was not replaced; the persisted state is the previous one",
        })
    return {
        "run_root": str(run_root),
        "status": "clean" if not findings else "diverged",
        "schema_version": state.get("schema_version"),
        "packets_recorded": len(recorded),
        "last_packet": (state.get("packets") or [{}])[-1].get("id") if state.get("packets") else None,
        "worker_lifecycle": (state.get("worker") or {}).get("lifecycle"),
        "next": state.get("next"),
        "findings": findings,
    }


def load_state(run_root: Path, *, migrate_state: bool = False, to_version: int = SCHEMA_RECORD) -> dict:
    """Read run state, or refuse.

    Refusal is deliberate in two cases: an unreadable schema version, and a
    readable state that predates this engine contract when no explicit
    migration was requested. Nothing is written on read.
    """
    run_root = Path(run_root)
    path = state_path(run_root)
    if not path.is_file():
        raise ContractError(f"No Ariadne run found at {run_root}")
    state = read_json(path)
    version = state.get("schema_version")
    if version not in READABLE_RUN_SCHEMAS:
        raise StaleSchema(SCHEMA_REFUSAL)
    problems = state_problems(state)
    if problems:
        raise ContractError("Run state is malformed: " + "; ".join(problems))
    if needs_migration(state):
        if not migrate_state:
            raise StaleSchema(
                f"Run state was written before the {ENGINE_CONTRACT} record contract; "
                "no gate from it can be trusted and it is not migrated implicitly. "
                "Re-run with --migrate to upgrade it in place (the pre-migration file is preserved)."
            )
        state, _report = migrate_file(run_root, to_version=to_version)
        problems = state_problems(state)
        if problems:
            raise ContractError("Migrated run state is malformed: " + "; ".join(problems))
    return state
