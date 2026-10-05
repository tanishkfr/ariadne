"""Score the bounded runtime against the reviewed corpus, and say what the score is worth.

The corpus in :mod:`~ariadne_engine.intelligence.corpus_data` has labels. This module is the
only thing that turns those labels into a claim about the engine, so it is deliberately
narrow about what it will claim:

* it runs the **real** seeded reference engine through the **real** in-process runtime. A
  stub provider would be easier to control and would measure a fiction;
* it reports **accuracy, coverage, abstention, calibration, latency and fallback** per
  family, because forcing one metric across incompatible families produces a number nobody
  can act on;
* it reports **selective risk** -- the error rate among the cases it chose to answer -- next
  to plain accuracy, because an engine that is right 92% of the time while answering
  everything is not the same engine as one that is right 92% of the time and abstains on the
  8% it cannot see;
* it looks for the 2.1 pathology directly: different inputs, one answer, one confidence. That
  failure is invisible in an average and obvious in a collision count.

**No threshold is chosen here.** :func:`sweep` reports the accuracy/abstention trade on the
development split; :mod:`~ariadne_engine.intelligence.calibration` is what turns that into a
threshold, and it may only read the development split. A threshold picked by looking at the
held-out numbers is a fitted number wearing a measured one's clothes.
"""

from __future__ import annotations

import time
from typing import Any, Mapping, Sequence

from .corpus import (
    EVALUATION_SPLITS,
    FAMILIES,
    FAMILY_DEFINITIONS,
    require_clean,
    select,
)

EVALUATION_VERSION = "ar-223-evaluated-intelligence-1"

CONFIDENCE_FLOOR = 0.8
"""What counts as "confident" when hunting for confident errors.

A named constant rather than a percentile of the observed run, because a percentile moves
with the data and the claim being tested -- a confident answer that is wrong -- does not.
"""

FLAT_CONFIDENCE_SPREAD = 0.02
"""How little confidence may vary across different inputs before the engine is suspect.

An engine that gives 0.99 and 0.98 to two genuinely different cases is not being careful
about the second one. This is a floor on suspicion, not proof of failure: the flag is a
finding to investigate, and :func:`confidence_profile` says so in its own output.
"""

METRICS = (
    "accuracy",
    "coverage",
    "abstention_rate",
    "selective_error_rate",
    "ece",
    "brier",
    "high_confidence_errors",
    "latency_p50_ms",
    "latency_p95_ms",
)
"""Reported per family, each computed only where it is meaningful.

``accuracy`` is undefined without ground truth, ``ece`` and ``brier`` are undefined without
a probability for the answered cases, and latency is a property of this machine rather than
of the engine. Every one of those returns ``None`` rather than a convenient zero.
"""


def questions() -> dict[str, dict]:
    """The four seeded question records, keyed by question id.

    Read from :func:`ariadne_engine.decisions.runtime.seeds.seed_families` rather than
    re-declared, so the answer space evaluated here is byte-identical to the one the
    integration asks. A benchmark question that differs from the production question by one
    option would be measuring a system nobody runs.
    """
    from ..decisions.runtime import seeds

    return {str(question["question_id"]): dict(question) for question, _ in seeds.seed_families().values()}


def runtime_for(engine: Any, *, model_revision: str = "") -> Any:
    """The seeded reference engine, in process, through the production runtime session.

    The same construction ``scripts/test-decision-runtime.py`` uses. No scripted provider,
    no hand-fed answers: whatever this measures is what the shipped engine does.
    """
    runtime = engine.decisions.runtime
    book = runtime.seeds.build_seed_book()
    implementation = runtime.reference.ReferenceBoundedEngine(
        book,
        model_revision=model_revision or runtime.reference.ENGINE_REVISION,
    )
    description = dict(implementation.status())
    description["runtime_kind"] = "local_bounded"
    return runtime.session.DecisionRuntime.in_process(implementation, description=description)


def answer_case(
    session: Any,
    question: Mapping[str, Any],
    projection: Mapping[str, Any],
    *,
    case_id: str,
    min_confidence: float | None = None,
) -> dict:
    """One corpus case through one bounded decision, timed.

    The runtime answers a batch keyed by ``"{state_index}:{question_id}"``; this unwraps that
    into a single flat row so a row can be compared with a label without knowing the wire
    format. An abstention keeps its reason and, where the engine offers one, its candidate --
    because "it declined, and this is what it would have said" is the difference between
    measuring abstention quality and measuring a refusal count.
    """
    question_id = str(question.get("question_id", ""))
    started = time.perf_counter()
    error = ""
    try:
        response = session.decide(dict(projection), [dict(question)], min_confidence=min_confidence)
    except Exception as exc:  # a runtime that raises is a fallback, not a crash
        latency_ms = round((time.perf_counter() - started) * 1000.0, 3)
        return {
            "case_id": case_id,
            "answer": "",
            "confidence": None,
            "confidence_kind": "NONE",
            "distribution": {},
            "abstained": False,
            "status": "failed",
            "reason": f"{type(exc).__name__}: {exc}",
            "candidate_answer": "",
            "candidate_confidence": None,
            "latency_ms": latency_ms,
            "error": error or type(exc).__name__,
        }
    latency_ms = round((time.perf_counter() - started) * 1000.0, 3)
    answers = response.get("answers") if isinstance(response, Mapping) else {}
    slot = dict(answers.get(f"0:{question_id}", {}) if isinstance(answers, Mapping) else {})
    abstained = bool(slot.get("abstained", False))
    return {
        "case_id": case_id,
        "answer": "" if abstained else str(slot.get("answer", "")),
        "confidence": slot.get("confidence"),
        "confidence_kind": str(slot.get("confidence_kind", "NONE")),
        "distribution": dict(slot.get("distribution", {}) or {}),
        "abstained": abstained,
        "status": "refused" if abstained else ("failed" if not slot.get("valid") else "answered"),
        "reason": str(slot.get("reason", "")),
        "candidate_answer": str(slot.get("candidate_answer", "") or ""),
        "candidate_confidence": slot.get("candidate_confidence"),
        "latency_ms": latency_ms,
        "error": "",
    }


def records_for(cases: Sequence[Mapping[str, Any]]) -> list[dict]:
    """Corpus rows in the shape the runtime evaluator reads.

    The corpus calls the truth a ``label`` and the evaluator calls it ``expected``. Bridging
    the two here, in one obvious place, keeps the corpus honest about its own vocabulary and
    keeps the evaluator's contract untouched.
    """
    return [
        {
            "case_id": str(row.get("case_id", "")),
            "expected": str(row.get("label", "")),
            "split": str(row.get("split", "")),
            "expected_abstain": bool(row.get("expected_abstain", False)),
            "difficulty": str(row.get("difficulty", "")),
        }
        for row in cases
    ]


def run_family(
    session: Any,
    *,
    family: str,
    cases: Sequence[Mapping[str, Any]],
    question: Mapping[str, Any],
    min_confidence: float | None = None,
) -> dict:
    """Answer every case of one family and assemble the rows plus the labelled records."""
    definition = FAMILY_DEFINITIONS[str(family)]
    rows = [
        answer_case(
            session,
            question,
            dict(case.get("projection", {})),
            case_id=str(case.get("case_id", "")),
            min_confidence=min_confidence,
        )
        for case in cases
    ]
    return {
        "family": str(family),
        "definition": definition["definition"],
        "question_id": definition["question_id"],
        "records": records_for(cases),
        "rows": rows,
        "min_confidence": min_confidence,
    }


def merge_rows(records: Sequence[Mapping[str, Any]], rows: Sequence[Mapping[str, Any]]) -> list[dict]:
    """Rows joined to their labels, expected abstention and difficulty.

    One flat list is what every analysis below wants, and joining once is cheaper than
    joining seven times inside seven analyses.
    """
    by_id = {str(row.get("case_id", "")): dict(row) for row in records}
    joined: list[dict] = []
    for row in rows:
        case_id = str(row.get("case_id", ""))
        label = by_id.get(case_id, {})
        expected = str(label.get("expected", ""))
        answer = str(row.get("answer", ""))
        joined.append(
            {
                **row,
                "expected": expected,
                "split": str(label.get("split", "")),
                "difficulty": str(label.get("difficulty", "")),
                "expected_abstain": bool(label.get("expected_abstain", False)),
                "correct": bool(answer) and answer == expected,
            }
        )
    return joined


def confidence_profile(joined: Sequence[Mapping[str, Any]]) -> dict:
    """Look for the 2.1 failure: many different truths, one answer, one confidence.

    Reported as counts and two named flags rather than a score, because the thing being
    detected is a pattern in the answers, and averaging it into a number is how it stayed
    invisible for a release. ``detected`` is a prompt to look, not a verdict on the engine.
    """
    answered = [row for row in joined if str(row.get("answer", ""))]
    expected = [str(row.get("expected", "")) for row in answered]
    answers = [str(row.get("answer", "")) for row in answered]
    confidences = [
        float(row["confidence"])
        for row in answered
        if isinstance(row.get("confidence"), (int, float)) and not isinstance(row.get("confidence"), bool)
    ]
    distinct_labels = sorted(set(expected))
    distinct_answers = sorted(set(answers))
    spread = round(max(confidences) - min(confidences), 6) if confidences else None
    high_confidence_errors = sum(
        1
        for row in answered
        if isinstance(row.get("confidence"), (int, float))
        and not isinstance(row.get("confidence"), bool)
        and float(row["confidence"]) >= CONFIDENCE_FLOOR
        and not row.get("correct")
    )
    collapsed = len(distinct_answers) == 1 and len(distinct_labels) >= 3
    flat = spread is not None and spread <= FLAT_CONFIDENCE_SPREAD and len(distinct_labels) >= 3
    return {
        "answered": len(answered),
        "distinct_labels": len(distinct_labels),
        "distinct_answers": len(distinct_answers),
        "dominant_answer": max(set(answers), key=answers.count) if answers else "",
        "dominant_answer_share": round(answers.count(max(set(answers), key=answers.count)) / len(answers), 6)
        if answers
        else None,
        "confidence_min": round(min(confidences), 6) if confidences else None,
        "confidence_max": round(max(confidences), 6) if confidences else None,
        "confidence_spread": spread,
        "high_confidence_errors": high_confidence_errors,
        "answer_collapse": collapsed,
        "confidence_flat": flat,
        "detected": bool(collapsed or flat or high_confidence_errors),
        "note": (
            "answer_collapse means one answer covered several different truths. confidence_flat "
            "means different inputs drew near-identical confidence. high_confidence_errors means "
            "the engine was confidently wrong, which is the only one of the three that is an "
            "error rather than a pattern"
        ),
    }


def abstention_quality(joined: Sequence[Mapping[str, Any]]) -> dict:
    """Whether abstention landed where the reviewers said it should.

    Two ways to be wrong, and they are not symmetric: missing a case that should have been
    declined is a *false answer*, while declining a case it could have handled is only a
    waste of the cheap path. Both are counted, and the ratio that matters -- how many of the
    declines were warranted -- is reported next to how many of the warranted declines
    happened.
    """
    expected = [row for row in joined if row.get("expected_abstain")]
    declined = [row for row in joined if row.get("abstained")]
    warranted = [row for row in declined if row.get("expected_abstain")]
    missed = [row for row in expected if not row.get("abstained")]
    unwarranted = [row for row in declined if not row.get("expected_abstain")]
    return {
        "expected_to_abstain": len(expected),
        "abstained": len(declined),
        "warranted_abstentions": len(warranted),
        "missed_abstentions": len(missed),
        "unwarranted_abstentions": len(unwarranted),
        "abstention_precision": round(len(warranted) / len(declined), 6) if declined else None,
        "abstention_recall": round(len(warranted) / len(expected), 6) if expected else None,
        "note": (
            "a missed abstention is a wrong answer dressed as a right one. An unwarranted "
            "abstention costs a cheap decision and nothing else, which is why precision and "
            "recall are reported as different numbers"
        ),
    }


def family_metrics(joined: Sequence[Mapping[str, Any]]) -> dict:
    """The per-family metrics, each ``None`` where it cannot honestly be computed.

    ECE and Brier are delegated to the runtime evaluator rather than recomputed here. A
    second implementation of the same metric is a second thing to be wrong, and the whole
    point of this milestone is that one number has one meaning.
    """
    from ..decisions.runtime import evaluation as runtime_evaluation

    total = len(joined)
    answered = [row for row in joined if str(row.get("answer", ""))]
    correct = [row for row in answered if row.get("correct")]
    abstained = [row for row in joined if row.get("abstained")]
    failed = [row for row in joined if str(row.get("status", "")) == "failed"]
    latencies = sorted(float(row["latency_ms"]) for row in joined if isinstance(row.get("latency_ms"), (int, float)))
    confident_errors = sum(
        1
        for row in answered
        if isinstance(row.get("confidence"), (int, float))
        and not isinstance(row.get("confidence"), bool)
        and float(row["confidence"]) >= CONFIDENCE_FLOOR
        and not row.get("correct")
    )
    confidences = [
        float(row["confidence"])
        for row in answered
        if isinstance(row.get("confidence"), (int, float)) and not isinstance(row.get("confidence"), bool)
    ]
    correctness = [bool(row.get("correct")) for row in answered]
    distributions = [
        (dict(row["distribution"]), str(row.get("expected", "")))
        for row in answered
        if isinstance(row.get("distribution"), Mapping) and row["distribution"]
    ]
    return {
        "cases": total,
        "answered": len(answered),
        "abstained": len(abstained),
        "failed": len(failed),
        "accuracy": round(len(correct) / len(answered), 6) if answered else None,
        "coverage": round(len(answered) / total, 6) if total else None,
        "abstention_rate": round(len(abstained) / total, 6) if total else None,
        "fallback_rate": round(len(failed) / total, 6) if total else None,
        "selective_error_rate": round(
            (len(answered) - len(correct)) / len(answered), 6
        )
        if answered
        else None,
        "high_confidence_errors": confident_errors,
        "ece": runtime_evaluation.ece(confidences, correctness),
        "brier": runtime_evaluation.brier_over(distributions),
        "latency_p50_ms": latencies[(50 * len(latencies) + 99) // 100 - 1] if latencies else None,
        "latency_p95_ms": latencies[(95 * len(latencies) + 99) // 100 - 1] if latencies else None,
    }


def evaluate(
    engine: Any,
    corpus: Mapping[str, Any] | None = None,
    *,
    families: Sequence[str] | None = None,
    splits: Sequence[str] | None = None,
    min_confidence_by_family: Mapping[str, float] | None = None,
    session: Any | None = None,
    runtime_status: Mapping[str, Any] | None = None,
) -> dict:
    """Evaluate the engine over the corpus, one report per family plus the whole run.

    ``corpus`` defaults to the authored one and is checked for leakage before a single case
    is answered. A leaky corpus produces a confident, meaningless number, and the only
    defence is refusing to produce it.
    """
    if corpus is None:
        from . import corpus_data

        corpus = corpus_data.corpus()
    require_clean(corpus)
    owned = session is None
    active = session or runtime_for(engine)
    catalogue = questions()
    thresholds = {str(key): float(value) for key, value in (min_confidence_by_family or {}).items()}
    per_family: dict[str, dict] = {}
    all_joined: list[dict] = []
    try:
        runtime_identity = dict(runtime_status or {}) or dict(active.status())
        for family in families or FAMILIES:
            cases = select(corpus, families=[family], splits=splits)
            if not cases:
                continue
            definition = FAMILY_DEFINITIONS[str(family)]
            question = catalogue[definition["question_id"]]
            run = run_family(
                active,
                family=family,
                cases=cases,
                question=question,
                min_confidence=thresholds.get(str(family)),
            )
            joined = merge_rows(run["records"], run["rows"])
            all_joined.extend(joined)
            per_family[str(family)] = {
                "definition": definition["definition"],
                "question_id": definition["question_id"],
                "splits": sorted({str(row.get("split", "")) for row in joined}),
                "min_confidence": thresholds.get(str(family)),
                "metrics": family_metrics(joined),
                "confidence": confidence_profile(joined),
                "abstention": abstention_quality(joined),
                "cases": joined,
            }
    finally:
        if owned:
            active.shutdown()
    return {
        "evaluation_version": EVALUATION_VERSION,
        "corpus_digest": str(corpus.get("corpus_digest", "")),
        "corpus_cases": int(corpus.get("case_count", 0)),
        "splits": list(splits) if splits else list(EVALUATION_SPLITS),
        "families": per_family,
        "overall": {
            "metrics": family_metrics(all_joined),
            "confidence": confidence_profile(all_joined),
            "abstention": abstention_quality(all_joined),
        },
        "runtime": {
            "model_revision": str(runtime_identity.get("model_revision", "")),
            "runtime_version": str(runtime_identity.get("runtime_version", "")),
            "implementation_revision": str(runtime_identity.get("implementation_revision", "")),
            "runtime_kind": str(runtime_identity.get("runtime_kind", "")),
            "confidence_kinds": list(runtime_identity.get("confidence_kinds", []) or []),
            "calibration_self_granted": bool(runtime_identity.get("calibration_self_granted", False)),
        },
        "limitations": [
            "confidence is provider probability; nothing here makes it calibrated",
            "latency is local wall clock and moves with the machine",
            "an evaluation is evidence about a run, never an authorisation",
            "the corpus is authored and reviewed, not scraped production traffic",
        ],
        "authorization_effect": "none",
    }


def sweep(
    engine: Any,
    *,
    thresholds: Sequence[float] = (0.0, 0.5, 0.6, 0.7, 0.75, 0.8, 0.85, 0.9, 0.95),
    family: str = "",
    session: Any | None = None,
) -> dict:
    """The accuracy/abstention trade across candidate thresholds, on one split.

    The output exists so a threshold can be *chosen* rather than assumed. It reads whatever
    rows the caller passes through ``splits``-selected cases, which is why the calibration
    module — and only the calibration module — calls it against ``DEVELOPMENT``.
    """
    from . import corpus_data

    corpus = corpus_data.corpus()
    require_clean(corpus)
    owned = session is None
    active = session or runtime_for(engine)
    catalogue = questions()
    wanted = [family] if family else list(FAMILIES)
    try:
        families: dict[str, list[dict]] = {}
        for name in wanted:
            cases = select(corpus, families=[name], splits=["DEVELOPMENT"])
            if not cases:
                continue
            question = catalogue[FAMILY_DEFINITIONS[name]["question_id"]]
            families[name] = [
                {
                    "case": case,
                    "row": answer_case(
                        active,
                        question,
                        dict(case.get("projection", {})),
                        case_id=str(case.get("case_id", "")),
                    ),
                }
                for case in cases
            ]
    finally:
        if owned:
            active.shutdown()
    curves: dict[str, list[dict]] = {}
    rows: dict[str, list[dict]] = {}
    for name, pairs in families.items():
        points: list[dict] = []
        rows[name] = [
            {
                **dict(pair["row"]),
                "expected": str(pair["case"]["label"]),
                "split": "DEVELOPMENT",
                "difficulty": str(pair["case"].get("difficulty", "")),
                "expected_abstain": bool(pair["case"].get("expected_abstain", False)),
                "correct": str(pair["row"].get("answer", "")) == str(pair["case"]["label"]),
            }
            for pair in pairs
        ]
        for threshold in thresholds:
            answered = 0
            correct = 0
            abstained = 0
            for pair in pairs:
                row = dict(pair["row"])
                confidence = row.get("confidence")
                numeric = (
                    isinstance(confidence, (int, float))
                    and not isinstance(confidence, bool)
                    and float(confidence) >= float(threshold)
                )
                if numeric and str(row.get("answer", "")):
                    answered += 1
                    correct += 1 if str(row["answer"]) == str(pair["case"]["label"]) else 0
                else:
                    abstained += 1
            points.append(
                {
                    "min_confidence": float(threshold),
                    "answered": answered,
                    "abstained": abstained,
                    "accuracy": round(correct / answered, 6) if answered else None,
                    "coverage": round(answered / len(pairs), 6) if pairs else None,
                }
            )
        curves[name] = points
    return {
        "sweep_version": EVALUATION_VERSION,
        "split": "DEVELOPMENT",
        "thresholds": [float(value) for value in thresholds],
        "curves": curves,
        "rows": rows,
        "note": (
            "read on the development split alone. A threshold chosen by looking at held-out "
            "numbers is a fitted number, and the corpus splits exist to make that visible. "
            "The rows are published so a temperature can be fitted on exactly these answers "
            "rather than on a second, differently-thresholded run"
        ),
    }


def canonical_report(
    engine: Any,
    corpus: Mapping[str, Any],
    *,
    family: str,
    splits: Sequence[str],
    min_confidence: float | None = None,
    session: Any | None = None,
) -> dict:
    """One family's run as an AR-206 evaluation report: identity-bound, with an evaluation id.

    Promotion cites one of these by id. A promotion that cites nothing cites an assertion, and
    AR-206 refuses an ``ELIGIBLE`` slice without an evaluation identity -- so the honest path
    is to produce the record and quote it rather than to invent an id that resolves to nothing.
    """
    from ..decisions.runtime import evaluation as runtime_evaluation

    owned = session is None
    active = session or runtime_for(engine)
    definition = FAMILY_DEFINITIONS[str(family)]
    question = questions()[definition["question_id"]]
    cases = select(corpus, families=[family], splits=splits)
    try:
        run = run_family(
            active,
            family=family,
            cases=cases,
            question=question,
            min_confidence=min_confidence,
        )
        status = dict(active.status())
    finally:
        if owned:
            active.shutdown()
    return runtime_evaluation.evaluate(
        run["records"],
        decision_definition=definition["definition"],
        questions=[question],
        runtime_version=str(status.get("runtime_version", "")),
        implementation_revision=str(status.get("implementation_revision", "")),
        model_revision=str(status.get("model_revision", "")),
        rows=run["rows"],
    )


def degradation(
    baseline: Mapping[str, Any],
    candidate: Mapping[str, Any],
    *,
    max_accuracy_drop: float = 0.05,
    max_ece_rise: float = 0.05,
    max_selective_error_rise: float = 0.05,
    max_confident_errors: int = 0,
) -> dict:
    """Whether a candidate run is worse than the baseline it claims to replace.

    Deliberately conservative and entirely mechanical: four thresholds, four named reasons,
    no weighting and no overall score. A health signal that can be argued with is a health
    signal that gets argued with instead of acted on.
    """
    reasons: list[str] = []
    pairs = (
        ("accuracy", max_accuracy_drop, False),
        ("ece", max_ece_rise, True),
        ("selective_error_rate", max_selective_error_rise, True),
    )
    changes: dict[str, dict] = {}
    for metric, tolerance, higher_is_worse in pairs:
        before = baseline.get(metric)
        after = candidate.get(metric)
        if not isinstance(before, (int, float)) or not isinstance(after, (int, float)):
            continue
        delta = round(float(after) - float(before), 6)
        changes[metric] = {"before": before, "after": after, "delta": delta, "tolerance": tolerance}
        if (delta > tolerance) if higher_is_worse else (delta < -tolerance):
            reasons.append(
                f"{metric} moved {delta:+g} against a tolerance of {tolerance:g} "
                f"({before} to {after})"
            )
    before_errors = baseline.get("high_confidence_errors")
    after_errors = candidate.get("high_confidence_errors")
    if isinstance(before_errors, int) and isinstance(after_errors, int):
        changes["high_confidence_errors"] = {
            "before": before_errors,
            "after": after_errors,
            "delta": after_errors - before_errors,
            "tolerance": max_confident_errors,
        }
        if after_errors - before_errors > max_confident_errors:
            reasons.append(
                f"confidently wrong answers rose from {before_errors} to {after_errors}, "
                "which is the failure a bounded authority cannot absorb"
            )
    return {
        "degraded": bool(reasons),
        "reasons": reasons,
        "changes": changes,
        "policy": {
            "max_accuracy_drop": max_accuracy_drop,
            "max_ece_rise": max_ece_rise,
            "max_selective_error_rise": max_selective_error_rise,
            "max_confident_errors": max_confident_errors,
        },
        "note": (
            "degradation is measured against a named baseline under named tolerances. A rise "
            "with no baseline to compare against is not a degradation report; it is a second run"
        ),
    }


def describe() -> dict:
    return {
        "version": EVALUATION_VERSION,
        "metrics": list(METRICS),
        "confidence_floor": CONFIDENCE_FLOOR,
        "flat_confidence_spread": FLAT_CONFIDENCE_SPREAD,
        "engine": "the seeded reference engine, in process, through the production session",
        "threshold_choice": (
            "declared by a caller and fitted only against the development split; this module "
            "never picks one itself"
        ),
        "detects": [
            "confidently wrong answers",
            "one answer covering several different truths",
            "different inputs drawing near-identical confidence",
            "abstention that missed the cases the reviewers marked unanswerable",
        ],
        "authorization_effect": "none",
    }


__all__ = [
    "CONFIDENCE_FLOOR",
    "EVALUATION_VERSION",
    "FLAT_CONFIDENCE_SPREAD",
    "METRICS",
    "abstention_quality",
    "canonical_report",
    "confidence_profile",
    "degradation",
    "describe",
    "evaluate",
    "family_metrics",
    "merge_rows",
    "questions",
    "records_for",
    "run_family",
    "runtime_for",
    "sweep",
]