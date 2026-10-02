"""Adoption slices: how a runtime becomes authoritative, and how it stops being so.

Promotion is the risky part of this milestone, so it is scoped as narrowly as the
architecture allows. A slice is not "the Decision Runtime". It is one exact tuple:

    decision definition x question version x model revision x scope

where scope names the risk class, reversibility, the languages it was evaluated in,
and whether verification was available. Promotion applies to that tuple and nothing
else. A slice promoted for low-risk, reversible failure classification says nothing
about protected dependency changes, and the engine refuses to let it.

The lifecycle is deliberately linear and deliberately reversible:

    UNTESTED -> SHADOW -> EVALUATED -> ELIGIBLE -> ACTIVE
                                                       |
                                                       v
                                                    SUSPENDED

:func:`transition` is the only way a status changes, and it enforces the order.
``ACTIVE`` is unreachable without an evaluation identity, and ``SUSPENDED`` is
reachable from ``ACTIVE`` with no conditions at all — because being able to stop a
thing quickly matters more than being able to start it carefully.

Two invariants the engine holds:

*promotion is reversible and project-local.* ``SUSPENDED`` restores the previous
authoritative path. Nothing migrates, nothing is written into a user project, and
re-enabling is a second transition.

*an ``ACTIVE`` slice cannot exceed its scope.* :func:`scope_problems` compares a
requested use against the slice's declared scope and refuses anything wider. A slice
that cannot be checked against its scope cannot be safely promoted.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from ...contracts import (
    ADOPTION_STATES,
    DECISION_CONSEQUENCES,
    SCHEMA_DECISION_RUNTIME,
    adoption_slice_problems,
    new_record_id,
    require_collection_capacity,
    utc_now,
)
from .manifest import revision_matches

ADOPTION_VERSION = "ar-206-adoption-1"
"""The adoption-slice record shape."""

TRANSITIONS: dict[str, tuple[str, ...]] = {
    "UNTESTED": ("SHADOW", "SUSPENDED"),
    "SHADOW": ("EVALUATED", "UNTESTED", "SUSPENDED"),
    "EVALUATED": ("ELIGIBLE", "SHADOW", "SUSPENDED"),
    "ELIGIBLE": ("ACTIVE", "EVALUATED", "SHADOW", "SUSPENDED"),
    "ACTIVE": ("SUSPENDED",),
    "SUSPENDED": ("UNTESTED", "SHADOW", "EVALUATED"),
}
"""Allowed next states. ``ACTIVE`` can only be left for ``SUSPENDED``."""

SCOPE_FIELDS = ("risk", "reversible", "languages", "verification_available")
"""What an eligibility scope must declare.

``languages`` is here because a threshold or an accuracy measured in English does not
transfer to another language, and that has to be stated rather than assumed.
``verification_available`` is here because promoting a slice that cannot be verified
removes the ability to catch it being wrong.
"""

_REQUIRED_SCOPE_FIELDS = ("risk", "reversible", "verification_available")


def scope_problems(scope: Mapping[str, Any]) -> list[str]:
    """Structural validation of an eligibility scope."""
    problems: list[str] = []
    if not isinstance(scope, Mapping) or not scope:
        return ["an adoption scope must be a non-empty object"]
    for name in _REQUIRED_SCOPE_FIELDS:
        if name not in scope:
            problems.append(f"adoption scope does not declare {name}")
    risk = str(scope.get("risk", ""))
    if risk and risk not in DECISION_CONSEQUENCES:
        problems.append(f"adoption scope names an unknown risk class: {risk}")
    if not isinstance(scope.get("reversible", None), bool):
        problems.append("adoption scope reversible must be true or false")
    if not isinstance(scope.get("verification_available", None), bool):
        problems.append("adoption scope verification_available must be true or false")
    languages = scope.get("languages")
    if not isinstance(languages, (list, tuple)) or not languages:
        problems.append("adoption scope declares no languages")
    for name in scope:
        if name not in SCOPE_FIELDS:
            problems.append(f"adoption scope declares an unknown field: {name}")
    return list(dict.fromkeys(problems))


def open_slice(
    state: dict,
    *,
    decision_definition: str,
    question_version: str,
    model_revision: str,
    scope: Mapping[str, Any],
    runtime: str = "",
    implementation: str = "",
    task_id: str = "",
    note: str = "",
) -> dict:
    """Open an adoption slice in ``UNTESTED``.

    A slice with no model revision is refused: promotion without a pinned revision
    would be a claim about a checkpoint that can move under it.
    """
    problems = scope_problems(scope)
    if problems:
        raise ValueError("refusing to open an invalid adoption slice: " + "; ".join(problems))
    require_collection_capacity(state, "decision_adoption")
    record = {
        "schema_version": SCHEMA_DECISION_RUNTIME,
        "slice_id": new_record_id("dad"),
        "adoption_version": ADOPTION_VERSION,
        "run_id": str(state.get("run_id", "")),
        "task_id": str(task_id),
        "decision_definition": str(decision_definition),
        "question_version": str(question_version),
        "model_revision": str(model_revision),
        "runtime": str(runtime),
        "implementation": str(implementation),
        "status": "UNTESTED",
        "scope": dict(scope),
        "evaluation_id": "",
        "calibration_profile_id": "",
        "history": [{"status": "UNTESTED", "at": utc_now(), "note": "slice opened"}],
        "note": str(note),
        "authorization_effect": "none",
        "recorded_at": utc_now(),
    }
    record_problems = adoption_slice_problems(record)
    if record_problems:
        raise ValueError("refusing to open an invalid adoption slice: " + "; ".join(record_problems))
    state.setdefault("decision_adoption", []).append(record)
    return record


def slices(state: Mapping[str, Any], *, decision_definition: str = "") -> list[dict]:
    rows = [dict(record) for record in state.get("decision_adoption", []) or []]
    if decision_definition:
        rows = [row for row in rows if str(row.get("decision_definition", "")) == str(decision_definition)]
    return rows


def find(
    state: Mapping[str, Any],
    *,
    decision_definition: str,
    question_version: str,
    model_revision: str,
) -> dict | None:
    """The most recent slice for one exact tuple. Revision matching is exact."""
    matches = [
        record
        for record in state.get("decision_adoption", []) or []
        if str(record.get("decision_definition", "")) == str(decision_definition)
        and str(record.get("question_version", "")) == str(question_version)
        and revision_matches(str(record.get("model_revision", "")), str(model_revision))
    ]
    if not matches:
        return None
    return dict(sorted(matches, key=lambda row: str(row.get("recorded_at", "")))[-1])


def transition(
    state: dict,
    slice_id: str,
    target: str,
    *,
    reason: str = "",
    evaluation_id: str = "",
    calibration_profile_id: str = "",
    note: str = "",
) -> dict:
    """Move one slice to ``target``, enforcing the lifecycle order.

    ``ACTIVE`` additionally requires an evaluation identity and a scope that passed
    validation, because "promoted" without either is an assertion.
    """
    if target not in ADOPTION_STATES:
        raise ValueError(f"unknown adoption state: {target!r}")
    if not str(reason or "").strip():
        # Every status change is an adoption event; an unlabelled one cannot be
        # reviewed later.
        raise ValueError("an adoption transition must state a reason")
    for index, record in enumerate(state.get("decision_adoption", []) or []):
        if str(record.get("slice_id", "")) != str(slice_id):
            continue
        current = str(record.get("status", "UNTESTED"))
        if target not in TRANSITIONS.get(current, ()):
            raise ValueError(
                f"an adoption slice in {current} cannot move to {target}; allowed: "
                + ", ".join(TRANSITIONS.get(current, ()) or ("(none)",))
            )
        updated = dict(record)
        if target in ("ELIGIBLE", "ACTIVE") and not str(evaluation_id or record.get("evaluation_id", "")).strip():
            raise ValueError(f"an {target} slice must name the evaluation that justified it")
        updated["status"] = str(target)
        updated["reason"] = str(reason)
        if evaluation_id:
            updated["evaluation_id"] = str(evaluation_id)
        if calibration_profile_id:
            updated["calibration_profile_id"] = str(calibration_profile_id)
        history = list(updated.get("history", []) or [])
        history.append({"status": str(target), "at": utc_now(), "reason": str(reason), "note": str(note)})
        updated["history"] = history
        updated["updated_at"] = utc_now()
        problems = adoption_slice_problems(updated)
        if problems:
            raise ValueError("refusing an invalid adoption transition: " + "; ".join(problems))
        state["decision_adoption"][index] = updated
        return updated
    raise ValueError(f"no adoption slice is recorded with id {slice_id!r}")


def suspend(state: dict, slice_id: str, *, reason: str, note: str = "") -> dict:
    """Withdraw promotion immediately.

    Unconditional by design: if the evidence degrades, stopping must not require
    passing a condition. The previous authoritative path resumes because nothing was
    ever migrated.
    """
    return transition(state, slice_id, "SUSPENDED", reason=reason, note=note)


def scope_matches(slice_record: Mapping[str, Any], requested: Mapping[str, Any]) -> list[str]:
    """Whether a slice may be used for a requested scope.

    The check is one-directional and strict. A slice declared for ``LOW`` risk does
    not cover ``HIGH``; a slice evaluated only in ``en`` does not cover ``de``; a
    slice declared reversible does not cover an irreversible operation. Anything the
    slice did not declare is out of its scope.
    """
    problems = scope_problems(dict(slice_record.get("scope", {})))
    if problems:
        return [f"the slice scope is invalid: {problem}" for problem in problems]
    declared = dict(slice_record["scope"])
    problems = scope_problems(dict(requested))
    if problems:
        return [f"the requested scope is invalid: {problem}" for problem in problems]
    risk_order = list(DECISION_CONSEQUENCES)
    declared_risk = str(declared.get("risk", "LOW"))
    requested_risk = str(requested.get("risk", "LOW"))
    if requested_risk != declared_risk:
        # Widening is refused outright. A narrower use is allowed, because a slice
        # proven safe for HIGH risk is still safe for LOW risk.
        if risk_order.index(requested_risk) > risk_order.index(declared_risk):
            problems.append(
                f"the slice is scoped to {declared_risk} risk and cannot answer a {requested_risk} risk question"
            )
    if declared.get("reversible") and not requested.get("reversible", True):
        problems.append("the slice is scoped to reversible operations only")
    if declared.get("verification_available") and not requested.get("verification_available", False):
        problems.append("the slice requires verification availability and the requested use has none")
    declared_languages = {str(item) for item in declared.get("languages", ())}
    requested_languages = {str(item) for item in requested.get("languages", ())}
    uncovered = requested_languages - declared_languages
    if uncovered:
        problems.append(
            "the slice was not evaluated for: " + ", ".join(sorted(uncovered))
        )
    return problems


def active_slice(
    state: Mapping[str, Any],
    *,
    decision_definition: str,
    question_version: str,
    model_revision: str,
) -> dict | None:
    """The ``ACTIVE`` slice for an exact tuple, or ``None``.

    A slice is only returned when its own identity matches. A slice promoted for a
    different revision, a different question version or a different decision definition
    does not apply, even if its definition name matches.
    """
    record = find(
        state,
        decision_definition=decision_definition,
        question_version=question_version,
        model_revision=model_revision,
    )
    if record is None or str(record.get("status", "")) != "ACTIVE":
        return None
    return record


def summarise(state: Mapping[str, Any]) -> dict:
    rows = slices(state)
    by_status: dict[str, int] = {name: 0 for name in ADOPTION_STATES}
    for record in rows:
        status = str(record.get("status", "UNTESTED"))
        by_status[status] = by_status.get(status, 0) + 1
    return {
        "version": ADOPTION_VERSION,
        "slices": len(rows),
        "by_status": by_status,
        "active_definitions": sorted(
            {
                str(record.get("decision_definition", ""))
                for record in rows
                if str(record.get("status", "")) == "ACTIVE"
            }
        ),
        "note": "promotion is scoped per definition, question version and model revision, and is reversible",
    }


def describe() -> dict:
    return {
        "version": ADOPTION_VERSION,
        "states": list(ADOPTION_STATES),
        "transitions": {name: list(targets) for name, targets in TRANSITIONS.items()},
        "scope_fields": list(SCOPE_FIELDS),
        "note": "an ACTIVE slice may not exceed its declared eligibility scope",
    }


def active_for(
    state: Mapping[str, Any],
    *,
    decision_definition: str,
    question_version: str,
    model_revision: str,
) -> dict:
    """A single lookup result shaped for a caller that must branch on it."""
    record = active_slice(
        state,
        decision_definition=decision_definition,
        question_version=question_version,
        model_revision=model_revision,
    )
    return {
        "active": record is not None,
        "slice": record,
        "scope": dict(record.get("scope", {})) if record else {},
        "evaluation_id": str(record.get("evaluation_id", "")) if record else "",
        "calibration_profile_id": str(record.get("calibration_profile_id", "")) if record else "",
    }


def slice_problems(state: Mapping[str, Any]) -> list[str]:
    """Validate every stored adoption slice, including its history's legal order."""
    problems: list[str] = []
    for record in state.get("decision_adoption", []) or []:
        for problem in adoption_slice_problems(record):
            problems.append(f"adoption {record.get('slice_id', '?')}: {problem}")
        previous = "UNTESTED"
        for step in record.get("history", []) or []:
            status = str(step.get("status", ""))
            if status not in TRANSITIONS.get(previous, ()):
                problems.append(
                    f"adoption {record.get('slice_id', '?')}: history moved {previous} to {status}"
                    ", which is not a legal transition"
                )
            previous = status
    return list(dict.fromkeys(problems))


def all_definitions(state: Mapping[str, Any]) -> list[str]:
    return sorted({str(record.get("decision_definition", "")) for record in state.get("decision_adoption", []) or []})


def scopes_of(state: Mapping[str, Any], decision_definition: str) -> list[dict]:
    return [
        dict(record.get("scope", {}))
        for record in state.get("decision_adoption", []) or []
        if str(record.get("decision_definition", "")) == str(decision_definition)
    ]


def covered_languages(scopes: Sequence[Mapping[str, Any]]) -> set[str]:
    languages: set[str] = set()
    for scope in scopes:
        languages.update(str(item) for item in scope.get("languages", ()) or ())
    return languages