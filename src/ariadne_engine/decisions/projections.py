"""Decision-specific state projections (AR-205D T4/T5).

A bounded decision must receive the *smallest defensible* state projection, not
the whole project. This module turns that principle into four reusable
contracts — failure classification, review escalation, evidence relevance and
route-family selection — where every field is declared as one of:

``REQUIRED``
    the decision cannot be made safely without it; a missing required field
    raises :class:`InsufficientState` (the structured reason is
    ``INSUFFICIENT_STATE``), never a guessed answer;
``OPTIONAL``
    it sharpens the decision but its absence is recorded, not fabricated;
``FORBIDDEN``
    it must never be projected: authorization material, credentials, prompt
    text, or anything that could widen the closed answer space.

The projection is *closed*: a field that is not declared for the contract is
refused rather than silently shipped. Extending a projection therefore requires
a deliberate contract edit — the opposite of leaking state by accident.

Projection minimisation may never omit a fact a safe policy needs. That is why
``protected`` and ``stakes`` are REQUIRED on the contracts whose policy depends
on them, and why the projection carries its own digest on every decision.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from ..contracts import PROJECTION_FIELD_MARKS, ContractError
from .batch import project as bound_projection


class InsufficientState(ContractError):
    """A required projection field is missing; the caller must not guess."""

    reason = "INSUFFICIENT_STATE"


@dataclass(frozen=True)
class ProjectionContract:
    """One declared projection shape for one decision family."""

    contract_id: str
    version: str
    fields: Mapping[str, str]
    note: str = ""

    def __post_init__(self) -> None:
        unknown = sorted(set(self.fields.values()) - set(PROJECTION_FIELD_MARKS))
        if unknown:
            raise ContractError(f"projection contract {self.contract_id} uses unknown marks: {unknown}")
        if not str(self.contract_id or "").strip() or not str(self.version or "").strip():
            raise ContractError("a projection contract needs an id and a version")

    @property
    def required(self) -> tuple[str, ...]:
        return tuple(sorted(name for name, mark in self.fields.items() if mark == "REQUIRED"))

    @property
    def optional(self) -> tuple[str, ...]:
        return tuple(sorted(name for name, mark in self.fields.items() if mark == "OPTIONAL"))

    @property
    def forbidden(self) -> tuple[str, ...]:
        return tuple(sorted(name for name, mark in self.fields.items() if mark == "FORBIDDEN"))

    def as_record(self) -> dict:
        return {
            "contract_id": str(self.contract_id),
            "version": str(self.version),
            "required": list(self.required),
            "optional": list(self.optional),
            "forbidden": list(self.forbidden),
            "note": str(self.note),
        }


CONTRACTS: dict[str, ProjectionContract] = {
    "failure-classification": ProjectionContract(
        contract_id="failure-classification",
        version="1",
        fields={
            "failure": "REQUIRED",
            "validator_outcome": "OPTIONAL",
            "changed_scope": "OPTIONAL",
            "previous_attempt": "OPTIONAL",
            "environment": "OPTIONAL",
            "supplied_evidence": "OPTIONAL",
            "authorization": "FORBIDDEN",
            "credentials": "FORBIDDEN",
            "allowed": "FORBIDDEN",
            "prompt": "FORBIDDEN",
        },
        note=(
            "The failure source and its detail are required. Everything else sharpens the class "
            "and is recorded as absent when it does not exist."
        ),
    ),
    "review-escalation": ProjectionContract(
        contract_id="review-escalation",
        version="1",
        fields={
            "stakes": "REQUIRED",
            "affected_scope": "REQUIRED",
            "verification_result": "REQUIRED",
            "protected": "REQUIRED",
            "review_findings": "OPTIONAL",
            "implementation_evidence": "OPTIONAL",
            "supplied_evidence": "OPTIONAL",
            "authorization": "FORBIDDEN",
            "approval": "FORBIDDEN",
            "credentials": "FORBIDDEN",
            "prompt": "FORBIDDEN",
        },
        note=(
            "Stakes, affected scope, verification result and protected-operation status are "
            "required so the escalation judgement can never be made blind to risk."
        ),
    ),
    "evidence-relevance": ProjectionContract(
        contract_id="evidence-relevance",
        version="1",
        fields={
            "requirement": "REQUIRED",
            "evidence_claim": "REQUIRED",
            "evidence_provenance": "REQUIRED",
            "freshness": "REQUIRED",
            "verification_level": "OPTIONAL",
            "supplied_evidence": "OPTIONAL",
            "authorization": "FORBIDDEN",
            "review_verdict": "FORBIDDEN",
            "credentials": "FORBIDDEN",
            "prompt": "FORBIDDEN",
        },
        note=(
            "Relevance may never override freshness or provenance: both are required fields, and "
            "the deterministic checks run before any judgement is requested."
        ),
    ),
    "route-family": ProjectionContract(
        contract_id="route-family",
        version="1",
        fields={
            "task_kind": "REQUIRED",
            "difficulty": "REQUIRED",
            "stakes": "REQUIRED",
            "available_capabilities": "REQUIRED",
            "required_capabilities": "REQUIRED",
            "stage": "OPTIONAL",
            "protected": "OPTIONAL",
            "supplied_evidence": "OPTIONAL",
            "authorization": "FORBIDDEN",
            "credentials": "FORBIDDEN",
            "prompt": "FORBIDDEN",
        },
        note=(
            "A route family is only requested when task structure has not already resolved it; "
            "the projection states what is known and what is UNKNOWN."
        ),
    ),
}
"""The declared decision projections, one per decision family."""


def contract(contract_id: str) -> ProjectionContract:
    value = CONTRACTS.get(str(contract_id))
    if value is None:
        raise ContractError(
            f"unknown projection contract {contract_id!r}; declared: " + ", ".join(sorted(CONTRACTS))
        )
    return value


def contract_problems(contract: ProjectionContract) -> list[str]:
    """Structural problems of one projection contract (used by tests and docs)."""
    problems: list[str] = []
    overlap = sorted(set(contract.required) & set(contract.forbidden))
    if overlap:
        problems.append(f"fields are both required and forbidden: {', '.join(overlap)}")
    if not contract.required:
        problems.append("a projection contract declares no required field")
    return problems


def build(
    contract_id: str,
    *,
    entries: Mapping[str, Any],
    verification_level: str = "",
    missing_is_fatal: bool = True,
) -> dict:
    """Bound, mark-check and digest one decision projection.

    Unknown and forbidden fields are refused. Missing required fields raise
    :class:`InsufficientState` when ``missing_is_fatal`` is true; a caller that
    must record the insufficiency instead of raising may set it to false and
    read ``missing_required`` from the result.
    """
    shape = contract(contract_id)
    if not isinstance(entries, Mapping):
        raise ContractError("a decision projection must be a mapping of named evidence slices")
    declared = set(shape.fields)
    given = {str(key) for key in entries}
    forbidden = sorted(given & set(shape.forbidden))
    if forbidden:
        raise ContractError(
            f"projection {contract_id} forbids field(s): {', '.join(forbidden)}; "
            "authorization and prompt material never enter a bounded decision"
        )
    undeclared = sorted(given - declared)
    if undeclared:
        raise ContractError(
            f"projection {contract_id} has undeclared field(s): {', '.join(undeclared)}; "
            "declare the field in the contract instead of shipping state by accident"
        )
    missing = sorted(name for name in shape.required if entries.get(name) is None)
    if missing and missing_is_fatal:
        raise InsufficientState(
            f"projection {contract_id} is missing required field(s): {', '.join(missing)}; "
            "the decision must report INSUFFICIENT_STATE instead of guessing"
        )
    bounded = bound_projection(entries={str(key): value for key, value in entries.items()})
    return {
        "contract_id": shape.contract_id,
        "contract_version": shape.version,
        "entries": bounded["entries"],
        "digest": bounded["digest"],
        "chars": bounded["chars"],
        "verification_level": str(verification_level or ""),
        "missing_required": missing,
        "required": list(shape.required),
        "optional": list(shape.optional),
        "forbidden": list(shape.forbidden),
    }


def describe() -> dict:
    """The declared contracts, for documentation and inspection surfaces."""
    return {
        "contracts": [CONTRACTS[key].as_record() for key in sorted(CONTRACTS)],
        "note": (
            "a projection is closed: required fields must be present, forbidden fields never are, "
            "and every decision records the digest of exactly what it saw"
        ),
    }


__all__ = [
    "InsufficientState",
    "ProjectionContract",
    "CONTRACTS",
    "contract",
    "contract_problems",
    "build",
    "describe",
]
