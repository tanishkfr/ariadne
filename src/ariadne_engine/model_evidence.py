"""Evidence-backed model performance, and the routing advice that follows from it.

What this is, and what it refuses to be
---------------------------------------
Ariadne already routes by *capability*, *role* and *difficulty* deterministically.
2.4B adds one thing: observed performance per provider/model, so a route can be
informed by what actually happened without letting a model, a vendor claim, or a
single lucky run change policy.

Three separations are load-bearing:

* **Declared is not observed.** An adapter declaring ``implementation`` is a
  statement. Only an engine-recorded attempt, validation, review and acceptance
  produce evidence.
* **Observed is not qualified.** A few attempts are an observation, not a model
  ranking. Qualification needs a declared minimum sample and a successful
  validated outcome; benchmark qualification is a separate, stronger source.
* **Advice is not control.** :func:`recommend` returns a decision and the
  evidence behind it. Unless a caller explicitly applies a human-promoted scope,
  the existing routing decision stands. There is no hidden self-modifying policy
  and no background job.

No confidence probability is invented. The numbers here are counts, sample sizes,
durations and usage figures the engine or a provider already measured. Where a
fact was not observed it is ``UNKNOWN``, and ``UNKNOWN`` never becomes a ranking.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Mapping, Sequence

from . import contracts, measurement
from .contracts import ContractError
from .serialization import digest_text, canonical_json

SCHEMA = "ar-24b-model-evidence-1"
POLICY = "model-evidence-1"
COLLECTION = "model_observations"
PROMOTION_COLLECTION = "model_promotions"

UNKNOWN = "UNKNOWN"

QUALIFICATION_LEVELS = (
    "DECLARED",
    "DIRECTLY_OBSERVED",
    "OBSERVED_QUALIFIED",
    "BENCHMARK_QUALIFIED",
    "UNAVAILABLE",
    "STALE",
    "UNKNOWN",
)
FRESHNESS_STATES = ("CURRENT", "STALE", "STALE_IDENTITY", "UNKNOWN")
EXECUTION_ROLES = (
    "bulk-implementation",
    "strong-implementation",
    "senior-reasoning",
    "independent-review",
)
ROLE_CAPABILITIES = {
    "bulk-implementation": ("implementation",),
    "strong-implementation": ("implementation", "implementation-repair"),
    "senior-reasoning": ("implementation", "implementation-repair", "escalation"),
    "independent-review": ("independent-review", "review"),
}
TIER_ORDER = {"light": 1, "standard": 2, "strong": 3, "senior": 4, UNKNOWN: 0}

MIN_OBSERVATION_SAMPLES = 3
"""Below this, a record is a direct observation and never a qualified capability."""

MIN_QUALIFIED_SAMPLES = 5
"""Minimum attempts before a production observation set may be called qualified."""

MIN_QUALIFIED_VALIDATED = 4
"""Of :data:`MIN_QUALIFIED_SAMPLES`, at least this many must validate.

A policy gate, not a probability. It is deliberately conservative: four of five
is not proof that a model is reliable, and the record says so.
"""

MIN_BENCHMARK_SAMPLES = 5
"""Minimum benchmark observations before benchmark qualification."""

MIN_APPLY_SAMPLES = 8
"""Minimum qualified samples before evidence may reorder an adapter selection.

Even then, application requires a recorded human promotion and a degraded or
unavailable baseline. Shadow advice uses the lower threshold because it changes
nothing.
"""

MAX_AGE_DAYS = 30
"""Observations older than this are stale and cannot support a recommendation."""

APPLY_POLICY = "shadow-only"
"""The shipped policy. Evidence is recorded and advised; execution is unchanged."""


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _timestamp(text: str) -> datetime | None:
    value = str(text or "").strip()
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _bool_or_unknown(value) -> bool | str:
    return bool(value) if isinstance(value, bool) else UNKNOWN


def observations(state: Mapping) -> list[dict]:
    values = state.get(COLLECTION) if isinstance(state, Mapping) else None
    if not isinstance(values, list):
        return []
    return [dict(item) for item in values if isinstance(item, Mapping)]


def _measurement_capabilities(row: Mapping) -> list[str]:
    task = dict(row.get("task") or {})
    required = (task.get("required_capabilities") or {}).get("value")
    if isinstance(required, list) and required:
        return sorted({str(item) for item in required if str(item).strip()})
    return ["implementation"]


def observations_from_measurements(state: Mapping) -> list[dict]:
    """Turn each attempt measurement into evidence rows, without inventing any.

    A row needs a provider and model the engine or provider actually observed.
    An unknown identity is still counted as an attempt but is not eligible for a
    capability claim, which is exactly the "model identity uncertain" rule.
    """
    rows: list[dict] = []
    for row in measurement.records(state):
        provider = dict(row.get("provider") or {})
        provider_name = str((provider.get("provider") or {}).get("value", UNKNOWN))
        model_name = str((provider.get("model") or {}).get("value", UNKNOWN))
        model_revision = str((provider.get("model_revision") or {}).get("value", UNKNOWN))
        adapter = str((provider.get("adapter") or {}).get("value", UNKNOWN))
        identity_known = provider_name not in ("", UNKNOWN) and model_name not in ("", UNKNOWN)
        outcome = dict(row.get("outcome") or {})
        execution = dict(row.get("execution") or {})
        # The task record does not store one execution role per attempt, so the
        # role is not inferred from difficulty. An unrecorded role stays UNKNOWN
        # and can inform implementation advice only; it can never satisfy an
        # independent-review boundary.
        role = UNKNOWN
        capabilities = _measurement_capabilities(row)
        value = {
            "schema_version": SCHEMA,
            "observation_id": "mob_" + digest_text(
                canonical_json([row.get("measurement_id", ""), provider_name, model_name, adapter])
            )[:16],
            "source": "task-measurement",
            "source_kind": "PRODUCTION_TASK",
            "provider": provider_name,
            "model": model_name,
            "model_revision": model_revision,
            "adapter": adapter,
            "execution_role": role,
            "capabilities": capabilities,
            "task_family": str((row.get("task") or {}).get("intent_family", {}).get("value", "unknown")),
            "identity_known": identity_known,
            "validated": str((outcome.get("validation") or {}).get("value", UNKNOWN)) == "passed",
            "accepted": (outcome.get("accepted") or {}).get("value") is True,
            "review_passed": str((outcome.get("review") or {}).get("value", UNKNOWN)) == "passed",
            "failed_validation": str((outcome.get("validation") or {}).get("value", UNKNOWN)) in ("failed", "blocked"),
            "repairs": int((execution.get("repair_attempts") or {}).get("value", 0) or 0)
            if isinstance((execution.get("repair_attempts") or {}).get("value"), int) else 0,
            "duration_seconds": (execution.get("wall_clock_seconds") or {}).get("value", UNKNOWN),
            "input_tokens": (execution.get("input_tokens") or {}).get("value", UNKNOWN),
            "output_tokens": (execution.get("output_tokens") or {}).get("value", UNKNOWN),
            "cached_input_tokens": (execution.get("cached_input_tokens") or {}).get("value", UNKNOWN),
            "declared_tier": UNKNOWN,
            "evidence_refs": [
                str((row.get("evidence") or {}).get("validation", "")),
                str((row.get("evidence") or {}).get("review_id", "")),
                str((row.get("evidence") or {}).get("proof_id", "")),
            ],
            "observed_at": str(row.get("recorded_at", "")),
            "note": "" if identity_known else "provider or model identity was not observed",
        }
        value["evidence_refs"] = [item for item in value["evidence_refs"] if item]
        rows.append(value)
    return rows


def observe(
    state: dict,
    *,
    provider: str,
    model: str,
    adapter: str = "",
    capabilities: Sequence[str] = ("implementation",),
    task_family: str = "unknown",
    execution_role: str = "bulk-implementation",
    validated: bool | None = None,
    accepted: bool | None = None,
    review_passed: bool | None = None,
    failed_validation: bool | None = None,
    repairs: int = 0,
    duration_seconds: float | None = None,
    input_tokens: int | None = None,
    output_tokens: int | None = None,
    cached_input_tokens: int | None = None,
    model_revision: str = "",
    declared_tier: str = "",
    source_kind: str = "BENCHMARK",
    evidence_refs: Sequence[str] = (),
    observed_at: str = "",
    identity_known: bool = True,
) -> dict:
    """Record one explicit observation, usually from a benchmark run.

    The caller must have measured it. A worker's claim is not accepted here any
    more than it is in :mod:`ariadne_engine.execution`.
    """
    if str(source_kind) not in ("BENCHMARK", "PRODUCTION_TASK", "ADAPTER_PROBE", "HUMAN_REVIEW"):
        raise ContractError(f"unsupported observation source kind: {source_kind!r}")
    if not str(provider).strip() or not str(model).strip():
        raise ContractError("a model observation needs a provider and a model")
    if str(execution_role) not in EXECUTION_ROLES:
        raise ContractError(f"unsupported execution role: {execution_role!r}")
    if str(declared_tier or UNKNOWN) not in TIER_ORDER:
        raise ContractError(f"unsupported declared tier: {declared_tier!r}")
    row = {
        "schema_version": SCHEMA,
        "observation_id": contracts.new_record_id("mob"),
        "source": "explicit-observation",
        "source_kind": str(source_kind),
        "provider": str(provider).strip(),
        "model": str(model).strip(),
        "model_revision": str(model_revision or UNKNOWN),
        "adapter": str(adapter or UNKNOWN),
        "execution_role": str(execution_role),
        "capabilities": sorted({str(item) for item in capabilities if str(item).strip()}) or ["implementation"],
        "task_family": str(task_family or "unknown"),
        "identity_known": bool(identity_known),
        "validated": _bool_or_unknown(validated),
        "accepted": _bool_or_unknown(accepted),
        "review_passed": _bool_or_unknown(review_passed),
        "failed_validation": _bool_or_unknown(failed_validation),
        "repairs": max(0, int(repairs or 0)),
        "duration_seconds": UNKNOWN if duration_seconds is None else max(0.0, float(duration_seconds)),
        "input_tokens": UNKNOWN if input_tokens is None else max(0, int(input_tokens)),
        "output_tokens": UNKNOWN if output_tokens is None else max(0, int(output_tokens)),
        "cached_input_tokens": UNKNOWN if cached_input_tokens is None else max(0, int(cached_input_tokens)),
        "declared_tier": str(declared_tier or UNKNOWN),
        "evidence_refs": [str(item) for item in evidence_refs if str(item).strip()],
        "observed_at": str(observed_at or contracts.utc_now()),
        "note": "",
    }
    contracts.require_collection_capacity(state, COLLECTION)
    state.setdefault(COLLECTION, []).append(row)
    return row


def observation_problems(row: Mapping) -> list[str]:
    problems: list[str] = []
    if not isinstance(row, Mapping):
        return ["model observation is not an object"]
    if str(row.get("schema_version", "")) != SCHEMA:
        problems.append("model observation has an unsupported schema version")
    for name in ("observation_id", "provider", "model", "observed_at"):
        if not str(row.get(name, "")).strip():
            problems.append(f"model observation has no {name}")
    if str(row.get("execution_role", "")) not in EXECUTION_ROLES:
        problems.append("model observation has an unsupported execution role")
    if not isinstance(row.get("capabilities"), (list, tuple)) or not row.get("capabilities"):
        problems.append("model observation declares no capability")
    return problems


def _capability_rows(rows: Sequence[Mapping], *, as_of: datetime) -> list[dict]:
    """Aggregate observations into one versioned record per identity/capability/family."""
    grouped: dict[tuple, list[dict]] = {}
    for raw in rows:
        row = dict(raw)
        if observation_problems(row):
            continue
        capabilities = [str(item) for item in row.get("capabilities") or ()]
        if not capabilities:
            continue
        for capability in capabilities:
            key = (
                str(row.get("provider", UNKNOWN)),
                str(row.get("model", UNKNOWN)),
                str(row.get("model_revision", UNKNOWN)),
                str(row.get("adapter", UNKNOWN)),
                str(row.get("task_family", "unknown")),
                capability,
            )
            grouped.setdefault(key, []).append(row)

    # An identity whose revision moved makes older observations stale. The
    # newest revision is determined by observation time, not by a string sort:
    # a version label need not be ordered.
    latest_revision: dict[tuple[str, str, str], tuple[datetime, str]] = {}
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        identity = (str(row.get("provider", "")), str(row.get("model", "")), str(row.get("adapter", "")))
        when = _timestamp(str(row.get("observed_at", ""))) or datetime.min.replace(tzinfo=timezone.utc)
        revision = str(row.get("model_revision", UNKNOWN))
        previous = latest_revision.get(identity)
        if previous is None or when > previous[0]:
            latest_revision[identity] = (when, revision)

    records: list[dict] = []
    for key, group in sorted(grouped.items()):
        provider, model, revision, adapter, family, capability = key
        group.sort(key=lambda item: str(item.get("observed_at", "")))
        first = group[0]
        last = group[-1]
        observed_times = [
            _timestamp(str(item.get("observed_at", ""))) for item in group
        ]
        observed_times = [item for item in observed_times if item is not None]
        latest_at = max(observed_times) if observed_times else None
        age_days = (as_of - latest_at).total_seconds() / 86400 if latest_at else None
        current = age_days is not None and age_days <= MAX_AGE_DAYS
        expected_revision = latest_revision.get((provider, model, adapter), (None, UNKNOWN))[1]
        revision_current = revision == expected_revision or revision == UNKNOWN or expected_revision == UNKNOWN
        identity_known = all(bool(item.get("identity_known", True)) for item in group)
        validated = [item for item in group if item.get("validated") is True]
        accepted = [item for item in group if item.get("accepted") is True]
        failed = [item for item in group if item.get("failed_validation") is True]
        reviews = [item for item in group if item.get("review_passed") is True]
        benchmark_samples = sum(1 for item in group if str(item.get("source_kind")) == "BENCHMARK")
        durations = [
            float(item["duration_seconds"]) for item in group
            if isinstance(item.get("duration_seconds"), (int, float))
            and not isinstance(item.get("duration_seconds"), bool)
        ]
        input_tokens = [
            int(item["input_tokens"]) for item in group
            if isinstance(item.get("input_tokens"), int) and not isinstance(item.get("input_tokens"), bool)
        ]
        output_tokens = [
            int(item["output_tokens"]) for item in group
            if isinstance(item.get("output_tokens"), int) and not isinstance(item.get("output_tokens"), bool)
        ]
        cached_tokens = [
            int(item["cached_input_tokens"]) for item in group
            if isinstance(item.get("cached_input_tokens"), int) and not isinstance(item.get("cached_input_tokens"), bool)
        ]
        if not identity_known:
            level = "UNKNOWN"
        elif not current or not revision_current:
            level = "STALE"
        elif len(group) < MIN_OBSERVATION_SAMPLES:
            level = "DIRECTLY_OBSERVED"
        elif benchmark_samples >= MIN_BENCHMARK_SAMPLES and len(validated) >= MIN_QUALIFIED_VALIDATED:
            level = "BENCHMARK_QUALIFIED"
        elif len(group) >= MIN_QUALIFIED_SAMPLES and len(validated) >= MIN_QUALIFIED_VALIDATED:
            level = "OBSERVED_QUALIFIED"
        else:
            level = "DIRECTLY_OBSERVED"
        records.append({
            "schema_version": SCHEMA,
            "registry_record_id": "mreg_" + digest_text(canonical_json(key))[:16],
            "provider": provider,
            "model": model,
            "model_revision": revision,
            "adapter": adapter,
            "task_family": family,
            "capability": capability,
            "execution_role": str(first.get("execution_role", "bulk-implementation")),
            "declared_tier": str(first.get("declared_tier", UNKNOWN)),
            "qualification": level,
            "freshness": (
                "CURRENT" if current and revision_current else
                "STALE_IDENTITY" if not revision_current else
                "STALE" if not current else
                "UNKNOWN"
            ),
            "sample_size": len(group),
            "benchmark_samples": benchmark_samples,
            "validated": len(validated),
            "accepted": len(accepted),
            "review_passed": len(reviews),
            "failed_validation": len(failed),
            "repairs": sum(int(item.get("repairs", 0) or 0) for item in group),
            "measurement_period": {
                "first": str(first.get("observed_at", "")),
                "last": str(last.get("observed_at", "")),
                "age_days": round(age_days, 3) if age_days is not None else UNKNOWN,
            },
            "measured": {
                "attempts": len(group),
                "duration_seconds_total": round(sum(durations), 3) if durations else UNKNOWN,
                "duration_seconds_mean": round(sum(durations) / len(durations), 3) if durations else UNKNOWN,
                "input_tokens_total": sum(input_tokens) if input_tokens else UNKNOWN,
                "output_tokens_total": sum(output_tokens) if output_tokens else UNKNOWN,
                "cached_input_tokens_total": sum(cached_tokens) if cached_tokens else UNKNOWN,
            },
            "evidence_refs": sorted({
                str(ref) for item in group for ref in item.get("evidence_refs") or () if str(ref).strip()
            }),
            "limitations": [
                "sample size is small" if len(group) < MIN_QUALIFIED_SAMPLES else "",
                "no formal benchmark observation" if benchmark_samples == 0 else "",
                "identity was not observed for every attempt" if not identity_known else "",
                "observations are older than the freshness window" if not current else "",
                "a newer model revision exists for this identity" if not revision_current else "",
            ],
            "recorded_at": contracts.utc_now(),
        })
    for record in records:
        record["limitations"] = [item for item in record["limitations"] if item]
        record["registry_digest"] = _registry_digest(record)
    return records


def declared_records(adapters: Mapping | None) -> list[dict]:
    """Declared capabilities, kept visibly separate from observations."""
    rows: list[dict] = []
    for adapter_id, adapter in sorted(dict(adapters or {}).items()):
        if not isinstance(adapter, Mapping):
            continue
        for capability in adapter.get("capabilities") or ():
            rows.append({
                "schema_version": SCHEMA,
                "registry_record_id": "dec_" + digest_text(canonical_json([adapter_id, str(capability)]))[:16],
                "provider": UNKNOWN,
                "model": UNKNOWN,
                "adapter": str(adapter_id),
                "capability": str(capability),
                "task_family": "any",
                "qualification": "DECLARED",
                "freshness": "UNKNOWN",
                "sample_size": 0,
                "source": "adapter-declaration",
                "note": "a declaration is not an observation and cannot satisfy a qualified requirement",
            })
    return rows


def registry(
    state: Mapping,
    *,
    adapters: Mapping | None = None,
    as_of: str = "",
) -> dict:
    """The operational registry: observed records plus declared capabilities."""
    as_of_dt = _timestamp(as_of) or _now()
    production = observations_from_measurements(state)
    explicit = observations(state)
    records = _capability_rows([*production, *explicit], as_of=as_of_dt)
    return {
        "schema_version": SCHEMA,
        "policy": POLICY,
        "apply_policy": APPLY_POLICY,
        "as_of": as_of_dt.isoformat(),
        "records": records,
        "declared": declared_records(adapters),
        "counts": {
            "observations_derived": len(production),
            "observations_explicit": len(explicit),
            "records": len(records),
            "qualified": sum(1 for row in records if row["qualification"] in ("OBSERVED_QUALIFIED", "BENCHMARK_QUALIFIED")),
            "stale": sum(1 for row in records if row["freshness"] != "CURRENT"),
        },
        "minimums": {
            "observation": MIN_OBSERVATION_SAMPLES,
            "qualified": MIN_QUALIFIED_SAMPLES,
            "qualified_validated": MIN_QUALIFIED_VALIDATED,
            "benchmark": MIN_BENCHMARK_SAMPLES,
            "apply": MIN_APPLY_SAMPLES,
            "max_age_days": MAX_AGE_DAYS,
        },
        "unknowns": [
            "provider authentication state",
            "provider quota",
            "model revision when the provider did not report it",
            "provider cost is not inferred from tokens",
            "token counts exist only where a provider reported them",
        ],
        "note": (
            "declared capabilities are listed separately and never promoted by declaration. "
            "A qualified record is a policy gate over measured counts, not a probability."
        ),
    }


def _registry_digest(record: Mapping) -> str:
    """A stable digest over the record's evidence, not the clock.

    ``measurement_period.age_days`` and ``recorded_at`` change simply because the
    registry was read again. Including them would invalidate a promotion without
    any evidence changing, so they are excluded. Qualification, freshness,
    counts and evidence references remain covered.
    """
    payload = {
        key: value for key, value in record.items()
        if key not in ("recorded_at", "registry_digest")
    }
    period = dict(payload.get("measurement_period") or {})
    period.pop("age_days", None)
    payload["measurement_period"] = period
    return digest_text(canonical_json(payload))


def _fresh(record: Mapping) -> bool:
    return str(record.get("freshness", "")) == "CURRENT"


def _candidate_healthy(record: Mapping) -> bool:
    """Whether an alternative's own outcomes show a positive validated margin.

    A record may meet the qualification gate (four validated of five) while a
    later run set has as many failures as passes. Such a candidate is not a safe
    alternative merely because it is on the right side of the old threshold.
    """
    validated = int(record.get("validated", 0) or 0)
    failed = int(record.get("failed_validation", 0) or 0)
    return validated > failed


def _qualified(record: Mapping, *, samples: int) -> bool:
    return (
        str(record.get("qualification", "")) in ("OBSERVED_QUALIFIED", "BENCHMARK_QUALIFIED")
        and int(record.get("sample_size", 0) or 0) >= samples
        and _fresh(record)
    )


def _role_ok(row: Mapping, role: str, capability: str) -> bool:
    """Whether an observation may inform this role.

    A production measurement without a recorded role may inform implementation
    advice; it may never inform independent review, because the review boundary
    is an independence fact and not an inference.
    """
    observed_role = str(row.get("execution_role", UNKNOWN))
    if capability not in ROLE_CAPABILITIES.get(role, ()):
        return False
    if role == "independent-review":
        return observed_role == "independent-review"
    return observed_role in ("", UNKNOWN, role)


def promotions(state: Mapping) -> list[dict]:
    values = state.get(PROMOTION_COLLECTION) if isinstance(state, Mapping) else None
    if not isinstance(values, list):
        return []
    return [dict(item) for item in values if isinstance(item, Mapping)]


def promoted_scope(
    state: Mapping,
    *,
    provider: str,
    model: str,
    capability: str,
    task_family: str,
    current_records: Sequence[Mapping] | None = None,
) -> dict | None:
    """An active, still-current promotion for exactly this identity and scope.

    The promotion carries the registry digest it was granted against. If a later
    observation changes that record's evidence, freshness or qualification, the
    digest no longer matches and the promotion stops applying. The apply path
    also re-checks qualification and samples, so this is a second, independent
    check rather than the only one.
    """
    current_records = (
        list(current_records) if current_records is not None
        else registry(state)["records"]
    )
    for row in reversed(promotions(state)):
        if not row.get("active", True):
            continue
        if str(row.get("provider", "")) != str(provider):
            continue
        if str(row.get("model", "")) != str(model):
            continue
        if str(row.get("capability", "")) != str(capability):
            continue
        family = str(row.get("task_family", "any"))
        if family not in ("any", str(task_family)):
            continue
        expected = str(row.get("record_digest", "") or "")
        if expected:
            current = next(
                (
                    record for record in current_records
                    if str(record.get("provider", "")) == str(provider)
                    and str(record.get("model", "")) == str(model)
                    and str(record.get("capability", "")) == str(capability)
                    and str(record.get("task_family", "any")) in ("any", str(task_family))
                ),
                None,
            )
            if current is None or str(current.get("registry_digest", "")) != expected:
                continue
        return row
    return None


def promote(
    state: dict,
    *,
    record: Mapping,
    identity: str,
    reason: str,
    task_family: str = "",
) -> dict:
    """Record a human's narrow promotion of measured evidence. Never auto-apply.

    The promotion is bookkeeping. It can make a recommendation eligible for
    application only when the record is benchmark-qualified, current and meets
    the apply sample bound; it cannot alter the trusted registry, bypass a
    review, or authorize a provider the caller did not already permit.
    """
    if not str(identity or "").strip():
        raise ContractError("a model-routing promotion needs the human identity that decided it")
    if str(record.get("qualification", "")) != "BENCHMARK_QUALIFIED":
        raise ContractError(
            "only a benchmark-qualified, current record can be promoted; "
            f"this record is {record.get('qualification')!r}"
        )
    if str(record.get("freshness", "")) != "CURRENT":
        raise ContractError("a stale performance record cannot be promoted")
    if int(record.get("sample_size", 0) or 0) < MIN_APPLY_SAMPLES:
        raise ContractError(
            f"a promotion needs at least {MIN_APPLY_SAMPLES} benchmark samples; "
            f"this record has {record.get('sample_size', 0)}"
        )
    row = {
        "schema_version": SCHEMA,
        "promotion_id": contracts.new_record_id("mpr"),
        "provider": str(record.get("provider", "")),
        "model": str(record.get("model", "")),
        "model_revision": str(record.get("model_revision", "")),
        "capability": str(record.get("capability", "")),
        "task_family": str(task_family or record.get("task_family", "any") or "any"),
        "identity": str(identity).strip(),
        "reason": str(reason),
        "record_digest": str(record.get("registry_digest", "")),
        "sample_size": int(record.get("sample_size", 0) or 0),
        "scope": "advisory-only",
        "active": True,
        "recorded_at": contracts.utc_now(),
    }
    contracts.require_collection_capacity(state, PROMOTION_COLLECTION)
    state.setdefault(PROMOTION_COLLECTION, []).append(row)
    return row


def _record_health(record: Mapping | None) -> str:
    if record is None:
        return "NO_EVIDENCE"
    if str(record.get("freshness", "")) != "CURRENT":
        return "STALE"
    if str(record.get("qualification", "")) == "UNAVAILABLE":
        return "UNAVAILABLE"
    if int(record.get("failed_validation", 0) or 0) >= 2:
        return "DEGRADED"
    if str(record.get("qualification", "")) in ("OBSERVED_QUALIFIED", "BENCHMARK_QUALIFIED"):
        return "QUALIFIED"
    return "INSUFFICIENT_EVIDENCE"


def recommend(
    state: Mapping,
    *,
    role: str,
    capability: str,
    task_family: str = "any",
    baseline_provider: str = "",
    baseline_model: str = "",
    baseline_adapter: str = "",
    independent_of: Sequence[str] = (),
    complexity: str = "UNKNOWN",
    stakes: str = "UNKNOWN",
    failure_count: int = 0,
    available_adapters: Sequence[str] | None = None,
    authorized_adapters: Sequence[str] | None = None,
    as_of: str = "",
) -> dict:
    """Advisory route recommendation with its evidence and limitations.

    The existing deterministic route stays the decision. This function answers a
    narrower question: *given the observations on record, is there a measured
    reason to change the adapter/model for this role and capability?* It returns
    ``KEEP_BASELINE`` when the evidence is weak, stale, or simply unchanged.
    """
    if str(role) not in EXECUTION_ROLES:
        raise ContractError(f"unsupported execution role: {role!r}")
    if capability not in ROLE_CAPABILITIES[role] and role != "independent-review":
        raise ContractError(f"role {role!r} does not carry capability {capability!r}")
    view = registry(state, as_of=as_of)
    if authorized_adapters is not None and not any(str(item).strip() for item in authorized_adapters):
        return {
            "schema_version": SCHEMA,
            "policy": POLICY,
            "controls_execution": False,
            "role": str(role),
            "capability": str(capability),
            "task_family": str(task_family),
            "decision": "NO_AUTHORIZED_PROVIDER",
            "reason": "the caller supplied no authorized provider for this route; no candidate can be selected",
            "baseline_health": "NO_EVIDENCE",
            "selected": {},
            "baseline": {},
            "alternatives_considered": [],
            "fallbacks": [],
            "evidence": {"records_considered": 0, "qualified_records": 0},
            "limitations": ["authorization is a caller-owned boundary; evidence cannot widen it"],
            "unknowns": ["provider quota", "provider authentication"],
            "recorded_at": contracts.utc_now(),
        }
    rows = [
        row for row in view["records"]
        if str(row.get("capability", "")) == str(capability)
        and _role_ok(row, role, capability)
        and (str(row.get("task_family", "any")) in ("any", str(task_family)))
    ]
    if available_adapters is not None:
        allowed = {str(item) for item in available_adapters}
        rows = [row for row in rows if str(row.get("adapter", "")) in allowed or str(row.get("adapter", "")) == UNKNOWN]
    if authorized_adapters is not None:
        allowed = {str(item) for item in authorized_adapters}
        rows = [row for row in rows if str(row.get("adapter", "")) in allowed or str(row.get("adapter", "")) == UNKNOWN]
    independent = {str(item) for item in independent_of if str(item).strip()}
    if role == "independent-review":
        rows = [
            row for row in rows
            if str(row.get("adapter", "")) not in independent
            and str(row.get("model", "")) not in independent
            and str(row.get("provider", "")) not in independent
        ]
    baseline = None
    if baseline_adapter or baseline_model:
        baseline = next(
            (
                row for row in rows
                if (baseline_adapter and str(row.get("adapter", "")) == str(baseline_adapter))
                or (
                    baseline_model
                    and str(row.get("model", "")) == str(baseline_model)
                    and (not baseline_provider or str(row.get("provider", "")) == str(baseline_provider))
                )
            ),
            None,
        )
    alternatives = [
        row for row in rows
        if row is not baseline
        and _fresh(row)
        and str(row.get("qualification", "")) in ("OBSERVED_QUALIFIED", "BENCHMARK_QUALIFIED")
        and int(row.get("sample_size", 0) or 0) >= MIN_QUALIFIED_SAMPLES
        and _candidate_healthy(row)
    ]
    alternatives.sort(
        key=lambda row: (
            0 if row["qualification"] == "BENCHMARK_QUALIFIED" else 1,
            -int(row.get("validated", 0) or 0),
            -int(row.get("sample_size", 0) or 0),
            str(row.get("adapter", "")),
        )
    )
    health = _record_health(baseline)
    decision = "KEEP_BASELINE"
    reason = "the existing deterministic route is retained"
    chosen: dict = {}
    unknowns = [
        "provider authentication state",
        "provider quota",
        "reasoning-effort performance (effort is recorded, not benchmarked separately)",
    ]
    if not rows:
        reason = "no observations exist for this role, capability and task family"
    elif health == "NO_EVIDENCE":
        reason = (
            f"no observed record exists for the baseline {baseline_adapter or baseline_model or 'route'}; "
            "a declared capability is not evidence"
        )
    elif health == "STALE":
        reason = "the baseline's observations are stale or describe an older model revision"
    elif health == "DEGRADED" or int(failure_count) >= 2:
        reason = "the baseline has repeated validation failures for this task"
    elif health == "QUALIFIED":
        reason = "the baseline has qualified, current evidence and no repeated failure is recorded"
    # A qualified alternative may replace a degraded or unavailable baseline, but
    # never a healthy, qualified one. A lighter tier may be preferred for a
    # low-stakes task only when the caller declared its tier; nothing is inferred
    # from a model name.
    eligible = [row for row in alternatives if row["qualification"] in ("OBSERVED_QUALIFIED", "BENCHMARK_QUALIFIED")]
    if eligible and (health in ("NO_EVIDENCE", "STALE", "DEGRADED") or int(failure_count) >= 2 or health == "UNAVAILABLE"):
        chosen = eligible[0]
        decision = "RECOMMEND_ALTERNATIVE"
        reason = (
            f"the baseline is {health.lower().replace('_', ' ')}; "
            f"{chosen.get('adapter') or chosen.get('model')} has {chosen.get('sample_size')} observation(s), "
            f"{chosen.get('validated')} validated"
        )
    elif eligible and str(stakes) in ("LOW", "MEDIUM") and str(complexity) != "HIGH":
        # Downgrade only when the caller supplied a declared tier and the
        # candidate is materially lighter. Same-tier evidence is not a reason to
        # shuffle a working route.
        baseline_tier = TIER_ORDER.get(str((baseline or {}).get("declared_tier", UNKNOWN)), 0)
        lighter = [
            row for row in eligible
            if baseline_tier and TIER_ORDER.get(str(row.get("declared_tier", UNKNOWN)), 0)
            and TIER_ORDER[str(row.get("declared_tier"))] < baseline_tier
        ]
        if lighter:
            chosen = lighter[0]
            decision = "RECOMMEND_LIGHTER"
            reason = (
                "a lighter declared tier has qualified evidence for a low-stakes, non-high-complexity task"
            )
        else:
            reason = "qualified alternatives exist, but none is a justified lighter or repaired route"
    fallbacks = [
        {
            "adapter": str(row.get("adapter", "")),
            "provider": str(row.get("provider", "")),
            "model": str(row.get("model", "")),
            "qualification": str(row.get("qualification", "")),
            "freshness": str(row.get("freshness", "")),
            "sample_size": int(row.get("sample_size", 0) or 0),
        }
        for row in eligible if row is not chosen
    ]
    if not chosen and baseline:
        chosen = {
            "adapter": str(baseline.get("adapter", "")),
            "provider": str(baseline.get("provider", "")),
            "model": str(baseline.get("model", "")),
            "qualification": str(baseline.get("qualification", "")),
            "freshness": str(baseline.get("freshness", "")),
            "sample_size": int(baseline.get("sample_size", 0) or 0),
        }
    return {
        "schema_version": SCHEMA,
        "policy": POLICY,
        "controls_execution": False,
        "role": str(role),
        "capability": str(capability),
        "task_family": str(task_family),
        "decision": decision,
        "reason": reason,
        "baseline_health": health,
        "selected": chosen,
        "baseline": {
            "adapter": str(baseline_adapter),
            "provider": str(baseline_provider),
            "model": str(baseline_model),
            "record": dict(baseline or {}) if baseline else {},
        },
        "alternatives_considered": [
            {
                "adapter": str(row.get("adapter", "")),
                "provider": str(row.get("provider", "")),
                "model": str(row.get("model", "")),
                "qualification": str(row.get("qualification", "")),
                "freshness": str(row.get("freshness", "")),
                "sample_size": int(row.get("sample_size", 0) or 0),
                "validated": int(row.get("validated", 0) or 0),
                "failed_validation": int(row.get("failed_validation", 0) or 0),
            }
            for row in rows if row is not baseline
        ],
        "fallbacks": fallbacks,
        "evidence": {
            "records_considered": len(rows),
            "qualified_records": len(eligible),
            "minimum_samples": MIN_QUALIFIED_SAMPLES,
            "minimum_apply_samples": MIN_APPLY_SAMPLES,
            "max_age_days": MAX_AGE_DAYS,
            "source": "engine measurements plus explicitly recorded benchmark observations",
        },
        "limitations": [
            "a sample count is not a probability",
            "a qualified record describes the measured tasks, not every task",
            "provider quota and authentication were not measured here",
            "declared tiers are caller-supplied, never inferred from a model name",
        ],
        "unknowns": unknowns,
        "recorded_at": contracts.utc_now(),
    }


def adapter_ranking(
    state: Mapping,
    *,
    adapters: Mapping,
    required: Sequence[str],
    task_family: str,
    role: str = "bulk-implementation",
    baseline_adapter: str = "",
    failure_count: int = 0,
    independent_of: Sequence[str] = (),
    require_promotion: bool = True,
    as_of: str = "",
) -> dict:
    """A bounded adapter order for the existing selector, or an explicit no-op.

    Application is deliberately narrow: the baseline must be degraded and the
    alternative must be benchmark-qualified, current, have at least
    :data:`MIN_APPLY_SAMPLES` samples, carry the required capability and have a
    recorded human promotion for this capability and family. Anything less
    returns ``apply: False`` and the existing preference order is used.
    """
    capability = str(next(iter(required), "implementation"))
    if capability not in ROLE_CAPABILITIES[role]:
        return {
            "schema_version": SCHEMA,
            "apply": False,
            "ranking": [],
            "reason": f"capability {capability!r} is not carried by role {role!r}",
            "unknowns": ["no supported capability for this role"],
        }
    view = registry(state, adapters=adapters, as_of=as_of)
    excluded = {str(item) for item in independent_of}
    candidates = [
        row for row in view["records"]
        if str(row.get("capability", "")) == capability
        and str(row.get("adapter", "")) in dict(adapters)
        and _fresh(row)
        and int(row.get("sample_size", 0) or 0) >= MIN_APPLY_SAMPLES
        and row["qualification"] == "BENCHMARK_QUALIFIED"
        and _candidate_healthy(row)
        and str(row.get("adapter", "")) not in excluded
        and str(row.get("model", "")) not in excluded
        and str(row.get("provider", "")) not in excluded
        and (
            not require_promotion
            or promoted_scope(
                state,
                provider=str(row.get("provider", "")),
                model=str(row.get("model", "")),
                capability=capability,
                task_family=task_family,
                current_records=view["records"],
            ) is not None
        )
    ]
    baseline = next((row for row in view["records"] if str(row.get("adapter", "")) == str(baseline_adapter)), None)
    baseline_health = _record_health(baseline)
    if not candidates:
        return {
            "schema_version": SCHEMA,
            "apply": False,
            "ranking": [],
            "reason": "no benchmark-qualified adapter has the apply sample bound",
            "baseline_health": baseline_health,
            "unknowns": ["provider quota", "provider authentication"],
        }
    if baseline_health == "QUALIFIED" and int(failure_count) < 2:
        return {
            "schema_version": SCHEMA,
            "apply": False,
            "ranking": [],
            "reason": "the baseline is qualified and has no repeated failure; no change is justified",
            "baseline_health": baseline_health,
            "unknowns": [],
        }
    ranking = [str(row.get("adapter", "")) for row in candidates]
    if baseline_adapter and baseline_adapter not in ranking:
        ranking.append(str(baseline_adapter))
    return {
        "schema_version": SCHEMA,
        "apply": True,
        "ranking": ranking,
        "reason": (
            f"the baseline is {baseline_health.lower().replace('_', ' ')} and "
            f"{len(candidates)} adapter(s) meet the benchmark sample bound"
        ),
        "baseline_health": baseline_health,
        "records": candidates,
        "unknowns": ["provider quota", "provider authentication"],
    }


def explain(decision: Mapping) -> str:
    """A compact, auditable routing block. No invented confidence number."""
    selected = dict(decision.get("selected") or {})
    lines = [
        "ROUTING EVIDENCE (advisory; the deterministic route remains authoritative)",
        f"- Role: {decision.get('role')}",
        f"- Capability: {decision.get('capability')}",
        f"- Decision: {decision.get('decision')}",
        f"- Selected: {selected.get('adapter') or selected.get('model') or 'none'}",
        f"- Why: {decision.get('reason')}",
        f"- Evidence: {decision.get('evidence', {}).get('records_considered', 0)} record(s) considered, "
        f"{decision.get('evidence', {}).get('qualified_records', 0)} qualified",
        f"- Baseline health: {decision.get('baseline_health')}",
    ]
    alternatives = decision.get("alternatives_considered") or []
    if alternatives:
        lines.append("- Alternatives: " + ", ".join(
            f"{item.get('adapter') or item.get('model')} ({item.get('qualification')}, n={item.get('sample_size')})"
            for item in alternatives[:5]
        ))
    if decision.get("limitations"):
        lines.append("- Limitations: " + "; ".join(str(item) for item in decision["limitations"]))
    if decision.get("unknowns"):
        lines.append("- Unknowns: " + "; ".join(str(item) for item in decision["unknowns"]))
    if decision.get("fallbacks"):
        lines.append("- Fallback conditions: " + ", ".join(
            str(item.get("adapter") or item.get("model")) for item in decision["fallbacks"]
        ))
    return "\n".join(lines)


def describe(state: Mapping, *, adapters: Mapping | None = None) -> str:
    view = registry(state, adapters=adapters)
    counts = view["counts"]
    return (
        f"model evidence: {counts['records']} observed record(s), {counts['qualified']} qualified, "
        f"{counts['stale']} stale; {counts['observations_derived']} derived from measurements, "
        f"{counts['observations_explicit']} explicit"
    )


__all__ = [
    "SCHEMA",
    "POLICY",
    "COLLECTION",
    "PROMOTION_COLLECTION",
    "UNKNOWN",
    "QUALIFICATION_LEVELS",
    "FRESHNESS_STATES",
    "EXECUTION_ROLES",
    "ROLE_CAPABILITIES",
    "TIER_ORDER",
    "MIN_OBSERVATION_SAMPLES",
    "MIN_QUALIFIED_SAMPLES",
    "MIN_QUALIFIED_VALIDATED",
    "MIN_BENCHMARK_SAMPLES",
    "MIN_APPLY_SAMPLES",
    "MAX_AGE_DAYS",
    "APPLY_POLICY",
    "observations",
    "observations_from_measurements",
    "observe",
    "observation_problems",
    "declared_records",
    "registry",
    "promotions",
    "promoted_scope",
    "promote",
    "recommend",
    "adapter_ranking",
    "explain",
    "describe",
]
