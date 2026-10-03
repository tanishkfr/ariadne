"""Grounded design direction: every major choice cites its evidence (AR-220).

This module does not redesign Design Intelligence. It adds the missing link
between a ``ReferenceSet`` and the *existing* AR-202D direction record, so that:

> **Why this navigation density?**
> → Reference X, observed hierarchy pattern
>
> **Why this panel behaviour?**
> → Reference Y + implementation reference Z
>
> **Why this colour palette?**
> → the project's own brand tokens, **not** a borrowed reference colour

Three separations are load-bearing, and each has its own representation rather
than living in one blob of prose:

* **observed / recommended / approved.** A reference observation is what a source
  records. A *principle* is what Ariadne proposes on top of it. Approval stays
  where it already lives - ``design.approve_direction`` behind gate ``G1D`` - and
  nothing here approves anything.
* **borrow / adapt / avoid.** Every pattern a reference set carries must be
  treated one way or the other, so reference acquisition cannot decay into
  reference cloning.
* **project identity before borrowed identity.** When a design choice's colour,
  type or spacing comes from the project, it says so *and names the project
  artefact*. The most common silent failure in reference-driven design is a
  borrowed palette arriving in a brand slot, and this is where that gets caught.

The compiler produces a **candidate** direction. It stops at approved-ready
evidence. It performs no UI implementation, no rendering and no critique: that is
AR-221's scope, and AR-220 does not go there.
"""

from __future__ import annotations

from typing import Mapping, Sequence

from .. import contracts
from ..contracts import ContractError

PRINCIPLE_CONFIDENCE = ("SUPPORTED", "PARTIAL", "WEAK", "UNSUPPORTED")
"""How much evidence stands behind an extracted principle.

``SUPPORTED`` requires two or more independent references on the dimension.
``UNSUPPORTED`` is the honest answer from a single vague description, and the
compiler will not invent a principle to fill a slot.
"""

MIN_REFERENCES_FOR_SUPPORTED = 2
"""Independence threshold for ``SUPPORTED``.

One reference agreeing with itself is not corroboration. This is the number that
keeps "two sites do it" from being recorded as a principle.
"""

GENERIC_GROUNDING_BLOCKERS = (
    "you should", "must use", "always use", "never use", "required to",
    "set the", "change the", "use this", "apply this", "ignore previous",
)
"""Phrases that turn a recorded observation into an instruction.

Checked by :func:`principles_problems` rather than trusted, because the whole
value of a reference layer is that it cannot be talked into issuing orders by
something it read.
"""


def extract_principles(
    members: Sequence[Mapping],
    references_by_id: Mapping[str, Mapping],
    *,
    applicable_to: str = "",
    dimension_filter: Sequence[str] = (),
) -> list[dict]:
    """Turn a set's observations into principles that cite the evidence.

    Only dimensions observed in **two or more independent source identities**
    produce a principle, and any dimension with one supporter is recorded as
    ``UNSUPPORTED`` rather than promoted. Corroboration is counted by distinct
    ``source_identity``, not by distinct reference ids, so the same document
    entered twice cannot manufacture agreement.
    """
    wanted = {str(item) for item in dimension_filter}
    by_dimension: dict[str, list[tuple[str, Mapping, Mapping]]] = {}
    for member in members:
        if not isinstance(member, Mapping):
            continue
        reference_id = str(member.get("reference_id", ""))
        record = references_by_id.get(reference_id) or {}
        classification = record.get("classification") if isinstance(record.get("classification"), Mapping) else {}
        identity = str(classification.get("source_identity", "")) or reference_id
        roles = [str(role) for role in (member.get("roles") or [])]
        for pattern in record.get("observed_patterns") or []:
            if not isinstance(pattern, Mapping):
                continue
            dimension = str(pattern.get("dimension", ""))
            if not dimension or (wanted and dimension not in wanted):
                continue
            by_dimension.setdefault(dimension, []).append((identity, record, pattern))

    principles: list[dict] = []
    for dimension in sorted(by_dimension):
        rows = by_dimension[dimension]
        identities = sorted({identity for identity, _r, _p in rows})
        confidence = (
            "SUPPORTED" if len(identities) >= MIN_REFERENCES_FOR_SUPPORTED
            else "PARTIAL" if len(identities) == 1
            else "UNSUPPORTED"
        )
        if confidence == "UNSUPPORTED":
            continue
        citations = sorted({str(record.get("reference_id", "")) for _i, record, _p in rows})
        principles.append({
            "principle_id": contracts.new_record_id("prn"),
            "dimension": dimension,
            "statement": _principle_statement(dimension, rows),
            "evidence": [
                {
                    "reference_id": str(record.get("reference_id", "")),
                    "source_identity": identity,
                    "observation": str(pattern.get("observation", "")),
                    "basis": str(pattern.get("basis", "")),
                }
                for identity, record, pattern in rows
            ],
            "distinct_sources": len(identities),
            "confidence": confidence,
            "applicability": str(applicable_to) or "not-evaluated",
            "note": (
                "this principle generalises what the cited sources record. It is a proposal, not an "
                "approval, and the sources remain the evidence"
            ),
        })
    return principles


def _principle_statement(dimension: str, rows: Sequence[tuple[str, Mapping, Mapping]]) -> str:
    """A deterministic statement naming the dimension and its support.

    Deliberately not a generated sentence about what the design *should* do. The
    statement is a claim about what was observed plus the count of independent
    sources that observed it; the judgement belongs to the direction that cites it.
    """
    identities = {identity for identity, _record, _pattern in rows}
    first = str(rows[0][2].get("observation", "")).strip()[:180]
    return (
        f"{dimension} is addressed consistently by {len(identities)} inspected source(s); "
        f"first observation: {first}"
    )


def treatments_for_set(members: Sequence[Mapping], references_by_id: Mapping[str, Mapping]) -> list[dict]:
    """Every member's BORROW / ADAPT / AVOID treatment, as a set-level table.

    A member with no treatment is reported, not defaulted. ``build_treatments``
    applies an ``ADAPT`` default at the *pattern* level inside one reference; at
    the *set* level the decision is the caller's, because choosing to borrow
    across a whole reference is a different act from choosing per pattern.
    """
    rows: list[dict] = []
    for member in members:
        if not isinstance(member, Mapping):
            continue
        reference_id = str(member.get("reference_id", ""))
        record = references_by_id.get(reference_id) or {}
        recorded = record.get("treatments")
        if not isinstance(recorded, list) or not recorded:
            rows.append({
                "reference_id": reference_id,
                "treated": False,
                "reason": "no treatment recorded; this reference contributes no pattern to the direction",
            })
            continue
        for item in recorded:
            if not isinstance(item, Mapping):
                continue
            rows.append({
                "reference_id": reference_id,
                "treated": True,
                "treatment": str(item.get("treatment", "")),
                "dimension": str(item.get("dimension", "")),
                "pattern": str(item.get("pattern", "")),
            })
    return rows


def principle_problems(principle: Mapping) -> list[str]:
    """Validate one extracted principle."""
    problems: list[str] = []
    if str(principle.get("dimension", "")) not in contracts.REFERENCE_PATTERN_DIMENSIONS:
        problems.append(f"unknown principle dimension: {principle.get('dimension')}")
    confidence = str(principle.get("confidence", ""))
    if confidence not in PRINCIPLE_CONFIDENCE:
        problems.append(f"unknown principle confidence: {confidence or 'missing'}")
    evidence = principle.get("evidence")
    if not isinstance(evidence, list) or not evidence:
        problems.append("a principle must cite at least one observation")
    else:
        identities = {str(row.get("source_identity", "")) for row in evidence if isinstance(row, Mapping)}
        if confidence == "SUPPORTED" and len(identities) < MIN_REFERENCES_FOR_SUPPORTED:
            problems.append(
                f"a principle claims SUPPORTED from {len(identities)} source(s); corroboration needs "
                f"{MIN_REFERENCES_FOR_SUPPORTED} independent source identities"
            )
    return problems


def principles_problems(principles: Sequence[Mapping]) -> list[str]:
    """Cross-record checks over extracted principles, including the injection boundary."""
    problems: list[str] = []
    for principle in principles:
        if not isinstance(principle, Mapping):
            problems.append("principle must be a mapping")
            continue
        problems.extend(principle_problems(principle))
        text = str(principle.get("statement", "")).lower()
        for blocker in GENERIC_GROUNDING_BLOCKERS:
            if blocker in text:
                problems.append(
                    f"principle {principle.get('dimension')} is phrased as an instruction ({blocker!r}); "
                    "an extracted principle must state what was observed, not order the design"
                )
                break
        for row in principle.get("evidence") or []:
            if not isinstance(row, Mapping):
                continue
            if not str(row.get("observation", "")).strip():
                problems.append(
                    f"principle {principle.get('dimension')} cites an empty observation; a citation must "
                    "say what was observed"
                )
    return problems


def grounded_choices(
    direction_sections: Mapping[str, Sequence[str]],
    members: Sequence[Mapping],
    references_by_id: Mapping[str, Mapping],
    *,
    project_identity: Mapping | None = None,
) -> list[dict]:
    """Explain every section of a direction by naming the evidence behind it.

    A section with no supporting reference is reported as ``PROJECT_CONSTRAINT``
    when project identity covers it and as ``UNGROUNDED`` when nothing does. A
    direction with ``UNGROUNDED`` sections has parts nobody can justify, which is
    precisely the thing this layer is meant to make visible.
    """
    identity = project_identity if isinstance(project_identity, Mapping) else {}
    rows: list[dict] = []
    for section in sorted(direction_sections):
        statements = [str(item) for item in direction_sections.get(section) or [] if str(item).strip()]
        if not statements:
            continue
        project_statements = [
            item.strip()[len(PROJECT_STATEMENT_PREFIX):].strip()
            for item in statements
            if item.strip().startswith(PROJECT_STATEMENT_PREFIX)
        ]
        supports = _section_supports(section, statements, members, references_by_id)
        tokens = identity.get("design_tokens") if isinstance(identity.get("design_tokens"), Mapping) else {}
        documents = identity.get("design_documents") if isinstance(identity.get("design_documents"), list) else []
        project_support = {
            "source": "project",
            "detail": (
                "the project's own design record constrains this section; a borrowed reference does not "
                "override project identity"
            ),
            "statements": project_statements,
            "artefacts": list(tokens.get("files") or []) + [
                str(row.get("path", "")) for row in documents if isinstance(row, Mapping)
            ],
        }
        # A section can be both project-constrained and reference-informed, and
        # saying so is the point. Collapsing it to whichever evidence happens to
        # match first would either hide the project's own constraint or claim a
        # reference supported a rule the project supplied.
        if project_statements and supports:
            rows.append({
                "section": section,
                "statements": len(statements),
                "grounding": "PROJECT_CONSTRAINT_AND_REFERENCE",
                "supports": [project_support, *supports],
                "project_statements": len(project_statements),
            })
            continue
        if supports:
            rows.append({
                "section": section,
                "statements": len(statements),
                "grounding": "REFERENCE_EVIDENCE",
                "supports": supports,
                "project_statements": len(project_statements),
            })
            continue
        if project_statements or tokens.get("found") or documents:
            rows.append({
                "section": section,
                "statements": len(statements),
                "grounding": "PROJECT_CONSTRAINT",
                "supports": [project_support],
                "project_statements": len(project_statements),
            })
            continue
        rows.append({
            "section": section,
            "statements": len(statements),
            "grounding": "UNGROUNDED",
            "supports": [],
            "problem": (
                f"direction section {section!r} cites no reference and no project constraint; it cannot be "
                "explained to a reviewer"
            ),
        })
    return rows


_SECTION_ROLE_HINTS = {
    "key_hierarchy": ("PRIMARY_DIRECTION", "LAYOUT_REFERENCE"),
    "interaction_principles": ("INTERACTION_REFERENCE", "PRIMARY_DIRECTION"),
    "visual_principles": ("PRIMARY_DIRECTION", "TYPOGRAPHY_REFERENCE"),
    "content_principles": ("PRIMARY_DIRECTION", "TYPOGRAPHY_REFERENCE"),
    "existing_system": ("IMPLEMENTATION_REFERENCE", "COMPONENT_REFERENCE"),
    "reference_findings_adopted": ("PRIMARY_DIRECTION", "LAYOUT_REFERENCE", "COMPONENT_REFERENCE"),
    "findings_rejected": ("COUNTER_REFERENCE",),
    "constraints": ("COUNTER_REFERENCE", "PRIMARY_DIRECTION"),
    "accessibility_requirements": ("PRIMARY_DIRECTION", "COMPONENT_REFERENCE"),
    "responsive_requirements": ("LAYOUT_REFERENCE", "PRIMARY_DIRECTION"),
}


PROJECT_STATEMENT_PREFIX = "[project]"
"""Marks a direction statement whose evidence is the project's own design record.

Without an explicit marker, a project-sourced interaction rule and a
reference-sourced one would be indistinguishable in the direction, and the
provenance would claim a reference supports something it never said.
"""


def _section_supports(
    section: str,
    statements: Sequence[str],
    members: Sequence[Mapping],
    references_by_id: Mapping[str, Mapping],
) -> list[dict]:
    """What supports a section: project statements and/or reference evidence.

    A section whose statements are *all* project-sourced is reported as
    ``PROJECT_CONSTRAINT`` even when references also match the section's roles,
    because attributing a project constraint to an external reference would be
    the exact confusion this layer exists to prevent.
    """
    project_only = bool(statements) and all(
        str(item).strip().startswith(PROJECT_STATEMENT_PREFIX) for item in statements
    )
    if project_only:
        return []
    roles = _SECTION_ROLE_HINTS.get(section, ())
    supports: list[dict] = []
    for member in members:
        if not isinstance(member, Mapping):
            continue
        member_roles = [str(role) for role in (member.get("roles") or [])]
        if roles and not any(role in member_roles for role in roles):
            continue
        reference_id = str(member.get("reference_id", ""))
        record = references_by_id.get(reference_id) or {}
        classification = record.get("classification") if isinstance(record.get("classification"), Mapping) else {}
        dimensions = sorted({
            str(row.get("dimension", ""))
            for row in (record.get("observed_patterns") or [])
            if isinstance(row, Mapping) and str(row.get("dimension", ""))
        })
        supports.append({
            "reference_id": reference_id,
            "source_kind": str(classification.get("source_kind", "")),
            "evidence_level": str(classification.get("evidence_level", "")),
            "roles": member_roles,
            "observed_dimensions": dimensions,
            "counter_pattern": str(member.get("counter_pattern", "")),
        })
    return supports


def compile_candidate_direction(
    state: dict,
    *,
    task_id: str,
    goal: str,
    scope: str,
    requirement_scope: str,
    reference_set_record: Mapping,
    references_by_id: Mapping[str, Mapping],
    members: Sequence[Mapping],
    project_identity: Mapping | None = None,
    product_context: Sequence[str] = (),
    accessible: Sequence[str] = (),
    responsive: Sequence[str] = (),
    existing_system: Sequence[str] = (),
    approved_deviations: Sequence[str] = (),
    project_sections: Mapping[str, Sequence[str]] | None = None,
    create: bool = True,
) -> dict:
    """Produce a grounded, **unapproved** design direction and its provenance.

    The returned record is the engine's ordinary AR-202D direction record plus an
    ``ar220_grounding`` block. It is created with ``status: "candidate"``: nothing
    here approves anything, and approval remains a human decision through
    ``G1D``.
    """
    from .. import design as design_module

    if not isinstance(reference_set_record, Mapping) or not reference_set_record:
        raise ContractError("a grounded direction needs the reference set it was derived from")
    set_problems = contracts.reference_set_problems(reference_set_record)
    if set_problems:
        raise ContractError(
            "cannot compile a direction from a malformed reference set: " + "; ".join(set_problems)
        )
    coverage_block = reference_set_record.get("coverage") if isinstance(reference_set_record.get("coverage"), Mapping) else {}
    if str(coverage_block.get("verdict", "")) != "READY":
        raise ContractError(
            "cannot compile a grounded direction from a reference set whose coverage is "
            f"{coverage_block.get('verdict', 'UNKNOWN')!r}; the holes are recorded as "
            + "; ".join(str(item) for item in (coverage_block.get("missing") or []) or ["unspecified"])
        )

    counter_members = [
        member for member in members
        if isinstance(member, Mapping) and "COUNTER_REFERENCE" in (member.get("roles") or [])
    ]
    if not counter_members:
        raise ContractError(
            "a grounded direction needs at least one counter-reference; a direction assembled only from "
            "things it admires has not been told what to avoid, and 'not a generic AI dashboard' is not "
            "executable without one"
        )

    principles = extract_principles(members, references_by_id, applicable_to=str(requirement_scope))
    principle_problems_found = principles_problems(principles)
    if principle_problems_found:
        raise ContractError("extracted principles are not supportable: " + "; ".join(principle_problems_found))

    grounding_sections = _sections_from_principles(
        principles, members, references_by_id, project_sections=project_sections
    )
    directions = grounding_sections
    grounding = {
        "reference_set_id": str(reference_set_record.get("reference_set_id", "")),
        "principles": principles,
        "treatments": treatments_for_set(members, references_by_id),
        "counter_references": [
            {
                "reference_id": str(member.get("reference_id", "")),
                "anti_pattern": str(member.get("counter_pattern", "")),
            }
            for member in counter_members
        ],
        "coverage": dict(coverage_block),
        "diversity": dict(
            reference_set_record.get("diversity")
            if isinstance(reference_set_record.get("diversity"), Mapping) else {}
        ),
        "budget": dict(
            reference_set_record.get("budget")
            if isinstance(reference_set_record.get("budget"), Mapping) else {}
        ),
        "observed_is_not_recommended": (
            "observed_patterns on each reference are what the source records; the principles below are "
            "Ariadne's generalisation; neither is an approval"
        ),
        "project_identity": dict(project_identity) if isinstance(project_identity, Mapping) else {},
        "status": "CANDIDATE",
        "approval_required": True,
        "approval_gate": "G1D",
    }

    if not create:
        return {"sections": directions, "grounding": grounding}

    record = design_module.create_direction(
        state,
        task_id=task_id,
        goal=goal,
        scope=scope,
        product_context=list(product_context) or [f"Design direction grounded in {requirement_scope}"],
        key_hierarchy=directions["key_hierarchy"],
        interaction_principles=directions["interaction_principles"],
        visual_principles=directions["visual_principles"],
        content_principles=directions["content_principles"],
        constraints=directions["constraints"],
        existing_system=list(existing_system),
        reference_findings_adopted=directions["reference_findings_adopted"],
        findings_rejected=directions["findings_rejected"],
        accessibility_requirements=list(accessible),
        responsive_requirements=list(responsive),
        approved_deviations=list(approved_deviations),
    )
    record["ar220_grounding"] = grounding
    grounding["choices"] = grounded_choices(
        {name: value for name, value in directions.items()},
        members,
        references_by_id,
        project_identity=project_identity,
    )
    ungrounded = [row["section"] for row in grounding["choices"] if row["grounding"] == "UNGROUNDED"]
    grounding["ungrounded_sections"] = ungrounded
    grounding["ready_for_approval"] = not ungrounded
    return record


def _sections_from_principles(
    principles: Sequence[Mapping],
    members: Sequence[Mapping],
    references_by_id: Mapping[str, Mapping],
    project_sections: Mapping[str, Sequence[str]] | None = None,
) -> dict[str, list[str]]:
    """Group extracted principles into the direction record's sections.

    The mapping from principle dimension to direction section is a declared table,
    not a model output, so a reviewer can see why a statement landed where it did.

    A section with no principle is left empty here and reported by
    :func:`grounded_choices` rather than padded with a generic sentence - *unless*
    the caller supplies ``project_sections``, which is the one honest way to fill
    it. Curated design analyses document colour, type, spacing and components;
    they generally do not document how an interface behaves over time, so an
    interaction section can only be grounded in the project's own documented
    behaviour. Those statements are labelled ``[project]`` at insertion time and
    are attributed to the project in :func:`grounded_choices`, never to a
    reference.
    """
    sections: dict[str, list[str]] = {
        "key_hierarchy": [], "interaction_principles": [], "visual_principles": [],
        "content_principles": [], "constraints": [], "reference_findings_adopted": [],
        "findings_rejected": [],
    }
    for principle in principles:
        dimension = str(principle.get("dimension", ""))
        statement = str(principle.get("statement", ""))
        citations = ", ".join(str(row.get("reference_id", "")) for row in principle.get("evidence") or [])
        composed = f"{statement} (observed in {citations}; {principle.get('confidence')})"
        if dimension in ("information-hierarchy", "layout-grid", "density"):
            sections["key_hierarchy"].append(composed)
        elif dimension in ("interaction", "navigation"):
            sections["interaction_principles"].append(composed)
        elif dimension in ("typography", "color-roles", "surface-treatment", "imagery-media"):
            sections["visual_principles"].append(composed)
        elif dimension in ("spacing", "radii", "borders"):
            sections["content_principles"].append(composed)
        elif dimension in ("component-geometry", "depth", "responsive-behavior"):
            sections["reference_findings_adopted"].append(composed)
        elif dimension == "motion":
            sections["interaction_principles"].append(composed)
    for member in members:
        if not isinstance(member, Mapping):
            continue
        if "COUNTER_REFERENCE" not in (member.get("roles") or []):
            continue
        anti_pattern = str(member.get("counter_pattern", "")).strip()
        reference_id = str(member.get("reference_id", ""))
        if not anti_pattern:
            raise ContractError(
                f"counter-reference {reference_id} names no anti-pattern; refusing to compile a direction "
                "from a set that records a rejection without saying what is rejected"
            )
        sections["findings_rejected"].append(
            f"do not adopt {anti_pattern} (counter-reference: {reference_id})"
        )
        sections["constraints"].append(
            f"the design must not drift toward {anti_pattern}"
        )
    for name, statements in (project_sections or {}).items():
        if name not in sections:
            continue
        for statement in statements or ():
            text = str(statement).strip()
            if text:
                sections[name].append(f"[project] {text}")
    return sections


def grounding_problems(record: Mapping) -> list[str]:
    """Structural checks on a compiled direction's grounding block."""
    problems: list[str] = []
    grounding = record.get("ar220_grounding")
    if not isinstance(grounding, Mapping):
        return ["direction carries no AR-220 grounding block"]
    if not str(grounding.get("reference_set_id", "")).strip():
        problems.append("grounding names no reference set")
    principles = grounding.get("principles")
    if not isinstance(principles, list) or not principles:
        problems.append("a grounded direction carries no extracted principle")
    problems.extend(principles_problems(principles or []))
    if not grounding.get("counter_references"):
        problems.append("a grounded direction must record at least one counter-reference")
    treatments = grounding.get("treatments")
    if not isinstance(treatments, list) or not any(
        isinstance(row, Mapping) and row.get("treated") for row in (treatments or [])
    ):
        problems.append("a grounded direction records no BORROW/ADAPT/AVOID treatment")
    if str(grounding.get("status", "")) != "CANDIDATE":
        problems.append("a compiled direction must be a CANDIDATE until G1D approves it")
    return list(dict.fromkeys(problems))


def direction_provenance(state: Mapping, direction_id: str) -> dict:
    """The answer to "why did you choose this design?", assembled from records.

    Every line names the reference ids and project artefacts that support it. A
    line with no support is reported as ``UNGROUNDED`` rather than omitted,
    because a reviewer needs to see the gap as much as the justification.
    """
    from .. import design as design_module

    record = design_module.direction(dict(state), direction_id)
    if record is None:
        return {"direction_id": direction_id, "found": False, "lines": []}
    grounding = record.get("ar220_grounding") if isinstance(record.get("ar220_grounding"), Mapping) else {}
    by_reference: dict[str, list[str]] = {}
    for principle in grounding.get("principles") or []:
        if not isinstance(principle, Mapping):
            continue
        for row in principle.get("evidence") or []:
            if isinstance(row, Mapping):
                by_reference.setdefault(str(row.get("reference_id", "")), []).append(
                    str(principle.get("dimension", ""))
                )
    from .. import references as references_module

    lines: list[dict] = []
    for reference_id in sorted(by_reference):
        reference = references_module.reference(dict(state), reference_id) or {}
        classification = reference.get("classification") if isinstance(reference.get("classification"), Mapping) else {}
        lines.append({
            "reference_id": reference_id,
            "title": str(reference.get("title", "")),
            "source_kind": str(classification.get("source_kind", "")),
            "evidence_level": str(classification.get("evidence_level", "")),
            "source_provider": str(classification.get("source_provider", "")),
            "supports_dimensions": sorted(set(by_reference[reference_id])),
            "limitations": list(reference.get("limitations") or []),
        })
    return {
        "direction_id": direction_id,
        "found": True,
        "status": str(record.get("status", "")),
        "approval_id": str(record.get("approval_id", "")),
        "ready_for_approval": bool(grounding.get("ready_for_approval")),
        "ungrounded_sections": list(grounding.get("ungrounded_sections") or []),
        "lines": lines,
        "project_identity": grounding.get("project_identity") or {},
        "note": (
            "colour, type and spacing come from the project's own tokens where the project's identity "
            "covers them; these lines list the references that informed hierarchy, layout, interaction and "
            "component choices, not borrowed brand values"
        ),
    }


__all__ = [
    "GENERIC_GROUNDING_BLOCKERS",
    "MIN_REFERENCES_FOR_SUPPORTED",
    "PRINCIPLE_CONFIDENCE",
    "compile_candidate_direction",
    "direction_provenance",
    "extract_principles",
    "grounded_choices",
    "grounding_problems",
    "principle_problems",
    "principles_problems",
    "treatments_for_set",
]