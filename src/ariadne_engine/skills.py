"""The native engineering skill registry and deterministic selection (Ariadne 2.3A).

What this module is, and what it is not
---------------------------------------
This is a registry of *executable agent skills*: methods with a purpose, a
precondition, a capability requirement, a loading cost and an expected evidence
output. It is deliberately not any of the three things it resembles:

* it is **not** ``references/capabilities.json`` — that registry describes UI
  libraries a design task may use, and it can never authorise an install;
* it is **not** :mod:`ariadne_engine.capabilities` — that module records what an
  *adapter* proved it can do, as evidence;
* it is **not** the creative plan in ``scripts/creative-intelligence.py`` — the
  full-project workflow keeps its own skill selection, and this module delegates
  to it rather than competing with it.

Selection is deterministic and cheap on purpose: no model call is made, no
document content is read to decide anything, and a candidate is described only
by the metadata below. Full skill instructions are loaded only for selected
skills, so an unselected skill never spends the worker's context.

The rules the selector enforces, in order:

1. only skills that apply to the task's intent family are candidates;
2. a skill whose required capability the host did not declare available is
   excluded, and the exclusion is recorded as a gap rather than hidden;
3. a skill that writes is excluded from a read-only task;
4. a skill that needs the review boundary is excluded when the plan does not
   retain review;
5. a creative-project skill cannot be selected into a lightweight task workflow
   (and vice versa): a small task must not silently pick up a design thesis;
6. externally sourced instructions are untrusted until explicitly approved by a
   human, and are never selected by default;
7. declared incompatibilities and competing strategy-slot values refuse the
   selection instead of producing contradictory instructions.

Everything a caller can inspect is in the returned record: chosen skills with
reasons, exclusions with reasons, required capabilities, unresolved gaps, the
documents that would be loaded and their measured cost.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Mapping, Sequence

from . import contracts, tooling
from .contracts import ContractError

SELECTION_POLICY = "task-skill-selection-1"

WORKFLOW_PROJECT = "project"
WORKFLOW_TASK = "task"
WORKFLOWS = (WORKFLOW_PROJECT, WORKFLOW_TASK, "any")

READ_ONLY = "read-only"
STANDARD = "standard"
PERMISSIONS = (READ_ONLY, STANDARD)

NATIVE_SOURCE = "native"
EXTERNAL_SOURCE = "external"

DOCUMENTS_MEASURED_CACHE: dict[str, int] = {}
"""Measured document sizes for the current process; reading a size writes nothing."""

STRATEGY_SLOTS = ("investigation", "change-strategy")
"""Named strategy slots. Two selected skills may not disagree inside one slot."""


def _entry(
    skill_id: str,
    *,
    version: str,
    title: str,
    purpose: str,
    workflows: tuple[str, ...],
    families: tuple[str, ...],
    mandatory_for: tuple[str, ...] = (),
    requires_capabilities: tuple[str, ...] = (),
    permission: str = READ_ONLY,
    preconditions: tuple[str, ...] = (),
    tools: tuple[str, ...] = (),
    context: tuple[str, ...] = (),
    outputs: tuple[str, ...] = (),
    evidence: tuple[str, ...] = (),
    incompatibilities: tuple[str, ...] = (),
    strategy_slots: dict | None = None,
    source: str = NATIVE_SOURCE,
    owner: str = "Ariadne",
) -> dict:
    return {
        "id": skill_id,
        "version": version,
        "title": title,
        "purpose": purpose,
        "workflows": tuple(workflows),
        "families": tuple(families),
        "mandatory_for": tuple(mandatory_for),
        "requires_capabilities": tuple(requires_capabilities),
        "permission": permission,
        "preconditions": tuple(preconditions),
        "tools": tuple(tools),
        "context": tuple(context),
        "outputs": tuple(outputs),
        "evidence": tuple(evidence),
        "incompatibilities": tuple(incompatibilities),
        "strategy_slots": dict(strategy_slots or {}),
        "source": source,
        "owner": owner,
    }


SKILL_REGISTRY: dict[str, dict] = {
    # ------------------------------------------------- native engineering skills
    "root-cause": _entry(
        "root-cause",
        version="1.0.0",
        title="Root-cause investigation",
        purpose=(
            "Reproduce a failure and trace the mechanism that produces it before any fix "
            "is written; a fix without a cause is a guess with better formatting."
        ),
        workflows=(WORKFLOW_TASK,),
        families=("bug",),
        mandatory_for=("bug",),
        requires_capabilities=("read", "search"),
        permission=READ_ONLY,
        preconditions=("a failure report or a symptom that can be reproduced",),
        tools=("shell",),
        context=("skills/root-cause.md",),
        outputs=("a recorded reproduction and the failing mechanism",),
        evidence=("the reproduction command or steps", "the traced cause with its file anchor"),
        strategy_slots={"investigation": "diagnosis"},
    ),
    "blast-radius": _entry(
        "blast-radius",
        version="1.0.0",
        title="Blast-radius analysis",
        purpose=(
            "Establish which callers, consumers and behaviours a change can break before "
            "it is made, so the change is scoped to its real surface."
        ),
        workflows=(WORKFLOW_TASK,),
        families=("bug", "feature", "refactor", "performance", "audit", "ui-redesign"),
        requires_capabilities=("read", "search"),
        permission=READ_ONLY,
        preconditions=("an identified change surface or a named subsystem",),
        context=("skills/blast-radius.md",),
        outputs=("the affected consumers and the regression surface",),
        evidence=("the search that found the consumers", "the behaviours at risk, named"),
        strategy_slots={"change-strategy": "bounded"},
    ),
    "behavior-tests": _entry(
        "behavior-tests",
        version="1.0.0",
        title="Behaviour-focused implementation",
        purpose=(
            "Express the required behaviour as a test that can fail, then make the change "
            "that makes it pass; meaningful tests where the project can run them."
        ),
        workflows=(WORKFLOW_TASK,),
        families=("bug", "feature", "refactor"),
        requires_capabilities=("read", "edit", "shell"),
        permission=STANDARD,
        preconditions=("the project can run a test or check command",),
        tools=("shell",),
        context=("skills/behavior-tests.md",),
        outputs=("a failing-then-passing check, or a recorded reason no executable check exists",),
        evidence=("the test command and its result", "the behaviour it binds"),
        strategy_slots={"change-strategy": "bounded"},
    ),
    "architecture-evaluation": _entry(
        "architecture-evaluation",
        version="1.0.0",
        title="Architecture evaluation",
        purpose=(
            "Compare plausible structural approaches against the project's real constraints "
            "and prefer the simplest structure that satisfies them."
        ),
        workflows=(WORKFLOW_TASK,),
        families=("feature", "refactor"),
        requires_capabilities=("read", "search"),
        permission=READ_ONLY,
        preconditions=("more than one plausible structure is on the table",),
        context=("skills/architecture-evaluation.md",),
        outputs=("the compared approaches with the chosen one and why",),
        evidence=("each rejected approach and the constraint that rejects it",),
        strategy_slots={"change-strategy": "bounded"},
    ),
    "adversarial-review": _entry(
        "adversarial-review",
        version="1.0.0",
        title="Adversarial code review",
        purpose=(
            "Challenge the implementation's assumptions with an independent read that tries "
            "to falsify the change, not to confirm it."
        ),
        workflows=(WORKFLOW_TASK,),
        families=("bug", "feature", "refactor", "performance", "audit", "ui-redesign"),
        requires_capabilities=("read", "search"),
        permission=READ_ONLY,
        preconditions=("review independence is enforced by the workflow boundary",),
        context=("skills/adversarial-review.md",),
        outputs=("ranked falsification attempts with evidence, or none found",),
        evidence=("each attempt and what actually happened when it was tried",),
    ),
    "performance-investigation": _entry(
        "performance-investigation",
        version="1.0.0",
        title="Performance investigation",
        purpose=(
            "Establish a measured baseline, state a hypothesis, change one thing and measure "
            "again; an unmeasured optimisation is a preference."
        ),
        workflows=(WORKFLOW_TASK,),
        families=("performance",),
        mandatory_for=("performance",),
        requires_capabilities=("read", "shell"),
        permission=READ_ONLY,
        preconditions=("a runnable workload or an observable measurement can be taken",),
        tools=("shell",),
        context=("skills/performance-investigation.md",),
        outputs=("a before/after measurement for the changed path",),
        evidence=("the baseline command and numbers", "the same measurement after the change"),
        strategy_slots={"investigation": "measurement"},
    ),
    "anti-slop": _entry(
        "anti-slop",
        version="1.0.0",
        title="Anti-slop engineering",
        purpose=(
            "Keep the change as small and as honest as the problem allows: no speculative "
            "abstraction, no duplicated logic, no weakened typing, no unearned complexity."
        ),
        workflows=(WORKFLOW_TASK,),
        families=("bug", "feature", "refactor", "performance", "audit", "ui-redesign"),
        mandatory_for=("bug", "feature", "refactor", "performance", "ui-redesign"),
        requires_capabilities=(),
        permission=READ_ONLY,
        context=("skills/anti-slop.md",),
        outputs=("a change proportional to the problem",),
        evidence=("the diff size and the reason each touched file had to change",),
        strategy_slots={"change-strategy": "bounded"},
    ),
    "engineering-reflection": _entry(
        "engineering-reflection",
        version="1.0.0",
        title="Engineering reflection",
        purpose=(
            "Turn a repeated error into a durable correction: a regression test, a rule, or "
            "a skill improvement, recorded where the next run will see it."
        ),
        workflows=(WORKFLOW_TASK,),
        families=("bug", "refactor", "performance", "audit"),
        requires_capabilities=("read",),
        permission=READ_ONLY,
        preconditions=("a failure class, repair, or finding is already recorded",),
        context=("skills/engineering-reflection.md",),
        outputs=("one durable correction bound to the repeated error",),
        evidence=("the repeated error and the test or rule that now catches it",),
    ),
    # ------------------------------------------------- existing Ariadne methods
    "intake": _entry(
        "intake",
        version="1.0.0",
        title="Project intake",
        purpose="Turn a vague request into a scoped, falsifiable project.",
        workflows=(WORKFLOW_PROJECT,),
        families=("new-project",),
        requires_capabilities=(),
        context=("skills/intake.md",),
        outputs=("the project brief and its constraints",),
        evidence=("the brief with its non-goals and success criteria",),
        owner="Ariadne creative workflow",
    ),
    "reference-analysis": _entry(
        "reference-analysis",
        version="1.0.0",
        title="Reference analysis",
        purpose="Study an inspected reference and extract applicability, not imitation.",
        workflows=(WORKFLOW_PROJECT,),
        families=("new-project", "ui-redesign"),
        requires_capabilities=(),
        context=("skills/reference-analysis.md",),
        outputs=("source-to-decision evidence for the design direction",),
        evidence=("an inspected source and the decision it changed",),
        owner="Ariadne creative workflow",
    ),
    "component-research": _entry(
        "component-research",
        version="1.0.0",
        title="Component research",
        purpose="Walk the minimum-solution ladder before proposing any dependency.",
        workflows=(WORKFLOW_PROJECT, WORKFLOW_TASK),
        families=("new-project", "feature"),
        requires_capabilities=(),
        context=("skills/component-research.md",),
        outputs=("a capability decision that never grants the G2 gate",),
        evidence=("the current registered capability and the rejected alternatives",),
        owner="Ariadne creative workflow",
    ),
    "design-direction": _entry(
        "design-direction",
        version="1.0.0",
        title="Design direction",
        purpose="Produce an original design thesis specific enough that a template would fail it.",
        workflows=(WORKFLOW_PROJECT,),
        families=("new-project",),
        requires_capabilities=(),
        context=("skills/design-direction.md",),
        outputs=("the design thesis presented at G1",),
        evidence=("the thesis, its rejects, and the human G1 decision",),
        owner="Ariadne creative workflow",
    ),
    "visual-qa": _entry(
        "visual-qa",
        version="1.0.0",
        title="Visual QA",
        purpose="Record rendered evidence and material drift against the approved direction.",
        workflows=(WORKFLOW_PROJECT, WORKFLOW_TASK),
        families=("ui-redesign", "new-project"),
        requires_capabilities=("capture",),
        preconditions=("an approved direction exists and a rendered target can be inspected",),
        context=("skills/visual-qa.md",),
        outputs=("hashed visual evidence and drift findings",),
        evidence=("the observation, its viewport, and the requirement it was compared against",),
        owner="Ariadne creative workflow",
    ),
    "creative-review": _entry(
        "creative-review",
        version="1.0.0",
        title="Creative review",
        purpose="Judge finished work as the audience will, from an isolated context.",
        workflows=(WORKFLOW_PROJECT,),
        families=("new-project",),
        requires_capabilities=(),
        context=("skills/creative-review.md",),
        outputs=("scored rubrics, ranked findings, one recommendation",),
        evidence=("the isolated review judgement and its findings",),
        owner="Ariadne creative workflow",
    ),
    "social-strategy": _entry(
        "social-strategy",
        version="1.0.0",
        title="Social content strategy",
        purpose="Research distribution only when the human explicitly asks for it.",
        workflows=(WORKFLOW_PROJECT,),
        families=(),
        requires_capabilities=(),
        context=("skills/social-strategy.md",),
        outputs=("the finished social artifact and its source evidence",),
        evidence=("SOURCE -> FINDING -> DECISION records",),
        owner="Ariadne creative workflow",
    ),
}

def registry_view() -> dict:
    """The registry as data, without document content."""
    return {
        "policy": SELECTION_POLICY,
        "slots": list(STRATEGY_SLOTS),
        "skills": [
            {
                key: (list(value) if isinstance(value, tuple) else value)
                for key, value in sorted(SKILL_REGISTRY[skill_id].items())
            }
            for skill_id in sorted(SKILL_REGISTRY)
        ],
        "count": len(SKILL_REGISTRY),
    }


def registry_problems(registry: Mapping | None = None, *, root: Path | None = None) -> list[str]:
    """Structural validation of the registry itself.

    A malformed registry is refused before it can drive a selection: an entry
    without an applicability list, a capability that no host vocabulary defines,
    a document that does not exist, an incompatibility naming a missing skill, or
    two entries disagreeing inside one strategy slot are all detectable here.
    """
    skills = dict(registry or SKILL_REGISTRY)
    problems: list[str] = []
    known_capabilities = set(tooling.CORE_CAPABILITIES) | {
        "capture", "reference-research", "design-direction",
    }
    for skill_id, entry in sorted(skills.items()):
        if str(entry.get("id", "")) != skill_id:
            problems.append(f"skill {skill_id!r} declares a different id")
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", str(skill_id)):
            problems.append(f"skill id is not a stable identifier: {skill_id!r}")
        if not re.fullmatch(r"\d+\.\d+\.\d+", str(entry.get("version", ""))):
            problems.append(f"skill {skill_id} has no semantic version")
        if not str(entry.get("purpose", "")).strip():
            problems.append(f"skill {skill_id} has no purpose")
        workflows = tuple(entry.get("workflows") or ())
        if not workflows or any(item not in WORKFLOWS for item in workflows):
            problems.append(f"skill {skill_id} declares an unknown workflow: {workflows}")
        if str(entry.get("permission", "")) not in PERMISSIONS:
            problems.append(f"skill {skill_id} declares an unknown permission level")
        if not tuple(entry.get("families") or ()) and entry.get("mandatory_for"):
            problems.append(f"skill {skill_id} is mandatory for families it does not declare")
        for family in tuple(entry.get("mandatory_for") or ()):
            if family not in tuple(entry.get("families") or ()):
                problems.append(f"skill {skill_id} is mandatory for undeclared family {family!r}")
        for capability in tuple(entry.get("requires_capabilities") or ()):
            if str(capability) not in known_capabilities:
                problems.append(
                    f"skill {skill_id} requires capability {capability!r}, which no host vocabulary declares"
                )
        for other in tuple(entry.get("incompatibilities") or ()):
            if str(other) not in skills:
                problems.append(f"skill {skill_id} is incompatible with unknown skill {other!r}")
        for slot, value in dict(entry.get("strategy_slots") or {}).items():
            if slot not in STRATEGY_SLOTS:
                problems.append(f"skill {skill_id} claims unknown strategy slot {slot!r}")
        if root is not None:
            for document in tuple(entry.get("context") or ()):
                if not (Path(root) / str(document)).is_file():
                    problems.append(f"skill {skill_id} names a missing skill document: {document}")
    for skill_id, entry in sorted(skills.items()):
        for other in tuple(entry.get("incompatibilities") or ()):
            if str(other) in skills and skill_id not in tuple(skills[str(other)].get("incompatibilities") or ()):
                problems.append(
                    f"incompatibility {skill_id} -> {other} is one-sided; both entries must declare it"
                )
    return problems


def host_capabilities(declared: Mapping | Sequence | None = None) -> dict:
    """The capability set the host actually provides, as declared.

    Without a declaration the runtime's own core contract is the declared
    default: read, search, edit, shell and the return handoff are the
    capabilities every implementation stage needs on its first turn
    (:data:`tooling.CORE_CAPABILITIES`). A caller that knows better passes its
    own set, and a capability that is absent is *absent*, never assumed.
    """
    if declared is None:
        values = {str(item): {"status": "DECLARED", "source": "ariadne-core-contract"}
                  for item in tooling.CORE_CAPABILITIES}
        return {"values": values, "source": "ariadne-core-contract"}
    if isinstance(declared, Mapping):
        values = {}
        for name, status in declared.items():
            text = str(status)
            values[str(name)] = {
                "status": "UNAVAILABLE" if text.lower() in ("unavailable", "absent", "no") else "DECLARED",
                "source": "host-declared",
            }
        return {"values": values, "source": "host-declared"}
    values = {str(item): {"status": "DECLARED", "source": "host-declared"} for item in declared}
    return {"values": values, "source": "host-declared"}


def _applicable(entry: Mapping, family: str) -> bool:
    return str(family) in tuple(entry.get("families") or ())


def _capability_exclusions(entry: Mapping, host: Mapping) -> list[dict]:
    gaps = []
    values = dict(host.get("values") or {})
    for capability in tuple(entry.get("requires_capabilities") or ()):
        status = str((values.get(str(capability)) or {}).get("status", ""))
        if status != "DECLARED":
            gaps.append({
                "capability": str(capability),
                "skill": str(entry.get("id", "")),
                "reason": (
                    f"the host did not declare {capability!r} available "
                    f"(recorded as {status or 'absent'})"
                ),
            })
    return gaps


def select_skills(
    *,
    intent_family: str = "",
    workflow: str = WORKFLOW_TASK,
    characterisation: Mapping | None = None,
    plan: Mapping | None = None,
    host: Mapping | None = None,
    explicit: Sequence[str] = (),
    approved_external: Sequence[str] = (),
    limit: int = 6,
    registry: Mapping | None = None,
    run_id: str = "",
    task_id: str = "",
) -> dict:
    """Choose the skills one task needs, and record every decision.

    The record distinguishes four different things that are easy to conflate:

    * ``selected`` — a skill the task will use, with the reason it was chosen;
    * ``excluded`` — a candidate the rules refused, with the exact reason;
    * ``gaps`` — a capability the task needs that the host did not declare, which
      is a report to the caller, never a silent downgrade;
    * ``delegated_to`` — for a full-project workflow, the existing creative plan
      remains the owner of creative skill selection.

    Contradictions do not throw: they set ``status`` to ``refused`` with an
    explicit ``conflicts`` list, so the caller can show the operator what
    disagreed instead of an unexplained stop.
    """
    skills = dict(registry or SKILL_REGISTRY)
    problems = registry_problems(skills)
    if problems:
        raise ContractError("the skill registry is malformed: " + "; ".join(problems))
    if str(workflow) not in WORKFLOWS:
        raise ContractError(f"unknown skill workflow: {workflow!r}")
    host_view = host if isinstance(host, Mapping) and "values" in host else host_capabilities(host)
    requested = {str(item) for item in explicit}
    approved = {str(item) for item in approved_external}
    for skill_id in sorted(requested):
        if skill_id not in skills:
            raise ContractError(f"skill selection names an unknown skill: {skill_id!r}")

    record = {
        "schema_version": contracts.SCHEMA_ADAPTIVE,
        "selection_id": contracts.new_record_id("skl"),
        "run_id": str(run_id),
        "task_id": str(task_id),
        "intent": str(intent_family),
        "workflow": str(workflow),
        "policy": SELECTION_POLICY,
        "selected": [],
        "excluded": [],
        "required_capabilities": [],
        "host_capabilities": {
            str(name): str(value.get("status"))
            for name, value in sorted(dict(host_view.get("values") or {}).items())
        },
        "gaps": [],
        "context": {"documents": [], "bytes": 0, "loading": "selected-only"},
        "conflicts": [],
        "delegated_to": "",
        "status": "selected",
        "policy_version": contracts.POLICY_VERSION,
        "recorded_at": contracts.utc_now(),
    }

    if workflow == WORKFLOW_PROJECT:
        record["delegated_to"] = "scripts/creative-intelligence.py:creative-plan"
        record["status"] = "selected"
        for skill_id in sorted(skills):
            record["excluded"].append({
                "id": skill_id,
                "reasons": [
                    "the full-project workflow keeps its own skill selection; "
                    "the creative plan remains the single owner"
                ],
            })
        return record

    characterisation = characterisation if isinstance(characterisation, Mapping) else {}
    plan = plan if isinstance(plan, Mapping) else {}
    review_retained = "review" in {str(item) for item in (plan.get("retained") or ())}
    read_only = str(plan.get("write_authorization", "")) == "none"
    difficulty = str((characterisation.get("difficulty") or {}).get("value", "UNKNOWN"))
    stakes = str((characterisation.get("stakes") or {}).get("value", "UNKNOWN"))
    scope = str((characterisation.get("expected_change_scope") or {}).get("value", "UNKNOWN"))
    elevated = (
        difficulty == "HIGH"
        or stakes == "HIGH"
        or scope == "multi-file"
        or bool((plan.get("review") or {}).get("required"))
    )

    selected: dict[str, dict] = {}
    for skill_id in sorted(skills):
        entry = skills[skill_id]
        reasons: list[str] = []
        mandatory = str(intent_family) in tuple(entry.get("mandatory_for") or ())
        applies = _applicable(entry, intent_family) or skill_id in requested
        if str(entry.get("source")) != NATIVE_SOURCE and skill_id not in approved:
            record["excluded"].append({
                "id": skill_id,
                "reasons": [
                    "externally sourced skill instructions are untrusted until a human "
                    "explicitly approves them"
                ],
            })
            if applicable_gap := _capability_exclusions(entry, host_view):
                record["gaps"].extend(applicable_gap)
            continue
        if not applies:
            if mandatory:
                record["conflicts"].append({
                    "skill": skill_id,
                    "reason": f"registry marks {skill_id} mandatory for a family it does not declare",
                })
            else:
                # An entry that is not applicable is still accounted for, so an
                # empty selection reads as "nothing applies", never as "nothing
                # was considered".
                record["excluded"].append({
                    "id": skill_id,
                    "reasons": [f"does not apply to intent family {intent_family!r}"],
                })
            continue
        if str(workflow) not in tuple(entry.get("workflows") or ()):
            record["excluded"].append({
                "id": skill_id,
                "reasons": [
                    f"{skill_id} belongs to the {tuple(entry.get('workflows') or ())} workflow; "
                    f"selecting it into a {workflow} task would contradict the task's own workflow"
                ],
            })
            continue
        if read_only and str(entry.get("permission")) == STANDARD:
            record["excluded"].append({
                "id": skill_id,
                "reasons": ["the task is read-only and this skill requires write authorisation"],
            })
            continue
        if skill_id == "adversarial-review" and not review_retained and not mandatory:
            record["excluded"].append({
                "id": skill_id,
                "reasons": ["the path plan does not retain the review boundary for this task"],
            })
            continue
        gaps = _capability_exclusions(entry, host_view)
        if gaps:
            record["gaps"].extend(gaps)
            record["excluded"].append({
                "id": skill_id,
                "reasons": [item["reason"] for item in gaps],
            })
            continue
        externally_approved = (
            str(entry.get("source")) == EXTERNAL_SOURCE and skill_id in approved
        )
        chosen_by_rule = (
            mandatory
            or skill_id in requested
            or externally_approved
            or _default_selected(skill_id, entry, elevated=elevated, review_retained=review_retained)
        )
        if not chosen_by_rule:
            record["excluded"].append({
                "id": skill_id,
                "reasons": [
                    "relevant to this task family but not required at this difficulty, stakes, or scope"
                ],
            })
            continue
        reason = (
            "mandatory for this intent family" if mandatory
            else "explicitly requested" if skill_id in requested
            else (
                "approved external skill whose declared families match this task"
                if externally_approved
                else _default_reason(skill_id, entry, elevated=elevated, review_retained=review_retained)
            )
        )
        selected[skill_id] = {
            "id": skill_id,
            "version": str(entry.get("version", "")),
            "title": str(entry.get("title", "")),
            "mandatory": bool(mandatory),
            "reason": reason,
            "permission": str(entry.get("permission", "")),
            "capabilities": [str(item) for item in (entry.get("requires_capabilities") or ())],
            "documents": [str(item) for item in (entry.get("context") or ())],
        }

    if len(selected) > int(limit):
        record["conflicts"].append({
            "skill": "selection-limit",
            "reason": (
                f"{len(selected)} skills are required or requested but the loading limit is {int(limit)}; "
                "reduce the task or raise the limit deliberately"
            ),
        })
    for skill_id, chosen in sorted(selected.items()):
        for other in tuple(skills[skill_id].get("incompatibilities") or ()):
            if str(other) in selected:
                record["conflicts"].append({
                    "skill": skill_id,
                    "reason": f"{skill_id} and {other} declare each other incompatible for one task",
                })
    slot_values: dict[str, dict[str, str]] = {}
    for skill_id, chosen in sorted(selected.items()):
        for slot, value in dict(skills[skill_id].get("strategy_slots") or {}).items():
            previous = slot_values.setdefault(str(slot), {})
            if previous and value not in previous.values():
                record["conflicts"].append({
                    "skill": skill_id,
                    "reason": (
                        f"strategy slot {slot!r} already holds {sorted(set(previous.values()))} "
                        f"and {skill_id} declares {value!r}"
                    ),
                })
            previous[skill_id] = str(value)
    if record["conflicts"]:
        record["status"] = "refused"
        record["selected"] = []
        return record

    record["selected"] = [selected[skill_id] for skill_id in sorted(selected)]
    record["required_capabilities"] = sorted({
        capability
        for entry in record["selected"]
        for capability in entry.get("capabilities", [])
    })
    seen_gap: set[tuple[str, str]] = set()
    unique_gaps = []
    for gap in record["gaps"]:
        key = (str(gap.get("capability", "")), str(gap.get("skill", "")))
        if key in seen_gap:
            continue
        seen_gap.add(key)
        unique_gaps.append(gap)
    record["gaps"] = unique_gaps
    return record


def _default_selected(skill_id: str, entry: Mapping, *, elevated: bool, review_retained: bool) -> bool:
    """The non-mandatory defaults, one rule per skill, all of them stated."""
    if skill_id == "blast-radius":
        return bool(elevated)
    if skill_id == "behavior-tests":
        return True
    if skill_id == "architecture-evaluation":
        return bool(elevated)
    if skill_id == "adversarial-review":
        return bool(review_retained)
    if skill_id == "visual-qa":
        return True
    if skill_id == "engineering-reflection":
        return False
    return False


def _default_reason(skill_id: str, entry: Mapping, *, elevated: bool, review_retained: bool) -> str:
    if skill_id == "blast-radius":
        return "difficulty, stakes, or change scope make a regression surface worth mapping"
    if skill_id == "behavior-tests":
        return "the change can be bound to an executable behaviour; a test is the cheapest proof"
    if skill_id == "architecture-evaluation":
        return "the task is complex enough that more than one structure is plausible"
    if skill_id == "adversarial-review":
        return "the path plan retains the review boundary and this skill is its method"
    if skill_id == "visual-qa":
        return "the task changes what renders; evidence compared to the approved direction is how that is judged"
    if skill_id == "engineering-reflection":
        return "a repeated failure class is recorded for this task"
    return "selected by rule"


def selection_problems(record: Mapping) -> list[str]:
    """Structural validation of one selection record (fail closed)."""
    problems = contracts.adaptive_schema_problems(record)
    if problems and not isinstance(record, Mapping):
        return problems
    if not re.fullmatch(r"skl_[0-9TZ]+_[0-9a-f]{8}", str(record.get("selection_id", ""))):
        problems.append("skill selection has a malformed selection id")
    for name in ("workflow", "policy", "policy_version", "recorded_at"):
        if not str(record.get(name, "")).strip():
            problems.append(f"skill selection has no {name}")
    if str(record.get("status", "")) not in ("selected", "refused"):
        problems.append(f"skill selection has an unsupported status: {record.get('status')!r}")
    if record.get("status") == "refused" and not record.get("conflicts"):
        problems.append("a refused skill selection records no conflict")
    if record.get("status") == "selected":
        for entry in record.get("selected") or ():
            if not isinstance(entry, Mapping) or not str(entry.get("id", "")).strip():
                problems.append("skill selection has a malformed selected entry")
                break
            if not str(entry.get("reason", "")).strip():
                problems.append(f"selected skill {entry.get('id')} records no reason")
                break
    for entry in record.get("excluded") or ():
        if not isinstance(entry, Mapping) or not str(entry.get("id", "")).strip():
            problems.append("skill selection has a malformed exclusion entry")
            break
        if not entry.get("reasons"):
            problems.append(f"excluded skill {entry.get('id')} records no reason")
            break
    context = record.get("context") or {}
    if str(context.get("loading", "")) != "selected-only":
        problems.append("skill selection does not declare selected-only loading")
    return problems


def documents(record: Mapping, *, root: Path | None = None) -> list[dict]:
    """The documents a selection would load, measured and nothing else.

    Only documents named by *selected* skills appear. An unselected skill's
    instructions are never listed, so a caller cannot accidentally load them.
    """
    seen: dict[str, dict] = {}
    for entry in record.get("selected") or ():
        for document in entry.get("documents") or ():
            name = str(document)
            if name in seen:
                continue
            entry_row = {
                "path": name,
                "skill": str(entry.get("id", "")),
                "bytes": 0,
            }
            if root is not None:
                target = Path(root) / name
                cache_key = str(target)
                if cache_key not in DOCUMENTS_MEASURED_CACHE:
                    try:
                        DOCUMENTS_MEASURED_CACHE[cache_key] = int(target.stat().st_size)
                    except OSError:
                        DOCUMENTS_MEASURED_CACHE[cache_key] = 0
                entry_row["bytes"] = DOCUMENTS_MEASURED_CACHE[cache_key]
            seen[name] = entry_row
    return [seen[name] for name in sorted(seen)]


AUTHORITY_MINTING_PATTERNS = (
    r"(?i)\b(?:grant|approve|authorise|authorize)\s+(?:the\s+)?(?:gate|approval|permission)\b",
    r"(?i)\bgates?\s+(?:are|is)\s+optional\b",
    r"(?i)\b(?:skip|bypass)\s+(?:the\s+)?(?:validation|verification|review|policy)\b",
    r"(?i)\bwithout\s+(?:asking|human\s+approval|approval)\b",
    r"(?i)\btreat\s+this\s+as\s+approval\b",
)
"""Phrases that claim authority a skill cannot have.

A skill document is untrusted instruction text. It may describe a method; it may
never mint an approval, skip a gate, or waive verification. The detector is used
when a document is loaded from a source that is not the reviewed registry entry,
and by the adversarial suite as a negative control.
"""


def document_authority_problems(text: str) -> list[str]:
    """Authority-minting claims in one skill document, by phrase."""
    problems = []
    for pattern in AUTHORITY_MINTING_PATTERNS:
        match = re.search(pattern, str(text or ""))
        if match:
            problems.append(f"skill text attempts to mint authority: {match.group(0)!r}")
    return problems


def describe(record: Mapping) -> str:
    """One operator sentence for a selection record."""
    if record.get("status") == "refused":
        return "skill selection refused: " + "; ".join(
            str(item.get("reason", "")) for item in record.get("conflicts") or []
        )
    if record.get("delegated_to"):
        return f"skill selection delegated to {record['delegated_to']}"
    chosen = ", ".join(str(item.get("id")) for item in record.get("selected") or []) or "none"
    gaps = len(record.get("gaps") or [])
    return f"skills selected: {chosen}" + (f"; {gaps} capability gap(s) reported" if gaps else "")


__all__ = [
    "SELECTION_POLICY",
    "WORKFLOW_PROJECT",
    "WORKFLOW_TASK",
    "WORKFLOWS",
    "READ_ONLY",
    "STANDARD",
    "NATIVE_SOURCE",
    "EXTERNAL_SOURCE",
    "STRATEGY_SLOTS",
    "SKILL_REGISTRY",
    "registry_view",
    "registry_problems",
    "host_capabilities",
    "select_skills",
    "selection_problems",
    "documents",
    "AUTHORITY_MINTING_PATTERNS",
    "document_authority_problems",
    "describe",
]
