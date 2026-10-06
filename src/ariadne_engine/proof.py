"""AR-224 Proof Receipts: stable projection of a verification pass.

A verification pass (acceptance.gates.run_pass) is the engine truth.
A Proof Receipt is the stable, shareable, append-only projection of one pass:

  VP-0041  -- human-readable proof id (VP- + zero-padded sequence)
  vps_...  -- underlying engine pass_id (kept for lineage)

Workers produce. Ariadne determines what is actually proven.

Invariants (release-critical):
  - receipts are append-only; a later run creates VP-0042, never overwrites VP-0041
  - receipt_digest binds canonical contents; content change invalidates it
  - digest integrity != third-party attestation (never call a hash a signature)
  - authorization_effect is always "none"; promotion never grants authority
  - no aggregate quality percentage; counts only
  - comparison requires task/contract/requirement lineage or refuses
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence

from . import contracts

PROOF_SCHEMA_VERSION = "ar-224-proof-receipt-1"
READABLE_PROOF_SCHEMAS = ("ar-224-proof-receipt-1",)

COLLECTION = "proof_receipts"

MAX_PROOF_RECEIPTS = 5_000

PROOF_ID_RE = re.compile(r"^VP-(\d{4,})$")

CI_EXIT = {
    "ACCEPTED": 0,
    "NOT_ACCEPTED": 1,
    "VERIFICATION_BLOCKED": 2,
    "USAGE_OR_CONFIGURATION_ERROR": 3,
}

_SHARE_UNSAFE_KEYS = (
    "absolute_path",
    "machine_path",
    "username",
    "user_name",
    "env",
    "environment_variables",
    "credential",
    "credentials",
    "secret",
    "token",
    "private_url",
    "raw_log",
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _canonical(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def canonical_bytes(receipt: Mapping[str, Any]) -> bytes:
    body = {k: v for k, v in dict(receipt).items() if k != "receipt_digest"}
    return _canonical(body).encode("utf-8")


def receipt_digest(receipt: Mapping[str, Any]) -> str:
    return hashlib.sha256(canonical_bytes(receipt)).hexdigest()


def _existing(state: Mapping[str, Any]) -> list[dict]:
    rows = state.get(COLLECTION, []) or []
    return [dict(r) for r in rows if isinstance(r, Mapping)]


def next_proof_id(state: Mapping[str, Any]) -> str:
    nums = []
    for row in _existing(state):
        m = PROOF_ID_RE.fullmatch(str(row.get("proof_id", "")))
        if m:
            try:
                nums.append(int(m.group(1)))
            except ValueError:
                continue
    nxt = (max(nums) + 1) if nums else 1
    return f"VP-{nxt:04d}"


def previous_proof_id(state: Mapping[str, Any]) -> str:
    rows = _existing(state)
    if not rows:
        return ""
    return str(rows[-1].get("proof_id", ""))


def create_receipt_from_pass(
    pass_record: Mapping[str, Any],
    *,
    proof_id: str = "",
    previous_id: str = "",
    reviewer: str = "ariadne-engine",
) -> dict:
    pid = proof_id or str(pass_record.get("pass_id", ""))
    # pass_id is vps_...; proof_id must be VP-NNNN. If caller passed a vps id,
    # keep it as engine lineage, not as proof id.
    if not PROOF_ID_RE.fullmatch(pid):
        raise contracts.ContractError(f"proof receipt needs a VP-NNNN proof_id, got {pid!r}")
    verdicts = dict(pass_record.get("requirement_verdicts", {}) or {})
    decisions = [dict(r) for r in pass_record.get("requirement_decisions", []) or []]
    claims = [dict(r) for r in pass_record.get("claim_assessments", []) or []]
    counts: dict[str, int] = {}
    for v in verdicts.values():
        counts[str(v)] = counts.get(str(v), 0) + 1
    contradicted = 0
    for c in claims:
        if str(c.get("assessment", c.get("verdict", ""))) in ("CONTRADICTED",):
            contradicted += 1
        elif str(c.get("status", "")) == "CONTRADICTED":
            contradicted += 1
    # claim_assessments from decisions.assess_claim carry "assessment" key;
    # fall back to counting blocking contradicted claims from readiness.
    readiness = pass_record.get("acceptance_readiness", {}) or {}
    if not contradicted:
        contradicted = len(readiness.get("contradicted_claims", []) or [])
    acceptance_state = str(pass_record.get("acceptance_state", "NOT_ACCEPTED"))
    if acceptance_state not in ("ACCEPTED", "NOT_ACCEPTED"):
        acceptance_state = "NOT_ACCEPTED"
    receipt = {
        "schema_version": PROOF_SCHEMA_VERSION,
        "proof_id": pid,
        "engine_pass_id": str(pass_record.get("pass_id", "")),
        "task_id": str(pass_record.get("task_id", "")),
        "contract_id": str(pass_record.get("contract_id", "")),
        "contract_revision": str(pass_record.get("contract_revision", "")),
        "work_digest": str(pass_record.get("work_digest", "")),
        "created_at": str(pass_record.get("recorded_at", "") or utc_now()),
        "requirement_decisions": decisions,
        "requirement_verdicts": verdicts,
        "verdict_counts": counts,
        "claim_assessments": claims,
        "contradicted_claims": contradicted,
        "blocking_summary": dict(pass_record.get("blocking_summary", {}) or {}),
        "acceptance_state": acceptance_state,
        "reviewer": reviewer,
        "provenance": {
            "created_by": "engine",
            "policy_version": str((pass_record.get("provenance", {}) or {}).get("policy_version", "")),
            "pass_kind": str(pass_record.get("pass_kind", "")),
        },
        "previous_proof_id": previous_id,
    }
    receipt["receipt_digest"] = receipt_digest(receipt)
    problems = receipt_problems(receipt)
    if problems:
        raise contracts.ContractError("proof receipt malformed: " + "; ".join(problems))
    return receipt


def receipt_problems(record: Mapping[str, Any]) -> list[str]:
    problems: list[str] = []
    if not isinstance(record, Mapping):
        return ["proof receipt is not an object"]
    if str(record.get("authorization_effect", "none")) != "none":
        problems.append("a proof receipt never grants authorization")
    for row in record.get("requirement_decisions", []) or []:
        if isinstance(row, Mapping) and str(row.get("authorization_effect", "none")) != "none":
            problems.append("a proof receipt decision never grants authorization")
            break
    if "slop_score" in record:
        problems.append("a proof receipt records requirement-level state, never a global slop score")
    if record.get("schema_version") not in READABLE_PROOF_SCHEMAS:
        problems.append(f"proof receipt schema unsupported: {record.get('schema_version')!r}")
    if not PROOF_ID_RE.fullmatch(str(record.get("proof_id", ""))):
        problems.append("proof receipt has a malformed proof id (want VP-NNNN)")
    for name in ("task_id", "contract_id", "contract_revision", "work_digest", "created_at"):
        if not str(record.get(name, "")).strip():
            problems.append(f"proof receipt has no {name}")
    if not isinstance(record.get("requirement_verdicts", None), Mapping):
        problems.append("proof receipt requirement_verdicts is not a mapping")
    else:
        for req, verdict in record["requirement_verdicts"].items():
            if str(verdict) not in contracts.ACCEPTANCE_VERDICTS:
                problems.append(f"proof receipt verdict unknown for {req}: {verdict}")
    if not isinstance(record.get("requirement_decisions", None), list):
        problems.append("proof receipt requirement_decisions is not a list")
    if not isinstance(record.get("claim_assessments", None), list):
        problems.append("proof receipt claim_assessments is not a list")
    if str(record.get("acceptance_state", "")) not in ("ACCEPTED", "NOT_ACCEPTED", "VERIFICATION_BLOCKED"):
        problems.append("proof receipt acceptance_state must be ACCEPTED, NOT_ACCEPTED or VERIFICATION_BLOCKED")
    digest = str(record.get("receipt_digest", ""))
    if not re.fullmatch(r"[0-9a-f]{64}", digest):
        problems.append("proof receipt digest is not a sha256")
    else:
        if receipt_digest(record) != digest:
            problems.append("proof receipt digest does not bind its contents")
    return problems


def verify_digest(receipt: Mapping[str, Any]) -> dict:
    expected = receipt_digest(receipt)
    actual = str(receipt.get("receipt_digest", ""))
    return {"ok": expected == actual, "expected": expected, "actual": actual}


def store_receipt(state: dict, receipt: Mapping[str, Any]) -> dict:
    problems = receipt_problems(receipt)
    if problems:
        raise contracts.ContractError("refusing to store malformed receipt: " + "; ".join(problems))
    rows = state.setdefault(COLLECTION, [])
    for row in rows:
        if isinstance(row, Mapping) and str(row.get("proof_id", "")) == str(receipt.get("proof_id", "")):
            raise contracts.ContractError(f"receipt {receipt.get('proof_id')} already stored; history is append-only")
        if isinstance(row, Mapping) and str(row.get("receipt_digest", "")) == str(receipt.get("receipt_digest", "")) and str(row.get("proof_id", "")) != str(receipt.get("proof_id", "")):
            # identical content under a different id is a copy error, not history
            raise contracts.ContractError("identical receipt content under a different proof id")
    if len(rows) >= MAX_PROOF_RECEIPTS:
        raise contracts.ContractError(f"{COLLECTION} bound of {MAX_PROOF_RECEIPTS} reached; refused, not truncated")
    stored = json.loads(_canonical(dict(receipt)))
    rows.append(stored)
    return stored


def get_receipt(state: Mapping[str, Any], proof_id: str) -> dict | None:
    for row in _existing(state):
        if str(row.get("proof_id", "")) == str(proof_id):
            return row
    return None


def list_receipts(state: Mapping[str, Any]) -> list[dict]:
    return _existing(state)


def history_for_requirement(state: Mapping[str, Any], requirement_id: str) -> list[dict]:
    out = []
    for row in _existing(state):
        verdicts = row.get("requirement_verdicts", {}) or {}
        if str(requirement_id) in verdicts:
            out.append({
                "proof_id": str(row.get("proof_id", "")),
                "verdict": str(verdicts[str(requirement_id)]),
                "work_digest": str(row.get("work_digest", "")),
                "created_at": str(row.get("created_at", "")),
            })
    return out


def _lineage_key(receipt: Mapping[str, Any]) -> tuple[str, str]:
    return (str(receipt.get("contract_id", "")), str(receipt.get("task_id", "")))


def compare_receipts(a: Mapping[str, Any], b: Mapping[str, Any]) -> dict:
    # Lineage safety: unrelated receipts must not compare directly.
    if _lineage_key(a) != _lineage_key(b):
        raise contracts.ContractError("receipts name different task/contract lineage; direct comparison refused")
    if str(a.get("contract_revision", "")) != str(b.get("contract_revision", "")):
        boundary = True
    else:
        boundary = False
    va = dict(a.get("requirement_verdicts", {}) or {})
    vb = dict(b.get("requirement_verdicts", {}) or {})
    if set(va.keys()) != set(vb.keys()):
        raise contracts.ContractError("receipts name different requirement sets; direct comparison refused")
    transitions = {}
    resolved = still_failing = new_failures = 0
    for req in sorted(set(va) | set(vb)):
        before, after = str(va.get(req, "")), str(vb.get(req, ""))
        transitions[req] = {"before": before, "after": after}
        if before == after:
            if after in ("FAILED", "UNPROVEN", "NEEDS_HUMAN"):
                still_failing += 1
            continue
        if after == "PROVEN" and before in ("FAILED", "PARTIAL", "UNPROVEN", "NEEDS_HUMAN"):
            resolved += 1
        elif after in ("FAILED", "UNPROVEN") and before in ("PROVEN", "PARTIAL"):
            new_failures += 1
        elif after in ("FAILED", "UNPROVEN", "NEEDS_HUMAN"):
            still_failing += 1
    return {
        "before": str(a.get("proof_id", "")),
        "after": str(b.get("proof_id", "")),
        "contract_revision_boundary": boundary,
        "resolved": resolved,
        "still_failing": still_failing,
        "new_failures": new_failures,
        "transitions": transitions,
    }


def _redact_value(key: str, value: Any) -> Any:
    kl = str(key).lower()
    for unsafe in _SHARE_UNSAFE_KEYS:
        if unsafe in kl:
            return "<redacted>"
    if isinstance(value, str):
        # absolute machine paths, windows or posix
        if re.match(r"^[A-Za-z]:\\", value) or value.startswith("\\\\"):
            return "<redacted-path>"
        if value.startswith("/") and len(value) > 1 and "/" in value[1:]:
            # keep contract/task relative refs, redact anything looking like a home dir
            if "/home/" in value or "/Users/" in value or "/AppData/" in value:
                return "<redacted-path>"
        if re.match(r"^https?://", value) and ("token" in value or "secret" in value or "@" in value):
            return "<redacted-url>"
    if isinstance(value, Mapping):
        return {k: _redact_value(k, v) for k, v in value.items()}
    if isinstance(value, list):
        return [_redact_value(key, v) for v in value]
    return value


def share_safe(receipt: Mapping[str, Any]) -> dict:
    body = {k: _redact_value(k, v) for k, v in dict(receipt).items() if k != "receipt_digest"}
    body["share_safe"] = True
    # digest of the share-safe projection, distinct from internal digest
    body["share_digest"] = hashlib.sha256(_canonical(body).encode("utf-8")).hexdigest()
    return body


def format_human(receipt: Mapping[str, Any], *, task_title: str = "") -> str:
    counts = dict(receipt.get("requirement_verdicts", {}) or {})
    tally: dict[str, int] = {}
    for v in counts.values():
        tally[str(v)] = tally.get(str(v), 0) + 1
    total = len(counts)
    worker_claimed = len(receipt.get("claim_assessments", []) or [])
    lines = [
        f"ARIADNE / {receipt.get('proof_id', '')}",
        "",
        "Task",
        task_title or str(receipt.get("task_id", "")),
        "",
        "Revision",
        str(receipt.get("work_digest", ""))[:12],
        "",
        "Requirements",
        str(total),
        "",
    ]
    for verdict in ("PROVEN", "PARTIAL", "UNPROVEN", "FAILED", "NEEDS_HUMAN"):
        lines.append(f"{verdict:12s} {tally.get(verdict, 0)}")
    lines += [
        "",
        "Worker claimed",
        f"{worker_claimed} statements assessed",
        "",
        "Contradicted claims",
        str(receipt.get("contradicted_claims", 0)),
        "",
        "VERDICT",
        str(receipt.get("acceptance_state", "")),
        "",
        f"Evaluated against {total} requirements using Proof Pass {receipt.get('proof_id', '')}.",
    ]
    return "\n".join(lines)


def format_comparison_human(comp: Mapping[str, Any]) -> str:
    lines = [
        f"Resolved           {comp.get('resolved', 0)}",
        f"Still failing      {comp.get('still_failing', 0)}",
        f"New failures       {comp.get('new_failures', 0)}",
        "",
    ]
    for req, t in (comp.get("transitions", {}) or {}).items():
        if t.get("before") != t.get("after"):
            lines += ["", str(req), f"{t.get('before')} -> {t.get('after')}"]
    if comp.get("contract_revision_boundary"):
        lines += ["", "Contract revision boundary: interpret transitions across revisions with care."]
    return "\n".join(lines)


def exit_code_for(acceptance_state: str, *, blocked: bool = False, usage_error: bool = False) -> int:
    if usage_error:
        return CI_EXIT["USAGE_OR_CONFIGURATION_ERROR"]
    if blocked:
        return CI_EXIT["VERIFICATION_BLOCKED"]
    if acceptance_state == "ACCEPTED":
        return CI_EXIT["ACCEPTED"]
    return CI_EXIT["NOT_ACCEPTED"]


# ------------------------------------------------- verify_task pipeline

def work_digest_for(task_text: str, work_ref: str = "") -> str:
    payload = "task:" + str(task_text or "") + "\nwork:" + str(work_ref or "")
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def resolve_zero_arg(state: Mapping[str, Any], *, task_id: str = "") -> dict:
    from .acceptance import contract as contract_module

    candidates = contract_module.contracts_for(state)
    if task_id:
        candidates = [c for c in candidates if str(c.get("task_id", "")) == str(task_id)]
    active = [c for c in candidates if str(c.get("status", "")) == "ACTIVE"]
    if not active:
        raise contracts.ContractError("no active verification contract; supply the original request explicitly")
    if len(active) > 1:
        raise contracts.ContractError(
            "more than one active contract matches; disambiguate explicitly, refusing to choose"
        )
    return active[0]


def ensure_contract(state: dict, *, task_text: str, task_id: str = "") -> dict:
    from .acceptance import contract as contract_module

    digest = contract_module.source_digest(task_text, task_id=task_id)
    existing = contract_module.for_task(state, task_id) if task_id else contract_module.contracts_for(state)
    for row in existing:
        if str(row.get("status", "")) == "ACTIVE" and str(row.get("source_digest", "")) == digest:
            return row
    # supersede stale active contracts for the same task before creating
    if task_id:
        for row in contract_module.for_task(state, task_id):
            if str(row.get("status", "")) == "ACTIVE":
                contract_module.supersede(state, str(row.get("contract_id", "")), by="ar-224-verify")
    return contract_module.create(state, text=task_text, task_id=task_id)


def ensure_requirements(state: dict, *, contract_record: Mapping[str, Any], task_text: str) -> list[dict]:
    from .acceptance import requirements as requirements_module

    contract_id = str(contract_record.get("contract_id", ""))
    task_id = str(contract_record.get("task_id", ""))
    existing = requirements_module.requirements_for_contract(state, contract_id)
    active = [r for r in existing if str(r.get("status", "")) == "ACTIVE"]
    if active:
        return active
    parts = requirements_module.split_candidate(task_text)
    if not parts:
        parts = [task_text.strip()]
    out = []
    for part in parts:
        # SUBJECTIVE-looking obligations still become EXPLICIT requirements;
        # human-gate handling is downstream (NEEDS_HUMAN), not here.
        out.append(requirements_module.create(
            state, contract_id=contract_id, text=part,
            kind="FUNCTIONAL", origin="EXPLICIT", task_id=task_id,
        ))
    return out


def ensure_claims(
    state: dict,
    *,
    contract_record: Mapping[str, Any],
    requirements: Sequence[Mapping[str, Any]],
    work_digest: str,
    worker_identity: str = "worker",
    completion_statements: Sequence[str] = (),
) -> list[dict]:
    from .acceptance import claims as claims_module

    contract_id = str(contract_record.get("contract_id", ""))
    task_id = str(contract_record.get("task_id", ""))
    existing = claims_module.current_claims(state, work_digest=work_digest, contract_id=contract_id)
    if existing:
        return existing
    out = []
    if completion_statements:
        for stmt in completion_statements:
            mapped = claims_module.map_to_requirements(stmt, requirements)
            scope = [str(m.get("requirement_id", "")) for m in mapped if m.get("requirement_id")]
            out.extend(claims_module.extract(
                state, actor=worker_identity, statement=stmt, origin="PROSE",
                contract_id=contract_id, work_digest=work_digest, task_id=task_id,
                requirement_scope=scope or None,
            ))
        return out
    for req in requirements:
        out.append(claims_module.create(
            state, actor=worker_identity, statement=f"completed: {req.get('text', '')}",
            claim_type="IMPLEMENTED", origin="STRUCTURED",
            contract_id=contract_id, requirement_ids=[str(req.get("requirement_id", ""))],
            work_digest=work_digest, task_id=task_id,
        ))
    return out


def ensure_evidence(
    state: dict,
    *,
    contract_record: Mapping[str, Any],
    requirements: Sequence[Mapping[str, Any]],
    work_digest: str,
    evidence_kind: str = "RUNTIME",
    observation: str = "",
) -> list[dict]:
    from .acceptance import evidence as evidence_module

    revision = str(contract_record.get("revision", "1"))
    contract_id = str(contract_record.get("contract_id", ""))
    existing = evidence_module.current(state, work_digest=work_digest, contract_revision=revision)
    if existing:
        return existing
    out = []
    for req in requirements:
        # Minimal honest evidence: an engine observation bound to the exact work
        # digest, derived from the contract record. It establishes that work was
        # presented for verification, not that the requirement is satisfied --
        # verdicts therefore stay UNPROVEN until stronger evidence arrives, which
        # is exactly the Claim-Evidence Gap the product must keep visible.
        out.append(evidence_module.record(
            state, kind=evidence_kind, stance="SUPPORTS",
            producer="ar-224-verify", producer_role="engine",
            observation=observation or f"work {work_digest[:12]} presented for verification",
            requirement_ids=[str(req.get("requirement_id", ""))],
            source_record_id=str(contract_record.get("contract_id", "")),
            source_kind="ENGINE_RECORD",
            work_digest=work_digest, contract_revision=revision, contract_id=contract_id,
            task_id=str(contract_record.get("task_id", "")),
        ))
    return out


def verify_task(
    state: dict,
    *,
    task_text: str,
    work_ref: str = "",
    work_digest: str = "",
    task_id: str = "",
    worker_identity: str = "worker",
    completion_statements: Sequence[str] = (),
    independent_review: Mapping[str, Any] | None = None,
    require_independent_review: bool = False,
) -> dict:
    """Outcome-oriented verify: request + work in, Proof Receipt out.

    Delegates every semantic to the AR-223 acceptance engine; this layer only
    constructs the verification model the user must not build by hand.
    """
    from .acceptance import gates as gates_module

    if not str(task_text or "").strip():
        raise contracts.ContractError("verify needs the original request text")
    digest = str(work_digest or "").strip() or work_digest_for(task_text, work_ref)
    if not re.fullmatch(r"[0-9a-f]{16,64}", digest):
        raise contracts.ContractError("work digest must be hex 16-64 chars")
    contract_record = ensure_contract(state, task_text=task_text, task_id=task_id)
    requirements = ensure_requirements(state, contract_record=contract_record, task_text=task_text)
    ensure_claims(
        state, contract_record=contract_record, requirements=requirements,
        work_digest=digest, worker_identity=worker_identity,
        completion_statements=completion_statements,
    )
    ensure_evidence(state, contract_record=contract_record, requirements=requirements, work_digest=digest)
    contract_module_active = contract_record
    pass_record = gates_module.run_pass(
        state, contract_id=str(contract_module_active.get("contract_id", "")),
        work_digest=digest, task_id=str(contract_module_active.get("task_id", "")),
        independent_review=independent_review,
        require_independent_review=require_independent_review,
    )
    receipt = create_receipt_from_pass(
        pass_record, proof_id=next_proof_id(state),
        previous_id=previous_proof_id(state),
    )
    contracts.require_collection_capacity(state, COLLECTION)
    return store_receipt(state, receipt)


# ---------------------------------------------------------- worker handoff

WORKER_HANDOFF_SCHEMA = "ar-224-worker-handoff-1"

WORKER_PRODUCERS = ("codex", "claude-code", "cursor", "opencode", "devin", "boreal", "ci", "human", "custom-agent")


def build_handoff(
    *,
    task_id: str,
    task_text: str,
    work_digest: str,
    worker_identity: str,
    producer: str = "custom-agent",
    completion_claims: Sequence[str] = (),
    evidence_refs: Sequence[str] = (),
) -> dict:
    prod = str(producer or "custom-agent").lower()
    if prod not in WORKER_PRODUCERS:
        raise contracts.ContractError(f"unknown worker producer: {producer!r}")
    if not str(task_text).strip():
        raise contracts.ContractError("worker handoff needs the original task text")
    if not str(work_digest).strip():
        raise contracts.ContractError("worker handoff needs a work digest")
    return {
        "schema_version": WORKER_HANDOFF_SCHEMA,
        "task_id": str(task_id or ""),
        "task_text": str(task_text),
        "work_digest": str(work_digest),
        "worker_identity": str(worker_identity or ""),
        "producer": prod,
        "completion_claims": [str(c) for c in completion_claims or ()],
        "evidence_refs": [str(e) for e in evidence_refs or ()],
        "note": "workers may submit evidence; workers cannot submit acceptance",
    }


def handoff_problems(handoff: Mapping[str, Any]) -> list[str]:
    problems: list[str] = []
    if handoff.get("schema_version") != WORKER_HANDOFF_SCHEMA:
        problems.append("worker handoff schema unsupported")
    if not str(handoff.get("task_text", "")).strip():
        problems.append("worker handoff has no task text")
    if not str(handoff.get("work_digest", "")).strip():
        problems.append("worker handoff has no work digest")
    if str(handoff.get("producer", "")) not in WORKER_PRODUCERS:
        problems.append("worker handoff names an unknown producer")
    if "acceptance" in handoff or "accepted" in handoff:
        problems.append("worker handoff must not carry acceptance")
    return problems
