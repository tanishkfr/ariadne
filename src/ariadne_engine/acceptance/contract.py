"""The Contract: a versioned, source-bound interpretation of what was requested.

Everything downstream of this module -- requirements, claims, evidence sufficiency,
acceptance -- assumes one thing exists: an immutable record of *what was asked for*,
bound to *exactly* the request that produced it. Without it, a verification pass is a
verdict about an interpretation nobody can inspect, and the gap between "what the user
wrote" and "what was graded" is invisible.

Four properties, each closing a specific way this goes wrong in practice.

**Bound to the source.** A contract carries a :func:`source_digest` computed over the
*normalised* request text and the references it came with. Normalisation matters: a
re-wrapped paragraph that says the same words is not a new request, and creating a
contract revision for it would turn a formatting difference into a re-verification
obligation. Conversely any change to the words *is* a new revision.

**Versioned, and history is never rewritten.** A materially changed source produces a
new contract with ``revision + 1`` and the previous one moves to ``SUPERSEDED``. The old
contract stays readable and its decisions stay readable, because a decision record that
cannot be read after the fact was never evidence of anything. :func:`assert_history`
checks that this is actually true rather than assuming it.

**Refuses silent reinterpretation.** :func:`decisions_for` will not hand back a
verification decision that was made against a different contract revision or a different
work digest. A pass against contract 1 cannot quietly certify contract 3.

**Cannot be laundered.** :func:`assert_source_binding` compares the recorded digest
against the source as it is now. An agent that replaces the original request with a
weaker one after implementation cannot make that replacement invisible, because the
revision and digest both move and the old contract is still sitting there.

What this module deliberately does not do is *interpret*. It stores an interpretation
someone or something produced, with its provenance. Producing it is
:mod:`ariadne_engine.acceptance.requirements`' problem and that module's rules --
``EXPLICIT`` / ``DERIVED`` / ``ASSUMED`` -- are what stop an interpretation from quietly
becoming forty-seven blocking obligations.
"""

from __future__ import annotations

import hashlib
from typing import Any, Mapping, Sequence

from .. import contracts
from ..contracts import ContractError, new_record_id, normalise, require_collection_capacity, utc_now

CONTRACT_VERSION = "ar-223-contract-1"
"""The contract record shape."""

CONTRACT_CONTRACT_VERSION = "ar-223-acceptance-contract-1"
"""Which acceptance contract produced these records, so a reader can tell."""

COLLECTION = "acceptance_contracts"
"""Where contracts live in the run state."""

CONTRACT_STATUSES = contracts.CONTRACT_STATUSES
"""A contract is either the live interpretation of a request or the history of one.

Aliased from the vocabulary module rather than restated, because a contract status that
exists twice is a status the validator and the writer can disagree about -- and the
validator is the one that has to be right.
"""


def source_digest(text: str, *, refs: Sequence[str] = (), task_id: str = "") -> str:
    """The digest binding a contract to the exact request it interprets.

    Normalised, so re-wrapping does not invalidate a proof, and hashed over the
    references as well as the words, because a contract built from a task description
    plus two linked documents is not bound to the description alone.
    """
    payload = "|".join([
        normalise(str(text or "")),
        ",".join(sorted(str(item) for item in refs or ())),
        normalise(str(task_id or "")),
    ])
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def requirements_digest(requirement_records: Sequence[Mapping[str, Any]]) -> str:
    """A digest over what a contract actually requires, ignoring wording of the contract.

    Two contracts with the same obligations are the same contract for the purpose of
    "can I reuse that verification", and two contracts with different obligations are
    not -- which is the property that makes selective re-verification possible instead
    of all-or-nothing.
    """
    rows = sorted(
        "|".join([
            str(record.get("text", "")),
            str(record.get("kind", "")),
            "blocking" if bool(record.get("blocking")) else "advisory",
            "gate" if bool(record.get("human_gate")) else "no-gate",
        ])
        for record in requirement_records or ()
    )
    return hashlib.sha256("\n".join(rows).encode("utf-8")).hexdigest()


def create(
    state: dict,
    *,
    text: str,
    task_id: str = "",
    source_refs: Sequence[str] = (),
    constraints: Sequence[str] = (),
    non_goals: Sequence[str] = (),
    requirement_ids: Sequence[str] = (),
    revision: int | None = None,
    supersedes: str = "",
    material_change_reason: str = "",
    origin: str = "USER_REQUEST",
    contract_id: str = "",
) -> dict:
    """Create a contract, or a new revision of one.

    ``revision`` is derived rather than supplied when the caller does not state it: the
    next revision after the newest contract for this task. A caller cannot jump a
    revision, because a gap in the sequence is indistinguishable from a contract that
    was quietly deleted.
    """
    body = " ".join(str(text or "").split())
    if not body:
        raise ContractError("a contract must record the request it interprets")
    if not str(task_id or "").strip():
        raise ContractError("a contract must belong to a task; an unowned contract has no lifecycle")
    existing = for_task(state, task_id)
    resolved_revision = max((int(row.get("revision", 1)) for row in existing), default=0) + 1
    if revision is not None:
        resolved_revision = int(revision)
    if resolved_revision < 1:
        raise ContractError("a contract revision starts at 1")
    if resolved_revision > 1 and not str(supersedes or "").strip():
        previous = [row for row in existing if int(row.get("revision", 1)) == resolved_revision - 1]
        if not previous:
            raise ContractError(
                f"contract revision {resolved_revision} names no revision "
                f"{resolved_revision - 1} to supersede; a revision cannot be invented without its "
                "predecessor"
            )
        supersedes = str(previous[0].get("contract_id", ""))
    digest = source_digest(body, refs=source_refs, task_id=task_id)
    same_source = [row for row in existing if str(row.get("source_digest", "")) == digest]
    if same_source and resolved_revision == 1:
        raise ContractError(
            f"an identical contract already exists for this task ({same_source[0].get('contract_id')}). "
            "A second contract for the same request is a re-interpretation, and a re-interpretation "
            "needs a different request to justify it"
        )
    record = {
        "schema_version": contracts.SCHEMA_ACCEPTANCE,
        "contract_id": contract_id or new_record_id("ctr"),
        "contract_version": CONTRACT_VERSION,
        "run_id": str(state.get("run_id", "")),
        "task_id": str(task_id),
        "source_text": body,
        "source_refs": [str(item) for item in source_refs or () if str(item).strip()],
        "source_digest": digest,
        "requirements": [str(item) for item in requirement_ids or () if str(item).strip()],
        "constraints": [str(item) for item in constraints or () if str(item).strip()],
        "non_goals": [str(item) for item in non_goals or () if str(item).strip()],
        "revision": resolved_revision,
        "supersedes": str(supersedes),
        "material_change_reason": str(material_change_reason),
        "origin": str(origin),
        "status": "ACTIVE",
        "superseded_by": "",
        "created_at": utc_now(),
        "provenance": {
            "created_by": "engine",
            "policy_version": contracts.POLICY_VERSION,
            "contract_version": CONTRACT_CONTRACT_VERSION,
            "interpretation_origin": str(origin),
        },
    }
    problems = contracts.acceptance_contract_problems(record)
    if problems:
        raise ContractError("acceptance contract is malformed: " + "; ".join(problems))
    require_collection_capacity(state, COLLECTION)
    state.setdefault(COLLECTION, []).append(record)
    if supersedes:
        _supersede(state, supersedes, by=record["contract_id"])
    return record


def _supersede(state: dict, contract_id: str, *, by: str) -> None:
    for index, record in enumerate(state.get(COLLECTION, []) or []):
        if str(record.get("contract_id", "")) == str(contract_id):
            state[COLLECTION][index] = {
                **state[COLLECTION][index],
                "status": "SUPERSEDED",
                "superseded_by": str(by),
            }
            return


def supersede(state: dict, contract_id: str, *, by: str) -> dict:
    """Mark one contract superseded by another. History is kept, never deleted."""
    successor = contract(state, by)
    if successor is None:
        raise ContractError(f"no contract is recorded with id {by!r}")
    _supersede(state, contract_id, by=by)
    updated = contract(state, contract_id)
    if updated is None:
        raise ContractError(f"no contract is recorded with id {contract_id!r}")
    return updated


# ------------------------------------------------------------------- retrieval


def contracts_for(state: Mapping[str, Any]) -> list[dict]:
    return [dict(row) for row in state.get(COLLECTION, []) or [] if isinstance(row, Mapping)]


def contract(state: Mapping[str, Any], contract_id: str) -> dict | None:
    for record in contracts_for(state):
        if str(record.get("contract_id", "")) == str(contract_id):
            return record
    return None


def for_task(state: Mapping[str, Any], task_id: str) -> list[dict]:
    return [
        row for row in contracts_for(state)
        if str(row.get("task_id", "")) == str(task_id)
    ]


def active(state: Mapping[str, Any], *, task_id: str = "") -> dict | None:
    """The live contract for a task, or ``None``.

    ``None`` when there are *several* is the honest answer, not a bug to paper over:
    two active contracts for one task means the interpretation is ambiguous, and picking
    the newest would quietly resolve an ambiguity nobody resolved.
    """
    rows = [
        row for row in contracts_for(state)
        if str(row.get("status", "ACTIVE")) == "ACTIVE"
        and (not task_id or str(row.get("task_id", "")) == str(task_id))
    ]
    if len(rows) != 1:
        return None
    return rows[0]


def revise(
    state: dict,
    *,
    previous_contract_id: str,
    text: str,
    task_id: str = "",
    material_change_reason: str = "",
    source_refs: Sequence[str] = (),
    constraints: Sequence[str] = (),
    non_goals: Sequence[str] = (),
) -> dict:
    """Create the next revision of a contract because the request materially changed."""
    previous = contract(state, previous_contract_id)
    if previous is None:
        raise ContractError(f"no contract is recorded with id {previous_contract_id!r}")
    resolved_task = task_id or str(previous.get("task_id", ""))
    reason = material_change_reason or "the source request changed"
    return create(
        state,
        text=text,
        task_id=resolved_task,
        source_refs=source_refs or list(previous.get("source_refs", ())),
        constraints=constraints,
        non_goals=non_goals,
        requirement_ids=list(previous.get("requirements", ())),
        supersedes=str(previous.get("contract_id", "")),
        material_change_reason=reason,
        origin=str(previous.get("origin", "USER_REQUEST")),
    )


def assess_material_change(
    previous: Mapping[str, Any],
    *,
    text: str = "",
    source_refs: Sequence[str] = (),
) -> dict:
    """Whether a proposed contract is a material change to the previous one.

    Material means *the obligations or the boundaries moved*, which is what
    invalidates a verification pass. Wording that normalises to the same words is not
    material and must not cost a re-verification.
    """
    reasons: list[str] = []
    previous_digest = str(previous.get("source_digest", ""))
    if text:
        candidate = source_digest(
            " ".join(str(text).split()),
            refs=source_refs or list(previous.get("source_refs", ())),
            task_id=str(previous.get("task_id", "")),
        )
    else:
        candidate = str(previous.get("source_digest", ""))
    if candidate != previous_digest:
        reasons.append("the source request's normalised text or references differ from the recorded digest")
    for name in ("constraints", "non_goals"):
        if str(previous.get(name)) and not previous.get(name):
            reasons.append(f"the previous contract's {name} were dropped")
    return {
        "material": bool(reasons),
        "changed": candidate != previous_digest,
        "previous_digest": previous_digest,
        "candidate_digest": candidate,
        "reasons": reasons,
        "note": (
            "a material change creates a new revision. The previous contract stays readable and "
            "its decisions stay readable, because a decision nobody can audit was never evidence"
        ),
    }


# --------------------------------------------------------------------- binding


def assert_source_binding(state: Mapping[str, Any], contract_id: str, *, text: str = "",
                          source_refs: Sequence[str] = ()) -> list[str]:
    """Findings where a contract's recorded source no longer matches the live source.

    The contract-laundering check. An agent that cannot improve its result sometimes
    tries the other direction: replace the requirement with one it can pass. The
    revision moves, so it is visible -- and this function is what makes it visible at
    evaluation time rather than six weeks later.
    """
    record = contract(state, contract_id)
    if record is None:
        return [f"no contract is recorded with id {contract_id!r}"]
    problems: list[str] = []
    if not text and not source_refs:
        return problems
    candidate = source_digest(
        " ".join(str(text or record.get("source_text", "")).split()),
        refs=source_refs or list(record.get("source_refs", ())),
        task_id=str(record.get("task_id", "")),
    )
    if candidate != str(record.get("source_digest", "")):
        problems.append(
            f"contract {contract_id} records source digest {record.get('source_digest')} but the source "
            f"now digests to {candidate}. The interpretation was replaced after the fact; the original "
            "request remains historical and is still readable"
        )
    return problems


def decisions_for(
    state: Mapping[str, Any],
    *,
    contract_id: str,
    work_digest: str,
) -> tuple[list[dict], list[str]]:
    """Decisions that may legitimately answer for this contract and this work.

    Returns ``(usable, refusals)``. A decision made against a superseded contract
    revision or a different work digest is returned as a refusal with the reason, not
    quietly dropped -- "old verification cannot silently apply" means it has to say so
    out loud.
    """
    from . import decisions as decisions_module

    record = contract(state, contract_id)
    if record is None:
        return [], [f"no contract is recorded with id {contract_id!r}"]
    usable: list[dict] = []
    refusals: list[str] = []
    for decision in decisions_module.decisions_for_contract(state, contract_id):
        if str(decision.get("contract_revision", "")) != str(record.get("revision", "")):
            refusals.append(
                f"{decision.get('verification_id')} was decided against contract revision "
                f"{decision.get('contract_revision')}, not revision {record.get('revision')}"
            )
            continue
        if work_digest and str(decision.get("work_digest", "")) != str(work_digest):
            refusals.append(
                f"{decision.get('verification_id')} was decided against work digest "
                f"{decision.get('work_digest')}, not the current {work_digest}"
            )
            continue
        usable.append(decision)
    return usable, refusals


def assert_history(state: Mapping[str, Any]) -> list[str]:
    """Whether the contract chain is still walkable.

    A superseded contract whose successor is gone is a hole: a later pass can no longer
    tell what the earlier pass was grading, which means the earlier pass cannot be
    audited. That is reported rather than tolerated.
    """
    problems: list[str] = []
    rows = contracts_for(state)
    by_id = {str(row.get("contract_id", "")): row for row in rows}
    live_by_task: dict[str, int] = {}
    for row in rows:
        contract_id = str(row.get("contract_id", ""))
        successor = str(row.get("superseded_by", ""))
        if successor and successor not in by_id:
            problems.append(
                f"contract {contract_id} is superseded by {successor}, which is not recorded. The "
                "chain has a hole and the earlier revision cannot be audited through it"
            )
        if str(row.get("status", "ACTIVE")) == "ACTIVE":
            task = str(row.get("task_id", ""))
            live_by_task[task] = live_by_task.get(task, 0) + 1
    for task, count in sorted(live_by_task.items()):
        if count > 1:
            problems.append(
                f"task {task} has {count} active contracts. Acceptance is ambiguous, and choosing the "
                "newest would resolve an ambiguity nobody resolved"
            )
    for row in rows:
        revision = int(row.get("revision", 1) or 1)
        if revision > 1 and not str(row.get("supersedes", "")):
            problems.append(
                f"contract {row.get('contract_id')} is revision {revision} but names no predecessor"
            )
    return problems


def summarise(state: Mapping[str, Any]) -> dict:
    rows = contracts_for(state)
    revisions = [int(row.get("revision", 1) or 1) for row in rows]
    return {
        "contracts": len(rows),
        "active": sum(1 for row in rows if str(row.get("status", "ACTIVE")) == "ACTIVE"),
        "superseded": sum(1 for row in rows if str(row.get("status", "ACTIVE")) != "ACTIVE"),
        "highest_revision": max(revisions, default=0),
        "tasks": sorted({str(row.get("task_id", "")) for row in rows}),
        "note": "a contract is an interpretation bound to one request; a changed request is a new revision",
    }


def problems(state: Mapping[str, Any]) -> list[str]:
    found: list[str] = []
    for record in contracts_for(state):
        found.extend(
            f"contract {record.get('contract_id', '?')}: {problem}"
            for problem in contracts.acceptance_contract_problems(record)
        )
    found.extend(assert_history(state))
    return list(dict.fromkeys(found))


__all__ = [
    "COLLECTION",
    "CONTRACT_CONTRACT_VERSION",
    "CONTRACT_STATUSES",
    "CONTRACT_VERSION",
    "active",
    "assert_history",
    "assert_source_binding",
    "assess_material_change",
    "contract",
    "contracts_for",
    "create",
    "decisions_for",
    "for_task",
    "problems",
    "requirements_digest",
    "revise",
    "source_digest",
    "summarise",
    "supersede",
]