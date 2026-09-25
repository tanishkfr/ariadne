"""Adaptive context decisions and conservative caching (AR-202 T4/T11/T12).

The compiler in ``scripts/prepare-stage.py`` still assembles every packet. This
module is the decision layer around it: it names, for every candidate source,
whether the packet includes or omits it and *why*, and it keeps a small,
versioned cache of already-hashed sources so unchanged inputs do not have to be
read and hashed again.

Hard rules, enforced against the plan the transport receives:

* a plan can only **omit** a candidate the transport declared removable, or
  **reuse** the recorded hashes of a candidate it still includes;
* a plan can never *add* a source, so a cache entry can never resurrect a
  forbidden source or introduce anything the stage does not already allow;
* a cache entry is valid only while the file's size and mtime identity match and
  the stage, policy version and project revision agree; anything else is a miss,
  is re-derived from the file, and the invalidation is observable.

No lossy summarisation exists here. A source is either delivered verbatim or
omitted with a reason; nothing is replaced by a summary.
"""

from __future__ import annotations

from pathlib import Path
from typing import Mapping

from . import contracts
from .contracts import CONTEXT_REASONS, ContractError

CACHE_NAME = "context-cache.json"
CACHE_SCHEMA = 1

REMOVABLE_BUCKETS = ("optional", "conditional")


def cache_path(run_root: Path) -> Path:
    return Path(run_root) / CACHE_NAME


def stat_identity(path: Path) -> dict:
    try:
        info = Path(path).stat()
    except OSError:
        return {"exists": False}
    return {"exists": True, "size": int(info.st_size), "mtime_ns": int(info.st_mtime_ns)}


def load_cache(run_root: Path) -> dict:
    """Read the cache. An unreadable or unknown-version cache is a miss, not a repair."""
    path = cache_path(Path(run_root))
    if not path.is_file():
        return {"schema_version": CACHE_SCHEMA, "entries": {}}
    import json

    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"schema_version": CACHE_SCHEMA, "entries": {}}
    if not isinstance(value, dict) or value.get("schema_version") != CACHE_SCHEMA:
        return {"schema_version": CACHE_SCHEMA, "entries": {}}
    if not isinstance(value.get("entries"), dict):
        value["entries"] = {}
    return value


def save_cache(run_root: Path, cache: Mapping) -> Path:
    import json

    path = cache_path(Path(run_root))
    payload = {
        "schema_version": CACHE_SCHEMA,
        "policy_version": contracts.POLICY_VERSION,
        "entries": {str(key): dict(value) for key, value in (cache.get("entries") or {}).items()},
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def candidate_is_removable(candidate: Mapping) -> bool:
    return bool(candidate.get("removable")) and str(candidate.get("bucket", "")) in REMOVABLE_BUCKETS


def design_source_state(state: dict) -> dict:
    """The design requirement of the current task, read from the design records.

    A run with no design records declares no design requirement, so a
    non-design task never gains or loses a source because of this rule.
    """
    from . import design

    characterisation = design.latest_characterisation(state)
    if not characterisation:
        return {"present": False, "required": False, "reference_required": False}
    characteristics = characterisation.get("characteristics") or {}
    values = {
        name: str((value or {}).get("value", "UNKNOWN"))
        for name, value in characteristics.items()
    }
    return {
        "present": True,
        "task_id": str(characterisation.get("task_id", "")),
        "design": values.get("design_task", "UNKNOWN"),
        "required": values.get("design_task") in ("REQUIRED", "OPTIONAL"),
        "reference_required": values.get("reference_research") == "REQUIRED",
        "reference_selected": values.get("reference_research") in ("REQUIRED", "OPTIONAL"),
    }


def _design_reason(candidate: Mapping, design_state: Mapping, characterisation: Mapping | None) -> tuple[str, str] | None:
    """(reason, evidence) when a design/reference source must be omitted, else None.

    The declaration itself is the trigger: a source that says it carries design or
    reference material is omitted unless this task actually needs that material.
    A run with no design records declares no design requirement, so a design
    source is not silently pulled into an unrelated task.
    """
    requires = str(candidate.get("requires", "") or "")
    if requires == "reference" and not (
        design_state.get("present") and design_state.get("reference_selected")
    ):
        return "IRRELEVANT_TO_TASK", "the task declares no reference research"
    if requires == "design" and not (design_state.get("present") and design_state.get("required")):
        return "IRRELEVANT_TO_TASK", "the task is not an interface design task"
    return None


def _changed_file_reason(candidate: Mapping, characterisation: Mapping | None) -> str:
    """``RELEVANT_CHANGED_FILE`` when the candidate names a file this revision changed."""
    changed = {str(item) for item in ((characterisation or {}).get("changed_files") or [])}
    if not changed:
        return ""
    declared = [str(item) for item in (candidate.get("changed_files") or []) if str(item).strip()]
    path = str(candidate.get("path", ""))
    for name in declared:
        normalised = name.replace("\\", "/")
        if normalised in changed or any(normalised.endswith(item) or item.endswith(normalised) for item in changed):
            return f"this revision changed {normalised}"
    if path and path.replace("\\", "/") in changed:
        return f"this revision changed {path}"
    return ""


def _reuse_entry(cache: Mapping, candidate: Mapping, *, stage: str, revision_hash: str) -> dict | None:
    path = str(candidate.get("path", ""))
    entry = (cache.get("entries") or {}).get(path)
    if not isinstance(entry, dict):
        return None
    if bool(candidate.get("forbidden")):
        return None
    if str(entry.get("stage", "")) != str(stage):
        return None
    if str(entry.get("policy_version", "")) != contracts.POLICY_VERSION:
        return None
    if revision_hash and str(entry.get("revision_hash", "")) != revision_hash:
        # The revision changed: the previous packet's hashes are not evidence
        # for this one. Conservative: recompute.
        return None
    current = stat_identity(Path(path))
    if not current.get("exists"):
        return None
    if int(entry.get("size", -1)) != int(current.get("size", -2)):
        return None
    if int(entry.get("mtime_ns", -1)) != int(current.get("mtime_ns", -2)):
        return None
    if not str(entry.get("source_sha256", "")):
        return None
    return entry


def decide(
    state: dict,
    *,
    stage: str,
    candidates: list[dict],
    characterisation: Mapping | None = None,
    run_root: Path | None = None,
    revision_hash: str = "",
    deduplicate: bool = True,
) -> dict:
    """Decide inclusion for every candidate and return the decision record.

    The record is written to the run state by ``record`` after the transport has
    produced the packet, so the delivered/omitted sets in it are the observed
    outcome rather than the plan.
    """
    cache = load_cache(Path(run_root)) if run_root is not None else {"entries": {}}
    creative_required = bool(state.get("creative_evidence_required", True))
    design_state = design_source_state(state)
    required_capabilities = {
        str(item.get("id"))
        for item in ((characterisation or {}).get("required_capabilities") or [])
    }
    decisions: list[dict] = []
    hits = 0
    misses = 0
    invalidated: list[dict] = []
    reuse: dict[str, dict] = {}

    for candidate in candidates:
        path = str(candidate.get("path", ""))
        entry = {
            "label": str(candidate.get("label", "") or Path(path).name),
            "path": path,
            "kind": str(candidate.get("kind", "")),
            "bucket": str(candidate.get("bucket", "")),
            "removable": bool(candidate.get("removable")),
        }
        if candidate.get("forbidden"):
            entry.update({"decision": "omitted", "reason": "FORBIDDEN_FOR_STAGE"})
            decisions.append(entry)
            continue
        if candidate.get("required"):
            if not candidate.get("exists", True):
                entry.update({"decision": "omitted", "reason": "MISSING"})
                decisions.append(entry)
                continue
            cached = _reuse_entry(cache, candidate, stage=stage, revision_hash=revision_hash) if run_root is not None else None
            if cached is not None:
                hits += 1
                entry.update({"decision": "included", "reason": "UNCHANGED_CACHED_INPUT", "cached": True})
                reuse[path] = {
                    "source_sha256": str(cached.get("source_sha256", "")),
                    "content_sha256": str(cached.get("content_sha256", "")),
                    "size": cached.get("size"),
                    "mtime_ns": cached.get("mtime_ns"),
                }
            else:
                if run_root is not None and (cache.get("entries") or {}).get(path):
                    misses += 1
                    invalidated.append({"path": path, "reason": "source changed since the cached delivery"})
                entry.update({"decision": "included", "reason": "REQUIRED_BY_STAGE"})
            decisions.append(entry)
            continue
        # ------------------------------------------------- removable candidates
        if not candidate.get("exists", True):
            reason = str(candidate.get("absent_reason", "") or "MISSING")
            entry.update({
                "decision": "omitted",
                "reason": reason if reason in CONTEXT_REASONS else "MISSING",
                "selectable": bool(candidate.get("selectable", False)),
            })
            if candidate.get("selection_reason"):
                entry["evidence"] = str(candidate["selection_reason"])
            decisions.append(entry)
            continue
        if not creative_required and str(candidate.get("requires", "")) == "creative":
            entry.update({"decision": "omitted", "reason": "IRRELEVANT_TO_TASK"})
            entry["evidence"] = "the run does not require creative evidence"
            decisions.append(entry)
            continue
        design_reason = _design_reason(candidate, design_state, characterisation)
        if design_reason is not None:
            reason, evidence = design_reason
            entry.update({"decision": "omitted", "reason": reason})
            entry["evidence"] = evidence
            decisions.append(entry)
            continue
        changed_reason = _changed_file_reason(candidate, characterisation)
        if changed_reason:
            entry.update({"decision": "included", "reason": "RELEVANT_CHANGED_FILE"})
            entry["evidence"] = changed_reason
            decisions.append(entry)
            continue
        cached = _reuse_entry(cache, candidate, stage=stage, revision_hash=revision_hash) if run_root is not None else None
        if cached is not None:
            hits += 1
            entry.update({"decision": "included", "reason": "UNCHANGED_CACHED_INPUT", "cached": True})
            reuse[path] = {
                "source_sha256": str(cached.get("source_sha256", "")),
                "content_sha256": str(cached.get("content_sha256", "")),
                "size": cached.get("size"),
                "mtime_ns": cached.get("mtime_ns"),
            }
        else:
            if run_root is not None and (cache.get("entries") or {}).get(path):
                misses += 1
                invalidated.append({"path": path, "reason": "source changed since the cached delivery"})
            entry.update({"decision": "included", "reason": "REQUIRED_BY_TASK_TYPE"})
        decisions.append(entry)

    decision = {
        "schema_version": contracts.SCHEMA_ADAPTIVE,
        "decision_id": contracts.new_record_id("ctx"),
        "run_id": str(state.get("run_id", "")),
        "stage": str(stage),
        "task_id": str((characterisation or {}).get("task_id", "")),
        "characterisation_id": str((characterisation or {}).get("characterisation_id", "")),
        "decisions": decisions,
        "candidates": len(candidates),
        "included": sum(1 for item in decisions if item["decision"] == "included"),
        "omitted": sum(1 for item in decisions if item["decision"] == "omitted"),
        "cache": {"hits": hits, "misses": misses, "invalidated": invalidated},
        "reuse": reuse,
        "deduplicate": bool(deduplicate),
        "policy_version": contracts.POLICY_VERSION,
        "recorded_at": contracts.utc_now(),
    }
    problems = contracts.context_decision_problems(decision)
    if problems:
        raise ContractError("context decision is malformed: " + "; ".join(problems))
    return decision


def plan(decision: Mapping, *, allow_omission: bool = True) -> dict:
    """The transport-facing plan. It can omit or reuse; it can never add."""
    omissions = {
        str(item.get("path")): str(item.get("reason"))
        for item in (decision.get("decisions") or [])
        if str(item.get("decision")) == "omitted" and item.get("removable") and allow_omission
    }
    return {
        "decision_id": str(decision.get("decision_id", "")),
        "policy_version": str(decision.get("policy_version", contracts.POLICY_VERSION)),
        "omit": omissions,
        "reuse": {str(key): dict(value) for key, value in (decision.get("reuse") or {}).items()},
        "deduplicate": bool(decision.get("deduplicate", True)),
    }


def validate_plan_values(plan: Mapping) -> list[str]:
    """Structural validation of a plan before it reaches the transport."""
    problems: list[str] = []
    if not isinstance(plan, Mapping):
        return ["context plan is not an object"]
    omit = plan.get("omit")
    if not isinstance(omit, Mapping):
        problems.append("context plan has no omission map")
    else:
        for path, reason in omit.items():
            if str(reason) not in CONTEXT_REASONS:
                problems.append(f"context plan omission has an unknown reason: {path} -> {reason}")
    reuse = plan.get("reuse")
    if not isinstance(reuse, Mapping):
        problems.append("context plan has no reuse map")
    else:
        for path, value in reuse.items():
            if not isinstance(value, Mapping):
                problems.append(f"context plan reuse entry is malformed: {path}")
                continue
            if not str(value.get("source_sha256", "")):
                problems.append(f"context plan reuse entry has no source hash: {path}")
    return problems


def record(state: dict, decision: Mapping) -> dict:
    problems = contracts.context_decision_problems(decision)
    if problems:
        raise ContractError("context decision is malformed: " + "; ".join(problems))
    state.setdefault("context_decisions", []).append(dict(decision))
    if len(state["context_decisions"]) > 200:
        state["context_decisions"] = state["context_decisions"][-200:]
    return dict(decision)


def finalise(decision: Mapping, manifest: Mapping) -> dict:
    """Reconcile the plan with what the transport actually delivered.

    The recorded decision is the *observed* outcome: a source the transport
    dropped (a duplicate, a stale input) is recorded as omitted with the
    transport's own machine-readable reason, and a source the transport added
    (a derived or restart-context source) is recorded as included. The plan is
    evidence of intent; the manifest is evidence of what happened.
    """
    planned = {str(item.get("path")): dict(item) for item in (decision.get("decisions") or [])}
    observed: list[dict] = []
    seen: set[str] = set()
    for source in (manifest.get("sources") or []):
        if not isinstance(source, Mapping):
            continue
        path = str(source.get("path", ""))
        if not path:
            continue
        seen.add(path)
        planned_item = planned.get(path, {})
        delivered = bool(source.get("delivered", True))
        reason = str(source.get("context_reason", "") or "")
        if reason not in CONTEXT_REASONS:
            reason = "REQUIRED_BY_STAGE" if delivered else str(planned_item.get("reason", "MISSING"))
            if reason not in CONTEXT_REASONS:
                reason = "MISSING"
        entry = {
            "label": str(source.get("label", "") or planned_item.get("label", "") or Path(path).name),
            "path": path,
            "kind": str(source.get("kind", "") or planned_item.get("kind", "")),
            "bucket": str(planned_item.get("bucket", "delivered")),
            "removable": bool(planned_item.get("removable")),
            "decision": "included" if delivered else "omitted",
            "reason": reason,
        }
        if source.get("duplicate_of"):
            entry["duplicate_of"] = str(source["duplicate_of"])
        if planned_item.get("cached"):
            entry["cached"] = True
        observed.append(entry)
    for path, item in planned.items():
        if path in seen:
            continue
        observed.append(dict(item))
    result = dict(decision)
    result["decisions"] = observed
    result["included"] = sum(1 for item in observed if item.get("decision") == "included")
    result["omitted"] = sum(1 for item in observed if item.get("decision") == "omitted")
    result["packet_id"] = str(manifest.get("packet_id", ""))
    result["packet_sha256"] = str(manifest.get("packet_sha256", ""))
    problems = contracts.context_decision_problems(result)
    if problems:
        raise ContractError("finalised context decision is malformed: " + "; ".join(problems))
    return result


def update_cache(run_root: Path, state: dict, decision: Mapping, manifest: Mapping, *, revision_hash: str = "") -> dict:
    """Update the cache from *observed* delivery, and return the new cache.

    Only sources that were actually delivered are cached. A forbidden source can
    therefore never enter the cache, and an omitted source is dropped from it.
    """
    cache = load_cache(Path(run_root))
    entries = dict(cache.get("entries") or {})
    # The entry is stamped with the revision of the packet that *delivered* it
    # (the manifest's own baseline), because a child inherits its parent's
    # baseline only when the parent is the same stage. A same-stage retry then
    # reads with exactly the revision the previous attempt wrote.
    delivered_revision = str((manifest.get("project_baseline") or {}).get("head", "") or revision_hash)
    delivered: dict[str, dict] = {}
    for source in (manifest.get("sources") or []):
        if not isinstance(source, Mapping):
            continue
        if not source.get("delivered", True):
            continue
        path = str(source.get("path", ""))
        if not path:
            continue
        delivered[path] = {
            "label": str(source.get("label", "")),
            "kind": str(source.get("kind", "")),
            "source_sha256": str(source.get("source_sha256", "")),
            "content_sha256": str(source.get("content_sha256", "")),
            "decision": "included",
        }
    for item in (decision.get("decisions") or []):
        path = str(item.get("path", ""))
        if str(item.get("decision")) != "included":
            entries.pop(path, None)
            continue
        record_value = delivered.get(path)
        if record_value is None:
            continue
        identity = stat_identity(Path(path))
        entries[path] = {
            **record_value,
            "size": identity.get("size"),
            "mtime_ns": identity.get("mtime_ns"),
            "stage": str(decision.get("stage", "")),
            "policy_version": contracts.POLICY_VERSION,
            "revision_hash": delivered_revision,
            "decision_id": str(decision.get("decision_id", "")),
            "recorded_at": contracts.utc_now(),
        }
    cache["entries"] = entries
    save_cache(Path(run_root), cache)
    return cache


def summarise(decision: Mapping) -> dict:
    """Deterministic metrics for one decision (bytes are measured, never estimated)."""
    return {
        "candidates": int(decision.get("candidates", 0) or 0),
        "included": int(decision.get("included", 0) or 0),
        "omitted": int(decision.get("omitted", 0) or 0),
        "cache_hits": int(((decision.get("cache") or {}).get("hits", 0)) or 0),
        "cache_misses": int(((decision.get("cache") or {}).get("misses", 0)) or 0),
        "invalidations": len(((decision.get("cache") or {}).get("invalidated", []) or [])),
    }


def describe(decision: Mapping) -> str:
    metrics = summarise(decision)
    return (
        f"context {decision.get('decision_id')}: {metrics['included']} included, "
        f"{metrics['omitted']} omitted, {metrics['cache_hits']} cache hit(s), "
        f"{metrics['invalidations']} invalidation(s)"
    )


__all__ = [
    "CACHE_NAME",
    "CACHE_SCHEMA",
    "REMOVABLE_BUCKETS",
    "cache_path",
    "stat_identity",
    "load_cache",
    "save_cache",
    "candidate_is_removable",
    "design_source_state",
    "decide",
    "finalise",
    "plan",
    "validate_plan_values",
    "record",
    "update_cache",
    "summarise",
    "describe",
]
