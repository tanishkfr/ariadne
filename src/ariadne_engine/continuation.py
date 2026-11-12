"""Revision-bound continuation projections for a resumed or new worker session.

Why this is separate from :mod:`ariadne_engine.history`
-------------------------------------------------------
AR-204's history compactor is structural and general: it preserves whole
*history entries* by kind, archives the original, and refuses to drop a
protected entry. That is the right tool for narration. It is not a task
resumption contract, because a worker that resumes a task needs the current
*authoritative* facts even if nobody wrote them into the conversation history:

* the original objective and the declared constraints;
* the repository revision the evidence actually describes;
* the modified files;
* the active attempt and lifecycle state;
* every required validation command;
* the latest failure and the unresolved review finding;
* the human decisions already made and the ones still open;
* the evidence references a new session must read.

So :func:`build` projects those facts from the durable task record and refuses
when the projection would describe a different revision than the one on disk.
The original state, evidence and approval records remain authoritative; a
continuation is a read-only view of them, and :func:`require_current` is how a
caller refuses a stale one instead of guessing.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Mapping, Sequence

from . import contracts, history
from .contracts import ContractError
from .serialization import canonical_json, digest_text

SCHEMA = "ar-24b-continuation-1"
POLICY = "structured-continuation-1"
COLLECTION = "continuations"
MAX_CONTINUATIONS = 2_000


def _validation_record(attempt: Mapping) -> dict:
    validation = dict((attempt or {}).get("validation") or {})
    path = str(validation.get("path", "") or "")
    expected = str(validation.get("validation_sha256", "") or "")
    if not path or not Path(path).is_file():
        return {}
    try:
        raw = Path(path).read_bytes()
    except OSError:
        return {}
    actual = hashlib.sha256(raw).hexdigest()
    if expected and actual != expected:
        return {}
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _latest_attempt(task: Mapping) -> dict:
    attempts = [item for item in (task or {}).get("attempts") or () if isinstance(item, Mapping)]
    return dict(attempts[-1]) if attempts else {}


def _failed_attempts(task: Mapping) -> list[dict]:
    rows: list[dict] = []
    for attempt in (task or {}).get("attempts") or ():
        if not isinstance(attempt, Mapping):
            continue
        validation = dict(attempt.get("validation") or {})
        if str(validation.get("status", "")) not in ("failed", "blocked"):
            continue
        commands = [
            str(item.get("id", ""))
            for item in validation.get("commands") or ()
            if isinstance(item, Mapping) and str(item.get("status", "")) == "failed"
        ]
        rows.append({
            "attempt_id": str(attempt.get("attempt_id", "")),
            "packet_id": str(attempt.get("packet_id", "")),
            "status": str(validation.get("status", "")),
            "failure_kind": str(validation.get("failure_kind", "")),
            "failure_reason": str(validation.get("failure_reason", "")),
            "failed_checks": commands,
            "repair_kind": str(attempt.get("repair_kind", "")),
        })
    return rows


def _unresolved_review(task: Mapping) -> list[str]:
    review = dict((task or {}).get("review") or {})
    if str(review.get("outcome", "")) != "failed":
        return []
    return [str(item) for item in review.get("findings") or () if str(item).strip()]


def _human_decisions(state: Mapping, task: Mapping) -> list[dict]:
    decisions: list[dict] = []
    acceptance = dict((task or {}).get("acceptance") or {})
    if acceptance.get("identity"):
        decisions.append({
            "kind": "acceptance",
            "identity": str(acceptance.get("identity", "")),
            "outcome": str(acceptance.get("outcome", "")),
            "reason": str(acceptance.get("reason", "")),
        })
    task_id = str((task or {}).get("task_id", ""))
    for item in (state.get("human_interventions") or ()) if isinstance(state, Mapping) else ():
        if not isinstance(item, Mapping):
            continue
        label = str(item.get("task_id", "") or "")
        if label and label != task_id:
            continue
        if str(item.get("status", "")) in ("open", "pending", ""):
            decisions.append({
                "kind": str(item.get("kind", "intervention")),
                "identity": str(item.get("identity", "")),
                "outcome": str(item.get("status", "open")),
                "reason": str(item.get("reason", item.get("question", ""))),
            })
    return decisions


def build(
    state: Mapping,
    task: Mapping,
    *,
    current_revision: str = "",
    history_entries: Sequence[Mapping] = (),
    root: Path | None = None,
    reduction_reason: str = "",
) -> dict:
    """Project one task's continuation facts and bind them to a revision.

    ``current_revision`` is optional. When supplied, the projection refuses if
    the validated revision it would describe is different, because a new worker
    session that reads a stale projection would work from evidence that no
    longer applies.
    """
    task = dict(task or {})
    if not str(task.get("task_id", "")).strip():
        raise ContractError("a continuation needs a recorded task")
    attempt = _latest_attempt(task)
    validation = dict(attempt.get("validation") or {})
    validation_file = _validation_record(attempt)
    validated_head = str((validation.get("validated_revision") or {}).get("head", "") or "")
    fingerprint = str((validation.get("validated_revision") or {}).get("implementation_fingerprint", "") or "")
    baseline_head = str((task.get("baseline") or {}).get("head", "") or "")
    revision = validated_head or baseline_head
    status = "CURRENT"
    stale_reasons: list[str] = []
    if current_revision and revision and str(current_revision) != revision:
        stale_reasons.append(
            f"the task evidence describes revision {revision[:12]}, not the current {str(current_revision)[:12]}"
        )
        status = "STALE"
    if not revision:
        status = "UNKNOWN"
        stale_reasons.append("the task records no repository revision")
    if not fingerprint:
        stale_reasons.append("no validated implementation fingerprint is recorded")

    scope = [str(item) for item in ((task.get("scope") or {}).get("declared") or ())]
    protected = [dict(item) for item in ((task.get("scope") or {}).get("protected") or ()) if isinstance(item, Mapping)]
    validation_commands = [str(item) for item in ((task.get("validation") or {}).get("declared") or ())]
    objective = str(task.get("objective", "") or (state.get("request") if isinstance(state, Mapping) else "") or "")
    failures = _failed_attempts(task)
    findings = _unresolved_review(task)
    decisions = _human_decisions(state, task)
    state_value = (
        "accepted" if str((task.get("acceptance") or {}).get("outcome")) == "accepted"
        else "rejected" if str((task.get("acceptance") or {}).get("outcome")) == "rejected"
        else "review-failed" if findings
        else "validated" if str(attempt.get("state", "")) == "validated"
        else "failed" if str(attempt.get("state", "")) == "failed"
        else "running" if str(attempt.get("state", "")) == "running"
        else "prepared"
    )

    narration = {}
    if history_entries:
        if root is None:
            raise ContractError("compacting narration needs a run root for its reversible archive")
        narration = history.compact(root, history_entries, policy="structured_v1", reason=reduction_reason or "continuation")
    projection = {
        "objective": objective,
        "scope": scope,
        "protected_scope": protected,
        "constraints": [
            f"permitted files: {', '.join(scope)}" if scope else "no write scope is declared",
            f"write authorization: {task.get('write_authorization', 'UNKNOWN')}",
            "the task contract, validation rows and human gates remain authoritative",
        ],
        "revision": {
            "validated_head": validated_head,
            "baseline_head": baseline_head,
            "implementation_fingerprint": fingerprint,
        },
        "modified_files": [str(item) for item in validation_file.get("changed_files") or ()],
        "lifecycle": {
            "status": state_value,
            "attempt_id": str(attempt.get("attempt_id", "")),
            "attempt_state": str(attempt.get("state", "")),
            "attempts": len([item for item in task.get("attempts") or () if isinstance(item, Mapping)]),
            "repair_attempts": len([
                item for item in task.get("attempts") or ()
                if isinstance(item, Mapping) and str(item.get("repair_kind", "")).strip()
            ]),
            "review_corrections": int(task.get("review_corrections", 0) or 0),
            "review_correction_limit": int(task.get("review_correction_limit", 0) or 0),
        },
        "validation_commands": validation_commands,
        "latest_failures": failures[-3:],
        "unresolved_review_findings": findings,
        "human_decisions": decisions,
        "evidence_refs": [
            str((attempt.get("return") or {}).get("path", "")),
            str(validation.get("path", "")),
            str((task.get("review") or {}).get("review_id", "")),
            str((task.get("proof") or {}).get("proof_id", "")),
        ],
        "narration": {
            "entries": int(narration.get("entries", 0) or 0),
            "active_entries": int(narration.get("active_entries", 0) or 0),
            "archive_path": str(narration.get("archive_path", "")),
            "archive_digest": str(narration.get("archive_digest", "")),
            "note": "narration is compacted; the facts above are not",
        } if narration else {"entries": 0, "note": "no narration entries were supplied"},
    }
    projection["evidence_refs"] = [item for item in projection["evidence_refs"] if item]
    record = {
        "schema_version": SCHEMA,
        "policy": POLICY,
        "continuation_id": contracts.new_record_id("cnt"),
        "run_id": str(state.get("run_id", "")) if isinstance(state, Mapping) else "",
        "task_id": str(task.get("task_id", "")),
        "status": status,
        "stale_reasons": stale_reasons,
        "revision": revision,
        "projection": projection,
        "recorded_at": contracts.utc_now(),
    }
    record["content_digest"] = digest_text(canonical_json({
        key: value for key, value in record.items() if key not in ("continuation_id", "recorded_at", "content_digest")
    }))
    return record


def problems(record: Mapping) -> list[str]:
    problems: list[str] = []
    if not isinstance(record, Mapping):
        return ["continuation record is not an object"]
    if str(record.get("schema_version", "")) != SCHEMA:
        problems.append("continuation record has an unsupported schema version")
    for name in ("continuation_id", "task_id", "recorded_at", "status"):
        if not str(record.get(name, "")).strip():
            problems.append(f"continuation record has no {name}")
    if str(record.get("status", "")) not in ("CURRENT", "STALE", "UNKNOWN"):
        problems.append("continuation record has an unsupported status")
    projection = record.get("projection")
    if not isinstance(projection, Mapping):
        problems.append("continuation record has no projection")
        return problems
    for name in ("objective", "scope", "validation_commands", "lifecycle", "human_decisions", "evidence_refs"):
        if name not in projection:
            problems.append(f"continuation projection has no {name}")
    digest = str(record.get("content_digest", ""))
    if digest:
        expected = digest_text(canonical_json({
            key: value for key, value in record.items() if key not in ("continuation_id", "recorded_at", "content_digest")
        }))
        if digest != expected:
            problems.append("continuation content digest does not match its contents")
    return problems


def record(state: dict, continuation: Mapping) -> dict:
    value = dict(continuation)
    problems_list = problems(value)
    if problems_list:
        raise ContractError("continuation record is malformed: " + "; ".join(problems_list))
    contracts.require_collection_capacity(state, COLLECTION)
    state.setdefault(COLLECTION, []).append(value)
    return value


def latest(state: Mapping, task_id: str) -> dict | None:
    rows = [
        dict(item) for item in (state.get(COLLECTION) or ())
        if isinstance(item, Mapping) and str(item.get("task_id", "")) == str(task_id)
    ]
    return rows[-1] if rows else None


def require_current(record: Mapping, *, revision_hash: str) -> dict:
    """Refuse a continuation that no longer describes the current revision."""
    if str(record.get("status", "")) != "CURRENT":
        raise ContractError(
            "the continuation is not current: " + "; ".join(str(item) for item in record.get("stale_reasons") or ())
        )
    recorded = str(record.get("revision", ""))
    if not recorded:
        raise ContractError("the continuation records no revision and cannot be resumed")
    if str(revision_hash) and recorded != str(revision_hash):
        raise ContractError(
            f"the continuation describes revision {recorded[:12]}, not the current {str(revision_hash)[:12]}"
        )
    return dict(record)


def render(record: Mapping) -> str:
    """The compact model-facing continuation block.

    It is a projection, not an authorization: the note says so on the block
    itself, because a resumed worker must not mistake a summary for a contract.
    """
    projection = dict(record.get("projection") or {})
    lines = [
        "CONTINUATION PROJECTION (derived from durable evidence; not an authorization)",
        f"Task: {record.get('task_id')} | revision: {str(record.get('revision', ''))[:12]} | status: {record.get('status')}",
        "",
        f"Objective: {projection.get('objective', 'UNKNOWN')}",
        "",
        "Constraints:",
        *[f"- {item}" for item in projection.get("constraints") or ()],
        "",
        "Permitted scope: " + (", ".join(projection.get("scope") or ()) or "none declared"),
        "Validation commands:",
        *[f"- {item}" for item in projection.get("validation_commands") or ()],
        "",
        "Lifecycle: " + ", ".join(
            f"{name}={value}" for name, value in sorted((projection.get("lifecycle") or {}).items())
        ),
        "Modified files: " + (", ".join(projection.get("modified_files") or ()) or "UNKNOWN"),
    ]
    failures = projection.get("latest_failures") or []
    if failures:
        lines.extend(["", "Latest failures:"])
        for failure in failures:
            lines.append(
                f"- {failure.get('attempt_id')}: {failure.get('failure_kind')} -- {failure.get('failure_reason')}"
            )
    findings = projection.get("unresolved_review_findings") or []
    if findings:
        lines.extend(["", "Unresolved review findings:"])
        lines.extend(f"- {item}" for item in findings)
    decisions = projection.get("human_decisions") or []
    if decisions:
        lines.extend(["", "Human decisions / open items:"])
        lines.extend(
            f"- {item.get('kind')}: {item.get('outcome') or 'open'}"
            + (f" ({item.get('identity')})" if item.get("identity") else "")
            for item in decisions
        )
    if projection.get("evidence_refs"):
        lines.extend(["", "Evidence references:"])
        lines.extend(f"- {item}" for item in projection["evidence_refs"])
    if record.get("stale_reasons"):
        lines.extend(["", "Staleness: " + "; ".join(str(item) for item in record["stale_reasons"])])
    return "\n".join(lines).rstrip() + "\n"


def describe(record: Mapping) -> str:
    projection = dict(record.get("projection") or {})
    return (
        f"continuation {record.get('continuation_id')}: task {record.get('task_id')}, "
        f"{len(projection.get('validation_commands') or [])} validation row(s), "
        f"{len(projection.get('unresolved_review_findings') or [])} unresolved review finding(s), "
        f"status {record.get('status')}"
    )


__all__ = [
    "SCHEMA",
    "POLICY",
    "COLLECTION",
    "MAX_CONTINUATIONS",
    "build",
    "problems",
    "record",
    "latest",
    "require_current",
    "render",
    "describe",
]
