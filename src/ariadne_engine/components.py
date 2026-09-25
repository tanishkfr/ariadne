"""Component intelligence and the minimum-solution ladder (AR-202D T4).

The question this module answers is not "which library exists" but "is this the
smallest solution, and is it safe to adopt *here*". Every meaningful component
decision is a record:

* the need it solves, in the project's own terms;
* the rung of the ladder that was actually evaluated first;
* at least one named alternative that was considered and why it lost;
* the existing-equivalent check, recorded rather than assumed;
* explicit findings (never invented numeric scores) for compatibility,
  accessibility, dependency weight, licence, framework fit, maintenance,
  customisation, visual fit and interaction fit;
* what it would cost, and who would have to authorize it.

Hard rules:

* a candidate is evaluated at the first rung that solves the need; a new
  external dependency is the *last* rung, never the first;
* no automatic installation exists anywhere in this module, and no function
  returns an install authority other than the literal human-only string;
* a candidate whose licence or compatibility is ``unknown`` is blocked rather
  than selected, because "probably fine" is not a finding;
* an evaluation is a recommendation, not permission: ``selected`` on the higher
  rungs still carries ``approval_required = True`` until a human G2 approval
  exists, and routing/authorization are never bypassed here.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Mapping, Sequence

from . import contracts
from .contracts import (
    COMPONENT_DECISIONS,
    COMPONENT_LADDER,
    COMPONENT_VERDICTS,
    ContractError,
)

INSTALL_AUTHORITY = "none — human G2 required"
"""The only install authority this module can record. Identical to the string the
existing capability plan uses, so no reviewer has to reconcile two spellings."""

LADDER_RULES: dict[str, str] = {
    "existing-project-component": "an existing project component already solves this need",
    "existing-design-system": "the project's design system already provides this primitive",
    "native-platform": "the platform/browser provides this capability without a dependency",
    "project-local-implementation": "the need is small enough to implement locally",
    "approved-dependency": "an already-approved dependency provides this capability",
    "approved-registry": "an approved registry/component source provides this capability",
    "new-external-dependency": "no earlier rung solves the need and a new dependency is proposed",
}
"""Why each rung exists. The order is the policy; the strings are the record."""

FINDING_NAMES = (
    "project_compatibility",
    "design_system_compatibility",
    "accessibility",
    "dependency_weight",
    "licence",
    "framework_compatibility",
    "maintenance_risk",
    "customisation_requirements",
    "visual_fit",
    "interaction_fit",
)
"""Findings an evaluation may record. An unrecorded finding stays ``unknown`` and
is reported as unknown rather than assumed benign."""

BLOCKING_FINDINGS = ("licence", "project_compatibility", "framework_compatibility")
"""Findings whose ``unknown`` verdict blocks selection.

A dependency whose licence or compatibility nobody established cannot be adopted
by default; that is the case where an optimistic default is most expensive.
"""

HIGHER_RUNGS = ("approved-dependency", "approved-registry", "new-external-dependency")

DEPENDENCY_RUNGS = HIGHER_RUNGS
"""Rungs that introduce an external dependency.

Only these carry licence and framework-compatibility obligations: a project
component or a native platform feature does not have a licence question, and
demanding one there would invent a requirement the project does not have.
"""


def candidates(state: dict) -> list[dict]:
    values = state.get("component_candidates")
    if not isinstance(values, list):
        return []
    return [item for item in values if isinstance(item, Mapping)]


def candidate(state: dict, candidate_id: str) -> dict | None:
    for record in candidates(state):
        if str(record.get("candidate_id", "")) == str(candidate_id):
            return record
    return None


# ------------------------------------------------------------------ registry

class ComponentRegistry:
    """Read-only view of component registry metadata.

    AR-202D ships two implementations: the repository's own
    ``references/capabilities.json`` (local, always available) and a fixture
    registry for deterministic tests. No live registry is contacted, and no
    registry call installs anything.
    """

    id = "abstract-registry"

    def entries(self) -> list[dict]:
        raise NotImplementedError

    def checked_on(self) -> str:
        return ""

    def freshness_days(self) -> int:
        return 90

    def problems(self) -> list[str]:
        return []

    def entry(self, name: str) -> dict | None:
        needle = str(name or "").strip().lower()
        for item in self.entries():
            if needle in (str(item.get("id", "")).lower(), str(item.get("name", "")).lower()):
                return dict(item)
        return None


class LocalCapabilityRegistry(ComponentRegistry):
    """The repository's declared capability registry, read locally."""

    id = "local-capability-registry"

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self._loaded: dict | None = None
        self._problems: list[str] = []

    def _load(self) -> dict:
        if self._loaded is not None:
            return self._loaded
        if not self.path.is_file():
            self._problems = [f"capability registry is missing: {self.path}"]
            self._loaded = {}
            return self._loaded
        try:
            value = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            self._problems = [f"capability registry is unreadable: {exc}"]
            self._loaded = {}
            return self._loaded
        if not isinstance(value, dict) or value.get("schema_version") != 1:
            self._problems = ["capability registry has an unsupported schema"]
            self._loaded = {}
            return self._loaded
        self._loaded = value
        return self._loaded

    def entries(self) -> list[dict]:
        value = self._load()
        rows = value.get("entries")
        return [dict(item) for item in rows] if isinstance(rows, list) else []

    def checked_on(self) -> str:
        return str(self._load().get("checked_on", ""))

    def freshness_days(self) -> int:
        try:
            return int(self._load().get("reverify_after_days", 90) or 90)
        except (TypeError, ValueError):
            return 90

    def problems(self) -> list[str]:
        self._load()
        problems = list(self._problems)
        if not problems and not self.entries():
            problems.append("capability registry declares no entries")
        return problems


class FixtureRegistry(ComponentRegistry):
    """Deterministic registry metadata for tests and benchmarks."""

    id = "fixture-registry"

    def __init__(self, payload: Mapping) -> None:
        self.payload = dict(payload or {})

    def entries(self) -> list[dict]:
        rows = self.payload.get("entries")
        return [dict(item) for item in rows] if isinstance(rows, list) else []

    def checked_on(self) -> str:
        return str(self.payload.get("checked_on", ""))

    def freshness_days(self) -> int:
        try:
            return int(self.payload.get("reverify_after_days", 90) or 90)
        except (TypeError, ValueError):
            return 90

    def problems(self) -> list[str]:
        return [str(item) for item in (self.payload.get("problems") or [])]


def default_registry(root: Path) -> ComponentRegistry:
    return LocalCapabilityRegistry(Path(root) / "references" / "capabilities.json")


# ---------------------------------------------------------------- evaluation

def _findings(rows: Mapping | None, *, defaults: Sequence[str] = ()) -> dict:
    resolved: dict[str, dict] = {}
    supplied = dict(rows or {})
    unknown_names = sorted(set(supplied) - set(FINDING_NAMES))
    if unknown_names:
        raise ContractError("component evaluation records unknown finding(s): " + ", ".join(unknown_names))
    for name in FINDING_NAMES:
        value = supplied.get(name)
        if value is None:
            resolved[name] = {
                "verdict": "unknown",
                "detail": "not established by this evaluation",
            }
            continue
        if not isinstance(value, Mapping):
            raise ContractError(f"component finding {name} must be an object")
        verdict = str(value.get("verdict", "")).strip().lower()
        if verdict not in COMPONENT_VERDICTS:
            raise ContractError(f"component finding {name} has an unsupported verdict: {verdict!r}")
        detail = str(value.get("detail", "")).strip()
        if verdict != "unknown" and not detail:
            raise ContractError(f"component finding {name} claims {verdict} without a reason")
        resolved[name] = {"verdict": verdict, "detail": detail, "evidence": [str(item) for item in (value.get("evidence") or [])]}
    return resolved


def evaluate(
    state: dict,
    *,
    need: str,
    task_id: str,
    rung: str,
    name: str,
    capability: str = "",
    alternatives: Sequence[Mapping] = (),
    existing_equivalent: Mapping | None = None,
    findings: Mapping | None = None,
    approved_dependencies: Sequence[str] = (),
    registry: ComponentRegistry | None = None,
    registry_entry: str = "",
    project_paths: Sequence[str] = (),
    approval_id: str = "",
    note: str = "",
) -> dict:
    """Evaluate one component candidate against the ladder and record the result.

    The returned record is a *recommendation*. ``permitted`` is False on the
    upper rungs until the run holds a human G2 approval; nothing here installs,
    resolves or downloads anything.
    """
    if rung not in COMPONENT_LADDER:
        raise ContractError(f"unknown ladder rung: {rung!r}")
    if not str(need or "").strip():
        raise ContractError("a component evaluation needs the need it solves")
    if not str(name or "").strip():
        raise ContractError("a component evaluation needs a candidate name")
    rows = [dict(item) for item in (alternatives or ()) if isinstance(item, Mapping)]
    if not rows:
        raise ContractError(
            "a component evaluation must name at least one alternative it considered; "
            "one candidate is not a comparison"
        )
    for row in rows:
        if not str(row.get("name", "")).strip() or not str(row.get("reason", "")).strip():
            raise ContractError("each considered alternative needs a name and the reason it lost")
    existing = dict(existing_equivalent or {})
    if "checked" not in existing:
        raise ContractError(
            "a component evaluation must record the existing-equivalent check (use checked=false with a reason)"
        )
    if not existing.get("checked") and not str(existing.get("reason", "")).strip():
        raise ContractError("an unchecked existing-equivalent needs a recorded reason")
    resolved = _findings(findings)
    approval = approval_record(state, approval_id)

    problems: list[str] = []
    if rung == "new-external-dependency" and not str(registry_entry or "").strip() and registry is not None:
        problems.append("a new external dependency must cite a registry entry or an explicit unregistered reason")
    if rung in ("approved-dependency",) and str(name) not in {str(item) for item in (approved_dependencies or ())}:
        problems.append(f"{name!r} is not a recorded approved dependency")

    registry_record: dict = {}
    if registry is not None and (registry_entry or rung in ("approved-registry", "new-external-dependency")):
        entry = registry.entry(registry_entry or name)
        registry_problems = list(registry.problems())
        if entry is None:
            registry_problems.append(f"registry has no entry for {registry_entry or name!r}")
        registry_record = {
            "registry": registry.id,
            "query": str(registry_entry or name),
            "checked_on": registry.checked_on(),
            "freshness_days": registry.freshness_days(),
            "entry": entry or {},
            "problems": registry_problems,
        }
        if entry is None:
            problems.extend(registry_problems)

    for finding in BLOCKING_FINDINGS:
        if rung in DEPENDENCY_RUNGS and resolved[finding]["verdict"] == "unknown":
            problems.append(
                f"{finding.replace('_', ' ')} is unknown; a dependency whose {finding.replace('_', ' ')} "
                "nobody established cannot be selected"
            )

    if rung in HIGHER_RUNGS:
        needs_approval = True
    else:
        needs_approval = False

    approval_source = "none"
    if str(approval_id or "").strip():
        approval_source = "recorded" if approval is not None else "unverified"

    if problems:
        decision = "blocked"
    elif rung in HIGHER_RUNGS and not str(approval_id or "").strip():
        decision = "blocked"
        problems.append(
            f"the {rung.replace('-', ' ')} rung needs a human G2 approval; a recommendation is not "
            "installation authority"
        )
    elif rung in HIGHER_RUNGS and approval is None:
        decision = "blocked"
        problems.append(
            f"the approval {quote(approval_id)} is not recorded in this run; an authorization id is a "
            "claim like any other and must name an approval the engine actually holds"
        )
    elif rung in HIGHER_RUNGS:
        decision = "selected"
    else:
        decision = "selected"

    record = {
        "schema_version": contracts.SCHEMA_DESIGN,
        "candidate_id": contracts.new_record_id("cnd"),
        "run_id": str(state.get("run_id", "")),
        "task_id": str(task_id),
        "need": str(need),
        "capability": str(capability or need),
        "rung": rung,
        "rung_rule": LADDER_RULES[rung],
        "candidate": {"name": str(name), "kind": rung},
        "existing_equivalent": existing,
        "alternatives": rows,
        "findings": resolved,
        "registry": registry_record,
        "project_paths": [str(item) for item in (project_paths or [])],
        "approval_required": bool(needs_approval),
        "approval_id": str(approval_id),
        "approval_source": approval_source,
        "approved_dependencies_source": "declared-by-caller",
        "install_authority": INSTALL_AUTHORITY,
        "decision": decision,
        "problems": problems,
        "note": str(note),
        "recorded_at": contracts.utc_now(),
    }
    recorded = record_problems(record)
    if recorded:
        raise ContractError("component candidate is malformed: " + "; ".join(recorded))
    contracts.require_design_capacity(state, "component_candidates")
    state.setdefault("component_candidates", []).append(record)
    return record


def record_problems(record: Mapping) -> list[str]:
    return contracts.component_candidate_problems(record)


def selected(state: dict, *, task_id: str = "") -> list[dict]:
    return [
        record for record in candidates(state)
        if str(record.get("decision")) == "selected"
        and (not task_id or str(record.get("task_id", "")) == str(task_id))
    ]


def blocked(state: dict, *, task_id: str = "") -> list[dict]:
    return [
        record for record in candidates(state)
        if str(record.get("decision")) == "blocked"
        and (not task_id or str(record.get("task_id", "")) == str(task_id))
    ]


def quote(value: object) -> str:
    """A readable, injection-free rendering of a caller-supplied value."""
    return repr(str(value))


def findings_of(record: Mapping) -> Mapping:
    return record.get("findings") if isinstance(record.get("findings"), Mapping) else {}


def approval_record(state: dict, approval_id: str) -> dict | None:
    """The run's recorded approval for an id, or ``None``.

    An approval id is a claim like any other, so it is checked against what the
    engine actually recorded: a recommendation may not cite an authorization that
    does not exist.
    """
    if not str(approval_id or "").strip():
        return None
    for record in state.get("approvals") or []:
        if isinstance(record, Mapping) and str(record.get("approval_id", "")) == str(approval_id):
            return dict(record)
    return None


def dependency_problems(state: dict, *, task_id: str = "") -> list[str]:
    """Whether any candidate for this task proposes an unauthorized dependency."""
    problems: list[str] = []
    for record in candidates(state):
        if task_id and str(record.get("task_id", "")) != str(task_id):
            continue
        if str(record.get("rung")) not in HIGHER_RUNGS:
            continue
        if not record.get("approval_required"):
            continue
        if str(record.get("decision")) == "selected":
            continue
        detail = "; ".join(str(item) for item in (record.get("problems") or []))
        problems.append(
            f"{record.get('candidate', {}).get('name', 'candidate')} on the "
            f"{str(record.get('rung')).replace('-', ' ')} rung is {record.get('decision')}: {detail}"
        )
    return problems


def summarise(state: dict) -> dict:
    """Deterministic component-intelligence counters."""
    records = candidates(state)
    by_rung: dict[str, int] = {rung: 0 for rung in COMPONENT_LADDER}
    decisions: dict[str, int] = {value: 0 for value in COMPONENT_DECISIONS}
    avoided = 0
    for record in records:
        rung = str(record.get("rung", ""))
        if rung in by_rung:
            by_rung[rung] += 1
        decision = str(record.get("decision", ""))
        if decision in decisions:
            decisions[decision] += 1
        if rung not in HIGHER_RUNGS and decision == "selected":
            avoided += 1
    return {
        "candidates": len(records),
        "by_rung": by_rung,
        "decisions": decisions,
        "dependencies_avoided": avoided,
        "approvals_required": sum(1 for record in records if record.get("approval_required")),
    }


def describe(record: Mapping) -> str:
    candidate_value = record.get("candidate") if isinstance(record.get("candidate"), Mapping) else {}
    return (
        f"{record.get('candidate_id')} {candidate_value.get('name', '?')} at "
        f"{str(record.get('rung')).replace('-', ' ')} -> {record.get('decision')}"
    )


__all__ = [
    "INSTALL_AUTHORITY",
    "LADDER_RULES",
    "FINDING_NAMES",
    "BLOCKING_FINDINGS",
    "HIGHER_RUNGS",
    "DEPENDENCY_RUNGS",
    "ComponentRegistry",
    "LocalCapabilityRegistry",
    "FixtureRegistry",
    "default_registry",
    "candidates",
    "candidate",
    "evaluate",
    "record_problems",
    "selected",
    "blocked",
    "dependency_problems",
    "summarise",
    "describe",
]
