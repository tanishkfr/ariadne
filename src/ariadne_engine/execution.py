"""Execution identity, execution-bound results, and the failure taxonomy (AR-202 T2/T6).

What this module can and cannot do
----------------------------------
The engine *creates* the execution identity at the moment the runtime prepares a
boundary or ingests a result. An identity is:

* generated here (a caller cannot choose one),
* bound to run id, task id (the packet), role, adapter invocation, revision and
  a nonce,
* carried by every result the engine accepts for that execution.

The engine cannot authenticate a person or isolate a process, and this module
never claims either. ``requested`` identity is what the run asked for,
``reported`` identity is what a worker claimed in its own output (untrusted
prose, kept as provenance), and ``observed`` identity is only written when the
runtime itself could establish it. A worker statement is never promoted to
``observed``; when the runtime cannot observe, the value stays ``UNKNOWN``.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Mapping

from . import contracts
from .contracts import ContractError, FAILURE_CLASSES

# ------------------------------------------------------------ state lifecycle

EXECUTION_TRANSITIONS: dict[str, frozenset[str]] = {
    "REQUESTED": frozenset({"CREATED", "UNKNOWN", "FAILED"}),
    "CREATED": frozenset({"STARTED", "FAILED", "UNKNOWN"}),
    "STARTED": frozenset({"OBSERVED", "COMPLETED", "FAILED"}),
    "OBSERVED": frozenset({"COMPLETED", "FAILED"}),
    "COMPLETED": frozenset(),
    "FAILED": frozenset(),
    "UNKNOWN": frozenset({"FAILED"}),
}

TERMINAL_EXECUTION_STATES = ("COMPLETED", "FAILED")

# ------------------------------------------------------------- failure model

FAILURE_SOURCES: dict[str, str] = {
    # worker validation / transport vocabulary (prepare-stage.worker_validation_problems)
    "routine": "IMPLEMENTATION_FAILURE",
    "contract": "VALIDATION_FAILURE",
    "out-of-scope": "AUTHORIZATION_FAILURE",
    "dangerous-action": "AUTHORIZATION_FAILURE",
    "repository-conflict": "CONFLICT",
    "worker-blocked": "IMPLEMENTATION_FAILURE",
    "validation-command": "VALIDATION_FAILURE",
    "validation-timeout": "TIMEOUT",
    # review outcomes
    "review-failed": "REVIEW_FAILURE",
    "review-blocked": "REVIEW_FAILURE",
    # environment / provider / capability
    "provider-unavailable": "PROVIDER_FAILURE",
    "provider-blocked": "PROVIDER_FAILURE",
    "provider-mismatch": "PROVIDER_FAILURE",
    "runtime-unavailable": "ENVIRONMENT_FAILURE",
    "missing-dependency": "ENVIRONMENT_FAILURE",
    "missing-capability": "CAPABILITY_FAILURE",
    # context / revision / interruption
    "context-missing": "CONTEXT_FAILURE",
    "context-stale": "CONTEXT_FAILURE",
    "packet-missing": "CONTEXT_FAILURE",
    "stale-revision": "STALE_REVISION",
    "revision-changed": "STALE_REVISION",
    "duplicate-result": "CONFLICT",
    "interrupted": "INTERRUPTED",
    "orphan-execution": "INTERRUPTED",
    "interrupted-write": "INTERRUPTED",
    # AR-202D design-intelligence vocabulary. Each entry maps a design failure
    # kind onto an existing class; the taxonomy itself is not duplicated and no
    # kind is invented that an existing class already models.
    "reference-unavailable": "CONTEXT_FAILURE",
    "reference-inspection-failed": "VALIDATION_FAILURE",
    "reference-provenance-invalid": "VALIDATION_FAILURE",
    "component-incompatible": "CAPABILITY_FAILURE",
    "design-direction-missing": "CONTEXT_FAILURE",
    "design-direction-stale": "STALE_REVISION",
    "design-direction-unapproved": "AUTHORIZATION_FAILURE",
    "render-capture-failed": "ENVIRONMENT_FAILURE",
    "render-evidence-stale": "STALE_REVISION",
    "accessibility-failure": "VALIDATION_FAILURE",
    "design-review-failure": "REVIEW_FAILURE",
    "requirement-evidence-insufficient": "VALIDATION_FAILURE",
    "refinement-limit-reached": "DESIGN_FAILURE",
}

DESIGN_SOURCE_KINDS: dict[str, str] = {
    "reference-unavailable": "REFERENCE_UNAVAILABLE",
    "reference-inspection-failed": "REFERENCE_INSPECTION_FAILED",
    "reference-provenance-invalid": "REFERENCE_PROVENANCE_INVALID",
    "component-incompatible": "COMPONENT_INCOMPATIBLE",
    "design-direction-missing": "DESIGN_DIRECTION_MISSING",
    "design-direction-stale": "DESIGN_DIRECTION_STALE",
    "design-direction-unapproved": "DESIGN_DIRECTION_UNAPPROVED",
    "render-capture-failed": "RENDER_CAPTURE_FAILED",
    "render-evidence-stale": "RENDER_EVIDENCE_STALE",
    "accessibility-failure": "ACCESSIBILITY_FAILURE",
    "design-review-failure": "DESIGN_REVIEW_FAILURE",
    "requirement-evidence-insufficient": "REQUIREMENT_EVIDENCE_INSUFFICIENT",
    "refinement-limit-reached": "REFINEMENT_LIMIT_REACHED",
}
"""Design failure source -> the design-kind label recorded beside the AR-202 class.

The *class* stays the AR-202 taxonomy so nothing downstream has to learn a second
severity/retry model; the kind preserves which design condition actually happened.
"""

FAILURE_FLAGS: dict[str, dict[str, bool]] = {
    "IMPLEMENTATION_FAILURE": {"retry_allowed": True, "strategy_change_allowed": True, "escalation_required": False},
    "VALIDATION_FAILURE": {"retry_allowed": True, "strategy_change_allowed": False, "escalation_required": False},
    "REVIEW_FAILURE": {"retry_allowed": True, "strategy_change_allowed": False, "escalation_required": False},
    "AUTHORIZATION_FAILURE": {"retry_allowed": False, "strategy_change_allowed": False, "escalation_required": True},
    "CAPABILITY_FAILURE": {"retry_allowed": False, "strategy_change_allowed": True, "escalation_required": True},
    "PROVIDER_FAILURE": {"retry_allowed": True, "strategy_change_allowed": True, "escalation_required": False},
    "TIMEOUT": {"retry_allowed": True, "strategy_change_allowed": True, "escalation_required": False},
    "ENVIRONMENT_FAILURE": {"retry_allowed": True, "strategy_change_allowed": True, "escalation_required": False},
    "CONTEXT_FAILURE": {"retry_allowed": True, "strategy_change_allowed": False, "escalation_required": True},
    "STALE_REVISION": {"retry_allowed": False, "strategy_change_allowed": True, "escalation_required": True},
    "CONFLICT": {"retry_allowed": False, "strategy_change_allowed": True, "escalation_required": True},
    "INTERRUPTED": {"retry_allowed": True, "strategy_change_allowed": False, "escalation_required": False},
    "DESIGN_FAILURE": {"retry_allowed": False, "strategy_change_allowed": True, "escalation_required": True},
    "UNKNOWN": {"retry_allowed": False, "strategy_change_allowed": False, "escalation_required": True},
}
"""Per-class advisory flags.

They are *recorded* facts about what the failure permits, not a second retry
policy: the bounded routine-repair budget (``policy.repair_allowed``) and the
worker lifecycle table stay the only enforcement of how many retries happen.
"""


def executions(state: dict) -> list[dict]:
    value = state.get("executions")
    if not isinstance(value, list):
        return []
    return [record for record in value if isinstance(record, dict)]


def failures(state: dict) -> list[dict]:
    value = state.get("failures")
    if not isinstance(value, list):
        return []
    return [record for record in value if isinstance(record, dict)]


def execution(state: dict, execution_id: str) -> dict | None:
    for record in executions(state):
        if str(record.get("execution_id", "")) == str(execution_id):
            return record
    return None


def task_revision(state: dict, packet: Path | None) -> dict:
    """The stable revision an execution is bound to: baseline + packet identity.

    The run state changes on every transition, so the run-state digest is not a
    usable binding. The project baseline head plus the prepared packet's own
    digest are: they change exactly when the artifact the execution works on
    changes.
    """
    revision = {
        "project": str(state.get("project", "")),
        "baseline": "",
        "packet_id": "",
        "packet_sha256": "",
    }
    if packet is not None:
        packet = Path(packet)
        manifest_path = packet / "manifest.json"
        if manifest_path.is_file():
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                manifest = {}
            if isinstance(manifest, dict):
                revision["packet_id"] = str(manifest.get("packet_id", ""))
                revision["packet_sha256"] = str(manifest.get("packet_sha256", ""))
                baseline = manifest.get("project_baseline")
                if isinstance(baseline, dict):
                    revision["baseline"] = str(baseline.get("head", ""))
    revision["revision_hash"] = hashlib.sha256(
        json.dumps(revision, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return revision


# ---------------------------------------------------------------- record I/O

def _append(state: dict, name: str, record: dict) -> None:
    state.setdefault(name, []).append(record)


def _transition(record: dict, target: str, *, at_field: str, extra: Mapping | None = None) -> dict:
    current = str(record.get("state", "UNKNOWN"))
    if target not in EXECUTION_TRANSITIONS.get(current, frozenset()):
        raise ContractError(f"execution {record.get('execution_id')} cannot move {current} -> {target}")
    record["state"] = target
    record[at_field] = contracts.utc_now()
    if extra:
        record.update({key: value for key, value in extra.items()})
    problems = contracts.execution_problems(record)
    if problems:
        raise ContractError("execution record would be malformed: " + "; ".join(problems))
    return record


def create(
    state: dict,
    *,
    task_id: str,
    role: str,
    adapter: str,
    invocation: str = "",
    requested: Mapping | None = None,
    parent: str = "",
    revision: Mapping | None = None,
    reason: str = "",
) -> dict:
    """Create the engine-owned execution identity for one boundary.

    ``execution_id`` is generated here. There is deliberately no parameter for
    it: an execution id a caller chose is not an execution identity.
    """
    if role not in contracts.EXECUTION_ROLES:
        raise ContractError(f"unsupported execution role: {role}")
    if not str(task_id or "").strip():
        raise ContractError("an execution needs a task id")
    if not str(adapter or "").strip():
        raise ContractError("an execution needs an adapter/runtime invocation")
    record = {
        "schema_version": contracts.SCHEMA_ADAPTIVE,
        "execution_id": contracts.new_execution_id(),
        "run_id": str(state.get("run_id", "")),
        "task_id": str(task_id),
        "role": role,
        "adapter": str(adapter),
        "invocation": str(invocation),
        "state": "CREATED",
        "created_at": contracts.utc_now(),
        "started_at": "",
        "observed_at": "",
        "completed_at": "",
        "failed_at": "",
        "nonce": hashlib.sha256(
            f"{contracts.new_record_id('nonce')}|{task_id}|{role}".encode("utf-8")
        ).hexdigest()[:32],
        "parent_execution": str(parent or ""),
        "requested": {
            "provider": str((requested or {}).get("provider", "") or ""),
            "model": str((requested or {}).get("model", "") or ""),
            "effort": str((requested or {}).get("effort", "") or ""),
            "worker_role": str((requested or {}).get("worker_role", "") or ""),
        },
        "reported": {},
        "observed": {
            "provider": "UNKNOWN",
            "model": "UNKNOWN",
            "source": "unavailable",
        },
        "provider_observed": {},
        "usage": {},
        "revision": dict(revision or {"revision_hash": "unbound"}),
        "result": {},
        "failure": {},
        "provenance": {
            "created_by": "engine",
            "source": "runtime-boundary",
            "policy_version": contracts.POLICY_VERSION,
            "reason": str(reason),
        },
    }
    problems = contracts.execution_problems(record)
    if problems:
        raise ContractError("execution record is malformed: " + "; ".join(problems))
    _append(state, "executions", record)
    return record


def mark_started(state: dict, execution_id: str) -> dict:
    record = _require(state, execution_id)
    return _transition(record, "STARTED", at_field="started_at")


def observe(
    state: dict,
    execution_id: str,
    *,
    provider: str = "",
    model: str = "",
    source: str = "",
    evidence: tuple[str, ...] = (),
) -> dict:
    """Record what the runtime could itself observe about a running execution.

    Only the runtime may observe. A worker-reported provider/model arriving here
    is refused rather than promoted: ``source`` must name an engine-side observer.
    """
    record = _require(state, execution_id)
    if source in ("", "worker", "worker-output", "handoff", "self-reported"):
        raise ContractError(
            "observed identity must come from the runtime, not from worker output; "
            "record the worker's claim as reported identity instead"
        )
    observed = {
        "provider": str(provider or "UNKNOWN") or "UNKNOWN",
        "model": str(model or "UNKNOWN") or "UNKNOWN",
        "source": str(source),
        "evidence": [str(item) for item in evidence],
    }
    record["observed"] = observed
    return _transition(record, "OBSERVED", at_field="observed_at")


def report(state: dict, execution_id: str, *, provider: str = "", model: str = "", evidence: str = "") -> dict:
    """Record a worker's *claim* about its own runtime. Never authoritative."""
    record = _require(state, execution_id)
    claimed = {
        "provider": str(provider or "").strip(),
        "model": str(model or "").strip(),
        "evidence": str(evidence),
        "trust": "worker-reported-unverified",
    }
    record["reported"] = claimed
    return record


# ------------------------------------------------------- economics telemetry

USAGE_FIELDS = (
    "input_tokens",
    "output_tokens",
    "cached_input_tokens",
    "uncached_input_tokens",
    "reasoning_tokens",
    "turns",
    "tool_calls",
    "tool_errors",
    "duration_seconds",
    # AR-204 extends the seam with the execution-efficiency dimensions a task
    # total needs. They are still measurements: a count or a duration the runtime
    # or adapter observed, never a value inferred from a model name.
    "request_count",
    "decision_calls",
    "repair_attempts",
    "worker_executions",
    "reviewer_executions",
    "validation_executions",
    "context_preparation_seconds",
    "provider_latency_seconds",
    "wall_clock_seconds",
)
"""Measured usage fields the engine records when a provider or runtime supplies them.

A field that was not supplied stays ``None``/absent. Nothing here is estimated,
derived or back-filled from a model name, and no billing figure is invented from
tokens: billing is recorded separately, only when a provider reports it
(``economics.record_billing``).
"""

CONTEXT_COMPOSITION_BUCKETS = (
    "static_system",
    "tool_schemas",
    "project_context",
    "retrieved_source",
    "evidence",
    "history",
    "summaries",
)
"""The context-composition buckets recorded when the runtime already knows them."""


def record_usage(
    state: dict,
    execution_id: str,
    *,
    source: str,
    provider: str = "",
    model: str = "",
    model_version: str = "",
    request_id: str = "",
    context_composition: Mapping | None = None,
    **values,
) -> dict:
    """Record provider-reported usage for one execution. Measured, never estimated.

    ``source`` must name the engine-side observer that supplied the figures (the
    adapter or runtime), not a worker's prose. Unknown fields remain absent;
    negative or non-numeric values are refused rather than clamped.
    """
    record = _require(state, execution_id)
    observer = str(source or "").strip()
    if observer.lower() in ("", "worker", "worker-output", "handoff", "self-reported"):
        raise ContractError(
            "usage must come from the adapter or runtime that measured it; a worker's claim is not "
            "a measurement"
        )
    unknown = sorted(set(values) - set(USAGE_FIELDS))
    if unknown:
        raise ContractError("usage record has undeclared field(s): " + ", ".join(unknown))
    measured: dict[str, object] = {}
    for name in USAGE_FIELDS:
        value = values.get(name)
        if value is None:
            continue
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ContractError(f"usage field {name} must be a number, not {type(value).__name__}")
        if float(value) < 0:
            raise ContractError(f"usage field {name} cannot be negative")
        measured[name] = int(value) if float(value).is_integer() else float(value)
    composition: dict[str, object] = {}
    for name, value in dict(context_composition or {}).items():
        if str(name) not in CONTEXT_COMPOSITION_BUCKETS:
            raise ContractError(f"unknown context-composition bucket: {name!r}")
        if isinstance(value, bool) or not isinstance(value, (int, float)) or float(value) < 0:
            raise ContractError(f"context-composition bucket {name} must be a non-negative number")
        composition[str(name)] = int(value) if float(value).is_integer() else float(value)
    usage = {
        "measured": True,
        "source": observer,
        "provider": str(provider or ""),
        "model": str(model or ""),
        "model_version": str(model_version or ""),
        "request_id": str(request_id or ""),
        "recorded_at": contracts.utc_now(),
        "values": measured,
        "context_composition": composition,
    }
    record["usage"] = usage
    return usage


def usage_view(state: dict, execution_id: str) -> dict:
    """The recorded usage for one execution, with unknowns left unknown."""
    record = _require(state, execution_id)
    usage = record.get("usage") if isinstance(record.get("usage"), Mapping) else {}
    values = usage.get("values") if isinstance(usage.get("values"), Mapping) else {}
    return {
        "execution_id": str(record.get("execution_id", "")),
        "measured": bool(usage.get("measured", False)),
        "source": str(usage.get("source", "")),
        "provider": str(usage.get("provider", "")),
        "model": str(usage.get("model", "")),
        "model_version": str(usage.get("model_version", "")),
        "request_id": str(usage.get("request_id", "")),
        "values": {name: values.get(name) for name in USAGE_FIELDS if values.get(name) is not None},
        "unknown_fields": [name for name in USAGE_FIELDS if values.get(name) is None],
        "context_composition": dict(usage.get("context_composition") or {}),
        "note": "only measured fields are recorded; absent fields are unknown, not zero",
    }


def telemetry_summary(state: dict) -> dict:
    """Measured-usage totals across executions. Unknowns stay unknown."""
    rows = executions(state)
    totals: dict[str, float] = {}
    measured_executions = 0
    for record in rows:
        usage = record.get("usage") if isinstance(record.get("usage"), Mapping) else {}
        values = usage.get("values") if isinstance(usage.get("values"), Mapping) else {}
        if not values:
            continue
        measured_executions += 1
        for name, value in values.items():
            totals[str(name)] = totals.get(str(name), 0) + float(value)
    return {
        "executions": len(rows),
        "executions_with_measured_usage": measured_executions,
        "totals": {name: (int(value) if float(value).is_integer() else value) for name, value in sorted(totals.items())},
        "note": "totals cover measured fields only; nothing was estimated",
    }


# ------------------------------------------------- bounded failure classification

def classify_with_decision(
    state: dict,
    *,
    source: str,
    detail: str = "",
    task_id: str = "",
    provider=None,
    projection_entries: Mapping | None = None,
    consequence: str = "LOW",
    execution_id: str = "",
    cache_enabled: bool = True,
) -> dict:
    """Classify a failure: deterministic first, bounded judgement only when needed.

    Code before judgment: the declared failure vocabulary is consulted first and
    a mapped source is classified deterministically — no provider is consulted
    and that fact is recorded in a compiled decision plan. Only an unmapped
    source may be put to a bounded decision, and only inside the safe class
    subset (authorization, revision, conflict and design failures are
    deterministic facts that must never be model-derived).

    AR-205D routes the bounded step through the Decision Compiler, a declared
    projection contract and the batch planner (with safe cache reuse). The
    decision can propose a class; it cannot authorize anything. When the
    provider is unavailable, fails, returns an answer outside the set, or the
    policy refuses the confidence, the class stays ``UNKNOWN`` and the caller is
    told to escalate. The decision record is returned either way, so the
    attempt is evidence rather than a silent fallback.
    """
    deterministic = classify(source, detail)
    from . import decisions

    outcome = decisions.integrations.classify_failure(
        state,
        source=source,
        detail=detail,
        deterministic_class=deterministic,
        task_id=str(task_id),
        provider=provider,
        projection_entries=projection_entries,
        consequence=str(consequence),
        execution_id=str(execution_id),
        cache_enabled=bool(cache_enabled),
    )
    if str(outcome.get("source", "")) == "deterministic":
        derived = str(outcome.get("class", "UNKNOWN"))
        return {
            "class": derived,
            "source": "deterministic",
            "decision_id": "",
            "reason": str(outcome.get("reason", "")),
            "escalation_required": bool(FAILURE_FLAGS[derived]["escalation_required"]),
            "decision": {},
            "plan_id": str(outcome.get("plan_id", "")),
        }
    class_name = str(outcome.get("class", "UNKNOWN"))
    escalation_required = bool(class_name == "UNKNOWN") or bool(outcome.get("escalation_required"))
    return {
        "class": class_name,
        "source": str(outcome.get("source", "fallback-unknown")),
        "decision_id": str(outcome.get("decision_id", "")),
        "reason": str(outcome.get("reason", "")),
        "escalation_required": escalation_required,
        "decision": outcome.get("decision") or {},
        "plan_id": str(outcome.get("plan_id", "")),
        "escalation": outcome.get("escalation") or {},
    }


def complete(state: dict, execution_id: str, *, result: Mapping | None = None, evidence: tuple[str, ...] = ()) -> dict:
    record = _require(state, execution_id)
    if str(record.get("state")) in TERMINAL_EXECUTION_STATES:
        raise ContractError(
            f"execution {execution_id} already finished as {record.get('state')}; a completed result cannot be replayed"
        )
    return _transition(
        record,
        "COMPLETED",
        at_field="completed_at",
        extra={"result": {**dict(result or {}), "evidence": [str(item) for item in evidence]}},
    )


def fail(
    state: dict,
    execution_id: str,
    *,
    source: str,
    evidence: tuple[str, ...] | list[str],
    detail: str = "",
    failure_class: str | None = None,
    design_failure_kind: str = "",
    classification: Mapping | None = None,
) -> tuple[dict, dict]:
    """Mark an execution FAILED with a classified failure. Never fabricates a result."""
    record = _require(state, execution_id)
    if str(record.get("state")) in TERMINAL_EXECUTION_STATES:
        raise ContractError(f"execution {execution_id} already finished as {record.get('state')}")
    evidence_list = [str(item) for item in evidence if str(item)]
    resolved = failure_class or classify(source)
    _transition(
        record,
        "FAILED",
        at_field="failed_at",
        extra={"failure": {"class": resolved, "source": str(source), "evidence": evidence_list}},
    )
    failure = record_failure(
        state,
        source=source,
        operation="execution:fail",
        evidence=evidence_list,
        execution_id=execution_id,
        task_id=str(record.get("task_id", "")),
        revision_hash=str((record.get("revision") or {}).get("revision_hash", "")),
        detail=detail,
        failure_class=failure_class,
        strategy=strategy_id(record),
        design_failure_kind=design_failure_kind,
        classification=classification,
    )
    return record, failure


def abandon(state: dict, execution_id: str, *, source: str, evidence: tuple[str, ...] | list[str], detail: str = "") -> tuple[dict, dict]:
    """Record that an open execution will not produce a result (operator-invoked).

    A truthful *failure*, never a success: the execution moves to FAILED and a
    classified failure is recorded beside it.
    """
    return fail(
        state, execution_id, source=source, evidence=evidence, detail=detail,
        failure_class="INTERRUPTED",
    )


def _require(state: dict, execution_id: str) -> dict:
    record = execution(state, execution_id)
    if record is None:
        raise ContractError(f"no engine-created execution record matches {execution_id!r}")
    return record


# ------------------------------------------------------------ failure records

def classify(source: str, detail: str = "") -> str:
    """Map an existing vocabulary value or free-text reason onto the taxonomy.

    Unmapped input stays ``UNKNOWN``: guessing a class would be worse than
    recording that the class is not known.
    """
    key = str(source or "").strip().lower().replace("_", "-")
    if key in FAILURE_SOURCES:
        return FAILURE_SOURCES[key]
    return "UNKNOWN"


def design_kind(source: str) -> str:
    """The design-specific label for a source, or ``''`` when it is not design work."""
    key = str(source or "").strip().lower().replace("_", "-")
    return DESIGN_SOURCE_KINDS.get(key, "")


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
    failure_class: str | None = None,
    strategy: str = "",
    design_failure_kind: str = "",
    classification: Mapping | None = None,
) -> dict:
    """Record one classified failure. ``evidence`` is required and never invented."""
    resolved = failure_class or classify(source, detail)
    if resolved not in FAILURE_CLASSES:
        raise ContractError(f"unsupported failure class: {resolved}")
    kind = str(design_failure_kind or design_kind(source) or "")
    if kind and kind not in contracts.DESIGN_FAILURE_KINDS:
        raise ContractError(f"unsupported design failure kind: {kind}")
    classification_record = {"source": "deterministic", "decision_id": ""}
    if classification:
        candidate = dict(classification)
        classification_source = str(candidate.get("source", "") or "")
        if classification_source not in contracts.FAILURE_CLASSIFICATION_SOURCES:
            raise ContractError(f"unsupported failure classification source: {classification_source!r}")
        classification_record = {
            "source": classification_source,
            "decision_id": str(candidate.get("decision_id", "")),
            "reason": str(candidate.get("reason", "")),
        }
        if classification_source == "bounded-decision" and resolved not in contracts.DECISION_CLASSIFIABLE_FAILURE_CLASSES:
            raise ContractError(
                f"a bounded decision may not propose the failure class {resolved}; authorization, "
                "revision, conflict and design failures are deterministic facts"
            )
    evidence_list = [str(item) for item in evidence if str(item)]
    if not evidence_list:
        raise ContractError("a failure needs at least one piece of evidence")
    flags = FAILURE_FLAGS[resolved]
    record = {
        "schema_version": contracts.SCHEMA_ADAPTIVE,
        "failure_id": contracts.new_record_id("fail"),
        "class": resolved,
        "design_kind": kind,
        "source": str(source),
        "operation": str(operation),
        "execution": str(execution_id),
        "task_id": str(task_id),
        "revision_hash": str(revision_hash),
        "detail": str(detail),
        "strategy": str(strategy or ""),
        "evidence": evidence_list,
        "classification": classification_record,
        "retry_allowed": flags["retry_allowed"],
        "strategy_change_allowed": flags["strategy_change_allowed"],
        "escalation_required": flags["escalation_required"],
        "recorded_at": contracts.utc_now(),
    }
    problems = contracts.failure_problems(record)
    if problems:
        raise ContractError("failure record is malformed: " + "; ".join(problems))
    _append(state, "failures", record)
    return record


def prior_failures(state: dict, *, task_id: str, failure_class: str | None = None) -> list[dict]:
    records = [item for item in failures(state) if str(item.get("task_id", "")) == str(task_id)]
    if failure_class:
        records = [item for item in records if item.get("class") == failure_class]
    return records


def last_failure(state: dict, *, task_id: str = "") -> dict | None:
    records = prior_failures(state, task_id=task_id) if task_id else failures(state)
    return records[-1] if records else None


# ------------------------------------------------------------------ identity

def identity_view(state: dict, execution_id: str, *, reported: Mapping | None = None) -> dict:
    """requested / reported / observed identity, with the mismatch recorded explicitly.

    AR-203 adds the provider-observed channel and the per-field claim level, so a
    consumer can see *who established each fact* rather than inferring it from
    which field happens to be populated.
    """
    record = execution(state, execution_id)
    if record is None:
        raise ContractError(f"no engine-created execution record matches {execution_id!r}")
    requested = dict(record.get("requested") or {})
    claimed = dict(reported if reported is not None else (record.get("reported") or {}))
    observed = dict(record.get("observed") or {})
    provider_observed = dict(record.get("provider_observed") or {})
    mismatches: list[str] = []
    for field in ("provider", "model"):
        asked = str(requested.get(field, "") or "").strip()
        said = str(claimed.get(field, "") or "").strip()
        if asked and said and asked.lower() != said.lower():
            mismatches.append(f"requested {field} {asked!r} but the execution reported {field} {said!r}")
        seen = str(provider_observed.get(field, "") or observed.get(field, "") or "").strip()
        if asked and seen and seen.upper() != "UNKNOWN" and asked.lower() != seen.lower():
            mismatches.append(f"requested {field} {asked!r} but the execution observed {field} {seen!r}")
    from . import provenance

    claims = provenance.identity_claims(record)
    return {
        "execution": execution_id,
        "requested": requested,
        "reported": claimed,
        "observed": observed,
        "provider_observed": provider_observed,
        "claims": claims,
        "observed_available": str(observed.get("source", "")) not in ("", "unavailable"),
        "provider_observed_available": bool(provider_observed),
        "mismatches": mismatches,
        "mismatch": bool(mismatches),
    }


def mismatch_decision(view: Mapping, *, pinned: bool) -> tuple[str, str]:
    """Whether an identity mismatch may proceed.

    A mismatch is always recorded. It refuses only when the task pinned a model
    or provider identity (a declared contract), because then the mismatch means
    the execution did not follow the instruction the run was authorized under.
    """
    if not view.get("mismatch"):
        return "accepted", ""
    if pinned:
        return "refused", (
            "the recorded worker runtime does not match the pinned provider/model for this task: "
            + "; ".join(str(item) for item in view.get("mismatches", []))
        )
    return "accepted", (
        "requested and reported runtime differ; recorded as provenance, not treated as a failure "
        "because this task pins no model identity: " + "; ".join(str(item) for item in view.get("mismatches", []))
    )


def verify_result(
    state: dict,
    execution_id: str,
    *,
    role: str,
    task_id: str,
    revision_hash: str = "",
) -> list[str]:
    """Preconditions for accepting a result for one execution. Fail closed."""
    problems: list[str] = []
    record = execution(state, execution_id)
    if record is None:
        return [
            f"no engine-created execution {execution_id!r} exists for this run; a result must name an "
            "execution the engine created"
        ]
    problems.extend(contracts.execution_problems(record))
    if str(record.get("role", "")) != role:
        problems.append(
            f"execution {execution_id} is a {record.get('role')} execution, not a {role} execution"
        )
    if task_id and str(record.get("task_id", "")) != str(task_id):
        problems.append(
            f"execution {execution_id} was created for task {record.get('task_id')}, "
            f"not {task_id}"
        )
    if str(record.get("state", "")) in TERMINAL_EXECUTION_STATES:
        problems.append(
            f"execution {execution_id} already finished as {record.get('state')}; "
            "a finished execution cannot accept another result"
        )
    if revision_hash and str((record.get("revision") or {}).get("revision_hash", "")) != revision_hash:
        problems.append(
            f"execution {execution_id} is bound to a different revision than the current boundary"
        )
    return problems


def open_executions(state: dict, *, role: str | None = None, task_id: str | None = None) -> list[dict]:
    records = []
    for record in executions(state):
        if str(record.get("state", "")) in TERMINAL_EXECUTION_STATES:
            continue
        if role and str(record.get("role", "")) != role:
            continue
        if task_id and str(record.get("task_id", "")) != str(task_id):
            continue
        records.append(record)
    return records


def latest_execution(state: dict, *, role: str, task_id: str) -> dict | None:
    matches = [record for record in executions(state) if record.get("role") == role and str(record.get("task_id", "")) == str(task_id)]
    return matches[-1] if matches else None


def strategy_key(record: Mapping) -> str:
    """A stable, full name for 'the strategy that already failed'."""
    requested = record.get("requested") if isinstance(record.get("requested"), Mapping) else {}
    return "|".join(
        str(item or "")
        for item in (
            record.get("role", ""),
            record.get("adapter", ""),
            (requested or {}).get("provider", ""),
            (requested or {}).get("model", ""),
            (requested or {}).get("worker_role", ""),
        )
    )


def strategy_id(record: Mapping) -> str:
    """The routing candidate id behind an execution.

    ``bulk``/``strong``/``senior-reasoning`` for an implementation worker, the
    provider id for a reasoning session, the role for a validator or reviewer.
    Routing compares this against the strategy that failed, so "do not repeat the
    strategy that already failed" is decided on the candidate the operator sees.
    """
    requested = record.get("requested") if isinstance(record.get("requested"), Mapping) else {}
    role = str(record.get("role", ""))
    if role == "implementer":
        return str((requested or {}).get("worker_role", "") or "implementer")
    if role == "reasoner":
        provider = str((requested or {}).get("provider", "") or "")
        if provider:
            return provider
        adapter = str(record.get("adapter", ""))
        return adapter.split(":", 1)[-1] if ":" in adapter else adapter
    return role or "unknown"


def status_report(state: dict, *, limit: int = 20) -> dict:
    """An honest summary for the operator: what ran, what is open, what failed."""
    records = executions(state)
    rows = []
    for record in records[-limit:]:
        view = identity_view(state, str(record.get("execution_id", "")))
        rows.append({
            "execution_id": record.get("execution_id"),
            "role": record.get("role"),
            "task_id": record.get("task_id"),
            "adapter": record.get("adapter"),
            "state": record.get("state"),
            "requested": view["requested"],
            "reported": view["reported"],
            "observed": view["observed"],
            "mismatch": view["mismatch"],
            "created_at": record.get("created_at"),
            "completed_at": record.get("completed_at") or record.get("failed_at") or "",
        })
    return {
        "executions": len(records),
        "open": len(open_executions(state)),
        "rows": rows,
        "failures": failures(state)[-limit:],
        "failure_classes": sorted({str(item.get("class")) for item in failures(state)}),
    }


def valid_execution_id(value: str) -> bool:
    return bool(re.fullmatch(r"exe_[0-9TZ]+_[0-9a-f]{8}", value or ""))


__all__ = [
    "EXECUTION_TRANSITIONS",
    "TERMINAL_EXECUTION_STATES",
    "FAILURE_SOURCES",
    "FAILURE_FLAGS",
    "DESIGN_SOURCE_KINDS",
    "USAGE_FIELDS",
    "CONTEXT_COMPOSITION_BUCKETS",
    "executions",
    "failures",
    "execution",
    "task_revision",
    "create",
    "mark_started",
    "observe",
    "report",
    "complete",
    "fail",
    "abandon",
    "classify",
    "classify_with_decision",
    "design_kind",
    "record_failure",
    "record_usage",
    "usage_view",
    "telemetry_summary",
    "prior_failures",
    "last_failure",
    "identity_view",
    "mismatch_decision",
    "verify_result",
    "open_executions",
    "latest_execution",
    "strategy_key",
    "strategy_id",
    "status_report",
    "valid_execution_id",
]
