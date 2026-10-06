"""Design Specificity Grammar: methodology, not a house style (AR-222D).

AR-220 proved a direction can cite its evidence. It did not make the direction
*specific*, and the gap between those two is where every generated design becomes
indistinguishable from every other generated design. A direction grounded in six real
references can still be "clean, modern dashboard with card grid" — cited, actionable,
and worthless.

So this module encodes **how to decide**, never **what to look like**. It contributes
no colour, no typeface, no spacing scale and no component. Ariadne has a house method,
not a house style, and the difference is enforceable: nothing here can be rendered.

Twelve principles, in the order they constrain a decision:

1. :data:`PRINCIPLE_ORDER`. Concept before aesthetic adjective -- "editorial" is a
   conclusion, not a starting point.
2. content before layout. A layout committed before its content is known is a layout
   for content nobody has.
3. divergence before convergence. Explore at least three materially different
   candidates; otherwise the first idea is the only one ever considered.
4. roles before literal values. Decide *what a colour is for*, then choose the value.
5. category defaults must be consciously chosen -- recorded, with a reason, rather than
   arrived at by not deciding.
6. every direction knows its own failure mode: the local attractor toward mediocrity
   it collapses into when executed lazily.
7. specificity of the richness source. A direction with no named source of visual
   richness will substitute generic cards, gradients and decoration.
8. motion requires intent. Every animation maps to a named intent or it is suspect.
9. project identity outranks external inspiration.
10. render before judging. A direction has not been evaluated until it has been
    rendered and looked at.
11. fresh-eyes critique: the reviewer sees the render and the requirements, never the
    implementer's rationale.
12. restraint is a tool, not the goal. Austere output is as much a house style as
    maximal output, and the grammar refuses to prefer either.

The last principle is the one that is easiest to get wrong in either direction, so it
is represented as data (:data:`ANTI_OVER_CORRECTION_AXES`) rather than as an
instruction, and :func:`convergence_problems` will refuse a direction set in which
every candidate collapsed toward the same attractor.
"""

from __future__ import annotations

from typing import Mapping, Sequence

from ...contracts import ContractError
from . import platform

PRINCIPLE_ORDER = (
    "concept_before_aesthetic_adjective",
    "content_before_layout",
    "divergence_before_convergence",
    "roles_before_literal_values",
    "category_defaults_consciously_chosen",
    "direction_knows_its_own_failure_mode",
    "richness_source_is_specific",
    "motion_requires_intent",
    "project_identity_outranks_external_inspiration",
    "render_before_judging",
    "fresh_eyes_critique",
    "restraint_is_a_tool_not_a_goal",
)
"""The order decisions are made in, and the completeness check for the grammar itself."""

GRAMMAR_PRINCIPLES = {
    "concept_before_aesthetic_adjective": (
        "an aesthetic adjective is a conclusion. Name the concrete thing the product is "
        "before naming how it should look, because 'editorial' constrains nothing until "
        "something has decided what the product is about"
    ),
    "content_before_layout": (
        "establish representative real content -- headings, actions, row counts, name "
        "lengths, numeric ranges, and the empty, loading and error states -- before "
        "committing a major layout. A layout chosen before its content is a layout for "
        "content nobody has"
    ),
    "divergence_before_convergence": (
        "produce at least three materially different candidates before selecting one. "
        "Convergence before divergence is how a first idea becomes a house style"
    ),
    "roles_before_literal_values": (
        "decide what a value is for before choosing it. 'Accent means the single "
        "actionable emphasis on this surface' is a decision; '#6d28d9' is not"
    ),
    "category_defaults_consciously_chosen": (
        "the defaults a category makes available are chosen or recorded as unexamined. "
        "Neither outcome is a failure; a default nobody considered is"
    ),
    "direction_knows_its_own_failure_mode": (
        "every direction names the cliché it collapses into when executed lazily. A "
        "direction that cannot name its own attractor has not been examined closely "
        "enough to have one"
    ),
    "richness_source_is_specific": (
        "name where visual richness comes from -- real content, typography, data "
        "visualisation, photography, material, motion, density. A direction with no "
        "named source compensates with generic cards, gradients and decoration"
    ),
    "motion_requires_intent": (
        "every animation maps to spatial continuity, state confirmation, affordance, "
        "direct manipulation or reward. Motion with no intent is suspect rather than "
        "automatically invalid"
    ),
    "project_identity_outranks_external_inspiration": (
        "when a reference and the project's own identity disagree, the project wins and "
        "the disagreement is recorded"
    ),
    "render_before_judging": (
        "a direction has not been evaluated until it has been rendered and looked at. "
        "Judging from a specification reviews the specification"
    ),
    "fresh_eyes_critique": (
        "the reviewer receives the render and the requirements. It never receives the "
        "implementer's rationale, and continuity of reviewer does not license that"
    ),
    "restraint_is_a_tool_not_a_goal": (
        "specificity is the goal. Minimal output is as much a house style as maximal "
        "output, and anti-default analysis must not become a demand for austerity"
    ),
}

COLOUR_ROLES = (
    "background",
    "surface",
    "surface_raised",
    "primary_content",
    "secondary_content",
    "separator",
    "accent_purpose",
    "semantic_positive",
    "semantic_caution",
    "semantic_critical",
)
"""What colour is *for*. A role is a decision; the value that fills it is a later step.

Deliberately not a token count. Nine roles is what this vocabulary happens to need; a
product with three surfaces does not become wrong, and a product with thirty states
does not become right.
"""

TYPE_ROLES = (
    "display",
    "navigation",
    "body",
    "metadata",
    "data_metric",
)
"""What type is *for*. Data and metadata are separated because a telemetry dashboard
that renders its numbers in body type has confused reading with measurement."""

MOTION_INTENTS = (
    "SPATIAL_CONTINUITY",
    "STATE_CONFIRMATION",
    "AFFORDANCE",
    "DIRECT_MANIPULATION",
    "REWARD",
)
"""The only intents motion may serve. There is deliberately no ``PREMIUM_ANIMATION``.

An animation that maps to none of these is reported as suspect -- not removed. Some
motion exists to establish that an object has physical presence, which is
``SPATIAL_CONTINUITY`` wearing a costume.
"""

INTENT_EVIDENCE = {
    "SPATIAL_CONTINUITY": (
        "the element appears from, or moves to, somewhere it previously occupied"
    ),
    "STATE_CONFIRMATION": (
        "the interface changes because something changed, and the change is the "
        "confirmation"
    ),
    "AFFORDANCE": (
        "the movement tells the user this thing can be touched, dragged or revealed"
    ),
    "DIRECT_MANIPULATION": (
        "the object tracks the pointer or finger continuously while it is held"
    ),
    "REWARD": (
        "something was completed, and the interface acknowledges the completion"
    ),
}
"""What has to be true for a motion intent to be claimed rather than asserted."""

RICHNESS_SOURCES = (
    "REAL_CONTENT",
    "TYPOGRAPHY",
    "DATA_VISUALISATION",
    "PHOTOGRAPHY",
    "ILLUSTRATION",
    "MATERIAL",
    "COLOUR",
    "MOTION",
    "SPATIAL_3D",
    "DIAGRAMMING",
    "MAPS",
    "PHYSICAL_OBJECT_METAPHOR",
    "CONTENT_DENSITY",
)
"""Where visual richness may come from.

``TYPOGRAPHY`` and ``CONTENT_DENSITY`` are first-class because a restrained product
should be able to say "the type is the interesting thing" or "the volume of real
content is the interesting thing" and have that count as a real answer rather than as
an absence of one.
"""

RESTRAINT_RICHNESS_SOURCES = ("REAL_CONTENT", "TYPOGRAPHY", "CONTENT_DENSITY")
"""Sources that legitimately produce an austere result.

Named because "no richness source was chosen" and "richness was chosen to be the
content itself" must be distinguishable, and only one of them is a hole.
"""

ROLE_BEFORE_VALUE = "meaning -> role -> implementation value"
"""The generalisation of every colour and type decision in the system.

Read as an obligation on process: the literal value is not permitted to be the thing
that was decided first, because then it was decided by nobody.
"""

ANTI_OVER_CORRECTION_AXES = (
    "density",
    "colour_variety",
    "surface_treatment",
    "typographic_voice",
    "structural_rigidity",
    "decoration_level",
)
"""Axes along which Ariadne could develop its own repeated style.

The failure this guards against is specific and worth naming: responding to generic AI
design by producing generic Ariadne design. "Sparse, monochrome, one accent, dense
technical tooling, editorial, Boreal" is not a diverse set of directions, it is one
direction six times, and a system that only knows how to avoid a cliché by picking its
opposite has simply traded one house style for another.
"""

ARIADNE_ATTRACTORS = (
    "receipt",
    "ledger",
    "ticket",
    "terminal",
    "control_panel",
    "print_shop",
)
"""Where this system's own competence pulls every concept.

Ariadne is unusually good at printed-matter metaphors, because a receipt is a real
artifact with real hierarchy, real density and real alignment rules -- which is exactly
why it must be named. Six concepts out of nine arriving as "technical document" means
the generator has found its own accent colour and started using it.
"""


def grammar() -> dict:
    """The methodology, as data, with its decision order intact."""
    return {
        "grammar_id": "design-specificity-grammar-1",
        "principles": [
            {"principle": key, "index": index, "statement": GRAMMAR_PRINCIPLES[key]}
            for index, key in enumerate(PRINCIPLE_ORDER, start=1)
        ],
        "roles": {
            "colour": list(COLOUR_ROLES),
            "type": list(TYPE_ROLES),
            "motion": list(MOTION_INTENTS),
        },
        "intent_evidence": {key: INTENT_EVIDENCE[key] for key in MOTION_INTENTS},
        "richness_sources": list(RICHNESS_SOURCES),
        "restraint_richness_sources": list(RESTRAINT_RICHNESS_SOURCES),
        "role_before_value": ROLE_BEFORE_VALUE,
        "anti_over_correction_axes": list(ANTI_OVER_CORRECTION_AXES),
        "self_attractors": list(ARIADNE_ATTRACTORS),
        "platform_boundary": platform.universal_defaults(),
        "house_style": None,
        "house_method": (
            "decide concept, then content, then roles, then values; name the failure "
            "mode; render before judging; let the human decide what the product means"
        ),
    }


def role_problems(role_kind: str, role: str) -> list[str]:
    """Validate one declared role against the vocabulary for its kind."""
    vocabularies = {"colour": COLOUR_ROLES, "type": TYPE_ROLES, "motion": MOTION_INTENTS}
    allowed = vocabularies.get(str(role_kind))
    if allowed is None:
        return [f"unknown role kind: {role_kind!r} (known: {', '.join(sorted(vocabularies))})"]
    if str(role) not in allowed:
        return [f"unknown {role_kind} role: {role!r}"]
    return []


def role_bindings(bindings: Sequence[Mapping]) -> list[dict]:
    """Validate role -> value bindings, in the grammar's order rather than the caller's.

    A binding with a role but no value is reported. So is one whose ``role`` is a
    literal value rather than a role -- the whole point of the role step is that the
    meaning is chosen first, and a binding that jumps straight to ``#0f172a`` has
    skipped the decision it was supposed to record.
    """
    problems: list[str] = []
    rows: list[dict] = []
    for binding in bindings or ():
        if not isinstance(binding, Mapping):
            problems.append("a role binding must be a mapping")
            continue
        kind = str(binding.get("role_kind", ""))
        role = str(binding.get("role", ""))
        value = str(binding.get("value", "")).strip()
        rows.append({
            "role_kind": kind,
            "role": role,
            "value": value,
            "meaning": str(binding.get("meaning", "")).strip(),
        })
        problems.extend(f"role binding {role!r}: {item}" for item in role_problems(kind, role))
        if not value:
            problems.append(f"role binding {role!r} records a role but no implementation value")
    order = {"colour": COLOUR_ROLES, "type": TYPE_ROLES, "motion": MOTION_INTENTS}
    rows.sort(key=lambda row: (
        list(order).index(row["role_kind"]) if row["role_kind"] in order else 99,
        order.get(row["role_kind"], ()).index(row["role"]) if row["role"] in order.get(row["role_kind"], ()) else 99,
    ))
    return rows, problems


def literal_value_first(bindings: Sequence[Mapping]) -> list[str]:
    """Bindings that jumped to a literal without ever naming the role's meaning.

    Detected rather than forbidden: a binding with no ``meaning`` is a warning about
    process, not proof that the value is wrong.
    """
    offenders: list[str] = []
    for binding in bindings or ():
        if not isinstance(binding, Mapping):
            continue
        if not str(binding.get("meaning", "")).strip() and str(binding.get("value", "")).strip():
            offenders.append(
                f"{binding.get('role_kind', '?')}/{binding.get('role', '?')}: the value was "
                "chosen before the role's meaning was written down"
            )
    return offenders


def motion_intent_problems(motions: Sequence[Mapping]) -> list[str]:
    """Every declared motion needs a supported intent and the evidence for it."""
    problems: list[str] = []
    for motion in motions or ():
        if not isinstance(motion, Mapping):
            problems.append("a motion entry must be a mapping")
            continue
        intent = str(motion.get("intent", "")).strip()
        if intent not in MOTION_INTENTS:
            problems.append(
                f"motion {motion.get('motion_id', '?')!r} declares intent {intent or 'none'!r}; "
                f"the vocabulary is {', '.join(MOTION_INTENTS)}. Intentless motion is suspect, "
                "not automatically invalid"
            )
            continue
        evidence = str(motion.get("evidence", "")).strip()
        if not evidence:
            problems.append(
                f"motion {motion.get('motion_id', '?')!r} claims {intent} but records no evidence "
                f"that it is true; the test is: {INTENT_EVIDENCE[intent]}"
            )
    return problems


def richness_problems(direction: Mapping) -> list[str]:
    """A major direction must name where its richness comes from."""
    problems: list[str] = []
    source = str(direction.get("richness_source", "")).strip()
    if not source:
        problems.append(
            "this direction names no richness source. Without one it will substitute generic "
            "cards, gradients and decoration; if the intent is restraint, name the content or the "
            "typography as the source"
        )
    elif source not in RICHNESS_SOURCES:
        problems.append(
            f"unknown richness source {source!r}; known: {', '.join(RICHNESS_SOURCES)}"
        )
    return problems


def assert_platform_neutral(*texts: str, label: str = "direction") -> None:
    """Refuse a universal record citing a platform rule. Delegates to :mod:`platform`."""
    platform.assert_no_leak(*texts, label=label)


def required_principles() -> tuple[str, ...]:
    return tuple(PRINCIPLE_ORDER)


def grammar_problems(record: Mapping) -> list[str]:
    """A stored grammar copy must be the whole grammar, in order, with no house style."""
    problems: list[str] = []
    if str(record.get("grammar_id", "")) != "design-specificity-grammar-1":
        problems.append("stored grammar is not the AR-222D grammar")
    principles = record.get("principles")
    if not isinstance(principles, list) or len(principles) != len(PRINCIPLE_ORDER):
        problems.append(
            f"the grammar must record all {len(PRINCIPLE_ORDER)} principles, "
            f"not {len(principles) if isinstance(principles, list) else 0}"
        )
    else:
        recorded = tuple(str(row.get("principle", "")) for row in principles if isinstance(row, Mapping))
        if recorded != PRINCIPLE_ORDER:
            missing = [item for item in PRINCIPLE_ORDER if item not in recorded]
            problems.append(
                "the grammar's principles do not match the methodology it claims to encode"
                + (f"; missing {missing}" if missing else "")
            )
    if record.get("house_style") is not None:
        problems.append(
            "a house style has been attached to the grammar. Ariadne has a house method, not a "
            "house style, and an aesthetic encoded here would be inherited by every future run"
        )
    platform.assert_no_leak(
        *(str(row.get("statement", "")) for row in (principles or []) if isinstance(row, Mapping)),
        label="grammar",
    )
    return problems


__all__ = [
    "ANTI_OVER_CORRECTION_AXES",
    "ARIADNE_ATTRACTORS",
    "COLOUR_ROLES",
    "GRAMMAR_PRINCIPLES",
    "INTENT_EVIDENCE",
    "MOTION_INTENTS",
    "PRINCIPLE_ORDER",
    "RESTRAINT_RICHNESS_SOURCES",
    "RICHNESS_SOURCES",
    "ROLE_BEFORE_VALUE",
    "TYPE_ROLES",
    "assert_platform_neutral",
    "grammar",
    "grammar_problems",
    "literal_value_first",
    "motion_intent_problems",
    "required_principles",
    "richness_problems",
    "role_bindings",
    "role_problems",
]