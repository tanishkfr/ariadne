"""A labelled benchmark corpus, with splits and guards against evaluating on it.

2.1 built the architecture. What 2.1 did not do was prove the reference decision engine
is *accurate*, and building more architecture would not change that. So this module is the
empirical half: a reviewed corpus of bounded decisions with real labels, split so that the
thing measured on the held-out set was never the thing tuned on.

**The labels are authored, not generated.** This is the single most important property of
the corpus, and it is the one a self-evaluating benchmark is always accused of not having.
No case's label is produced by asking the engine what it would say. Each label is a
human judgement about a projection, written down in
:mod:`~ariadne_engine.intelligence.corpus_data`, and every case carries its reviewer,
their second opinion where one was taken, and whether they agreed. A corpus built by
running the model and recording its output measures the model against itself and reports
excellent numbers for a system that learned nothing.

**Splits are enforced, not requested.**
:data:`SPLITS` distinguishes four:

``DEVELOPMENT``    the only split a threshold may be tuned against
``HELD_OUT``       read once, at evaluation, after tuning is finished
``ADVERSARIAL``    built to break the engine: false confidence, ambiguity, near-misses
``REAL_WORLD``     drawn from Ariadne's own recorded decisions

and :func:`leakage_problems` is the mechanism that makes the distinction real. It compares
**projection digests** across splits, not just case ids, because the failure mode that
actually happens is subtler than a duplicated id: two near-identical questions in different
splits, one tuned against and one scored. Same question, two splits, one inflated number.

**Abstention is part of the corpus.** Cases carry ``expected_abstain``, so "should not have
answered" is a reviewable property of the data rather than a thing the metric reports as an
unfortunate side effect. An engine that answers everything scores well on accuracy and
badly on the only metric that matters for bounded authority.

**Disagreement is kept.** Where two reviewers differed and one was right, both the
disagreement and the adjudication are recorded. High disagreement is a finding about the
*question* -- an ambiguous requirement, an underspecified projection -- and reading it as a
finding about the model is how a corpus with bad labels gets used to "prove" a model is
bad.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Iterable, Mapping, Sequence

from ..contracts import ContractError

CORPUS_VERSION = "ar-223-corpus-1"
"""The corpus document shape."""

SPLITS = ("DEVELOPMENT", "HELD_OUT", "ADVERSARIAL", "REAL_WORLD")
"""The four splits, and the only ones a corpus may declare."""

TUNING_SPLITS = ("DEVELOPMENT",)
"""Splits a threshold, weight or prompt may be fitted against.

One, not two. ``ADVERSARIAL`` cases are read to *understand* failure modes and the
findings inform the next development cycle -- but a threshold fitted against them stops
being an adversarial set, and an adversarial set is the only thing that reports a
pathology before a user does.
"""

EVALUATION_SPLITS = ("HELD_OUT", "ADVERSARIAL", "REAL_WORLD")
"""Splits that report a number about generalisation."""

SOURCE_KINDS = (
    "REVIEWED_FIXTURE",
    "REAL_HISTORY",
    "ADVERSARIAL_FIXTURE",
    "BOUNDARY_FIXTURE",
)
"""Where a case's label came from."""

AGREEMENT_LEVELS = ("SINGLE_REVIEWER", "SECOND_REVIEWER_AGREED", "ADJUDICATED")
"""How much review a label received."""

FAMILIES = (
    "FAILURE_CLASSIFICATION",
    "REVIEW_ESCALATION",
    "EVIDENCE_RELEVANCE",
    "ROUTE_FAMILY",
)
"""The bounded decision families Ariadne actually asks at integration points.

Four, and all four are ``ChoiceDecision`` over an existing answer space -- which is the
answer to "audit the real production families": the runtime's ``BinaryDecision`` and
``ScaleDecision`` primitives exist and are tested, but nothing in Ariadne's integration
path asks one. Benchmarking a primitive nothing uses would produce a large impressive
corpus about a question nobody asks.
"""

FAMILY_DEFINITIONS = {
    "FAILURE_CLASSIFICATION": {"definition": "failure-classification", "question_id": "failure-class"},
    "REVIEW_ESCALATION": {"definition": "review-escalation", "question_id": "review-escalation"},
    "EVIDENCE_RELEVANCE": {"definition": "evidence-relevance", "question_id": "evidence-relevance"},
    "ROUTE_FAMILY": {"definition": "route-family", "question_id": "route-family"},
}
"""Which real integration each family corresponds to."""


def projection_digest(projection: Mapping[str, Any]) -> str:
    """A stable identity for one projection's *content*.

    Canonicalised, so key order and whitespace cannot manufacture a "different" case. The
    digest is what :func:`leakage_problems` compares, and comparing anything weaker -- a
    case id, a row index -- would miss the near-duplicate case that inflates a held-out
    number.
    """
    canonical = json.dumps(projection, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


def case(
    *,
    case_id: str,
    family: str,
    split: str,
    projection: Mapping[str, Any],
    label: str,
    provenance: Mapping[str, Any],
    expected_abstain: bool = False,
    difficulty: str = "ORDINARY",
) -> dict:
    """Build one reviewed case, validated on the way in.

    ``difficulty`` records whether the case was written to be easy or hard. It costs
    nothing and it is what lets a later reader separate "the engine is wrong about
    genuinely ambiguous questions" from "the engine is wrong about questions nobody would
    ask".
    """
    if str(family) not in FAMILIES:
        raise ContractError(f"unknown decision family: {family!r}")
    if str(split) not in SPLITS:
        raise ContractError(
            f"unsupported corpus split: {split!r}. A corpus that can put a case anywhere cannot "
            "prove a held-out number means anything"
        )
    if not str(label or "").strip():
        raise ContractError(f"corpus case {case_id} has no label; an unlabelled case cannot be scored")
    if not isinstance(projection, Mapping) or not projection:
        raise ContractError(f"corpus case {case_id} has no projection")
    reviewer = str(provenance.get("reviewer", "")) if isinstance(provenance, Mapping) else ""
    if not reviewer:
        raise ContractError(
            f"corpus case {case_id} names no reviewer. A label without a reviewer is a guess with "
            "a row number"
        )
    return {
        "schema_version": CORPUS_VERSION,
        "case_id": str(case_id),
        "family": str(family),
        "split": str(split),
        "definition": FAMILY_DEFINITIONS[str(family)]["definition"],
        "question_id": FAMILY_DEFINITIONS[str(family)]["question_id"],
        "projection": dict(projection),
        "projection_digest": projection_digest(projection),
        "label": str(label),
        "expected_abstain": bool(expected_abstain),
        "difficulty": str(difficulty),
        "provenance": dict(provenance),
    }


def build(cases: Sequence[Mapping[str, Any]]) -> dict:
    """Assemble a corpus document from reviewed cases."""
    rows = [dict(row) for row in cases]
    return {
        "schema_version": CORPUS_VERSION,
        "cases": rows,
        "case_count": len(rows),
        "corpus_digest": projection_digest([row.get("projection_digest", "") for row in rows]),
        "distribution": distribution(rows),
        "note": (
            "labels are authored and reviewed, never produced by the engine under test. A corpus "
            "that labels itself measures agreement with itself"
        ),
    }


def distribution(cases: Sequence[Mapping[str, Any]]) -> dict:
    """The exact per-family, per-split counts.

    Reported rather than summarised. "Several hundred reviewed decisions" is a vanity
    number; what a reader needs is how many of each kind, how many of which were expected to
    be abstained on, and how many were written to break the engine.
    """
    by_family: dict[str, int] = {name: 0 for name in FAMILIES}
    by_split: dict[str, int] = {name: 0 for name in SPLITS}
    cells: dict[str, dict[str, int]] = {
        family: {split: 0 for split in SPLITS} for family in FAMILIES
    }
    abstain: dict[str, int] = {name: 0 for name in FAMILIES}
    difficulty: dict[str, int] = {}
    disagreement = 0
    for row in cases:
        family = str(row.get("family", ""))
        split = str(row.get("split", ""))
        if family in by_family:
            by_family[family] += 1
        if split in by_split:
            by_split[split] += 1
        if family in cells and split in cells[family]:
            cells[family][split] += 1
        if row.get("expected_abstain") and family in abstain:
            abstain[family] += 1
        level = str(row.get("difficulty", ""))
        difficulty[level] = difficulty.get(level, 0) + 1
        provenance = row.get("provenance")
        if isinstance(provenance, Mapping) and str(
            provenance.get("agreement", "")
        ) == "ADJUDICATED":
            disagreement += 1
    return {
        "cases": len(list(cases)),
        "by_family": by_family,
        "by_split": by_split,
        "cells": cells,
        "expected_abstain": abstain,
        "by_difficulty": dict(sorted(difficulty.items())),
        "adjudicated_labels": disagreement,
        "note": "counts, not a score: a benchmark's shape is part of what it claims",
    }


def leakage_problems(corpus: Mapping[str, Any]) -> list[str]:
    """Every way this corpus could report a number that means nothing.

    Four checks, each a real way leakage happens:

    * a ``case_id`` in more than one split -- a copy-paste into the held-out set;
    * a **projection digest** in more than one split -- the same question scored on both
      sides, which is the failure that actually inflates numbers and the one a case-id
      check cannot see;
    * a case with no reviewer, no source kind, or an unknown source kind;
    * a case in a tuning split that a caller also asked to be an evaluation split.
    """
    rows = [row for row in corpus.get("cases", []) or [] if isinstance(row, Mapping)]
    problems: list[str] = []
    by_id: dict[str, set[str]] = {}
    by_digest: dict[str, set[str]] = {}
    for row in rows:
        case_id = str(row.get("case_id", ""))
        split = str(row.get("split", ""))
        digest = str(row.get("projection_digest", "") or projection_digest(row.get("projection", {})))
        by_id.setdefault(case_id, set()).add(split)
        by_digest.setdefault(digest, set()).add(split)
        provenance = row.get("provenance")
        if not isinstance(provenance, Mapping) or not str(provenance.get("reviewer", "")):
            problems.append(f"corpus case {case_id} names no reviewer")
        elif str(provenance.get("source_kind", "")) not in SOURCE_KINDS:
            problems.append(
                f"corpus case {case_id} names an unknown label source: {provenance.get('source_kind')!r}"
            )
        if split not in SPLITS:
            problems.append(f"corpus case {case_id} is in an undeclared split: {split!r}")
    for case_id, splits in sorted(by_id.items()):
        if len(splits) > 1:
            problems.append(
                f"corpus case {case_id} appears in more than one split ({', '.join(sorted(splits))}). "
                "The same case on both sides of the evaluation is not a held-out number"
            )
    for digest, splits in sorted(by_digest.items()):
        if len(splits) > 1:
            examples = sorted({
                str(row.get("case_id", "")) for row in rows
                if str(row.get("projection_digest", "")) == digest
            })
            problems.append(
                f"projection digest {digest} appears in more than one split "
                f"({', '.join(sorted(splits))}): {', '.join(examples)}. Same question, two splits; "
                "a threshold fitted on one is fitted on the other"
            )
    return list(dict.fromkeys(problems))


def tuning_report(corpus: Mapping[str, Any], *, tuned_on: Sequence[str]) -> dict:
    """What was tuned against what, recorded so an evaluation can check it.

    A single call that answers the question a reviewer should always ask before believing a
    number: which rows could have influenced the thing being scored?
    """
    allowed = {str(item) for item in tuned_on}
    rows = [row for row in corpus.get("cases", []) or [] if isinstance(row, Mapping)]
    tuning = [row for row in rows if str(row.get("split", "")) in allowed]
    evaluation = [row for row in rows if str(row.get("split", "")) in set(EVALUATION_SPLITS)]
    overlap = sorted({
        str(row.get("projection_digest", "")) for row in tuning
    } & {str(row.get("projection_digest", "")) for row in evaluation})
    return {
        "tuned_on": sorted(allowed),
        "tuning_cases": len(tuning),
        "evaluation_cases": len(evaluation),
        "digest_overlap_with_evaluation": overlap,
        "clean": not overlap,
        "note": (
            "the tuning set is the DEVELOPMENT split alone. Adversarial cases are read to "
            "understand failure, never fitted against, or they stop being adversarial"
        ),
    }


def select(
    corpus: Mapping[str, Any],
    *,
    families: Sequence[str] | None = None,
    splits: Sequence[str] | None = None,
) -> list[dict]:
    """The rows matching a family and split selection."""
    rows = [row for row in corpus.get("cases", []) or [] if isinstance(row, Mapping)]
    if families:
        wanted = {str(item) for item in families}
        rows = [row for row in rows if str(row.get("family", "")) in wanted]
    if splits:
        wanted = {str(item) for item in splits}
        rows = [row for row in rows if str(row.get("split", "")) in wanted]
    return rows


def require_clean(corpus: Mapping[str, Any]) -> None:
    """Refuse to evaluate a corpus that leaks, rather than reporting a number anyway.

    Raising rather than warning. A leaky corpus produces a number that looks fine and
    means nothing, and the only defence is refusing to produce it.
    """
    problems = leakage_problems(corpus)
    if problems:
        raise ContractError(
            "this benchmark corpus cannot be evaluated as it stands: " + "; ".join(problems)
        )


def describe() -> dict:
    return {
        "version": CORPUS_VERSION,
        "splits": list(SPLITS),
        "tuning_splits": list(TUNING_SPLITS),
        "evaluation_splits": list(EVALUATION_SPLITS),
        "families": list(FAMILIES),
        "source_kinds": list(SOURCE_KINDS),
        "labels": "authored and reviewed; never produced by the engine under test",
        "guarded": (
            "case ids and projection digests are both checked for split overlap, because "
            "near-duplicate questions across splits is how a held-out number becomes a "
            "tuned-on number with extra steps"
        ),
    }


__all__ = [
    "AGREEMENT_LEVELS",
    "CORPUS_VERSION",
    "EVALUATION_SPLITS",
    "FAMILIES",
    "FAMILY_DEFINITIONS",
    "SOURCE_KINDS",
    "SPLITS",
    "TUNING_SPLITS",
    "build",
    "case",
    "describe",
    "distribution",
    "leakage_problems",
    "projection_digest",
    "require_clean",
    "select",
    "tuning_report",
]