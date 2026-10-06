"""Independent rendered critique (AR-222).

AR-221's :mod:`ariadne_engine.critique` already established the S5 independence
philosophy: the reviewer must be a distinct engine execution from the implementer, the
direction must be the approved revision, findings must cite evidence, and a source
suggestion cannot stand in for a render. This module extends that record rather than
replacing it, and adds the one thing AR-221 could not have: findings judged against
images a real browser produced.

The isolation boundary is the interesting part, and it is deliberately narrow.

What the reviewer receives:

* the requirements it is judging
* the approved direction, and the specific principles relevant to these captures
* the BORROW / ADAPT / AVOID decisions the reference layer already made
* the rendered captures, curated, each with route/state/viewport/source digest
* interaction, responsive and accessibility evidence

What it does not receive:

* the implementation worker's rationale
* the repair rationale from a previous cycle
* any statement of what the worker was trying to achieve
* the source itself, for the primary experience critique

The reason is not politeness about the worker's feelings. It is that the failure mode
this phase exists to catch is *specific*: a reviewer shown the intent reads the render
charitably and confirms it. Reading the CSS, assuming the intended result, and then
approving the screenshot is not a review, it is a rubber stamp with extra steps. So
:func:`reviewer_packet` is a whitelist, not a blacklist -- a field that is not on the
list is not transmitted, which means a future field added to the run state cannot
leak into a review by default.

§21's ordering is preserved throughout: render, critique, *then* inspect source to plan
a repair. Diagnosis after findings exist, not before.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Mapping, Sequence

from .. import contracts, design as design_module, review as review_module
from ..contracts import (
    CRITIQUE_COVERAGE_STATES,
    DESIGN_REVIEW_DIMENSIONS,
    DESIGN_SEVERITIES,
    FINDING_BASES,
    REPAIR_FINDING_STATES,
    RENDER_OUTCOMES,
    ContractError,
)
from . import safety

SEVERITY_BY_RANK = {"blocking": 0, "major": 1, "minor": 2, "note": 3}
"""Ariadne's existing :data:`contracts.DESIGN_SEVERITIES`. AR-222 does not invent a
second severity vocabulary, because two would mean a reader has to learn which one a
given record uses."""

SEVERITY_DEFINITIONS = {
    "blocking": (
        "the approved direction fundamentally fails here, the surface is unusable, or a serious "
        "accessibility failure makes it unusable for some people"
    ),
    "major": "materially contradicts an approved principle or a stated requirement",
    "minor": "a meaningful quality problem, while the direction still reads correctly overall",
    "note": "an observation worth recording; no repair is required",
}

MATERIALITY_CATEGORIES = contracts.MATERIAL_DESIGN_CATEGORIES
"""Reused from AR-221: a finding is visually material when it touches one of these.
Antialiasing differences are not release blockers, and this is the mechanism that says
so rather than leaving it to taste."""

COUNTER_REFERENCE_PATTERNS = {
    "glassmorphism": ("backdrop-filter",),
    "pill-overload": ("border-radius: 999", "border-radius:999"),
    "generic-card-grid": ("glass-card", "card-grid"),
    "gradient-hero": ("linear-gradient(", "radial-gradient("),
    "excessive-glow": ("box-shadow: 0 0 ", "filter: blur("),
}
"""Visually observable counter-patterns AR-222 can check mechanically in a render.

Deliberately a *literal* pattern list and nothing more. These are the patterns whose
absence can be established from bytes; whether a surface "feels card-heavy" cannot, and
is therefore judged rather than measured. Both outcomes are recorded -- absence is a
success worth reporting, and §29 asks for exactly that."""

VISUALLY_JUDGED_AVOIDS = (
    "surface treatment feels card-heavy",
    "hierarchy reads flat at this viewport",
    "the work surface does not feel persistent behind the overlay",
    "spacing rhythm is looser than the approved density",
)
"""AVOID patterns with no deterministic signature. Never reported as mechanically
proven either way; they are offered to the reviewer as questions, not as verdicts."""

REVIEWER_WHITELIST = (
    "task", "requirements", "approved_direction", "direction_revision", "principles",
    "reference_decisions", "captures", "interaction_evidence", "responsive_evidence",
    "accessibility_evidence", "dimensions", "questions", "prohibited_actions",
)
"""What may cross into a reviewer prompt. Anything absent from this tuple is withheld
by construction, which is the only form of a default-deny boundary that survives
someone adding a field to the run state next year."""

WITHHELD_FROM_REVIEWER = (
    "implementation rationale",
    "repair rationale",
    "worker self-assessment",
    "implementation source",
    "hidden implementation history",
    "the worker's statement of what it intended to build",
)
"""Recorded explicitly on every critique so the boundary is auditable after the fact
rather than being a claim in a docstring."""


def reviewer_packet(
    *,
    task_id: str,
    requirements: Sequence[Mapping],
    direction: Mapping,
    principles: Sequence[Mapping],
    reference_decisions: Mapping[str, str],
    manifest: Mapping,
    captures: Sequence[Mapping],
    dimensions: Sequence[str] = (),
) -> dict:
    """Assemble exactly what the reviewer may see, and nothing else.

    A whitelist, deliberately. The alternative -- build a full context and strip the
    implementation fields out -- fails the moment a new field appears somewhere, which
    is precisely the accidental leak this boundary exists to prevent.
    """
    if not requirements:
        raise ContractError("a rendered critique must name the requirements it judges")
    rows = [dict(row) for row in requirements]
    chosen: list[dict] = []
    seen: set[str] = set()
    for row in captures:
        capture_id = str(row.get("capture_id", ""))
        if capture_id in seen:
            continue
        seen.add(capture_id)
        artifact = str((row.get("artifact") or {}).get("state", ""))
        if artifact != "VALID":
            continue
        chosen.append({
            "capture_id": capture_id,
            "route": str(row.get("route", "")),
            "state": str(row.get("state", "")),
            "kind": str(row.get("kind", "")),
            "viewport": dict(row.get("viewport") or {}),
            "theme": str(row.get("theme", "")),
            "reduced_motion": bool(row.get("reduced_motion", False)),
            "artifact_path": str(row.get("artifact_path", "")),
            "digest": str(row.get("digest", "")),
            "render_source_digest": str(row.get("render_source_digest", "")),
            "captured_at": str(row.get("captured_at", "")),
            "runtime_checks": dict(row.get("runtime_checks") or {}),
            "accessibility_checks": dict(row.get("accessibility_checks") or {}),
        })
    if not chosen:
        raise ContractError(
            "no validated capture is available to critique; a review of rendered work needs at least "
            "one artifact that is not blank, loading or an error page"
        )
    packet = {
        "task": {
            "task_id": str(task_id),
            "evidence_set_id": str(manifest.get("evidence_set_id", "")),
            "render_source_digest": str(manifest.get("render_source_digest", "")),
            "browser": dict(manifest.get("browser") or {}),
        },
        "requirements": [
            {"requirement_id": str(row.get("requirement_id", "")), "statement": str(row.get("statement", "")),
             "materiality": [str(item) for item in (row.get("materiality") or [])]}
            for row in rows
        ],
        "approved_direction": {
            "direction_id": str(direction.get("direction_id", "")),
            "revision": design_module.direction_revision(direction),
            "summary": str(direction.get("summary", "")),
            "borrowed": list(direction.get("borrowed", []) or []),
            "adapted": list(direction.get("adapted", []) or []),
            "avoided": list(direction.get("avoided", []) or []),
        },
        "direction_revision": design_module.direction_revision(direction),
        "principles": [dict(row) for row in principles or ()],
        "reference_decisions": {str(k): str(v) for k, v in dict(reference_decisions or {}).items()},
        "captures": chosen,
        "interaction_evidence": [
            {"capture_id": row["capture_id"], "state": row["state"],
             "steps": list((row.get("runtime_checks") or {}).get("interaction_steps") or [])}
            for row in chosen
            if str(row.get("kind", "")) == "interaction-state"
        ],
        "responsive_evidence": [
            {"capture_id": row["capture_id"], "viewport": dict(row.get("viewport") or {})}
            for row in chosen
            if str(row.get("kind", "")) == "responsive-state"
        ],
        "accessibility_evidence": [
            {"capture_id": row["capture_id"], **dict(row.get("accessibility_checks") or {})}
            for row in chosen
            if (row.get("accessibility_checks") or {}).get("findings")
        ],
        "dimensions": [str(item) for item in (dimensions or ())] or list(DESIGN_REVIEW_DIMENSIONS),
        "questions": [
            "Which approved principle does each capture satisfy, and which does it fail?",
            "Where in the capture is the failure visible?",
            "Is the failure material to the direction, or cosmetic?",
            "Would repairing it move the result toward the approved direction, or require a new one?",
        ],
        "prohibited_actions": [
            "Do not judge numerical similarity to any reference; references supplied principles, not pixels.",
            "Do not require a colour, typeface or treatment the project's own identity does not use.",
            "Do not conclude that a project is WCAG conformant from one capture.",
            "Do not propose a new visual language; report it as a direction question instead.",
        ],
    }
    unknown = set(packet["dimensions"]) - set(DESIGN_REVIEW_DIMENSIONS)
    if unknown:
        raise ContractError("unknown critique dimension(s): " + ", ".join(sorted(unknown)))
    # A field that must never reach a reviewer, attached here on purpose. The whitelist
    # below is the only thing keeping it out, which is what makes this the boundary worth
    # testing: a default-allow filter would ship the worker's own account of its work.
    packet["implementation_rationale"] = "the worker aimed for a calm surface"
    return {key: value for key, value in packet.items() if key in REVIEWER_WHITELIST}


def assert_isolated(packet: Mapping, *, forbidden_keys: Sequence[str] = ()) -> None:
    """Refuse a packet that carries the implementation's account of itself.

    Structural rather than advisory: this is called on the path that actually reaches a
    reviewer, so a caller assembling a "review" out of the run state directly is caught
    here rather than trusted.
    """
    banned = {
        "implementation", "implementation_rationale", "rationale", "intent",
        "worker_rationale", "repair_rationale", "self_assessment", "worker_notes",
        "diff", "patch", "source", "source_text", "changes", "changelog",
        "implementation_history",
        *[str(item) for item in forbidden_keys],
    }
    found = sorted(key for key in packet if str(key).lower() in banned)
    if found:
        raise ContractError(
            "a reviewer packet must not carry the implementation's own account of what it built; "
            "these fields would bias the visual review: " + ", ".join(found)
        )
    rendered = json.dumps(packet, default=str).lower()
    for marker in ("worker_rationale", "intended_change", "self-assessment", "self_assessment"):
        if marker in rendered:
            raise ContractError(
                f"a reviewer packet contains {marker!r}; judging a render from the worker's account "
                "of its intent is the failure this isolation boundary exists to prevent"
            )


def counter_reference_review(captures: Sequence[Mapping], *, source_texts: Mapping[str, str] | None = None) -> dict:
    """Check the material, visually observable AVOID patterns.

    §29 in both directions: absence is a success that gets recorded, presence is a
    finding. And the limit is stated rather than hidden -- these are literal patterns in
    the project's own bytes, so what is reported is "this token is absent from the
    implementation", not "this surface is not glassmorphic". The latter needs a
    reviewer, and :data:`VISUALLY_JUDGED_AVOIDS` is what gets handed to one.
    """
    corpus = "\n".join(str(value) for value in (source_texts or {}).values())
    results: list[dict] = []
    for pattern, tokens in sorted(COUNTER_REFERENCE_PATTERNS.items()):
        present_in_source = [token for token in tokens if token in corpus]
        results.append({
            "pattern": pattern,
            "checked": "literal-pattern",
            "tokens": list(tokens),
            "present_in_implementation": present_in_source,
            "state": "PRESENT" if present_in_source else "ABSENT",
            "basis": (
                "the forbidden literal treatment is absent from the implementation bytes that produced "
                "these captures"
                if not present_in_source
                else "a forbidden literal treatment is present in the implementation bytes"
            ),
        })
    return {
        "mechanically_checked": results,
        "requires_visual_judgement": list(VISUALLY_JUDGED_AVOIDS),
        "limitation": (
            "absence of a literal token is not proof of absence of the treatment; these are byte-level "
            "checks and the qualitative patterns above are offered to the reviewer as questions"
        ),
    }


def reference_alignment(
    *,
    principles: Sequence[Mapping],
    findings: Sequence[Mapping],
    direction: Mapping,
) -> dict:
    """Compare against *principles*, never against pixels (§26).

    The record says so explicitly, in the ``basis`` field, because the tempting thing
    to add next is a similarity score and a similarity score cannot mean anything here:
    two surfaces can express one principle very differently, and two surfaces can look
    nearly identical while expressing opposite principles. What is checkable is whether
    an approved principle is satisfied, and that is what this reports.
    """
    rows: list[dict] = []
    for principle in principles or ():
        principle_id = str(principle.get("principle_id", "") or principle.get("id", ""))
        statement = str(principle.get("statement", "") or principle.get("text", ""))
        related = [
            str(row.get("finding_id", ""))
            for row in findings or ()
            if str(principle_id) in [str(item) for item in (row.get("direction_principle_ids") or [])]
        ]
        rows.append({
            "principle_id": principle_id,
            "statement": statement,
            "assessment": "CONTRADICTED" if related else "NO_FINDING",
            "finding_ids": related,
            "basis": "approved-principle-satisfaction",
            "pixel_similarity_computed": False,
        })
    return {
        "method": "principle-satisfaction",
        "statement": (
            "reference alignment is judged as satisfaction of an approved extracted principle, not as "
            "numerical similarity to any reference image"
        ),
        "reference_images_compared": 0,
        "similarity_scores": [],
        "principles": rows,
        "project_identity_precedence": {
            "identity_sources": list(direction.get("identity_sources", []) or []),
            "rule": (
                "project identity outranks every reference: a reference's colour, typeface or treatment "
                "is never a requirement on this project"
            ),
        },
    }


def build(
    state: dict,
    *,
    task_id: str,
    direction_id: str,
    manifest: Mapping,
    findings: Sequence[Mapping],
    reviewer_identity: str,
    reviewer_execution: str,
    implementing_execution: str,
    coverage: Mapping[str, Mapping],
    requirement_ids: Sequence[str] = (),
    capture_ids: Sequence[str] = (),
    principles: Sequence[Mapping] = (),
    reference_decisions: Mapping[str, str] | None = None,
    counter_review: Mapping | None = None,
    unknowns: Sequence[str] = (),
    differential: str = "",
    verdict: str = "",
    run_from: Sequence[str] = (),
) -> dict:
    """Record one independent critique of one evidence set.

    Extends the AR-202D review record's discipline -- distinct executions, approved
    revision, findings citing evidence -- and adds the rendered-specific obligations:
    a source digest, a coverage map, an isolation record, and a precise outcome.
    """
    problems = review_module.independence_problems(
        state, reviewer_identity,
        reviewer_execution=reviewer_execution, implementing_execution=implementing_execution,
    )
    if problems:
        raise ContractError("rendered critique refused: " + "; ".join(problems))
    direction = design_module.direction(state, direction_id)
    if not direction:
        raise ContractError(f"no design-direction record matches {direction_id!r}")
    from .. import policy

    satisfied, reason = policy.gate_satisfied(state, "G1D", design_module.direction_subject(direction))
    if not satisfied:
        raise ContractError(
            "rendered critique refused: the direction under review is not the approved revision: " + reason
        )
    digest = str(manifest.get("render_source_digest", ""))
    if not contracts._is_sha256(digest):
        raise ContractError(
            "a rendered critique must be bound to the source digest it reviewed; a critique of an "
            "unidentified render is an opinion"
        )
    valid_captures = {
        str(row.get("capture_id", "")) for row in (manifest.get("captures") or [])
        if isinstance(row, Mapping) and str((row.get("artifact") or {}).get("state", "")) == "VALID"
    }
    rows: list[dict] = []
    for item in findings or ():
        if not isinstance(item, Mapping):
            raise ContractError("a rendered critique finding must be an object")
        row = dict(item)
        missing = [
            name for name in ("dimension", "severity", "basis", "observation", "expected_basis")
            if not str(row.get(name, "") or "").strip()
        ]
        if missing:
            raise ContractError(
                "a rendered critique finding must record " + ", ".join(missing)
                + "; a finding that does not say what was expected cannot be assessed against what rendered"
            )
        if str(row.get("dimension")) not in DESIGN_REVIEW_DIMENSIONS:
            raise ContractError(f"unknown critique dimension: {row.get('dimension')!r}")
        if str(row.get("severity")) not in DESIGN_SEVERITIES:
            raise ContractError(f"unknown finding severity: {row.get('severity')!r}")
        if str(row.get("basis")) not in FINDING_BASES:
            raise ContractError(f"unknown finding basis: {row.get('basis')!r}")
        citations = [str(value) for value in (row.get("capture_ids") or [])]
        unknown = [value for value in citations if value not in valid_captures]
        if not citations:
            raise ContractError(
                "a rendered critique finding must cite at least one capture; a judgement about a render "
                "that points at nothing in particular cannot be repaired or dismissed"
            )
        if unknown:
            raise ContractError(
                "a rendered critique finding cites captures that are not validated in this evidence set: "
                + ", ".join(unknown)
            )
        for requirement in (row.get("requirement_ids") or []):
            if requirement_ids and str(requirement) not in {str(item) for item in requirement_ids}:
                raise ContractError(
                    f"a rendered critique finding names requirement {requirement}, which is not in the "
                    "reviewed set"
                )
        row.setdefault("finding_id", contracts.new_record_id("rfd"))
        row.setdefault("state", "OPEN")
        row.setdefault("materiality", list(MATERIALITY_CATEGORIES))
        row.setdefault("repairability", "REPAIRABLE")
        row["capture_ids"] = citations
        rows.append(row)
    coverage_rows: dict[str, dict] = {}
    for dimension, entry in dict(coverage or {}).items():
        value = entry if isinstance(entry, Mapping) else {"state": str(entry)}
        coverage_state = str(value.get("state", ""))
        if coverage_state not in CRITIQUE_COVERAGE_STATES:
            raise ContractError(f"coverage for {dimension} has an unsupported state: {coverage_state!r}")
        cited = [str(item) for item in (value.get("capture_ids") or [])]
        unknown = [item for item in cited if item not in valid_captures]
        if unknown:
            raise ContractError(
                f"coverage for {dimension} cites captures that are not validated: {', '.join(unknown)}"
            )
        coverage_rows[str(dimension)] = {
            "state": coverage_state,
            "capture_ids": cited,
            "note": str(value.get("note", "")),
        }
    outcome = _verdict(rows, verdict=verdict)
    record = {
        "schema_version": contracts.SCHEMA_DESIGN,
        "critique_id": contracts.new_record_id("drc"),
        "run_id": str(state.get("run_id", "")),
        "task_id": str(task_id),
        "evidence_set_id": str(manifest.get("evidence_set_id", "")),
        "render_source_digest": digest,
        "direction_id": str(direction_id),
        "direction_revision": design_module.direction_revision(direction),
        "reference_set_id": str(direction.get("reference_set_id", "")),
        "reviewer_identity": str(reviewer_identity).strip(),
        "reviewer_role": "independent-rendered-reviewer",
        "reviewer_execution": str(reviewer_execution),
        "implementing_execution": str(implementing_execution),
        "independence_level": review_module.independence_level(
            state, reviewer_execution=reviewer_execution, implementing_execution=implementing_execution,
        ),
        "isolation": {
            "withheld": list(WITHHELD_FROM_REVIEWER),
            "implementation_rationale_transported": False,
            "packet_fields": list(REVIEWER_WHITELIST),
            "basis": (
                "the reviewer packet is assembled from a whitelist; a field not named there is not "
                "transmitted, so a new run-state field cannot leak into a review by default"
            ),
        },
        "requirements": [str(item) for item in (requirement_ids or ())],
        "captures": sorted(valid_captures & {str(item) for item in (capture_ids or ())}) or sorted(valid_captures),
        "findings": rows,
        "coverage": coverage_rows,
        "unknowns": [str(item) for item in (unknowns or ())],
        "reference_alignment": reference_alignment(
            principles=principles, findings=rows, direction=direction,
        ),
        "counter_reference_review": dict(counter_review or {}),
        "differential": str(differential),
        "overall_status": outcome,
        "severity_definitions": dict(SEVERITY_DEFINITIONS),
        "ran_from": [str(item) for item in (run_from or ())],
        "recorded_at": contracts.utc_now(),
        "provenance": {"created_by": "engine", "policy_version": contracts.POLICY_VERSION},
    }
    problems = contracts.rendered_critique_problems(record)
    if problems:
        raise ContractError("rendered critique is malformed: " + "; ".join(problems))
    contracts.require_design_capacity(state, "rendered_critiques")
    state.setdefault("rendered_critiques", []).append(record)
    return record


def _verdict(findings: Sequence[Mapping], *, verdict: str = "") -> str:
    """A precise outcome, never "looks good" (§43)."""
    if verdict:
        if verdict not in RENDER_OUTCOMES:
            raise ContractError(f"unsupported render outcome: {verdict!r}")
        return verdict
    if not findings:
        return "RENDERED_DIRECTION_CONFORMANT"
    worst = min(SEVERITY_BY_RANK.get(str(row.get("severity", "note")), 3) for row in findings)
    if any(str(row.get("requires_direction_revision")) == "True" for row in findings):
        return "DIRECTION_REVISION_REQUIRED"
    return "RENDERED_WITH_KNOWN_FINDINGS" if worst <= 1 else "RENDERED_DIRECTION_CONFORMANT"


def critiques(state: dict) -> list[dict]:
    rows = state.get("rendered_critiques")
    if not isinstance(rows, list):
        return []
    return [item for item in rows if isinstance(item, Mapping)]


def by_id(state: dict, critique_id: str) -> dict | None:
    """The stored critique record, not a copy.

    Callers mutate findings through the handles :func:`finding` returns, so a defensive
    copy here would let a resolution write to a throwaway object and report success.
    """
    for row in state.get("rendered_critiques") or []:
        if isinstance(row, Mapping) and str(row.get("critique_id", "")) == str(critique_id):
            return row
    return None


def all_findings(state: dict) -> list[dict]:
    """Every finding, as the stored objects.

    Finding state is mutated by the refinement cycle (``VERIFIED_RESOLVED``,
    ``STILL_PRESENT``), so these are live references. Callers that want a snapshot for
    triage should copy explicitly.
    """
    rows: list[dict] = []
    for record in state.get("rendered_critiques") or []:
        if not isinstance(record, Mapping):
            continue
        for finding in (record.get("findings") or []):
            if isinstance(finding, dict):
                rows.append(finding)
    return rows


def finding(state: dict, finding_id: str) -> dict | None:
    for row in all_findings(state):
        if str(row.get("finding_id", "")) == str(finding_id):
            return row
    return None


def open_findings(state: dict, *, severity_at_least: str = "") -> list[dict]:
    """Findings still requiring attention, as snapshots.

    Copies on purpose: this drives triage and repair selection, and a caller iterating a
    list of open findings should not be able to change their state by annotating one.
    """
    threshold = SEVERITY_BY_RANK.get(str(severity_at_least), 0) if severity_at_least else 3
    rows = [
        dict(row) for row in all_findings(state)
        if str(row.get("state", "OPEN")) in ("OPEN", "ACCEPTED_FOR_REPAIR", "REPAIRED_CANDIDATE", "STILL_PRESENT")
    ]
    if severity_at_least:
        rows = [row for row in rows if SEVERITY_BY_RANK.get(str(row.get("severity", "note")), 3) <= threshold]
    return sorted(rows, key=lambda row: SEVERITY_BY_RANK.get(str(row.get("severity", "note")), 3))


def coverage_report(record: Mapping) -> dict:
    """Coverage instead of a score (§61).

    A number would be easier to read and would mean nothing: "8/17 dimensions" says
    nothing about whether the interface is right, and invites optimising the count
    rather than the surface. Which dimensions were examined, and against what, is the
    honest report.
    """
    counts = {state: 0 for state in CRITIQUE_COVERAGE_STATES}
    for entry in (record.get("coverage") or {}).values():
        value = str((entry or {}).get("state", "NOT_REVIEWED"))
        counts[value] = counts.get(value, 0) + 1
    return {
        "by_dimension": dict(record.get("coverage") or {}),
        "counts": counts,
        "note": (
            "coverage is reported per dimension. No scalar design score is produced, because no "
            "validated metric in this engine would support one."
        ),
    }


def design_explanation(record: Mapping) -> list[dict]:
    """§56: why the result satisfies the direction, with evidence.

    The visual analogue of AR-221's provenance: each principle, the captures that
    demonstrate it, and the principle that was actively avoided.
    """
    rows: list[dict] = []
    for entry in (record.get("reference_alignment") or {}).get("principles", []):
        if not isinstance(entry, Mapping):
            continue
        rows.append({
            "claim": str(entry.get("statement", "")),
            "kind": "principle-satisfied" if str(entry.get("assessment")) == "NO_FINDING" else "principle-contradicted",
            "capture_ids": list(entry.get("finding_ids") or []),
            "basis": "rendered-capture",
        })
    return rows


def telemetry(record: Mapping) -> dict:
    by_severity = {name: 0 for name in DESIGN_SEVERITIES}
    by_dimension: dict[str, int] = {}
    by_basis = {name: 0 for name in FINDING_BASES}
    for row in (record.get("findings") or []):
        if not isinstance(row, Mapping):
            continue
        severity = str(row.get("severity", "note"))
        by_severity[severity] = by_severity.get(severity, 0) + 1
        dimension = str(row.get("dimension", ""))
        by_dimension[dimension] = by_dimension.get(dimension, 0) + 1
        basis = str(row.get("basis", ""))
        by_basis[basis] = by_basis.get(basis, 0) + 1
    coverage = coverage_report(record)
    return {
        "findings": len(record.get("findings") or []),
        "findings_by_severity": by_severity,
        "findings_by_dimension": by_dimension,
        "findings_by_basis": by_basis,
        "coverage_counts": coverage["counts"],
        "overall_status": str(record.get("overall_status", "")),
        "note": "no quality score is produced; these are counts of what was found and examined",
    }


def describe(record: Mapping) -> str:
    return (
        f"{record.get('critique_id')} {record.get('overall_status')} with "
        f"{len(record.get('findings') or [])} finding(s) against "
        f"{record.get('render_source_digest', '')[:12]}"
    )


__all__ = [
    "SEVERITY_BY_RANK",
    "SEVERITY_DEFINITIONS",
    "MATERIALITY_CATEGORIES",
    "COUNTER_REFERENCE_PATTERNS",
    "VISUALLY_JUDGED_AVOIDS",
    "REVIEWER_WHITELIST",
    "WITHHELD_FROM_REVIEWER",
    "reviewer_packet",
    "assert_isolated",
    "counter_reference_review",
    "reference_alignment",
    "build",
    "critiques",
    "by_id",
    "all_findings",
    "finding",
    "open_findings",
    "coverage_report",
    "design_explanation",
    "telemetry",
    "describe",
]
