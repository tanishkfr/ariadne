"""``ReferenceSet``: a deliberate set of design evidence (AR-220).

A reference set is not a folder of inspiration. Its purpose is stated in one
line and enforced in the validator:

> assemble enough evidence to support a design direction.

Three things make it that, rather than a bookmark list:

**Roles.** Every member says what job it is doing. ``Linear`` as hierarchy
evidence and ``shadcn resizable-panel`` as implementation evidence are different
claims about different things, and the set refuses to hold them as if they were
interchangeable.

**Counter-references.** A set may record what the design must *not* become, and a
counter-reference must name the anti-pattern. Disliking something is not a
counter-reference; recording the specific failure mode that a reference set of dark
glass dashboards represents is. This is the mechanism that makes
"precise and dense, not a generic AI dashboard" an executable statement rather
than a preference.

**Sufficiency, not vibes.** The set carries a deterministic coverage verdict, a
deterministic diversity verdict and a budget verdict. ``UNKNOWN`` is a valid
answer for all three, and reporting ``UNKNOWN`` is preferred to reporting a
confident verdict the evidence does not support.

Nothing here reaches out to the network or widens the set on its own. There is no
"search until satisfied" loop, because that loop is how a research budget stops
existing; a set that is insufficient says so and the caller decides whether to
spend more.
"""

from __future__ import annotations

import re
from typing import Mapping, Sequence

from .. import contracts
from ..contracts import ContractError
from . import safety

ROLE_REQUIREMENTS: dict[str, tuple[str, ...]] = {
    "PRIMARY_DIRECTION": ("source_kind", "observed_patterns"),
    "INTERACTION_REFERENCE": ("source_kind",),
    "LAYOUT_REFERENCE": ("source_kind",),
    "TYPOGRAPHY_REFERENCE": ("source_kind",),
    "COMPONENT_REFERENCE": ("source_kind",),
    "IMPLEMENTATION_REFERENCE": ("source_kind",),
    "COUNTER_REFERENCE": ("source_kind", "counter_pattern"),
}
"""What each role requires of a member before the set will accept it.

Only two requirements are structural: a member must be classified, and a
counter-reference must name an anti-pattern. Nothing here demands a particular
*kind* of source, because relevance beats provenance in this system - a highly
relevant curated analysis beats an unrelated first-party system, and the set
cannot encode that preference without becoming a ranking nobody can audit.
"""

DIVERSITY_AXES = (
    "industry", "surface", "source-kind", "light-dark", "emphasis", "role",
)
"""The axes a reference set's diversity is measured across.

Six axes, all derived from the classification and observation record - never from
a brand name or an aesthetic judgement. If a future source does not classify
itself on an axis, that axis reports ``UNKNOWN`` for that member, which lowers
confidence in the verdict rather than silently counting as diversity.
"""

DIVERSITY_VOTING_AXES = ("industry", "light-dark", "emphasis", "role")
"""The axes that decide the verdict.

Split from :data:`DIVERSITY_AXES` on purpose. ``surface`` and ``source-kind``
describe *provenance*, not design variety: a set assembled from one catalogue is
uniform in both by construction, so letting them vote would report every
single-provider set as too homogeneous on an axis nobody chose. They stay
reported - they are real evidence about the set - but they do not decide it.
"""

DIVERSITY_PROVENANCE_AXES = ("surface", "source-kind")
"""Reported, not voted. Uniformity here is a property of the provider."""

DIVERSITY_MIN_DISTINCT = 3
"""Below this many members the verdict is ``UNKNOWN``, not ``DIVERSE_ENOUGH``.

Three dark SaaS dashboards are homogeneous whatever their token values say, and
two references cannot be a set. Making the floor explicit means the verdict is
never a function of one or two records.
"""

HOMOGENEOUS_SHARE = 0.8
"""Above this share of members sharing one axis value, the set is too narrow."""

MIN_COVERAGE_ROLES = ("PRIMARY_DIRECTION",)
"""A set must be able to name a primary direction to ground a design direction."""


def role_spend(members: Sequence[Mapping]) -> dict[str, int]:
    """How much of the role budget a set consumes.

    ``primary_references`` and ``counter_references`` are budget lines like the
    retrieval lines, so a set has to spend against them. They were defined but
    never debited, which meant a set could hold four primary references against a
    cap of three and still report ``WITHIN_BUDGET`` - a bound that exists only on
    paper.
    """
    return {
        "primary_references": sum(
            1 for member in members
            if isinstance(member, Mapping) and "PRIMARY_DIRECTION" in (member.get("roles") or [])
        ),
        "counter_references": sum(
            1 for member in members
            if isinstance(member, Mapping) and "COUNTER_REFERENCE" in (member.get("roles") or [])
        ),
    }


def create(
    state: dict,
    *,
    requirement_scope: str,
    members: Sequence[Mapping],
    references_by_id: Mapping[str, Mapping],
    budget: Mapping | None = None,
    created_at: str = "",
    reference_set_id: str = "",
    note: str = "",
) -> dict:
    """Build, validate and append one ``ReferenceSet`` record.

    ``members`` is a list of ``{reference_id, roles, treatments?, counter_pattern?,
    note?}``. Every cross-record check runs here so an invalid set never reaches
    the run state.
    """
    rows = [dict(member) for member in members if isinstance(member, Mapping)]
    if not rows:
        raise ContractError("a reference set must contain at least one reference")
    if not str(requirement_scope or "").strip():
        raise ContractError("a reference set must record the requirement scope it was assembled for")

    seen: set[str] = set()
    for member in rows:
        reference_id = str(member.get("reference_id", "")).strip()
        if reference_id in seen:
            raise ContractError(
                f"reference set lists {reference_id} more than once; one reference enters a set once, "
                "however many roles it holds"
            )
        seen.add(reference_id)
        unknown = [
            role for role in (member.get("roles") or [])
            if str(role) not in contracts.REFERENCE_ROLES
        ]
        if unknown:
            raise ContractError(f"reference set member {reference_id} has unknown role(s): {unknown}")
        if not member.get("roles"):
            raise ContractError(
                f"reference set member {reference_id} names no role; an unroled reference cannot be "
                "used to justify a design choice"
            )

    problems: list[str] = []
    for member in rows:
        problems.extend(
            contracts.reference_set_member_problems(member, references_by_id=references_by_id)
        )
    if problems:
        raise ContractError("reference set member is not supportable: " + "; ".join(problems))

    selected = {str(member.get("reference_id")): references_by_id[str(member.get("reference_id"))] for member in rows}
    resolved_budget = resolve_budget(budget)
    # Debit the role lines before validating, so an over-cap set is refused rather
    # than recorded as within budget. `spend` refuses before incrementing, so a
    # rejected set leaves the budget untouched.
    for line, amount in role_spend(rows).items():
        spend(resolved_budget, line, amount)
    record = {
        "schema_version": contracts.SCHEMA_DESIGN,
        "reference_set_id": str(reference_set_id or contracts.new_record_id("rfs")),
        "run_id": str(state.get("run_id", "")),
        "requirement_scope": safety.reference_text_is_data(requirement_scope, field="requirement_scope"),
        "created_at": str(created_at or contracts.utc_now()),
        "members": rows,
        "coverage": coverage(selected, rows),
        "diversity": diversity(selected, rows),
        "budget": resolved_budget,
        "limitations": set_limitations(selected, rows),
        "approved_direction_id": "",
        "provenance": {
            "created_by": "engine",
            "policy_version": contracts.POLICY_VERSION,
        },
        "note": str(note),
    }
    record_problems = contracts.reference_set_problems(record)
    if record_problems:
        raise ContractError("reference set is malformed: " + "; ".join(record_problems))
    contracts.require_design_capacity(state, "design_reference_sets")
    state.setdefault("design_reference_sets", []).append(record)
    return record


def reference_sets(state: Mapping) -> list[dict]:
    values = state.get("design_reference_sets")
    if not isinstance(values, list):
        return []
    return [item for item in values if isinstance(item, Mapping)]


def reference_set(state: Mapping, reference_set_id: str) -> dict | None:
    for record in reference_sets(state):
        if str(record.get("reference_set_id", "")) == str(reference_set_id):
            return dict(record)
    return None


def latest_reference_set(state: Mapping) -> dict:
    rows = reference_sets(state)
    return dict(rows[-1]) if rows else {}


# --------------------------------------------------------------------- coverage


def coverage(references_by_id: Mapping[str, Mapping], rows: Sequence[Mapping]) -> dict:
    """Which design jobs the set can currently speak to.

    Reported as named holes, not as a number. "No interaction evidence and no
    counter-reference" is actionable; "coverage 0.6" is not.
    """
    roles: dict[str, int] = {}
    for member in rows:
        for role in member.get("roles") or []:
            roles[str(role)] = roles.get(str(role), 0) + 1
    evidence_levels: dict[str, int] = {}
    kinds: dict[str, int] = {}
    pattern_dimensions: set[str] = set()
    for member in rows:
        record = references_by_id.get(str(member.get("reference_id", ""))) or {}
        classification = record.get("classification") if isinstance(record.get("classification"), Mapping) else {}
        level = str(classification.get("evidence_level", "UNKNOWN"))
        evidence_levels[level] = evidence_levels.get(level, 0) + 1
        kind = str(classification.get("source_kind", "UNKNOWN"))
        kinds[kind] = kinds.get(kind, 0) + 1
        for pattern in record.get("observed_patterns") or []:
            if isinstance(pattern, Mapping) and str(pattern.get("dimension", "")):
                pattern_dimensions.add(str(pattern["dimension"]))

    missing: list[str] = []
    for role in MIN_COVERAGE_ROLES:
        if not roles.get(role):
            missing.append(f"no member holds {role}")

    insufficient = bool(missing)
    if insufficient:
        verdict = "INSUFFICIENT"
    elif not pattern_dimensions:
        verdict = "INSUFFICIENT"
        missing.append("no member carries an extracted observation, so nothing can be justified")
    else:
        verdict = "READY"
    return {
        "verdict": verdict,
        "roles": dict(sorted(roles.items())),
        "evidence_levels": dict(sorted(evidence_levels.items())),
        "source_kinds": dict(sorted(kinds.items())),
        "pattern_dimensions": sorted(pattern_dimensions),
        "missing": missing,
        "note": (
            "coverage reports which design jobs the set can speak to; it is not a quality score and "
            "says nothing about whether the direction those references support is a good one"
        ),
    }


def set_limitations(references_by_id: Mapping[str, Mapping], rows: Sequence[Mapping]) -> list[str]:
    """Every limitation any member carries, kept with the member that carries it."""
    collected: list[str] = []
    for member in rows:
        reference_id = str(member.get("reference_id", ""))
        record = references_by_id.get(reference_id) or {}
        for limitation in record.get("limitations") or []:
            collected.append(f"{reference_id}: {limitation}")
    return collected


# -------------------------------------------------------------------- diversity


_SURFACE_ROLE_HINTS = ("surface", "canvas", "background", "base", "bg")
"""Token names whose value describes the *base* surface rather than an accent.

Lightness has to be read from the canvas, not by averaging a palette. Averaging is
wrong for the way real design systems are written: a dark system routinely declares
``inverse-canvas: #ffffff`` and white inverse surfaces alongside its near-black
base, so the mean of every token lands mid-grey and a near-black tool gets
reported as ``light-dominant``. The canvas is the ground truth.
"""

_INVERSE_ROLE_MARKERS = ("inverse", "light-mode-", "lightmode")
"""Tokens describing the *opposite* palette, excluded from the base read.

The published corpus pairs every dark theme with an ``inverse-*`` set, and those
tokens name the same roles in the other palette. Counting them alongside the base
canvas is how a near-black system ends up averaging out to "light".
"""


def _is_base_surface_token(name: str) -> bool:
    lowered = str(name or "").lower()
    if any(marker in lowered for marker in _INVERSE_ROLE_MARKERS):
        return False
    return any(hint in lowered for hint in _SURFACE_ROLE_HINTS)


def _axes(record: Mapping) -> dict[str, str]:
    """Classify one reference across the diversity axes, from recorded evidence.

    Every axis value is either read from the record or reported ``UNKNOWN``. None
    is inferred from a brand name, because "Linear" and "Vercel" are names, not
    evidence of anything.
    """
    classification = record.get("classification") if isinstance(record.get("classification"), Mapping) else {}
    dimensions = {
        str(row.get("dimension", ""))
        for row in (record.get("observed_patterns") or [])
        if isinstance(row, Mapping)
    }
    light_dark = "UNKNOWN"
    tokens = record.get("design_tokens") if isinstance(record.get("design_tokens"), Mapping) else {}
    colors = tokens.get("colors") or []
    if colors:
        light_dark = _light_dark_from_tokens(colors)
    emphasis = "UNKNOWN"
    if dimensions & {"interaction", "motion", "navigation"}:
        emphasis = "interaction"
    elif dimensions & {"component-geometry", "layout-grid", "density"}:
        emphasis = "layout"
    elif dimensions & {"typography"}:
        emphasis = "typography"
    elif dimensions & {"color-roles", "surface-treatment"}:
        emphasis = "surface"
    return {
        "industry": str(classification.get("product", "") or classification.get("brand", "") or "UNKNOWN").lower() or "UNKNOWN",
        "surface": str(classification.get("surface", "") or "UNKNOWN"),
        "source-kind": str(classification.get("source_kind", "UNKNOWN")),
        "light-dark": light_dark,
        "emphasis": emphasis,
        "role": "recorded-per-member",
    }


def _light_dark_from_tokens(colors: Sequence[Mapping]) -> str:
    """Classify a palette light or dark from its base surface.

    Prefers a declared canvas/surface token. Failing that, uses the darkest token
    as the base, because a design system's base surface is its darkest value in a
    dark system and its lightest in a light one. Averaging every token is never
    used, for the reason in :data:`_SURFACE_ROLE_HINTS`.
    """
    lumas: list[tuple[str, float]] = []
    for entry in colors:
        if not isinstance(entry, Mapping):
            continue
        values = entry.get("values")
        if not isinstance(values, Mapping):
            continue
        value = _relative_luminance(str(values.get("value", "")))
        if value is not None:
            lumas.append((str(entry.get("name", "")).lower(), value))
    if not lumas:
        return "UNKNOWN"
    canvas = [value for name, value in lumas if _is_base_surface_token(name)]
    if canvas:
        base = sum(canvas) / len(canvas)
    else:
        base = min(value for _name, value in lumas)
    return "dark-dominant" if base < 0.35 else "light-dominant"


def _relative_luminance(value: str) -> float | None:
    text = str(value or "").strip().lower()
    if not text.startswith("#") or len(text) not in (4, 7):
        return None
    body = text[1:]
    if len(body) == 3:
        body = "".join(char * 2 for char in body)
    try:
        channels = [int(body[index:index + 2], 16) / 255.0 for index in (0, 2, 4)]
    except ValueError:
        return None
    linear = [
        channel / 12.92 if channel <= 0.03928 else ((channel + 0.055) / 1.055) ** 2.4
        for channel in channels
    ]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


PROVIDER_CONSTANT_AXES = ("surface",)
"""Deprecated in favour of the voting/provenance split in
:data:`DIVERSITY_VOTING_AXES` / :data:`DIVERSITY_PROVENANCE_AXES`.

Kept as a name because it is the concept the split implements: an axis whose
value is fixed by the provider rather than by the selection. Every getdesign.md
entry analyses a website, so ``surface=website`` always, for any selection at all.
"""


def diversity(references_by_id: Mapping[str, Mapping], rows: Sequence[Mapping]) -> dict:
    """Deterministic diversity verdict over the set's recorded classification.

    The check is deliberately coarse and deliberately says so. It catches the
    obvious failure - five near-identical dark SaaS dashboards - and it does not
    claim to measure aesthetic similarity, because nothing here can. When the
    members carry too little classified information to judge, the verdict is
    ``UNKNOWN``, which is an answer rather than a failure.
    """
    members = [
        (str(member.get("reference_id", "")), _axes(references_by_id.get(str(member.get("reference_id", ""))) or {}))
        for member in rows
    ]
    distinct: dict[str, int] = {}
    unknown_counts: dict[str, int] = {}
    for axis in DIVERSITY_AXES:
        if axis == "role":
            values = sorted({str(role) for member in rows for role in (member.get("roles") or [])})
            distinct[axis] = len(values)
            unknown_counts[axis] = 0
            continue
        values = [axes.get(axis, "UNKNOWN") for _id, axes in members]
        distinct[axis] = len({value for value in values if value != "UNKNOWN"})
        unknown_counts[axis] = sum(1 for value in values if value == "UNKNOWN")

    if len(members) < DIVERSITY_MIN_DISTINCT:
        return {
            "verdict": "UNKNOWN",
            "distinct_per_axis": dict(sorted(distinct.items())),
            "unknown_per_axis": dict(sorted(unknown_counts.items())),
            "homogeneous_axes": [],
            "reason": (
                f"the set holds {len(members)} member(s); fewer than {DIVERSITY_MIN_DISTINCT} cannot be "
                "judged for diversity, and reporting otherwise would be a verdict the evidence cannot "
                "support"
            ),
        }

    homogeneous: list[dict] = []
    provider_constant: list[str] = []
    provenance_axes: list[str] = []
    # The provider-constant test considers the *external* members only. A project's
    # own DESIGN.md is a different kind of thing from a curated catalogue entry,
    # and letting it break the tie would make every mixed set look non-uniform.
    external = [
        axes for _id, axes in members
        if axes.get("source-kind") not in ("LOCAL_DESIGN_FILE", "UNKNOWN")
    ]
    external_kinds = {axes.get("source-kind", "UNKNOWN") for axes in external}
    for axis in DIVERSITY_AXES:
        if axis == "role":
            continue
        if unknown_counts[axis] == len(members):
            continue
        values = [axes.get(axis, "UNKNOWN") for _id, axes in members]
        counts: dict[str, int] = {}
        for value in values:
            if value == "UNKNOWN":
                continue
            counts[value] = counts.get(value, 0) + 1
        if not counts:
            continue
        dominant, share_count = max(counts.items(), key=lambda item: (item[1], item[0]))
        classified = sum(counts.values())
        if axis not in DIVERSITY_VOTING_AXES:
            # Provenance axes are recorded but do not vote; see
            # DIVERSITY_VOTING_AXES for why.
            provenance_axes.append(axis)
            continue
        if classified and share_count / classified > HOMOGENEOUS_SHARE:
            homogeneous.append({
                "axis": axis,
                "value": dominant,
                "share": round(share_count / classified, 3),
            })

    voting_axes = list(DIVERSITY_VOTING_AXES)
    insufficient_information = sum(1 for axis in voting_axes if distinct.get(axis, 0) <= 1)
    if homogeneous:
        verdict = "TOO_HOMOGENEOUS"
    elif insufficient_information >= 4:
        verdict = "UNKNOWN"
    else:
        verdict = "DIVERSE_ENOUGH"

    reason = ""
    if verdict == "TOO_HOMOGENEOUS":
        reason = "; ".join(
            f"{item['axis']}={item['value']} holds {item['share']:.0%} of classified members" for item in homogeneous
        )
    elif verdict == "UNKNOWN":
        reason = (
            f"{insufficient_information} of {len(voting_axes)} diversity axes carry a single value or are "
            "unclassified, so this verdict would be a guess"
        )
    else:
        reason = "no informative axis is dominated by a single value"
    return {
        "verdict": verdict,
        "distinct_per_axis": dict(sorted(distinct.items())),
        "unknown_per_axis": dict(sorted(unknown_counts.items())),
        "homogeneous_axes": homogeneous,
        "provider_constant_axes": provider_constant,
        "provenance_axes": provenance_axes,
        "single_provider": len(external_kinds) <= 1 and bool(external),
        "voting_axes": voting_axes,
        "reason": reason,
        "note": (
            "this measures recorded classification, not aesthetic similarity. Five references with "
            "different industries and the same dark palette still read as homogeneous to a person, and "
            "this check will not catch that"
        ),
    }


# ----------------------------------------------------------------------- budget


def default_budget() -> dict:
    return {
        "limits": dict(contracts.REFERENCE_BUDGET_DEFAULTS),
        "spent": {
            "candidate_retrieval": 0,
            "deep_inspection": 0,
            "primary_references": 0,
            "counter_references": 0,
        },
        "expansions": [],
        "verdict": "WITHIN_BUDGET",
        "note": (
            "these are defaults, not truths. A task may expand a budget, and an expansion is recorded "
            "with its reason rather than applied silently"
        ),
    }


def resolve_budget(budget: Mapping | None, *, spent: Mapping | None = None) -> dict:
    """Validate a research budget, refusing an expansion that was not justified."""
    resolved = default_budget()
    if budget is not None:
        if not isinstance(budget, Mapping):
            raise ContractError("a reference budget must be a mapping")
        limits = budget.get("limits") if isinstance(budget.get("limits"), Mapping) else budget
        for name in contracts.REFERENCE_BUDGET_DEFAULTS:
            value = limits.get(name) if isinstance(limits, Mapping) else None
            if value is None:
                continue
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ContractError(f"budget limit {name!r} must be a non-negative integer")
            base = contracts.REFERENCE_BUDGET_DEFAULTS[name]
            if value > base and not str(budget.get("reason", "")).strip():
                raise ContractError(
                    f"budget limit {name!r} is expanded from {base} to {value} with no recorded reason; "
                    "expanding a research budget has to say why"
                )
            resolved["limits"][name] = int(value)
        if str(budget.get("reason", "")).strip():
            for name, value in sorted(limits.items()) if isinstance(limits, Mapping) else []:
                base = contracts.REFERENCE_BUDGET_DEFAULTS.get(name)
                if base is not None and isinstance(value, int) and value > base:
                    resolved["expansions"].append({
                        "limit": name,
                        "from": base,
                        "to": int(value),
                        "reason": str(budget["reason"]),
                    })
    if spent:
        for name, value in spent.items():
            if name in resolved["spent"]:
                resolved["spent"][name] = int(value)
    resolved["verdict"] = budget_verdict(resolved)
    return resolved


def budget_verdict(budget: Mapping) -> str:
    limits = budget.get("limits") if isinstance(budget.get("limits"), Mapping) else {}
    spent = budget.get("spent") if isinstance(budget.get("spent"), Mapping) else {}
    for name in contracts.REFERENCE_BUDGET_DEFAULTS:
        cap = limits.get(name)
        used = spent.get(name)
        if isinstance(cap, int) and isinstance(used, int) and used > cap:
            return "OVER_BUDGET"
    return "WITHIN_BUDGET"


def spend(budget: Mapping, name: str, amount: int = 1) -> dict:
    """Record spending against a budget and refuse to exceed it silently.

    The refusal happens *before* the increment, so an over-budget call leaves the
    budget exactly as it was. Continuing past a bound because "one more fetch will
    probably help" is how a bounded subsystem becomes unbounded.
    """
    if name not in contracts.REFERENCE_BUDGET_DEFAULTS:
        raise ContractError(f"unknown reference budget line: {name!r}")
    limits = budget.get("limits") if isinstance(budget.get("limits"), Mapping) else {}
    spent = budget.get("spent") if isinstance(budget.get("spent"), Mapping) else {}
    cap = limits.get(name)
    used = int(spent.get(name, 0))
    if isinstance(cap, int) and used + int(amount) > cap:
        raise ContractError(
            f"reference budget line {name!r} is exhausted ({used}/{cap}); reference research stops here "
            "rather than exceeding a bound that was set to be a bound"
        )
    spent[name] = used + int(amount)
    budget["spent"] = dict(spent)
    budget["verdict"] = budget_verdict(budget)
    return budget


# ---------------------------------------------------------- source preference

PREFERENCE_ORDER = (
    "FIRST_PARTY_DESIGN_MD", "LOCAL_DESIGN_FILE", "FIGMA_DOCUMENT", "LIVE_SITE_INSPECTION",
    "SOURCE_REPOSITORY", "MCP_RESULT", "COMPONENT_REGISTRY", "CLI_RESULT",
    "CURATED_DESIGN_ANALYSIS", "SECONDARY_DESCRIPTION",
)
"""Deterministic preference when evidence *type* differs.

This is a tie-break, not a score. It exists so a first-party design system is
never silently passed over for a curated analysis when the two are equally
relevant, and it is deliberately not folded into relevance: a highly relevant
curated analysis outranks an unrelated first-party system every time, because
the ordering below is only consulted when relevance has not already separated the
candidates.
"""

PREFERENCE_RANK = {kind: index for index, kind in enumerate(PREFERENCE_ORDER)}


def preference(record: Mapping) -> tuple[int, str]:
    """``(preference_rank, evidence_level)`` for one reference."""
    classification = record.get("classification") if isinstance(record.get("classification"), Mapping) else {}
    kind = str(classification.get("source_kind", "SECONDARY_DESCRIPTION"))
    level = str(classification.get("evidence_level", "UNVERIFIED"))
    return (PREFERENCE_RANK.get(kind, len(PREFERENCE_ORDER)), level)


def preference_order(references_by_id: Mapping[str, Mapping], reference_ids: Sequence[str]) -> list[str]:
    """Sort reference ids by preference, stably.

    Stability matters: two references of equal kind and evidence level keep the
    order the caller chose, so this function never reorders a deliberate
    selection into an arbitrary one.
    """
    return [
        reference_id
        for reference_id in sorted(
            reference_ids,
            key=lambda rid: (preference(references_by_id.get(rid) or {}), rid),
        )
    ]


def rank_candidates(candidates: Sequence[Mapping], *, limit: int) -> list[dict]:
    """Order search candidates by relevance, then by declared preference.

    Relevance comes first and is the recorded score the adapter produced. The
    source-kind preference is only a tie-break between equally scored candidates,
    which is the whole point of refusing to reduce everything to one scalar.

    Ranking more candidates than the cap *truncates* rather than raising. The cap
    is the bound doing its job; refusing here would make a wider search an error
    instead of a filtered result, and would punish a caller for retrieving more
    evidence than it intends to inspect. The input bound lives at the budget and
    at ``search``, where it belongs.
    """
    ordered = sorted(
        (dict(row) for row in candidates if isinstance(row, Mapping)),
        key=lambda row: (
            -float(row.get("score", 0.0) or 0.0),
            PREFERENCE_RANK.get(str(row.get("source_kind", "SECONDARY_DESCRIPTION")), len(PREFERENCE_ORDER)),
            str(row.get("slug", "")),
        ),
    )
    return ordered[: max(int(limit), 0)]


# ------------------------------------------------------------------- reporting


def summarise(record: Mapping) -> str:
    """A short human view of one reference set."""
    lines = [f"Reference set {record.get('reference_set_id', '')}"]
    scope = str(record.get("requirement_scope", ""))
    if scope:
        lines.append(f"Scope: {scope}")
    references = record.get("members") or []
    for member in references:
        reference_id = str(member.get("reference_id", ""))
        roles = ", ".join(str(role) for role in (member.get("roles") or []))
        counter = str(member.get("counter_pattern", ""))
        suffix = f" (not: {counter})" if counter else ""
        lines.append(f"  - {reference_id}  roles: {roles}{suffix}")
    coverage_block = record.get("coverage") if isinstance(record.get("coverage"), Mapping) else {}
    diversity_block = record.get("diversity") if isinstance(record.get("diversity"), Mapping) else {}
    budget_block = record.get("budget") if isinstance(record.get("budget"), Mapping) else {}
    lines.append(
        f"Coverage: {coverage_block.get('verdict', 'UNKNOWN')}   "
        f"Diversity: {diversity_block.get('verdict', 'UNKNOWN')}   "
        f"Budget: {budget_block.get('verdict', 'UNKNOWN')}"
    )
    return "\n".join(lines)


def provenance_problems(state: Mapping) -> list[str]:
    """Cross-record checks over every reference set in the run."""
    from .. import references as references_module

    problems: list[str] = []
    by_id = {str(record.get("reference_id")): record for record in references_module.references(state)}
    seen: set[str] = set()
    for record in reference_sets(state):
        set_id = str(record.get("reference_set_id", ""))
        if set_id in seen:
            problems.append(f"duplicate reference set id: {set_id}")
        seen.add(set_id)
        problems.extend(contracts.reference_set_problems(record))
        for member in record.get("members") or []:
            if not isinstance(member, Mapping):
                continue
            problems.extend(
                contracts.reference_set_member_problems(member, references_by_id=by_id)
            )
        direction_id = str(record.get("approved_direction_id", "") or "")
        if direction_id and not str(record.get("approved_at", "")):
            problems.append(
                f"reference set {set_id} names an approved direction but records no approval time; a "
                "set is bound to a direction by the direction's own approval record, not by assertion"
            )
    return problems


def assert_observation_not_recommendation(record: Mapping) -> list[str]:
    """Check that an observation block has not been written as an instruction.

    The observation/recommendation/approval separation is a stated invariant, and
    an invariant nobody checks is a comment. A pattern whose text reads as a
    directive to the *design* (rather than a statement about the *source*) is
    reported here so it cannot quietly move a reference from evidence into
    instruction.
    """
    problems: list[str] = []
    for pattern in record.get("observed_patterns") or []:
        if not isinstance(pattern, Mapping):
            continue
        observation = str(pattern.get("observation", ""))
        directive = re.search(
            r"^\s*(?:you\s+should|must\s+use|always\s+use|never\s+use|required\s+to|"
            r"set\s+the|change\s+the|use\s+this|apply\s+this)\b",
            observation,
            re.IGNORECASE,
        )
        if directive:
            problems.append(
                f"observed pattern on {pattern.get('dimension')} is phrased as an instruction to the "
                f"design rather than an observation about the source: {observation[:80]!r}"
            )
    return problems


__all__ = [
    "DIVERSITY_AXES",
    "DIVERSITY_MIN_DISTINCT",
    "DIVERSITY_PROVENANCE_AXES",
    "DIVERSITY_VOTING_AXES",
    "HOMOGENEOUS_SHARE",
    "PREFERENCE_ORDER",
    "PREFERENCE_RANK",
    "ROLE_REQUIREMENTS",
    "assert_observation_not_recommendation",
    "budget_verdict",
    "coverage",
    "create",
    "default_budget",
    "diversity",
    "latest_reference_set",
    "preference",
    "preference_order",
    "provenance_problems",
    "rank_candidates",
    "reference_set",
    "reference_sets",
    "resolve_budget",
    "set_limitations",
    "spend",
    "summarise",
]