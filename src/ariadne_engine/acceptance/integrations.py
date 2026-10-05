"""Integration: joining acceptance intelligence to the records AR-220 to AR-222 produced.

This layer exists because the acceptance engine must not require a migration. Every
historical record family -- AR-203 verification records, AR-222D rendered evidence sets and
capture artifacts, AR-220 reference artefacts -- is *mapped into* the acceptance vocabulary
rather than rewritten, and the mapping is explicit so a reader can tell a derived record
from an authored one.

Three mappings, each carrying the provenance it derived:

``from_rendered_evidence_set``
    An AR-222D evidence set becomes one acceptance evidence item per requirement it names,
    with ``produced_by: MAPPED_FROM_AR222`` recorded. The 390px clipping capture that made
    Beacon AR-222's permanent negative fixture therefore becomes assessable input without
    anything about it being altered.

``from_verification_record``
    An AR-203 verification record becomes acceptance evidence bound to the work digest and
    dependency set it already carries, reusing AR-203's own four-state freshness.

``from_design_requirement``
    An AR-202D ``design_requirements`` closure record becomes a requirement definition, with
    ``DESIGN_REQUIREMENT_EVIDENCE`` (``source`` / ``rendered`` / ``behavioural``) mapped
    onto the acceptance evidence vocabulary.

Also here: :func:`explain_proof_readiness`, which is what AR-222D's
:mod:`~ariadne_engine.rendered_critique.proof` was *for*. It called
:func:`~ariadne_engine.rendered_critique.proof.proof_report` an explicit placeholder for
AR-223 and hard-coded ``verdicts: []`` with a note saying the threshold was deliberately
not hard-coded there. This function is the other half of that sentence: it takes the
lineage AR-222D proved was complete and produces verdicts from current evidence only --
never from the lineage alone.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from .. import contracts
from ..contracts import ContractError

MAPPED_FROM = {
    "RENDERED_EVIDENCE_SET": "MAPPED_FROM_AR222_EVIDENCE_SET",
    "VERIFICATION_RECORD": "MAPPED_FROM_AR203_VERIFICATION",
    "DESIGN_REQUIREMENT": "MAPPED_FROM_AR202D_REQUIREMENT",
}
"""How a mapped record says where it came from.

Stamped on every derived record. A record whose provenance is unstated is a record
somebody has to reverse-engineer later, and reverse-engineering provenance is how a
mapped artefact quietly becomes indistinguishable from an authored one.
"""

DESIGN_EVIDENCE_TO_ACCEPTANCE = {
    "source": "DIFF",
    "rendered": "RENDER",
    "behavioural": "RUNTIME",
}
"""AR-202D evidence kinds mapped onto acceptance evidence kinds.

Not a merge. The two vocabularies mean different things -- ``source`` asks whether the
code says so, ``DIFF`` asks what changed -- and the mapping is stated so a reader can see
which question the mapped evidence is actually answering.
"""


def from_rendered_evidence_set(
    state: dict,
    evidence_set: Mapping[str, Any],
    *,
    contract_id: str,
    contract_revision: str,
    task_id: str = "",
) -> list[dict]:
    """Turn one AR-222D rendered evidence set into acceptance evidence items.

    The capture a reviewer looked at becomes an observation Ariadne can weigh, per
    requirement the set names. Nothing about the capture is edited: its artefact digest,
    its viewport and its reviewer identity are carried across unchanged, because a
    migration that tidied its input would be indistinguishable from falsifying it.
    """
    from . import evidence as evidence_module

    created: list[dict] = []
    work_digest = str(evidence_set.get("render_source_digest", ""))
    if not work_digest:
        raise ContractError(
            "a rendered evidence set with no work digest cannot be mapped; evidence bound to no "
            "revision can never establish a current requirement"
        )
    requirement_ids = [str(item) for item in evidence_set.get("requirement_ids") or ()]
    if not requirement_ids:
        observations = evidence_set.get("captures") or ()
        requirement_ids = sorted({
            str(capture.get("requirement_id", ""))
            for capture in observations if isinstance(capture, Mapping)
        } - {""})
    if not requirement_ids:
        return created
    artifact = evidence_set.get("artifact") if isinstance(
        evidence_set.get("artifact"), Mapping) else {}
    observations = evidence_set.get("observations") or evidence_set.get("summary") or ()
    if isinstance(observations, str):
        observations = [observations]
    for capture in (evidence_set.get("captures") or ()):
        if isinstance(capture, Mapping) and str(capture.get("requirement_id", "")):
            observations = list(observations) + [
                f"rendered capture at viewport {capture.get('viewport', '')}"
            ]
    text = "; ".join(str(item) for item in observations) or "rendered evidence set captured"
    stance = str(evidence_set.get("stance", "") or _stance_from_status(evidence_set))
    for requirement_id in requirement_ids:
        created.append(evidence_module.record(
            state,
            kind="RENDER",
            stance=stance,
            producer=str(
                evidence_set.get("producer_execution")
                or evidence_set.get("captured_by")
                or evidence_set.get("producer")
                or "ariadne-render"
            ),
            producer_role=str(evidence_set.get("producer_role", "evidence_producer")),
            producer_execution=str(evidence_set.get("producer_execution", "")),
            observation=text,
            requirement_ids=[requirement_id],
            artifact_path=str(artifact.get("path", "")),
            artifact_sha256=str(artifact.get("sha256", "")),
            work_digest=work_digest,
            contract_revision=contract_revision,
            contract_id=contract_id,
            task_id=task_id,
            environment=evidence_set.get("environment") if isinstance(
                evidence_set.get("environment"), Mapping) else {},
            viewport=str(evidence_set.get("viewport", "")),
            reviewer_identity=str(evidence_set.get("reviewer_identity", "")),
            notes=f"{MAPPED_FROM['RENDERED_EVIDENCE_SET']} {evidence_set.get('evidence_set_id', '')}",
        ))
    return created


def _stance_from_status(evidence_set: Mapping[str, Any]) -> str:
    """Read a stance out of an AR-222D evidence set's own status.

    ``SUPPORTS`` is the mapping for a set that exists, because an observed rendering is
    evidence *about* the requirement regardless of what a later critique concludes. The
    critique's findings become separate ``CONTRADICTS`` items; folding them in here would
    mean the capture stopped being an observation and became an argument.
    """
    status = str(evidence_set.get("status", ""))
    if status in ("BLOCKED", "FAILED", "DIRECTION_REVISION_REQUIRED"):
        return "CONTRADICTS"
    return "SUPPORTS"


def from_verification_record(
    state: dict,
    record: Mapping[str, Any],
    *,
    requirement_ids: Sequence[str],
    contract_id: str,
    contract_revision: str,
    task_id: str = "",
) -> list[dict]:
    """Turn one AR-203 verification record into acceptance evidence.

    AR-203 records carry a level, an execution, a revision, a dependency set and an
    artefact digest -- everything acceptance needs. Reusing them rather than re-running
    them is the point: the record was made under stricter rules than acceptance requires,
    and re-deriving it would throw away that provenance.
    """
    from . import evidence as evidence_module

    if not requirement_ids:
        return []
    level = str(record.get("level", ""))
    if level == "DECLARED":
        return []
    artifacts = [row for row in record.get("evidence", []) or () if isinstance(row, Mapping)]
    path = str(artifacts[0].get("path", "")) if artifacts else ""
    digest = str(artifacts[0].get("sha256", "")) if artifacts else ""
    return [
        evidence_module.record(
            state,
            kind="PROVENANCE",
            stance="SUPPORTS",
            producer=str(record.get("execution_id") or "ariadne-engine"),
            producer_role="evidence_producer",
            producer_execution=str(record.get("execution_id", "")),
            observation=(
                f"verification at level {level} by method {record.get('method', '')}: "
                f"{record.get('claim', '')}"
            ),
            requirement_ids=[requirement_id],
            artifact_path=path,
            artifact_sha256=digest,
            work_digest=str(record.get("revision", "")),
            contract_revision=contract_revision,
            contract_id=contract_id,
            task_id=task_id,
            notes=f"{MAPPED_FROM['VERIFICATION_RECORD']} {record.get('verification_id', '')}",
        )
        for requirement_id in requirement_ids
    ]


def from_design_requirements(
    state: dict,
    *,
    contract_id: str,
    task_id: str = "",
    kind: str = "FUNCTIONAL",
) -> list[dict]:
    """Create requirement definitions from AR-202D design-requirement closure records.

    ``DESIGN_REQUIREMENT_EVIDENCE`` is mapped into the acceptance evidence vocabulary
    rather than merged, so ``source`` becomes a ``DIFF`` question and ``rendered`` becomes
    a ``RENDER`` one. A derived requirement is never blocking on its own -- a requirement
    Ariadne inferred cannot get the power to stop a project -- which is what makes this a
    safe way to import historical intent.
    """
    from . import requirements as requirements_module

    created: list[dict] = []
    for row in state.get("design_requirements", []) or []:
        requirement_id = str(row.get("requirement_id", ""))
        if not requirement_id:
            continue
        if requirements_module.requirement(state, requirement_id) is not None:
            continue
        mapped = DESIGN_EVIDENCE_TO_ACCEPTANCE.get(str(row.get("evidence_kind", "")), "DIFF")
        created.append(requirements_module.create(
            state,
            contract_id=contract_id,
            text=f"{requirement_id}: the design requirement recorded for this surface",
            kind=str(kind),
            origin="DERIVED",
            blocking=False,
            evidence_policy={
                "authoritative": [],
                "required": [mapped],
                "supporting": [],
                "insufficient_alone": list(requirements_module.INSUFFICIENT_ALONE),
            },
            task_id=task_id,
            rationale=f"{MAPPED_FROM['DESIGN_REQUIREMENT']} {row.get('record_id', '')}",
        ))
    return created


# ------------------------------------------------------------------ proof path


def explain_proof_readiness(
    state: Mapping[str, Any],
    *,
    contract_id: str,
    work_digest: str,
) -> dict:
    """Take AR-222D's proof lineage and say what can be concluded from it now.

    AR-222D's :func:`~ariadne_engine.rendered_critique.proof.proof_report` deliberately
    produced ``verdicts: []`` and said why: *"hard-coding a threshold here would make the
    future engine inherit a threshold nobody agreed to"*. This is the other half -- it
    reads the lineage and produces verdicts **from current evidence only**, so a complete
    chain of provenance still yields ``UNPROVEN`` when the evidence it points at is stale,
    and yields ``PROVEN`` only when the evidence it points at is current and sufficient.

    The distinction is the whole value of the split between readiness and acceptance:
    availability of provenance is not sufficiency of evidence.
    """
    from . import decisions as decisions_module
    from . import evidence as evidence_module
    from ..rendered_critique import proof

    report = proof.proof_report(state)
    rows = evidence_module.current(state, work_digest=work_digest)
    by_requirement: dict[str, list[Mapping[str, Any]]] = {}
    for row in rows:
        for requirement_id in row.get("requirement_ids") or ():
            by_requirement.setdefault(str(requirement_id), []).append(row)
    readiness: list[dict] = []
    for path in report["paths"]:
        requirement_id = str(path.get("requirement_id", ""))
        usable = by_requirement.get(requirement_id, [])
        complete = proof.path_state(path) == "COMPLETE"
        readiness.append({
            "requirement_id": requirement_id,
            "lineage": proof.path_state(path),
            "current_evidence": [str(row.get("evidence_id", "")) for row in usable],
            "conclusion_possible": bool(usable) and complete,
            "note": (
                "the chain is complete but the evidence it points at is not current, so nothing can "
                "be concluded from it"
                if complete and not usable
                else "the chain is complete and current evidence is available to weigh"
                if complete
                else "the chain is incomplete, so no conclusion is reachable even with current evidence"
            ),
        })
    return {
        "contract_id": str(contract_id),
        "work_digest": str(work_digest),
        "requirements": len(readiness),
        "readiness": readiness,
        "lineage_complete": report["complete"],
        "lineage_incomplete": report["incomplete"],
        "gaps": report["gaps"],
        "absent_roles": report["absent_roles"],
        "self_certification": report["self_certification"],
        "verdicts_available": sum(1 for row in readiness if row["conclusion_possible"]),
        "note": (
            "AR-222D reported availability of provenance and refused to emit verdicts. This reports "
            "which of those requirements could now be concluded about from current evidence, and "
            "still emits none itself"
        ),
    }


def audit(state: Mapping[str, Any]) -> dict:
    """The whole acceptance picture, for a diagnostic."""
    from . import claims as claims_module
    from . import contract as contract_module
    from . import evidence as evidence_module
    from . import requirements as requirements_module
    from . import security as security_module

    return {
        "version": contracts.ACCEPTANCE_CONTRACT_VERSION,
        "verdicts": list(contracts.ACCEPTANCE_VERDICTS),
        "contracts": contract_module.summarise(state),
        "requirements": requirements_module.summarise(state),
        "claims": claims_module.summarise(state),
        "evidence": evidence_module.summarise(state),
        "security": security_module.findings(state),
        "problems": (
            contract_module.problems(state)
            + requirements_module.problems(state)
            + claims_module.problems(state)
            + evidence_module.problems(state)
        ),
        "confidence_is_not_permission": (
            "no acceptance or verification record grants authority. Confidence is a number a model "
            "produced; permission is something a human decided"
        ),
    }


__all__ = [
    "DESIGN_EVIDENCE_TO_ACCEPTANCE",
    "MAPPED_FROM",
    "audit",
    "explain_proof_readiness",
    "from_design_requirements",
    "from_rendered_evidence_set",
    "from_verification_record",
]