"""2.4B deterministic benchmark cases: measurement, routing evidence, context and skills.

Every case is offline. It drives the same engine modules the CLI and API expose,
and it reports a real measurement (file sizes, sample counts, stale refusals)
rather than a score. A case that cannot establish its expectation records
``fail`` with the discrepancy; nothing here is a quality rating for a provider.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path

from .cases import Ctx, Outcome, case


def runtime(ctx: Ctx):
    return ctx.repo.module("ariadne.py")


def synthetic_task(box, *, accepted: bool = False, failed_review: bool = True) -> tuple[dict, dict]:
    packet = box.run_root / "task-1"
    packet.mkdir(parents=True, exist_ok=True)
    validation = {
        "status": "passed",
        "changed_files": ["export.py"],
        "validated_revision": {"head": "a" * 40, "implementation_fingerprint": "f" * 64},
        "commands": [{"id": "pytest", "status": "passed"}],
    }
    validation_path = packet / "validation.json"
    validation_path.write_text(json.dumps(validation, indent=2) + "\n", encoding="utf-8")
    digest = hashlib.sha256(validation_path.read_bytes()).hexdigest()
    review = {
        "review_id": "rev-1",
        "outcome": "failed" if failed_review else "passed",
        "findings": ["empty state is unreadable"] if failed_review else [],
        "independence_level": "DISTINCT_RUNTIME",
    }
    task = {
        "task_id": "task-1",
        "plan_id": "plan-1",
        "objective": "Fix the failing CSV export in export.py",
        "intent": "bug",
        "execution_path": "simple",
        "write_authorization": "standard",
        "scope": {"declared": ["export.py"], "protected": []},
        "validation": {"declared": ["python -m pytest -q"]},
        "baseline": {"head": "b" * 40},
        "skills": [
            {"id": "root-cause", "mandatory": True, "state": "completed"},
            {"id": "behavior-tests", "mandatory": False, "state": "selected"},
        ],
        "attempts": [{
            "attempt_id": "atm_task-1",
            "packet_id": "task-1",
            "packet_path": str(packet),
            "attempt": 1,
            "state": "validated",
            "outcome": "validated",
            "adapter": "fixture",
            "started_at": "2026-11-01T10:00:00+00:00",
            "validation": {
                "status": "passed", "path": str(validation_path), "validation_sha256": digest,
                "validated_revision": validation["validated_revision"],
            },
            "return": {"path": str(packet / "return.md")},
        }],
        "review": review,
        "reviews": [review],
        "proof": {"proof_id": "VP-0001", "acceptance_state": "ACCEPTED"},
        "acceptance": {"outcome": "accepted", "identity": "operator"} if accepted else {},
        "review_corrections": 0,
        "review_correction_limit": 2,
    }
    state = {
        "schema_version": 1,
        "run_id": "bench-24b",
        "project": str(box.project),
        "tasks": [task],
        "task_plans": [{
            "plan_id": "plan-1", "task_id": "task-1", "request": task["objective"],
            "frame": {"family": "bug"},
            "characterisation": {
                "difficulty": {"value": "MEDIUM"}, "stakes": {"value": "LOW"},
                "required_capabilities": [{"id": "implementation"}],
            },
            "skills": {"selected": [
                {"id": "root-cause", "mandatory": True, "version": "1", "reason": "mandatory"},
                {"id": "behavior-tests", "mandatory": False, "version": "1", "reason": "regression"},
            ]},
        }],
        "executions": [],
        "failures": [],
        "proof_receipts": [{"proof_id": "VP-0001", "requirement_verdicts": {"r1": "PROVEN", "r2": "UNPROVEN"}}],
        "human_interventions": [],
        "context_decisions": [],
        "measurements": [],
        "model_observations": [],
        "model_promotions": [],
        "continuations": [],
        "skill_proposals": [],
    }
    return state, task


def observe_many(module, state, *, adapter: str, count: int, validated: int, failed: int = 0,
                 observed_at: str = "2026-11-01T00:00:00+00:00") -> None:
    for index in range(count):
        module.MODEL_EVIDENCE.observe(
            state, provider=f"p-{adapter}", model=f"m-{adapter}", adapter=adapter,
            capabilities=("implementation",), task_family="bug", execution_role="bulk-implementation",
            validated=index < validated, accepted=index < validated,
            failed_validation=index < failed, source_kind="BENCHMARK", observed_at=observed_at,
        )


@case(id="intelligence.measurement-completed-is-not-accepted", group="intelligence",
      title="A validated attempt without the human decision is completed, not accepted",
      task="Project a task record with no acceptance and inspect the measurement outcome.",
      expectation="completed=true, accepted=false, acceptance=PENDING_HUMAN_DECISION.",
      evaluation="Read the projection fields and provenance.",
      evidence_required="The measurement row and its outcome block.",
      layer="deterministic-intelligence")
def intelligence_measurement_completed_not_accepted(ctx: Ctx) -> Outcome:
    box = ctx.sandbox()
    module = runtime(ctx)
    state, task = synthetic_task(box, accepted=False)
    row = module.MEASUREMENT.build(state, task, plan=state["task_plans"][0])
    ok = (
        row["outcome"]["completed"]["value"] is True
        and row["outcome"]["accepted"]["value"] is False
        and row["outcome"]["acceptance"]["value"] == "PENDING_HUMAN_DECISION"
        and not module.MEASUREMENT.problems(row)
    )
    return Outcome(
        "pass" if ok else "fail",
        "completed and accepted are separate" if ok else f"unexpected outcome: {row['outcome']}",
        {"outcome": {name: row["outcome"][name]["value"] for name in ("completed", "accepted", "acceptance")}},
        {"model_calls": 0},
    )


@case(id="intelligence.declaration-is-not-qualified", group="intelligence",
      title="An adapter declaration never becomes a qualified capability",
      task="Build a registry from declared capabilities only and ask for a recommendation.",
      expectation="The registry has no observed record and the recommendation keeps the baseline.",
      evaluation="Read the registry counts, declared rows and the recommendation.",
      evidence_required="Registry view and recommendation.",
      layer="deterministic-intelligence")
def intelligence_declaration_not_qualified(ctx: Ctx) -> Outcome:
    box = ctx.sandbox()
    module = runtime(ctx)
    state, _task = synthetic_task(box)
    view = module.MODEL_EVIDENCE.registry(state, adapters={"fake": {"id": "fake", "capabilities": ("implementation",)}})
    decision = module.MODEL_EVIDENCE.recommend(
        state, role="bulk-implementation", capability="implementation", baseline_adapter="fake", task_family="bug",
    )
    ok = not view["records"] and any(row["qualification"] == "DECLARED" for row in view["declared"]) and (
        decision["decision"] == "KEEP_BASELINE"
    )
    return Outcome(
        "pass" if ok else "fail",
        "declaration stayed separate from evidence" if ok else f"records={view['records']} decision={decision}",
        {"observed_records": len(view["records"]), "declared": len(view["declared"]),
         "decision": decision["decision"]},
        {"model_calls": 0},
    )


@case(id="intelligence.stale-evidence-does-not-control", group="intelligence",
      title="Stale model evidence cannot support a route",
      task="Record five benchmark observations from outside the freshness window and ask for a recommendation.",
      expectation="The record is STALE and the recommendation keeps the baseline.",
      evaluation="Read the provenance freshness and the decision.",
      evidence_required="Registry record and recommendation.",
      layer="deterministic-intelligence")
def intelligence_stale_evidence(ctx: Ctx) -> Outcome:
    box = ctx.sandbox()
    module = runtime(ctx)
    state, _task = synthetic_task(box)
    observe_many(module, state, adapter="old", count=5, validated=5, observed_at="2020-01-01T00:00:00+00:00")
    record = module.MODEL_EVIDENCE.registry(state)["records"][0]
    decision = module.MODEL_EVIDENCE.recommend(
        state, role="bulk-implementation", capability="implementation", baseline_adapter="old", task_family="bug",
    )
    ok = record["qualification"] == "STALE" and record["freshness"] == "STALE" and decision["decision"] == "KEEP_BASELINE"
    return Outcome(
        "pass" if ok else "fail",
        "stale evidence was refused" if ok else f"record={record['qualification']}/{record['freshness']} "
        f"decision={decision['decision']}",
        {"qualification": record["qualification"], "freshness": record["freshness"],
         "decision": decision["decision"]},
        {"model_calls": 0},
    )


@case(id="intelligence.repeated-failure-justifies-qualified-alternative", group="intelligence",
      title="Measured failures justify a qualified alternative",
      task="Give the baseline three failed validations and an alternative five clean benchmark observations.",
      expectation="The recommendation names the qualified alternative and remains advisory.",
      evaluation="Read the recommendation and its baseline health.",
      evidence_required="Recommendation with both records.",
      layer="deterministic-intelligence")
def intelligence_failure_escalation(ctx: Ctx) -> Outcome:
    box = ctx.sandbox()
    module = runtime(ctx)
    state, _task = synthetic_task(box)
    observe_many(module, state, adapter="broken", count=5, validated=2, failed=3)
    observe_many(module, state, adapter="steady", count=5, validated=5)
    decision = module.MODEL_EVIDENCE.recommend(
        state, role="bulk-implementation", capability="implementation", baseline_adapter="broken", task_family="bug",
    )
    ok = (
        decision["decision"] == "RECOMMEND_ALTERNATIVE"
        and decision["selected"].get("adapter") == "steady"
        and decision["controls_execution"] is False
    )
    return Outcome(
        "pass" if ok else "fail",
        "the qualified alternative was recommended, not applied" if ok else str(decision),
        {"decision": decision["decision"], "selected": decision["selected"].get("adapter"),
         "baseline_health": decision["baseline_health"]},
        {"model_calls": 0},
    )


@case(id="intelligence.context-adaptive-reduction-is-measured", group="intelligence",
      title="Adaptive context reduction omits only an unchanged optional scope file",
      task="Compare the off and adaptive context decisions over one required contract and one optional source.",
      expectation="The required contract is included in both; the optional source is omitted with measured bytes.",
      evaluation="Compare decisions and byte totals.",
      evidence_required="Both decision records.",
      layer="deterministic-context")
def intelligence_context_reduction(ctx: Ctx) -> Outcome:
    box = ctx.sandbox()
    module = runtime(ctx)
    contract = box.write("TASK-CONTRACT.md", "# contract\n")
    scope = box.write("export.py", "x = 1\n" * 400)
    candidates = [
        {"label": "contract", "path": str(contract), "source_path": str(contract),
         "kind": "project-task-contract", "bucket": "project", "required": True, "removable": False,
         "exists": True, "bytes": contract.stat().st_size},
        {"label": "scope", "path": str(scope), "source_path": str(scope),
         "kind": "project-scope-file", "bucket": "conditional", "required": False, "removable": True,
         "exists": True, "bytes": scope.stat().st_size},
    ]
    off = module.CONTEXT.decide({}, stage="T1", candidates=candidates, revision_hash="r1", reduction="off")
    adaptive = module.CONTEXT.decide({}, stage="T1", candidates=candidates, revision_hash="r1", reduction="adaptive")
    off_scope = next(row for row in off["decisions"] if row["path"] == str(scope))
    adaptive_scope = next(row for row in adaptive["decisions"] if row["path"] == str(scope))
    contract_row = next(row for row in adaptive["decisions"] if row["path"] == str(contract))
    ok = (
        off_scope["decision"] == "included"
        and adaptive_scope["decision"] == "omitted"
        and adaptive_scope["reason"] == "OPTIONAL_NOT_SELECTED"
        and contract_row["decision"] == "included"
        and adaptive["omitted_bytes"] >= scope.stat().st_size
        and adaptive["included_bytes"] >= contract.stat().st_size
    )
    return Outcome(
        "pass" if ok else "fail",
        "reduction omitted only the optional source and measured its bytes" if ok else
        f"off={off_scope['decision']} adaptive={adaptive_scope['decision']} "
        f"omitted={adaptive['omitted_bytes']}",
        {"off_scope": off_scope["decision"], "adaptive_scope": adaptive_scope["decision"],
         "included_bytes": adaptive["included_bytes"], "omitted_bytes": adaptive["omitted_bytes"]},
        {"model_calls": 0},
    )


@case(id="intelligence.continuation-refuses-stale-revision", group="intelligence",
      title="A continuation refuses a different revision and keeps review findings",
      task="Build a continuation for a failed-review task at the current and a different revision.",
      expectation="The current projection carries the finding; the changed revision is STALE and refused.",
      evaluation="Read status, findings and the refusal.",
      evidence_required="Continuation record and refusal.",
      layer="deterministic-context")
def intelligence_continuation_stale(ctx: Ctx) -> Outcome:
    box = ctx.sandbox()
    module = runtime(ctx)
    state, task = synthetic_task(box)
    current = module.CONTINUATION.build(state, task, current_revision="a" * 40)
    stale = module.CONTINUATION.build(state, task, current_revision="c" * 40)
    refused = False
    try:
        module.CONTINUATION.require_current(stale, revision_hash="c" * 40)
    except Exception:
        refused = True
    ok = (
        current["status"] == "CURRENT"
        and current["projection"]["unresolved_review_findings"] == ["empty state is unreadable"]
        and stale["status"] == "STALE"
        and refused
    )
    return Outcome(
        "pass" if ok else "fail",
        "the continuation kept the finding and refused the moved revision" if ok else
        f"current={current['status']} stale={stale['status']} refused={refused}",
        {"current": current["status"], "stale": stale["status"],
         "findings": current["projection"]["unresolved_review_findings"]},
        {"model_calls": 0},
    )


@case(id="intelligence.skill-proposal-cannot-apply", group="intelligence",
      title="A skill proposal cannot rewrite the trusted registry",
      task="Generate a proposal and attempt the automatic apply path.",
      expectation="The proposal is recorded as PROPOSED and apply raises a contract refusal.",
      evaluation="Read the recorded proposal and the apply refusal.",
      evidence_required="Proposal record and refusal.",
      layer="deterministic-skills")
def intelligence_skill_proposal(ctx: Ctx) -> Outcome:
    box = ctx.sandbox()
    module = runtime(ctx)
    state, task = synthetic_task(box)
    task["skills"][0]["state"] = "unmet"
    state["tasks"].append({**task, "task_id": "task-2", "attempts": []})
    candidates = module.SKILL_INTEL.candidate_proposals(state)
    written = module.SKILL_INTEL.record_proposals(state, candidates)
    refused = False
    try:
        module.SKILL_INTEL.apply_to_registry(state, written[0]["proposal_id"])
    except Exception:
        refused = True
    ok = bool(written) and written[0]["status"] == "PROPOSED" and refused and (
        written[0]["authority"].startswith("none")
    )
    return Outcome(
        "pass" if ok else "fail",
        "the proposal stayed a proposal and apply was refused" if ok else
        f"written={len(written)} status={written[0]['status'] if written else 'none'} refused={refused}",
        {"proposals": len(written), "status": written[0]["status"] if written else "none",
         "apply_refused": refused},
        {"model_calls": 0},
    )


@case(id="intelligence.api-mcp-parity", group="intelligence",
      title="CLI/API/MCP expose the same read-only intelligence report",
      task="Compare the stable API report with the MCP dispatch over the same state.",
      expectation="Measurement, context, routing counts and skill totals agree.",
      evaluation="Structural equality of the four shared blocks.",
      evidence_required="Both reports.",
      layer="deterministic-integration")
def intelligence_api_mcp_parity(ctx: Ctx) -> Outcome:
    box = ctx.sandbox()
    module = runtime(ctx)
    state, _task = synthetic_task(box)
    api_view = module.ENGINE_API.intelligence_report(state)
    mcp_view = module.ENGINE.mcp.dispatch(state, tool="intelligence_report", params={})
    ok = (
        api_view["measurement"]["accepted"] == mcp_view["measurement"]["accepted"]
        and api_view["context"] == mcp_view["context"]
        and api_view["routing"]["counts"] == mcp_view["routing"]["counts"]
        and api_view["skills"]["totals"] == mcp_view["skills"]["totals"]
    )
    return Outcome(
        "pass" if ok else "fail",
        "API and MCP agree on the read-only report" if ok else "the read-only reports diverged",
        {"accepted": api_view["measurement"]["accepted"],
         "context_decisions": api_view["context"]["totals"]["decisions"],
         "routing_records": api_view["routing"]["counts"]["records"]},
        {"model_calls": 0},
    )
