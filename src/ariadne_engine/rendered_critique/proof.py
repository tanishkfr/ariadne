"""Proof readiness: provenance that survives into Acceptance Intelligence (AR-222D).

AR-223 will introduce intentional Acceptance Intelligence -- ``PROVEN``, ``PARTIAL``,
``UNPROVEN``, ``FAILED``, ``CONTRADICTED``, ``NEEDS_HUMAN``. This module deliberately
introduces **none of that**. No verdict, no score, no sufficiency threshold, no
re-verification scheduler.

What it does is much narrower, and it is the thing that makes AR-223 possible without
migration pain:

> **Could AR-223 later evaluate this requirement without reconstructing missing provenance?**

The chain it must be able to walk, without parsing prose and without guessing:

```text
requirement -> implementation revision -> evidence -> finding
            -> repair attempt -> resulting revision -> new evidence
```

Every link already exists somewhere in AR-220 to AR-222. What did *not* exist was a way to
ask whether the chain is **complete** at a point in time, and a way to see the same
requirement followed across two passes. So this module joins existing records, and reports
gaps.

Three things it refuses to do, because each would produce a false green:

* **It does not infer a missing link.** A finding with no requirement id is a gap, not a
  requirement AR-223 could reasonably attribute. Fabricating the attribution here is how
  a proof system ends up proving the wrong thing.
* **It does not judge sufficiency.** Enough evidence is an AR-223 policy question, and
  answering it here would hard-code a threshold nobody has agreed to.
* **It does not overwrite history.** ``before`` evidence, the original finding, the repair
  attempt and the ``after`` evidence are all required to still be present. A pass that
  lost its before-capture has broken the chain permanently, and saying so is more useful
  than quietly reporting the surviving half.
"""

from __future__ import annotations

from typing import Mapping, Sequence

from .. import contracts
from ..contracts import ContractError

PROOF_FIELDS = (
    "requirement_id",
    "current_work_digest",
    "evidence_identity",
    "producer_identity",
    "reviewer_identity",
    "finding_identity",
    "repair_identity",
    "resulting_work_digest",
    "new_evidence_identity",
)
"""The nine facts AR-223 needs per requirement-path. Availability, not correctness.

Each is a *field that must exist somewhere in the joined record*, so an AR-223 evaluation
never has to read prose to work out who produced what or which revision it observed.
"""

ACTOR_ROLES = contracts.PROOF_ACTOR_ROLES
"""The identities a proof path must be able to distinguish.

The reason this list exists is a single future rule: *the worker cannot independently
certify itself.* Enforcing it needs the roles already recorded, which means adding them now
-- before anything depends on them -- rather than retro-fitting identities onto records
that never carried them.

Moved to :data:`ariadne_engine.contracts.PROOF_ACTOR_ROLES` in AR-223. From AR-223 on
two subsystems need this list -- proof readiness to *detect* a role collision and
acceptance to *refuse* one -- and two copies of a list whose whole purpose is agreement
would drift exactly where it matters. The name is kept here so existing readers and the
AR-222D suites are unaffected.
"""

SELF_CERTIFICATION_PAIRS = contracts.SELF_CERTIFICATION_PAIRS
"""Role pairs that may not be the same actor.

Evidence produced by the party whose work it evidences, and reviewed by the party that
implemented or repaired it, are the two ways independence can be faked.
"""

LINEAGE_STATES = ("COMPLETE", "INCOMPLETE", "UNKNOWN")
"""Never a verdict. ``COMPLETE`` means every link is *present*, not that the evidence is
sufficient or the requirement is met -- which is precisely AR-223's judgement, not ours."""


def _rows(values: object) -> list[Mapping]:
    return [row for row in (values or []) if isinstance(row, Mapping)]


def actor_table(state: Mapping) -> dict:
    """Every actor identity the state records, keyed by the role it played.

    Derived rather than asserted: each role is read from the records that actually exist,
    so a role nobody recorded simply does not appear -- and :func:`proof_problems` then
    reports it missing instead of the chain quietly claiming a reviewer existed.
    """
    from .. import design as design_module

    rows: dict[str, list[dict]] = {role: [] for role in ACTOR_ROLES}
    rows["user_or_human_approver"].extend({
        "approval_id": str(item.get("approval_id", "")),
        "identity": str(item.get("identity", "")),
        "channel": str(item.get("channel", "")),
        "subject_id": str(item.get("subject_id", "")),
        "subject_type": str(item.get("subject_type", "")),
    } for item in _rows(state.get("approvals")))
    for plan in _rows(state.get("design_implementation_plans")):
        rows["implementation_worker"].append({
            "plan_id": str(plan.get("plan_id", "")),
            "implementation_execution": str(plan.get("implementation_execution", "")),
        })
    for run in _rows(state.get("implementation_runs")):
        rows["implementation_worker"].append({
            "execution_id": str(run.get("execution_id", "")),
            "role": str(run.get("role", "")),
        })
    for evidence_set in _rows(state.get("rendered_evidence_sets")):
        rows["evidence_producer"].append({
            "evidence_set_id": str(evidence_set.get("evidence_set_id", "")),
            "render_source_digest": str(evidence_set.get("render_source_digest", "")),
            "producer": str(
                evidence_set.get("producer_execution")
                or evidence_set.get("captured_by")
                or evidence_set.get("provenance", {}).get("created_by")
                if isinstance(evidence_set.get("provenance"), Mapping)
                else evidence_set.get("producer_execution", "")
            ),
        })
    for critique in _rows(state.get("rendered_critiques")):
        rows["independent_reviewer"].append({
            "critique_id": str(critique.get("critique_id", "")),
            "reviewer_execution": str(critique.get("reviewer_execution", "")),
            "reviewer_identity": str(critique.get("reviewer_identity", "")),
            "implementing_execution": str(critique.get("implementing_execution", "")),
            "review_session_id": str(critique.get("review_session_id", "")),
        })
    for plan in _rows(state.get("refinement_plans")):
        rows["repair_worker"].append({
            "refinement_plan_id": str(plan.get("refinement_plan_id", "")),
            "repair_execution": str(plan.get("repair_execution", "")),
        })
    rows["engine"].append({
        "engine": "ariadne",
        "policy_version": contracts.POLICY_VERSION,
        "design_directions": len(_rows(state.get("design_directions"))),
    })
    return {
        name: [row for row in entries if row] for name, entries in rows.items()
    }


def self_certification_findings(state: Mapping) -> list[dict]:
    """Where one actor occupied two roles that must be held by different actors.

    This is a *finding*, not a refusal: AR-222D records the collision so AR-223 can enforce
    on it, and refuses nothing itself. It also deliberately ignores the engine row -- the
    engine produced the evidence records, and saying "the engine reviewed its own work"
    because it wrote both records would be true and useless.
    """
    actors = actor_table(state)
    findings: list[dict] = []
    for producer_role, reviewer_role in SELF_CERTIFICATION_PAIRS:
        producers = {
            str(entry.get("producer_execution") or entry.get("implementation_execution")
                or entry.get("execution_id") or "")
            for entry in actors[producer_role]
        }
        reviewers = {
            str(entry.get("reviewer_execution") or entry.get("repair_execution") or "")
            for entry in actors[reviewer_role]
        }
        shared = sorted({item for item in producers & reviewers if item})
        if shared:
            findings.append({
                "roles": [producer_role, reviewer_role],
                "shared_identities": shared,
                "problem": (
                    f"the same actor recorded as {producer_role} and as {reviewer_role}: "
                    f"{', '.join(shared)}. AR-223 will need to refuse the worker certifying its "
                    "own work, and this is the provenance that refusal depends on"
                ),
            })
    return findings


def requirement_paths(state: Mapping) -> list[dict]:
    """Every requirement, followed across passes into the findings it produced.

    Joins existing records. It does not create any, and it does not repair a broken link --
    a finding with no requirement id is reported as an orphan rather than guessed onto the
    nearest requirement, because a guessed attribution is a false proof.
    """
    requirements = {
        str(row.get("requirement_id", "")): row for row in _rows(state.get("design_requirements"))
    }
    directions = _rows(state.get("design_directions"))
    plans = _rows(state.get("design_implementation_plans"))
    evidence_sets = _rows(state.get("rendered_evidence_sets"))
    critiques = _rows(state.get("rendered_critiques"))
    refinements = _rows(state.get("refinement_plans"))
    plans_by_finding: dict[str, list[Mapping]] = {}
    for plan in refinements:
        for finding_id in (plan.get("finding_ids") or []):
            plans_by_finding.setdefault(str(finding_id), []).append(plan)

    paths: list[dict] = []
    for requirement_id, requirement in sorted(requirements.items()):
        if not requirement_id:
            continue
        related_critiques = [
            critique for critique in critiques
            if requirement_id in (critique.get("requirements") or [])
            or any(
                requirement_id in (finding.get("requirement_ids") or [])
                for finding in _rows(critique.get("findings"))
            )
        ]
        findings: list[dict] = []
        for critique in related_critiques:
            evidence_set_id = str(critique.get("evidence_set_id", ""))
            evidence_set = next(
                (row for row in evidence_sets if str(row.get("evidence_set_id")) == evidence_set_id), {}
            )
            for finding in _rows(critique.get("findings")):
                finding_id = str(finding.get("finding_id", ""))
                repair = next(iter(plans_by_finding.get(finding_id, [])), {})
                findings.append({
                    "finding_id": finding_id,
                    "requirement_id_on_finding": str(
                        (finding.get("requirement_ids") or [""])[0] if finding.get("requirement_ids") else ""
                    ),
                    "dimension": str(finding.get("dimension", "")),
                    "severity": str(finding.get("severity", "")),
                    "state": str(finding.get("state", "")),
                    "critique_id": str(critique.get("critique_id", "")),
                    "reviewer_execution": str(critique.get("reviewer_execution", "")),
                    "implementing_execution": str(critique.get("implementing_execution", "")),
                    "review_session_id": str(critique.get("review_session_id", "")),
                    "evidence": {
                        "evidence_set_id": evidence_set_id,
                        "observed_work_digest": str(evidence_set.get("render_source_digest", "")),
                        "critique_declared_digest": str(critique.get("render_source_digest", "")),
                        "captures": len(_rows(evidence_set.get("captures"))),
                    },
                    "repair": {
                        "refinement_plan_id": str(repair.get("refinement_plan_id", "")),
                        "repair_execution": str(repair.get("repair_execution", "")),
                        "work_digest_before": str(repair.get("render_source_digest_before", "")),
                        "work_digest_after": str(repair.get("render_source_digest_after", "")),
                        "after_evidence_set_id": str(repair.get("after_evidence_set_id", "")),
                        "status": str(repair.get("status", "")),
                    },
                })
        paths.append({
            "requirement_id": requirement_id,
            "requirement_state": str(requirement.get("state", "")),
            "requirement_revision": str(requirement.get("revision_hash", "")),
            "direction_ids": sorted({
                str(row.get("direction_id", "")) for row in directions
                if requirement_id in (row.get("requirement_ids") or [])
                or requirement_id in str(row.get("constraints") or "")
            }),
            "implementation_plan_ids": sorted({
                str(plan.get("plan_id", "")) for plan in plans
                if requirement_id in (plan.get("requirement_ids") or [])
                or requirement_id in str(plan.get("requirements") or "")
            }),
            "findings": findings,
        })
    return paths


def _finding_gaps(path: Mapping) -> list[str]:
    gaps: list[str] = []
    requirement_id = str(path.get("requirement_id", ""))
    for finding in _rows(path.get("findings")):
        finding_id = str(finding.get("finding_id", ""))
        if not str(finding.get("requirement_id_on_finding", "")):
            gaps.append(
                f"{requirement_id} / {finding_id}: the finding does not carry its requirement id. "
                "AR-223 would have to guess which requirement this finding is about"
            )
        evidence = finding.get("evidence") if isinstance(finding.get("evidence"), Mapping) else {}
        if not str(evidence.get("evidence_set_id", "")):
            gaps.append(f"{requirement_id} / {finding_id}: no evidence set identity")
        if not str(evidence.get("observed_work_digest", "")):
            gaps.append(
                f"{requirement_id} / {finding_id}: the evidence records no work revision, so it is "
                "not answerable which revision was observed"
            )
        if not str(finding.get("reviewer_execution", "")):
            gaps.append(f"{requirement_id} / {finding_id}: no independent reviewer identity")
        repair = finding.get("repair") if isinstance(finding.get("repair"), Mapping) else {}
        if str(repair.get("status", "")) in ("VALIDATED", "RE_RENDERED", "CLOSED"):
            if not str(repair.get("work_digest_before", "")) or not str(repair.get("work_digest_after", "")):
                gaps.append(
                    f"{requirement_id} / {finding_id}: the repair records no before/after work digest, "
                    "so the resulting revision cannot be identified"
                )
            if not str(repair.get("after_evidence_set_id", "")):
                gaps.append(
                    f"{requirement_id} / {finding_id}: the repair produced no new evidence set, so "
                    "there is nothing to evaluate the repair against"
                )
            if not str(repair.get("repair_execution", "")):
                gaps.append(f"{requirement_id} / {finding_id}: the repair records no repair worker identity")
    return gaps


def path_state(path: Mapping) -> str:
    """``COMPLETE`` when every link is present. Never a verdict on quality."""
    if _finding_gaps(path):
        return "INCOMPLETE"
    if not _rows(path.get("findings")):
        return "INCOMPLETE"
    return "COMPLETE"


def proof_report(state: Mapping) -> dict:
    """The whole proof-readiness picture, with no verdict anywhere in it."""
    paths = requirement_paths(state)
    gaps: list[str] = []
    for path in paths:
        gaps.extend(_finding_gaps(path))
    orphans: list[str] = []
    known = {str(path.get("requirement_id", "")) for path in paths}
    for critique in _rows(state.get("rendered_critiques")):
        for finding in _rows(critique.get("findings")):
            cited = [str(item) for item in (finding.get("requirement_ids") or [])]
            if not cited:
                orphans.append(
                    f"finding {finding.get('finding_id', '?')} cites no requirement at all. It is not "
                    "attached to any requirement path and cannot be evaluated against one"
                )
            else:
                missing = [item for item in cited if item not in known]
                if missing:
                    orphans.append(
                        f"finding {finding.get('finding_id', '?')} cites requirement(s) "
                        f"{', '.join(missing)} that do not exist in this state"
                    )
    actors = actor_table(state)
    absent_roles = sorted(
        role for role in ACTOR_ROLES
        if not [entry for entry in actors.get(role, []) if entry]
    )
    return {
        "requirements": len(paths),
        "paths": paths,
        "complete": sum(1 for path in paths if path_state(path) == "COMPLETE"),
        "incomplete": sum(1 for path in paths if path_state(path) == "INCOMPLETE"),
        "gaps": gaps,
        "orphans": orphans,
        "actors": actors,
        "absent_roles": absent_roles,
        "self_certification": self_certification_findings(state),
        "verdicts": [],
        "verdict_note": (
            "no acceptance verdict is produced here. PROVEN / PARTIAL / UNPROVEN / FAILED / "
            "CONTRADICTED / NEEDS_HUMAN is AR-223's decision, and hard-coding a threshold here "
            "would make the future engine inherit a threshold nobody agreed to"
        ),
        "fields_required_by_ar223": list(PROOF_FIELDS),
        "basis": (
            "availability of provenance, not sufficiency of evidence. A COMPLETE path means every "
            "link exists so AR-223 can walk it; it does not mean the requirement is met"
        ),
    }


def proof_problems(state: Mapping) -> list[str]:
    """Whether this state would let AR-223 evaluate without reconstructing provenance."""
    report = proof_report(state)
    problems: list[str] = []
    if not report["requirements"]:
        problems.append(
            "no design requirement exists, so there is nothing for AR-223 to evaluate. Requirement "
            "identity must exist before acceptance intelligence does"
        )
    for gap in report["gaps"]:
        problems.append(gap)
    for orphan in report["orphans"]:
        problems.append(orphan)
    if report["absent_roles"]:
        problems.append(
            "no actor was recorded for these roles: "
            + ", ".join(report["absent_roles"])
            + ". AR-223 enforces that the worker cannot independently certify itself, and that "
              "enforcement needs the roles recorded now rather than retrofitted later"
        )
    for finding in report["self_certification"]:
        problems.append(finding["problem"])
    return problems


def assert_append_only(state: Mapping) -> list[str]:
    """Before-evidence, findings, repairs and after-evidence must all still be present.

    :data:`contracts.RENDERED_EVIDENCE_STATES` records a status per set, and
    ``rerendered`` sets must coexist with their originals rather than replace them. This is
    checked rather than assumed because the *only* thing that makes a multi-pass proof
    possible is that pass one is still readable after pass two.
    """
    problems: list[str] = []
    plans = _rows(state.get("refinement_plans"))
    for plan in plans:
        plan_id = str(plan.get("refinement_plan_id", ""))
        before = str(plan.get("render_source_digest_before", ""))
        after = str(plan.get("render_source_digest_after", ""))
        if str(plan.get("status")) in ("RE_RENDERED", "CLOSED"):
            if not before:
                problems.append(
                    f"{plan_id}: the pre-repair work digest is gone. Before-evidence is history and "
                    "must survive the repair; a proof that cannot compare before to after proves nothing"
                )
            if after and before and after == before:
                problems.append(
                    f"{plan_id}: the post-repair work digest equals the pre-repair digest, so the "
                    "recorded repair changed nothing observable"
                )
        critique_id = str(plan.get("critique_id", ""))
        critique = next(
            (row for row in _rows(state.get("rendered_critiques"))
             if str(row.get("critique_id")) == critique_id), {}
        )
        if critique and not _rows(critique.get("findings")):
            problems.append(
                f"{plan_id}: the critique this repair responded to no longer has findings. The "
                "original finding must survive the repair attempt"
            )
    for evidence_set in _rows(state.get("rendered_evidence_sets")):
        if str(evidence_set.get("status")) == "SUPERSEDED" and not str(
            evidence_set.get("superseded_by", "")
        ):
            problems.append(
                f"{evidence_set.get('evidence_set_id', '?')}: marked SUPERSEDED without naming what "
                "superseded it, so the before/after relationship is lost"
            )
    return problems


def fixture_lineage(state: Mapping, *, requirement_id: str = "") -> dict:
    """A lineage record AR-223 fixtures can be built from, with the gaps still visible.

    Deliberately usable even when incomplete: a fixture that only worked on a perfect state
    would never exercise the gap path, which is the path that matters.
    """
    paths = requirement_paths(state)
    path = next(
        (row for row in paths if str(row.get("requirement_id")) == requirement_id), None
    ) if requirement_id else (paths[0] if paths else None)
    if path is None:
        raise ContractError(f"no requirement path matches {requirement_id!r}")
    return {
        "requirement_id": str(path.get("requirement_id", "")),
        "state": path_state(path),
        "available": {
            field: _availability(field, path)
            for field in PROOF_FIELDS
        },
        "gaps": _finding_gaps(path),
        "chain": [
            {"stage": "requirement", "id": str(path.get("requirement_id", ""))},
            *[
                {"stage": "implementation_revision", "id": str(plan_id)}
                for plan_id in (path.get("implementation_plan_ids") or [])
            ],
            *[
                {
                    "stage": "evidence",
                    "id": str((finding.get("evidence") or {}).get("evidence_set_id", "")),
                    "observed_work_digest": str((finding.get("evidence") or {}).get("observed_work_digest", "")),
                }
                for finding in _rows(path.get("findings"))
            ],
            *[
                {
                    "stage": "finding",
                    "id": str(finding.get("finding_id", "")),
                    "requirement_id": str(finding.get("requirement_id_on_finding", "")),
                }
                for finding in _rows(path.get("findings"))
            ],
            *[
                {
                    "stage": "repair",
                    "id": str((finding.get("repair") or {}).get("refinement_plan_id", "")),
                    "resulting_work_digest": str((finding.get("repair") or {}).get("work_digest_after", "")),
                }
                for finding in _rows(path.get("findings"))
                if str((finding.get("repair") or {}).get("refinement_plan_id", ""))
            ],
            *[
                {
                    "stage": "new_evidence",
                    "id": str((finding.get("repair") or {}).get("after_evidence_set_id", "")),
                }
                for finding in _rows(path.get("findings"))
                if str((finding.get("repair") or {}).get("after_evidence_set_id", ""))
            ],
        ],
        "note": (
            "gaps are carried, not hidden. An AR-223 fixture built from an incomplete path is the "
            "one that exercises the interesting distinctions"
        ),
    }


def _availability(field: str, path: Mapping) -> bool:
    findings = _rows(path.get("findings"))
    if not findings:
        return False
    if field == "requirement_id":
        return bool(str(path.get("requirement_id", "")))
    if field == "current_work_digest":
        return any(str((f.get("evidence") or {}).get("observed_work_digest", "")) for f in findings)
    if field == "evidence_identity":
        return any(str((f.get("evidence") or {}).get("evidence_set_id", "")) for f in findings)
    if field == "producer_identity":
        return bool(path.get("implementation_plan_ids"))
    if field == "reviewer_identity":
        return any(str(f.get("reviewer_execution", "")) for f in findings)
    if field == "finding_identity":
        return any(str(f.get("finding_id", "")) for f in findings)
    if field == "repair_identity":
        return any(str((f.get("repair") or {}).get("repair_execution", "")) for f in findings)
    if field == "resulting_work_digest":
        return any(str((f.get("repair") or {}).get("work_digest_after", "")) for f in findings)
    if field == "new_evidence_identity":
        return any(str((f.get("repair") or {}).get("after_evidence_set_id", "")) for f in findings)
    return False


__all__ = [
    "ACTOR_ROLES",
    "LINEAGE_STATES",
    "PROOF_FIELDS",
    "SELF_CERTIFICATION_PAIRS",
    "actor_table",
    "assert_append_only",
    "fixture_lineage",
    "path_state",
    "proof_problems",
    "proof_report",
    "requirement_paths",
    "self_certification_findings",
]
