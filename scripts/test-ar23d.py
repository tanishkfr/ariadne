#!/usr/bin/env python3
"""AR-23D suite: project-level TEST evidence from engine-executed validations.

The 2.3C-R closure recorded one limitation: the engine reran the S4B contract's
validation commands and recorded the results in the packet's
``evidence/validation.json``, but those results never reached the project-level
acceptance ledger, so a Proof Pass over a fully validated project still showed
``TEST`` outstanding. This suite covers the closure of that boundary:

* the producer records a ``validated_revision`` fingerprint of the exact
  implementation bytes the commands ran against;
* the acceptance mapper (``integrations.from_worker_validation``) turns one
  genuine, current record into ``TEST`` evidence per requirement -- and refuses
  failed, blocked, unevidenced, stale, fictionally-placed and fingerprint-less
  records by name instead of counting them;
* the Proof Pass binds its whole revision (works with the digest) to the
  implementation, so a source change moves the revision and previously recorded
  observations go stale rather than silently staying current;
* the reviewer-independence level only rises to ``DISTINCT_PROVIDER`` on
  provider-*observed* identities, so two executions on the same provider with
  different requested labels are not mislabelled as distinct providers.

Every case drives the real engine on a temporary git project: real snapshots,
real fingerprints, real engine executions, real receipts. Negative controls
assert that nothing was recorded, not merely that a flag was false.

Run:  python scripts/test-ar23d.py [name-filter]
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import importlib.util  # noqa: E402

from ariadne_engine import contracts, execution as execution_module, proof, provenance, review  # noqa: E402
from ariadne_engine.acceptance import decisions as decisions_module  # noqa: E402
from ariadne_engine.acceptance import evidence as evidence_module  # noqa: E402
from ariadne_engine.acceptance import integrations as integrations_module  # noqa: E402
from ariadne_engine.acceptance import requirements as requirements_module  # noqa: E402

_spec = importlib.util.spec_from_file_location("prepare_stage", ROOT / "scripts" / "prepare-stage.py")
TRANSPORT = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(TRANSPORT)

CASES: list = []
SKIPS: list[tuple[str, str]] = []

TASK = "Build the widget page."


def case(fn):
    CASES.append(fn)
    return fn


class SkipCase(Exception):
    """The environment cannot honestly run this case; it is recorded, not faked."""


# --------------------------------------------------------------- fixtures


def make_project(root: Path) -> Path:
    project = root / "widget"
    project.mkdir()
    (project / "index.html").write_text("<html><body>widget</body></html>\n", encoding="utf-8")
    (project / "app.js").write_text("export const widget = 1;\n", encoding="utf-8")
    (project / "styles.css").write_text("body { margin: 0; }\n", encoding="utf-8")
    (project / "QA.md").write_text("# QA\n\nmechanical evidence\n", encoding="utf-8")
    (project / "AGENTS.md").write_text("# Agents\n", encoding="utf-8")
    tests = project / "tests"
    tests.mkdir()
    (tests / "test_widget.py").write_text("def test_ok():\n    assert True\n", encoding="utf-8")
    subprocess.run(["git", "init", "-q"], cwd=project, check=True, capture_output=True)
    return project


def make_packet(run_root: Path, project: Path, packet_id: str = "widget-S4B") -> Path:
    packet = run_root / packet_id
    (packet / "evidence").mkdir(parents=True)
    manifest = {
        "packet_id": packet_id,
        "packet_sha256": hashlib.sha256(packet_id.encode("utf-8")).hexdigest(),
        "project_baseline": {"head": "HEAD", "state": "dirty", "entries": []},
    }
    (packet / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return packet


def make_state(root: Path, project: Path, packets: list[dict]) -> dict:
    return {
        "schema_version": 1,
        "run_id": "ar23d-suite",
        "project": str(project),
        "run_root": str(root),
        "packets": packets,
        "executions": [],
        "failures": [],
    }


def record_validation(
    state: dict,
    project: Path,
    packet: Path,
    *,
    packet_id: str = "widget-S4B",
    status: str = "passed",
    scope_status: str = "within-contract",
    failure_kind: str = "none",
    required_status: str = "passed",
    with_execution: bool = True,
    execution_role: str = "validator",
    fingerprint: str | None = None,
) -> dict:
    """One validation record shaped exactly as ``validate_worker`` writes it.

    The record is written through the real transport helpers and bound to a real
    engine-created execution -- the same construction the runtime performs. Cases
    that need a *fabricated* record mutate one of these fields, which is the
    point: the refusal must name the field that made it a non-observation.
    """
    snapshot = TRANSPORT.project_git_snapshot(project)
    revision = dict(TRANSPORT.validated_revision(snapshot))
    if fingerprint is not None:
        revision["implementation_fingerprint"] = fingerprint
    record = {
        "schema_version": TRANSPORT.WORKER_VALIDATION_SCHEMA,
        "kind": "worker-validation",
        "packet_id": packet_id,
        "stage": "S4B",
        "independent": True,
        "executor": "Ariadne local validator",
        "started": "2026-10-15T00:00:00+00:00",
        "ended": "2026-10-15T00:00:01+00:00",
        "duration_seconds": 1.0,
        "scope": {
            "status": scope_status,
            "changed": ["app.js"],
            "outside": ["app.js"] if scope_status == "out-of-scope" else [],
            "sensitive": [],
            "immutable": [],
            "head_changed": False,
        },
        "changed_files": ["app.js"],
        "commands": [
            {
                "id": "tests",
                "check": "tests",
                "command": "python -m unittest discover -s tests",
                "required": True,
                "expected": "exit 0; all tests pass",
                "status": required_status,
                "returncode": 0 if required_status == "passed" else 1,
                "duration_seconds": 0.1,
                "stdout_sha256": None,
                "stderr_sha256": None,
                "error": None,
            }
        ],
        "usage": "unknown",
        "cost": "unknown",
        "status": status,
        "failure_kind": failure_kind,
        "failure_reason": "none",
        "validated_revision": revision,
    }
    if with_execution:
        execution = execution_module.create(
            state,
            task_id=packet_id,
            role=execution_role,
            adapter="scripts/ariadne.py:validate-worker",
            invocation="validate-worker",
            requested={"provider": "Ariadne local validator", "model": "local-independent-validator"},
            revision=execution_module.task_revision(state, packet),
            reason="independent worker validation of the recorded implementation",
        )
        execution_module.mark_started(state, str(execution["execution_id"]))
        execution_module.complete(
            state, str(execution["execution_id"]),
            result={"packet_id": packet_id, "status": status, "artifact": str(packet / "evidence" / "validation.json")},
            evidence=(str(packet / "evidence" / "validation.json"),),
        )
        record["execution"] = {
            "execution_id": str(execution["execution_id"]),
            "role": execution_role,
            "parent_execution": "",
            "implementing_execution": "",
        }
    (packet / "evidence" / "validation.json").write_text(
        json.dumps(record, indent=2, sort_keys=True), encoding="utf-8"
    )
    return record


def validations_for(state: dict, packet_id: str = "widget-S4B") -> list[dict]:
    packet = Path(state["packets"][-1]["path"])
    record = json.loads((packet / "evidence" / "validation.json").read_text(encoding="utf-8"))
    return [{"packet_id": packet_id, "record": record}]


def verify(state: dict, *, fingerprint: str = "") -> dict:
    current = fingerprint or current_fingerprint(state)
    # Mirrors the CLI's revision composition: the pass digest binds the
    # implementation bytes, so a source change moves the revision.
    digest = proof.work_digest_for(TASK, "ar23d-work|impl:" + current)
    return proof.verify_task(
        state, task_text=TASK, work_digest=digest, task_id="widget-task",
        engine_validations=validations_for(state),
        implementation_fingerprint=current,
    )


def current_fingerprint(state: dict) -> str:
    return TRANSPORT.implementation_fingerprint(TRANSPORT.project_git_snapshot(Path(state["project"])))


def test_rows(state: dict, digest: str, requirement_id: str = "") -> list[dict]:
    return [
        row for row in evidence_module.evidence(state)
        if str(row.get("kind", "")) == "TEST"
        and (not digest or str(row.get("work_digest", "")) == digest)
        and (not requirement_id or requirement_id in (row.get("requirement_ids") or ()))
    ]


# ------------------------------------------------------------------ positive


@case
def genuine_validation_becomes_current_test_evidence():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        project = make_project(root)
        packet = make_packet(root, project)
        state = make_state(root, project, [{"id": "widget-S4B", "stage": "S4B", "path": str(packet)}])
        record = record_validation(state, project, packet)
        receipt = verify(state)
        execution_id = record["execution"]["execution_id"]
        rows = test_rows(state, receipt["work_digest"])
        assert rows, "the genuine validation did not become TEST evidence"
        row = rows[0]
        assert row["producer_execution"] == execution_id
        assert row["source_record_id"] == "widget-S4B"
        assert row["source_kind"] == "ENGINE_RECORD"
        assert "python -m unittest discover -s tests" in row["observation"]
        assert "(exit 0, passed)" in row["observation"]
        assert "MAPPED_FROM_ENGINE_WORKER_VALIDATION" in row["notes"]
        assert row["work_digest"] == receipt["work_digest"]
        assert rows[0]["stance"] == "SUPPORTS"
        decision = receipt["requirement_decisions"][0]
        assert decision["verdict"] == "PROVEN", decision
        assert receipt["acceptance_state"] == "ACCEPTED", receipt["acceptance_state"]


@case
def passing_checks_satisfy_only_the_declared_test_position():
    # The anti-cheat control: TEST evidence is live and current, and the
    # requirement still is not PROVEN because its own policy asks for more.
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        project = make_project(root)
        packet = make_packet(root, project)
        state = make_state(root, project, [{"id": "widget-S4B", "stage": "S4B", "path": str(packet)}])
        record_validation(state, project, packet)
        contract_record = proof.ensure_contract(state, task_text=TASK, task_id="widget-task")
        requirement = requirements_module.create(
            state, contract_id=str(contract_record["contract_id"]),
            text=TASK, kind="FUNCTIONAL", origin="EXPLICIT", task_id="widget-task",
            evidence_policy={
                "AUTHORITATIVE": [],
                "REQUIRED": ["TEST", "RUNTIME"],
                "SUPPORTING": [],
                "INSUFFICIENT_ALONE": [],
            },
        )
        digest = proof.work_digest_for(TASK, "ar23d-work")
        summary = integrations_module.from_worker_validation(
            state,
            validations=validations_for(state),
            implementation_fingerprint=current_fingerprint(state),
            contract_id=str(contract_record["contract_id"]),
            contract_revision=str(contract_record.get("revision", "1")),
            requirements=[requirement],
            task_id="widget-task",
            work_digest=digest,
        )
        assert summary["recorded"], "the positive control recorded nothing"
        rows = evidence_module.current(
            state, requirement_id=str(requirement["requirement_id"]),
            work_digest=digest, contract_revision=str(contract_record.get("revision", "1")),
        )
        assert any(str(row.get("kind")) == "TEST" for row in rows)
        decision = decisions_module.decide_requirement(
            requirement, rows=rows, contract_revision=str(contract_record.get("revision", "1")),
            work_digest=digest,
        )
        assert decision["verdict"] != "PROVEN", decision
        assert "RUNTIME" in json.dumps(decision)


@case
def test_insufficient_alone_never_carries_a_requirement():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        project = make_project(root)
        packet = make_packet(root, project)
        state = make_state(root, project, [{"id": "widget-S4B", "stage": "S4B", "path": str(packet)}])
        record_validation(state, project, packet)
        contract_record = proof.ensure_contract(state, task_text=TASK, task_id="widget-task")
        requirement = requirements_module.create(
            state, contract_id=str(contract_record["contract_id"]),
            text="The widget feels right.", kind="FUNCTIONAL", origin="EXPLICIT",
            task_id="widget-task",
            evidence_policy={
                "AUTHORITATIVE": [],
                "REQUIRED": ["REVIEW"],
                "SUPPORTING": ["TEST"],
                "INSUFFICIENT_ALONE": ["TEST"],
            },
        )
        digest = proof.work_digest_for(TASK, "ar23d-work")
        integrations_module.from_worker_validation(
            state,
            validations=validations_for(state),
            implementation_fingerprint=current_fingerprint(state),
            contract_id=str(contract_record["contract_id"]),
            contract_revision=str(contract_record.get("revision", "1")),
            requirements=[requirement],
            task_id="widget-task",
            work_digest=digest,
        )
        rows = evidence_module.current(
            state, requirement_id=str(requirement["requirement_id"]),
            work_digest=digest, contract_revision=str(contract_record.get("revision", "1")),
        )
        assert any(str(row.get("kind")) == "TEST" for row in rows), "the observation itself must exist"
        decision = decisions_module.decide_requirement(
            requirement, rows=rows, contract_revision=str(contract_record.get("revision", "1")),
            work_digest=digest,
        )
        assert decision["verdict"] != "PROVEN", decision


# ------------------------------------------------------------------ negative


def _refusal_reason(state: dict) -> str:
    summary = integrations_module.from_worker_validation(
        state,
        validations=validations_for(state),
        implementation_fingerprint=current_fingerprint(state),
        contract_id="ctr_probe",
        contract_revision="1",
        requirements=[{
            "requirement_id": "rqm_probe",
            "evidence_policy": {"authoritative": [], "required": ["TEST"], "supporting": [], "insufficient_alone": []},
        }],
        task_id="widget-task",
        work_digest=proof.work_digest_for(TASK, "ar23d-work"),
    )
    refusal = summary["refused"][0]["reason"] if summary["refused"] else ""
    assert not summary["recorded"], "a refused record must map to nothing"
    return refusal


@case
def a_failed_validation_is_never_test_evidence():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        project = make_project(root)
        packet = make_packet(root, project)
        state = make_state(root, project, [{"id": "widget-S4B", "stage": "S4B", "path": str(packet)}])
        record_validation(state, project, packet, status="failed", required_status="failed", failure_kind="routine")
        assert "failed" in _refusal_reason(state)


@case
def a_blocked_out_of_scope_validation_is_never_test_evidence():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        project = make_project(root)
        packet = make_packet(root, project)
        state = make_state(root, project, [{"id": "widget-S4B", "stage": "S4B", "path": str(packet)}])
        # A command run that passed, but on a repository whose scope is outside
        # the contract: the result is not evidence about this contract at all.
        record_validation(state, project, packet, scope_status="out-of-scope", failure_kind="none")
        reason = _refusal_reason(state)
        assert "out-of-scope" in reason, reason
        # A blocked record is refused on its status before anything else.
        record_validation(state, project, packet, status="blocked", failure_kind="out-of-scope")
        assert "blocked" in _refusal_reason(state)


@case
def a_required_command_that_did_not_pass_is_never_test_evidence():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        project = make_project(root)
        packet = make_packet(root, project)
        state = make_state(root, project, [{"id": "widget-S4B", "stage": "S4B", "path": str(packet)}])
        record = record_validation(state, project, packet)
        record["commands"][0]["status"] = "failed"
        (packet / "evidence" / "validation.json").write_text(json.dumps(record), encoding="utf-8")
        assert "did not pass" in _refusal_reason(state)


# ---------------------------------------------------------------- adversarial


@case
def a_worker_written_validation_file_maps_to_nothing():
    # No engine execution was ever created for this record: nothing executed it,
    # so it is a claim wearing an evidence filename.
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        project = make_project(root)
        packet = make_packet(root, project)
        state = make_state(root, project, [{"id": "widget-S4B", "stage": "S4B", "path": str(packet)}])
        record_validation(state, project, packet, with_execution=False)
        reason = _refusal_reason(state)
        assert "no validator execution" in reason


@case
def a_record_naming_a_foreign_execution_maps_to_nothing():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        project = make_project(root)
        packet = make_packet(root, project)
        state = make_state(root, project, [{"id": "widget-S4B", "stage": "S4B", "path": str(packet)}])
        record = record_validation(state, project, packet, execution_role="implementer")
        assert "not validator" in _refusal_reason(state) or "adapter" in _refusal_reason(state)


@case
def a_record_for_another_project_maps_to_nothing():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        project = make_project(root)
        other = root / "other-project"
        other.mkdir()
        packet = make_packet(root, project)
        state = make_state(root, project, [{"id": "widget-S4B", "stage": "S4B", "path": str(packet)}])
        record_validation(state, project, packet)
        execution = state["executions"][-1]
        execution["revision"]["project"] = str(other)
        assert "different project" in _refusal_reason(state)


@case
def a_forged_fingerprint_cannot_vouch_for_a_moved_tree():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        project = make_project(root)
        packet = make_packet(root, project)
        state = make_state(root, project, [{"id": "widget-S4B", "stage": "S4B", "path": str(packet)}])
        # The record claims a fingerprint of a tree that is not the current one.
        record_validation(state, project, packet, fingerprint="0" * 64)
        assert "stale" in _refusal_reason(state)


# ------------------------------------------------------------------- replay


@case
def replaying_a_pass_neither_duplicates_nor_loses_test_evidence():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        project = make_project(root)
        packet = make_packet(root, project)
        state = make_state(root, project, [{"id": "widget-S4B", "stage": "S4B", "path": str(packet)}])
        record_validation(state, project, packet)
        first = verify(state)
        second = verify(state)
        assert first["work_digest"] == second["work_digest"]
        rows = test_rows(state, first["work_digest"])
        assert len(rows) == 1, f"replay duplicated evidence: {len(rows)} rows"
        assert second["acceptance_state"] == "ACCEPTED"
        assert first["requirement_decisions"][0]["verdict"] == second["requirement_decisions"][0]["verdict"]
        assert second["validation_mapping"]["replayed"], (
            "a replayed pass must account for the existing evidence instead of recording blind"
        )


# --------------------------------------------------------------- stale steps


@case
def a_source_change_moves_the_revision_and_stales_the_recorded_tests():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        project = make_project(root)
        packet = make_packet(root, project)
        state = make_state(root, project, [{"id": "widget-S4B", "stage": "S4B", "path": str(packet)}])
        record_validation(state, project, packet)
        first = verify(state)
        assert first["acceptance_state"] == "ACCEPTED"
        # The implementation changes after validation. The record is unchanged,
        # but it is no longer about the current bytes.
        (project / "app.js").write_text("export const widget = 2;\n", encoding="utf-8")
        second = verify(state)
        assert second["work_digest"] != first["work_digest"], "the pass revision must bind the implementation"
        refused = second["validation_mapping"]["refused"]
        assert refused and "stale" in json.dumps(refused), refused
        reason = _refusal_reason(state)
        assert "stale" in reason, reason
        assert not test_rows(state, second["work_digest"]), "stale results must not appear current"
        decision = second["requirement_decisions"][0]
        assert decision["verdict"] != "PROVEN", decision
        assert second["acceptance_state"] != "ACCEPTED"
        # ...while the earlier receipt is preserved, not rewritten.
        assert proof.get_receipt(state, first["proof_id"])["acceptance_state"] == "ACCEPTED"


@case
def evidence_documents_do_not_move_the_implementation_fingerprint():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        project = make_project(root)
        before = current_fingerprint(state := make_state(root, project, []))
        (project / "QA.md").write_text("# QA\n\nedited by the review ingest\n", encoding="utf-8")
        (project / "AGENTS.md").write_text("# Agents\n\ncurrent state updated\n", encoding="utf-8")
        assert current_fingerprint(state) == before, "evidence documents must not invalidate implementation evidence"
        (project / "styles.css").write_text("body { margin: 1px; }\n", encoding="utf-8")
        assert current_fingerprint(state) != before, "implementation changes must move the fingerprint"


# ------------------------------------------------------------- independence


def _execution(state: dict, role: str, suffix: str) -> str:
    record = execution_module.create(
        state, task_id=f"task-{suffix}", role=role,
        adapter=f"scripts/{suffix}.py:{role}", invocation=f"{role} --{suffix}",
        requested={"provider": f"label-{suffix}", "model": f"model-label-{suffix}"},
    )
    return str(record["execution_id"])


@case
def same_provider_different_requested_labels_is_not_distinct_provider():
    state = {"schema_version": 1, "run_id": "ar23d-independence", "executions": []}
    implementer = _execution(state, "implementer", "worker")
    reviewer = _execution(state, "reviewer", "reviewer")
    level = review.independence_level(
        state, reviewer_execution=reviewer, implementing_execution=implementer
    )
    assert level == "DISTINCT_RUNTIME", level


@case
def equal_provider_observations_stay_distinct_runtime():
    state = {"schema_version": 1, "run_id": "ar23d-independence", "executions": []}
    implementer = _execution(state, "implementer", "worker")
    reviewer = _execution(state, "reviewer", "reviewer")
    for execution_id in (implementer, reviewer):
        provenance.record_provider_observation(
            state, execution_id, provider="same-provider", model="same-model",
            source="fixture-adapter",
        )
    level = review.independence_level(
        state, reviewer_execution=reviewer, implementing_execution=implementer
    )
    assert level == "DISTINCT_RUNTIME", level


@case
def different_provider_observations_are_distinct_provider():
    state = {"schema_version": 1, "run_id": "ar23d-independence", "executions": []}
    implementer = _execution(state, "implementer", "worker")
    reviewer = _execution(state, "reviewer", "reviewer")
    provenance.record_provider_observation(
        state, implementer, provider="provider-a", model="model-a", source="fixture-adapter",
    )
    provenance.record_provider_observation(
        state, reviewer, provider="provider-b", model="model-b", source="fixture-adapter",
    )
    level = review.independence_level(
        state, reviewer_execution=reviewer, implementing_execution=implementer
    )
    assert level == "DISTINCT_PROVIDER", level


@case
def one_sided_observation_never_reaches_distinct_provider():
    state = {"schema_version": 1, "run_id": "ar23d-independence", "executions": []}
    implementer = _execution(state, "implementer", "worker")
    reviewer = _execution(state, "reviewer", "reviewer")
    provenance.record_provider_observation(
        state, reviewer, provider="provider-b", model="model-b", source="fixture-adapter",
    )
    level = review.independence_level(
        state, reviewer_execution=reviewer, implementing_execution=implementer
    )
    assert level == "DISTINCT_RUNTIME", level


# ----------------------------------------------------------- producer shape


@case
def the_producer_records_a_valid_revision_binding():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        project = make_project(root)
        packet = make_packet(root, project)
        state = make_state(root, project, [{"id": "widget-S4B", "stage": "S4B", "path": str(packet)}])
        record = record_validation(state, project, packet)
        assert record["validated_revision"]["head"]
        fingerprint = record["validated_revision"]["implementation_fingerprint"]
        assert len(fingerprint) == 64 and fingerprint == current_fingerprint(state)
        assert TRANSPORT.worker_validation_problems(record, "widget-S4B") == []
        # A malformed binding is refused by the transport's own structural check.
        broken = json.loads(json.dumps(record))
        broken["validated_revision"]["implementation_fingerprint"] = "not-a-digest"
        assert TRANSPORT.worker_validation_problems(broken, "widget-S4B")


@case
def records_without_a_revision_binding_are_refused_not_guessed():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        project = make_project(root)
        packet = make_packet(root, project)
        state = make_state(root, project, [{"id": "widget-S4B", "stage": "S4B", "path": str(packet)}])
        record = record_validation(state, project, packet)
        del record["validated_revision"]
        (packet / "evidence" / "validation.json").write_text(json.dumps(record), encoding="utf-8")
        reason = _refusal_reason(state)
        assert "predates" in reason or "cannot be proven current" in reason


@case
def no_current_fingerprint_means_no_mapping():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        project = make_project(root)
        packet = make_packet(root, project)
        state = make_state(root, project, [{"id": "widget-S4B", "stage": "S4B", "path": str(packet)}])
        record_validation(state, project, packet)
        summary = integrations_module.from_worker_validation(
            state,
            validations=validations_for(state),
            implementation_fingerprint="",
            contract_id="ctr_probe",
            contract_revision="1",
            requirements=[{
                "requirement_id": "rqm_probe",
                "evidence_policy": {"authoritative": [], "required": ["TEST"], "supporting": [], "insufficient_alone": []},
            }],
            task_id="widget-task",
            work_digest=proof.work_digest_for(TASK, "ar23d-work"),
        )
        assert summary["refused"] and not summary["recorded"]


# --------------------------------------------------------------- intel gate


@case
def the_engine_cli_gathers_only_structurally_valid_records():
    assert hasattr(TRANSPORT, "implementation_fingerprint")
    assert hasattr(TRANSPORT, "validated_revision")
    import ariadne as runtime  # the runtime module under scripts/

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        project = make_project(root)
        packet = make_packet(root, project)
        state = make_state(root, project, [{"id": "widget-S4B", "stage": "S4B", "path": str(packet)}])
        record_validation(state, project, packet)
        gathered = runtime.recorded_worker_validations(state)
        assert len(gathered) == 1 and gathered[0]["packet_id"] == "widget-S4B"
        (packet / "evidence" / "validation.json").write_text("{not json", encoding="utf-8")
        assert runtime.recorded_worker_validations(state) == []
        # A non-S4B packet never contributes validations.
        (packet / "evidence" / "validation.json").write_text("{}", encoding="utf-8")
        state["packets"][0]["stage"] = "S5"
        assert runtime.recorded_worker_validations(state) == []


def main() -> int:
    filters = [arg.lower() for arg in sys.argv[1:]]
    passed = 0
    failures: list[str] = []
    total = 0
    for fn in CASES:
        name = fn.__name__.replace("_", " ")
        if filters and not any(item in name for item in filters):
            continue
        total += 1
        try:
            fn()
        except SkipCase as exc:
            SKIPS.append((name, str(exc)))
            print(f"skip {name}: {exc}")
            continue
        except BaseException as exc:  # noqa: BLE001
            print(f"FAIL {name}: {exc}")
            failures.append(name)
            continue
        print(f"ok   {name}")
        passed += 1
    skipped = f" ({len(SKIPS)} skipped)" if SKIPS else ""
    print(f"{passed}/{total} passed{skipped}")
    if failures:
        print("AR-23D suite: FAILURES PRESENT")
        return 1
    print("AR-23D suite: all green")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
