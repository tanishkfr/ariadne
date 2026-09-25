"""Risk-adjusted decision policy (AR-203 T10).

The policy decides whether a bounded judgement may be *acted on*. It is
categorical on purpose — no false precision, no invented probability thresholds —
and it encodes three invariants:

1. **Decision confidence is not authorization.** No rule in this module grants a
   gate, a scope expansion, a dependency install, a destructive action, an
   acceptance or a release. ``authorization_effect`` is always ``none``, and a
   ``PROTECTED`` consequence is refused regardless of confidence.
2. **Confidence provenance matters.** A self-reported number from a generative
   model is not a calibrated probability, and a policy that needs stronger
   evidence cannot be satisfied by relabelling one.
3. **Missing confidence is allowed to be missing.** ``NONE`` is a valid answer
   for a low-consequence judgement; it is recorded as such and never guessed.

Thresholds, if they ever exist, are keyed to ``provider + model version +
primitive + question definition`` — never to a provider alone, so a moving model
alias cannot silently inherit an earlier version's calibration.
"""

from __future__ import annotations

from typing import Any, Mapping

from ..contracts import CONFIDENCE_KINDS, DECISION_CONSEQUENCES, ContractError

POLICY_VERSION = "ar-203-decision-policy-1"

MIN_EVIDENCE_BY_CONSEQUENCE = {
    "LOW": "",
    "MEDIUM": "OBSERVED",
    "HIGH": "REPRODUCED",
    "PROTECTED": "VERIFIED",
}
"""The verification level a decision's supporting evidence must reach per consequence.

An empty requirement means a low-consequence judgement may stand on a valid
answer alone. This is about the *evidence behind the judgement*, not about the
answer's confidence: a medium-consequence judgement needs an observed fact behind
it and a high-consequence one needs reproduction before it may drive action.
"""

STRONG_CONFIDENCE_KINDS = (
    "CALIBRATED_PROBABILITY",
    "PROVIDER_PROBABILITY",
    "DERIVED_CONFIDENCE",
)
"""Confidence kinds that are not a generative model's self-assessment.

``DERIVED_CONFIDENCE`` is Ariadne's own deterministic computation from evidence,
which is why it is acceptable where a self-reported number is not.
"""

_THRESHOLDS: dict[str, float] = {}
"""Calibrated thresholds, keyed provider|model_version|primitive|question_id.

Empty in AR-203: no calibration data exists yet, and inventing thresholds would
be false precision. The keying exists so a later milestone can add entries
without a contract change.
"""


def threshold_key(*, provider: str, model_version: str, primitive: str, question_id: str) -> str:
    return "|".join(str(item or "") for item in (provider, model_version, primitive, question_id))


def _usable_probability(value: Any) -> bool:
    """Whether a recorded confidence is a usable probability.

    A probability is a real number inside ``(0, 1]``. ``0.0`` states *no*
    confidence and must never satisfy a policy that requires evidence; values
    outside the unit interval (or non-numeric values) are malformed and are
    refused rather than clamped. Booleans are not probabilities.
    """
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    return 0.0 < float(value) <= 1.0


def register_threshold(*, provider: str, model_version: str, primitive: str, question_id: str, value: float) -> str:
    """Register one calibrated threshold for one concrete model version.

    A moving alias must never be registered: a threshold bound to an alias would
    silently apply to a model the calibration never measured.
    """
    if not str(model_version or "").strip():
        raise ContractError("a calibrated threshold needs a concrete model version")
    if not 0.0 <= float(value) <= 1.0:
        raise ContractError("a calibrated threshold must be inside [0, 1]")
    key = threshold_key(provider=provider, model_version=model_version, primitive=primitive, question_id=question_id)
    _THRESHOLDS[key] = float(value)
    return key


def threshold_for(*, provider: str, model_version: str, primitive: str, question_id: str) -> float | None:
    key = threshold_key(provider=provider, model_version=model_version, primitive=primitive, question_id=question_id)
    return _THRESHOLDS.get(key)


def authorization_effect() -> str:
    """The only authorization effect a decision record may claim."""
    return "none"


def protected_action_problems(record: Mapping, action: str) -> list[str]:
    """Whether a decision record is being used to authorize a protected action.

    It always is a problem: decisions inform policy, they never replace
    authorization.
    """
    if str(record.get("authorization_effect", "none")) != "none":
        return ["the decision record claims an authorization effect; decision records never authorize"]
    return [
        f"decision {record.get('decision_id')} cannot authorize {action!r}: decision confidence is not "
        "authorization; a protected operation needs the human gate that governs it"
    ]


def confidence_verdict(record: Mapping, *, consequence: str) -> dict:
    """Whether the recorded confidence is acceptable evidence for this consequence.

    Returns ``{"accepted": bool, "reason": str, "low_confidence": bool}``. The
    verdict concerns *acting on the judgement*; it never grants authorization.
    """
    if consequence not in DECISION_CONSEQUENCES:
        raise ContractError(f"unsupported decision consequence: {consequence!r}")
    kind = str(record.get("confidence_kind", "NONE"))
    value = record.get("confidence")
    if kind not in CONFIDENCE_KINDS:
        return {"accepted": False, "reason": f"unknown confidence kind {kind!r}", "low_confidence": True}
    if consequence == "PROTECTED":
        return {
            "accepted": False,
            "reason": "a protected operation is human-controlled regardless of confidence",
            "low_confidence": True,
        }
    if consequence == "LOW":
        if value is None or kind == "NONE" or not _usable_probability(value):
            return {
                "accepted": True,
                "reason": "low consequence: a judgement with no usable confidence is accepted as a low-confidence advisory",
                "low_confidence": True,
            }
        return {"accepted": True, "reason": "low consequence: the recorded confidence is sufficient", "low_confidence": False}
    if consequence == "MEDIUM":
        if kind in STRONG_CONFIDENCE_KINDS:
            if _usable_probability(value):
                return {"accepted": True, "reason": f"medium consequence: {kind} is sufficient", "low_confidence": False}
            return {
                "accepted": False,
                "reason": (
                    f"medium consequence: {kind} was recorded with a value that is not a usable "
                    "probability inside (0, 1]; fall back to the deterministic path or escalate"
                ),
                "low_confidence": True,
            }
        return {
            "accepted": False,
            "reason": (
                "medium consequence requires confidence that is not self-reported "
                f"(recorded: {kind}); fall back to the deterministic path or escalate"
            ),
            "low_confidence": True,
        }
    if kind in STRONG_CONFIDENCE_KINDS:
        if not _usable_probability(value):
            return {
                "accepted": False,
                "reason": (
                    "high consequence requires calibrated or provider/derived confidence and independent "
                    f"verification; {kind} was recorded with a value that is not a usable probability "
                    "inside (0, 1]"
                ),
                "low_confidence": True,
            }
        if kind == "CALIBRATED_PROBABILITY":
            return {"accepted": True, "reason": "high consequence: a calibrated probability was recorded", "low_confidence": False}
        return {
            "accepted": True,
            "reason": f"high consequence: {kind} is accepted as decision evidence and still requires independent verification",
            "low_confidence": False,
        }
    return {
        "accepted": False,
        "reason": (
            "high consequence requires calibrated or provider/derived confidence and independent "
            f"verification; recorded: {kind}"
        ),
        "low_confidence": True,
    }


def evidence_verdict(record: Mapping, *, consequence: str, verification_level: str = "") -> dict:
    """Whether the evidence behind a decision reaches the level its consequence needs."""
    required = MIN_EVIDENCE_BY_CONSEQUENCE[consequence]
    from ..contracts import VERIFICATION_LEVEL_ORDER

    if consequence == "PROTECTED":
        return {"accepted": False, "required": required,
                "reason": "protected operations are human-controlled; no decision evidence substitutes for authorization"}
    if not required:
        return {
            "accepted": True, "required": "",
            "reason": "low consequence: a valid answer needs no further evidence level",
        }
    reached = VERIFICATION_LEVEL_ORDER.get(str(verification_level or ""), 0)
    if reached >= VERIFICATION_LEVEL_ORDER[required]:
        return {"accepted": True, "required": required, "reason": f"evidence reached {verification_level} ({required} required)"}
    return {
        "accepted": False,
        "required": required,
        "reason": (
            f"consequence {consequence} requires evidence at {required}; recorded "
            f"{verification_level or 'UNVERIFIED'}"
        ),
    }


def may_act(
    record: Mapping,
    *,
    consequence: str,
    verification_level: str = "",
    require_evidence: bool = True,
) -> dict:
    """The full risk-adjusted verdict for acting on one decision record.

    A refusal always names the deterministic alternative: fall back to the
    deterministic path, or escalate to a human. It never silently proceeds.
    """
    if str(record.get("status", "")) != "answered" or record.get("answer_valid") is not True:
        return {
            "accepted": False,
            "low_confidence": True,
            "reason": f"the decision is {record.get('status')}; there is no valid answer to act on",
            "fallback": "deterministic",
            "authorization_effect": authorization_effect(),
        }
    confidence = confidence_verdict(record, consequence=consequence)
    evidence = (
        evidence_verdict(record, consequence=consequence, verification_level=verification_level)
        if require_evidence else {"accepted": True, "required": "", "reason": "evidence requirement waived by the caller"}
    )
    accepted = bool(confidence["accepted"] and evidence["accepted"])
    reasons = []
    if not confidence["accepted"]:
        reasons.append(confidence["reason"])
    if not evidence["accepted"]:
        reasons.append(evidence["reason"])
    return {
        "accepted": accepted,
        "low_confidence": bool(confidence["low_confidence"]),
        "reason": "; ".join(reasons) if reasons else confidence["reason"],
        "required_evidence": evidence.get("required", ""),
        "fallback": "" if accepted else ("escalate" if consequence in ("HIGH", "PROTECTED") else "deterministic"),
        "authorization_effect": authorization_effect(),
    }


__all__ = [
    "POLICY_VERSION",
    "MIN_EVIDENCE_BY_CONSEQUENCE",
    "STRONG_CONFIDENCE_KINDS",
    "threshold_key",
    "register_threshold",
    "threshold_for",
    "authorization_effect",
    "protected_action_problems",
    "confidence_verdict",
    "evidence_verdict",
    "may_act",
]
