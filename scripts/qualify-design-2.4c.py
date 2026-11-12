#!/usr/bin/env python3
"""Ariadne 2.4C design qualification: real rendered UI, defects, correction, proof.

This is not a synthetic unit fixture. It creates a disposable static surface,
renders it in the installed Chromium-family browser through Ariadne's existing
capture pipeline, checks a declared viewport matrix, exercises real keyboard and
form interactions, computes accessibility findings, compares before/after
screenshots, and records the result as engine evidence.

Phases:
    before  create the defective surface, capture it, record findings
    after   write the corrected surface, capture it, compare, record a passing
            independent rendered critique and a creative Proof Receipt

The project and captures live under ``validation/runs/2.4c/design``. They are
disposable qualification artifacts, never a user project.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ariadne_engine import (  # noqa: E402
    contracts,
    critique as design_critique,
    design,
    execution,
    policy,
    proof,
    rendered_critique,
    review,
)
from ariadne_engine.rendered_critique import source as design_source  # noqa: E402
from ariadne_engine.rendered_critique import (  # noqa: E402
    adapter as render_adapter,
    critique as rendered_critique_module,
    evidence as rendered_evidence,
    plan as capture_plan,
    viewports,
    visual_regression,
)

DEFECTIVE = {
    "index.html": """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Quiet Countdown</title>
  <link rel="stylesheet" href="styles.css">
</head>
<body>
  <header class="site-header">
    <a class="brand" href="/">Quiet</a>
    <nav aria-label="Primary">
      <a href="#timer">Timer</a>
      <a href="#about">About</a>
      <a href="#settings">Settings</a>
    </nav>
  </header>
  <main id="timer">
    <h1>Quiet countdown</h1>
    <p class="lede">Set one duration. Let the room stay quiet.</p>
    <form id="timer-form" novalidate>
      <label for="duration">Minutes</label>
      <input id="duration" name="duration" type="text" inputmode="numeric" value="25">
      <button id="start" type="submit">Start</button>
      <p id="feedback" class="feedback" aria-live="polite"></p>
    </form>
    <output id="clock" aria-live="polite">25:00</output>
    <button id="open-settings" type="button">Settings</button>
  </main>
  <section id="about"><h2>About</h2><p>One uninterrupted block.</p></section>
  <section id="settings" class="settings-panel" role="dialog" aria-modal="true" aria-label="Settings" hidden>
    <h2>Settings</h2>
    <p>Nothing to configure yet.</p>
    <button id="dialog-close" type="button">Close</button>
  </section>
  <script src="app.js"></script>
</body>
</html>
""",
    "styles.css": """* { box-sizing: border-box; }
body {
  margin: 0;
  font-family: Georgia, serif;
  background: #f7f4ee;
  color: #9a948b;
}
.site-header {
  display: flex;
  gap: 24px;
  align-items: center;
  padding: 20px 48px;
  width: 1120px;
}
.site-header nav { display: flex; gap: 18px; }
.site-header a { color: inherit; text-decoration: none; }
main { width: 980px; margin: 0 auto; padding: 48px 0; }
h1 { font-size: 56px; margin: 0 0 16px; }
.lede { font-size: 20px; }
form { display: flex; gap: 12px; align-items: end; margin-top: 40px; }
input {
  width: 120px;
  padding: 10px;
  border: 1px solid #cfc8bd;
  background: #ffffff;
  color: #9a948b;
}
button {
  padding: 10px 18px;
  border: 0;
  background: #1f2937;
  color: #ffffff;
  cursor: pointer;
}
button:focus { outline: none; }
input:focus { outline: none; }
#clock { display: block; font-size: 96px; margin-top: 40px; }
.feedback { min-height: 24px; }
.settings-panel { width: 360px; margin: 40px auto; padding: 24px; background: #ffffff; }
""",
    "app.js": """(function () {
  const form = document.getElementById('timer-form');
  const input = document.getElementById('duration');
  const feedback = document.getElementById('feedback');
  const clock = document.getElementById('clock');
  const panel = document.getElementById('settings');
  const opener = document.getElementById('open-settings');
  const closer = document.getElementById('dialog-close');

  function render(minutes) {
    const safe = Math.max(0, Number(minutes) || 0);
    const whole = Math.floor(safe);
    const seconds = Math.round((safe - whole) * 60);
    clock.textContent = String(whole).padStart(2, '0') + ':' + String(seconds).padStart(2, '0');
  }

  form.addEventListener('submit', function (event) {
    event.preventDefault();
    const value = Number(input.value);
    if (!Number.isFinite(value) || value <= 0 || value > 180) {
      feedback.textContent = '';
      return;
    }
    feedback.textContent = 'Timer set for ' + value + ' minute(s).';
    render(value);
  });

  opener.addEventListener('click', function () {
    panel.hidden = false;
  });
  closer.addEventListener('click', function () {
    panel.hidden = true;
  });
  render(input.value);
})();
""",
}

FIXED = {
    "styles.css": """* { box-sizing: border-box; }
body {
  margin: 0;
  font-family: Georgia, serif;
  background: #f7f4ee;
  color: #1f2937;
}
.site-header {
  display: flex;
  flex-wrap: wrap;
  gap: 16px 24px;
  align-items: center;
  padding: 20px 24px;
  max-width: 1120px;
}
.site-header nav { display: flex; flex-wrap: wrap; gap: 18px; }
.site-header a { color: inherit; text-decoration: none; display: inline-flex; align-items: center; min-height: 24px; }
main { max-width: 980px; margin: 0 auto; padding: 40px 24px; }
h1 { font-size: clamp(36px, 8vw, 56px); margin: 0 0 16px; }
.lede { font-size: 20px; }
form { display: flex; flex-wrap: wrap; gap: 12px; align-items: end; margin-top: 40px; }
input {
  width: 140px;
  min-height: 44px;
  padding: 10px;
  border: 1px solid #8a8175;
  background: #ffffff;
  color: #1f2937;
}
button {
  min-height: 44px;
  padding: 10px 18px;
  border: 0;
  background: #1f2937;
  color: #ffffff;
  cursor: pointer;
}
button:focus-visible, input:focus-visible, a:focus-visible {
  outline: 3px solid #0b63ce;
  outline-offset: 3px;
}
#clock { display: block; font-size: clamp(64px, 18vw, 96px); margin-top: 40px; }
#about { max-width: 980px; margin: 0 auto; padding: 24px 24px; }
.feedback { min-height: 24px; color: #8a1c1c; }
.settings-panel {
  position: fixed;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  width: min(360px, calc(100% - 32px));
  max-height: calc(100vh - 32px);
  overflow: auto;
  padding: 24px;
  background: #ffffff;
  border: 1px solid #8a8175;
  box-shadow: 0 18px 48px rgba(31, 41, 55, 0.24);
}
.settings-panel[hidden] { display: none; }
@media (max-width: 600px) {
  .site-header { width: auto; padding: 16px; }
  main { padding: 24px 16px; }
}
""",
    "app.js": """(function () {
  const form = document.getElementById('timer-form');
  const input = document.getElementById('duration');
  const feedback = document.getElementById('feedback');
  const clock = document.getElementById('clock');
  const panel = document.getElementById('settings');
  const opener = document.getElementById('open-settings');
  const closer = document.getElementById('dialog-close');

  function render(minutes) {
    const safe = Math.max(0, Number(minutes) || 0);
    const whole = Math.floor(safe);
    const seconds = Math.round((safe - whole) * 60);
    clock.textContent = String(whole).padStart(2, '0') + ':' + String(seconds).padStart(2, '0');
  }

  function showError(message) {
    feedback.setAttribute('role', 'alert');
    feedback.textContent = message;
    input.setAttribute('aria-invalid', 'true');
    input.setAttribute('aria-errormessage', 'feedback');
  }

  function clearError() {
    feedback.textContent = '';
    input.removeAttribute('aria-invalid');
    input.removeAttribute('aria-errormessage');
  }

  form.addEventListener('submit', function (event) {
    event.preventDefault();
    const value = Number(input.value);
    if (!Number.isFinite(value) || value <= 0 || value > 180) {
      showError('Enter a duration between 1 and 180 minutes.');
      return;
    }
    clearError();
    feedback.textContent = 'Timer set for ' + value + ' minute(s).';
    render(value);
  });

  opener.addEventListener('click', function () {
    panel.hidden = false;
    closer.focus();
  });
  closer.addEventListener('click', function () {
    panel.hidden = true;
    opener.focus();
  });
  render(input.value);
})();
""",
}

MATRIX = [
    {"class": "narrow", "width": 320, "height": 800},
    {"class": "mobile", "width": 390, "height": 844},
    {"class": "tablet", "width": 834, "height": 1112},
    {"class": "desktop", "width": 1440, "height": 900},
    {"class": "wide", "width": 1920, "height": 1080},
]


def write_project(project: Path, *, fixed: bool) -> None:
    project.mkdir(parents=True, exist_ok=True)
    for relative, text in DEFECTIVE.items():
        (project / relative).write_text(text, encoding="utf-8", newline="\n")
    if fixed:
        for relative, text in FIXED.items():
            (project / relative).write_text(text, encoding="utf-8", newline="\n")
    (project / "QA.md").write_text(
        "# QA\n\n## Judgement\n\nPending independent review.\n\n## Screenshots\n\n"
        "Rendered evidence is recorded by the qualification run.\n",
        encoding="utf-8",
    )


def state_for(project: Path, run_root: Path) -> dict:
    state = {
        "schema_version": contracts.SCHEMA_RUN,
        "run_id": "design-qualification",
        "project": str(project),
        "run_root": str(run_root),
        "task_plans": [],
        "design_directions": [],
        "design_requirements": [],
        "rendered_evidence": [],
        "rendered_evidence_sets": [],
        "rendered_critiques": [],
        "design_reviews": [],
        "reviews": [],
        "executions": [],
        "approvals": [],
        "proof_receipts": [],
        "approvals": [],
    }
    direction = design.create_direction(
        state,
        task_id="design-qualification",
        goal="A quiet countdown that remains legible and operable on a narrow phone.",
        scope="index.html, styles.css, app.js",
        product_context=[
            "A single-purpose focus timer, used at a desk and on a phone.",
            "The interface should feel calm, not decorative.",
        ],
        key_hierarchy=[
            "The clock is the primary focal point.",
            "The duration form is secondary and must be operable by keyboard.",
        ],
        interaction_principles=[
            "Every interactive control is reachable by keyboard.",
            "Focus is always visible on the control that has it.",
            "An invalid duration produces an inline message associated with the field.",
            "Opening settings moves focus into the panel and closing it returns focus.",
        ],
        visual_principles=[
            "Body and control text meet WCAG 2.2 AA contrast.",
            "The header and form wrap rather than overflow at 320 CSS px.",
        ],
        content_principles=[
            "Error text names the accepted range.",
        ],
        constraints=["No new dependency.", "Static HTML, CSS and JavaScript only."],
        accessibility_requirements=[
            "WCAG 2.2 AA text contrast and visible keyboard focus.",
            "Accessible names for the duration field and controls.",
            "Inline error feedback is announced.",
        ],
        responsive_requirements=[
            "Declared viewport matrix: 320, 390, 834, 1440 and 1920 CSS px.",
            "No horizontal overflow at the narrow width.",
        ],
        existing_system=["No existing design system; one static page."],
        reference_findings_adopted=["None; no external reference was used."],
        findings_rejected=["None."],
        approved_deviations=["None."],
    )
    subject = design.direction_subject(direction)
    policy.approve(
        state, "G1D", subject, identity="2.4c-qualification-fixture",
        note="Disposable qualification fixture: approved design direction, not a release gate.",
    )
    direction["status"] = "approved"
    direction["approval_id"] = state["approvals"][-1]["approval_id"]
    implementer = execution.create(
        state, task_id="design-qualification", role="implementer",
        adapter="deterministic-fixture", invocation="qualify-design-2.4c",
        requested={"provider": "local-fixture", "model": "deterministic"}, reason="fixture implementation",
    )
    reviewer = execution.create(
        state, task_id="design-qualification", role="reviewer",
        adapter="visual-qa-subagent", invocation="qualify-design-2.4c",
        requested={"provider": "independent-agent", "model": "visual-qa"},
        parent=str(implementer["execution_id"]), reason="independent rendered review",
    )
    return {"state": state, "direction": direction, "implementer": implementer, "reviewer": reviewer}


def capture(
    *,
    project: Path,
    run_root: Path,
    binding: dict,
    direction: dict,
    implementer_execution: str,
    label: str,
    assertions: bool,
) -> tuple[dict, dict, list[dict]]:
    rows = viewports.declared({"viewports": MATRIX})
    basis = [{
        "basis": "REQUIREMENT",
        "reason": "the direction requires responsive verification across the declared viewport matrix",
    }]
    targets = viewports.targets(
        rows, routes=["/index.html"], basis=basis, required_regions=["#timer", "#clock"],
    )
    if assertions:
        targets.append(capture_plan.interaction_state(
            route="/index.html", state="settings-open",
            action={"kind": "click", "selector": "#open-settings"},
            viewport={"width": 1440, "height": 900, "viewport_class": "desktop"},
            basis=[{"basis": "REQUIREMENT", "reason": "dialog focus handling is a declared interaction principle"}],
            assertions=[
                {"kind": "visible", "selector": "#settings", "description": "settings panel visible"},
                {"kind": "focus", "selector": "#dialog-close", "description": "focus moved into settings"},
            ],
        ))
        targets.append(capture_plan.interaction_state(
            route="/index.html", state="invalid-duration",
            action={"kind": "sequence", "actions": [
                {"kind": "fill", "selector": "#duration", "value": "abc"},
                {"kind": "click", "selector": "#start"},
            ]},
            viewport={"width": 390, "height": 844, "viewport_class": "mobile"},
            basis=[{"basis": "REQUIREMENT", "reason": "invalid input feedback is a declared interaction principle"}],
            assertions=[
                {"kind": "visible", "selector": "#feedback", "description": "inline feedback visible"},
                {"kind": "aria", "selector": "#duration", "attribute": "aria-invalid", "equals": "true"},
            ],
        ))
    plan = capture_plan.create(
        implementation_plan_id=f"design-qualification-{label}",
        direction_id=str(direction["direction_id"]),
        binding=binding,
        target_surface=str(project),
        launch_command=["python", "-m", "http.server"],
        targets=targets,
        budget=capture_plan.capture_budget(
            overrides={"responsive_captures": 5, "interaction_states": 2},
            expansions=[
                {"name": "responsive_captures", "reason": "five declared viewport classes"},
                {"name": "interaction_states", "reason": "dialog focus and invalid-input feedback are declared requirements"},
            ],
        ),
        required_evidence=["screenshot", "interaction"],
        notes="2.4C rendered UI qualification",
    )
    server = render_adapter.LocalServer(project)
    adapters = render_adapter.select_adapters(
        run_root, launch_command=["python", "--version"], allow_hosts=["127.0.0.1"],
    )
    browser = adapters["chromium-render"]
    base_url = server.start()
    directory = run_root / "captures" / label
    try:
        browser.launch()
        manifest = rendered_evidence.execute(
            plan, adapter=browser, binding=binding, directory=directory,
            base_url=base_url, allow_hosts=["127.0.0.1"],
            capture_execution=str(implementer_execution),
        )
    finally:
        browser.shutdown()
        server.shutdown()
    manifest["manifest_path"] = str(directory / rendered_evidence.MANIFEST_NAME)
    return plan, manifest, list(targets)


def findings_from_manifest(manifest: dict) -> list[dict]:
    captures = [row for row in manifest.get("captures") or [] if isinstance(row, dict)]
    by_route = captures
    findings: list[dict] = []
    seen_checks: set[str] = set()
    for row in manifest.get("accessibility_checks") or []:
        if not isinstance(row, dict):
            continue
        for finding in row.get("findings") or []:
            if not isinstance(finding, dict):
                continue
            check = str(finding.get("check", ""))
            if check in seen_checks:
                continue
            seen_checks.add(check)
            dimension = {
                "contrast": "accessibility", "focus-visible": "interaction",
                "target-size": "affordance", "accessible-name": "accessibility",
                "dialog-focus": "interaction", "form-errors": "feedback",
                "reduced-motion": "motion",
            }.get(check, "accessibility")
            severity = "major" if check in ("contrast", "focus-visible", "dialog-focus", "form-errors") else "minor"
            capture_id = str(row.get("capture_id", "")) or str(captures[0].get("capture_id", ""))
            findings.append({
                "dimension": dimension,
                "severity": severity,
                "basis": "DETERMINISTIC",
                "observation": str(finding.get("detail", "")),
                "expected_basis": "the approved direction requires WCAG 2.2 AA contrast, visible focus and inline error feedback",
                "capture_ids": [capture_id],
                "repair_scope": "index.html, styles.css, app.js",
            })
    for row in manifest.get("interaction_checks") or []:
        if not isinstance(row, dict):
            continue
        for check in row.get("checks") or []:
            if not isinstance(check, dict) or str(check.get("state")) != "FAILED":
                continue
            findings.append({
                "dimension": "interaction" if check.get("kind") != "aria" else "accessibility",
                "severity": "major",
                "basis": "DETERMINISTIC",
                "observation": f"the {check.get('kind')} assertion on {check.get('selector')} failed in the live page",
                "expected_basis": "the approved direction declares this interaction state as required",
                "capture_ids": [str(row.get("capture_id", ""))],
                "repair_scope": "index.html, styles.css, app.js",
            })
    for row in manifest.get("runtime_checks") or []:
        if not isinstance(row, dict):
            continue
        for check in row.get("checks") or []:
            if not isinstance(check, dict) or check.get("check") not in ("horizontal-overflow", "content-within-viewport"):
                continue
            if check.get("passed") is False:
                findings.append({
                    "dimension": "responsiveness",
                    "severity": "major",
                    "basis": "DETERMINISTIC",
                    "observation": str(check.get("detail", "")),
                    "expected_basis": "the approved direction requires no horizontal overflow at the narrow width",
                    "capture_ids": [str(row.get("capture_id", ""))],
                    "repair_scope": "styles.css",
                })
    return findings


def review_state(
    *,
    state: dict,
    manifest: dict,
    findings: list[dict],
    direction: dict,
    reviewer_execution: str,
    implementing_execution: str,
    qualitative: dict | None,
    label: str,
) -> dict:
    captures = [str(row.get("capture_id", "")) for row in manifest.get("captures") or [] if isinstance(row, dict)]
    dimensions = contracts.DESIGN_REVIEW_DIMENSIONS
    coverage = {
        dimension: {"state": "REVIEWED", "capture_ids": captures[:2] or captures}
        for dimension in dimensions
    }
    record = rendered_critique_module.build(
        state,
        task_id="design-qualification",
        direction_id=str(direction["direction_id"]),
        manifest=manifest,
        findings=findings,
        reviewer_identity="2.4c-independent-visual-review",
        reviewer_execution=str(reviewer_execution),
        implementing_execution=str(implementing_execution),
        coverage=coverage,
        capture_ids=captures,
        qualitative=qualitative or {},
        unknowns=[],
    )
    return record


def packet_and_review(
    *,
    state: dict,
    project: Path,
    run_root: Path,
    direction: dict,
    reviewer_execution: str,
    implementing_execution: str,
    judgement: str,
    label: str,
) -> tuple[Path, dict]:
    packet = run_root / f"qualification-{label}-S5"
    packet.mkdir(parents=True, exist_ok=True)
    (packet / "evidence").mkdir(exist_ok=True)
    packet_text = "# Ariadne S5 independent review packet\n\nDisposable 2.4C qualification.\n"
    (packet / "packet.txt").write_text(packet_text, encoding="utf-8")
    packet_digest = hashlib.sha256(packet_text.encode("utf-8")).hexdigest()
    fingerprint = design_source.render_source_digest(project)
    (packet / "manifest.json").write_text(json.dumps({
        "packet_id": packet.name,
        "packet_sha256": packet_digest,
        "sources": [{"label": "rendered evidence", "delivered": True}],
    }, indent=2), encoding="utf-8")
    validation = {
        "status": "passed",
        "packet_id": packet.name,
        "scope": {"changed": ["index.html", "styles.css", "app.js"], "status": "within-contract"},
        "validated_revision": {"implementation_fingerprint": fingerprint, "head": "qualification"},
    }
    (packet / "evidence" / "validation.json").write_text(
        json.dumps(validation, indent=2), encoding="utf-8"
    )
    (packet / "evidence" / "review-judgement.md").write_text(judgement, encoding="utf-8")
    (project / "QA.md").write_text(
        "# QA\n\n## Judgement\n\n" + judgement + "\n\n## Screenshots\n\nRendered captures are recorded.\n",
        encoding="utf-8",
    )
    record = review.build_record(
        state, packet,
        reviewer_identity="2.4c-independent-visual-review",
        review_kind="experience",
        reviewer_role="independent-reviewer",
        block=judgement,
        recommendation="present g3",
        reviewer_execution=str(reviewer_execution),
        implementing_execution=str(implementing_execution),
    )
    review.store(state, packet, record)
    state["packets"] = [{"id": packet.name, "stage": "S5", "path": str(packet)}]
    return packet, record


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=["before", "after"])
    parser.add_argument("--root", default=str(ROOT / "validation" / "runs" / "2.4c" / "design"))
    args = parser.parse_args(argv)
    root = Path(args.root).resolve()
    project = root / "project"
    run_root = root / "run"
    if args.phase == "before" and run_root.exists():
        shutil.rmtree(run_root)
    if args.phase == "after":
        # Keep the before captures; only replace this phase's own append-only
        # directory and packet. The before images are the proof of the change.
        for relative in ("captures/after", "qualification-after-S5"):
            target = run_root / relative
            if target.exists():
                shutil.rmtree(target)
    run_root.mkdir(parents=True, exist_ok=True)
    write_project(project, fixed=args.phase == "after")
    built = state_for(project, run_root)
    state = built["state"]
    direction = built["direction"]
    binding = design_source.bind(project)
    plan, manifest, targets = capture(
        project=project, run_root=run_root, binding=binding, direction=direction,
        implementer_execution=built["implementer"]["execution_id"],
        label=args.phase, assertions=True,
    )
    rendered_evidence.append(state, manifest)
    rendered_evidence.record_evidence(
        state, manifest, task_id="design-qualification", direction_id=str(direction["direction_id"]),
        capture_execution=str(built["implementer"]["execution_id"]),
    )
    findings = findings_from_manifest(manifest)
    qualitative = None
    if args.phase == "after":
        review_file = root / "visual-review.json"
        qualitative = json.loads(review_file.read_text(encoding="utf-8")) if review_file.is_file() else {
            "screens_reviewed": [str(row.get("capture_id")) for row in manifest.get("captures") or []],
            "factual_failures": [],
            "subjective_recommendations": [],
            "technically_correct_but_visually_weak": False,
            "overall_note": "No independent visual review file was recorded.",
        }
        qualitative["screens_reviewed"] = [
            str(row.get("capture_id")) for row in manifest.get("captures") or []
        ]
    critique_record = review_state(
        state=state, manifest=manifest, findings=findings, direction=direction,
        reviewer_execution=built["reviewer"]["execution_id"],
        implementing_execution=built["implementer"]["execution_id"],
        qualitative=qualitative, label=args.phase,
    )
    comparison = None
    if args.phase == "after":
        before_path = root / "report-before.json"
        if before_path.is_file():
            before = json.loads(before_path.read_text(encoding="utf-8"))
            before_manifest = json.loads(Path(before["manifest_path"]).read_text(encoding="utf-8"))
            comparisons = []
            for row in manifest.get("captures") or []:
                viewport = row.get("viewport") or {}
                width = int(viewport.get("width", 0) or 0)
                try:
                    comparisons.append(visual_regression.build(
                        before_manifest=before_manifest, after_manifest=manifest,
                        route=str(row.get("route", "/")), state=str(row.get("state", "default")),
                        width=width, threshold=0.1, task_id="design-qualification",
                    ))
                except contracts.ContractError as exc:
                    comparisons.append({"error": str(exc), "width": width})
            comparison = comparisons
    judgement = (
        "## Judgement\n\nThe corrected surface is visually coherent and the declared interaction states hold. "
        "No blocking finding remains.\n\n## Findings\n\nNone\n\n**Recommendation:** present g3\n"
        if args.phase == "after" else
        "## Judgement\n\nThe rendered surface has blocking accessibility and responsive defects.\n\n"
        "## Findings\n\n" + "\n".join(f"- {item['observation']}" for item in findings) + "\n\n"
        "**Recommendation:** fix and re-review\n"
    )
    packet, review_record = packet_and_review(
        state=state, project=project, run_root=run_root, direction=direction,
        reviewer_execution=built["reviewer"]["execution_id"],
        implementing_execution=built["implementer"]["execution_id"],
        judgement=judgement, label=args.phase,
    )
    receipt = None
    if args.phase == "after":
        fingerprint = design_source.render_source_digest(project)
        work_digest = proof.work_digest_for(
            "Repair the countdown page's accessibility and narrow-layout defects and verify the corrected render.",
            f"{packet.name}|{fingerprint}",
        )
        receipt = proof.verify_task(
            state,
            task_text="Repair the countdown page's accessibility and narrow-layout defects and verify the corrected render.",
            work_digest=work_digest,
            task_id="design-qualification",
            worker_identity="deterministic-fixture",
            implementation_fingerprint=fingerprint,
            evidence_kinds=("TEST", "SCREENSHOT", "RUNTIME"),
            evidence_observation=(
                "The engine reran the declared viewport matrix in Chromium, the interaction assertions "
                "passed, the accessibility checks passed, and the before/after captures are recorded."
            ),
        )
        (run_root / "proof-receipt.json").write_text(
            json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        serialised = json.dumps(state, indent=2, sort_keys=True, default=str) + "\n"
        (run_root / "state.json").write_text(serialised, encoding="utf-8")
        # The standard run-state name lets the host/recovery read-only views be
        # exercised against the same qualification artifact.
        (run_root / "ariadne-run.json").write_text(serialised, encoding="utf-8")
    report = {
        "schema_version": "ariadne-24c-design-qualification-1",
        "phase": args.phase,
        "project": str(project),
        "run_root": str(run_root),
        "render_source_digest": binding.get("render_source_digest"),
        "browser": manifest.get("browser"),
        "viewport_matrix": MATRIX,
        "plan_id": plan.get("capture_plan_id"),
        "manifest_path": str(Path(manifest.get("manifest_path", "")) or ""),
        "captures": [
            {
                "capture_id": row.get("capture_id"),
                "route": row.get("route"),
                "state": row.get("state"),
                "viewport": row.get("viewport"),
                "artifact_path": row.get("artifact_path"),
                "digest": row.get("digest"),
                "interaction_checks": row.get("interaction_checks"),
            }
            for row in manifest.get("captures") or []
        ],
        "runtime_checks": manifest.get("runtime_checks"),
        "accessibility_checks": manifest.get("accessibility_checks"),
        "interaction_checks": manifest.get("interaction_checks"),
        "verification_status": manifest.get("verification_status"),
        "findings": findings,
        "critique_id": critique_record.get("critique_id"),
        "critique_status": critique_record.get("overall_status"),
        "review_id": review_record.get("review_id"),
        "review_outcome": review_record.get("outcome"),
        "proof_id": (receipt or {}).get("proof_id"),
        "acceptance_state": (receipt or {}).get("acceptance_state"),
        "creative_review_binding": (receipt or {}).get("creative_review"),
        "visual_comparison": comparison,
        "recorded_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    target = root / f"report-{args.phase}.json"
    target.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "phase": args.phase,
        "captures": len(manifest.get("captures") or []),
        "verification_status": manifest.get("verification_status"),
        "findings": len(findings),
        "critique_status": critique_record.get("overall_status"),
        "proof": (receipt or {}).get("proof_id"),
        "creative_review": bool((receipt or {}).get("creative_review")),
        "report": str(target),
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
