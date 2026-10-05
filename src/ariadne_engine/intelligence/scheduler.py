"""Choose the cheapest intelligence that has actually earned enough quality for this decision.

Every bounded decision in Ariadne already has a ladder in front of it: deterministic rules, then
a bounded local runtime, then generative generation, then a human. AR-205D built that ladder
from architecture -- *what could answer* -- and that is the wrong question, because a capable
answerer that has never been measured is exactly the thing that should not answer. AR-223
replaces "could" with "has earned", and the change is only possible because
:mod:`~ariadne_engine.intelligence.promotion` produces measured evidence per decision family.

So the scheduler reads an adoption slice rather than a capability list:

* a **deterministic** rule that resolves the question is always preferred, whatever quality the
  model has. Model inference answering a question a table already answers is pure cost;
* a **bounded local** answer is used only when a slice is ``ACTIVE`` for this decision
  definition, question version and model revision, *and* its declared scope covers the request.
  ``scope_matches`` only narrows, so a slice proven for ``LOW`` risk cannot answer a
  ``PROTECTED`` request even if it is brilliant at it;
* anything else **escalates** to generation or to a human.

**The scheduler cannot grant authority, and this is enforced rather than documented.** A
``PROTECTED`` risk class and the named protected operations resolve to ``HUMAN`` before any
profile is consulted, :func:`choose` refuses a request to treat a probability as a permission,
and every record it writes carries ``authorization_effect: none``. Confidence and permission
are different quantities, held by different parties, and this module exists to keep them from
being confused at the one place where they are adjacent.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from ..contracts import ContractError
from ..decisions.runtime import promotion as runtime_promotion
from ..decisions.runtime import selection as runtime_selection
from .corpus import definition_for

SCHEDULER_VERSION = "ar-223-intelligence-scheduling-1"

LEVELS = ("DETERMINISTIC", "BOUNDED_LOCAL", "GENERATIVE", "HUMAN")
"""The ladder, cheapest first.

Ordered by cost and by how little authority they need. ``BOUNDED_LOCAL`` is cheaper than
``GENERATIVE`` and, when it has earned its slice, more predictable; it is not automatically
safer, which is why it sits behind the policy gate rather than ahead of the ladder.
"""

PROTECTED_OPERATIONS = (
    "approve_g1d",
    "grant_g2",
    "accept_protected_work",
    "authorise_release",
    "security_sensitive_mutation",
    "satisfy_human_gate",
)
"""Operations no measurement of any model can ever authorise.

Listed rather than inferred from a risk string, because a risk string is something a caller
supplies and this list is something the repository owns. A caller that names one of these gets
``HUMAN`` no matter what profile is ``ACTIVE``, what its confidence was, or how good its
calibration looked.
"""

RISK_ORDER = ("LOW", "MEDIUM", "HIGH", "PROTECTED")
"""Widening order. A slice may narrow from its declared risk and never widen into it."""


def _widens_to(requested: str, declared: str) -> bool:
    """Whether a requested risk class is wider than one a slice may declare."""
    try:
        return RISK_ORDER.index(str(requested)) > RISK_ORDER.index(str(declared))
    except ValueError:
        return True


def refuse_authority(request: Mapping[str, Any]) -> None:
    """Refuse a request that treats a probability as a permission.

    Raised, not returned, because the callers of this module are scheduling code: a boolean
    somebody might ignore is a weaker guarantee than an exception nobody can accidentally
    route around.
    """
    if bool(request.get("grants_authority", False)) or bool(request.get("accept_work", False)):
        raise ContractError(
            "confidence is not permission: no intelligence level may be asked to grant authority, "
            "accept protected work or satisfy a human gate. Route this to a human"
        )


def choose(
    state: Mapping[str, Any],
    *,
    decision_definition: str,
    question_version: str = "1",
    model_revision: str = "",
    risk: str = "LOW",
    deterministic_available: bool = False,
    deterministic_result: Any = None,
    operation: str = "",
    reversible: bool = True,
    verification_available: bool = False,
    languages: Sequence[str] = ("en",),
    confidence: float | None = None,
    runtime_available: bool = False,
    candidate: Mapping[str, Any] | None = None,
    grants_authority: bool = False,
    accept_work: bool = False,
) -> dict:
    """The level that should answer, and the reason the cheaper levels did not.

    Deterministic first, always. Then a proven bounded slice, and only inside its declared
    scope. Then escalation. The order is the whole module; every branch below it is a
    refinement of "what has earned the right to answer this".

    ``grants_authority`` and ``accept_work`` exist only so a caller can be refused. There is no
    value of either that changes the level chosen.
    """
    refuse_authority(
        {
            "operation": operation,
            "grants_authority": bool(grants_authority),
            "accept_work": bool(accept_work),
        }
    )
    request = {
        "risk": str(risk),
        "reversible": bool(reversible),
        "verification_available": bool(verification_available),
        "languages": [str(item) for item in languages],
    }
    considered: list[dict] = []
    if operation and str(operation) in PROTECTED_OPERATIONS:
        return _decision(
            level="HUMAN",
            reason=f"{operation} is a protected operation; no measured model answers it",
            considered=[{"level": "HUMAN", "because": "protected operation"}],
            definition=decision_definition,
            risk=risk,
            confidence=confidence,
            slice_record={},
            scope_problems=[],
        )
    if str(risk) == "PROTECTED":
        return _decision(
            level="HUMAN",
            reason="the risk class is PROTECTED, which reserves this decision for a person",
            considered=[{"level": "HUMAN", "because": "protected risk class"}],
            definition=decision_definition,
            risk=risk,
            confidence=confidence,
            slice_record={},
            scope_problems=[],
        )
    if deterministic_available:
        considered.append({"level": "DETERMINISTIC", "because": "a declared rule resolves it"})
        return _decision(
            level="DETERMINISTIC",
            reason="a deterministic rule already answers this; model inference would only cost more",
            considered=considered,
            definition=decision_definition,
            risk=risk,
            confidence=confidence,
            slice_record={},
            scope_problems=[],
        )
    considered.append({"level": "DETERMINISTIC", "because": "no declared rule resolves it"})
    record = runtime_promotion.find(
        state,
        decision_definition=str(decision_definition),
        question_version=str(question_version),
        model_revision=str(model_revision),
    ) or {}
    status = str(record.get("status", "")) if record else ""
    if status != "ACTIVE":
        considered.append(
            {
                "level": "BOUNDED_LOCAL",
                "because": f"no ACTIVE slice for this definition and revision (found {status or 'none'})",
            }
        )
        return _decision(
            level="GENERATIVE",
            reason=(
                "the bounded runtime exists but has no ACTIVE slice for this decision definition, "
                "question version and model revision, so its answer would be unmeasured"
            ),
            considered=considered,
            definition=decision_definition,
            risk=risk,
            confidence=confidence,
            slice_record=record,
            scope_problems=[],
        )
    scope_problems = runtime_promotion.scope_matches(record, request)
    if scope_problems:
        considered.append(
            {"level": "BOUNDED_LOCAL", "because": "the ACTIVE slice's scope does not cover this request"}
        )
        return _decision(
            level="GENERATIVE",
            reason=(
                "the slice is ACTIVE but its declared scope does not cover this request, and a "
                "slice may narrow its risk class and never widen it"
            ),
            considered=considered,
            definition=decision_definition,
            risk=risk,
            confidence=confidence,
            slice_record=record,
            scope_problems=scope_problems,
        )
    considered.append({"level": "BOUNDED_LOCAL", "because": "an ACTIVE slice covers this request"})
    return _decision(
        level="BOUNDED_LOCAL",
        reason=(
            "an ACTIVE slice for this definition, question version and model revision covers the "
            "requested risk class, and a measured calibration profile may supply a threshold"
        ),
        considered=considered,
        definition=decision_definition,
        risk=risk,
        confidence=confidence,
        slice_record=record,
        scope_problems=[],
        min_confidence=(float(candidate.get("min_confidence")) if candidate and candidate.get("min_confidence") is not None else None),
        calibration_profile_id=str(dict(candidate).get("profile_id", "")) if candidate else "",
    )


def _decision(
    *,
    level: str,
    reason: str,
    considered: Sequence[Mapping[str, Any]],
    definition: str,
    risk: str,
    confidence: float | None,
    slice_record: Mapping[str, Any],
    scope_problems: Sequence[str],
    min_confidence: float | None = None,
    calibration_profile_id: str = "",
) -> dict:
    return {
        "scheduler_version": SCHEDULER_VERSION,
        "level": level,
        "reason": reason,
        "decision_definition": str(definition),
        "risk": str(risk),
        "considered": [dict(item) for item in considered],
        "slice_id": str(slice_record.get("slice_id", "")),
        "slice_status": str(slice_record.get("status", "")),
        "scope_problems": list(scope_problems),
        "min_confidence": min_confidence,
        "calibration_profile_id": str(calibration_profile_id),
        "observed_confidence": confidence,
        "confidence_grants_nothing": True,
        "escalates": level in ("GENERATIVE", "HUMAN"),
        "authorization_effect": "none",
        "note": (
            "the observed confidence is recorded for review and cannot raise this level, lower a "
            "risk class or satisfy a gate"
        ),
    }


def for_family(
    state: Mapping[str, Any],
    family: str,
    *,
    risk: str = "",
    deterministic_available: bool = False,
    model_revision: str = "",
    question_version: str = "1",
    operation: str = "",
    confidence: float | None = None,
    candidate: Mapping[str, Any] | None = None,
    verification_available: bool = True,
    reversible: bool = True,
    languages: Sequence[str] = ("en",),
) -> dict:
    """:func:`choose` with the family's real definition and default risk filled in.

    ``verification_available`` defaults to true because a caller that has reached the bounded
    level at all is normally the one holding the evidence. It is a parameter rather than a
    constant because the scope check is one-directional: a slice promoted on verification
    cannot be used on a request that has none, and the way to express that is to say so here
    rather than to discover it as a scope problem downstream.
    """
    definition = definition_for(str(family))["definition"]
    from .promotion import RISK_BY_FAMILY

    return choose(
        state,
        decision_definition=definition,
        question_version=question_version,
        model_revision=model_revision,
        risk=str(risk or RISK_BY_FAMILY.get(str(family), "LOW")),
        deterministic_available=deterministic_available,
        operation=operation,
        confidence=confidence,
        candidate=candidate,
        verification_available=bool(verification_available),
        reversible=bool(reversible),
        languages=languages,
    )


def select_provider(
    state: Mapping[str, Any],
    *,
    family: str,
    model_revision: str = "",
    question: Mapping[str, Any] | None = None,
    runtime: Any | None = None,
    provider: Any | None = None,
    risk: str = "",
) -> dict:
    """AR-206's provider selection, reached only when the scheduler chose the bounded level.

    Delegated rather than reimplemented, and deliberately ordered *after*
    :func:`for_family`: AR-206 will happily return an authoritative provider for a definition
    with an ACTIVE slice, and it has no way to know that the request is ``PROTECTED``. Running
    the scheduler first is what keeps a licensed model out of a decision it was never allowed
    to touch.
    """
    decision = for_family(
        state,
        family,
        risk=risk,
        deterministic_available=False,
        model_revision=model_revision,
        verification_available=True,
    )
    if decision["level"] != "BOUNDED_LOCAL":
        return {
            "scheduler_version": SCHEDULER_VERSION,
            "selected": False,
            "decision": decision,
            "selection": {},
            "authorization_effect": "none",
        }
    selection = runtime_selection.select_bounded_provider(
        state,
        provider=provider,
        runtime=runtime,
        definition=decision["decision_definition"],
        question_version="1",
        question=question,
        consequence=decision["risk"],
        scope={
            "risk": decision["risk"],
            "reversible": True,
            "verification_available": True,
            "languages": ["en"],
        },
        reversible=True,
        verification_available=True,
        languages=("en",),
    )
    return {
        "scheduler_version": SCHEDULER_VERSION,
        "selected": str(selection.get("mode", "")) == runtime_selection.MODE_AUTHORITATIVE,
        "decision": decision,
        "selection": selection,
        "authorization_effect": "none",
    }


def describe() -> dict:
    return {
        "version": SCHEDULER_VERSION,
        "levels": list(LEVELS),
        "protected_operations": list(PROTECTED_OPERATIONS),
        "risk_order": list(RISK_ORDER),
        "order": (
            "protected operation or protected risk resolves to a human first; then a deterministic "
            "rule; then a bounded slice proven for this definition and revision and scoped no "
            "wider than the request; then escalation"
        ),
        "invariant": "confidence is never permission",
        "authorization_effect": "none",
    }


__all__ = [
    "LEVELS",
    "PROTECTED_OPERATIONS",
    "RISK_ORDER",
    "SCHEDULER_VERSION",
    "choose",
    "describe",
    "for_family",
    "refuse_authority",
    "select_provider",
]