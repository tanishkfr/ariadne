"""Aggregate acceptance: the one rule set that may say ACCEPTED or NOT_ACCEPTED.

Everything upstream produces requirement-level facts. This module is the only place a
whole task is called accepted, and it does so from a policy that is written down rather
than felt:

    ACCEPTED only if
      every blocking requirement is PROVEN
      AND no blocking requirement is FAILED
      AND no blocking requirement has a contradicted required completion claim
      AND required independent review occurred
      AND the evidence relied on is current
      AND required human and authorisation gates are satisfied

Each clause closes a different failure, and the clauses are not interchangeable:

* *all blocking proven* -- an outstanding blocking requirement is not a rounding error.
* *no blocking failed* -- stated separately so a later change cannot quietly relax it
  into "proven or failed".
* *no contradicted claim* -- because a worker asserting "all responsive behaviour fixed"
  while a capture shows otherwise is a fact about the worker that acceptance must reflect,
  independent of whether the requirement eventually passed.
* *independent review required* -- the engine's own verdict is a determination from
  recorded evidence, which is not the same act as independent review, and conflating the
  two makes every verdict self-certifying.
* *evidence current* -- a decision whose bound work digest has moved is history.
* *human gates satisfied* -- and this never substitutes for a protected gate that existing
  policy requires. **AR-223 does not bypass protected human acceptance.** Where the
  lifecycle demands a human acceptance record, its absence is decisive regardless of how
  much is PROVEN.

Non-blocking requirements are not hidden. A policy may accept with advisory requirements
``PARTIAL`` or ``UNPROVEN``, and the acceptance state **carries them** so a reader sees
exactly what was accepted around. Silence about the eight things nobody proved is the
same as lying about them, only quieter.

And there is no percentage. ``5 PROVEN, 1 FAILED, 2 UNPROVEN`` is reported as those
counts. A composite would invent a scale nobody measured, hide every distinction above,
and go *up* when a requirement is deleted.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from .. import contracts
from ..contracts import ContractError, new_record_id, require_collection_capacity, utc_now

POLICY_VERSION = "ar-223-acceptance-policy-1"
"""The acceptance policy version, recorded with every state read."""

PASS_KINDS = ("INITIAL", "REVERIFICATION", "REPAIR")
"""What kind of look this pass is.

``REVERIFICATION`` names the pass it re-verifies. History is append-only: pass one stays
readable after pass two, because a repair lineage whose first pass has been overwritten
proves that the repair happened and nothing about what it repaired.
"""

ACCEPTED_WHEN = (
    "every blocking requirement is PROVEN",
    "no blocking requirement is FAILED",
    "no blocking requirement carries a contradicted required claim",
    "required independent review occurred",
    "the evidence relied on is current",
    "required human and authorisation gates are satisfied",
    "no protected human acceptance is outstanding",
)
"""The policy, as a list a test and a reader can both check."""


def evaluate(
    state: Mapping[str, Any],
    *,
    contract_record: Mapping[str, Any],
    work_digest: str,
    decisions_by_requirement: Mapping[str, Mapping[str, Any]],
    claim_assessments: Sequence[Mapping[str, Any]],
    requirements: Sequence[Mapping[str, Any]],
    independent_review: Mapping[str, Any] | None = None,
    human_acceptance: Mapping[str, Any] | None = None,
    require_independent_review: bool = True,
    require_human_acceptance: bool = False,
    protected: bool = False,
) -> dict:
    """Evaluate the whole acceptance policy over one set of requirement decisions.

    Returns the state plus every clause's own verdict, so a reader can see *which* rule
    stopped acceptance rather than being told only that it was not accepted.
    """
    blockers: list[dict] = []
    advisory: list[dict] = []
    for requirement_record in requirements:
        requirement_id = str(requirement_record.get("requirement_id", ""))
        row = decisions_by_requirement.get(requirement_id) or {}
        verdict = str(row.get("verdict", "UNPROVEN"))
        entry = {
            "requirement_id": requirement_id,
            "text": str(requirement_record.get("text", "")),
            "kind": str(requirement_record.get("kind", "")),
            "origin": str(requirement_record.get("origin", "")),
            "verdict": verdict,
            "evidence_ids": list(row.get("evidence_ids") or ()),
            "rationale": str(row.get("rationale", "")),
            "uncertainty": str(row.get("uncertainty", "")),
            "decision_id": str(row.get("verification_id", "")),
            "human_gate": bool(requirement_record.get("human_gate")),
        }
        (blockers if bool(requirement_record.get("blocking")) else advisory).append(entry)

    unproven = [row for row in blockers if row["verdict"] != "PROVEN"]
    failed = [row for row in blockers if row["verdict"] == "FAILED"]
    escalated = [row for row in blockers if row["verdict"] == "NEEDS_HUMAN"]
    partial_blocking = [row for row in blockers if row["verdict"] == "PARTIAL"]

    contradicted_claims = [
        {
            "claim_id": str(row.get("claim_id", "")),
            "actor": str(row.get("actor", "")),
            "statement": str(row.get("statement", "")),
            "requirement_ids": list(row.get("requirement_ids") or ()),
            "rationale": str(row.get("rationale", "")),
        }
        for row in claim_assessments
        if str(row.get("claim_verdict", "")) == "CONTRADICTED"
        and any(
            str(requirement_id) in {str(item["requirement_id"]) for item in blockers}
            for requirement_id in (row.get("requirement_ids") or ())
        )
    ]

    from . import security as security_module

    review_problems: list[str] = []
    if require_independent_review:
        reviewer = str((independent_review or {}).get("reviewer", ""))
        if not reviewer:
            review_problems.append(
                "policy requires an independent review and none is recorded. The engine's own "
                "determination from recorded evidence is not independent review"
            )
        else:
            review_problems.extend(
                security_module.independent_reviewer_problems(
                    state, reviewer=reviewer, require_independent=True,
                )
            )

    from . import evidence as evidence_module

    cited = {
        str(identifier)
        for row in decisions_by_requirement.values()
        for identifier in (row.get("evidence_ids") or ())
    }
    stale_cited: list[dict] = []
    for identifier in sorted(cited):
        item = evidence_module.by_id(state, identifier)
        if item is None:
            stale_cited.append({
                "evidence_id": identifier, "state": "MISSING",
                "problem": "a decision cited evidence that is not recorded",
            })
            continue
        if str(item.get("state", "")) != "CURRENT":
            stale_cited.append({
                "evidence_id": identifier,
                "state": str(item.get("state", "")),
                "problem": f"evidence {identifier} is {item.get('state')}, so it cannot establish a "
                           "current requirement",
            })
        elif work_digest and str(item.get("work_digest", "")) != str(work_digest):
            stale_cited.append({
                "evidence_id": identifier,
                "state": "STALE",
                "problem": f"evidence {identifier} observed a different work digest than the one "
                           "being accepted",
            })

    gate_problems: list[str] = []
    if protected:
        gate_problems.append(
            "this work is protected, so acceptance requires the human gate that governs it. No "
            "engine decision, and no number of PROVEN requirements, substitutes for it"
        )
    if require_human_acceptance and not (human_acceptance or {}).get("accepted"):
        gate_problems.append(
            "policy requires a recorded human acceptance and none is present. AR-223 does not "
            "bypass protected human acceptance"
        )
    for row in blockers:
        if row["human_gate"] and row["verdict"] != "PROVEN":
            gate_problems.append(
                f"{row['requirement_id']} carries a human gate and is {row['verdict']}"
            )

    clauses = [
        {"clause": ACCEPTED_WHEN[0], "ok": not unproven,
         "detail": [f"{row['requirement_id']} is {row['verdict']}" for row in unproven]},
        {"clause": ACCEPTED_WHEN[1], "ok": not failed,
         "detail": [f"{row['requirement_id']} FAILED" for row in failed]},
        {"clause": ACCEPTED_WHEN[2], "ok": not contradicted_claims,
         "detail": [f"{row['claim_id']} CONTRADICTED" for row in contradicted_claims]},
        {"clause": ACCEPTED_WHEN[3], "ok": not review_problems, "detail": review_problems},
        {"clause": ACCEPTED_WHEN[4], "ok": not stale_cited,
         "detail": [row["problem"] for row in stale_cited]},
        {"clause": ACCEPTED_WHEN[5], "ok": not gate_problems, "detail": gate_problems},
        {"clause": ACCEPTED_WHEN[6], "ok": not protected or bool(
            (human_acceptance or {}).get("accepted")),
         "detail": [] if (human_acceptance or {}).get("accepted") else (
             ["no human acceptance recorded for protected work"] if protected else [])},
    ]
    accepted = all(clause["ok"] for clause in clauses)
    return {
        "policy_version": POLICY_VERSION,
        "accepted": accepted,
        "acceptance_state": "ACCEPTED" if accepted else "NOT_ACCEPTED",
        "blocking": blockers,
        "non_blocking": advisory,
        "unproven_blocking": [row["requirement_id"] for row in unproven],
        "failed_blocking": [row["requirement_id"] for row in failed],
        "escalated_blocking": [row["requirement_id"] for row in escalated],
        "partial_blocking": [row["requirement_id"] for row in partial_blocking],
        "contradicted_claims": contradicted_claims,
        "review_problems": review_problems,
        "stale_evidence": stale_cited,
        "gate_problems": gate_problems,
        "clauses": clauses,
        "advisory_note": (
            "non-blocking requirements that are not PROVEN are carried here rather than hidden. "
            "Accepting around them is permitted; saying nothing about them is not"
        ),
    }


def explain(acceptance: Mapping[str, Any]) -> str:
    """The acceptance result as a person can read it, with nothing opaque.

    The shape is the brief's:

        NOT ACCEPTED

        Blocking:
        R7 -- responsive layout -- FAILED
          evidence: E41

        R8 -- keyboard traversal -- UNPROVEN
          missing: interaction trace

        Worker claim C11:
        "all responsive behavior fixed"
        -> CONTRADICTED by E41

    No "opaque judgment" means no clause of the policy is unreported: a reader who wants
    to know why acceptance failed gets every clause, its verdict and its detail.
    """
    lines: list[str] = [str(acceptance.get("acceptance_state", "NOT_ACCEPTED"))]
    blocking = list(acceptance.get("blocking") or [])
    non_blocking = list(acceptance.get("non_blocking") or [])
    if blocking:
        lines.append("")
        lines.append("Blocking:")
        for row in blocking:
            lines.append(f"  {row['requirement_id']} -- {row['text']} -- {row['verdict']}")
            if row.get("evidence_ids"):
                lines.append(f"    evidence: {', '.join(row['evidence_ids'])}")
            if row.get("uncertainty"):
                lines.append(f"    {row['uncertainty']}")
    if non_blocking:
        lines.append("")
        lines.append("Non-blocking (accepted around, not hidden):")
        for row in non_blocking:
            lines.append(f"  {row['requirement_id']} -- {row['text']} -- {row['verdict']}")
            if row.get("uncertainty"):
                lines.append(f"    {row['uncertainty']}")
    for row in acceptance.get("contradicted_claims") or ():
        lines.append("")
        lines.append(f"Worker claim {row['claim_id']}:")
        lines.append(f"  {row['statement']!r}")
        lines.append("  -> CONTRADICTED")
        if row.get("rationale"):
            lines.append(f"     {row['rationale']}")
    for row in acceptance.get("stale_evidence") or ():
        lines.append(f"Stale evidence: {row['evidence_id']} -- {row['problem']}")
    for clause in acceptance.get("clauses") or ():
        if clause["ok"]:
            continue
        lines.append("")
        lines.append(f"Unmet clause: {clause['clause']}")
        for detail in clause["detail"] or ():
            lines.append(f"  - {detail}")
    return "\n".join(lines)


# ------------------------------------------------------------------ the pass


def run_pass(
    state: dict,
    *,
    contract_id: str,
    work_digest: str,
    task_id: str = "",
    pass_kind: str = "INITIAL",
    supersedes_pass_id: str = "",
    repair_ids: Sequence[str] = (),
    human_review: Mapping[str, Any] | None = None,
    independent_review: Mapping[str, Any] | None = None,
    human_acceptance: Mapping[str, Any] | None = None,
    require_independent_review: bool = True,
    require_human_acceptance: bool = False,
    protected: bool = False,
    bounded_advice: Mapping[str, Mapping[str, Any]] | None = None,
    evidence_root: Any = None,
) -> dict:
    """Run one complete verification pass and record it.

    The order is fixed and load-bearing: refresh evidence freshness first, so nothing
    stale can be weighed; then decide every requirement independently, so one requirement's
    outcome cannot colour another's; then assess claims, which are a *separate* record
    family; then aggregate, which is the only place acceptance is decided.

    ``bounded_advice`` is keyed by requirement id and is consulted only where the
    deterministic rules left the question open. It cannot promote a requirement, and the
    confidence it carries is recorded rather than obeyed.
    """
    from . import contract as contract_module
    from . import decisions as decisions_module
    from . import evidence as evidence_module
    from . import requirements as requirements_module

    if str(pass_kind) not in PASS_KINDS:
        raise ContractError(f"unsupported pass kind: {pass_kind!r}")
    contract_record = contract_module.contract(state, contract_id)
    if contract_record is None:
        raise ContractError(f"no contract is recorded with id {contract_id!r}")
    revision = str(contract_record.get("revision", "1"))

    if evidence_root is not None:
        evidence_module.refresh(
            state, work_digest=work_digest,
            contract_revision=revision, artifact_root=evidence_root,
        )

    requirements = requirements_module.active_requirements(state, contract_id=contract_id)
    rows = evidence_module.current(
        state, work_digest=work_digest, contract_revision=revision,
    )
    by_requirement: dict[str, list[Mapping[str, Any]]] = {}
    for row in rows:
        for requirement_id in row.get("requirement_ids") or ():
            by_requirement.setdefault(str(requirement_id), []).append(row)

    decisions_by_requirement: dict[str, dict] = {}
    for requirement_record in requirements:
        requirement_id = str(requirement_record.get("requirement_id", ""))
        outcome = decisions_module.decide_requirement(
            requirement_record,
            rows=by_requirement.get(requirement_id, []),
            human_review=human_review,
            contract_revision=revision,
            work_digest=work_digest,
            bounded_advice=(bounded_advice or {}).get(requirement_id),
        )
        decisions_by_requirement[requirement_id] = outcome

    verdicts = {
        requirement_id: str(row.get("verdict", "UNPROVEN"))
        for requirement_id, row in decisions_by_requirement.items()
    }

    from . import claims as claims_module

    claim_rows = claims_module.current_claims(
        state, work_digest=work_digest, contract_id=contract_id,
    )
    claim_assessments = [
        decisions_module.assess_claim(
            row, requirement_verdicts=verdicts, rows=rows, work_digest=work_digest,
        )
        for row in claim_rows
    ]

    acceptance = evaluate(
        state,
        contract_record=contract_record,
        work_digest=work_digest,
        decisions_by_requirement=decisions_by_requirement,
        claim_assessments=claim_assessments,
        requirements=requirements,
        independent_review=independent_review,
        human_acceptance=human_acceptance,
        require_independent_review=require_independent_review,
        require_human_acceptance=require_human_acceptance,
        protected=protected,
    )

    pass_id = new_record_id("vps")
    stored: list[dict] = []
    for requirement_record in requirements:
        requirement_id = str(requirement_record.get("requirement_id", ""))
        stored.append(
            decisions_module.record_decision(
                state,
                requirement_record=requirement_record,
                outcome=decisions_by_requirement[requirement_id],
                contract_id=contract_id,
                contract_revision=revision,
                work_digest=work_digest,
                pass_id=pass_id,
            )
        )

    record = {
        "schema_version": contracts.SCHEMA_ACCEPTANCE,
        "pass_id": pass_id,
        "pass_kind": str(pass_kind),
        "run_id": str(state.get("run_id", "")),
        "task_id": str(task_id or contract_record.get("task_id", "")),
        "contract_id": str(contract_id),
        "contract_revision": revision,
        "work_digest": str(work_digest),
        "supersedes_pass_id": str(supersedes_pass_id),
        "repair_ids": [str(item) for item in repair_ids or ()],
        "requirement_decisions": [dict(row) for row in stored],
        "requirement_verdicts": verdicts,
        "claim_assessments": [dict(row) for row in claim_assessments],
        "blocking_summary": {
            "blocking": len(acceptance["blocking"]),
            "non_blocking": len(acceptance["non_blocking"]),
            "unproven": list(acceptance["unproven_blocking"]),
            "failed": list(acceptance["failed_blocking"]),
            "escalated": list(acceptance["escalated_blocking"]),
            "contradicted_claims": [
                row["claim_id"] for row in acceptance["contradicted_claims"]
            ],
        },
        "acceptance_readiness": acceptance,
        "acceptance_state": str(acceptance["acceptance_state"]),
        "evidence_root": str(evidence_root or ""),
        "aggregate_score": None,
        "explanation": explain(acceptance),
        "recorded_at": utc_now(),
        "authorization_effect": "none",
        "provenance": {
            "created_by": "engine",
            "policy_version": POLICY_VERSION,
            "contract_version": contracts.ACCEPTANCE_CONTRACT_VERSION,
        },
    }
    problems = contracts.verification_pass_problems(record)
    if problems:
        raise ContractError("verification pass is malformed: " + "; ".join(problems))
    require_collection_capacity(state, decisions_module.PASS_COLLECTION)
    state.setdefault(decisions_module.PASS_COLLECTION, []).append(record)
    return record


# ------------------------------------------------------------------- history


def passes(state: Mapping[str, Any]) -> list[dict]:
    from . import decisions as decisions_module

    return [
        dict(row) for row in state.get(decisions_module.PASS_COLLECTION, []) or []
        if isinstance(row, Mapping)
    ]


def pass_record(state: Mapping[str, Any], pass_id: str) -> dict | None:
    for row in passes(state):
        if str(row.get("pass_id", "")) == str(pass_id):
            return row
    return None


def lineage(state: Mapping[str, Any], requirement_id: str) -> list[dict]:
    """One requirement followed across every pass that decided it.

    ``Pass 1 -- FAILED``, then the repair, then ``Pass 2 -- PROVEN`` -- all of it still
    readable. This is the whole of :mod:`~ariadne_engine.acceptance.invalidation`'s repair
    lineage, expressed as a view rather than a mutation.
    """
    from . import decisions as decisions_module

    rows: list[dict] = []
    for record in passes(state):
        for decision in record.get("requirement_decisions") or ():
            if str(decision.get("requirement_id", "")) != str(requirement_id):
                continue
            rows.append({
                "pass_id": str(record.get("pass_id", "")),
                "pass_kind": str(record.get("pass_kind", "")),
                "recorded_at": str(record.get("recorded_at", "")),
                "work_digest": str(record.get("work_digest", "")),
                "verdict": str(decision.get("verdict", "")),
                "evidence_ids": list(decision.get("evidence_ids") or ()),
                "decision_id": str(decision.get("verification_id", "")),
                "supersedes_pass_id": str(record.get("supersedes_pass_id", "")),
                "repair_ids": list(record.get("repair_ids") or ()),
            })
    return rows


def assert_history(state: Mapping[str, Any]) -> list[str]:
    """Whether the pass chain is still walkable and still append-only.

    Four things that must hold, each catching a way a repair lineage quietly becomes
    unreconstructable: a pass whose predecessor is missing; a re-verification that does not
    name what it re-verifies; two passes over **identical work** reaching different
    conclusions; and a verdict going backwards without the work having moved at all.

    The last two are the same check for a reason. A requirement legitimately dropping from
    ``PROVEN`` to ``UNPROVEN`` after a code change is the system working -- the earlier pass
    answered a different question. The same drop with an unchanged work digest means one of
    the two passes is wrong, and nothing in the records can say which.
    """
    rows = passes(state)
    known = {str(row.get("pass_id", "")) for row in rows}
    problems: list[str] = []
    for record in rows:
        previous = str(record.get("supersedes_pass_id", ""))
        if previous and previous not in known:
            problems.append(
                f"pass {record.get('pass_id')} re-verifies {previous}, which is not recorded. The "
                "chain has a hole and the earlier result cannot be read through it"
            )
        if str(record.get("pass_kind", "")) in ("REVERIFICATION", "REPAIR") and not previous:
            problems.append(
                f"pass {record.get('pass_id')} is a {record.get('pass_kind')} pass but names no pass "
                "it follows. Repair lineage is only meaningful as a chain"
            )
    history: dict[str, list[dict]] = {}
    for record in rows:
        for decision in record.get("requirement_decisions") or ():
            history.setdefault(str(decision.get("requirement_id", "")), []).append({
                "verdict": str(decision.get("verdict", "")),
                "recorded_at": str(record.get("recorded_at", "")),
                "pass_kind": str(record.get("pass_kind", "")),
                "pass_id": str(record.get("pass_id", "")),
                "work_digest": str(record.get("work_digest", "")),
            })
    for requirement_id, steps in sorted(history.items()):
        if len(steps) < 2:
            continue
        ordered = sorted(steps, key=lambda step: (step["recorded_at"], step["pass_id"]))
        for earlier, later in zip(ordered, ordered[1:]):
            if earlier["verdict"] == later["verdict"]:
                continue
            if earlier["work_digest"] == later["work_digest"]:
                problems.append(
                    f"{requirement_id} is {earlier['verdict']} in {earlier['pass_id']} and "
                    f"{later['verdict']} in {later['pass_id']} over the identical work digest "
                    f"{later['work_digest'][:16]}. Two passes over one revision reached different "
                    "conclusions and nothing in the records says which is right"
                )
    return list(dict.fromkeys(problems))


def problems(state: Mapping[str, Any]) -> list[str]:
    from . import contract as contract_module
    from . import claims as claims_module
    from . import decisions as decisions_module
    from . import evidence as evidence_module
    from . import requirements as requirements_module

    found: list[str] = []
    found.extend(contract_module.problems(state))
    found.extend(requirements_module.problems(state))
    found.extend(claims_module.problems(state))
    found.extend(evidence_module.problems(state))
    for row in decisions_module.decisions(state):
        found.extend(
            f"decision {row.get('verification_id', '?')}: {problem}"
            for problem in contracts.verification_decision_problems(row)
        )
    for row in passes(state):
        found.extend(
            f"pass {row.get('pass_id', '?')}: {problem}"
            for problem in contracts.verification_pass_problems(row)
        )
    found.extend(assert_history(state))
    return list(dict.fromkeys(found))


__all__ = [
    "ACCEPTED_WHEN",
    "PASS_KINDS",
    "POLICY_VERSION",
    "assert_history",
    "evaluate",
    "explain",
    "lineage",
    "pass_record",
    "passes",
    "problems",
    "run_pass",
]