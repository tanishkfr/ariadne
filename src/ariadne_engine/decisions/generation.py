"""The generation gate (AR-205D T10).

Before generative intelligence is invoked, Ariadne records why it is justified.
The reason is one of the declared codes — creation required, open-ended
reasoning required, no bounded answer space, a bounded decision that was
insufficient, repair content required, synthesis required — and it is
accounted for structurally.

This is not user-facing bureaucracy. It is the economics and provenance
evidence that answers "why did this task pay for generation?" without
pretending a bounded judgement or a deterministic fact could have done the
work. A generative need that the compiler produced and no justification
recorded is reported as an unjustified gate.
"""

from __future__ import annotations

from typing import Mapping, Sequence

from .. import contracts
from ..contracts import (
    DECISION_INTELLIGENCE_CONTRACT,
    GENERATION_REASONS,
    SCHEMA_DECISION_INTELLIGENCE,
    ContractError,
)
from . import compiler

GATE_POLICY_VERSION = "ar-205d-generation-gate-1"
"""The generation-gate policy version recorded on every justification."""


def justify(
    state: dict,
    *,
    reason: str,
    task_id: str = "",
    stage: str = "",
    detail: str = "",
    requirement_id: str = "",
    decision_id: str = "",
    plan_id: str = "",
) -> dict:
    """Record one generation justification. The reason must be declared."""
    if str(reason) not in GENERATION_REASONS:
        raise ContractError(
            f"generation must be justified with a declared reason: {reason!r}; declared: "
            + ", ".join(GENERATION_REASONS)
        )
    record = {
        "schema_version": SCHEMA_DECISION_INTELLIGENCE,
        "justification_id": contracts.new_record_id("gen"),
        "run_id": str(state.get("run_id", "")),
        "task_id": str(task_id),
        "stage": str(stage),
        "reason": str(reason),
        "detail": str(detail),
        "requirement_id": str(requirement_id),
        "decision_id": str(decision_id),
        "plan_id": str(plan_id),
        "policy_version": GATE_POLICY_VERSION,
        "contract_version": DECISION_INTELLIGENCE_CONTRACT,
        "authorization_effect": "none",
        "recorded_at": contracts.utc_now(),
    }
    problems = contracts.generation_justification_problems(record)
    if problems:
        raise ContractError("the generation justification is malformed: " + "; ".join(problems))
    contracts.require_collection_capacity(state, "generation_justifications")
    state.setdefault("generation_justifications", []).append(record)
    return record


def justifications(state: Mapping, *, task_id: str = "") -> list[dict]:
    return [
        dict(item) for item in (state.get("generation_justifications") or [])
        if isinstance(item, Mapping)
        and (not task_id or str(item.get("task_id", "")) == str(task_id))
    ]


def gate(state: Mapping, *, task_id: str = "") -> dict:
    """Whether every generative need for this task carries a justification."""
    plan = compiler.latest(state, task_id=task_id)
    needs = list((plan or {}).get("generative_needs") or [])
    recorded = justifications(state, task_id=task_id)
    justified: list[dict] = []
    unjustified: list[dict] = []
    used: set[int] = set()
    for need in needs:
        requirement_id = str(need.get("requirement_id", ""))
        match = None
        for index, item in enumerate(recorded):
            if index in used:
                continue
            if str(item.get("requirement_id", "")) == requirement_id and str(item.get("reason", "")) == str(need.get("reason", "")):
                match = item
                used.add(index)
                break
        if match is None:
            unjustified.append({
                "requirement_id": requirement_id,
                "kind": str(need.get("kind", "")),
                "reason": str(need.get("reason", "")),
            })
        else:
            justified.append({"requirement_id": requirement_id, "justification_id": str(match.get("justification_id", ""))})
    return {
        "open": bool(unjustified),
        "generative_needs": len(needs),
        "justified": justified,
        "unjustified": unjustified,
        "plan_id": str((plan or {}).get("plan_id", "")),
        "recorded_justifications": len(recorded),
        "policy_version": GATE_POLICY_VERSION,
    }


def gate_problems(state: Mapping, *, task_id: str = "") -> list[str]:
    """Deterministic problems for an unjustified generation path."""
    view = gate(state, task_id=task_id)
    return [
        f"generation for requirement {item['requirement_id']!r} ({item['reason']}) has no recorded "
        "justification; generative execution must be able to say why it was needed"
        for item in view["unjustified"]
    ]


def summarise(state: Mapping) -> dict:
    rows = [item for item in (state.get("generation_justifications") or []) if isinstance(item, Mapping)]
    reasons: dict[str, int] = {}
    for item in rows:
        key = str(item.get("reason", ""))
        reasons[key] = reasons.get(key, 0) + 1
    return {
        "justifications": len(rows),
        "reasons": dict(sorted(reasons.items())),
        "note": "a recorded reason is provenance; it does not grant authorization",
    }


__all__ = [
    "GATE_POLICY_VERSION",
    "justify",
    "justifications",
    "gate",
    "gate_problems",
    "summarise",
]
