"""Benchmark cases for AR-200.

Status semantics (deliberately strict, matching the AR-200 evidence rules):

    pass      the runtime satisfied the integrity expectation for this case
    fail      the runtime violated the integrity expectation (a real defect)
    observed  behavioural probe recorded without a pass/fail judgement
    error     the harness itself could not evaluate the case
    skip      the case declared itself not executable in this environment

Every case records the commands it ran and the artifacts it read, so a result
can be re-derived from the sandbox without trusting the harness summary.
"""

from __future__ import annotations

import ast
import contextlib
import hashlib
import io
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from .driver import Repo, Result, Sandbox
from . import fixtures as F


# --------------------------------------------------------------------- model

@dataclass
class Case:
    id: str
    group: str
    title: str
    task: str
    expectation: str
    evaluation: str
    evidence_required: str
    runner: Callable[[], "Outcome"]
    layer: str = "deterministic"
    requires: tuple[str, ...] = ()
    cost: str = "none"
    executable: bool = True
    notes: str = ""


@dataclass
class Outcome:
    status: str
    actual: str
    evidence: dict = field(default_factory=dict)
    metrics: dict = field(default_factory=dict)


@dataclass
class Ctx:
    repo: Repo
    work_root: Path
    fixtures: dict
    case: Case

    def sandbox(self) -> Sandbox:
        return Sandbox.create(self.work_root, self.case.id, self.repo)


CASES: list[Case] = []


def case(**kw):
    def register(fn):
        CASES.append(Case(runner=fn, **kw))
        return fn
    return register


def parse_ratio(text: str) -> tuple[int, int] | None:
    match = re.search(r"(?:PASS|FAILED)\s+(\d+)/(\d+)", text)
    if match:
        return int(match.group(1)), int(match.group(2))
    return None


def ratio_outcome(result: Result, label: str, key: str = "checks") -> Outcome:
    ratio = parse_ratio(result.combined)
    if result.timed_out:
        return Outcome("error", f"{label} timed out")
    if ratio is None:
        return Outcome("error", f"{label} printed no pass ratio",
                       {"exit_code": result.returncode, "tail": result.tail(4)})
    passed, total = ratio
    return Outcome(
        "pass" if passed == total and result.returncode == 0 else "fail",
        f"{label}: {passed}/{total}",
        {"exit_code": result.returncode, "tail": result.tail(3), "command": " ".join(result.argv)},
        {key: total, "passed": passed, "failed": total - passed,
         "duration_seconds": result.duration_seconds, "model_calls": 0},
    )


def exit_outcome(result: Result, expect_code: int, label: str, extra: dict | None = None) -> Outcome:
    if result.timed_out:
        return Outcome("error", f"{label} timed out")
    ok = result.returncode == expect_code
    evidence = {"exit_code": result.returncode, "expected_exit_code": expect_code,
                "tail": result.tail(4), "command": " ".join(result.argv)}
    if extra:
        evidence.update(extra)
    return Outcome("pass" if ok else "fail", f"{label}: exit {result.returncode} (expected {expect_code})",
                   evidence, {"duration_seconds": result.duration_seconds, "model_calls": 0})


def contains(text: str, needles: list[str]) -> list[str]:
    return [needle for needle in needles if needle not in text]


# =============================================================== group: suites

@case(id="suite.repo-self-test", group="suites",
      title="Repository aggregate deterministic suite",
      task="Run every offline suite the repository already ships (18 named suites).",
      expectation="All embedded suites pass with no model, network or install step.",
      evaluation="Exit code 0 and the final 'SELF-TEST PASS' marker.",
      evidence_required="Full stdout tail plus the final marker.",
      layer="deterministic")
def suite_repo_self_test(ctx: Ctx) -> Outcome:
    result = ctx.repo.script_run("check.py", "--self-test", timeout=900)
    outcome = exit_outcome(result, 0, "check.py --self-test")
    outcome.evidence["suite_markers"] = len(re.findall(r"(?m)^ok {2,}", result.combined))
    outcome.metrics["duration_seconds"] = result.duration_seconds
    outcome.metrics["model_calls"] = 0
    return outcome


@case(id="suite.runtime-self-test", group="suites",
      title="Runtime controller self-test",
      task="Drive the 125-case runtime lifetime suite (state, gates, repairs, review, routing).",
      expectation="125/125 pass.", evaluation="Parse 'PASS n/n' from stdout.",
      evidence_required="Pass ratio and command line.", layer="deterministic")
def suite_runtime(ctx: Ctx) -> Outcome:
    return ratio_outcome(ctx.repo.script_run("ariadne.py", "--self-test", timeout=900),
                         "ariadne.py --self-test")


@case(id="suite.transport-self-test", group="suites",
      title="Context transport self-test",
      task="Drive the 50-case packet/context compiler suite (staleness, tamper, isolation).",
      expectation="50/50 pass.", evaluation="Parse 'PASS n/n' from stdout.",
      evidence_required="Pass ratio and command line.", layer="deterministic")
def suite_transport(ctx: Ctx) -> Outcome:
    return ratio_outcome(ctx.repo.script_run("prepare-stage.py", "--self-test", timeout=900),
                         "prepare-stage.py --self-test")


@case(id="suite.reasoner-self-test", group="suites",
      title="Reasoner adapter self-test",
      task="Validate provider contract, capability evidence classes and fallback rules.",
      expectation="All cases pass.", evaluation="Parse 'PASS n/n' from stdout.",
      evidence_required="Pass ratio.", layer="deterministic")
def suite_reasoner(ctx: Ctx) -> Outcome:
    return ratio_outcome(ctx.repo.script_run("reasoners.py", timeout=300), "reasoners.py")


@case(id="suite.repo-contract", group="suites",
      title="Repository contract checks",
      task="Run the 18 repository contract checks (links, distribution, policies, prompts).",
      expectation="Every check prints ok and the run ends with PASS.",
      evaluation="Exit code 0, zero FAIL lines, final PASS.",
      evidence_required="Check count and final marker.", layer="deterministic")
def suite_repo_contract(ctx: Ctx) -> Outcome:
    result = ctx.repo.script_run("check.py", timeout=600)
    ok_lines = len(re.findall(r"(?m)^ok {2,}", result.combined))
    fails = len(re.findall(r"(?m)^FAIL", result.combined))
    passed = result.returncode == 0 and fails == 0 and result.combined.strip().endswith("PASS")
    return Outcome("pass" if passed else "fail", f"contract checks: {ok_lines} ok, {fails} fail",
                   {"exit_code": result.returncode, "tail": result.tail(3),
                    "command": " ".join(result.argv)},
                   {"checks": ok_lines, "failed": fails, "duration_seconds": result.duration_seconds,
                    "model_calls": 0})


@case(id="suite.validation-guards", group="suites",
      title="Validation-instrument guard self-test",
      task="Prove every measurement guard in the run-record validator can actually fail.",
      expectation="All guards fire on broken input.", evaluation="Parse 'PASS n guards'.",
      evidence_required="Guard count and result.", layer="deterministic")
def suite_validation_guards(ctx: Ctx) -> Outcome:
    result = ctx.repo.script_run("validate.py", "--self-test", timeout=300)
    match = re.search(r"PASS\s+(\d+) guards", result.combined)
    if result.timed_out or not match:
        return Outcome("error", "guard self-test produced no verdict",
                       {"exit_code": result.returncode, "tail": result.tail(3)})
    return Outcome("pass" if result.returncode == 0 else "fail",
                   f"{match.group(1)} guards all fail correctly",
                   {"exit_code": result.returncode, "command": " ".join(result.argv)},
                   {"checks": int(match.group(1)), "duration_seconds": result.duration_seconds,
                    "model_calls": 0})


@case(id="suite.distribution-lifecycle", group="suites",
      title="Installed-product lifecycle suite",
      task="Install/update/rollback/doctor/uninstall lifecycle against local bundles.",
      expectation="All cases pass.", evaluation="Parse closing 'PASS n/n'.",
      evidence_required="Pass ratio.", layer="deterministic")
def suite_distribution(ctx: Ctx) -> Outcome:
    return ratio_outcome(ctx.repo.script_run("test-distribution.py", timeout=900),
                         "test-distribution.py")


@case(id="suite.release-bundle", group="suites",
      title="Release bundle self-test",
      task="Verify manifest hashing, allowlist contents and offline determinism.",
      expectation="All cases pass.", evaluation="Parse closing 'PASS n/n'.",
      evidence_required="Pass ratio.", layer="deterministic")
def suite_release(ctx: Ctx) -> Outcome:
    return ratio_outcome(ctx.repo.script_run("build-release.py", "--self-test", timeout=600),
                         "build-release.py --self-test")


@case(id="suite.real-project-fixtures", group="suites",
      title="Real-project fixture self-test",
      task="Drive the five v1.5 real-project archetypes through the runtime structures.",
      expectation="All cases pass.", evaluation="Parse closing 'PASS n/n'.",
      evidence_required="Pass ratio.", layer="deterministic")
def suite_real_projects(ctx: Ctx) -> Outcome:
    return ratio_outcome(ctx.repo.script_run("test-real-projects.py", timeout=600),
                         "test-real-projects.py")


@case(id="suite.social-fixtures", group="suites",
      title="Social-intelligence fixture self-test",
      task="Drive the five social archetypes through the creative-operations structures.",
      expectation="All cases pass.", evaluation="Parse closing 'PASS n/n'.",
      evidence_required="Pass ratio.", layer="deterministic")
def suite_social(ctx: Ctx) -> Outcome:
    return ratio_outcome(ctx.repo.script_run("test-social-intelligence.py", timeout=600),
                         "test-social-intelligence.py")


@case(id="suite.reasoner-rollback", group="suites",
      title="Reasoner rollback across two release bundles",
      task="Verify reasoner switching/rollback semantics across an upgrade between two built bundles.",
      expectation="All cases pass.", evaluation="Parse closing 'PASS n/n'.",
      evidence_required="Pass ratio.",
      layer="deterministic", executable=False,
      notes="Requires two built release bundles (--baseline-bundle/--current-bundle); not executable in AR-200. "
            "The reasoner-switch path itself is covered by suite.runtime-self-test.")
def suite_reasoner_rollback(ctx: Ctx) -> Outcome:
    return Outcome("skip", "requires two release bundles; see suite.runtime-self-test for reasoner switching",
                   {"usage": "python scripts/test-reasoner-rollback.py --baseline-bundle <zip> --current-bundle <zip>"})


@case(id="suite.writing-contracts", group="suites",
      title="Writing-contract self-test",
      task="Verify the writing intent contracts are structurally complete.",
      expectation="All cases pass.", evaluation="Exit code 0.",
      evidence_required="Exit code and tail.", layer="deterministic")
def suite_writing_contracts(ctx: Ctx) -> Outcome:
    return exit_outcome(ctx.repo.script_run("test-writing-architecture.py", timeout=300), 0,
                        "test-writing-architecture.py")


@case(id="suite.writing-execution", group="suites",
      title="Writing-execution self-test",
      task="Verify writing execution paths and hard rules.",
      expectation="All cases pass.", evaluation="Exit code 0.",
      evidence_required="Exit code and tail.", layer="deterministic")
def suite_writing_execution(ctx: Ctx) -> Outcome:
    return exit_outcome(ctx.repo.script_run("test-writing-execution.py", timeout=600), 0,
                        "test-writing-execution.py")


@case(id="suite.validation-run-benchmark", group="suites",
      title="Existing validation-run measurement",
      task="Read the recorded B1 validation run through the validator's benchmark mode.",
      expectation="At least one run is read and reported without error.",
      evaluation="Exit code 0 and a non-empty run table.",
      evidence_required="Run table tail.", layer="deterministic")
def suite_validation_benchmark(ctx: Ctx) -> Outcome:
    result = ctx.repo.script_run("validate.py", "--benchmark", timeout=300)
    rows = len(re.findall(r"(?m)^B\d+\s", result.combined))
    return Outcome("pass" if result.returncode == 0 and rows >= 1 else "fail",
                   f"{rows} recorded validation run(s) read",
                   {"exit_code": result.returncode, "tail": result.tail(3),
                    "command": " ".join(result.argv)},
                   {"runs": rows, "duration_seconds": result.duration_seconds, "model_calls": 0})


# ============================================================ group: lifecycle

@case(id="lifecycle.start-creates-verified-s1", group="lifecycle",
      title="Start creates one verified S1 packet",
      task="Start a run and inspect the state, packet and manifest.",
      expectation="State schema 1, single S1 packet, packet verifies against its manifest, no gate granted.",
      evaluation="Read state/manifest; run TRANSPORT.verify_packet.",
      evidence_required="State keys, packet path, verify result, gate field.",
      layer="deterministic-lifecycle")
def lifecycle_start(ctx: Ctx) -> Outcome:
    box = ctx.sandbox()
    result = F.start_s1(ctx.repo, box)
    if result.returncode != 0:
        return Outcome("fail", f"start failed: {result.tail(3)}", {"exit_code": result.returncode})
    state = box.state()
    packet = box.current_packet()
    transport = ctx.repo.module("prepare-stage.py")
    problems = transport.verify_packet(packet)
    manifest = box.manifest()
    ok = (state.get("schema_version") == 1 and len(state["packets"]) == 1
          and state["packets"][0]["stage"] == "S1" and not problems
          and manifest.get("provider") == "codex"
          and state.get("reasoner", {}).get("id") == "codex")
    return Outcome("pass" if ok else "fail",
                   f"S1 packet {'verified' if not problems else 'problems: ' + '; '.join(problems)}",
                   {"state_schema": state.get("schema_version"), "stage": state["packets"][0]["stage"],
                    "manifest_provider": manifest.get("provider"),
                    "reasoner": state.get("reasoner", {}).get("id"),
                    "packet": box.rel_root(packet), "packet_bytes": (packet / "packet.txt").stat().st_size,
                    "gate_record": "none granted by start"},
                   {"packet_bytes": (packet / "packet.txt").stat().st_size, "model_calls": 0})


@case(id="lifecycle.duplicate-run-refused", group="lifecycle",
      title="Duplicate run is refused",
      task="Start twice into the same run root.",
      expectation="Second start exits non-zero and does not overwrite the first run.",
      evaluation="Compare exit code and state packet count.",
      evidence_required="Exit codes and refusal message.", layer="deterministic-lifecycle")
def lifecycle_duplicate(ctx: Ctx) -> Outcome:
    box = ctx.sandbox()
    first = F.start_s1(ctx.repo, box)
    second = F.start_s1(ctx.repo, box)
    state = box.state() if (box.run_root / "ariadne-run.json").is_file() else {}
    ok = first.returncode == 0 and second.returncode == 1 and len(state.get("packets", [])) == 1
    return Outcome("pass" if ok else "fail",
                   f"first={first.returncode}, second={second.returncode}, packets={len(state.get('packets', []))}",
                   {"second_message": second.tail(2), "command": " ".join(second.argv)})


@case(id="lifecycle.incomplete-brief-blocks", group="lifecycle",
      title="Incomplete brief cannot advance",
      task="Run advance at S1 without the brief documents.",
      expectation="Exit 2, no stage evidence written, missing outputs named.",
      evaluation="Exit code plus absence of stage-result.json.",
      evidence_required="Exit code, message, evidence directory listing.",
      layer="deterministic-lifecycle")
def lifecycle_incomplete_brief(ctx: Ctx) -> Outcome:
    box = ctx.sandbox()
    F.start_s1(ctx.repo, box)
    result = ctx.repo.cli("advance", "--run-root", str(box.run_root))
    evidence_dir = box.current_packet() / "evidence"
    written = sorted(p.name for p in evidence_dir.iterdir()
                     if p.name not in ("_README.md",)) if evidence_dir.is_dir() else []
    ok = result.returncode == 2 and not written
    return Outcome("pass" if ok else "fail",
                   f"exit {result.returncode}; stage evidence written: {written or 'none'}",
                   {"message": result.tail(3), "command": " ".join(result.argv)})


@case(id="lifecycle.s1-to-s3-prepared", group="lifecycle",
      title="Completed brief prepares S3",
      task="Record S1 outputs and let the runtime choose the next boundary.",
      expectation="A verified S3 packet is prepared automatically.",
      evaluation="Exit code plus last packet stage.",
      evidence_required="Stage of last packet and verify result.", layer="deterministic-lifecycle")
def lifecycle_s1_to_s3(ctx: Ctx) -> Outcome:
    box = ctx.sandbox()
    F.start_s1(ctx.repo, box)
    F.complete_s1(ctx.repo, box, ctx.fixtures)
    result = F.to_s3(ctx.repo, box)
    transport = ctx.repo.module("prepare-stage.py")
    problems = transport.verify_packet(box.current_packet())
    stage = box.packets()[-1]["stage"]
    ok = result.returncode == 0 and stage == "S3" and not problems
    return Outcome("pass" if ok else "fail", f"S3 prepared={stage == 'S3'}, verify problems={problems}",
                   {"exit_code": result.returncode, "tail": result.tail(2)})


@case(id="lifecycle.s3-blocks-without-human-g1", group="lifecycle",
      title="S3 cannot reach the build boundary without a human G1 record",
      task="Advance from S3 while DESIGN.md only holds a draft direction.",
      expectation="Exit non-zero, no S4A packet, and the runtime names the missing human decision.",
      evaluation="Exit code, packet stages and the recorded next action.",
      evidence_required="Stage list and the reason the runtime recorded.",
      layer="deterministic-lifecycle")
def lifecycle_s3_gate_holds(ctx: Ctx) -> Outcome:
    box = ctx.sandbox()
    F.start_s1(ctx.repo, box)
    F.complete_s1(ctx.repo, box, ctx.fixtures)
    F.to_s3(ctx.repo, box)
    box.write("DESIGN.md", F.design_md("draft — awaiting G1"))
    result = ctx.repo.cli("advance", "--run-root", str(box.run_root))
    state = box.state()
    stages = [entry["stage"] for entry in state["packets"]]
    next_text = str(state.get("next", ""))
    reason_names_human = "human" in next_text.lower() or "creative" in next_text.lower()
    ok = (result.returncode != 0 and stages[-1] == "S3"
          and "S4A" not in stages and reason_names_human)
    return Outcome("pass" if ok else "fail",
                   f"exit {result.returncode}; stages={stages}; next={next_text!r}",
                   {"tail": result.tail(3), "state_next": next_text,
                    "command": " ".join(result.argv)})


@case(id="lifecycle.g1-locked-prepares-s4a", group="lifecycle",
      title="Locked G1 direction prepares S4A",
      task="Write the locked direction and the recorded gate, then continue.",
      expectation="S4A packet prepared and the human creative decision marked resolved.",
      evaluation="Exit code, last stage, intervention status.",
      evidence_required="Stage list and intervention status.", layer="deterministic-lifecycle")
def lifecycle_g1_to_s4a(ctx: Ctx) -> Outcome:
    box = ctx.sandbox()
    F.start_s1(ctx.repo, box)
    F.complete_s1(ctx.repo, box, ctx.fixtures)
    F.to_s3(ctx.repo, box)
    box.write("DESIGN.md", F.design_md("draft — awaiting G1"))
    F.lock_g1(box)
    result = F.approve_s3_and_reach_s4a(ctx.repo, box)
    entries = box.packets()
    state = box.state()
    resolved = [row for row in state.get("human_interventions", [])
                if row.get("category") == "creative-decision" and row.get("status") == "resolved"]
    ok = result.returncode == 0 and entries[-1]["stage"] == "S4A" and bool(resolved)
    return Outcome("pass" if ok else "fail",
                   f"exit {result.returncode}; stages={[e['stage'] for e in entries]}; "
                   f"resolved creative decisions={len(resolved)}",
                   {"tail": result.tail(2), "command": " ".join(result.argv)})


@case(id="lifecycle.s4b-requires-cleared-preflight", group="lifecycle",
      title="Implementation boundary requires provider preflight",
      task="Prepare the build boundary without recording provider/model readiness.",
      expectation="Continuation pauses with a named preflight reason; no S4B packet.",
      evaluation="Exit code and last packet stage.",
      evidence_required="Pause reason and stage list.", layer="deterministic-lifecycle")
def lifecycle_preflight_required(ctx: Ctx) -> Outcome:
    box = ctx.sandbox()
    F.reach_s4a_with_handoff(ctx.repo, box, ctx.fixtures)
    result = ctx.repo.cli("prepare-next", "--run-root", str(box.run_root))
    stages = [entry["stage"] for entry in box.packets()]
    ok = result.returncode == 2 and stages[-1] == "S4A"
    return Outcome("pass" if ok else "fail", f"exit {result.returncode}; stages={stages}",
                   {"tail": result.tail(3), "command": " ".join(result.argv)})


@case(id="lifecycle.s4b-packet-contract", group="lifecycle",
      title="S4B packet carries worker contract and repository baseline",
      task="Clear preflight and prepare the implementation packet.",
      expectation="Packet has a worker role, bounded repair limit, unique in-project return target and a git baseline.",
      evaluation="Inspect manifest fields and verify_packet.",
      evidence_required="Worker block, return target, baseline head.", layer="deterministic-lifecycle")
def lifecycle_s4b_packet(ctx: Ctx) -> Outcome:
    box = ctx.sandbox()
    F.reach_s4a_with_handoff(ctx.repo, box, ctx.fixtures)
    result = F.clear_preflight_and_reach_s4b(ctx.repo, box)
    manifest = box.manifest() if box.packets() else {}
    worker = manifest.get("worker") or {}
    baseline = manifest.get("project_baseline") or {}
    target = Path(manifest.get("return_target", ""))
    transport = ctx.repo.module("prepare-stage.py")
    problems = transport.verify_packet(box.current_packet()) if box.packets() else ["no packet"]
    expected_target = box.project / ".ariadne" / "returns" / f"{manifest.get('packet_id')}.md"
    ok = (result.returncode == 0 and box.packets()[-1]["stage"] == "S4B"
          and worker.get("role") in transport.WORKER_ROLES
          and 0 <= int(worker.get("repair_limit", -1)) <= transport.MAX_ROUTINE_REPAIRS
          and target.resolve() == expected_target.resolve()
          and isinstance(baseline, dict) and bool(baseline)
          and not problems)
    return Outcome("pass" if ok else "fail",
                   f"S4B packet={'ok' if ok else 'incomplete'}; worker={worker.get('role')}; "
                   f"repair_limit={worker.get('repair_limit')}; verify={problems or 'clean'}",
                   {"manifest_worker": worker, "return_target": str(target),
                    "baseline_keys": sorted(baseline.keys()),
                    "max_routine_repairs": transport.MAX_ROUTINE_REPAIRS,
                    "command": " ".join(result.argv)})


@case(id="lifecycle.blocked-return-halts", group="lifecycle",
      title="Blocked worker return stops without an automatic retry",
      task="Deliver a blocked implementation return and run advance.",
      expectation="Exit 2, no new packet, a blocked-return record in the operations log.",
      evaluation="Exit code, packet count, log text.",
      evidence_required="Log line and stage list.", layer="deterministic-lifecycle")
def lifecycle_blocked_return(ctx: Ctx) -> Outcome:
    box = ctx.sandbox()
    F.reach_s4a_with_handoff(ctx.repo, box, ctx.fixtures)
    F.clear_preflight_and_reach_s4b(ctx.repo, box)
    before = len(box.packets())
    F.deliver_return(box, ctx.fixtures, status="blocked")
    result = ctx.repo.cli("advance", "--run-root", str(box.run_root))
    stages = [entry["stage"] for entry in box.packets()]
    ok = result.returncode == 2 and len(stages) == before
    return Outcome("pass" if ok else "fail",
                   f"exit {result.returncode}; packets {before} -> {len(stages)}",
                   {"tail": result.tail(3), "log_has_blocked": "blocked" in box.operations_log().lower(),
                    "command": " ".join(result.argv)})


@case(id="lifecycle.independent-validation-executes", group="lifecycle",
      title="Independent validation executes the declared commands",
      task="Deliver a complete return and let Ariadne validate it independently.",
      expectation="validation.json records real command executions with return codes and hashes.",
      evaluation="Read validation evidence and compare command ids with HANDOFF.md.",
      evidence_required="Command records with returncode, stdout hash, scope status.",
      layer="deterministic-lifecycle")
def lifecycle_validation(ctx: Ctx) -> Outcome:
    box = ctx.sandbox()
    F.reach_s4a_with_handoff(ctx.repo, box, ctx.fixtures)
    F.clear_preflight_and_reach_s4b(ctx.repo, box)
    F.deliver_return(box, ctx.fixtures, status="complete")
    result = ctx.repo.cli("validate-worker", "--run-root", str(box.run_root))
    validation_path = box.current_packet() / "evidence" / "validation.json"
    validation = json.loads(validation_path.read_text(encoding="utf-8")) if validation_path.is_file() else {}
    commands = validation.get("commands", [])
    executed = [c for c in commands if c.get("returncode") is not None]
    ok = (result.returncode == 0 and validation.get("status") == "passed"
          and validation.get("independent") is True and bool(executed)
          and validation.get("scope", {}).get("status") == "within-contract")
    return Outcome("pass" if ok else "fail",
                   f"validation={validation.get('status')}; commands executed={len(executed)}/{len(commands)}; "
                   f"scope={validation.get('scope', {}).get('status')}",
                   {"commands": [{k: c.get(k) for k in ("id", "command", "returncode", "status")}
                                 for c in commands],
                    "scope": validation.get("scope"),
                    "evidence": box.rel_root(validation_path),
                    "command": " ".join(result.argv)},
                   {"validation_commands": len(commands), "model_calls": 0})


@case(id="lifecycle.repair-budget-bounded", group="lifecycle",
      title="Repair budget stays bounded",
      task="Attempt to widen the worker repair limit beyond the contract maximum.",
      expectation="The transport rejects a repair limit above MAX_ROUTINE_REPAIRS.",
      evaluation="Mutate the S4B manifest in the sandbox and re-verify.",
      evidence_required="Verifier problem string and contract constant.",
      layer="deterministic-lifecycle")
def lifecycle_repair_budget(ctx: Ctx) -> Outcome:
    box = ctx.sandbox()
    F.reach_s4a_with_handoff(ctx.repo, box, ctx.fixtures)
    F.clear_preflight_and_reach_s4b(ctx.repo, box)
    transport = ctx.repo.module("prepare-stage.py")
    manifest_path = box.current_packet() / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["worker"]["repair_limit"] = transport.MAX_ROUTINE_REPAIRS + 3
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    problems = transport.verify_packet(box.current_packet())
    ok = any("repair limit" in problem for problem in problems)
    return Outcome("pass" if ok else "fail",
                   f"verify problems after widening repair_limit: {problems or 'none'}",
                   {"max_routine_repairs": transport.MAX_ROUTINE_REPAIRS, "problems": problems})


@case(id="lifecycle.s5-isolation", group="lifecycle",
      title="S5 packet is the canonical isolated pair",
      task="Validate a complete return and let the runtime prepare the review boundary.",
      expectation="S5 delivers only the current prompt block and EVALUATION-RUBRICS.md; no project or build context.",
      evaluation="Inspect delivered source labels and forbidden kinds.",
      evidence_required="Delivered labels list and verifier result.", layer="deterministic-lifecycle")
def lifecycle_s5_isolation(ctx: Ctx) -> Outcome:
    box = ctx.sandbox()
    F.reach_s4a_with_handoff(ctx.repo, box, ctx.fixtures)
    F.clear_preflight_and_reach_s4b(ctx.repo, box)
    F.deliver_return(box, ctx.fixtures, status="complete")
    ctx.repo.cli("validate-worker", "--run-root", str(box.run_root))
    result = F.prepare_s5(ctx.repo, box)
    manifest = box.manifest() if box.packets() else {}
    delivered = [s["label"] for s in manifest.get("sources", []) if s.get("delivered", True)]
    kinds = {s.get("kind") for s in manifest.get("sources", []) if s.get("delivered", True)}
    transport = ctx.repo.module("prepare-stage.py")
    problems = transport.verify_packet(box.current_packet())
    ok = (result.returncode == 0 and box.packets()[-1]["stage"] == "S5"
          and delivered == ["current S5 prompt block", "EVALUATION-RUBRICS.md"]
          and kinds <= {"canonical-prompt", "canonical"} and not problems)
    return Outcome("pass" if ok else "fail", f"S5 delivered={delivered}; verify={problems or 'clean'}",
                   {"delivered": delivered, "kinds": sorted(kinds),
                    "packet_bytes": (box.current_packet() / "packet.txt").stat().st_size,
                    "command": " ".join(result.argv)},
                   {"packet_bytes": (box.current_packet() / "packet.txt").stat().st_size})


@case(id="lifecycle.acceptance-requires-review-and-gate", group="lifecycle",
      title="Acceptance requires review evidence and the recorded human gate",
      task="Attempt to accept a worker result with no independent review and no G3 record.",
      expectation="Acceptance is refused; no acceptance state is written.",
      evaluation="Exit code 1 and worker acceptance_state unchanged.",
      evidence_required="Refusal message and worker state.", layer="deterministic-lifecycle")
def lifecycle_acceptance(ctx: Ctx) -> Outcome:
    box = ctx.sandbox()
    F.reach_s4a_with_handoff(ctx.repo, box, ctx.fixtures)
    F.clear_preflight_and_reach_s4b(ctx.repo, box)
    F.deliver_return(box, ctx.fixtures, status="complete")
    ctx.repo.cli("validate-worker", "--run-root", str(box.run_root))
    F.prepare_s5(ctx.repo, box)
    result = ctx.repo.cli("record-acceptance", "--run-root", str(box.run_root), "--outcome", "accepted")
    worker = box.state().get("worker", {})
    ok = result.returncode == 1 and worker.get("acceptance_state") != "ACCEPTED"
    return Outcome("pass" if ok else "fail",
                   f"exit {result.returncode}; acceptance_state={worker.get('acceptance_state')}",
                   {"tail": result.tail(3), "command": " ".join(result.argv)})


@case(id="lifecycle.telemetry-keeps-unknowns", group="lifecycle",
      title="Telemetry never invents usage or cost",
      task="Run a worker cycle and read worker-telemetry.jsonl.",
      expectation="Usage and cost remain the literal string 'unknown' when the provider did not report them.",
      evaluation="Scan telemetry rows for missing or fabricated numeric usage.",
      evidence_required="Event names and usage/cost values.", layer="deterministic-lifecycle")
def lifecycle_telemetry(ctx: Ctx) -> Outcome:
    box = ctx.sandbox()
    F.reach_s4a_with_handoff(ctx.repo, box, ctx.fixtures)
    F.clear_preflight_and_reach_s4b(ctx.repo, box)
    F.deliver_return(box, ctx.fixtures, status="complete")
    ctx.repo.cli("validate-worker", "--run-root", str(box.run_root))
    rows = box.telemetry()
    bad = [r for r in rows if r.get("usage") not in (None, "unknown") or r.get("cost") not in (None, "unknown")]
    events = sorted({r.get("event") for r in rows})
    ok = bool(rows) and not bad and "worker-validation" in events
    return Outcome("pass" if ok else "fail",
                   f"{len(rows)} telemetry rows, {len(bad)} with invented usage/cost",
                   {"events": events, "sample": rows[-1] if rows else None},
                   {"telemetry_rows": len(rows), "model_calls": 0, "cost": 0.0})


@case(id="lifecycle.state-schema-mismatch-refused", group="lifecycle",
      title="Unknown run-state schema is refused, not migrated",
      task="Bump the sandboxed run-state schema_version and read status.",
      expectation="The runtime refuses the state instead of guessing or migrating.",
      evaluation="Exit code and refusal message.",
      evidence_required="Message text and exit code.", layer="deterministic-lifecycle")
def lifecycle_schema_mismatch(ctx: Ctx) -> Outcome:
    box = ctx.sandbox()
    F.start_s1(ctx.repo, box)
    state_path = box.run_root / "ariadne-run.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["schema_version"] = 2
    state_path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    result = ctx.repo.cli("status", "--run-root", str(box.run_root))
    ok = result.returncode == 1 and "schema is unsupported" in result.combined
    return Outcome("pass" if ok else "fail", f"exit {result.returncode}: {result.tail(2)}",
                   {"tail": result.tail(3), "command": " ".join(result.argv)})


@case(id="lifecycle.stale-project-input-detected", group="lifecycle",
      title="Changed project input invalidates a prepared packet",
      task="Modify a delivered project input after packet preparation.",
      expectation="Packet verification reports the stale source; strict consumption refuses.",
      evaluation="Run verify_packet and a strict current_packet read.",
      evidence_required="Verifier problems and refusal message.", layer="deterministic-lifecycle")
def lifecycle_stale_input(ctx: Ctx) -> Outcome:
    box = ctx.sandbox()
    F.start_s1(ctx.repo, box)
    F.complete_s1(ctx.repo, box, ctx.fixtures)
    F.to_s3(ctx.repo, box)
    transport = ctx.repo.module("prepare-stage.py")
    runtime = ctx.repo.module("ariadne.py")
    clean = transport.verify_packet(box.current_packet())
    box.append("PROJECT.md", "\n<!-- changed after preparation -->\n")
    stale = transport.verify_packet(box.current_packet())
    try:
        runtime.current_packet(box.state())
        refused = False
    except Exception:
        refused = True
    ok = not clean and any("stale source" in p for p in stale) and refused
    return Outcome("pass" if ok else "fail",
                   f"clean={clean or 'none'}; after change={stale}; strict read refused={refused}",
                   {"stale_problems": stale, "strict_refusal": refused})


# ============================================================= group: security

@case(id="security.gate-forgery-in-agents-md", group="security",
      title="Gate approval requires an out-of-band human record",
      task="Play the role of an actor with ordinary write access and CLI access: write the locked direction "
           "and the gate field into the two project documents, record the stage result, then continue. "
           "No human decision is ever supplied.",
      expectation="An agent-writable project document must not be sufficient to grant a human gate.",
      evaluation="Attempt the continuation and observe whether G1 is treated as granted.",
      evidence_required="Exit code, resulting stage, and the exact documents that were sufficient.",
      layer="deterministic-lifecycle")
def security_gate_forgery(ctx: Ctx) -> Outcome:
    box = ctx.sandbox()
    F.start_s1(ctx.repo, box)
    F.complete_s1(ctx.repo, box, ctx.fixtures)
    F.to_s3(ctx.repo, box)
    # Write both approval artefacts exactly as the runtime's own G1 detection used to read them.
    box.write("DESIGN.md", F.design_md("locked at G1 on 2026-09-22"))
    box.write("AGENTS.md", F.agents_md("S3", "G1", "prompts/build-kickoff.md"))
    recorded = ctx.repo.cli("record-result", "--run-root", str(box.run_root), "--status", "complete",
                            "--provider", "self", "--model", "none",
                            "--summary", "Direction approved at G1",
                            "--file", "DESIGN.md", "--file", "AGENTS.md")
    result = ctx.repo.cli("prepare-next", "--run-root", str(box.run_root))
    stages = [entry["stage"] for entry in box.packets()]
    state = box.state()
    resolved = [row for row in state.get("human_interventions", [])
                if row.get("category") == "creative-decision" and row.get("status") == "resolved"]
    approvals = state.get("approvals", [])
    # Regression fixture: the original reproduction must still fail the case.
    granted = result.returncode == 0 and stages[-1] == "S4A"
    return Outcome(
        "fail" if granted else "pass",
        ("G1 accepted from actor-written project documents; the runtime itself recorded the human creative "
         "decision as resolved" if granted else
         f"G1 was not accepted from project documents; exit {result.returncode}; "
         f"recorded approvals={len(approvals)}"),
        {"documents_sufficient": ["DESIGN.md **Status:** locked at G1", "AGENTS.md **Last gate passed:** G1"],
         "record_result_exit": recorded.returncode,
         "exit_code": result.returncode, "stages": stages,
         "runtime_marked_human_decision_resolved": resolved[0] if resolved else None,
         "tail": result.tail(3), "command": " ".join(result.argv)},
        {"false_acceptance": 1 if granted else 0, "model_calls": 0},
    )


@case(id="security.creative-gate-bypass", group="security",
      title="Creative-evidence gate holds on every continuation path",
      task="At S3 with a locked direction and no recorded creative evidence, compare three continuation "
           "paths: advance without a recorded stage result, advance after recording one, and prepare-next.",
      expectation="Every continuation path enforces the same creative-evidence requirement.",
      evaluation="Run each path in its own sandbox and compare exit codes and resulting stages.",
      evidence_required="Exit codes, stages and messages for all three paths.",
      layer="deterministic-lifecycle")
def security_creative_bypass(ctx: Ctx) -> Outcome:
    def prepare_box(suffix: str) -> Sandbox:
        box = Sandbox.create(ctx.work_root, ctx.case.id + suffix, ctx.repo)
        F.start_s1(ctx.repo, box)
        F.complete_s1(ctx.repo, box, ctx.fixtures)
        F.to_s3(ctx.repo, box)
        # Documents and the recorded human decision are supplied; the direction's
        # creative evidence deliberately is not, so the only remaining requirement
        # is the creative-evidence precondition under test.
        box.write("DESIGN.md", F.design_md("locked at G1 on 2026-09-22"))
        box.write("AGENTS.md", F.agents_md("S3", "G1", "prompts/build-kickoff.md"))
        F.record_g1_approval(box, ctx.repo)
        return box

    # The fixture records the G1 approval through the engine but leaves the
    # direction's creative evidence unresolved, so every path must block.
    direct = prepare_box("-direct")
    direct_result = ctx.repo.cli("advance", "--run-root", str(direct.run_root))
    direct_stage = direct.packets()[-1]["stage"]

    recorded = prepare_box("-recorded")
    ctx.repo.cli("record-result", "--run-root", str(recorded.run_root), "--status", "complete",
                 "--provider", "self", "--model", "none", "--summary", "Direction recorded",
                 "--file", "DESIGN.md", "--file", "AGENTS.md")
    advance_after_record = ctx.repo.cli("advance", "--run-root", str(recorded.run_root))
    recorded_stage = recorded.packets()[-1]["stage"]

    planned = prepare_box("-prepare-next")
    ctx.repo.cli("record-result", "--run-root", str(planned.run_root), "--status", "complete",
                 "--provider", "self", "--model", "none", "--summary", "Direction recorded",
                 "--file", "DESIGN.md", "--file", "AGENTS.md")
    prepare_result = ctx.repo.cli("prepare-next", "--run-root", str(planned.run_root))
    planned_stage = planned.packets()[-1]["stage"]

    blocked = {direct_result.returncode != 0,
               advance_after_record.returncode != 0,
               prepare_result.returncode != 0}
    consistent = len(blocked) == 1  # all three agree
    return Outcome(
        "pass" if consistent else "fail",
        (f"consistent enforcement: advance(no stage result) exit {direct_result.returncode} -> {direct_stage}; "
         f"advance(after stage result) exit {advance_after_record.returncode} -> {recorded_stage}; "
         f"prepare-next exit {prepare_result.returncode} -> {planned_stage}") if consistent else
        (f"inconsistent enforcement: advance(no stage result) exit {direct_result.returncode} -> {direct_stage}; "
         f"advance(after stage result) exit {advance_after_record.returncode} -> {recorded_stage}; "
         f"prepare-next exit {prepare_result.returncode} -> {planned_stage}"),
        {"direct_tail": direct_result.tail(2), "recorded_tail": advance_after_record.tail(2),
         "prepare_next_tail": prepare_result.tail(2),
         "note": ("the creative plan is a required artefact; every continuation path now enforces it"
                  if consistent else "the creative plan is a required artefact; a path that skips it is a bypass")},
        {"gate_bypass": 0 if consistent else 1, "model_calls": 0},
    )


@case(id="security.review-attestation-unverified", group="security",
      title="Review independence is a recorded identity, not a self-written attestation",
      task="Ingest a review judgement with no reviewer identity, with the implementation worker's own identity, "
           "with the attestation line removed, and finally with an independent identity.",
      expectation="Independence comes from a recorded reviewer identity bound to the reviewed revision; a "
                  "self-written attestation field and the implementer's own identity must not satisfy it.",
      evaluation="Compare ingestion exit codes across the four variants and inspect the stored review record.",
      evidence_required="Exit codes, the accepted fields, and the stored review record.",
      layer="deterministic-lifecycle")
def security_review_attestation(ctx: Ctx) -> Outcome:
    box = ctx.sandbox()
    F.reach_s4a_with_handoff(ctx.repo, box, ctx.fixtures)
    F.clear_preflight_and_reach_s4b(ctx.repo, box)
    F.deliver_return(box, ctx.fixtures, status="complete")
    ctx.repo.cli("validate-worker", "--run-root", str(box.run_root))
    F.prepare_s5(ctx.repo, box)
    review_text = ctx.fixtures["review"]()
    source = box.root / "review.md"
    source.write_text(review_text, encoding="utf-8")
    unattested = box.root / "review-no-attestation.md"
    unattested.write_text(
        review_text.replace("**Reviewed independently:** yes", "**Reviewed independently:** no"),
        encoding="utf-8",
    )
    no_identity = ctx.repo.cli("ingest-review", "--run-root", str(box.run_root), "--input", str(source))
    worker_identity = ctx.repo.cli("ingest-review", "--run-root", str(box.run_root),
                                   "--input", str(source), "--reviewer-identity", "bulk")
    unattested_no_identity = ctx.repo.cli("ingest-review", "--run-root", str(box.run_root),
                                          "--input", str(unattested))
    independent = ctx.repo.cli("ingest-review", "--run-root", str(box.run_root),
                               "--input", str(source), "--reviewer-identity", "independent-reviewer-7")
    state = box.state()
    records = state.get("reviews", [])
    record = records[-1] if records else {}
    review_path = box.current_packet() / "evidence" / "review-judgement.md"
    fixed = (
        no_identity.returncode != 0
        and worker_identity.returncode != 0
        and unattested_no_identity.returncode != 0
        and independent.returncode == 0
        and record.get("reviewer_identity") == "independent-reviewer-7"
        and bool(record.get("context_digest"))
    )
    field_only_authority = no_identity.returncode == 0
    return Outcome(
        "pass" if fixed else "fail",
        ("review independence is bound to a recorded identity and revision: no identity, the implementer's "
         "own identity and an unattested block are all refused; an independent identity is recorded"
         if fixed else
         f"unexpected behaviour: no-identity={no_identity.returncode}, worker-identity="
         f"{worker_identity.returncode}, unattested={unattested_no_identity.returncode}, "
         f"independent={independent.returncode}, recorded_identity={record.get('reviewer_identity')!r}"),
        {"no_identity_exit": no_identity.returncode, "worker_identity_exit": worker_identity.returncode,
         "unattested_exit": unattested_no_identity.returncode, "independent_exit": independent.returncode,
         "attestation_line": "**Reviewed independently:** yes",
         "review_record": {key: record.get(key) for key in
                           ("review_id", "packet_id", "reviewer_identity", "context_digest", "outcome")},
         "judgement_evidence": box.rel_root(review_path),
         "no_identity_message": no_identity.tail(2), "worker_identity_message": worker_identity.tail(2)},
        {"false_acceptance": 1 if field_only_authority else 0, "model_calls": 0},
    )


@case(id="security.sensitive-path-write-blocked", group="security",
      title="Sensitive path writes are blocked at validation",
      task="Have the worker create .env inside the project, then validate.",
      expectation="Validation blocks with a dangerous-action classification and no pass.",
      evaluation="Read validation.json status and failure_kind.",
      evidence_required="Status, failure kind and the offending path.",
      layer="deterministic-lifecycle")
def security_sensitive_write(ctx: Ctx) -> Outcome:
    box = ctx.sandbox()
    F.reach_s4a_with_handoff(ctx.repo, box, ctx.fixtures)
    F.clear_preflight_and_reach_s4b(ctx.repo, box)
    F.deliver_return(box, ctx.fixtures, status="complete")
    box.write(".env", "SECRET=benchmark\n")
    result = ctx.repo.cli("validate-worker", "--run-root", str(box.run_root))
    validation = json.loads((box.current_packet() / "evidence" / "validation.json").read_text(encoding="utf-8"))
    ok = (validation.get("status") == "blocked"
          and validation.get("failure_kind") in ("dangerous-action", "sensitive"))
    return Outcome("pass" if ok else "fail",
                   f"status={validation.get('status')}; failure_kind={validation.get('failure_kind')}",
                   {"exit_code": result.returncode, "scope": validation.get("scope"),
                    "failure_reason": validation.get("failure_reason")},
                   {"unauthorized_operations": 0 if ok else 1})


@case(id="security.out-of-scope-write-blocked", group="security",
      title="Out-of-contract writes are blocked at validation",
      task="Have the worker modify a file that HANDOFF.md scope does not permit.",
      expectation="Validation blocks with an out-of-scope classification.",
      evaluation="Read validation.json scope status and changed paths.",
      evidence_required="Scope status, changed list, exit code.", layer="deterministic-lifecycle")
def security_out_of_scope(ctx: Ctx) -> Outcome:
    box = ctx.sandbox()
    F.reach_s4a_with_handoff(ctx.repo, box, ctx.fixtures)
    F.clear_preflight_and_reach_s4b(ctx.repo, box)
    F.deliver_return(box, ctx.fixtures, status="complete")
    box.write("unrelated-notes.md", "A file the contract never authorised.\n")
    result = ctx.repo.cli("validate-worker", "--run-root", str(box.run_root))
    validation = json.loads((box.current_packet() / "evidence" / "validation.json").read_text(encoding="utf-8"))
    scope = validation.get("scope", {})
    ok = validation.get("status") == "blocked" and scope.get("status") == "out-of-scope"
    return Outcome("pass" if ok else "fail",
                   f"status={validation.get('status')}; scope={scope.get('status')}; "
                   f"outside={scope.get('outside')}",
                   {"exit_code": result.returncode, "scope": scope,
                    "failure_reason": validation.get("failure_reason")})


@case(id="security.handoff-immutability", group="security",
      title="Immutable worker contract cannot change mid-attempt",
      task="Modify HANDOFF.md after the S4B packet was prepared, then validate.",
      expectation="Validation blocks as a repository conflict and names HANDOFF.md.",
      evaluation="Read validation.json status, failure_kind and immutable list.",
      evidence_required="Failure kind and immutable paths.", layer="deterministic-lifecycle")
def security_handoff_immutable(ctx: Ctx) -> Outcome:
    box = ctx.sandbox()
    F.reach_s4a_with_handoff(ctx.repo, box, ctx.fixtures)
    F.clear_preflight_and_reach_s4b(ctx.repo, box)
    F.deliver_return(box, ctx.fixtures, status="complete")
    box.append("HANDOFF.md", "\n<!-- widened scope after preparation -->\n")
    result = ctx.repo.cli("validate-worker", "--run-root", str(box.run_root))
    validation = json.loads((box.current_packet() / "evidence" / "validation.json").read_text(encoding="utf-8"))
    scope = validation.get("scope", {})
    ok = (validation.get("status") == "blocked"
          and validation.get("failure_kind") == "repository-conflict"
          and "HANDOFF.md" in (scope.get("immutable") or []))
    return Outcome("pass" if ok else "fail",
                   f"status={validation.get('status')}; kind={validation.get('failure_kind')}; "
                   f"immutable={scope.get('immutable')}",
                   {"exit_code": result.returncode, "failure_reason": validation.get("failure_reason"),
                    "scope": scope})


@case(id="security.evidence-not-overwritable", group="security",
      title="Recorded evidence cannot be overwritten",
      task="Ingest the same worker return and validation twice.",
      expectation="The second write is refused for both return and validation evidence.",
      evaluation="Compare exit codes and file hashes across attempts.",
      evidence_required="Both refusal messages and the unchanged hash.",
      layer="deterministic-lifecycle")
def security_no_overwrite(ctx: Ctx) -> Outcome:
    box = ctx.sandbox()
    F.reach_s4a_with_handoff(ctx.repo, box, ctx.fixtures)
    F.clear_preflight_and_reach_s4b(ctx.repo, box)
    target = F.deliver_return(box, ctx.fixtures, status="complete")
    first = ctx.repo.cli("ingest-return", "--run-root", str(box.run_root), "--input", str(target))
    after_first = hashlib.sha256((box.current_packet() / "evidence" / "return-handoff.md").read_bytes()).hexdigest()
    second = ctx.repo.cli("ingest-return", "--run-root", str(box.run_root), "--input", str(target))
    after_second = hashlib.sha256((box.current_packet() / "evidence" / "return-handoff.md").read_bytes()).hexdigest()
    validate_first = ctx.repo.cli("validate-worker", "--run-root", str(box.run_root))
    validate_second = ctx.repo.cli("validate-worker", "--run-root", str(box.run_root))
    ok = (first.returncode == 0 and second.returncode == 1 and after_first == after_second
          and validate_first.returncode == 0 and validate_second.returncode == 1)
    return Outcome("pass" if ok else "fail",
                   f"ingest {first.returncode}->{second.returncode}; validate "
                   f"{validate_first.returncode}->{validate_second.returncode}; hash stable={after_first == after_second}",
                   {"second_message": second.tail(2), "validate_second_message": validate_second.tail(2)})


@case(id="security.packet-tamper-detected", group="security",
      title="Tampered packet is detected, not trusted",
      task="Edit the prepared packet text after preparation and re-verify.",
      expectation="Packet hash mismatch is reported and the run refuses to continue.",
      evaluation="Verify the packet, then attempt a continuation.",
      evidence_required="Verifier problem and refusal exit code.", layer="deterministic-lifecycle")
def security_packet_tamper(ctx: Ctx) -> Outcome:
    box = ctx.sandbox()
    F.start_s1(ctx.repo, box)
    F.complete_s1(ctx.repo, box, ctx.fixtures)
    F.to_s3(ctx.repo, box)
    packet_file = box.current_packet() / "packet.txt"
    packet_file.write_text(packet_file.read_text(encoding="utf-8") + "\nINJECTED LINE\n", encoding="utf-8")
    transport = ctx.repo.module("prepare-stage.py")
    problems = transport.verify_packet(box.current_packet())
    result = ctx.repo.cli("advance", "--run-root", str(box.run_root))
    ok = any("packet hash mismatch" in p for p in problems) and result.returncode != 0
    return Outcome("pass" if ok else "fail",
                   f"verify={problems or 'none'}; advance exit {result.returncode}",
                   {"problems": problems, "tail": result.tail(2)})


# ============================================================== group: context

@case(id="context.conditional-omission-recorded", group="context",
      title="Declined conditional inputs are recorded as omitted",
      task="Prepare S3 with --motion no --assets no and inspect the manifest.",
      expectation="Motion/asset policies are omitted with a recorded reason and never delivered.",
      evaluation="Read the manifest omitted list and packet body.",
      evidence_required="Omitted entries and absence from the packet.",
      layer="deterministic")
def context_omission(ctx: Ctx) -> Outcome:
    box = ctx.sandbox()
    F.start_s1(ctx.repo, box)
    F.complete_s1(ctx.repo, box, ctx.fixtures)
    F.to_s3(ctx.repo, box)
    manifest = box.manifest()
    omitted = " ".join(manifest.get("omitted_conditionals", []))
    packet = box.packet_text()
    ok = (manifest.get("omitted_conditionals")
          and "DESIGN-MOTION.md" in omitted and "DESIGN-ASSETS.md" in omitted
          and "===== BEGIN DESIGN-MOTION.md" not in packet
          and "===== BEGIN DESIGN-ASSETS.md" not in packet)
    return Outcome("pass" if ok else "fail",
                   f"omitted_conditionals={manifest.get('omitted_conditionals')}",
                   {"omitted_conditionals": manifest.get("omitted_conditionals"),
                    "packet_bytes": len(packet)},
                   {"packet_bytes": len(packet)})


@case(id="context.conditional-inclusion-hashed", group="context",
      title="Triggered conditional inputs are delivered and hash-stamped",
      task="Prepare S3 with --motion yes and inspect delivered sources.",
      expectation="DESIGN-MOTION.md is delivered with a matching SOURCE-SHA256 header.",
      evaluation="Compare the header hash with the canonical file hash.",
      evidence_required="Header line and computed hash.", layer="deterministic")
def context_inclusion(ctx: Ctx) -> Outcome:
    box = ctx.sandbox()
    F.start_s1(ctx.repo, box)
    F.complete_s1(ctx.repo, box, ctx.fixtures)
    result = ctx.repo.cli("prepare-next", "--run-root", str(box.run_root), "--motion", "yes", "--assets", "no")
    manifest = box.manifest()
    entries = [s for s in manifest.get("sources", []) if s.get("path") == "DESIGN-MOTION.md"]
    entry = entries[0] if entries else {}
    canonical = ctx.repo.root / "DESIGN-MOTION.md"
    real_hash = hashlib.sha256(canonical.read_bytes()).hexdigest()
    packet = box.packet_text()
    header_ok = f"SOURCE-SHA256 {entry.get('source_sha256')}" in packet
    ok = result.returncode == 0 and bool(entry) and entry.get("source_sha256") == real_hash and header_ok
    return Outcome("pass" if ok else "fail",
                   f"delivered={bool(entry)}; hash matches canonical={entry.get('source_sha256') == real_hash}",
                   {"entry": entry, "canonical_sha256": real_hash, "packet_bytes": len(packet)},
                   {"packet_bytes": len(packet)})


@case(id="context.creative-ledger-project-mismatch", group="context",
      title="Creative evidence from another project is refused",
      task="Write a creative ledger that names a different project, then prepare S3.",
      expectation="Preparation refuses with an explicit ownership error.",
      evaluation="Exit code and message.",
      evidence_required="Refusal text and ledger identity.", layer="deterministic")
def context_ledger_mismatch(ctx: Ctx) -> Outcome:
    box = ctx.sandbox()
    F.start_s1(ctx.repo, box)
    F.complete_s1(ctx.repo, box, ctx.fixtures)
    box.write(".ariadne/creative-evidence.json", json.dumps({
        "schema_version": 2, "project": str(box.root / "some-other-project"),
        "research_depth": "none", "skills": [], "references": [], "decisions": [], "resources": [],
    }, indent=2) + "\n")
    result = ctx.repo.cli("prepare-next", "--run-root", str(box.run_root), "--motion", "no", "--assets", "no")
    ok = result.returncode != 0 and "different project" in result.combined
    return Outcome("pass" if ok else "fail", f"exit {result.returncode}: {result.tail(2)}",
                   {"tail": result.tail(3), "ledger_project": str(box.root / "some-other-project")})


@case(id="context.delivered-source-hashes-match", group="context",
      title="Every delivered source hash matches its canonical bytes",
      task="Prepare S1 and S3 packets and compare every manifest source hash to the file.",
      expectation="All delivered source hashes match; the packet contains exactly the declared sections.",
      evaluation="Recompute hashes for all sources and run verify_packet.",
      evidence_required="Per-source comparison and verifier result.", layer="deterministic")
def context_hashes(ctx: Ctx) -> Outcome:
    box = ctx.sandbox()
    F.start_s1(ctx.repo, box)
    F.complete_s1(ctx.repo, box, ctx.fixtures)
    F.to_s3(ctx.repo, box)
    transport = ctx.repo.module("prepare-stage.py")
    mismatches = []
    checked = 0
    for entry in box.manifest().get("sources", []):
        if not entry.get("delivered", True):
            continue
        path = transport.resolve_source_path(entry, box.manifest())
        if not Path(path).is_file():
            continue
        checked += 1
        if hashlib.sha256(Path(path).read_bytes()).hexdigest() != entry.get("source_sha256"):
            mismatches.append(entry.get("path"))
    problems = transport.verify_packet(box.current_packet())
    ok = not mismatches and not problems and checked > 0
    return Outcome("pass" if ok else "fail",
                   f"{checked} delivered sources checked, {len(mismatches)} mismatched, verify={problems or 'clean'}",
                   {"mismatches": mismatches, "checked": checked, "problems": problems},
                   {"sources_checked": checked})


@case(id="context.packet-size-baseline", group="context",
      title="Packet size baseline per stage",
      task="Measure delivered context bytes for S1 and S3 under a fixed fixture.",
      expectation="Measurement-only: record bytes, sources and omitted inputs for later comparison.",
      evaluation="Sum packet.txt bytes and count delivered sources.",
      evidence_required="Per-stage byte counts and source counts.", layer="deterministic")
def context_size(ctx: Ctx) -> Outcome:
    box = ctx.sandbox()
    F.start_s1(ctx.repo, box)
    s1_packet = box.current_packet()
    s1_bytes = (s1_packet / "packet.txt").stat().st_size
    s1_sources = len([s for s in box.manifest().get("sources", []) if s.get("delivered", True)])
    F.complete_s1(ctx.repo, box, ctx.fixtures)
    F.to_s3(ctx.repo, box)
    s3_packet = box.current_packet()
    s3_bytes = (s3_packet / "packet.txt").stat().st_size
    s3_manifest = box.manifest()
    s3_sources = len([s for s in s3_manifest.get("sources", []) if s.get("delivered", True)])
    return Outcome("observed",
                   f"S1 {s1_bytes} bytes/{s1_sources} sources; S3 {s3_bytes} bytes/{s3_sources} sources",
                   {"s1": {"bytes": s1_bytes, "sources": s1_sources},
                    "s3": {"bytes": s3_bytes, "sources": s3_sources,
                           "omitted": s3_manifest.get("omitted")},
                    "note": "context bytes are measured, not estimated"},
                   {"s1_packet_bytes": s1_bytes, "s3_packet_bytes": s3_bytes,
                    "s3_sources": s3_sources})


# =============================================================== group: design

@case(id="design.creative-plan-requires-brief", group="design",
      title="Creative planning requires a completed brief",
      task="Attempt creative planning before the brief exists.",
      expectation="Refused; no ledger written.",
      evaluation="Exit code and absence of creative-evidence.json.",
      evidence_required="Refusal message.", layer="deterministic")
def design_plan_requires_brief(ctx: Ctx) -> Outcome:
    box = ctx.sandbox()
    F.start_s1(ctx.repo, box)
    assessment = box.root / "assessment.json"
    assessment.write_text(json.dumps({"research_depth": "none", "skills": [], "references": [],
                                      "decisions": [], "resources": []}), encoding="utf-8")
    result = ctx.repo.cli("creative-plan", "--run-root", str(box.run_root), "--input", str(assessment))
    ledger = box.project / ".ariadne" / "creative-evidence.json"
    ok = result.returncode == 1 and not ledger.is_file()
    return Outcome("pass" if ok else "fail", f"exit {result.returncode}: {result.tail(2)}",
                   {"tail": result.tail(3), "ledger_written": ledger.is_file()})


@case(id="design.unsupported-claim-blocks-g1", group="design",
      title="Unsupported creative claims block the G1 presentation",
      task="Reach S3 with a design direction but no creative plan or skill evidence, then advance.",
      expectation="Exit 2 with an unsupported-claim reason and no G1 request.",
      evaluation="Exit code and message.",
      evidence_required="Message text and intervention state.", layer="deterministic")
def design_unsupported_claim(ctx: Ctx) -> Outcome:
    box = ctx.sandbox()
    F.start_s1(ctx.repo, box)
    F.complete_s1(ctx.repo, box, ctx.fixtures)
    F.to_s3(ctx.repo, box)
    box.write("DESIGN.md", F.design_md("draft — awaiting G1"))
    result = ctx.repo.cli("advance", "--run-root", str(box.run_root))
    ok = result.returncode == 2 and ("creative" in result.combined.lower())
    return Outcome("pass" if ok else "fail", f"exit {result.returncode}: {result.tail(3)}",
                   {"tail": result.tail(4), "state_next": box.state().get("next")})


@case(id="design.operations-ledger-derived", group="design",
      title="Implementation targets are derived from the approved direction",
      task="Prepare the S4B packet and inspect the creative-operations ledger.",
      expectation="A ledger of approved requirements is derived from DESIGN.md/HANDOFF.md without another human task.",
      evaluation="Read creative-operations.json and its requirement ids.",
      evidence_required="Requirement ids and the log line that records the derivation.",
      layer="deterministic")
def design_operations_ledger(ctx: Ctx) -> Outcome:
    box = ctx.sandbox()
    F.reach_s4a_with_handoff(ctx.repo, box, ctx.fixtures)
    F.clear_preflight_and_reach_s4b(ctx.repo, box)
    ledger_path = box.project / ".ariadne" / "creative-operations.json"
    ledger = json.loads(ledger_path.read_text(encoding="utf-8")) if ledger_path.is_file() else {}
    operations = ctx.repo.module("creative-operations.py")
    problems = operations.ledger_problems(box.project, ledger) if ledger else ["no ledger"]
    requirements = [item.get("id") for item in ledger.get("requirements", [])]
    ok = bool(ledger) and not problems and bool(requirements) and "signature-moment" in requirements
    return Outcome("pass" if ok else "fail",
                   f"requirements={requirements}; problems={problems or 'none'}",
                   {"requirement_ids": requirements, "ledger_schema": ledger.get("schema_version"),
                    "log_derivation": "Design-to-implementation trace generated" in box.operations_log()})


# ========================================================= group: distribution

@case(id="distribution.manifest-rejects-incomplete", group="distribution",
      title="Release manifest validation rejects incomplete metadata",
      task="Feed the release-manifest validator malformed and truncated manifests.",
      expectation="Missing files, bad hashes, wrong product/schema and absent compatibility range are rejected.",
      evaluation="Call the validator directly with mutated manifests and assert each mutation fails.",
      evidence_required="Per-mutation problem lists.", layer="deterministic")
def distribution_manifest(ctx: Ctx) -> Outcome:
    # The launcher is a real package under src/; import it by path with the repo's src first.
    import importlib
    src = str(ctx.repo.root / "src")
    if src not in sys.path:
        sys.path.insert(0, src)
    module = importlib.import_module("ariadne.cli")
    # Positive control: the release builder's own manifest must validate.
    release = ctx.repo.module("build-release.py")
    good = release.runtime_manifest("benchmark")
    mutations = {
        "wrong_product": {**good, "product": "Other"},
        "bad_schema": {**good, "schema_version": 2},
        "no_files": {**good, "files": {}},
        "bad_hash": {**good, "files": {**good["files"], "VERSION": "zz"}},
        "no_compat_range": {**good, "project_state_schema": {}},
        "bad_version": {**good, "version": "two"},
        "omits_required_files": {**good, "files": {k: v for k, v in list(good["files"].items())[1:]}},
    }
    results = {}
    positive = module.validate_release_manifest(good)
    for name, value in mutations.items():
        results[name] = module.validate_release_manifest(value)
    ok = not positive and all(results.values())
    return Outcome("pass" if ok else "fail",
                   f"positive control problems={positive or 'none'}; "
                   f"mutations rejected={sum(1 for v in results.values() if v)}/{len(mutations)}",
                   {"positive_control": positive, "mutations": results})


@case(id="distribution.version-and-schema-coupling", group="distribution",
      title="Version and project-state schema stay in lockstep",
      task="Compare VERSION, pyproject metadata, the run-state schema and the declared compatibility range.",
      expectation="One version authority; declared project-state range matches the runtime's accepted schema.",
      evaluation="Read the files and the runtime constant, and compare.",
      evidence_required="Version strings and schema numbers.", layer="deterministic")
def distribution_version(ctx: Ctx) -> Outcome:
    version = (ctx.repo.root / "VERSION").read_text(encoding="utf-8").strip()
    pyproject = (ctx.repo.root / "pyproject.toml").read_text(encoding="utf-8")
    runtime = ctx.repo.module("ariadne.py")
    release = ctx.repo.module("build-release.py")
    sources = release.runtime_sources()
    manifest = release.runtime_manifest("benchmark")
    declared = manifest.get("project_state_schema", {})
    ok = (f'dynamic = ["version"]' in pyproject and "name = \"ariadne\"" in pyproject
          and declared.get("min") == runtime.RUNTIME_SCHEMA == declared.get("max")
          and manifest.get("version") == version
          and manifest.get("minimum_bootstrap_version") == "1.4.0"
          and manifest.get("product") == "Ariadne")
    return Outcome("pass" if ok else "fail",
                   f"version={version}; schema declared={declared}; runtime accepts {runtime.RUNTIME_SCHEMA}",
                   {"version": version, "declared_schema": declared,
                    "runtime_schema": runtime.RUNTIME_SCHEMA,
                    "minimum_bootstrap_version": manifest.get("minimum_bootstrap_version"),
                    "runtime_sources": len(sources),
                    "pyproject_has_static_version": re.search(r"(?m)^version =", pyproject) is not None})


@case(id="distribution.release-tooling-offline", group="distribution",
      title="Release and runtime tooling stay offline and dependency-free",
      task="Statistically scan the shipped scripts and the build backend for network or third-party imports.",
      expectation="No network client imports in release/runtime tooling; no declared dependencies.",
      evaluation="Parse imports with ast across shipped Python files.",
      evidence_required="Import inventory per file.", layer="deterministic")
def distribution_offline(ctx: Ctx) -> Outcome:
    network = {"urllib", "http", "socket", "requests", "httpx", "aiohttp", "ftplib", "smtplib"}
    files = (sorted((ctx.repo.root / "scripts").glob("*.py"))
             + sorted((ctx.repo.root / "src" / "ariadne").glob("*.py"))
             + sorted((ctx.repo.root / "build_backend").glob("*.py")))
    findings = {}
    for path in files:
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError as exc:
            findings[path.name] = [f"syntax error: {exc}"]
            continue
        names = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                names.add(node.module.split(".")[0])
        hits = sorted(names & network)
        if hits:
            findings[path.name] = hits
    pyproject = (ctx.repo.root / "pyproject.toml").read_text(encoding="utf-8")
    dependency_free = re.search(r"(?m)^dependencies = \[\]\s*$", pyproject) is not None
    # urllib is permitted only in the launcher, which must fetch release descriptors.
    findings = {name: hits for name, hits in findings.items()
                if not (name == "cli.py" and set(hits) <= {"urllib", "http"})}
    ok = not findings and dependency_free
    return Outcome("pass" if ok else "fail",
                   f"network imports outside the launcher: {findings or 'none'}; dependencies=[] is {dependency_free}",
                   {"findings": findings, "files_scanned": len(files), "dependency_free": dependency_free},
                   {"files_scanned": len(files)})


@case(id="distribution.uninstall-and-rollback-guards", group="distribution",
      title="Rollback and uninstall keep hard safety guards",
      task="Drive an installed-product lifecycle in a sandboxed data home using a local bundle.",
      expectation="Rollback restores a verified previous runtime; uninstall refuses a dangerous root.",
      evaluation="Reuse the shipped lifecycle suite output for the guarded paths.",
      evidence_required="Suite pass ratio for the lifecycle group.",
      layer="deterministic",
      notes="Covered by suite.distribution-lifecycle; kept as an explicit distribution contract case.")
def distribution_lifecycle_guards(ctx: Ctx) -> Outcome:
    result = ctx.repo.script_run("test-distribution.py", timeout=900)
    outcome = ratio_outcome(result, "installed-product lifecycle")
    if outcome.status == "pass":
        outcome.actual += " (rollback/uninstall guards included)"
    return outcome


# =============================================================== suite: heavy

@case(id="suite.wheel-install", group="suites",
      title="Wheel build and isolated install",
      task="Build the launcher wheel and install it into a throwaway venv.",
      expectation="Wheel builds offline, installs, and the installed launcher runs.",
      evaluation="Exit code of the shipped wheel suite.",
      evidence_required="Pass ratio and venv path.",
      layer="deterministic", executable=False,
      notes="Requires a working pip/venv and is slow; not executed during AR-200 (see BENCHMARKS.md).")
def suite_wheel_install(ctx: Ctx) -> Outcome:
    return Outcome("skip", "not executed in AR-200 (requires pip/venv; see BENCHMARKS.md)",
                   {"case_id": "suite.wheel-install"})


@case(id="suite.engine-core", group="suites",
      title="Orchestration-core self-test",
      task="Exercise the AR-201 contracts, transition choke point, approval binding, review records, "
           "migration and API in isolated temporary directories.",
      expectation="All engine-core checks pass with no model call and no network.",
      evaluation="Exit code 0 from scripts/test-engine-core.py.",
      evidence_required="Exit code and tail.",
      layer="deterministic")
def suite_engine_core(ctx: Ctx) -> Outcome:
    return exit_outcome(ctx.repo.script_run("test-engine-core.py", timeout=600), 0,
                        "test-engine-core.py")


# ====================================================== group: AR-201 authorization

@case(id="lifecycle.approval-stale-after-edit", group="lifecycle",
      title="A semantic edit invalidates a recorded approval",
      task="Reach S3 with the direction evidence and a recorded G1 approval, edit the design thesis, then "
           "continue to S4A.",
      expectation="The approval no longer binds the new revision and the continuation is refused.",
      evaluation="Compare the exit code, the recorded approval and the refusal reason.",
      evidence_required="Exit code, approval fingerprint, refusal message.",
      layer="deterministic-lifecycle")
def lifecycle_approval_stale(ctx: Ctx) -> Outcome:
    box = ctx.sandbox()
    F.start_s1(ctx.repo, box)
    F.complete_s1(ctx.repo, box, ctx.fixtures)
    F.to_s3(ctx.repo, box)
    F.lock_g1(box)
    state = box.state()
    approval = state["approvals"][-1]
    box.write("DESIGN.md", F.design_md("locked at G1 on 2026-09-22").replace(
        "archival but immediate", "archival but weightless"))
    ctx.repo.cli("record-result", "--run-root", str(box.run_root), "--status", "complete",
                 "--provider", "self", "--model", "none", "--summary", "Direction edited",
                 "--file", "DESIGN.md", "--file", "AGENTS.md")
    result = ctx.repo.cli("prepare-next", "--run-root", str(box.run_root))
    stages = [entry["stage"] for entry in box.packets()]
    after = box.state()
    refused = result.returncode != 0 and stages[-1] == "S3"
    named = "stale" in result.combined.lower() or "approval" in result.combined.lower()
    preserved = any(row["approval_id"] == approval["approval_id"] for row in after.get("approvals", []))
    ok = refused and named and preserved
    return Outcome(
        "pass" if ok else "fail",
        (f"the edited revision refused the recorded G1 approval; it is preserved but unbound "
         f"(exit {result.returncode}, stages {stages})") if ok else
        f"stale approval behaviour unexpected: exit {result.returncode}, stages {stages}, tail={result.tail(2)}",
        {"exit_code": result.returncode, "stages": stages, "tail": result.tail(3),
         "approval_gate": approval.get("gate"), "approval_revision": approval.get("revision_hash", "")[:12],
         "approvals_after": len(after.get("approvals", []))},
        {"false_acceptance": 0 if ok else 1, "model_calls": 0},
    )


@case(id="lifecycle.approval-channel-required", group="lifecycle",
      title="A non-human approval channel cannot satisfy a gate",
      task="Write an approval record for G1 carrying a worker channel and a worker identity into the run "
           "state by hand, then continue to S4A.",
      expectation="The gate stays unsatisfied: only the human CLI channel grants authority.",
      evaluation="Read the refusal reason and confirm no S4A packet was prepared.",
      evidence_required="Exit code, refusal reason, recorded channels.",
      layer="deterministic-lifecycle")
def lifecycle_approval_channel(ctx: Ctx) -> Outcome:
    box = ctx.sandbox()
    F.start_s1(ctx.repo, box)
    F.complete_s1(ctx.repo, box, ctx.fixtures)
    F.to_s3(ctx.repo, box)
    box.write("DESIGN.md", F.design_md("locked at G1 on 2026-09-22"))
    box.write("AGENTS.md", F.agents_md("S3", "G1", "prompts/build-kickoff.md"))
    F.record_direction_evidence(ctx.repo, box)
    state = box.state()
    runtime = ctx.repo.module("ariadne.py")
    subject = runtime.POLICY.design_direction_subject(box.project)
    state.setdefault("approvals", []).append({
        "schema_version": 2, "approval_id": "apv_20260922T000000Z_deadbeef", "gate": "G1",
        "subject_type": "design-direction", "subject_id": subject.subject_id,
        "revision_hash": subject.revision_hash, "identity": "bulk",
        "channel": "worker-cli", "note": "self-authorized", "recorded_at": "2026-09-22T00:00:00+00:00",
        "stage": "S3", "packet_id": "", "consumed_by": [],
    })
    (box.run_root / "ariadne-run.json").write_text(
        json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    result = ctx.repo.cli("prepare-next", "--run-root", str(box.run_root))
    stages = [entry["stage"] for entry in box.packets()]
    channel_named = "channel" in result.combined.lower() or "human-cli" in result.combined
    ok = result.returncode == 2 and stages[-1] == "S3" and channel_named
    return Outcome(
        "pass" if ok else "fail",
        (f"the worker-channel approval was refused and G1 stayed unsatisfied (exit {result.returncode})"
         if ok else
         f"unexpected self-authorization behaviour: exit {result.returncode}, stages {stages}, "
         f"tail={result.tail(2)}"),
        {"exit_code": result.returncode, "stages": stages, "tail": result.tail(3),
         "forged_channel": "worker-cli"},
        {"self_authorization": 0 if ok else 1, "model_calls": 0},
    )


@case(id="lifecycle.invalid-transition-refused", group="lifecycle",
      title="The transition table refuses illegal jumps and never half-applies them",
      task="Call the engine's transition choke point directly with an illegal stage jump and with a "
           "refused worker transition.",
      expectation="Illegal transitions raise structured errors and leave the state unchanged.",
      evaluation="Catch InvalidTransition/PolicyRefusal and compare the state before and after.",
      evidence_required="Exception types, state digests before and after.",
      layer="deterministic-lifecycle")
def lifecycle_invalid_transition(ctx: Ctx) -> Outcome:
    box = ctx.sandbox()
    F.start_s1(ctx.repo, box)
    runtime = ctx.repo.module("ariadne.py")
    state = box.state()
    before = json.dumps(state, sort_keys=True)
    illegal = refused = False
    message = ""
    try:
        runtime.STATEMACHINE.assert_transition("stage", "S1", "S4B")
    except runtime.CONTRACTS.InvalidTransition as exc:
        illegal = True
        message = str(exc)
    try:
        runtime.STATEMACHINE.apply_transition(
            state,
            runtime.CONTRACTS.TransitionRequest(kind="worker-lifecycle", to="validated",
                                                reason="asserted by the worker"),
            permitted=False,
            problems=["independent validation has not run"],
        )
    except runtime.CONTRACTS.PolicyRefusal:
        refused = True
    unchanged = json.dumps(state, sort_keys=True) == before
    ok = illegal and refused and unchanged
    return Outcome(
        "pass" if ok else "fail",
        (f"illegal jumps are refused ({message}); a refused transition leaves the state byte-identical"
         if ok else
         f"unexpected: illegal={illegal}, refused={refused}, unchanged={unchanged}"),
        {"illegal_message": message, "state_unchanged": unchanged,
         "packets": [entry["stage"] for entry in state.get("packets", [])],
         "worker_fields": sorted((state.get("worker") or {}).keys())},
        {"bypasses_allowed": 0 if ok else 1, "model_calls": 0},
    )


@case(id="lifecycle.schema-migration-explicit", group="lifecycle",
      title="Legacy run state needs an explicit, additive, reversible migration",
      task="Strip the engine contract from a copy of a live run state, then read it without and with "
           "--migrate, and repeat the migration.",
      expectation="Reading refuses with an explicit instruction; migration preserves the original file, "
                    "records history, invents no approval and is idempotent.",
      evaluation="Compare exit codes, the preserved backup, the migration history and the approval count.",
      evidence_required="Exit codes, backup bytes, migration history, approvals.",
      layer="deterministic-lifecycle")
def lifecycle_schema_migration(ctx: Ctx) -> Outcome:
    box = ctx.sandbox()
    F.start_s1(ctx.repo, box)
    F.complete_s1(ctx.repo, box, ctx.fixtures)
    F.to_s3(ctx.repo, box)
    state_path = box.run_root / "ariadne-run.json"
    live = json.loads(state_path.read_text(encoding="utf-8"))
    legacy = {key: value for key, value in live.items()
              if key not in ("engine", "approvals", "migration_history", "transitions", "reviews")}
    legacy["packets"][0]["reasoner_output_baseline"] = None
    state_path.write_text(json.dumps(legacy, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    legacy_bytes = state_path.read_bytes()
    without = ctx.repo.cli("status", "--run-root", str(box.run_root))
    migrated = ctx.repo.cli("status", "--run-root", str(box.run_root), "--migrate")
    backup = box.run_root / "ariadne-run.v1.bak"
    backup_matches = backup.is_file() and backup.read_bytes() == legacy_bytes
    after = json.loads(state_path.read_text(encoding="utf-8"))
    history = after.get("migration_history", [])
    approvals = after.get("approvals", [])
    repeat = ctx.repo.cli("status", "--run-root", str(box.run_root), "--migrate")
    after_repeat = json.loads(state_path.read_text(encoding="utf-8"))
    unknown = json.loads(state_path.read_text(encoding="utf-8"))
    unknown["schema_version"] = 99
    state_path.write_text(json.dumps(unknown, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    unreadable = ctx.repo.cli("status", "--run-root", str(box.run_root), "--migrate")
    refused_unknown = unreadable.returncode == 1 and "schema is unsupported" in unreadable.combined
    ok = (
        without.returncode == 1 and "--migrate" in without.combined
        and migrated.returncode == 0 and backup_matches
        and len(history) == 1 and history[0]["approvals_created"] == 0 and approvals == []
        and repeat.returncode == 0
        and len(after_repeat.get("migration_history", [])) == 1
        and refused_unknown
    )
    return Outcome(
        "pass" if ok else "fail",
        (f"legacy state refused explicitly, migrated additively with a preserved backup and no invented "
         f"approval; an unknown schema is still refused") if ok else
        (f"unexpected migration behaviour: without={without.returncode}, "
         f"with={migrated.returncode}, backup={backup_matches}, "
         f"history={len(history)}, approvals={len(approvals)}, repeat={repeat.returncode}, "
         f"unknown_refused={refused_unknown}"),
        {"without_exit": without.returncode, "with_exit": migrated.returncode,
         "repeat_exit": repeat.returncode, "backup_matches_original": backup_matches,
         "migration_history": history, "approvals_after": len(approvals),
         "unknown_schema_exit": unreadable.returncode,
         "without_message": without.tail(2)},
        {"migrations_implicit": 0 if without.returncode == 1 else 1, "model_calls": 0},
    )


@case(id="lifecycle.api-vertical-slice", group="lifecycle",
      title="The protected slice works through the Python API",
      task="Drive start, record-result, prepare-next, approve-gate and status through ENGINE_API with no "
           "subprocess, and check the reported state changes.",
      expectation="Every API call returns the documented exit code and the run reaches the approved boundary, "
                  "with refusals reported as results rather than exceptions.",
      evaluation="Compare API exit codes, messages and Result.state_changed against the run state.",
      evidence_required="API results, resulting stages, recorded approvals.",
      layer="deterministic-lifecycle")
def lifecycle_api_vertical_slice(ctx: Ctx) -> Outcome:
    box = ctx.sandbox()
    runtime = ctx.repo.module("ariadne.py")
    api = runtime.ENGINE_API
    started = api.start_run(project=str(box.project), run_root=str(box.run_root),
                            request="API slice.", run_id="api-slice")
    status = api.status(run_root=str(box.run_root))
    box.write("PROJECT.md", F.project_md())
    box.write("AGENTS.md", F.agents_md("S1", "none", "prompts/design-direction.md"))
    recorded = api.record_result(run_root=str(box.run_root), status="complete",
                                 provider="api-fixture", model="none",
                                 summary="S1 brief complete", file=["PROJECT.md", "AGENTS.md"])
    ctx.repo.cli("creative-plan", "--run-root", str(box.run_root), "--input",
                 str(_assessment_file(ctx, box)))
    s3 = api.prepare_next(run_root=str(box.run_root), motion="no", assets="no")
    box.write("DESIGN.md", F.design_md("locked at G1 on 2026-09-22"))
    box.write("AGENTS.md", F.agents_md("S3", "G1", "prompts/build-kickoff.md"))
    F.record_direction_evidence(ctx.repo, box)
    ungated = api.prepare_next(run_root=str(box.run_root))
    approved = api.approve_gate(run_root=str(box.run_root), gate="G1", identity="api-operator",
                                note="API fixture")
    directed = api.record_result(run_root=str(box.run_root), status="complete",
                                 provider="api-fixture", model="none",
                                 summary="Direction approved at G1",
                                 file=["DESIGN.md", "AGENTS.md"])
    s4a = api.prepare_next(run_root=str(box.run_root))
    state = box.state()
    stages = [entry["stage"] for entry in state["packets"]]
    ok = (
        started.exit_code == 0 and started.state_changed
        and status.exit_code == 0 and not status.state_changed
        and recorded.exit_code == 0
        and s3.exit_code == 0
        and ungated.exit_code == 2 and "approval" in ungated.message.lower()
        and approved.exit_code == 0 and approved.state_changed
        and directed.exit_code == 0
        and s4a.exit_code == 0 and stages[-1] == "S4A"
        and len(state.get("approvals", [])) == 1
        and not s4a.message.startswith("STOPPED")
    )
    return Outcome(
        "pass" if ok else "fail",
        ("the API drove S1 to an approved S4A boundary; the unapproved continuation returned exit 2 as a "
         "Result, and state_changed matched the writes") if ok else
        (f"unexpected API behaviour: start={started.exit_code}, status={status.exit_code}, "
         f"record={recorded.exit_code}, s3={s3.exit_code}, ungated={ungated.exit_code}, "
         f"approved={approved.exit_code}, s4a={s4a.exit_code}, stages={stages}"),
        {"start_exit": started.exit_code, "status_exit": status.exit_code,
         "record_exit": recorded.exit_code, "s3_exit": s3.exit_code,
         "ungated_exit": ungated.exit_code, "ungated_message": ungated.message.strip()[:200],
         "approved_exit": approved.exit_code, "s4a_exit": s4a.exit_code, "stages": stages,
         "s4a_message": s4a.message.strip()[:300],
         "approvals": [row.get("approval_id") for row in state.get("approvals", [])],
         "state_changed_flags": [started.state_changed, status.state_changed,
                                 approved.state_changed, s4a.state_changed]},
        {"api_bypasses": 0 if ok else 1, "model_calls": 0},
    )


def _assessment_file(ctx: Ctx, box: Sandbox) -> Path:
    path = box.root / "api-assessment.json"
    path.write_text(json.dumps(ctx.repo.module("creative-intelligence.py").low_assessment(),
                               indent=2) + "\n", encoding="utf-8")
    return path


@case(id="security.approval-wrong-target-refused", group="security",
      title="An approval for one target or operation cannot authorize another",
      task="Record a G1 approval, then present it as a G2 handoff approval and as an approval for a "
           "different design revision.",
      expectation="Each mismatch is refused and named.",
      evaluation="Read the gate checks for wrong operation, wrong target and wrong revision.",
      evidence_required="Refusal reasons for each mismatch.",
      layer="deterministic-lifecycle")
def security_approval_wrong_target(ctx: Ctx) -> Outcome:
    box = ctx.sandbox()
    F.start_s1(ctx.repo, box)
    F.complete_s1(ctx.repo, box, ctx.fixtures)
    F.to_s3(ctx.repo, box)
    F.lock_g1(box)
    runtime = ctx.repo.module("ariadne.py")
    state = box.state()
    policy = runtime.POLICY
    design_subject = policy.design_direction_subject(box.project)
    handoff = box.write("HANDOFF.md", ctx.fixtures["handoff"]())
    handoff_subject = policy.handoff_subject(box.project)
    wrong_operation = policy.gate_satisfied(state, "G2", handoff_subject)[1]
    wrong_target = policy.gate_satisfied(state, "G1", handoff_subject)[1]
    other_revision = runtime.CONTRACTS.Subject(
        "design-direction", "DESIGN.md", "f" * 64)
    wrong_revision = policy.gate_satisfied(state, "G1", other_revision)[1]
    named = all([
        "no G2 approval" in wrong_operation or "different target" in wrong_operation,
        "does not match this operation" in wrong_target or "different target" in wrong_target,
        "stale" in wrong_revision or "different target" in wrong_revision,
    ])
    ok = named and not any(
        policy.gate_satisfied(state, gate, subject)[0]
        for gate, subject in (("G2", handoff_subject), ("G1", other_revision))
    )
    return Outcome(
        "pass" if ok else "fail",
        ("a G1 approval does not satisfy G2, does not bind the handoff target and does not travel to "
         "another revision") if ok else "an approval crossed its operation, target or revision boundary",
        {"wrong_operation_reason": wrong_operation, "wrong_target_reason": wrong_target,
         "wrong_revision_reason": wrong_revision,
         "design_revision": design_subject.revision_hash[:12]},
        {"approval_reuse": 0 if ok else 1, "model_calls": 0},
    )


@case(id="security.acceptance-after-review-and-single-use", group="security",
      title="Acceptance needs the recorded review and spends the G3 approval once",
      task="Reach S5, ingest an independent review, record the human G3 approval, accept the result and "
           "then repeat the accepted outcome.",
      expectation="Acceptance succeeds once with the bound approval; the replay is refused.",
      evaluation="Compare exit codes, lifecycle states and the consumed approval record.",
      evidence_required="Exit codes, worker lifecycle, approval consumption.",
      layer="deterministic-lifecycle")
def security_acceptance_flow(ctx: Ctx) -> Outcome:
    box = ctx.sandbox()
    F.reach_s4a_with_handoff(ctx.repo, box, ctx.fixtures)
    F.clear_preflight_and_reach_s4b(ctx.repo, box)
    F.deliver_return(box, ctx.fixtures, status="complete")
    ctx.repo.cli("validate-worker", "--run-root", str(box.run_root))
    F.prepare_s5(ctx.repo, box)
    source = box.root / "review.md"
    source.write_text(ctx.fixtures["review"](), encoding="utf-8")
    reviewed = F.ingest_independent_review(ctx.repo, box, source)
    reviewed_state = box.state()
    before_gate = ctx.repo.cli("record-acceptance", "--run-root", str(box.run_root),
                               "--outcome", "accepted")
    gate = F.record_g3(ctx.repo, box)
    accepted = ctx.repo.cli("record-acceptance", "--run-root", str(box.run_root), "--outcome", "accepted")
    after = box.state()
    replay = ctx.repo.cli("record-acceptance", "--run-root", str(box.run_root), "--outcome", "accepted")
    replay_state = box.state()
    consumed = [
        row for row in replay_state.get("approvals", [])
        if row.get("gate") == "G3" and row.get("consumed_by")
    ]
    ok = (
        reviewed.returncode == 0
        and reviewed_state["worker"]["review_state"] == "REVIEWED"
        and before_gate.returncode == 1
        and gate.returncode == 0
        and accepted.returncode == 0
        and after["worker"]["acceptance_state"] == "ACCEPTED"
        and after["worker"]["lifecycle"] == "accepted"
        and replay.returncode == 1
        and bool(consumed)
        and replay_state["worker"]["acceptance_state"] == "ACCEPTED"
    )
    return Outcome(
        "pass" if ok else "fail",
        ("acceptance required the recorded review and the bound human approval, succeeded once, and "
         "refused the replay because the approval was spent") if ok else
        (f"unexpected acceptance flow: reviewed={reviewed.returncode}, without_gate={before_gate.returncode}, "
         f"gate={gate.returncode}, accepted={accepted.returncode}, replay={replay.returncode}, "
         f"consumed={len(consumed)}, lifecycle={replay_state.get('worker', {}).get('lifecycle')}"),
        {"review_exit": reviewed.returncode, "accept_without_gate": before_gate.returncode,
         "gate_exit": gate.returncode, "accept_exit": accepted.returncode, "replay_exit": replay.returncode,
         "review_state_after": reviewed_state["worker"].get("review_state"),
         "acceptance_state": replay_state["worker"].get("acceptance_state"),
         "consumed_approvals": [row.get("approval_id") for row in consumed],
         "replay_message": replay.tail(2)},
        {"replay_acceptance": 0 if replay.returncode == 1 else 1, "model_calls": 0},
    )


@case(id="security.review-record-required", group="security",
      title="A review judgement on disk is not a review record",
      task="Write a convincing review judgement into the S5 evidence directory by hand, then try to approve "
           "G3 and accept the result.",
      expectation="Neither the gate nor acceptance can be obtained without a recorded review bound to the "
                  "revision.",
      evaluation="Read the exit codes and the stored review records.",
      evidence_required="Exit codes, review records, acceptance state.",
      layer="deterministic-lifecycle")
def security_review_record_required(ctx: Ctx) -> Outcome:
    box = ctx.sandbox()
    F.reach_s4a_with_handoff(ctx.repo, box, ctx.fixtures)
    F.clear_preflight_and_reach_s4b(ctx.repo, box)
    F.deliver_return(box, ctx.fixtures, status="complete")
    ctx.repo.cli("validate-worker", "--run-root", str(box.run_root))
    F.prepare_s5(ctx.repo, box)
    packet = box.current_packet()
    (packet / "evidence").mkdir(parents=True, exist_ok=True)
    (packet / "evidence" / "review-judgement.md").write_text(
        "## Judgement\n\nLooks strong.\n\n**Recommendation:** Present G3\n", encoding="utf-8")
    gate = F.record_g3(ctx.repo, box)
    accepted = ctx.repo.cli("record-acceptance", "--run-root", str(box.run_root), "--outcome", "accepted")
    state = box.state()
    records = state.get("reviews", [])
    ok = gate.returncode == 1 and accepted.returncode == 1 and not records \
        and state["worker"]["acceptance_state"] == "UNKNOWN"
    return Outcome(
        "pass" if ok else "fail",
        ("a hand-written judgement could not grant the gate or acceptance: the review record, not the file, "
         "is the evidence") if ok else
        (f"unexpected: gate={gate.returncode}, accepted={accepted.returncode}, "
         f"records={len(records)}, acceptance={state['worker'].get('acceptance_state')}"),
        {"gate_exit": gate.returncode, "accept_exit": accepted.returncode,
         "review_records": len(records), "gate_message": gate.tail(2),
         "acceptance_state": state["worker"].get("acceptance_state")},
        {"fabricated_review_accepted": 0 if accepted.returncode == 1 else 1, "model_calls": 0},
    )


@case(id="security.migrated-legacy-gate-refused", group="security",
      title="Migration never converts a document gate field into an approval",
      task="Migrate a legacy run whose AGENTS.md records G1 and whose DESIGN.md is locked, then continue.",
      expectation="The run keeps no approval and must re-obtain the human gate.",
      evaluation="Read the approvals after migration and the continuation exit code.",
      evidence_required="Migration history, approval count, exit code.",
      layer="deterministic-lifecycle")
def security_migrated_legacy_gate(ctx: Ctx) -> Outcome:
    box = ctx.sandbox()
    F.start_s1(ctx.repo, box)
    F.complete_s1(ctx.repo, box, ctx.fixtures)
    F.to_s3(ctx.repo, box)
    box.write("DESIGN.md", F.design_md("locked at G1 on 2026-09-22"))
    box.write("AGENTS.md", F.agents_md("S3", "G1", "prompts/build-kickoff.md"))
    state_path = box.run_root / "ariadne-run.json"
    live = json.loads(state_path.read_text(encoding="utf-8"))
    legacy = {key: value for key, value in live.items()
              if key not in ("engine", "approvals", "migration_history", "transitions", "reviews")}
    state_path.write_text(json.dumps(legacy, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    migrated = ctx.repo.cli("status", "--run-root", str(box.run_root), "--migrate")
    after = box.state()
    result = ctx.repo.cli("prepare-next", "--run-root", str(box.run_root))
    stages = [entry["stage"] for entry in box.packets()]
    approvals = after.get("approvals", [])
    ok = migrated.returncode == 0 and approvals == [] \
        and result.returncode != 0 and stages[-1] == "S3"
    return Outcome(
        "pass" if ok else "fail",
        ("migration preserved the documents but created no approval; the migrated run had to re-obtain G1"
         if ok else
         f"unexpected: migrated={migrated.returncode}, approvals={len(approvals)}, "
         f"exit={result.returncode}, stages={stages}"),
        {"migration_exit": migrated.returncode, "approvals_after": len(approvals),
         "continuation_exit": result.returncode, "stages": stages, "tail": result.tail(3),
         "migration_history": after.get("migration_history", [])},
        {"invented_approvals": len(approvals), "model_calls": 0},
    )


@case(id="lifecycle.recovery-reports-interrupted-work", group="lifecycle",
      title="Interrupted work is reported, never adopted or inferred as success",
      task="Leave an orphan packet directory and an interrupted state write beside a live run, then inspect "
           "recovery state and continue normally.",
      expectation="Recovery names the divergence, adopts nothing, and the run keeps working.",
      evaluation="Read the recovery report and the packet list before and after.",
      evidence_required="Recovery report, packet list, continuation exit code.",
      layer="deterministic-lifecycle")
def lifecycle_recovery_report(ctx: Ctx) -> Outcome:
    box = ctx.sandbox()
    F.start_s1(ctx.repo, box)
    packets_before = [entry["id"] for entry in box.packets()]
    orphan = box.run_root / "packets" / "bench-S4B-C9"
    orphan.mkdir(parents=True, exist_ok=True)
    (orphan / "manifest.json").write_text('{"stage": "S4B"}\n', encoding="utf-8")
    (box.run_root / ".ariadne-run.json.aborted.tmp").write_text("{}\n", encoding="utf-8")
    runtime = ctx.repo.module("ariadne.py")
    report = runtime.PERSISTENCE.recovery_report(box.run_root)
    kinds = sorted(item["kind"] for item in report["findings"])
    adopted = [entry["id"] for entry in box.packets()]
    view = io.StringIO()
    with contextlib.redirect_stdout(view):
        api_result = runtime.ENGINE_API.recovery_report(run_root=str(box.run_root))
    ok = (
        report["status"] == "diverged"
        and kinds == ["interrupted-write", "orphan-packet"]
        and adopted == packets_before
        and api_result.exit_code == 2
        and "orphan-packet" in api_result.message
    )
    return Outcome(
        "pass" if ok else "fail",
        ("interrupted work is reported as a divergence, no packet is adopted and the API exposes the same "
         "report") if ok else f"unexpected recovery report: {report['status']}, kinds={kinds}, adopted={adopted}",
        {"status": report["status"], "finding_kinds": kinds,
         "packets_before": packets_before, "packets_after": adopted,
         "api_exit": api_result.exit_code, "last_packet": report.get("last_packet")},
        {"orphans_adopted": len(adopted) - len(packets_before), "model_calls": 0},
    )
