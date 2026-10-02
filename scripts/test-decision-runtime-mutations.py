#!/usr/bin/env python3
"""AR-206 mutation tests for the Decision Runtime's safety properties.

A functional suite proves the protections hold. It cannot prove they are *load-bearing*:
every check would still pass with a guard quietly inverted, because a test asserts that
something is refused and an inverted guard that refuses for a different reason looks
identical from the outside.

So each mutation here removes or weakens exactly one protection in a *copy* of the
engine package and then runs the attack that protection exists to refuse. A mutation is
caught when the attack is refused by the original and allowed by the mutant -- exactly
what a failing protection test would observe. A mutant that cannot even import is not a
caught mutation; it is a compile error, and counting it would inflate the result.

The repository sources are never written. The engine package is copied to a temporary
directory, mutated there, imported under a unique module name, and discarded. The
script verifies before and after that every engine source file is byte-identical
(sha256), so "restore byte-exact" holds by construction rather than by discipline.

These twelve target the properties the feature exists to guarantee: that an abstention
cannot become an answer, that only a matched PROVEN profile may label a probability
calibrated, that a moving alias cannot satisfy a profile or a cache key, that shadow
mode is structurally unable to influence a decision, that a runtime can never grant
authority, that a closed answer space is actually closed, that metrics are not compared
across different experiments, that a promotion slice cannot outgrow its scope, and that
a freshly computed digest of bytes just found is not verification.

Run: python scripts/test-decision-runtime-mutations.py
"""

from __future__ import annotations

import hashlib
import os
import importlib.util
import inspect
import json
import shutil
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ENGINE = ROOT / "src" / "ariadne_engine"
RUNTIME = "decisions/runtime"


def source_hashes() -> dict[str, str]:
    return {
        path.relative_to(ENGINE).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(ENGINE.rglob("*.py"))
    }


def load_mutant(package_root: Path, name: str):
    spec = importlib.util.spec_from_file_location(
        name, package_root / "__init__.py",
        submodule_search_locations=[str(package_root)],
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


# ------------------------------------------------------------------- fixtures


def state(module) -> dict:
    return {
        "schema_version": 1,
        "run_id": "ar206-mutation",
        "project": "C:/tmp/mutation-project",
        "packets": [{"id": "t-S1", "stage": "S1", "path": "C:/tmp/mutation-run/t-S1"}],
        "approvals": [],
    }


def runtime_of(module):
    return module.decisions.runtime


def seeded(module, **overrides):
    """A healthy in-process runtime carrying the real seed weight book."""
    RUNTIME = runtime_of(module)
    impl = RUNTIME.reference.ReferenceBoundedEngine(RUNTIME.seeds.build_seed_book())
    described = dict(impl.status())
    described["runtime_kind"] = "local_bounded"
    described.update(overrides)
    return RUNTIME.session.DecisionRuntime.in_process(impl, description=described)


def failure_question(module) -> dict:
    return {
        "question_id": "failure-class",
        "instructions": "classify the failure",
        "primitive": "ChoiceDecision",
        "options": list(module.contracts.DECISION_CLASSIFIABLE_FAILURE_CLASSES),
        "projection_contract": "failure-classification",
        "definition_version": "1",
        "consequence": "LOW",
    }


def projection(module, entries: dict) -> dict:
    return {"entries": entries, "digest": "d" * 64}


IMPL = {"failure": "Traceback (most recent call last): TypeError: undefined name 'render'"}
LOW_SCOPE = {"risk": "LOW", "reversible": True, "verification_available": True, "languages": ["en"]}


def proven_slice(module, local: dict) -> str:
    """Open a slice and drive it all the way to ACTIVE, legitimately."""
    RUNTIME = runtime_of(module)
    question = failure_question(module)
    scope = dict(LOW_SCOPE)
    opened = RUNTIME.promotion.open_slice(
        local, decision_definition="failure-classification", question_version="1",
        model_revision=RUNTIME.reference.ENGINE_REVISION, scope=scope,
    )
    slice_id = opened["slice_id"]
    profile = RUNTIME.profiles.build_profile(
        decision_definition="failure-classification", questions=[question],
        runtime="local_bounded", implementation=RUNTIME.reference.ENGINE_NAME,
        model=RUNTIME.reference.ENGINE_NAME, revision=RUNTIME.reference.ENGINE_REVISION,
        dataset_digest="e" * 64, dataset_size=RUNTIME.profiles.MIN_PROFILE_DATASET,
        accuracy=0.9, coverage=0.95, ece=0.05, brier=0.08,
    )
    RUNTIME.profiles.record_profile(local, profile)
    for target in ("SHADOW", "EVALUATED", "ELIGIBLE"):
        RUNTIME.promotion.transition(local, slice_id, target, reason="mutation fixture",
                                     evaluation_id="dev-1")
    RUNTIME.promotion.transition(local, slice_id, "ACTIVE", reason="mutation fixture",
                                 evaluation_id="dev-1",
                                 calibration_profile_id=profile.profile_id)
    return slice_id


# --------------------------------------------------------------------- probes
# A probe returns True when the protection holds, i.e. the attack was refused.


def probe_abstention_is_not_an_answer(module) -> bool:
    """A question with no local model must abstain, never emit a label."""
    RUNTIME = runtime_of(module)
    impl = RUNTIME.reference.ReferenceBoundedEngine(RUNTIME.seeds.build_seed_book())
    question = {
        "question_id": "never-fitted", "instructions": "?",
        "primitive": "ChoiceDecision", "options": ["ALPHA", "BETA"],
        "projection_contract": "unknown-contract", "definition_version": "1",
        "consequence": "LOW",
    }
    answered = impl.decide({
        "state_projections": [projection(module, IMPL)], "questions": [question],
    })
    slot = answered["answers"]["0:never-fitted"]
    return (slot["valid"] is False and slot["reason"] == "NO_LOCAL_MODEL"
            and slot["answer"] is None and slot["abstained"] is True)


def probe_unsupported_primitive_is_refused(module) -> bool:
    """MultiSelectDecision must be refused, not silently coerced."""
    RUNTIME = runtime_of(module)
    if not RUNTIME.reference.unsupported_primitive("MultiSelectDecision"):
        return False
    session = seeded(module)
    try:
        provider = RUNTIME.provider.LocalBoundedProvider(session)
        result = provider.answer({
            "projection": projection(module, IMPL),
            "questions": [{"question_id": "multi", "instructions": "pick two",
                           "primitive": "MultiSelectDecision", "options": ["a", "b"],
                           "max_selections": 2, "consequence": "LOW"}],
        })
    except Exception:
        return True
    finally:
        session.shutdown()
    return result["answers"]["multi"]["abstained"] is True


def probe_draft_profile_cannot_calibrate(module) -> bool:
    """Only a PROVEN profile may label a probability calibrated."""
    RUNTIME = runtime_of(module)
    local = state(module)
    question = failure_question(module)
    identity = {"runtime": "local_bounded", "implementation": RUNTIME.reference.ENGINE_NAME,
                "model_revision": RUNTIME.reference.ENGINE_REVISION}
    draft = RUNTIME.profiles.build_profile(
        decision_definition="failure-classification", questions=[question],
        runtime=identity["runtime"], implementation=identity["implementation"],
        model=RUNTIME.reference.ENGINE_NAME, revision=identity["model_revision"],
        dataset_digest="d" * 64, dataset_size=10,
        accuracy=0.99, coverage=0.99, ece=0.0, brier=0.0,
        thresholds_by_risk={"LOW": 0.1},
    )
    if draft.status != "DRAFT":
        return False
    RUNTIME.profiles.record_profile(local, draft)
    verdict = RUNTIME.profiles.profile_for(
        local, decision_definition="failure-classification", question=question, risk="LOW",
        **identity,
    )
    return (verdict["accepted"] is False
            and verdict["confidence_kind"] == "PROVIDER_PROBABILITY")


def probe_alias_cannot_satisfy_a_profile(module) -> bool:
    """A profile is bound to a concrete revision; a moving alias must not match it."""
    RUNTIME = runtime_of(module)
    local = state(module)
    question = failure_question(module)
    RUNTIME.profiles.record_profile(local, RUNTIME.profiles.build_profile(
        decision_definition="failure-classification", questions=[question],
        runtime="local_bounded", implementation=RUNTIME.reference.ENGINE_NAME,
        model=RUNTIME.reference.ENGINE_NAME, revision=RUNTIME.reference.ENGINE_REVISION,
        dataset_digest="e" * 64, dataset_size=RUNTIME.profiles.MIN_PROFILE_DATASET,
        accuracy=0.9, coverage=0.95, ece=0.05, brier=0.08,
        thresholds_by_risk={"LOW": 0.5},
    ))
    verdict = RUNTIME.profiles.profile_for(
        local, decision_definition="failure-classification", question=question, risk="LOW",
        runtime="local_bounded", implementation=RUNTIME.reference.ENGINE_NAME,
        model_revision="latest",
    )
    return verdict["accepted"] is False


def probe_runtime_cannot_self_grant_calibration(module) -> bool:
    """An engine that declares it calibrates its own probabilities must be refused."""
    RUNTIME = runtime_of(module)

    class SelfCertifying(RUNTIME.reference.ReferenceBoundedEngine):
        def status(self) -> dict:
            described = dict(super().status())
            described["calibration_self_granted"] = True
            return described

    impl = SelfCertifying(RUNTIME.seeds.build_seed_book())
    described = dict(impl.status())
    described["runtime_kind"] = "local_bounded"
    lying = RUNTIME.session.DecisionRuntime.in_process(impl, description=described)
    try:
        return "the decision runtime claims to grant its own calibration" in lying.problems()
    finally:
        lying.shutdown()


def probe_closed_answer_space(module) -> bool:
    """An answer outside the declared option set must be refused, not accepted."""
    RUNTIME = runtime_of(module)
    session = seeded(module)

    class Rogue:
        def available(self):
            return True, "rogue"

        def status(self):
            return {"runtime_version": "1", "implementation": "rogue",
                    "implementation_revision": "r", "model": "rogue", "model_revision": "r1",
                    "device": "cpu", "runtime_kind": "local_bounded",
                    "primitives": ["ChoiceDecision"],
                    "confidence_kinds": ["PROVIDER_PROBABILITY"]}

        def decide(self, *_args, **_kwargs):
            return {"provider": "rogue", "model": "rogue", "model_version": "r1",
                    "runtime_version": "1", "device": "cpu",
                    "answers": {"0:failure-class": {
                        "question_id": "failure-class", "answer": "APPROVED_EVERYTHING",
                        "valid": True, "confidence": 0.99,
                        "confidence_kind": "PROVIDER_PROBABILITY",
                        "distribution": {"APPROVED_EVERYTHING": 0.99}}}}

    try:
        rogue = RUNTIME.session.DecisionRuntime.in_process(Rogue(), description=Rogue().status())
        result = RUNTIME.provider.LocalBoundedProvider(rogue).answer({
            "projection": projection(module, IMPL),
            "questions": [failure_question(module)],
        })
    finally:
        session.shutdown()
    slot = result["answers"]["failure-class"]
    return bool(slot.get("problems")) and result["failed_questions"] == ["failure-class"]


def probe_shadow_isolation_is_load_bearing(module) -> bool:
    """A shadow record claiming an execution effect must be detected."""
    RUNTIME = runtime_of(module)
    local = state(module)
    session = seeded(module)
    try:
        RUNTIME.observe.observe(
            local, session, question=failure_question(module),
            projection=projection(module, IMPL), authoritative_answer="VALIDATION_FAILURE",
        )
    finally:
        session.shutdown()
    if not local["decision_shadow"]:
        return False
    if RUNTIME.shadow.shadow_problems(local):
        return False
    local["decision_shadow"][0]["execution_effect"] = "authoritative"
    return bool(RUNTIME.shadow.shadow_problems(local))


def probe_shadow_ground_truth_must_be_sourced(module) -> bool:
    """An unsourced "this was wrong" is not evidence."""
    RUNTIME = runtime_of(module)
    local = state(module)
    session = seeded(module)
    try:
        observed = RUNTIME.observe.observe(
            local, session, question=failure_question(module),
            projection=projection(module, IMPL), authoritative_answer="VALIDATION_FAILURE",
        )
    finally:
        session.shutdown()
    if not observed.get("shadow_id"):
        return False
    try:
        RUNTIME.shadow.record_ground_truth(
            local, observed["shadow_id"], ground_truth="IMPLEMENTATION_FAILURE", source="")
    except ValueError:
        return True
    return False


def probe_shadow_ground_truth_is_persisted(module) -> bool:
    """A recorded outcome must reach the state, not just the return value."""
    RUNTIME = runtime_of(module)
    local = state(module)
    session = seeded(module)
    try:
        observed = RUNTIME.observe.observe(
            local, session, question=failure_question(module),
            projection=projection(module, IMPL), authoritative_answer="VALIDATION_FAILURE",
        )
        RUNTIME.shadow.record_ground_truth(
            local, observed["shadow_id"], ground_truth="IMPLEMENTATION_FAILURE",
            source="verification run 1",
        )
    finally:
        session.shutdown()
    stored = local["decision_shadow"][0]
    if stored.get("ground_truth") != "IMPLEMENTATION_FAILURE":
        return False
    if stored.get("agreement") != "MATCH":
        return False
    return len(RUNTIME.export.collect(local)["rows"]) == 1


def probe_no_authority_from_the_runtime(module) -> bool:
    """Nothing the runtime produces may carry an authorisation effect."""
    RUNTIME = runtime_of(module)
    local = state(module)
    session = seeded(module)
    try:
        provider = RUNTIME.provider.LocalBoundedProvider(session)
        answered = provider.answer({
            "projection": projection(module, IMPL),
            "questions": [failure_question(module)],
        })
        if answered["authorization_effect"] != "none":
            return False
        if provider.describe()["authorization_effect"] != "none":
            return False
        RUNTIME.observe.observe(
            local, session, question=failure_question(module),
            projection=projection(module, IMPL), authoritative_answer="VALIDATION_FAILURE",
        )
    finally:
        session.shutdown()
    if local["decision_shadow"][0]["authorization_effect"] != "none":
        return False
    # And a shadow prediction is never stored as a verification.
    return not any("verifications" in key for key in local)


def probe_promotion_cannot_skip_the_lifecycle(module) -> bool:
    """UNTESTED may not become ACTIVE."""
    RUNTIME = runtime_of(module)
    local = state(module)
    opened = RUNTIME.promotion.open_slice(
        local, decision_definition="failure-classification", question_version="1",
        model_revision=RUNTIME.reference.ENGINE_REVISION, scope=dict(LOW_SCOPE),
    )
    try:
        RUNTIME.promotion.transition(local, opened["slice_id"], "ACTIVE",
                                     reason="skipping the evidence", evaluation_id="dev-1")
    except (ValueError, module.contracts.ContractError):
        return True
    return False


def probe_slice_cannot_outgrow_its_scope(module) -> bool:
    """A slice promoted for LOW/en/reversible must not cover a wider use.

    Every request states the whole scope, so each widening is refused for exactly one
    reason. Without that, a mutant that removes one check would still be caught by
    another, and the mutation would look caught for the wrong reason.
    """
    RUNTIME = runtime_of(module)
    local = state(module)
    proven_slice(module, local)
    session = seeded(module)
    in_scope = {"reversible": True, "verification_available": True, "languages": ["en"]}
    try:
        low = RUNTIME.selection.select_bounded_provider(
            local, runtime=session, definition="failure-classification", question_version="1",
            question=failure_question(module), consequence="LOW", **in_scope,
        )
        high = RUNTIME.selection.select_bounded_provider(
            local, runtime=session, definition="failure-classification", question_version="1",
            question=failure_question(module), consequence="HIGH", **in_scope,
        )
        german = RUNTIME.selection.select_bounded_provider(
            local, runtime=session, definition="failure-classification", question_version="1",
            question=failure_question(module), consequence="LOW", reversible=True,
            verification_available=True, languages=["de"],
        )
        irreversible = RUNTIME.selection.select_bounded_provider(
            local, runtime=session, definition="failure-classification", question_version="1",
            question=failure_question(module), consequence="LOW", reversible=False,
            verification_available=True, languages=["en"],
        )
        unverified = RUNTIME.selection.select_bounded_provider(
            local, runtime=session, definition="failure-classification", question_version="1",
            question=failure_question(module), consequence="LOW", reversible=True,
            verification_available=False, languages=["en"],
        )
    finally:
        session.shutdown()
    if low["mode"] != RUNTIME.selection.MODE_AUTHORITATIVE:
        return False
    return all(
        selection["mode"] == RUNTIME.selection.MODE_SHADOW and selection["problems"]
        for selection in (high, german, irreversible, unverified)
    )


def probe_metrics_need_comparable_identity(module) -> bool:
    """A metric comparison across different experiments must be refused."""
    RUNTIME = runtime_of(module)
    question = failure_question(module)
    base = {
        "decision_definition": "failure-classification", "questions": [question],
        "runtime_version": RUNTIME.reference.ENGINE_VERSION,
        "implementation_revision": RUNTIME.reference.ENGINE_REVISION,
        "model_revision": RUNTIME.reference.ENGINE_REVISION,
        "calibration_profile_id": "dcp-mutation", "threshold_policy_version": "policy-1",
    }
    records = [{"case_id": "c1", "expected": "IMPLEMENTATION_FAILURE",
                "projection": {"entries": dict(IMPL)}}]
    rows = [{"case_id": "c1", "answer": "IMPLEMENTATION_FAILURE", "confidence": 0.9,
             "distribution": {"IMPLEMENTATION_FAILURE": 0.9}, "latency_ms": 1.0}]
    original = RUNTIME.evaluation.evaluate(records, rows=rows, **base)
    drift = RUNTIME.evaluation.evaluate(records, rows=rows,
                                        **{**base, "model_revision": "deadbeef"})
    if RUNTIME.evaluation.compare(original, drift)["comparable"]:
        return False
    same = RUNTIME.evaluation.evaluate(records, rows=rows, **base)
    if not RUNTIME.evaluation.compare(original, same)["comparable"]:
        return False
    try:
        RUNTIME.evaluation.assert_regression(original, drift)
    except AssertionError:
        return True
    return False


def probe_fresh_digest_is_not_verification(module) -> bool:
    """Hashing bytes you just downloaded is not verifying them."""
    RUNTIME = runtime_of(module)
    with tempfile.TemporaryDirectory(prefix="ar206-integrity-") as workspace:
        root = Path(workspace)
        RUNTIME.seeds.install_seeds(root)
        if RUNTIME.integrity.require_reviewed_digests(None)["status"] != "UNKNOWN":
            return False
        session = RUNTIME.session.DecisionRuntime.discover(root=root)
        try:
            if session.integrity()["status"] != "UNKNOWN":
                return False
        finally:
            session.shutdown()
        (root / "weights.json").write_text("{}", encoding="utf-8")
        return bool(RUNTIME.integrity.problems(root))
    return True


def probe_production_path_abstains(module) -> bool:
    """The production path must abstain below an evidence-backed threshold.

    Deliberately routed through ``decisions.batch.evaluate`` rather than
    ``session.decide``. That distinction is the whole closure pass: calling the runtime
    directly proves the machinery works, while calling the real caller proves it is
    reachable. Every mutation below targets the wiring, and a probe that called the
    engine directly would report all of them as caught while the product still could not
    abstain.
    """
    RUNTIME = runtime_of(module)
    batch = module.decisions.batch
    C = module.decisions.contracts
    question = C.DecisionQuestion(
        question_id="failure-class", instructions="bounded failure class",
        primitive="ChoiceDecision",
        options=tuple(module.contracts.DECISION_CLASSIFIABLE_FAILURE_CLASSES),
        projection_contract="failure-classification", definition_version="1",
        consequence="LOW")
    entries = {"failure": "Traceback: TypeError: x"}
    projection = {"entries": entries, "digest": "a" * 64, "verification_level": "OBSERVED"}
    session = seeded(module)
    try:
        provider = RUNTIME.provider.LocalBoundedProvider(session)
        state = {
            "schema_version": 1, "run_id": "mutation", "project": "C:/tmp/m",
            "packets": [], "approvals": [], "decisions": [], "decision_batches": [],
        }
        RUNTIME.profiles.record_profile(state, RUNTIME.profiles.build_profile(
            decision_definition="failure-classification", questions=[question.as_record()],
            runtime=provider.provider, implementation=provider.model, model=provider.model,
            revision=provider.model_version, dataset_digest="f" * 64,
            dataset_size=RUNTIME.profiles.MIN_PROFILE_DATASET,
            accuracy=0.9, coverage=0.95, ece=0.05, brier=0.08,
            thresholds_by_risk={"LOW": 0.999}))
        batch.evaluate(state, questions=[question], projection=projection,
                       provider=provider, task_id="m")
    finally:
        session.shutdown()
    record = state["decisions"][-1]
    return (record["status"] == "refused"
            and record.get("abstention_reason") == "BELOW_MIN_CONFIDENCE"
            and record["answer"] == "")


def probe_retired_profile_ignored(module) -> bool:
    """A RETIRED profile must supply no threshold through the production path."""
    return not _threshold_supplied(module, status="RETIRED")


def probe_revision_mismatch_ignored(module) -> bool:
    """A profile bound to another model revision must supply no threshold."""
    return not _threshold_supplied(module, revision="deadbeef")


def probe_question_schema_mismatch_ignored(module) -> bool:
    """A profile measured on a different question version must supply no threshold.

    The explicit ``question_version`` check and the ``question_schema_digest`` check cover
    this independently, so the mutation targets the schema digest: removing only the
    version check leaves the other guard standing, which is defence in depth rather than
    a load-bearing property, and a mutation that survives proves nothing.
    """
    return not _threshold_supplied(module, profile_version="1", query_version="2")


def probe_risk_class_mismatch_ignored(module) -> bool:
    """A LOW-risk threshold must not apply to a HIGH-risk decision.

    ``build_profile`` does not require a threshold for every risk class a question could
    carry, so a PROVEN profile may legitimately declare only LOW. The lookup is where the
    risk class is enforced, and this is the guard doing the work.
    """
    return not _threshold_supplied(module, consequence="HIGH", declared_risks=("LOW",))


def probe_no_universal_fallback_threshold(module) -> bool:
    """With no profile at all, nothing may be invented."""
    RUNTIME = runtime_of(module)
    batch = module.decisions.batch
    C = module.decisions.contracts
    question = C.DecisionQuestion(
        question_id="failure-class", instructions="bounded failure class",
        primitive="ChoiceDecision",
        options=tuple(module.contracts.DECISION_CLASSIFIABLE_FAILURE_CLASSES),
        projection_contract="failure-classification", definition_version="1",
        consequence="LOW")
    session = seeded(module)
    try:
        provider = RUNTIME.provider.LocalBoundedProvider(session)
        resolved = batch.effective_policy(
            {"schema_version": 1, "run_id": "m", "project": "p", "packets": [], "approvals": []},
            [question], runtime=provider.provider, implementation=provider.model,
            model_revision=provider.model_version)
    finally:
        session.shutdown()
    return resolved["min_confidence_by_question"] == {}


def probe_evidence_preserved(module) -> bool:
    """A threshold abstention must keep the evidence it was judged on.

    Section 11 of the closure requires the original answer, probability and threshold to
    survive the refusal. An abstention that forgets them is indistinguishable from never
    having looked, and the escalation that follows cannot be judged on the evidence.
    """
    RUNTIME = runtime_of(module)
    batch = module.decisions.batch
    C = module.decisions.contracts
    question = C.DecisionQuestion(
        question_id="failure-class", instructions="bounded failure class",
        primitive="ChoiceDecision",
        options=tuple(module.contracts.DECISION_CLASSIFIABLE_FAILURE_CLASSES),
        projection_contract="failure-classification", definition_version="1",
        consequence="LOW")
    session = seeded(module)
    try:
        provider = RUNTIME.provider.LocalBoundedProvider(session)
        state = {"schema_version": 1, "run_id": "m", "project": "p", "packets": [],
                 "approvals": [], "decisions": [], "decision_batches": []}
        RUNTIME.profiles.record_profile(state, RUNTIME.profiles.build_profile(
            decision_definition="failure-classification", questions=[question.as_record()],
            runtime=provider.provider, implementation=provider.model, model=provider.model,
            revision=provider.model_version, dataset_digest="f" * 64,
            dataset_size=RUNTIME.profiles.MIN_PROFILE_DATASET,
            accuracy=0.9, coverage=0.95, ece=0.05, brier=0.08,
            thresholds_by_risk={"LOW": 0.999}))
        batch.evaluate(
            state, questions=[question],
            projection={"entries": {"failure": "Traceback: TypeError: x"},
                        "digest": "a" * 64, "verification_level": "OBSERVED"},
            provider=provider, task_id="m")
    finally:
        session.shutdown()
    record = state["decisions"][-1]
    return (record["status"] == "refused"
            and record.get("candidate_answer") == "IMPLEMENTATION_FAILURE"
            and float(record.get("candidate_confidence") or 0.0) > 0.0
            and record["answer"] == ""
            and record.get("threshold_applied") == 0.999)


def probe_never_reports_calibrated(module) -> bool:
    """No answer may reach the record claiming to be a calibrated probability.

    The threat is a sidecar that lies about itself, not the reference engine, which
    never claims calibration. So the probe uses a rogue runtime whose declared
    ``confidence_kinds`` is the honest list and whose answer nonetheless says
    ``CALIBRATED_PROBABILITY`` - the engine declaring it does not calibrate its own
    numbers while the answer says otherwise.
    """
    RUNTIME = runtime_of(module)
    C = module.decisions.contracts

    class SelfCertifying:
        def available(self):
            return True, "self-certifying"

        def status(self):
            return {"runtime_version": "1", "implementation": "x",
                    "implementation_revision": "r", "model": "x", "model_revision": "r1",
                    "device": "cpu", "runtime_kind": "local_bounded",
                    "primitives": ["ChoiceDecision"],
                    "confidence_kinds": ["PROVIDER_PROBABILITY", "NONE"],
                    "calibration_self_granted": False}

        def decide(self, *_args, **_kwargs):
            return {"provider": "x", "model": "x", "model_version": "r1",
                    "runtime_version": "1", "device": "cpu",
                    "answers": {"0:failure-class": {
                        "question_id": "failure-class", "answer": "IMPLEMENTATION_FAILURE",
                        "valid": True, "confidence": 0.9,
                        "confidence_kind": "CALIBRATED_PROBABILITY",
                        "distribution": {"IMPLEMENTATION_FAILURE": 0.9}}}}

    session = RUNTIME.session.DecisionRuntime.in_process(
        SelfCertifying(), description=SelfCertifying().status())
    try:
        provider = RUNTIME.provider.LocalBoundedProvider(session)
        result = provider.answer({
            "projection": {"entries": {"failure": "Traceback: TypeError: x"}, "digest": "a" * 64},
            "questions": [C.DecisionQuestion(
                question_id="failure-class", instructions="bounded failure class",
                primitive="ChoiceDecision",
                options=tuple(module.contracts.DECISION_CLASSIFIABLE_FAILURE_CLASSES),
                projection_contract="failure-classification", definition_version="1",
                consequence="LOW").as_record()],
        })
    finally:
        session.shutdown()
    slot = result["answers"]["failure-class"]
    return (slot.get("confidence_kind") != "CALIBRATED_PROBABILITY"
            and result["failed_questions"] == ["failure-class"])


def probe_confidence_cannot_authorize(module) -> bool:
    """Confidence must not buy authority, on the production path."""
    RUNTIME = runtime_of(module)
    batch = module.decisions.batch
    C = module.decisions.contracts
    question = C.DecisionQuestion(
        question_id="failure-class", instructions="bounded failure class",
        primitive="ChoiceDecision",
        options=tuple(module.contracts.DECISION_CLASSIFIABLE_FAILURE_CLASSES),
        projection_contract="failure-classification", definition_version="1",
        consequence="PROTECTED")
    session = seeded(module)
    try:
        provider = RUNTIME.provider.LocalBoundedProvider(session)
        state = {"schema_version": 1, "run_id": "m", "project": "p", "packets": [],
                 "approvals": [], "decisions": [], "decision_batches": []}
        batch.evaluate(
            state, questions=[question],
            projection={"entries": {"failure": "Traceback: TypeError: undefined name x"},
                        "digest": "b" * 64, "verification_level": "UNVERIFIED"},
            provider=provider, task_id="m")
    finally:
        session.shutdown()
    record = state["decisions"][-1]
    return (record["authorization_effect"] == "none"
            and record["acted_on"] is False
            and record["policy_verdict"]["accepted"] is False)


def probe_batch_threshold_does_not_leak(module) -> bool:
    """One question's threshold must not be applied to its siblings."""
    RUNTIME = runtime_of(module)
    batch = module.decisions.batch
    C = module.decisions.contracts
    first = C.DecisionQuestion(
        question_id="failure-class", instructions="bounded failure class",
        primitive="ChoiceDecision",
        options=tuple(module.contracts.DECISION_CLASSIFIABLE_FAILURE_CLASSES),
        projection_contract="failure-classification", definition_version="1",
        consequence="LOW")
    second = C.DecisionQuestion(
        question_id="review-escalation", instructions="bounded review escalation",
        primitive="ChoiceDecision", options=tuple(module.contracts.REVIEW_ESCALATIONS),
        projection_contract="review-escalation", definition_version="1",
        consequence="LOW")
    session = seeded(module)
    try:
        provider = RUNTIME.provider.LocalBoundedProvider(session)
        state = {"schema_version": 1, "run_id": "m", "project": "p", "packets": [],
                 "approvals": [], "decisions": [], "decision_batches": []}
        RUNTIME.profiles.record_profile(state, RUNTIME.profiles.build_profile(
            decision_definition="failure-classification", questions=[first.as_record()],
            runtime=provider.provider, implementation=provider.model, model=provider.model,
            revision=provider.model_version, dataset_digest="f" * 64,
            dataset_size=RUNTIME.profiles.MIN_PROFILE_DATASET,
            accuracy=0.9, coverage=0.95, ece=0.05, brier=0.08,
            thresholds_by_risk={"LOW": 0.999}))
        batch.evaluate(
            state, questions=[first, second],
            projection={"entries": {"failure": "Traceback: TypeError: x", "stakes": "high",
                                    "affected_scope": "release", "protected": True},
                        "digest": "c" * 64, "verification_level": "OBSERVED"},
            provider=provider, task_id="m")
    finally:
        session.shutdown()
    statuses = {row["question_id"]: row["status"] for row in state["decisions"]}
    return (statuses.get("failure-class") == "refused"
            and statuses.get("review-escalation") == "answered")


def _threshold_supplied(module, *, status: str = "", revision: str = "",
                        profile_version: str = "1", query_version: str = "1",
                        consequence: str = "LOW", declared_risks: tuple = ()) -> bool:
    """Whether a threshold is supplied through the production path under these conditions.

    ``profile_version`` and ``query_version`` are separate on purpose: a mismatch is only
    meaningful if the profile was measured on one version and the decision asks another.

    An evaluation that raises counts as "no threshold applied". A mutant that borrows
    another class's threshold and then cannot look it up has not let the wrong threshold
    through either, and calling that a pass would be scoring the mutant on a crash rather
    than on the property under test.
    """
    RUNTIME = runtime_of(module)
    batch = module.decisions.batch
    C = module.decisions.contracts

    def asked(version: str) -> C.DecisionQuestion:
        return C.DecisionQuestion(
            question_id="failure-class", instructions="bounded failure class",
            primitive="ChoiceDecision",
            options=tuple(module.contracts.DECISION_CLASSIFIABLE_FAILURE_CLASSES),
            projection_contract="failure-classification", definition_version=version,
            consequence=consequence)

    measured = asked(profile_version)
    querying = asked(query_version)
    session = seeded(module)
    try:
        provider = RUNTIME.provider.LocalBoundedProvider(session)
        state = {"schema_version": 1, "run_id": "m", "project": "p", "packets": [],
                 "approvals": [], "decisions": [], "decision_batches": []}
        record = RUNTIME.profiles.build_profile(
            decision_definition="failure-classification", questions=[measured.as_record()],
            runtime=provider.provider, implementation=provider.model, model=provider.model,
            revision=revision or provider.model_version, dataset_digest="f" * 64,
            dataset_size=RUNTIME.profiles.MIN_PROFILE_DATASET,
            accuracy=0.9, coverage=0.95, ece=0.05, brier=0.08,
            thresholds_by_risk={risk: 0.999 for risk in (declared_risks or (consequence,))})
        RUNTIME.profiles.record_profile(state, record)
        if status:
            RUNTIME.profiles.set_profile_status(state, record.profile_id, status)
        try:
            batch.evaluate(
                state, questions=[querying],
                projection={"entries": {"failure": "Traceback: TypeError: x"},
                            "digest": "d" * 64, "verification_level": "OBSERVED"},
                provider=provider, task_id="m")
        except Exception:
            return False
    finally:
        session.shutdown()
    return bool(state["decisions"][-1]["effective_policy"]["min_confidence_by_question"])


def probe_legacy_alias_still_matches(module) -> bool:
    """A profile stored with a legacy runtime alias must still match the canonical runtime."""
    RUNTIME = runtime_of(module)
    canonical = module.contracts.CANONICAL_RUNTIME_ID
    Question = module.decisions.contracts.DecisionQuestion
    legacy = Question(
        question_id="failure-class", instructions="bounded failure class",
        primitive="ChoiceDecision",
        options=tuple(module.contracts.DECISION_CLASSIFIABLE_FAILURE_CLASSES),
        projection_contract="failure-classification", definition_version="1",
        consequence="LOW")
    state = {"schema_version": 1, "run_id": "m", "project": "p", "packets": [], "approvals": []}
    built = RUNTIME.profiles.build_profile(
        decision_definition="failure-classification", questions=[legacy.as_record()],
        runtime="local_bounded", implementation=RUNTIME.reference.ENGINE_NAME,
        model=RUNTIME.reference.ENGINE_NAME, revision=RUNTIME.reference.ENGINE_REVISION,
        dataset_digest="7" * 64, dataset_size=RUNTIME.profiles.MIN_PROFILE_DATASET,
        accuracy=0.9, coverage=0.95, ece=0.05, brier=0.08, thresholds_by_risk={"LOW": 0.9})
    # Exactly what 2.1 development wrote, before canonicalisation existed.
    state.setdefault("calibration_profiles", []).append(
        {**built.as_record(), "runtime": "local_bounded"})
    verdict = RUNTIME.profiles.profile_for(
        state, decision_definition="failure-classification", question=legacy, risk="LOW",
        runtime=canonical, implementation=RUNTIME.reference.ENGINE_NAME,
        model_revision=RUNTIME.reference.ENGINE_REVISION)
    if not verdict["accepted"]:
        return False
    # And normalisation must stay narrow: a different revision still refuses, and so
    # must an unrecognised runtime name, which must never silently become this one.
    drifted = RUNTIME.profiles.profile_for(
        state, decision_definition="failure-classification", question=legacy, risk="LOW",
        runtime=canonical, implementation=RUNTIME.reference.ENGINE_NAME,
        model_revision="deadbeef")
    if drifted["accepted"]:
        return False
    unknown = RUNTIME.profiles.profile_for(
        state, decision_definition="failure-classification", question=legacy, risk="LOW",
        runtime="unknown-runtime", implementation=RUNTIME.reference.ENGINE_NAME,
        model_revision=RUNTIME.reference.ENGINE_REVISION)
    if unknown["accepted"]:
        return False
    external = RUNTIME.profiles.profile_for(
        state, decision_definition="failure-classification", question=legacy, risk="LOW",
        runtime="external_bounded", implementation=RUNTIME.reference.ENGINE_NAME,
        model_revision=RUNTIME.reference.ENGINE_REVISION)
    return external["accepted"] is False


def probe_doctor_checks_the_runtime(module) -> bool:
    """`doctor` must report on the Decision Runtime, not skip it."""
    RUNTIME = runtime_of(module)
    api = module.api
    with tempfile.TemporaryDirectory(prefix="ar206-mut-doctor-") as workspace:
        root = Path(workspace) / "runtime"
        RUNTIME.seeds.install_seeds(root)
        health = api.decision_runtime_health(root=root, timeout=15.0)
    labels = {row[1] for row in health.get("rows", [])}
    return health["status"] == "HEALTHY" and "Decision Runtime" in labels


def probe_absent_runtime_is_not_fatal(module) -> bool:
    """An absent optional runtime must not be reported as a problem."""
    api = module.api
    with tempfile.TemporaryDirectory(prefix="ar206-mut-absent-") as workspace:
        home = Path(workspace) / "data"
        previous_home = os.environ.get("ARIADNE_DATA_HOME")
        previous_override = os.environ.pop("ARIADNE_DECISION_RUNTIME", None)
        os.environ["ARIADNE_DATA_HOME"] = str(home)
        try:
            health = api.decision_runtime_health(timeout=6.0)
        finally:
            if previous_home is None:
                os.environ.pop("ARIADNE_DATA_HOME", None)
            else:
                os.environ["ARIADNE_DATA_HOME"] = previous_home
            if previous_override is not None:
                os.environ["ARIADNE_DECISION_RUNTIME"] = previous_override
    return (health["status"] == "OPTIONAL_RUNTIME_UNAVAILABLE"
            and all(row[0] != "problem" for row in health.get("rows", [])))


def probe_doctor_never_claims_calibration(module) -> bool:
    """A working runtime with no profile must not be reported as calibrated."""
    api = module.api
    RUNTIME = runtime_of(module)
    with tempfile.TemporaryDirectory(prefix="ar206-mut-cal-") as workspace:
        root = Path(workspace) / "runtime"
        RUNTIME.seeds.install_seeds(root)
        health = api.decision_runtime_health(root=root, timeout=15.0)
    text = json.dumps(health, default=str).lower()
    return health["status"] == "HEALTHY" and health["calibration"]["proven"] == 0 and "calibrated" not in text


def probe_broken_runtime_is_named(module) -> bool:
    """A configured runtime that will not start must be named, not crash."""
    api = module.api
    RUNTIME = runtime_of(module)
    with tempfile.TemporaryDirectory(prefix="ar206-mut-broken-") as workspace:
        root = Path(workspace) / "runtime"
        RUNTIME.seeds.install_seeds(root)
        (root / "weights.json").write_text("{ not json at all", encoding="utf-8")
        health = api.decision_runtime_health(root=root, timeout=6.0)
    return (health["status"] == "BROKEN"
            and any(row[0] == "problem" for row in health.get("rows", []))
            and "Traceback" not in json.dumps(health, default=str))


def probe_doctor_makes_no_process_launch(module) -> bool:
    """`doctor` must answer its own question in-process, not by launching a process.

    A doctor that spawns a sidecar on every invocation is slow enough to destabilise the
    suite that calls it, and it inherits every hang the transport can have. It was
    observed flaking the distribution suite under load before this was reasoned about.
    """
    api = module.api
    source = inspect.getsource(api.decision_runtime_health)
    smoke_source = inspect.getsource(api._runtime_smoke)
    launches = ("Popen", "DecisionRuntime.discover", "SubprocessTransport", "import subprocess")
    if any(token in source for token in launches) or any(
            token in smoke_source for token in launches):
        return False
    with tempfile.TemporaryDirectory(prefix="ar206-mut-noproc-") as workspace:
        root = Path(workspace) / "runtime"
        runtime_of(module).seeds.install_seeds(root)
        started = time.perf_counter()
        health = api.decision_runtime_health(root=root)
        elapsed = time.perf_counter() - started
    # An in-process check answers in milliseconds; a process launch cannot.
    return health["status"] == "HEALTHY" and elapsed < 2.0


MUTATIONS: tuple[dict, ...] = (
    {
        "name": "let an abstention become an answer",
        "file": f"{RUNTIME}/reference.py",
        "old": '        return Score(question_id, family, "", 0.0, {}, True, "NO_LOCAL_MODEL")',
        "new": '        return Score(question_id, family, str(space[0]), 1.0,\n'
               '                      {str(space[0]): 1.0}, False, "")',
        "probe": probe_abstention_is_not_an_answer,
    },
    {
        "name": "answer the primitive the runtime cannot represent",
        "file": f"{RUNTIME}/reference.py",
        "old": '    return str(primitive) not in SUPPORTED_PRIMITIVES',
        "new": "    return False",
        "probe": probe_unsupported_primitive_is_refused,
    },
    {
        "name": "accept a DRAFT profile as calibration",
        "file": f"{RUNTIME}/profiles.py",
        "old": '        if candidate.status != "PROVEN":\n'
               '            reasons.append(f"the matching profile is {candidate.status}, not PROVEN")',
        "new": '        if candidate.status not in ("PROVEN", "DRAFT"):\n'
               '            reasons.append(f"the matching profile is {candidate.status}, not PROVEN")',
        "probe": probe_draft_profile_cannot_calibrate,
    },
    {
        "name": "let a moving alias satisfy a calibration profile",
        "file": f"{RUNTIME}/profiles.py",
        "old": '    if not revision_matches(candidate.revision, str(model_revision)):',
        "new": "    if False:",
        "probe": probe_alias_cannot_satisfy_a_profile,
    },
    {
        "name": "let the runtime self-grant calibration",
        "file": f"{RUNTIME}/session.py",
        "old": '        "calibration_self_granted": bool(described.get("calibration_self_granted", False)),',
        "new": '        "calibration_self_granted": False,',
        "probe": probe_runtime_cannot_self_grant_calibration,
    },
    {
        "name": "accept an answer outside the closed answer space",
        "file": f"{RUNTIME}/provider.py",
        "old": "        if parsed.problems:",
        "new": "        if False:",
        "probe": probe_closed_answer_space,
    },
    {
        "name": "make the shadow isolation check decorative",
        "file": f"{RUNTIME}/shadow.py",
        "old": '    problems: list[str] = []\n'
               '    for record in state.get("decision_shadow", []) or []:\n'
               '        for problem in shadow_record_problems(record):',
        "new": '    problems: list[str] = []\n'
               '    for record in []:\n'
               '        for problem in shadow_record_problems(record):',
        "probe": probe_shadow_isolation_is_load_bearing,
    },
    {
        "name": "accept ground truth with no source",
        "file": f"{RUNTIME}/shadow.py",
        "old": '    if not str(source or "").strip():\n'
               '        raise ValueError("ground truth must name its source; an unsourced outcome is not evidence")',
        "new": "    if False:\n        pass",
        "probe": probe_shadow_ground_truth_must_be_sourced,
    },
    {
        "name": "compute the reconciled record without storing it",
        "file": f"{RUNTIME}/shadow.py",
        "old": "            state[\"decision_shadow\"][index] = updated",
        "new": "            pass",
        "probe": probe_shadow_ground_truth_is_persisted,
    },
    {
        "name": "let the runtime grant authority",
        "file": f"{RUNTIME}/provider.py",
        "old": '            "authorization_effect": "none",',
        "new": '            "authorization_effect": "PRE_APPROVED",',
        "probe": probe_no_authority_from_the_runtime,
    },
    {
        "name": "let a slice jump straight to ACTIVE",
        "file": f"{RUNTIME}/promotion.py",
        "old": '    "UNTESTED": ("SHADOW", "SUSPENDED"),',
        "new": '    "UNTESTED": ("SHADOW", "SUSPENDED", "ACTIVE", "ELIGIBLE"),',
        "probe": probe_promotion_cannot_skip_the_lifecycle,
    },
    {
        "name": "let a slice outgrow its risk scope",
        "file": f"{RUNTIME}/promotion.py",
        "old": '    if declared.get("reversible") and not requested.get("reversible", True):',
        "new": "    if False:",
        "probe": probe_slice_cannot_outgrow_its_scope,
    },
    {
        "name": "let a slice answer a language it was never evaluated for",
        "file": f"{RUNTIME}/promotion.py",
        "old": "    uncovered = requested_languages - declared_languages\n    if uncovered:",
        "new": "    uncovered = set()\n    if uncovered:",
        "probe": probe_slice_cannot_outgrow_its_scope,
    },
    {
        "name": "compare metrics across different experiments",
        "file": f"{RUNTIME}/evaluation.py",
        "old": "    return (not reasons), reasons",
        "new": "    return True, reasons",
        "probe": probe_metrics_need_comparable_identity,
    },
    {
        "name": "call freshly computed digests verification",
        "file": f"{RUNTIME}/integrity.py",
        "old": '            "status": "UNKNOWN",\n'
               '            "detail": "no reviewed digest record was supplied; '
               'refusing to describe the artifact as verified",',
        "new": '            "status": "PASS",\n'
               '            "detail": "verified",',
        "probe": probe_fresh_digest_is_not_verification,
    },
    # -- AR-206 closure: the abstention policy wiring -------------------------------
    {
        "name": "remove the resolved policy from the batch request",
        "file": "decisions/batch.py",
        "old": '            "policy": {\n'
               '                "min_confidence_by_question": dict(effective["min_confidence_by_question"]),\n'
               '                "calibration_profile_by_question": dict(\n'
               '                    effective["calibration_profile_by_question"]),\n'
               '            },',
        "new": '            "policy": {},',
        "probe": probe_production_path_abstains,
    },
    {
        "name": "invent a universal fallback threshold",
        "file": "decisions/batch.py",
        "old": '        if not verdict.get("accepted"):\n            continue',
        "new": '        if not verdict.get("accepted"):\n'
               '            thresholds[question.question_id] = 0.8\n'
               '            continue',
        "probe": probe_no_universal_fallback_threshold,
    },
    {
        "name": "let a RETIRED profile act",
        "file": f"{RUNTIME}/profiles.py",
        "old": '        if candidate.status != "PROVEN":\n'
               '            reasons.append(f"the matching profile is {candidate.status}, not PROVEN")\n'
               '            continue',
        "new": '        if candidate.status not in ("PROVEN", "RETIRED", "REVOKED", "DRAFT"):\n'
               '            reasons.append(f"the matching profile is {candidate.status}, not PROVEN")\n'
               '            continue',
        "probe": probe_retired_profile_ignored,
    },
    {
        "name": "ignore the model revision when matching a profile",
        "file": f"{RUNTIME}/profiles.py",
        "old": '    if not revision_matches(candidate.revision, str(model_revision)):',
        "new": "    if False:",
        "probe": probe_revision_mismatch_ignored,
    },
    {
        "name": "ignore the question version when matching a profile",
        "file": f"{RUNTIME}/profiles.py",
        "edits": (
            ('    if expected_version not in {part.strip() for part in candidate.question_version.split(",")}:',
             "    if False:"),
            ('    if candidate.question_schema_digest != expected_schema:',
             "    if False:"),
            ('    if candidate.decision_definition_digest != expected_definition:',
             "    if False:"),
        ),
        "probe": probe_question_schema_mismatch_ignored,
    },
    {
        "name": "borrow another risk class's threshold when none was measured",
        "file": f"{RUNTIME}/profiles.py",
        "edits": (
            ('    speaking = [profile for profile in matching if risk in profile.thresholds_by_risk]',
             '    speaking = list(matching)'),
            ('        "min_confidence": float(chosen.thresholds_by_risk[risk]),',
             '        "min_confidence": float(\n'
             '            chosen.thresholds_by_risk.get(\n'
             '                risk, min(chosen.thresholds_by_risk.values(), default=0.0))),'),
        ),
        "probe": probe_risk_class_mismatch_ignored,
    },
    {
        "name": "apply the first question's threshold to the whole batch",
        "file": f"{RUNTIME}/reference.py",
        "old": '                threshold = by_question.get(question_id, min_confidence)',
        "new": '                threshold = next(iter(by_question.values()), min_confidence)',
        "probe": probe_batch_threshold_does_not_leak,
    },
    {
        "name": "discard the evidence behind a threshold abstention",
        "file": f"{RUNTIME}/reference.py",
        "old": '                    if score.has_evidence:\n'
               '                        slot["candidate_answer"] = score.label\n'
               '                        slot["candidate_confidence"] = score.probability',
        "new": '                    if False:\n'
               '                        slot["candidate_answer"] = score.label\n'
               '                        slot["candidate_confidence"] = score.probability',
        "probe": probe_evidence_preserved,
    },
    {
        "name": "relabel a provider probability as calibrated",
        "file": f"{RUNTIME}/provider.py",
        "old": '    claimed = str(value or "PROVIDER_PROBABILITY")\n'
               '    return claimed if claimed in offered else "SELF_REPORTED_CONFIDENCE"',
        "new": '    return str(value or "PROVIDER_PROBABILITY")',
        "probe": probe_never_reports_calibrated,
    },
    {
        "name": "let confidence grant authorization",
        "file": "decisions/batch.py",
        "old": '            "acted_on": False,',
        "new": '            "acted_on": True,',
        "probe": probe_confidence_cannot_authorize,
    },
    # -- AR-206 polish: canonical identity and doctor integration --------------------
    {
        "name": "remove runtime canonicalization entirely",
        "file": "contracts.py",
        "old": '    return RUNTIME_ID_ALIASES.get(label, label)',
        "new": "    return label",
        "probe": probe_legacy_alias_still_matches,
    },
    {
        "name": "canonicalise every string, including unknown runtimes",
        "file": "contracts.py",
        "old": '    return RUNTIME_ID_ALIASES.get(label, label)',
        "new": '    return RUNTIME_ID_ALIASES.get(label, CANONICAL_RUNTIME_ID)',
        "probe": probe_legacy_alias_still_matches,
    },
{
        "name": "let a doctor skip the Decision Runtime entirely",
        "file": "api.py",
        "old": '    record["rows"] = rows\n    record["problems"] = problems\n    return record',
        "new": '    record["rows"] = []\n    record["problems"] = problems\n    return record',
        "probe": probe_doctor_checks_the_runtime,
    },
    {
        "name": "make an absent optional runtime fatal",
        "file": "api.py",
        "old": '            ("ok", "Decision Runtime",\n'
               '             "not installed (optional); Ariadne answers bounded questions without it"),',
        "new": '            ("problem", "Decision Runtime",\n'
               '             "not installed; Ariadne cannot answer bounded questions"),',
        "probe": probe_absent_runtime_is_not_fatal,
    },
    {
        "name": "let doctor call an unprofiled runtime calibrated",
        "file": "api.py",
        "old": '    record["status"] = "HEALTHY" if record["smoke"]["passed"] else "AVAILABLE_WITH_LIMITATIONS"',
        "new": '    record["status"] = "CALIBRATED"\n'
               '    record["calibration"] = {"profiles": 1, "proven": 1,\n'
               '                            "active_families": 1, "active_thresholds": 1}',
        "probe": probe_doctor_never_claims_calibration,
    },
    {
        "name": "hide a broken runtime behind a healthy report",
        "file": "api.py",
        "old": '    if not status:\n        record["status"] = "BROKEN"',
        "new": '    if not status:\n        record["status"] = "HEALTHY"',
        "probe": probe_broken_runtime_is_named,
    },
    {
        "name": "make doctor launch a sidecar it can then hang on",
        "file": "api.py",
        "old": '        engine = sidecar_module.build_engine(found["root"])',
        "new": '        from .decisions.runtime import session as _doctor_session\n'
               '        _doctor_session.DecisionRuntime.discover(\n'
               '            root=str(found["root"]),\n'
               '        ).shutdown()\n'
               '        engine = sidecar_module.build_engine(found["root"])',
        "probe": probe_doctor_makes_no_process_launch,
    },
)


def run() -> int:
    before = source_hashes()
    results: list[tuple[str, bool, bool, bool, str]] = []
    with tempfile.TemporaryDirectory(prefix="ar206-runtime-mutations-") as workspace:
        root = Path(workspace)
        pristine = root / "pristine" / "ariadne_engine"
        live = root / "live" / "ariadne_engine"
        shutil.copytree(ENGINE, pristine)
        control_module = load_mutant(pristine, "ariadne_engine_ar206_control")
        for index, mutation in enumerate(MUTATIONS):
            shutil.rmtree(live.parent, ignore_errors=True)
            live.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(pristine, live)
            target = live / mutation["file"]
            text = target.read_text(encoding="utf-8")
            edits = mutation.get("edits") or ((mutation.get("old", ""), mutation.get("new", "")),)
            missing = [old for old, _ in edits if old not in text]
            if missing:
                results.append((mutation["name"], False, False, False,
                                "mutation target not found; the source moved and this test is stale"))
                continue
            for old, new in edits:
                text = text.replace(old, new, 1)
            target.write_text(text, encoding="utf-8")
            try:
                mutant = load_mutant(live, f"ariadne_engine_ar206_mutation_{index}")
            except Exception as exc:  # noqa: BLE001 - a mutation that cannot import is not caught
                results.append((mutation["name"], True, False, False,
                                f"mutant failed to import: {exc}"))
                continue
            try:
                control = bool(mutation["probe"](control_module))
                mutated = bool(mutation["probe"](mutant))
            except Exception as exc:  # noqa: BLE001
                results.append((mutation["name"], True, False, False, f"probe error: {exc}"))
                continue
            caught = control and not mutated
            detail = (
                "refused by the original, allowed by the mutant"
                if caught else
                ("the probe did not hold on the original" if not control
                 else "the mutant still refused the attack")
            )
            results.append((mutation["name"], control, mutated, caught, detail))
    after = source_hashes()
    print("ARIADNE DECISION RUNTIME MUTATION TESTS\n")
    failed = 0
    for name, control, mutated, caught, detail in results:
        if not caught:
            failed += 1
        print(("ok    " if caught else "FAIL  ") + f"{name}: {detail}")
    print(f"\n{'unmodified' if before == after else 'MODIFIED'}  "
          f"engine sources byte-identical: {before == after}")
    print(f"{'FAILED' if failed else 'PASS'}  {len(results) - failed}/{len(results)} mutations caught")
    return 1 if failed or before != after else 0


if __name__ == "__main__":
    raise SystemExit(run())
