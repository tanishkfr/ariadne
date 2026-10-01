"""Calibration profiles: the only thing that may call a probability calibrated.

A provider reports a number. Ariadne's confidence contract already distinguishes five
origins, and only one of them is ``CALIBRATED_PROBABILITY``. A profile is the licence
that grants it, and it is deliberately hard to obtain.

A profile binds, at minimum:

* the decision definition and question version it was measured for;
* the runtime, implementation and **concrete** model revision it was measured against;
* the dataset digest and size, and the question-schema digest;
* the method and the measured numbers — accuracy, coverage, ECE, Brier;
* a threshold per risk class.

Binding is not bookkeeping. Each key closes a specific way a calibrated number could
be a lie:

*model revision* stops a calibration measured against one checkpoint being applied to
another checkpoint, including one that arrived under the same alias.

*question schema digest* stops a calibration measured on one wording being applied to
reworded questions. Rewording a bounded question changes the decision, and a threshold
tuned on the old wording is a threshold for a question nobody asked.

*decision definition and question version* stop one decision family borrowing another
family's numbers. Failure classification and review escalation are separate
calibration domains; one good profile does not transfer.

*risk class thresholds* stop a threshold fitted for a low-stakes decision from
silently gating a high-stakes one.

:func:`profile_for` is the only entry point that decides whether a probability may be
relabelled. It returns a profile or a refusal with reasons — never a default
threshold, and never a profile whose identity does not match.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from typing import Any, Mapping, Sequence

from ...contracts import (
    CALIBRATION_PROFILE_STATUSES,
    DECISION_CONSEQUENCES,
    SCHEMA_DECISION_RUNTIME,
    calibration_profile_problems,
    new_record_id,
    utc_now,
)
from ..contracts import DecisionQuestion
from .manifest import revision_matches

CALIBRATION_PROFILE_VERSION = "ar-206-calibration-profile-1"
"""The profile record shape, independent of the model it describes."""

CALIBRATION_METHODS = ("TEMPERATURE_SCALING", "ISOTONIC", "PLATT", "BINNED_RELIABILITY", "MEASURED_ONLY")
"""How the numbers were obtained.

``MEASURED_ONLY`` reports accuracy/coverage/ECE/Brier without rescaling anything. It is
the honest default for a new profile: measuring is not the same as correcting, and a
profile that corrects must say which correction it made.
"""

MIN_PROFILE_DATASET = 50
"""Below this, the measured numbers are reported but the profile stays ``DRAFT``.

Fifty is not a threshold that makes a model good. It is the point below which a
single disagreement moves accuracy by two points, so a "calibrated" label would be a
statement about sampling noise.
"""


def question_schema_digest(questions: Sequence[DecisionQuestion | Mapping[str, Any]]) -> str:
    """The digest of a set of question *definitions*.

    Covers the contract, question id, primitive, ordered answer space and definition
    version for each question, sorted so set order cannot change the digest. The
    instructions text is deliberately **not** in the schema digest: it belongs to the
    question identity, which is fingerprinted separately, so a rewording is visible as
    a changed question rather than hidden inside an unchanged "schema".
    """
    rows = []
    for question in questions:
        record = question.as_record() if isinstance(question, DecisionQuestion) else dict(question)
        rows.append(
            {
                "contract": str(record.get("projection_contract", "")),
                "question_id": str(record.get("question_id", "")),
                "primitive": str(record.get("primitive", "")),
                "allowed": [str(item) for item in record.get("options", ()) or ()],
                "definition_version": str(record.get("definition_version", "1")),
            }
        )
    rows.sort(key=lambda row: json.dumps(row, sort_keys=True, default=str))
    canonical = json.dumps(rows, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def decision_definition_digest(decision_definition: str, questions: Sequence[Any]) -> str:
    """The digest of one decision family's complete definition.

    Includes the question instructions, because a bounded question's wording *is* part
    of its contract. Two definitions that differ only in wording are different
    decisions and must not share a calibration profile or an evaluation report.
    """
    rows = []
    for question in questions:
        record = question.as_record() if isinstance(question, DecisionQuestion) else dict(question)
        rows.append(
            {
                "question_id": str(record.get("question_id", "")),
                "instructions": str(record.get("instructions", "")),
                "primitive": str(record.get("primitive", "")),
                "allowed": [str(item) for item in record.get("options", ()) or ()],
                "consequence": str(record.get("consequence", "LOW")),
                "definition_version": str(record.get("definition_version", "1")),
            }
        )
    rows.sort(key=lambda row: json.dumps(row, sort_keys=True, default=str))
    payload = {"decision_definition": str(decision_definition), "questions": rows}
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class CalibrationProfile:
    """A measured statement about one runtime's probabilities on one question.

    Frozen on purpose. A calibration profile that can be edited in place after it has
    justified a promotion is not evidence; it is a mutable claim.
    """

    decision_definition: str
    question_version: str
    runtime: str
    implementation: str
    model: str
    revision: str
    dataset_digest: str
    dataset_size: int
    question_schema_digest: str
    decision_definition_digest: str
    calibration_method: str
    accuracy: float
    coverage: float
    ece: float
    brier: float
    thresholds_by_risk: Mapping[str, float]
    status: str = "DRAFT"
    owner: str = ""
    created_at: str = field(default_factory=utc_now)
    profile_id: str = ""
    note: str = ""
    schema_version: int = SCHEMA_DECISION_RUNTIME
    authorization_effect: str = "none"

    def as_record(self) -> dict:
        record = asdict(self)
        record["model_revision"] = self.revision
        return record

    def problems(self) -> list[str]:
        record = dict(self.as_record())
        record["profile_id"] = self.profile_id or new_record_id("dcp")
        record["model_revision"] = self.revision
        return calibration_profile_problems(record)


def profile_from(record: Mapping[str, Any]) -> CalibrationProfile:
    """Rebuild a profile from its stored record."""
    return CalibrationProfile(
        decision_definition=str(record.get("decision_definition", "")),
        question_version=str(record.get("question_version", "")),
        runtime=str(record.get("runtime", "")),
        implementation=str(record.get("implementation", "")),
        model=str(record.get("model", "")),
        revision=str(record.get("model_revision", record.get("revision", ""))),
        dataset_digest=str(record.get("dataset_digest", "")),
        dataset_size=int(record.get("dataset_size", 0) or 0),
        question_schema_digest=str(record.get("question_schema_digest", "")),
        decision_definition_digest=str(record.get("decision_definition_digest", "")),
        calibration_method=str(record.get("calibration_method", "MEASURED_ONLY")),
        accuracy=float(record.get("accuracy", 0.0) or 0.0),
        coverage=float(record.get("coverage", 0.0) or 0.0),
        ece=float(record.get("ece", 0.0) or 0.0),
        brier=float(record.get("brier", 0.0) or 0.0),
        thresholds_by_risk=dict(record.get("thresholds_by_risk", {}) or {}),
        status=str(record.get("status", "DRAFT")),
        owner=str(record.get("owner", "")),
        created_at=str(record.get("created_at", "") or utc_now()),
        profile_id=str(record.get("profile_id", "")),
        note=str(record.get("note", "")),
    )


def build_profile(
    *,
    decision_definition: str,
    questions: Sequence[Any],
    runtime: str,
    implementation: str,
    model: str,
    revision: str,
    dataset_digest: str,
    dataset_size: int,
    accuracy: float,
    coverage: float,
    ece: float,
    brier: float,
    calibration_method: str = "MEASURED_ONLY",
    thresholds_by_risk: Mapping[str, float] | None = None,
    owner: str = "",
    note: str = "",
) -> CalibrationProfile:
    """Build a profile and set its status from what was actually measured.

    ``PROVEN`` requires a dataset at or above :data:`MIN_PROFILE_DATASET` and a
    method that was really run. There is no argument that sets ``PROVEN`` directly,
    because a caller that can set the status can also set the evidence.
    """
    if calibration_method not in CALIBRATION_METHODS:
        raise ValueError(f"unknown calibration method: {calibration_method!r}")
    thresholds = {
        str(risk): float(value) for risk, value in dict(thresholds_by_risk or {}).items()
    }
    status = "DRAFT"
    if dataset_size >= MIN_PROFILE_DATASET:
        status = "PROVEN"
    profile = CalibrationProfile(
        decision_definition=str(decision_definition),
        question_version=",".join(sorted({str(_question(q).get("definition_version", "1")) for q in questions})) or "1",
        runtime=str(runtime),
        implementation=str(implementation),
        model=str(model),
        revision=str(revision),
        dataset_digest=str(dataset_digest),
        dataset_size=int(dataset_size),
        question_schema_digest=question_schema_digest(questions),
        decision_definition_digest=decision_definition_digest(decision_definition, questions),
        calibration_method=str(calibration_method),
        accuracy=float(accuracy),
        coverage=float(coverage),
        ece=float(ece),
        brier=float(brier),
        thresholds_by_risk=thresholds,
        status=status,
        owner=str(owner),
        profile_id=new_record_id("dcp"),
        note=str(note),
    )
    problems = profile.problems()
    if problems:
        raise ValueError("refusing to build an invalid calibration profile: " + "; ".join(problems))
    return profile


def _question(question: Any) -> Mapping[str, Any]:
    return question.as_record() if isinstance(question, DecisionQuestion) else dict(question)


def profile_for(
    state: Mapping[str, Any],
    *,
    decision_definition: str,
    question: Any,
    runtime: str,
    implementation: str,
    model_revision: str,
    risk: str = "LOW",
) -> dict:
    """Whether a probability from this runtime may be called calibrated.

    Returns ``{"accepted": bool, "profile": dict|None, "reasons": [...],
    "confidence_kind": str, "min_confidence": float|None}``.

    Every refusal names its cause. There is no path from "no profile" to
    ``CALIBRATED_PROBABILITY``, and no default threshold: when nothing matches, the
    caller gets ``PROVIDER_PROBABILITY`` and no threshold at all, which is the
    conservative fallback the contract requires.
    """
    reasons: list[str] = []
    record = _question(question)
    if str(risk) not in DECISION_CONSEQUENCES:
        return {
            "accepted": False,
            "profile": None,
            "reasons": [f"unknown risk class: {risk}"],
            "confidence_kind": "PROVIDER_PROBABILITY",
            "min_confidence": None,
        }
    candidates: list[CalibrationProfile] = []
    for raw in state.get("calibration_profiles", []) or []:
        try:
            candidates.append(profile_from(raw))
        except Exception:  # noqa: BLE001 - an unreadable record is not a usable profile
            reasons.append("a stored calibration profile could not be read and was ignored")
    if not candidates:
        reasons.append("no calibration profile is recorded for this decision family")
        return _refuse(reasons)
    matching: list[CalibrationProfile] = []
    for candidate in candidates:
        why = _mismatch(
            candidate,
            decision_definition=decision_definition,
            question=record,
            runtime=runtime,
            implementation=implementation,
            model_revision=model_revision,
        )
        if why:
            reasons.append(why)
            continue
        if candidate.status != "PROVEN":
            reasons.append(f"the matching profile is {candidate.status}, not PROVEN")
            continue
        if candidate.problems():
            reasons.append("the matching profile has structural problems and cannot be trusted")
            continue
        matching.append(candidate)
    if not matching:
        return _refuse(reasons)
    chosen = sorted(matching, key=lambda profile: (-profile.dataset_size, profile.profile_id))[0]
    threshold = chosen.thresholds_by_risk.get(str(risk))
    return {
        "accepted": True,
        "profile": chosen.as_record(),
        "profile_id": chosen.profile_id,
        "reasons": [],
        "confidence_kind": "CALIBRATED_PROBABILITY",
        "min_confidence": None if threshold is None else float(threshold),
        "threshold_risk": str(risk),
    }


def _mismatch(
    candidate: CalibrationProfile,
    *,
    decision_definition: str,
    question: Mapping[str, Any],
    runtime: str,
    implementation: str,
    model_revision: str,
) -> str:
    if candidate.decision_definition != str(decision_definition):
        return (
            f"profile {candidate.profile_id} is bound to decision definition "
            f"{candidate.decision_definition!r}, not {str(decision_definition)!r}"
        )
    if not revision_matches(candidate.revision, str(model_revision)):
        return (
            f"profile {candidate.profile_id} is bound to model revision {candidate.revision!r}, "
            f"but the runtime loaded {str(model_revision)!r}"
        )
    if candidate.runtime != str(runtime):
        return f"profile {candidate.profile_id} is bound to runtime {candidate.runtime!r}, not {str(runtime)!r}"
    if candidate.implementation != str(implementation):
        return (
            f"profile {candidate.profile_id} is bound to implementation {candidate.implementation!r}, "
            f"not {str(implementation)!r}"
        )
    expected_schema = question_schema_digest([question])
    if candidate.question_schema_digest != expected_schema:
        return (
            f"profile {candidate.profile_id} was measured on a different question schema; "
            "the question definition changed"
        )
    expected_definition = decision_definition_digest(decision_definition, [question])
    if candidate.decision_definition_digest != expected_definition:
        return (
            f"profile {candidate.profile_id} was measured on a different decision definition; "
            "the question wording changed"
        )
    expected_version = str(question.get("definition_version", "1"))
    if expected_version not in {part.strip() for part in candidate.question_version.split(",")}:
        return (
            f"profile {candidate.profile_id} is bound to question version {candidate.question_version!r}, "
            f"not {expected_version!r}"
        )
    return ""


def _refuse(reasons: Sequence[str]) -> dict:
    return {
        "accepted": False,
        "profile": None,
        "reasons": list(dict.fromkeys(reasons)),
        "confidence_kind": "PROVIDER_PROBABILITY",
        "min_confidence": None,
    }


def record_profile(state: dict, profile: CalibrationProfile) -> dict:
    """Store a profile. Refuses an invalid one rather than storing it for later."""
    problems = profile.problems()
    if problems:
        raise ValueError("refusing to record an invalid calibration profile: " + "; ".join(problems))
    from ...contracts import require_collection_capacity

    require_collection_capacity(state, "calibration_profiles")
    record = profile.as_record()
    record["model_revision"] = profile.revision
    record["profile_id"] = profile.profile_id or new_record_id("dcp")
    record["recorded_at"] = utc_now()
    state.setdefault("calibration_profiles", []).append(record)
    return record


def set_profile_status(state: dict, profile_id: str, status: str) -> dict:
    """Change a profile's status by issuing a new record, never by editing one.

    A profile's history is what makes an earlier promotion auditable. Overwriting the
    status would leave a promotion pointing at a profile whose numbers have since been
    withdrawn with nothing to show for it.
    """
    if status not in CALIBRATION_PROFILE_STATUSES:
        raise ValueError(f"unknown calibration profile status: {status!r}")
    for record in state.get("calibration_profiles", []) or []:
        if str(record.get("profile_id", "")) == str(profile_id):
            updated = dict(record)
            updated["status"] = str(status)
            updated["superseded_at"] = utc_now()
            return updated
    raise ValueError(f"no calibration profile is recorded with id {profile_id!r}")


def describe() -> dict:
    return {
        "version": CALIBRATION_PROFILE_VERSION,
        "methods": CALIBRATION_METHODS,
        "statuses": list(CALIBRATION_PROFILE_STATUSES),
        "min_dataset_size": MIN_PROFILE_DATASET,
        "risk_classes": list(DECISION_CONSEQUENCES),
        "note": (
            "a profile is the only licence for CALIBRATED_PROBABILITY; without a matching "
            "PROVEN profile the result stays PROVIDER_PROBABILITY and no threshold applies"
        ),
    }