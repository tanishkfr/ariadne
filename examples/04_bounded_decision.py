"""Example 04: one bounded decision, evaluated by the deterministic provider."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from ariadne_engine import decisions  # noqa: E402


def main() -> int:
    state: dict = {}
    question = decisions.contracts.DecisionQuestion(
        question_id="failure-class",
        instructions="Classify this failure into exactly one declared class.",
        options=("TIMEOUT", "AUTHORIZATION_FAILURE", "UNKNOWN"),
        consequence="LOW",
    )
    provider = decisions.providers.DeterministicProvider(
        script={"failure-class": {
            "answer": "TIMEOUT", "confidence": 0.8, "confidence_kind": "DERIVED_CONFIDENCE",
        }},
    )
    projection = decisions.batch.project(entries={"command": {"timed_out": True}})
    batch = decisions.batch.evaluate(
        state, questions=[question], projection=projection,
        provider=provider, task_id="example-task",
    )
    record = decisions.batch.decision(state, batch["results"][0]["decision_id"])
    print("status:", record["status"])
    print("answer:", record.get("raw"))
    print("provider:", record["provider"], "model:", record["model_version"])
    print("authorization effect:", record["authorization_effect"])
    print("acted on:", record["acted_on"])
    print(
        "\nA decision can inform the next action; it can never authorize a protected "
        "one, and it is bound to the projection digest it saw."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
