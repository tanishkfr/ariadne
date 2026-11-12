"""Creative-proof binding for the S5 review (Ariadne 2.4C).

2.4A-R produced a real Proof Receipt for the corrected implementation and its
engine-run validation, but the receipt did not bind the independent S5 review
that authorized the correction. This module closes that gap without creating a
second verification engine and without touching human authority.

The chain is deliberately narrow::

    current S5 packet
      -> current review record for that packet
      -> engine-created reviewer and implementer executions
      -> current validation file + review judgement digest
      -> a versioned binding
      -> the Proof Receipt's ``creative_review`` field

A binding is evidence, never authorization. ``authorization_effect`` is
``none``; G3 is still recorded by :mod:`ariadne_engine.policy` from a human
channel. A stale review, a substituted packet, a changed judgement file, a
non-independent reviewer, a failed review, or a different implementation all
produce a refusal rather than a weaker binding.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Mapping

from . import contracts, provenance, review
from .contracts import ContractError

BINDING_SCHEMA = "ar-24c-creative-review-binding-1"
BINDING_COLLECTION = "creative_review_bindings"
MAX_BINDINGS = 2_000

ALLOWED_INDEPENDENCE = (
    "ENGINE_DISTINCT_EXECUTION",
    "DISTINCT_RUNTIME",
    "DISTINCT_PROVIDER",
    "HUMAN_REVIEW",
)
"""Independence levels a creative proof may rely on.

``DECLARED_DISTINCT`` is what two caller-supplied labels are worth; the review
record's own contract already refuses it for a usable review. ``NONE`` never
counts. The list is explicit so a future level cannot silently become
sufficient.
"""

REQUIRED_FIELDS = (
    "packet_id",
    "packet_digest",
    "review_id",
    "reviewer_identity",
    "reviewer_execution",
    "implementing_execution",
    "independence_level",
    "outcome",
    "reviewed_revision",
    "implementation_revision",
    "implementation_fingerprint",
    "review_evidence_digest",
    "review_judgement_sha256",
    "review_context_digest",
)


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _canonical(value: Mapping[str, Any]) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _manifest(packet: Path) -> dict:
    path = Path(packet) / "manifest.json"
    if not path.is_file():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def current_packets(state: Mapping[str, Any]) -> list[dict]:
    packets = state.get("packets")
    if not isinstance(packets, list):
        return []
    return [dict(row) for row in packets if isinstance(row, Mapping)]


def review_packet(state: Mapping[str, Any]) -> dict | None:
    """The most recent S5 packet, which is the creative review's subject."""
    for row in reversed(current_packets(state)):
        if str(row.get("stage", "")) == "S5":
            return row
    return None


def current_stage(state: Mapping[str, Any]) -> str:
    packets = current_packets(state)
    return str(packets[-1].get("stage", "")) if packets else ""


def is_creative_review_boundary(state: Mapping[str, Any]) -> bool:
    """Whether this run is at the S5 boundary the binding is required for.

    A T1 task (stage ``T1``), a technical S4B verification, a historical run
    with no packets and a run already past S6 do not get a new obligation. The
    obligation applies exactly where a creative independent review is the
    boundary the engine is being asked to prove.
    """
    return current_stage(state) == "S5"


def _review_evidence_digest(record: Mapping[str, Any], packet: Path, manifest: Mapping[str, Any]) -> str:
    judgement = packet / "evidence" / "review-judgement.md"
    validation = packet / "evidence" / "validation.json"
    body = {
        "review": {
            key: record.get(key)
            for key in (
                "review_id", "packet_id", "review_kind", "reviewer_identity", "reviewer_role",
                "context_digest", "reviewed_revision", "validation_sha256", "requirements",
                "evidence", "findings", "outcome", "recommendation", "recorded_at",
                "execution_binding", "reviewer_execution", "implementing_execution",
                "independence_level", "review_judgement_sha256",
            )
        },
        "packet_sha256": str(manifest.get("packet_sha256", "")),
        "judgement_sha256": _sha256_file(judgement) if judgement.is_file() else "",
        "validation_sha256": _sha256_file(validation) if validation.is_file() else "",
    }
    return hashlib.sha256(_canonical(body).encode("utf-8")).hexdigest()


def _binding_digest(binding: Mapping[str, Any]) -> str:
    body = {key: value for key, value in binding.items() if key != "binding_digest"}
    return hashlib.sha256(_canonical(body).encode("utf-8")).hexdigest()


def _validation_record(packet: Path) -> dict:
    path = Path(packet) / "evidence" / "validation.json"
    if not path.is_file():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _review_problems(
    state: Mapping[str, Any],
    *,
    packet: Path,
    manifest: Mapping[str, Any],
    record: Mapping[str, Any],
) -> list[str]:
    problems: list[str] = []
    try:
        problems.extend(contracts.review_problems(record))
    except Exception as exc:  # noqa: BLE001 - malformed records fail closed
        problems.append(f"the review record could not be validated: {exc}")
    packet_id = str(manifest.get("packet_id") or packet.name)
    if str(record.get("packet_id", "")) != packet_id:
        problems.append(
            f"the review is bound to packet {record.get('packet_id')!r}, not the current packet {packet_id!r}"
        )
    packet_digest = str(manifest.get("packet_sha256", ""))
    if not re.fullmatch(r"[0-9a-f]{64}", packet_digest):
        problems.append("the current S5 packet has no packet digest; nothing can be bound to it")
    elif str(record.get("context_digest", "")) != packet_digest:
        problems.append(
            "the review's context digest does not match the current S5 packet; the packet was "
            "replaced or the review describes a different review context"
        )
    outcome = str(record.get("outcome", ""))
    if outcome != "passed":
        problems.append(
            f"the current S5 review outcome is {outcome!r}; only a passing review can bind to proof"
        )
    if str(record.get("recommendation", "")).strip().lower() not in ("present g3", "passed", ""):
        problems.append(
            "the current S5 review did not recommend presentation to G3; a failed or blocked "
            "review cannot be counted as completion"
        )
    if record.get("findings") and outcome != "passed":
        problems.append("the current S5 review still carries blocking findings")
    judgement = packet / "evidence" / "review-judgement.md"
    if not judgement.is_file():
        problems.append("the current S5 packet has no recorded review judgement")
    elif not re.fullmatch(r"[0-9a-f]{64}", str(record.get("review_judgement_sha256", ""))):
        problems.append("the review record carries no judgement digest")
    elif str(record.get("review_judgement_sha256")) != _sha256_file(judgement):
        problems.append(
            "the review judgement file changed after the review was recorded; the review's evidence "
            "digest no longer describes what is on disk"
        )
    validation = packet / "evidence" / "validation.json"
    if not validation.is_file():
        problems.append("the current S5 packet carries no validation record for the reviewed revision")
    else:
        validation_digest = _sha256_file(validation)
        recorded = str(record.get("reviewed_revision", ""))
        if recorded and recorded != validation_digest:
            problems.append(
                "the review reviewed a different validation record than the one in the current S5 packet"
            )
        if not str(record.get("validation_sha256", "")):
            problems.append("the review record names no validation digest")
        elif str(record.get("validation_sha256")) != validation_digest:
            problems.append(
                "the review's validation digest does not match the current validation record"
            )
        validation_record = _validation_record(packet)
        if str(validation_record.get("status", "")) != "passed":
            problems.append(
                "the reviewed validation is not a passed record; a creative proof cannot rest on an "
                "unvalidated revision"
            )
    reviewer_execution = str(record.get("reviewer_execution", ""))
    implementing_execution = str(record.get("implementing_execution", ""))
    try:
        provenance.require_engine_execution(
            state, reviewer_execution, label="the creative review's reviewer execution",
        )
        provenance.require_engine_execution(
            state, implementing_execution, label="the creative review's implementation execution",
        )
    except ContractError as exc:
        problems.append(str(exc))
    if reviewer_execution and implementing_execution and reviewer_execution == implementing_execution:
        problems.append(
            "the review and implementation are the same engine execution; independence is not established"
        )
    level = str(record.get("independence_level", "") or "")
    if level and level not in ALLOWED_INDEPENDENCE:
        problems.append(
            f"the review's independence level {level!r} is not sufficient for creative proof"
        )
    if not level:
        problems.append("the review records no independence level")
    return list(dict.fromkeys(problems))


def build(
    state: Mapping[str, Any],
    *,
    work_digest: str,
    implementation_fingerprint: str = "",
    packet: Path | None = None,
) -> dict:
    """Build the current binding or raise with every reason it cannot be built."""
    packet_row = review_packet(state)
    if packet_row is None:
        raise ContractError(
            "creative proof requires an S5 review packet; this run carries no S5 packet to bind"
        )
    packet_path = Path(packet) if packet is not None else Path(str(packet_row.get("path", "")))
    manifest = _manifest(packet_path)
    packet_id = str(manifest.get("packet_id") or packet_path.name)
    record = review.current_review(state, packet_id=packet_id)
    if record is None:
        raise ContractError(
            f"creative proof requires an independent review of the current S5 packet {packet_id!r}; "
            "no review record exists for it"
        )
    problems = _review_problems(state, packet=packet_path, manifest=manifest, record=record)
    if problems:
        raise ContractError("creative review cannot bind to proof: " + "; ".join(problems))
    validation = _validation_record(packet_path)
    fingerprint = str(
        implementation_fingerprint
        or (validation.get("validated_revision") or {}).get("implementation_fingerprint", "")
        or ""
    )
    recorded_fingerprint = str(
        (validation.get("validated_revision") or {}).get("implementation_fingerprint", "") or ""
    )
    if recorded_fingerprint and fingerprint and recorded_fingerprint != fingerprint:
        raise ContractError(
            "creative review cannot bind to proof: the reviewed validation describes implementation "
            f"{recorded_fingerprint[:12]}, but the current implementation is {fingerprint[:12]}"
        )
    binding = {
        "schema_version": BINDING_SCHEMA,
        "required": True,
        "packet_id": packet_id,
        "packet_stage": "S5",
        "packet_digest": str(manifest.get("packet_sha256", "")),
        "review_id": str(record.get("review_id", "")),
        "review_kind": str(record.get("review_kind", "")),
        "reviewer_identity": str(record.get("reviewer_identity", "")),
        "reviewer_execution": str(record.get("reviewer_execution", "")),
        "implementing_execution": str(record.get("implementing_execution", "")),
        "independence_level": str(record.get("independence_level", "")),
        "outcome": str(record.get("outcome", "")),
        "recommendation": str(record.get("recommendation", "")),
        "reviewed_revision": str(record.get("reviewed_revision", "")),
        "review_context_digest": str(record.get("context_digest", "")),
        "implementation_revision": str(work_digest),
        "implementation_fingerprint": fingerprint,
        "review_evidence_digest": _review_evidence_digest(record, packet_path, manifest),
        "review_judgement_sha256": str(record.get("review_judgement_sha256", "")),
        "findings": list(record.get("findings") or []),
        "outstanding_findings": [],
        "correction_lineage": [
            {
                "review_id": str(row.get("review_id", "")),
                "packet_id": str(row.get("packet_id", "")),
                "outcome": str(row.get("outcome", "")),
                "recorded_at": str(row.get("recorded_at", "")),
                "reviewer_execution": str(row.get("reviewer_execution", "")),
            }
            for row in review.reviews(state)
            if str(row.get("packet_id", "")) != packet_id
        ][-12:],
        "authorization_effect": "none",
        "recorded_at": contracts.utc_now(),
        "provenance": {
            "created_by": "engine",
            "policy_version": contracts.POLICY_VERSION,
            "basis": "current S5 packet, current passed review, engine-created executions",
        },
    }
    binding["binding_digest"] = _binding_digest(binding)
    shape = binding_shape_problems(binding)
    if shape:
        raise ContractError("creative review binding is malformed: " + "; ".join(shape))
    return binding


def binding_shape_problems(binding: Mapping[str, Any]) -> list[str]:
    """Self-contained validation, usable on a stored Proof Receipt."""
    problems: list[str] = []
    if not isinstance(binding, Mapping):
        return ["creative review binding is not an object"]
    if str(binding.get("schema_version", "")) != BINDING_SCHEMA:
        problems.append(f"creative review binding schema is unsupported: {binding.get('schema_version')!r}")
    if str(binding.get("authorization_effect", "none")) != "none":
        problems.append("a creative review binding never grants authorization")
    for name in REQUIRED_FIELDS:
        if not str(binding.get(name, "") or "").strip():
            problems.append(f"creative review binding has no {name}")
    for name in ("packet_digest", "reviewed_revision", "review_judgement_sha256",
                 "review_evidence_digest", "implementation_revision", "review_context_digest"):
        value = str(binding.get(name, ""))
        if value and not re.fullmatch(r"[0-9a-f]{64}", value):
            problems.append(f"creative review binding {name} is not a sha256")
    if str(binding.get("outcome", "")) != "passed":
        problems.append("creative review binding records a non-passing review")
    if str(binding.get("independence_level", "")) not in ALLOWED_INDEPENDENCE:
        problems.append("creative review binding records an insufficient independence level")
    if str(binding.get("reviewer_execution", "")) == str(binding.get("implementing_execution", "")):
        problems.append("creative review binding names one execution as reviewer and implementer")
    if binding.get("outstanding_findings"):
        problems.append("creative review binding still carries outstanding findings")
    digest = str(binding.get("binding_digest", ""))
    if not re.fullmatch(r"[0-9a-f]{64}", digest):
        problems.append("creative review binding has no binding digest")
    elif _binding_digest(binding) != digest:
        problems.append("creative review binding digest does not bind its contents")
    return list(dict.fromkeys(problems))


def current_problems(
    binding: Mapping[str, Any],
    state: Mapping[str, Any],
    *,
    work_digest: str = "",
    implementation_fingerprint: str = "",
) -> list[str]:
    """Whether a stored binding still describes the current creative proof."""
    problems = binding_shape_problems(binding)
    if problems:
        return problems
    packet_row = review_packet(state)
    if packet_row is None:
        return ["the run no longer carries an S5 packet, so the stored review binding is stale"]
    packet_path = Path(str(packet_row.get("path", "")))
    manifest = _manifest(packet_path)
    packet_id = str(manifest.get("packet_id") or packet_path.name)
    if str(binding.get("packet_id", "")) != packet_id:
        problems.append("the stored binding names a different S5 packet than the current one")
    if str(binding.get("packet_digest", "")) != str(manifest.get("packet_sha256", "")):
        problems.append("the current S5 packet digest differs from the bound packet")
    record = review.current_review(state, packet_id=packet_id)
    if record is None:
        problems.append("the current S5 packet no longer has a review record")
    else:
        if str(record.get("review_id", "")) != str(binding.get("review_id", "")):
            problems.append("the current review record is not the one the binding names")
        problems.extend(_review_problems(state, packet=packet_path, manifest=manifest, record=record))
        if str(record.get("reviewed_revision", "")) != str(binding.get("reviewed_revision", "")):
            problems.append("the review's reviewed revision changed after binding")
    if work_digest and str(binding.get("implementation_revision", "")) != str(work_digest):
        problems.append(
            "the stored binding describes a different implementation revision than the receipt's "
            "current work digest"
        )
    if implementation_fingerprint and str(binding.get("implementation_fingerprint", "")) != str(
        implementation_fingerprint
    ):
        problems.append(
            "the stored binding describes a different implementation fingerprint than the current one"
        )
    return list(dict.fromkeys(problems))


def store(state: dict, binding: Mapping[str, Any]) -> dict:
    """Record a binding idempotently; an identical binding is not appended twice."""
    problems = binding_shape_problems(binding)
    if problems:
        raise ContractError("refusing to store malformed creative binding: " + "; ".join(problems))
    rows = state.setdefault(BINDING_COLLECTION, [])
    for row in rows:
        if isinstance(row, Mapping) and str(row.get("binding_digest", "")) == str(
            binding.get("binding_digest", "")
        ):
            return dict(row)
    if len(rows) >= MAX_BINDINGS:
        raise ContractError(
            f"{BINDING_COLLECTION} bound of {MAX_BINDINGS} reached; refused, not truncated"
        )
    stored = json.loads(_canonical(binding))
    rows.append(stored)
    return stored


def describe(binding: Mapping[str, Any]) -> str:
    return (
        f"{binding.get('packet_id')} review {binding.get('review_id')} "
        f"({binding.get('outcome')}, {binding.get('independence_level')})"
    )


