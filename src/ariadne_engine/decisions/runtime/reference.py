"""The reference bounded engine: a small, real, local probabilistic classifier.

This is what makes "baked in" true. It answers bounded questions on the user's
machine with no download, no network, no third-party dependency and no model file,
and it does so in microseconds — because it is not a neural network. It is a
multinomial naive-Bayes log-odds scorer over features of the projected state.

Being honest about what that means:

* Its probabilities are **not calibrated**. Naive Bayes with correlated features is
  systematically overconfident, and no amount of rescaling makes it a statement
  about how often it is right. So the engine reports them as
  ``PROVIDER_PROBABILITY`` and refuses to call them anything else. Calibrated
  probability is a licence a measured :class:`~ariadne_engine.decisions.runtime.profiles.CalibrationProfile`
  grants, and this engine does not grant it to itself.
* It is weak on long, subtle text and strong on enumerated structure. That matches
  the decision families Ariadne actually asks it about, which are mostly closed
  vocabularies over small structured projections.
* It refuses rather than guesses. No weights for a question means ``NO_LOCAL_MODEL``
  and an abstention, which Ariadne escalates. An untrained runtime is an escalation,
  never a plausible default.

Weights are bound to a *question identity*, not to a label set in the abstract: the
family key is a digest over the contract, question id, primitive, the ordered answer
space and the definition version. Change the option set and the weights no longer
apply. That is the same rule Ariadne already applies to the decision cache, applied
to the thing that produces the decision.

The engine is torch-free on purpose. Anything heavier belongs in the sidecar as a
separate implementation; this one has to work in a bare Python.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from ...contracts import RUNTIME_PRIMITIVE_MAPPINGS, UNSUPPORTED_PRIMITIVE

ENGINE_NAME = "ariadne-reference-bounded"
"""The implementation name recorded in provenance. It describes the engine, not a vendor."""

ENGINE_REVISION = "ar-206-reference-1"
"""Bumped whenever scoring behaviour changes. Bound into every weight file."""

WEIGHTS_SCHEMA = "ariadne-reference-bounded-weights/1"
"""The weight-file document shape."""

ENGINE_VERSION = "1.0.0"
"""The reference engine's own version, independent of Ariadne's."""

SUPPORTED_PRIMITIVES = tuple(RUNTIME_PRIMITIVE_MAPPINGS)
"""BinaryDecision, ChoiceDecision, ScaleDecision. MultiSelectDecision is absent on
purpose: the engine scores one closed label, and scoring options independently would
report a confidence for a combination that was never evaluated."""

ADD_K = 1.0
"""Additive smoothing for unseen features. Smoothed, never zeroed, so an unseen token
lowers a probability instead of forbidding it."""

MAX_FEATURES_PER_ITEM = 4_000
"""Per-item feature bound. A projection that explodes into thousands of tokens is
refused rather than silently truncated — a truncated score is a score about part of
the state, presented as if it were the whole."""

MAX_LABELS = 32
"""Answer-space bound, matching the schema compiler's ``MAX_OPTIONS``."""

_TOKEN = re.compile(r"[A-Za-z0-9_]+")
_WS = re.compile(r"\s+")


class EngineError(RuntimeError):
    """The engine could not score. Raised, never answered."""


# --------------------------------------------------------------- question identity


def question_identity(question: Mapping[str, Any]) -> str:
    """The digest a weight file must be filed under.

    Covers the contract, question id, primitive, the ordered answer space and the
    definition version. Option *order* is part of the key: an ordered answer space is
    positional, and reordering it is a different question.

    The *instructions* are deliberately not part of it. A weight file records how the
    family performs over an answer space, not how one phrasing happened to read, so
    rewording a question keeps its weights. Wording that changes the decision belongs to
    a different ``definition_version`` or a different ``projection_contract``, and both
    of those are in the key. Calibration is where wording is policed instead: a profile
    binds a ``question_schema_digest`` *and* a ``decision_definition_digest``, the latter
    covering the instructions.
    """
    payload = {
        "contract": str(question.get("projection_contract", "")),
        "question_id": str(question.get("question_id", "")),
        "primitive": str(question.get("primitive", "")),
        "allowed": [str(item) for item in answer_space(question)],
        "definition_version": str(question.get("definition_version", "1")),
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def answer_space(question: Mapping[str, Any]) -> tuple[str, ...]:
    """The declared closed answer space, derived the same way the engine derives it.

    A question's answer space has four encodings in circulation — ``allowed``,
    ``options``, ``scale`` and the ``positive``/``negative`` pair — and only one of
    them is populated for a given primitive. :meth:`DecisionQuestion.as_record`
    flattens every primitive into ``allowed`` *and* ``options``, and empties ``scale``
    and drops the positive/negative pair entirely, so a record-form question read
    through the primitive-specific fields would come out empty for a scale and
    ``("yes", "no")`` for a binary regardless of the pair it actually declared.

    The order below is therefore: the canonical ``allowed`` list, then whichever
    encoding this particular question actually carries. It reads the same space for
    every producer of a question record, which is what keeps a fitted weight file
    matching the question it was fitted for.
    """
    for field in ("allowed", "options", "scale"):
        space = tuple(str(item) for item in question.get(field, ()) or ())
        if space:
            return space
    if str(question.get("primitive", "")) == "BinaryDecision":
        return (str(question.get("positive", "yes")), str(question.get("negative", "no")))
    return ()


def unsupported_primitive(primitive: str) -> bool:
    """Whether this engine cannot represent a primitive faithfully."""
    return str(primitive) not in SUPPORTED_PRIMITIVES


# --------------------------------------------------------------------- features


def _normalise_scalar(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        number = float(value)
        if not math.isfinite(number):
            # nan and inf are not magnitudes. Left alone, math.log10(nan) raises and
            # math.log10(0) divides by zero, and because the engine converts features to
            # integer bins that turns one bad value in a projection into a failure for
            # every question asked of that state rather than for the one that had it.
            return "~nonfinite"
        if number.is_integer() and abs(number) < 1e15:
            return str(int(number))
        # A continuous value contributes its order of magnitude, not its exact
        # digits: an exact-value feature would never recur and would only add noise.
        magnitude = int(math.floor(math.log10(abs(number)))) if number else 0
        return f"~1e{magnitude}"
    text = _WS.sub(" ", str(value)).strip()
    return text


def features_for(entries: Mapping[str, Any]) -> list[str]:
    """Deterministic feature tokens for one projected state.

    Structure and text are both reduced to the same token space so a weight table
    never has to know which kind of field it was fitted on. Field name is always part
    of the token, because ``stakes=high`` and ``scope=high`` are different evidence.
    """
    tokens: list[str] = []
    for key in sorted(str(name) for name in entries):
        raw_key = next(name for name in entries if str(name) == key)
        tokens.append(f"f={key}")
        value = entries[raw_key]
        if isinstance(value, Mapping):
            for inner in sorted(str(name) for name in value):
                inner_raw = next(name for name in value if str(name) == inner)
                tokens.append(f"f={key}.{inner}")
                tokens.append(f"f={key}.{inner}={_normalise_scalar(value[inner_raw])}")
            continue
        if isinstance(value, (list, tuple)):
            tokens.append(f"f={key}=list{len(value)}")
            for item in list(value)[:16]:
                tokens.append(f"f={key}~{_normalise_scalar(item)}")
            continue
        tokens.append(f"f={key}={_normalise_scalar(value)}")
        if isinstance(value, str):
            for word in _TOKEN.findall(value.lower())[:512]:
                tokens.append(f"w={key}:{word}")
    if len(tokens) > MAX_FEATURES_PER_ITEM:
        raise EngineError(
            f"the projected state expands to {len(tokens)} features, above the bound of {MAX_FEATURES_PER_ITEM}"
        )
    return tokens


# ----------------------------------------------------------------------- weights


@dataclass(frozen=True)
class FamilyWeights:
    """Weights for exactly one question identity."""

    family: str
    labels: tuple[str, ...]
    label_prior: tuple[float, ...]
    feature_weights: Mapping[str, tuple[float, ...]]
    samples: int
    source: str

    def weights_problems(self) -> list[str]:
        problems: list[str] = []
        if not self.labels:
            problems.append("a weight family declares no labels")
        if len(self.labels) > MAX_LABELS:
            problems.append(f"a weight family declares {len(self.labels)} labels, above the bound of {MAX_LABELS}")
        if len(self.label_prior) != len(self.labels):
            problems.append("a weight family's label prior does not match its labels")
        for feature, vector in self.feature_weights.items():
            if len(vector) != len(self.labels):
                problems.append(f"feature {feature!r} does not have one weight per label")
                break
        if self.samples < 0:
            problems.append("a weight family declares a negative sample count")
        return problems


@dataclass
class WeightBook:
    """Every family this runtime installation can answer."""

    engine_revision: str
    source: str
    families: dict[str, FamilyWeights] = field(default_factory=dict)

    @property
    def questions(self) -> tuple[str, ...]:
        return tuple(sorted(self.families))

    def get(self, family: str) -> FamilyWeights | None:
        return self.families.get(str(family))

    def summary(self) -> dict:
        return {
            "engine_revision": self.engine_revision,
            "source": self.source,
            "families": len(self.families),
            "questions": list(self.questions),
            "samples": sum(weights.samples for weights in self.families.values()),
        }


def empty_book(source: str = "no weights") -> WeightBook:
    return WeightBook(engine_revision=ENGINE_REVISION, source=str(source), families={})


def weights_problems(book: Mapping[str, Any]) -> list[str]:
    """Structural validation of a weight file. Fail closed."""
    problems: list[str] = []
    if not isinstance(book, Mapping):
        return ["weight file is not an object"]
    if str(book.get("schema", "")) != WEIGHTS_SCHEMA:
        problems.append(f"weight file schema is unsupported: {book.get('schema')!r}")
    if str(book.get("engine_revision", "")) != ENGINE_REVISION:
        problems.append(
            f"weight file targets engine revision {book.get('engine_revision')!r}, not {ENGINE_REVISION!r}"
        )
    if not str(book.get("source", "")).strip():
        problems.append("weight file names no source")
    families = book.get("families")
    if not isinstance(families, Mapping):
        problems.append("weight file families are not an object")
        return problems
    for family, block in families.items():
        if not isinstance(block, Mapping):
            problems.append(f"weight family {family!r} is not an object")
            continue
        labels = block.get("labels")
        if not isinstance(labels, (list, tuple)) or not labels:
            problems.append(f"weight family {family!r} declares no labels")
            continue
        if len(labels) > MAX_LABELS:
            problems.append(f"weight family {family!r} exceeds the {MAX_LABELS}-label bound")
        width = len(labels)
        prior = block.get("label_prior")
        if not isinstance(prior, (list, tuple)) or len(prior) != width:
            problems.append(f"weight family {family!r} label prior does not match its labels")
        table = block.get("feature_weights")
        if not isinstance(table, Mapping):
            problems.append(f"weight family {family!r} has no feature table")
            continue
        for feature, vector in table.items():
            if not isinstance(vector, (list, tuple)) or len(vector) != width:
                problems.append(f"weight family {family!r} feature {feature!r} does not have one weight per label")
                break
        samples = block.get("samples", 0)
        if not isinstance(samples, int) or isinstance(samples, bool) or samples < 0:
            problems.append(f"weight family {family!r} has an invalid sample count")
    return list(dict.fromkeys(problems))


def load_weights(path: Path) -> WeightBook:
    """Read a weight file. An invalid file is refused, never partially honoured."""
    path = Path(path)
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise EngineError(f"weight file is unreadable at {path}: {exc}") from exc
    problems = weights_problems(document)
    if problems:
        raise EngineError("weight file is invalid: " + "; ".join(problems))
    families: dict[str, FamilyWeights] = {}
    for family, block in document["families"].items():
        labels = tuple(str(item) for item in block["labels"])
        families[str(family)] = FamilyWeights(
            family=str(family),
            labels=labels,
            label_prior=tuple(float(value) for value in block["label_prior"]),
            feature_weights={
                str(feature): tuple(float(value) for value in vector)
                for feature, vector in block["feature_weights"].items()
            },
            samples=int(block.get("samples", 0)),
            source=str(block.get("source", document.get("source", ""))),
        )
    return WeightBook(
        engine_revision=str(document["engine_revision"]),
        source=str(document["source"]),
        families=families,
    )


def fit_family(
    *,
    family: str,
    labels: Sequence[str],
    examples: Iterable[tuple[Mapping[str, Any], str]],
    source: str,
) -> FamilyWeights:
    """Fit one family by multinomial naive-Bayes log-odds over projected states.

    ``examples`` is ``(projection entries, correct label)``. Every label the fitted
    table can produce must be observable in the examples, so an absent label is a
    training error rather than a label the engine can never be right about.
    """
    label_list = [str(item) for item in labels]
    if not label_list:
        raise EngineError("cannot fit a family with no labels")
    if len(label_list) > MAX_LABELS:
        raise EngineError(f"cannot fit {len(label_list)} labels; the bound is {MAX_LABELS}")
    index = {label: position for position, label in enumerate(label_list)}
    counts = [dict() for _ in label_list]
    totals = [0.0] * len(label_list)
    document_counts = [0] * len(label_list)
    seen = 0
    for entries, label in examples:
        target = str(label)
        if target not in index:
            raise EngineError(f"training example carries label {target!r}, which is outside the answer space")
        position = index[target]
        tokens = features_for(entries)
        for token in tokens:
            counts[position][token] = counts[position].get(token, 0.0) + 1.0
            totals[position] += 1.0
        document_counts[position] += 1
        seen += 1
    if seen == 0:
        raise EngineError(f"family {family!r} has no training examples")
    unobserved = [label for label, count in zip(label_list, document_counts) if count == 0]
    if unobserved:
        raise EngineError(
            f"family {family!r} has no training example for: {', '.join(sorted(unobserved))}"
        )
    prior = [math.log(count / seen) for count in document_counts]
    vocabulary: set[str] = set()
    for bucket in counts:
        vocabulary.update(bucket)
    vocabulary_size = len(vocabulary) or 1
    table: dict[str, tuple[float, ...]] = {}
    for token in sorted(vocabulary):
        vector = []
        for position in range(len(label_list)):
            numerator = counts[position].get(token, 0.0) + ADD_K
            denominator = totals[position] + ADD_K * vocabulary_size
            vector.append(math.log(numerator / denominator))
        table[token] = tuple(vector)
    return FamilyWeights(
        family=str(family),
        labels=tuple(label_list),
        label_prior=tuple(prior),
        feature_weights=table,
        samples=seen,
        source=str(source),
    )


def write_weights(path: Path, book: Mapping[str, FamilyWeights], *, source: str) -> Path:
    document = {
        "schema": WEIGHTS_SCHEMA,
        "engine_revision": ENGINE_REVISION,
        "source": str(source),
        "families": {
            family: {
                "labels": list(weights.labels),
                "label_prior": list(weights.label_prior),
                "feature_weights": {feature: list(vector) for feature, vector in sorted(weights.feature_weights.items())},
                "samples": weights.samples,
                "source": weights.source,
            }
            for family, weights in sorted(book.items())
        },
    }
    problems = weights_problems(document)
    if problems:
        raise EngineError("refusing to write an invalid weight file: " + "; ".join(problems))
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    return path


# ----------------------------------------------------------------------- scoring


@dataclass(frozen=True)
class Score:
    """One scored question."""

    question_id: str
    family: str
    label: str
    probability: float
    distribution: dict[str, float]
    abstained: bool
    reason: str
    threshold: float | None = None
    """The threshold that was applied, when one applied."""
    profile_id: str = ""
    """The calibration profile the threshold came from, when it came from one."""

    @property
    def has_evidence(self) -> bool:
        """Whether this abstention still has a computed answer behind it.

        ``BELOW_MIN_CONFIDENCE`` does: the engine reasoned to a label and a probability
        and then declined to stand behind it. ``NO_LOCAL_MODEL`` and
        ``ANSWER_SPACE_MISMATCH`` do not: there was nothing to reason from. Collapsing
        the two would throw away the evidence that justifies an escalation.
        """
        return bool(self.label) and self.probability > 0.0


def _threshold_map(value: Any) -> dict[str, float]:
    """Per-question thresholds from a request, validated rather than coerced.

    A threshold that is not a finite number in [0, 1] is a malformed request, and
    silently dropping it would turn a caller's mistake into a missing safety gate: the
    question would be answered with no threshold at all, which reads as "no profile
    justifies one" and is the opposite of what a malformed value means. A caller that
    states a malformed threshold is refused.
    """
    if value in (None, "", {}):
        return {}
    if not isinstance(value, Mapping):
        raise EngineError("min_confidence_by_question must be an object keyed by question id")
    thresholds: dict[str, float] = {}
    for key, raw in value.items():
        try:
            number = float(raw)
        except (TypeError, ValueError) as exc:
            raise EngineError(
                f"the threshold for question {key!r} is not a number: {raw!r}"
            ) from exc
        if not math.isfinite(number) or number < 0.0 or number > 1.0:
            raise EngineError(
                f"the threshold for question {key!r} is outside [0, 1]: {raw!r}"
            )
        thresholds[str(key)] = number
    return thresholds


def _profile_map(value: Any) -> dict[str, str]:
    """The calibration profile each per-question threshold came from, for the record."""
    if value in (None, "", {}):
        return {}
    if not isinstance(value, Mapping):
        raise EngineError("calibration_profile_by_question must be an object")
    return {str(key): str(item) for key, item in value.items()}


def score_question(
    question: Mapping[str, Any],
    entries: Mapping[str, Any],
    weights: WeightBook,
    *,
    min_confidence: float | None = None,
    profile_id: str = "",
) -> Score:
    """Score one question against one projected state.

    Refuses, rather than guesses, when the primitive is unsupported, the family is
    unknown, or the answer space does not match the fitted one. A refusal is
    ``abstained`` with a reason, which Ariadne turns into an escalation — never into
    an answer with a low confidence attached.

    A threshold abstention keeps the label and the probability it computed. Discarding
    them would make an abstention indistinguishable from never having looked, and
    ``label``/``probability`` are what an escalation needs in order to be judged on the
    evidence rather than on the excuse.
    """
    question_id = str(question.get("question_id", ""))
    primitive = str(question.get("primitive", ""))
    if unsupported_primitive(primitive):
        raise EngineError(f"{question_id}: {UNSUPPORTED_PRIMITIVE} {primitive}")
    space = answer_space(question)
    if len(space) < 2:
        raise EngineError(f"{question_id}: a bounded question needs at least two answers")
    family = question_identity(question)
    block = weights.get(family)
    if block is None:
        return Score(question_id, family, "", 0.0, {}, True, "NO_LOCAL_MODEL")
    if tuple(block.labels) != tuple(space):
        return Score(question_id, family, "", 0.0, {}, True, "ANSWER_SPACE_MISMATCH")
    width = len(block.labels)
    logits = list(block.label_prior)
    for token in features_for(entries):
        vector = block.feature_weights.get(token)
        if vector is None:
            continue
        for position in range(width):
            logits[position] += vector[position]
    peak = max(logits)
    exponentials = [math.exp(value - peak) for value in logits]
    total = sum(exponentials) or 1.0
    distribution = {
        label: round(value / total, 6) for label, value in zip(block.labels, exponentials)
    }
    label = block.labels[max(range(width), key=lambda position: logits[position])]
    probability = distribution[label]
    if min_confidence is not None and probability < float(min_confidence):
        return Score(
            question_id,
            family,
            label,
            probability,
            distribution,
            True,
            "BELOW_MIN_CONFIDENCE",
            float(min_confidence),
            str(profile_id),
        )
    return Score(question_id, family, label, probability, distribution, False, "")


# --------------------------------------------------------------------- the engine


class ReferenceBoundedEngine:
    """The engine object a transport wraps.

    It exposes the four sidecar methods as plain callables:
    ``status()``, ``decide(request)``, ``decide_batch(request)`` and ``warm()``.
    Keeping the surface this small is what lets the same engine be driven
    in-process by tests and over a pipe by the shipping sidecar, with no second
    implementation to drift.
    """

    def __init__(self, weights: WeightBook | None = None, *, model_revision: str = ENGINE_REVISION) -> None:
        self._weights = weights or empty_book()
        self._model_revision = str(model_revision)
        self._warm = False

    # -- lifecycle ---------------------------------------------------------

    def warm(self) -> dict:
        """Mark the engine ready. There is no checkpoint to load, so this is honest."""
        self._warm = True
        return {"warmed": True, "seconds": 0.0, "model_revision": self._model_revision}

    def status(self) -> dict:
        return {
            "available": True,
            "reason": "the reference bounded engine is loaded",
            "runtime_version": ENGINE_VERSION,
            "implementation": ENGINE_NAME,
            "implementation_revision": ENGINE_REVISION,
            "model": ENGINE_NAME,
            "model_revision": self._model_revision,
            "primitives": SUPPORTED_PRIMITIVES,
            "warm": self._warm,
            "device": "cpu",
            "confidence_kinds": ("PROVIDER_PROBABILITY", "NONE"),
            "calibration_self_granted": False,
            "weights": self._weights.summary(),
        }

    # -- calls -------------------------------------------------------------

    def decide(self, request: Mapping[str, Any]) -> Mapping[str, Any]:
        return self.decide_batch({
            "states": [dict(request.get("state") or {})],
            "questions": list(request.get("questions") or []),
            "min_confidence": request.get("min_confidence"),
            "min_confidence_by_question": request.get("min_confidence_by_question"),
            "calibration_profile_by_question": request.get("calibration_profile_by_question"),
        })

    def decide_batch(self, request: Mapping[str, Any]) -> Mapping[str, Any]:
        """Answer every question over every state as one bounded inference unit.

        This is the "single state, many questions" case and it is the reason the
        transport exists: one call, one set of features per state, one bounded
        inference, and results mapped back by ``(state index, question id)``. Nothing
        is issued per question, and a missing answer is reported rather than filled.

        Thresholds are resolved per question. ``min_confidence_by_question`` takes
        precedence for the question it names, and the batch-wide ``min_confidence`` is
        only the fallback for questions nobody stated a threshold for. A batch-wide
        threshold applied to every question would abstain a question whose profile
        justifies no threshold at all, and would apply one risk class's evidence to
        another's decision.
        """
        states = [dict(item) for item in request.get("states") or []]
        questions = [dict(item) for item in request.get("questions") or []]
        min_confidence = request.get("min_confidence")
        by_question = _threshold_map(request.get("min_confidence_by_question"))
        profiles = _profile_map(request.get("calibration_profile_by_question"))
        if not states:
            raise EngineError("a decide call needs at least one state")
        if not questions:
            raise EngineError("a decide call needs at least one question")
        answers: dict[str, Any] = {}
        abstained: dict[str, Any] = {}
        failed: list[str] = []
        for state_position, state in enumerate(states):
            entries = dict(state.get("entries") or state)
            digest = str(state.get("digest", ""))
            for question in questions:
                question_id = str(question.get("question_id", ""))
                key = f"{state_position}:{question_id}"
                threshold = by_question.get(question_id, min_confidence)
                profile_id = profiles.get(question_id, "")
                try:
                    score = score_question(
                        question, entries, self._weights,
                        min_confidence=threshold, profile_id=profile_id,
                    )
                except EngineError as exc:
                    failed.append(key)
                    answers[key] = {
                        "question_id": question_id,
                        "state_index": state_position,
                        "state_digest": digest,
                        "answer": None,
                        "valid": False,
                        "reason": str(exc),
                    }
                    continue
                if score.abstained:
                    abstained[key] = {"question_id": question_id, "reason": score.reason}
                    # `answer` stays None: there is no answer, and a caller that finds
                    # one here has been told to escalate rather than to use it. The
                    # computed label and probability travel beside it as evidence, so a
                    # refusal can be judged on what the engine actually reasoned rather
                    # than on the fact that it declined.
                    slot = {
                        "question_id": question_id,
                        "state_index": state_position,
                        "state_digest": digest,
                        "answer": None,
                        "valid": False,
                        "abstained": True,
                        "reason": score.reason,
                        "distribution": score.distribution,
                        "threshold": score.threshold,
                        "calibration_profile_id": score.profile_id,
                    }
                    if score.has_evidence:
                        slot["candidate_answer"] = score.label
                        slot["candidate_confidence"] = score.probability
                        slot["confidence_kind"] = "PROVIDER_PROBABILITY"
                    answers[key] = slot
                    continue
                answers[key] = {
                    "question_id": question_id,
                    "state_index": state_position,
                    "state_digest": digest,
                    "answer": score.label,
                    "valid": True,
                    "abstained": False,
                    "confidence": score.probability,
                    "confidence_kind": "PROVIDER_PROBABILITY",
                    "distribution": score.distribution,
                    "reason": "",
                }
        return {
            "provider": ENGINE_NAME,
            "model": ENGINE_NAME,
            "model_version": self._model_revision,
            "implementation_revision": ENGINE_REVISION,
            "runtime_version": ENGINE_VERSION,
            "device": "cpu",
            "answers": answers,
            "abstained": abstained,
            "failed_questions": failed,
            "usage": {
                "states": len(states),
                "questions": len(questions),
                "answer_slots": len(states) * len(questions),
                "abstained": len(abstained),
                "failed": len(failed),
            },
        }