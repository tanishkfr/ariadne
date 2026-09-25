"""Decision primitives, question definitions and the decision record shape.

A bounded decision is a question whose answer space is closed and declared before
the provider is asked:

* ``BinaryDecision``     one of two declared answers (default yes/no)
* ``ChoiceDecision``     exactly one of a declared option set
* ``ScaleDecision``      one declared ordinal step (an ordered scale)
* ``MultiSelectDecision`` one or more of a declared option set, bounded by a maximum

Each primitive defines the question id, the instructions, the allowed answer
space, the digest of the projected state the provider saw, and (on the answer)
the provider, model, raw answer, normalised answer, confidence and the kind of
that confidence.

Type validity is not correctness: an answer inside the allowed space can still be
wrong, which is why a decision record is evidence of *what judgement was
produced*, never proof that the resulting side effect happened or that it was
authorized.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

from ..contracts import (
    CONFIDENCE_KINDS,
    DECISION_CONSEQUENCES,
    DECISION_PRIMITIVES,
    ContractError,
)

QUESTION_ID_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,79}")


def state_digest(value: Any) -> str:
    """A stable digest of the projected state one decision was made against."""
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class DecisionQuestion:
    """One bounded question. The allowed space is declared, never inferred."""

    question_id: str
    instructions: str
    primitive: str = "ChoiceDecision"
    options: tuple[str, ...] = ()
    scale: tuple[str, ...] = ()
    positive: str = "yes"
    negative: str = "no"
    max_selections: int = 1
    consequence: str = "LOW"
    definition_version: str = "1"
    evidence_digest: str = ""
    projection_contract: str = ""
    """The declared projection contract this question's state must satisfy.

    AR-205D: a bounded question carries the name of the state projection it
    needs, so the planner can group questions that share one projected state
    and refuse a question whose state was never declared.
    """

    def __post_init__(self) -> None:
        if not QUESTION_ID_PATTERN.fullmatch(str(self.question_id or "")):
            raise ContractError(f"decision question id is malformed: {self.question_id!r}")
        if not str(self.instructions or "").strip():
            raise ContractError(f"decision question {self.question_id} has no instructions")
        if self.primitive not in DECISION_PRIMITIVES:
            raise ContractError(f"unsupported decision primitive: {self.primitive!r}")
        if self.consequence not in DECISION_CONSEQUENCES:
            raise ContractError(f"unsupported decision consequence: {self.consequence!r}")
        if self.primitive == "ChoiceDecision" and len(self.options) < 2:
            raise ContractError(f"a choice decision needs at least two declared options: {self.question_id}")
        if self.primitive == "ScaleDecision" and len(self.scale) < 2:
            raise ContractError(f"a scale decision needs an ordered scale with at least two steps: {self.question_id}")
        if self.primitive == "MultiSelectDecision":
            if len(self.options) < 2:
                raise ContractError(f"a multi-select decision needs at least two declared options: {self.question_id}")
            if not 1 <= int(self.max_selections) <= len(self.options):
                raise ContractError(
                    f"a multi-select decision needs a maximum between 1 and {len(self.options)}: {self.question_id}"
                )
        if self.primitive == "BinaryDecision" and str(self.positive) == str(self.negative):
            raise ContractError(f"a binary decision needs two distinct answers: {self.question_id}")

    @property
    def allowed(self) -> tuple[str, ...]:
        if self.primitive == "BinaryDecision":
            return (str(self.positive), str(self.negative))
        if self.primitive == "ScaleDecision":
            return tuple(str(item) for item in self.scale)
        return tuple(str(item) for item in self.options)

    def as_record(self) -> dict:
        return {
            "question_id": str(self.question_id),
            "instructions": str(self.instructions),
            "primitive": str(self.primitive),
            "options": list(self.allowed),
            "scale": list(self.scale),
            "max_selections": int(self.max_selections),
            "consequence": str(self.consequence),
            "definition_version": str(self.definition_version),
            "evidence_digest": str(self.evidence_digest),
            "projection_contract": str(self.projection_contract),
            "allowed": list(self.allowed),
        }


def validate_answer(question: DecisionQuestion, raw: Any) -> tuple[list[str], list[str]]:
    """Validate one answer against the question's declared space.

    Returns ``(normalised_answers, problems)``. A value outside the space is
    reported as a problem; it is never coerced into a nearby allowed answer.
    """
    problems: list[str] = []
    if raw is None:
        return [], ["the provider returned no answer"]
    values: list[str] = []
    if isinstance(raw, (list, tuple)):
        values = [str(item).strip() for item in raw]
    else:
        text = str(raw).strip()
        values = [text] if text else []
    values = [value for value in values if value]
    if not values:
        return [], ["the provider returned an empty answer"]
    allowed = list(question.allowed)
    if question.primitive == "MultiSelectDecision":
        unknown = [value for value in values if value not in allowed]
        if unknown:
            problems.append("answer outside the declared option set: " + ", ".join(sorted(set(unknown))))
        if len(set(values)) > int(question.max_selections):
            problems.append(
                f"the answer selects {len(set(values))} options; at most {question.max_selections} are allowed"
            )
        return sorted(set(values)), problems
    if len(values) != 1:
        problems.append("the answer must be exactly one value for this primitive")
        return values, problems
    if values[0] not in allowed:
        problems.append("answer outside the declared option set: " + values[0])
    return values, problems


@dataclass(frozen=True)
class DecisionAnswer:
    """One provider answer, validated against its question."""

    question_id: str
    raw: Any
    answers: tuple[str, ...]
    valid: bool
    confidence: float | None = None
    confidence_kind: str = "NONE"
    distribution: Mapping[str, float] = field(default_factory=dict)
    problems: tuple[str, ...] = ()

    def as_record(self) -> dict:
        return {
            "question_id": str(self.question_id),
            "raw": self.raw,
            "answer": ", ".join(self.answers),
            "answers": list(self.answers),
            "answer_valid": bool(self.valid),
            "confidence": self.confidence,
            "confidence_kind": str(self.confidence_kind),
            "distribution": dict(self.distribution),
            "problems": list(self.problems),
        }


def answer_from_provider(question: DecisionQuestion, value: Mapping | Any) -> DecisionAnswer:
    """Build one validated answer from a provider's raw payload.

    The confidence kind is preserved exactly as the provider declared it. A
    missing kind becomes ``NONE``; a self-reported number stays
    ``SELF_REPORTED_CONFIDENCE`` and is never promoted.
    """
    problems: list[str] = []
    payload = value if isinstance(value, Mapping) else {"answer": value}
    raw = payload.get("answer", payload.get("answers"))
    answers, validation_problems = validate_answer(question, raw)
    problems.extend(validation_problems)
    confidence_value = payload.get("confidence")
    confidence: float | None = None
    if confidence_value is not None:
        try:
            confidence = float(confidence_value)
        except (TypeError, ValueError):
            problems.append("the provider returned a confidence that is not a number")
            confidence = None
        else:
            if not 0.0 <= confidence <= 1.0:
                problems.append("the provider returned a confidence outside [0, 1]")
                confidence = None
    kind = str(payload.get("confidence_kind", "") or "").strip() or ("NONE" if confidence is None else "SELF_REPORTED_CONFIDENCE")
    if kind not in CONFIDENCE_KINDS:
        problems.append(f"unknown confidence kind: {kind!r}")
        kind = "NONE"
    if kind == "NONE" and confidence is not None:
        problems.append("a confidence value must declare where it came from")
    if confidence is None:
        kind = "NONE"
    distribution: dict[str, float] = {}
    raw_distribution = payload.get("distribution")
    if isinstance(raw_distribution, Mapping):
        for key, item in raw_distribution.items():
            try:
                distribution[str(key)] = float(item)
            except (TypeError, ValueError):
                problems.append(f"distribution entry {key!r} is not a number")
    return DecisionAnswer(
        question_id=str(question.question_id),
        raw=raw,
        answers=tuple(answers),
        valid=not problems,
        confidence=confidence,
        confidence_kind=kind,
        distribution=distribution,
        problems=tuple(problems),
    )


def batch_digest(questions: Sequence[DecisionQuestion], projection_digest: str) -> str:
    """Digest over the questions and the projected state of one batch."""
    payload = {
        "projection": str(projection_digest),
        "questions": [question.as_record() for question in questions],
    }
    return state_digest(payload)


__all__ = [
    "QUESTION_ID_PATTERN",
    "state_digest",
    "DecisionQuestion",
    "validate_answer",
    "DecisionAnswer",
    "answer_from_provider",
    "batch_digest",
]
