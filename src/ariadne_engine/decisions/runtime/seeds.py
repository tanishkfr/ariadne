"""Seed weights, derived from rules Ariadne already ships.

The reference engine refuses to answer a question it has no weights for. Shipping it
with *no* weights would therefore make the "baked in" claim hollow: every bounded
question would abstain on a fresh install.

So the first weight set is derived from Ariadne's own deterministic decision tables —
the same vocabularies and mappings that
:mod:`ariadne_engine.decisions.compiler` and
:mod:`ariadne_engine.decisions.integrations` already use to decide without a model.
That derivation is honest in a way a downloaded checkpoint is not:

* it is reproducible from source that is already in the wheel;
* its provenance is stated exactly (``source`` names the tables, not a corpus);
* its probabilities are honestly labelled uncalibrated, because a rule match is not
  a probability and the engine reports ``PROVIDER_PROBABILITY``;
* it can be thrown away and replaced by a fitted or checkpoint-backed set without
  any other part of Ariadne noticing.

What it is *not*: evidence of model quality. These are not parameters learned from a
labelled corpus; they are features encoding rules the engine already knows. That
distinction is preserved in the weight file's ``source`` field and in the calibration
machinery, which only calls a probability calibrated when a measured profile says so.
Nothing here attempts to make a rule table look like a trained model.

Every training example below is written against the *real* projection field names
declared by :mod:`ariadne_engine.decisions.projections`. A seed keyed on invented
field names would produce features that never occur at inference time, which is
exactly the kind of plausible-but-wrong model this architecture exists to avoid.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping, Sequence

from ...contracts import (
    DECISION_CLASSIFIABLE_FAILURE_CLASSES,
    EVIDENCE_RELEVANCE_ANSWERS,
    REVIEW_ESCALATIONS,
    ROUTE_FAMILIES,
)
from .reference import (
    ENGINE_REVISION,
    WeightBook,
    answer_space,
    fit_family,
    question_identity,
    write_weights,
)

SEED_SOURCE = (
    "ariadne deterministic decision tables (ar-205d decision-intelligence answer-space "
    "vocabularies and projection contracts); rule-derived features, not a trained corpus"
)
"""Provenance string written into every seeded family. It says what this is and is not."""


def _question(
    *,
    question_id: str,
    primitive: str,
    contract: str,
    options: Sequence[str] | None = None,
    scale: Sequence[str] | None = None,
) -> dict[str, Any]:
    question: dict[str, Any] = {
        "question_id": question_id,
        "primitive": primitive,
        "projection_contract": contract,
        "definition_version": "1",
        "instructions": f"bounded {question_id} over the {contract} projection",
    }
    if primitive == "ChoiceDecision":
        question["options"] = list(options or ())
    elif primitive == "ScaleDecision":
        question["scale"] = list(scale or ())
    else:
        question["positive"] = "yes"
        question["negative"] = "no"
    return question


def _example(entries: Mapping[str, Any], label: str) -> tuple[dict, str]:
    return dict(entries), label


def _failure_examples() -> list[tuple[dict, str]]:
    """Failure classification, keyed on the ``failure-classification`` contract.

    ``failure`` is the REQUIRED field, so it is the primary evidence. The optional
    ``validator_outcome`` and ``environment`` fields appear on the examples where they
    are the deciding evidence, which teaches the engine to use them when present
    rather than to ignore them.
    """
    rows: list[tuple[str, str, dict[str, Any]]] = [
        ("IMPLEMENTATION_FAILURE", "Traceback (most recent call last): AssertionError in module formatter", {}),
        ("IMPLEMENTATION_FAILURE", "TypeError: undefined name 'render_page' while refactoring the parser", {}),
        ("IMPLEMENTATION_FAILURE", "SyntaxError: expected token at line 42 after the edit", {}),
        ("IMPLEMENTATION_FAILURE", "AttributeError: object of type None has no attribute render", {}),
        ("IMPLEMENTATION_FAILURE", "NameError is not defined in the new helper function", {"changed_scope": "src/engine/render.py"}),
        ("VALIDATION_FAILURE", "1 failed, 12 passed: expected True but got False", {}),
        ("VALIDATION_FAILURE", "pytest reported 2 failed tests in the contract suite", {"validator_outcome": "exit code 1"}),
        ("VALIDATION_FAILURE", "verification command failed: the rendered evidence does not match the requirement", {}),
        ("VALIDATION_FAILURE", "the acceptance check failed because the assertion in test_release.py did not hold", {"validator_outcome": "failed"}),
        ("TIMEOUT", "the operation timed out after 30 seconds", {}),
        ("TIMEOUT", "deadline exceeded while awaiting the response", {}),
        ("TIMEOUT", "hung waiting for the subprocess to return", {"environment": "cpu"}),
        ("ENVIRONMENT_FAILURE", "OSError: [Errno 13] permission denied on /etc/hosts", {}),
        ("ENVIRONMENT_FAILURE", "socket.gaierror: [Errno -2] name or service not known", {"environment": "network"}),
        ("ENVIRONMENT_FAILURE", "Connection refused connecting to the local service", {}),
        ("ENVIRONMENT_FAILURE", "no space left on device while writing the build", {}),
        ("PROVIDER_FAILURE", "the model provider returned 500 for this request", {}),
        ("PROVIDER_FAILURE", "rate limit exceeded calling the remote provider", {}),
        ("PROVIDER_FAILURE", "upstream provider authentication failed with 401", {}),
        ("PROVIDER_FAILURE", "provider quota exhausted for this api key", {}),
        ("CONTEXT_FAILURE", "required context missing: no projection entries were supplied", {}),
        ("CONTEXT_FAILURE", "insufficient state to answer the bounded question", {}),
        ("CONTEXT_FAILURE", "the referenced project file was not found in the run", {}),
        ("CONTEXT_FAILURE", "earlier conversation detail was truncated and lost", {}),
        ("UNKNOWN", "unclear cause, not identified", {}),
        ("UNKNOWN", "indeterminate: mixed signals, several plausible causes", {}),
        ("UNKNOWN", "cannot classify from the available evidence", {}),
        ("UNKNOWN", "ambiguous root cause across the failure log", {}),
    ]
    return [_example({"failure": failure, **extra}, label) for label, failure, extra in rows]


def _review_examples() -> list[tuple[dict, str]]:
    """Review escalation, keyed on the ``review-escalation`` contract."""
    rows: list[tuple[str, dict[str, Any]]] = [
        ("routine", {"stakes": "low", "affected_scope": "one file", "verification_result": "VERIFIED", "protected": False, "review_findings": []}),
        ("routine", {"stakes": "low", "affected_scope": "documentation only", "verification_result": "INDEPENDENTLY_REPRODUCED", "protected": False}),
        ("routine", {"stakes": "low", "affected_scope": "formatting", "verification_result": "VERIFIED", "protected": False}),
        ("independent_review", {"stakes": "medium", "affected_scope": "three modules", "verification_result": "OBSERVED", "protected": False, "review_findings": ["minor concern raised"]}),
        ("independent_review", {"stakes": "medium", "affected_scope": "public interface", "verification_result": "OBSERVED", "protected": False}),
        ("independent_review", {"stakes": "medium", "affected_scope": "shared helper", "verification_result": "REPRODUCED", "protected": False}),
        ("enhanced_review", {"stakes": "high", "affected_scope": "every route", "verification_result": "UNVERIFIED", "protected": False}),
        ("enhanced_review", {"stakes": "high", "affected_scope": "wide blast radius", "verification_result": "STALE", "protected": False}),
        ("enhanced_review", {"stakes": "high", "affected_scope": "core engine", "verification_result": "UNVERIFIED", "protected": False, "review_findings": ["design question raised"]}),
        ("human_attention", {"stakes": "high", "affected_scope": "release", "verification_result": "VERIFIED", "protected": True}),
        ("human_attention", {"stakes": "low", "affected_scope": "protected operation", "verification_result": "VERIFIED", "protected": True}),
        ("human_attention", {"stakes": "high", "affected_scope": "destructive deletion", "verification_result": "REPRODUCED", "protected": True}),
        ("human_attention", {"stakes": "medium", "affected_scope": "protected dependency change", "verification_result": "OBSERVED", "protected": True}),
    ]
    return [_example(entries, label) for label, entries in rows]


def _evidence_examples() -> list[tuple[dict, str]]:
    """Evidence relevance, keyed on the ``evidence-relevance`` contract."""
    rows: list[tuple[str, dict[str, Any]]] = [
        ("SUPPORTS", {"requirement": "the parser accepts a bare list", "evidence_claim": "list input parsed", "evidence_provenance": "engine-test", "freshness": "CURRENT"}),
        ("SUPPORTS", {"requirement": "the release notes name the version", "evidence_claim": "notes contain 2.0.0", "evidence_provenance": "artifact", "freshness": "CURRENT"}),
        ("SUPPORTS", {"requirement": "tests pass", "evidence_claim": "all green", "evidence_provenance": "verification", "freshness": "CURRENT"}),
        ("PARTIALLY_SUPPORTS", {"requirement": "the change is reversible", "evidence_claim": "mostly reversible", "evidence_provenance": "reviewer-note", "freshness": "CURRENT"}),
        ("PARTIALLY_SUPPORTS", {"requirement": "all consumers updated", "evidence_claim": "some consumers updated", "evidence_provenance": "incomplete", "freshness": "CURRENT"}),
        ("PARTIALLY_SUPPORTS", {"requirement": "the interface is stable", "evidence_claim": "signature unchanged in one place", "evidence_provenance": "partial", "freshness": "CURRENT"}),
        ("IRRELEVANT", {"requirement": "the parser accepts a bare list", "evidence_claim": "colour palette changed", "evidence_provenance": "design-note", "freshness": "CURRENT"}),
        ("IRRELEVANT", {"requirement": "tests pass", "evidence_claim": "the logo was redrawn", "evidence_provenance": "asset", "freshness": "CURRENT"}),
        ("IRRELEVANT", {"requirement": "the release is approved", "evidence_claim": "unrelated linter note", "evidence_provenance": "lint", "freshness": "CURRENT"}),
        ("CONTRADICTS", {"requirement": "the parser accepts a bare list", "evidence_claim": "bare list raised an error", "evidence_provenance": "engine-test", "freshness": "CURRENT"}),
        ("CONTRADICTS", {"requirement": "tests pass", "evidence_claim": "one test failed", "evidence_provenance": "verification", "freshness": "CURRENT"}),
        ("CONTRADICTS", {"requirement": "the release is approved", "evidence_claim": "approval was refused", "evidence_provenance": "human", "freshness": "CURRENT"}),
        ("UNKNOWN", {"requirement": "the parser behaves", "evidence_claim": "no claim recorded", "evidence_provenance": "none", "freshness": "CURRENT"}),
        ("UNKNOWN", {"requirement": "performance is acceptable", "evidence_claim": "not measured", "evidence_provenance": "absent", "freshness": "CURRENT"}),
        ("UNKNOWN", {"requirement": "the change is safe", "evidence_claim": "unclear", "evidence_provenance": "unknown", "freshness": "CURRENT"}),
        ("UNKNOWN", {"requirement": "the docs match", "evidence_claim": "cannot assess", "evidence_provenance": "missing", "freshness": "CURRENT"}),
    ]
    return [_example(entries, label) for label, entries in rows]


def _route_examples() -> list[tuple[dict, str]]:
    """Route family, keyed on the ``route-family`` contract."""
    rows: list[tuple[str, dict[str, Any]]] = [
        ("mechanical", {"task_kind": "edit", "difficulty": "trivial", "stakes": "low", "available_capabilities": ["file-edit"], "required_capabilities": ["file-edit"]}),
        ("mechanical", {"task_kind": "format", "difficulty": "trivial", "stakes": "low", "available_capabilities": ["file-edit"], "required_capabilities": ["file-edit"]}),
        ("mechanical", {"task_kind": "rename", "difficulty": "easy", "stakes": "low", "available_capabilities": ["file-edit"], "required_capabilities": ["file-edit"]}),
        ("implementation", {"task_kind": "feature", "difficulty": "moderate", "stakes": "medium", "available_capabilities": ["file-edit"], "required_capabilities": ["file-edit"]}),
        ("implementation", {"task_kind": "implementation", "difficulty": "moderate", "stakes": "medium", "available_capabilities": ["file-edit"], "required_capabilities": ["file-edit"]}),
        ("implementation", {"task_kind": "bugfix", "difficulty": "moderate", "stakes": "medium", "available_capabilities": ["file-edit"], "required_capabilities": ["file-edit"]}),
        ("design", {"task_kind": "design", "difficulty": "open", "stakes": "medium", "available_capabilities": ["render"], "required_capabilities": ["render"]}),
        ("design", {"task_kind": "design-direction", "difficulty": "open", "stakes": "medium", "available_capabilities": ["render"], "required_capabilities": ["render"]}),
        ("research", {"task_kind": "research", "difficulty": "open", "stakes": "low", "available_capabilities": ["references"], "required_capabilities": ["references"]}),
        ("research", {"task_kind": "investigation", "difficulty": "open", "stakes": "low", "available_capabilities": ["references"], "required_capabilities": ["references"]}),
        ("recovery", {"task_kind": "recovery", "difficulty": "moderate", "stakes": "high", "available_capabilities": ["file-edit"], "required_capabilities": ["file-edit"]}),
        ("recovery", {"task_kind": "repair", "difficulty": "moderate", "stakes": "high", "available_capabilities": ["file-edit"], "required_capabilities": ["file-edit"]}),
        ("recovery", {"task_kind": "debug", "difficulty": "moderate", "stakes": "medium", "available_capabilities": ["file-edit"], "required_capabilities": ["file-edit"]}),
        ("unknown", {"task_kind": "unclassified", "difficulty": "unknown", "stakes": "low", "available_capabilities": [], "required_capabilities": []}),
        ("unknown", {"task_kind": "ambiguous", "difficulty": "unknown", "stakes": "low", "available_capabilities": [], "required_capabilities": []}),
        ("unknown", {"task_kind": "misc", "difficulty": "unknown", "stakes": "low", "available_capabilities": [], "required_capabilities": []}),
    ]
    return [_example(entries, label) for label, entries in rows]


def seed_families() -> dict[str, tuple[dict[str, Any], list[tuple[dict, str]]]]:
    """Build the seeded question families and their training examples.

    Each family mirrors one real Ariadne integration, so the answer space the runtime
    is asked to fill is exactly the space
    :mod:`ariadne_engine.decisions.integrations` already publishes. The question ids
    and contracts match, which means the family digest matches what the integration
    will actually ask.
    """
    failure = _question(
        question_id="failure-class",
        primitive="ChoiceDecision",
        contract="failure-classification",
        options=DECISION_CLASSIFIABLE_FAILURE_CLASSES,
    )
    review = _question(
        question_id="review-escalation",
        primitive="ChoiceDecision",
        contract="review-escalation",
        options=REVIEW_ESCALATIONS,
    )
    evidence = _question(
        question_id="evidence-relevance",
        primitive="ChoiceDecision",
        contract="evidence-relevance",
        options=EVIDENCE_RELEVANCE_ANSWERS,
    )
    route = _question(
        question_id="route-family",
        primitive="ChoiceDecision",
        contract="route-family",
        options=ROUTE_FAMILIES,
    )
    return {
        question_identity(failure): (failure, _failure_examples()),
        question_identity(review): (review, _review_examples()),
        question_identity(evidence): (evidence, _evidence_examples()),
        question_identity(route): (route, _route_examples()),
    }


def build_seed_book() -> WeightBook:
    """Fit the seed weight book from the derived families."""
    families: dict[str, Any] = {}
    for family, (question, examples) in seed_families().items():
        families[family] = fit_family(
            family=family,
            labels=answer_space(question),
            examples=examples,
            source=SEED_SOURCE,
        )
    return WeightBook(engine_revision=ENGINE_REVISION, source=SEED_SOURCE, families=families)


def install_seeds(root: Path) -> dict:
    """Write the seed weight file and manifest into a runtime installation.

    This is the whole of the reference runtime's install step: no download, no
    network, no dependency. It makes bounded local inference genuinely available on
    a fresh install, which is the point.
    """
    from .manifest import default_manifest, write_manifest

    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    book = build_seed_book()
    weights_path = write_weights(root / "weights.json", book.families, source=SEED_SOURCE)
    manifest = default_manifest(
        runtime_version="1.0.0",
        implementation="ariadne-reference-bounded",
        implementation_revision=ENGINE_REVISION,
        model="ariadne-reference-bounded",
        model_revision=ENGINE_REVISION,
        primitives=("BinaryDecision", "ChoiceDecision", "ScaleDecision"),
        languages=("en",),
    )
    manifest["source"] = SEED_SOURCE
    manifest_path = write_manifest(root / "runtime-manifest.json", manifest)
    return {
        "root": str(root),
        "weights": str(weights_path),
        "manifest": str(manifest_path),
        "families": len(book.families),
        "samples": sum(weights.samples for weights in book.families.values()),
        "source": SEED_SOURCE,
    }


def describe_seed() -> dict:
    """A description of what the reference runtime can answer, for diagnostics."""
    book = build_seed_book()
    return {
        "implementation": "ariadne-reference-bounded",
        "engine_revision": ENGINE_REVISION,
        "source": SEED_SOURCE,
        "families": book.summary()["families"],
        "samples": book.summary()["samples"],
        "note": "rule-derived features; probabilities are uncalibrated by construction",
    }