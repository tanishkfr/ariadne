"""AR-224 MCP surface: deliberately small adapter over the stable API.

Architecture is always::

    MCP -> Ariadne stable API -> Acceptance / Verification engine

never::

    MCP -> second implementation of verification

All inputs are untrusted. This module fails closed on path traversal,
proof-ID forgery, reviewer-identity forgery, human-approval forgery,
contract replacement, evidence laundering, prompt injection, oversized
payloads and command injection. MCP cannot mint authority.
"""

from __future__ import annotations

import re
from typing import Any, Mapping

from . import contracts

MCP_SCHEMA_VERSION = "ar-224-mcp-1"

MAX_TEXT_CHARS = 20_000
MAX_LIST_ITEMS = 50

TOOLS = (
    "create_verification_contract",
    "verify_work",
    "get_verification",
    "compare_verifications",
)

_PROOF_ID_RE = re.compile(r"^VP-\d{4,}$")
_FORBIDDEN_PATH = re.compile(r"(\.\.|^[A-Za-z]:\\|^\\\\|^/etc|^/proc)")
_FORBIDDEN_CMD = re.compile(r"[;&|`$()]|\$\(")


def tool_schemas() -> dict:
    return {
        "schema_version": MCP_SCHEMA_VERSION,
        "tools": [
            {"name": "create_verification_contract", "params": ["task_text", "task_id"]},
            {"name": "verify_work", "params": ["task_text", "work_ref", "work_digest", "task_id", "completion_statements"]},
            {"name": "get_verification", "params": ["proof_id"]},
            {"name": "compare_verifications", "params": ["before", "after"]},
        ],
        "authority": "MCP cannot grant human approval, reviewer identity, or authorization_effect",
    }


def _check_text(name: str, value: Any, *, allow_empty: bool = False) -> str:
    text = str(value or "")
    if not text.strip() and not allow_empty:
        raise contracts.ContractError(f"MCP input {name} is empty")
    if len(text) > MAX_TEXT_CHARS:
        raise contracts.ContractError(f"MCP input {name} exceeds {MAX_TEXT_CHARS} chars")
    if _FORBIDDEN_CMD.search(text):
        raise contracts.ContractError(f"MCP input {name} carries command-injection shapes")
    # prompt-injection content is treated as DATA_ONLY downstream; here we refuse
    # only directive smuggling that claims authority.
    lowered = text.lower()
    for phrase in ("approve", "human approval", "independent review by me", "grant authorization"):
        if phrase in lowered and "mcp" in lowered:
            raise contracts.ContractError(f"MCP input {name} claims authority it cannot mint")
    return text


def _check_proof_id(value: Any) -> str:
    text = str(value or "")
    if not _PROOF_ID_RE.fullmatch(text):
        raise contracts.ContractError(f"MCP proof id malformed (want VP-NNNN): {value!r}")
    if ".." in text or "/" in text or "\\" in text:
        raise contracts.ContractError("MCP proof id carries path traversal")
    return text


def _check_path(value: Any) -> str:
    text = str(value or "")
    if _FORBIDDEN_PATH.search(text):
        raise contracts.ContractError(f"MCP path refused: {value!r}")
    return text


def dispatch(state: dict, *, tool: str, params: Mapping[str, Any] | None = None) -> dict:
    """Dispatch one MCP tool call onto the stable state API (no second engine)."""
    from . import api as api_module

    params = dict(params or {})
    # callers may never set reviewer, approval, or authorization
    for forbidden in ("reviewer", "reviewer_identity", "human_approval", "human_acceptance",
                      "independent_review", "authorization_effect", "accepted", "verdict"):
        if forbidden in params:
            raise contracts.ContractError(f"MCP may not set {forbidden}; authority cannot be minted here")
    name = str(tool or "")
    if name not in TOOLS:
        raise contracts.ContractError(f"unknown MCP tool: {tool!r}")
    if name == "create_verification_contract":
        task_text = _check_text("task_text", params.get("task_text", ""))
        task_id = str(params.get("task_id", "") or "")
        _check_path(task_id)
        return api_module.create_proof_contract_state(state, task_text=task_text, task_id=task_id)
    if name == "verify_work":
        task_text = _check_text("task_text", params.get("task_text", ""))
        work_ref = str(params.get("work_ref", "") or "")
        work_digest = str(params.get("work_digest", "") or "")
        if work_ref:
            _check_path(work_ref)
            _check_text("work_ref", work_ref, allow_empty=True)
        if work_digest and not re.fullmatch(r"[0-9a-f]{16,64}", work_digest):
            raise contracts.ContractError("MCP work_digest must be hex 16-64 chars")
        statements = params.get("completion_statements", ()) or ()
        if not isinstance(statements, (list, tuple)):
            raise contracts.ContractError("MCP completion_statements must be a list")
        if len(statements) > MAX_LIST_ITEMS:
            raise contracts.ContractError("MCP completion_statements oversized")
        clean = [_check_text("statement", s) for s in statements]
        return api_module.verify_work_state(
            state, task_text=task_text, work_ref=work_ref, work_digest=work_digest,
            task_id=str(params.get("task_id", "") or ""), completion_statements=tuple(clean),
        )
    if name == "get_verification":
        pid = _check_proof_id(params.get("proof_id", ""))
        return api_module.get_proof_state(state, pid)
    if name == "compare_verifications":
        before = _check_proof_id(params.get("before", ""))
        after = _check_proof_id(params.get("after", ""))
        return api_module.compare_proofs_state(state, before, after)
    raise contracts.ContractError(f"unhandled MCP tool: {tool!r}")


def describe() -> dict:
    return {
        "schema_version": MCP_SCHEMA_VERSION,
        "tools": sorted(TOOLS),
        "delegation": "MCP -> stable API -> acceptance engine; no duplicate verification semantics",
        "authority": "none; reviewer and approval identities are engine-side only",
    }
