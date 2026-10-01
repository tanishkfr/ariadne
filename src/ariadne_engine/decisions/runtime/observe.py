"""Shadow observation: run the runtime beside a decision that has already been made.

This is the only place the Decision Runtime touches the real engine paths, and it is
built so that it *cannot* influence them:

* the caller passes in the authoritative result, which is already recorded;
* :func:`observe` returns the shadow record, and nothing else the caller can use;
* every call is wrapped so an exception becomes ``runtime_failed=True`` on the record
  rather than propagating into the decision path;
* the recorded ``execution_effect`` is the literal ``"none"`` and the record validator
  refuses any other value.

The order matters and is not negotiable: the authoritative path runs first, unmodified,
and only then does the runtime see the question. A shadow mode implemented the other way
round — runtime first, then decide whether to use it — is a fallback with extra steps
and none of the evidence.

:func:`observe_many` handles the multi-question case. Several independent questions over
one projected state go to the runtime as one bounded inference, which is the whole point
of having a batching runtime, and each answer becomes its own shadow record.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from ...contracts import ContractError
from ..contracts import DecisionQuestion
from . import shadow as shadow_module
from .session import DecisionRuntime

OBSERVER_VERSION = "ar-206-observer-1"
"""The observer's own record shape."""


def observe(
    state: dict,
    runtime: DecisionRuntime,
    *,
    question: DecisionQuestion | Mapping[str, Any],
    projection: Mapping[str, Any],
    authoritative_answer: str,
    authoritative_decision_id: str = "",
    task_id: str = "",
    definition: str = "",
    ground_truth: str = "",
) -> dict:
    """Record one shadow prediction beside an already-made decision."""
    record = question.as_record() if isinstance(question, DecisionQuestion) else dict(question)
    available, reason = runtime.available()
    if not available:
        return {
            "observer": OBSERVER_VERSION,
            "recorded": False,
            "runtime_failed": True,
            "reason": str(reason),
            "execution_effect": "none",
        }
    status = runtime.status()
    try:
        response = runtime.decide(dict(projection), [record])
    except Exception as exc:  # noqa: BLE001 - a shadow failure is recorded, never raised into the path
        return {
            "observer": OBSERVER_VERSION,
            "recorded": False,
            "runtime_failed": True,
            "reason": f"the decision runtime failed during shadow observation: {exc}",
            "execution_effect": "none",
        }
    slot = dict(response.get("answers", {}) or {}).get(f"0:{record.get('question_id', '')}", {})
    abstained = bool(slot.get("abstained")) or not slot.get("valid", False)
    answer = "" if abstained else str(slot.get("answer", ""))
    stored = shadow_module.record_shadow(
        state,
        question=record,
        projection_digest=str(projection.get("digest", "")),
        answer=answer,
        distribution=slot.get("distribution", {}),
        confidence=slot.get("confidence"),
        confidence_kind=str(slot.get("confidence_kind", "PROVIDER_PROBABILITY")),
        authoritative_answer=str(authoritative_answer),
        authoritative_decision_id=str(authoritative_decision_id),
        ground_truth=str(ground_truth),
        runtime={
            "runtime_version": status.get("runtime_version", ""),
            "implementation": status.get("implementation", ""),
            "implementation_revision": status.get("implementation_revision", ""),
            "model": status.get("model", ""),
            "model_revision": status.get("model_revision", ""),
            "device": status.get("device", ""),
        },
        task_id=str(task_id),
        definition=str(definition or record.get("projection_contract", "")),
        runtime_kind=str(status.get("runtime_kind", "local_bounded")),
        abstained=abstained,
        reason=str(slot.get("reason", "")) if abstained else "",
    )
    return {
        "observer": OBSERVER_VERSION,
        "recorded": True,
        "runtime_failed": False,
        "shadow_id": stored["shadow_id"],
        "answer": answer,
        "abstained": abstained,
        "agreement": stored["agreement"],
        "confidence": stored["confidence"],
        "confidence_kind": stored["confidence_kind"],
        "model_revision": stored["model_revision"],
        "execution_effect": "none",
        "note": "the authoritative decision was already recorded; this observation cannot change it",
    }


def observe_many(
    state: dict,
    runtime: DecisionRuntime,
    *,
    questions: Sequence[DecisionQuestion | Mapping[str, Any]],
    projection: Mapping[str, Any],
    authoritative: Mapping[str, str],
    task_id: str = "",
    definition: str = "",
) -> dict:
    """Shadow-observe several independent questions over one projected state.

    One bounded inference for all of them, which is the batching the runtime exists to
    provide. Results are mapped back by question id; a question the runtime did not
    answer is recorded as an abstention rather than dropped, so coverage is visible.
    """
    records = [q.as_record() if isinstance(q, DecisionQuestion) else dict(q) for q in questions]
    if not records:
        return {"observer": OBSERVER_VERSION, "recorded": 0, "results": [], "execution_effect": "none"}
    available, reason = runtime.available()
    if not available:
        return {
            "observer": OBSERVER_VERSION,
            "recorded": 0,
            "runtime_failed": True,
            "reason": str(reason),
            "results": [],
            "execution_effect": "none",
        }
    status = runtime.status()
    results: list[dict] = []
    try:
        response = runtime.decide(dict(projection), records)
    except Exception as exc:  # noqa: BLE001
        return {
            "observer": OBSERVER_VERSION,
            "recorded": 0,
            "runtime_failed": True,
            "reason": f"the decision runtime failed during shadow observation: {exc}",
            "results": [],
            "execution_effect": "none",
        }
    slots = dict(response.get("answers", {}) or {})
    for record in records:
        question_id = str(record.get("question_id", ""))
        slot = dict(slots.get(f"0:{question_id}", {}))
        abstained = bool(slot.get("abstained")) or not slot.get("valid", False)
        stored = shadow_module.record_shadow(
            state,
            question=record,
            projection_digest=str(projection.get("digest", "")),
            answer="" if abstained else str(slot.get("answer", "")),
            distribution=slot.get("distribution", {}),
            confidence=slot.get("confidence"),
            confidence_kind=str(slot.get("confidence_kind", "PROVIDER_PROBABILITY")),
            authoritative_answer=str(dict(authoritative).get(question_id, "")),
            runtime={
                "runtime_version": status.get("runtime_version", ""),
                "implementation": status.get("implementation", ""),
                "implementation_revision": status.get("implementation_revision", ""),
                "model": status.get("model", ""),
                "model_revision": status.get("model_revision", ""),
                "device": status.get("device", ""),
            },
            task_id=str(task_id),
            definition=str(definition or record.get("projection_contract", "")),
            runtime_kind=str(status.get("runtime_kind", "local_bounded")),
            abstained=abstained,
            reason=str(slot.get("reason", "")) if abstained else "",
        )
        results.append(
            {
                "question_id": question_id,
                "shadow_id": stored["shadow_id"],
                "answer": stored["answer"],
                "abstained": bool(abstained),
                "agreement": stored["agreement"],
                "confidence": stored["confidence"],
                "model_revision": stored["model_revision"],
            }
        )
    return {
        "observer": OBSERVER_VERSION,
        "recorded": len(results),
        "questions": len(records),
        "inference_calls": 1,
        "results": results,
        "runtime_failed": False,
        "execution_effect": "none",
        "note": "one bounded inference covered every independent question over this projection",
    }


def require_isolated(state: Mapping[str, Any]) -> None:
    """Refuse to continue when a stored shadow record claims an execution effect.

    Called from the diagnostics path. A shadow record that says it acted is a bug, and
    this raises rather than reporting it, because the alternative is a run that quietly
    stops being trustworthy.
    """
    problems = shadow_module.shadow_problems(state)
    if problems:
        raise ContractError("shadow isolation is broken: " + "; ".join(problems))


def describe() -> dict:
    """What shadow observation is and is not allowed to do."""
    return {
        "version": OBSERVER_VERSION,
        "order": [
            "the authoritative path runs first and is recorded",
            "the runtime then sees the question and predicts",
            "the prediction is recorded as evidence only",
        ],
        "may": ["record a prediction", "record a comparison", "record an abstention"],
        "may_not": [
            "influence the authoritative decision",
            "grant authorization",
            "count as verification",
            "change a calibration profile or an adoption slice",
        ],
        "execution_effect": "none",
    }


def shadow_report(state: Mapping[str, Any]) -> dict:
    """A read-only summary of shadow evidence and its isolation."""
    from ..contracts import state_digest  # noqa: F401 - keeps the digest import local to reporting

    return {
        "version": OBSERVER_VERSION,
        "summary": shadow_module.compare(state),
        "isolation_problems": shadow_module.shadow_problems(state),
        "influence_problems": shadow_module.shadow_effect_problems(
            state, state.get("decisions", []) or []
        ),
        "execution_effect": "none",
    }