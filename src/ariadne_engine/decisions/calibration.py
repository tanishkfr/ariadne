"""Calibration outcome collection (AR-205D T12).

Ariadne does not self-tune in v2, and nothing here trains anything. What this
module does is *prepare* the raw material a later, deliberate calibration step
would need: for each bounded decision, the answer, the confidence and its
kind, the provider and concrete model version, and whatever downstream outcome
evidence the engine later observed.

Two rules keep the data honest:

* a downstream failure is **never** automatically labelled a wrong decision.
  Only recorded evidence can move a decision to ``CONTRADICTED`` or
  ``OVERRIDDEN``, and those categories require evidence;
* sensitive task content is not duplicated here. Records carry ids, digests
  and outcome categories; the raw state stays in the existing evidence systems
  where it was authorized.
"""

from __future__ import annotations

from typing import Mapping, Sequence

from .. import contracts
from ..contracts import (
    CALIBRATION_OUTCOME_CATEGORIES,
    DECISION_INTELLIGENCE_CONTRACT,
    SCHEMA_DECISION_INTELLIGENCE,
    ContractError,
)
from . import batch as batch_module

CALIBRATION_POLICY_VERSION = "ar-205d-calibration-1"
"""The calibration-collection policy version recorded on every outcome."""

OUTCOME_SOURCES = ("engine-observation", "human", "verification", "review")
"""Where an outcome observation may come from. Worker prose is not a source."""


def _decision(state: Mapping, decision_id: str) -> dict | None:
    for item in state.get("decisions") or []:
        if isinstance(item, Mapping) and str(item.get("decision_id", "")) == str(decision_id):
            return dict(item)
    return None


def record_outcome(
    state: dict,
    *,
    decision_id: str,
    category: str,
    evidence: Sequence[str] = (),
    downstream: Mapping | None = None,
    source: str = "engine-observation",
    note: str = "",
) -> dict:
    """Record one eventual outcome for one bounded decision.

    ``SUPPORTED`` and ``UNRESOLVED`` may be recorded from an observation alone.
    ``CONTRADICTED`` and ``OVERRIDDEN`` require evidence ids or digests — a
    hunch, a failed downstream run, or a worker's opinion is not evidence that
    the decision was wrong.
    """
    record = _decision(state, decision_id)
    if record is None:
        raise ContractError(f"no decision record matches {decision_id!r}")
    if str(category) not in CALIBRATION_OUTCOME_CATEGORIES:
        raise ContractError(
            f"unsupported outcome category {category!r}; declared: "
            + ", ".join(CALIBRATION_OUTCOME_CATEGORIES)
        )
    if str(source) not in OUTCOME_SOURCES:
        raise ContractError(
            f"an outcome observation must come from a declared source: {source!r}; declared: "
            + ", ".join(OUTCOME_SOURCES)
        )
    evidence_rows = [str(item) for item in evidence or () if str(item).strip()]
    if category in ("CONTRADICTED", "OVERRIDDEN") and not evidence_rows:
        raise ContractError(
            "a decision is only contradicted or overridden by recorded evidence, never by a "
            "downstream failure alone"
        )
    outcome = {
        "schema_version": SCHEMA_DECISION_INTELLIGENCE,
        "outcome_id": contracts.new_record_id("dco"),
        "run_id": str(state.get("run_id", "")),
        "task_id": str(record.get("task_id", "")),
        "decision_id": str(decision_id),
        "question_id": str(record.get("question_id", "")),
        "answer": str(record.get("answer", "")),
        "confidence": record.get("confidence"),
        "confidence_kind": str(record.get("confidence_kind", "NONE")),
        "provider": str(record.get("provider", "")),
        "model": str(record.get("model", "")),
        "model_version": str(record.get("model_version", "")),
        "category": str(category),
        "downstream": {
            "verified_result": str((downstream or {}).get("verified_result", "")),
            "later_contradiction": str((downstream or {}).get("later_contradiction", "")),
            "human_override": str((downstream or {}).get("human_override", "")),
        },
        "evidence": evidence_rows,
        "source": str(source),
        "note": str(note),
        "policy_version": CALIBRATION_POLICY_VERSION,
        "contract_version": DECISION_INTELLIGENCE_CONTRACT,
        "authorization_effect": "none",
        "recorded_at": contracts.utc_now(),
    }
    problems = contracts.decision_outcome_problems(outcome)
    if problems:
        raise ContractError("the decision outcome is malformed: " + "; ".join(problems))
    contracts.require_collection_capacity(state, "decision_outcomes")
    state.setdefault("decision_outcomes", []).append(outcome)
    return outcome


def outcomes(state: Mapping, *, decision_id: str = "", task_id: str = "") -> list[dict]:
    return [
        dict(item) for item in (state.get("decision_outcomes") or [])
        if isinstance(item, Mapping)
        and (not decision_id or str(item.get("decision_id", "")) == str(decision_id))
        and (not task_id or str(item.get("task_id", "")) == str(task_id))
    ]


def calibration_data(state: Mapping, *, task_id: str = "") -> list[dict]:
    """One row per decision with whatever outcome evidence exists.

    A decision with no recorded outcome is ``UNRESOLVED`` — absence of evidence
    is not evidence that the decision was right.
    """
    rows: list[dict] = []
    for record in batch_module.decisions(state):
        if task_id and str(record.get("task_id", "")) != str(task_id):
            continue
        observed = outcomes(state, decision_id=str(record.get("decision_id", "")))
        categories = [str(item.get("category", "")) for item in observed]
        rows.append({
            "decision_id": str(record.get("decision_id", "")),
            "task_id": str(record.get("task_id", "")),
            "question_id": str(record.get("question_id", "")),
            "answer": str(record.get("answer", "")),
            "confidence": record.get("confidence"),
            "confidence_kind": str(record.get("confidence_kind", "NONE")),
            "provider": str(record.get("provider", "")),
            "model_version": str(record.get("model_version", "")),
            "status": str(record.get("status", "")),
            "outcomes": observed,
            "outcome_category": categories[-1] if categories else "UNRESOLVED",
            "evidence": [item for outcome in observed for item in (outcome.get("evidence") or [])],
        })
    return rows


def summarise(state: Mapping) -> dict:
    rows = [item for item in (state.get("decision_outcomes") or []) if isinstance(item, Mapping)]
    categories: dict[str, int] = {}
    for item in rows:
        key = str(item.get("category", ""))
        categories[key] = categories.get(key, 0) + 1
    return {
        "outcomes": len(rows),
        "categories": dict(sorted(categories.items())),
        "note": (
            "raw outcomes are collected for future calibration; nothing is tuned automatically "
            "and no downstream failure is auto-labelled a wrong decision"
        ),
    }


__all__ = [
    "CALIBRATION_POLICY_VERSION",
    "OUTCOME_SOURCES",
    "record_outcome",
    "outcomes",
    "calibration_data",
    "summarise",
]
