"""Evidence-bound review records.

A review reaches ``REVIEWED`` only when a review record exists that names:

* who reviewed (``reviewer_identity``), recorded verbatim from the operator or
  the engine API;
* what was reviewed (``packet_id`` + ``context_digest`` = the S5 packet sha256);
* which revision was reviewed (``reviewed_revision`` = the digest of the
  independent validation evidence for the implementation);
* which requirements applied (the S5 packet's delivered source labels);
* which evidence the reviewer actually had (``evidence``);
* what the reviewer concluded (``findings``, ``outcome``,
  ``recommendation``).

Two kinds of review exist and they deliberately require different evidence:

``experience``
    the S5 design/experience lens: it needs the isolated review context, the
    recorded judgement and the mechanical QA artifact.
``technical``
    a technical review: it needs the recorded judgement plus the independent
    validation record and the changed-file set it covers.

Neither kind accepts the implementer's summary as proof. A worker statement
that "review passed" is not a review record. ``review_state`` stays
``NOT_REVIEWED`` (the truthful ``NOT_PERFORMED`` equivalent) until a record
exists, and a review record never grants human acceptance.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import re
import uuid
from pathlib import Path

from . import contracts
from .contracts import ContractError, SCHEMA_RECORD, normalise, utc_now

REVIEW_ID_TEMPLATE = "rev_{stamp}_{suffix}"

REVIEW_KINDS = contracts.REVIEW_KINDS

REQUIRED_EVIDENCE = {
    "experience": ("isolated review context", "recorded review judgement", "mechanical QA evidence"),
    "technical": ("recorded review judgement", "independent validation record", "reviewed source revision"),
}

EXECUTION_BINDING = "engine"
"""How a review record is bound to execution identity.

``engine`` means the record names the implementing and reviewing executions the
engine created. A record without that binding cannot demonstrate that review and
implementation were different executions and is refused by
``required_review_problems`` and by ``contracts.review_problems``."""

OUTCOME_BY_RECOMMENDATION = {
    "present g3": "passed",
    "fix and re-review": "failed",
    "restart the direction": "blocked",
}

REVIEW_HEADINGS = (
    "Judgement",
    "Accepted patterns",
    "Feel tests",
    "Review lenses",
    "Findings",
    "Review recommendation",
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _manifest(packet: Path) -> dict:
    path = Path(packet) / "manifest.json"
    if not path.is_file():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def reviews(state: dict) -> list[dict]:
    value = state.get("reviews")
    if not isinstance(value, list):
        return []
    return [record for record in value if isinstance(record, dict)]


def current_review(state: dict, *, packet_id: str | None = None) -> dict | None:
    for record in reversed(reviews(state)):
        if packet_id and str(record.get("packet_id", "")) != packet_id:
            continue
        return record
    return None


# ------------------------------------------------------------- independence

def worker_identities(state: dict) -> list[str]:
    worker = state.get("worker") or {}
    values = [
        worker.get("worker_role"), worker.get("provider"), worker.get("model"),
        worker.get("task_id"), worker.get("identity"),
    ]
    return [str(value).strip().lower() for value in values if str(value or "").strip()]


def independence_problems(
    state: dict,
    reviewer_identity: str,
    *,
    reviewer_execution: str = "",
    implementing_execution: str = "",
) -> list[str]:
    """A reviewer that is the implementation worker cannot establish independence.

    Two checks, and the execution check is the stronger one: the engine created
    both executions, so ``implementing_execution != reviewing_execution`` is a
    machine-established fact rather than a claimed label.

    AR-203 adds a third: both ids must resolve to engine-created execution
    *records in this run*. A well-formed ``exe_…`` string a caller invented is
    not an execution, so it cannot establish independence.
    """
    from . import provenance

    problems: list[str] = []
    identity = str(reviewer_identity or "").strip()
    if not identity:
        problems.append("a review needs a reviewer identity; the implementer cannot review its own work")
    elif identity.lower() in worker_identities(state):
        problems.append(
            f"reviewer identity {identity!r} matches the implementation worker identity recorded in run "
            "state; an implementer cannot review its own work"
        )
    if not str(reviewer_execution or "").strip():
        problems.append("a review must be bound to the engine-created execution that produced it")
    if not str(implementing_execution or "").strip():
        problems.append("a review must name the engine-created implementation execution it reviews")
    if str(reviewer_execution) and str(reviewer_execution) == str(implementing_execution):
        problems.append(
            "the reviewing execution is the implementing execution; independence cannot be established "
            "from the same execution"
        )
    for label, value in (("reviewer", reviewer_execution), ("implementing", implementing_execution)):
        if not str(value or "").strip():
            continue
        try:
            provenance.require_engine_execution(state, str(value), label=f"a review's {label} execution")
        except ContractError as exc:
            problems.append(str(exc))
    return list(dict.fromkeys(problems))


def independence_level(
    state: dict,
    *,
    reviewer_execution: str = "",
    implementing_execution: str = "",
    human_review: bool = False,
) -> str:
    """The independence level the engine can establish from facts, never labels.

    ``DECLARED_DISTINCT`` is what two different labels are worth; the stronger
    levels require engine-created executions and, above that, *observed* runtime
    or provider differences. No level is categorically better for every task:
    policy decides which one a review requires.
    """
    from . import provenance

    reviewer = provenance.execution(state, str(reviewer_execution)) if reviewer_execution else None
    implementer = provenance.execution(state, str(implementing_execution)) if implementing_execution else None
    if reviewer is None or implementer is None:
        if str(reviewer_execution) and str(implementing_execution) and str(reviewer_execution) != str(implementing_execution):
            return "DECLARED_DISTINCT"
        return "NONE"
    if str(reviewer.get("execution_id")) == str(implementer.get("execution_id")):
        return "NONE"
    level = "ENGINE_DISTINCT_EXECUTION"
    reviewer_runtime = "|".join(str(reviewer.get(key, "")) for key in ("adapter", "invocation"))
    implementer_runtime = "|".join(str(implementer.get(key, "")) for key in ("adapter", "invocation"))
    if reviewer_runtime and implementer_runtime and reviewer_runtime != implementer_runtime:
        level = "DISTINCT_RUNTIME"
    observed = provenance.identity_claims(reviewer)
    other = provenance.identity_claims(implementer)
    reviewer_identity = (observed.get("provider", {}).get("value", ""), observed.get("model", {}).get("value", ""))
    implementer_identity = (other.get("provider", {}).get("value", ""), other.get("model", {}).get("value", ""))
    if (
        all(item and item != "UNKNOWN" for item in reviewer_identity + implementer_identity)
        and reviewer_identity != implementer_identity
    ):
        level = "DISTINCT_PROVIDER"
    if human_review:
        level = "HUMAN_REVIEW"
    return level


# ----------------------------------------------------------------- evidence

def evidence_available(state: dict, packet: Path, *, pending: tuple[str, ...] = ()) -> list[str]:
    packet = Path(packet)
    project = Path(state.get("project", ""))
    available: list[str] = []
    if (packet / "manifest.json").is_file():
        available.append("isolated review context")
    if (packet / "evidence" / "review-judgement.md").is_file():
        available.append("recorded review judgement")
    if (project / "QA.md").is_file():
        available.append("mechanical QA evidence")
    if (packet / "evidence" / "validation.json").is_file():
        available.append("independent validation record")
    validation = _validation_record(packet)
    if validation.get("scope", {}).get("changed"):
        available.append("reviewed source revision")
    for name in pending:
        if name not in available:
            available.append(name)
    return available


def _validation_record(packet: Path) -> dict:
    path = Path(packet) / "evidence" / "validation.json"
    if not path.is_file():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def review_evidence_problems(
    state: dict,
    packet: Path,
    review_kind: str,
    *,
    pending: tuple[str, ...] = (),
) -> list[str]:
    """Whether the evidence this review kind requires actually exists.

    ``pending`` names evidence the caller is about to write in the same
    operation (the incoming judgement block), so a check never fails for
    something the operation itself is creating.
    """
    if review_kind not in REQUIRED_EVIDENCE:
        return [f"unknown review kind: {review_kind}"]
    available = set(evidence_available(state, packet, pending=pending))
    missing = [name for name in REQUIRED_EVIDENCE[review_kind] if name not in available]
    if missing:
        return [f"{review_kind} review is missing required evidence: " + ", ".join(missing)]
    validation = _validation_record(packet)
    if review_kind == "technical" and validation.get("status") != "passed":
        return ["a technical review requires a passed independent validation for the reviewed revision"]
    return []


def required_review_problems(state: dict, packet: Path) -> list[str]:
    """Whether the required review contract for this revision has been satisfied."""
    packet = Path(packet)
    packet_id = str(_manifest(packet).get("packet_id") or packet.name)
    record = current_review(state, packet_id=packet_id)
    if record is None:
        return [
            "the required independent review has not been performed for this revision "
            "(review state is NOT_REVIEWED)"
        ]
    problems = contracts.review_problems(record)
    if problems:
        return ["the recorded review is not usable: " + "; ".join(problems)]
    return []


# ------------------------------------------------------------------ record

def _findings(block: str) -> list[str]:
    section = ""
    match = re.search(r"(?im)^###\s+Findings\s*$", block)
    if match:
        remainder = block[match.end():]
        end = re.search(r"(?m)^#{2,3}\s+\S", remainder)
        section = remainder[: end.start()] if end else remainder
    findings = []
    for line in section.splitlines():
        text = normalise(re.sub(r"^[\s>*\-]+", "", line))
        if text and text.lower() not in ("none", "n/a"):
            findings.append(text)
    return findings


def build_record(
    state: dict,
    packet: Path,
    *,
    reviewer_identity: str,
    review_kind: str = "experience",
    reviewer_role: str = "independent-reviewer",
    block: str = "",
    recommendation: str = "",
    outcome: str | None = None,
    evidence: tuple[str, ...] | None = None,
    requirements: tuple[str, ...] | None = None,
    findings: tuple[str, ...] | None = None,
    reviewer_execution: str = "",
    implementing_execution: str = "",
) -> dict:
    """Construct a review record from the evidence that actually exists."""
    packet = Path(packet)
    manifest = _manifest(packet)
    validation = _validation_record(packet)
    packet_id = str(manifest.get("packet_id") or packet.name)
    judgement = packet / "evidence" / "review-judgement.md"
    context_digest = str(manifest.get("packet_sha256") or "")
    if not re.fullmatch(r"[0-9a-f]{64}", context_digest):
        raise ContractError("the review context has no packet digest; nothing was recorded")
    delivered = [
        str(source.get("label"))
        for source in manifest.get("sources", [])
        if source.get("delivered", True)
    ]
    recommendation = normalise(recommendation) or "not recorded"
    resolved_outcome = outcome or OUTCOME_BY_RECOMMENDATION.get(recommendation.lower(), "not-performed")
    record = {
        "schema_version": SCHEMA_RECORD,
        "review_id": REVIEW_ID_TEMPLATE.format(
            stamp=utc_now().replace("-", "").replace(":", ""), suffix=uuid.uuid4().hex[:8]
        ),
        "run_id": str(state.get("run_id", "")),
        "packet_id": packet_id,
        "review_kind": review_kind,
        "reviewer_identity": str(reviewer_identity).strip(),
        "reviewer_role": str(reviewer_role).strip(),
        "context_digest": context_digest,
        "reviewed_revision": _sha256(packet / "evidence" / "validation.json")
        if (packet / "evidence" / "validation.json").is_file() else "",
        "requirements": list(requirements if requirements is not None else delivered),
        "evidence": list(evidence if evidence is not None else sorted(evidence_available(state, packet))),
        "findings": list(findings if findings is not None else _findings(block)),
        "outcome": resolved_outcome,
        "recommendation": recommendation,
        "recorded_at": utc_now(),
        "independent": True,
        "execution_binding": EXECUTION_BINDING,
        "reviewer_execution": str(reviewer_execution),
        "implementing_execution": str(implementing_execution),
        "independence_level": independence_level(
            state,
            reviewer_execution=str(reviewer_execution),
            implementing_execution=str(implementing_execution),
        ),
    }
    problems = contracts.review_problems(record)
    if problems:
        raise ContractError("review record is malformed: " + "; ".join(problems))
    if judgement.is_file():
        record["review_judgement_sha256"] = _sha256(judgement)
    return record


def store(state: dict, packet: Path, record: dict) -> Path:
    """Persist the record in run state and beside the evidence it describes.

    A record that already carries the engine execution binding is never
    overwritten. A pre-AR-202 record without the binding is preserved beside the
    new one as ``review-record.legacy.json`` and replaced, because an unbound
    record cannot demonstrate review independence and would otherwise block the
    packet forever. The legacy bytes are kept, never deleted.
    """
    destination = Path(packet) / "evidence" / "review-record.json"
    if destination.exists():
        existing = {}
        try:
            existing = json.loads(destination.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            existing = {}
        bound = str((existing or {}).get("execution_binding", "")) == EXECUTION_BINDING
        if not isinstance(existing, dict) or bound or not existing:
            raise ContractError(f"Refusing to overwrite existing review record: {destination}")
        legacy = destination.with_name("review-record.legacy.json")
        if legacy.exists():
            raise ContractError(f"Refusing to overwrite existing legacy review record: {legacy}")
        destination.replace(legacy)
    from . import persistence

    persistence.write_json(destination, record)
    state.setdefault("reviews", []).append(record)
    return destination


def escalation_advice(
    state: dict,
    *,
    packet: Path | None = None,
    task_id: str = "",
    stakes: str = "LOW",
    verification_result: str = "",
    protected: bool = False,
    provider=None,
    **options,
) -> dict:
    """Bounded advice on how much review the available evidence suggests.

    The advice is an input to policy, never a replacement: the review the engine
    *requires* is still decided by :func:`required_review_problems`. With no
    provider configured the deterministic rules answer where they can and the
    result otherwise says so, rather than inventing a review level.
    """
    derived = str(verification_result or "")
    if not derived and packet is not None:
        missing = evidence_available(state, Path(packet))
        derived = "UNVERIFIED" if missing else "VERIFIED"
    from .decisions import integrations

    return integrations.review_escalation(
        state,
        task_id=str(task_id),
        stakes=str(stakes),
        verification_result=derived,
        protected=bool(protected),
        provider=provider,
        **options,
    )
