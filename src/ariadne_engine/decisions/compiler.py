"""The provider-neutral Decision Compiler (AR-205D T1/T3).

The compiler does not answer questions. It decides *what form of intelligence
each unresolved question deserves*, before anything is asked of a provider:

.. code-block:: text

    CAN CODE KNOW IT?
          | yes -> DETERMINISTIC (record the fact, call nothing)
          | no
          v
    CAN IT BE A BOUNDED JUDGMENT?
          | yes -> BOUNDED (closed answer space, projection contract)
          | no
          v
    DOES IT REQUIRE CREATION / OPEN REASONING?
          | yes -> GENERATIVE (with a recorded reason)
          | no  -> UNRESOLVED (policy decides escalation; never silently generative)

    ... and a question policy reserves to a human is HUMAN, whatever the
    confidence any model could report.

The rule table is explicit, versioned and declarative. Unknown requirement
kinds classify as ``UNRESOLVED`` — never as ``GENERATIVE`` — because a silent
default to the most expensive mechanism is exactly the failure this module
exists to prevent.

Code must win when code knows: a requirement that already carries a
deterministically established value is classified ``DETERMINISTIC`` and no
bounded question is created for it. That guard is enforced here and tested by
adversarial cases, not left to callers' discipline.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from .. import contracts
from ..contracts import (
    DECISION_CLASSIFICATIONS,
    DECISION_CLASSIFIABLE_FAILURE_CLASSES,
    DECISION_INTELLIGENCE_CONTRACT,
    EVIDENCE_RELEVANCE_ANSWERS,
    GENERATION_REASONS,
    REVIEW_ESCALATIONS,
    ROUTE_FAMILIES,
    SCHEMA_DECISION_INTELLIGENCE,
    ContractError,
)
from . import policy

COMPILER_VERSION = "ar-205d-decision-compiler-1"
"""The compiler rule-table version recorded on every plan."""

CLASSIFICATION_REASONS = {
    "DETERMINISTIC": (
        "CODE_KNOWS",
        "DETERMINISTIC_RULE",
    ),
    "BOUNDED": ("CLOSED_ANSWER_SPACE",),
    "GENERATIVE": ("OPEN_ENDED",),
    "HUMAN": ("POLICY_REQUIRES_HUMAN",),
    "UNRESOLVED": ("UNRESOLVED_CLASSIFICATION",),
}
"""Why a requirement received its classification."""

DETERMINISTIC_KINDS = {
    "file-exists": "the file system answers this exactly",
    "file-count": "counting files is deterministic",
    "content-hash": "a digest is deterministic",
    "approval-exists": "an approval record either exists and is current, or it does not",
    "test-exit-code": "a process exit code is recorded fact",
    "capability-available": "the capability registry answers this from evidence",
    "revision-match": "two revisions either match or they do not",
    "policy-state": "declared policy state is readable fact",
}
"""Requirement kinds code can establish exactly. No provider is ever consulted."""

BOUNDED_KINDS: dict[str, dict] = {
    "failure-class": {
        "options": DECISION_CLASSIFIABLE_FAILURE_CLASSES,
        "projection_contract": "failure-classification",
        "consequence": "LOW",
        "instructions": (
            "Classify the observed failure into exactly one declared class using only the projected "
            "evidence. Answer UNKNOWN when the evidence does not establish a class."
        ),
    },
    "task-class": {
        "options": ROUTE_FAMILIES,
        "projection_contract": "route-family",
        "consequence": "LOW",
        "instructions": (
            "Choose the route family that best matches the projected task structure. Answer unknown "
            "when the structure does not establish one."
        ),
    },
    "remediation-family": {
        "options": ("repair", "retry", "redesign", "escalate", "unknown"),
        "projection_contract": "failure-classification",
        "consequence": "MEDIUM",
        "instructions": (
            "Choose the remediation family the projected failure evidence supports. Do not choose "
            "escalate merely to avoid a judgement."
        ),
    },
    "review-escalation": {
        "options": REVIEW_ESCALATIONS,
        "projection_contract": "review-escalation",
        "consequence": "MEDIUM",
        "instructions": (
            "Choose the review escalation the projected stakes, scope and verification result support. "
            "Answer human_attention when the evidence cannot establish a lighter escalation."
        ),
    },
    "evidence-relevance": {
        "options": EVIDENCE_RELEVANCE_ANSWERS,
        "projection_contract": "evidence-relevance",
        "consequence": "LOW",
        "instructions": (
            "Decide whether the projected evidence claim materially supports the stated requirement. "
            "Freshness and provenance are given facts, not choices."
        ),
    },
    "design-materiality": {
        "options": ("material", "minor", "cosmetic", "unknown"),
        "projection_contract": "review-escalation",
        "consequence": "LOW",
        "instructions": (
            "Classify how material the projected design finding is to the stated requirement."
        ),
    },
}
"""Requirement kinds that are judgement with a closed answer space."""

GENERATIVE_KINDS: dict[str, str] = {
    "implementation": "CREATION_REQUIRED",
    "repair-content": "REPAIR_CONTENT_REQUIRED",
    "architecture-synthesis": "SYNTHESIS_REQUIRED",
    "open-investigation": "OPEN_ENDED_REASONING_REQUIRED",
    "design-direction": "CREATION_REQUIRED",
    "writing-draft": "CREATION_REQUIRED",
}
"""Requirement kinds that genuinely require creation or open-ended reasoning."""

HUMAN_KINDS = {
    "release-approval",
    "scope-expansion",
    "dependency-install",
    "destructive-action",
    "acceptance",
    "protected-operation",
    "review-waiver",
    "policy-change",
}
"""Requirement kinds policy reserves to a human regardless of any confidence."""

QUESTION_ID_PATTERN_MAX = 79


def _question_id_for(requirement: Mapping, seen: set[str]) -> str:
    base = str(requirement.get("question_id") or requirement.get("kind") or "").strip()
    if not base:
        raise ContractError("a compiled question needs a question id or a declared kind")
    candidate = base[:QUESTION_ID_PATTERN_MAX]
    if candidate in seen:
        suffix = str(requirement.get("requirement_id", "") or "").strip()
        candidate = f"{base[:60]}:{suffix}"[:QUESTION_ID_PATTERN_MAX]
    if candidate in seen:
        raise ContractError(f"the compiled plan repeats question id {candidate!r}")
    seen.add(candidate)
    return candidate


def classify_requirement(requirement: Mapping, *, known: bool = False) -> dict:
    """Classify one requirement without asking anyone anything.

    ``known`` means code has already established the answer; that always wins
    and no question is created.
    """
    kind = str(requirement.get("kind", "") or "").strip()
    if not kind:
        raise ContractError("a requirement needs a declared kind")
    if kind not in DETERMINISTIC_KINDS and kind not in BOUNDED_KINDS and kind not in GENERATIVE_KINDS and kind not in HUMAN_KINDS:
        return {
            "kind": kind,
            "classification": "UNRESOLVED",
            "reason": "UNRESOLVED_CLASSIFICATION",
            "detail": "the compiler has no declared rule for this requirement kind",
        }
    if known:
        return {
            "kind": kind,
            "classification": "DETERMINISTIC",
            "reason": "CODE_KNOWS",
            "detail": "code has already established the answer; no provider is consulted",
        }
    if kind in DETERMINISTIC_KINDS:
        return {
            "kind": kind,
            "classification": "DETERMINISTIC",
            "reason": "DETERMINISTIC_RULE",
            "detail": DETERMINISTIC_KINDS[kind],
        }
    if kind in BOUNDED_KINDS:
        return {
            "kind": kind,
            "classification": "BOUNDED",
            "reason": "CLOSED_ANSWER_SPACE",
            "detail": "judgement with a closed, declared answer space",
        }
    if kind in GENERATIVE_KINDS:
        return {
            "kind": kind,
            "classification": "GENERATIVE",
            "reason": "OPEN_ENDED",
            "detail": "this requirement requires creation or open-ended reasoning",
        }
    return {
        "kind": kind,
        "classification": "HUMAN",
        "reason": "POLICY_REQUIRES_HUMAN",
        "detail": "policy reserves this choice to a human regardless of any confidence",
    }


def _normalise_requirements(requirements: Sequence[Mapping]) -> list[dict]:
    ordered: list[dict] = []
    seen: set[str] = set()
    for index, requirement in enumerate(requirements or ()):
        if not isinstance(requirement, Mapping):
            raise ContractError("a compiled requirement must be a mapping")
        requirement_id = str(requirement.get("requirement_id", "") or f"req-{index + 1}")
        if requirement_id in seen:
            raise ContractError(f"the compiled plan repeats requirement id {requirement_id!r}")
        seen.add(requirement_id)
        value = dict(requirement)
        value["requirement_id"] = requirement_id
        ordered.append(value)
    return ordered


def _dependency_problems(dependencies: Mapping[str, Sequence[str]]) -> list[str]:
    problems: list[str] = []
    for requirement_id, values in dependencies.items():
        for dependency in values or ():
            if str(dependency) == requirement_id:
                problems.append(f"requirement {requirement_id!r} depends on itself")
            elif str(dependency) not in dependencies:
                problems.append(
                    f"requirement {requirement_id!r} depends on {dependency!r}, which is not in the plan"
                )
    resolved: set[str] = set()
    remaining = set(dependencies)
    while remaining:
        ready = {
            key for key in remaining
            if not ({str(item) for item in dependencies.get(key, ())} - resolved)
        }
        if not ready:
            problems.append(
                "the requirement dependencies contain a cycle: " + ", ".join(sorted(remaining))
            )
            break
        resolved.update(ready)
        remaining -= ready
    return problems


def _bounded_question(requirement: Mapping, rule: Mapping, seen: set[str]) -> dict:
    kind = str(requirement["kind"])
    options = tuple(str(item) for item in (requirement.get("options") or rule.get("options") or ()))
    if len(options) < 2:
        raise ContractError(f"bounded requirement {kind} declares fewer than two options")
    primitive = str(requirement.get("primitive") or "ChoiceDecision")
    consequence = str(requirement.get("stakes") or rule.get("consequence") or "LOW")
    if consequence not in contracts.DECISION_CONSEQUENCES:
        raise ContractError(f"bounded requirement {kind} declares an unsupported consequence: {consequence!r}")
    if consequence == "PROTECTED":
        raise ContractError(
            f"bounded requirement {kind} declares PROTECTED consequence; a protected operation is a "
            "human gate, not a bounded question"
        )
    return {
        "requirement_id": str(requirement["requirement_id"]),
        "kind": kind,
        "classification": "BOUNDED",
        "question_id": _question_id_for(requirement, seen),
        "instructions": str(requirement.get("instructions") or rule.get("instructions") or ""),
        "primitive": primitive,
        "options": list(options),
        "consequence": consequence,
        "definition_version": str(requirement.get("definition_version") or "1"),
        "projection_contract": str(
            requirement.get("projection_contract") or rule.get("projection_contract") or ""
        ),
        "depends_on": [str(item) for item in (requirement.get("depends_on") or ())],
    }


def compile_plan(
    state: dict,
    *,
    requirements: Sequence[Mapping],
    task_id: str = "",
    stage: str = "",
    stakes: str = "LOW",
    facts: Mapping[str, Any] | None = None,
    capabilities: Mapping | None = None,
    authorization: Mapping | None = None,
    previous_attempts: Sequence[Mapping] = (),
    failure_evidence: Sequence[Mapping] = (),
    verification_obligations: Sequence[Mapping] = (),
    protected_actions: Sequence[str] = (),
    decision_provider=None,
    generative_available: bool = False,
    deterministic_verification: bool = False,
    record: bool = True,
) -> dict:
    """Compile one decision plan and (by default) record it in the run state.

    This is deterministic construction: it reads declared state and rule tables,
    asks no provider and produces the plan the graph and batch planner consume.

    ``record=False`` compiles an unrecorded sub-plan for one integration call;
    the durable evidence for a bounded question is its decision record, so
    integration advice does not need to grow the task-level plan history.
    """
    if not isinstance(state, dict):
        raise ContractError("the decision compiler needs a run state object")
    if str(stakes) not in contracts.DECISION_CONSEQUENCES:
        raise ContractError(f"unsupported plan stakes: {stakes!r}")
    normalised = _normalise_requirements(requirements)
    known_facts = {str(key): value for key, value in dict(facts or {}).items()}

    facts_out: list[dict] = []
    questions: list[dict] = []
    generative: list[dict] = []
    unresolved: list[dict] = []
    protected: list[dict] = []
    escalations: list[dict] = []
    dependencies: dict[str, list[str]] = {}
    counts = {name: 0 for name in DECISION_CLASSIFICATIONS}
    question_ids: set[str] = set()

    for requirement in normalised:
        requirement_id = str(requirement["requirement_id"])
        kind = str(requirement["kind"])
        declared_known = requirement.get("known")
        if declared_known is not None:
            has_known, known_value = True, declared_known
        elif known_facts.get(requirement_id) is not None:
            has_known, known_value = True, known_facts[requirement_id]
        else:
            has_known, known_value = False, None
        verdict = classify_requirement(requirement, known=has_known)
        classification = verdict["classification"]
        counts[classification] += 1
        dependencies[requirement_id] = [str(item) for item in (requirement.get("depends_on") or ())]
        if classification == "DETERMINISTIC":
            facts_out.append({
                "fact_id": requirement_id,
                "kind": kind,
                "statement": str(requirement.get("statement") or kind),
                "known": bool(has_known),
                "value": known_value if has_known else None,
                "source": str(requirement.get("source") or ("code" if has_known else "check-required")),
                "reason": verdict["reason"],
            })
        elif classification == "BOUNDED":
            question = _bounded_question(requirement, BOUNDED_KINDS.get(kind, {}), question_ids)
            if not question["projection_contract"]:
                raise ContractError(f"bounded requirement {kind} declares no projection contract")
            questions.append(question)
        elif classification == "GENERATIVE":
            reason = str(requirement.get("generative_reason") or GENERATIVE_KINDS.get(kind, ""))
            if reason not in GENERATION_REASONS:
                raise ContractError(
                    f"generative requirement {kind} needs a declared generation reason, got {reason!r}"
                )
            generative.append({
                "requirement_id": requirement_id,
                "kind": kind,
                "reason": reason,
                "detail": str(requirement.get("detail") or ""),
            })
        elif classification == "HUMAN":
            protected.append({
                "requirement_id": requirement_id,
                "kind": kind,
                "statement": str(requirement.get("statement") or kind),
                "gate": str(requirement.get("gate") or "human"),
            })
        else:
            unresolved.append({
                "requirement_id": requirement_id,
                "kind": kind,
                "detail": verdict["detail"],
            })
            escalations.append({"requirement_id": requirement_id, "reason": "UNRESOLVED_CLASSIFICATION"})

    for action in protected_actions or ():
        protected.append({
            "requirement_id": "",
            "kind": "protected-operation",
            "statement": str(action),
            "gate": "human",
        })

    problems = _dependency_problems(dependencies)
    if problems:
        raise ContractError("the compiled decision plan is invalid: " + "; ".join(problems))

    provider_available, provider_reason = (False, "no decision provider is configured")
    provider_identity = {"provider": "", "model": "", "model_version": ""}
    if decision_provider is not None and hasattr(decision_provider, "available"):
        provider_available, provider_reason = decision_provider.available()
        provider_identity = {
            "provider": str(getattr(decision_provider, "provider", "") or ""),
            "model": str(getattr(decision_provider, "model", "") or ""),
            "model_version": str(getattr(decision_provider, "model_version", "") or ""),
        }
    if questions and not provider_available:
        escalations.append({"requirement_id": "", "reason": "NO_DECISION_PROVIDER"})

    avoided_by_deterministic = sum(1 for fact in facts_out if fact["known"])
    avoided_by_bounded = len(questions)
    fallback_policy = {
        "DETERMINISTIC": "compute" if not questions else "compute-then-continue",
        "BOUNDED": "bounded-decision" if provider_available else "deterministic-fallback",
        "GENERATIVE": "generation-with-justification" if generative_available else "human-gate",
        "HUMAN": "human-gate",
        "UNRESOLVED": "escalate-human",
        "provider_unavailable": "deterministic-fallback",
        "low_confidence": "escalate",
        "conflicting_evidence": "escalate",
        "protected": "human-authorization-required",
    }
    fast_path = {
        "applies": bool(
            not questions and not generative and not unresolved and not protected
            and str(stakes) in ("LOW", "MEDIUM")
            and deterministic_verification
        ),
        "reason": (
            "deterministic facts and deterministic verification cover this task; no bounded or "
            "generative call is justified"
        ),
    }
    if fast_path["applies"] and any(fact["known"] is False for fact in facts_out):
        fast_path["applies"] = False
        fast_path["reason"] = "a deterministic check still has to run; the fast path starts after it"

    plan = {
        "schema_version": SCHEMA_DECISION_INTELLIGENCE,
        "plan_id": contracts.new_record_id("dcp"),
        "run_id": str(state.get("run_id", "")),
        "task_id": str(task_id),
        "stage": str(stage),
        "stakes": str(stakes),
        "compiler_version": COMPILER_VERSION,
        "deterministic_facts": facts_out,
        "bounded_questions": questions,
        "generative_needs": generative,
        "dependencies": dependencies,
        "verification_requirements": [dict(item) for item in verification_obligations or ()],
        "protected_actions": protected,
        "unresolved": unresolved,
        "escalations": escalations,
        "fallback_policy": fallback_policy,
        "classifications": counts,
        "fast_path": fast_path,
        "economics": {
            "deterministic_facts": len(facts_out),
            "bounded_questions": len(questions),
            "generative_needs": len(generative),
            "model_calls_avoided_by_deterministic": avoided_by_deterministic,
            "model_calls_avoided_by_bounded_decision": avoided_by_bounded,
            "generative_calls_required": len(generative),
            "note": (
                "structural counts only: a bounded question has a closed answer space and is a "
                "cheaper mechanism than generation; no monetary saving is claimed"
            ),
        },
        "inputs": {
            "capabilities": {str(key): value for key, value in dict(capabilities or {}).items()},
            "authorization": {str(key): value for key, value in dict(authorization or {}).items()},
            "previous_attempts": len(previous_attempts or ()),
            "failure_evidence": len(failure_evidence or ()),
        },
        "provider": {
            "bounded": {
                "available": bool(provider_available),
                "reason": str(provider_reason),
                **provider_identity,
            },
            "generative": {"available": bool(generative_available)},
            "deterministic": {"available": True},
        },
        "policy_version": policy.POLICY_VERSION,
        "contract_version": DECISION_INTELLIGENCE_CONTRACT,
        "authorization_effect": "none",
        "recorded_at": contracts.utc_now(),
    }
    problems = contracts.decision_plan_problems(plan)
    if problems:
        raise ContractError("the compiled decision plan is malformed: " + "; ".join(problems))
    if record:
        contracts.require_collection_capacity(state, "decision_plans")
        state.setdefault("decision_plans", []).append(plan)
    return plan


def plan(state: Mapping, plan_id: str) -> dict | None:
    for record in state.get("decision_plans") or []:
        if isinstance(record, Mapping) and str(record.get("plan_id", "")) == str(plan_id):
            return record
    return None


def latest(state: Mapping, *, task_id: str = "") -> dict | None:
    rows = [
        record for record in (state.get("decision_plans") or [])
        if isinstance(record, Mapping)
        and (not task_id or str(record.get("task_id", "")) == str(task_id))
    ]
    return rows[-1] if rows else None


def summarise(state: Mapping) -> dict:
    """Deterministic compiler counters over the recorded plans."""
    rows = [record for record in (state.get("decision_plans") or []) if isinstance(record, Mapping)]
    classifications: dict[str, int] = {}
    for record in rows:
        for name, value in (record.get("classifications") or {}).items():
            classifications[str(name)] = classifications.get(str(name), 0) + int(value or 0)
    return {
        "plans": len(rows),
        "classifications": dict(sorted(classifications.items())),
        "fast_paths": sum(1 for record in rows if (record.get("fast_path") or {}).get("applies")),
        "questions": sum(len(record.get("bounded_questions") or []) for record in rows),
        "generative_needs": sum(len(record.get("generative_needs") or []) for record in rows),
        "unresolved": sum(len(record.get("unresolved") or []) for record in rows),
        "note": "classification is epistemic; a provider being unavailable is an escalation, not a class",
    }


__all__ = [
    "COMPILER_VERSION",
    "CLASSIFICATION_REASONS",
    "DETERMINISTIC_KINDS",
    "BOUNDED_KINDS",
    "GENERATIVE_KINDS",
    "HUMAN_KINDS",
    "classify_requirement",
    "compile_plan",
    "plan",
    "latest",
    "summarise",
]
