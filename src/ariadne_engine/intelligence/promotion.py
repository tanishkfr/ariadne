"""Decide whether measured quality is enough to be *acted upon*, and take the authority back when it stops being.

AR-206 already knows how to hold a calibration profile, and it sets ``PROVEN`` from one thing:
the dataset was big enough and a method really ran. That is a statement about *evidence*, not
about *merit*. A profile over three hundred cases of a 31%-accurate classifier is thoroughly
measured and completely undeserving of authority, and AR-206's own vocabulary says so --
``authorization_effect`` is ``none`` on every record it writes.

So this module is the second gate, and it is the one that decides authority:

* :data:`POLICY` states, in advance and in public, what measured quality is worth. Each bound
  has a reason attached in :func:`describe`;
* :func:`assess` compares a measured report against that policy and returns the reasons it
  failed, not a score;
* :func:`promote` drives the **real** AR-206 adoption lifecycle -- ``UNTESTED -> SHADOW ->
  EVALUATED -> ELIGIBLE -> ACTIVE`` -- through
  :mod:`ariadne_engine.decisions.runtime.promotion`, so every status change is an adoption
  event with a reason and an evaluation id, and ``ACTIVE`` remains reachable only from
  ``ELIGIBLE``;
* :func:`enforce_health` compares a new run against the baseline that was promoted on and
  **suspends** an ``ACTIVE`` slice when the measured quality has degraded beyond the same
  policy. Reversible, evidenced, and the only automatic removal of authority in the engine.

**What promotion never does.** It never grants permission. An ``ACTIVE`` slice means "for this
decision definition, at this question version, under this model revision, at this risk class,
the bounded runtime may answer instead of escalating." It does not mean the work is accepted,
a grant may be issued, or a human gate is satisfied. Those are separate authorities with
separate owners, and :mod:`~ariadne_engine.intelligence.scheduler` refuses to cross them.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from ..contracts import ContractError
from ..decisions.runtime import promotion as runtime_promotion
from .calibration import MEASURED_SPLITS
from .corpus import FAMILIES, FAMILY_DEFINITIONS
from .corpus_data import corpus as authored_corpus

PROMOTION_VERSION = "ar-223-verified-promotion-1"

POLICY = {
    "min_accuracy": 0.90,
    "max_ece": 0.10,
    "max_selective_error_rate": 0.10,
    "min_coverage": 0.40,
    "max_high_confidence_errors": 0,
    "min_adversarial_accuracy": 0.60,
    "min_measured_cases": 50,
}
"""What measured quality buys authority. Declared, reasoned, and applied unchanged.

Each bound, and why it is there:

``min_accuracy`` 0.90
    A bounded classifier that cannot name the class nine times in ten does not deserve to
    answer instead of escalating. Below that it is a coin-toss with extra steps.
``max_ece`` 0.10
    Provider probability that misses reality by more than a tenth is not calibrated
    confidence, whatever the field says on the record.
``max_selective_error_rate`` 0.10
    The same bound on the errors *among the cases it chose to answer*, which is the number
    that actually bounds harm. Plain accuracy can hide it by abstaining on everything.
``min_coverage`` 0.40
    An engine that can only answer two cases in five is not useless -- the scheduler escalates
    the rest -- but below that it is theatre, and promotion should say so.
``max_high_confidence_errors`` 0
    Zero, not a small number. Confidently wrong is the one failure a bounded authority cannot
    absorb at any rate, because the confidence is exactly what would have suppressed the
    check.
``min_adversarial_accuracy`` 0.60
    Authority has to survive the cases written to break it. A family that is excellent on
    ordinary input and collapses on adversarial input has learned the ordinary input.
``min_measured_cases`` 50
    AR-206's floor, restated here so a profile cannot be both "measured" and "too small to
    license anything" and leave the gap unstated.
"""

RISK_BY_FAMILY = {
    "FAILURE_CLASSIFICATION": "LOW",
    "REVIEW_ESCALATION": "MEDIUM",
    "EVIDENCE_RELEVANCE": "LOW",
    "ROUTE_FAMILY": "LOW",
}
"""The risk class each family's slice may serve.

Taken from the consequence the real integration attaches to the question, not from how well
the engine did. ``scope_matches`` only ever narrows, so an ``ACTIVE`` ``LOW`` slice cannot be
borrowed for a ``MEDIUM`` request -- which is what makes risk-aware scheduling possible
without a second mechanism.
"""


def scope_for(family: str) -> dict:
    """The adoption scope a family may hold.

    ``verification_available`` is true because every promoted family must be able to point at
    the evaluation that justified it; declaring otherwise would make the slice refuse the very
    evidence that promoted it.
    """
    return {
        "risk": str(RISK_BY_FAMILY.get(str(family), "LOW")),
        "reversible": True,
        "verification_available": True,
        "languages": ["en"],
    }


def _metric(report: Mapping[str, Any], name: str) -> Any:
    block = report.get("metrics") if isinstance(report, Mapping) else None
    return block.get(name) if isinstance(block, Mapping) else None


def assess(
    report: Mapping[str, Any],
    *,
    adversarial: Mapping[str, Any] | None = None,
    policy: Mapping[str, Any] | None = None,
) -> dict:
    """Whether one family's measured report satisfies :data:`POLICY`.

    Returns every failing reason, not the first one. A promotion gate that stops explaining
    after the first objection gets worked around by relaxing that objection.
    """
    rules = dict(policy or POLICY)
    reasons: list[str] = []
    accuracy = _metric(report, "accuracy")
    ece = _metric(report, "ece")
    selective = _metric(report, "selective_error_rate")
    coverage = _metric(report, "coverage")
    confident_errors = _metric(report, "high_confidence_errors")
    cases = _metric(report, "cases")
    if not isinstance(accuracy, (int, float)) or accuracy < float(rules["min_accuracy"]):
        reasons.append(
            f"accuracy {accuracy} is below the {rules['min_accuracy']} this family needs before it "
            "may answer instead of escalating"
        )
    if not isinstance(ece, (int, float)) or ece > float(rules["max_ece"]):
        reasons.append(
            f"ECE {ece} exceeds {rules['max_ece']}; the runtime reports provider probability and "
            "this is how far that number is from reality"
        )
    if not isinstance(selective, (int, float)) or selective > float(rules["max_selective_error_rate"]):
        reasons.append(
            f"selective error rate {selective} exceeds {rules['max_selective_error_rate']} among the "
            "cases it chose to answer"
        )
    if not isinstance(coverage, (int, float)) or coverage < float(rules["min_coverage"]):
        reasons.append(
            f"coverage {coverage} is below {rules['min_coverage']}; below that the bounded path is "
            "ceremony and the escalation path is the only honest one"
        )
    if not isinstance(confident_errors, int) or confident_errors > int(rules["max_high_confidence_errors"]):
        reasons.append(
            f"{confident_errors} confidently wrong answers against a budget of "
            f"{rules['max_high_confidence_errors']}"
        )
    if adversarial is not None:
        adversarial_accuracy = _metric(adversarial, "accuracy")
        if not isinstance(adversarial_accuracy, (int, float)) or adversarial_accuracy < float(
            rules["min_adversarial_accuracy"]
        ):
            reasons.append(
                f"adversarial accuracy {adversarial_accuracy} is below "
                f"{rules['min_adversarial_accuracy']}; authority has to survive the cases written "
                "to break it"
            )
    if not isinstance(cases, int) or cases < int(rules["min_measured_cases"]):
        reasons.append(
            f"{cases} measured cases is below the {rules['min_measured_cases']} a profile needs; a "
            "small measurement is an anecdote with a decimal point"
        )
    return {
        "family": str(report.get("family", "")),
        "promotable": not reasons,
        "reasons": reasons,
        "policy": rules,
        "measured": {
            "accuracy": accuracy,
            "ece": ece,
            "selective_error_rate": selective,
            "coverage": coverage,
            "high_confidence_errors": confident_errors,
            "cases": cases,
            "adversarial_accuracy": _metric(adversarial or {}, "accuracy"),
        },
        "authorization_effect": "none",
    }


def promote(
    state: dict,
    *,
    family: str,
    profile: Mapping[str, Any],
    measured: Mapping[str, Any],
    adversarial: Mapping[str, Any] | None = None,
    model_revision: str,
    question_version: str = "1",
    task_id: str = "",
    owner: str = "ar-223-verification-engineer",
    evaluation_id: str = "",
) -> dict:
    """Walk one family through the real lifecycle, or refuse at the gate with reasons.

    The happy path performs five transitions, each with its own reason and the evaluation id
    that justifies it, and each validated by AR-206's own transition rules. The unhappy path
    stops at ``EVALUATED``: the profile keeps whatever quality evidence it has, the slice is
    recorded, and ``ACTIVE`` is simply not reachable. A refused promotion leaves evidence
    behind rather than nothing, because "we measured it and it was not good enough" is the
    finding this milestone most needs to keep.
    """
    if str(family) not in FAMILIES:
        raise ContractError(f"unknown decision family: {family!r}")
    verdict = assess(
        {"family": str(family), "metrics": dict(measured)},
        adversarial={"metrics": dict(adversarial or {})},
    )
    definition = FAMILY_DEFINITIONS[str(family)]["definition"]
    evaluation_id = str(
        evaluation_id or dict(measured).get("evaluation_id", "")
    ) or str(dict(adversarial or {}).get("evaluation_id", ""))
    if not evaluation_id:
        raise ContractError(
            f"cannot promote {family} without an evaluation to cite: AR-206 requires an "
            "evaluation identity for ELIGIBLE and ACTIVE, and a promotion with nothing behind "
            "it is an assertion"
        )
    existing = runtime_promotion.find(
        state,
        decision_definition=definition,
        question_version=str(question_version),
        model_revision=str(model_revision),
    )
    if existing is None:
        record = runtime_promotion.open_slice(
            state,
            decision_definition=definition,
            question_version=str(question_version),
            model_revision=str(model_revision),
            scope=scope_for(family),
            runtime=str(model_revision),
            task_id=str(task_id),
            note=f"AR-223 opened this slice after measuring {dict(measured).get('cases')} cases",
        )
        slice_id = str(record["slice_id"])
    else:
        slice_id = str(existing["slice_id"])

    steps: list[dict] = []
    state, _ = _transition(state, slice_id, "SHADOW", reason="opened under shadow so the runtime could observe without being obeyed")
    steps.append({"status": "SHADOW", "reason": "observed before obeyed"})
    runtime_promotion.transition(
        state,
        slice_id,
        "EVALUATED",
        reason=(
            f"evaluated against the AR-223 policy over {','.join(MEASURED_SPLITS)}"
            + (f" (report {evaluation_id})" if evaluation_id else "")
        ),
        evaluation_id=evaluation_id,
        note=json_reasons(verdict),
    )
    steps.append({"status": "EVALUATED", "reason": json_reasons(verdict)})
    if verdict["promotable"]:
        state, _ = _transition(state, slice_id, "ELIGIBLE", reason=eligibility_reason(verdict))
        steps.append({"status": "ELIGIBLE", "reason": eligibility_reason(verdict)})
        state, _ = _transition(state, slice_id, "ACTIVE", reason="promoted under the AR-223 policy")
        steps.append({"status": "ACTIVE", "reason": "measured quality reached the policy"})
    return {
        "promotion_version": PROMOTION_VERSION,
        "family": str(family),
        "slice_id": slice_id,
        "status": str(runtime_promotion.find(state, decision_definition=definition, question_version=str(question_version), model_revision=str(model_revision))["status"]),
        "scope": scope_for(family),
        "verdict": verdict,
        "steps": steps,
        "profile_id": str(dict(profile).get("profile_id", "")),
        "profile_status": str(dict(profile).get("status", "")),
        "owner": owner,
        "authority": (
            "may answer this decision at this question version under this model revision within "
            "its risk class; grants nothing"
            if verdict["promotable"]
            else "none: the measured quality did not reach the policy"
        ),
        "authorization_effect": "none",
        "state": state,
    }


def _transition(state: dict, slice_id: str, target: str, *, reason: str) -> tuple[dict, str]:
    """One lifecycle transition, tolerant of a slice that is already there.

    Idempotent because a re-run on the same evidence should be a no-op rather than an error,
    and because ``SHADOW`` is both the first and a legal later target. AR-206's
    ``transition`` mutates the state in place and returns the updated *record*, so the state
    is handed straight back rather than reassigned from the return value.
    """
    record = _find(state, slice_id)
    if str(record.get("status", "")) == target:
        return state, slice_id
    runtime_promotion.transition(state, slice_id, target, reason=reason)
    return state, slice_id


def _find(state: Mapping[str, Any], slice_id: str) -> dict:
    for record in _all(state):
        if str(record.get("slice_id", "")) == str(slice_id):
            return dict(record)
    return {}


def _all(state: Mapping[str, Any]) -> list[dict]:
    rows = state.get("decision_adoption") if isinstance(state, Mapping) else None
    return [dict(value) for value in rows or [] if isinstance(value, Mapping)]


def eligibility_reason(verdict: Mapping[str, Any]) -> str:
    """The sentence attached to the ``ELIGIBLE`` transition.

    Written from the measured numbers rather than from a template, because the history of an
    adoption slice is exactly the place where a vague reason becomes indistinguishable from
    no reason at all.
    """
    measured = dict(verdict.get("measured", {}))
    return (
        f"eligible on measured evidence: accuracy {measured.get('accuracy')}, "
        f"ECE {measured.get('ece')}, selective error {measured.get('selective_error_rate')}, "
        f"coverage {measured.get('coverage')}, confidently wrong {measured.get('high_confidence_errors')}, "
        f"adversarial accuracy {measured.get('adversarial_accuracy')}"
    )


def json_reasons(verdict: Mapping[str, Any]) -> str:
    return "; ".join(str(reason) for reason in dict(verdict).get("reasons", []) or []) or "policy satisfied"


def enforce_health(
    state: dict,
    *,
    family: str,
    baseline: Mapping[str, Any],
    candidate: Mapping[str, Any],
    reason: str = "",
) -> dict:
    """Compare a new run against the promoted baseline and suspend authority if it degraded.

    The only automatic removal of authority in Ariadne, and deliberately the mirror image of
    promotion: the same policy numbers, read in the same direction, with the same refusal to
    proceed on a missing value.
    """
    from .evaluation import degradation

    report = degradation(
        {key: value for key, value in dict(baseline).items() if key != "family"},
        {key: value for key, value in dict(candidate).items() if key != "family"},
        max_accuracy_drop=0.05,
        max_ece_rise=0.05,
        max_selective_error_rise=0.05,
        max_confident_errors=0,
    )
    definition = FAMILY_DEFINITIONS[str(family)]["definition"]
    slices = runtime_promotion.slices(state, decision_definition=definition)
    active = [record for record in slices if str(record.get("status", "")) == "ACTIVE"]
    if not report["degraded"] or not active:
        return {
            "promotion_version": PROMOTION_VERSION,
            "family": str(family),
            "action": "none",
            "degradation": report,
            "active_slices": [str(record.get("slice_id", "")) for record in active],
        }
    record = dict(active[-1])
    why = reason or "; ".join(report["reasons"])
    runtime_promotion.suspend(
        state,
        str(record.get("slice_id", "")),
        reason=f"measured degradation: {why}",
        note="AR-223 health enforcement; reversible by re-promotion under the same policy",
    )
    return {
        "promotion_version": PROMOTION_VERSION,
        "family": str(family),
        "action": "suspended",
        "slice_id": str(record.get("slice_id", "")),
        "degradation": report,
        "reversible": True,
        "state": state,
    }


def run_and_promote(
    engine: Any,
    state: dict,
    *,
    corpus: Mapping[str, Any] | None = None,
    families: Sequence[str] = FAMILIES,
    model_revision: str = "",
    task_id: str = "",
    owner: str = "ar-223-verification-engineer",
) -> dict:
    """Measure the shipped engine, then let the policy decide what happens to it.

    The whole vertical slice in one call, in the only order that keeps the evidence
    independent: fit on development, measure out-of-sample, produce the evaluation record,
    then promote or refuse. Nothing here is allowed to look at a held-out number before the
    threshold exists, and the caller receives the reports alongside the decisions so a reader
    can check that rather than take it.
    """
    from . import calibration
    from . import evaluation

    document = corpus or authored_corpus()
    fit_report = calibration.fit(engine, document)
    thresholds = {
        family: float(record["ar223"]["threshold_fit"]["threshold"])
        for family, record in fit_report["profiles"].items()
        if record.get("ar223", {}).get("threshold_fit", {}).get("threshold") is not None
    }
    measured = evaluation.evaluate(
        engine, document, splits=list(calibration.MEASURED_SPLITS), min_confidence_by_family=thresholds
    )
    adversarial = evaluation.evaluate(
        engine, document, splits=["ADVERSARIAL"], min_confidence_by_family=thresholds
    )
    revision = str(model_revision or measured.get("runtime", {}).get("model_revision", ""))
    outcomes: dict[str, dict] = {}
    for family in families:
        block = dict(measured.get("families", {}).get(family, {}) or {})
        if not block:
            continue
        report = evaluation.canonical_report(
            engine,
            document,
            family=family,
            splits=list(calibration.MEASURED_SPLITS),
            min_confidence=thresholds.get(family),
        )
        outcome = promote(
            state,
            family=family,
            profile=dict(fit_report["profiles"].get(family, {})),
            measured=dict(block.get("metrics", {})),
            adversarial=dict(adversarial.get("families", {}).get(family, {}).get("metrics", {})),
            model_revision=revision,
            task_id=str(task_id),
            owner=str(owner),
            evaluation_id=str(report.get("evaluation_id", "")),
        )
        state = dict(outcome.pop("state"))
        outcome["evaluation_id"] = str(report.get("evaluation_id", ""))
        outcome["metrics"] = dict(block.get("metrics", {}))
        outcome["adversarial_metrics"] = dict(
            adversarial.get("families", {}).get(family, {}).get("metrics", {})
        )
        outcomes[family] = outcome
    return {
        "promotion_version": PROMOTION_VERSION,
        "model_revision": revision,
        "thresholds": thresholds,
        "policy": dict(POLICY),
        "calibration": {
            "profiles": {
                family: {
                    "profile_id": str(record.get("profile_id", "")),
                    "status": str(record.get("status", "")),
                    "dataset_size": int(record.get("dataset_size", 0) or 0),
                    "calibration_method": str(record.get("calibration_method", "")),
                }
                for family, record in fit_report["profiles"].items()
            },
            "unfittable": dict(fit_report["unfittable"]),
        },
        "outcomes": outcomes,
        "promoted": sorted(
            family for family, outcome in outcomes.items() if outcome["verdict"]["promotable"]
        ),
        "refused": sorted(
            family for family, outcome in outcomes.items() if not outcome["verdict"]["promotable"]
        ),
        "report": (
            "families whose measured quality reached the policy are ACTIVE inside their declared "
            "risk class; the rest are recorded as EVALUATED with their reasons. Nothing here "
            "grants authority beyond answering a bounded question"
        ),
        "authorization_effect": "none",
        "state": state,
    }


def summarise(state: Mapping[str, Any]) -> dict:
    """Every adoption slice, its status, and what that status is worth."""
    records = _all(state)
    return {
        "promotion_version": PROMOTION_VERSION,
        "policy": dict(POLICY),
        "slices": [
            {
                "slice_id": str(record.get("slice_id", "")),
                "decision_definition": str(record.get("decision_definition", "")),
                "question_version": str(record.get("question_version", "")),
                "model_revision": str(record.get("model_revision", "")),
                "status": str(record.get("status", "")),
                "scope": dict(record.get("scope", {}) or {}),
                "history": [dict(step) for step in record.get("history", []) or []],
            }
            for record in records
        ],
        "active": [
            str(record.get("decision_definition", "")) for record in records
            if str(record.get("status", "")) == "ACTIVE"
        ],
        "invariant": (
            "an ACTIVE slice answers bounded questions inside its risk class. It approves nothing, "
            "grants nothing, and accepts nothing"
        ),
        "authorization_effect": "none",
    }


def describe() -> dict:
    return {
        "version": PROMOTION_VERSION,
        "policy": dict(POLICY),
        "risk_by_family": dict(RISK_BY_FAMILY),
        "lifecycle": list(runtime_promotion.TRANSITIONS),
        "gate": (
            "AR-206 sets PROVEN from evidence volume; this module sets ACTIVE from measured merit. "
            "Both are required and neither substitutes for the other"
        ),
        "removes_authority": "enforce_health, on measured degradation against the promoted baseline",
        "authorization_effect": "none",
    }


__all__ = [
    "POLICY",
    "PROMOTION_VERSION",
    "RISK_BY_FAMILY",
    "assess",
    "describe",
    "eligibility_reason",
    "enforce_health",
    "promote",
    "run_and_promote",
    "scope_for",
    "summarise",
]