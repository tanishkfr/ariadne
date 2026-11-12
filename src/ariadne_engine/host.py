"""Stable, read-only host integration contract (Ariadne 2.4C).

A host (a desktop app, editor, or service) may display Ariadne's state and ask
the engine to perform a decision, but it must not re-implement workflow,
verification, proof, recovery or authorization. This module is the one
provider-neutral projection a host consumes.

It is deliberately read-only:

* ``host_status`` projects durable state and never writes;
* ``host_events`` reads the existing append-only engine log with a resumable
  cursor and refuses an unknown cursor instead of replaying events;
* ``read_only`` and ``authority_effect`` are explicit on every response;
* no operation here can approve a gate, record a review, validate work, accept
  a task, or mint a proof.

The module is not a second store. It derives from ``ariadne-run.json``, the
engine event log, the task lifecycle records, the review/proof records and the
measurement records the engine already owns. If those disagree, the response
says so rather than choosing a winner.

Schema version: ``ariadne-host-1``.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from . import contracts, events, provenance

CONTRACT_NAME = "ariadne-host"
CONTRACT_VERSION = 1
SCHEMA_VERSION = "ariadne-host-1"
EVENT_CURSOR_SCHEMA = "ariadne-host-event-cursor-1"

MAX_EVENTS_PER_PAGE = 200
READ_ONLY_NOTE = (
    "This surface is read-only. It reports what the engine recorded; it cannot approve a "
    "gate, validate work, record a review, accept a task, or mint proof."
)


def _packet(state: Mapping[str, Any]) -> dict:
    packets = state.get("packets")
    if not isinstance(packets, list) or not packets:
        return {}
    return dict(packets[-1]) if isinstance(packets[-1], Mapping) else {}


def _task_report(state: Mapping[str, Any]) -> dict:
    """The runtime's one task derivation, when a bound runtime is available.

    A caller that already has the report passes it in. The API/MCP/CLI doors do
    that, so every surface projects the same task view rather than three
    approximations of it.
    """
    from . import api

    runtime = api.runtime()
    return runtime.task_report(state, task_id="")


def _identity_claims(state: Mapping[str, Any]) -> dict:
    rows = [
        row for row in (state.get("executions") or [])
        if isinstance(row, Mapping)
    ]
    if not rows:
        return {
            "provider": {"value": "UNKNOWN", "level": "UNKNOWN"},
            "model": {"value": "UNKNOWN", "level": "UNKNOWN"},
            "basis": "no engine-created execution is recorded",
        }
    implementers = [row for row in rows if str(row.get("role", "")) == "implementer"]
    latest = (implementers or rows)[-1]
    claims = provenance.identity_claims(latest)
    return {
        "provider": dict(claims.get("provider") or {"value": "UNKNOWN", "level": "UNKNOWN"}),
        "model": dict(claims.get("model") or {"value": "UNKNOWN", "level": "UNKNOWN"}),
        "basis": "the latest engine-created execution; requested values are not provider observations",
        "execution_id": str(latest.get("execution_id", "")),
    }


def _proof_view(state: Mapping[str, Any], task_report: Mapping[str, Any]) -> dict:
    proof = dict(task_report.get("proof") or {})
    if proof.get("proof_id") and not proof.get("receipt_digest"):
        for row in reversed(state.get("proof_receipts") or []):
            if not isinstance(row, Mapping):
                continue
            if str(row.get("proof_id", "")) == str(proof.get("proof_id", "")):
                proof = {**dict(row), **proof}
                break
    if not proof:
        for row in reversed(state.get("proof_receipts") or []):
            if isinstance(row, Mapping):
                proof = dict(row)
                break
    binding = proof.get("creative_review") if isinstance(proof.get("creative_review"), Mapping) else {}
    integrity: list[str] = []
    if proof:
        from . import proof as proof_module

        integrity.extend(proof_module.receipt_problems(proof))
    freshness: list[str] = []
    tasks = [row for row in (state.get("tasks") or []) if isinstance(row, Mapping)]
    if tasks and proof:
        from . import task_execution

        try:
            freshness = task_execution.proof_current_problems(tasks[-1])
        except Exception as exc:  # noqa: BLE001 - old or partial state is reported, not guessed
            freshness = [f"the task proof could not be checked: {type(exc).__name__}: {exc}"]
    if binding:
        from . import creative_proof

        freshness.extend(creative_proof.current_problems(
            binding, state,
            work_digest=str(proof.get("work_digest", "")),
            implementation_fingerprint=str(proof.get("implementation_fingerprint", "")),
        ))
    return {
        "proof_id": str(proof.get("proof_id", "")),
        "acceptance_state": (
            "INVALID_RECEIPT" if integrity else str(proof.get("acceptance_state", "UNKNOWN"))
        ),
        "receipt_digest": str(proof.get("receipt_digest", "")),
        "requirement_verdicts": dict(proof.get("requirement_verdicts") or {}),
        "fresh": not freshness and not integrity,
        "freshness_problems": list(dict.fromkeys(freshness)),
        "integrity_problems": list(dict.fromkeys(integrity)),
        "creative_review": {
            "bound": bool(binding),
            "packet_id": str(binding.get("packet_id", "")),
            "review_id": str(binding.get("review_id", "")),
            "outcome": str(binding.get("outcome", "")),
            "independence_level": str(binding.get("independence_level", "")),
            "binding_digest": str(binding.get("binding_digest", "")),
        },
        "authorization_effect": "none",
    }


def _review_view(state: Mapping[str, Any], task_report: Mapping[str, Any]) -> dict:
    review = dict(task_report.get("review") or {})
    if not review:
        rows = [row for row in (state.get("reviews") or []) if isinstance(row, Mapping)]
        review = dict(rows[-1]) if rows else {}
    return {
        "review_id": str(review.get("review_id", "")),
        "packet_id": str(review.get("packet_id", "")),
        "reviewer_identity": str(review.get("reviewer_identity", "")),
        "reviewer_execution": str(review.get("reviewer_execution", "")),
        "independence_level": str(review.get("independence_level", "UNKNOWN")),
        "outcome": str(review.get("outcome", "NOT_REVIEWED")),
        "findings": list(review.get("findings") or []),
        "blockers": list(task_report.get("review_blockers") or []),
        "reviewed_revision": str(review.get("reviewed_revision", "")),
    }


def _authority_view(
    state: Mapping[str, Any],
    task_report: Mapping[str, Any],
) -> dict:
    gates = dict(task_report.get("gates") or {})
    stage = str(_packet(state).get("stage", ""))
    proof = _proof_view(state, task_report)
    review = _review_view(state, task_report)
    accepted = str(gates.get("human_acceptance_recorded", "") or "")
    pending = ""
    if stage == "S5" and review.get("outcome") == "passed" and not accepted:
        pending = "G3"
    elif gates.get("human_acceptance_pending") and not accepted:
        pending = "TASK_ACCEPTANCE"
    elif gates.get("ahead"):
        pending = str((gates.get("ahead") or [""])[0])
    elif proof.get("proof_id") and not accepted:
        pending = "TASK_ACCEPTANCE"
    subject_digest = ""
    subject_id = ""
    if pending == "G3":
        from . import policy

        packet = _packet(state)
        path = Path(str(packet.get("path", "")))
        subject = policy.review_subject(state, path) if path.is_dir() else None
        if subject is not None:
            subject_digest = str(subject.revision_hash)
            subject_id = str(subject.subject_id)
        elif packet:
            subject_digest = str(packet.get("packet_sha256", "")) or str(
                (proof.get("creative_review") or {}).get("packet_digest", "")
            )
            subject_id = str(packet.get("id", ""))
    elif pending == "TASK_ACCEPTANCE":
        subject_id = str(proof.get("proof_id", ""))
        subject_digest = str(proof.get("receipt_digest", ""))
    return {
        "pending_gate": pending,
        "gate_subject_id": subject_id,
        "gate_subject_digest": subject_digest,
        "human_decision_required": bool(pending or gates.get("human_decision_required")),
        "human_decision_recorded": accepted,
        "permitted_action_boundary": (
            "read-only: display state and ask the authorized human to use the engine's approval/"
            "acceptance channel. This surface cannot record that decision."
        ),
        "authority_effect": "none",
    }


def _blockers(
    task_report: Mapping[str, Any],
    authority: Mapping[str, Any],
    verification: Mapping[str, Any],
) -> list[dict]:
    rows: list[dict] = []
    for problem in verification.get("stale_problems") or []:
        rows.append({"kind": "stale-evidence", "detail": str(problem)})
    for problem in verification.get("review_blockers") or []:
        rows.append({"kind": "review", "detail": str(problem)})
    recovery = dict(task_report.get("recovery") or {})
    if recovery.get("interrupted_operation"):
        rows.append({
            "kind": "interrupted-operation",
            "detail": str(recovery.get("required_human_action") or "an operation was interrupted"),
        })
    if authority.get("pending_gate"):
        rows.append({
            "kind": "human-gate",
            "detail": f"{authority['pending_gate']} is pending; only an authorized human can decide it",
        })
    return rows


def _verification_view(state: Mapping[str, Any], task_report: Mapping[str, Any]) -> dict:
    validation = dict(task_report.get("last_validation") or {})
    proof = _proof_view(state, task_report)
    review = _review_view(state, task_report)
    return {
        "last_validation": {
            "status": str(validation.get("status", "NOT_RUN")),
            "failure_kind": str(validation.get("failure_kind", "")),
            "fresh": bool(validation.get("fresh", False)),
            "validated_revision": dict(validation.get("validated_revision") or {}),
            "stale_problems": list(validation.get("problems") or []),
        },
        "evidence_freshness": str(task_report.get("evidence_freshness", "UNKNOWN")),
        "review": review,
        "proof": proof,
        "unresolved_blockers": [],
        "rendered": dict(task_report.get("rendered") or {}),
    }


def _resources_view(state: Mapping[str, Any]) -> dict:
    from . import efficiency, measurement, skill_intelligence

    try:
        measured = measurement.summarise(state)
    except Exception as exc:  # noqa: BLE001 - a read view must not crash on old state
        measured = {"error": f"{type(exc).__name__}: {exc}"}
    try:
        skills = skill_intelligence.effectiveness(state)
    except Exception as exc:  # noqa: BLE001
        skills = {"error": f"{type(exc).__name__}: {exc}"}
    return {
        "measured": measured,
        "unknowns": [
            "provider token counts and cost when no provider reported them",
            "billing and quota when no supported interface supplied them",
            "model identity beyond the level the engine observed",
        ],
        "efficiency": efficiency.efficiency_config(state),
        "skills": skills,
    }


def _event_cursor(last: Mapping[str, Any]) -> dict:
    if not last:
        return {"schema_version": EVENT_CURSOR_SCHEMA, "seq": 0, "event_id": "", "digest": ""}
    return {
        "schema_version": EVENT_CURSOR_SCHEMA,
        "seq": int(last.get("seq", 0) or 0),
        "event_id": str(last.get("event_id", "")),
        "digest": str(last.get("digest", "")),
    }


def _event_summary(event: Mapping[str, Any]) -> dict:
    return {
        "event_id": str(event.get("event_id", "")),
        "seq": int(event.get("seq", 0) or 0),
        "type": str(event.get("type", "")),
        "recorded_at": str(event.get("recorded_at", "")),
        "task_id": str(event.get("task_id", "")),
        "stage": str(event.get("stage", "")),
        "execution": str(event.get("execution", "")),
        "revision": str(event.get("revision", "")),
        "data": dict(event.get("data") or {}),
    }


def status(
    state: Mapping[str, Any],
    *,
    task_report: Mapping[str, Any] | None = None,
    event_limit: int = 50,
) -> dict:
    """Project the versioned host view. Pure read; no state is mutated."""
    report = dict(task_report) if task_report is not None else _task_report(state)
    packet = _packet(state)
    task_id = str(report.get("task_id") or packet.get("id", ""))
    project = str(state.get("project", ""))
    current_head = str(report.get("current_head", ""))
    revision = current_head or str(
        (report.get("last_validation") or {}).get("validated_revision", {}).get("head", "")
    )
    authority = _authority_view(state, report)
    verification = _verification_view(state, report)
    verification["unresolved_blockers"] = _blockers(report, authority, verification)
    event_rows: list[dict] = []
    integrity: list[str] = []
    root_text = str(state.get("run_root", "") or "")
    if root_text:
        root = Path(root_text)
        event_rows = [row for row in events.read(root) if isinstance(row, Mapping)]
        integrity = events.integrity_problems(root)
    cursor = _event_cursor(event_rows[-1] if event_rows else {})
    return {
        "schema_version": SCHEMA_VERSION,
        "contract": {"name": CONTRACT_NAME, "version": CONTRACT_VERSION},
        "read_only": True,
        "authority_effect": "none",
        "note": READ_ONLY_NOTE,
        "task": {
            "task_id": task_id,
            "run_id": str(state.get("run_id", "")),
            "objective": str(
                report.get("objective")
                or state.get("request")
                or ""
            ),
            "lifecycle_state": str(report.get("status", "UNKNOWN")),
            "stage": str(packet.get("stage", "")),
            "active_attempt": dict(report.get("current_attempt") or {}),
            "repository_revision": revision,
            "revision_drift": bool(report.get("revision_drift", False)),
            "attempts": list(report.get("attempts") or []),
        },
        "execution": {
            "selected_adapter": str(
                (report.get("selected_worker") or {}).get("adapter", "")
                or (report.get("current_attempt") or {}).get("adapter", "")
            ),
            "identity": _identity_claims(state),
            "routing_explanation": {
                "rule": str(((state.get("routing_decisions") or [{}])[-1] or {}).get("rule", "")),
                "reason": str(((state.get("routing_decisions") or [{}])[-1] or {}).get("reason", "")),
                "controls_execution": False,
            },
            "active_operation": dict(report.get("current_operation") or {}),
            "progress": {
                "attempts": len(report.get("attempts") or []),
                "open_executions": list(report.get("open_executions") or []),
                "skills_unmet": list(report.get("skills_unmet") or []),
            },
        },
        "verification": verification,
        "recovery": {
            "interrupted_operation": dict((report.get("recovery") or {}).get("interrupted_operation") or {}),
            "safe_continuation": str((report.get("recovery") or {}).get("safe_continuation", "UNKNOWN")),
            "required_human_action": str((report.get("recovery") or {}).get("required_human_action", "")),
            "last_durable_operation": dict((report.get("recovery") or {}).get("last_durable_operation") or {}),
        },
        "authority": authority,
        "resources": _resources_view(state),
        "events": {
            "cursor": cursor,
            "integrity_problems": integrity,
            "delivery": "poll host_events with the returned cursor; the log is append-only",
        },
        "limits": {
            "read_only": True,
            "no_internal_paths": True,
            "no_secrets": True,
            "project_revision_observed_at": str(report.get("current_head", "")) or "UNKNOWN",
        },
    }


def event_page(
    run_root: Path,
    *,
    cursor: Mapping[str, Any] | None = None,
    limit: int = 100,
) -> dict:
    """Read one page after a cursor, refusing an unknown cursor.

    The cursor is the stable identity of the last event a host processed. If it
    no longer exists in the log (truncation, corruption, wrong run), the answer
    is ``CURSOR_INVALID`` and no events are returned: replaying from the start
    would silently duplicate logical transitions in the host.
    """
    root = Path(run_root)
    bound = max(1, min(int(limit or 100), MAX_EVENTS_PER_PAGE))
    integrity = events.integrity_problems(root)
    rows = [row for row in events.read(root) if isinstance(row, Mapping)]
    if not rows:
        return {
            "schema_version": SCHEMA_VERSION,
            "read_only": True,
            "authority_effect": "none",
            "status": "EMPTY",
            "events": [],
            "cursor": _event_cursor({}),
            "next_cursor": _event_cursor({}),
            "has_more": False,
            "integrity_problems": integrity,
        }
    if cursor:
        seq = int(cursor.get("seq", 0) or 0)
        digest = str(cursor.get("digest", ""))
        event_id = str(cursor.get("event_id", ""))
        if seq < 0 or seq > int(rows[-1].get("seq", 0) or 0):
            return {
                "schema_version": SCHEMA_VERSION,
                "read_only": True,
                "authority_effect": "none",
                "status": "CURSOR_INVALID",
                "events": [],
                "cursor": _event_cursor({}),
                "problems": [f"cursor seq {seq} is outside the log (0..{rows[-1].get('seq')})"],
                "integrity_problems": integrity,
            }
        found = next((row for row in rows if int(row.get("seq", 0) or 0) == seq), None)
        if found is None or str(found.get("digest", "")) != digest or (
            event_id and str(found.get("event_id", "")) != event_id
        ):
            return {
                "schema_version": SCHEMA_VERSION,
                "read_only": True,
                "authority_effect": "none",
                "status": "CURSOR_INVALID",
                "events": [],
                "cursor": _event_cursor({}),
                "problems": ["the cursor does not name an event in this log; refusing to replay"],
                "integrity_problems": integrity,
            }
        remaining = [row for row in rows if int(row.get("seq", 0) or 0) > seq]
    else:
        remaining = rows
    page = remaining[:bound]
    next_cursor = _event_cursor(page[-1]) if page else _event_cursor(rows[-1])
    return {
        "schema_version": SCHEMA_VERSION,
        "read_only": True,
        "authority_effect": "none",
        "status": "OK" if not integrity else "INTEGRITY_PROBLEM",
        "events": [_event_summary(row) for row in page],
        "cursor": _event_cursor(rows[0]) if not cursor else _event_cursor(
            next((row for row in rows if int(row.get("seq", 0) or 0) == int(cursor.get("seq", 0) or 0)), rows[0])
        ),
        "next_cursor": next_cursor,
        "has_more": len(remaining) > len(page),
        "integrity_problems": integrity,
        "event_count": len(rows),
    }


def describe() -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "contract": {"name": CONTRACT_NAME, "version": CONTRACT_VERSION},
        "read_only": True,
        "authority_effect": "none",
        "operations": ["host_status", "host_events"],
        "ownership": {
            "ariadne": [
                "workflow decisions", "task and attempt records", "model/skill recommendations",
                "evidence", "validation", "review", "proof", "recovery state", "human-gate requirements",
            ],
            "host": [
                "user interface", "session navigation", "notifications", "host permissions",
                "host-specific computer/browser interaction", "its own application state",
                "transport to the user",
            ],
        },
        "note": READ_ONLY_NOTE,
    }
