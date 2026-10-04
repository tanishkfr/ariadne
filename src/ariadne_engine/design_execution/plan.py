"""``DesignImplementationPlan``: an approved direction, expressed as code obligations.

> **References do not produce code. Approved design principles produce
> implementation constraints.**

AR-220 stopped at approved-ready *direction* evidence. This module is the next
link and the first one that can lose information, because a direction is prose and
code is not. Prose survives translation by being re-read; an implementation plan
does not, so every obligation it states has to name the thing it came from:

```text
Accent colour        → PROJECT_IDENTITY   → src/styles/tokens.css
Dense navigation     → APPROVED_DIRECTION → supported by 4 inspected references
Keyboard-operable    → ENGINEERING_CONSTRAINT + accessibility floor
   panel divider        → reference pattern, adapted
Rounded glass cards  → FORBIDDEN           → counter-reference's own anti-pattern
```

Four refusals are load-bearing, and each closes a specific way this layer could
otherwise launder inspiration into authority:

1. **No approval, no plan.** The compiler requires a ``G1D`` approval that the run
   actually holds, bound to the direction's *current* fingerprint. A candidate
   direction has nothing to consume, and the brief's "implementation needs
   something to consume" is not an approval.
2. **The reference set must be the one the direction was built from.** A plan
   assembled against a different set is a different design, however similar the
   topics.
3. **A reference principle cannot outrank a human decision.** Precedence is
   explicit and contradictions are *suppressed and recorded*, not silently
   resolved in the direction's favour.
4. **Accessibility is a floor, not a competitor.** It has no precedence number,
   because it is not competing with anything - a reference cannot trade away
   keyboard access, focus visibility, semantics, labels, contrast, reduced motion
   or touch targets.

The compiler is deterministic and bounded. It states *what to implement*; it never
regenerates an aesthetic, and it never asks a model to invent one.
"""

from __future__ import annotations

import re
from typing import Mapping, Sequence

from .. import contracts
from ..contracts import ContractError

PLAN_GATE = "G1D"
"""The approval a plan binds to. Design direction approval, unchanged from 2.1.

AR-221 does not invent a second gate. The authority to shape an interface is the
same authority that approved its direction, and a run with two gates for one
decision has one too many.
"""

ACCESSIBILITY_CATEGORIES = ("accessibility",)
"""Constraint categories that sit on the floor rather than in the ranking."""


# --------------------------------------------------------------------- binding

def approval_binding(state: Mapping, direction_record: Mapping) -> dict:
    """Bind an approved direction to the approval that authorises implementing it.

    Returns the binding block, or raises with the reason. The check is the
    existing approval boundary, not a second opinion of it:

    * the direction must carry ``status == "approved"``;
    * the run must hold the recorded approval id;
    * that approval must bind to the direction's *current* fingerprint, so an edit
      made after approval invalidates the plan rather than silently surviving it;
    * the approval must have arrived on the human channel;
    * the approving identity must not be this run's implementation worker.

    No bypass, and no fixture-only approval path. A test that wants an approved
    direction calls ``design.approve_direction`` exactly as an operator would, so
    the thing the tests exercise is the thing production runs.
    """
    from .. import design as design_module
    from .. import policy
    from .. import review as review_module

    direction_id = str(direction_record.get("direction_id", ""))
    if str(direction_record.get("status", "")) != "approved":
        raise ContractError(
            f"design direction {direction_id!r} has status "
            f"{direction_record.get('status') or 'missing'!r}; only an approved direction can be "
            "implemented. A candidate direction is a proposal, and implementation needs something a "
            f"human authorised - grant {PLAN_GATE} or stop"
        )
    approval_id = str(direction_record.get("approval_id", "")).strip()
    if not approval_id:
        raise ContractError(
            f"design direction {direction_id!r} claims approval but records no approval id; an "
            "authorization id is a claim like any other"
        )
    recorded = [
        approval for approval in (state.get("approvals") or [])
        if isinstance(approval, Mapping) and str(approval.get("approval_id", "")) == approval_id
    ]
    if not recorded:
        raise ContractError(
            f"the approval {approval_id!r} on direction {direction_id!r} is not recorded in this run; "
            "an approval the engine does not hold is a claim, not a gate"
        )
    approval = recorded[0]
    if str(approval.get("gate", "")) != PLAN_GATE:
        raise ContractError(
            f"the approval {approval_id!r} was granted for gate {approval.get('gate')!r}, not {PLAN_GATE}"
        )
    channel = str(approval.get("channel", ""))
    if channel != contracts.APPROVAL_CHANNEL_HUMAN:
        raise ContractError(
            f"the approval {approval_id!r} arrived on channel {channel!r}; only the human channel "
            "authorises an implementation, because implementation is what the human is approving"
        )
    revision = contracts.direction_fingerprint(direction_record)
    if str(approval.get("revision_hash", "")) != revision:
        raise ContractError(
            f"the approval {approval_id!r} is stale: the direction changed after it was granted "
            "(DESIGN_DIRECTION_STALE). Re-approve the current revision rather than implementing the old one"
        )
    identity = str(approval.get("identity", "")).strip()
    worker_ids = {value.lower() for value in review_module.worker_identities(dict(state))}
    if identity and identity.lower() in worker_ids:
        raise ContractError(
            f"the recorded identity {identity!r} is this run's implementation worker; an implementer "
            "cannot approve the design it is about to build"
        )
    problems = design_module.direction_problems(dict(state), task_id=str(direction_record.get("task_id", "")))
    if problems:
        raise ContractError(
            "the approved direction is not in a usable state: " + "; ".join(problems)
        )
    return {
        "gate": PLAN_GATE,
        "approval_id": approval_id,
        "direction_revision_hash": revision,
        "approved_at": str(direction_record.get("approved_at", "")),
        "identity": identity,
        "channel": channel,
        "note": str(approval.get("note", "")),
    }


# ------------------------------------------------------------------ constraints

def constraint(
    *,
    category: str,
    statement: str,
    basis: str,
    evidence: str,
    constraint_id: str = "",
    surfaces: Sequence[str] = (),
    material: bool = True,
    treatment: str = "",
    principle_ids: Sequence[str] = (),
    reference_ids: Sequence[str] = (),
    accessibility_floor: bool = False,
    detectors: Sequence[str] = (),
) -> dict:
    """One implementation constraint, with its basis and the evidence for it.

    The signature makes the interesting arguments mandatory and keyword-only,
    because the failure mode this record exists to prevent is a constraint that
    carries a category and a statement and nothing else.
    """
    if category not in contracts.IMPLEMENTATION_CONSTRAINT_CATEGORIES:
        raise ContractError(f"unknown implementation constraint category: {category}")
    if basis not in contracts.IMPLEMENTATION_CONSTRAINT_BASES:
        raise ContractError(f"unknown implementation constraint basis: {basis}")
    text = " ".join(str(statement).split())
    if not text:
        raise ContractError("an implementation constraint must state something")
    if not str(evidence).strip():
        raise ContractError(
            f"constraint {text[:60]!r} names basis {basis} but no evidence; a basis without a source "
            "is a label"
        )
    if treatment and treatment not in contracts.REFERENCE_TREATMENTS:
        raise ContractError(f"unknown reference treatment on a constraint: {treatment}")
    if accessibility_floor and basis not in contracts.ACCESSIBILITY_FLOOR_BASES:
        raise ContractError(
            "the accessibility floor cannot be claimed from "
            f"{basis}; inspiration does not originate accessibility obligations"
        )
    return {
        "constraint_id": str(constraint_id or contracts.new_record_id("dic")),
        "category": category,
        "statement": text,
        "basis": basis,
        "authority": contracts.CONSTRAINT_PRECEDENCE[basis],
        "evidence": str(evidence),
        "material": bool(material),
        "treatment": str(treatment),
        "surfaces": [str(item) for item in surfaces],
        "principle_ids": [str(item) for item in principle_ids],
        "reference_ids": [str(item) for item in reference_ids],
        "accessibility_floor": "TRUE" if accessibility_floor else "FALSE",
        "detectors": [str(item) for item in detectors],
    }


def resolve_precedence(constraints: Sequence[Mapping]) -> dict:
    """Apply the permanent precedence order and report what it removed.

    Two rules, in this order, and nothing else:

    1. **Authority.** Two constraints that share a category and intersect on a
       surface are competing for the same slot. The one with lower precedence loses,
       and the loser is recorded.
    2. **Literal contradiction.** At *equal* authority two constraints on the same
       slot can only genuinely conflict if both commit to a concrete value and the
       values differ. Two constraints that defer to the project's own tokens are
       compatible, and neither is dropped.

    Contradiction is never guessed from prose. A direction that adds an accent
    alongside an existing neutral palette is not a conflict, and treating it as one
    would silently delete half the plan.

    The order in which constraints are *declared* does not decide precedence; only
    :data:`contracts.CONSTRAINT_PRECEDENCE` does. Otherwise the last line written
    would win, which is not a policy anyone can reason about.
    """
    kept: list[Mapping] = []
    suppressed: list[dict] = []
    for candidate in constraints:
        conflicts = _conflicts_with(candidate, kept)
        if not conflicts:
            kept.append(candidate)
            continue
        winner = conflicts
        suppressed.append({
            "constraint_id": str(candidate.get("constraint_id", "")),
            "statement": str(candidate.get("statement", "")),
            "basis": str(candidate.get("basis", "")),
            "authority": candidate.get("authority"),
            "category": str(candidate.get("category", "")),
            "conflicts_with": str(winner.get("constraint_id", "")),
            "reason": (
                f"{candidate.get('basis')} ({candidate.get('authority')}) cannot override "
                f"{winner.get('basis')} ({winner.get('authority')}) on {candidate.get('category')}"
            ),
            "outcome": "SUPPRESSED_BY_PRECEDENCE",
        })
    # An accessibility floor is never suppressed, whatever its own authority number,
    # because it is not competing. Two things follow from that.

    # First: a floor outranks *every* reference-sourced constraint that touches a
    # surface it covers, in any category. The rule is deliberately asymmetric in
    # origin - "inspiration may not trade away accessibility" - rather than keyed on
    # category, because a reference-sourced layout constraint and an accessibility
    # floor share no category and would otherwise never meet.

    # Second: a floor does not displace project identity or the user's own
    # requirement. Those legitimately shape layout, and pretending otherwise would
    # make a floor unusable.
    REFERENCE_SOURCED_BASES = ("REFERENCE_PRINCIPLE", "IMPLEMENTATION_REFERENCE")
    floor_survivors = [row for row in kept if str(row.get("accessibility_floor", "")) == "TRUE"]
    for floor in floor_survivors:
        floor_surfaces = _scope(floor)
        for other in list(kept):
            if other is floor:
                continue
            if str(other.get("basis", "")) not in REFERENCE_SOURCED_BASES:
                continue
            if not _overlaps(floor, other):
                continue
            kept.remove(other)
            suppressed.append({
                "constraint_id": str(other.get("constraint_id", "")),
                "statement": str(other.get("statement", "")),
                "basis": str(other.get("basis", "")),
                "authority": other.get("authority"),
                "category": str(other.get("category", "")),
                "conflicts_with": str(floor.get("constraint_id", "")),
                "reason": (
                    f"{other.get('basis')} tried to trade away an accessibility floor "
                    f"({floor.get('statement')}); accessibility is not a preference and inspiration "
                    "cannot rank it"
                ),
                "outcome": "SUPPRESSED_BY_ACCESSIBILITY_FLOOR",
            })

    # The incremental loop above can only suppress a constraint that arrives *after*
    # the one that beats it. Precedence must not depend on declaration order, so a
    # final pass removes anything that is still outranked by a survivor. Without this,
    # writing the borrowed palette first and the project identity second would let the
    # borrowed palette stand - which is precisely how an accidental ordering becomes
    # an unstated policy.
    final: list[Mapping] = []
    for candidate in kept:
        winner = _beats(candidate, [row for row in kept if row is not candidate])
        if winner is None:
            final.append(candidate)
            continue
        suppressed.append({
            "constraint_id": str(candidate.get("constraint_id", "")),
            "statement": str(candidate.get("statement", "")),
            "basis": str(candidate.get("basis", "")),
            "authority": candidate.get("authority"),
            "category": str(candidate.get("category", "")),
            "conflicts_with": str(winner.get("constraint_id", "")),
            "reason": (
                f"{candidate.get('basis')} ({candidate.get('authority')}) cannot override "
                f"{winner.get('basis')} ({winner.get('authority')}) on {candidate.get('category')}"
            ),
            "outcome": "SUPPRESSED_BY_PRECEDENCE",
        })
    return {
        "constraints": [dict(row) for row in final],
        "suppressed": _dedupe(suppressed),
        "order": [
            basis for basis, _value in sorted(
                contracts.CONSTRAINT_PRECEDENCE.items(), key=lambda item: -item[1]
            )
        ],
    }


def _dedupe(rows: Sequence[Mapping]) -> list[dict]:
    seen: set[tuple[str, str]] = set()
    result: list[dict] = []
    for row in rows:
        key = (str(row.get("constraint_id", "")), str(row.get("outcome", "")))
        if key in seen:
            continue
        seen.add(key)
        result.append(dict(row))
    return result


def _beats(candidate: Mapping, others: Sequence[Mapping]) -> Mapping | None:
    """The highest-authority constraint in ``others`` that outranks ``candidate``.

    Accessibility loses this comparison deliberately: a floor is protected by the
    accessibility pass, not by its authority number, so it cannot outrank anything
    here and cannot be displaced from here either.
    """
    category = str(candidate.get("category", ""))
    surfaces = _scope(candidate)
    mine = contracts.CONSTRAINT_PRECEDENCE[str(candidate.get("basis", ""))]
    mine_values = _declared_values(candidate, category)
    best: Mapping | None = None
    for other in others:
        if str(other.get("category", "")) != category:
            continue
        if not surfaces & _scope(other):
            continue
        theirs = contracts.CONSTRAINT_PRECEDENCE[str(other.get("basis", ""))]
        if theirs < mine:
            continue
        if theirs == mine:
            their_values = _declared_values(other, category)
            if not (mine_values and their_values and mine_values != their_values):
                continue
        if best is None or contracts.CONSTRAINT_PRECEDENCE[str(best.get("basis", ""))] < theirs:
            best = other
    return best


_COLOUR_VALUE_RE = re.compile(
    r"(?:#[0-9a-fA-F]{3,8}\b|\b(?:rgb|rgba|hsl|hsla)\([^)]*\)|\b(?:oklch|color-mix)\([^)]*\))"
)
_TYPE_FAMILY_RE = re.compile(r"(?:\bfont-family\b|['\"][A-Z][A-Za-z0-9 ]{2,}['\"]\s*(?:,|;|$))")
_RADIUS_RE = re.compile(r"\b\d+(?:\.\d+)?px\b")
_TOKEN_RE = re.compile(r"var\(\s*(--[A-Za-z0-9_-]+)\s*[,)]")


ALL_SURFACES = "*"
"""The wildcard an unscoped constraint speaks for."""


def _scope(row: Mapping) -> set[str]:
    """The surfaces a constraint speaks for. An empty list means *all of them*.

    Treating an unscoped constraint as scoped to nothing would make it immune to
    precedence, which is a quiet way for a colour rule to survive forever: nothing
    else can collide with it. Scoping a constraint is what narrows it, never what
    exempts it.
    """
    declared = {str(item) for item in row.get("surfaces") or []}
    return declared or {ALL_SURFACES}


def _overlaps(left: Mapping, right: Mapping) -> bool:
    """Whether two constraints govern any surface in common."""
    left_scope, right_scope = _scope(left), _scope(right)
    return ALL_SURFACES in left_scope or ALL_SURFACES in right_scope or bool(left_scope & right_scope)


def _conflicts_with(candidate: Mapping, established: Sequence[Mapping]) -> Mapping | None:
    """The highest-authority established constraint ``candidate`` collides with, if any.

    A collision needs the same category and an overlapping surface - otherwise two
    constraints are governing different regions of the interface and neither is
    touching the other's slot.

    Once they collide, authority decides, with one exception: at *equal* authority
    they only conflict if both commit to a concrete value and the values differ. Two
    constraints that defer to the project's tokens do not contradict each other, and
    dropping one of them would delete a plan for no reason a reader could name.
    """
    category = str(candidate.get("category", ""))
    candidates = [
        other for other in established
        if str(other.get("category", "")) == category and _overlaps(candidate, other)
    ]
    if not candidates:
        return None
    mine = _declared_values(candidate, category)
    best: Mapping | None = None
    for other in candidates:
        candidate_authority = contracts.CONSTRAINT_PRECEDENCE[str(candidate.get("basis", ""))]
        other_authority = contracts.CONSTRAINT_PRECEDENCE[str(other.get("basis", ""))]
        if candidate_authority < other_authority:
            if best is None or contracts.CONSTRAINT_PRECEDENCE[str(best.get("basis", ""))] < other_authority:
                best = other
            continue
        if candidate_authority > other_authority:
            continue
        theirs = _declared_values(other, category)
        if mine and theirs and mine != theirs:
            if best is None or contracts.CONSTRAINT_PRECEDENCE[str(best.get("basis", ""))] < other_authority:
                best = other
    return best


def _declared_values(row: Mapping, category: str) -> frozenset[str]:
    """Concrete design values a constraint commits to, if any.

    A constraint that defers to the project ("use the tokens in tokens.css") names
    no value and therefore conflicts with nothing. That is the correct reading: it
    is not competing for the slot, it has handed the slot to the project.
    """
    text = f"{row.get('statement', '')} {row.get('evidence', '')}".lower()
    if category == "color":
        values = frozenset(value.lower() for value in _COLOUR_VALUE_RE.findall(text))
    elif category == "typography":
        values = frozenset(value.lower() for value in _TYPE_FAMILY_RE.findall(text))
    elif category in ("surface", "spacing"):
        values = frozenset(_RADIUS_RE.findall(text))
    else:
        values = frozenset()
    return values


# ------------------------------------------------------------------- AVOID sets

_COUNTER_DETECTORS = {
    "glass": ("backdrop-filter", "-webkit-backdrop-filter"),
    "gradient": ("linear-gradient(", "radial-gradient(", "conic-gradient("),
    "pill": ("border-radius: 999", "border-radius: 50%", "rounded-full", "border-radius:100%"),
    "card": ("card-grid", "glass-card", "hero-card"),
    "glow": ("drop-shadow(", "text-shadow:", "box-shadow: 0 0 "),
}
"""Structural detectors for the surface treatments a counter-reference rules out.

These are the patterns that make "not a generic AI dashboard" executable. A
prohibition the worker has to remember is not a prohibition, so each AVOID
treatment becomes a set of literal signatures that a change is checked against.
The list is a floor, not a complete detector, and the docs say so.
"""


def forbidden_pattern_from_avoid(
    *, pattern_id: str, reason: str, reference_id: str, anti_pattern: str, detectors: Sequence[str] = ()
) -> dict:
    """One mechanically checkable prohibition derived from an AVOID treatment."""
    if not str(reason).strip():
        raise ContractError("a forbidden copy pattern must record the reason it exists")
    return {
        "pattern_id": str(pattern_id),
        "reason": str(reason),
        "reference_id": str(reference_id),
        "anti_pattern": str(anti_pattern),
        "detectors": [str(item) for item in detectors],
        "outcome_on_match": "REFERENCE_CLONING",
        "enforced_by": "grounding.classify_change",
        "note": (
            "a reference may inform a direction and must never be reproduced literally; this row is the "
            "machine-checkable form of that refusal"
        ),
    }


def detectors_for_anti_pattern(anti_pattern: str) -> list[str]:
    """Literal signatures implied by a recorded anti-pattern.

    Matching is keyword-driven and deliberately narrow. A false positive here costs
    a legitimate design decision its freedom; a false negative costs the refusal
    its meaning. Under-detecting is the cheaper error, and the record says which
    detectors applied so a reviewer can see the coverage rather than assume it.
    """
    text = str(anti_pattern or "").lower()
    found: list[str] = []
    for key, signatures in _COUNTER_DETECTORS.items():
        if key in text:
            found.extend(signatures)
    return sorted(set(found))


# ------------------------------------------------------------------- compiler

def compile_plan(
    state: dict,
    *,
    direction_id: str,
    reference_set_id: str,
    project_root: str,
    target_surfaces: Sequence[str],
    constraints: Sequence[Mapping] | None = None,
    component_reuse_decisions: Sequence[Mapping] | None = None,
    forbidden_copy_patterns: Sequence[Mapping] | None = None,
    validation_requirements: Sequence[Mapping] | None = None,
    implementation_references: Sequence[Mapping] | None = None,
    borrow_adapt_avoid_bindings: Sequence[Mapping] | None = None,
    created_at: str = "",
    plan_id: str = "",
    note: str = "",
) -> dict:
    """Compile an approved direction into an implementation plan.

    The caller supplies what it inspected; this function decides what may stand.
    Specifically it enforces the four refusals in the module docstring, applies
    precedence, and refuses to record a plan whose validation requirements cannot
    be turned into a bounded argv by the *existing* transport allowlist.

    That last one is not decoration. Validation commands arrive from design
    material, and design material has already been shown to contain instructions
    aimed at execution. Routing them through ``safe_validation_argv`` means a
    reference cannot smuggle ``sh -c`` into the mechanical checks that certify its
    own implementation.
    """
    from .. import design as design_module
    from ..design_reference import sets as sets_module

    if not target_surfaces or not [str(item).strip() for item in target_surfaces]:
        raise ContractError("an implementation plan must name at least one target surface")
    record = design_module.direction(state, direction_id)
    if record is None:
        raise ContractError(f"no design-direction record matches {direction_id!r}")
    binding = approval_binding(state, record)

    grounding = record.get("ar220_grounding") if isinstance(record.get("ar220_grounding"), Mapping) else {}
    derived_set = str(grounding.get("reference_set_id", "")).strip()
    if not derived_set:
        raise ContractError(
            f"direction {direction_id!r} carries no reference-set grounding; it was not built from a "
            "reference set, so a plan claiming one would be asserting a lineage it does not have"
        )
    if derived_set != str(reference_set_id).strip():
        raise ContractError(
            f"the reference set {reference_set_id!r} is not the set direction {direction_id!r} was built "
            f"from ({derived_set!r}); implementing against a different evidence set is a different design"
        )
    set_record = sets_module.reference_set(state, derived_set)
    if set_record is None:
        raise ContractError(f"the reference set {derived_set!r} named by the direction does not exist in this run")

    if constraints is not None and not list(constraints):
        raise ContractError(
            "an implementation plan states no implementation constraint. The approved direction said what "
            "the design is; this is the record that says what the code must do about it, and an empty one "
            "certifies nothing"
        )
    resolved = resolve_precedence(list(constraints or []))
    if not resolved["constraints"]:
        raise ContractError(
            "every proposed implementation constraint was suppressed by precedence, leaving nothing to "
            "implement; report the conflict instead of recording an empty plan"
        )

    validation_rows = _validation_rows(validation_requirements or ())
    if not validation_rows:
        raise ContractError(
            "an implementation plan declares no mechanical validation requirement. Build, typecheck and "
            "test evidence is what separates an implemented design from an asserted one"
        )

    plan = {
        "schema_version": contracts.SCHEMA_DESIGN,
        "plan_id": str(plan_id or contracts.new_record_id("dip")),
        "run_id": str(state.get("run_id", "")),
        "task_id": str(record.get("task_id", "")),
        "direction_id": str(direction_id),
        "reference_set_id": str(derived_set),
        "approval_binding": binding,
        "project_scope": str(project_root),
        "target_surfaces": [str(item) for item in target_surfaces],
        "constraints": resolved["constraints"],
        "suppressed_constraints": resolved["suppressed"],
        "component_reuse_decisions": [dict(row) for row in (component_reuse_decisions or [])],
        "implementation_references": [dict(row) for row in (implementation_references or [])],
        "borrow_adapt_avoid_bindings": [dict(row) for row in (borrow_adapt_avoid_bindings or [])],
        "requirement_bindings": _requirement_bindings(record, grounding),
        "reference_bindings": _reference_bindings(grounding),
        "forbidden_copy_patterns": [dict(row) for row in (forbidden_copy_patterns or [])],
        "validation_requirements": validation_rows,
        "status": "READY",
        "provenance": {
            "created_by": "engine",
            "policy_version": contracts.POLICY_VERSION,
            "direction_grounding": "ar220_grounding",
            "compiler": "design_execution.plan.compile_plan",
        },
        "created_at": str(created_at or contracts.utc_now()),
        "note": str(note),
    }
    problems = contracts.implementation_plan_problems(plan)
    if problems:
        raise ContractError("implementation plan is malformed: " + "; ".join(problems))
    contracts.require_design_capacity(state, "design_implementation_plans")
    state.setdefault("design_implementation_plans", []).append(plan)
    return plan


def _validation_rows(requirements: Sequence[Mapping]) -> list[dict]:
    """Turn declared validation requirements into bounded argv, or refuse.

    Reuses the transport allowlist rather than restating it. A second allowlist
    would be a second policy, and the one Ariadne actually enforces at S4B would
    stop being the one that matters.
    """
    from .. import policy

    transport = policy.transport_tool()
    rows: list[dict] = []
    for requirement in requirements:
        if not isinstance(requirement, Mapping):
            raise ContractError("a validation requirement must be a mapping")
        command = str(requirement.get("command", "")).strip()
        if not command:
            raise ContractError("a validation requirement must name a command")
        argv, reason = transport.safe_validation_argv(command)
        if argv is None:
            raise ContractError(
                f"validation command {command!r} is refused by the transport boundary: {reason}. "
                "Mechanical checks run as a bounded argv, never a shell line"
            )
        rows.append({
            "check_id": str(requirement.get("check_id", "") or contracts.new_record_id("chk")),
            "command": command,
            "argv": list(argv),
            "required": bool(requirement.get("required", True)),
            "expected": str(requirement.get("expected", "exit 0")),
            "kind": str(requirement.get("kind", "mechanical")),
        })
    if not any(row["required"] for row in rows):
        raise ContractError(
            "every declared validation is optional; a plan whose checks may all be skipped cannot "
            "certify anything"
        )
    return rows


def _requirement_bindings(record: Mapping, grounding: Mapping) -> list[dict]:
    """Requirement-level bindings, taken from the direction rather than invented.

    A plan may not claim a requirement binding the approved direction does not
    carry. The binding is a link in the trace, and a link added after
    implementation is a link with nothing behind it.
    """
    rows: list[dict] = []
    for statement in record.get("statements") or []:
        if not isinstance(statement, Mapping):
            continue
        value = str(statement.get("value", "")).strip()
        if not value:
            continue
        rows.append({
            "binding": value,
            "actionable": bool(statement.get("actionable", True)),
            "source": "APPROVED_DIRECTION",
            "direction_id": str(record.get("direction_id", "")),
        })
    goal = str(record.get("goal", "")).strip()
    if goal:
        rows.append({
            "binding": goal,
            "actionable": True,
            "source": "REQUIREMENT",
            "direction_id": str(record.get("direction_id", "")),
        })
    scope = str(grounding.get("reference_set_id", ""))
    if scope:
        rows.append({
            "binding": f"evidence scope: {scope}",
            "actionable": False,
            "source": "REFERENCE_SET",
            "direction_id": str(record.get("direction_id", "")),
        })
    return rows


def _reference_bindings(grounding: Mapping) -> list[dict]:
    """Which reference ids reached the plan, and through what.

    Recorded from the grounding block rather than from the reference set, because
    a set member that informed no constraint is not evidence this plan rests on
    and must not appear in its lineage.
    """
    rows: list[dict] = []
    for principle in grounding.get("principles") or []:
        if not isinstance(principle, Mapping):
            continue
        principle_id = str(principle.get("principle_id", ""))
        for evidence in principle.get("evidence") or []:
            if not isinstance(evidence, Mapping):
                continue
            rows.append({
                "reference_id": str(evidence.get("reference_id", "")),
                "source_identity": str(evidence.get("source_identity", "")),
                "principle_id": principle_id,
                "dimension": str(principle.get("dimension", "")),
                "confidence": str(principle.get("confidence", "")),
            })
    for counter in grounding.get("counter_references") or []:
        if not isinstance(counter, Mapping):
            continue
        rows.append({
            "reference_id": str(counter.get("reference_id", "")),
            "source_identity": "counter-reference",
            "principle_id": "",
            "dimension": "counter-pattern",
            "confidence": "RULES_OUT",
        })
    return rows


# ------------------------------------------------------------------- accessors

def plans(state: Mapping) -> list[dict]:
    values = state.get("design_implementation_plans")
    if not isinstance(values, list):
        return []
    return [dict(item) for item in values if isinstance(item, Mapping)]


def plan(state: Mapping, plan_id: str) -> dict | None:
    for record in plans(state):
        if str(record.get("plan_id", "")) == str(plan_id):
            return record
    return None


def latest_plan(state: Mapping, *, task_id: str = "") -> dict:
    rows = [
        record for record in plans(state)
        if not task_id or str(record.get("task_id", "")) == str(task_id)
    ]
    return rows[-1] if rows else {}


def plan_problems(state: Mapping, *, plan_id: str = "") -> list[str]:
    """Structural and cross-record checks over every plan in the run.

    The cross-record half is what makes the trace queryable rather than decorative:
    a plan whose approval has since been consumed, or whose direction no longer
    matches the approval bound to it, is reported here instead of being trusted by
    whatever reads it next.
    """
    from .. import design as design_module

    problems: list[str] = []
    rows = plans(state)
    if plan_id:
        rows = [record for record in rows if str(record.get("plan_id", "")) == str(plan_id)]
    seen: set[str] = set()
    for record in rows:
        identifier = str(record.get("plan_id", ""))
        if identifier in seen:
            problems.append(f"duplicate implementation plan id: {identifier}")
        seen.add(identifier)
        problems.extend(contracts.implementation_plan_problems(record))
        binding = record.get("approval_binding") if isinstance(record.get("approval_binding"), Mapping) else {}
        direction = design_module.direction(dict(state), str(record.get("direction_id", "")))
        if direction is None:
            problems.append(
                f"implementation plan {identifier} names direction {record.get('direction_id')!r}, "
                "which does not exist in this run"
            )
            continue
        current = contracts.direction_fingerprint(direction)
        if current != str(binding.get("direction_revision_hash", "")):
            problems.append(
                f"implementation plan {identifier} is stale: its direction now fingerprints "
                f"{current[:12]}… while the plan was approved against "
                f"{str(binding.get('direction_revision_hash', ''))[:12]}…"
            )
    return list(dict.fromkeys(problems))


def constraint_index(record: Mapping) -> dict[str, Mapping]:
    """Constraint id -> constraint, for the change recorder and the trace."""
    return {
        str(row.get("constraint_id", "")): row
        for row in record.get("constraints") or []
        if isinstance(row, Mapping) and str(row.get("constraint_id", ""))
    }


def summarise(record: Mapping) -> str:
    """A short human view of what a plan obliges and why."""
    binding = record.get("approval_binding") if isinstance(record.get("approval_binding"), Mapping) else {}
    constraints = [row for row in record.get("constraints") or [] if isinstance(row, Mapping)]
    bases: dict[str, int] = {}
    for row in constraints:
        basis = str(row.get("basis", ""))
        bases[basis] = bases.get(basis, 0) + 1
    lines = [
        f"Implementation plan {record.get('plan_id')}  status: {record.get('status')}",
        f"  direction:   {record.get('direction_id')} (approved via {binding.get('gate')} "
        f"{binding.get('approval_id')})",
        f"  references:  {record.get('reference_set_id')}",
        f"  surfaces:    {', '.join(str(item) for item in record.get('target_surfaces') or [])}",
        f"  constraints: {len(constraints)} (" + ", ".join(
            f"{basis} {count}" for basis, count in sorted(bases.items(), key=lambda item: -item[1])
        ) + ")",
    ]
    suppressed = [row for row in record.get("suppressed_constraints") or [] if isinstance(row, Mapping)]
    if suppressed:
        lines.append(f"  suppressed by precedence: {len(suppressed)}")
        for row in suppressed:
            lines.append(f"    - {row.get('outcome')}: {row.get('reason')}")
    forbidden = [row for row in record.get("forbidden_copy_patterns") or [] if isinstance(row, Mapping)]
    if forbidden:
        lines.append(f"  forbidden:   {len(forbidden)}")
        for row in forbidden:
            lines.append(f"    - {row.get('pattern_id')}: {row.get('anti_pattern')}")
    reuse = [row for row in record.get("component_reuse_decisions") or [] if isinstance(row, Mapping)]
    if reuse:
        lines.append(f"  components:  {len(reuse)}")
        for row in reuse:
            lines.append(f"    - {row.get('need')}: {row.get('decision')}")
    lines.append(f"  validation:  " + ", ".join(
        str(row.get("command", "")) for row in record.get("validation_requirements") or []
        if isinstance(row, Mapping)
    ))
    return "\n".join(lines)


__all__ = [
    "ACCESSIBILITY_CATEGORIES",
    "PLAN_GATE",
    "approval_binding",
    "compile_plan",
    "constraint",
    "constraint_index",
    "detectors_for_anti_pattern",
    "forbidden_pattern_from_avoid",
    "latest_plan",
    "plan",
    "plan_problems",
    "plans",
    "resolve_precedence",
    "summarise",
]