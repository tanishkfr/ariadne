"""Safe decision-result caching (AR-205D T5).

A decision result may be reused only when everything that produced it is still
the same: the decision definition (question, version, primitive, allowed
space), the projected state digest, the provider, the *concrete* model version
and the policy version. The cache key binds all of them, so a hit is never a
guess:

.. code-block:: text

    key = H(question definition digest | projection digest | provider |
            concrete model version | policy version)

Keying on task text or a question id alone is refused by construction. A
concrete model version is mandatory — an entry stored against a moving alias
could be served under a model the original decision never saw.

Reuse preserves provenance rather than laundering it: a reused decision is a
*new* decision record that cites the original decision and cache entry, keeps
the original confidence and its kind exactly, and is re-judged by the current
policy. A cached decision does not become more trustworthy because it was
reused, and cache reuse never carries an authorization effect.

Invalidation is content-driven. A changed projection produces a different
digest (a miss, not a silent reuse); stored dependency fingerprints are
compared on lookup so a relevant change marks an entry stale; entries may be
explicitly revoked or superseded; and an optional expiry marks time-bound
entries stale. Irrelevant global state changes do not touch the cache.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping

from .. import contracts
from ..contracts import (
    DECISION_INTELLIGENCE_CONTRACT,
    SCHEMA_DECISION,
    SCHEMA_DECISION_INTELLIGENCE,
    ContractError,
)
from . import batch as batch_module
from . import policy
from .contracts import DecisionQuestion, batch_digest, validate_answer
from .providers import concrete_model_version

REUSE_MISS_REASONS = (
    "NO_ENTRY",
    "QUESTION_DEFINITION_CHANGED",
    "STATE_CHANGED",
    "PROVIDER_CHANGED",
    "MODEL_VERSION_CHANGED",
    "POLICY_VERSION_CHANGED",
    "FINGERPRINT_CHANGED",
    "EXPIRED",
    "REVOKED",
    "SUPERSEDED",
)
"""Structured reasons a cache lookup did not serve a decision."""


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def definition_digest(question: DecisionQuestion) -> str:
    record = question.as_record()
    return hashlib.sha256(_canonical(record).encode("utf-8")).hexdigest()


def key_for(
    question: DecisionQuestion,
    *,
    projection_digest: str,
    provider: str,
    model_version: str,
    policy_version: str,
) -> str:
    """The full cache key. Every binding is mandatory."""
    if not isinstance(question, DecisionQuestion):
        raise ContractError("a decision cache key needs a DecisionQuestion")
    if not str(projection_digest or "").strip():
        raise ContractError("a decision cache key needs the projected state digest")
    if not str(provider or "").strip():
        raise ContractError("a decision cache key needs the provider identity")
    if not str(model_version or "").strip():
        raise ContractError(
            "a decision cache key needs a concrete model version; a moving alias cannot be cached"
        )
    if not concrete_model_version(model_version):
        raise ContractError(
            f"a decision cache key needs a concrete model version; {model_version!r} is a moving alias"
        )
    if not str(policy_version or "").strip():
        raise ContractError("a decision cache key needs the policy version")
    payload = {
        "question": question.as_record(),
        "definition_digest": definition_digest(question),
        "projection_digest": str(projection_digest),
        "provider": str(provider),
        "model_version": str(model_version),
        "policy_version": str(policy_version),
    }
    return hashlib.sha256(_canonical(payload).encode("utf-8")).hexdigest()


def entries(state: Mapping) -> list[dict]:
    return [dict(item) for item in (state.get("decision_cache") or []) if isinstance(item, Mapping)]


def entry(state: Mapping, cache_id: str) -> dict | None:
    for item in entries(state):
        if str(item.get("cache_id", "")) == str(cache_id):
            return item
    return None


def _stored(state: Mapping, cache_id: str) -> dict:
    for item in state.get("decision_cache") or []:
        if isinstance(item, Mapping) and str(item.get("cache_id", "")) == str(cache_id):
            return item
    raise ContractError(f"no decision cache entry matches {cache_id!r}")


def _expired(item: Mapping, *, now: datetime) -> bool:
    expires_at = str(item.get("expires_at", "") or "")
    if not expires_at:
        return False
    try:
        deadline = datetime.fromisoformat(expires_at)
    except ValueError:
        return True
    if deadline.tzinfo is None:
        deadline = deadline.replace(tzinfo=timezone.utc)
    return now >= deadline


def _fingerprint_mismatch(item: Mapping, current: Mapping | None) -> list[str]:
    if not current:
        return []
    stored = item.get("fingerprints") if isinstance(item.get("fingerprints"), Mapping) else {}
    changed: list[str] = []
    for key, value in current.items():
        name = str(key)
        if name not in stored:
            changed.append(name)
        elif str(stored[name]) != str(value):
            changed.append(name)
    return sorted(changed)


def lookup(
    state: Mapping,
    *,
    question: DecisionQuestion,
    projection_digest: str,
    provider: str,
    model_version: str,
    policy_version: str = policy.POLICY_VERSION,
    current_fingerprints: Mapping | None = None,
    now: datetime | None = None,
) -> dict:
    """Look one decision up. Returns ``{"hit", "entry", "reason", "detail"}``."""
    key = key_for(
        question,
        projection_digest=projection_digest,
        provider=provider,
        model_version=model_version,
        policy_version=policy_version,
    )
    moment = now or datetime.now(timezone.utc)
    for item in entries(state):
        if str(item.get("key", "")) != key:
            continue
        if str(item.get("freshness", "")) == "REVOKED":
            return {"hit": False, "entry": None, "reason": "REVOKED", "detail": str(item.get("reason", ""))}
        if str(item.get("freshness", "")) == "SUPERSEDED" or str(item.get("superseded_by", "")):
            return {"hit": False, "entry": None, "reason": "SUPERSEDED", "detail": str(item.get("superseded_by", ""))}
        if str(item.get("freshness", "")) == "STALE":
            return {
                "hit": False,
                "entry": None,
                "reason": str(item.get("stale_reason", "") or "FINGERPRINT_CHANGED"),
                "detail": str(item.get("reason", "")),
            }
        if _expired(item, now=moment):
            return {"hit": False, "entry": None, "reason": "EXPIRED", "detail": str(item.get("expires_at", ""))}
        changed = _fingerprint_mismatch(item, current_fingerprints)
        if changed:
            return {
                "hit": False,
                "entry": None,
                "reason": "FINGERPRINT_CHANGED",
                "detail": "the decision's evidence changed: " + ", ".join(changed),
            }
        return {"hit": True, "entry": item, "reason": "HIT", "detail": ""}
    return {
        "hit": False,
        "entry": None,
        "reason": _diagnose(
            state,
            question=question,
            projection_digest=projection_digest,
            provider=provider,
            model_version=model_version,
            policy_version=policy_version,
        ),
        "detail": "",
    }


def _diagnose(
    state: Mapping,
    *,
    question: DecisionQuestion,
    projection_digest: str,
    provider: str,
    model_version: str,
    policy_version: str,
) -> str:
    """Why no exact key matched, in structured terms (never a guessed hit)."""
    digest = definition_digest(question)
    same_question = [
        item for item in entries(state)
        if str(item.get("question_id", "")) == str(question.question_id)
    ]
    if not same_question:
        return "NO_ENTRY"
    if not any(str(item.get("definition_digest", "")) == digest for item in same_question):
        return "QUESTION_DEFINITION_CHANGED"
    if not any(str(item.get("provider", "")) == str(provider) for item in same_question):
        return "PROVIDER_CHANGED"
    if not any(str(item.get("model_version", "")) == str(model_version) for item in same_question):
        return "MODEL_VERSION_CHANGED"
    if not any(str(item.get("policy_version", "")) == str(policy_version) for item in same_question):
        return "POLICY_VERSION_CHANGED"
    return "STATE_CHANGED"


def store(
    state: dict,
    record: Mapping,
    *,
    question: DecisionQuestion,
    projection_digest: str,
    fingerprints: Mapping | None = None,
    ttl_seconds: int | None = None,
) -> dict:
    """Store an answered decision for safe reuse.

    Only an ``answered`` record with a valid answer and a concrete model
    version is cacheable. A model version that is empty or looks like a moving
    alias is refused.
    """
    if str(record.get("status", "")) != "answered" or record.get("answer_valid") is not True:
        raise ContractError(
            f"decision {record.get('decision_id')} is {record.get('status')}; only a validated answer is cacheable"
        )
    model_version = str(record.get("model_version", "") or "").strip()
    provider = str(record.get("provider", "") or "").strip()
    if not model_version:
        raise ContractError(
            "a decision with no concrete model version cannot be cached; an alias may move under the answer"
        )
    if not provider:
        raise ContractError("a decision with no provider identity cannot be cached")
    key = key_for(
        question,
        projection_digest=projection_digest,
        provider=provider,
        model_version=model_version,
        policy_version=str(record.get("policy_version", "") or policy.POLICY_VERSION),
    )
    expires_at = ""
    if ttl_seconds is not None:
        if int(ttl_seconds) <= 0:
            raise ContractError("a decision cache TTL must be positive")
        expires_at = (
            datetime.now(timezone.utc) + timedelta(seconds=int(ttl_seconds))
        ).isoformat(timespec="seconds")
    item = {
        "schema_version": SCHEMA_DECISION_INTELLIGENCE,
        "cache_id": contracts.new_record_id("dch"),
        "key": key,
        "question_id": str(question.question_id),
        "definition_version": str(question.definition_version),
        "definition_digest": definition_digest(question),
        "primitive": str(question.primitive),
        "options": list(question.allowed),
        "state_digest": str(projection_digest),
        "provider": provider,
        "model": str(record.get("model", "") or ""),
        "model_version": model_version,
        "policy_version": str(record.get("policy_version", "") or policy.POLICY_VERSION),
        "contract_version": DECISION_INTELLIGENCE_CONTRACT,
        "source_decision_id": str(record.get("decision_id", "")),
        "answer": str(record.get("answer", "")),
        "answers": [str(value) for value in (record.get("answers") or [])],
        "answer_valid": True,
        "confidence": record.get("confidence"),
        "confidence_kind": str(record.get("confidence_kind", "NONE")),
        "distribution": {str(key): float(value) for key, value in dict(record.get("distribution") or {}).items()},
        "fingerprints": {str(key): str(value) for key, value in dict(fingerprints or {}).items()},
        "freshness": "CURRENT",
        "reason": "",
        "superseded_by": "",
        "expires_at": expires_at,
        "authorization_effect": "none",
        "recorded_at": contracts.utc_now(),
        "note": (
            "provenance is preserved on reuse; this entry never grants authorization and is only "
            "served when every binding still matches"
        ),
    }
    problems = contracts.decision_cache_entry_problems(item)
    if problems:
        raise ContractError("the decision cache entry is malformed: " + "; ".join(problems))
    contracts.require_collection_capacity(state, "decision_cache")
    state.setdefault("decision_cache", []).append(item)
    return item


def store_decision(
    state: dict,
    *,
    decision_id: str,
    question: DecisionQuestion,
    projection_digest: str,
    fingerprints: Mapping | None = None,
    ttl_seconds: int | None = None,
) -> dict:
    """Cache one recorded decision by id (the call sites' convenience path)."""
    for item in state.get("decisions") or []:
        if isinstance(item, Mapping) and str(item.get("decision_id", "")) == str(decision_id):
            return store(
                state, item,
                question=question,
                projection_digest=projection_digest,
                fingerprints=fingerprints,
                ttl_seconds=ttl_seconds,
            )
    raise ContractError(f"no decision record matches {decision_id!r}")


def invalidate(
    state: dict,
    *,
    reason: str,
    question_id: str = "",
    cache_id: str = "",
    key: str = "",
    model_version: str = "",
    superseded_by: str = "",
) -> list[str]:
    """Revoke or supersede matching entries. The reason is mandatory."""
    if not str(reason or "").strip():
        raise ContractError("an invalidation must record why the cached decision is no longer reusable")
    touched: list[str] = []
    for item in state.get("decision_cache") or []:
        if not isinstance(item, dict):
            continue
        if cache_id and str(item.get("cache_id", "")) != str(cache_id):
            continue
        if key and str(item.get("key", "")) != str(key):
            continue
        if question_id and str(item.get("question_id", "")) != str(question_id):
            continue
        if model_version and str(item.get("model_version", "")) != str(model_version):
            continue
        if not (cache_id or key or question_id or model_version):
            raise ContractError(
                "an invalidation must name at least one of cache id, key, question id or model version"
            )
        if superseded_by:
            item["freshness"] = "SUPERSEDED"
            item["superseded_by"] = str(superseded_by)
        else:
            item["freshness"] = "REVOKED"
        item["reason"] = str(reason)
        item["invalidated_at"] = contracts.utc_now()
        touched.append(str(item.get("cache_id", "")))
    return touched


def expire(state: dict, *, now: datetime | None = None) -> list[str]:
    """Mark time-bound entries stale. Expiry is a freshness verdict, not deletion."""
    moment = now or datetime.now(timezone.utc)
    touched: list[str] = []
    for item in state.get("decision_cache") or []:
        if not isinstance(item, dict) or str(item.get("freshness", "")) != "CURRENT":
            continue
        if _expired(item, now=moment):
            item["freshness"] = "STALE"
            item["stale_reason"] = "EXPIRED"
            item["reason"] = "the cached decision passed its expiry"
            touched.append(str(item.get("cache_id", "")))
    return touched


def materialise(
    state: dict,
    item: Mapping,
    *,
    question: DecisionQuestion,
    projection: Mapping,
    consequence: str,
    verification_level: str = "",
    require_evidence: bool = True,
    task_id: str = "",
    stage: str = "",
) -> dict:
    """Serve one cache entry as a new decision record that preserves provenance.

    The reused answer is re-judged by the *current* policy and the *current*
    verification level. Reuse never raises confidence and never authorizes.
    """
    projection_digest = str(projection.get("digest", ""))
    if not projection_digest or projection_digest != str(item.get("state_digest", "")):
        raise ContractError(
            "a cached decision can only be reused against the exact projected state it was made on"
        )
    recomputed = batch_module.project(entries=projection.get("entries") or {})["digest"]
    if recomputed != projection_digest:
        raise ContractError(
            "the supplied projection entries do not hash to the recorded state digest; "
            "reuse is refused rather than trusting a caller-supplied digest"
        )
    if str(item.get("question_id", "")) != str(question.question_id):
        raise ContractError(
            f"cache entry {item.get('cache_id')} was made for question {item.get('question_id')!r}; "
            f"it cannot be reused for {question.question_id!r}"
        )
    if str(item.get("definition_digest", "")) != definition_digest(question):
        raise ContractError(
            "the cached decision was made against a different question definition; reuse is refused"
        )
    answers, answer_problems = validate_answer(question, item.get("answers") or item.get("answer"))
    if answer_problems or not answers:
        raise ContractError(
            "the cached answer does not satisfy the current question's declared option set; reuse is refused"
        )
    if str(item.get("freshness", "")) != "CURRENT":
        raise ContractError(f"cache entry {item.get('cache_id')} is {item.get('freshness')}; it cannot be reused")
    if item.get("answer_valid") is not True:
        raise ContractError("a cached decision without a validated answer cannot be reused")
    batch_id = contracts.new_record_id("dcb")
    batch_record = {
        "schema_version": SCHEMA_DECISION,
        "batch_id": batch_id,
        "run_id": str(state.get("run_id", "")),
        "task_id": str(task_id),
        "stage": str(stage),
        "state_digest": projection_digest,
        "projection": dict(projection.get("entries") or {}),
        "projection_chars": int(projection.get("chars", 0) or 0),
        "batch_digest": batch_digest([question], projection_digest),
        "questions": [question.as_record()],
        "provider": str(item.get("provider", "")),
        "model": str(item.get("model", "")),
        "model_version": str(item.get("model_version", "")),
        "provider_request_id": "",
        "provider_available": False,
        "provider_reason": "served from the decision cache; no provider call was made",
        "served_from_cache": True,
        "cache_id": str(item.get("cache_id", "")),
        "execution_id": "",
        "status": "answered",
        "results": [],
        "usage": {},
        "policy_version": policy.POLICY_VERSION,
        "contract_version": contracts.DECISION_CONTRACT_VERSION,
        "authorization_effect": "none",
        "recorded_at": contracts.utc_now(),
    }
    decision_id = contracts.new_record_id("dec")
    record = {
        "schema_version": SCHEMA_DECISION,
        "decision_id": decision_id,
        "batch_id": batch_id,
        "run_id": str(state.get("run_id", "")),
        "task_id": str(task_id),
        "stage": str(stage),
        "question_id": str(question.question_id),
        "instructions": question.instructions,
        "primitive": question.primitive,
        "definition_version": question.definition_version,
        "state_digest": projection_digest,
        "options": list(question.allowed),
        "scale": list(question.scale),
        "consequence": str(consequence),
        "answer": str(item.get("answer", "")),
        "answers": [str(value) for value in (item.get("answers") or [])],
        "answer_valid": True,
        "confidence": item.get("confidence"),
        "confidence_kind": str(item.get("confidence_kind", "NONE")),
        "distribution": dict(item.get("distribution") or {}),
        "provider": str(item.get("provider", "")),
        "model": str(item.get("model", "")),
        "model_version": str(item.get("model_version", "")),
        "provider_request_id": "",
        "execution_id": "",
        "policy_version": policy.POLICY_VERSION,
        "contract_version": contracts.DECISION_CONTRACT_VERSION,
        "status": "answered",
        "problems": [],
        "policy_verdict": {},
        "acted_on": False,
        "resulting_action": "",
        "authorization_effect": "none",
        "usage": {},
        "cached": True,
        "cache_id": str(item.get("cache_id", "")),
        "source_decision_id": str(item.get("source_decision_id", "")),
        "recorded_at": contracts.utc_now(),
    }
    verdict = policy.may_act(
        record, consequence=consequence,
        verification_level=verification_level,
        require_evidence=require_evidence,
    )
    record["policy_verdict"] = verdict
    if not verdict.get("accepted"):
        record["status"] = "refused"
    problems = contracts.decision_record_problems(record)
    if problems:
        raise ContractError("the reused decision record is malformed: " + "; ".join(problems))
    batch_record["results"] = [{
        "decision_id": decision_id,
        "question_id": str(question.question_id),
        "status": record["status"],
        "answer": record["answer"],
        "answer_valid": True,
        "confidence": record["confidence"],
        "confidence_kind": record["confidence_kind"],
    }]
    problems = contracts.decision_batch_problems(batch_record)
    if problems:
        raise ContractError("the cache-reuse batch record is malformed: " + "; ".join(problems))
    contracts.require_collection_capacity(state, "decision_batches")
    state.setdefault("decision_batches", []).append(batch_record)
    contracts.require_collection_capacity(state, "decisions")
    state.setdefault("decisions", []).append(record)
    return record


def summarise(state: Mapping) -> dict:
    rows = entries(state)
    fresh = [item for item in rows if str(item.get("freshness", "")) == "CURRENT"]
    reused = [
        record for record in (state.get("decisions") or [])
        if isinstance(record, Mapping) and record.get("cached") is True
    ]
    return {
        "entries": len(rows),
        "by_freshness": {
            name: sum(1 for item in rows if str(item.get("freshness", "")) == name)
            for name in sorted({str(item.get("freshness", "")) for item in rows})
        },
        "reusable": len(fresh),
        "reuses_recorded": len(reused),
        "note": "a reuse is a new decision record citing the original; confidence provenance is preserved",
    }


__all__ = [
    "REUSE_MISS_REASONS",
    "definition_digest",
    "key_for",
    "entries",
    "entry",
    "lookup",
    "store",
    "store_decision",
    "invalidate",
    "expire",
    "materialise",
    "summarise",
]
