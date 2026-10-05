"""Concept-first exploration and material divergence (AR-222D).

The reflex this replaces is: pick an aesthetic adjective, then build the thing.

> "It's an F1 dashboard." → *dark, neon, technical* → done.

That ordering is the single largest source of interchangeable output. The adjective
arrives first, and once chosen it constrains everything downstream while answering
nothing about what an F1 dashboard is *for*. So the concept comes first: a concrete
thing the product genuinely is, drawn from a family of source families, from which
the aesthetic follows rather than precedes.

Two failure modes make this a real module rather than a slogan:

**Collapse.** Concepts gravitate toward whatever this system is best at. Receipts,
ledgers, tickets, terminals, control panels, print shops. Those are strong metaphors
*because* Ariadne keeps reaching for them, which is exactly why reaching is the risk.
:func:`convergence_risk` measures the collapse.

**Fake divergence.** Three options that differ only in colour are one option offered
three times, and presenting them to a user as a real choice is worse than presenting
one. :func:`material_divergence` requires candidates to differ on *substance* --
surface character, hierarchy model, type character, richness source, interaction
character, layout structure, motion language -- and :func:`divergence_problems` refuses
a set that only varies a palette.

There is no fixed candidate count in the grammar, only a floor of three, because two
candidates is a choice already made.
"""

from __future__ import annotations

from typing import Mapping, Sequence

from ...contracts import ContractError
from . import content as content_module
from . import grammar as grammar_module

CONCEPT_FAMILIES = (
    "objects_materials",
    "places_environments",
    "media",
    "nature",
    "physical_systems",
    "instruments",
    "printed_matter",
    "culture_activity",
    "domain_native_artifacts",
)
"""Families a concept may be drawn from.

Illustrative rather than exhaustive, and deliberately not a taxonomy. The purpose is to
prevent a generator from reaching for one family every time, not to classify every
object in the world. :data:`grammar_module.ARIADNE_ATTRACTORS` covers the specific
failure: printed-matter and physical-system metaphors are *in* these families, so
listing them is not sufficient protection on its own.
"""

DIVERGENCE_AXES = (
    "ground_surface_character",
    "hierarchy_model",
    "type_character",
    "richness_source",
    "interaction_character",
    "layout_structure",
    "motion_language",
)
"""The axes on which candidates must differ materially.

Colour is absent by design. Colour is the axis a generator reaches for first because it
is the easiest to vary and the least meaningful; allowing it to count as divergence is
how three identical options get presented as a decision.

``hierarchy_model`` and ``layout_structure`` are separate axes because a layout can
change shape while the hierarchy stays identical -- the classic "same dashboard, three
arrangements".
"""

MIN_CANDIDATES = 3
"""The floor. Two candidates is a choice already made."""

MIN_DIVERGENT_AXES = 3
"""How many substantive axes must differ across the candidate set as a whole.

Three, rather than one per candidate, so that three candidates differing from each
other on one axis each still fails: that is three variations of one direction.
"""

MATERIAL_DESIGN_CATEGORIES = (
    "dense_operational",
    "reading_oriented",
    "visual_led",
    "content_led",
    "instrument_like",
    "workspace_tool",
    "narrative",
    "transient",
)
"""Substance labels that actually describe how a product behaves.

These exist so ``hierarchy_model`` can be compared between candidates rather than
prose-compared. Two candidates that both say "dense operational" are the same
direction with different colours, whatever their concepts are called.
"""

CONCEPT_MARKERS = (
    # Ariadne's own attractors, checked as words so the collapse is measurable.
    "receipt",
    "ledger",
    "ticket",
    "terminal",
    "control panel",
    "control-panel",
    "console",
    "telemetry console",
    "print shop",
    "paper trail",
)
"""Words that indicate this system reached for its own accent colour.

Not banned. A race telemetry console may genuinely be the right answer for a timing
engineer. What is refused is *six of nine* concepts arriving as consoles with no one
having asked whether the product is a console.
"""

PERFECT_DEMO_DATA_MARKERS = (
    "perfectly balanced",
    "100% success",
    "all systems nominal",
    "zero errors",
)


def concept(
    *,
    concept_id: str,
    name: str,
    statement: str,
    family: str,
    source_thing: str,
    hierarchy_model: str,
    ground_surface_character: str,
    type_character: str,
    interaction_character: str,
    layout_structure: str,
    motion_language: str,
    richness_source: str,
    content_model: Mapping | None = None,
    domain: str = "",
    notes: str = "",
) -> dict:
    """One concept candidate, described so that divergence is measurable."""
    record = {
        "concept_id": str(concept_id),
        "name": str(name).strip(),
        "concept": str(statement).strip(),
        "family": str(family),
        "source_thing": str(source_thing).strip(),
        "hierarchy_model": str(hierarchy_model),
        "ground_surface_character": str(ground_surface_character),
        "type_character": str(type_character),
        "interaction_character": str(interaction_character),
        "layout_structure": str(layout_structure),
        "motion_language": str(motion_language),
        "richness_source": str(richness_source),
        "content_model": dict(content_model) if isinstance(content_model, Mapping) else {},
        "domain": str(domain),
        "notes": str(notes),
    }
    problems = concept_problems(record)
    if problems:
        raise ContractError("concept candidate is not usable: " + "; ".join(problems))
    return record


def concept_problems(record: Mapping) -> list[str]:
    """A concept must name a concrete thing, not an adjective."""
    problems: list[str] = []
    if not str(record.get("name", "")).strip():
        problems.append("a concept candidate is named")
    statement = str(record.get("concept", "")).strip()
    if not statement:
        problems.append("a concept candidate states the idea in one sentence a human can approve")
    if str(record.get("family", "")) not in CONCEPT_FAMILIES:
        problems.append(
            f"concept family {record.get('family', '')!r} is not one of the known families "
            f"({', '.join(CONCEPT_FAMILIES)})"
        )
    source_thing = str(record.get("source_thing", "")).strip()
    if not source_thing:
        problems.append(
            "a concept names the concrete thing the product is being understood as. 'modern' "
            "is not a thing; 'a pit wall timing screen' is"
        )
    if len(source_thing.split()) <= 2 and source_thing.lower() in (
        "minimal", "modern", "clean", "sleek", "premium", "editorial", "bold",
    ):
        problems.append(
            f"the concept's source thing is the aesthetic adjective {source_thing!r}, which is a "
            "conclusion rather than a starting point (concept before aesthetic adjective)"
        )
    for axis in DIVERGENCE_AXES:
        if not str(record.get(axis, "")).strip():
            problems.append(f"concept records its {axis.replace('_', ' ')}")
    if str(record.get("hierarchy_model", "")) not in MATERIAL_DESIGN_CATEGORIES:
        problems.append(
            f"hierarchy model {record.get('hierarchy_model', '')!r} is not a material design "
            f"category ({', '.join(MATERIAL_DESIGN_CATEGORIES)}); a free-text hierarchy cannot be "
            "compared against another candidate's"
        )
    problems.extend(grammar_module.richness_problems(record))
    model = record.get("content_model")
    if isinstance(model, Mapping) and model:
        problems.extend(content_module.content_model_problems(model))
    return list(dict.fromkeys(problems))


def _axis_signature(candidate: Mapping, axis: str) -> str:
    if axis == "hierarchy_model":
        return str(candidate.get("hierarchy_model", "")).strip().lower()
    if axis == "richness_source":
        return str(candidate.get("richness_source", "")).strip().upper()
    return " ".join(str(candidate.get(axis, "")).lower().split())


def material_divergence(candidates: Sequence[Mapping]) -> dict:
    """Which axes actually differ, and by how much.

    Reported as data because the interesting output is *which* axes failed, not a
    verdict. A candidate set that differs on surface and type but shares a hierarchy
    model has a specific, fixable problem.
    """
    rows: list[dict] = []
    for axis in DIVERGENCE_AXES:
        signatures = [_axis_signature(candidate, axis) for candidate in candidates]
        distinct = sorted({signature for signature in signatures if signature})
        rows.append({
            "axis": axis,
            "distinct_values": len(distinct),
            "values": distinct[: len(candidates) + 1],
            "divergent": len(distinct) >= 2,
        })
    divergent = [row["axis"] for row in rows if row["divergent"]]
    # Colour is never counted, and is reported separately so a generator that only
    # varied palette can be told exactly what it did.
    palette_only = (
        len(divergent) == 0
        and len({str(candidate.get("name", "")) for candidate in candidates}) > 1
    )
    return {
        "axes": rows,
        "divergent_axes": divergent,
        "divergent_count": len(divergent),
        "palette_only": palette_only,
        "basis": (
            "colour is excluded from the divergence axes on purpose: three options differing only "
            "in hue are one option presented three times"
        ),
    }


def divergence_problems(candidates: Sequence[Mapping]) -> list[str]:
    """Whether a candidate set satisfies divergence before convergence."""
    problems: list[str] = []
    rows = [row for row in (candidates or ()) if isinstance(row, Mapping)]
    if len(rows) < MIN_CANDIDATES:
        problems.append(
            f"exploration produced {len(rows)} materially different candidate(s); the floor is "
            f"{MIN_CANDIDATES}. Two candidates is a choice already made"
        )
        return problems
    report = material_divergence(rows)
    if report["palette_only"]:
        problems.append(
            "the candidates differ only in colour. Palette is not a divergence axis; produce "
            "candidates that differ in hierarchy model, layout structure, type character or "
            "richness source"
        )
    if report["divergent_count"] < MIN_DIVERGENT_AXES:
        problems.append(
            f"candidates differ on {report['divergent_count']} substantive axis/axes "
            f"({', '.join(report['divergent_axes']) or 'none'}); at least {MIN_DIVERGENT_AXES} must "
            "differ for the set to be a real choice rather than three variations"
        )
    identities = {str(row.get("concept_id", "")) for row in rows}
    if len(identities) < len(rows):
        problems.append("candidate concept ids must be distinct")
    return problems


def convergence_risk(candidates: Sequence[Mapping], *, threshold: float = 0.5) -> dict:
    """Whether the candidate set is collapsing toward Ariadne's own attractors.

    This is the anti-over-correction check. A system that responds to generic AI design
    by emitting one generic *Ariadne* design has not been fixed; it has swapped which
    cliché it produces. The measurement is deliberately about the system's own pull,
    not about a list of forbidden aesthetics.
    """
    rows = [row for row in (candidates or ()) if isinstance(row, Mapping)]
    if not rows:
        return {"risk": "UNKNOWN", "share": 0.0, "markers": [], "total": 0, "note": "no candidates"}
    hits: list[dict] = []
    for candidate in rows:
        text = " ".join(
            " ".join(str(candidate.get(key, "")).lower().split())
            for key in ("name", "concept", "source_thing", "interaction_character", "motion_language")
        ).replace("_", " ")
        markers = sorted({marker for marker in CONCEPT_MARKERS if marker in text})
        if markers:
            hits.append({"concept_id": str(candidate.get("concept_id", "")), "markers": markers})
    share = len(hits) / len(rows)
    return {
        "risk": "CONVERGING" if share >= threshold else "DIVERSE",
        "share": round(share, 3),
        "threshold": threshold,
        "markers": hits,
        "total": len(rows),
        "note": (
            "the attractors named here are this system's own competence, not a list of banned "
            "aesthetics. A single console concept can be right; a set that is mostly consoles means "
            "the generator found its own accent colour"
        ),
    }


def convergence_problems(candidates: Sequence[Mapping], *, threshold: float = 0.5) -> list[str]:
    """Refuse a candidate set that is one direction wearing several names."""
    report = convergence_risk(candidates, threshold=threshold)
    if report["risk"] != "CONVERGING":
        return []
    return [
        f"{report['share']:.0%} of the candidates converge on this system's own attractors "
        f"({', '.join(sorted({marker for row in report['markers'] for marker in row['markers']}))}). "
        "Anti-over-correction: responding to generic AI design by producing generic Ariadne design is "
        "not a fix. Diverge the concept families before converging on one direction."
    ]


def axis_spread_problems(candidates: Sequence[Mapping]) -> list[str]:
    """Convergence on *any* axis, including Ariadne's aesthetic habits.

    :func:`convergence_problems` only knows about the word-level attractors. This also
    catches a set that is all editorial, all monochrome or all sparse without any of
    those words appearing.
    """
    rows = [row for row in (candidates or ()) if isinstance(row, Mapping)]
    if len(rows) < MIN_CANDIDATES:
        return []
    problems: list[str] = []
    report = material_divergence(rows)
    for axis in DIVERGENCE_AXES:
        row = next((item for item in report["axes"] if item["axis"] == axis), None)
        if row is None:
            continue
        if row["distinct_values"] == 1 and row["distinct_values"] > 0:
            shared = row["values"][0] if row["values"] else ""
            problems.append(
                f"every candidate shares the same {axis.replace('_', ' ')} ({shared!r}). "
                + (
                    "That is the shape of a house style forming: candidates that agree on their "
                    "ground character are the same direction with different names."
                    if axis in ("hierarchy_model", "layout_structure")
                    else "Divergence here is what makes the choice real."
                )
            )
    return problems


def exploration_problems(candidates: Sequence[Mapping], *, threshold: float = 0.5) -> list[str]:
    """Every reason a candidate set is not yet a real set of options."""
    problems: list[str] = []
    rows = [row for row in (candidates or ()) if isinstance(row, Mapping)]
    for row in rows:
        problems.extend(f"candidate {row.get('concept_id', '?')}: {item}" for item in concept_problems(row))
    problems.extend(divergence_problems(rows))
    problems.extend(convergence_problems(rows, threshold=threshold))
    problems.extend(axis_spread_problems(rows))
    families = {str(row.get("family", "")) for row in rows}
    if len(rows) >= MIN_CANDIDATES and len(families) < 2:
        problems.append(
            f"all {len(rows)} candidates come from the same concept family ({', '.join(families)}). "
            "Concept-first exploration means diverging the families, not the adjectives within one"
        )
    return list(dict.fromkeys(problems))


def candidate_evaluation(candidates: Sequence[Mapping], *, evidence: Mapping | None = None) -> list[dict]:
    """Internal evaluation of each candidate, on named axes, with no aggregate score.

    Deliberately a table and not a number. A composite "design quality: 92%" is
    uninterpretable, invites gaming, and hides exactly the trade-off a human needs to
    see: two candidates can each be strong on different axes, and collapsing them to one
    number destroys the information the choice depends on.
    """
    rows: list[dict] = []
    supplied = evidence if isinstance(evidence, Mapping) else {}
    for candidate in candidates or ():
        if not isinstance(candidate, Mapping):
            continue
        concept_id = str(candidate.get("concept_id", ""))
        notes = supplied.get(concept_id) if isinstance(supplied.get(concept_id), Mapping) else {}
        rows.append({
            "concept_id": concept_id,
            "name": str(candidate.get("name", "")),
            "assessments": {
                "product_fit": str(notes.get("product_fit", "not-assessed")),
                "project_identity": str(notes.get("project_identity", "not-assessed")),
                "requirement_coverage": str(notes.get("requirement_coverage", "not-assessed")),
                "specificity": str(notes.get("specificity", "not-assessed")),
                "reference_support": str(notes.get("reference_support", "not-assessed")),
                "category_default_dependence": str(notes.get("category_default_dependence", "not-assessed")),
                "implementation_feasibility": str(notes.get("implementation_feasibility", "not-assessed")),
                "accessibility_constraints": str(notes.get("accessibility_constraints", "not-assessed")),
                "coherence": str(notes.get("coherence", "not-assessed")),
            },
            "aggregate_score": None,
            "score_note": (
                "no global numerical design score. Value and friction are human-judged and are not "
                "aggregated; a composite number hides the trade-off the decision turns on"
            ),
        })
    return rows


def recommend(candidates: Sequence[Mapping], *, evaluation: Sequence[Mapping] | None = None,
              recommendation_id: str = "") -> dict:
    """One recommended direction, with the alternatives kept and marked secondary.

    The recommendation is derived from recorded assessments, never from a score. When
    no assessment is recorded the recommendation is honestly ``UNASSESSED`` rather than
    defaulting to the first candidate, which would silently turn ordering into
    authority.
    """
    rows = [row for row in (candidates or ()) if isinstance(row, Mapping)]
    if not rows:
        raise ContractError("a recommendation needs at least one candidate")
    judged = {
        str(row.get("concept_id", "")): row
        for row in (evaluation or ())
        if isinstance(row, Mapping)
    }
    ranked: list[tuple[int, Mapping]] = []
    unassessed: list[str] = []
    for candidate in rows:
        assessment = judged.get(str(candidate.get("concept_id", "")))
        if assessment is None:
            unassessed.append(str(candidate.get("concept_id", "")))
            continue
        values = assessment.get("assessments") if isinstance(assessment.get("assessments"), Mapping) else {}
        verdicts = [
            str(value) for key, value in values.items()
            if key != "category_default_dependence" and str(value) != "not-assessed"
        ]
        if not verdicts:
            unassessed.append(str(candidate.get("concept_id", "")))
            continue
        supported = sum(1 for value in verdicts if value.upper() in ("STRONG", "SUPPORTED", "CLEAR"))
        weak = sum(1 for value in verdicts if value.upper() in ("WEAK", "UNSUPPORTED", "DOUBTFUL"))
        ranked.append((supported - weak, candidate))
    if not ranked:
        return {
            "recommendation_id": str(recommendation_id),
            "recommended_concept_id": "",
            "status": "UNASSESSED",
            "reason": (
                "no candidate was internally evaluated, so no recommendation can be made. Choosing "
                "the first one would make list order do the work of judgement"
            ),
            "alternatives": [str(row.get("concept_id", "")) for row in rows],
            "unassessed": unassessed,
            "alternatives_role": "secondary",
        }
    ranked.sort(key=lambda item: (-item[0], str(item[1].get("concept_id", ""))))
    best_score, best = ranked[0]
    tied = [candidate for score, candidate in ranked if score == best_score]
    return {
        "recommendation_id": str(recommendation_id),
        "recommended_concept_id": str(best.get("concept_id", "")),
        "status": "UNASSESSED" if best_score == 0 else "RECOMMENDED",
        "reason": (
            "the strongest of the internally assessed candidates on the recorded axes"
            if best_score > 0 else
            "no candidate scored clearly above the others; the recommendation is provisional and the "
            "human decides"
        ),
        "tied_with": sorted(str(row.get("concept_id", "")) for row in tied) if len(tied) > 1 else [],
        "alternatives": [
            str(candidate.get("concept_id", "")) for _score, candidate in ranked[1:]
        ],
        "alternatives_role": "secondary",
        "user_flow": "recommendation -> approve / adjust / show alternatives",
        "never": "the user is never required to choose among every internal experiment",
    }


__all__ = [
    "CONCEPT_FAMILIES",
    "CONCEPT_MARKERS",
    "DIVERGENCE_AXES",
    "MATERIAL_DESIGN_CATEGORIES",
    "MIN_CANDIDATES",
    "MIN_DIVERGENT_AXES",
    "axis_spread_problems",
    "candidate_evaluation",
    "concept",
    "concept_problems",
    "convergence_problems",
    "convergence_risk",
    "divergence_problems",
    "exploration_problems",
    "material_divergence",
    "recommend",
]