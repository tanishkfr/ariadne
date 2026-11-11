#!/usr/bin/env python3
"""Ariadne 2.4C: design verification, creative proof and host contract tests.

Every case here is deterministic. The live browser/UI qualification is a
separate recorded exercise in ``validation/runs/2.4c/design``; these cases prove
the checks that qualification relies on, including the defects each check must
catch.
"""

from __future__ import annotations

import contextlib
import hashlib
import importlib.util
import json
import struct
import subprocess
import sys
import tempfile
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

_spec = importlib.util.spec_from_file_location("ar23b_support", ROOT / "scripts" / "test-ar23b.py")
BASE = importlib.util.module_from_spec(_spec)
sys.modules["ar23b_support"] = BASE
_spec.loader.exec_module(BASE)

from ariadne_engine import (  # noqa: E402
    api,
    contracts,
    creative_proof,
    events,
    host,
    integration,
    mcp,
    persistence,
    policy,
    proof,
    rendered_critique,
    review,
    visual_diff,
)
from ariadne_engine.rendered_critique import critique, evidence, viewports, visual_regression  # noqa: E402

CASES: list = []


def case(fn):
    CASES.append(fn)
    return fn


def raises(fn, needle: str = "") -> str:
    try:
        fn()
    except Exception as exc:  # noqa: BLE001 - the assertion is the message
        text = str(exc)
        assert needle in text, f"refusal {text!r} did not name {needle!r}"
        return text
    raise AssertionError("expected a refusal, got success")


# --------------------------------------------------------------- fixtures


def execution(state: dict, *, role: str, adapter: str, suffix: str) -> dict:
    record = {
        "schema_version": contracts.SCHEMA_ADAPTIVE,
        "execution_id": f"exe_20261112T000000Z_{suffix}",
        "run_id": str(state.get("run_id", "run")),
        "task_id": "pkt-S5",
        "adapter": adapter,
        "created_at": "2026-11-12T00:00:00+00:00",
        "role": role,
        "state": "COMPLETED",
        "nonce": hashlib.sha256(suffix.encode()).hexdigest()[:32],
        "revision": {"revision_hash": "c" * 64},
        "provenance": {"created_by": "engine"},
        "requested": {"provider": adapter, "model": "m"},
        "observed": {"provider": adapter, "model": "m"},
    }
    state.setdefault("executions", []).append(record)
    return record


def png(width: int, height: int, colour=(255, 255, 255), region=None) -> bytes:
    rows = []
    for y in range(height):
        row = bytearray()
        for x in range(width):
            pixel = colour
            if region and region[0] <= x < region[2] and region[1] <= y < region[3]:
                pixel = (0, 0, 0)
            row.extend((pixel[0], pixel[1], pixel[2], 255))
        rows.append(b"\x00" + bytes(row))
    raw = zlib.compress(b"".join(rows), 9)

    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + kind + data + struct.pack(
            ">I", zlib.crc32(kind + data) & 0xFFFFFFFF
        )

    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
        + chunk(b"IDAT", raw)
        + chunk(b"IEND", b"")
    )


def manifest(directory: Path, *, set_id: str, digest: str, width: int) -> dict:
    path = directory / f"{set_id}.png"
    path.write_bytes(png(40, 30, region=(5, 5, 12, 12) if set_id == "after" else None))
    return {
        "schema_version": contracts.SCHEMA_DESIGN,
        "evidence_set_id": set_id,
        "capture_plan_id": "rcp-test",
        "render_source_digest": digest,
        "browser": {"adapter": "chromium-render", "browser": "chromium"},
        "captures": [{
            "capture_id": "capture_001",
            "route": "/",
            "state": "default",
            "viewport": {"width": width, "height": 800},
            "artifact_path": str(path),
            "digest": hashlib.sha256(path.read_bytes()).hexdigest(),
            "captured_at": "2026-11-12T00:00:00+00:00",
            "render_source_digest": digest,
            "artifact": {"state": "VALID", "reasons": []},
        }],
        "status": "COMPLETE",
        "started_at": "2026-11-12T00:00:00+00:00",
    }


def s5_state(
    root: Path,
    *,
    outcome: str = "passed",
    recommendation: str = "present g3",
    findings: tuple[str, ...] = (),
    reviewer_execution: str = "",
    implementing_execution: str = "",
    with_review: bool = True,
    packet_id: str = "pkt-S5",
) -> tuple[dict, Path]:
    packet = root / packet_id
    (packet / "evidence").mkdir(parents=True)
    judgement = packet / "evidence" / "review-judgement.md"
    judgement.write_text("## Judgement\n\nA complete independent review.\n", encoding="utf-8")
    validation = packet / "evidence" / "validation.json"
    validation.write_text(json.dumps({
        "status": "passed",
        "packet_id": packet_id,
        "validated_revision": {
            "implementation_fingerprint": "a" * 64,
            "head": "b" * 40,
        },
    }, indent=2), encoding="utf-8")
    packet_digest = hashlib.sha256(b"current-packet").hexdigest()
    (packet / "manifest.json").write_text(json.dumps({
        "packet_id": packet_id,
        "packet_sha256": packet_digest,
        "sources": [],
    }), encoding="utf-8")
    state = {
        "schema_version": contracts.SCHEMA_RUN,
        "run_id": "run-creative",
        "project": str(root / "project"),
        "run_root": str(root),
        "packets": [{"id": packet_id, "stage": "S5", "path": str(packet)}],
        "reviews": [],
        "executions": [],
        "approvals": [],
    }
    reviewer = execution(state, role="reviewer", adapter="opencode", suffix="11111111")
    implementer = execution(state, role="implementer", adapter="command-code", suffix="22222222")
    if with_review:
        record = {
            "schema_version": contracts.SCHEMA_RECORD,
            "review_id": "rev_20261112T000000Z_abcdef12",
            "run_id": "run-creative",
            "packet_id": packet_id,
            "attempt_id": "",
            "task_id": packet_id,
            "review_kind": "experience",
            "reviewer_identity": "reviewer",
            "reviewer_role": "independent-reviewer",
            "context_digest": packet_digest,
            "reviewed_revision": hashlib.sha256(validation.read_bytes()).hexdigest(),
            "validation_sha256": hashlib.sha256(validation.read_bytes()).hexdigest(),
            "requirements": ["r1"],
            "evidence": ["recorded review judgement"],
            "findings": list(findings),
            "outcome": outcome,
            "recommendation": recommendation,
            "recorded_at": "2026-11-12T00:00:00+00:00",
            "independent": True,
            "execution_binding": "engine",
            "reviewer_execution": reviewer_execution or reviewer["execution_id"],
            "implementing_execution": implementing_execution or implementer["execution_id"],
            "independence_level": "DISTINCT_RUNTIME",
            "review_judgement_sha256": hashlib.sha256(judgement.read_bytes()).hexdigest(),
        }
        state["reviews"].append(record)
    return state, packet


# ------------------------------------------------------- C1 viewport matrix


@case
def a_declared_matrix_is_the_only_responsive_ladder_used():
    implementation = {
        "viewports": [
            {"class": "narrow", "width": 320, "height": 800},
            {"class": "mobile", "width": 390, "height": 844},
            {"class": "tablet", "width": 834, "height": 1112},
            {"class": "desktop", "width": 1440, "height": 900},
            {"class": "wide", "width": 1920, "height": 1080, "device_scale_factor": 1},
        ]
    }
    rows = rendered_critique.plan.responsive_viewports(
        {"claims": {"responsive": "the inspector stacks"}}, implementation
    )
    assert [row["width"] for row in rows] == [320, 390, 834, 1440, 1920], rows
    assert [row["viewport_class"] for row in rows] == ["narrow", "mobile", "tablet", "desktop", "wide"]


@case
def wrong_viewport_evidence_does_not_satisfy_the_requested_width():
    state = {
        "rendered_evidence": [{
            "evidence_id": "rnd_20261112T000000Z_11111111",
            "requirement_id": "r1",
            "state": "VERIFIED",
            "viewport": {"width": "390"},
            "revision_hash": "c" * 64,
        }]
    }
    from ariadne_engine import render

    assert render.strongest(state, "r1", viewport_width="390")["evidence_id"].startswith("rnd_")
    assert render.strongest(state, "r1", viewport_width="1440") == {}


@case
def a_responsive_claim_missing_a_declared_class_is_refused():
    implementation = {
        "viewports": [{"class": "desktop", "width": 1440, "height": 900}],
        "supported_width_range": [320, 1920],
    }
    problems = viewports.matrix_problems(implementation, responsive_claimed=True)
    assert any("omits viewport class" in problem for problem in problems), problems


@case
def a_matrix_with_a_duplicate_width_is_refused():
    raises(
        lambda: viewports.declared({"viewports": [
            {"class": "mobile", "width": 390, "height": 844},
            {"class": "tablet", "width": 390, "height": 1112},
        ]}),
        "repeats width",
    )


@case
def declared_matrix_targets_cover_every_supported_class():
    rows = viewports.declared({"viewports": [
        {"class": "narrow", "width": 320, "height": 800},
        {"class": "mobile", "width": 390, "height": 844},
        {"class": "tablet", "width": 834, "height": 1112},
        {"class": "desktop", "width": 1440, "height": 900},
        {"class": "wide", "width": 1920, "height": 1080},
    ]})
    targets = viewports.targets(rows, routes=["/"], basis=[{"basis": "REQUIREMENT", "reason": "responsive check"}])
    assert len(targets) == 5, targets
    assert {row["viewport_class"] for row in targets} == {
        "narrow", "mobile", "tablet", "desktop", "wide"
    }, targets


# -------------------------------------------------------- C1 visual diff


@case
def pixel_comparison_finds_the_changed_region_and_not_the_identical_one():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        same_a = root / "a.png"
        same_b = root / "b.png"
        changed = root / "c.png"
        same_a.write_bytes(png(40, 30))
        same_b.write_bytes(png(40, 30))
        changed.write_bytes(png(40, 30, region=(5, 5, 12, 12)))
        identical = visual_diff.compare_files(same_a, same_b)
        different = visual_diff.compare_files(same_a, changed)
        assert identical["verdict"] == "IDENTICAL", identical
        assert different["verdict"] == "CHANGED", different
        assert different["bounding_box"] == {"x": 5, "y": 5, "width": 7, "height": 7}, different
        assert different["changed_pixels"] == 49, different


@case
def a_dimension_mismatch_is_not_a_visual_diff():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        left = root / "a.png"
        right = root / "b.png"
        left.write_bytes(png(40, 30))
        right.write_bytes(png(41, 30))
        result = visual_diff.compare_files(left, right)
        assert result["verdict"] == "INCOMPATIBLE", result
        assert result["diff_ratio"] is None
        assert "same viewport" in result["reason"]


@case
def a_changed_render_requires_review_and_never_scores_quality():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        before = manifest(root, set_id="before", digest="1" * 64, width=390)
        after = manifest(root, set_id="after", digest="2" * 64, width=390)
        record = visual_regression.build(
            before_manifest=before, after_manifest=after, route="/", width=390,
            threshold=0.1, task_id="task-1",
        )
        assert record["result"]["verdict"] == "CHANGED", record
        assert record["requires_review"] is True
        assert record["quality_judgement"] == "none"
        assert record["authorization_effect"] == "none"


@case
def a_visual_regression_of_the_same_revision_is_refused():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        before = manifest(root, set_id="before", digest="1" * 64, width=390)
        after = manifest(root, set_id="after", digest="1" * 64, width=390)
        raises(
            lambda: visual_regression.build(
                before_manifest=before, after_manifest=after, route="/", width=390,
            ),
            "same source digest",
        )


# ---------------------------------------------------- C1 accessibility checks


@case
def accessibility_checks_catch_contrast_focus_dialog_and_form_defects():
    report = {
        "unlabelled_controls": [{"tag": "button"}],
        "focusable_count": 2,
        "focusable_without_ring": [{"tag": "button", "label": "Start"}],
        "small_targets": [{"tag": "button", "w": 18, "h": 18}],
        "prefers_reduced_motion": True,
        "transition_duration": "0.3s",
        "accessibility": {
            "contrast": {
                "checks": 2,
                "failures": [{
                    "tag": "p", "text": "quiet", "ratio": 2.1, "required": 4.5,
                    "foreground": "rgb(154, 148, 139)", "background": "rgb(247, 244, 238)",
                }],
                "unverified": 1,
            },
            "dialogs": [{"visible": True, "focus_inside": False, "accessible_name": "Settings"}],
            "form_controls": [{"id": "duration", "invalid": True, "described_by": ""}],
            "status_messages": [{"role": "alert", "text": "Enter a duration"}],
        },
    }
    a11y = evidence.accessibility_report(report)
    checks = {finding["check"] for finding in a11y["findings"]}
    assert {"accessible-name", "focus-visible", "target-size", "reduced-motion",
            "contrast", "dialog-focus", "form-errors"} <= checks, checks
    assert a11y["contrast"]["failures"] == 1
    assert a11y["contrast"]["unverified"] == 1
    assert "WCAG conformance" in a11y["not_established"]
    assert "colour contrast as perceived" in " ".join(a11y["not_established"])


@case
def a_focus_ring_on_one_control_does_not_hide_a_ringless_control():
    a11y = evidence.accessibility_report({
        "focusable_count": 2,
        "focusable": True,
        "focus_visible": True,
        "focusable_without_ring": [{"tag": "button", "label": "Save"}],
    })
    assert any(finding["check"] == "focus-visible" for finding in a11y["findings"])
    assert "1 of 2" in a11y["findings"][0]["detail"]


# ---------------------------------------------------- C1 interaction scripts


class FakeAdapter:
    def __init__(self, values):
        self.values = list(values)

    def evaluate(self, expression):
        value = self.values.pop(0)
        if isinstance(value, Exception):
            raise value
        return value


@case
def interaction_assertions_record_pass_fail_and_unverified():
    checks = evidence._evaluate_assertions(FakeAdapter([True, False, RuntimeError("no page")]), [
        {"kind": "visible", "selector": "#timer", "description": "timer visible"},
        {"kind": "text", "text": "Started"},
        {"kind": "aria", "selector": "#duration", "attribute": "aria-invalid", "equals": "true"},
    ])
    assert [row["state"] for row in checks] == ["PASSED", "FAILED", "UNVERIFIED"], checks
    assert checks[1]["passed"] is False
    assert checks[2]["passed"] is None


# ------------------------------------------------------- C1 review judgement


@case
def a_green_automated_check_cannot_clear_an_open_design_finding():
    from ariadne_engine.rendered_critique import contracts_bridge

    verdict = critique._verdict([{
        "finding_id": "rfd_1", "dimension": "interaction", "severity": "major",
        "basis": "DETERMINISTIC", "state": "OPEN",
    }])
    assert verdict == "RENDERED_WITH_KNOWN_FINDINGS", verdict
    problems = contracts_bridge.validate_visual_acceptance({
        "visual_acceptance": "VERIFIED_BY_RENDERED_CHECK",
    })
    assert problems, "a visual acceptance claim without a critique id was accepted"


@case
def a_review_can_say_technically_correct_but_visually_weak_without_a_score():
    row = critique._qualitative(
        {
            "screens_reviewed": ["capture_001"],
            "factual_failures": [],
            "subjective_recommendations": [{
                "screen": "capture_001", "dimension": "typography",
                "text": "The headline scale is correct but the page reads flat; give the clock more authority.",
            }],
            "technically_correct_but_visually_weak": True,
            "overall_note": "No factual defect remains; the composition needs one clear focal point.",
        },
        valid_captures={"capture_001"},
        finding_ids=set(),
        requirement_ids=["r1"],
    )
    assert row["technically_correct_but_visually_weak"] is True
    assert row["scoring"].startswith("none")
    assert row["subjective_recommendations"][0]["blocking"] is False
    problems = contracts.rendered_critique_problems({"qualitative": {"score": 91}})
    assert any("numeric taste score" in problem for problem in problems), problems


# --------------------------------------------------------- C2 creative proof


@case
def a_current_passed_review_binds_to_the_proof_receipt():
    with tempfile.TemporaryDirectory() as tmp:
        state, packet = s5_state(Path(tmp))
        binding = creative_proof.build(
            state, work_digest="d" * 64, implementation_fingerprint="a" * 64,
        )
        assert binding["packet_id"] == "pkt-S5"
        assert binding["review_id"] == "rev_20261112T000000Z_abcdef12"
        assert not creative_proof.binding_shape_problems(binding)
        receipt = proof.verify_task(
            state, task_text="Deliver the reviewed countdown page.", work_digest="d" * 64,
            task_id="pkt-S5", implementation_fingerprint="a" * 64,
        )
        assert receipt.get("creative_review", {}).get("review_id") == binding["review_id"]
        assert not proof.receipt_problems(receipt)
        assert receipt["creative_review"]["authorization_effect"] == "none"
        assert state.get("approvals") == [], "proof must not mint a human gate"


@case
def a_missing_review_blocks_creative_proof():
    with tempfile.TemporaryDirectory() as tmp:
        state, _packet = s5_state(Path(tmp), with_review=False)
        raises(
            lambda: creative_proof.build(state, work_digest="d" * 64),
            "no review record exists",
        )


@case
def a_failed_review_cannot_bind_to_proof():
    with tempfile.TemporaryDirectory() as tmp:
        state, _packet = s5_state(
            Path(tmp), outcome="failed", recommendation="fix and re-review",
            findings=("the clock is unreadable",),
        )
        raises(
            lambda: creative_proof.build(state, work_digest="d" * 64),
            "outcome is 'failed'",
        )


@case
def a_changed_judgement_file_invalidates_the_review_digest():
    with tempfile.TemporaryDirectory() as tmp:
        state, packet = s5_state(Path(tmp))
        binding = creative_proof.build(
            state, work_digest="d" * 64, implementation_fingerprint="a" * 64,
        )
        (packet / "evidence" / "review-judgement.md").write_text(
            "## Judgement\n\nA different judgement.\n", encoding="utf-8"
        )
        problems = creative_proof.current_problems(
            binding, state, work_digest="d" * 64, implementation_fingerprint="a" * 64,
        )
        assert any("judgement file changed" in problem for problem in problems), problems


@case
def a_different_implementation_revision_invalidates_the_binding():
    with tempfile.TemporaryDirectory() as tmp:
        state, _packet = s5_state(Path(tmp))
        binding = creative_proof.build(
            state, work_digest="d" * 64, implementation_fingerprint="a" * 64,
        )
        problems = creative_proof.current_problems(
            binding, state, work_digest="e" * 64, implementation_fingerprint="f" * 64,
        )
        assert any("different implementation revision" in problem for problem in problems), problems
        old_fingerprint_build = lambda: creative_proof.build(
            state, work_digest="d" * 64, implementation_fingerprint="f" * 64,
        )
        raises(old_fingerprint_build, "current implementation is")


@case
def another_attempts_review_cannot_satisfy_the_current_packet():
    with tempfile.TemporaryDirectory() as tmp:
        state, _packet = s5_state(Path(tmp))
        state["reviews"][0]["packet_id"] = "pkt-other"
        raises(
            lambda: creative_proof.build(state, work_digest="d" * 64),
            "no review record exists",
        )


@case
def a_review_by_the_implementing_execution_is_refused():
    with tempfile.TemporaryDirectory() as tmp:
        state, _packet = s5_state(Path(tmp))
        shared = state["executions"][0]["execution_id"]
        state["reviews"][0]["reviewer_execution"] = shared
        state["reviews"][0]["implementing_execution"] = shared
        raises(
            lambda: creative_proof.build(state, work_digest="d" * 64),
            "independence is not established",
        )


@case
def a_stale_s5_packet_digest_is_refused():
    with tempfile.TemporaryDirectory() as tmp:
        state, packet = s5_state(Path(tmp))
        binding = creative_proof.build(
            state, work_digest="d" * 64, implementation_fingerprint="a" * 64,
        )
        manifest_path = packet / "manifest.json"
        value = json.loads(manifest_path.read_text(encoding="utf-8"))
        value["packet_sha256"] = "9" * 64
        manifest_path.write_text(json.dumps(value), encoding="utf-8")
        problems = creative_proof.current_problems(
            binding, state, work_digest="d" * 64, implementation_fingerprint="a" * 64,
        )
        assert any("packet digest differs" in problem for problem in problems), problems


@case
def a_tampered_binding_or_receipt_fails_closed():
    with tempfile.TemporaryDirectory() as tmp:
        state, _packet = s5_state(Path(tmp))
        binding = creative_proof.build(
            state, work_digest="d" * 64, implementation_fingerprint="a" * 64,
        )
        tampered = dict(binding)
        tampered["outcome"] = "failed"
        assert creative_proof.binding_shape_problems(tampered)
        receipt = proof.verify_task(
            state, task_text="Deliver the reviewed countdown page.", work_digest="d" * 64,
            task_id="pkt-S5", implementation_fingerprint="a" * 64,
        )
        receipt["acceptance_state"] = "ACCEPTED"
        assert any("digest does not bind" in problem for problem in proof.receipt_problems(receipt))


@case
def a_version_one_receipt_stays_readable_and_is_not_reinterpreted():
    with tempfile.TemporaryDirectory() as tmp:
        state, _packet = s5_state(Path(tmp))
        receipt = proof.verify_task(
            state, task_text="Deliver the reviewed countdown page.", work_digest="d" * 64,
            task_id="pkt-S5", implementation_fingerprint="a" * 64,
        )
        old = dict(receipt)
        old.pop("creative_review", None)
        old["schema_version"] = "ar-224-proof-receipt-1"
        old["receipt_digest"] = proof.receipt_digest(old)
        assert proof.receipt_problems(old) == [], proof.receipt_problems(old)
        assert old.get("creative_review") is None
        assert receipt["schema_version"] == "ar-224-proof-receipt-2"


@case
def g3_is_still_a_human_owned_decision_after_a_passing_review():
    with tempfile.TemporaryDirectory() as tmp:
        state, packet = s5_state(Path(tmp))
        subject = policy.review_subject(state, packet)
        satisfied, reason = policy.gate_satisfied(state, "G3", subject)
        assert not satisfied and "no G3 approval" in reason, (satisfied, reason)
        proof.verify_task(
            state, task_text="Deliver the reviewed countdown page.", work_digest="d" * 64,
            task_id="pkt-S5", implementation_fingerprint="a" * 64,
        )
        assert state.get("approvals") == []


# ----------------------------------------------------------- C3 host contract


@case
def host_contract_is_versioned_read_only_and_has_no_authority():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        project = BASE.make_project(root)
        assert BASE.start_task(project)[0] == 0
        run_root = BASE.run_root_for(project)
        state = BASE.state_of(run_root)
        state["run_root"] = str(run_root)
        view = api.host_status_state(state)
        assert view["schema_version"] == "ariadne-host-1"
        assert view["read_only"] is True
        assert view["authority_effect"] == "none"
        assert view["authority"]["authority_effect"] == "none"
        assert "cannot approve" in view["note"]
        for forbidden in ("approve", "accept", "validate", "review"):
            assert forbidden not in json.dumps(view["authority"]).lower() or "cannot" in view["authority"]["permitted_action_boundary"]


@case
def host_events_resume_without_duplicating_a_transition():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        project = BASE.make_project(root)
        assert BASE.start_task(project)[0] == 0
        run_root = BASE.run_root_for(project)
        first = host.event_page(run_root)
        assert first["status"] == "OK", first
        assert first["events"], "the task preparation emitted no events"
        cursor = first["next_cursor"]
        second = host.event_page(run_root, cursor=cursor)
        assert second["status"] == "OK", second
        first_ids = {row["event_id"] for row in first["events"]}
        second_ids = {row["event_id"] for row in second["events"]}
        assert not (first_ids & second_ids), (first_ids, second_ids)
        assert all(int(row["seq"]) > int(cursor["seq"]) for row in second["events"])


@case
def an_unknown_host_cursor_is_refused_not_replayed():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        project = BASE.make_project(root)
        assert BASE.start_task(project)[0] == 0
        run_root = BASE.run_root_for(project)
        page = host.event_page(run_root)
        bad = dict(page["next_cursor"])
        bad["digest"] = "0" * 64
        refused = host.event_page(run_root, cursor=bad)
        assert refused["status"] == "CURSOR_INVALID", refused
        assert refused["events"] == []
        assert refused["problems"]


@case
def cli_api_and_mcp_host_views_agree():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        project = BASE.make_project(root)
        assert BASE.start_task(project)[0] == 0
        run_root = BASE.run_root_for(project)
        state = BASE.state_of(run_root)
        state["run_root"] = str(run_root)
        api_view = api.host_status_state(state)
        mcp_view = mcp.dispatch(state, tool="host_status", params={})
        completed = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "ariadne.py"), "host-status",
             "--run-root", str(run_root), "--json"],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
        )
        assert completed.returncode == 0, completed.stderr
        cli_view = json.loads(completed.stdout)
        for view in (api_view, mcp_view, cli_view):
            assert view["schema_version"] == "ariadne-host-1"
            assert view["read_only"] is True
            assert view["authority_effect"] == "none"
        assert api_view["task"]["task_id"] == mcp_view["task"]["task_id"] == cli_view["task"]["task_id"]
        assert api_view["authority"]["pending_gate"] == cli_view["authority"]["pending_gate"]


@case
def integration_protocol_two_exposes_the_host_contract_and_keeps_v1_supported():
    description = integration.describe()
    assert description["protocol"]["version"] == 2
    assert description["protocol"]["min_supported"] == 1
    assert "host_status" in description["operations"]
    assert "host_events" in description["operations"]
    assert description["host_contract"]["read_only"] is True
    _v1, problems = integration.negotiate({
        "protocol_version": 1, "required_capabilities": ["lifecycle"], "consumer": "v1/1",
    })
    assert problems == [], problems
    _v2, problems = integration.negotiate({
        "protocol_version": 2, "required_capabilities": ["host-contract", "events-cursor"],
        "consumer": "v2/1",
    })
    assert problems == [], problems


@case
def an_external_consumer_reads_the_contract_and_survives_a_restart():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        project = BASE.make_project(root)
        assert BASE.start_task(project)[0] == 0
        run_root = BASE.run_root_for(project)
        consumer = ROOT / "tests" / "fixtures" / "external-host-consumer" / "consumer.py"
        state_file = root / "consumer-state.json"
        first = subprocess.run(
            [sys.executable, str(consumer), "--ariadne", str(ROOT / "scripts" / "ariadne.py"),
             "--run-root", str(run_root), "--state", str(state_file), "--json"],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
        )
        assert first.returncode == 0, (first.stdout, first.stderr)
        first_report = json.loads(first.stdout)
        assert first_report["status"] == "OK", first_report
        assert first_report["read_only"] is True
        second = subprocess.run(
            [sys.executable, str(consumer), "--ariadne", str(ROOT / "scripts" / "ariadne.py"),
             "--run-root", str(run_root), "--state", str(state_file), "--json"],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
        )
        assert second.returncode == 0, (second.stdout, second.stderr)
        second_report = json.loads(second.stdout)
        assert second_report["run_count"] == 2
        assert second_report["events"]["duplicate_event_ids"] == [], second_report
        assert second_report["refused_cursor"] == "CURSOR_INVALID", second_report


@case
def host_status_exposes_the_creative_g3_and_a_fresh_proof():
    with tempfile.TemporaryDirectory() as tmp:
        state, packet = s5_state(Path(tmp))
        receipt = proof.verify_task(
            state, task_text="Deliver the reviewed countdown page.", work_digest="d" * 64,
            task_id="pkt-S5", implementation_fingerprint="a" * 64,
        )
        state["proof_receipts"] = [receipt]
        view = host.status(state, task_report={"task_id": packet.name, "proof": {"proof_id": receipt["proof_id"]}})
        assert view["authority"]["pending_gate"] == "G3", view["authority"]
        assert view["authority"]["gate_subject_digest"], view["authority"]
        assert view["verification"]["proof"]["creative_review"]["bound"] is True
        assert view["verification"]["proof"]["fresh"] is True, view["verification"]["proof"]
        assert view["read_only"] is True


@case
def a_forged_host_proof_state_is_reported_invalid():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        project = BASE.make_project(root)
        assert BASE.start_task(project)[0] == 0
        run_root = BASE.run_root_for(project)
        state = BASE.state_of(run_root)
        state["run_root"] = str(run_root)
        state["proof_receipts"] = [{
            "schema_version": "ar-224-proof-receipt-2",
            "proof_id": "VP-9999",
            "task_id": "forged",
            "contract_id": "forged",
            "contract_revision": "1",
            "work_digest": "d" * 64,
            "created_at": "2026-11-12T00:00:00+00:00",
            "requirement_verdicts": {},
            "requirement_decisions": [],
            "claim_assessments": [],
            "acceptance_state": "ACCEPTED",
            "receipt_digest": "0" * 64,
        }]
        views = host.status(state, task_report={"task_id": "forged", "proof": {"proof_id": "VP-9999"}})
        assert views["verification"]["proof"]["acceptance_state"] == "INVALID_RECEIPT"
        assert views["verification"]["proof"]["integrity_problems"]


def main() -> int:
    filters = [arg.lower().replace("_", " ") for arg in sys.argv[1:]]
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
        except Exception as exc:  # noqa: BLE001
            failures.append(fn.__name__)
            import traceback
            print(f"FAIL {fn.__name__}: {exc}")
            traceback.print_exc()
        else:
            passed += 1
            print(f"ok   {fn.__name__}")
    print(f"\n{'PASS' if not failures else 'FAIL'}  {passed}/{total}")
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
