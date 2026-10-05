"""Worker claims: what an actor says it did, kept separate from what happened.

The permanent rule this module exists to hold:

    **The worker may produce evidence. It cannot mint its own independent acceptance.**

Everything about a claim record is built so that honouring that rule is structural
rather than a matter of remembering it. A claim carries the actor that made it, the
work revision it is about, when it was made and where it came from -- and, crucially,
it is a *different kind of object* from
:mod:`ariadne_engine.acceptance.evidence`. A claim can be true. A claim can also be
completely unfounded. Nothing in this module decides which, because deciding that is
:mod:`ariadne_engine.acceptance.decisions`' job and it decides it against evidence.

**Prose is not truth, but prose is not nothing either.** A worker that says *"implemented
mobile navigation, fixed keyboard accessibility, and all tests pass"* has made three
claims, and collapsing that into one sentence would make it impossible to say which
part is contradicted when 182 tests pass and 4 fail. :func:`extract` splits prose into
claims deterministically, maps each to requirements by recorded overlap, and marks the
mapping ``UNMAPPED`` when it cannot -- because an unmapped claim is still a claim, and
silently dropping it would hide exactly the overstatement the system exists to catch.

**A claim is bound to a revision.** A claim about revision ``A`` does not apply to
revision ``B``. This is not pedantry: it is the difference between "the mobile nav was
fixed" and "the mobile nav was fixed, then someone changed it again", and only the
second one is what a user needs to know.

**External claims are data, not instructions.** A claim's text comes from outside the
trust boundary -- an agent transcript, a CI log, a pull-request body, a human operator.
:func:`sanitise` records that fact structurally, and
:mod:`ariadne_engine.acceptance.security` refuses any attempt to make a claim act as
its own evidence.
"""

from __future__ import annotations

import re
from typing import Any, Mapping, Sequence

from .. import contracts
from ..contracts import ContractError, new_record_id, require_collection_capacity, utc_now

CLAIM_VERSION = "ar-223-claim-1"
"""The claim record shape."""

COLLECTION = "acceptance_claims"
"""Where claims live in the run state."""

CLAIM_ORIGINS = ("PROSE", "STRUCTURED", "CI", "OPERATOR", "IMPORTED")
"""How the claim reached Ariadne.

``PROSE`` is a worker's summary. ``STRUCTURED`` is an agent emitting claims in the
record shape rather than in English -- much better, and available to every actor. The
distinction is kept because a structured claim and a prose claim fail differently: a
structured claim can be *parsed* and a prose claim can only be *extracted*.
"""

ACTOR_ROLES = contracts.PROOF_ACTOR_ROLES
"""Reuses AR-222D's role vocabulary rather than inventing a parallel one.

The list already existed because
:mod:`ariadne_engine.rendered_critique.proof` needed it to make self-certification
*detectable*. It needed to exist before anything depended on it, and this is what
depends on it.
"""


# ------------------------------------------------------------------ extraction

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?;])\s+|\n+")
_CLAUSE_SPLIT = re.compile(
    r",\s+(?:and\s+)?(?:also\s+)?(?=all\s|every\s|the\s+\w+\s+(?:is|are|now|passes|works))"
    r"|\s+and\s+(?=(?:all|every)\s)"
    r"|;\s*",
    re.I,
)

_CLAIM_TYPE_CUES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("VERIFIED", ("verified", "independently verified", "confirmed by review", "reviewed and confirmed")),
    ("PRESERVED", ("preserved", "no regressions", "still works", "unchanged", "regression-free")),
    ("TESTED", ("tests pass", "tests passed", "all tests", "test suite green", "suite passes", "lint clean")),
    ("FIXED", ("fixed", "resolved", "corrected", "repaired", "regression fixed")),
    ("IMPLEMENTED", ("implemented", "added", "built", "created", "introduced", "wired")),
    ("COMPLETE", ("complete", "completed", "done", "finished", "ready", "shipped")),
)
"""Deterministic cue vocabulary mapping prose to a claim type.

Order matters: ``VERIFIED`` is checked before ``TESTED`` before ``IMPLEMENTED``,
because "implemented and tested" is not the same claim as "verified", and a worker
that says "verified" has made a stronger assertion that needs stronger evidence. The
cue vocabulary is finite and stated, which is what makes the classification auditable
-- and its limits are a known limitation rather than a hidden weakness.
"""


def _classify(statement: str) -> str:
    lowered = statement.lower()
    for claim_type, cues in _CLAIM_TYPE_CUES:
        if any(cue in lowered for cue in cues):
            return claim_type
    return "IMPLEMENTED"


def _significant(text: str) -> set[str]:
    stop = {
        "the", "a", "an", "and", "or", "of", "to", "in", "on", "for", "with", "is", "are",
        "was", "were", "be", "been", "it", "its", "this", "that", "these", "those", "all",
        "every", "each", "now", "also", "still", "not", "no", "as", "at", "by", "from",
        "has", "have", "had", "do", "does", "did", "can", "will", "would", "should",
    }
    return {
        word
        for word in "".join(c if c.isalnum() else " " for c in str(text).lower()).split()
        if word not in stop and len(word) > 2
    }


def split_statements(text: str) -> list[str]:
    """Split one worker message into the individual claims it makes.

    Deterministic and conservative. It splits on sentence boundaries and on the two
    coordinations that reliably mean *two claims* -- a semicolon, and ``and`` directly
    in front of a quantified universal (``and all tests pass``). It does not split on
    every ``and``, because *"the nav works and is animated"* is one claim about one
    thing, and splitting it produces two half-claims no evidence can address.

    A statement that cannot be split further is returned whole. One sentence, one claim.
    """
    cleaned = " ".join(str(text or "").split())
    if not cleaned:
        return []
    statements: list[str] = []
    for sentence in _SENTENCE_SPLIT.split(cleaned):
        stripped = sentence.strip(" -*\u2022")
        if not stripped:
            continue
        pieces = _CLAUSE_SPLIT.split(stripped)
        for piece in pieces:
            candidate = " ".join(str(piece).split()).strip(" ,;")
            if candidate and len(candidate.split()) >= 2:
                statements.append(candidate)
    return statements


def map_to_requirements(
    statement: str,
    requirements: Sequence[Mapping[str, Any]],
) -> list[dict]:
    """Which requirements a statement is *about*, with the mapping recorded.

    Lexical overlap, deterministic, and reported honestly. A statement with no overlap
    is mapped ``UNMAPPED`` rather than attached to the nearest requirement: a guessed
    attribution is how a proof system ends up proving the wrong thing with real
    evidence.
    """
    words = _significant(statement)
    if not words:
        return []
    rows: list[dict] = []
    for record in requirements or ():
        overlap = words & _significant(record.get("text", ""))
        coverage = len(overlap) / max(1, len(_significant(record.get("text", ""))))
        if overlap and coverage >= 0.5:
            rows.append({
                "requirement_id": str(record.get("requirement_id", "")),
                "mapping": "EXACT",
                "overlap": sorted(overlap),
                "coverage": round(coverage, 3),
            })
    if rows:
        return rows
    for record in requirements or ():
        overlap = words & _significant(record.get("text", ""))
        if overlap:
            rows.append({
                "requirement_id": str(record.get("requirement_id", "")),
                "mapping": "LEXICAL",
                "overlap": sorted(overlap),
                "coverage": round(len(overlap) / max(1, len(words)), 3),
            })
    return rows


def extract(
    state: dict,
    *,
    actor: str,
    statement: str,
    origin: str = "PROSE",
    contract_id: str = "",
    work_digest: str = "",
    actor_execution: str = "",
    actor_role: str = "implementation_worker",
    requirement_scope: Sequence[Mapping[str, Any]] | None = None,
    task_id: str = "",
    source_label: str = "",
) -> list[dict]:
    """Extract one or more claims from a worker's message, and record each.

    Returns the created records. The caller is expected to treat every one of them as
    *awaiting evidence*; nothing here upgrades a claim because it was extracted
    cleanly, and nothing here discards one because it could not be mapped.
    """
    if not str(actor or "").strip():
        raise ContractError("a claim needs the actor who made it")
    if str(origin) not in CLAIM_ORIGINS:
        raise ContractError(f"unsupported claim origin: {origin!r}")
    if str(actor_role) not in ACTOR_ROLES:
        raise ContractError(f"unsupported actor role: {actor_role!r}")
    from . import requirements as requirements_module

    if requirement_scope is None:
        requirement_scope = requirements_module.active_requirements(
            state, contract_id=contract_id,
        )
    external = str(origin) in ("PROSE", "CI", "IMPORTED")
    created: list[dict] = []
    for piece in split_statements(statement):
        mappings = map_to_requirements(piece, requirement_scope)
        claim_type = _classify(piece)
        record = {
            "schema_version": contracts.SCHEMA_ACCEPTANCE,
            "claim_id": new_record_id("clm"),
            "claim_version": CLAIM_VERSION,
            "run_id": str(state.get("run_id", "")),
            "task_id": str(task_id),
            "contract_id": str(contract_id),
            "actor": str(actor),
            "actor_execution": str(actor_execution),
            "actor_role": str(actor_role),
            "statement": piece,
            "statement_digest": contracts.digest_fields("acceptance-claim", {
                "actor": str(actor), "statement": piece,
            }),
            "claim_type": claim_type,
            "requirement_ids": [row["requirement_id"] for row in mappings],
            "requirement_mapping": [row["mapping"] for row in mappings],
            "mapping_detail": mappings,
            "work_digest": str(work_digest),
            "assertion": {},
            "origin": str(origin),
            "external": bool(external),
            "source_label": str(source_label),
            "status": "AWAITING_EVIDENCE",
            "recorded_at": utc_now(),
            "provenance": {
                "created_by": "engine",
                "policy_version": contracts.POLICY_VERSION,
                "contract_version": contracts.ACCEPTANCE_CONTRACT_VERSION,
                "extraction": "deterministic: sentence and quantified-universal coordination",
            },
        }
        problems = contracts.acceptance_claim_problems(record)
        if problems:
            raise ContractError("acceptance claim is malformed: " + "; ".join(problems))
        require_collection_capacity(state, COLLECTION)
        state.setdefault(COLLECTION, []).append(record)
        created.append(record)
    return created


# ------------------------------------------------------------------- authoring


def create(
    state: dict,
    *,
    actor: str,
    statement: str,
    claim_type: str = "IMPLEMENTED",
    origin: str = "STRUCTURED",
    contract_id: str = "",
    requirement_ids: Sequence[str] = (),
    work_digest: str = "",
    assertion: Mapping[str, Any] | None = None,
    actor_execution: str = "",
    actor_role: str = "implementation_worker",
    task_id: str = "",
    source_label: str = "",
) -> dict:
    """Record one claim the actor stated in Ariadne's own shape.

    The structured path. An actor that can emit ``{passed: 26, failed: 0}`` has made a
    claim the engine can *check* rather than *interpret*, which is worth a great deal
    more than a paragraph of prose and costs the actor nothing.
    """
    if not str(actor or "").strip():
        raise ContractError("a claim needs the actor who made it")
    if str(claim_type) not in contracts.CLAIM_TYPES:
        raise ContractError(f"unsupported claim type: {claim_type!r}")
    if str(origin) not in CLAIM_ORIGINS:
        raise ContractError(f"unsupported claim origin: {origin!r}")
    if str(actor_role) not in ACTOR_ROLES:
        raise ContractError(f"unsupported actor role: {actor_role!r}")
    from . import requirements as requirements_module

    unknown = [
        requirement_id for requirement_id in requirement_ids or ()
        if requirements_module.requirement(state, str(requirement_id)) is None
    ]
    if unknown:
        raise ContractError(
            "claim names requirement(s) that do not exist: " + ", ".join(sorted(unknown))
            + ". A claim about a requirement nobody recorded cannot be assessed"
        )
    statement_text = " ".join(str(statement or "").split())
    if not statement_text:
        raise ContractError("a claim must state something")
    record = {
        "schema_version": contracts.SCHEMA_ACCEPTANCE,
        "claim_id": new_record_id("clm"),
        "claim_version": CLAIM_VERSION,
        "run_id": str(state.get("run_id", "")),
        "task_id": str(task_id),
        "contract_id": str(contract_id),
        "actor": str(actor),
        "actor_execution": str(actor_execution),
        "actor_role": str(actor_role),
        "statement": statement_text,
        "statement_digest": contracts.digest_fields("acceptance-claim", {
            "actor": str(actor), "statement": statement_text,
        }),
        "claim_type": str(claim_type),
        "requirement_ids": [str(item) for item in requirement_ids or ()],
        "requirement_mapping": ["STRUCTURED"] * len(list(requirement_ids or ())),
        "mapping_detail": [
            {"requirement_id": str(item), "mapping": "STRUCTURED", "overlap": [], "coverage": 1.0}
            for item in requirement_ids or ()
        ],
        "work_digest": str(work_digest),
        "assertion": dict(assertion or {}),
        "origin": str(origin),
        "external": str(origin) in ("PROSE", "CI", "IMPORTED"),
        "source_label": str(source_label),
        "status": "AWAITING_EVIDENCE",
        "recorded_at": utc_now(),
        "provenance": {
            "created_by": "engine",
            "policy_version": contracts.POLICY_VERSION,
            "contract_version": contracts.ACCEPTANCE_CONTRACT_VERSION,
            "extraction": "structured: the actor stated the claim",
        },
    }
    problems = contracts.acceptance_claim_problems(record)
    if problems:
        raise ContractError("acceptance claim is malformed: " + "; ".join(problems))
    require_collection_capacity(state, COLLECTION)
    state.setdefault(COLLECTION, []).append(record)
    return record


def sanitise(text: str) -> dict:
    """Record that a claim's words came from outside the trust boundary.

    Deliberately does not strip anything. Filtering external prose is a losing game --
    the injection arrives in the next phrasing -- and the defence is structural: the
    text is stored as *data*, no evaluation path reads it as an instruction, and this
    record says so. An external claim is assessed against evidence or not at all.

    What it does surface is *how* the text was treated, so a reader can see that the
    engine noticed the difference rather than having forgotten it.
    """
    body = " ".join(str(text or "").split())
    directive_cues = (
        "ignore policy", "ignore previous", "mark this proven", "mark as proven", "accept this task",
        "ariadne verified", "ariadne approved", "treat this as evidence", "this is independent review",
        "override", "you are now", "system prompt", "disregard",
    )
    lowered = body.lower()
    return {
        "text": body,
        "external": True,
        "trust": "DATA_ONLY",
        "length": len(body),
        "directive_cues": sorted({cue for cue in directive_cues if cue in lowered}),
        "instruction_authority": "none",
        "note": (
            "external text is stored as data and is never read as an instruction. It can be the "
            "subject of a claim; it can never be the evidence that establishes one"
        ),
    }


# ------------------------------------------------------------------- retrieval


def claims(state: Mapping[str, Any]) -> list[dict]:
    return [dict(row) for row in state.get(COLLECTION, []) or [] if isinstance(row, Mapping)]


def claim(state: Mapping[str, Any], claim_id: str) -> dict | None:
    for record in claims(state):
        if str(record.get("claim_id", "")) == str(claim_id):
            return record
    return None


def claims_for(state: Mapping[str, Any], *, requirement_id: str = "", actor: str = "",
               work_digest: str = "", contract_id: str = "") -> list[dict]:
    rows = claims(state)
    if requirement_id:
        rows = [row for row in rows if str(requirement_id) in (row.get("requirement_ids") or ())]
    if actor:
        rows = [row for row in rows if str(row.get("actor", "")) == str(actor)]
    if work_digest:
        rows = [row for row in rows if str(row.get("work_digest", "")) == str(work_digest)]
    if contract_id:
        rows = [row for row in rows if str(row.get("contract_id", "")) == str(contract_id)]
    return rows


def current_claims(state: Mapping[str, Any], *, requirement_id: str = "",
                   work_digest: str = "", contract_id: str = "") -> list[dict]:
    """Claims bound to the current work revision.

    The filter is the point. A claim about revision ``A`` is history, not a statement
    about revision ``B``, and returning it as if it were current would let a repaired
    requirement inherit the repair's predecessor's assurance.
    """
    rows = claims_for(
        state, requirement_id=requirement_id, work_digest=work_digest,
        contract_id=contract_id,
    )
    if not work_digest:
        return rows
    return [row for row in rows if str(row.get("work_digest", "")) == str(work_digest)]


def unmapped(state: Mapping[str, Any]) -> list[dict]:
    """Claims that could not be attached to any requirement.

    Surfaced, not dropped. An overstatement nobody scoped is still an overstatement,
    and it is frequently the one that would have been missed.
    """
    return [row for row in claims(state) if not row.get("requirement_ids")]


def actor_identities(state: Mapping[str, Any]) -> dict[str, list[str]]:
    """Which identities acted in which role, across claims and evidence alike."""
    table: dict[str, set[str]] = {role: set() for role in ACTOR_ROLES}
    for record in claims(state):
        role = str(record.get("actor_role", ""))
        identity = str(record.get("actor_execution") or record.get("actor", ""))
        if role in table and identity:
            table[role].add(identity)
    from . import evidence as evidence_module

    for record in evidence_module.evidence(state):
        role = str(record.get("producer_role", ""))
        identity = str(record.get("producer_execution") or record.get("producer", ""))
        if role in table and identity:
            table[role].add(identity)
    return {role: sorted(values) for role, values in table.items()}


def summarise(state: Mapping[str, Any]) -> dict:
    rows = claims(state)
    by_type: dict[str, int] = {name: 0 for name in contracts.CLAIM_TYPES}
    for record in rows:
        claim_type = str(record.get("claim_type", ""))
        by_type[claim_type] = by_type.get(claim_type, 0) + 1
    return {
        "claims": len(rows),
        "by_type": by_type,
        "unmapped": len(unmapped(state)),
        "external": sum(1 for row in rows if row.get("external")),
        "note": "a claim is not evidence; every claim here is still awaiting assessment",
    }


def problems(state: Mapping[str, Any]) -> list[str]:
    found: list[str] = []
    for record in claims(state):
        found.extend(
            f"claim {record.get('claim_id', '?')}: {problem}"
            for problem in contracts.acceptance_claim_problems(record)
        )
    return list(dict.fromkeys(found))


__all__ = [
    "ACTOR_ROLES",
    "CLAIM_ORIGINS",
    "CLAIM_VERSION",
    "COLLECTION",
    "actor_identities",
    "claim",
    "claims",
    "claims_for",
    "create",
    "current_claims",
    "extract",
    "map_to_requirements",
    "problems",
    "sanitise",
    "split_statements",
    "summarise",
    "unmapped",
]