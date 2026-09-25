"""Decision batches: independent bounded questions over one projected state.

A batch evaluates several questions in one provider call. The questions must be
*independent*: no answer may depend on another answer in the same batch. When
question B depends on A's answer, that is a second decision step, because a
batch that could chain answers would hide a dependency the record cannot express.

The projected state is deliberately small: the caller projects only the evidence
the decision needs (a command result, a validator result, a previous attempt, a
requirement and its provenance), and the projection is refused when it exceeds
its bound rather than silently truncated. The projection's digest is recorded on
every decision, so a replay against a different state is detectable.

A decision record is evidence of what judgement was produced. It is not proof
that the resulting side effect occurred, and it never authorizes anything; the
``authorization_effect`` field is always ``none``.
"""

from __future__ import annotations

import json
from typing import Any, Mapping, Sequence

from .. import contracts
from ..contracts import ContractError
from . import policy
from .contracts import (
    DecisionQuestion,
    answer_from_provider,
    batch_digest,
    state_digest,
)
from .providers import DecisionProvider, DecisionProviderError

PROJECTION_LIMIT_CHARS = 16_000
PROJECTION_LIMIT_ENTRIES = 64


def project(*, entries: Mapping[str, Any]) -> dict:
    """Bound and digest one decision projection.

    The projection is a named set of evidence slices. It is refused — never
    truncated — when it exceeds the entry or character bound, because a decision
    made against silently missing evidence is worse than no decision.
    """
    if not isinstance(entries, Mapping):
        raise ContractError("a decision projection must be a mapping of named evidence slices")
    if len(entries) > PROJECTION_LIMIT_ENTRIES:
        raise ContractError(
            f"the decision projection has {len(entries)} entries; at most {PROJECTION_LIMIT_ENTRIES} are "
            "accepted, and evidence is refused rather than dropped"
        )
    encoded = json.dumps({str(key): value for key, value in entries.items()}, sort_keys=True, default=str)
    if len(encoded) > PROJECTION_LIMIT_CHARS:
        raise ContractError(
            f"the decision projection is {len(encoded)} characters; at most {PROJECTION_LIMIT_CHARS} are "
            "accepted. Project the evidence this decision needs, not the whole project."
        )
    return {
        "entries": {str(key): value for key, value in entries.items()},
        "digest": state_digest({str(key): value for key, value in entries.items()}),
        "chars": len(encoded),
    }


def batches(state: Mapping) -> list[dict]:
    values = state.get("decision_batches")
    if not isinstance(values, list):
        return []
    return [item for item in values if isinstance(item, Mapping)]


def decisions(state: Mapping) -> list[dict]:
    values = state.get("decisions")
    if not isinstance(values, list):
        return []
    return [item for item in values if isinstance(item, Mapping)]


def batch(state: Mapping, batch_id: str) -> dict | None:
    for record in batches(state):
        if str(record.get("batch_id", "")) == str(batch_id):
            return record
    return None


def decision(state: Mapping, decision_id: str) -> dict | None:
    for record in decisions(state):
        if str(record.get("decision_id", "")) == str(decision_id):
            return record
    return None


def for_question(state: Mapping, question_id: str, *, task_id: str = "") -> list[dict]:
    rows = [record for record in decisions(state) if str(record.get("question_id", "")) == str(question_id)]
    if task_id:
        rows = [record for record in rows if str(record.get("task_id", "")) == str(task_id)]
    return rows


def _unique_questions(questions: Sequence[DecisionQuestion]) -> list[DecisionQuestion]:
    seen: set[str] = set()
    ordered: list[DecisionQuestion] = []
    for question in questions or ():
        if not isinstance(question, DecisionQuestion):
            raise ContractError("a decision batch contains a question that is not a DecisionQuestion")
        if question.question_id in seen:
            raise ContractError(f"a decision batch cannot repeat question id {question.question_id!r}")
        seen.add(question.question_id)
        ordered.append(question)
    if not ordered:
        raise ContractError("a decision batch needs at least one question")
    return ordered


def evaluate(
    state: dict,
    *,
    questions: Sequence[DecisionQuestion],
    projection: Mapping,
    provider: DecisionProvider,
    task_id: str = "",
    stage: str = "",
    execution_id: str = "",
    require_evidence: bool = True,
) -> dict:
    """Ask one batch of independent questions and record every outcome.

    The provider is asked exactly once. Its failure is recorded as a failure, its
    unavailability as unavailability, and an answer outside the declared space as
    invalid — never coerced, never replaced by a plausible default.
    """
    if not isinstance(provider, DecisionProvider):
        raise ContractError("a decision batch needs a DecisionProvider")
    ordered = _unique_questions(questions)
    if not isinstance(projection, Mapping) or not str(projection.get("digest", "")):
        raise ContractError("a decision batch needs a projected state with a digest")
    projection_digest = str(projection.get("digest", ""))
    execution = ""
    if execution_id:
        from .. import provenance

        execution = str(provenance.require_engine_execution(
            state, execution_id, label="a decision batch",
        ).get("execution_id", ""))
    batch_id = contracts.new_record_id("dcb")
    available, unavailable_reason = provider.available()
    response: dict = {}
    provider_error = ""
    if available:
        request = {
            "batch_id": batch_id,
            "state_digest": projection_digest,
            "projection": dict(projection.get("entries") or {}),
            "questions": [question.as_record() for question in ordered],
            "instructions": (
                "Answer each question independently from the projected state only. Do not use an answer "
                "to another question in this batch. Answer inside the declared option set."
            ),
        }
        try:
            response = dict(provider.answer(request) or {})
        except DecisionProviderError as exc:
            provider_error = str(exc)
        except Exception as exc:  # a provider bug is a failure, never an answer
            provider_error = f"{type(exc).__name__}: {exc}"
    provider_identity = {
        "provider": str(response.get("provider", provider.provider or "")),
        "model": str(response.get("model", provider.model or "")),
        "model_version": str(response.get("model_version", provider.model_version or "")),
        "request_id": str(response.get("request_id", "")),
        "usage": dict(response.get("usage") or {}),
    }
    answers_payload = response.get("answers") if isinstance(response.get("answers"), Mapping) else {}
    failed_questions = {str(item) for item in (response.get("failed_questions") or [])}
    results: list[dict] = []
    for question in ordered:
        decision_id = contracts.new_record_id("dec")
        record = {
            "schema_version": contracts.SCHEMA_DECISION,
            "decision_id": decision_id,
            "batch_id": batch_id,
            "run_id": str(state.get("run_id", "")),
            "task_id": str(task_id),
            "stage": str(stage),
            "question_id": question.question_id,
            "instructions": question.instructions,
            "primitive": question.primitive,
            "definition_version": question.definition_version,
            "state_digest": projection_digest,
            "options": list(question.allowed),
            "scale": list(question.scale),
            "consequence": question.consequence,
            "answer": "",
            "answers": [],
            "answer_valid": False,
            "confidence": None,
            "confidence_kind": "NONE",
            "distribution": {},
            "provider": provider_identity["provider"],
            "model": provider_identity["model"],
            "model_version": provider_identity["model_version"],
            "provider_request_id": provider_identity["request_id"],
            "execution_id": execution,
            "policy_version": policy.POLICY_VERSION,
            "contract_version": contracts.DECISION_CONTRACT_VERSION,
            "status": "unavailable",
            "problems": [],
            "policy_verdict": {},
            "acted_on": False,
            "resulting_action": "",
            "authorization_effect": "none",
            "usage": dict(provider_identity["usage"]),
            "recorded_at": contracts.utc_now(),
        }
        if not available:
            record["status"] = "unavailable"
            record["problems"] = [unavailable_reason or "no decision provider is available"]
        elif provider_error:
            record["status"] = "failed"
            record["problems"] = [provider_error]
        elif question.question_id in failed_questions or question.question_id not in answers_payload:
            record["status"] = "failed"
            record["problems"] = ["the provider returned no answer for this question"]
        else:
            answer = answer_from_provider(question, answers_payload[question.question_id])
            record["answer"] = ", ".join(answer.answers)
            record["answers"] = list(answer.answers)
            record["answer_valid"] = bool(answer.valid)
            record["confidence"] = answer.confidence
            record["confidence_kind"] = answer.confidence_kind
            record["distribution"] = dict(answer.distribution)
            record["raw"] = answer.raw
            record["problems"] = list(answer.problems)
            record["status"] = "answered" if answer.valid else "invalid"
        if record["status"] == "answered":
            verdict = policy.may_act(
                record, consequence=question.consequence,
                verification_level=str((projection.get("verification_level") or "")),
                require_evidence=require_evidence,
            )
            record["policy_verdict"] = verdict
            if not verdict.get("accepted"):
                record["status"] = "refused"
        problems = contracts.decision_record_problems(record)
        if problems:
            raise ContractError("decision record is malformed: " + "; ".join(problems))
        contracts.require_collection_capacity(state, "decisions")
        state.setdefault("decisions", []).append(record)
        results.append({
            "decision_id": decision_id,
            "question_id": question.question_id,
            "status": record["status"],
            "answer": record["answer"],
            "answer_valid": record["answer_valid"],
            "confidence": record["confidence"],
            "confidence_kind": record["confidence_kind"],
        })
    answered = [item for item in results if item["status"] == "answered"]
    refused = [item for item in results if item["status"] == "refused"]
    invalid = [item for item in results if item["status"] == "invalid"]
    failed = [item for item in results if item["status"] == "failed"]
    if not available or provider_error:
        status = "unavailable" if not available else "failed"
    elif answered and not (refused or invalid or failed):
        status = "answered"
    elif answered:
        status = "partial"
    elif invalid:
        status = "partial"
    else:
        status = "failed"
    batch_record = {
        "schema_version": contracts.SCHEMA_DECISION,
        "batch_id": batch_id,
        "run_id": str(state.get("run_id", "")),
        "task_id": str(task_id),
        "stage": str(stage),
        "state_digest": projection_digest,
        "projection": dict(projection.get("entries") or {}),
        "projection_chars": int(projection.get("chars", 0) or 0),
        "batch_digest": batch_digest(ordered, projection_digest),
        "questions": [question.as_record() for question in ordered],
        "provider": provider_identity["provider"],
        "model": provider_identity["model"],
        "model_version": provider_identity["model_version"],
        "provider_request_id": provider_identity["request_id"],
        "provider_available": bool(available),
        "provider_reason": str(unavailable_reason if not available else provider_error),
        "execution_id": execution,
        "status": status,
        "results": results,
        "usage": dict(provider_identity["usage"]),
        "policy_version": policy.POLICY_VERSION,
        "contract_version": contracts.DECISION_CONTRACT_VERSION,
        "authorization_effect": "none",
        "recorded_at": contracts.utc_now(),
    }
    problems = contracts.decision_batch_problems(batch_record)
    if problems:
        raise ContractError("decision batch is malformed: " + "; ".join(problems))
    contracts.require_collection_capacity(state, "decision_batches")
    state.setdefault("decision_batches", []).append(batch_record)
    return batch_record


def mark_acted_on(state: dict, decision_id: str, *, action: str, verification_id: str = "") -> dict:
    """Record that an accepted decision drove one concrete action.

    This is the decision -> action edge of the trace. It records what the engine
    did with the judgement; it never re-labels a refused or invalid decision as
    acted on.
    """
    record = decision(state, decision_id)
    if record is None:
        raise ContractError(f"no decision record matches {decision_id!r}")
    if str(record.get("status", "")) not in ("answered", "refused"):
        raise ContractError(
            f"decision {decision_id} is {record.get('status')}; only an answered decision can be acted on"
        )
    if str(record.get("status")) == "refused":
        raise ContractError(
            f"decision {decision_id} was refused by policy; acting on it would bypass the risk-adjusted rule"
        )
    if not str(action or "").strip():
        raise ContractError("an acted-on decision must record the resulting action")
    record["acted_on"] = True
    record["resulting_action"] = str(action)
    record["acted_at"] = contracts.utc_now()
    if verification_id:
        record["verification_id"] = str(verification_id)
    return record


def trace(state: Mapping, *, task_id: str = "") -> list[dict]:
    """The decision -> action trace for one task (or the whole run)."""
    rows: list[dict] = []
    for record in decisions(state):
        if task_id and str(record.get("task_id", "")) != str(task_id):
            continue
        rows.append({
            "decision_id": record.get("decision_id"),
            "batch_id": record.get("batch_id"),
            "question_id": record.get("question_id"),
            "status": record.get("status"),
            "answer": record.get("answer"),
            "confidence": record.get("confidence"),
            "confidence_kind": record.get("confidence_kind"),
            "provider": record.get("provider"),
            "model_version": record.get("model_version"),
            "policy_version": record.get("policy_version"),
            "policy_verdict": record.get("policy_verdict"),
            "acted_on": bool(record.get("acted_on")),
            "resulting_action": record.get("resulting_action", ""),
            "verification_id": record.get("verification_id", ""),
        })
    return rows


def summarise(state: Mapping) -> dict:
    """Deterministic decision-plane counters."""
    rows = decisions(state)
    statuses: dict[str, int] = {}
    for record in rows:
        key = str(record.get("status", "unknown"))
        statuses[key] = statuses.get(key, 0) + 1
    return {
        "batches": len(batches(state)),
        "decisions": len(rows),
        "statuses": dict(sorted(statuses.items())),
        "acted_on": sum(1 for record in rows if record.get("acted_on")),
        "confidence_kinds": dict(sorted({
            str(record.get("confidence_kind", "NONE")): sum(
                1 for item in rows if str(item.get("confidence_kind", "NONE")) == str(record.get("confidence_kind", "NONE"))
            )
            for record in rows
        })),
    }


__all__ = [
    "PROJECTION_LIMIT_CHARS",
    "PROJECTION_LIMIT_ENTRIES",
    "project",
    "batches",
    "decisions",
    "batch",
    "decision",
    "for_question",
    "evaluate",
    "mark_acted_on",
    "trace",
    "summarise",
]
