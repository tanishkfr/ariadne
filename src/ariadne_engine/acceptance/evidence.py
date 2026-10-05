"""Evidence: what was observed, by whom, about which revision, and how it bears.

Ariadne had evidence before AR-223 -- AR-203 verification records, AR-222D rendered
evidence sets and capture artifacts, AR-220 reference artefacts. This module does not
replace any of it. It introduces the one thing none of them had: an evidence item bound
to a **requirement**, so that "is this enough?" becomes answerable instead of rhetorical.

Four properties, each closing a specific way acceptance goes wrong.

**Requirement-specific strength.** There is no global ranking. :func:`assess` asks what
the evidence does *to one requirement under that requirement's declared policy*. A build
result directly establishes "it compiles" and establishes nothing whatsoever about
whether a button works. A screenshot establishes nothing about persistence. A unit test
establishes nothing about whether the result feels premium, and
:mod:`ariadne_engine.acceptance.requirements` will say so out loud rather than accept it.

**Producer identity is preserved.** The worker may produce evidence -- running tests,
supplying a capture, pasting a log -- and that evidence is recorded with the worker named
as its producer. What it cannot do is mint independent acceptance; the distinction is
enforced at acceptance time by :mod:`ariadne_engine.acceptance.security`, and it is
recorded here so that enforcement has something to read.

**Freshness is first-class, and specific.** Every evidence item names the work digest and
contract revision it observed. :func:`freshness` answers ``CURRENT`` / ``STALE`` /
``UNKNOWN`` against the digest now, reusing the same four-state vocabulary AR-203
already uses for verification records, and an item whose digest does not match can never
establish a current requirement however convincing its contents.

**Conflict is recorded, not resolved by fiat.** Support and contradiction can both be
present and current. :func:`conflicts` names them. Resolution is a *policy* question
answered by the requirement: if one of them is ``AUTHORITATIVE`` for that requirement it
settles the matter; if not, the honest verdict is ``NEEDS_HUMAN``, because a system that
silently picks a side in that situation is not verifying, it is choosing.

**Laundering fails here, not later.** Artefact digests are recorded at creation and
re-checked on read. A renamed file, an edited digest, a stale capture presented as
current, or a worker's own screenshot relabelled as an independent review are each
refused at the boundary, with a named reason.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from .. import contracts
from ..contracts import ContractError, new_record_id, require_collection_capacity, utc_now

EVIDENCE_VERSION = "ar-223-evidence-1"
"""The acceptance-evidence record shape."""

COLLECTION = "acceptance_evidence"
"""Where acceptance evidence lives in the run state."""

ARTIFACT_KIND_RELEVANCE = {
    "TEST": ("tests/", "test_", ".test.", ".spec."),
    "BUILD": ("dist/", "build/", "typecheck"),
    "STATIC_ANALYSIS": ("lint", "tsc", "mypy", "ruff"),
    "DIFF": (".diff", ".patch"),
    "RUNTIME": (".log", "trace", "runtime"),
    "RENDER": (".png", ".jpg", ".jpeg", ".webp"),
    "SCREENSHOT": (".png", ".jpg", ".jpeg", ".webp"),
    "INTERACTION": ("trace", "session", ".jsonl"),
    "ACCESSIBILITY": ("axe", "a11y", "accessibility"),
    "REVIEW": ("critique", "review", "reviewer"),
    "PERFORMANCE": ("trace.json", "profile", "benchmark"),
    "PROVENANCE": ("manifest", "lock", "provenance"),
}
"""Which artefact names plausibly belong to which evidence kind.

Used only as a *warning*, never as a verdict. An artefact whose name suggests one kind
while the record claims another is flagged for a human to look at, because the commonest
laundering route is a good-looking capture relabelled as a performance measurement. It
is not proof of anything on its own -- ``trace.json`` is genuinely both an interaction
trace and a performance profile -- so it informs ``concerns`` rather than the verdict.
"""


def artifact_digest(path: Path | str) -> str:
    """The sha256 of an artefact the engine can actually re-read."""
    target = Path(path)
    if not target.is_file():
        raise ContractError(f"evidence artefact is not readable: {target}")
    return hashlib.sha256(target.read_bytes()).hexdigest()


def record(
    state: dict,
    *,
    kind: str,
    stance: str,
    producer: str,
    producer_role: str,
    observation: str,
    requirement_ids: Sequence[str],
    artifact_path: str = "",
    artifact_sha256: str = "",
    source_record_id: str = "",
    source_kind: str = "",
    work_digest: str,
    contract_revision: str,
    contract_id: str = "",
    producer_execution: str = "",
    external: bool = False,
    task_id: str = "",
    environment: Mapping[str, Any] | None = None,
    viewport: str = "",
    reviewer_identity: str = "",
    notes: str = "",
) -> dict:
    """Record one piece of evidence about one or more requirements.

    ``stance`` is what the observation does to the requirement -- ``SUPPORTS``,
    ``PARTIALLY_SUPPORTS`` or ``CONTRADICTS`` -- and it is separate from ``kind``, which
    is what sort of observation it is. Conflating the two is how "screenshot > test > diff"
    came to be believed.

    ``requirement_ids`` is mandatory and must resolve. Evidence that is not about
    anything cannot establish anything, and a record without a subject is a record nobody
    can ever check.
    """
    if str(kind) not in contracts.ACCEPTANCE_EVIDENCE_KINDS:
        raise ContractError(f"unsupported evidence kind: {kind!r}")
    if str(stance) not in contracts.EVIDENCE_STANCES_FOR_CLAIM:
        raise ContractError(f"unsupported evidence stance: {stance!r}")
    if str(producer_role) not in contracts.PROOF_ACTOR_ROLES:
        raise ContractError(f"unsupported evidence producer role: {producer_role!r}")
    if not str(producer or "").strip():
        raise ContractError("evidence must name the producer; unattributed evidence cannot be assessed")
    if not str(observation or "").strip():
        raise ContractError("evidence must record what was observed")
    if not str(work_digest or "").strip():
        raise ContractError(
            "evidence must be bound to the work revision it observed. Unbound evidence can never "
            "establish a current requirement"
        )
    from . import requirements as requirements_module

    subjects = [str(item) for item in requirement_ids or () if str(item).strip()]
    if not subjects:
        raise ContractError(
            "evidence must name at least one requirement; evidence about nothing establishes nothing"
        )
    unknown = [
        requirement_id for requirement_id in subjects
        if requirements_module.requirement(state, requirement_id) is None
    ]
    if unknown:
        raise ContractError(
            "evidence names requirement(s) that do not exist: " + ", ".join(sorted(unknown))
        )
    artifact: dict[str, str] = {}
    if artifact_path or artifact_sha256:
        if not artifact_path:
            raise ContractError("evidence naming a digest must also name the artefact it is a digest of")
        resolved = artifact_digest(artifact_path)
        if artifact_sha256 and artifact_sha256 != resolved:
            raise ContractError(
                "evidence artefact does not match the digest it declares. An artefact whose bytes "
                "changed after it was observed is not the observation"
            )
        artifact = {"path": str(Path(artifact_path).resolve()), "sha256": resolved}
    elif source_record_id:
        if str(source_kind) not in contracts.EVIDENCE_SOURCE_KINDS:
            raise ContractError(
                f"unsupported evidence source kind: {source_kind!r}. Evidence that is not an "
                "artefact must name the record it was derived from and what that record is"
            )
    else:
        raise ContractError(
            "evidence must cite a re-readable artefact or the record it was derived from. "
            "Evidence that points at nothing is an assertion, and an assertion is a claim"
        )
    row = {
        "schema_version": contracts.SCHEMA_ACCEPTANCE,
        "evidence_id": new_record_id("evd"),
        "evidence_version": EVIDENCE_VERSION,
        "run_id": str(state.get("run_id", "")),
        "task_id": str(task_id),
        "contract_id": str(contract_id),
        "contract_revision": str(contract_revision),
        "kind": str(kind),
        "stance": str(stance),
        "producer": str(producer),
        "producer_execution": str(producer_execution),
        "producer_role": str(producer_role),
        "requirement_ids": subjects,
        "observation": " ".join(str(observation).split()),
        "work_digest": str(work_digest),
        "artifact": artifact,
        "source_record_id": str(source_record_id),
        "source_kind": str(source_kind or ("ARTIFACT" if artifact else "")),
        "environment": dict(environment or {}),
        "viewport": str(viewport),
        "reviewer_identity": str(reviewer_identity),
        "external": bool(external),
        "state": "CURRENT",
        "superseded_by": "",
        "notes": str(notes),
        "recorded_at": utc_now(),
        "provenance": {
            "created_by": "engine",
            "policy_version": contracts.POLICY_VERSION,
            "contract_version": contracts.ACCEPTANCE_CONTRACT_VERSION,
        },
    }
    problems = contracts.acceptance_evidence_problems(row)
    if problems:
        raise ContractError("acceptance evidence is malformed: " + "; ".join(problems))
    require_collection_capacity(state, COLLECTION)
    state.setdefault(COLLECTION, []).append(row)
    return row


# ------------------------------------------------------------------- retrieval


def evidence(state: Mapping[str, Any]) -> list[dict]:
    return [dict(row) for row in state.get(COLLECTION, []) or [] if isinstance(row, Mapping)]


def by_id(state: Mapping[str, Any], evidence_id: str) -> dict | None:
    for row in evidence(state):
        if str(row.get("evidence_id", "")) == str(evidence_id):
            return row
    return None


def for_requirement(state: Mapping[str, Any], requirement_id: str) -> list[dict]:
    return [
        row for row in evidence(state)
        if str(requirement_id) in (row.get("requirement_ids") or ())
    ]


def producers(state: Mapping[str, Any]) -> dict[str, list[dict]]:
    """Evidence grouped by producing identity, with the roles each one played."""
    table: dict[str, list[dict]] = {}
    for row in evidence(state):
        identity = str(row.get("producer_execution") or row.get("producer", ""))
        if not identity:
            continue
        table.setdefault(identity, []).append({
            "evidence_id": str(row.get("evidence_id", "")),
            "producer_role": str(row.get("producer_role", "")),
            "kind": str(row.get("kind", "")),
            "requirement_ids": list(row.get("requirement_ids") or ()),
        })
    return table


# ------------------------------------------------------------------- freshness


def freshness(
    row: Mapping[str, Any],
    *,
    work_digest: str = "",
    contract_revision: str = "",
    artifact_root: Path | str | None = None,
) -> dict:
    """Whether one evidence item can speak about the work as it is now.

    ``CURRENT`` / ``STALE`` / ``UNKNOWN`` / ``SUPERSEDED`` -- the four-state vocabulary
    AR-203 already established for verification records, reused rather than reinvented.

    ``UNKNOWN`` rather than ``CURRENT`` when the caller supplies no current digest: no
    comparison is not a passing comparison.
    """
    if str(row.get("superseded_by", "")):
        return {"state": "SUPERSEDED", "problems": [f"superseded by {row.get('superseded_by')}"]}
    problems: list[str] = []
    if not work_digest:
        return {"state": "UNKNOWN", "problems": ["no current work digest was supplied"]}
    if str(row.get("work_digest", "")) != str(work_digest):
        problems.append(
            f"evidence observed work digest {row.get('work_digest')}, not the current {work_digest}"
        )
    if contract_revision and str(row.get("contract_revision", "")) != str(contract_revision):
        problems.append(
            f"evidence was recorded against contract revision {row.get('contract_revision')}, "
            f"not the current {contract_revision}"
        )
    artifact = row.get("artifact") if isinstance(row.get("artifact"), Mapping) else {}
    if artifact and artifact_root is not None:
        target = Path(artifact_root) / str(artifact.get("path", ""))
        resolved = Path(str(artifact.get("path", "")))
        if not resolved.is_file() and not target.is_file():
            problems.append("the evidence artefact is no longer readable")
        else:
            actual = artifact_digest(resolved if resolved.is_file() else target)
            if actual != str(artifact.get("sha256", "")):
                problems.append(
                    "the evidence artefact's bytes differ from the digest recorded when it was "
                    "observed"
                )
    if problems:
        return {"state": "STALE", "problems": problems}
    return {"state": "CURRENT", "problems": []}


def refresh(
    state: dict,
    *,
    work_digest: str,
    contract_revision: str = "",
    artifact_root: Path | str | None = None,
) -> dict:
    """Re-evaluate every item's freshness against the work as it is now.

    Mutates the recorded ``state`` field and nothing else. The observation itself never
    changes -- only the verdict about whether it still applies -- and the previous value
    is kept in ``previous_state`` so the transition is readable afterwards.
    """
    summary: dict[str, int] = {name: 0 for name in contracts.FRESHNESS_STATES}
    moved: list[dict] = []
    index = 0
    for row in state.get(COLLECTION, []) or []:
        verdict = freshness(
            row, work_digest=work_digest,
            contract_revision=contract_revision, artifact_root=artifact_root,
        )
        updated = dict(row)
        if str(updated.get("state", "")) != verdict["state"]:
            updated["previous_state"] = str(updated.get("state", ""))
        updated["state"] = verdict["state"]
        updated["freshness_problems"] = verdict["problems"]
        updated["freshness_checked_at"] = utc_now()
        state[COLLECTION][index] = updated
        summary[verdict["state"]] = summary.get(verdict["state"], 0) + 1
        if verdict["state"] != "CURRENT":
            moved.append({"evidence_id": updated.get("evidence_id"), "state": verdict["state"],
                          "problems": verdict["problems"]})
        index += 1
    return {"work_digest": str(work_digest), "states": summary, "not_current": moved}


def current(
    state: Mapping[str, Any],
    *,
    requirement_id: str = "",
    work_digest: str = "",
    contract_revision: str = "",
) -> list[dict]:
    """Only the evidence that is current for this work, by the recorded state.

    Deliberately reads the *recorded* state rather than recomputing, so a caller that has
    not refreshed is told the truth about what the state says -- an item recorded as
    ``CURRENT`` whose artefact was later edited is caught by :func:`refresh`, not hidden
    here.
    """
    rows = [
        row for row in evidence(state)
        if str(row.get("state", "CURRENT")) == "CURRENT" and not str(row.get("superseded_by", ""))
    ]
    if requirement_id:
        rows = [row for row in rows if str(requirement_id) in (row.get("requirement_ids") or ())]
    if work_digest:
        rows = [row for row in rows if str(row.get("work_digest", "")) == str(work_digest)]
    if contract_revision:
        rows = [row for row in rows if str(row.get("contract_revision", "")) == str(contract_revision)]
    return rows


def supersede(state: dict, evidence_id: str, *, by: str) -> dict:
    """Mark one item superseded. History is kept, never deleted."""
    row = by_id(state, evidence_id)
    if row is None:
        raise ContractError(f"no acceptance evidence is recorded with id {evidence_id!r}")
    if not str(by or "").strip():
        raise ContractError("superseding evidence must name what superseded it")
    for index, candidate in enumerate(state.get(COLLECTION, []) or []):
        if str(candidate.get("evidence_id", "")) == str(evidence_id):
            state[COLLECTION][index] = {
                **candidate, "state": "SUPERSEDED", "superseded_by": str(by),
            }
            return state[COLLECTION][index]
    raise ContractError(f"no acceptance evidence is recorded with id {evidence_id!r}")


# ------------------------------------------------------ requirement-specific read


def assess(
    requirement_record: Mapping[str, Any],
    rows: Sequence[Mapping[str, Any]],
) -> dict:
    """What the available evidence establishes for one requirement, per its policy.

    The whole of the sufficiency question, deterministically. Returns which policy
    positions were met, which are outstanding, what is supporting, what is contradicting,
    and any conflict -- but **no verdict**. The verdict belongs to
    :mod:`ariadne_engine.acceptance.decisions`, because deciding is a different act from
    measuring and keeping them apart is what stops a measurement being reported as a
    conclusion.
    """
    from . import requirements as requirements_module

    policy = requirement_record.get("evidence_policy") if isinstance(
        requirement_record.get("evidence_policy"), Mapping) else {}
    met: list[str] = []
    outstanding: list[str] = []
    supporting: list[dict] = []
    partial: list[dict] = []
    contradicting: list[dict] = []
    ignored: list[dict] = []
    by_kind_support: dict[str, list[dict]] = {}
    for stance_kind in contracts.EVIDENCE_STANCES:
        for kind in requirements_module.stance_kinds(requirement_record, stance_kind):
            usable = [
                row for row in rows
                if str(row.get("kind", "")) == kind
                and str(row.get("stance", "")) in contracts.EVIDENCE_STANCES_FOR_CLAIM
            ]
            if stance_kind == "AUTHORITATIVE":
                supporting.extend(row for row in usable if str(row.get("stance")) == "SUPPORTS")
                contradicting.extend(row for row in usable if str(row.get("stance")) == "CONTRADICTS")
                continue
            if stance_kind == "REQUIRED":
                satisfied = [row for row in usable if str(row.get("stance")) == "SUPPORTS"]
                (met if satisfied else outstanding).append(kind)
                by_kind_support[kind] = satisfied
                supporting.extend(satisfied)
                contradicting.extend(row for row in usable if str(row.get("stance")) == "CONTRADICTS")
                continue
            if stance_kind == "SUPPORTING":
                satisfied = [row for row in usable if str(row.get("stance")) == "SUPPORTS"]
                if satisfied:
                    supporting.extend(satisfied)
                ignored.append({
                    "kind": kind,
                    "reason": "supporting evidence does not establish a requirement on its own",
                    "count": len(satisfied),
                })
                continue
            if stance_kind == "INSUFFICIENT_ALONE":
                ignored.append({
                    "kind": kind,
                    "reason": (
                        "the requirement declares this evidence insufficient on its own, so it is "
                        "recorded and never used to establish anything"
                    ),
                    "count": len(usable),
                })
                for row in usable:
                    partial.append(row)
    for row in rows:
        kind = str(row.get("kind", ""))
        stance = str(row.get("stance", ""))
        if stance == "PARTIALLY_SUPPORTS":
            partial.append(row)
        if stance == "CONTRADICTS" and str(requirements_module.stance_of(
                requirement_record, kind)) in ("AUTHORITATIVE", "REQUIRED"):
            contradicting.append(row)
    return {
        "requirement_id": str(requirement_record.get("requirement_id", "")),
        "met": met,
        "outstanding": outstanding,
        "supporting": _ids(supporting),
        "partial": _ids(partial),
        "contradicting": _ids(contradicting),
        "ignored": ignored,
        "by_kind_support": {
            kind: _ids(rows_for_kind) for kind, rows_for_kind in sorted(by_kind_support.items())
        },
        "note": (
            "measurement, not a verdict. Whether this establishes the requirement is "
            "ariadne_engine.acceptance.decisions' judgement, and the two are separate on purpose"
        ),
    }


def _ids(rows: Iterable[Mapping[str, Any]]) -> list[str]:
    """Evidence ids in first-seen order, without repeats.

    The same record can be reached twice -- once through the kind it declares and once
    through the stance it takes -- and a duplicated id in the supporting list reads as
    two independent pieces of evidence when it is one.
    """
    seen: list[str] = []
    for row in rows or ():
        identifier = str(row.get("evidence_id", ""))
        if identifier and identifier not in seen:
            seen.append(identifier)
    return seen


def conflicts(
    requirement_record: Mapping[str, Any],
    rows: Sequence[Mapping[str, Any]],
) -> list[dict]:
    """Evidence that disagrees about the same requirement, both of it current.

    Recorded rather than resolved. The only deterministic resolutions are: an
    ``AUTHORITATIVE`` kind settles the matter, or the requirement is ``NEEDS_HUMAN``.
    Everything else is a case where the engine has no business preferring one
    observation over another.
    """
    from . import requirements as requirements_module

    support = [
        row for row in rows
        if str(row.get("stance")) == "SUPPORTS"
        and str(requirements_module.stance_of(requirement_record, str(row.get("kind", "")))) != "INSUFFICIENT_ALONE"
    ]
    contradict = [
        row for row in rows
        if str(row.get("stance")) == "CONTRADICTS"
        and str(requirements_module.stance_of(requirement_record, str(row.get("kind", "")))) != "INSUFFICIENT_ALONE"
    ]
    if not support or not contradict:
        return []
    authoritative_contradiction = [
        row for row in contradict
        if str(requirements_module.stance_of(requirement_record, str(row.get("kind", "")))) == "AUTHORITATIVE"
    ]
    return [{
        "requirement_id": str(requirement_record.get("requirement_id", "")),
        "supporting": [str(row.get("evidence_id", "")) for row in support],
        "contradicting": [str(row.get("evidence_id", "")) for row in contradict],
        "resolved_by": "AUTHORITATIVE_EVIDENCE" if authoritative_contradiction else "UNRESOLVED",
        "authority": [str(row.get("evidence_id", "")) for row in authoritative_contradiction],
        "problem": (
            "current evidence both supports and contradicts this requirement"
            + (
                f"; {authoritative_contradiction[0].get('evidence_id')} is authoritative for it and "
                "settles the matter"
                if authoritative_contradiction
                else "; no authoritative evidence settles it, so the honest answer is NEEDS_HUMAN "
                     "rather than picking a side"
            )
        ),
    }]


def concerns(row: Mapping[str, Any]) -> list[str]:
    """Plausible laundering shapes worth a human's attention.

    A warning, never a verdict. The artefact-name check catches the commonest route --
    a good-looking capture relabelled as something it is not -- while acknowledging that
    names overlap (``trace.json`` is genuinely both an interaction trace and a
    performance profile), which is why this informs a human rather than deciding.
    """
    found: list[str] = []
    kind = str(row.get("kind", ""))
    artifact = row.get("artifact") if isinstance(row.get("artifact"), Mapping) else {}
    name = str(artifact.get("path", "")).lower()
    if name:
        hints = ARTIFACT_KIND_RELEVANCE.get(kind, ())
        if hints and not any(hint in name for hint in hints):
            found.append(
                f"evidence is recorded as {kind} but its artefact name ({Path(name).name}) matches no "
                f"{kind} artefact this engine recognises"
            )
    if str(row.get("producer_role", "")) == "evidence_producer" and str(
        row.get("producer_role", "")
    ) == str(row.get("reviewer_identity", "")) and str(row.get("reviewer_identity", "")):
        found.append("the artefact's producer and its recorded reviewer are the same identity")
    if str(row.get("external")) == "True" and str(row.get("stance")) == "SUPPORTS":
        found.append(
            "external content is recorded as supporting evidence. External text may be the subject "
            "of a claim; whether it establishes anything is a separate question this record does not "
            "answer"
        )
    return found


def summarise(state: Mapping[str, Any]) -> dict:
    rows = evidence(state)
    by_kind: dict[str, int] = {name: 0 for name in contracts.ACCEPTANCE_EVIDENCE_KINDS}
    by_stance: dict[str, int] = {name: 0 for name in contracts.EVIDENCE_STANCES_FOR_CLAIM}
    by_state: dict[str, int] = {name: 0 for name in contracts.FRESHNESS_STATES}
    for row in rows:
        by_kind[str(row.get("kind", ""))] = by_kind.get(str(row.get("kind", "")), 0) + 1
        by_stance[str(row.get("stance", ""))] = by_stance.get(str(row.get("stance", "")), 0) + 1
        by_state[str(row.get("state", ""))] = by_state.get(str(row.get("state", "")), 0) + 1
    return {
        "evidence": len(rows),
        "by_kind": by_kind,
        "by_stance": by_stance,
        "by_state": by_state,
        "unreadable_artefacts": sum(
            1 for row in rows
            if isinstance(row.get("artifact"), Mapping) and row.get("artifact") and not Path(
                str((row.get("artifact") or {}).get("path", ""))
            ).is_file()
        ),
    }


def problems(state: Mapping[str, Any]) -> list[str]:
    found: list[str] = []
    for row in evidence(state):
        found.extend(
            f"evidence {row.get('evidence_id', '?')}: {problem}"
            for problem in contracts.acceptance_evidence_problems(row)
        )
        found.extend(f"evidence {row.get('evidence_id', '?')}: {problem}" for problem in concerns(row))
    return list(dict.fromkeys(found))


__all__ = [
    "ARTIFACT_KIND_RELEVANCE",
    "COLLECTION",
    "EVIDENCE_VERSION",
    "artifact_digest",
    "assess",
    "by_id",
    "concerns",
    "conflicts",
    "current",
    "evidence",
    "for_requirement",
    "freshness",
    "problems",
    "producers",
    "record",
    "refresh",
    "summarise",
    "supersede",
]