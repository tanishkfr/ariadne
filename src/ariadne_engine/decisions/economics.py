"""Structural economics of the decision plane (AR-205D T15/T16).

Everything here is measured from records the engine wrote — calls, questions,
state bytes, cache reuse, escalations, second opinions and the decision-plane
overhead itself. No dollar figure is fabricated: without live provider usage
there is nothing to convert into money, and this module says so instead.

:func:`compiled_plan_comparison` compares an execution plan with and without
decision compilation structurally: model-call count, decision-call count, state
bytes, generative stages, verification stages and worker count. It measures
structure only; it never claims quality parity, because that would require
model-backed evidence this milestone deliberately does not purchase.
"""

from __future__ import annotations

import json
from typing import Mapping

from . import batch as batch_module
from . import cache as cache_module
from . import calibration, compiler, consensus as consensus_module, generation, graph as graph_module

ECONOMICS_VERSION = "ar-205d-economics-1"


def _plans(state: Mapping, *, task_id: str = "") -> list[dict]:
    return [
        dict(item) for item in (state.get("decision_plans") or [])
        if isinstance(item, Mapping)
        and (not task_id or str(item.get("task_id", "")) == str(task_id))
    ]


def _records(state: Mapping, key: str, *, task_id: str = "") -> list[dict]:
    return [
        dict(item) for item in (state.get(key) or [])
        if isinstance(item, Mapping)
        and (not task_id or str(item.get("task_id", "")) == str(task_id))
    ]


def intelligence_economics(state: Mapping, *, task_id: str = "") -> dict:
    """Measured decision-plane counts and bytes for one task (or the run)."""
    plans = _plans(state, task_id=task_id)
    batches = [
        item for item in _records(state, "decision_batches", task_id=task_id)
        if not item.get("served_from_cache")
    ]
    cached_batches = [
        item for item in _records(state, "decision_batches", task_id=task_id)
        if item.get("served_from_cache")
    ]
    decisions = [
        item for item in batch_module.decisions(state)
        if not task_id or str(item.get("task_id", "")) == str(task_id)
    ]
    escalations = 0
    for record in decisions:
        if str(record.get("status", "")) != "answered" or not (record.get("policy_verdict") or {}).get("accepted"):
            escalations += 1
    plan_economics = {
        "model_calls_avoided_by_deterministic": sum(
            int((plan.get("economics") or {}).get("model_calls_avoided_by_deterministic", 0) or 0)
            for plan in plans
        ),
        "model_calls_avoided_by_bounded_decision": sum(
            int((plan.get("economics") or {}).get("model_calls_avoided_by_bounded_decision", 0) or 0)
            for plan in plans
        ),
        "generative_calls_required": sum(
            int((plan.get("economics") or {}).get("generative_calls_required", 0) or 0)
            for plan in plans
        ),
    }
    state_bytes = sum(int(item.get("projection_chars", 0) or 0) for item in batches)
    overhead = _overhead_bytes(state, task_id=task_id)
    return {
        "version": ECONOMICS_VERSION,
        "task_id": str(task_id),
        "plans": len(plans),
        "fast_path_plans": sum(1 for plan in plans if (plan.get("fast_path") or {}).get("applies")),
        "questions": sum(len(plan.get("bounded_questions") or []) for plan in plans),
        "provider_calls": len(batches),
        "questions_per_batch": [
            len(item.get("questions") or []) for item in batches
        ],
        "cache_served": len(cached_batches),
        "cache_reuses": sum(1 for record in decisions if record.get("cached")),
        "generative_needs": sum(len(plan.get("generative_needs") or []) for plan in plans),
        "generation_justifications": len(_records(state, "generation_justifications", task_id=task_id)),
        "escalations": escalations,
        "second_opinions": len(_records(state, "decision_consensus", task_id=task_id)),
        "state_bytes": state_bytes,
        "decision_plane_overhead_bytes": overhead,
        "counts": {
            **plan_economics,
            "bounded_decision_calls": len(batches),
            "generative_calls": "UNKNOWN - no generative provider usage was recorded",
        },
        "note": (
            "structural counts only; avoided model calls are counted from compiled plans, and no "
            "monetary saving is claimed without measured comparable usage"
        ),
    }


def _overhead_bytes(state: Mapping, *, task_id: str = "") -> int:
    keys = (
        "decision_plans", "decision_graphs", "decision_cache", "decision_consensus",
        "generation_justifications", "decision_outcomes", "decisions", "decision_batches",
    )
    total = 0
    for key in keys:
        for item in state.get(key) or []:
            if not isinstance(item, Mapping):
                continue
            if task_id and str(item.get("task_id", "")) and str(item.get("task_id", "")) != str(task_id):
                continue
            total += len(json.dumps(item, sort_keys=True, default=str).encode("utf-8"))
    return total


def compiled_plan_view(state: Mapping, *, task_id: str = "") -> dict:
    """The compiled plan's structural shape, derived from records."""
    plans = _plans(state, task_id=task_id)
    batches = [
        item for item in _records(state, "decision_batches", task_id=task_id)
        if not item.get("served_from_cache")
    ]
    graphs = _records(state, "decision_graphs", task_id=task_id)
    return {
        "model_calls": len(batches),
        "decision_calls": sum(len(item.get("questions") or []) for item in batches),
        "state_bytes": sum(int(item.get("projection_chars", 0) or 0) for item in batches),
        "generative_stages": sum(len(plan.get("generative_needs") or []) for plan in plans),
        "verification_stages": sum(
            len(plan.get("verification_requirements") or []) for plan in plans
        ) + sum(
            1 for item in graphs
            for node in item.get("nodes") or []
            if str(node.get("kind", "")) == "VERIFICATION"
        ),
        "worker_count": sum(
            len(plan.get("generative_needs") or []) for plan in plans
        ) or (1 if plans else 0),
        "human_gates": sum(
            1 for item in graphs
            for node in item.get("nodes") or []
            if str(node.get("kind", "")) == "HUMAN_GATE"
        ),
    }


def compiled_plan_comparison(
    state: Mapping,
    *,
    baseline: Mapping,
    task_id: str = "",
) -> dict:
    """Compare an old execution plan with the decision-compiled plan structurally."""
    compiled = compiled_plan_view(state, task_id=task_id)
    keys = ("model_calls", "decision_calls", "state_bytes", "generative_stages", "verification_stages", "worker_count")
    deltas = {}
    for key in keys:
        base = baseline.get(key)
        value = compiled.get(key)
        if isinstance(base, (int, float)) and isinstance(value, (int, float)):
            deltas[key] = int(value) - int(base)
        else:
            deltas[key] = "UNKNOWN"
    return {
        "baseline": {key: baseline.get(key, "UNKNOWN") for key in keys},
        "compiled": {key: compiled.get(key) for key in keys},
        "deltas": deltas,
        "claim_boundary": (
            "structural comparison only: no live model was invoked and no quality parity is claimed; "
            "state bytes are the projections actually sent"
        ),
    }


def summarise(state: Mapping) -> dict:
    """Run-level decision-intelligence economics and the sub-system counters."""
    return {
        "intelligence": intelligence_economics(state),
        "compiler": compiler.summarise(state),
        "graph": graph_module.summarise(state),
        "cache": cache_module.summarise(state),
        "consensus": consensus_module.summarise(state),
        "generation": generation.summarise(state),
        "calibration": calibration.summarise(state),
        "note": "every counter is derived from records; nothing is estimated",
    }


__all__ = [
    "ECONOMICS_VERSION",
    "intelligence_economics",
    "compiled_plan_view",
    "compiled_plan_comparison",
    "summarise",
]
