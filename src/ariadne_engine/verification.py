"""Verification records, levels and freshness (AR-203 T4/T7).

A verification record answers one question about one claim:

* what claim was verified, about which subject;
* what produced the claim (the execution that observed it);
* what evidence was examined, and what the engine re-hashed itself;
* what was reproduced, and by which execution;
* which revision and which dependency fingerprints it applies to;
* what was actually established, at which level;
* what remains unverified.

Levels never skip and never rise by re-hashing a declaration:

``DECLARED``                 a party asserted it; no evidence was examined
``OBSERVED``                 the engine examined real evidence in a named execution
``REPRODUCED``               the same execution re-produced the observed result from a new artifact
``INDEPENDENTLY_REPRODUCED`` a different engine execution re-produced it
``VERIFIED``                 independently reproduced against the current revision and dependencies
``STALE``                    was established, but a bound dependency has since changed
``UNVERIFIED``               nothing was established

Freshness is dependency-specific: a record names the fingerprints it was
established against, and it becomes stale only when one of *those* dependencies
changes, not when anything in the project changes.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Mapping, Sequence

from . import contracts
from .contracts import (
    VERIFICATION_LEVELS,
    VERIFICATION_LEVEL_ORDER,
    ContractError,
)

DEFAULT_LIMITATION = (
    "the engine can verify what it can observe and re-produce; it cannot prove a human's intent or "
    "a remote system's internal state"
)


def is_sha256(value: str) -> bool:
    return bool(re.fullmatch(r"[0-9a-f]{64}", str(value or "")))


def records(state: Mapping) -> list[dict]:
    values = state.get("verifications")
    if not isinstance(values, list):
        return []
    return [item for item in values if isinstance(item, Mapping)]


def verification(state: Mapping, verification_id: str) -> dict | None:
    for record in records(state):
        if str(record.get("verification_id", "")) == str(verification_id):
            return record
    return None


def for_subject(state: Mapping, subject: str) -> list[dict]:
    return [record for record in records(state) if str(record.get("subject", "")) == str(subject)]


def dependencies_digest(dependencies: Mapping | None) -> str:
    """A stable digest over one dependency fingerprint set."""
    payload = {str(key): str(value) for key, value in dict(dependencies or {}).items()}
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _artifact_evidence(rows: Sequence[Mapping | str], *, label: str) -> tuple[list[dict], list[str]]:
    """Normalise evidence rows and re-hash every artifact the engine can read."""
    normalised: list[dict] = []
    problems: list[str] = []
    for item in rows or ():
        row = {str(key): value for key, value in item.items()} if isinstance(item, Mapping) else {"detail": str(item)}
        path_value = str(row.get("path", "") or "")
        digest = str(row.get("sha256", "") or "")
        if path_value:
            path = Path(path_value)
            if not path.is_file():
                problems.append(f"{label} evidence artifact does not exist: {path}")
                continue
            actual = hashlib.sha256(path.read_bytes()).hexdigest()
            if digest and digest != actual:
                problems.append(f"{label} evidence artifact changed after it was recorded: {path}")
                continue
            row["sha256"] = actual
            row["path"] = str(path.resolve())
        elif digest:
            problems.append(f"{label} evidence records a digest with no artifact the engine can re-read")
            continue
        normalised.append(row)
    return normalised, problems


def _reproduction_evidence(artifact: Mapping, *, original_path: str, label: str) -> tuple[dict, list[str]]:
    """The artifact a reproduction produced: it must be a real, different file."""
    path_value = str((artifact or {}).get("path", "") or "")
    digest = str((artifact or {}).get("sha256", "") or "")
    if not path_value:
        return {}, [f"{label} needs the artifact the verifier re-produced, not only a digest"]
    path = Path(path_value)
    if not path.is_file():
        return {}, [f"{label} reproduction artifact does not exist: {path}"]
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest and digest != actual:
        return {}, [f"{label} reproduction artifact does not match the digest it declares"]
    if str(path.resolve()) == str(Path(original_path).resolve()):
        return {}, [
            f"{label} re-opened the original artifact; re-hashing one file is not re-production"
        ]
    return {"path": str(path.resolve()), "sha256": actual}, []


def create(
    state: dict,
    *,
    subject: str,
    claim: str,
    level: str,
    method: str,
    execution_id: str = "",
    verifier_execution_id: str = "",
    revision: str = "",
    evidence: Sequence[Mapping | str] = (),
    reproduced_artifact: Mapping | None = None,
    dependencies: Mapping | None = None,
    limitations: Sequence[str] = (),
    task_id: str = "",
    subject_type: str = "",
    observed_digest: str = "",
    observed_anchor: str = "",
) -> dict:
    """Create one verification record. Each level carries its own obligations."""
    if level not in VERIFICATION_LEVELS:
        raise ContractError(f"unsupported verification level: {level!r}")
    if level in ("STALE",):
        raise ContractError("STALE is a freshness verdict, not a level a record is created at")
    if not str(subject or "").strip() or not str(claim or "").strip():
        raise ContractError("a verification record needs the subject and the claim it verifies")
    if not str(method or "").strip():
        raise ContractError("a verification record needs the method that established it")
    from . import provenance

    problems: list[str] = []
    observed_execution: dict | None = None
    verifier_execution: dict | None = None
    if VERIFICATION_LEVEL_ORDER[level] >= VERIFICATION_LEVEL_ORDER["OBSERVED"]:
        if not str(revision or "").strip():
            problems.append(f"a verification at {level} must be bound to a revision")
        if str(execution_id or "").strip():
            observed_execution = provenance.require_engine_execution(
                state, execution_id, label=f"a {level} verification",
            )
        elif not str(observed_anchor or "").strip():
            problems.append(
                f"a verification at {level} needs the engine execution that observed it, or the "
                "engine-recorded anchor the observation came from"
            )
    else:
        observed_execution = None
    evidence_rows, evidence_problems = _artifact_evidence(evidence, label="verification")
    problems.extend(evidence_problems)
    if VERIFICATION_LEVEL_ORDER[level] >= VERIFICATION_LEVEL_ORDER["OBSERVED"] and not evidence_rows:
        problems.append(f"a verification at {level} must examine at least one piece of real evidence")
    if VERIFICATION_LEVEL_ORDER[level] >= VERIFICATION_LEVEL_ORDER["REPRODUCED"]:
        if not observed_digest:
            observed = [row.get("sha256") for row in evidence_rows if row.get("sha256")]
            observed_digest = str(observed[0]) if observed else ""
        if not is_sha256(observed_digest):
            problems.append(f"a verification at {level} must record the observed digest it reproduced")
        reproduction, reproduction_problems = _reproduction_evidence(
            reproduced_artifact or {},
            original_path=str((evidence_rows[0] or {}).get("path", "")) if evidence_rows else "",
            label=f"a {level} verification",
        )
        problems.extend(reproduction_problems)
        reproduced_digest = str(reproduction.get("sha256", ""))
        if observed_digest and reproduced_digest and observed_digest != reproduced_digest:
            problems.append(
                "the re-produced artifact does not match the observed artifact; a mismatch is a "
                "finding, not a verification"
            )
    else:
        reproduction = {}
        reproduced_digest = ""
    if VERIFICATION_LEVEL_ORDER[level] >= VERIFICATION_LEVEL_ORDER["INDEPENDENTLY_REPRODUCED"]:
        verifier_execution = provenance.require_engine_execution(
            state, verifier_execution_id, label=f"a {level} verification",
        )
        if observed_execution is not None and str(observed_execution.get("execution_id")) == str(
            verifier_execution.get("execution_id")
        ):
            problems.append(
                f"a verification at {level} names one execution as both observer and independent verifier"
            )
    if level == "REPRODUCED" and verifier_execution_id:
        verifier_execution = provenance.require_engine_execution(
            state, verifier_execution_id, label="a REPRODUCED verification",
        )
        if observed_execution is None or str(verifier_execution.get("execution_id")) != str(
            observed_execution.get("execution_id")
        ):
            problems.append(
                "REPRODUCED means the observing execution re-produced its own result; a different "
                "execution is INDEPENDENTLY_REPRODUCED, not REPRODUCED"
            )
    dependency_map = {str(key): str(value) for key, value in dict(dependencies or {}).items()}
    if level == "VERIFIED":
        if not dependency_map:
            problems.append(
                "a VERIFIED record must name the dependency fingerprints it was established against, "
                "so its currentness can be re-evaluated"
            )
    if problems:
        raise ContractError("verification refused: " + "; ".join(dict.fromkeys(problems)))
    record = {
        "schema_version": contracts.SCHEMA_VERIFICATION,
        "verification_id": contracts.new_record_id("vrf"),
        "run_id": str(state.get("run_id", "")),
        "task_id": str(task_id),
        "subject_type": str(subject_type),
        "subject": str(subject),
        "claim": str(claim),
        "method": str(method),
        "level": str(level),
        "execution_id": str(execution_id),
        "observed_anchor": str(observed_anchor),
        "verifier_execution_id": str(verifier_execution_id),
        "revision": str(revision),
        "evidence": evidence_rows,
        "observed_digest": str(observed_digest),
        "reproduced_digest": str(reproduced_digest),
        "reproduction": dict(reproduction),
        "dependencies": dependency_map,
        "dependencies_digest": dependencies_digest(dependency_map),
        "freshness": "CURRENT",
        "superseded_by": "",
        "limitations": [str(item) for item in (limitations or ()) if str(item).strip()] or [DEFAULT_LIMITATION],
        "recorded_at": contracts.utc_now(),
        "provenance": {
            "created_by": "engine",
            "policy_version": contracts.POLICY_VERSION,
            "contract_version": contracts.VERIFICATION_CONTRACT,
        },
    }
    problems = contracts.verification_record_problems(record)
    if problems:
        raise ContractError("verification record is malformed: " + "; ".join(problems))
    contracts.require_collection_capacity(state, "verifications")
    state.setdefault("verifications", []).append(record)
    return record


def re_full_sha256(value: str) -> bool:
    import re

    return bool(re.fullmatch(r"[0-9a-f]{64}", str(value or "")))


def freshness_of(record: Mapping, *, current: Mapping | None = None) -> dict:
    """Evaluate one record's freshness against current dependency fingerprints.

    ``current`` maps dependency names to their fingerprints now. A dependency the
    record does not name cannot make it stale (that is the point of
    dependency-specific fingerprints); a named dependency missing from ``current``
    makes freshness ``UNKNOWN`` rather than guessing.
    """
    if str(record.get("superseded_by", "")):
        return {"state": "SUPERSEDED", "problems": [f"superseded by {record.get('superseded_by')}"]}
    dependencies = record.get("dependencies") if isinstance(record.get("dependencies"), Mapping) else {}
    if not dependencies:
        if VERIFICATION_LEVEL_ORDER.get(str(record.get("level", "")), 0) >= VERIFICATION_LEVEL_ORDER["VERIFIED"]:
            return {"state": "UNKNOWN", "problems": ["the record names no dependency fingerprints"]}
        return {"state": "UNKNOWN", "problems": ["no dependency fingerprints were recorded"]}
    if current is None:
        return {"state": "UNKNOWN", "problems": ["no current dependency fingerprints were supplied"]}
    changed: list[str] = []
    unknown: list[str] = []
    for name, expected in dependencies.items():
        if name not in current:
            unknown.append(name)
        elif str(current[name]) != str(expected):
            changed.append(name)
    if changed:
        return {"state": "STALE", "problems": [f"dependency changed: {name}" for name in sorted(changed)]}
    if unknown:
        return {"state": "UNKNOWN", "problems": [f"dependency not supplied: {name}" for name in sorted(unknown)]}
    return {"state": "CURRENT", "problems": []}


def refresh(state: dict, verification_id: str, *, current: Mapping) -> dict:
    """Re-evaluate one record's freshness and record the verdict.

    A record that goes stale answers as ``STALE`` while ``established_level`` keeps
    what it once established. When its dependencies match again the level is
    restored from that history — the evidence itself never changed, only the
    currentness verdict — and the restoration is recorded.
    """
    record = verification(state, verification_id)
    if record is None:
        raise ContractError(f"no verification record matches {verification_id!r}")
    verdict = freshness_of(record, current=current)
    record["freshness"] = verdict["state"]
    record["freshness_checked_at"] = contracts.utc_now()
    if verdict["state"] == "STALE":
        if str(record.get("level", "")) != "STALE":
            record["established_level"] = str(record.get("level", ""))
        record["level"] = "STALE"
    elif verdict["state"] == "CURRENT" and str(record.get("level", "")) == "STALE":
        restored = str(record.get("established_level", "") or "UNVERIFIED")
        record["level"] = restored
        record["restored_at"] = contracts.utc_now()
    problems = contracts.verification_record_problems(record)
    if problems:
        raise ContractError("verification record would be malformed: " + "; ".join(problems))
    return record


def effective_level(record: Mapping, *, current: Mapping | None = None) -> str:
    """The level this record answers with *now*.

    A stale record answers as ``STALE`` even though ``established_level`` keeps
    what it once established, because a stale artifact may remain useful history
    but cannot satisfy a current requirement.
    """
    if str(record.get("superseded_by", "")):
        return "STALE"
    if current is not None:
        verdict = freshness_of(record, current=current)
        if verdict["state"] != "CURRENT":
            return "STALE" if verdict["state"] == "STALE" else str(record.get("level", "UNKNOWN"))
    return str(record.get("level", "UNVERIFIED"))


def status(state: Mapping, *, subject: str = "", current: Mapping | None = None) -> dict:
    """The verification status for one subject (or the whole run)."""
    rows = for_subject(state, subject) if subject else records(state)
    best = "UNVERIFIED"
    details: list[dict] = []
    for record in rows:
        level = effective_level(record, current=current)
        details.append({
            "verification_id": record.get("verification_id"),
            "subject": record.get("subject"),
            "claim": record.get("claim"),
            "level": level,
            "established_level": record.get("established_level", record.get("level")),
            "freshness": record.get("freshness"),
            "method": record.get("method"),
            "revision": record.get("revision"),
        })
        if VERIFICATION_LEVEL_ORDER.get(level, 0) > VERIFICATION_LEVEL_ORDER.get(best, 0):
            best = level
    return {
        "subject": str(subject),
        "records": len(rows),
        "level": best,
        "details": details,
    }


def supersede(state: dict, verification_id: str, *, by: str) -> dict:
    """Mark one record superseded by a later one. History is kept, never deleted."""
    record = verification(state, verification_id)
    if record is None:
        raise ContractError(f"no verification record matches {verification_id!r}")
    successor = verification(state, by)
    if successor is None:
        raise ContractError(f"no verification record matches the successor {by!r}")
    if str(successor.get("subject")) != str(record.get("subject")):
        raise ContractError("a verification record can only be superseded by one for the same subject")
    record["superseded_by"] = str(by)
    record["freshness"] = "SUPERSEDED"
    return record


def summarise(state: Mapping) -> dict:
    """Deterministic verification counters."""
    rows = records(state)
    counts = {level.lower(): 0 for level in VERIFICATION_LEVELS}
    for record in rows:
        counts[str(record.get("level", "")).lower()] = counts.get(str(record.get("level", "")).lower(), 0) + 1
    return {
        "records": len(rows),
        "levels": counts,
        "stale": sum(1 for record in rows if str(record.get("freshness")) == "STALE"),
        "verified": counts.get("verified", 0),
        "independent": counts.get("independently_reproduced", 0) + counts.get("verified", 0),
    }


def describe(record: Mapping) -> str:
    return (
        f"{record.get('verification_id')} {record.get('level')} ({record.get('freshness')}) "
        f"{record.get('subject')}: {record.get('claim')}"
    )


def relevance_advice(
    state: dict,
    *,
    requirement: str,
    claim: str,
    provenance: Mapping | str = "",
    freshness: str = "",
    verification_id: str = "",
    provider=None,
    **options,
) -> dict:
    """Bounded advice on whether one evidence claim supports a requirement.

    Freshness and provenance are checked deterministically first and can never
    be overridden by the advice; stale evidence is ``IRRELEVANT`` regardless of
    what any provider would answer. When a verification record id is given, its
    engine-computed freshness is used instead of a caller's claim.
    """
    record = verification(state, verification_id) if verification_id else None
    if record is not None:
        freshness = str(freshness_of(record).get("state", "") or freshness)
        provenance = provenance or {
            "method": str(record.get("method", "")),
            "execution_id": str(record.get("execution_id", "")),
            "revision": str(record.get("revision", "")),
        }
        claim = claim or str(record.get("claim", ""))
    from .decisions import integrations

    return integrations.evidence_relevance(
        state,
        requirement=str(requirement),
        claim=str(claim),
        provenance=provenance,
        freshness=str(freshness or "UNKNOWN"),
        provider=provider,
        **options,
    )


__all__ = [
    "DEFAULT_LIMITATION",
    "records",
    "verification",
    "for_subject",
    "dependencies_digest",
    "create",
    "freshness_of",
    "refresh",
    "effective_level",
    "status",
    "supersede",
    "summarise",
    "describe",
    "relevance_advice",
]
