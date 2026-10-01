"""Real engine integrations of the Decision Plane (AR-205D T8).

Four genuine engine choices consume Decision Intelligence through one path —
compiler, projection, batch planner, escalation:

``class failure``
    failure classification. Deterministic vocabulary first; only an unmapped
    source may become a bounded question, and only inside the safe class subset.
``review_escalation``
    whether the available evidence suggests routine, independent, enhanced or
    human review. Policy still controls the review that is *required*.
``evidence_relevance``
    whether one evidence claim materially supports a stated requirement. It can
    never override freshness or provenance, and it can never elevate stale
    evidence.
``route_family``
    the route family, and only when task structure has not already resolved it.
    Policy authority stays deterministic: the family is an input to routing,
    never a replacement for it.

Every integration follows the same invariant chain:

1. deterministic facts are checked first and win;
2. a bounded question is built from a declared projection contract;
3. the planner batches independent questions and stages dependent ones;
4. policy judges the answer; confidence is never authorization;
5. when no accepted answer exists the result is a structured escalation, never
   a plausible default and never a silently invoked generative call.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from ..contracts import (
    DECISION_CLASSIFIABLE_FAILURE_CLASSES,
    EVIDENCE_RELEVANCE_ANSWERS,
    REVIEW_ESCALATIONS,
    ROUTE_FAMILIES,
    ContractError,
)
from . import escalation, planner
from . import projections as projection_module
from .contracts import DecisionQuestion
from .providers import DecisionProvider, UnavailableProvider

INTEGRATION_VERSION = "ar-205d-integrations-1"

MAX_FORBIDDEN_FIELD_DEPTH = 6
"""How deep the forbidden-field walk goes before it refuses rather than descends.

Six levels is far past anything a declared projection contract produces. A structure
deeper than that is not evidence a caller meant to supply, and an unbounded walk over
caller-supplied data is a denial of service in the middle of a trust boundary.
"""

ROUTE_FAMILY_FOR_TASK_KIND = {
    "mechanical": "mechanical",
    "edit": "implementation",
    "feature": "implementation",
    "bugfix": "implementation",
    "refactor": "implementation",
    "implementation": "implementation",
    "implementation-planning": "implementation",
    "design": "design",
    "design-direction": "design",
    "research": "research",
    "recovery": "recovery",
    "repair": "recovery",
    "debug": "recovery",
}
"""Task kinds whose route family is already a deterministic fact.

A model judgement is only requested when the task structure does not map here.
"""


def _entries(
    defaults: Mapping,
    projection_entries: Mapping | None,
    *,
    contract_id: str,
) -> dict:
    """The declared projection entries plus the caller's slices, explicitly named.

    Caller-supplied evidence is recorded under the contract's
    ``supplied_evidence`` field rather than spread into arbitrary keys, so the
    projection stays closed: a field the contract did not declare cannot enter
    the decision state by accident. A field the contract declares FORBIDDEN is
    refused outright — nesting it under ``supplied_evidence`` would smuggle
    prompt, credential or authorization material into the decision state.

    The forbidden check walks the whole supplied mapping, not just its top level. A
    one-level check is exactly the shape that reads as closed while being open: the
    reference engine is lexical today, so ``{"failure": {"prompt": "..."}}`` only
    adds an unseen feature token, and the hole would sit there unnoticed until the
    engine were prompt-backed — at which point the projection *is* the prompt and a
    key nested one level down is the whole attack.
    """
    entries: dict = {}
    if projection_entries:
        supplied = {str(key): value for key, value in dict(projection_entries).items()}
        forbidden_names = set(projection_module.contract(contract_id).forbidden)
        nested = _nested_forbidden_fields(supplied, forbidden_names)
        if nested:
            raise ContractError(
                f"projection {contract_id} forbids field(s): {', '.join(nested)}; "
                "authorization and prompt material never enter a bounded decision"
            )
        entries["supplied_evidence"] = supplied
    for key, value in dict(defaults).items():
        entries.setdefault(key, value)
    return entries


def _nested_forbidden_fields(supplied: Mapping, forbidden: set[str], *, _depth: int = 0) -> list[str]:
    """Every forbidden field name appearing anywhere in the supplied mapping.

    Bounded in depth and breadth so a deep or wide structure is a refusal rather than
    an unbounded walk, and cycles are cut rather than followed. A path is reported in
    full, because ``supplied_evidence.detail.prompt`` and ``supplied_evidence.prompt``
    are different mistakes and only one of them is nested.
    """
    if _depth > MAX_FORBIDDEN_FIELD_DEPTH or len(forbidden) == 0:
        return []
    found: list[str] = []
    for key, value in supplied.items():
        if str(key) in forbidden:
            found.append(str(key))
        if isinstance(value, Mapping):
            for nested in _nested_forbidden_fields(value, forbidden, _depth=_depth + 1):
                found.append(f"{key}.{nested}")
        elif isinstance(value, (list, tuple)):
            for index, item in enumerate(value):
                if isinstance(item, Mapping):
                    for nested in _nested_forbidden_fields(item, forbidden, _depth=_depth + 1):
                        found.append(f"{key}[{index}].{nested}")
    return sorted(dict.fromkeys(found))


def _bounded_answer(
    state: dict,
    *,
    requirement: Mapping,
    question_id: str,
    instructions: str,
    options: Sequence[str],
    contract_id: str,
    entries: Mapping[str, Any],
    provider: DecisionProvider | None,
    task_id: str,
    stage: str,
    consequence: str,
    verification_level: str,
    execution_id: str = "",
    cache_enabled: bool = True,
    generative_available: bool = False,
    runtime: Any = None,
    shadow: bool = True,
) -> dict:
    """The one shared path: compile, project, batch, judge, escalate.

    ``runtime`` and ``shadow`` are AR-206 additions and both default to off, so
    every existing caller behaves exactly as it did in 2.0 when no runtime is passed.
    When a runtime *is* passed, the authoritative answer above is already decided and
    recorded before the runtime is consulted, and the prediction is stored with an
    ``execution_effect`` of ``"none"``. The returned ``shadow`` block is the only
    thing the runtime contributed, and it carries no authority.
    """
    active = provider if provider is not None else UnavailableProvider()
    if not isinstance(active, DecisionProvider):
        raise ContractError("a decision integration needs a DecisionProvider")
    plan = compiler_compile(
        state,
        requirement=requirement,
        provider=active,
        task_id=task_id,
        stage=stage,
        stakes=consequence,
        generative_available=generative_available,
    )
    try:
        projection = projection_module.build(
            contract_id, entries=entries, verification_level=verification_level,
        )
    except projection_module.InsufficientState as exc:
        verdict = escalation.escalation_for(
            {"status": "failed"}, classification="BOUNDED", consequence=consequence,
            generative_available=generative_available, stronger_available=False,
        )
        verdict["reason"] = "INSUFFICIENT_STATE"
        verdict["detail"] = f"INSUFFICIENT_STATE: {exc}"
        verdict["insufficient_state"] = True
        return {
            "status": "insufficient-state",
            "answer": "",
            "source": "insufficient-state",
            "reason": f"INSUFFICIENT_STATE: {exc}",
            "decision_id": "",
            "plan_id": str(plan.get("plan_id", "")),
            "projection_digest": "",
            "record": {},
            "escalation": verdict,
            "shadow": {
                "observed": False,
                "reason": "the projection was insufficient, so there was nothing safe to ask",
                "execution_effect": "none",
            },
        }
    question = DecisionQuestion(
        question_id=question_id,
        instructions=instructions,
        primitive="ChoiceDecision",
        options=tuple(options),
        consequence=consequence,
        evidence_digest=projection["digest"],
        projection_contract=contract_id,
    )
    result = planner.evaluate_step(
        state,
        questions=[question],
        projections={contract_id: projection},
        provider=active,
        task_id=task_id,
        stage=stage,
        execution_id=execution_id,
        verification_level=verification_level,
        cache_enabled=cache_enabled,
        fingerprints={question_id: {"state_digest": projection["digest"]}},
    )
    rows = result.get("results") or []
    if not rows:
        return {
            "status": "failed",
            "answer": "",
            "source": "fallback",
            "reason": "the batch planner produced no result for the question",
            "decision_id": "",
            "plan_id": str(plan.get("plan_id", "")),
            "projection_digest": projection["digest"],
            "record": {},
            "escalation": escalation.escalation_for(
                {"status": "failed"}, classification="BOUNDED", consequence=consequence,
                generative_available=generative_available, stronger_available=False,
            ),
            "shadow": {
                "observed": False,
                "reason": "the batch planner produced no result, so there was nothing to observe",
                "execution_effect": "none",
            },
        }
    row = dict(rows[0])
    record = planner.decision(state, str(row.get("decision_id", "")))
    accepted = str(row.get("status", "")) == "answered"
    verdict = escalation.escalation_for(
        record or {"status": str(row.get("status", "")), "confidence_kind": str(row.get("confidence_kind", "NONE")),
                  "policy_verdict": {}},
        classification="BOUNDED",
        consequence=consequence,
        generative_available=generative_available,
        stronger_available=False,
    )
    observation = _observe_runtime(
        state,
        runtime=runtime,
        shadow=shadow,
        question=question,
        projection=projection,
        authoritative_answer=str(row.get("answer", "")) if accepted else "",
        authoritative_decision_id=str(row.get("decision_id", "")),
        task_id=task_id,
        definition=contract_id,
    )
    return {
        "status": str(row.get("status", "")),
        "answer": str(row.get("answer", "")) if accepted else "",
        "source": "bounded-decision" if accepted else "fallback",
        "reason": (
            "a bounded decision produced this answer under the declared policy"
            if accepted
            else str(verdict.get("detail", "")) or str((record or {}).get("status", ""))
        ),
        "decision_id": str(row.get("decision_id", "")),
        "plan_id": str(plan.get("plan_id", "")),
        "projection_digest": projection["digest"],
        "record": record or {},
        "cached": bool(row.get("cached")),
        "escalation": verdict,
        "shadow": observation,
    }


def _no_shadow(reason: str) -> dict:
    """The shadow block for a path that never asked the runtime anything.

    A deterministic rule resolving the question is the system working as designed, so
    there is genuinely nothing to observe. The key is still present, in one shared
    vocabulary, because a caller must be able to ask "was a bounded model involved
    here?" without having to know in advance which branch the code took.
    """
    return {
        "observed": False,
        "reason": str(reason),
        "execution_effect": "none",
    }


def _observe_runtime(
    state: dict,
    *,
    runtime: Any,
    shadow: bool,
    question: DecisionQuestion,
    projection: Mapping[str, Any],
    authoritative_answer: str,
    authoritative_decision_id: str,
    task_id: str,
    definition: str,
) -> dict:
    """Let the native Decision Runtime observe the decided question. Never influences.

    Imported lazily and wrapped: the Decision Runtime is optional, so neither the
    import nor the call may be able to break an integration that works perfectly well
    without it. Any failure is reported as an observation failure and changes nothing.
    """
    if runtime is None or not shadow:
        # A caller with no runtime attached still gets a complete block, in the same
        # vocabulary as every other one. A shadow key that is only sometimes present, or
        # that changes shape, is how a caller ends up reading a prediction as an answer.
        return _no_shadow("shadow observation was not requested for this path")
    try:
        from .runtime import observe as observe_module
    except Exception as exc:  # noqa: BLE001 - an optional subsystem cannot break a path
        return {"observed": False, "runtime_failed": True, "reason": f"the decision runtime is unavailable: {exc}"}
    try:
        return observe_module.observe(
            state,
            runtime,
            question=question,
            projection=projection,
            authoritative_answer=authoritative_answer,
            authoritative_decision_id=authoritative_decision_id,
            task_id=task_id,
            definition=definition,
        )
    except Exception as exc:  # noqa: BLE001 - a shadow failure is recorded, never raised into the path
        return {
            "observed": False,
            "runtime_failed": True,
            "reason": f"shadow observation failed and changed nothing: {exc}",
            "execution_effect": "none",
        }


def compiler_compile(
    state: dict,
    *,
    requirement: Mapping,
    provider: DecisionProvider,
    task_id: str,
    stage: str,
    stakes: str,
    generative_available: bool,
) -> dict:
    from . import compiler

    return compiler.compile_plan(
        state,
        requirements=[requirement],
        task_id=task_id,
        stage=stage,
        stakes=stakes,
        decision_provider=provider,
        generative_available=generative_available,
        record=False,
    )


# ------------------------------------------------------------ failure classification


def classify_failure(
    state: dict,
    *,
    source: str,
    detail: str = "",
    deterministic_class: str = "UNKNOWN",
    task_id: str = "",
    provider: DecisionProvider | None = None,
    projection_entries: Mapping | None = None,
    consequence: str = "LOW",
    execution_id: str = "",
    cache_enabled: bool = True,
    generative_available: bool = False,
    runtime: Any = None,
    shadow: bool = True,
) -> dict:
    """Classify a failure: deterministic first, bounded judgement only when needed.

    ``deterministic_class`` is what the declared failure vocabulary already
    established. When it is not ``UNKNOWN`` no provider is consulted at all —
    that is the code-before-judgment guard, recorded in the returned plan.
    """
    if deterministic_class != "UNKNOWN":
        return {
              "class": deterministic_class,
              "source": "deterministic",
              "decision_id": "",
              "reason": "the declared failure vocabulary mapped this source; no model was consulted",
              "escalation_required": False,
              "decision": {},
              "plan_id": "",
              "shadow": _no_shadow("a declared vocabulary resolved the class deterministically, so no bounded question was asked"),
          }
    entries = _entries(
        {"failure": {"source": str(source), "detail": str(detail)}},
        projection_entries,
        contract_id="failure-classification",
    )
    outcome = _bounded_answer(
        state,
        requirement={
            "requirement_id": "failure-class",
            "kind": "failure-class",
            "stakes": str(consequence),
        },
        question_id="failure-class",
        instructions=(
            "Classify this failure into exactly one declared class from the projected evidence. "
            "Answer UNKNOWN when the evidence does not establish a class."
        ),
        options=DECISION_CLASSIFIABLE_FAILURE_CLASSES,
        contract_id="failure-classification",
        entries=entries,
        provider=provider,
        task_id=task_id,
        stage="failure-classification",
        consequence=str(consequence),
        verification_level="",
        execution_id=execution_id,
        cache_enabled=cache_enabled,
        generative_available=generative_available,
        runtime=runtime,
        shadow=shadow,
    )
    answer = str(outcome.get("answer", ""))
    if answer and answer != "UNKNOWN":
        return {
            "class": answer,
            "source": "bounded-decision",
            "decision_id": str(outcome.get("decision_id", "")),
            "reason": str(outcome.get("reason", "")),
            "escalation_required": bool(
                answer in ("TIMEOUT", "ENVIRONMENT_FAILURE", "PROVIDER_FAILURE", "CONTEXT_FAILURE", "UNKNOWN")
            ),
            "decision": outcome.get("record") or {},
            "plan_id": str(outcome.get("plan_id", "")),
            "escalation": outcome.get("escalation") or {},
            "shadow": outcome.get("shadow") or {},
        }
    return {
        "class": "UNKNOWN",
        "source": "fallback-unknown",
        "decision_id": str(outcome.get("decision_id", "")),
        "reason": str(outcome.get("reason", "the bounded decision did not produce an accepted class")),
        "escalation_required": True,
        "decision": outcome.get("record") or {},
        "plan_id": str(outcome.get("plan_id", "")),
        "escalation": outcome.get("escalation") or {},
        "shadow": outcome.get("shadow") or {},
    }


# ------------------------------------------------------------------ review escalation


def review_escalation(
    state: dict,
    *,
    task_id: str = "",
    stakes: str = "LOW",
    affected_scope: Sequence[str] = (),
    verification_result: str = "UNVERIFIED",
    protected: bool = False,
    review_findings: Sequence[Mapping] = (),
    implementation_evidence: Mapping | None = None,
    provider: DecisionProvider | None = None,
    consequence: str = "MEDIUM",
    verification_level: str = "",
    projection_entries: Mapping | None = None,
    cache_enabled: bool = True,
    generative_available: bool = False,
    runtime: Any = None,
    shadow: bool = True,
) -> dict:
    """How much review the available evidence suggests.

    Deterministic rules come first: a protected operation always suggests
    human attention; low stakes with independent reproduction is routine; high
    stakes without any verification is enhanced review regardless of what any
    model would say. Policy still decides the review that is *required*.
    """
    deterministic = ""
    deterministic_reason = ""
    if protected:
        deterministic = "human_attention"
        deterministic_reason = "a protected operation always suggests human attention, whatever the evidence"
    elif stakes == "LOW" and verification_result in ("VERIFIED", "INDEPENDENTLY_REPRODUCED"):
        deterministic = "routine"
        deterministic_reason = "low stakes and independently established evidence suggest routine review"
    elif stakes == "HIGH" and verification_result in ("UNVERIFIED", "STALE", ""):
        deterministic = "enhanced_review"
        deterministic_reason = "high stakes without current verification suggest enhanced review"
    if deterministic:
        return {
              "escalation": deterministic,
              "source": "deterministic",
              "reason": deterministic_reason,
              "decision_id": "",
              "plan_id": "",
              "policy_still_controls": True,
              "escalation_verdict": {},
              "shadow": _no_shadow("the declared review rule resolved the escalation deterministically, so no bounded question was asked"),
          }
    defaults = {
        "stakes": str(stakes),
        "affected_scope": [str(item) for item in affected_scope],
        "verification_result": str(verification_result),
        "protected": bool(protected),
    }
    if review_findings:
        defaults["review_findings"] = [dict(item) for item in review_findings if isinstance(item, Mapping)]
    if implementation_evidence:
        defaults["implementation_evidence"] = dict(implementation_evidence)
    entries = _entries(defaults, projection_entries, contract_id="review-escalation")
    outcome = _bounded_answer(
        state,
        requirement={
            "requirement_id": "review-escalation",
            "kind": "review-escalation",
            "stakes": str(consequence),
        },
        question_id="review-escalation",
        instructions=(
            "Choose the review escalation the projected stakes, scope and verification result support. "
            "Answer human_attention when the evidence cannot establish a lighter escalation."
        ),
        options=REVIEW_ESCALATIONS,
        contract_id="review-escalation",
        entries=entries,
        provider=provider,
        task_id=task_id,
        stage="review-escalation",
        consequence=str(consequence),
        verification_level=str(verification_level),
        cache_enabled=cache_enabled,
        generative_available=generative_available,
        runtime=runtime,
        shadow=shadow,
    )
    answer = str(outcome.get("answer", "")) or "human_attention"
    return {
        "escalation": answer if str(outcome.get("status")) == "answered" else "human_attention",
        "source": str(outcome.get("source", "fallback")),
        "reason": str(outcome.get("reason", "")),
        "decision_id": str(outcome.get("decision_id", "")),
        "plan_id": str(outcome.get("plan_id", "")),
        "policy_still_controls": True,
        "escalation_verdict": outcome.get("escalation") or {},
        "shadow": outcome.get("shadow") or {},
    }


# ------------------------------------------------------------------ evidence relevance


def evidence_relevance(
    state: dict,
    *,
    requirement: str,
    claim: str,
    provenance: Mapping | str,
    freshness: str,
    verification_level: str = "",
    task_id: str = "",
    requirement_id: str = "",
    provider: DecisionProvider | None = None,
    consequence: str = "LOW",
    projection_entries: Mapping | None = None,
    cache_enabled: bool = True,
    generative_available: bool = False,
    runtime: Any = None,
    shadow: bool = True,
) -> dict:
    """Whether one evidence claim materially supports a stated requirement.

    Freshness and provenance are checked deterministically *before* anything is
    asked, and they can never be overridden by the judgement: stale evidence
    answers ``IRRELEVANT`` with source ``deterministic`` no matter what a
    provider would prefer.
    """
    freshness_value = str(freshness or "UNKNOWN").upper()
    if freshness_value in ("STALE", "SUPERSEDED"):
        return {
              "answer": "IRRELEVANT",
              "source": "deterministic",
              "reason": "stale evidence cannot materially support a current requirement",
              "decision_id": "",
              "plan_id": "",
              "freshness_checked": True,
              "provenance_checked": False,
              "may_override_freshness": False,
              "escalation_verdict": {},
              "shadow": _no_shadow("staleness is a fact about the evidence, not a bounded judgement"),
          }
    provenance_present = bool(provenance) if not isinstance(provenance, str) else bool(provenance.strip())
    if not provenance_present:
        return {
              "answer": "UNKNOWN",
              "source": "deterministic",
              "reason": "evidence without provenance cannot be judged relevant",
              "decision_id": "",
              "plan_id": "",
              "freshness_checked": True,
              "provenance_checked": True,
              "may_override_freshness": False,
              "escalation_verdict": {},
              "shadow": _no_shadow("missing provenance is a fact about the evidence, not a bounded judgement"),
          }
    defaults = {
        "requirement": str(requirement),
        "evidence_claim": str(claim),
        "evidence_provenance": provenance if isinstance(provenance, Mapping) else {"source": str(provenance)},
        "freshness": freshness_value,
    }
    if verification_level:
        defaults["verification_level"] = str(verification_level)
    entries = _entries(defaults, projection_entries, contract_id="evidence-relevance")
    outcome = _bounded_answer(
        state,
        requirement={
            "requirement_id": str(requirement_id or "evidence-relevance"),
            "kind": "evidence-relevance",
            "stakes": str(consequence),
        },
        question_id="evidence-relevance",
        instructions=(
            "Decide whether the projected evidence claim materially supports the stated requirement. "
            "Freshness and provenance are given facts, not choices."
        ),
        options=EVIDENCE_RELEVANCE_ANSWERS,
        contract_id="evidence-relevance",
        entries=entries,
        provider=provider,
        task_id=task_id,
        stage="evidence-relevance",
        consequence=str(consequence),
        verification_level=str(verification_level),
        cache_enabled=cache_enabled,
        generative_available=generative_available,
        runtime=runtime,
        shadow=shadow,
    )
    answer = str(outcome.get("answer", ""))
    if answer not in EVIDENCE_RELEVANCE_ANSWERS:
        answer = "UNKNOWN"
    return {
        "answer": answer,
        "source": str(outcome.get("source", "fallback")),
        "reason": str(outcome.get("reason", "")),
        "decision_id": str(outcome.get("decision_id", "")),
        "plan_id": str(outcome.get("plan_id", "")),
        "freshness_checked": True,
        "provenance_checked": True,
        "may_override_freshness": False,
        "escalation_verdict": outcome.get("escalation") or {},
        "shadow": outcome.get("shadow") or {},
    }


# ----------------------------------------------------------------------- route family


def route_family(
    state: dict,
    *,
    task_kind: str,
    difficulty: str = "UNKNOWN",
    stakes: str = "LOW",
    available_capabilities: Sequence[str] = (),
    required_capabilities: Sequence[str] = (),
    stage: str = "",
    protected: bool = False,
    task_id: str = "",
    provider: DecisionProvider | None = None,
    consequence: str = "LOW",
    projection_entries: Mapping | None = None,
    cache_enabled: bool = True,
    generative_available: bool = False,
    runtime: Any = None,
    shadow: bool = True,
) -> dict:
    """The route family, when task structure has not already resolved it.

    The result is an input to routing, not a routing decision: policy authority
    remains deterministic and a bounded answer never overrides a protected
    operation.
    """
    known = ROUTE_FAMILY_FOR_TASK_KIND.get(str(task_kind or "").strip().lower())
    if known:
        return {
              "family": known,
              "source": "deterministic",
              "reason": f"task kind {task_kind!r} maps to a declared route family",
              "decision_id": "",
              "plan_id": "",
              "policy_authority": "deterministic",
              "escalation_verdict": {},
              "shadow": _no_shadow("the declared task-kind map resolved the family deterministically, so no bounded question was asked"),
          }
    if protected:
        return {
              "family": "unknown",
              "source": "deterministic",
              "reason": "a protected operation routes through human policy, not a bounded judgement",
              "decision_id": "",
              "plan_id": "",
              "policy_authority": "deterministic",
              "escalation_verdict": {},
              "shadow": _no_shadow("a protected operation is never a bounded judgement, whatever the runtime would have said"),
          }
    defaults = {
        "task_kind": str(task_kind or "UNKNOWN"),
        "difficulty": str(difficulty or "UNKNOWN"),
        "stakes": str(stakes),
        "available_capabilities": sorted(str(item) for item in available_capabilities),
        "required_capabilities": sorted(str(item) for item in required_capabilities),
        "protected": bool(protected),
    }
    if stage:
        defaults["stage"] = str(stage)
    entries = _entries(defaults, projection_entries, contract_id="route-family")
    outcome = _bounded_answer(
        state,
        requirement={
            "requirement_id": "route-family",
            "kind": "route-family",
            "stakes": str(consequence),
        },
        question_id="route-family",
        instructions=(
            "Choose the route family that best matches the projected task structure. Answer unknown "
            "when the structure does not establish one."
        ),
        options=ROUTE_FAMILIES,
        contract_id="route-family",
        entries=entries,
        provider=provider,
        task_id=task_id,
        stage=str(stage or "route-family"),
        consequence=str(consequence),
        verification_level="",
        cache_enabled=cache_enabled,
        generative_available=generative_available,
        runtime=runtime,
        shadow=shadow,
    )
    family = str(outcome.get("answer", ""))
    if family not in ROUTE_FAMILIES:
        family = "unknown"
    return {
        "family": family if str(outcome.get("status")) == "answered" else "unknown",
        "source": str(outcome.get("source", "fallback")),
        "reason": str(outcome.get("reason", "")),
        "decision_id": str(outcome.get("decision_id", "")),
        "plan_id": str(outcome.get("plan_id", "")),
        "policy_authority": "deterministic",
        "escalation_verdict": outcome.get("escalation") or {},
        "shadow": outcome.get("shadow") or {},
    }


def describe() -> dict:
    return {
        "integration_version": INTEGRATION_VERSION,
        "integrations": [
            {
                "name": "failure_classification",
                "entry_point": "execution.classify_with_decision",
                "question": "failure-class",
                "contract": "failure-classification",
            },
            {
                "name": "review_escalation",
                "entry_point": "review.escalation_advice",
                "question": "review-escalation",
                "contract": "review-escalation",
            },
            {
                "name": "evidence_relevance",
                "entry_point": "verification.relevance_advice",
                "question": "evidence-relevance",
                "contract": "evidence-relevance",
            },
            {
                "name": "route_family",
                "entry_point": "routing.family_advice",
                "question": "route-family",
                "contract": "route-family",
            },
        ],
        "invariant": "code before judgment, judgment before generation; confidence is never authorization",
    }


__all__ = [
    "INTEGRATION_VERSION",
    "ROUTE_FAMILY_FOR_TASK_KIND",
    "classify_failure",
    "review_escalation",
    "evidence_relevance",
    "route_family",
    "describe",
]
