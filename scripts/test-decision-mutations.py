#!/usr/bin/env python3
"""AR-205D mutation tests for the decision-intelligence protections.

Each mutation removes or weakens one protection in a *copy* of the engine
package, then runs the attack that protection exists to refuse. A mutation is
caught when the attack is refused by the original and allowed by the mutant,
which is exactly what a failing protection test would observe.

The repository sources are never written: the engine package is copied to a
temporary directory, mutated there, imported under a unique module name, and
discarded. The script verifies before and after that every engine source file
is byte-identical (sha256), so "restore byte-exact" holds by construction.

Run: python scripts/test-decision-mutations.py
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).resolve().parent.parent
ENGINE = ROOT / "src" / "ariadne_engine"


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


def state(module, **extra) -> dict:
    value = {
        "schema_version": 1,
        "run_id": "mutation",
        "project": "C:/tmp/mutation-project",
        "run_root": "C:/tmp/mutation-run",
        "packets": [{"id": "t-S4B", "stage": "S4B", "path": "C:/tmp/mutation-run/t-S4B"}],
        "approvals": [],
    }
    value.update(extra)
    return value


def question(module, **overrides):
    options = {
        "question_id": "failure-class",
        "instructions": "Classify the failure.",
        "options": module.contracts.DECISION_CLASSIFIABLE_FAILURE_CLASSES,
        "consequence": "LOW",
        "projection_contract": "failure-classification",
    }
    options.update(overrides)
    return module.decisions.contracts.DecisionQuestion(**options)


def failure_projection(module) -> dict:
    return module.decisions.projections.build(
        "failure-classification", entries={"failure": {"source": "mystery", "detail": "d"}},
    )


def scripted(module, answer="TIMEOUT", confidence=0.8, kind="DERIVED_CONFIDENCE", model_version="1"):
    return module.decisions.providers.DeterministicProvider(
        script={"failure-class": {"answer": answer, "confidence": confidence,
                                  "confidence_kind": kind}},
        model_version=model_version,
    )


# ------------------------------------------------------------------- probes
# A probe returns True when the protection holds (the attack is refused).


def probe_deterministic_first(module) -> bool:
    verdict = module.decisions.compiler.classify_requirement({"kind": "failure-class"}, known=True)
    plan = module.decisions.compiler.compile_plan(
        state(module),
        requirements=[{"requirement_id": "fact", "kind": "failure-class", "known": True, "value": "x"}],
        decision_provider=module.decisions.providers.UnavailableProvider(),
    )
    return verdict["classification"] == "DETERMINISTIC" and not plan["bounded_questions"]


def probe_batch_independence(module) -> bool:
    problems = module.economics.batch_dependency_problems(
        [{"question_id": "a"}, {"question_id": "b"}], depends_on={"b": ["a"]},
    )
    return bool(problems)


def probe_cache_model_binding(module) -> bool:
    value = question(module)
    first = module.decisions.cache.key_for(
        value, projection_digest="ab" * 32, provider="p", model_version="1", policy_version="v",
    )
    second = module.decisions.cache.key_for(
        value, projection_digest="ab" * 32, provider="p", model_version="2", policy_version="v",
    )
    return first != second


def probe_confidence_authority(module) -> bool:
    record = {
        "decision_id": "dec_fixture_00000000",
        "status": "answered",
        "answer_valid": True,
        "confidence": 0.99,
        "confidence_kind": "CALIBRATED_PROBABILITY",
    }
    return module.decisions.policy.may_act(record, consequence="PROTECTED")["accepted"] is False


def probe_human_gate(module) -> bool:
    local = state(module)
    graph = module.decisions.graph.create(local, nodes=[{"id": "gate", "kind": "HUMAN_GATE"}])
    try:
        module.decisions.graph.mark_outcome(
            local, graph["graph_id"], "gate", status="SUCCEEDED", outcome={"approved": True},
            human_decision={"identity": "engine", "channel": "engine", "approved": True},
        )
    except module.contracts.ContractError:
        return True
    return False


def probe_closed_answer_set(module) -> bool:
    value = question(module)
    _, problems = module.decisions.contracts.validate_answer(value, "AUTHORIZATION_FAILURE")
    return bool(problems)


def probe_state_digest(module) -> bool:
    projection = module.decisions.batch.project(entries={"failure": {"source": "x"}})
    return len(str(projection.get("digest", ""))) == 64


def probe_stale_cache(module) -> bool:
    local = state(module)
    provider = scripted(module)
    projection = failure_projection(module)
    module.decisions.planner.evaluate_step(
        local, questions=[question(module)], projections={"failure-classification": projection},
        provider=provider, cache_enabled=True,
    )
    module.decisions.cache.invalidate(local, question_id="failure-class", reason="the requirement changed")
    lookup = module.decisions.cache.lookup(
        local, question=question(module), projection_digest=projection["digest"],
        provider="deterministic-fixture", model_version="1",
    )
    return lookup["hit"] is False


def probe_generation_gate(module) -> bool:
    local = state(module)
    module.decisions.compiler.compile_plan(
        local, requirements=[{"requirement_id": "impl", "kind": "implementation"}],
        generative_available=True,
    )
    return bool(module.decisions.generation.gate_problems(local))


MUTATIONS: tuple[dict, ...] = (
    {
        "name": "remove the deterministic-first guard",
        "file": "decisions/compiler.py",
        "old": "    if known:\n        return {\n            \"kind\": kind,\n            \"classification\": \"DETERMINISTIC\",\n            \"reason\": \"CODE_KNOWS\",",
        "new": "    if known and False:\n        return {\n            \"kind\": kind,\n            \"classification\": \"DETERMINISTIC\",\n            \"reason\": \"CODE_KNOWS\",",
        "probe": probe_deterministic_first,
    },
    {
        "name": "weaken batch independence",
        "file": "economics.py",
        "old": "    depends = {str(key): {str(item) for item in (value or [])} for key, value in dict(depends_on or {}).items()}\n    ids = {str(question.get(\"question_id\", \"\")) for question in questions or ()}",
        "new": "    return []\n    depends = {str(key): {str(item) for item in (value or [])} for key, value in dict(depends_on or {}).items()}\n    ids = {str(question.get(\"question_id\", \"\")) for question in questions or ()}",
        "probe": probe_batch_independence,
    },
    {
        "name": "remove the cache model-version binding",
        "file": "decisions/cache.py",
        "old": "        \"provider\": str(provider),\n        \"model_version\": str(model_version),\n        \"policy_version\": str(policy_version),",
        "new": "        \"provider\": str(provider),\n        \"policy_version\": str(policy_version),",
        "probe": probe_cache_model_binding,
    },
    {
        "name": "allow confidence to authorize a protected action",
        "file": "decisions/policy.py",
        "edits": (
            (
                "            \"accepted\": False,\n            \"reason\": \"a protected operation is human-controlled regardless of confidence\",",
                "            \"accepted\": True,\n            \"reason\": \"a protected operation is human-controlled regardless of confidence\",",
            ),
            (
                "    if consequence == \"PROTECTED\":\n        return {\"accepted\": False, \"required\": required,\n                \"reason\": \"protected operations are human-controlled; no decision evidence substitutes for authorization\"}",
                "    if consequence == \"PROTECTED\":\n        return {\"accepted\": True, \"required\": required,\n                \"reason\": \"protected operations are human-controlled; no decision evidence substitutes for authorization\"}",
            ),
        ),
        "probe": probe_confidence_authority,
    },
    {
        "name": "remove the protected human gate",
        "file": "decisions/graph.py",
        "old": "    if str(item.get(\"kind\", \"\")) == \"HUMAN_GATE\":\n        if status == \"SUCCEEDED\":",
        "new": "    if False:\n        if status == \"SUCCEEDED\":",
        "probe": probe_human_gate,
    },
    {
        "name": "accept an answer outside the closed set",
        "file": "decisions/contracts.py",
        "old": "    if values[0] not in allowed:\n        problems.append(\"answer outside the declared option set: \" + values[0])",
        "new": "    if False:\n        problems.append(\"answer outside the declared option set: \" + values[0])",
        "probe": probe_closed_answer_set,
    },
    {
        "name": "bypass the projected state digest",
        "file": "decisions/batch.py",
        "old": "        \"digest\": state_digest({str(key): value for key, value in entries.items()}),",
        "new": "        \"digest\": \"\" if entries else state_digest({str(key): value for key, value in entries.items()}),",
        "probe": probe_state_digest,
    },
    {
        "name": "permit a revoked cached decision",
        "file": "decisions/cache.py",
        "old": "        if str(item.get(\"freshness\", \"\")) == \"REVOKED\":",
        "new": "        if False:",
        "probe": probe_stale_cache,
    },
    {
        "name": "skip the generation justification",
        "file": "decisions/generation.py",
        "old": "def gate_problems(state: Mapping, *, task_id: str = \"\") -> list[str]:\n    \"\"\"Deterministic problems for an unjustified generation path.\"\"\"",
        "new": "def gate_problems(state: Mapping, *, task_id: str = \"\") -> list[str]:\n    \"\"\"Deterministic problems for an unjustified generation path.\"\"\"\n    return []",
        "probe": probe_generation_gate,
    },
)


def run() -> int:
    before = source_hashes()
    results: list[tuple[str, bool, bool, bool, str]] = []
    with tempfile.TemporaryDirectory(prefix="ariadne-mutations-") as workspace:
        root = Path(workspace)
        pristine = root / "pristine" / "ariadne_engine"
        live = root / "live" / "ariadne_engine"
        shutil.copytree(ENGINE, pristine)
        control_module = load_mutant(pristine, "ariadne_engine_mutation_control")
        for index, mutation in enumerate(MUTATIONS):
            shutil.rmtree(live.parent, ignore_errors=True)
            live.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(pristine, live)
            target = live / mutation["file"]
            text = target.read_text(encoding="utf-8")
            edits = mutation.get("edits") or ((mutation.get("old", ""), mutation.get("new", "")),)
            missing = [old for old, _ in edits if old not in text]
            if missing:
                results.append((mutation["name"], False, False, False, "mutation target not found"))
                continue
            for old, new in edits:
                text = text.replace(old, new, 1)
            target.write_text(text, encoding="utf-8")
            try:
                mutant = load_mutant(live, f"ariadne_engine_mutation_{index}")
            except Exception as exc:  # a mutation that cannot even import is not a caught mutation
                results.append((mutation["name"], True, False, False, f"mutant failed to import: {exc}"))
                continue
            try:
                control = bool(mutation["probe"](control_module))
                mutated = bool(mutation["probe"](mutant))
            except Exception as exc:
                results.append((mutation["name"], True, False, False, f"probe error: {exc}"))
                continue
            caught = control and not mutated
            detail = (
                "refused by the original, allowed by the mutant"
                if caught else
                ("the probe did not hold on the original" if not control else "the mutant still refused the attack")
            )
            results.append((mutation["name"], control, mutated, caught, detail))
    after = source_hashes()
    print("ARIADNE AR-205D MUTATION TESTS\n")
    failed = 0
    for name, control, mutated, caught, detail in results:
        if not caught:
            failed += 1
        print(("ok    " if caught else "FAIL  ") + f"{name}: {detail}")
    print(f"\n{'unmodified' if before == after else 'MODIFIED'}  engine sources byte-identical: {before == after}")
    print(f"{'FAILED' if failed else 'PASS'}  {len(results) - failed}/{len(results)} mutations caught")
    return 1 if failed or before != after else 0


if __name__ == "__main__":
    raise SystemExit(run())
