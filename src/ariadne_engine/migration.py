"""AR-205 explicit v1 -> v2 project migration: inventory, dry run, apply, rollback.

Migration is an operator decision with an audit trail, never a read side effect:

* :func:`plan` is read-only. It classifies every persisted object it finds as
  ``READ_DIRECTLY``, ``MIGRATE``, ``LEGACY_READ_ONLY`` or ``UNSUPPORTED`` and
  states exactly what an apply would change and what it would preserve.
* :func:`apply` migrates only the run state through
  :mod:`ariadne_engine.persistence`, which backsup the pre-migration bytes and
  writes additively. It never converts a document gate mirror into an approval,
  never creates a review or validation record, and never raises an evidence
  level. Unreadable or malformed state refuses before anything is written.
* :func:`rollback` restores the preserved pre-migration bytes only while the
  migrated state is byte-identical to what migration produced. After further v2
  work it refuses and keeps both states, because records created under v2 cannot
  meaningfully exist in the v1 file.

Every applied or rolled-back migration appends one record to
``migration-report.json`` beside the run state so the action is durable evidence
rather than console output.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from pathlib import Path

from . import contracts, package_version, persistence
from .contracts import ContractError, ENGINE_CONTRACT, SCHEMA_RECORD, StaleSchema

READ_DIRECTLY = "READ_DIRECTLY"
MIGRATE = "MIGRATE"
LEGACY_READ_ONLY = "LEGACY_READ_ONLY"
UNSUPPORTED = "UNSUPPORTED"

REPORT_NAME = "migration-report.json"
REPORT_SCHEMA = 1
V2_BACKUP_STEM = "ariadne-run.v2"

READABLE_LEDGER_SCHEMAS = {
    "creative-evidence.json": (1, 2),
    "creative-operations.json": (1,),
}
"""Ledger schema versions this release reads without transforming.

Kept in step with ``scripts/creative-intelligence.py`` (``SUPPORTED_SCHEMA_VERSIONS``)
and ``scripts/creative-operations.py`` (``SCHEMA_VERSION``); the release tests
compare them directly so the two lists cannot drift apart.
"""

DOCUMENT_MIRRORS = ("PROJECT.md", "AGENTS.md", "DESIGN.md", "HANDOFF.md", "QA.md", "RESEARCH.md")

RUN_STATE_DOCUMENTS = ("OPERATIONS.md",)
RUN_STATE_LOGS = ("engine-events.jsonl", "worker-telemetry.jsonl")


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _file_digest(path: Path) -> str:
    return _sha256(Path(path).read_bytes())


def report_path(run_root: Path) -> Path:
    return Path(run_root) / REPORT_NAME


def load_report(run_root: Path) -> dict:
    """Read the migration evidence records. A malformed report is refused, not guessed."""
    path = report_path(run_root)
    if not path.is_file():
        return {"schema_version": REPORT_SCHEMA, "records": []}
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or value.get("schema_version") != REPORT_SCHEMA:
        raise ContractError(f"Migration report is malformed: {path}")
    records = value.get("records")
    if not isinstance(records, list):
        raise ContractError(f"Migration report has no records: {path}")
    return value


def _append_record(run_root: Path, record: dict) -> dict:
    value = load_report(run_root)
    value["records"].append(record)
    persistence.write_json(report_path(run_root), value)
    return record


def _ledger_rows(project: Path) -> list[dict]:
    rows: list[dict] = []
    state_dir = project / ".ariadne"
    if state_dir.is_dir():
        for path in sorted(state_dir.glob("*.json")):
            try:
                value = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                rows.append({
                    "path": str(path),
                    "kind": "project-ledger",
                    "schema_version": None,
                    "classification": UNSUPPORTED,
                    "action": "none",
                    "detail": "the ledger is unreadable; migration leaves it untouched",
                })
                continue
            schema = value.get("schema_version") if isinstance(value, dict) else None
            readable = READABLE_LEDGER_SCHEMAS.get(path.name)
            if readable is None:
                classification = UNSUPPORTED if isinstance(schema, int) else LEGACY_READ_ONLY
                detail = (
                    "the file has a schema marker this release does not define"
                    if isinstance(schema, int)
                    else "the file carries no versioned schema; it is preserved as operator material"
                )
            elif isinstance(schema, int) and schema in readable:
                classification = READ_DIRECTLY
                detail = f"schema {schema} is read directly; no transformation is proposed"
            else:
                classification = UNSUPPORTED
                detail = f"schema {schema!r} is not in the readable set {readable}"
            rows.append({
                "path": str(path),
                "kind": "project-ledger",
                "schema_version": schema if isinstance(schema, int) else None,
                "classification": classification,
                "action": "none",
                "detail": detail,
            })
        for path in sorted(state_dir.rglob("*.md")):
            rows.append({
                "path": str(path),
                "kind": "project-evidence",
                "schema_version": None,
                "classification": LEGACY_READ_ONLY,
                "action": "none",
                "detail": "legacy evidence text stays legacy evidence; nothing is promoted",
            })
    for name in DOCUMENT_MIRRORS:
        path = project / name
        if path.is_file():
            rows.append({
                "path": str(path),
                "kind": "project-document",
                "schema_version": None,
                "classification": LEGACY_READ_ONLY,
                "action": "none",
                "detail": "document gate mirrors are never converted into approval records",
            })
    return rows


def render(value: dict) -> str:
    """The operator text for a plan, apply or rollback result."""
    lines: list[str] = []
    if "rollback" in value:
        record = value["rollback"]
        lines.append("Rollback complete: the pre-migration state was restored.")
        lines.append(f"- restored from: {record['restored_from']}")
        lines.append(f"- migrated state preserved at: {record['preserved_v2_state']}")
        lines.append(f"- restored digest: {record['state_sha256_restored']}")
        lines.append("No approval, review, validation or placement was invented or removed by the rollback.")
        return "\n".join(lines) + "\n"
    if value.get("dry_run") and "source" in value:
        source = value["source"]
        lines.append(f"Ariadne migration dry run: {value['run_root']}")
        lines.append(
            f"- source: run schema {source['run_schema']}, record schema "
            f"{source['record_schema']!r}, engine contract {source['engine_contract']!r}"
        )
        lines.append(
            f"- target: run schema {value['target']['run_schema']}, record schema "
            f"{value['target']['record_schema']}, engine contract {value['target']['engine_contract']}"
        )
        lines.append(f"- migration needed: {'yes' if source['needs_migration'] else 'no (already current)'}")
        counts: dict[str, int] = {}
        for row in value["objects"]:
            counts[row["classification"]] = counts.get(row["classification"], 0) + 1
        lines.append(
            "- objects: "
            + ", ".join(f"{name.lower()} {count}" for name, count in sorted(counts.items()))
            + f" ({len(value['objects'])} total)"
        )
        for row in value["objects"]:
            if row["classification"] in (MIGRATE, UNSUPPORTED):
                lines.append(f"  - {row['classification']}: {row['path']} - {row['detail']}")
        if value["transformations"]:
            lines.append("- transformations on apply:")
            lines.extend(f"  - {item}" for item in value["transformations"])
        lines.append("- preserved legacy objects:")
        lines.extend(f"  - {item}" for item in value["preserved_legacy"])
        if value["unsupported"]:
            lines.append("- unsupported data (apply refuses until resolved):")
            lines.extend(f"  - {row['path']}: {row['detail']}" for row in value["unsupported"])
        lines.append(
            f"- backup plan: {value['backup_plan']['path']} "
            f"({'already exists' if value['backup_plan']['exists'] else 'written on apply'})"
        )
        expected = value["expected_post_state"]
        lines.append(
            f"- expected after apply: run schema {expected['run_schema']}, record schema "
            f"{expected['record_schema']}, approvals {expected['approvals']}, "
            f"approvals created {expected['approvals_created']}, "
            f"migration history entries {expected['migration_history']}"
        )
        lines.append(f"- {value['note']}")
        if value["source"]["needs_migration"] and not value["unsupported"]:
            lines.append("- apply with: ariadne migrate --apply")
        elif not value["source"]["needs_migration"]:
            lines.append("- no migration is required; the run state already carries the v2 engine contract")
        return "\n".join(lines) + "\n"
    evidence = value.get("evidence", {})
    lines.append("Migration applied." if evidence.get("migrated") else "Migration already current; nothing was written.")
    if evidence:
        lines.append(f"- backup: {evidence['backup']}")
        lines.append(
            f"- record schema: {evidence['from_record_schema']!r} -> {evidence['to_record_schema']}"
        )
        lines.append(
            f"- approvals preserved: {evidence['approvals_before']}; approvals created: {evidence['approvals_created']}"
        )
        lines.append(f"- run-state digest after: {evidence['state_sha256_after']}")
    lines.append("Legacy documents and gate mirrors remain unapproved; re-grant any human gate explicitly.")
    return "\n".join(lines) + "\n"


def report_view(run_root: Path) -> dict:
    value = load_report(Path(run_root))
    return {
        "run_root": str(Path(run_root).resolve()),
        "records": value["records"],
    }


def inventory(run_root: Path, state: dict) -> list[dict]:
    """Classify every persisted object migration can see. Read-only."""
    run_root = Path(run_root)
    needs = persistence.needs_migration(state)
    marker = persistence.engine_marker(state)
    rows = [{
        "path": str(persistence.state_path(run_root)),
        "kind": "run-state",
        "schema_version": state.get("schema_version"),
        "record_schema": marker.get("record_schema"),
        "classification": MIGRATE if needs else READ_DIRECTLY,
        "action": "additive record-contract migration" if needs else "none",
        "detail": (
            "the run carries no current engine contract; an explicit apply adds the marker and one "
            "migration record and preserves every approval"
            if needs
            else "the run already carries this engine contract"
        ),
    }]
    for name in RUN_STATE_DOCUMENTS:
        if (run_root / name).is_file():
            rows.append({
                "path": str(run_root / name),
                "kind": "operator-log",
                "schema_version": None,
                "classification": LEGACY_READ_ONLY,
                "action": "none",
                "detail": "the operator log is append-only history; migration never rewrites it",
            })
    for name in RUN_STATE_LOGS:
        if (run_root / name).is_file():
            rows.append({
                "path": str(run_root / name),
                "kind": "engine-log",
                "schema_version": None,
                "classification": READ_DIRECTLY,
                "action": "none",
                "detail": "append-only engine records are read as they are",
            })
    for backup in sorted(run_root.glob("ariadne-run.v*.bak")):
        rows.append({
            "path": str(backup),
            "kind": "migration-backup",
            "schema_version": None,
            "classification": LEGACY_READ_ONLY,
            "action": "none",
            "detail": "preserved pre-migration bytes; never overwritten or removed",
        })
    packets = state.get("packets") if isinstance(state.get("packets"), list) else []
    for entry in packets:
        if not isinstance(entry, dict):
            continue
        manifest = Path(str(entry.get("path", ""))) / "manifest.json"
        if manifest.is_file():
            rows.append({
                "path": str(manifest),
                "kind": "packet-manifest",
                "schema_version": 1,
                "classification": READ_DIRECTLY,
                "action": "none",
                "detail": "packet manifests are immutable transport evidence",
            })
    project_text = str(state.get("project", "")).strip()
    if project_text:
        project = Path(project_text)
        if project.is_dir():
            rows.extend(_ledger_rows(project))
    return rows


def blocking_unsupported(rows: list[dict]) -> list[dict]:
    """Rows that must be resolved before an apply may touch anything."""
    return [row for row in rows if row["classification"] == UNSUPPORTED]


def plan(run_root: Path) -> dict:
    """The dry run: what migration would change, preserve, back up and refuse."""
    run_root = Path(run_root).resolve()
    state_file = persistence.state_path(run_root)
    if not state_file.is_file():
        raise ContractError(f"No Ariadne run found at {run_root}")
    state = persistence.read_json(state_file)
    version = state.get("schema_version")
    if version not in persistence.READABLE_RUN_SCHEMAS:
        raise StaleSchema(persistence.SCHEMA_REFUSAL)
    problems = persistence.state_problems(state)
    if problems:
        raise ContractError("Run state is malformed: " + "; ".join(problems))
    needs = persistence.needs_migration(state)
    marker = persistence.engine_marker(state)
    rows = inventory(run_root, state)
    approvals = state.get("approvals") if isinstance(state.get("approvals"), list) else []
    history = state.get("migration_history") if isinstance(state.get("migration_history"), list) else []
    backup = run_root / persistence.BACKUP_TEMPLATE.format(version=version)
    transforms = []
    if needs:
        transforms = [
            "add the engine contract marker (contract, run/record schemas, written_at)",
            "append one run-state-migration record to migration_history",
            "preserve every existing approval unchanged; create none",
            "leave the run-state file schema and every legacy document untouched",
        ]
    unsupported = blocking_unsupported(rows)
    return {
        "dry_run": True,
        "run_root": str(run_root),
        "project": state.get("project"),
        "engine": {
            "version": package_version(),
            "contract": ENGINE_CONTRACT,
            "record_schema": SCHEMA_RECORD,
        },
        "source": {
            "run_schema": version,
            "record_schema": marker.get("record_schema"),
            "engine_contract": marker.get("contract"),
            "needs_migration": needs,
            "migration_history": len(history),
            "approvals": len(approvals),
        },
        "target": {
            "run_schema": version,
            "record_schema": SCHEMA_RECORD,
            "engine_contract": ENGINE_CONTRACT,
        },
        "objects": rows,
        "transformations": transforms,
        "preserved_legacy": [
            "the pre-migration state is copied to " + str(backup) + " before any write",
            "legacy approvals stay approvals; no new approval, review, validation or capability record is created",
            "document gate mirrors in PROJECT.md/AGENTS.md/DESIGN.md remain mirrors and grants nothing",
            "project ledgers and evidence text keep their own schemas",
        ],
        "unsupported": unsupported,
        "backup_plan": {
            "path": str(backup),
            "exists": backup.is_file(),
            "writes": "only on apply, and only when a migration is actually needed",
        },
        "expected_post_state": {
            "run_schema": version,
            "record_schema": SCHEMA_RECORD,
            "approvals": len(approvals),
            "approvals_created": 0,
            "migration_history": len(history) + (1 if needs else 0),
        },
        "idempotent": not needs,
        "note": "dry run: nothing was written",
    }


def apply(run_root: Path) -> dict:
    """Migrate after verifying the plan; refuse rather than proceed unsafely."""
    run_root = Path(run_root).resolve()
    reviewed = plan(run_root)
    if reviewed["unsupported"]:
        reasons = "; ".join(f"{row['path']}: {row['detail']}" for row in reviewed["unsupported"])
        raise ContractError(
            "Unsupported legacy data must be resolved before migration; nothing was written: " + reasons
        )
    before = _file_digest(persistence.state_path(run_root))
    state, report = persistence.migrate_file(run_root)
    after_digest = _file_digest(persistence.state_path(run_root))
    evidence = {
        "action": "apply",
        "at": contracts.utc_now(),
        "run_root": str(run_root),
        "engine_version": package_version(),
        "from_record_schema": reviewed["source"]["record_schema"],
        "to_record_schema": reviewed["target"]["record_schema"],
        "run_schema": reviewed["source"]["run_schema"],
        "backup": str(run_root / persistence.BACKUP_TEMPLATE.format(version=reviewed["source"]["run_schema"])),
        "state_sha256_before": before,
        "state_sha256_after": after_digest,
        "approvals_before": reviewed["source"]["approvals"],
        "approvals_created": 0,
        "migrated": bool(report.get("migrated")),
    }
    if evidence["migrated"]:
        _append_record(run_root, evidence)
    else:
        evidence["note"] = "already current; no backup was written and no evidence record was added"
    return {"plan": reviewed, "report": report, "evidence": evidence, "dry_run": False}


def rollback(run_root: Path) -> dict:
    """Restore the preserved pre-migration bytes while that remains honest."""
    run_root = Path(run_root).resolve()
    evidence = load_report(run_root)
    applied = [row for row in evidence["records"] if row.get("action") == "apply"]
    state_file = persistence.state_path(run_root)
    if not state_file.is_file():
        raise ContractError(f"No Ariadne run found at {run_root}")
    if not applied:
        raise ContractError(
            "No applied migration is recorded for this run; there is nothing to roll back"
        )
    last = applied[-1]
    backup = Path(str(last.get("backup", "")))
    if not backup.is_file():
        raise ContractError(
            f"The preserved pre-migration state is missing: {backup}. "
            "Rollback is impossible without it; nothing was changed"
        )
    current_digest = _file_digest(state_file)
    if current_digest != last.get("state_sha256_after"):
        state = persistence.read_json(state_file)
        raise ContractError(
            "The run has changed since migration "
            f"(approvals: {len(state.get('approvals') or [])}, transitions: {len(state.get('transitions') or [])}). "
            "Restoring the pre-migration file would discard records created under v2, so rollback is refused. "
            f"The pre-migration bytes remain at {backup}. Nothing was changed"
        )
    preserved = run_root / f"{V2_BACKUP_STEM}.bak"
    counter = 2
    while preserved.exists():
        preserved = run_root / f"{V2_BACKUP_STEM}.{counter}.bak"
        counter += 1
    preserved.write_bytes(state_file.read_bytes())
    restored = backup.read_bytes()
    temporary = state_file.with_name(f".{state_file.name}.{uuid.uuid4().hex}.tmp")
    temporary.write_bytes(restored)
    persistence.replace_with_retry(temporary, state_file)
    temporary.unlink(missing_ok=True)
    restored_digest = _file_digest(state_file)
    if restored_digest != last.get("state_sha256_before"):
        raise ContractError(
            "The restored state does not match the recorded pre-migration bytes; "
            f"the migrated state is preserved at {preserved}"
        )
    record = {
        "action": "rollback",
        "at": contracts.utc_now(),
        "run_root": str(run_root),
        "restored_from": str(backup),
        "preserved_v2_state": str(preserved),
        "state_sha256_restored": restored_digest,
        "expected_sha256": last.get("state_sha256_before"),
    }
    _append_record(run_root, record)
    return {"rollback": record, "preserved": str(preserved), "dry_run": False}
