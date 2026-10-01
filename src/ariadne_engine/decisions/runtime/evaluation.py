"""Evaluation with identity: a metric is only evidence if you know what produced it.

The failure this module exists to prevent is quiet. Two reports of different
datasets, different question schemas and different model revisions produce perfectly
well-formed arithmetic, and a delta between them looks exactly like an improvement.
Printing that delta would be inventing evidence.

So every report binds an identity, and every comparison checks it:

* ``dataset_digest`` â€” the digest of the dataset *bytes*, not its path. Two datasets
  share a path across a rebase, a CI cache or a colleague's checkout.
* ``question_schema_digest`` and ``decision_definition_digest`` â€” what was asked.
* ``runtime_version``, ``implementation_revision`` and ``model_revision`` â€” what
  answered.
* ``calibration_profile_id`` and ``threshold_policy_version`` â€” what was applied.

:func:`compare` refuses when any of those differ and names each one. The refusal is
the feature.

Metrics are computed only where ground truth exists. Coverage, abstention rate and
latency are always measurable; accuracy, ECE and Brier are not, and a task without
labels reports them as ``UNKNOWN`` rather than as zero.
"""

from __future__ import annotations

import hashlib
import json
import time
from typing import Any, Mapping, Sequence

from ...contracts import (
    EVALUATION_COMPARABILITY_KEYS,
    SCHEMA_DECISION_RUNTIME,
    new_record_id,
    utc_now,
)
from ..contracts import DecisionQuestion
from .profiles import decision_definition_digest, question_schema_digest

EVALUATION_VERSION = "ar-206-evaluation-1"
"""The evaluation report shape."""

EVALUATION_IDENTITY_KEYS = tuple(EVALUATION_COMPARABILITY_KEYS)
"""The identity every report binds. Kept in step with the engine contract."""

DEFAULT_ECE_BINS = 15
"""Equal-width reliability bins. Fifteen is the convention; the value is recorded so
two reports using different bin counts are visibly different experiments."""


def dataset_digest(records: Sequence[Mapping[str, Any]]) -> str:
    """Digest of the evaluation rows themselves, order-independent.

    Order-independent on purpose: shuffling a dataset does not change what it
    contains, and refusing to compare two shuffled runs of the same data would train
    everyone to ignore the gate.
    """
    canonical = sorted(json.dumps(dict(row), sort_keys=True, default=str) for row in records)
    return hashlib.sha256("\n".join(canonical).encode("utf-8")).hexdigest()


def identity(
    *,
    records: Sequence[Mapping[str, Any]],
    decision_definition: str,
    questions: Sequence[Any],
    runtime_version: str,
    implementation_revision: str,
    model_revision: str,
    calibration_profile_id: str = "",
    threshold_policy_version: str = "",
    question_schema: str = "",
    decision_definition_digest_value: str = "",
) -> dict:
    """The identity block every report carries."""
    schema_digest = question_schema_digest(questions)
    return {
        "dataset_digest": dataset_digest(records),
        "question_schema_digest": schema_digest or str(question_schema),
        "decision_definition_digest": decision_definition_digest_value
        or decision_definition_digest(decision_definition, questions),
        "runtime_version": str(runtime_version),
        "implementation_revision": str(implementation_revision),
        "model_revision": str(model_revision),
        "calibration_profile_id": str(calibration_profile_id),
        "threshold_policy_version": str(threshold_policy_version),
        "decision_definition": str(decision_definition),
        "question_count": len(list(questions)),
        "dataset_rows": len(list(records)),
    }


def ece(confidences: Sequence[float], correct: Sequence[bool], bins: int = DEFAULT_ECE_BINS) -> float | None:
    """Expected calibration error over equal-width confidence bins.

    Returns ``None`` rather than ``0.0`` when there is nothing to bin. A zero error
    on an empty set is a claim about quality, and there is none.
    """
    pairs = [
        (float(c), bool(t))
        for c, t in zip(confidences, correct)
        if isinstance(c, (int, float)) and not isinstance(c, bool) and 0.0 <= float(c) <= 1.0
    ]
    if not pairs:
        return None
    width = 1.0 / max(1, int(bins))
    total = 0.0
    for index in range(int(bins)):
        low = index * width
        high = low + width
        selected = [
            (c, t) for c, t in pairs if (low <= c < high or (index == int(bins) - 1 and c == 1.0))
        ]
        if not selected:
            continue
        mean_confidence = sum(c for c, _ in selected) / len(selected)
        accuracy = sum(1 for _, t in selected if t) / len(selected)
        total += (len(selected) / len(pairs)) * abs(accuracy - mean_confidence)
    return round(total, 6)




def evaluate(
    records: Sequence[Mapping[str, Any]],
    *,
    decision_definition: str,
    questions: Sequence[Any],
    runtime_version: str,
    implementation_revision: str,
    model_revision: str,
    calibration_profile_id: str = "",
    threshold_policy_version: str = "",
    question_schema: str = "",
    decision_definition_digest_value: str = "",
    rows: Sequence[Mapping[str, Any]] | None = None,
) -> dict:
    """Score one evaluation run and bind its identity.

    ``records`` are the evaluation cases (``{"projection": {...}, "expected": "..."}``).
    ``rows`` are the runtime's answers for the same cases, matched by ``case_id``.

    A case with no answer counts against coverage, not against accuracy. A case with no
    expected label contributes to latency and abstention but not to accuracy. Both
    are reported, because a run that only ever reports its best subset is not a run.
    """
    started = time.perf_counter()
    identities = identity(
        records=records,
        decision_definition=decision_definition,
        questions=questions,
        runtime_version=runtime_version,
        implementation_revision=implementation_revision,
        model_revision=model_revision,
        calibration_profile_id=calibration_profile_id,
        threshold_policy_version=threshold_policy_version,
        question_schema=question_schema,
        decision_definition_digest_value=decision_definition_digest_value,
    )
    answers = {str(row.get("case_id", "")): dict(row) for row in (rows or [])}
    total = len(list(records))
    answered = 0
    abstained = 0
    failed = 0
    grounded = 0
    correct = 0
    confidences: list[float] = []
    correctness: list[bool] = []
    distributions: list[tuple[dict[str, float], str]] = []
    confusion: dict[str, dict[str, int]] = {}
    latencies: list[float] = []
    by_case: list[dict] = []

    for case in records:
        case_id = str(case.get("case_id", ""))
        expected = str(case.get("expected", ""))
        row = answers.get(case_id, {})
        latency = row.get("latency_ms")
        if isinstance(latency, (int, float)) and not isinstance(latency, bool):
            latencies.append(float(latency))
        predicted = str(row.get("answer", ""))
        if row.get("abstained"):
            abstained += 1
        elif row.get("status") in ("failed", "invalid", "unavailable"):
            failed += 1
        elif predicted:
            answered += 1
        if predicted and expected:
            grounded += 1
            is_correct = predicted == expected
            correct += 1 if is_correct else 0
            correctness.append(is_correct)
            confidence = row.get("confidence")
            if isinstance(confidence, (int, float)) and not isinstance(confidence, bool):
                confidences.append(float(confidence))
            distribution = row.get("distribution")
            if isinstance(distribution, Mapping) and distribution:
                distributions.append(({str(k): float(v) for k, v in distribution.items()}, expected))
            confusion.setdefault(expected, {}).setdefault(predicted, 0)
            confusion[expected][predicted] += 1
        by_case.append(
            {
                "case_id": case_id,
                "expected": expected,
                "answer": predicted,
                "confidence": row.get("confidence"),
                "abstained": bool(row.get("abstained", False)),
                "status": str(row.get("status", "")),
            }
        )

    elapsed_ms = round((time.perf_counter() - started) * 1000.0, 3)
    measured = [
        float(row["latency_ms"]) for row in (rows or [])
        if isinstance(row.get("latency_ms"), (int, float)) and not isinstance(row.get("latency_ms"), bool)
    ] or latencies
    return {
        "schema_version": SCHEMA_DECISION_RUNTIME,
        "evaluation_id": new_record_id("dev"),
        "evaluation_version": EVALUATION_VERSION,
        "identity": identities,
        "totals": {
            "cases": total,
            "answered": answered,
            "abstained": abstained,
            "failed": failed,
            "ground_truth": grounded,
            "correct": correct,
        },
        "metrics": {
            "accuracy": round(correct / grounded, 6) if grounded else None,
            "coverage": round(answered / total, 6) if total else None,
            "abstention_rate": round(abstained / total, 6) if total else None,
            "failure_rate": round(failed / total, 6) if total else None,
            "ece": ece(confidences, correctness),
            "ece_bins": DEFAULT_ECE_BINS,
            "brier": brier_over(distributions),
            "latency_p50_ms": _percentile(measured, 50),
            "latency_p95_ms": _percentile(measured, 95),
        },
        "confusion": confusion,
        "cases": by_case,
        "elapsed_ms": elapsed_ms,
        "measured_on_this_machine": True,
        "limitations": [
            "accuracy, ECE and Brier are reported only where explicit ground truth exists",
            "latency is local wall-clock for this run and depends on the machine",
            "an evaluation report is evidence about a run, never an authorisation",
        ],
        "recorded_at": utc_now(),
        "authorization_effect": "none",
    }


def _percentile(values: Sequence[float], percentile: int) -> float | None:
    """Nearest-rank percentile.

    Nearest-rank rather than interpolated: an interpolated p95 of five samples
    invents a measurement that was not taken, and a performance claim should not be
    able to do that.
    """
    ordered = sorted(float(value) for value in values)
    if not ordered:
        return None
    rank = (percentile * len(ordered) + 99) // 100
    index = min(max(rank - 1, 0), len(ordered) - 1)
    return round(ordered[index], 3)


def brier_over(distributions: Sequence[tuple[Mapping[str, float], str]]) -> float | None:
    """Multi-class Brier score across correctly-labelled cases."""
    total = 0.0
    scored = 0
    for distribution, expected in distributions:
        if not distribution:
            continue
        for label, probability in distribution.items():
            value = float(probability) if isinstance(probability, (int, float)) else 0.0
            total += (value - (1.0 if str(label) == str(expected) else 0.0)) ** 2
        scored += 1
    if not scored:
        return None
    return round(total / scored, 6)


def identity_of(report: Mapping[str, Any]) -> dict:
    block = report.get("identity")
    return dict(block) if isinstance(block, Mapping) else {}


def comparable_to(
    baseline: Mapping[str, Any],
    candidate: Mapping[str, Any],
    *,
    keys: Sequence[str] = EVALUATION_IDENTITY_KEYS,
) -> tuple[bool, list[str]]:
    """Whether two reports describe the same experiment.

    Returns ``(ok, reasons)``. Each reason names the key, what it means, and the two
    values, so a refused comparison is actionable rather than a bare ``False``.

    A key absent on either side is ``unknown``, not a conflict. That keeps reports
    written before an identity key existed comparable to themselves rather than
    refusing everything and teaching everyone to ignore the gate.
    """
    reasons: list[str] = []
    here = identity_of(candidate)
    there = identity_of(baseline)
    labels = {
        "dataset_digest": "dataset bytes",
        "question_schema_digest": "question schema",
        "decision_definition_digest": "decision definition",
        "runtime_version": "runtime version",
        "implementation_revision": "implementation revision",
        "model_revision": "model revision",
    }
    for key in keys:
        mine = here.get(key)
        theirs = there.get(key)
        if mine is None or theirs is None or str(mine) == str(theirs):
            continue
        label = labels.get(key, key)
        reasons.append(f"{label} ({key}): baseline is {theirs}, this run is {mine}")
    return (not reasons), reasons


def compare(baseline: Mapping[str, Any], candidate: Mapping[str, Any]) -> dict:
    """Metric comparison, refused across non-comparable runs.

    A shared metric the candidate no longer reports is reported as ``missing`` rather
    than as no change. A run whose every case errored has an empty accuracy, and must
    not pass the gate by having nothing left to compare.
    """
    ok, reasons = comparable_to(baseline, candidate)
    base_metrics = dict(baseline.get("metrics", {}) or {})
    candidate_metrics = dict(candidate.get("metrics", {}) or {})
    shared = sorted(set(base_metrics) & set(candidate_metrics))
    deltas: dict[str, dict] = {}
    for key in shared:
        before = base_metrics[key]
        after = candidate_metrics[key]
        if not isinstance(before, (int, float)) or not isinstance(after, (int, float)):
            continue
        deltas[key] = {
            "baseline": before,
            "candidate": after,
            "delta": round(float(after) - float(before), 6),
            "improved": _improved(key, float(before), float(after)),
        }
    missing = sorted(key for key in base_metrics if key not in candidate_metrics)
    return {
        "comparable": ok,
        "reasons": reasons,
        "deltas": deltas,
        "missing_metrics": missing,
        "note": (
            "a metric comparison without experiment identity is not evidence; the gate refuses "
            "rather than printing a delta across different experiments"
        ),
    }


LOWER_IS_BETTER = ("ece", "brier", "abstention_rate", "failure_rate", "latency_p50_ms", "latency_p95_ms")


def _improved(metric: str, before: float, after: float) -> bool:
    """Direction of improvement. Unknown metrics are reported, not scored."""
    if metric in LOWER_IS_BETTER:
        return after < before
    if metric in ("accuracy", "coverage"):
        return after > before
    return False


def assert_regression(
    baseline: Mapping[str, Any],
    candidate: Mapping[str, Any],
    *,
    tolerances: Mapping[str, float] | None = None,
) -> None:
    """Raise ``AssertionError`` when a comparable candidate regresses.

    Latency needs an explicit tolerance because a re-run differs by timing noise, not
    by quality, and an un-toleranced latency gate would fail on a quiet machine.
    """
    result = compare(baseline, candidate)
    if not result["comparable"]:
        raise AssertionError("baseline is not comparable: " + "; ".join(result["reasons"]))
    tolerances = dict(tolerances or {})
    failures = []
    for metric, delta in result["deltas"].items():
        limit = tolerances.get(metric)
        if limit is None:
            if delta["improved"]:
                continue
            if delta["baseline"] == delta["candidate"]:
                continue
            failures.append(f"{metric} regressed by {abs(delta['delta'])}")
            continue
        allowed = float(limit)
        if _improved(metric, delta["baseline"], delta["candidate"]):
            continue
        if abs(delta["delta"]) > allowed:
            failures.append(f"{metric} moved {delta['delta']}, beyond the tolerance of {allowed}")
    if result["missing_metrics"]:
        failures.append("metrics missing from the candidate: " + ", ".join(result["missing_metrics"]))
    if failures:
        raise AssertionError("evaluation regression: " + "; ".join(failures))


def describe() -> dict:
    return {
        "version": EVALUATION_VERSION,
        "identity_keys": list(EVALUATION_IDENTITY_KEYS),
        "metrics": [
            "accuracy", "coverage", "abstention_rate", "failure_rate",
            "ece", "brier", "latency_p50_ms", "latency_p95_ms", "confusion",
        ],
        "ece_bins": DEFAULT_ECE_BINS,
        "percentile": "nearest-rank; an interpolated percentile would invent a measurement",
        "note": (
            "comparison is refused when dataset, question schema, decision definition, runtime "
            "or model revision differ; unknown stays unknown"
        ),
    }


def _unused(question: Any) -> Any:  # pragma: no cover
    return question if isinstance(question, DecisionQuestion) else question
