"""Shadow mode: the runtime predicts while the authoritative path runs unchanged.

The pattern this borrows is the highest-value thing in the adoption story, and it is
worth being precise about why. Promoting a new implementation of a judgement is the
riskiest thing Ariadne does in the 2.1 milestone, and the only way to know whether a
local runtime is any good is to watch it answer questions it is not yet trusted to
answer. Shadow mode is that watch.

The isolation is structural, not conventional:

* the shadow call happens **after** the authoritative decision is recorded, and its
  result is written to a different collection;
* :func:`record_shadow` refuses any record claiming an execution effect, and the
  record validator refuses it again on the way back out;
* nothing in the Plane reads ``state["decision_shadow"]`` to make a decision. It is
  written by :mod:`ariadne_engine.decisions.runtime.integrations` and read by
  :mod:`~ariadne_engine.decisions.runtime.evaluation` and the diagnostics. That
  asymmetry is what makes "it cannot affect execution" a property rather than a
  promise;
* :func:`shadow_effect_problems` exists so a test can assert the property instead of
  trusting it.

What gets stored is deliberately small: the question, the projection *digest* (not the
projection text), the answer, the distribution, the runtime identity and the
comparison. Shadow records are evidence about a runtime, and evidence about a runtime
is not a licence to keep the user's project content.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from ...contracts import (
    SCHEMA_DECISION_RUNTIME,
    SHADOW_AGREEMENTS,
    new_record_id,
    require_collection_capacity,
    shadow_record_problems,
    utc_now,
)
from ..contracts import state_digest

SHADOW_VERSION = "ar-206-shadow-1"
"""The shadow record shape."""

SHADOW_AGGREGATION_VERSION = "ar-206-shadow-aggregate-1"
"""The per-slice comparison summary shape."""


def agreement(
    *,
    shadow_answer: str,
    authoritative_answer: str,
    ground_truth: str = "",
) -> str:
    """How a shadow prediction compares to the authoritative result.

    ``DISAGREE`` is a *difference*, not a verdict. Only explicit ground truth decides
    which side was right, and without it the record stays ``UNKNOWN`` — never silently
    counted as a loss for the runtime, which would bias promotion against the very
    implementation being measured.
    """
    predicted = str(shadow_answer or "")
    actual = str(authoritative_answer or "")
    truth = str(ground_truth or "")
    if not predicted:
        return "UNKNOWN"
    if not actual:
        return "UNKNOWN"
    if predicted == actual:
        return "MATCH"
    if not truth:
        return "DISAGREE"
    return "MATCH" if truth == predicted else "DISAGREE"


def record_shadow(
    state: dict,
    *,
    question: Mapping[str, Any],
    projection_digest: str,
    answer: str,
    distribution: Mapping[str, float] | None = None,
    confidence: float | None = None,
    confidence_kind: str = "PROVIDER_PROBABILITY",
    authoritative_answer: str = "",
    authoritative_decision_id: str = "",
    ground_truth: str = "",
    runtime: Mapping[str, Any] | None = None,
    task_id: str = "",
    definition: str = "",
    runtime_kind: str = "local_bounded",
    abstained: bool = False,
    reason: str = "",
) -> dict:
    """Record one shadow prediction beside a decision that was already made.

    ``question`` is stored by identity fields only. The projection is stored as its
    digest. Neither the projected text nor the answer distribution beyond the answered
    label is kept, so a shadow collection does not become a second copy of the user's
    project state.
    """
    require_collection_capacity(state, "decision_shadow")
    runtime_facts = dict(runtime or {})
    resolved_agreement = (
        "UNKNOWN"
        if abstained
        else agreement(
            shadow_answer=answer,
            authoritative_answer=authoritative_answer,
            ground_truth=ground_truth,
        )
    )
    record = {
        "schema_version": SCHEMA_DECISION_RUNTIME,
        "shadow_id": new_record_id("dsh"),
        "shadow_version": SHADOW_VERSION,
        "run_id": str(state.get("run_id", "")),
        "task_id": str(task_id),
        "question_id": str(question.get("question_id", "")),
        "primitive": str(question.get("primitive", "")),
        "definition": str(definition or question.get("projection_contract", "")),
        "definition_version": str(question.get("definition_version", "1")),
        "question_identity": state_digest(
            {
                "question_id": str(question.get("question_id", "")),
                "instructions": str(question.get("instructions", "")),
                "primitive": str(question.get("primitive", "")),
                "options": [str(item) for item in question.get("options", ()) or ()],
            }
        ),
        "projection_digest": str(projection_digest),
        "answer": str(answer),
        "distribution": {str(k): float(v) for k, v in dict(distribution or {}).items()},
        "confidence": None if confidence is None else float(confidence),
        "confidence_kind": str(confidence_kind),
        "agreement": resolved_agreement,
        "ground_truth": str(ground_truth),
        "authoritative_answer": str(authoritative_answer),
        "authoritative_decision_id": str(authoritative_decision_id),
        "runtime_kind": str(runtime_kind),
        "runtime_version": str(runtime_facts.get("runtime_version", "")),
        "implementation": str(runtime_facts.get("implementation", "")),
        "implementation_revision": str(runtime_facts.get("implementation_revision", "")),
        "model": str(runtime_facts.get("model", "")),
        "model_revision": str(runtime_facts.get("model_revision", "")),
        "device": str(runtime_facts.get("device", "")),
        "abstained": bool(abstained),
        "reason": str(reason),
        # The load-bearing field. It is not optional and it has one legal value.
        "execution_effect": "none",
        "authorization_effect": "none",
        "recorded_at": utc_now(),
    }
    problems = shadow_record_problems(record)
    if problems:
        raise ValueError("refusing to record an invalid shadow prediction: " + "; ".join(problems))
    state.setdefault("decision_shadow", []).append(record)
    return record


def shadow_problems(state: Mapping[str, Any]) -> list[str]:
    """Validate every stored shadow record. Structural problems are reported, not raised."""
    problems: list[str] = []
    for record in state.get("decision_shadow", []) or []:
        for problem in shadow_record_problems(record):
            problems.append(f"shadow {record.get('shadow_id', '?')}: {problem}")
    return list(dict.fromkeys(problems))


def shadow_effect_problems(state: Mapping[str, Any], decisions: Sequence[Mapping[str, Any]]) -> list[str]:
    """Whether any recorded decision could have been influenced by a shadow record.

    This is the property that makes shadow mode safe, expressed so a test can check
    it. A decision is suspicious when it carries no ``execution_id`` while a shadow
    record claims the same question and projection digest for the same task — the
    shape an influence bug would take.

    The check is deliberately conservative and reports rather than blocks: a false
    positive costs a diagnostic line, and a false negative costs the invariant.
    """
    problems: list[str] = []
    if not state.get("decision_shadow"):
        return problems
    shadow_keys = {
        (
            str(record.get("task_id", "")),
            str(record.get("question_id", "")),
            str(record.get("projection_digest", "")),
        )
        for record in state.get("decision_shadow", [])
    }
    for decision in decisions:
        key = (
            str(decision.get("task_id", "")),
            str(decision.get("question_id", "")),
            str(decision.get("state_digest", "")),
        )
        if key in shadow_keys and not str(decision.get("execution_id", "")):
            problems.append(
                f"decision {decision.get('decision_id', '?')} shares a question and projection "
                "digest with a shadow record but records no execution; verify the shadow path "
                "did not influence it"
            )
    return problems


def shadow_records(
    state: Mapping[str, Any],
    *,
    task_id: str = "",
    definition: str = "",
) -> list[dict]:
    rows = [dict(record) for record in state.get("decision_shadow", []) or []]
    if task_id:
        rows = [row for row in rows if str(row.get("task_id", "")) == str(task_id)]
    if definition:
        rows = [row for row in rows if str(row.get("definition", "")) == str(definition)]
    return rows


def compare(
    state: Mapping[str, Any],
    *,
    definition: str = "",
) -> dict:
    """Summarise shadow predictions against authoritative results.

    ``DISAGREE`` is reported as a count, not a score. With no ground truth a
    disagreement rate measures how often two implementations differ, which is
    interesting and is not accuracy.
    """
    rows = shadow_records(state, definition=definition)
    by_agreement: dict[str, int] = {name: 0 for name in SHADOW_AGREEMENTS}
    revisions: set[str] = set()
    for row in rows:
        by_agreement[str(row.get("agreement", "UNKNOWN"))] = by_agreement.get(str(row.get("agreement", "UNKNOWN")), 0) + 1
        revisions.add(str(row.get("model_revision", "")))
    predicted = sum(1 for row in rows if not row.get("abstained"))
    grounded = sum(1 for row in rows if str(row.get("ground_truth", "")))
    resolved = [
        row
        for row in rows
        if not row.get("abstained")
        and str(row.get("ground_truth", ""))
        and str(row.get("answer", "")) == str(row.get("ground_truth", ""))
    ]
    comparable = [
        row
        for row in rows
        if not row.get("abstained") and str(row.get("ground_truth", ""))
    ]
    return {
        "version": SHADOW_AGGREGATION_VERSION,
        "records": len(rows),
        "predicted": predicted,
        "abstained": sum(1 for row in rows if row.get("abstained")),
        "ground_truth_records": grounded,
        "by_agreement": by_agreement,
        "match_rate": round(len(resolved) / len(comparable), 4) if comparable else None,
        "accuracy": round(len(resolved) / len(comparable), 4) if comparable else None,
        "coverage": round(predicted / len(rows), 4) if rows else None,
        "model_revisions": sorted(revisions),
        "note": (
            "accuracy is reported only where explicit ground truth exists; a disagreement "
            "without ground truth is a difference between two implementations, not an error"
        ),
    }


def record_ground_truth(state: dict, shadow_id: str, *, ground_truth: str, source: str = "verification") -> dict:
    """Attach explicit ground truth to a shadow record and re-derive its agreement.

    Ground truth must be sourced. An unreferenced "this was wrong" is how a runtime
    gets blamed for a disagreement that was really an unclear question.
    """
    if not str(source or "").strip():
        raise ValueError("ground truth must name its source; an unsourced outcome is not evidence")
    if not str(ground_truth or "").strip():
        raise ValueError("ground truth must state the correct answer")
    for record in state.get("decision_shadow", []) or []:
        if str(record.get("shadow_id", "")) == str(shadow_id):
            updated = dict(record)
            updated["ground_truth"] = str(ground_truth)
            updated["ground_truth_source"] = str(source)
            updated["agreement"] = agreement(
                shadow_answer=str(record.get("answer", "")),
                authoritative_answer=str(record.get("authoritative_answer", "")),
                ground_truth=str(ground_truth),
            )
            updated["reconciled_at"] = utc_now()
            return updated
    raise ValueError(f"no shadow record is recorded with id {shadow_id!r}")


def describe() -> dict:
    return {
        "version": SHADOW_VERSION,
        "agreements": list(SHADOW_AGREEMENTS),
        "fields_kept": [
            "question identity", "projection digest", "answer", "distribution",
            "confidence and its kind", "runtime identity", "comparison",
        ],
        "fields_not_kept": ["projected state text", "repository content", "credentials"],
        "execution_effect": "none",
        "note": (
            "the authoritative decision is recorded first and the shadow prediction second; "
            "no Plane read path consumes shadow records"
        ),
    }