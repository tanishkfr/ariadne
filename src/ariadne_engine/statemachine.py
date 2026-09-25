"""The single transition choke point.

Everything that can change a *protected* field of run state goes through
``apply_transition``:

* ``state["packets"]``            (stage progression: appending one prepared packet)
* ``state["worker"]["lifecycle"]``
* ``state["worker"]["implementation_state"]``
* ``state["worker"]["validation_state"]``
* ``state["worker"]["review_state"]``
* ``state["worker"]["acceptance_state"]``

A transition is *proposed* by any command and *permitted* only when its
preconditions hold (``policy.continuation_problems``, gate satisfaction, repair
budget, evidence). The table below is the whole lifecycle: a request that is not
in it is refused with the caller's own reason preserved verbatim, and a refused
request changes nothing (``apply_transition`` raises before mutating, and the
caller persists only after it returns).

The four success concepts stay separate on purpose: an implementation is not a
validation, a validation is not a review, and a review is not an acceptance.
"""

from __future__ import annotations

from typing import Mapping

from . import contracts
from .contracts import ContractError, InvalidTransition, PolicyRefusal

# --------------------------------------------------------------- stage table

STAGE_TRANSITIONS: frozenset[tuple[str | None, str | None]] = frozenset({
    (None, "S1"),
    ("S1", "S1"),        # reasoner retry: a new linked child at the same boundary
    ("S1", "S2"),
    ("S1", "S3"),
    ("S2", "S2"),        # reasoner retry
    ("S2", "S3"),
    ("S3", "S3"),        # rejected direction / reasoner retry: a new linked S3 child
    ("S3", "S4A"),
    ("S4A", "S4A"),      # reasoner retry at the same boundary
    ("S4A", "S4B"),
    ("S4B", "S4B"),      # routine repair or escalation
    ("S4B", "S5"),
    ("S5", "S5"),        # re-prepared review boundary
    ("S5", "S6"),
    ("S6", None),
})

# ------------------------------------------------------ worker lifecycle table

baseline = "baseline"
validated = "validated"
routine_repair = "routine-repair"
escalation_required = "escalation-required"
reviewed = "reviewed"
accepted = "accepted"
rejected = "rejected"
validation_pending = "validation-pending"
repair_or_escalation = "repair-or-escalation"

WORKER_LIFECYCLE_TRANSITIONS: frozenset[tuple[str, str]] = frozenset({
    (baseline, baseline),                    # a new worker attempt re-baselines
    (routine_repair, baseline),              # bounded repair: new attempt
    (escalation_required, baseline),         # escalation: stronger worker attempt
    (validation_pending, baseline),          # a fresh attempt after a complete return
    (repair_or_escalation, baseline),        # a fresh attempt after a partial return
    (baseline, validated),
    (baseline, routine_repair),
    (baseline, escalation_required),
    (routine_repair, validated),
    (routine_repair, escalation_required),
    (baseline, validation_pending),          # the worker returned a complete handoff
    (routine_repair, validation_pending),
    (escalation_required, validation_pending),
    (baseline, repair_or_escalation),        # the worker returned partial or blocked
    (routine_repair, repair_or_escalation),
    (escalation_required, repair_or_escalation),
    (validation_pending, validated),         # independent validation ran and passed
    (validation_pending, routine_repair),
    (validation_pending, escalation_required),
    (validated, reviewed),
    (reviewed, accepted),
    (reviewed, rejected),
})

LIFECYCLE_FIELDS = (
    "implementation_state",
    "validation_state",
    "review_state",
    "acceptance_state",
)

TRANSITION_HISTORY_LIMIT = 50


def current_stage(state: dict) -> str | None:
    packets = state.get("packets") or []
    if not packets:
        return None
    return str(packets[-1].get("stage") or "") or None


def lifecycle_of(state: dict) -> str:
    worker = state.get("worker") or {}
    return str(worker.get("lifecycle") or baseline)


def assert_transition(kind: str, current: str | None, target: str | None) -> None:
    """Raise ``InvalidTransition`` unless (current, target) is in the table."""
    if kind == "stage":
        if (current, target) not in STAGE_TRANSITIONS:
            raise InvalidTransition(
                f"Stage transition {current or 'start'} -> {target or 'done'} is not permitted by the declared table"
            )
        return
    if kind == "worker-lifecycle":
        if current is None or target is None or (current, target) not in WORKER_LIFECYCLE_TRANSITIONS:
            raise InvalidTransition(
                f"Worker lifecycle transition {current or 'unknown'} -> {target or 'unknown'} "
                "is not permitted by the declared table"
            )
        return
    raise ContractError(f"unsupported transition kind: {kind}")


def _validate_lifecycle_fields(request: contracts.TransitionRequest) -> None:
    unknown = sorted(set(request.fields) - set(LIFECYCLE_FIELDS) - {"lifecycle", "last_validation", "acceptance_evidence"})
    if unknown:
        raise ContractError("worker transition carries undeclared field(s): " + ", ".join(unknown))
    target = request.to
    fields = dict(request.fields)
    if target == validated and fields.get("validation_state") not in (None, "VALIDATED"):
        raise PolicyRefusal(["a validated worker transition cannot carry another validation state"])
    if target == accepted and fields.get("acceptance_state") not in (None, "ACCEPTED"):
        raise PolicyRefusal(["an accepted transition cannot carry another acceptance state"])
    if target == rejected and fields.get("acceptance_state") not in (None, "REJECTED"):
        raise PolicyRefusal(["a rejected transition cannot carry another acceptance state"])


def apply_transition(
    state: dict,
    request: contracts.TransitionRequest,
    *,
    permitted: bool,
    problems: list[str] | None = None,
) -> dict:
    """Apply one permitted transition in memory and return the state.

    The caller persists the returned state atomically. When ``permitted`` is
    false the request is refused with the supplied problems, and no field of
    ``state`` is touched.
    """
    if not permitted:
        raise PolicyRefusal(problems or ["the requested transition is not permitted"])
    if request.kind == "stage":
        current = current_stage(state)
        assert_transition("stage", current, request.to)
        if not isinstance(request.packet, dict) or not request.packet.get("id"):
            raise ContractError("a stage transition must carry the prepared packet entry")
        state.setdefault("packets", []).append(request.packet)
        state["last_transition"] = _record(request, from_state=current or "start", to_state=str(request.to))
        history = state.setdefault("transitions", [])
        history.append(state["last_transition"])
        if len(history) > TRANSITION_HISTORY_LIMIT:
            state["transitions"] = history[-TRANSITION_HISTORY_LIMIT:]
        return state
    if request.kind == "worker-lifecycle":
        _validate_lifecycle_fields(request)
        current = lifecycle_of(state)
        assert_transition("worker-lifecycle", current, request.to)
        worker = state.setdefault("worker", {})
        for name, value in request.fields.items():
            if name in LIFECYCLE_FIELDS or name in ("last_validation", "acceptance_evidence"):
                worker[name] = value
        worker["lifecycle"] = request.to
        worker["lifecycle_recorded_at"] = contracts.utc_now()
        state["last_transition"] = _record(request, from_state=current, to_state=request.to)
        history = state.setdefault("transitions", [])
        history.append(state["last_transition"])
        if len(history) > TRANSITION_HISTORY_LIMIT:
            state["transitions"] = history[-TRANSITION_HISTORY_LIMIT:]
        return state
    raise ContractError(f"unsupported transition kind: {request.kind}")


def _record(request: contracts.TransitionRequest, *, from_state: str, to_state: str) -> dict:
    return {
        "schema_version": contracts.SCHEMA_RECORD,
        "kind": request.kind,
        "from": from_state,
        "to": to_state,
        "reason": request.reason,
        "evidence": list(request.evidence),
        "actor": request.actor,
        "operation": request.operation,
        "recorded_at": contracts.utc_now(),
    }


def worker_transition_for(
    status_value: str,
    failure_kind: str = "routine",
    repair_attempts: int = 0,
    repair_limit: int = 2,
) -> dict:
    """Classify one independent validation result into a permitted transition.

    This is the runtime's existing ``worker_outcome`` classification, kept as a
    pure function so the caller cannot mutate a protected field itself.
    """
    if status_value == "passed":
        return {
            "to": validated,
            "fields": {"implementation_state": "IMPLEMENTED", "validation_state": "VALIDATED"},
            "retryable": False,
            "escalation_required": False,
            "next": "Prepare the isolated independent review.",
        }
    if status_value == "blocked" or failure_kind in {
        "contract", "out-of-scope", "dangerous-action", "repository-conflict", "worker-blocked"
    }:
        return {
            "to": escalation_required,
            "fields": {"implementation_state": "IMPLEMENTED", "validation_state": "BLOCKED"},
            "retryable": False,
            "escalation_required": True,
            "next": "Stop and escalate the worker conflict to a stronger worker or senior reasoning agent.",
        }
    if repair_attempts < repair_limit:
        remaining = repair_limit - repair_attempts
        return {
            "to": routine_repair,
            "fields": {"implementation_state": "IMPLEMENTED", "validation_state": "FAILED"},
            "retryable": True,
            "escalation_required": False,
            "next": f"Prepare one bounded routine repair retry ({remaining} remaining).",
        }
    return {
        "to": escalation_required,
        "fields": {"implementation_state": "IMPLEMENTED", "validation_state": "FAILED"},
        "retryable": False,
        "escalation_required": True,
        "next": "Stop: the routine repair budget is exhausted; escalate the implementation.",
    }
