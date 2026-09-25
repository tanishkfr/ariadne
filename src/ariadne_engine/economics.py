"""Task-level harness economics: spend only what the task earns (AR-204 T5-T11).

What this module is
-------------------
AR-203 recorded usage *on an execution*. AR-204 measures the **task**: every
execution, decision batch and repair that was spent on it, and the one number the
milestone exists for — cost per verified completed task.

The rules this module enforces on itself:

* **Measured stays measured.** A usage field that no provider reported is absent,
  not zero. ``UNKNOWN`` never renders as ``0``.
* **Derived money is labelled.** A monetary figure computed from tokens and a
  *registered price profile* is returned with ``derived: true``, the profile id
  and the profile's declared source. Without a profile, monetary cost is
  ``UNKNOWN`` — no price is invented and no ephemeral provider price is baked
  into the engine.
* **Failed attempts count.** A failed or abandoned execution is part of what the
  task cost; excluding it would make a retry look free.
* **Code before judgment.** Everything here is arithmetic over records the engine
  already wrote. No provider is consulted, and no field is guessed.

Price profiles are *data*, not architecture: they are registered by a caller (or
loaded from a JSON file), versioned by their canonical digest, and never consulted
by routing or authorization. Cost can inform a human decision; it cannot grant a
capability or satisfy evidence.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from . import contracts, execution
from .contracts import ContractError
from .serialization import canonical_json, deep_sorted, digest_text, stable_digest

# --------------------------------------------------------------- source buckets

SOURCE_BUCKETS = (
    "SYSTEM",
    "TOOL_SCHEMAS",
    "TASK",
    "PROJECT_FACTS",
    "PROJECT_SOURCE",
    "RETRIEVED_SOURCE",
    "POLICY",
    "SKILLS",
    "DESIGN_CONTEXT",
    "EVIDENCE",
    "HISTORY",
    "SUMMARY",
    "PREVIOUS_ATTEMPTS",
    "DECISION_CONTEXT",
    "OTHER",
)
"""Every rendered request is decomposable into these source buckets (AR-204 T8)."""

AR203_BUCKET_MAP = {
    "static_system": "SYSTEM",
    "tool_schemas": "TOOL_SCHEMAS",
    "project_context": "PROJECT_FACTS",
    "retrieved_source": "RETRIEVED_SOURCE",
    "evidence": "EVIDENCE",
    "history": "HISTORY",
    "summaries": "SUMMARY",
}
"""The AR-203 composition buckets map onto the AR-204 vocabulary without renaming."""

SOURCE_ORIGINS = (
    "engine",
    "project",
    "policy",
    "retrieved",
    "task",
    "worker",
    "derived",
    "unknown",
)

CACHEABILITY = ("CACHEABLE", "VOLATILE", "UNKNOWN")

CONTEXT_USAGE_TERMS = (
    "INCLUDED",
    "ACCESSED",
    "REFERENCED",
    "REQUIRED_BY_POLICY",
    "OMITTED",
    "UNKNOWN_VALUE",
)
"""Careful terminology (AR-204 T8).

``INCLUDED`` means a source was delivered. ``ACCESSED`` and ``REFERENCED`` mean a
later record named it. ``REQUIRED_BY_POLICY`` means a deterministic rule demands
it. ``OMITTED`` means it was deliberately excluded. ``UNKNOWN_VALUE`` means the
run cannot say. "It appeared in a successful run" is never recorded as "it was
useful".
"""


def source_record(
    bucket: str,
    *,
    origin: str = "unknown",
    label: str = "",
    path: str = "",
    bytes_measured: int | None = None,
    tokens_measured: int | None = None,
    cacheability: str = "UNKNOWN",
    reason: str = "",
    usage: str = "UNKNOWN_VALUE",
    duplicate_of: str = "",
    referenced_by: Sequence[str] = (),
) -> dict:
    """One attributable source row.

    ``bytes_measured`` is a deterministic local measurement and is always
    available when the renderer produced the row; ``tokens_measured`` is only ever
    a provider or tokenizer figure and stays absent otherwise. The two are never
    converted into each other.
    """
    if str(bucket) not in SOURCE_BUCKETS:
        raise ContractError(f"unknown source bucket: {bucket!r}")
    if str(origin) not in SOURCE_ORIGINS:
        raise ContractError(f"unknown source origin: {origin!r}")
    if str(cacheability) not in CACHEABILITY:
        raise ContractError(f"unknown cacheability: {cacheability!r}")
    if str(usage) not in CONTEXT_USAGE_TERMS:
        raise ContractError(f"unknown context usage term: {usage!r}")
    for name, value in (("bytes_measured", bytes_measured), ("tokens_measured", tokens_measured)):
        if value is None:
            continue
        if isinstance(value, bool) or not isinstance(value, (int, float)) or float(value) < 0:
            raise ContractError(f"{name} must be a non-negative measured number")
    row = {
        "bucket": str(bucket),
        "origin": str(origin),
        "label": str(label),
        "path": str(path),
        "cacheability": str(cacheability),
        "reason": str(reason),
        "usage": str(usage),
        "duplicate_of": str(duplicate_of),
        "referenced_by": [str(item) for item in referenced_by],
    }
    if bytes_measured is not None:
        row["bytes"] = int(bytes_measured)
    if tokens_measured is not None:
        row["tokens"] = int(tokens_measured)
    return row


def source_accounting(rows: Sequence[Mapping]) -> dict:
    """Aggregate source rows. Byte and token totals are reported separately."""
    by_bucket: dict[str, dict] = {}
    duplicate_bytes = 0
    cacheable_bytes = 0
    volatile_bytes = 0
    bytes_total = 0
    tokens_total = 0
    tokens_rows = 0
    unmeasured_rows = 0
    for row in rows:
        bucket = str(row.get("bucket", "OTHER"))
        entry = by_bucket.setdefault(bucket, {"sources": 0, "bytes": 0, "tokens": 0, "token_rows": 0})
        entry["sources"] += 1
        size = row.get("bytes")
        if isinstance(size, (int, float)) and not isinstance(size, bool):
            bytes_total += int(size)
            entry["bytes"] += int(size)
            if str(row.get("duplicate_of", "")):
                duplicate_bytes += int(size)
            if str(row.get("cacheability")) == "CACHEABLE":
                cacheable_bytes += int(size)
            elif str(row.get("cacheability")) == "VOLATILE":
                volatile_bytes += int(size)
        tokens = row.get("tokens")
        if isinstance(tokens, (int, float)) and not isinstance(tokens, bool):
            tokens_total += int(tokens)
            entry["tokens"] += int(tokens)
            entry["token_rows"] += 1
            tokens_rows += 1
        else:
            unmeasured_rows += 1
    known = cacheable_bytes + volatile_bytes
    return {
        "buckets": dict(sorted(by_bucket.items())),
        "bytes_total": bytes_total,
        "tokens_total": tokens_total,
        "token_measured_rows": tokens_rows,
        "rows_without_token_measurement": unmeasured_rows,
        "duplicate_bytes": duplicate_bytes,
        "cacheable_bytes": cacheable_bytes,
        "volatile_bytes": volatile_bytes,
        "unknown_cacheability_bytes": max(0, bytes_total - known),
        "stable_prefix_ratio": (round(cacheable_bytes / bytes_total, 6) if bytes_total else None),
        "volatile_prefix_ratio": (round(volatile_bytes / bytes_total, 6) if bytes_total else None),
        "note": "bytes are measured locally; tokens are recorded only when a provider or tokenizer measured them",
    }


# --------------------------------------------------------------- price profiles

PRICE_PROFILE_FIELDS = (
    "provider",
    "model",
    "effective_date",
    "input_uncached_per_million",
    "input_cached_per_million",
    "output_per_million",
    "reasoning_per_million",
    "currency",
    "source",
)
"""A provider-neutral, versioned price profile (AR-204 T19).

Prices are data: a profile names its own source and effective date, is versioned
by its canonical digest, and is never hard-coded into routing.
"""

_PRICE_PROFILES: dict[str, dict] = {}


def normalise_price_profile(profile: Mapping) -> dict:
    if not isinstance(profile, Mapping):
        raise ContractError("a price profile must be an object")
    provider = str(profile.get("provider", "")).strip()
    model = str(profile.get("model", "")).strip()
    if not provider or not model:
        raise ContractError("a price profile needs a provider and a model")
    source = str(profile.get("source", "")).strip()
    if not source:
        raise ContractError(
            "a price profile must name its source; an unsourced price is an invented price"
        )
    normalised: dict[str, Any] = {
        "provider": provider,
        "model": model,
        "effective_date": str(profile.get("effective_date", "")).strip(),
        "currency": str(profile.get("currency", "USD")).strip() or "USD",
        "source": source,
    }
    for name in ("input_uncached_per_million", "input_cached_per_million",
                 "output_per_million", "reasoning_per_million"):
        value = profile.get(name)
        if value is None:
            normalised[name] = None
            continue
        if isinstance(value, bool) or not isinstance(value, (int, float)) or float(value) < 0:
            raise ContractError(f"price field {name} must be a non-negative number")
        normalised[name] = float(value)
    if all(normalised[name] is None for name in (
        "input_uncached_per_million", "input_cached_per_million", "output_per_million",
        "reasoning_per_million",
    )):
        raise ContractError("a price profile must declare at least one price")
    return normalised


def register_price_profile(profile: Mapping) -> str:
    """Register one profile and return its digest id. Data, never authority."""
    normalised = normalise_price_profile(profile)
    profile_id = "price_" + digest_text(canonical_json(normalised))[:16]
    _PRICE_PROFILES[profile_id] = normalised
    return profile_id


def price_profiles() -> dict[str, dict]:
    return {key: dict(value) for key, value in sorted(_PRICE_PROFILES.items())}


def price_profile(profile_id: str) -> dict | None:
    value = _PRICE_PROFILES.get(str(profile_id))
    return dict(value) if value else None


def load_price_profiles(path: Path) -> list[str]:
    """Load profiles from a JSON document. The file is data; a bad file is refused."""
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ContractError(f"price profile file is unreadable: {exc}") from exc
    profiles = value.get("profiles") if isinstance(value, Mapping) else None
    if not isinstance(profiles, list):
        raise ContractError("a price profile file needs a 'profiles' list")
    return [register_price_profile(item) for item in profiles]


def cost_from_usage(values: Mapping, *, profile_id: str) -> dict:
    """Derive a monetary figure from measured tokens and a registered profile.

    The result is explicitly ``derived``: it is an arithmetic consequence of a
    measured token count and a declared price, not a provider invoice. A token
    field with no measured value contributes nothing and is listed in
    ``unpriced_fields``; it is never assumed to be zero.
    """
    profile = price_profile(profile_id)
    if profile is None:
        raise ContractError(f"no registered price profile matches {profile_id!r}")
    if not isinstance(values, Mapping):
        raise ContractError("cost needs a mapping of measured usage values")

    def tokens(name: str) -> int | None:
        value = values.get(name)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return None
        return int(value)

    lines: list[dict] = []
    total = 0.0
    unpriced: list[str] = []
    missing: list[str] = []

    def charge(name: str, rate_name: str, label: str) -> None:
        nonlocal total
        count = tokens(name)
        rate = profile.get(rate_name)
        if count is None:
            missing.append(name)
            return
        if rate is None:
            unpriced.append(name)
            return
        amount = count / 1_000_000 * float(rate)
        total += amount
        lines.append({"field": name, "tokens": count, "rate": float(rate), "amount": round(amount, 8), "label": label})

    input_total = tokens("input_tokens")
    uncached = tokens("uncached_input_tokens")
    cached = tokens("cached_input_tokens")
    if uncached is not None or cached is not None:
        charge("uncached_input_tokens", "input_uncached_per_million", "uncached input")
        charge("cached_input_tokens", "input_cached_per_million", "cached input")
        if input_total is not None:
            split = (uncached or 0) + (cached or 0)
            if split != input_total:
                lines.append({
                    "field": "input_tokens",
                    "tokens": input_total,
                    "rate": None,
                    "amount": None,
                    "label": "the provider's input split does not sum to its input total; the split was used",
                })
    elif input_total is not None:
        charge("input_tokens", "input_uncached_per_million", "input (cache split unavailable)")
    else:
        missing.append("input_tokens")
    charge("output_tokens", "output_per_million", "output")
    charge("reasoning_tokens", "reasoning_per_million", "reasoning")
    return {
        "amount": round(float(total), 8),
        "currency": str(profile.get("currency", "USD")),
        "derived": True,
        "basis": "measured tokens x registered price profile",
        "profile_id": str(profile_id),
        "profile": profile,
        "lines": lines,
        "unpriced_fields": sorted(set(unpriced)),
        "unmeasured_fields": sorted(set(missing)),
        "complete": not unpriced and not missing,
    }


# ------------------------------------------------------------- billing (measured)


def record_billing(
    state: dict,
    execution_id: str,
    *,
    source: str,
    amount: float,
    currency: str = "USD",
    basis: str = "",
    request_id: str = "",
) -> dict:
    """Record a *provider-reported* billing amount for one execution.

    This is the only place a monetary figure becomes a measurement, and it is
    named as the provider's figure with the observer that supplied it. Nothing
    here derives or scales a price.
    """
    record = execution.execution(state, execution_id)
    if record is None:
        raise ContractError(f"no engine-created execution record matches {execution_id!r}")
    observer = str(source or "").strip()
    if observer.lower() in ("", "worker", "worker-output", "handoff", "self-reported"):
        raise ContractError(
            "a billing figure must come from the adapter or provider that reported it; "
            "a worker's claim is not a measurement"
        )
    if isinstance(amount, bool) or not isinstance(amount, (int, float)) or float(amount) < 0:
        raise ContractError("a billing amount must be a non-negative number")
    if not str(currency or "").strip():
        raise ContractError("a billing figure needs a currency")
    billing = {
        "measured": True,
        "source": observer,
        "amount": float(amount),
        "currency": str(currency).strip().upper(),
        "basis": str(basis),
        "request_id": str(request_id),
        "recorded_at": contracts.utc_now(),
    }
    usage = record.setdefault("usage", {})
    if not isinstance(usage, dict):
        raise ContractError("the execution usage record is malformed")
    usage["billing"] = billing
    return billing


def billing_view(state: dict, execution_id: str) -> dict:
    record = execution.execution(state, execution_id)
    if record is None:
        raise ContractError(f"no engine-created execution record matches {execution_id!r}")
    usage = record.get("usage") if isinstance(record.get("usage"), Mapping) else {}
    billing = usage.get("billing") if isinstance(usage.get("billing"), Mapping) else {}
    if not billing:
        return {"execution_id": execution_id, "monetary": "UNKNOWN", "reason": "no measured billing was recorded"}
    return {
        "execution_id": execution_id,
        "monetary": "MEASURED",
        "amount": float(billing.get("amount", 0.0)),
        "currency": str(billing.get("currency", "")),
        "source": str(billing.get("source", "")),
        "basis": str(billing.get("basis", "")),
    }


# --------------------------------------------------------------- cache telemetry

CACHE_OBSERVATION_FIELDS = (
    "cache_hit",
    "cached_input_tokens",
    "uncached_input_tokens",
    "cache_read_tokens",
    "cache_write_tokens",
)


def record_cache_observation(
    state: dict,
    execution_id: str,
    *,
    source: str,
    observed: Mapping | None = None,
    structural: Mapping | None = None,
    provider_metadata: Mapping | None = None,
) -> dict:
    """Record what was *measured* about caching, and what is only structural.

    A structural observation (``stable_prefix_digest``, ``stable_prefix_bytes``,
    ``volatile_bytes``) says the request *could* be cached. It is never recorded
    as a cache hit: ``cache_hit`` stays ``None`` unless a provider reported it,
    because calling structural cacheability a hit would be a fabricated
    measurement.
    """
    record = execution.execution(state, execution_id)
    if record is None:
        raise ContractError(f"no engine-created execution record matches {execution_id!r}")
    observer = str(source or "").strip()
    if observer.lower() in ("", "worker", "worker-output", "handoff", "self-reported"):
        raise ContractError(
            "a cache observation must come from the adapter or provider that measured it"
        )
    values = dict(observed or {})
    measured: dict[str, Any] = {}
    for name in CACHE_OBSERVATION_FIELDS:
        if name not in values:
            continue
        value = values[name]
        if name == "cache_hit":
            if not isinstance(value, bool):
                raise ContractError("cache_hit must be a boolean when reported")
            measured[name] = value
            continue
        if isinstance(value, bool) or not isinstance(value, (int, float)) or float(value) < 0:
            raise ContractError(f"cache field {name} must be a non-negative number")
        measured[name] = int(value)
    structure: dict[str, Any] = {}
    for name in ("stable_prefix_digest", "stable_prefix_bytes", "volatile_bytes", "boundary_index"):
        if structural is None or name not in structural:
            continue
        structure[name] = structural[name]
    observation = {
        "source": observer,
        "measured": measured,
        "structural": structure,
        "provider_metadata": dict(provider_metadata or {}),
        "cache_hit": measured.get("cache_hit"),
        "structural_only": not bool(measured),
        "recorded_at": contracts.utc_now(),
        "note": (
            "structural cacheability is not a cache hit; cache_hit stays unknown unless a provider "
            "reported it"
        ),
    }
    record["cache_observation"] = observation
    return observation


def cache_observation(state: dict, execution_id: str) -> dict:
    record = execution.execution(state, execution_id)
    if record is None:
        raise ContractError(f"no engine-created execution record matches {execution_id!r}")
    value = record.get("cache_observation")
    return dict(value) if isinstance(value, Mapping) else {}


# ------------------------------------------------------------------- task tree

ROLE_NODE_KINDS = {
    "reasoner": "coordinator",
    "implementer": "worker",
    "validator": "validation",
    "reviewer": "review",
}

NODE_KINDS = ("coordinator", "decision", "worker", "repair", "validation", "review")

CONTRIBUTING_STATES = ("COMPLETED",)


def _node_for_execution(record: Mapping, *, prior_failed: bool) -> dict:
    role = str(record.get("role", ""))
    kind = ROLE_NODE_KINDS.get(role, "unknown")
    if kind == "worker" and prior_failed:
        kind = "repair"
    usage = record.get("usage") if isinstance(record.get("usage"), Mapping) else {}
    values = usage.get("values") if isinstance(usage.get("values"), Mapping) else {}
    requested = record.get("requested") if isinstance(record.get("requested"), Mapping) else {}
    observed = record.get("observed") if isinstance(record.get("observed"), Mapping) else {}
    return {
        "node_kind": kind,
        "execution_id": str(record.get("execution_id", "")),
        "role": role,
        "task_id": str(record.get("task_id", "")),
        "parent_execution": str(record.get("parent_execution", "")),
        "state": str(record.get("state", "UNKNOWN")),
        "requested": dict(requested),
        "observed": dict(observed),
        "provider": str(observed.get("provider", "UNKNOWN")),
        "model": str(observed.get("model", "UNKNOWN")),
        "measured_usage": {str(key): value for key, value in values.items()},
        "usage_measured": bool(usage.get("measured")),
        "context_composition": dict(usage.get("context_composition") or {}),
        "billing": dict(usage.get("billing") or {}),
        "cache": dict(record.get("cache_observation") or {}),
        "failed": str(record.get("state", "")) == "FAILED",
    }


def task_tree(state: Mapping, task_id: str, *, batches: Sequence[Mapping] | None = None) -> dict:
    """The execution tree for one task: coordinator, decisions, worker, repair, validation, review.

    Every node names the execution that produced it. A node contributes to a
    verified completion only when the task actually reached one *and* the node
    completed; a failed node is still listed because it is part of what the task
    cost.
    """
    task_id = str(task_id)
    rows = [record for record in execution.executions(state) if str(record.get("task_id", "")) == task_id]
    prior_failed = False
    nodes: list[dict] = []
    for record in rows:
        node = _node_for_execution(record, prior_failed=prior_failed)
        if node["failed"] and str(record.get("role")) == "implementer":
            prior_failed = True
        nodes.append(node)
    decision_nodes: list[dict] = []
    for batch in batches if batches is not None else (state.get("decision_batches") or []):
        if not isinstance(batch, Mapping):
            continue
        if str(batch.get("task_id", "")) != task_id:
            continue
        decision_nodes.append({
            "node_kind": "decision",
            "batch_id": str(batch.get("batch_id", "")),
            "task_id": task_id,
            "questions": len(batch.get("questions") or []),
            "status": str(batch.get("status", "")),
            "projection_chars": int(batch.get("projection_chars", 0) or 0),
            "usage": dict(batch.get("usage") or {}),
            "execution_id": str(batch.get("execution_id", "")),
            "request_count": 1 if batch.get("provider_available") else 0,
        })
    failures = [record for record in execution.failures(state) if str(record.get("task_id", "")) == task_id]
    return {
        "task_id": task_id,
        "nodes": [*decision_nodes, *nodes],
        "executions": len(nodes),
        "decision_batches": len(decision_nodes),
        "failures": len(failures),
        "failed_executions": sum(1 for node in nodes if node["failed"]),
    }


TREE_QUOTE_FIELDS = (
    "input_tokens",
    "output_tokens",
    "cached_input_tokens",
    "uncached_input_tokens",
    "reasoning_tokens",
    "request_count",
    "turns",
    "tool_calls",
    "tool_errors",
    "worker_executions",
    "reviewer_executions",
    "validation_executions",
    "decision_calls",
    "repair_attempts",
    "duration_seconds",
    "provider_latency_seconds",
    "context_preparation_seconds",
    "wall_clock_seconds",
)


def _sum_usage(rows: Sequence[Mapping]) -> dict:
    totals: dict[str, float] = {}
    measured_rows = 0
    for row in rows:
        values = row.get("measured_usage") if isinstance(row, Mapping) else None
        if not values:
            continue
        measured_rows += 1
        for name, value in values.items():
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                continue
            totals[str(name)] = totals.get(str(name), 0) + float(value)
    return {
        "totals": {name: (int(value) if float(value).is_integer() else value) for name, value in sorted(totals.items())},
        "measured_nodes": measured_rows,
    }


def task_tree_costs(tree: Mapping) -> dict:
    """Cost shares across the tree, from measured usage only."""
    nodes = list(tree.get("nodes") or [])
    quote: dict[str, dict] = {}
    for kind in NODE_KINDS:
        subset = [node for node in nodes if str(node.get("node_kind", "")) == kind]
        if not subset and kind != "worker":
            continue
        quote[kind] = _sum_usage(subset)
    totals = _sum_usage(nodes)
    quota = totals["totals"]
    denominator = quota.get("output_tokens") if quota.get("output_tokens") is not None else None
    shares: dict[str, Any] = {}
    for kind, entry in quote.items():
        value = entry["totals"].get("output_tokens")
        if denominator and value is not None:
            shares[kind] = round(float(value) / float(denominator), 6)
        else:
            shares[kind] = "UNKNOWN"
    return {
        "by_kind": quote,
        "totals": totals,
        "shares_by_output_tokens": shares,
        "failed_node_usage": _sum_usage([node for node in nodes if node.get("failed")]),
        "note": "shares are computed from measured output tokens only; a share is UNKNOWN when output tokens were not measured",
    }


# -------------------------------------------------------------------- task cost


def _monetary_total(state: Mapping, rows: Sequence[Mapping], *, profile_id: str, currency: str = "") -> dict:
    """Measured billing if every measured row carries it, else a derived figure, else UNKNOWN."""
    billed = [row for row in rows if isinstance(row, Mapping) and row.get("billing")]
    measured_rows = [row for row in rows if isinstance(row, Mapping) and row.get("usage_measured")]
    if measured_rows and len(billed) == len(measured_rows):
        currencies = {str(row["billing"].get("currency", "")) for row in billed}
        if len(currencies) == 1:
            amount = sum(float(row["billing"].get("amount", 0.0)) for row in billed)
            return {
                "monetary": "MEASURED",
                "amount": round(amount, 8),
                "currency": currencies.pop(),
                "billed_executions": len(billed),
            }
        return {
            "monetary": "UNKNOWN",
            "reason": "the task's executions were billed in more than one currency",
            "currencies": sorted(currencies),
        }
    if profile_id:
        combined: dict[str, float] = {}
        for row in measured_rows:
            for name, value in (row.get("measured_usage") or {}).items():
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    combined[name] = combined.get(name, 0) + float(value)
        if combined:
            priced = cost_from_usage(combined, profile_id=profile_id)
            priced["monetary"] = "DERIVED"
            return priced
    return {
        "monetary": "UNKNOWN",
        "reason": (
            "no provider-reported billing was recorded and no price profile was supplied"
            if not profile_id else "no measured usage existed to price"
        ),
    }


def task_cost(
    state: Mapping,
    task_id: str,
    *,
    profile_id: str = "",
    current: Mapping | None = None,
) -> dict:
    """Everything spent on one task, including failed and abandoned attempts."""
    task_id = str(task_id)
    tree = task_tree(state, task_id)
    rows = [node for node in tree["nodes"] if node.get("node_kind") != "decision"]
    decision_rows = [node for node in tree["nodes"] if node.get("node_kind") == "decision"]
    measured = _sum_usage(rows)
    decision_measured = _sum_usage(decision_rows)
    combined_rows = [*rows, *[{
        "usage_measured": bool(node.get("request_count")),
        "measured_usage": {
            **{k: v for k, v in (node.get("usage") or {}).items() if isinstance(v, (int, float)) and not isinstance(v, bool)},
            **({"request_count": node["request_count"]} if node.get("request_count") else {}),
        },
        "billing": {},
    } for node in decision_rows]]
    verification = _task_verification(state, task_id, current=current)
    return {
        "task_id": task_id,
        "executions": len(rows),
        "decision_batches": len(decision_rows),
        "failed_executions": tree["failed_executions"],
        "measured": measured,
        "decision_batches_measured": decision_measured,
        "totals": _combine_totals(measured["totals"], decision_measured["totals"]),
        "monetary": _monetary_total(state, combined_rows, profile_id=profile_id),
        "usage_complete": measured["measured_nodes"] == len(rows) and bool(rows),
        "nodes_without_usage": [node["execution_id"] for node in rows if not node.get("usage_measured")],
        "verification": verification,
        "note": (
            "failed and abandoned attempts are included; a task whose executions were not all measured "
            "reports usage_complete=false rather than a smaller total"
        ),
    }


def _combine_totals(*totals: Mapping) -> dict:
    combined: dict[str, float] = {}
    for block in totals:
        for name, value in (block or {}).items():
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                combined[str(name)] = combined.get(str(name), 0) + float(value)
    return {name: (int(value) if float(value).is_integer() else value) for name, value in sorted(combined.items())}


def _task_verification(state: Mapping, task_id: str, *, current: Mapping | None = None) -> dict:
    from . import verification as verification_module

    view = verification_module.status(state, subject=task_id, current=current)
    return {
        "subject": task_id,
        "level": view.get("level", "UNVERIFIED"),
        "records": view.get("records", 0),
        "verified": str(view.get("level", "")) == "VERIFIED",
    }


def verified_completion_cost(
    state: Mapping,
    task_id: str,
    *,
    profile_id: str = "",
    current: Mapping | None = None,
) -> dict:
    """The milestone's primary metric: what one verified completion cost.

    The figure is only returned when the task actually reached an AR-203
    verification at ``VERIFIED``. Otherwise the answer is ``verified: false`` and
    the spend is reported as *cost of an unverified attempt* — deliberately a
    different number. When no usage was measured the token totals are returned
    with ``monetary: UNKNOWN``; the metric is never fabricated.
    """
    cost = task_cost(state, task_id, profile_id=profile_id, current=current)
    verified = bool(cost["verification"]["verified"])
    return {
        "task_id": str(task_id),
        "metric": "verified_completion_cost",
        "verified": verified,
        "cost_label": "verified_completion_cost" if verified else "cost_of_unverified_attempt",
        "monetary": cost["monetary"],
        "totals": cost["totals"],
        "executions": cost["executions"],
        "failed_executions": cost["failed_executions"],
        "decision_batches": cost["decision_batches"],
        "usage_complete": cost["usage_complete"],
        "verification": cost["verification"],
        "note": (
            "only measured usage is summed; absent fields stay unknown, and a task that did not reach a "
            "VERIFIED record never reports a verified completion cost"
        ),
    }


# --------------------------------------------------------- context-economics view


def context_economics(state: Mapping) -> dict:
    """Context attribution across the run: decisions, composition and duplication."""
    decisions = state.get("context_decisions") if isinstance(state.get("context_decisions"), list) else []
    reason_counts: dict[str, int] = {}
    included = 0
    omitted = 0
    cache_hits = 0
    cache_misses = 0
    invalidations = 0
    duplicate_rows: list[dict] = []
    for decision in decisions:
        if not isinstance(decision, Mapping):
            continue
        for item in (decision.get("decisions") or []):
            if not isinstance(item, Mapping):
                continue
            if str(item.get("decision")) == "included":
                included += 1
            elif str(item.get("decision")) == "omitted":
                omitted += 1
            reason = str(item.get("reason", "UNKNOWN"))
            reason_counts[reason] = reason_counts.get(reason, 0) + 1
            if item.get("duplicate_of"):
                duplicate_rows.append({"path": item.get("path"), "duplicate_of": item.get("duplicate_of")})
        cache = decision.get("cache") if isinstance(decision.get("cache"), Mapping) else {}
        cache_hits += int(cache.get("hits", 0) or 0)
        cache_misses += int(cache.get("misses", 0) or 0)
        invalidations += len(cache.get("invalidated") or [])
    composition: dict[str, dict[str, float]] = {}
    for record in execution.executions(state):
        usage = record.get("usage") if isinstance(record.get("usage"), Mapping) else {}
        block = usage.get("context_composition") if isinstance(usage.get("context_composition"), Mapping) else {}
        for bucket, value in block.items():
            mapped = AR203_BUCKET_MAP.get(str(bucket), "OTHER")
            entry = composition.setdefault(mapped, {"bytes": 0, "token_contributions": 0, "executions": 0})
            entry["executions"] += 1
            if str(bucket) in ("static_system", "tool_schemas"):
                entry["token_contributions"] += 1
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                entry["bytes"] += int(value) if str(bucket) not in ("static_system", "tool_schemas") else 0
    return {
        "decisions": len(decisions),
        "sources_included": included,
        "sources_omitted": omitted,
        "reasons": dict(sorted(reason_counts.items())),
        "cache": {"hits": cache_hits, "misses": cache_misses, "invalidations": invalidations},
        "duplicates": duplicate_rows,
        "composition": dict(sorted(composition.items())),
        "terminology": list(CONTEXT_USAGE_TERMS),
        "note": (
            "an included source is not a useful source: ACCESSED and REFERENCED require a later record "
            "naming it, and nothing here infers causal value from a successful run"
        ),
    }


def rank_opportunities(rows: Sequence[Mapping]) -> list[dict]:
    """Rank cost-optimisation opportunities by a declared heuristic.

    ``score = cost_share x removable_fraction / quality_risk_weight``. The formula
    is a prioritisation heuristic, not a prediction; rows whose inputs are
    UNKNOWN are listed after the ranked rows with ``score: None`` rather than
    scored with an invented number.
    """
    risk_weight = {"low": 1.0, "medium": 2.0, "high": 4.0}
    ranked: list[dict] = []
    unknown: list[dict] = []
    for row in rows or ():
        item = {str(key): value for key, value in dict(row).items()}
        share = item.get("cost_share")
        removable = item.get("removable_fraction")
        risk = str(item.get("quality_risk", "medium")).lower()
        if isinstance(share, (int, float)) and isinstance(removable, (int, float)) and risk in risk_weight:
            item["score"] = round(float(share) * float(removable) / risk_weight[risk], 6)
            item["heuristic"] = "cost_share x removable_fraction / quality_risk_weight"
            ranked.append(item)
        else:
            item["score"] = None
            item["heuristic"] = "not scored: an input was UNKNOWN"
            unknown.append(item)
    ranked.sort(key=lambda item: (-float(item["score"]), str(item.get("layer", ""))))
    return [*ranked, *unknown]


# --------------------------------------------------------- decision-plane economics


def batch_dependency_problems(questions: Sequence[Mapping], *, depends_on: Mapping | None = None) -> list[str]:
    """Refuse a dependency inside a supposedly parallel batch (invariant 50).

    A question that depends on another question's answer in the same batch cannot
    be answered independently, so the batch would hide a sequencing error behind a
    single model call.
    """
    depends = {str(key): {str(item) for item in (value or [])} for key, value in dict(depends_on or {}).items()}
    ids = {str(question.get("question_id", "")) for question in questions or ()}
    problems: list[str] = []
    for question in questions or ():
        question_id = str(question.get("question_id", ""))
        for dependency in sorted(depends.get(question_id, set())):
            if dependency in ids and dependency != question_id:
                problems.append(
                    f"question {question_id!r} depends on {dependency!r} in the same batch; "
                    "dependent questions need separate decision steps"
                )
        if question_id in depends.get(question_id, set()):
            problems.append(f"question {question_id!r} depends on itself")
    return problems


def plan_batches(questions: Sequence[Mapping], *, depends_on: Mapping | None = None) -> dict:
    """Group independent questions into batches; dependent ones become later steps.

    This is a deterministic plan, not a provider call. Questions with no
    dependency on any other question go in the first batch; a question that
    depends on a planned question goes in a later step. Cycles are refused.
    """
    depends = {str(key): {str(item) for item in (value or [])} for key, value in dict(depends_on or {}).items()}
    ids = [str(question.get("question_id", "")) for question in questions or ()]
    if len(set(ids)) != len(ids):
        raise ContractError("a batch plan cannot repeat a question id")
    remaining = list(ids)
    steps: list[list[str]] = []
    resolved: set[str] = set()
    while remaining:
        ready = [qid for qid in remaining if not (depends.get(qid, set()) - resolved)]
        if not ready:
            raise ContractError(
                "the declared question dependencies contain a cycle: " + ", ".join(sorted(remaining))
            )
        steps.append(ready)
        resolved.update(ready)
        remaining = [qid for qid in remaining if qid not in resolved]
    return {
        "steps": steps,
        "batches": len(steps),
        "questions": len(ids),
        "independent": len(steps) == 1,
        "note": "questions in one step share one projected state and cannot reference another answer in that step",
    }


def decision_economics(state: Mapping, *, task_id: str = "") -> dict:
    """Per-batch decision cost, with the state/dependency checks AR-204 adds."""
    import json as _json

    from .decisions import batch as batch_module

    rows: list[dict] = []
    for record in batch_module.batches(state):
        if task_id and str(record.get("task_id", "")) != str(task_id):
            continue
        questions = [item for item in (record.get("questions") or []) if isinstance(item, Mapping)]
        depends = {
            str(item.get("question_id", "")): list(item.get("depends_on") or [])
            for item in questions
            if item.get("depends_on")
        }
        usage = record.get("usage") if isinstance(record.get("usage"), Mapping) else {}
        rows.append({
            "batch_id": str(record.get("batch_id", "")),
            "task_id": str(record.get("task_id", "")),
            "status": str(record.get("status", "")),
            "questions": len(questions),
            "state_bytes": int(record.get("projection_chars", 0) or 0),
            "state_digest": str(record.get("state_digest", "")),
            "request_count": 1 if record.get("provider_available") else 0,
            "provider": str(record.get("provider", "")),
            "model_version": str(record.get("model_version", "")),
            "usage": {str(key): value for key, value in usage.items()},
            "usage_measured": bool(usage),
            "dependency_problems": batch_dependency_problems(questions, depends_on=depends),
            "results": [
                {"question_id": item.get("question_id"), "status": item.get("status")}
                for item in (record.get("results") or [])
            ],
        })
    measured = sum(1 for row in rows if row["usage_measured"])
    return {
        "task_id": str(task_id),
        "batches": rows,
        "totals": {
            "batches": len(rows),
            "questions": sum(row["questions"] for row in rows),
            "requests": sum(row["request_count"] for row in rows),
            "state_bytes": sum(row["state_bytes"] for row in rows),
            "measured_batches": measured,
        },
        "note": "one batch is one provider request; a batch whose usage was not measured stays unmeasured",
    }


def decision_layer_cost(
    *,
    deterministic_calls: int = 0,
    bounded_batches: Sequence[Mapping] = (),
    generative_usage: Mapping | None = None,
) -> dict:
    """Compare deterministic code, bounded decisions and generative inference.

    The three layers are reported side by side with whatever was actually
    measured. A layer that was not measured says ``UNKNOWN``; the comparison does
    not assume a bounded decision is cheaper than a generative call.
    """
    bounded_measured = [
        dict(row.get("usage") or {}) for row in bounded_batches
        if isinstance(row, Mapping) and row.get("usage_measured")
    ]
    bounded_totals = _combine_totals(*bounded_measured) if bounded_measured else {}
    return {
        "deterministic": {"provider_calls": 0, "answer": deterministic_calls, "measured": True},
        "bounded": {
            "provider_calls": sum(1 for row in bounded_batches if isinstance(row, Mapping) and row.get("request_count")),
            "usage": bounded_totals,
            "measured": bool(bounded_measured),
        },
        "generative": {
            "usage": dict(generative_usage or {}),
            "measured": bool(generative_usage),
        },
        "rule": "code before judgment, judgment before generation",
        "note": "a layer with no measurement is UNKNOWN, not zero",
    }


def summarise(state: Mapping) -> dict:
    """Run-level economics: execution totals, task count and measured coverage."""
    tree_tasks = sorted({str(record.get("task_id", "")) for record in execution.executions(state)})
    measured = execution.telemetry_summary(state)
    return {
        "tasks_with_executions": len(tree_tasks),
        "task_ids": tree_tasks[:50],
        "executions": measured["executions"],
        "executions_with_measured_usage": measured["executions_with_measured_usage"],
        "measured_totals": measured["totals"],
        "note": "coverage is stated explicitly so a cheap-looking total with poor coverage is visible",
    }


__all__ = [
    "SOURCE_BUCKETS",
    "AR203_BUCKET_MAP",
    "SOURCE_ORIGINS",
    "CACHEABILITY",
    "CONTEXT_USAGE_TERMS",
    "PRICE_PROFILE_FIELDS",
    "CACHE_OBSERVATION_FIELDS",
    "ROLE_NODE_KINDS",
    "NODE_KINDS",
    "TREE_QUOTE_FIELDS",
    "source_record",
    "source_accounting",
    "normalise_price_profile",
    "register_price_profile",
    "price_profiles",
    "price_profile",
    "load_price_profiles",
    "cost_from_usage",
    "record_billing",
    "billing_view",
    "record_cache_observation",
    "cache_observation",
    "task_tree",
    "task_tree_costs",
    "task_cost",
    "verified_completion_cost",
    "context_economics",
    "rank_opportunities",
    "batch_dependency_problems",
    "plan_batches",
    "decision_economics",
    "decision_layer_cost",
    "summarise",
]
