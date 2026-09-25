"""The canonical, append-only engine event log (AR-202 T8).

One machine-readable source of structured truth lives beside the run state:

``<run_root>/engine-events.jsonl``
    one JSON object per line, chained by digest so a rewritten or reordered log
    is detectable. Events are *appended*: nothing in this module rewrites or
    repairs an existing line.

The human/legacy surfaces stay compatibility projections, not competing
sources:

* ``OPERATIONS.md`` is the operator view (written by the runtime, unchanged);
* ``worker-telemetry.jsonl`` keeps its AR-201 row schema and receives one row
  per engine event through the projector the runtime binds.

An event is not authorization and not evidence by itself: it records that the
engine decided or observed something, and it carries the execution identity,
revision and decision ids needed to find the record that *is* the evidence.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Callable, Mapping

from . import contracts
from .contracts import ContractError

LOG_NAME = "engine-events.jsonl"

EVENT_TYPES = (
    "task_characterized",
    "context_decided",
    "context_cache_hit",
    "context_invalidated",
    "route_selected",
    "execution_created",
    "execution_started",
    "execution_observed",
    "execution_completed",
    "execution_failed",
    "fallback_selected",
    "recovery_proposed",
    "recovery_applied",
    "approval_recorded",
    "approval_consumed",
    "validation_recorded",
    "review_recorded",
    "failure_classified",
    # AR-202D design-intelligence vocabulary. The same append-only log and the
    # same digest chain carry them; there is no second design event system.
    "design_task_characterized",
    "design_plan_selected",
    "reference_found",
    "reference_accessed",
    "reference_inspected",
    "reference_analysed",
    "reference_used",
    "component_candidate_evaluated",
    "design_direction_created",
    "design_direction_approved",
    "design_requirement_recorded",
    "rendered_evidence_recorded",
    "rendered_evidence_verified",
    "design_review_started",
    "design_finding_recorded",
    "refinement_started",
    "refinement_completed",
    # AR-203 verification-plane vocabulary. The same append-only log and the same
    # digest chain carry them; there is no second verification event system.
    "capability_declared",
    "capability_observed",
    "capability_verified",
    "execution_identity_observed",
    "review_independence_established",
    "verification_started",
    "verification_observed",
    "verification_reproduced",
    "verification_failed",
    "verification_stale",
    "decision_batch_created",
    "decision_recorded",
    "decision_low_confidence",
    "decision_failed",
    # AR-204 harness-economics vocabulary. The same append-only log and the same
    # digest chain carry them; there is no second economics event system.
    "usage_recorded",
    "billing_recorded",
    "cache_observed",
    "output_externalized",
    "history_compacted",
    "path_selected",
    "efficiency_configured",
    # AR-205D decision-intelligence vocabulary. The same append-only log and the
    # same digest chain carry them; there is no second decision event system.
    "decision_plan_compiled",
    "decision_fast_path",
    "decision_graph_created",
    "decision_graph_node",
    "decision_cache_reused",
    "decision_cache_invalidated",
    "decision_escalated",
    "decision_second_opinion",
    "generation_justified",
    "decision_outcome_recorded",
)
"""The declared event vocabulary. A type outside this set is refused, so the log
cannot accumulate an undocumented ad-hoc event name."""

_EVENT_LIMIT = 2000

_PROJECTOR: Callable[[Path, dict], None] | None = None


def bind_projector(projector: Callable[[Path, dict], None] | None) -> None:
    """Register the runtime's legacy telemetry writer as a projection target."""
    global _PROJECTOR
    _PROJECTOR = projector


def log_path(run_root: Path) -> Path:
    return Path(run_root) / LOG_NAME


def _canonical(payload: Mapping) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)


def last_event(run_root: Path) -> dict:
    path = log_path(run_root)
    if not path.is_file():
        return {}
    last = {}
    try:
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    value = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(value, dict):
                    last = value
    except OSError:
        return {}
    return last


def emit(run_root: Path, event_type: str, **payload) -> dict:
    """Append one event and return it. Never rewrites an existing line."""
    if event_type not in EVENT_TYPES:
        raise ContractError(f"unsupported engine event type: {event_type}")
    run_root = Path(run_root)
    previous = last_event(run_root)
    record = {
        "schema_version": contracts.SCHEMA_ADAPTIVE,
        "event_id": contracts.new_record_id("evt"),
        "type": event_type,
        "recorded_at": contracts.utc_now(),
        "seq": int(previous.get("seq", 0) or 0) + 1,
        "previous_digest": str(previous.get("digest", "")),
        "run_id": str(payload.pop("run_id", "") or ""),
        "task_id": str(payload.pop("task_id", "") or ""),
        "stage": str(payload.pop("stage", "") or ""),
        "execution": str(payload.pop("execution", "") or ""),
        "revision": str(payload.pop("revision", "") or ""),
        "actor": str(payload.pop("actor", "") or ""),
        "data": {key: value for key, value in payload.items()},
    }
    record["digest"] = hashlib.sha256(
        (str(previous.get("digest", "")) + _canonical(record)).encode("utf-8")
    ).hexdigest()
    run_root.mkdir(parents=True, exist_ok=True)
    with log_path(run_root).open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(record, sort_keys=True) + "\n")
    if _PROJECTOR is not None:
        try:
            _PROJECTOR(run_root, record)
        except Exception:  # a legacy projection must never break the engine path
            pass
    return record


def read(run_root: Path, *, limit: int | None = None, event_type: str | None = None) -> list[dict]:
    """Read events oldest-first. The log is never modified by reading it."""
    path = log_path(Path(run_root))
    if not path.is_file():
        return []
    values: list[dict] = []
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(value, dict):
                continue
            if event_type and value.get("type") != event_type:
                continue
            values.append(value)
    except OSError:
        return []
    if len(values) > _EVENT_LIMIT:
        values = values[-_EVENT_LIMIT:]
    return values[-limit:] if limit else values


def integrity_problems(run_root: Path) -> list[str]:
    """Verify the digest chain. A broken chain is a finding, never repaired."""
    problems: list[str] = []
    previous = ""
    seq = 0
    for index, event in enumerate(read(run_root), start=1):
        if int(event.get("seq", 0) or 0) != seq + 1:
            problems.append(f"event sequence break at line {index}")
            return problems
        seq = int(event["seq"])
        if str(event.get("previous_digest", "")) != previous:
            problems.append(f"event chain break at seq {seq}")
            return problems
        candidate = dict(event)
        digest = str(candidate.pop("digest", ""))
        if digest != hashlib.sha256((previous + _canonical(candidate)).encode("utf-8")).hexdigest():
            problems.append(f"event digest mismatch at seq {seq}")
            return problems
        previous = digest
    return problems


def summarise(run_root: Path) -> dict:
    """A compact, honest view of the log for the operator."""
    events = read(run_root)
    counts: dict[str, int] = {}
    for event in events:
        key = str(event.get("type", "unknown"))
        counts[key] = counts.get(key, 0) + 1
    return {
        "path": str(log_path(Path(run_root))),
        "events": len(events),
        "types": counts,
        "last": str((events[-1].get("type") if events else "")),
        "integrity_problems": integrity_problems(run_root),
    }


def valid_type(value: str) -> bool:
    return bool(re.fullmatch(r"[a-z_]+", value or "")) and value in EVENT_TYPES


__all__ = [
    "LOG_NAME",
    "EVENT_TYPES",
    "bind_projector",
    "log_path",
    "emit",
    "read",
    "last_event",
    "integrity_problems",
    "summarise",
    "valid_type",
]
