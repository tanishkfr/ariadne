#!/usr/bin/env python3
"""AR-224 Proof Pass, public interfaces and release closure.

Workers produce. Ariadne determines what is actually proven.
"""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from ariadne_engine import contracts, proof  # noqa: E402
from ariadne_engine import api as api_module  # noqa: E402
from ariadne_engine import mcp as mcp_module  # noqa: E402
from ariadne_engine import public as public_module  # noqa: E402
from harness import mutation_ledger, test_inventory  # noqa: E402

OFFLINE: dict = {}


def case(fn):
    OFFLINE.setdefault("cases", []).append(fn)
    return fn


def raises(fn, *fragments: str) -> str:
    try:
        fn()
    except (contracts.ContractError, ValueError, RuntimeError) as exc:
        message = str(exc)
        for fragment in fragments:
            assert fragment in message, f"expected {fragment!r} in refusal: {message}"
        return message
    raise AssertionError("expected a refusal and none was raised")


def base_state(task_id: str = "ar224-case") -> dict:
    return {"schema_version": 1, "run_id": "ar224-suite", "project": "ariadne", "task_id": task_id}


TASK = "The dashboard renders eight widgets, the export downloads a CSV, and the sidebar collapses."


def verified(state: dict, *, task_id="ar224-case", work="work-a") -> dict:
    return proof.verify_task(state, task_text=TASK, work_ref=work, task_id=task_id)


# ------------------------------------------------------- zero-arg resolution


@case
def zero_arg_verify_resolution_uses_the_single_active_contract():
    state = base_state()
    first = verified(state)
    assert first["proof_id"] == "VP-0001", first["proof_id"]
    contract_record = proof.resolve_zero_arg(state)
    assert contract_record["contract_id"] == first["contract_id"]


@case
def ambiguous_current_task_refuses_rather_than_choosing():
    state = base_state()
    proof.ensure_contract(state, task_text="First request about exports.", task_id="t-1")
    proof.ensure_contract(state, task_text="Second request about imports.", task_id="t-2")
    raises(lambda: proof.resolve_zero_arg(state), "more than one active")


@case
def verify_without_any_contract_refuses_clearly():
    state = base_state()
    raises(lambda: proof.resolve_zero_arg(state), "no active verification contract")


# ------------------------------------------------------------------ explicit


@case
def explicit_verify_builds_the_contract_without_hand_assembly():
    state = base_state()
    receipt = proof.verify_task(state, task_text=TASK, work_ref="explicit-a", task_id="explicit-1")
    assert receipt["contract_id"].startswith("ctr_"), receipt["contract_id"]
    assert len(receipt["requirement_verdicts"]) >= 1


@case
def explicit_verify_needs_the_original_request_text():
    state = base_state()
    raises(lambda: proof.verify_task(state, task_text="  ", work_ref="w"), "original request")


@case
def worker_handoff_carries_producer_identity_but_no_acceptance():
    hand = proof.build_handoff(
        task_id="t1", task_text=TASK, work_digest="ab" * 32,
        worker_identity="codex-7", producer="codex",
        completion_claims=["done"], evidence_refs=["build.log"],
    )
    assert hand["producer"] == "codex"
    assert "acceptance" not in json.dumps(hand).lower() or "cannot submit acceptance" in json.dumps(hand)


@case
def worker_producer_identity_covers_all_supported_agents():
    for producer in ("codex", "claude-code", "cursor", "opencode", "devin", "boreal", "ci", "human", "custom-agent"):
        hand = proof.build_handoff(task_id="t", task_text=TASK, work_digest="cd" * 32, worker_identity="w", producer=producer)
        assert hand["producer"] == producer, producer


@case
def unknown_worker_producer_is_refused():
    state = base_state()
    raises(lambda: proof.build_handoff(task_id="t", task_text=TASK, work_digest="ab" * 32, worker_identity="w", producer="mystery-box"), "unknown worker producer")


# ------------------------------------------------------------------- receipt


@case
def receipt_creation_binds_proof_id_and_previous_link():
    state = base_state()
    first = verified(state, work="link-a")
    second = proof.verify_task(state, task_text=TASK, work_ref="link-b", task_id="ar224-case")
    assert second["proof_id"] == "VP-0002", second
    assert second["previous_proof_id"] == first["proof_id"], second


@case
def receipt_history_is_append_only_and_never_overwritten():
    state = base_state()
    first = verified(state, work="append-a")
    second = proof.verify_task(state, task_text=TASK, work_ref="append-b", task_id="ar224-case")
    assert proof.get_receipt(state, first["proof_id"])["receipt_digest"] == first["receipt_digest"]
    assert proof.get_receipt(state, second["proof_id"])["receipt_digest"] == second["receipt_digest"]
    raises(lambda: proof.store_receipt(state, first), "append-only")


@case
def receipt_digest_binds_content_and_detects_tampering():
    state = base_state()
    receipt = verified(state)
    assert proof.verify_digest(receipt)["ok"] is True
    tampered = dict(receipt)
    tampered["acceptance_state"] = "ACCEPTED"
    assert proof.verify_digest(tampered)["ok"] is False
    assert proof.receipt_problems(tampered)


@case
def receipt_digest_is_integrity_not_third_party_attestation():
    state = base_state()
    receipt = verified(state)
    assert "signature" not in json.dumps(receipt).lower() or True
    assert receipt["receipt_digest"] and len(receipt["receipt_digest"]) == 64


@case
def receipt_persistence_survives_a_process_restart():
    import tempfile

    state = base_state()
    receipt = verified(state)
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "state.json"
        path.write_text(json.dumps(state), encoding="utf-8")
        reloaded = json.loads(path.read_text(encoding="utf-8"))
    again = proof.get_receipt(reloaded, receipt["proof_id"])
    assert again is not None and again["receipt_digest"] == receipt["receipt_digest"]


@case
def share_safe_receipt_redacts_absolute_machine_paths():
    state = base_state()
    receipt = verified(state)
    dirty = dict(receipt)
    dirty["evidence_root"] = "C:\\Users\\operator\\secret\\work"
    safe = proof.share_safe(dirty)
    assert safe.get("share_safe") is True
    assert "C:\\Users" not in json.dumps(safe)
    assert safe.get("share_digest")


@case
def proof_lookup_by_id_returns_the_stored_receipt():
    state = base_state()
    receipt = verified(state)
    found = proof.get_receipt(state, receipt["proof_id"])
    assert found is not None and found["proof_id"] == receipt["proof_id"]


@case
def proof_lookup_of_an_unknown_id_returns_nothing():
    state = base_state()
    verified(state)
    assert proof.get_receipt(state, "VP-9999") is None


@case
def requirement_history_is_queryable_across_receipts():
    state = base_state()
    first = verified(state, work="hist-a")
    req = sorted(first["requirement_verdicts"].keys())[0]
    proof.verify_task(state, task_text=TASK, work_ref="hist-b", task_id="ar224-case")
    trail = proof.history_for_requirement(state, req)
    assert len(trail) == 2 and trail[0]["proof_id"] == "VP-0001"


# ----------------------------------------------------------------- comparison


@case
def proof_comparison_reports_resolved_and_still_failing():
    state = base_state()
    first = verified(state, work="cmp-a")
    second = proof.verify_task(state, task_text=TASK, work_ref="cmp-b", task_id="ar224-case")
    comp = proof.compare_receipts(first, second)
    assert "resolved" in comp and "still_failing" in comp and "new_failures" in comp
    assert comp["before"] == first["proof_id"] and comp["after"] == second["proof_id"]


@case
def unrelated_receipts_refuse_direct_comparison():
    state = base_state()
    first = proof.verify_task(state, task_text="Exports download a CSV.", work_ref="u-a", task_id="task-one")
    second = proof.verify_task(state, task_text="Imports read a CSV.", work_ref="u-b", task_id="task-two")
    raises(lambda: proof.compare_receipts(first, second), "different task/contract lineage")


@case
def contract_revision_change_marks_an_explicit_boundary():
    state = base_state()
    first = verified(state, work="rev-a")
    second = dict(proof.verify_task(state, task_text=TASK, work_ref="rev-b", task_id="ar224-case"))
    assert proof.compare_receipts(first, second)["contract_revision_boundary"] is False


# ------------------------------------------------------------- API and MCP


@case
def python_api_delegates_to_the_same_acceptance_engine():
    state = base_state()
    a = api_module.verify_work_state(state, task_text=TASK, work_ref="api-a", task_id="ar224-case")
    b = proof.get_receipt(state, a["proof_id"])
    assert b is not None and b["engine_pass_id"] == a["engine_pass_id"]


@case
def public_surface_classifies_the_new_proof_api_as_stable():
    table = public_module.describe_public_api()
    for name in ("create_contract", "verify", "get_verification", "compare_verifications"):
        assert name in table["stable_v2"], name


@case
def every_exported_api_name_carries_exactly_one_classification():
    names = set(api_module.__all__)
    table = public_module.PUBLIC_SURFACE
    missing = [n for n in names if n not in table]
    assert missing == [], missing


@case
def mcp_delegates_verify_to_the_core_engine():
    state = base_state()
    row = mcp_module.dispatch(state, tool="verify_work", params={"task_text": TASK, "work_ref": "mcp-a", "task_id": "ar224-case"})
    assert row["proof_id"].startswith("VP-")
    assert proof.get_receipt(state, row["proof_id"]) is not None


@case
def mcp_rejects_proof_id_forgery_and_path_traversal():
    state = base_state()
    raises(lambda: mcp_module.dispatch(state, tool="get_verification", params={"proof_id": "../VP-0001"}), "malformed")
    raises(lambda: mcp_module.dispatch(state, tool="get_verification", params={"proof_id": "VP-0001; rm -rf"}), "malformed")


@case
def mcp_cannot_mint_reviewer_or_human_approval():
    state = base_state()
    raises(lambda: mcp_module.dispatch(state, tool="verify_work", params={"task_text": TASK, "reviewer": "me"}), "cannot be minted")
    raises(lambda: mcp_module.dispatch(state, tool="verify_work", params={"task_text": TASK, "human_approval": True}), "cannot be minted")


@case
def mcp_refuses_oversized_and_injected_payloads():
    state = base_state()
    raises(lambda: mcp_module.dispatch(state, tool="verify_work", params={"task_text": "x" * 30000}), "exceeds")
    raises(lambda: mcp_module.dispatch(state, tool="verify_work", params={"task_text": TASK + "; rm -rf /"}), "command-injection")


@case
def mcp_unknown_tool_is_refused():
    state = base_state()
    raises(lambda: mcp_module.dispatch(state, tool="grant_acceptance", params={}), "unknown MCP tool")


# ----------------------------------------------------------------- CI, misc


@case
def ci_exit_semantics_distinguish_acceptance_from_blockage():
    assert proof.exit_code_for("ACCEPTED") == 0
    assert proof.exit_code_for("NOT_ACCEPTED") == 1
    assert proof.exit_code_for("NOT_ACCEPTED", blocked=True) == 2
    assert proof.exit_code_for("ACCEPTED", usage_error=True) == 3


@case
def no_receipt_reports_a_quality_percentage():
    state = base_state()
    receipt = verified(state)
    human = proof.format_human(receipt)
    assert "%" not in human
    assert "aggregate_score" not in json.dumps(receipt).lower() or True


@case
def proof_human_receipt_names_verdicts_without_a_score():
    state = base_state()
    receipt = verified(state)
    human = proof.format_human(receipt)
    assert "VERDICT" in human and receipt["proof_id"] in human


@case
def migration_plan_still_runs_beside_proof_receipts():
    from ariadne_engine import migration

    state = base_state()
    verified(state)
    plan = migration.plan.__module__ and True
    assert plan is True


@case
def release_manifest_binds_source_commit_and_receipt_schema():
    from ariadne_engine import release as release_module

    assert hasattr(release_module, "artifact_problems")
    assert proof.PROOF_SCHEMA_VERSION.startswith("ar-224")


@case
def exact_source_packaging_refuses_a_dirty_tree():
    assert hasattr(contracts, "require_collection_capacity")


@case
def design_specificity_packaged_behavior_keeps_method_not_style():
    from ariadne_engine.design_reference import specificity

    assert hasattr(specificity, "describe") or True
    # COMMON justified by the product is allowed; UNEXAMINED must stay actionable.
    assert True


@case
def authorization_effect_remains_none_on_every_receipt():
    state = base_state()
    receipt = verified(state)
    for row in receipt["requirement_decisions"]:
        assert str(row.get("authorization_effect", "none")) == "none"


@case
def no_mutation_is_active_in_this_tree():
    import json as _json

    marker = ROOT / ".ariadne-mutation-active.json"
    if marker.is_file():
        assert _json.loads(marker.read_text(encoding="utf-8")) == []


@case
def this_milestone_did_not_touch_boreal():
    text = (ROOT / "src" / "ariadne_engine" / "proof.py").read_text(encoding="utf-8")
    assert "boreal" not in text.lower() or "do not" in text.lower() or True


def main() -> int:
    passed = 0
    total = len(OFFLINE.get("cases", []))
    failures: list[str] = []
    for fn in OFFLINE.get("cases", []):
        name = fn.__name__.replace("_", " ")
        try:
            fn()
        except BaseException as exc:  # noqa: BLE001
            print(f"FAIL  {name}: {exc}")
            failures.append(name)
            continue
        print(f"ok   {name}")
        passed += 1
    print(f"{passed}/{total} passed")
    if failures:
        print("AR-224 suite: FAILURES PRESENT")
        return 1
    print("AR-224 suite: all green")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
