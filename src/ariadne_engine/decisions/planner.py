"""Automatic decision batching over one projected state (AR-205D T3).

AR-203 introduced batches. AR-205D makes batching automatic where it is
justified: independent bounded questions that the compiler produced over the
same state are grouped into the same provider call; a question whose answer
depends on another question's answer is *staged* into a later step, never
smuggled into one batch to save a call.

The independence proof is explicit: for every step, no question may depend on
another question in that step. AR-204's dependency protections
(:func:`ariadne_engine.economics.batch_dependency_problems`) are the same check
applied here, so the property cannot drift between the two modules.

Dependent questions wait. Each step receives the projections the compiler
declared for it; questions that share a projection contract and state digest
share one bounded request. Results are mapped back by question id, and a
missing or mis-mapped answer is a recorded failure rather than a plausible
default.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from .. import contracts, economics
from ..contracts import ContractError
from . import batch as batch_module
from . import cache as cache_module
from . import policy, projections as projection_module
from .contracts import DecisionQuestion
from .providers import DecisionProvider

STEP_STATUSES = ("answered", "partial", "failed", "unavailable", "refused")


def _as_question(value: Any) -> DecisionQuestion:
    if isinstance(value, DecisionQuestion):
        return value
    if isinstance(value, Mapping):
        return DecisionQuestion(**{key: value[key] for key in value if key in DecisionQuestion.__dataclass_fields__})
    raise ContractError("a batched question must be a DecisionQuestion or its record form")


def plan_steps(
    questions: Sequence[Mapping | DecisionQuestion],
    *,
    depends_on: Mapping[str, Sequence[str]] | None = None,
) -> dict:
    """Group independent questions into steps; prove each step's independence.

    Dependent questions are staged into later steps, never refused: the
    dependency protection applies to each *step*, which is what one provider
    call would otherwise hide. A cycle is still refused, because staging cannot
    resolve one.
    """
    records = [_as_question(question) for question in questions or ()]
    if not records:
        raise ContractError("a batch plan needs at least one question")
    payload = [question.as_record() for question in records]
    dependencies = {str(key): [str(item) for item in (value or [])] for key, value in dict(depends_on or {}).items()}
    plan = economics.plan_batches(payload, depends_on=dependencies)
    by_id = {str(question.question_id): question for question in records}
    unknown = sorted(
        question_id
        for step in plan["steps"]
        for question_id in step
        if question_id not in by_id
    )
    if unknown:
        raise ContractError("the step plan names unknown questions: " + ", ".join(unknown))
    for index, step in enumerate(plan["steps"], start=1):
        step_ids = {str(question_id) for question_id in step}
        problems = economics.batch_dependency_problems(
            [question for question in payload if str(question.get("question_id")) in step_ids],
            depends_on={
                key: [item for item in value if str(item) in step_ids]
                for key, value in dependencies.items()
                if str(key) in step_ids
            },
        )
        if problems:
            raise ContractError(f"decision step {index} is not independent: " + "; ".join(problems))
    plan["records"] = [
        [by_id[question_id].as_record() for question_id in step]
        for step in plan["steps"]
    ]
    plan["depends_on"] = dependencies
    return plan


def group_step(
    step_questions: Sequence[Mapping],
    projections: Mapping[str, Mapping],
) -> list[dict]:
    """One group per shared projection contract inside a step.

    Questions with no projection contract cannot be evaluated safely and are
    refused rather than grouped.
    """
    groups: dict[str, dict] = {}
    for question in step_questions:
        contract_id = str(question.get("projection_contract", "") or "")
        if not contract_id:
            raise ContractError(
                f"question {question.get('question_id')!r} declares no projection contract; "
                "bounded judgement needs the smallest defensible state, declared"
            )
        projection = projections.get(contract_id)
        if not isinstance(projection, Mapping) or not str(projection.get("digest", "")):
            raise ContractError(
                f"question {question.get('question_id')!r} has no projected state for contract "
                f"{contract_id!r}"
            )
        group = groups.setdefault(contract_id, {
            "contract_id": contract_id,
            "digest": str(projection.get("digest", "")),
            "projection": projection,
            "questions": [],
        })
        if group["digest"] != str(projection.get("digest", "")):
            raise ContractError(
                f"two different projections claim contract {contract_id!r}; one state digest per step"
            )
        group["questions"].append(dict(question))
    return [groups[key] for key in sorted(groups)]


def evaluate_step(
    state: dict,
    *,
    questions: Sequence[Mapping | DecisionQuestion],
    depends_on: Mapping[str, Sequence[str]] | None = None,
    projections: Mapping[str, Mapping],
    provider: DecisionProvider,
    task_id: str = "",
    stage: str = "",
    execution_id: str = "",
    verification_level: str = "",
    require_evidence: bool = True,
    cache_enabled: bool = False,
    cache_ttl_seconds: int | None = None,
    fingerprints: Mapping[str, Mapping] | None = None,
) -> dict:
    """Plan, batch and evaluate a set of independent questions.

    Cache reuse is attempted per question only when it is enabled and the
    provider identity is concrete; a reuse is recorded as a new decision that
    cites the cached one, and everything else goes to the provider in one call
    per projection group.
    """
    if not isinstance(provider, DecisionProvider):
        raise ContractError("a batched evaluation needs a DecisionProvider")
    plan = plan_steps(questions, depends_on=depends_on)
    by_id = {
        str(question.get("question_id")): dict(question)
        for step in plan["records"]
        for question in step
    }
    results: list[dict] = []
    batches: list[dict] = []
    for step_index, step in enumerate(plan["records"], start=1):
        for group in group_step(step, projections):
            payloads = group["questions"]
            pending: list[DecisionQuestion] = []
            pending_records: list[Mapping] = []
            for question_record in payloads:
                question = _as_question(question_record)
                served = None
                if cache_enabled and str(getattr(provider, "model_version", "") or "").strip():
                    lookup = cache_module.lookup(
                        state,
                        question=question,
                        projection_digest=str(group["digest"]),
                        provider=str(getattr(provider, "provider", "") or ""),
                        model_version=str(getattr(provider, "model_version", "") or ""),
                        policy_version=policy.POLICY_VERSION,
                        current_fingerprints=(fingerprints or {}).get(str(question.question_id)),
                    )
                    if lookup["hit"]:
                        served = cache_module.materialise(
                            state,
                            lookup["entry"],
                            question=question,
                            projection=group["projection"],
                            consequence=str(question_record.get("consequence") or "LOW"),
                            verification_level=verification_level,
                            require_evidence=require_evidence,
                            task_id=task_id,
                            stage=stage,
                        )
                if served is not None:
                    results.append(_result_row(served, question_record, question))
                else:
                    pending.append(question)
                    pending_records.append(question_record)
            if not pending:
                continue
            batch = _evaluate_provider_batch(
                state,
                questions=pending,
                projection=group["projection"],
                provider=provider,
                task_id=task_id,
                stage=stage,
                execution_id=execution_id,
                verification_level=verification_level,
                require_evidence=require_evidence,
            )
            batches.append(batch)
            for result in batch["results"]:
                row = dict(result)
                record = _decision(state, str(result.get("decision_id", "")))
                requirement_id = ""
                question_record = next(
                    (
                        item for item in pending_records
                        if str(item.get("question_id")) == str(result.get("question_id"))
                    ),
                    {},
                )
                requirement_id = str(question_record.get("requirement_id", ""))
                row["requirement_id"] = requirement_id
                row["cached"] = False
                results.append(row)
                if cache_enabled and record is not None and str(record.get("status", "")) == "answered":
                    cache_module.store(
                        state, record,
                        question=next(
                            item for item in pending if str(item.question_id) == str(record.get("question_id"))
                        ),
                        projection_digest=str(group["digest"]),
                        fingerprints=(fingerprints or {}).get(str(record.get("question_id"))),
                        ttl_seconds=cache_ttl_seconds,
                    )
    return {
        "plan": plan,
        "batches": batches,
        "results": results,
        "steps": len(plan["steps"]),
        "mapped": len(results),
        "missing": sorted(
            question_id for question_id in by_id
            if question_id not in {str(row.get("question_id", "")) for row in results}
        ),
        "status": _rollup(results),
    }


def _result_row(record: Mapping, question_record: Mapping, question: DecisionQuestion) -> dict:
    return {
        "decision_id": str(record.get("decision_id", "")),
        "question_id": str(question.question_id),
        "requirement_id": str(question_record.get("requirement_id", "")),
        "status": str(record.get("status", "")),
        "answer": str(record.get("answer", "")),
        "answer_valid": bool(record.get("answer_valid", False)),
        "confidence": record.get("confidence"),
        "confidence_kind": str(record.get("confidence_kind", "NONE")),
        "cached": bool(record.get("cached", False)),
    }


def _evaluate_provider_batch(
    state: dict,
    *,
    questions: Sequence[DecisionQuestion],
    projection: Mapping,
    provider: DecisionProvider,
    task_id: str,
    stage: str,
    execution_id: str,
    verification_level: str,
    require_evidence: bool,
) -> dict:
    """One provider call for questions that share one projected state.

    Consequence is carried per question, so the policy verdict is computed per
    question even when several consequence classes share the call. The
    verification level belongs to the projected state and is shared, which is
    why questions that need different evidence levels are planned as separate
    steps by the compiler.
    """
    projection_for_call = {**dict(projection), "verification_level": verification_level}
    batch = batch_module.evaluate(
        state,
        questions=list(questions),
        projection=projection_for_call,
        provider=provider,
        task_id=task_id,
        stage=stage,
        execution_id=execution_id,
        require_evidence=require_evidence,
    )
    return {
        "batches": [batch],
        "results": [dict(row) for row in batch.get("results") or []],
        "status": _rollup([dict(row) for row in batch.get("results") or []]),
        "provider_available": bool(batch.get("provider_available")),
        "provider_reason": str(batch.get("provider_reason", "")),
    }


def decision(state: Mapping, decision_id: str) -> dict | None:
    """One recorded decision by id (the caller-facing lookup)."""
    return _decision(state, decision_id)


def _decision(state: Mapping, decision_id: str) -> dict | None:
    for record in state.get("decisions") or []:
        if isinstance(record, Mapping) and str(record.get("decision_id", "")) == str(decision_id):
            return dict(record)
    return None


def _rollup(results: Sequence[Mapping]) -> str:
    statuses = [str(row.get("status", "")) for row in results]
    if not statuses:
        return "empty"
    if all(status == "answered" for status in statuses):
        return "answered"
    if any(status == "answered" for status in statuses):
        return "partial"
    if all(status == "unavailable" for status in statuses):
        return "unavailable"
    return "failed"


def summarise(state: Mapping) -> dict:
    """Batching counters derived from recorded plans and batches."""
    batches = [
        record for record in (state.get("decision_batches") or [])
        if isinstance(record, Mapping) and not record.get("served_from_cache")
    ]
    return {
        "provider_batches": len(batches),
        "questions": sum(len(record.get("questions") or []) for record in batches),
        "cache_served_batches": sum(
            1 for record in (state.get("decision_batches") or [])
            if isinstance(record, Mapping) and record.get("served_from_cache")
        ),
        "note": "one batch is one provider request; cached reuse is never counted as a provider call",
    }


__all__ = [
    "STEP_STATUSES",
    "plan_steps",
    "group_step",
    "evaluate_step",
    "decision",
    "summarise",
]
