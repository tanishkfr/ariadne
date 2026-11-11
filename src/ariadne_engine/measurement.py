"""The 2.4B execution measurement contract.

What this module is
-------------------
Ariadne already records the facts a task produced: one durable task record with
its attempts, validation, review, proof and acceptance; one engine-created
execution per worker invocation; and provider-reported usage only when an
adapter or the runtime actually measured it. Those records are authoritative and
this module never replaces them.

What was missing was one **readable, versioned row per attempt** that answers the
question an efficiency claim needs answered: what was asked, which intelligence
was chosen, what did it observe, what did it consume, and what was actually
accepted. So this module is a projection over existing records, not a second
store of truth:

* every field carries its provenance -- ``OBSERVED`` by the engine,
  ``REPORTED`` by a provider that supplied a measurement, ``DECLARED`` by a
  caller, or ``UNKNOWN``;
* an absent measurement is ``UNKNOWN``. It is never zero and never estimated
  from character counts, a model name, or a price table;
* a completed task is not an accepted task. ``COMPLETED`` means the worker
  returned; ``ACCEPTED`` requires the human decision that actually closes the
  task, and the two are separate fields;
* records are versioned. Updating an attempt's projection supersedes the earlier
  row instead of overwriting it, so a later review cannot silently rewrite what
  the attempt looked like when it finished.

No provider is called here and no token figure is invented.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Mapping, Sequence

from . import contracts
from .contracts import ContractError
from .serialization import canonical_json, digest_text

MEASUREMENT_SCHEMA = "ar-24b-measurement-1"
MEASUREMENT_POLICY = "intelligence-measurement-1"
COLLECTION = "measurements"
MAX_MEASUREMENTS = 10_000

UNKNOWN = "UNKNOWN"
OBSERVED = "OBSERVED"
REPORTED = "REPORTED"
DECLARED = "DECLARED"
PROVENANCE_LEVELS = (OBSERVED, REPORTED, DECLARED, UNKNOWN)

TASK_FAMILIES = (
    "feature", "bug", "refactor", "performance", "audit", "research",
    "verification", "ui-redesign", "new-project", "continue-project", "unknown",
)

OUTCOME_FIELDS = (
    "validation", "review", "proof", "requirements_proven",
    "requirements_unresolved", "acceptance",
)


def _field(value, *, provenance: str, source: str, evidence: Sequence[str] = ()) -> dict:
    """One measured value with its provenance.

    ``UNKNOWN`` is a first-class value, not an error. It is what the engine says
    when it did not observe the fact, and a report must be able to count it.
    """
    level = str(provenance or UNKNOWN)
    if level not in PROVENANCE_LEVELS:
        raise ContractError(f"unsupported measurement provenance: {level!r}")
    if value is None or (isinstance(value, str) and not value.strip()):
        level = UNKNOWN
        value = UNKNOWN
    if level == UNKNOWN:
        value = UNKNOWN
    return {
        "value": value,
        "provenance": level,
        "source": str(source),
        "evidence": [str(item) for item in evidence if str(item).strip()],
    }


def _value(row: Mapping | None) -> object:
    return (row or {}).get("value", UNKNOWN) if isinstance(row, Mapping) else UNKNOWN


def _number_or_unknown(value) -> object:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return UNKNOWN
    return int(value) if float(value).is_integer() else value


def _timestamp(text: str) -> datetime | None:
    value = str(text or "").strip()
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed


def _duration_seconds(started: str, ended: str) -> object:
    start = _timestamp(started)
    end = _timestamp(ended)
    if start is None or end is None:
        return UNKNOWN
    seconds = (end - start).total_seconds()
    if seconds < 0:
        return UNKNOWN
    return round(seconds, 3)


def _packet_bytes(path: str) -> object:
    target = Path(str(path or ""))
    if not str(path or "").strip():
        return UNKNOWN
    if target.is_dir():
        # A task attempt records its packet directory; the request the worker
        # actually received is the packet file inside it.
        packet = target / "packet.txt"
        target = packet if packet.is_file() else target
    try:
        return int(target.stat().st_size) if target.is_file() else UNKNOWN
    except OSError:
        return UNKNOWN


def _usage_values(record: Mapping | None) -> tuple[dict, dict]:
    usage = (record or {}).get("usage") if isinstance(record, Mapping) else None
    if not isinstance(usage, Mapping):
        return {}, {}
    values = usage.get("values") if isinstance(usage.get("values"), Mapping) else {}
    return dict(usage), dict(values)


def _validation_record(attempt: Mapping) -> dict:
    """The engine's own validation file, re-hashed before it is trusted."""
    validation = dict((attempt or {}).get("validation") or {})
    path = str(validation.get("path", "") or "")
    expected = str(validation.get("validation_sha256", "") or "")
    if not path or not Path(path).is_file():
        return {}
    try:
        raw = Path(path).read_bytes()
    except OSError:
        return {}
    actual = hashlib.sha256(raw).hexdigest()
    if expected and actual != expected:
        return {}
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _proof_counts(state: Mapping, task: Mapping) -> dict:
    proof = dict((task or {}).get("proof") or {})
    proof_id = str(proof.get("proof_id", "") or "")
    receipts = state.get("proof_receipts") if isinstance(state, Mapping) else None
    if not proof_id or not isinstance(receipts, list):
        return {}
    for receipt in receipts:
        if isinstance(receipt, Mapping) and str(receipt.get("proof_id", "")) == proof_id:
            verdicts = dict(receipt.get("requirement_verdicts") or {})
            proven = sum(
                1 for value in verdicts.values()
                if str(value) in ("PROVEN", "PROVEN_UNAFFECTED")
            )
            unresolved = len(verdicts) - proven
            return {
                "receipt": dict(receipt),
                "proven": proven,
                "unresolved": unresolved,
            }
    return {}


def _review_required(task: Mapping) -> bool:
    review = dict((task or {}).get("review") or {})
    return bool(review)


def build(
    state: Mapping,
    task: Mapping,
    *,
    attempt: Mapping | None = None,
    execution: Mapping | None = None,
    plan: Mapping | None = None,
) -> dict:
    """Project one task attempt into a measurement record.

    The function is pure with respect to the run state: it reads records and, for
    a validation record or a packet, re-hashes the file before using it. It never
    writes and never guesses.
    """
    task = dict(task or {})
    attempts = [item for item in task.get("attempts") or () if isinstance(item, Mapping)]
    selected_attempt = dict(attempt or (attempts[-1] if attempts else {}))
    attempt_id = str(selected_attempt.get("attempt_id", "") or "")
    packet_id = str(selected_attempt.get("packet_id", "") or "")
    plan = dict(plan or {})
    characterisation = dict(plan.get("characterisation") or {})
    frame = dict(plan.get("frame") or {})
    plan_skills = plan.get("skills") if isinstance(plan.get("skills"), Mapping) else {}
    task_skills = task.get("skills") if isinstance(task.get("skills"), list) else []
    selected_entries = list(plan_skills.get("selected") or task_skills or ())
    selected_skills = []
    for entry in selected_entries:
        if not isinstance(entry, Mapping):
            continue
        selected_skills.append({
            "id": str(entry.get("id", "")),
            "version": str(entry.get("version", "")),
            "mandatory": bool(entry.get("mandatory")),
            "selection_reason": str(entry.get("reason", entry.get("selection_reason", ""))),
            "state": str(entry.get("state", "selected")),
        })

    # ------------------------------------------------------------ identity
    execution_record = dict(execution or {})
    if not execution_record and str(selected_attempt.get("execution_id", "")).strip():
        rows = state.get("executions") if isinstance(state, Mapping) else None
        for row in rows or ():
            if isinstance(row, Mapping) and str(row.get("execution_id", "")) == str(selected_attempt.get("execution_id")):
                execution_record = dict(row)
                break
    requested = dict(execution_record.get("requested") or {})
    reported = dict(execution_record.get("reported") or {})
    observed = dict(execution_record.get("observed") or {})
    provider_observed = dict(execution_record.get("provider_observed") or {})
    observed_available = (
        str(observed.get("source", "unavailable")) not in ("", "unavailable")
        and str(observed.get("provider", UNKNOWN)).upper() != UNKNOWN
    )
    if provider_observed.get("provider") or provider_observed.get("model"):
        identity_source = "provider-observed"
        provider_value = str(provider_observed.get("provider", "") or UNKNOWN)
        model_value = str(provider_observed.get("model", "") or UNKNOWN)
        identity_provenance = OBSERVED
    elif observed_available:
        identity_source = str(observed.get("source", "runtime-observed"))
        provider_value = str(observed.get("provider", UNKNOWN) or UNKNOWN)
        model_value = str(observed.get("model", UNKNOWN) or UNKNOWN)
        identity_provenance = OBSERVED
    elif reported.get("provider") or reported.get("model"):
        identity_source = "worker-reported"
        provider_value = str(reported.get("provider", "") or UNKNOWN)
        model_value = str(reported.get("model", "") or UNKNOWN)
        identity_provenance = REPORTED
    elif requested.get("provider") or requested.get("model"):
        identity_source = "preflight-declared"
        provider_value = str(requested.get("provider", "") or UNKNOWN)
        model_value = str(requested.get("model", "") or UNKNOWN)
        identity_provenance = DECLARED
    else:
        identity_source = "unavailable"
        provider_value = UNKNOWN
        model_value = UNKNOWN
        identity_provenance = UNKNOWN
    usage, usage_values = _usage_values(execution_record)
    model_revision = str(usage.get("model_version", "") or UNKNOWN)
    effort = str(requested.get("effort", "") or UNKNOWN)
    adapter_id = str(selected_attempt.get("adapter", "") or execution_record.get("adapter", "") or UNKNOWN)
    availability_value = UNKNOWN
    availability_provenance = UNKNOWN
    if execution_record:
        availability_value = str(execution_record.get("state", UNKNOWN) or UNKNOWN)
        availability_provenance = OBSERVED

    # ----------------------------------------------------------- execution
    validation = dict(selected_attempt.get("validation") or {})
    validation_file = _validation_record(selected_attempt)
    started_at = str(selected_attempt.get("started_at", "") or execution_record.get("started_at", "") or "")
    finished_at = str(
        execution_record.get("completed_at", "")
        or execution_record.get("failed_at", "")
        or validation.get("recorded_at", "")
        or ""
    )
    changed_files = []
    for item in validation_file.get("changed_files") or ():
        if str(item).strip() and str(item) not in changed_files:
            changed_files.append(str(item))
    packet_path = str(selected_attempt.get("packet_path", "") or "")
    context_decisions = [
        item for item in (state.get("context_decisions") if isinstance(state, Mapping) else []) or ()
        if isinstance(item, Mapping) and str(item.get("task_id", "")) in (str(task.get("task_id", "")), packet_id)
    ]
    context_decision = context_decisions[-1] if context_decisions else {}
    context_metrics = context_decision.get("metrics") if isinstance(context_decision.get("metrics"), Mapping) else {}
    if not context_metrics and context_decision:
        context_metrics = {
            "candidates": context_decision.get("candidates"),
            "included": context_decision.get("included"),
            "omitted": context_decision.get("omitted"),
            "included_bytes": context_decision.get("included_bytes"),
            "omitted_bytes": context_decision.get("omitted_bytes"),
            "cache_hits": (context_decision.get("cache") or {}).get("hits"),
            "cache_misses": (context_decision.get("cache") or {}).get("misses"),
            "invalidations": len((context_decision.get("cache") or {}).get("invalidated") or ()),
        }
    failures = [
        item for item in (state.get("failures") if isinstance(state, Mapping) else []) or ()
        if isinstance(item, Mapping) and str(item.get("task_id", "")) in (str(task.get("task_id", "")), packet_id)
    ]
    quota_failures = 0
    for failure in failures:
        detail = (str(failure.get("detail", "")) + " " + str(failure.get("evidence", ""))).lower()
        if str(failure.get("class", "")) == "PROVIDER_FAILURE" and any(
            token in detail for token in ("quota", "rate limit", "rate-limit", "usage limit", "429")
        ):
            quota_failures += 1
    worker_exit = UNKNOWN
    if str(selected_attempt.get("state", "")) in ("returned", "validated", "failed"):
        worker_exit = str(selected_attempt.get("outcome", selected_attempt.get("state", UNKNOWN)))
    repair_attempts = sum(1 for item in attempts if str(item.get("repair_kind", "")).strip())
    measured_values = usage_values if usage.get("measured") else {}

    execution_row = {
        "started_at": _field(started_at, provenance=OBSERVED if started_at else UNKNOWN, source="attempt-record"),
        "finished_at": _field(finished_at, provenance=OBSERVED if finished_at else UNKNOWN, source="execution-or-validation-record"),
        "wall_clock_seconds": _field(
            _duration_seconds(started_at, finished_at),
            provenance=OBSERVED if _duration_seconds(started_at, finished_at) != UNKNOWN else UNKNOWN,
            source="attempt-and-execution-timestamps",
        ),
        "attempts": _field(len(attempts), provenance=OBSERVED, source="task-record"),
        "repair_attempts": _field(repair_attempts, provenance=OBSERVED, source="task-attempt-records"),
        "tool_calls": _field(
            _number_or_unknown(measured_values.get("tool_calls")),
            provenance=REPORTED if measured_values.get("tool_calls") is not None else UNKNOWN,
            source=str(usage.get("source", "provider-usage")) if measured_values else "unavailable",
        ),
        "tool_errors": _field(
            _number_or_unknown(measured_values.get("tool_errors")),
            provenance=REPORTED if measured_values.get("tool_errors") is not None else UNKNOWN,
            source=str(usage.get("source", "provider-usage")) if measured_values else "unavailable",
        ),
        "input_tokens": _field(
            _number_or_unknown(measured_values.get("input_tokens")),
            provenance=REPORTED if measured_values.get("input_tokens") is not None else UNKNOWN,
            source=str(usage.get("source", "provider-usage")) if measured_values else "unavailable",
        ),
        "output_tokens": _field(
            _number_or_unknown(measured_values.get("output_tokens")),
            provenance=REPORTED if measured_values.get("output_tokens") is not None else UNKNOWN,
            source=str(usage.get("source", "provider-usage")) if measured_values else "unavailable",
        ),
        "cached_input_tokens": _field(
            _number_or_unknown(measured_values.get("cached_input_tokens")),
            provenance=REPORTED if measured_values.get("cached_input_tokens") is not None else UNKNOWN,
            source=str(usage.get("source", "provider-usage")) if measured_values else "unavailable",
        ),
        "context_bytes": _field(
            _packet_bytes(packet_path),
            provenance=OBSERVED if _packet_bytes(packet_path) != UNKNOWN else UNKNOWN,
            source="packet-file-size",
            evidence=[packet_path] if packet_path else (),
        ),
        "context_sources": _field(
            _number_or_unknown(context_metrics.get("included")),
            provenance=OBSERVED if context_metrics.get("included") is not None else UNKNOWN,
            source="context-decision",
        ),
        "context_sources_omitted": _field(
            _number_or_unknown(context_metrics.get("omitted")),
            provenance=OBSERVED if context_metrics.get("omitted") is not None else UNKNOWN,
            source="context-decision",
        ),
        "context_cache_hits": _field(
            _number_or_unknown(context_metrics.get("cache_hits")),
            provenance=OBSERVED if context_metrics.get("cache_hits") is not None else UNKNOWN,
            source="context-decision",
        ),
        "context_cache_misses": _field(
            _number_or_unknown(context_metrics.get("cache_misses")),
            provenance=OBSERVED if context_metrics.get("cache_misses") is not None else UNKNOWN,
            source="context-decision",
        ),
        "context_invalidations": _field(
            _number_or_unknown(context_metrics.get("invalidations")),
            provenance=OBSERVED if context_metrics.get("invalidations") is not None else UNKNOWN,
            source="context-decision",
        ),
        "quota_failures": _field(
            quota_failures,
            provenance=OBSERVED,
            source="recorded-failure-records",
            evidence=["only recorded failures are counted; an unrecorded provider failure is unknown"],
        ),
        "worker_exit_status": _field(
            worker_exit,
            provenance=OBSERVED if worker_exit != UNKNOWN else UNKNOWN,
            source="attempt-outcome",
        ),
        "changed_files": _field(
            changed_files,
            provenance=OBSERVED if validation_file else UNKNOWN,
            source="engine-validation-record",
        ),
    }

    # -------------------------------------------------------------- outcome
    review = dict(task.get("review") or {})
    review_value = UNKNOWN
    review_provenance = UNKNOWN
    if review:
        review_value = str(review.get("outcome", UNKNOWN) or UNKNOWN)
        review_provenance = OBSERVED
    elif _review_required(task):
        review_value = "REQUIRED_NOT_RECORDED"
        review_provenance = OBSERVED
    proof = dict(task.get("proof") or {})
    proof_counts = _proof_counts(state, task)
    acceptance = dict(task.get("acceptance") or {})
    if acceptance.get("outcome") in ("accepted", "rejected"):
        acceptance_value = str(acceptance.get("outcome"))
        acceptance_provenance = OBSERVED
        acceptance_evidence = [
            f"recorded human identity: {acceptance.get('identity', '')}",
            str(acceptance.get("reason", "")),
        ]
    else:
        acceptance_value = "PENDING_HUMAN_DECISION"
        acceptance_provenance = OBSERVED
        acceptance_evidence = ["no human acceptance decision is recorded"]
    outcome_row = {
        "validation": _field(
            str(validation.get("status", "") or UNKNOWN),
            provenance=OBSERVED if validation.get("status") else UNKNOWN,
            source="attempt-validation",
        ),
        "review": _field(review_value, provenance=review_provenance, source="task-review"),
        "review_independence": _field(
            str(review.get("independence_level", "") or UNKNOWN),
            provenance=OBSERVED if review.get("independence_level") else UNKNOWN,
            source="task-review",
        ),
        "proof": _field(
            str(proof.get("proof_id", "") or UNKNOWN),
            provenance=OBSERVED if proof else UNKNOWN,
            source="task-proof",
        ),
        "requirements_proven": _field(
            _number_or_unknown(proof_counts.get("proven")),
            provenance=OBSERVED if proof_counts else UNKNOWN,
            source="proof-receipt",
        ),
        "requirements_unresolved": _field(
            _number_or_unknown(proof_counts.get("unresolved")),
            provenance=OBSERVED if proof_counts else UNKNOWN,
            source="proof-receipt",
        ),
        "acceptance": _field(acceptance_value, provenance=acceptance_provenance, source="task-acceptance", evidence=acceptance_evidence),
        "completed": _field(
            str(selected_attempt.get("state", "")) in ("returned", "validated"),
            provenance=OBSERVED,
            source="attempt-outcome",
        ),
        "accepted": _field(
            acceptance_value == "accepted",
            provenance=OBSERVED,
            source="task-acceptance",
        ),
    }

    record = {
        "schema_version": MEASUREMENT_SCHEMA,
        "measurement_id": contracts.new_record_id("msr"),
        "policy": MEASUREMENT_POLICY,
        "run_id": str(state.get("run_id", "")) if isinstance(state, Mapping) else "",
        "task_id": str(task.get("task_id", "")),
        "attempt_id": attempt_id,
        "packet_id": packet_id,
        "intent_family": str(frame.get("family", task.get("intent", "")) or "unknown"),
        "task": {
            "intent_family": _field(
                str(frame.get("family", task.get("intent", "")) or "unknown"),
                provenance=DECLARED if frame.get("family") else (OBSERVED if task.get("intent") else UNKNOWN),
                source="task-plan" if frame.get("family") else "task-record",
            ),
            "complexity": _field(
                str((characterisation.get("difficulty") or {}).get("value", UNKNOWN)),
                provenance=OBSERVED if characterisation.get("difficulty") else UNKNOWN,
                source="task-characterisation",
            ),
            "risk": _field(
                str((characterisation.get("stakes") or {}).get("value", UNKNOWN)),
                provenance=OBSERVED if characterisation.get("stakes") else UNKNOWN,
                source="task-characterisation",
            ),
            "required_capabilities": _field(
                [str(item.get("id", "")) for item in characterisation.get("required_capabilities") or ()],
                provenance=OBSERVED if characterisation.get("required_capabilities") else UNKNOWN,
                source="task-characterisation",
            ),
            "execution_path": _field(
                str(task.get("execution_path", "") or (plan.get("path") or {}).get("path", "") or UNKNOWN),
                provenance=OBSERVED if task.get("execution_path") or plan.get("path") else UNKNOWN,
                source="task-plan",
            ),
            "selected_skills": _field(
                selected_skills,
                provenance=OBSERVED if selected_skills else UNKNOWN,
                source="task-skill-selection",
            ),
        },
        "provider": {
            "adapter": _field(
                adapter_id,
                provenance=OBSERVED if adapter_id != UNKNOWN else UNKNOWN,
                source="attempt-or-execution-record",
            ),
            "provider": _field(provider_value, provenance=identity_provenance, source=identity_source),
            "model": _field(model_value, provenance=identity_provenance, source=identity_source),
            "model_revision": _field(
                model_revision,
                provenance=REPORTED if model_revision != UNKNOWN else UNKNOWN,
                source=str(usage.get("source", "provider-usage")) if model_revision != UNKNOWN else "unavailable",
            ),
            "reasoning_effort": _field(
                effort,
                provenance=DECLARED if effort != UNKNOWN else UNKNOWN,
                source="execution-request",
            ),
            "availability": _field(availability_value, provenance=availability_provenance, source="execution-state"),
            "authentication": _field(
                UNKNOWN,
                provenance=UNKNOWN,
                source="not-observed",
                evidence=["the engine does not authenticate a provider; a caller preflight may declare it"],
            ),
            "requested": _field(
                dict(requested),
                provenance=DECLARED if requested else UNKNOWN,
                source="execution-request",
            ),
            "reported": _field(
                dict(reported),
                provenance=REPORTED if reported else UNKNOWN,
                source="worker-claim",
            ),
            "observed": _field(
                dict(observed),
                provenance=OBSERVED if observed_available else UNKNOWN,
                source=str(observed.get("source", "unavailable")),
            ),
        },
        "execution": execution_row,
        "outcome": outcome_row,
        "revision": {
            "baseline_head": _field(
                str((task.get("baseline") or {}).get("head", "") or UNKNOWN),
                provenance=OBSERVED if (task.get("baseline") or {}).get("head") else UNKNOWN,
                source="task-baseline",
            ),
            "validated_head": _field(
                str((validation.get("validated_revision") or {}).get("head", "") or UNKNOWN),
                provenance=OBSERVED if (validation.get("validated_revision") or {}).get("head") else UNKNOWN,
                source="attempt-validation",
            ),
            "implementation_fingerprint": _field(
                str((validation.get("validated_revision") or {}).get("implementation_fingerprint", "") or UNKNOWN),
                provenance=OBSERVED if (validation.get("validated_revision") or {}).get("implementation_fingerprint") else UNKNOWN,
                source="attempt-validation",
            ),
        },
        "evidence": {
            "attempt_return": str((selected_attempt.get("return") or {}).get("path", "")),
            "validation": str(validation.get("path", "")),
            "validation_sha256": str(validation.get("validation_sha256", "")),
            "review_id": str(review.get("review_id", "")),
            "proof_id": str(proof.get("proof_id", "")),
            "packet": packet_path,
        },
        "unknowns": [],
        "recorded_at": contracts.utc_now(),
    }
    unknowns = []
    for group in ("task", "provider", "execution", "outcome", "revision"):
        for name, row in (record[group] or {}).items():
            if isinstance(row, Mapping) and str(row.get("provenance", "")) == UNKNOWN:
                unknowns.append(f"{group}.{name}")
    record["unknowns"] = sorted(unknowns)
    record["content_digest"] = digest_text(canonical_json({
        key: value for key, value in record.items() if key not in ("measurement_id", "recorded_at", "content_digest")
    }))
    return record


def problems(record: Mapping) -> list[str]:
    problems: list[str] = []
    if not isinstance(record, Mapping):
        return ["measurement record is not an object"]
    if str(record.get("schema_version", "")) != MEASUREMENT_SCHEMA:
        problems.append("measurement record has an unsupported schema version")
    for name in ("measurement_id", "task_id", "attempt_id", "recorded_at"):
        if not str(record.get(name, "")).strip():
            problems.append(f"measurement record has no {name}")
    for group in ("task", "provider", "execution", "outcome", "revision"):
        block = record.get(group)
        if not isinstance(block, Mapping):
            problems.append(f"measurement record has no {group} block")
            continue
        for field, row in block.items():
            if not isinstance(row, Mapping):
                problems.append(f"measurement {group}.{field} is not a field record")
                continue
            if str(row.get("provenance", "")) not in PROVENANCE_LEVELS:
                problems.append(f"measurement {group}.{field} has unsupported provenance")
            if row.get("value") is None:
                problems.append(f"measurement {group}.{field} has no value")
    if str(record.get("outcome", {}).get("accepted", {}).get("value")) == "UNKNOWN":
        problems.append("measurement acceptance cannot be UNKNOWN when the decision state is known")
    digest = str(record.get("content_digest", ""))
    if digest:
        expected = digest_text(canonical_json({
            key: value for key, value in record.items() if key not in ("measurement_id", "recorded_at", "content_digest")
        }))
        if digest != expected:
            problems.append("measurement content digest does not match its contents")
    return problems


def records(state: Mapping) -> list[dict]:
    values = state.get("measurements") if isinstance(state, Mapping) else None
    if not isinstance(values, list):
        return []
    return [
        dict(item) for item in values
        if isinstance(item, Mapping) and str(item.get("freshness", "CURRENT")) == "CURRENT"
    ]


def latest_for_attempt(state: Mapping, task_id: str, attempt_id: str) -> dict | None:
    rows = [
        item for item in records(state)
        if str(item.get("task_id", "")) == str(task_id)
        and str(item.get("attempt_id", "")) == str(attempt_id)
    ]
    return rows[-1] if rows else None


def record(state: dict, measurement: Mapping) -> dict:
    """Append a measurement projection, superseding the earlier row for the attempt.

    Superseding is explicit: the previous row keeps its bytes and gains a
    ``freshness`` marker. A later review or acceptance therefore adds a new
    version instead of rewriting what the attempt looked like before.
    """
    value = dict(measurement)
    problems_list = problems(value)
    if problems_list:
        raise ContractError("measurement record is malformed: " + "; ".join(problems_list))
    task_id = str(value.get("task_id", ""))
    attempt_id = str(value.get("attempt_id", ""))
    existing = [
        item for item in state.setdefault(COLLECTION, [])
        if isinstance(item, Mapping)
        and str(item.get("task_id", "")) == task_id
        and str(item.get("attempt_id", "")) == attempt_id
        and str(item.get("freshness", "CURRENT")) == "CURRENT"
    ]
    for previous in existing:
        previous["freshness"] = "SUPERSEDED"
        previous["superseded_at"] = contracts.utc_now()
        value["supersedes"] = str(previous.get("measurement_id", ""))
    contracts.require_collection_capacity(state, COLLECTION)
    state[COLLECTION].append(value)
    return value


def record_task(state: dict, task: Mapping, *, plan: Mapping | None = None) -> list[dict]:
    """Project every attempt of one task. Used after the lifecycle settles."""
    written = []
    attempts = [item for item in (task or {}).get("attempts") or () if isinstance(item, Mapping)]
    if not attempts:
        return written
    for attempt in attempts:
        measurement = build(state, task, attempt=attempt, plan=plan)
        written.append(record(state, measurement))
    return written


def task_view(state: Mapping, task_id: str) -> dict:
    rows = [item for item in records(state) if str(item.get("task_id", "")) == str(task_id)]
    return {
        "task_id": str(task_id),
        "attempts": rows,
        "accepted": any(
            str((row.get("outcome") or {}).get("accepted", {}).get("value")) == "True"
            for row in rows
        ),
        "unknowns": sorted({name for row in rows for name in row.get("unknowns") or []}),
    }


def summarise(state: Mapping) -> dict:
    """Measured totals across the run. Unknowns are counted, never zero-filled."""
    rows = records(state)
    acceptance = {"accepted": 0, "rejected": 0, "pending": 0}
    validation = {"passed": 0, "failed": 0, "blocked": 0, "unknown": 0}
    totals = {
        "wall_clock_seconds": 0.0,
        "input_tokens": 0,
        "output_tokens": 0,
        "cached_input_tokens": 0,
        "tool_calls": 0,
        "context_bytes": 0,
        "context_sources": 0,
        "context_sources_omitted": 0,
        "context_cache_hits": 0,
        "context_cache_misses": 0,
        "repair_attempts": 0,
        "quota_failures": 0,
    }
    measured_fields: dict[str, int] = {name: 0 for name in totals}
    unknown_by_field: dict[str, int] = {}
    for row in rows:
        outcome = row.get("outcome") or {}
        accepted = str((outcome.get("accepted") or {}).get("value", ""))
        if accepted == "True":
            acceptance["accepted"] += 1
        elif str((outcome.get("acceptance") or {}).get("value", "")) == "rejected":
            acceptance["rejected"] += 1
        else:
            acceptance["pending"] += 1
        state_value = str((outcome.get("validation") or {}).get("value", UNKNOWN))
        validation[state_value if state_value in validation else "unknown"] += 1
        for group in ("task", "provider", "execution", "outcome", "revision"):
            for name, field in (row.get(group) or {}).items():
                if str((field or {}).get("provenance", "")) == UNKNOWN:
                    unknown_by_field[f"{group}.{name}"] = unknown_by_field.get(f"{group}.{name}", 0) + 1
        for name in totals:
            field = (row.get("execution") or {}).get(name)
            if not isinstance(field, Mapping) or str(field.get("provenance", "")) == UNKNOWN:
                continue
            value = field.get("value")
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                continue
            totals[name] += value
            measured_fields[name] += 1
    for name, value in list(totals.items()):
        totals[name] = int(value) if float(value).is_integer() else round(float(value), 3)
    return {
        "schema_version": MEASUREMENT_SCHEMA,
        "policy": MEASUREMENT_POLICY,
        "tasks": len({str(row.get("task_id", "")) for row in rows}),
        "attempts": len(rows),
        "accepted": acceptance["accepted"],
        "rejected": acceptance["rejected"],
        "pending_human_decision": acceptance["pending"],
        "validation": validation,
        "totals": totals,
        "measured_fields": measured_fields,
        "unknown_by_field": dict(sorted(unknown_by_field.items())),
        "coverage": {
            "attempts_with_measured_tokens": measured_fields["input_tokens"],
            "attempts_with_measured_wall_clock": measured_fields["wall_clock_seconds"],
            "attempts_with_measured_context": measured_fields["context_bytes"],
            "attempts_total": len(rows),
        },
        "note": (
            "only measured fields are summed; UNKNOWN is reported in unknown_by_field and is never "
            "converted to zero. A completed attempt is not counted as accepted without the human decision."
        ),
        "recorded_at": contracts.utc_now(),
    }


def describe(state: Mapping) -> str:
    summary = summarise(state)
    return (
        f"measurement: {summary['attempts']} attempt(s) across {summary['tasks']} task(s); "
        f"{summary['accepted']} accepted, {summary['pending_human_decision']} pending human decision; "
        f"{len(summary['unknown_by_field'])} field(s) still unknown"
    )


__all__ = [
    "MEASUREMENT_SCHEMA",
    "MEASUREMENT_POLICY",
    "COLLECTION",
    "MAX_MEASUREMENTS",
    "UNKNOWN",
    "OBSERVED",
    "REPORTED",
    "DECLARED",
    "PROVENANCE_LEVELS",
    "TASK_FAMILIES",
    "OUTCOME_FIELDS",
    "build",
    "problems",
    "records",
    "latest_for_attempt",
    "record",
    "record_task",
    "task_view",
    "summarise",
    "describe",
]
