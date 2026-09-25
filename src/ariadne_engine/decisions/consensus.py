"""Independent second decisions (AR-205D T7).

For selected higher-stakes bounded judgements, policy may request one
independent second decision. It is never universal. The declared policies are:

``single``
    one decision, no second.
``second_on_low_confidence``
    a second opinion when the first decision was refused or carried weak
    confidence provenance.
``second_on_high_stakes``
    a second opinion whenever the consequence class is HIGH (PROTECTED never
    reaches a bounded decision at all).
``second_on_disagreement``
    a second opinion when the first answer is internally undecided — a flat
    distribution or no dominant answer — before it is acted on.

When two independent decisions disagree, labels are never averaged. The
structured result is ``DECISION_CONFLICT``, which escalates under the ladder.

Two agreeing models do not establish truth. Every consensus record states
``establishes_truth: false`` and keeps both providers, models, projections,
answers and confidence provenances side by side. Consensus is evidence of
agreement — never of correctness, and never of authorization.
"""

from __future__ import annotations

from typing import Mapping

from .. import contracts
from ..contracts import (
    CONFIDENCE_KINDS,
    CONSENSUS_POLICIES,
    DECISION_INTELLIGENCE_CONTRACT,
    SCHEMA_DECISION_INTELLIGENCE,
    ContractError,
)
from . import batch as batch_module
from . import policy, projections as projection_module
from .contracts import DecisionQuestion
from .providers import DecisionProvider

CONSENSUS_POLICY_VERSION = "ar-205d-consensus-1"
"""The second-opinion rule-table version recorded on every comparison."""


def should_second(
    *,
    policy_name: str,
    record: Mapping,
    stakes: str = "LOW",
) -> dict:
    """Whether policy asks for an independent second decision."""
    if str(policy_name) not in CONSENSUS_POLICIES:
        raise ContractError(
            f"unsupported consensus policy {policy_name!r}; declared: " + ", ".join(CONSENSUS_POLICIES)
        )
    if policy_name == "single":
        return {"required": False, "reason": "the policy asks for one decision only", "policy": policy_name}
    if policy_name == "second_on_high_stakes":
        if str(stakes) in ("HIGH", "PROTECTED"):
            return {"required": True, "reason": "high stakes: an independent second decision is requested", "policy": policy_name}
        return {"required": False, "reason": f"stakes {stakes} do not meet the second-opinion threshold", "policy": policy_name}
    if policy_name == "second_on_low_confidence":
        kind = str(record.get("confidence_kind", "NONE"))
        accepted = bool((record.get("policy_verdict") or {}).get("accepted", False))
        if kind not in ("CALIBRATED_PROBABILITY", "PROVIDER_PROBABILITY", "DERIVED_CONFIDENCE") or not accepted:
            return {
                "required": True,
                "reason": f"the first decision's confidence provenance is {kind} and acceptance is {accepted}",
                "policy": policy_name,
            }
        return {"required": False, "reason": "the first decision carries strong confidence provenance", "policy": policy_name}
    distribution = record.get("distribution") if isinstance(record.get("distribution"), Mapping) else {}
    values = [float(value) for value in distribution.values() if isinstance(value, (int, float))]
    dominant = max(values) if values else None
    if str(record.get("status", "")) != "answered" or (dominant is not None and dominant < 0.5):
        return {
            "required": True,
            "reason": "the first decision is internally undecided; a second decision is requested",
            "policy": policy_name,
        }
    return {"required": False, "reason": "the first decision has a dominant answer", "policy": policy_name}


def _different_provider(first: Mapping, second: DecisionProvider) -> list[str]:
    problems: list[str] = []
    if (
        str(first.get("provider", "")) == str(getattr(second, "provider", "") or "")
        and str(first.get("model_version", "")) == str(getattr(second, "model_version", "") or "")
    ):
        problems.append(
            "a second decision must be independent: it cannot come from the same provider and model "
            "version as the first"
        )
    return problems


def run_second(
    state: dict,
    *,
    question: DecisionQuestion,
    projection: Mapping,
    provider: DecisionProvider,
    first_decision_id: str,
    policy_name: str,
    stakes: str = "LOW",
    task_id: str = "",
    stage: str = "",
    consequence: str = "LOW",
    verification_level: str = "",
    require_evidence: bool = True,
) -> dict:
    """Request one independent second decision and record the comparison.

    A second opinion that could not be obtained is recorded as
    ``second_unavailable``; it never silently inherits the first answer.
    """
    if not isinstance(provider, DecisionProvider):
        raise ContractError("a second decision needs a DecisionProvider")
    first = None
    for item in state.get("decisions") or []:
        if isinstance(item, Mapping) and str(item.get("decision_id", "")) == str(first_decision_id):
            first = dict(item)
            break
    if first is None:
        raise ContractError(f"no decision record matches {first_decision_id!r}")
    trigger = should_second(policy_name=policy_name, record=first, stakes=stakes)
    if not trigger["required"]:
        comparison = _comparison(
            question=question,
            first=first,
            second=None,
            verdict="not_required",
            policy_name=policy_name,
            reason=trigger["reason"],
        )
        _record(state, comparison, task_id=task_id, stage=stage)
        return comparison
    independence = _different_provider(first, provider)
    if independence:
        raise ContractError("; ".join(independence))
    available, unavailable_reason = provider.available()
    if not available:
        comparison = _comparison(
            question=question,
            first=first,
            second=None,
            verdict="second_unavailable",
            policy_name=policy_name,
            reason=str(unavailable_reason or "no second provider is configured"),
        )
        _record(state, comparison, task_id=task_id, stage=stage)
        return comparison
    batch = batch_module.evaluate(
        state,
        questions=[question],
        projection={**dict(projection), "verification_level": verification_level},
        provider=provider,
        task_id=task_id,
        stage=stage,
        require_evidence=require_evidence,
    )
    result = (batch.get("results") or [{}])[0]
    second = batch_module.decision(state, str(result.get("decision_id", ""))) or {}
    comparison = _comparison(
        question=question,
        first=first,
        second=second,
        verdict="",
        policy_name=policy_name,
        reason="",
        consequence=consequence,
    )
    _record(state, comparison, task_id=task_id, stage=stage)
    return comparison


def _comparison(
    *,
    question: DecisionQuestion,
    first: Mapping,
    second: Mapping | None,
    verdict: str,
    policy_name: str,
    reason: str,
    consequence: str = "LOW",
) -> dict:
    if not verdict:
        first_answers = [str(item) for item in (first.get("answers") or [])]
        second_answers = [str(item) for item in ((second or {}).get("answers") or [])]
        first_valid = str(first.get("status", "")) == "answered" and first.get("answer_valid") is True
        second_valid = str((second or {}).get("status", "")) == "answered" and (second or {}).get("answer_valid") is True
        if not second_valid:
            verdict = "second_unavailable"
            reason = "the second decision produced no valid answer"
        elif not first_valid:
            verdict = "conflict"
            reason = "the first decision has no valid answer to compare against"
        elif sorted(first_answers) == sorted(second_answers):
            verdict = "agree"
            reason = (
                "two independent decisions produced the same answer; this is evidence of agreement, "
                "not proof of correctness"
            )
        else:
            verdict = "conflict"
            reason = "two independent decisions disagree; labels are not averaged and policy escalates"
    return {
        "schema_version": SCHEMA_DECISION_INTELLIGENCE,
        "question_id": str(question.question_id),
        "question_definition_version": str(question.definition_version),
        "primitive": str(question.primitive),
        "policy": str(policy_name),
        "policy_version": CONSENSUS_POLICY_VERSION,
        "verdict": str(verdict),
        "reason": str(reason),
        "consequence": str(consequence),
        "first": {
            "decision_id": str(first.get("decision_id", "")),
            "answer": str(first.get("answer", "")),
            "answers": [str(item) for item in (first.get("answers") or [])],
            "status": str(first.get("status", "")),
            "provider": str(first.get("provider", "")),
            "model": str(first.get("model", "")),
            "model_version": str(first.get("model_version", "")),
            "confidence": first.get("confidence"),
            "confidence_kind": str(first.get("confidence_kind", "NONE")),
            "state_digest": str(first.get("state_digest", "")),
        },
        "second": {
            "decision_id": str((second or {}).get("decision_id", "")),
            "answer": str((second or {}).get("answer", "")),
            "answers": [str(item) for item in ((second or {}).get("answers") or [])],
            "status": str((second or {}).get("status", "")),
            "provider": str((second or {}).get("provider", "")),
            "model": str((second or {}).get("model", "")),
            "model_version": str((second or {}).get("model_version", "")),
            "confidence": (second or {}).get("confidence"),
            "confidence_kind": str((second or {}).get("confidence_kind", "NONE")),
            "state_digest": str((second or {}).get("state_digest", "")),
        },
        "establishes_truth": False,
        "authorization_effect": "none",
        "contract_version": DECISION_INTELLIGENCE_CONTRACT,
        "recorded_at": contracts.utc_now(),
    }


def _record(state: dict, comparison: dict, *, task_id: str, stage: str) -> dict:
    comparison["consensus_id"] = contracts.new_record_id("dcn")
    comparison["run_id"] = str(state.get("run_id", ""))
    comparison["task_id"] = str(task_id)
    comparison["stage"] = str(stage)
    problems = contracts.decision_consensus_problems(comparison)
    if problems:
        raise ContractError("the consensus record is malformed: " + "; ".join(problems))
    contracts.require_collection_capacity(state, "decision_consensus")
    state.setdefault("decision_consensus", []).append(comparison)
    return comparison


def consensus(state: Mapping, consensus_id: str) -> dict | None:
    for item in state.get("decision_consensus") or []:
        if isinstance(item, Mapping) and str(item.get("consensus_id", "")) == str(consensus_id):
            return dict(item)
    return None


def conflicts(state: Mapping, *, task_id: str = "") -> list[dict]:
    return [
        dict(item) for item in (state.get("decision_consensus") or [])
        if isinstance(item, Mapping)
        and str(item.get("verdict", "")) == "conflict"
        and (not task_id or str(item.get("task_id", "")) == str(task_id))
    ]


def summarise(state: Mapping) -> dict:
    rows = [item for item in (state.get("decision_consensus") or []) if isinstance(item, Mapping)]
    verdicts: dict[str, int] = {}
    for item in rows:
        key = str(item.get("verdict", ""))
        verdicts[key] = verdicts.get(key, 0) + 1
    return {
        "second_opinions": len(rows),
        "verdicts": dict(sorted(verdicts.items())),
        "conflicts": verdicts.get("conflict", 0),
        "note": "agreement is evidence of agreement, not correctness; no label was ever averaged",
    }


__all__ = [
    "CONSENSUS_POLICY_VERSION",
    "should_second",
    "run_second",
    "consensus",
    "conflicts",
    "summarise",
]
