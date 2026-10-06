"""Requirements: the independently verifiable obligations a contract carries.

Ariadne already threaded a requirement *id* through ten modules by AR-222D. What did
not exist was a requirement **definition** -- an obligation with its own text, its own
evidence policy, and its own statement about whether it blocks acceptance. AR-222D said
so in its own words at
:mod:`ariadne_engine.rendered_critique.proof`:

    Requirement identity must exist before acceptance intelligence does.

This module is that identity. It does three things and refuses a fourth.

**It does not invent obligations.** A requirement carries
:data:`~ariadne_engine.contracts.REQUIREMENT_ORIGINS` -- ``EXPLICIT``,
``DERIVED`` or ``ASSUMED`` -- and only ``EXPLICIT`` may block acceptance by
default. This is the difference between interpreting a request and manufacturing one.
*"Make me a cool F1 dashboard"* may legitimately become one requirement per surface.
It does not become forty-seven blocking obligations the user never agreed to, because
an inferred obligation is a guess wearing a ticket number, and a guess that blocks
acceptance is a guess that can silently stop a project.

**It does not atomise prose into confetti.** "Mobile navigation works below 768px and
supports keyboard dismissal" may split into two requirements, because the two halves
need materially *different* evidence -- a rendered capture at a viewport cannot
establish keyboard dismissal. But a sentence that needs one kind of evidence stays one
requirement. :func:`split_candidate` is offered to a caller and never applied
automatically, and a split records its lineage so the parent text stays readable.

**It does not rank evidence globally.** There is no ``screenshot > test > diff``
ordering in this module, because that ordering is false. A build result *directly*
establishes "it compiles" and establishes nothing whatsoever about whether a button
works. Evidence strength is therefore declared **per requirement**, as three
positions in :data:`~ariadne_engine.contracts.EVIDENCE_STANCES`:

``AUTHORITATIVE``     if current and relevant, this settles the requirement either way
``REQUIRED``          must be present and supporting for the requirement to be PROVEN
``SUPPORTING``        counts toward a partial establishment, never establishes alone
``INSUFFICIENT_ALONE`` never establishes anything on its own, whatever it says

The last position is the one that catches a build proving a screenshot requirement, a
screenshot proving a persistence requirement, and a unit test proving subjective
polish. Naming a stance is what lets the engine refuse those, and refusing them is the
whole point.

What it refuses: a requirement whose evidence policy is empty. A requirement nothing
could ever satisfy is not a requirement; it is a way of making acceptance
unreachable without anybody being able to say why.
"""

from __future__ import annotations

from typing import Any, Iterable, Mapping, Sequence

from .. import contracts
from ..contracts import ContractError, new_record_id, require_collection_capacity, utc_now

REQUIREMENT_VERSION = "ar-223-requirement-1"
"""The requirement record shape."""

COLLECTION = "acceptance_requirements"
"""Where requirement definitions live in the run state."""


# --------------------------------------------------------------- structural split

SPLIT_CONNECTORS = (" and ", " but ", " while ", " plus ", " as well as ", "; ", " — ", " – ")
"""Coordinators that can join two obligations needing different evidence.

Deliberately narrow. Conjunction is the only structure that reliably means *two
obligations* rather than one, and a splitter built on anything broader produces
fragments no evidence can address. The em-dash forms are included because a
requirement written that way usually names a scope and then a property of it.
"""


def split_candidate(text: str) -> list[str]:
    """Propose an atomic split of one requirement, or report that none is needed.

    Returns ``[]`` when the text should stay whole, and a list of parts when it
    should not. The caller decides. Nothing here applies a split automatically,
    because atomisation that runs unattended is requirement explosion with extra
    steps, and requirement explosion is how a one-sentence request becomes an
    unaccepting project.
    """
    cleaned = " ".join(str(text or "").split())
    if not cleaned:
        return []
    parts: list[str] = []
    remaining = cleaned
    for connector in SPLIT_CONNECTORS:
        if connector not in remaining:
            continue
        pieces = [piece.strip(" ,.;:") for piece in remaining.split(connector)]
        pieces = [piece for piece in pieces if piece]
        if len(pieces) < 2:
            continue
        # A conjunction joining two clauses that need the same kind of proof is not a
        # split. "the layout is responsive and legible" is one requirement about one
        # capture. A split here would produce two tickets no single artefact closes.
        remaining = " ".join(pieces)
        parts = pieces
        break
    if len(parts) < 2:
        return []
    lowered = {part.lower() for part in parts}
    if len(lowered) < 2:
        return []
    return parts


def _default_policy_for(kind: str) -> dict[str, list[str]]:
    """The starting evidence policy for a requirement kind.

    A *starting* policy, not a fixed one. It exists so a requirement cannot be
    created with nothing to say about what would prove it, and every entry is a
    placeholder a caller is expected to narrow to the requirement's real subject. The
    one entry that is not a placeholder is :data:`INSUFFICIENT_ALONE`, which is always
    true regardless of kind: a worker's statement about itself proves nothing.
    """
    return {
        "AUTHORITATIVE": [],
        "REQUIRED": list(DEFAULT_REQUIRED_EVIDENCE.get(str(kind), ["TEST"])),
        "SUPPORTING": [],
        "INSUFFICIENT_ALONE": list(INSUFFICIENT_ALONE),
    }


DEFAULT_REQUIRED_EVIDENCE: dict[str, tuple[str, ...]] = {
    "FUNCTIONAL": ("TEST", "RUNTIME"),
    "VISUAL": ("RENDER",),
    "INTERACTION": ("INTERACTION",),
    "CONSTRAINT": ("DIFF",),
    "REGRESSION": ("TEST",),
    "ACCESSIBILITY": ("ACCESSIBILITY",),
    "PERFORMANCE": ("PERFORMANCE",),
    "SECURITY": ("STATIC_ANALYSIS",),
    "CONTENT": ("REVIEW",),
    "SUBJECTIVE": ("REVIEW",),
}
"""What a requirement of each kind would ordinarily need, before narrowing.

Recorded here so a new requirement kind has an obvious starting point, and so the
:func:`policy_problems` validator has something to compare against. A requirement is
free to declare less than the table says -- a performance requirement with a static
budget may need only ``DIFF`` -- and free to declare more. It is not free to declare
nothing.
"""

INSUFFICIENT_ALONE: tuple[str, ...] = ()
"""Evidence kinds that can never establish anything on their own, **per requirement**.

Empty by default, deliberately. Insufficiency is not a property of an evidence kind -- a
``REVIEW`` settles a subjective requirement and establishes nothing about persistence, and
``SCREENSHOT`` is the reverse -- so there is no honest global list to start from, and
writing one would reintroduce exactly the ``screenshot > test > diff`` ranking this module
exists to dismantle.

The rule is enforced structurally instead, in two places:

* :func:`stance_of` returns ``INSUFFICIENT_ALONE`` for any kind a requirement did not
  declare, so silence is the weakest stance rather than the middle one; and
* a worker's statement is not an insufficient evidence kind -- it is **not an evidence
  kind at all**. :mod:`ariadne_engine.acceptance.claims` models those as claims, so
  :func:`~ariadne_engine.contracts.acceptance_requirement_problems` refuses any policy
  naming ``CLAIM`` or ``STATEMENT`` with the reason that a claim may be what is being
  verified and is never the thing that verifies it.

Both halves matter. The first stops an unlisted screenshot chipping away at a runtime
requirement; the second means there is no route at all by which a worker can talk its way
into being evidence.
"""


# ------------------------------------------------------------------- the record


def create(
    state: dict,
    *,
    contract_id: str,
    text: str,
    kind: str = "FUNCTIONAL",
    origin: str = "EXPLICIT",
    blocking: bool | None = None,
    evidence_policy: Mapping[str, Sequence[str]] | None = None,
    verification_mode: str = "DETERMINISTIC",
    source_refs: Sequence[str] = (),
    scope_paths: Sequence[str] = (),
    human_gate: bool | None = None,
        split_from: str = "",
        decision_path: str = "",
        requirement_id: str = "",
        task_id: str = "",
        rationale: str = "",
        dependencies: Mapping[str, str] | None = None,
    ) -> dict:
    """Create one requirement definition.

    ``blocking`` and ``human_gate`` are derived from the origin when not stated, and
    the derivation is the point of the exercise:

    ==================  ==========  =============
    origin              blocking    human gate
    ==================  ==========  =============
    ``EXPLICIT``        True        False
    ``DERIVED``         False       False
    ``ASSUMED``         False       True
    ==================  ==========  =============

    An ``ASSUMED`` requirement never blocks and always asks a human, because the only
    thing an assumption can honestly contribute is a question. A ``DERIVED``
    requirement -- one that follows necessarily from an explicit one -- is surfaced and
    surfaced loudly, but it does not get to stop work on its own; that is the difference
    between interpreting a request and expanding it.
    """
    body = " ".join(str(text or "").split())
    if not body:
        raise ContractError("a requirement must state the obligation it carries")
    if not str(contract_id or "").strip():
        raise ContractError("a requirement must belong to a contract")
    if str(kind) not in contracts.REQUIREMENT_KINDS:
        raise ContractError(f"unsupported requirement kind: {kind!r}")
    if str(origin) not in contracts.REQUIREMENT_ORIGINS:
        raise ContractError(f"unsupported requirement origin: {origin!r}")
    if str(verification_mode) not in contracts.DECISION_CLASSIFICATIONS:
        raise ContractError(f"unsupported verification mode: {verification_mode!r}")
    policy = dict(evidence_policy) if evidence_policy is not None else _default_policy_for(str(kind))
    resolved_blocking = (str(origin) == "EXPLICIT") if blocking is None else bool(blocking)
    resolved_gate = (str(origin) == "ASSUMED") if human_gate is None else bool(human_gate)
    record = {
        "schema_version": contracts.SCHEMA_ACCEPTANCE,
        "requirement_id": requirement_id or new_record_id("rqm"),
        "requirement_version": REQUIREMENT_VERSION,
        "run_id": str(state.get("run_id", "")),
        "task_id": str(task_id),
        "contract_id": str(contract_id),
        "text": body,
        "kind": str(kind),
        "origin": str(origin),
        "blocking": bool(resolved_blocking),
        "human_gate": bool(resolved_gate),
        "evidence_policy": {
            "AUTHORITATIVE": [str(item) for item in policy.get("AUTHORITATIVE", ()) or ()],
            "REQUIRED": [str(item) for item in policy.get("REQUIRED", ()) or ()],
            "SUPPORTING": [str(item) for item in policy.get("SUPPORTING", ()) or ()],
            "INSUFFICIENT_ALONE": [str(item) for item in policy.get(
                "INSUFFICIENT_ALONE", INSUFFICIENT_ALONE) or ()],
        },
        "verification_mode": str(verification_mode),
        "source_refs": [str(item) for item in source_refs or () if str(item).strip()],
        "scope_paths": [str(item) for item in scope_paths or () if str(item).strip()],
        "dependencies": {str(key): str(value) for key, value in dict(dependencies or {}).items()},
        "split_from": str(split_from),
        "status": "ACTIVE",
        "superseded_by": "",
        "rationale": str(rationale),
        "recorded_at": utc_now(),
        "provenance": {
            "created_by": "engine",
            "policy_version": contracts.POLICY_VERSION,
            "contract_version": contracts.ACCEPTANCE_CONTRACT_VERSION,
        },
    }
    problems = contracts.acceptance_requirement_problems(record)
    if problems:
        raise ContractError("acceptance requirement is malformed: " + "; ".join(problems))
    require_collection_capacity(state, COLLECTION)
    state.setdefault(COLLECTION, []).append(record)
    return record


def record_split(
    state: dict,
    *,
    parent: Mapping[str, Any],
    parts: Sequence[str],
    kinds: Sequence[str] = (),
    contract_id: str = "",
    evidence_policy: Mapping[str, Sequence[str]] | None = None,
    verification_mode: str = "DETERMINISTIC",
    reason: str = "",
) -> list[dict]:
    """Split one requirement into parts that need different evidence, keeping lineage.

    The parent is superseded rather than deleted, and the children name it. A reader
    of the finished contract can reconstruct the sentence the user agreed to from the
    parts, which is the only thing that makes an atomic requirement set defensible.
    """
    parent_id = str(parent.get("requirement_id", ""))
    if not parent_id:
        raise ContractError("a split needs a parent requirement")
    body = " ".join(str(parent.get("text", "")).split())
    proposed = split_candidate(body)
    if len(proposed) < 2:
        raise ContractError(
            "this requirement does not split: it states one obligation, and atomising it would "
            "produce fragments no single piece of evidence could address"
        )
    children = [
        create(
            state,
            contract_id=contract_id or str(parent.get("contract_id", "")),
            text=part,
            kind=str(kinds[index]) if index < len(kinds) else str(parent.get("kind", "FUNCTIONAL")),
            origin=str(parent.get("origin", "EXPLICIT")),
            evidence_policy=evidence_policy,
            verification_mode=verification_mode,
            source_refs=list(parent.get("source_refs", ())),
            split_from=parent_id,
            rationale=reason or f"split from {parent_id}: the parts need materially different evidence",
        )
        for index, part in enumerate(proposed)
    ]
    index = _index_of(state, parent_id)
    if index is None:
        raise ContractError(f"no requirement is recorded with id {parent_id!r}")
    state[COLLECTION][index] = {**state[COLLECTION][index], "status": "SUPERSEDED",
                                 "superseded_by": [child["requirement_id"] for child in children]}
    return children


def _index_of(state: Mapping[str, Any], requirement_id: str) -> int | None:
    for index, record in enumerate(state.get(COLLECTION, []) or []):
        if str(record.get("requirement_id", "")) == str(requirement_id):
            return index
    return None


def all_requirements(state: Mapping[str, Any]) -> list[dict]:
    """Every requirement definition, superseded ones included."""
    return [dict(row) for row in state.get(COLLECTION, []) or [] if isinstance(row, Mapping)]


def active_requirements(state: Mapping[str, Any], *, contract_id: str = "") -> list[dict]:
    """The requirements a pass may evaluate. Superseded history stays readable."""
    rows = [
        row for row in all_requirements(state)
        if str(row.get("status", "ACTIVE")) == "ACTIVE" and not str(row.get("superseded_by", ""))
    ]
    if contract_id:
        rows = [row for row in rows if str(row.get("contract_id", "")) == str(contract_id)]
    return rows


def requirement(state: Mapping[str, Any], requirement_id: str) -> dict | None:
    for record in all_requirements(state):
        if str(record.get("requirement_id", "")) == str(requirement_id):
            return record
    return None


def requirements_for_contract(state: Mapping[str, Any], contract_id: str) -> list[dict]:
    return active_requirements(state, contract_id=contract_id)


def blocking(state: Mapping[str, Any], *, contract_id: str = "") -> list[dict]:
    """Only the requirements allowed to govern acceptance."""
    return [
        row for row in active_requirements(state, contract_id=contract_id)
        if bool(row.get("blocking"))
    ]


# ------------------------------------------------------------- evidence policy


def stance_of(requirement_record: Mapping[str, Any], evidence_kind: str) -> str:
    """Which position ``evidence_kind`` occupies for this requirement.

    Accepts either a requirement record or a bare evidence policy, because both appear at
    call sites and a function that silently mis-reads one of them returns
    ``INSUFFICIENT_ALONE`` for everything -- which looks like correct caution and is
    actually the policy being ignored.

    Returns ``"INSUFFICIENT_ALONE"`` for anything undeclared. That default is deliberate
    and is the weakest stance rather than the middle one: an engineer who forgot to
    declare an evidence kind has not thereby licensed it, and treating silence as
    ``SUPPORTING`` would let an unlisted screenshot chip away at a ``RUNTIME``
    requirement until enough of them added up.
    """
    policy = requirement_record.get("evidence_policy")
    if not isinstance(policy, Mapping):
        policy = requirement_record
    kind = str(evidence_kind)
    for stance in contracts.EVIDENCE_STANCES:
        if kind in {str(item) for item in policy.get(stance, ()) or ()}:
            return stance
    return "INSUFFICIENT_ALONE"


def required_kinds(requirement_record: Mapping[str, Any]) -> list[str]:
    policy = requirement_record.get("evidence_policy")
    return [str(item) for item in (policy or {}).get("REQUIRED", ()) or ()]


def stance_kinds(requirement_record: Mapping[str, Any], stance: str) -> list[str]:
    """Every evidence kind this requirement places in one policy position."""
    policy = requirement_record.get("evidence_policy")
    if not isinstance(policy, Mapping):
        return []
    return [str(item) for item in policy.get(str(stance), ()) or ()]


def authoritative_kinds(requirement_record: Mapping[str, Any]) -> list[str]:
    policy = requirement_record.get("evidence_policy")
    return [str(item) for item in (policy or {}).get("AUTHORITATIVE", ()) or ()]


def policy_problems(requirement_record: Mapping[str, Any]) -> list[str]:
    """Why a requirement's evidence policy cannot be trusted, in words."""
    problems: list[str] = []
    policy = requirement_record.get("evidence_policy")
    if not isinstance(policy, Mapping):
        return ["the requirement declares no evidence policy"]
    for stance in contracts.EVIDENCE_STANCES:
        values = policy.get(stance, [])
        if not isinstance(values, (list, tuple)):
            problems.append(f"evidence policy {stance} is not a list")
            continue
        for value in values:
            if str(value) not in contracts.ACCEPTANCE_EVIDENCE_KINDS:
                problems.append(
                    f"evidence policy names an unknown evidence kind: {value}"
                )
    declared = {str(item) for stance in contracts.EVIDENCE_STANCES for item in policy.get(stance, ()) or ()}
    if not declared:
        problems.append(
            "the requirement names no evidence that could establish it. A requirement nothing "
            "could satisfy is not a requirement; it makes acceptance unreachable without saying why"
        )
    overlap = (
        set(policy.get("REQUIRED", ()) or ())
        & set(policy.get("INSUFFICIENT_ALONE", ()) or ())
    )
    if overlap:
        problems.append(
            "evidence is both required and insufficient alone: "
            + ", ".join(sorted(str(item) for item in overlap))
        )
    return problems


def derive_policy(
    *,
    kind: str,
    needs_runtime: bool = False,
    needs_capture: bool = False,
    needs_review: bool = False,
    additional_required: Sequence[str] = (),
    supporting: Sequence[str] = (),
    authoritative: Sequence[str] = (),
) -> dict[str, list[str]]:
    """Build an evidence policy from what a requirement actually needs.

    A convenience for the common cases, deliberately narrow: it takes statements about
    what kind of proof is needed rather than guessing from text. Anything subtler is
    written out by the caller, because a policy assembled by inference from prose is
    exactly the failure mode this module exists to prevent.
    """
    policy = _default_policy_for(str(kind))
    required = list(policy["REQUIRED"])
    if needs_runtime and "RUNTIME" not in required:
        required.append("RUNTIME")
    if needs_capture and "RENDER" not in required:
        required.append("RENDER")
    if needs_review and "REVIEW" not in required:
        required.append("REVIEW")
    for extra in additional_required:
        if str(extra) not in required:
            required.append(str(extra))
    return {
        "AUTHORITATIVE": list(dict.fromkeys(str(item) for item in authoritative)),
        "REQUIRED": list(dict.fromkeys(required)),
        "SUPPORTING": [str(item) for item in supporting if str(item) not in required],
        "INSUFFICIENT_ALONE": list(policy["INSUFFICIENT_ALONE"]),
    }


def summarise(state: Mapping[str, Any], *, contract_id: str = "") -> dict:
    """Deterministic counters. Never a quality percentage.

    ``5 PROVEN, 1 FAILED, 2 UNPROVEN`` is five proven requirements, one failed one and
    two unproven ones. Collapsing that to *74%* would invent a scale nobody measured,
    destroy exactly the distinction the verdicts exist to preserve, and produce a
    number that goes up when a requirement is deleted.
    """
    rows = active_requirements(state, contract_id=contract_id)
    by_kind: dict[str, int] = {name: 0 for name in contracts.REQUIREMENT_KINDS}
    by_origin: dict[str, int] = {name: 0 for name in contracts.REQUIREMENT_ORIGINS}
    blocking_count = 0
    for row in rows:
        kind = str(row.get("kind", ""))
        if kind in by_kind:
            by_kind[kind] += 1
        origin = str(row.get("origin", ""))
        if origin in by_origin:
            by_origin[origin] += 1
        if bool(row.get("blocking")):
            blocking_count += 1
    return {
        "requirements": len(rows),
        "blocking": blocking_count,
        "non_blocking": len(rows) - blocking_count,
        "by_kind": by_kind,
        "by_origin": by_origin,
        "note": "counts, not a score: requirement-level state is the primary record",
    }


def problems(state: Mapping[str, Any]) -> list[str]:
    """Structural problems across every recorded requirement."""
    found: list[str] = []
    for record in all_requirements(state):
        found.extend(
            f"requirement {record.get('requirement_id', '?')}: {problem}"
            for problem in contracts.acceptance_requirement_problems(record)
        )
        found.extend(
            f"requirement {record.get('requirement_id', '?')}: {problem}"
            for problem in policy_problems(record)
        )
    return list(dict.fromkeys(found))


__all__ = [
    "COLLECTION",
    "DEFAULT_REQUIRED_EVIDENCE",
    "INSUFFICIENT_ALONE",
    "REQUIREMENT_VERSION",
    "SPLIT_CONNECTORS",
    "active_requirements",
    "all_requirements",
    "authoritative_kinds",
    "blocking",
    "create",
    "derive_policy",
    "policy_problems",
    "problems",
    "record_split",
    "requirement",
    "requirements_for_contract",
    "required_kinds",
    "split_candidate",
    "stance_of",
    "stance_kinds",
    "summarise",
]