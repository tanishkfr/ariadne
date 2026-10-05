"""Turn measured runs into a licence, and refuse to let the licence outlive its evidence.

A calibration profile is the only object in Ariadne permitted to call a probability
calibrated. This module decides when one is earned, what it is bound to, and when it must be
thrown away. Three rules do all the work:

**Bound, not inherited.** A profile names the runtime, the model revision, the question
schema digest, the decision-definition digest and the corpus revision it was measured under.
:func:`stale_reasons` compares those against what is running now and names every dimension
that moved. A profile from a previous model revision does not degrade gracefully into the
next one; it stops applying.

**Fitted on development, measured elsewhere.** :func:`fit` reads the development split only.
The temperature it fits and the threshold it picks are both fitted values, and a fitted
value quoted as a measured one is the exact confusion this milestone exists to remove. The
held-out numbers in :mod:`~ariadne_engine.intelligence.evaluation` are reported against
these fitted parameters and are therefore genuinely out-of-sample.

**Confidence is not permission.** Nothing here can grant authority. A profile supplies a
threshold and a probability that may be described as calibrated; whether a bounded answer may
be *acted upon* is the promotion lifecycle and the risk policy's business, in
:mod:`~ariadne_engine.intelligence.promotion`.
"""

from __future__ import annotations

import math
from typing import Any, Mapping, Sequence

from ..contracts import ContractError
from ..decisions.runtime import profiles as runtime_profiles
from .corpus import FAMILIES, definition_for

CALIBRATION_VERSION = "ar-223-calibration-1"

IDENTITY_KEYS = (
    "runtime",
    "implementation_revision",
    "model_revision",
    "question_schema_digest",
    "decision_definition_digest",
    "corpus_revision",
)
"""The identity a calibration claim is made under.

Every one of these, if it moves, invalidates the claim. ``corpus_revision`` is the addition
over AR-206: a profile measured on one corpus says nothing about a different one, and 2.1 had
no way to say so because it had never measured anything.
"""

MIN_CALIBRATION_CASES = 50
"""Re-exported from the runtime so both sides quote one number."""

MEASURED_SPLITS = ("HELD_OUT", "REAL_WORLD")
"""The splits a profile's quality may be measured on.

Everything out-of-sample, and nothing adversarial. A profile needs enough cases to be a
measurement rather than an anecdote, and it needs them to be cases the fit never saw.
"""

THRESHOLD_POLICY = {
    "min_coverage": 0.6,
    "prefer_higher_threshold": True,
    "note": (
        "the threshold is the highest value on the development curve whose accuracy is at "
        "least as good as the best accuracy available at or above the minimum coverage. "
        "Among thresholds that tie, the higher one wins, because abstaining is the cheaper "
        "mistake"
    ),
}
"""How a threshold is chosen. Declared here so it can be argued with before it is used."""

TEMPERATURE_GRID = (0.25, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0, 4.0)
"""Candidate temperatures for the calibration fit.

A grid rather than a solver: a bounded search over eight values is reproducible, auditable,
and cannot quietly converge on something extreme. ``1.0`` is always in it so the fit can
report that no temperature was better than not calibrating.
"""


def _log_probability(distribution: Mapping[str, float], label: str, temperature: float) -> float:
    """Log probability of ``label`` under a temperature-scaled distribution."""
    scaled = {
        str(key): math.log(max(float(value), 1e-12)) / float(temperature)
        for key, value in dict(distribution).items()
    }
    top = max(scaled.values())
    denominator = sum(math.exp(value - top) for value in scaled.values())
    return float(scaled.get(str(label), -30.0) - top - math.log(denominator))


def fit_temperature(joined: Sequence[Mapping[str, Any]]) -> dict:
    """Fit one temperature on development cases and report what it actually bought.

    Temperature scaling is the cheapest honest thing available: it changes how peaked a
    distribution is and nothing else, so it cannot invent a separation the engine does not
    have. Reported with the before and after ECE because a calibration fit that makes the
    score worse is a finding, and reporting only the after would hide it.
    """
    from ..decisions.runtime import evaluation as runtime_evaluation

    usable = [
        row
        for row in joined
        if isinstance(row.get("distribution"), Mapping)
        and row["distribution"]
        and str(row.get("expected", ""))
        and not row.get("abstained")
    ]
    if len(usable) < 5:
        return {
            "fitted": False,
            "temperature": 1.0,
            "cases": len(usable),
            "reason": "too few answered cases with a distribution to fit a temperature",
        }
    confidences = [
        float(row["confidence"])
        for row in usable
        if isinstance(row.get("confidence"), (int, float)) and not isinstance(row.get("confidence"), bool)
    ]
    correctness = [bool(row.get("correct")) for row in usable]
    before = runtime_evaluation.ece(confidences, correctness)
    scored: list[tuple[float, float]] = []
    for temperature in TEMPERATURE_GRID:
        total = 0.0
        for row in usable:
            total -= _log_probability(dict(row["distribution"]), str(row["expected"]), temperature)
        scored.append((total / len(usable), temperature))
    scored.sort()
    best_nll, best = scored[0]
    at_one = next((value for value, temperature in scored if temperature == 1.0), best_nll)
    scaled_confidences = []
    for row in usable:
        distribution = dict(row["distribution"])
        exponentiated = {
            key: math.exp(math.log(max(float(value), 1e-12)) / best)
            for key, value in distribution.items()
        }
        total = sum(exponentiated.values()) or 1.0
        scaled_confidences.append(max(exponentiated.get(str(row["expected"]), 0.0) / total, 0.0))
    after = runtime_evaluation.ece(scaled_confidences, correctness)
    improved = before is not None and after is not None and after < before
    return {
        "fitted": True,
        "temperature": float(best),
        "cases": len(usable),
        "negative_log_likelihood_before": round(at_one, 6),
        "negative_log_likelihood_after": round(best_nll, 6),
        "ece_before": before,
        "ece_after": after,
        "improved": bool(improved),
        "method": "TEMPERATURE_SCALING" if improved else "MEASURED_ONLY",
        "note": (
            "a temperature rescales a distribution; it cannot separate cases the engine "
            "cannot already separate. ECE after a bad fit is reported rather than replaced"
        ),
    }


def fit_threshold(curve: Sequence[Mapping[str, Any]], *, policy: Mapping[str, Any] | None = None) -> dict:
    """Pick one threshold from a development curve under the declared policy."""
    rules = dict(policy or THRESHOLD_POLICY)
    floor = float(rules.get("min_coverage", 0.6))
    eligible = [
        point
        for point in curve
        if isinstance(point.get("accuracy"), (int, float))
        and isinstance(point.get("coverage"), (int, float))
        and float(point["coverage"]) >= floor
    ]
    if not eligible:
        return {
            "threshold": None,
            "reason": (
                f"no threshold on the development curve reaches {floor} coverage while still "
                "answering; the engine cannot be given a threshold at this coverage"
            ),
        }
    best_accuracy = max(float(point["accuracy"]) for point in eligible)
    tied = [point for point in eligible if float(point["accuracy"]) >= best_accuracy]
    chosen = max(tied, key=lambda point: float(point["min_confidence"]))
    return {
        "threshold": float(chosen["min_confidence"]),
        "development_accuracy": float(chosen["accuracy"]),
        "development_coverage": float(chosen["coverage"]),
        "candidates_considered": len(list(curve)),
        "candidates_eligible": len(eligible),
        "policy": rules,
        "point": dict(chosen),
    }


def dataset_digest_for(corpus: Mapping[str, Any], *, family: str) -> str:
    """The digest of the cases a family's profile was measured on.

    Family-scoped on purpose. A digest over the whole corpus would change whenever an
    unrelated family gained a row, which would invalidate every profile in the repository
    for a reason that has nothing to do with the evidence behind any of them.
    """
    from .corpus import projection_digest

    rows = [
        str(row.get("projection_digest", ""))
        for row in corpus.get("cases", []) or []
        if isinstance(row, Mapping) and str(row.get("family", "")) == str(family)
    ]
    return projection_digest(rows)


def identity(engine: Any, *, family: str, corpus_revision: str = "") -> dict:
    """What is running right now, on the six dimensions a calibration claim is bound to."""
    from .corpus import CORPUS_VERSION

    runtime = engine.decisions.runtime
    catalogue = {
        str(question["question_id"]): question
        for question, _ in runtime.seeds.seed_families().values()
    }
    question = catalogue[definition_for(str(family))["question_id"]]
    implementation = runtime.reference.ReferenceBoundedEngine(runtime.seeds.build_seed_book())
    status = dict(implementation.status())
    return {
        "family": str(family),
        "runtime": str(status.get("runtime_kind", "local_bounded")),
        "implementation": str(status.get("implementation", "")),
        "implementation_revision": str(status.get("implementation_revision", "")),
        "model_revision": str(status.get("model_revision", "")),
        "question_schema_digest": runtime_profiles.question_schema_digest([question]),
        "decision_definition_digest": runtime_profiles.decision_definition_digest(
            definition_for(str(family))["definition"], [question]
        ),
        "corpus_revision": str(corpus_revision or CORPUS_VERSION),
        "confidence_kinds": list(status.get("confidence_kinds", []) or []),
        "calibration_self_granted": bool(status.get("calibration_self_granted", False)),
        "deliberate": (
            "the runtime reports provider probability only. It cannot grant itself "
            "calibration, and no code path here treats its output as calibrated without a "
            "profile measured by this module"
        ),
    }


def stale_reasons(profile: Mapping[str, Any], observed: Mapping[str, Any]) -> list[str]:
    """Every dimension on which a recorded profile no longer describes the system.

    Naming rather than counting. "Calibration is stale" is unfalsifiable; "the model revision
    moved from ar-206-reference-1 to ar-206-reference-2" is a sentence somebody can fix.
    """
    reasons: list[str] = []
    for key in IDENTITY_KEYS:
        if key not in observed:
            continue
        before = str(profile.get("model_revision" if key == "model_revision" else key, ""))
        after = str(observed.get(key, ""))
        if before != after:
            reasons.append(
                f"{key} moved from {before or 'unset'} to {after or 'unset'}; a profile measured "
                "under one identity does not carry to another"
            )
    if bool(profile.get("calibration_self_granted", False)):
        reasons.append(
            "the profile claims the runtime granted itself calibration; a runtime may not do that"
        )
    return reasons


def build_profile(
    engine: Any,
    corpus: Mapping[str, Any],
    *,
    family: str,
    report: Mapping[str, Any],
    development: Mapping[str, Any],
    threshold: Mapping[str, Any],
    temperature: Mapping[str, Any],
) -> dict:
    """Assemble a real calibration profile for one family, from measured evidence only.

    ``report`` is the held-out evaluation; ``development`` is the development sweep. Mixing
    them would make the profile self-referential, so the measured quality recorded here is
    the out-of-sample one and the fitted parameters are the ones fitted on development.
    """
    from ..decisions.runtime import seeds

    catalogue = {
        str(question["question_id"]): question
        for question, _ in seeds.seed_families().values()
    }
    question = catalogue[definition_for(str(family))["question_id"]]
    metrics = dict(report.get("metrics", {}) or {})
    observed = identity(engine, family=family)
    method = str(temperature.get("method", "MEASURED_ONLY"))
    dataset = dataset_digest_for(corpus, family=family)
    measured_size = int(metrics.get("answered", 0) or 0)
    profile = runtime_profiles.build_profile(
        decision_definition=definition_for(str(family))["definition"],
        questions=[question],
        runtime=str(observed.get("runtime", "local_bounded")),
        implementation=str(observed.get("implementation", "")),
        model="ariadne-reference-bounded",
        revision=str(observed.get("model_revision", "")),
        dataset_digest=dataset,
        dataset_size=measured_size,
        accuracy=float(metrics.get("accuracy") or 0.0),
        coverage=float(metrics.get("coverage") or 0.0),
        ece=float(metrics.get("ece") or 0.0),
        brier=float(metrics.get("brier") or 0.0),
        calibration_method=method,
        thresholds_by_risk={"LOW": float(threshold.get("threshold") or 0.0)} if threshold.get("threshold") else {},
        owner="ar-223-verification-engineer",
        note=(
            f"measured on {measured_size} out-of-sample cases; threshold fitted on the "
            f"development split alone; calibration method {method}"
        ),
    )
    record = profile.as_record()
    record["ar223"] = {
        "calibration_version": CALIBRATION_VERSION,
        "family": str(family),
        "identity": observed,
        "threshold_fit": dict(threshold),
        "temperature": dict(temperature),
        "measured_split": ",".join(MEASURED_SPLITS),
        "fitted_split": "DEVELOPMENT",
        "dataset_digest": dataset,
        "confers_authority": False,
        "authorization_effect": "none",
    }
    return record


def confers(state: Mapping[str, Any], **options: Any) -> dict:
    """Whether the runtime may describe a probability as calibrated, per AR-206's own gate.

    A thin, honest delegate. Re-implementing the match would be a second answer to "is this
    profile still the profile that was measured", and two answers is how a stale profile
    keeps working.
    """
    return runtime_profiles.profile_for(state, **options)


def require_current(record: Mapping[str, Any], engine: Any, *, family: str) -> dict:
    """Refuse to hand out a profile whose identity no longer matches what is running."""
    block = dict(record.get("ar223", {}) or {})
    recorded = dict(block.get("identity", {}) or {})
    observed = identity(engine, family=family)
    reasons = stale_reasons(recorded, observed)
    if reasons:
        raise ContractError(
            "this calibration profile does not describe the system that is running: "
            + "; ".join(reasons)
        )
    return {"current": True, "identity": observed, "reasons": []}


def fit(
    engine: Any,
    corpus: Mapping[str, Any] | None = None,
    *,
    held_out_report: Mapping[str, Any] | None = None,
    families: Sequence[str] = FAMILIES,
    owner: str = "ar-223-verification-engineer",
) -> dict:
    """Fit thresholds and temperatures on development, then measure on evaluation cases.

    The order is the whole point: the sweep reads ``DEVELOPMENT`` only, and the profile's
    quality numbers come from a report this function did not have while fitting.

    The measured splits are ``HELD_OUT`` and ``REAL_WORLD``. ``ADVERSARIAL`` is excluded on
    purpose -- it is deliberately unrepresentative, and a corpus that let a stress set license
    production authority would be measuring its own construction. Its findings are reported
    elsewhere; they do not grant anything.
    """
    from . import corpus_data
    from . import evaluation

    document = corpus or corpus_data.corpus()
    sweep = evaluation.sweep(engine)
    report = held_out_report or evaluation.evaluate(
        engine, document, splits=list(MEASURED_SPLITS)
    )
    profiles: dict[str, dict] = {}
    unfittable: dict[str, str] = {}
    for family in families:
        block = dict(report.get("families", {}).get(family, {}) or {})
        curve = list(sweep.get("curves", {}).get(family, []) or [])
        threshold = fit_threshold(curve)
        development_rows = list(sweep.get("rows", {}).get(family, []) or [])
        temperature = fit_temperature(development_rows)
        if threshold.get("threshold") is None:
            unfittable[family] = str(threshold.get("reason", ""))
            continue
        record = build_profile(
            engine,
            document,
            family=family,
            report=block,
            development={"points": development_rows},
            threshold=threshold,
            temperature=temperature,
        )
        record["ar223"]["fitted_cases"] = len(development_rows)
        profiles[family] = record
    return {
        "calibration_version": CALIBRATION_VERSION,
        "corpus_digest": str(document.get("corpus_digest", "")),
        "profiles": profiles,
        "unfittable": unfittable,
        "owner": owner,
        "policy": dict(THRESHOLD_POLICY),
        "note": (
            "every threshold and temperature in this report was fitted against the development "
            "split; the quality numbers come from held-out cases. Nothing here was tuned on the "
            "numbers it reports"
        ),
        "authorization_effect": "none",
    }


def describe() -> dict:
    return {
        "version": CALIBRATION_VERSION,
        "identity_keys": list(IDENTITY_KEYS),
        "min_cases": MIN_CALIBRATION_CASES,
        "threshold_policy": dict(THRESHOLD_POLICY),
        "temperature_grid": list(TEMPERATURE_GRID),
        "invalidation": (
            "any identity dimension that moves invalidates the claim. Nothing is inherited "
            "across a model, runtime, prompt, schema, behaviour or corpus change"
        ),
        "authorization_effect": "none",
    }


__all__ = [
    "CALIBRATION_VERSION",
    "IDENTITY_KEYS",
    "MIN_CALIBRATION_CASES",
    "TEMPERATURE_GRID",
    "THRESHOLD_POLICY",
    "build_profile",
    "confers",
    "describe",
    "fit",
    "fit_temperature",
    "fit_threshold",
    "identity",
    "require_current",
    "stale_reasons",
]