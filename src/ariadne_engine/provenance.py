"""Engine-bound execution provenance (AR-203 T1).

AR-202 introduced execution identities and kept requested, reported and observed
identity apart. AR-203 strengthens the boundary in three concrete ways:

1. **Claim levels are explicit.** Every identity fact carries the level that
   established it (``REQUESTED``, ``ENGINE_CREATED``, ``RUNTIME_OBSERVED``,
   ``PROVIDER_OBSERVED``, ``VERIFIED``, ``UNKNOWN``). ``requested model = X``
   never silently becomes ``observed model = X``.

2. **Provider observation is its own channel.** A model/provider adapter that
   actually reports what it ran may record a *provider* observation; a worker's
   prose may not. The runtime-observed channel and the provider-observed channel
   are separate fields, so a consumer can tell who established the fact.

3. **Execution identities used as provenance must exist.** ``render.verify``,
   ``critique.build_review`` and every verification record now require an
   engine-created execution *record in this run's state* rather than a
   well-formed string. A caller can still fabricate a record by writing run
   state directly; that is the documented trust boundary (the run-state writer),
   not something this module pretends to solve.

What this module cannot do: authenticate a person, isolate a process, or prove a
subprocess really ran a named model. Those limits are recorded honestly in every
view it returns.
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Mapping

from . import contracts
from .contracts import ContractError

WORKER_SOURCES = ("", "worker", "worker-output", "handoff", "self-reported", "reported", "prose")

PROVIDER_SOURCE_HINTS = ("adapter", "provider", "runtime", "cli", "api", "sdk", "gateway")


def executions(state: Mapping) -> list[dict]:
    value = state.get("executions")
    if not isinstance(value, list):
        return []
    return [record for record in value if isinstance(record, Mapping)]


def execution(state: Mapping, execution_id: str) -> dict | None:
    for record in executions(state):
        if str(record.get("execution_id", "")) == str(execution_id):
            return record
    return None


def require_engine_execution(
    state: Mapping,
    execution_id: str,
    *,
    role: str = "",
    task_id: str = "",
    label: str = "this operation",
    allow_finished: bool = True,
) -> dict:
    """Resolve an execution id to the engine-created record, or refuse.

    A well-formed ``exe_…`` string is not an execution identity: it must name a
    record this engine created in *this run's* state, with engine provenance and
    a supported role. This is the replacement for shape-only checks; the
    remaining trust boundary (a caller writing run state directly) is documented
    and is the same boundary every earlier milestone has.
    """
    value = str(execution_id or "").strip()
    if not value:
        raise ContractError(f"{label} requires the engine-created execution that performed it")
    record = execution(state, value)
    if record is None:
        raise ContractError(
            f"{label} names execution {value!r}, which this engine did not create for this run; "
            "a caller-chosen id is not an execution identity"
        )
    problems = contracts.execution_problems(record)
    if problems:
        raise ContractError(f"{label} names an execution record that is not usable: " + "; ".join(problems))
    if role and str(record.get("role", "")) != role:
        raise ContractError(
            f"{label} names a {record.get('role')} execution, not a {role} execution"
        )
    if task_id and str(record.get("task_id", "")) != str(task_id):
        raise ContractError(
            f"{label} names execution {value} created for task {record.get('task_id')}, not {task_id}"
        )
    if not allow_finished and str(record.get("state", "")) in ("COMPLETED", "FAILED"):
        raise ContractError(
            f"{label} names execution {value}, which already finished as {record.get('state')}"
        )
    return record


def require_distinct_executions(
    state: Mapping,
    first: str,
    second: str,
    *,
    label: str = "this operation",
) -> tuple[dict, dict]:
    """Two engine-created executions that are provably different records."""
    left = require_engine_execution(state, first, label=label)
    right = require_engine_execution(state, second, label=label)
    if str(left.get("execution_id")) == str(right.get("execution_id")):
        raise ContractError(
            f"{label} names one execution as both participants; independence cannot be "
            "established from the same execution"
        )
    return left, right


def identity_claims(record: Mapping) -> dict:
    """Per-field identity with the level that established each value.

    The map is built only from what the record itself carries. Nothing is
    inferred from a name, and nothing a worker reported is promoted.
    """
    requested = record.get("requested") if isinstance(record.get("requested"), Mapping) else {}
    reported = record.get("reported") if isinstance(record.get("reported"), Mapping) else {}
    observed = record.get("observed") if isinstance(record.get("observed"), Mapping) else {}
    provider_observed = record.get("provider_observed") if isinstance(record.get("provider_observed"), Mapping) else {}
    claims: dict[str, dict] = {}
    for field in contracts.IDENTITY_FIELDS:
        asked = str((requested or {}).get(field, "") or "").strip()
        said = str((reported or {}).get(field, "") or "").strip()
        seen = str((observed or {}).get(field, "") or "").strip()
        told = str((provider_observed or {}).get(field, "") or "").strip()
        observed_available = str((observed or {}).get("source", "")) not in ("", "unavailable")
        provider_available = bool(told) and told != "UNKNOWN"
        if provider_available:
            claims[field] = {
                "value": told,
                "level": "PROVIDER_OBSERVED",
                "evidence": [f"provider observation via {provider_observed.get('source', 'adapter')}"],
            }
        elif observed_available and seen and seen != "UNKNOWN":
            claims[field] = {
                "value": seen,
                "level": "RUNTIME_OBSERVED",
                "evidence": list(observed.get("evidence") or []),
            }
        elif asked:
            claims[field] = {
                "value": asked,
                "level": "REQUESTED",
                "evidence": ["the run requested this identity; the execution may not have used it"],
            }
        elif said:
            claims[field] = {
                "value": said,
                "level": "DECLARED",
                "evidence": ["the worker declared this in its own output; unverified prose"],
            }
        else:
            claims[field] = {
                "value": "UNKNOWN",
                "level": "UNKNOWN",
                "evidence": ["nothing established this identity; it remains unknown"],
            }
        if said and claims[field]["value"] != said:
            claims[field]["worker_claim"] = said
    return claims


def record_provider_observation(
    state: Mapping,
    execution_id: str,
    *,
    provider: str = "",
    model: str = "",
    request_id: str = "",
    run_id: str = "",
    source: str,
    raw: Mapping | None = None,
) -> dict:
    """Record what a model/provider adapter reported for one execution.

    Only an engine-side adapter or provider observer may write this channel. A
    worker statement arriving here is refused rather than promoted; the worker's
    own claim stays on the ``reported`` channel.
    """
    record = require_engine_execution(state, execution_id, label="a provider observation")
    observer = str(source or "").strip()
    if observer.lower() in WORKER_SOURCES:
        raise ContractError(
            "a provider observation must come from an engine-side adapter or provider observer, "
            "not from worker output; record the worker's claim as reported identity instead"
        )
    if not observer:
        raise ContractError("a provider observation needs the observer that established it")
    observation = {
        "provider": str(provider or "UNKNOWN") or "UNKNOWN",
        "model": str(model or "UNKNOWN") or "UNKNOWN",
        "request_id": str(request_id or ""),
        "provider_run_id": str(run_id or ""),
        "source": observer,
        "raw": dict(raw or {}),
        "observed_at": contracts.utc_now(),
    }
    record["provider_observed"] = observation
    return observation


def provenance_digest(record: Mapping) -> str:
    """A stable digest over the identity-bearing facts of one execution.

    It changes when any identity fact, the revision binding or the result
    changes, so two records can be compared without trusting labels.
    """
    payload = {
        "execution_id": str(record.get("execution_id", "")),
        "run_id": str(record.get("run_id", "")),
        "task_id": str(record.get("task_id", "")),
        "role": str(record.get("role", "")),
        "adapter": str(record.get("adapter", "")),
        "invocation": str(record.get("invocation", "")),
        "requested": dict(record.get("requested") or {}),
        "reported": dict(record.get("reported") or {}),
        "observed": dict(record.get("observed") or {}),
        "provider_observed": dict(record.get("provider_observed") or {}),
        "revision": dict(record.get("revision") or {}),
        "parent_execution": str(record.get("parent_execution", "")),
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    ).hexdigest()


def execution_provenance(state: Mapping, execution_id: str) -> dict:
    """The full provenance view for one engine-created execution.

    Every field a caller might need to audit what actually happened is present;
    fields the engine could not establish are ``UNKNOWN`` rather than guessed.
    """
    record = require_engine_execution(state, execution_id, label="an execution provenance request")
    claims = identity_claims(record)
    observed = dict(record.get("observed") or {})
    provider_observed = dict(record.get("provider_observed") or {})
    provenance = dict(record.get("provenance") or {})
    usage = record.get("usage") if isinstance(record.get("usage"), Mapping) else {}
    return {
        "schema_version": contracts.SCHEMA_ADAPTIVE,
        "execution_id": str(record.get("execution_id", "")),
        "task_id": str(record.get("task_id", "")),
        "run_id": str(record.get("run_id", "")),
        "parent_execution": str(record.get("parent_execution", "")),
        "role": str(record.get("role", "")),
        "adapter": str(record.get("adapter", "")),
        "invocation": str(record.get("invocation", "")),
        "state": str(record.get("state", "")),
        "requested": dict(record.get("requested") or {}),
        "reported": dict(record.get("reported") or {}),
        "observed": observed,
        "provider_observed": provider_observed,
        "claims": claims,
        "provider_request_id": str(provider_observed.get("request_id", "")),
        "provider_run_id": str(provider_observed.get("provider_run_id", "")),
        "revision": dict(record.get("revision") or {}),
        "created_at": str(record.get("created_at", "")),
        "started_at": str(record.get("started_at", "")),
        "observed_at": str(record.get("observed_at", "")),
        "completed_at": str(record.get("completed_at", "")),
        "failed_at": str(record.get("failed_at", "")),
        "outcome": str(record.get("state", "")),
        "provenance": provenance,
        "provenance_source": str(provenance.get("source", "")),
        "provenance_digest": provenance_digest(record),
        "usage": dict(usage),
        "limitations": [
            "the engine cannot authenticate a process or prove a named model executed; "
            "observed identity is only as strong as the adapter that reported it",
        ],
    }


def verify_observation_chain(state: Mapping, execution_id: str) -> dict:
    """Whether the record's own observation channels are internally consistent.

    A provider-observed fact requires a recorded observer source; a runtime
    observation requires an engine-side source; a worker claim never appears on
    an observed channel. This is the engine-side check behind the invariant
    "worker prose cannot replace engine execution provenance".
    """
    record = require_engine_execution(state, execution_id, label="an observation check")
    problems: list[str] = []
    observed = record.get("observed") if isinstance(record.get("observed"), Mapping) else {}
    if str(observed.get("source", "")) in ("worker", "worker-output", "handoff", "self-reported"):
        problems.append("the runtime-observed channel carries a worker-reported source")
    provider_observed = record.get("provider_observed") if isinstance(record.get("provider_observed"), Mapping) else {}
    if provider_observed and not str(provider_observed.get("source", "")).strip():
        problems.append("a provider observation carries no observer source")
    if provider_observed and str(provider_observed.get("source", "")).lower() in WORKER_SOURCES:
        problems.append("the provider-observed channel carries a worker-reported source")
    if str(record.get("provider_observed", "") or "") and not isinstance(provider_observed, Mapping):
        problems.append("the provider-observed field is not an object")
    return {
        "execution_id": str(record.get("execution_id", "")),
        "ok": not problems,
        "problems": problems,
    }


def provider_request_problems(state: Mapping) -> list[str]:
    """Whether two executions claim the same provider request id.

    A provider request id is how a bill or a provider-side trace is tied back to
    an execution; two executions claiming one request is a provenance conflict
    (a replayed or mislabelled observation), never a coincidence to ignore.
    """
    problems: list[str] = []
    seen: dict[str, str] = {}
    for record in executions(state):
        observation = record.get("provider_observed") if isinstance(record.get("provider_observed"), Mapping) else {}
        request_id = str((observation or {}).get("request_id", "") or "").strip()
        if not request_id:
            continue
        execution_id = str(record.get("execution_id", ""))
        if request_id in seen and seen[request_id] != execution_id:
            problems.append(
                f"provider request id {request_id!r} is claimed by both {seen[request_id]} and {execution_id}"
            )
        seen[request_id] = execution_id
    return problems


def same_execution(first: Mapping, second: Mapping) -> bool:
    """Whether two provenance views describe the same engine execution record."""
    return str(first.get("execution_id", "")) == str(second.get("execution_id", ""))


def valid_execution_id(value: str) -> bool:
    return bool(re.fullmatch(r"exe_[0-9TZ]+_[0-9a-f]{8}", value or ""))


__all__ = [
    "WORKER_SOURCES",
    "executions",
    "execution",
    "require_engine_execution",
    "require_distinct_executions",
    "identity_claims",
    "record_provider_observation",
    "provenance_digest",
    "execution_provenance",
    "verify_observation_chain",
    "provider_request_problems",
    "same_execution",
    "valid_execution_id",
]
