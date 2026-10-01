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
import importlib.util
import shutil
import sys
import tempfile
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
