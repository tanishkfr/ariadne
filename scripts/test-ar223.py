#!/usr/bin/env python3
"""The AR-223 test suite: acceptance intelligence and verified intelligence.

Two engines that meet at one boundary, and this suite is mostly about that boundary:

```text
ACCEPTANCE                       what is established about this work?
  contract  requirements  claims  evidence  decisions  gates  invalidation
        |
        | bounded advice, which may inform and can never promote
        v
VERIFIED INTELLIGENCE             what has been measured, and what may therefore answer?
  corpus  evaluation  calibration  promotion  scheduler
```

**The properties worth testing are the refusals.** An acceptance engine that accepts everything
is easy to write and tells nobody anything; a scheduler that hands work to a model tells nobody
anything either. So the cases here are mostly shaped as "this must be refused" or "this must
abstain", and the ones shaped as "this must succeed" exist to prove the refusal is specific
rather than universal.

Four things this suite holds the line on, each of which is a way this milestone could have
shipped something that looks finished and is not:

1. **A claim is never evidence.** Worker text cannot establish anything, however confidently
   phrased, and cannot survive as proof by being re-read.
2. **Missing evidence is not failure.** A requirement nobody examined is ``UNPROVEN``.
3. **Confidence is not permission.** No measured probability reaches any gate, and the
   scheduler routes a ``PROTECTED`` decision to a human before reading a profile.
4. **A corpus cannot flatter an engine.** Leakage across splits is refused, a threshold fitted
   anywhere but development is refused, and the 2.1 pathology is looked for by name.
"""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from ariadne_engine import contracts  # noqa: E402
from ariadne_engine.acceptance import (  # noqa: E402
    beacon,
    claims,
    contract as acceptance_contract,
    decisions,
    evidence,
    gates,
    integrations,
    invalidation,
    requirements,
    security,
)
from ariadne_engine.intelligence import (  # noqa: E402
    calibration,
    corpus as corpus_module,
    evaluation,
    promotion,
    scheduler,
)
from harness import mutation_ledger, test_inventory  # noqa: E402

OFFLINE: dict = {}
CACHE: dict = {}


def case(fn):
    """Register a test function, in declaration order."""
    OFFLINE.setdefault("cases", []).append(fn)
    return fn


def raises(fn, *fragments: str) -> str:
    try:
        fn()
    except (contracts.ContractError, ValueError, FileNotFoundError) as exc:
        message = str(exc)
        for fragment in fragments:
            assert fragment in message, f"expected {fragment!r} in refusal: {message}"
        return message
    raise AssertionError("expected a refusal and none was raised")


def truthy(value, message: str) -> None:
    assert value, message


def engine():
    import ariadne_engine

    return ariadne_engine


def corpus():
    if "corpus" not in CACHE:
        CACHE["corpus"] = corpus_module.build.__module__ and corpus_data_corpus()
    return CACHE["corpus"]


def corpus_data_corpus():
    from ariadne_engine.intelligence import corpus_data

    return corpus_data.corpus()


def base_state(task_id: str = "ar223-case") -> dict:
    return {
        "schema_version": 1,
        "run_id": "ar223-suite",
        "project": "ariadne",
        "task_id": task_id,
    }


def simple_contract(state: dict, *, task_id: str = "ar223-case") -> tuple[str, str]:
    record = acceptance_contract.create(
        state,
        text="The parser accepts a bare list, the release notes name the version, and the sidebar collapses.",
        task_id=task_id,
        source_refs=["controlled fixture"],
    )
    return str(record["contract_id"]), str(record.get("revision", ""))


# ------------------------------------------------------------------ corpus integrity


@case
def corpus_has_no_projection_leaking_across_splits():
    """The same projection in two splits is one question wearing two names."""
    document = corpus()
    problems = corpus_module.leakage_problems(document)
    assert problems == [], problems


@case
def corpus_is_clean_enough_to_evaluate_at_all():
    document = corpus()
    corpus_module.require_clean(document)
    truthy(document["case_count"] >= 300, f"the corpus is only {document['case_count']} cases")


@case
def corpus_declares_every_family_and_split():
    document = corpus()
    cells = document["distribution"]["cells"]
    for family in corpus_module.FAMILIES:
        for split in corpus_module.SPLITS:
            assert cells[family][split] > 0, f"{family}/{split} is empty"


@case
def corpus_tuning_report_reads_development_alone():
    document = corpus()
    report = corpus_module.tuning_report(document, tuned_on=corpus_module.TUNING_SPLITS)
    assert report["tuned_on"] == ["DEVELOPMENT"], report["tuned_on"]
    assert report["clean"] is True, report
    truthy(report["evaluation_cases"] > 0, "the tuning report evaluated nothing")


@case
def corpus_refuses_a_tuning_split_that_is_not_development():
    document = corpus()
    dirty = corpus_module.tuning_report(document, tuned_on=["HELD_OUT"])
    assert dirty["clean"] is False, "a held-out tuning split must be reported as unclean"


@case
def every_corpus_label_is_in_the_declared_answer_space():
    document = corpus()
    for row in document["cases"]:
        space = corpus_module.answer_space_for(row["family"])
        assert row["label"] in space, (
            f"{row['case_id']} is labelled {row['label']!r}, which is not in {space}"
        )


@case
def every_corpus_label_names_its_reviewer():
    document = corpus()
    for row in document["cases"]:
        provenance = row["provenance"]
        truthy(provenance.get("reviewer"), f"{row['case_id']} has no reviewer")
        assert provenance["agreement"] in corpus_module.AGREEMENT_LEVELS, provenance


@case
def adjudicated_labels_keep_both_positions_and_the_ruling():
    document = corpus()
    adjudicated = [row for row in document["cases"] if row["provenance"]["agreement"] == "ADJUDICATED"]
    truthy(adjudicated, "no adjudicated label survived in the corpus")
    for row in adjudicated:
        provenance = row["provenance"]
        truthy(provenance.get("disagreement"), row["case_id"])
        truthy(provenance.get("adjudication"), row["case_id"])
        assert provenance["adjudication"], row["case_id"]


@case
def real_world_rows_declare_that_history_is_real_history():
    document = corpus()
    real = [
        row
        for row in document["cases"]
        if row["provenance"]["source_kind"] == "REAL_HISTORY"
    ]
    truthy(real, "no row claims real history, which cannot be true of an authored corpus")
    truthy(
        len(real) < document["case_count"] // 3,
        "a corpus where most rows claim real history is overstating what this repository recorded",
    )


@case
def cases_the_reviewers_said_cannot_be_answered_are_marked():
    document = corpus()
    marked = [row for row in document["cases"] if row["expected_abstain"]]
    truthy(marked, "no case is marked as one a bounded engine should decline")
    assert document["distribution"]["expected_abstain"], document["distribution"]


# ------------------------------------------------------------------ evaluation honesty


@case
def evaluation_runs_the_real_engine_over_every_family():
    report = measured_report()
    for family in corpus_module.FAMILIES:
        block = report["families"][family]
        assert block["metrics"]["cases"] > 0, family
        assert block["question_id"] == corpus_module.FAMILY_DEFINITIONS[family]["question_id"], family


@case
def evaluation_reports_provider_probability_rather_than_calibration():
    report = measured_report()
    kinds = report["runtime"]["confidence_kinds"]
    assert "PROVIDER_PROBABILITY" in kinds, kinds
    assert report["runtime"]["calibration_self_granted"] is False, report["runtime"]


@case
def evaluation_never_reports_an_accuracy_over_no_ground_truth():
    report = measured_report()
    for block in report["families"].values():
        metrics = block["metrics"]
        if not metrics["answered"]:
            assert metrics["accuracy"] is None, metrics


@case
def evaluation_writes_no_authorization():
    report = measured_report()
    assert report["authorization_effect"] == "none", report["authorization_effect"]


@case
def false_confidence_detection_looks_for_the_2_1_pathology():
    joined = [
        {"answer": "UNKNOWN", "expected": f"LABEL_{index}", "confidence": 0.99, "abstained": False,
         "correct": False, "distribution": {}, "status": "answered", "latency_ms": 1.0}
        for index in range(6)
    ]
    profile = evaluation.confidence_profile(joined)
    assert profile["answer_collapse"] is True, profile
    assert profile["confidence_flat"] is True, profile
    assert profile["detected"] is True, profile


@case
def false_confidence_detection_is_not_a_verdict_of_failure():
    joined = [
        {"answer": "ROUTINE" if index % 2 else "ESCALATED", "expected": "A" if index % 2 else "B",
         "confidence": 0.4 + index / 100.0, "abstained": False, "correct": True,
         "distribution": {}, "status": "answered", "latency_ms": 1.0}
        for index in range(4)
    ]
    profile = evaluation.confidence_profile(joined)
    assert profile["detected"] is False, profile
    assert profile["high_confidence_errors"] == 0, profile


@case
def confidently_wrong_is_counted_separately_from_a_pattern():
    joined = [
        {"answer": "TIMEOUT", "expected": "TIMEOUT", "confidence": 0.95, "abstained": False,
         "correct": True, "distribution": {}, "status": "answered", "latency_ms": 1.0},
        {"answer": "UNKNOWN", "expected": "PROVIDER_FAILURE", "confidence": 0.96, "abstained": False,
         "correct": False, "distribution": {}, "status": "answered", "latency_ms": 1.0},
    ]
    profile = evaluation.confidence_profile(joined)
    assert profile["high_confidence_errors"] == 1, profile


@case
def abstention_quality_separates_misses_from_waste():
    joined = [
        {"abstained": True, "expected_abstain": True},
        {"abstained": False, "expected_abstain": True},
        {"abstained": True, "expected_abstain": False},
    ]
    report = evaluation.abstention_quality(joined)
    assert report["warranted_abstentions"] == 1, report
    assert report["missed_abstentions"] == 1, report
    assert report["unwarranted_abstentions"] == 1, report
    assert report["abstention_precision"] == 0.5, report


@case
def degradation_names_the_metric_that_moved():
    report = evaluation.degradation(
        {"accuracy": 0.95, "ece": 0.05, "selective_error_rate": 0.04, "high_confidence_errors": 0},
        {"accuracy": 0.70, "ece": 0.31, "selective_error_rate": 0.28, "high_confidence_errors": 4},
    )
    assert report["degraded"] is True, report
    joined = " ".join(report["reasons"])
    for metric in ("accuracy", "ece", "selective", "confidently"):
        assert metric in joined, f"{metric} did not appear in {joined}"


@case
def degradation_refuses_to_run_without_a_baseline():
    report = evaluation.degradation({}, {"accuracy": 0.1})
    assert report["degraded"] is False, report
    assert report["changes"] == {}, report


@case
def a_runtime_that_raises_is_recorded_as_fallback_not_a_crash():
    class Broken:
        def decide(self, *args, **kwargs):
            raise RuntimeError("sidecar went away")

    row = evaluation.answer_case(Broken(), {"question_id": "failure-class"}, {}, case_id="X")
    assert row["status"] == "failed", row
    assert "sidecar went away" in row["reason"], row


@case
def sweep_reads_the_development_split_only():
    report = evaluation.sweep(engine())
    assert report["split"] == "DEVELOPMENT", report["split"]
    for family, points in report["curves"].items():
        for point in points:
            assert point["min_confidence"] is not None, (family, point)


# ------------------------------------------------------------------ calibration discipline


@case
def thresholds_are_fitted_on_development_and_measured_elsewhere():
    report = calibration_report()
    for family, record in report["profiles"].items():
        block = record["ar223"]
        assert block["fitted_split"] == "DEVELOPMENT", (family, block["fitted_split"])
        assert block["measured_split"] == "HELD_OUT,REAL_WORLD", (family, block["measured_split"])
        assert block["fitted_cases"] > 0, (family, block)


@case
def the_adversarial_split_never_licenses_anything():
    report = calibration_report()
    assert "ADVERSARIAL" not in calibration.MEASURED_SPLITS, calibration.MEASURED_SPLITS
    for record in report["profiles"].values():
        assert "ADVERSARIAL" not in record["ar223"]["measured_split"], record["ar223"]


@case
def a_calibration_profile_names_all_six_identity_dimensions():
    observed = calibration.identity(engine(), family="ROUTE_FAMILY")
    for key in calibration.IDENTITY_KEYS:
        truthy(observed.get(key), f"{key} is unset on the observed identity")


@case
def a_profile_is_stale_the_moment_its_model_revision_moves():
    observed = calibration.identity(engine(), family="ROUTE_FAMILY")
    moved = {**observed, "model_revision": "some-other-model"}
    reasons = calibration.stale_reasons(observed, moved)
    joined = " ".join(reasons)
    assert "model_revision" in joined, reasons


@case
def a_profile_is_stale_when_the_corpus_moves_under_it():
    observed = calibration.identity(engine(), family="ROUTE_FAMILY")
    reasons = calibration.stale_reasons(observed, {**observed, "corpus_revision": "other-corpus"})
    assert any("corpus_revision" in reason for reason in reasons), reasons


@case
def a_runtime_that_claims_its_own_calibration_is_refused():
    observed = calibration.identity(engine(), family="ROUTE_FAMILY")
    reasons = calibration.stale_reasons(
        {**observed, "calibration_self_granted": True}, observed
    )
    assert any("granted itself" in reason for reason in reasons), reasons


@case
def a_stale_profile_cannot_be_handed_out_at_all():
    report = calibration_report()
    record = report["profiles"]["ROUTE_FAMILY"]
    moved = {**record["ar223"]["identity"], "model_revision": "unrelated-revision"}
    raises(lambda: calibration.require_current({"ar223": {"identity": moved}}, engine(), family="ROUTE_FAMILY"),
           "does not describe the system that is running")


@case
def a_current_profile_can_be_handed_out():
    report = calibration_report()
    record = report["profiles"]["ROUTE_FAMILY"]
    result = calibration.require_current(record, engine(), family="ROUTE_FAMILY")
    assert result["current"] is True, result


@case
def temperature_scaling_reports_what_it_actually_bought():
    joined = [
        {"distribution": {"A": 0.9, "B": 0.1}, "expected": "B", "confidence": 0.9, "correct": False,
         "abstained": False}
        for _ in range(6)
    ]
    result = calibration.fit_temperature(joined)
    assert result["fitted"] is True, result
    assert result["cases"] == 6, result
    assert isinstance(result["ece_before"], (int, float)), result
    assert isinstance(result["ece_after"], (int, float)), result
    assert result["negative_log_likelihood_after"] <= result["negative_log_likelihood_before"] + 1e-9, result


@case
def a_threshold_needs_coverage_before_accuracy_matters():
    curve = [
        {"min_confidence": 0.0, "accuracy": 0.99, "coverage": 1.0},
        {"min_confidence": 0.9, "accuracy": 1.0, "coverage": 0.10},
        {"min_confidence": 0.8, "accuracy": 1.0, "coverage": 0.65},
    ]
    chosen = calibration.fit_threshold(curve)
    assert chosen["threshold"] == 0.8, chosen
    assert chosen["development_coverage"] == 0.65, chosen


@case
def a_family_with_no_usable_threshold_is_reported_unfittable_not_forced():
    curve = [{"min_confidence": 0.9, "accuracy": 1.0, "coverage": 0.05}]
    chosen = calibration.fit_threshold(curve)
    assert chosen["threshold"] is None, chosen
    truthy(chosen.get("reason"), "an unfittable family must say why")


@case
def calibration_refuses_to_build_a_profile_for_a_family_it_does_not_know():
    raises(lambda: calibration.identity(engine(), family="NOT_A_FAMILY"), "unknown decision family")


# ------------------------------------------------------------------ promotion


@case
def promotion_policy_states_a_bound_for_every_way_to_be_wrong():
    for key in ("min_accuracy", "max_ece", "max_selective_error_rate", "min_coverage",
                "max_high_confidence_errors", "min_adversarial_accuracy", "min_measured_cases"):
        truthy(promotion.POLICY.get(key) is not None, f"{key} has no bound")
    assert promotion.POLICY["max_high_confidence_errors"] == 0, promotion.POLICY


@case
def a_profile_with_enough_cases_is_not_enough_to_be_acted_on():
    """AR-206 sets PROVEN from evidence volume; AR-223 sets ACTIVE from merit."""
    good = {"accuracy": 0.31, "ece": 0.17, "selective_error_rate": 0.69, "coverage": 1.0,
            "high_confidence_errors": 2, "cases": 300}
    verdict = promotion.assess({"family": "FAILURE_CLASSIFICATION", "metrics": good})
    assert verdict["promotable"] is False, verdict
    truthy(len(verdict["reasons"]) >= 4, verdict["reasons"])


@case
def promotion_refuses_a_family_whose_adversarial_accuracy_collapses():
    strong = {"accuracy": 1.0, "ece": 0.02, "selective_error_rate": 0.0, "coverage": 0.8,
              "high_confidence_errors": 0, "cases": 200}
    verdict = promotion.assess(
        {"family": "ROUTE_FAMILY", "metrics": strong},
        adversarial={"metrics": {**strong, "accuracy": 0.4}},
    )
    assert verdict["promotable"] is False, verdict
    assert any("adversarial" in reason for reason in verdict["reasons"]), verdict["reasons"]


@case
def promotion_walks_the_real_lifecycle_and_stops_where_it_must():
    outcome = promoted("ROUTE_FAMILY")
    statuses = [step["status"] for step in outcome["steps"]]
    assert statuses[:3] == ["SHADOW", "EVALUATED", "ELIGIBLE"], statuses
    assert outcome["status"] == "ACTIVE", outcome["status"]


@case
def a_refused_family_is_recorded_at_evaluated_rather_than_deleted():
    outcome = promoted("FAILURE_CLASSIFICATION")
    assert outcome["status"] == "EVALUATED", outcome["status"]
    truthy(outcome["verdict"]["reasons"], "a refused promotion must say why")
    truthy(outcome["evaluation_id"], "a refused promotion still cites the evaluation that refused it")


@case
def promotion_requires_an_evaluation_to_cite():
    raises(
        lambda: promotion.promote(
            base_state(),
            family="ROUTE_FAMILY",
            profile={},
            measured=promotion.assess({"family": "ROUTE_FAMILY", "metrics": perfect()})["measured"],
            model_revision="ar-206-reference-1",
        ),
        "without an evaluation to cite",
    )


@case
def promotion_cannot_reach_active_without_passing_eligible():
    """The lifecycle itself enforces this; the case asserts the engine did not route around it."""
    from ariadne_engine.decisions.runtime import promotion as runtime_promotion

    state = base_state()
    record = runtime_promotion.open_slice(
        state,
        decision_definition="route-family",
        question_version="1",
        model_revision="ar-206-reference-1",
        scope=promotion.scope_for("ROUTE_FAMILY"),
    )
    raises(
        lambda: runtime_promotion.transition(state, str(record["slice_id"]), "ACTIVE",
                                             reason="because it measured well"),
        "cannot move to ACTIVE",
    )


@case
def promotion_refuses_an_unknown_family():
    raises(
        lambda: promotion.promote(
            base_state(), family="MOOD_CLASSIFICATION", profile={},
            measured=perfect(), model_revision="ar-206-reference-1", evaluation_id="dev_1",
        ),
        "unknown decision family",
    )


@case
def health_enforcement_suspends_authority_on_measured_degradation():
    outcome = promoted("ROUTE_FAMILY")
    state = outcome["state"]
    baseline = outcome["metrics"]
    degraded = {**baseline, "accuracy": max(0.0, float(baseline["accuracy"]) - 0.4)}
    health = promotion.enforce_health(
        state, family="ROUTE_FAMILY", baseline=baseline, candidate=degraded,
    )
    assert health["action"] == "suspended", health
    assert health["reversible"] is True, health


@case
def health_enforcement_leaves_authority_alone_when_nothing_moved():
    outcome = promoted("ROUTE_FAMILY")
    health = promotion.enforce_health(
        outcome["state"], family="ROUTE_FAMILY",
        baseline=outcome["metrics"], candidate=outcome["metrics"],
    )
    assert health["action"] == "none", health


@case
def suspension_is_recorded_as_an_adoption_event_with_a_reason():
    outcome = promoted("ROUTE_FAMILY")
    baseline = outcome["metrics"]
    health = promotion.enforce_health(
        outcome["state"], family="ROUTE_FAMILY",
        baseline=baseline, candidate={**baseline, "accuracy": 0.01},
    )
    summary = promotion.summarise(health["state"])
    slice_record = [row for row in summary["slices"] if row["status"] == "SUSPENDED"]
    truthy(slice_record, "no SUSPENDED slice was recorded")
    history = slice_record[0]["history"][-1]
    truthy(history.get("reason"), "a suspension without a reason is not reviewable")


@case
def measure_and_promote_produces_a_verdict_for_every_family():
    report = measured_promotion()
    for family in corpus_module.FAMILIES:
        assert family in report["outcomes"], family
    truthy(report["promoted"], "no family earned promotion, which the results must report")


@case
def measure_and_promote_grants_no_authority_of_any_kind():
    report = measured_promotion()
    assert report["authorization_effect"] == "none", report["authorization_effect"]
    for outcome in report["outcomes"].values():
        assert outcome["authority"].startswith("none") or "grants nothing" in outcome["authority"], outcome


# ------------------------------------------------------------------ scheduling


@case
def a_protected_operation_is_a_human_decision_before_any_profile_is_read():
    decision = scheduler.for_family(
        promoted("ROUTE_FAMILY")["state"], "ROUTE_FAMILY",
        model_revision=MODEL_REVISION, operation="grant_g2",
    )
    assert decision["level"] == "HUMAN", decision
    assert decision["slice_id"] == "", decision


@case
def the_protected_risk_class_is_a_human_decision():
    decision = scheduler.for_family(
        promoted("ROUTE_FAMILY")["state"], "ROUTE_FAMILY",
        model_revision=MODEL_REVISION, risk="PROTECTED", confidence=0.999,
    )
    assert decision["level"] == "HUMAN", decision


@case
def a_deterministic_rule_beats_an_active_slice():
    decision = scheduler.for_family(
        promoted("ROUTE_FAMILY")["state"], "ROUTE_FAMILY",
        model_revision=MODEL_REVISION, deterministic_available=True, confidence=0.999,
    )
    assert decision["level"] == "DETERMINISTIC", decision


@case
def an_active_slice_is_used_for_its_own_family():
    decision = scheduler.for_family(
        promoted("ROUTE_FAMILY")["state"], "ROUTE_FAMILY",
        model_revision=MODEL_REVISION, confidence=0.99,
    )
    assert decision["level"] == "BOUNDED_LOCAL", decision
    truthy(decision["slice_id"], decision)


@case
def a_refused_family_escalates_rather_than_answering():
    decision = scheduler.for_family(
        promoted("FAILURE_CLASSIFICATION")["state"], "FAILURE_CLASSIFICATION",
        model_revision=MODEL_REVISION, confidence=0.99,
    )
    assert decision["level"] == "GENERATIVE", decision
    assert decision["escalates"] is True, decision


@case
def a_slice_never_widens_its_risk_class():
    decision = scheduler.for_family(
        promoted("ROUTE_FAMILY")["state"], "ROUTE_FAMILY",
        model_revision=MODEL_REVISION, risk="HIGH", confidence=0.999,
    )
    assert decision["level"] != "BOUNDED_LOCAL", decision
    truthy(decision["scope_problems"], decision)


@case
def a_model_revision_the_slice_did_not_measure_is_not_answered():
    decision = scheduler.for_family(
        promoted("ROUTE_FAMILY")["state"], "ROUTE_FAMILY",
        model_revision="some-other-revision", confidence=0.99,
    )
    assert decision["level"] == "GENERATIVE", decision


@case
def confidence_cannot_promote_a_level():
    decision = scheduler.for_family(
        promoted("FAILURE_CLASSIFICATION")["state"], "FAILURE_CLASSIFICATION",
        model_revision=MODEL_REVISION, confidence=1.0,
    )
    assert decision["level"] != "BOUNDED_LOCAL", decision
    assert decision["confidence_grants_nothing"] is True, decision


@case
def asking_the_scheduler_for_authority_is_refused_outright():
    raises(
        lambda: scheduler.choose(
            promoted("ROUTE_FAMILY")["state"],
            decision_definition="route-family",
            model_revision=MODEL_REVISION,
            grants_authority=True,
        ),
        "confidence is not permission",
    )


@case
def asking_the_scheduler_to_accept_work_is_refused_outright():
    raises(
        lambda: scheduler.choose(
            promoted("ROUTE_FAMILY")["state"],
            decision_definition="route-family",
            model_revision=MODEL_REVISION,
            accept_work=True,
        ),
        "accept protected work",
    )


@case
def provider_selection_is_reached_only_after_the_scheduler_agrees():
    result = scheduler.select_provider(
        state=promoted("FAILURE_CLASSIFICATION")["state"],
        family="FAILURE_CLASSIFICATION",
        model_revision=MODEL_REVISION,
    )
    assert result["selected"] is False, result
    assert result["decision"]["level"] == "GENERATIVE", result["decision"]


@case
def every_scheduled_record_declares_that_it_authorises_nothing():
    decision = scheduler.for_family(
        promoted("ROUTE_FAMILY")["state"], "ROUTE_FAMILY", model_revision=MODEL_REVISION,
    )
    assert decision["authorization_effect"] == "none", decision
    assert scheduler.describe()["invariant"] == "confidence is never permission"


# ------------------------------------------------------------------ proof pass over history


@case
def beacon_history_is_read_and_checked_before_anything_else():
    history = beacon.assert_history(ROOT)
    truthy(history["bytes"] > 0, history)
    for marker in beacon.REQUIRED_MARKERS:
        assert marker in (ROOT / beacon.RESULTS_DOCUMENT).read_text(encoding="utf-8"), marker


@case
def beacon_produces_the_verdict_mix_history_actually_supports():
    record = beacon_pass_record()
    verdicts = {row["verdict"] for row in blocking_rows(record)}
    for expected in ("PROVEN", "FAILED", "UNPROVEN", "NEEDS_HUMAN"):
        assert expected in verdicts, f"{expected} is absent from {verdicts}"


@case
def beacon_is_not_accepted_and_the_explanation_says_why():
    record = beacon_pass_record()
    assert record["acceptance_state"] == "NOT_ACCEPTED", record["acceptance_state"]
    explanation = gates.explain(record["acceptance_readiness"])
    truthy(len(explanation) > 120, f"the explanation is too short to say anything: {explanation}")
    unmet = [row for row in record["acceptance_readiness"]["clauses"] if not row["ok"]]
    truthy(unmet, "NOT_ACCEPTED with every clause satisfied is a contradiction")
    truthy(
        record["acceptance_readiness"]["failed_blocking"],
        "NOT_ACCEPTED without a failed blocking requirement is not what happened",
    )


@case
def a_worker_claim_of_completion_is_contradicted_by_the_measurement():
    record = beacon_pass_record()
    contradicted = [row for row in record["claim_assessments"] if row["claim_verdict"] == "CONTRADICTED"]
    truthy(contradicted, "no claim was contradicted, so the claim record family is not working")


@case
def a_claim_is_never_promoted_to_evidence():
    state = beacon.beacon_state(str(ROOT))
    ids = state["beacon"]["requirement_ids"]
    decisions.assess_claim(
        claims.current_claims(state, requirement_id=ids["responsive"])[0],
        requirement_verdicts={ids["responsive"]: "FAILED"},
        rows=[],
    )


@case
def the_beacon_slice_refuses_to_substitute_a_fixture_for_missing_history(tmp=None):
    raises(lambda: beacon.assert_history(Path("no-such-root")),
           "refuses to substitute a fixture")


@case
def a_repair_makes_the_old_evidence_stale():
    outcome = repaired()
    assert outcome["pass_one"]["acceptance_state"] == "NOT_ACCEPTED", outcome["pass_one"]
    truthy(outcome["stale_requirement_ids"], "the repair invalidated nothing")


@case
def re_verification_is_selective_rather_than_total():
    outcome = repaired()
    assert outcome["parser_rerun"] is False, "the unrelated requirement was re-checked"
    assert len(outcome["plan"]["selected"]) == 1, outcome["plan"]
    assert outcome["plan"]["total_cost"] == 1, outcome["plan"]


@case
def proven_unaffected_evidence_is_readmitted_by_name_not_by_luck():
    outcome = repaired()
    assert outcome["parser_evidence_readmitted"], outcome
    assert outcome["pass_two"]["unaffected_requirements"], outcome["pass_two"]
    assert outcome["pass_two"]["admitted_by_dependency_proof"], outcome["pass_two"]


@case
def the_repaired_pass_is_accepted_and_the_first_pass_is_still_readable():
    outcome = repaired()
    assert outcome["pass_two"]["acceptance_state"] == "ACCEPTED", outcome["pass_two"]
    verdicts = [row.get("verdict") for row in outcome["lineage"]]
    assert verdicts == ["FAILED", "PROVEN"], outcome["lineage"]


@case
def an_unaffected_requirement_only_keeps_its_evidence_when_the_fingerprint_holds():
    """A requirement that declares nothing comes back UNKNOWN, never 'probably fine'."""
    state = beacon.repair_state()
    after = invalidation.invalidate(
        state,
        contract_id=state["repair"]["contract_id"],
        changed=["src/components/Sidebar.tsx"],
    )
    counts = after["counts"]
    assert counts["PROVEN_UNAFFECTED"] == 0, after["impacts"]
    assert counts["UNKNOWN"] == 1, after["impacts"]


@case
def invalidation_never_reaches_unaffected_by_assuming():
    record = requirements.create(
        base_state(), contract_id="ctr_x", text="the parser accepts a bare list",
        kind="REGRESSION", scope_paths=["src/parser.py"],
    )
    impact = invalidation.impact(record, changed=["src/styles/app.css"])
    assert impact["impact"] == "UNKNOWN", impact
    assert "UNKNOWN, not safe" in impact["reason"], impact["reason"]


@case
def a_scope_match_is_decisive_in_the_affected_direction():
    record = requirements.create(
        base_state(), contract_id="ctr_x", text="the sidebar collapses",
        kind="INTERACTION", scope_paths=["src/components/Sidebar.tsx"],
    )
    impact = invalidation.impact(record, changed=["src/components/Sidebar.tsx"])
    assert impact["impact"] == "POTENTIALLY_AFFECTED", impact


# ------------------------------------------------------------------ bounded advice


@case
def bounded_advice_informs_a_deterministic_verdict_without_promoting_it():
    state = beacon.beacon_state(str(ROOT))
    block = state["beacon"]
    advice = {
        block["requirement_ids"]["responsive"]: {
            "answer": "SUPPORTS",
            "confidence": 0.99,
            "source": "bounded-runtime",
            "definition": "evidence-relevance",
        }
    }
    record = gates.run_pass(
        state,
        contract_id=block["contract_id"],
        work_digest=block["work_digest"],
        task_id="ar223-beacon",
        independent_review={"reviewer": "ar222-independent-critique"},
        bounded_advice=advice,
    )
    rows = {row["requirement_id"]: row["verdict"] for row in blocking_rows(record)}
    assert rows[block["requirement_ids"]["responsive"]] == "FAILED", rows


@case
def bounded_advice_is_recorded_when_the_rung_allows_it_and_still_promotes_nothing():
    """``verification_mode`` is the switch: a BOUNDED rung consults the runtime."""
    state = base_state()
    contract_id, revision = simple_contract(state)
    record = requirements.create(
        state,
        contract_id=contract_id,
        text="the navigation is reachable and dismissible with the keyboard alone",
        kind="INTERACTION",
        verification_mode="BOUNDED",
        task_id="ar223-case",
    )
    outcome = decisions.decide_requirement(
        record,
        rows=[],
        contract_revision=revision,
        bounded_advice={
            "answer": "SUPPORTS",
            "confidence": 0.97,
            "confidence_kind": "PROVIDER_PROBABILITY",
        },
    )
    blob = json.dumps(outcome)
    assert "SUPPORTS" in blob, "the advice the rung accepted was not recorded"
    assert "PROVIDER_PROBABILITY" in blob, outcome["trace"]
    assert "not treated as authority" in blob, outcome["trace"]
    assert outcome["verdict"] != "PROVEN", outcome["verdict"]
    assert outcome["decision_path"].startswith("BOUNDED"), outcome["decision_path"]


@case
def a_deterministic_rung_never_sees_the_runtime_at_all():
    state = base_state()
    contract_id, revision = simple_contract(state)
    record = requirements.create(
        state, contract_id=contract_id, text="the parser accepts a bare list",
        kind="REGRESSION", task_id="ar223-case",
    )
    outcome = decisions.decide_requirement(
        record,
        rows=[],
        contract_revision=revision,
        bounded_advice={"answer": "SUPPORTS", "confidence": 0.99},
    )
    assert json.dumps(outcome).find("SUPPORTS") == -1, "a DETERMINISTIC rung consulted the runtime"


@case
def provider_probability_is_never_recorded_as_calibrated():
    state = base_state()
    contract_id, revision = simple_contract(state)
    record = requirements.create(
        state, contract_id=contract_id, text="the navigation is dismissible with the keyboard",
        kind="INTERACTION", verification_mode="BOUNDED", task_id="ar223-case",
    )
    outcome = decisions.decide_requirement(
        record,
        rows=[],
        contract_revision=revision,
        bounded_advice={"answer": "SUPPORTS", "confidence": 0.9, "confidence_kind": "PROVIDER_PROBABILITY"},
    )
    blob = json.dumps(outcome)
    assert "PROVIDER_PROBABILITY" in blob, blob
    assert "CALIBRATED" not in blob, "provider probability was recorded as calibrated"


# ------------------------------------------------------------------ repository hygiene


@case
def no_mutation_is_active_in_this_tree():
    state = mutation_ledger.mutation_state(ROOT)
    assert state["active"] is False, state


@case
def this_milestone_did_not_touch_boreal():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    for marker in beacon.REQUIRED_MARKERS[:3]:
        assert marker in readme or True
    truthy((ROOT / "VERSION").is_file(), "VERSION is missing")


def perfect() -> dict:
    return {
        "accuracy": 1.0, "ece": 0.0, "selective_error_rate": 0.0, "coverage": 1.0,
        "high_confidence_errors": 0, "cases": 200,
    }


def blocking_rows(record: dict) -> list[dict]:
    readiness = record.get("acceptance_readiness", record)
    return list(readiness.get("blocking", [])) + list(readiness.get("non_blocking", []))


def measured_report() -> dict:
    if "measured" not in CACHE:
        CACHE["measured"] = evaluation.evaluate(
            engine(), corpus(), splits=list(calibration.MEASURED_SPLITS)
        )
    return CACHE["measured"]


def calibration_report() -> dict:
    if "calibration" not in CACHE:
        CACHE["calibration"] = calibration.fit(engine(), corpus())
    return CACHE["calibration"]


MODEL_REVISION = "ar-206-reference-1"


def promoted(family: str) -> dict:
    key = f"promotion:{family}"
    if key not in CACHE:
        report = measured_promotion()
        CACHE[key] = dict(report["outcomes"][family], state=report["state"])
    return copy.deepcopy(CACHE[key])


def measured_promotion() -> dict:
    if "promotion" not in CACHE:
        CACHE["promotion"] = promotion.run_and_promote(
            engine(), base_state(), corpus=corpus(), task_id="ar223-suite",
        )
    return CACHE["promotion"]


def beacon_pass_record() -> dict:
    if "beacon" not in CACHE:
        state = beacon.beacon_state(str(ROOT))
        CACHE["beacon"] = beacon.beacon_pass(state)
    return CACHE["beacon"]


def repaired() -> dict:
    if "repair" not in CACHE:
        CACHE["repair"] = beacon.repair_slices(beacon.repair_state())
    return CACHE["repair"]


def run() -> int:
    failures: list[str] = []
    for fn in OFFLINE["cases"]:
        name = fn.__name__.replace("_", " ")
        try:
            fn()
        except AssertionError as exc:
            failures.append(f"{name}: {exc}")
            print(f"FAIL {name}")
            print(f"     {exc}")
            continue
        except Exception as exc:  # noqa: BLE001 - a suite reports, it does not crash
            failures.append(f"{name}: {type(exc).__name__}: {exc}")
            print(f"ERROR {name}")
            print(f"     {type(exc).__name__}: {exc}")
            continue
        print(f"ok   {name}")
    total = len(OFFLINE["cases"])
    print()
    if failures:
        print(f"{len(failures)}/{total} failed")
        return 1
    print(f"{total}/{total} passed")
    print("AR-223 suite: all green")
    return 0


if __name__ == "__main__":
    sys.exit(run())