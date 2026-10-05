"""Verification decisions: one verdict per requirement, per pass, with reasons.

This is the module that decides. Everything upstream measures -- the contract says what
was asked, the requirements say what must hold, the evidence says what was observed -- and
this module turns that into one of six answers per requirement, every time, with the
reason and the evidence attached.

**The six verdicts, precisely.**

``PROVEN``
    Current evidence, sufficient under this requirement's own declared policy, establishes
    it. Not *probably implemented*. Not *the worker said complete*.

``PARTIAL``
    A meaningful subset is established and the rest is outstanding. Used sparingly and
    deliberately: if the requirement should have been split instead, the honest response is
    to fix the requirement model rather than to report 60% of an un-split sentence. The
    split is offered by
    :func:`~ariadne_engine.acceptance.requirements.split_candidate` and applied by a
    human, because requirement atomisation that runs unattended is requirement explosion.

``UNPROVEN``
    No contradictory evidence exists, and sufficient current evidence is missing. **This is
    not ``FAILED``.** Missing evidence is not failure; it is missing evidence. Collapsing
    the two is how a system learns to report unbuilt work as broken and broken work as
    merely uninspected.

``FAILED``
    Current evidence directly observes the requirement being violated. This is about the
    *work*, and it stands on its own with or without anybody having claimed anything.

``CONTRADICTED``
    Not a requirement verdict. It describes a **worker's claim** that current evidence
    directly disproves, and :func:`verification_decision_problems` refuses it as a
    requirement verdict precisely to keep the two apart. So ``R7 -> FAILED`` alongside
    ``C13 "R7 fixed" -> CONTRADICTED`` is two records saying two different true things,
    and ``R7 -> FAILED`` with no claim at all is one record saying one true thing.

``NEEDS_HUMAN``
    The available evidence cannot honestly support an automatic decision -- ambiguous
    product intent, subjective final acceptance, protected authorisation, a
    meaning-changing design choice, a policy-required gate, an unresolved evidence
    conflict. Abstention is a valid outcome, and :data:`NEEDS_HUMAN` records *why* from a
    finite vocabulary so an operator can act on the reason rather than on the fact.

**The decision path is recorded, not summarised.** Every non-trivial decision keeps its
input facts, the deterministic results, any bounded-runtime result with its confidence
*kind*, whether it fell back, and which rule produced the verdict. ``PROVEN`` therefore
carries its own derivation and a reader never has to take it on trust -- which is what
makes "Ariadne says the work is done" a checkable statement rather than an assertion.

**Order of operations, and why.** A verdict never consults model confidence, and never
consults a bounded runtime while a deterministic rule settles the question. The ladder is
:data:`DECISION_LADDER`, and spending model inference on something schema and rules already
determine is spending the most expensive resource on the least valuable question.
"""

from __future__ import annotations

from typing import Any, Iterable, Mapping, Sequence

from .. import contracts
from ..contracts import ContractError, new_record_id, require_collection_capacity, utc_now

DECISION_COLLECTION = "verification_decisions"
PASS_COLLECTION = "verification_passes"

DECISION_LADDER = (
    "DETERMINISTIC",
    "BOUNDED",
    "GENERATIVE",
    "HUMAN",
)
"""The order in which a question may be answered, most authoritative first.

Not a preference. A deterministic rule that settles a question is both cheaper and more
auditable than a bounded inference about the same question, so using the inference first
is spending the expensive resource on the easy question and making the result harder to
explain. :func:`decide_requirement` walks this list and stops at the first rung that
answers.
"""

HUMAN_GATE_BY_KIND = {
    "SUBJECTIVE": "SUBJECTIVE_FINAL_ACCEPTANCE",
}
"""Requirement kinds that always carry a human gate unless one was explicitly waived.

``SUBJECTIVE`` is the honest admission. *"Feels premium"* is not a testable predicate,
and an engine that returns ``PROVEN`` for it has not verified anything -- it has agreed
with itself and written the agreement down. Abstaining is the correct answer, and the
correct answer is not a failure of the system.
"""


# ---------------------------------------------------------------- one decision


def decide_requirement(
    requirement_record: Mapping[str, Any],
    *,
    rows: Sequence[Mapping[str, Any]],
    human_review: Mapping[str, Any] | None = None,
    contract_revision: str = "",
    work_digest: str = "",
    bounded_advice: Mapping[str, Any] | None = None,
) -> dict:
    """Decide one requirement from current evidence. Deterministic unless told otherwise.

    ``bounded_advice`` is consulted **only** for questions the deterministic rules left
    open, and only when the requirement's ``verification_mode`` names it. It carries the
    runtime's answer plus its ``confidence_kind``; the confidence is recorded and is
    explicitly *not* a licence to decide, because :data:`CONFIDENCE_KINDS` distinguishes a
    provider's number from a calibrated one and neither is authorisation.
    """
    from . import evidence as evidence_module
    from . import requirements as requirements_module

    requirement_id = str(requirement_record.get("requirement_id", ""))
    measurement = evidence_module.assess(requirement_record, rows)
    conflict_rows = evidence_module.conflicts(requirement_record, rows)
    met = measurement["met"]
    outstanding = measurement["outstanding"]
    supporting = measurement["supporting"]
    contradicting = measurement["contradicting"]
    partial = measurement["partial"]
    deterministic = {
        "policy_met": met,
        "policy_outstanding": outstanding,
        "supporting": supporting,
        "contradicting": contradicting,
        "partial": partial,
        "ignored": measurement["ignored"],
        "conflicts": conflict_rows,
    }
    trace: list[dict] = [{
        "rung": "DETERMINISTIC",
        "applied": True,
        "result": f"policy met {sorted(met)}, outstanding {sorted(outstanding)}",
    }]

    unmet_gates: list[str] = []
    if bool(requirement_record.get("human_gate")):
        unmet_gates.append("POLICY_REQUIRED_HUMAN_GATE")
    kind_gate = HUMAN_GATE_BY_KIND.get(str(requirement_record.get("kind", "")))
    if kind_gate and not (human_review or {}).get("approved"):
        unmet_gates.append(kind_gate)
    if human_review is not None and str(human_review.get("approved", "")) != "True":
        unmet_gates.append("AMBIGUOUS_PRODUCT_INTENT")
    if unmet_gates and not (human_review or {}).get("approved"):
        trace.append({
            "rung": "DETERMINISTIC",
            "applied": True,
            "result": f"human gate unsatisfied: {', '.join(sorted(set(unmet_gates)))}",
        })
        return _finish(
            requirement_record,
            verdict="NEEDS_HUMAN",
            evidence_ids=supporting + contradicting + partial,
            claim_ids=[],
            human_gate_reasons=sorted(set(unmet_gates)),
            rationale=(
                f"{requirement_id} cannot honestly be decided automatically: "
                + ", ".join(sorted(set(unmet_gates)))
                + ". The available evidence cannot support an automatic answer, so Ariadne says so "
                  "rather than manufacturing one"
            ),
            uncertainty="a human decision is required and has not been given",
            decision_path="DETERMINISTIC:human-gate",
            deterministic=deterministic,
            trace=trace,
            work_digest=work_digest,
            contract_revision=contract_revision,
        )

    unresolved_conflicts = [row for row in conflict_rows if str(row.get("resolved_by")) != "AUTHORITATIVE_EVIDENCE"]
    if unresolved_conflicts:
        trace.append({
            "rung": "DETERMINISTIC",
            "applied": True,
            "result": "current evidence both supports and contradicts, with nothing authoritative to settle it",
        })
        return _finish(
            requirement_record,
            verdict="NEEDS_HUMAN",
            evidence_ids=supporting + contradicting,
            claim_ids=[],
            human_gate_reasons=["EVIDENCE_CONFLICT_UNRESOLVED"],
            rationale=(
                f"{requirement_id} has current evidence on both sides and no authoritative evidence "
                "to settle it: " + unresolved_conflicts[0].get("problem", "")
            ),
            uncertainty=(
                "choosing one observation over another is not verification, so this is escalated "
                "rather than resolved by preference"
            ),
            decision_path="DETERMINISTIC:unresolved-conflict",
            deterministic=deterministic,
            trace=trace,
            work_digest=work_digest,
            contract_revision=contract_revision,
        )

    contradicting_rows = conflicting_rows(requirement_record, rows)
    authoritative_contradiction = [
        row for row in contradicting_rows
        if str(requirements_module.stance_of(
            requirement_record, str(row.get("kind", "")))) == "AUTHORITATIVE"
    ]
    required_contradiction = [
        row for row in contradicting_rows
        if str(requirements_module.stance_of(
            requirement_record, str(row.get("kind", "")))) == "REQUIRED"
    ]
    if authoritative_contradiction or required_contradiction:
        deciding = authoritative_contradiction or required_contradiction
        trace.append({
            "rung": "DETERMINISTIC",
            "applied": True,
            "result": f"{len(deciding)} current evidence item(s) directly contradict this requirement",
        })
        return _finish(
            requirement_record,
            verdict="FAILED",
            evidence_ids=[str(row.get("evidence_id", "")) for row in deciding],
            claim_ids=[],
            human_gate_reasons=[],
            rationale=(
                f"{requirement_id} is violated by current evidence: "
                + "; ".join(str(row.get("observation", "")) for row in deciding)
            ),
            uncertainty=(
                "FAILED describes the work. Whether any worker claimed otherwise is a separate "
                "record, because a worker that made no claim at all is the common case"
            ),
            decision_path=(
                "DETERMINISTIC:authoritative-contradiction"
                if authoritative_contradiction
                else "DETERMINISTIC:required-contradiction"
            ),
            deterministic=deterministic,
            trace=trace,
            work_digest=work_digest,
            contract_revision=contract_revision,
        )

    if not outstanding:
        trace.append({"rung": "DETERMINISTIC", "applied": True, "result": "every required evidence kind supports"})
        return _finish(
            requirement_record,
            verdict="PROVEN",
            evidence_ids=supporting,
            claim_ids=[],
            human_gate_reasons=[],
            rationale=(
                f"{requirement_id} is established by current evidence under its own policy "
                f"({', '.join(sorted(met))})"
            ),
            uncertainty="",
            decision_path="DETERMINISTIC:policy-satisfied",
            deterministic=deterministic,
            trace=trace,
            work_digest=work_digest,
            contract_revision=contract_revision,
        )

    if met:
        trace.append({
            "rung": "DETERMINISTIC",
            "applied": True,
            "result": f"partially established: {sorted(met)} met, {sorted(outstanding)} outstanding",
        })
        return _finish(
            requirement_record,
            verdict="PARTIAL",
            evidence_ids=supporting + partial,
            claim_ids=[],
            human_gate_reasons=[],
            rationale=(
                f"{requirement_id} is partly established: {', '.join(sorted(met))} is proven and "
                f"{', '.join(sorted(outstanding))} is outstanding"
            ),
            uncertainty=(
                "if this requirement should have been split, the fix is to split it rather than to "
                "keep reporting a fraction of an unsplit sentence"
            ),
            decision_path="DETERMINISTIC:policy-partially-satisfied",
            deterministic=deterministic,
            trace=trace,
            work_digest=work_digest,
            contract_revision=contract_revision,
        )

    trace.append({
        "rung": "DETERMINISTIC",
        "applied": True,
        "result": f"no required evidence kind is present; outstanding {sorted(outstanding)}",
    })
    mode = str(requirement_record.get("verification_mode", "DETERMINISTIC"))
    advice_used = False
    if mode in ("BOUNDED", "GENERATIVE") and bounded_advice is not None:
        advice_used = True
        trace.append({
            "rung": mode,
            "applied": True,
            "result": (
                f"bounded advice {bounded_advice.get('answer') or 'abstained'} "
                f"(confidence_kind={bounded_advice.get('confidence_kind', 'NONE')}); "
                "recorded, not treated as authority"
            ),
            "confidence_kind": str(bounded_advice.get("confidence_kind", "NONE")),
            "fell_back": str(bool(bounded_advice.get("abstained"))),
        })
    return _finish(
        requirement_record,
        verdict="UNPROVEN",
        evidence_ids=supporting + partial,
        claim_ids=[],
        human_gate_reasons=[],
        rationale=(
            f"{requirement_id} has no contradictory evidence and no sufficient current evidence: "
            + ", ".join(sorted(outstanding))
            + " is missing. UNPROVEN is not FAILED; nothing observed a violation"
        ),
        uncertainty=(
            f"missing: {', '.join(sorted(outstanding))}. Absent evidence is not a defect and is "
            "never reported as one"
        ),
        decision_path=(
            "BOUNDED:insufficient-evidence" if advice_used
            else "DETERMINISTIC:insufficient-evidence"
        ),
        deterministic=deterministic,
        trace=trace,
        work_digest=work_digest,
        contract_revision=contract_revision,
    )


def conflicting_rows(
    requirement_record: Mapping[str, Any],
    rows: Sequence[Mapping[str, Any]],
) -> list[Mapping[str, Any]]:
    """Evidence that contradicts this requirement under its declared policy."""
    from . import requirements as requirements_module

    return [
        row for row in rows
        if str(row.get("stance")) == "CONTRADICTS"
        and str(requirements_module.stance_of(requirement_record, str(row.get("kind", "")))) != "INSUFFICIENT_ALONE"
    ]


def _finish(
    requirement_record: Mapping[str, Any],
    *,
    verdict: str,
    evidence_ids: Sequence[str],
    claim_ids: Sequence[str],
    human_gate_reasons: Sequence[str],
    rationale: str,
    uncertainty: str,
    decision_path: str,
    deterministic: Mapping[str, Any],
    trace: Sequence[Mapping[str, Any]],
    work_digest: str,
    contract_revision: str,
) -> dict:
    return {
        "requirement_id": str(requirement_record.get("requirement_id", "")),
        "verdict": str(verdict),
        "evidence_ids": [str(item) for item in evidence_ids if str(item)],
        "claim_ids": [str(item) for item in claim_ids if str(item)],
        "human_gate_reasons": [str(item) for item in human_gate_reasons if str(item)],
        "rationale": str(rationale),
        "uncertainty": str(uncertainty),
        "decision_path": str(decision_path),
        "deterministic": dict(deterministic),
        "trace": [dict(step) for step in trace],
        "work_digest": str(work_digest),
        "contract_revision": str(contract_revision),
        "authorization_effect": "none",
    }


# ------------------------------------------------------------------- claims


def assess_claim(
    claim_record: Mapping[str, Any],
    *,
    requirement_verdicts: Mapping[str, str],
    rows: Sequence[Mapping[str, Any]],
    work_digest: str = "",
) -> dict:
    """Assess one worker claim against the current evidence about it.

    Returns a **claim** verdict, deliberately kept in its own record:

    ``CONTRADICTED``  the claim's own checkable assertion is directly disproved, or the
                      requirement it claims is ``FAILED`` by current evidence
    ``SUPPORTED``     the requirement it claims is ``PROVEN``
    ``UNPROVEN``      nothing contradicts it and nothing establishes it either
    ``NEEDS_HUMAN``   the claim is about a requirement that escalated

    A claim with no checkable assertion and no mapped requirement cannot be assessed at
    all, and says so. It is not quietly counted as fine.
    """
    claim_id = str(claim_record.get("claim_id", ""))
    statement = str(claim_record.get("statement", ""))
    assertion = claim_record.get("assertion") if isinstance(
        claim_record.get("assertion"), Mapping) else {}
    mapped = [str(item) for item in claim_record.get("requirement_ids") or ()]
    trace: list[dict] = []

    contradiction = _assertion_contradiction(assertion, rows, work_digest=work_digest)
    if contradiction:
        trace.append({
            "rung": "DETERMINISTIC",
            "applied": True,
            "result": (
                f"the claim's own assertion is contradicted by {contradiction['evidence_id']}: "
                f"{contradiction['observed']}"
            ),
        })
        return _claim_finish(
            claim_record,
            verdict="CONTRADICTED",
            evidence_ids=[str(contradiction["evidence_id"])],
            rationale=(
                f"{claim_id} claims {statement!r}, and current evidence says "
                f"{contradiction['observed']}. A claim the evidence directly disproves is "
                "contradicted, which is a statement about the claim -- not about the requirement, "
                "which is separately FAILED"
            ),
            uncertainty="",
            decision_path="DETERMINISTIC:assertion-contradicted",
            trace=trace,
            requirement_verdicts=requirement_verdicts,
        )

    failed = [item for item in mapped if str(requirement_verdicts.get(item, "")) == "FAILED"]
    if failed:
        trace.append({
            "rung": "DETERMINISTIC",
            "applied": True,
            "result": f"the claimed requirement(s) {sorted(failed)} are FAILED by current evidence",
        })
        return _claim_finish(
            claim_record,
            verdict="CONTRADICTED",
            evidence_ids=[],
            rationale=(
                f"{claim_id} claims {statement!r} about {', '.join(sorted(failed))}, and those "
                "requirements are observed violated. A worker's assertion that work it did is fine, "
                "where the evidence observes it is not, is a contradicted claim"
            ),
            uncertainty="",
            decision_path="DETERMINISTIC:requirement-failed",
            trace=trace,
            requirement_verdicts=requirement_verdicts,
        )

    proven = [item for item in mapped if str(requirement_verdicts.get(item, "")) == "PROVEN"]
    if mapped and len(proven) == len(mapped):
        trace.append({
            "rung": "DETERMINISTIC",
            "applied": True,
            "result": f"every claimed requirement is PROVEN: {sorted(proven)}",
        })
        return _claim_finish(
            claim_record,
            verdict="SUPPORTED",
            evidence_ids=[],
            rationale=(
                f"{claim_id} claims {statement!r}, and every requirement it names is PROVEN by "
                "current evidence. Note what this is: the claim is consistent with the evidence. "
                "The evidence is what established the requirement"
            ),
            uncertainty="",
            decision_path="DETERMINISTIC:requirements-proven",
            trace=trace,
            requirement_verdicts=requirement_verdicts,
        )

    escalated = [
        item for item in mapped if str(requirement_verdicts.get(item, "")) == "NEEDS_HUMAN"
    ]
    if escalated:
        trace.append({
            "rung": "DETERMINISTIC",
            "applied": True,
            "result": f"the claimed requirement(s) {sorted(escalated)} escalated to a human",
        })
        return _claim_finish(
            claim_record,
            verdict="NEEDS_HUMAN",
            evidence_ids=[],
            rationale=(
                f"{claim_id} is about {', '.join(sorted(escalated))}, which Ariadne escalated. The "
                "claim follows the requirement it is about"
            ),
            uncertainty="a human decision is outstanding",
            decision_path="DETERMINISTIC:requirement-escalated",
            trace=trace,
            requirement_verdicts=requirement_verdicts,
        )

    if not mapped and not assertion:
        trace.append({
            "rung": "DETERMINISTIC",
            "applied": True,
            "result": "the claim names no requirement and states no checkable assertion",
        })
        return _claim_finish(
            claim_record,
            verdict="UNPROVEN",
            evidence_ids=[],
            rationale=(
                f"{claim_id} claims {statement!r} but is mapped to no requirement and states no "
                "checkable assertion, so nothing about it can be established. It is recorded and "
                "reported as unestablished rather than discarded -- an unscoped claim is often the "
                "overstatement"
            ),
            uncertainty="no requirement to assess and no assertion to check",
            decision_path="DETERMINISTIC:no-subject",
            trace=trace,
            requirement_verdicts=requirement_verdicts,
        )

    trace.append({
        "rung": "DETERMINISTIC",
        "applied": True,
        "result": "nothing contradicts the claim and nothing establishes it",
    })
    return _claim_finish(
        claim_record,
        verdict="UNPROVEN",
        evidence_ids=[],
        rationale=(
            f"{claim_id} claims {statement!r}; current evidence neither contradicts it nor "
            "establishes it. A claim awaiting evidence is the ordinary state of a claim, not a "
            "finding"
        ),
        uncertainty="awaiting evidence",
        decision_path="DETERMINISTIC:awaiting-evidence",
        trace=trace,
        requirement_verdicts=requirement_verdicts,
    )


def _assertion_contradiction(
    assertion: Mapping[str, Any],
    rows: Sequence[Mapping[str, Any]],
    *,
    work_digest: str = "",
) -> dict | None:
    """Directly disprove a checkable claim from a count-shaped assertion.

    The narrow, deterministic case the brief names: a worker claims *26 tests pass*, the
    evidence records *25 passed, 1 failed*. Both halves are counts, so this is arithmetic
    rather than interpretation -- which is exactly why it is worth implementing at all.

    Only counts are read. A prose assertion is not machine-checkable, and pretending
    otherwise is how an engine ends up agreeing with whatever it was told.
    """
    if not assertion:
        return None
    claimed_passed = assertion.get("passed")
    if claimed_passed is None:
        return None
    for row in rows:
        if work_digest and str(row.get("work_digest", "")) not in ("", str(work_digest)):
            continue
        if str(row.get("kind", "")) != "TEST":
            continue
        observed = str(row.get("observation", ""))
        passed = _first_int(observed, r"(\d+)\s+passed")
        failed = _first_int(observed, r"(\d+)\s+failed")
        if passed is None:
            continue
        if int(claimed_passed) != passed or (failed or 0) > 0:
            return {
                "evidence_id": str(row.get("evidence_id", "")),
                "observed": f"{passed} passed and {failed or 0} failed",
            }
    return None


def _first_int(text: str, pattern: str) -> int | None:
    import re

    match = re.search(pattern, str(text or ""), re.I)
    return int(match.group(1)) if match else None


def _claim_finish(
    claim_record: Mapping[str, Any],
    *,
    verdict: str,
    evidence_ids: Sequence[str],
    rationale: str,
    uncertainty: str,
    decision_path: str,
    trace: Sequence[Mapping[str, Any]],
    requirement_verdicts: Mapping[str, str],
) -> dict:
    return {
        "claim_id": str(claim_record.get("claim_id", "")),
        "actor": str(claim_record.get("actor", "")),
        "actor_role": str(claim_record.get("actor_role", "")),
        "statement": str(claim_record.get("statement", "")),
        "claim_verdict": str(verdict),
        "requirement_ids": [str(item) for item in claim_record.get("requirement_ids") or ()],
        "requirement_verdicts": {
            str(item): str(requirement_verdicts.get(str(item), ""))
            for item in claim_record.get("requirement_ids") or ()
        },
        "evidence_ids": [str(item) for item in evidence_ids if str(item)],
        "rationale": str(rationale),
        "uncertainty": str(uncertainty),
        "decision_path": str(decision_path),
        "trace": [dict(step) for step in trace],
        "authorization_effect": "none",
    }


# ----------------------------------------------------------------- recording


def record_decision(
    state: dict,
    *,
    requirement_record: Mapping[str, Any],
    outcome: Mapping[str, Any],
    contract_id: str,
    contract_revision: str,
    work_digest: str,
    pass_id: str = "",
    reviewer: str = "ariadne-engine",
) -> dict:
    """Store one requirement decision, fail-closed.

    The validator refuses a ``CONTRADICTED`` requirement verdict, refuses a ``PROVEN`` or
    ``FAILED`` verdict that cites no evidence, and refuses any decision whose
    ``authorization_effect`` is not ``none``. Those three refusals are the whole point of
    this function existing: they are properties a verdict must have *before* anybody reads
    it, not properties a reader has to remember to check.
    """
    from . import security as security_module

    record = {
        "schema_version": contracts.SCHEMA_ACCEPTANCE,
        "verification_id": new_record_id("vdz"),
        "run_id": str(state.get("run_id", "")),
        "task_id": str(requirement_record.get("task_id", "")),
        "pass_id": str(pass_id),
        "contract_id": str(contract_id),
        "contract_revision": str(contract_revision),
        "requirement_id": str(requirement_record.get("requirement_id", "")),
        "work_digest": str(work_digest),
        "verdict": str(outcome.get("verdict", "")),
        "evidence_ids": [str(item) for item in outcome.get("evidence_ids") or () if str(item)],
        "claim_ids": [str(item) for item in outcome.get("claim_ids") or () if str(item)],
        "human_gate_reasons": [str(item) for item in outcome.get("human_gate_reasons") or ()],
        "reviewer": str(reviewer),
        "decision_path": str(outcome.get("decision_path", "")),
        "rationale": str(outcome.get("rationale", "")),
        "uncertainty": str(outcome.get("uncertainty", "")),
        "deterministic": dict(outcome.get("deterministic") or {}),
        "trace": [dict(step) for step in outcome.get("trace") or ()],
        "blocking": bool(requirement_record.get("blocking")),
        "requirement_kind": str(requirement_record.get("kind", "")),
        "requirement_origin": str(requirement_record.get("origin", "")),
        "recorded_at": utc_now(),
        "authorization_effect": "none",
        "provenance": {
            "created_by": "engine",
            "policy_version": contracts.POLICY_VERSION,
            "contract_version": contracts.ACCEPTANCE_CONTRACT_VERSION,
        },
    }
    problems = contracts.verification_decision_problems(record)
    laundering = security_module.decision_laundering_findings(state, record)
    problems.extend(laundering["problems"])
    if problems:
        raise ContractError("verification decision is malformed: " + "; ".join(problems))
    require_collection_capacity(state, DECISION_COLLECTION)
    state.setdefault(DECISION_COLLECTION, []).append(record)
    return record


def decisions(state: Mapping[str, Any]) -> list[dict]:
    return [dict(row) for row in state.get(DECISION_COLLECTION, []) or [] if isinstance(row, Mapping)]


def decision(state: Mapping[str, Any], verification_id: str) -> dict | None:
    for row in decisions(state):
        if str(row.get("verification_id", "")) == str(verification_id):
            return row
    return None


def decisions_for_contract(state: Mapping[str, Any], contract_id: str) -> list[dict]:
    return [
        row for row in decisions(state)
        if str(row.get("contract_id", "")) == str(contract_id)
    ]


def latest_by_requirement(state: Mapping[str, Any], *, contract_id: str = "") -> dict[str, dict]:
    """The most recent decision per requirement. History stays readable."""
    rows = decisions(state)
    if contract_id:
        rows = [row for row in rows if str(row.get("contract_id", "")) == str(contract_id)]
    ordered = sorted(
        rows, key=lambda row: (str(row.get("recorded_at", "")), str(row.get("verification_id", ""))),
    )
    latest: dict[str, dict] = {}
    for row in ordered:
        latest[str(row.get("requirement_id", ""))] = row
    return latest


def latest_verdicts(state: Mapping[str, Any], *, contract_id: str = "") -> dict[str, str]:
    return {
        requirement_id: str(row.get("verdict", ""))
        for requirement_id, row in latest_by_requirement(state, contract_id=contract_id).items()
    }


__all__ = [
    "DECISION_COLLECTION",
    "DECISION_LADDER",
    "HUMAN_GATE_BY_KIND",
    "PASS_COLLECTION",
    "assess_claim",
    "conflicting_rows",
    "decide_requirement",
    "decision",
    "decisions",
    "decisions_for_contract",
    "latest_by_requirement",
    "latest_verdicts",
    "record_decision",
]