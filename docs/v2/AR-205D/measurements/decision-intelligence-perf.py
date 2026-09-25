#!/usr/bin/env python3
"""Local overhead measurements for the AR-205D decision-intelligence layer.

Deterministic, offline, stdlib only. Reports median and p95 wall time for the
five operations the milestone asks about: compile plan, build decision graph,
batch planning, state projection, cache lookup and trace generation.

Run: python docs/v2/AR-205D/measurements/decision-intelligence-perf.py
"""

from __future__ import annotations

import json
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "src"))
import ariadne_engine as engine  # noqa: E402

DEC = engine.decisions
ITERATIONS = 200


def state() -> dict:
    return {
        "schema_version": 1,
        "run_id": "perf",
        "project": str(ROOT),
        "run_root": str(ROOT / "validation" / "perf"),
        "packets": [{"id": "perf-S4B", "stage": "S4B", "path": str(ROOT / "validation" / "perf")}],
        "approvals": [],
    }


def provider():
    return DEC.providers.DeterministicProvider(
        script={"failure-class": {"answer": "TIMEOUT", "confidence": 0.8,
                                  "confidence_kind": "DERIVED_CONFIDENCE"}},
        model_version="2026.1",
    )


def timed(callable_, iterations: int = ITERATIONS) -> dict:
    samples: list[float] = []
    for _ in range(iterations):
        started = time.perf_counter()
        callable_()
        samples.append((time.perf_counter() - started) * 1_000_000)
    samples.sort()
    return {
        "median_us": round(statistics.median(samples), 1),
        "p95_us": round(samples[int(len(samples) * 0.95) - 1], 1),
        "iterations": iterations,
    }


def main() -> int:
    measurements: dict[str, dict] = {}

    plan_state = state()
    requirements = [
        {"requirement_id": "test", "kind": "test-exit-code", "known": True, "value": 0},
        {"requirement_id": "failure-class", "kind": "failure-class"},
        {"requirement_id": "impl", "kind": "implementation"},
    ]
    measurements["compile_plan"] = timed(lambda: DEC.compiler.compile_plan(
        plan_state, requirements=requirements, task_id="perf-S4B",
        decision_provider=provider(), generative_available=True, record=False,
    ))
    plan = DEC.compiler.compile_plan(plan_state, requirements=requirements, task_id="perf-S4B")
    graph_state = state()
    measurements["build_decision_graph"] = timed(lambda: DEC.graph.from_plan(graph_state, plan))

    questions = [
        DEC.contracts.DecisionQuestion(
            question_id=f"q{index}", instructions="Choose.", options=("a", "b"),
            projection_contract="failure-classification",
        )
        for index in range(4)
    ]
    measurements["batch_planning"] = timed(lambda: DEC.planner.plan_steps(
        questions, depends_on={"q1": ["q0"]},
    ))
    entries = {"failure": {"source": "mystery", "detail": "d"}, "changed_scope": ["src/x.py"]}
    measurements["state_projection"] = timed(lambda: DEC.projections.build(
        "failure-classification", entries=entries,
    ))
    projection = DEC.projections.build("failure-classification", entries=entries)
    cache_state = state()
    question = DEC.contracts.DecisionQuestion(
        question_id="failure-class", instructions="Classify.",
        options=engine.contracts.DECISION_CLASSIFIABLE_FAILURE_CLASSES,
        projection_contract="failure-classification",
    )
    DEC.planner.evaluate_step(
        cache_state, questions=[question], projections={"failure-classification": projection},
        provider=provider(), cache_enabled=True,
    )
    measurements["cache_lookup_hit"] = timed(lambda: DEC.cache.lookup(
        cache_state, question=question, projection_digest=projection["digest"],
        provider="deterministic-fixture", model_version="2026.1",
    ))
    trace_state = state()
    DEC.compiler.compile_plan(
        trace_state,
        requirements=[{"requirement_id": "failure-class", "kind": "failure-class"}],
        task_id="perf-S4B", decision_provider=provider(),
    )
    DEC.integrations.classify_failure(
        trace_state, source="mystery", provider=provider(), task_id="perf-S4B",
    )
    measurements["trace_generation"] = timed(
        lambda: DEC.trace.explain(trace_state, task_id="perf-S4B"), iterations=50,
    )

    document = {
        "schema_version": 1,
        "milestone": "AR-205D",
        "environment": {"python": sys.version.split()[0], "platform": sys.platform},
        "iterations": ITERATIONS,
        "measurements": measurements,
        "note": (
            "local wall-clock only: these are structural overheads of the decision layer, "
            "not provider latency and not a benchmark of model quality"
        ),
    }
    destination = Path(__file__).with_name("decision-intelligence-perf.json")
    destination.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(document, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
