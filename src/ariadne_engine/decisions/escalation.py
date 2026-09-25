"""The intelligence escalation ladder (AR-205D T6).

.. code-block:: text

    DETERMINISTIC
         | unresolved
    BOUNDED DECISION
         | insufficient / low confidence
    STRONGER BOUNDED DECISION
         | insufficient
    GENERATIVE REASONING
         | policy requires
    HUMAN

Not every task traverses every level, and escalation is never disguised:
:func:`escalation_for` returns structured reasons from the declared vocabulary
rather than the vague "needs a stronger model" that hides an unexplained
decision.

"Stronger" does not mean "more expensive". The available strengthening options
are capability-shaped — an alternate provider that declares the primitive, a
provider specialised for this question, a richer projection, another question
definition version, or an independent second decision — and deliberately carry
no price ordering. Price is not capability, and nothing here selects a provider
by cost.
"""

from __future__ import annotations

from typing import Mapping

from ..contracts import (
    DECISION_CLASSIFICATIONS,
    ESCALATION_REASONS,
    ContractError,
)

ESCALATION_POLICY_VERSION = "ar-205d-escalation-1"
"""The escalation rule-table version recorded on every escalation verdict."""

LADDER = ("DETERMINISTIC", "BOUNDED", "STRONGER_BOUNDED", "GENERATIVE", "HUMAN")
"""The declared rungs, weakest mechanism first."""

STRENGTHENING_OPTIONS = (
    "alternate_provider",
    "specialised_provider",
    "richer_projection",
    "alternate_question_version",
    "independent_second_decision",
)
"""Capability-shaped ways to strengthen a bounded decision. No price ranking."""


def reason_for_record(record: Mapping, *, classification: str = "BOUNDED", consequence: str = "LOW") -> str:
    """The structured reason one decision outcome cannot be acted on.

    Returns an empty string when the decision is accepted as evidence.
    """
    if classification not in DECISION_CLASSIFICATIONS:
        raise ContractError(f"unsupported classification: {classification!r}")
    if consequence == "PROTECTED" or classification == "HUMAN":
        return "POLICY_REQUIRES_HUMAN"
    if classification == "UNRESOLVED":
        return "UNRESOLVED_CLASSIFICATION"
    if classification == "GENERATIVE":
        return "GENERATIVE_REQUIRED"
    status = str(record.get("status", ""))
    if status == "answered" and (record.get("policy_verdict") or {}).get("accepted") is True:
        return ""
    if status == "unavailable":
        return "NO_DECISION_PROVIDER"
    if status == "failed":
        return "DECISION_FAILED"
    if status == "invalid":
        return "OUT_OF_DISTRIBUTION"
    if status == "refused":
        kind = str(record.get("confidence_kind", "NONE"))
        return "LOW_CONFIDENCE" if kind != "NONE" else "NO_CONFIDENCE"
    return "DECISION_REFUSED"


def stronger_options(
    *,
    record: Mapping,
    projection: Mapping | None = None,
    richer_projection_available: bool = False,
    alternate_providers_available: bool = False,
    alternate_definition_available: bool = False,
) -> list[dict]:
    """The capability-shaped strengthening options for one refused decision."""
    options: list[dict] = []
    if alternate_providers_available:
        options.append({
            "option": "alternate_provider",
            "detail": "another configured provider declares this primitive",
            "selected_by": "capability-registry",
        })
    if richer_projection_available:
        options.append({
            "option": "richer_projection",
            "detail": "the projection contract has optional fields this attempt did not carry",
            "selected_by": "projection-contract",
        })
    if alternate_definition_available:
        options.append({
            "option": "alternate_question_version",
            "detail": "an alternative formulation of the same question exists",
            "selected_by": "question-definition",
        })
    options.append({
        "option": "independent_second_decision",
        "detail": "ask one independent provider and compare, without averaging labels",
        "selected_by": "consensus-policy",
    })
    return options


def escalation_for(
    record: Mapping,
    *,
    classification: str = "BOUNDED",
    consequence: str = "LOW",
    generative_available: bool = False,
    stronger_available: bool = False,
) -> dict:
    """The next rung for one decision outcome, with its structured reason.

    A protected consequence always escalates to the human rung. When no
    stronger bounded option and no generative execution exist, the human rung
    is the only honest destination — never a silent retry.
    """
    if classification not in DECISION_CLASSIFICATIONS:
        raise ContractError(f"unsupported classification: {classification!r}")
    if consequence not in ("LOW", "MEDIUM", "HIGH", "PROTECTED"):
        raise ContractError(f"unsupported consequence: {consequence!r}")
    reason = reason_for_record(record, classification=classification, consequence=consequence)
    if not reason:
        return {
            "classification": classification,
            "escalated": False,
            "next": "",
            "reason": "",
            "detail": "the decision was accepted as evidence; the ladder stops here",
            "policy_version": ESCALATION_POLICY_VERSION,
        }
    if reason == "POLICY_REQUIRES_HUMAN":
        return {
            "classification": classification,
            "escalated": True,
            "next": "HUMAN",
            "reason": "POLICY_REQUIRES_HUMAN",
            "detail": "policy reserves this choice to a human; confidence cannot substitute",
            "policy_version": ESCALATION_POLICY_VERSION,
        }
    if reason == "UNRESOLVED_CLASSIFICATION":
        return {
            "classification": classification,
            "escalated": True,
            "next": "HUMAN",
            "reason": "UNRESOLVED_CLASSIFICATION",
            "detail": "the requirement could not be classified safely; policy decides the escalation",
            "policy_version": ESCALATION_POLICY_VERSION,
        }
    if reason == "GENERATIVE_REQUIRED":
        return {
            "classification": classification,
            "escalated": True,
            "next": "GENERATIVE" if generative_available else "HUMAN",
            "reason": "GENERATIVE_REQUIRED",
            "detail": "this requirement needs creation or open-ended reasoning",
            "policy_version": ESCALATION_POLICY_VERSION,
        }
    if stronger_available:
        return {
            "classification": classification,
            "escalated": True,
            "next": "STRONGER_BOUNDED",
            "reason": reason,
            "detail": "a stronger bounded mechanism is available; it is not selected by price",
            "policy_version": ESCALATION_POLICY_VERSION,
        }
    if generative_available:
        return {
            "classification": classification,
            "escalated": True,
            "next": "GENERATIVE",
            "reason": reason,
            "detail": "no stronger bounded mechanism is configured; generation is justified structurally",
            "policy_version": ESCALATION_POLICY_VERSION,
        }
    return {
        "classification": classification,
        "escalated": True,
        "next": "HUMAN",
        "reason": reason,
        "detail": "no safer mechanism is configured; the question goes to a human rather than guessing",
        "policy_version": ESCALATION_POLICY_VERSION,
    }


def problems(verdict: Mapping) -> list[str]:
    """Structural validation of one escalation verdict."""
    problems_found: list[str] = []
    if str(verdict.get("reason", "")) and str(verdict.get("reason")) not in ESCALATION_REASONS:
        problems_found.append(f"an escalation must use a declared reason: {verdict.get('reason')!r}")
    if str(verdict.get("next", "")) and str(verdict.get("next")) not in LADDER:
        problems_found.append(f"an escalation must land on a declared rung: {verdict.get('next')!r}")
    if verdict.get("escalated") and not str(verdict.get("reason", "")):
        problems_found.append("an escalation must record why it happened")
    return problems_found


def describe() -> dict:
    return {
        "ladder": list(LADDER),
        "reasons": list(ESCALATION_REASONS),
        "strengthening_options": list(STRENGTHENING_OPTIONS),
        "policy_version": ESCALATION_POLICY_VERSION,
        "note": "stronger means better-suited capability, not a higher price",
    }


__all__ = [
    "ESCALATION_POLICY_VERSION",
    "LADDER",
    "STRENGTHENING_OPTIONS",
    "reason_for_record",
    "stronger_options",
    "escalation_for",
    "problems",
    "describe",
]
