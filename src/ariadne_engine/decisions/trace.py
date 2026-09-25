"""The decision trace (AR-205D T11).

A task's trail is *derived* from recorded evidence, never written by hand:

.. code-block:: text

    Task
     |  Fact: test_failed = true                    (plan record)
     |  Decision: failure_class = implementation    (decision record)
     |  Policy: routine repair allowed              (policy verdict)
     |  Execution: repair-2                         (execution record)
     |  Verification: PASS                          (verification record)
     |  Review: not required by policy              (policy record)

:func:`build` reads plans, decisions, consensus, generation justifications,
executions and verifications, orders them deterministically and returns the
steps with the record id each step came from. :func:`explain` answers the
operator's questions — what was known, what was decided, with what confidence
kind, why escalation happened, why generation was invoked, what policy selected
and what verification followed — using only structured Ariadne evidence.

Hidden provider reasoning is never exposed; only records the engine wrote.
"""

from __future__ import annotations

from typing import Mapping

from .. import contracts
from . import batch as batch_module
from . import calibration, compiler, consensus as consensus_module, escalation, generation

STEP_ORDER = {
    "FACT": 0,
    "CLASSIFICATION": 1,
    "PROTECTED": 2,
    "QUESTION": 3,
    "DECISION": 4,
    "POLICY": 5,
    "ESCALATION": 6,
    "CACHE": 7,
    "CONSENSUS": 8,
    "GENERATION": 9,
    "EXECUTION": 10,
    "ACTION": 11,
    "VERIFICATION": 12,
}
"""Deterministic step ordering for the trace."""


def _plan_question(plan: Mapping | None, question_id: str) -> dict:
    for item in (plan or {}).get("bounded_questions") or []:
        if str(item.get("question_id", "")) == str(question_id):
            return dict(item)
    return {}


def _executions(state: Mapping, *, task_id: str) -> list[dict]:
    return [
        dict(item) for item in (state.get("executions") or [])
        if isinstance(item, Mapping)
        and (not task_id or str(item.get("task_id", "")) == str(task_id))
    ]


def _verifications(state: Mapping, *, execution_ids: set[str], verification_ids: set[str]) -> list[dict]:
    rows = []
    for item in state.get("verifications") or []:
        if not isinstance(item, Mapping):
            continue
        if str(item.get("verification_id", "")) in verification_ids or str(item.get("execution_id", "")) in execution_ids:
            rows.append(dict(item))
    return rows


def build(state: Mapping, *, task_id: str = "") -> dict:
    """The ordered, record-derived decision trace for one task."""
    plan = compiler.latest(state, task_id=task_id)
    steps: list[dict] = []

    def add(kind: str, label: str, record_id: str, detail: Mapping | None = None) -> None:
        steps.append({
            "kind": str(kind),
            "label": str(label),
            "record": str(record_id),
            "detail": {str(key): value for key, value in dict(detail or {}).items()},
        })

    for fact in (plan or {}).get("deterministic_facts") or []:
        value = fact.get("value")
        label = (
            f"Fact: {fact.get('statement') or fact.get('kind')} = {value!r}"
            if fact.get("known")
            else f"Check: {fact.get('statement') or fact.get('kind')} (deterministic, not yet computed)"
        )
        add("FACT", label, str((plan or {}).get("plan_id", "")), fact)
    for question in (plan or {}).get("bounded_questions") or []:
        add("CLASSIFICATION", f"Classified {question.get('requirement_id')} as BOUNDED", str((plan or {}).get("plan_id", "")), question)
        add("QUESTION", f"Question: {question.get('question_id')}", str(question.get("question_id", "")), question)
    for item in (plan or {}).get("protected_actions") or []:
        add("PROTECTED", f"Protected: {item.get('statement')}", str((plan or {}).get("plan_id", "")), item)

    decisions = [
        item for item in batch_module.decisions(state)
        if not task_id or str(item.get("task_id", "")) == str(task_id)
    ]
    verification_ids: set[str] = set()
    execution_ids = {str(item.get("execution_id", "")) for item in _executions(state, task_id=task_id)}
    for record in decisions:
        question = _plan_question(plan, str(record.get("question_id", "")))
        classification = str(question.get("classification", "BOUNDED"))
        add("DECISION", f"Decision: {record.get('question_id')} = {record.get('answer') or record.get('status')}", str(record.get("decision_id", "")), record)
        verdict = record.get("policy_verdict") if isinstance(record.get("policy_verdict"), Mapping) else {}
        if verdict:
            add("POLICY", f"Policy: {verdict.get('reason') or record.get('status')}", str(record.get("decision_id", "")), verdict)
        if record.get("cached"):
            add("CACHE", f"Cache: reused decision {record.get('source_decision_id')}", str(record.get("cache_id", "")), {
                "cache_id": record.get("cache_id"),
                "source_decision_id": record.get("source_decision_id"),
            })
        if str(record.get("status", "")) != "answered" or not verdict.get("accepted"):
            derived = escalation.escalation_for(
                record,
                classification=classification,
                consequence=str(record.get("consequence", "LOW")),
                generative_available=bool(((plan or {}).get("provider") or {}).get("generative", {}).get("available")),
                stronger_available=False,
            )
            add("ESCALATION", f"Escalation: {derived.get('reason')} -> {derived.get('next')}", str(record.get("decision_id", "")), derived)
        if record.get("acted_on"):
            add("ACTION", f"Execution: {record.get('resulting_action')}", str(record.get("execution_id", "") or record.get("decision_id", "")), {
                "action": record.get("resulting_action"),
                "verification_id": record.get("verification_id", ""),
            })
        if record.get("verification_id"):
            verification_ids.add(str(record["verification_id"]))

    for item in (state.get("decision_consensus") or []):
        if not isinstance(item, Mapping):
            continue
        if task_id and str(item.get("task_id", "")) != str(task_id):
            continue
        if str(item.get("verdict", "")) == "conflict":
            add("CONSENSUS", f"Decision conflict on {item.get('question_id')} ({item.get('policy')})", str(item.get("consensus_id", "")), item)
        else:
            add("CONSENSUS", f"Second opinion: {item.get('verdict')} ({item.get('policy')})", str(item.get("consensus_id", "")), item)
    for item in generation.justifications(state, task_id=task_id):
        add("GENERATION", f"Generation justified: {item.get('reason')}", str(item.get("justification_id", "")), item)
    for item in _executions(state, task_id=task_id):
        state_name = str(item.get("state", ""))
        failure = item.get("failure") if isinstance(item.get("failure"), Mapping) else {}
        label = f"Execution {item.get('execution_id')}: {state_name}"
        if failure:
            label += f" ({failure.get('class')})"
        add("EXECUTION", label, str(item.get("execution_id", "")), item)
    for item in _verifications(state, execution_ids=execution_ids, verification_ids=verification_ids):
        add("VERIFICATION", f"Verification: {item.get('level')} ({item.get('freshness')})", str(item.get("verification_id", "")), item)

    steps.sort(key=lambda step: (STEP_ORDER.get(str(step["kind"]), 99), str(step["record"]), str(step["label"])))
    counts: dict[str, int] = {}
    for step in steps:
        counts[str(step["kind"])] = counts.get(str(step["kind"]), 0) + 1
    return {
        "task_id": str(task_id),
        "plan_id": str((plan or {}).get("plan_id", "")),
        "steps": steps,
        "counts": dict(sorted(counts.items())),
        "derivation": "derived from recorded plans, decisions, executions and verifications; nothing is handwritten",
        "limitations": [
            "the trace covers records the engine wrote; provider-internal reasoning is not exposed",
            "a step's presence is evidence the engine recorded it, not proof a side effect succeeded",
        ],
    }


def explain(state: Mapping, *, task_id: str = "") -> dict:
    """The read-only diagnostic view behind ``ariadne decision-trace``."""
    plan = compiler.latest(state, task_id=task_id)
    decisions = [
        item for item in batch_module.decisions(state)
        if not task_id or str(item.get("task_id", "")) == str(task_id)
    ]
    known_facts = [
        {"fact_id": fact.get("fact_id"), "kind": fact.get("kind"), "value": fact.get("value")}
        for fact in (plan or {}).get("deterministic_facts") or []
        if fact.get("known")
    ]
    checks = [
        {"fact_id": fact.get("fact_id"), "kind": fact.get("kind"), "source": fact.get("source")}
        for fact in (plan or {}).get("deterministic_facts") or []
        if not fact.get("known")
    ]
    escalations = []
    confidence_kinds: dict[str, int] = {}
    for record in decisions:
        kind = str(record.get("confidence_kind", "NONE"))
        confidence_kinds[kind] = confidence_kinds.get(kind, 0) + 1
        question = _plan_question(plan, str(record.get("question_id", "")))
        if str(record.get("status", "")) != "answered" or not (record.get("policy_verdict") or {}).get("accepted"):
            derived = escalation.escalation_for(
                record,
                classification=str(question.get("classification", "BOUNDED")),
                consequence=str(record.get("consequence", "LOW")),
                generative_available=bool(((plan or {}).get("provider") or {}).get("generative", {}).get("available")),
                stronger_available=False,
            )
            escalations.append({
                "decision_id": record.get("decision_id"),
                "question_id": record.get("question_id"),
                "reason": derived.get("reason"),
                "next": derived.get("next"),
                "detail": derived.get("detail"),
                "derived": True,
            })
    trace = build(state, task_id=task_id)
    answers = {
        "facts_known": known_facts,
        "deterministic_checks_outstanding": checks,
        "decisions": [
            {
                "decision_id": record.get("decision_id"),
                "question_id": record.get("question_id"),
                "answer": record.get("answer"),
                "status": record.get("status"),
                "confidence": record.get("confidence"),
                "confidence_kind": record.get("confidence_kind"),
                "provider": record.get("provider"),
                "model_version": record.get("model_version"),
                "cached": bool(record.get("cached")),
            }
            for record in decisions
        ],
        "confidence_kinds": dict(sorted(confidence_kinds.items())),
        "escalations": escalations,
        "generation": [
            {
                "justification_id": item.get("justification_id"),
                "reason": item.get("reason"),
                "requirement_id": item.get("requirement_id"),
                "detail": item.get("detail"),
            }
            for item in generation.justifications(state, task_id=task_id)
        ],
        "policy": {
            "fallback_policy": dict((plan or {}).get("fallback_policy") or {}),
            "plan_policy_version": str((plan or {}).get("policy_version", "")),
        },
        "verification": [
            {
                "verification_id": step["detail"].get("verification_id"),
                "subject": step["detail"].get("subject"),
                "level": step["detail"].get("level"),
                "freshness": step["detail"].get("freshness"),
            }
            for step in trace["steps"] if step["kind"] == "VERIFICATION"
        ],
        "cache": {
            "entries": len([item for item in (state.get("decision_cache") or []) if isinstance(item, Mapping)]),
            "reuses": sum(1 for record in decisions if record.get("cached")),
        },
        "consensus": consensus_module.summarise(state),
        "calibration": calibration.summarise(state),
    }
    lines = [f"{step['kind']}: {step['label']}" for step in trace["steps"]]
    return {
        "task_id": str(task_id),
        "plan_id": trace["plan_id"],
        "answers": answers,
        "trace": trace,
        "lines": lines,
        "note": "structured Ariadne evidence only; no hidden provider reasoning",
    }


__all__ = [
    "STEP_ORDER",
    "build",
    "explain",
]
