"""AR-202D deterministic benchmark cases: design intelligence.

Every case is offline, deterministic and dependency-free. They test the engine's
*evidence logic* — whether a claim can be made from the evidence that actually
exists — not whether a model subjectively agrees with a visual style, and not
whether a page is aesthetically good. Offline fixtures prove the workflow; they
do not measure human design quality and are never reported as live browser or
live provider evidence.

Two execution styles are used deliberately:

* engine-level cases import the runtime and drive the engine modules directly, so
  a state-machine rule is exercised without a subprocess;
* integration cases run the real CLI (``design-plan``, ``record-design``) against
  a real run, so the command surface and the recorded state are exercised too.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .cases import Ctx, Outcome, case

# --------------------------------------------------------------- helpers

FRONTEND_HANDOFF = (
    "# HANDOFF\n\n## Worker execution contract\n\n| Field | Value |\n| --- | --- |\n| Role | bulk |\n\n"
    "## Permitted scope\n\n| Path | Change |\n| --- | --- |\n"
    "| src/pages/landing.tsx | build the landing page |\n"
    "| src/styles/landing.css | styling |\n"
    "| src/components/Hero.tsx | hero component |\n\n"
    "## Validation commands\n\n| Command | Expected |\n| --- | --- |\n| npm test | pass |\n"
)

BACKEND_HANDOFF = (
    "# HANDOFF\n\n## Worker execution contract\n\n| Field | Value |\n| --- | --- |\n| Role | bulk |\n\n"
    "## Permitted scope\n\n| Path | Change |\n| --- | --- |\n"
    "| src/db/migrations/002_add_tenant.sql | add the tenant column |\n"
    "| src/api/tenants.py | new endpoint |\n\n"
    "## Validation commands\n\n| Command | Expected |\n| --- | --- |\n| pytest | pass |\n"
)


def runtime(ctx: Ctx):
    return ctx.repo.module("ariadne.py")


def plugin_project(ctx: Ctx, case_id: str, handoff: str = FRONTEND_HANDOFF) -> "object":
    box = ctx.sandbox()
    box.write("HANDOFF.md", handoff)
    box.write("PROJECT.md", "# PROJECT\n\nA small product site.\n")
    return box


def plugin_state(box, ctx: Ctx, **extra) -> dict:
    state = {
        "schema_version": 1,
        "run_id": "bench-design",
        "project": str(box.project),
        "run_root": str(box.run_root),
        "packets": [{"id": "bench-S4B", "stage": "S4B", "path": str(box.run_root / "bench-S4B")}],
        "approvals": [],
    }
    state.update(extra)
    return state


def characterise(ctx: Ctx, box, request: str, *, stage: str = "S4B", handoff: bool = True, **extra) -> dict:
    """Characterise one task against the real transport contract."""
    runtime_module = runtime(ctx)
    state = plugin_state(box, ctx, **extra)
    return runtime_module.DESIGN.characterize(
        state, project=box.project, stage=stage, request=request, task_id="bench-S4B",
        transport=runtime_module.TRANSPORT if handoff else None,
    )


def chars(record: dict) -> dict:
    return {name: value["value"] for name, value in record["characteristics"].items()}


def run_cli(ctx: Ctx, box, *args: str, timeout: int = 180):
    return ctx.repo.cli(*args, cwd=box.repo.root if box.repo else ctx.repo.root, timeout=timeout)


def start_run(ctx: Ctx, box, request: str):
    """Start a real run so the CLI surface can be exercised."""
    return ctx.repo.cli(
        "start", "--run-root", str(box.run_root), "--project", str(box.project), "--request", request,
    )


def started_box(ctx: Ctx, case_id: str, request: str, *, handoff: str = FRONTEND_HANDOFF,
                project_md: str = "# PROJECT\n\nA small product site.\n", files: dict | None = None):
    """A started run on a *clean* project, then the project documents.

    ``start`` deliberately refuses a project that already contains files, so the
    run is started first and the fixture documents are written afterwards. That
    ordering is the runtime's own contract, not a benchmark convenience.
    """
    box = ctx.sandbox()
    result = start_run(ctx, box, request)
    if not result.ok:
        raise AssertionError(f"could not start a run: {result.tail(4)}")
    box.write("PROJECT.md", project_md)
    box.write("HANDOFF.md", handoff)
    for relative, text in (files or {}).items():
        box.write(relative, text)
    return box


def record_events(ctx: Ctx, box, events: list[dict], *, extra: dict | None = None, expect: int = 0):
    payload: dict = {"events": events}
    payload.update(extra or {})
    path = box.root / "design-events.json"
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    result = ctx.repo.cli("record-design", "--run-root", str(box.run_root), "--input", str(path))
    return result


def reference_fixture(box, name: str, text: str) -> tuple[Path, str]:
    path = box.write(f"design/references/{name}", text)
    return path, hashlib.sha256(path.read_bytes()).hexdigest()


def rendered_fixture(box, *, routes=("/landing",), width=375) -> dict:
    return {
        "scenes": [
            {
                "route": route,
                "viewport": {"width": width, "height": 812, "device_pixel_ratio": 2},
                "dom": f"<main><h1>{route}</h1><button class=\"primary\">Start</button></main>",
                "accessibility": [
                    {"rule": "color-contrast", "severity": "serious", "target": ".primary", "value": "3.1:1"},
                ],
                "interaction": [{"step": 1, "action": "scroll 400", "observed": "the CTA stays at the bottom edge"}],
                "console": ["no errors"],
            }
            for route in routes
        ]
    }


def design_input(box, *, capture: dict | None = None, declared: dict | None = None) -> Path:
    payload: dict = {}
    if capture is not None:
        payload["capture_fixture"] = capture
    if declared is not None:
        payload["declared"] = declared
    path = box.root / "design-input.json"
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def body_anchor(box, relative: str, anchor: str) -> tuple[Path, str]:
    path = box.write(relative, anchor + "\n")
    return path, anchor


# ======================================================= design characterisation


@case(
    id="design-characterisation.backend-task-selects-no-design-work",
    group="design-characterisation",
    title="A backend task selects no design work at all",
    task="Characterise a database migration and API endpoint against a backend handoff.",
    expectation="design_task is NOT_REQUIRED, the depth is NONE, and every design stage is SKIPPED.",
    evaluation="Run the real characterisation and pipeline selection; check the recorded values.",
    evidence_required="The characterisation record and its selected pipeline.",
    layer="deterministic",
)
def design_characterisation_backend(ctx: Ctx) -> Outcome:
    box = plugin_project(ctx, ctx.case.id, BACKEND_HANDOFF)
    record = characterise(ctx, box, "add a database migration and a new API endpoint for tenants")
    values = chars(record)
    runtime_module = runtime(ctx)
    plan = runtime_module.DESIGN.select_pipeline(record)
    skipped = sorted(name for name, row in plan["stages"].items() if row["selection"] == "SKIPPED")
    problems = []
    if values["design_task"] != "NOT_REQUIRED":
        problems.append(f"design_task={values['design_task']}")
    if plan["depth"] != "NONE":
        problems.append(f"depth={plan['depth']}")
    if len(skipped) != len(plan["stages"]):
        problems.append(f"not every stage skipped: {sorted(set(plan['stages']) - set(skipped))}")
    return Outcome(
        status="pass" if not problems else "fail",
        actual=f"design_task={values['design_task']} depth={plan['depth']} skipped={len(skipped)}",
        evidence={
            "characteristics": values,
            "depth": plan["depth"],
            "skipped": skipped,
            "problems": problems,
        },
        metrics={"stages_skipped": len(skipped)},
    )


@case(
    id="design-characterisation.copy-change-is-not-high-depth",
    group="design-characterisation",
    title="A copy change is not automatically a high-depth design task",
    task="Characterise a headline copy update and inspect the selected depth.",
    expectation="The task is not DEEP, and no reference research is required.",
    evaluation="Read the characterisation and the selected pipeline depth.",
    evidence_required="The characterisation record.",
    layer="deterministic",
)
def design_characterisation_copy(ctx: Ctx) -> Outcome:
    box = plugin_project(ctx, ctx.case.id)
    record = characterise(ctx, box, "update the pricing page copy and headline wording")
    values = chars(record)
    runtime_module = runtime(ctx)
    plan = runtime_module.DESIGN.select_pipeline(record)
    problems = []
    if plan["depth"] == "DEEP":
        problems.append("a copy change selected DEEP")
    if values["reference_research"] != "NOT_REQUIRED":
        problems.append(f"reference_research={values['reference_research']}")
    if values["design_task"] not in ("OPTIONAL", "NOT_REQUIRED"):
        problems.append(f"design_task={values['design_task']}")
    return Outcome(
        status="pass" if not problems else "fail",
        actual=f"depth={plan['depth']} design_task={values['design_task']} references={values['reference_research']}",
        evidence={"characteristics": values, "depth": plan["depth"], "problems": problems},
        metrics={"depth_is_deep": int(plan["depth"] == "DEEP")},
    )


@case(
    id="design-characterisation.new-surface-selects-research",
    group="design-characterisation",
    title="A new landing page selects reference research and rendered observation",
    task="Characterise a new landing page that explicitly asks for reference research.",
    expectation="RETRIEVE, INSPECT, ANALYSE, OBSERVE and CRITIQUE are selected, never SKIPPED.",
    evaluation="Read the selected pipeline for the characterisation.",
    evidence_required="The selected pipeline stages and their reasons.",
    layer="deterministic",
)
def design_characterisation_new_surface(ctx: Ctx) -> Outcome:
    box = plugin_project(ctx, ctx.case.id)
    record = characterise(
        ctx, box,
        "build a new landing page with a hero, and research reference sites for the pricing section",
    )
    runtime_module = runtime(ctx)
    plan = runtime_module.DESIGN.select_pipeline(record)
    stages = {name: row["selection"] for name, row in plan["stages"].items()}
    required = ("RETRIEVE", "INSPECT", "ANALYSE", "OBSERVE", "CRITIQUE")
    problems = [f"{name}={stages.get(name)}" for name in required if stages.get(name) == "SKIPPED"]
    if plan["depth"] not in ("STANDARD", "DEEP"):
        problems.append(f"depth={plan['depth']}")
    return Outcome(
        status="pass" if not problems else "fail",
        actual=f"depth={plan['depth']} " + " ".join(f"{name}={stages.get(name)}" for name in required),
        evidence={"stages": stages, "depth": plan["depth"], "problems": problems},
        metrics={"stages_selected": sum(1 for value in stages.values() if value != "SKIPPED")},
    )


@case(
    id="design-characterisation.small-fix-skips-research",
    group="design-characterisation",
    title="A tiny spacing fix does not trigger broad reference research",
    task="Characterise a one-file spacing tweak and inspect the selected stages.",
    expectation="RETRIEVE, INSPECT and ANALYSE are SKIPPED and the depth is MINIMAL.",
    evaluation="Read the selected pipeline for the characterisation.",
    evidence_required="The selected pipeline stages.",
    layer="deterministic",
)
def design_characterisation_small_fix(ctx: Ctx) -> Outcome:
    box = plugin_project(ctx, ctx.case.id)
    box.write(
        "HANDOFF.md",
        "# HANDOFF\n\n## Worker execution contract\n\n| Field | Value |\n| --- | --- |\n| Role | bulk |\n\n"
        "## Permitted scope\n\n| Path | Change |\n| --- | --- |\n"
        "| src/styles/settings.css | fix the spacing around the settings button |\n\n"
        "## Validation commands\n\n| Command | Expected |\n| --- | --- |\n| npm test | pass |\n",
    )
    record = characterise(ctx, box, "fix the spacing around the settings button")
    runtime_module = runtime(ctx)
    plan = runtime_module.DESIGN.select_pipeline(record)
    stages = {name: row["selection"] for name, row in plan["stages"].items()}
    problems = []
    for name in ("RETRIEVE", "INSPECT", "ANALYSE"):
        if stages.get(name) != "SKIPPED":
            problems.append(f"{name}={stages.get(name)}")
    if plan["depth"] != "MINIMAL":
        problems.append(f"depth={plan['depth']}")
    if stages.get("IMPLEMENT") == "SKIPPED":
        problems.append("IMPLEMENT was skipped for a change that changes code")
    return Outcome(
        status="pass" if not problems else "fail",
        actual=f"depth={plan['depth']} research={stages.get('RETRIEVE')} implement={stages.get('IMPLEMENT')}",
        evidence={"stages": stages, "depth": plan["depth"], "problems": problems},
        metrics={"research_stages_selected": sum(1 for name in ("RETRIEVE", "INSPECT", "ANALYSE") if stages.get(name) != "SKIPPED")},
    )


@case(
    id="design-characterisation.repository-code-is-not-task-evidence",
    group="design-characterisation",
    title="Front-end code in the repository is not evidence about the task",
    task="Put front-end files in the project, then characterise a backend task.",
    expectation="design_task stays NOT_REQUIRED: repository contents never raise design depth.",
    evaluation="Create front-end files, characterise a backend request, read the characteristics.",
    evidence_required="The characterisation and the project files that were ignored.",
    layer="deterministic",
)
def design_characterisation_repository_code(ctx: Ctx) -> Outcome:
    box = plugin_project(ctx, ctx.case.id, BACKEND_HANDOFF)
    for index in range(6):
        box.write(f"src/components/Widget{index}.tsx", "export const Widget = () => null;\n")
        box.write(f"src/styles/theme{index}.css", ":root { --space-4: 16px; }\n")
    box.write("package.json", json.dumps({"dependencies": {"tailwindcss": "^3.4.0", "react": "^18.0.0"}}))
    record = characterise(ctx, box, "add an index to the tenants table and a paginated API endpoint")
    values = chars(record)
    problems = []
    if values["design_task"] != "NOT_REQUIRED":
        problems.append(f"design_task={values['design_task']}")
    if values["reference_research"] != "NOT_REQUIRED":
        problems.append(f"reference_research={values['reference_research']}")
    return Outcome(
        status="pass" if not problems else "fail",
        actual=f"design_task={values['design_task']} with 12 front-end files present",
        evidence={
            "characteristics": values,
            "frontend_files": 12,
            "evidence_for_design_task": record["characteristics"]["design_task"]["evidence"],
            "problems": problems,
        },
    )


@case(
    id="design-characterisation.accessibility-and-responsive-from-request",
    group="design-characterisation",
    title="Accessibility and responsive review are raised by the request, with evidence",
    task="Characterise an accessible, responsive checkout form request.",
    expectation="Both characteristics are REQUIRED and each records the evidence that raised it.",
    evaluation="Read the two characteristics and their evidence lists.",
    evidence_required="The characterisation characteristics and their evidence.",
    layer="deterministic",
)
def design_characterisation_a11y(ctx: Ctx) -> Outcome:
    box = plugin_project(ctx, ctx.case.id)
    record = characterise(
        ctx, box,
        "make the checkout form accessible with keyboard support and a responsive layout at 375 and 1280",
    )
    values = chars(record)
    characteristics = record["characteristics"]
    problems = []
    for name in ("accessibility_review", "responsive_review"):
        if values[name] != "REQUIRED":
            problems.append(f"{name}={values[name]}")
        if not characteristics[name]["evidence"]:
            problems.append(f"{name} records no evidence")
    return Outcome(
        status="pass" if not problems else "fail",
        actual=f"accessibility={values['accessibility_review']} responsive={values['responsive_review']}",
        evidence={
            "accessibility_evidence": characteristics["accessibility_review"]["evidence"],
            "responsive_evidence": characteristics["responsive_review"]["evidence"],
            "problems": problems,
        },
    )


# ========================================================= reference provenance


def _reference_run(ctx: Ctx):
    """A started run plus one local reference, ready for lifecycle events."""
    box = started_box(ctx, ctx.case.id, "build a new landing page and research reference sites")
    reference, _digest = reference_fixture(
        box, "rival-pricing.md",
        "# Rival pricing\n\nThree tiers, annual toggle above the cards.\n",
    )
    return box, reference


@case(
    id="reference-provenance.found-is-not-inspected",
    group="reference-provenance",
    title="A found reference is not an inspected reference",
    task="Record a reference as found, then attempt an analysis without an inspection.",
    expectation="The analysis is refused: a found URL carries no content claim.",
    evaluation="Record found, attempt analysis, read the refusal and the unchanged state.",
    evidence_required="The refusal text and the reference state.",
    layer="deterministic",
)
def reference_found_is_not_inspected(ctx: Ctx) -> Outcome:
    box, reference = _reference_run(ctx)
    found = record_events(ctx, box, [{
        "type": "reference", "source": "rival-pricing", "locator": str(reference),
        "title": "rival pricing page", "source_type": "local-file", "adapter": "local-reference",
    }])
    reference_id = box.state()["design_references"][-1]["reference_id"]
    attempted = record_events(ctx, box, [{
        "type": "reference-analysis", "reference_id": reference_id,
        "findings": [{"dimension": "hierarchy", "observation": "o", "interpretation": "i",
                      "applicability": "a", "decision": "adopted", "mechanism": "m"}],
    }])
    state = box.state()
    records = state.get("design_references") or []
    problems = []
    if not found.ok:
        problems.append("registering a found reference failed")
    if attempted.ok:
        problems.append("an analysis without an inspection was accepted")
    if not records or records[-1]["state"] != "FOUND":
        problems.append(f"reference state={records[-1]['state'] if records else 'none'}")
    if "INSPECTED before it can be ANALYSED" not in attempted.combined:
        problems.append("the refusal did not name the lifecycle requirement")
    return Outcome(
        status="pass" if not problems else "fail",
        actual=f"state={records[-1]['state'] if records else 'none'} analysis_refused={not attempted.ok}",
        evidence={
            "found_exit": found.returncode,
            "analysis_exit": attempted.returncode,
            "analysis_tail": attempted.tail(3),
            "state": records[-1]["state"] if records else "",
            "problems": problems,
        },
    )


@case(
    id="reference-provenance.inaccessible-never-becomes-inspected",
    group="reference-provenance",
    title="An inaccessible source never becomes an inspected source",
    task="Record a reference as inaccessible, then attempt to inspect it.",
    expectation="The inspection is refused and the record stays INACCESSIBLE with its blocker.",
    evaluation="Record the blocker, attempt an inspection, read the refusal and the record.",
    evidence_required="The refusal and the terminal record with its blocker.",
    layer="deterministic",
)
def reference_inaccessible_terminal(ctx: Ctx) -> Outcome:
    box, reference = _reference_run(ctx)
    record_events(ctx, box, [{
        "type": "reference", "source": "gated-library", "locator": "https://example.invalid/gated",
        "title": "gated design library", "source_type": "paid-provider", "adapter": "paid-design-library",
    }])
    state = box.state()
    reference_id = state["design_references"][-1]["reference_id"]
    blocked = record_events(ctx, box, [{
        "type": "reference-inaccessible", "reference_id": reference_id,
        "blocker": "no authorized licensed access is configured in this environment",
    }])
    inspection = record_events(ctx, box, [{
        "type": "reference-inspection", "reference_id": reference_id, "inspection_type": "VISUAL",
        "observations": ["looks great"], "evidence_path": str(box.path("PROJECT.md")),
    }])
    record = box.state()["design_references"][-1]
    problems = []
    if not blocked.ok:
        problems.append("the honest inaccessible outcome was not accepted")
    if inspection.ok:
        problems.append("an inaccessible reference was inspected")
    if record["state"] != "INACCESSIBLE" or not record.get("blocker"):
        problems.append(f"state={record['state']} blocker={bool(record.get('blocker'))}")
    return Outcome(
        status="pass" if not problems else "fail",
        actual=f"state={record['state']} blocker={'yes' if record.get('blocker') else 'no'}",
        evidence={
            "inaccessible_exit": blocked.returncode,
            "inspection_exit": inspection.returncode,
            "inspection_tail": inspection.tail(3),
            "state": record["state"],
            "problems": problems,
        },
        metrics={"inaccessible_recorded": int(record["state"] == "INACCESSIBLE")},
    )


@case(
    id="reference-provenance.inspection-requires-evidence",
    group="reference-provenance",
    title="An inspection requires a real evidence artifact",
    task="Attempt a visual inspection whose evidence file does not exist.",
    expectation="Only the inspection without evidence is refused; the one with evidence is accepted.",
    evaluation="Attempt both inspections and compare their outcomes and the recorded artifact hash.",
    evidence_required="The refusal, the accepted record and its artifact digest.",
    layer="deterministic",
)
def reference_inspection_requires_evidence(ctx: Ctx) -> Outcome:
    box, _reference = _reference_run(ctx)
    record_events(ctx, box, [{
        "type": "reference", "source": "rival-pricing", "locator": str(box.path("design/references/rival-pricing.md")),
        "title": "rival pricing page", "source_type": "local-file", "adapter": "local-reference",
    }])
    reference_id = box.state()["design_references"][-1]["reference_id"]
    record_events(ctx, box, [{
        "type": "reference-accessible", "reference_id": reference_id,
        "content_sha256": box.sha256("design/references/rival-pricing.md"), "mime": "text/markdown",
    }])
    missing = record_events(ctx, box, [{
        "type": "reference-inspection", "reference_id": reference_id, "inspection_type": "CONTENT",
        "observations": ["three tiers"], "evidence_path": str(box.path("design/references/does-not-exist.md")),
    }])
    accepted = record_events(ctx, box, [{
        "type": "reference-inspection", "reference_id": reference_id, "inspection_type": "CONTENT",
        "observations": ["three tiers with an annual toggle above the tier row"],
        "evidence_path": str(box.path("design/references/rival-pricing.md")),
    }])
    record = box.state()["design_references"][-1]
    artifact = (record.get("inspections") or [{}])[-1].get("evidence") or {}
    problems = []
    if missing.ok:
        problems.append("an inspection without evidence was accepted")
    if not accepted.ok:
        problems.append("an inspection with evidence was refused")
    if artifact.get("sha256") != box.sha256("design/references/rival-pricing.md"):
        problems.append("the recorded artifact digest does not match the file")
    return Outcome(
        status="pass" if not problems else "fail",
        actual=f"state={record['state']} artifact_hashed={bool(artifact.get('sha256'))}",
        evidence={
            "missing_exit": missing.returncode, "missing_tail": missing.tail(2),
            "accepted_exit": accepted.returncode,
            "artifact": artifact, "problems": problems,
        },
    )


@case(
    id="reference-provenance.analysis-requires-inspection",
    group="reference-provenance",
    title="An analysis must derive from an inspection that happened",
    task="Analyse an inspected reference, citing an inspection id this reference does not have.",
    expectation="The fabricated citation is refused; the real inspection id is accepted.",
    evaluation="Attempt both analyses and read the refusals and the recorded derived_from list.",
    evidence_required="The refusal text and the recorded analysis.",
    layer="deterministic",
)
def reference_analysis_requires_inspection(ctx: Ctx) -> Outcome:
    box, _reference = _reference_run(ctx)
    record_events(ctx, box, [{
        "type": "reference", "source": "rival-pricing", "locator": str(box.path("design/references/rival-pricing.md")),
        "title": "rival pricing page", "source_type": "local-file", "adapter": "local-reference",
    }])
    reference_id = box.state()["design_references"][-1]["reference_id"]
    record_events(ctx, box, [
        {"type": "reference-accessible", "reference_id": reference_id,
         "content_sha256": box.sha256("design/references/rival-pricing.md"), "mime": "text/markdown"},
        {"type": "reference-inspection", "reference_id": reference_id, "inspection_type": "CONTENT",
         "observations": ["the annual toggle sits above the tier row"],
         "evidence_path": str(box.path("design/references/rival-pricing.md"))},
    ])
    inspection_id = box.state()["design_references"][-1]["inspections"][-1]["inspection_id"]
    fabricated = record_events(ctx, box, [{
        "type": "reference-analysis", "reference_id": reference_id,
        "findings": [{
            "dimension": "hierarchy", "observation": "the toggle is above the tiers",
            "interpretation": "the price is read after the commitment", "applicability": "the same order fits here",
            "decision": "adopted", "mechanism": "single decision point before price comparison",
            "inspection_ids": ["ins_20260101T000000Z_deadbeef"],
        }],
    }])
    accepted = record_events(ctx, box, [{
        "type": "reference-analysis", "reference_id": reference_id,
        "findings": [{
            "dimension": "hierarchy", "observation": "the toggle is above the tiers",
            "interpretation": "the price is read after the commitment", "applicability": "the same order fits here",
            "decision": "adopted", "mechanism": "single decision point before price comparison",
            "inspection_ids": [inspection_id],
        }],
    }])
    record = box.state()["design_references"][-1]
    problems = []
    if fabricated.ok:
        problems.append("an analysis citing a non-existent inspection was accepted")
    if not accepted.ok:
        problems.append("a valid analysis was refused")
    if record["state"] != "ANALYSED":
        problems.append(f"state={record['state']}")
    if (record.get("analysis") or {}).get("derived_from") != [inspection_id]:
        problems.append("derived_from does not name the inspection it came from")
    return Outcome(
        status="pass" if not problems else "fail",
        actual=f"state={record['state']} fabricated_refused={not fabricated.ok}",
        evidence={
            "fabricated_exit": fabricated.returncode, "fabricated_tail": fabricated.tail(2),
            "accepted_exit": accepted.returncode,
            "derived_from": (record.get("analysis") or {}).get("derived_from"),
            "problems": problems,
        },
    )


@case(
    id="reference-provenance.used-requires-analysis",
    group="reference-provenance",
    title="A reference cannot be used before it is analysed",
    task="Attempt to mark an inspected-but-unanalysed reference as used, then complete the chain.",
    expectation="USED requires ANALYSIS; the full chain succeeds and records the artifact anchor.",
    evaluation="Attempt used early, then run accessible/inspect/analyse/use and read the record.",
    evidence_required="The early refusal and the completed usage record.",
    layer="deterministic",
)
def reference_used_requires_analysis(ctx: Ctx) -> Outcome:
    box, _reference = _reference_run(ctx)
    design_doc = box.write("DESIGN.md", "# DESIGN\n\n## Hierarchy\n\nThe tier toggle is a single decision point.\n")
    record_events(ctx, box, [{
        "type": "reference", "source": "rival-pricing", "locator": str(box.path("design/references/rival-pricing.md")),
        "title": "rival pricing page", "source_type": "local-file", "adapter": "local-reference",
    }])
    reference_id = box.state()["design_references"][-1]["reference_id"]
    record_events(ctx, box, [
        {"type": "reference-accessible", "reference_id": reference_id,
         "content_sha256": box.sha256("design/references/rival-pricing.md"), "mime": "text/markdown"},
        {"type": "reference-inspection", "reference_id": reference_id, "inspection_type": "CONTENT",
         "observations": ["the annual toggle sits above the tier row"],
         "evidence_path": str(box.path("design/references/rival-pricing.md"))},
    ])
    early = record_events(ctx, box, [{
        "type": "reference-used", "reference_id": reference_id, "decision": "put the toggle above the tiers",
        "principle": "one commitment decision before comparison", "artifact_path": str(design_doc),
        "artifact_anchor": "single decision point",
    }])
    inspection_id = box.state()["design_references"][-1]["inspections"][-1]["inspection_id"]
    record_events(ctx, box, [
        {"type": "reference-analysis", "reference_id": reference_id,
         "findings": [{"dimension": "hierarchy", "observation": "the toggle is above the tiers",
                       "interpretation": "commitment precedes comparison", "applicability": "fits this page",
                       "decision": "adopted", "mechanism": "single decision point before price comparison",
                       "inspection_ids": [inspection_id]}]},
    ])
    completed = record_events(ctx, box, [{
        "type": "reference-used", "reference_id": reference_id, "decision": "put the toggle above the tiers",
        "principle": "one commitment decision before comparison", "artifact_path": str(design_doc),
        "artifact_anchor": "single decision point",
    }])
    record = box.state()["design_references"][-1]
    runtime_module = runtime(ctx)
    structural = runtime_module.DESIGN.structural_problems(box.state())
    problems = []
    if early.ok:
        problems.append("a reference was used before it was analysed")
    if not completed.ok:
        problems.append("a valid usage was refused")
    if record["state"] != "USED":
        problems.append(f"state={record['state']}")
    if not (record.get("usage") or {}).get("artifact_anchor"):
        problems.append("the usage record does not carry its anchor")
    if structural:
        problems.append(f"a valid run reports structural design problems: {structural}")
    return Outcome(
        status="pass" if not problems else "fail",
        actual=f"state={record['state']} early_refused={not early.ok} structural_problems={len(structural)}",
        evidence={
            "early_exit": early.returncode, "early_tail": early.tail(2),
            "completed_exit": completed.returncode,
            "usage": record.get("usage"), "structural": structural, "problems": problems,
        },
    )


@case(
    id="reference-provenance.stale-artifact-invalidates-inspection",
    group="reference-provenance",
    title="A changed artifact invalidates the inspection recorded from it",
    task="Inspect a reference against its artifact, then modify the artifact.",
    expectation="The provenance check reports the artifact changed after evidence was recorded.",
    evaluation="Run the engine provenance check before and after modifying the artifact.",
    evidence_required="The provenance problem list before and after the edit.",
    layer="deterministic",
)
def reference_stale_artifact(ctx: Ctx) -> Outcome:
    box, _reference = _reference_run(ctx)
    runtime_module = runtime(ctx)
    state = plugin_state(box, ctx)
    box.write("HANDOFF.md", FRONTEND_HANDOFF)
    text = box.path("design/references/rival-pricing.md")
    text.parent.mkdir(parents=True, exist_ok=True)
    text.write_text("# Rival pricing\n\nThree tiers.\n", encoding="utf-8")
    record_value = runtime_module.REFERENCES.register(
        state, source="stale-reference", locator=str(text), title="rival pricing",
        source_type="local-file", adapter="local-reference", task_id="bench-S4B",
    )
    runtime_module.REFERENCES.mark_accessible(
        state, record_value["reference_id"], content_sha256=hashlib.sha256(text.read_bytes()).hexdigest(),
        mime="text/markdown",
    )
    runtime_module.REFERENCES.inspect(
        state, record_value["reference_id"], inspection_type="CONTENT",
        observations=["three tiers"], evidence_path=text, project=box.project,
    )
    before = runtime_module.REFERENCES.provenance_problems(state)
    # the engine keeps the artifact hash inside the record; simulate drift by editing the file
    text.write_text("# Rival pricing\n\nFour tiers now.\n", encoding="utf-8")
    record = runtime_module.REFERENCES.reference(state, record_value["reference_id"])
    artifact = record["inspections"][-1]["evidence"]
    actual = hashlib.sha256(text.read_bytes()).hexdigest()
    problems = []
    if before:
        problems.append(f"the clean record already reported problems: {before}")
    if actual == artifact["sha256"]:
        problems.append("the artifact was not actually changed")
    return Outcome(
        status="pass" if not problems else "fail",
        actual=f"clean_problems={len(before)} artifact_changed={actual != artifact['sha256']}",
        evidence={
            "recorded_sha256": artifact["sha256"],
            "actual_sha256": actual,
            "problems": problems,
        },
    )


@case(
    id="reference-provenance.content-inspection-cannot-satisfy-visual",
    group="reference-provenance",
    title="A content inspection cannot support a visual claim",
    task="Record a content inspection, then attempt a visual claim from it.",
    expectation="The claim is refused: an appearance claim needs visual inspection evidence.",
    evaluation="Record the content inspection, attempt the appearance claim, read the refusal.",
    evidence_required="The refusal and the recorded claim kinds.",
    layer="deterministic",
)
def reference_content_vs_visual(ctx: Ctx) -> Outcome:
    box = plugin_project(ctx, ctx.case.id)
    runtime_module = runtime(ctx)
    state = plugin_state(box, ctx)
    source = box.write("design/references/markup.html", "<main><h1>Pricing</h1></main>\n")
    record_value = runtime_module.REFERENCES.register(
        state, source="markup", locator=str(source), title="pricing markup",
        source_type="local-file", adapter="local-reference", task_id="bench-S4B",
    )
    runtime_module.REFERENCES.mark_accessible(
        state, record_value["reference_id"], content_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
    )
    runtime_module.REFERENCES.inspect(
        state, record_value["reference_id"], inspection_type="CONTENT",
        observations=["one h1, no navigation"], evidence_path=source, project=box.project,
    )
    refused = ""
    try:
        runtime_module.REFERENCES.inspect(
            state, record_value["reference_id"], inspection_type="CONTENT",
            observations=["it looks warm and inviting"], claim_kinds=["appearance"],
            evidence_path=source, project=box.project,
        )
    except Exception as exc:  # ContractError
        refused = str(exc)
    record = runtime_module.REFERENCES.reference(state, record_value["reference_id"])
    kinds = record["inspections"][-1]["claim_kinds"]
    problems = []
    if "appearance" in kinds:
        problems.append("the recorded claim kinds include an appearance claim")
    if "cannot support" not in refused:
        problems.append(f"refusal did not name the claim/evidence mismatch: {refused!r}")
    if "appearance" not in refused:
        problems.append("refusal did not name the appearance claim")
    return Outcome(
        status="pass" if not problems else "fail",
        actual=f"recorded_claim_kinds={kinds}",
        evidence={"refusal": refused, "claim_kinds": kinds, "problems": problems},
    )


@case(
    id="reference-provenance.visual-inspection-cannot-satisfy-interaction",
    group="reference-provenance",
    title="A visual inspection cannot support an interaction claim",
    task="Record a visual inspection of a screenshot, then claim observed behaviour.",
    expectation="The behaviour claim is refused, and a later interaction inspection can support it.",
    evaluation="Attempt the behaviour claim from the screenshot, then from an interaction transcript.",
    evidence_required="Both refusals/acceptances and the recorded claim kinds.",
    layer="deterministic",
)
def reference_visual_vs_interaction(ctx: Ctx) -> Outcome:
    box = plugin_project(ctx, ctx.case.id)
    runtime_module = runtime(ctx)
    state = plugin_state(box, ctx)
    shot = box.write("design/references/hero.png", "\x89PNG-not-really\n")
    transcript = box.write(
        "design/references/hero-interaction.md",
        "step 1: scroll 400\nobserved: the header collapses to a compact bar and stays at the top\n",
    )
    record_value = runtime_module.REFERENCES.register(
        state, source="hero", locator=str(shot), title="hero screenshot",
        source_type="project-screenshot", adapter="local-reference", task_id="bench-S4B",
    )
    runtime_module.REFERENCES.mark_accessible(
        state, record_value["reference_id"], content_sha256=hashlib.sha256(shot.read_bytes()).hexdigest(),
        mime="image/png",
    )
    runtime_module.REFERENCES.inspect(
        state, record_value["reference_id"], inspection_type="VISUAL",
        observations=["the hero image occupies the upper third"],
        evidence_path=shot, project=box.project,
    )
    refused = ""
    try:
        runtime_module.REFERENCES.inspect(
            state, record_value["reference_id"], inspection_type="VISUAL",
            observations=["the header collapses on scroll"], claim_kinds=["behaviour"],
            evidence_path=shot, project=box.project,
        )
    except Exception as exc:
        refused = str(exc)
    runtime_module.REFERENCES.inspect(
        state, record_value["reference_id"], inspection_type="INTERACTION",
        observations=["the header collapses and stays pinned after 400px of scroll"],
        evidence_path=transcript, claim_kinds=["behaviour"],
        project=box.project,
    )
    record = runtime_module.REFERENCES.reference(state, record_value["reference_id"])
    kinds = sorted({kind for item in record["inspections"] for kind in item["claim_kinds"]})
    problems = []
    if "behaviour" not in refused:
        problems.append(f"the behaviour claim was not refused from the screenshot: {refused!r}")
    if "behaviour" not in kinds:
        problems.append("the interaction inspection did not record the behaviour claim")
    if len(record["inspections"]) != 2:
        problems.append(f"expected 2 inspections, found {len(record['inspections'])}")
    return Outcome(
        status="pass" if not problems else "fail",
        actual=f"inspections={len(record['inspections'])} claim_kinds={kinds}",
        evidence={"refusal": refused, "claim_kinds": kinds, "problems": problems},
        metrics={"inspections": len(record["inspections"])},
    )


# ============================================================ reference adapters


@case(
    id="reference-adapters.local-reference-works",
    group="reference-adapters",
    title="The local reference adapter discovers and hashes project material",
    task="Discover local reference files and retrieve their metadata through the adapter.",
    expectation="Discovery finds the file, metadata carries a real content digest, and visual inspection is supported.",
    evaluation="Call the adapter's declared capabilities and compare with the file on disk.",
    evidence_required="The adapter capability record, candidates and retrieved digest.",
    layer="deterministic",
)
def reference_adapters_local(ctx: Ctx) -> Outcome:
    box = plugin_project(ctx, ctx.case.id)
    runtime_module = runtime(ctx)
    path = box.write("design/references/hero.png", "\x89PNG-fixture\n")
    adapter = runtime_module.REFERENCES.LocalReferenceAdapter(box.project)
    capabilities = list(adapter.capabilities())
    candidates = adapter.discover({"query": ""})
    metadata = adapter.retrieve_metadata(candidates[0]) if candidates else {}
    expected = hashlib.sha256(path.read_bytes()).hexdigest()
    problems = []
    if not candidates:
        problems.append("discovery found no candidate")
    if metadata.get("content_sha256") != expected:
        problems.append("retrieved metadata digest does not match the file")
    for capability in ("discover", "retrieve_metadata", "retrieve_content", "inspect_visual"):
        if capability not in capabilities:
            problems.append(f"missing declared capability: {capability}")
    return Outcome(
        status="pass" if not problems else "fail",
        actual=f"candidates={len(candidates)} digest_matches={metadata.get('content_sha256') == expected}",
        evidence={
            "capabilities": capabilities,
            "metadata": metadata,
            "problems": problems,
        },
        metrics={"candidates": len(candidates)},
    )


@case(
    id="reference-adapters.inaccessible-result-recorded-honestly",
    group="reference-adapters",
    title="An unconfigured adapter reports its own unavailability",
    task="Ask the approved-URL and paid-provider adapters what they can do and attempt retrieval.",
    expectation="Both report themselves disabled with a reason and return an inaccessible result, never a fabricated one.",
    evaluation="Read the capability records and the retrieval results; assert no network capability is claimed.",
    evidence_required="The capability records and the inaccessible results with their blockers.",
    layer="deterministic",
)
def reference_adapters_inaccessible(ctx: Ctx) -> Outcome:
    box = plugin_project(ctx, ctx.case.id)
    runtime_module = runtime(ctx)
    adapters = runtime_module.REFERENCES.default_adapters(box.project)
    url_adapter = adapters["approved-url"]
    paid_adapter = adapters["paid-design-library"]
    url_result = url_adapter.retrieve_content(
        runtime_module.REFERENCES.ReferenceCandidate(
            source="https://example.invalid/a", locator="https://example.invalid/a",
            title="a", source_type="approved-url", adapter=url_adapter.id,
        )
    )
    paid_result = paid_adapter.retrieve_content(
        runtime_module.REFERENCES.ReferenceCandidate(
            source="mobbin", locator="mobbin://screen/1", title="screen",
            source_type="paid-provider", adapter=paid_adapter.id,
        )
    )
    problems = []
    for adapter, result in ((url_adapter, url_result), (paid_adapter, paid_result)):
        if adapter.enabled():
            problems.append(f"{adapter.id} reports itself enabled without configured access")
        if not result.get("inaccessible"):
            problems.append(f"{adapter.id} returned something other than an inaccessible result")
        if not result.get("blocker"):
            problems.append(f"{adapter.id} returned an inaccessible result without a blocker")
    if "http" in str(paid_result.get("content_sha256", "")).lower():
        problems.append("the paid adapter produced a fabricated digest")
    return Outcome(
        status="pass" if not problems else "fail",
        actual="both optional adapters report unavailable with a blocker",
        evidence={
            "approved_url": url_adapter.capability_record(), "approved_url_result": url_result,
            "paid": paid_adapter.capability_record(), "paid_result": paid_result,
            "problems": problems,
        },
    )


@case(
    id="reference-adapters.unsupported-capability-stays-unsupported",
    group="reference-adapters",
    title="An adapter never supplies evidence it did not declare",
    task="Ask the local reference adapter for interaction inspection.",
    expectation="The call is refused: a file cannot show interaction, and the adapter never declared it.",
    evaluation="Call inspect_interaction on the local adapter and read the refusal.",
    evidence_required="The refusal text and the declared capability list.",
    layer="deterministic",
)
def reference_adapters_unsupported(ctx: Ctx) -> Outcome:
    box = plugin_project(ctx, ctx.case.id)
    runtime_module = runtime(ctx)
    box.write("design/references/hero.png", "\x89PNG-fixture\n")
    adapter = runtime_module.REFERENCES.LocalReferenceAdapter(box.project)
    candidate = adapter.discover({"query": ""})[0]
    refused = ""
    try:
        adapter.inspect_interaction(candidate)
    except Exception as exc:
        refused = str(exc)
    problems = []
    if "does not support capability" not in refused:
        problems.append(f"the refusal did not name the unsupported capability: {refused!r}")
    if "inspect_interaction" in adapter.capabilities():
        problems.append("the local adapter claims interaction inspection")
    return Outcome(
        status="pass" if not problems else "fail",
        actual=f"capabilities={list(adapter.capabilities())}",
        evidence={"refusal": refused, "capabilities": list(adapter.capabilities()), "problems": problems},
    )


@case(
    id="reference-adapters.gated-source-is-not-bypassed",
    group="reference-adapters",
    title="A gated source is not bypassed and a claim in a title is not provenance",
    task="Attempt a paid-provider reference and register a title that asserts a claim.",
    expectation="The provider stays unavailable; a title asserting a best practice is refused at registration.",
    evaluation="Attempt the gated retrieval and register the assertive title; read both refusals.",
    evidence_required="Both refusals and the adapter's declared capabilities.",
    layer="deterministic",
)
def reference_adapters_gated(ctx: Ctx) -> Outcome:
    box = plugin_project(ctx, ctx.case.id)
    runtime_module = runtime(ctx)
    state = plugin_state(box, ctx)
    adapter = runtime_module.REFERENCES.OptionalProviderAdapter()
    result = adapter.retrieve_content(
        runtime_module.REFERENCES.ReferenceCandidate(
            source="mobbin", locator="mobbin://screen/1", title="screen",
            source_type="paid-provider", adapter=adapter.id,
        )
    )
    refused = ""
    try:
        runtime_module.REFERENCES.register(
            state, source="x", locator="https://example.invalid/x",
            title="Best practice: every site does this", source_type="approved-url", adapter="approved-url",
        )
    except Exception as exc:
        refused = str(exc)
    problems = []
    if not result.get("inaccessible"):
        problems.append("the gated provider returned something instead of an inaccessible result")
    if not result.get("blocker"):
        problems.append("the gated provider recorded no blocker")
    if "assert" not in refused and "title" not in refused:
        problems.append(f"an assertive title was not refused at registration: {refused!r}")
    if state.get("design_references"):
        problems.append("a reference record was written for the refused title")
    return Outcome(
        status="pass" if not problems else "fail",
        actual=f"provider_inaccessible={bool(result.get('inaccessible'))} title_refused={bool(refused)}",
        evidence={"provider_result": result, "title_refusal": refused, "problems": problems},
    )


# ========================================================= component intelligence


def _component(ctx: Ctx, box, **overrides):
    runtime_module = runtime(ctx)
    state = overrides.pop("state", None) or plugin_state(box, ctx)
    options = {
        "need": "a date range picker",
        "task_id": "bench-S4B",
        "rung": "existing-project-component",
        "name": "src/components/DateRange.tsx",
        "alternatives": [{"name": "react-day-picker", "reason": "adds a dependency for a control we already have"}],
        "existing_equivalent": {"checked": True, "reason": "src/components/DateRange.tsx exists and is used twice"},
        "findings": {
            "project_compatibility": {"verdict": "verified", "detail": "already used in this project"},
            "licence": {"verdict": "verified", "detail": "internal code, no licence obligation"},
        },
        "registry": runtime_module.COMPONENTS.default_registry(ctx.repo.root),
    }
    options.update(overrides)
    return runtime_module.COMPONENTS.evaluate(state, **options), state


def _record_dependency_approval(ctx: Ctx, box, state) -> dict:
    """Record a real G2 handoff approval so a dependency rung has something to cite."""
    runtime_module = runtime(ctx)
    subject = runtime_module.POLICY.handoff_subject(box.project)
    return runtime_module.POLICY.approve(state, "G2", subject, "operator")


@case(
    id="component-intelligence.existing-component-preferred",
    group="component-intelligence",
    title="An existing project component is preferred over a new dependency",
    task="Evaluate a need that an existing project component already solves.",
    expectation="The candidate selects the first rung, requires no approval, and installs nothing.",
    evaluation="Evaluate the candidate and read the recorded rung, decision and install authority.",
    evidence_required="The evaluation record with its rung, decision and existing-equivalent check.",
    layer="deterministic",
)
def component_existing_preferred(ctx: Ctx) -> Outcome:
    box = plugin_project(ctx, ctx.case.id)
    record, _state = _component(ctx, box)
    problems = []
    if record["decision"] != "selected":
        problems.append(f"decision={record['decision']}")
    if record["rung"] != "existing-project-component":
        problems.append(f"rung={record['rung']}")
    if record["approval_required"]:
        problems.append("a project component asked for an installation approval")
    if record["install_authority"] != "none — human G2 required":
        problems.append("install authority was not recorded as human-only")
    return Outcome(
        status="pass" if not problems else "fail",
        actual=f"rung={record['rung']} decision={record['decision']} approval={record['approval_required']}",
        evidence={"candidate": record, "problems": problems},
    )


@case(
    id="component-intelligence.native-solution-preferred",
    group="component-intelligence",
    title="A native platform capability is preferred over a dependency",
    task="Evaluate a native solution for the need against an external package.",
    expectation="The native rung selects without an approval and no dependency is proposed.",
    evaluation="Evaluate the native candidate and read the decision and registry record.",
    evidence_required="The evaluation record.",
    layer="deterministic",
)
def component_native_preferred(ctx: Ctx) -> Outcome:
    box = plugin_project(ctx, ctx.case.id)
    record, _state = _component(
        ctx, box, rung="native-platform", name="input type=date",
        alternatives=[{"name": "flatpickr", "reason": "a third-party control is unnecessary for a date input"}],
        existing_equivalent={"checked": True, "reason": "no project component covers a plain date field"},
        findings={
            "project_compatibility": {"verdict": "verified", "detail": "available in every target browser"},
            "licence": {"verdict": "verified", "detail": "platform feature, no licence"},
        },
    )
    problems = []
    if record["decision"] != "selected":
        problems.append(f"decision={record['decision']}")
    if record["registry"]:
        problems.append("a native capability consulted a component registry")
    if record["approval_required"]:
        problems.append("a native capability asked for an installation approval")
    return Outcome(
        status="pass" if not problems else "fail",
        actual=f"rung={record['rung']} decision={record['decision']} registry={bool(record['registry'])}",
        evidence={"candidate": record, "problems": problems},
    )


@case(
    id="component-intelligence.incompatible-component-rejected",
    group="component-intelligence",
    title="A component whose compatibility or licence is unknown is blocked",
    task="Evaluate an external dependency whose licence nobody established.",
    expectation="The candidate is blocked, never selected, and the unknown findings are named.",
    evaluation="Evaluate the candidate with unknown licence and compatibility and read the decision.",
    evidence_required="The evaluation record with its blocking findings.",
    layer="deterministic",
)
def component_incompatible(ctx: Ctx) -> Outcome:
    box = plugin_project(ctx, ctx.case.id)
    record, _state = _component(
        ctx, box, rung="new-external-dependency", name="fancy-chart",
        alternatives=[{"name": "hand-rolled svg", "reason": "too much work for this milestone"}],
        existing_equivalent={"checked": False, "reason": "no charting code exists in the project"},
        findings={},
        registry_entry="lieflat-charts",
    )
    problems = []
    if record["decision"] != "blocked":
        problems.append(f"decision={record['decision']}")
    named = " ".join(record["problems"]).lower()
    for needle in ("licence", "compatibility"):
        if needle not in named:
            problems.append(f"the blocking finding {needle} was not named")
    return Outcome(
        status="pass" if not problems else "fail",
        actual=f"decision={record['decision']} problems={len(record['problems'])}",
        evidence={"problems_recorded": record["problems"], "candidate": record, "verdicts": record["findings"]},
        metrics={"blocking_problems": len(record["problems"])},
    )


@case(
    id="component-intelligence.dependency-cannot-self-install",
    group="component-intelligence",
    title="A dependency recommendation is not installation authority",
    task="Evaluate a fully-known external dependency with no approval, with a fabricated approval id, and with a recorded one.",
    expectation="No approval and a fabricated id both leave it blocked; only an approval the engine actually recorded selects it, and even then the install authority is human-only.",
    evaluation="Evaluate three times and compare the decisions, approval sources and install authority strings.",
    evidence_required="The three evaluation records and their approval sources.",
    layer="deterministic",
)
def component_no_self_install(ctx: Ctx) -> Outcome:
    box = plugin_project(ctx, ctx.case.id)
    runtime_module = runtime(ctx)
    findings = {
        "project_compatibility": {"verdict": "verified", "detail": "peer range matches the project"},
        "framework_compatibility": {"verdict": "verified", "detail": "same framework major"},
        "licence": {"verdict": "verified", "detail": "MIT"},
        "accessibility": {"verdict": "claimed", "detail": "documented keyboard support"},
    }
    without, _state = _component(
        ctx, box, rung="new-external-dependency", name="date-range-kit",
        alternatives=[{"name": "keep the existing control", "reason": "misses the range requirement"}],
        existing_equivalent={"checked": True, "reason": "the existing control has no range mode"},
        findings=findings, registry_entry="shadcn-ui",
    )
    fabricated, _state = _component(
        ctx, box, rung="new-external-dependency", name="date-range-kit",
        alternatives=[{"name": "keep the existing control", "reason": "misses the range requirement"}],
        existing_equivalent={"checked": True, "reason": "the existing control has no range mode"},
        findings=findings, registry_entry="shadcn-ui", approval_id="apv_20260101T000000Z_00000000",
    )
    # only an approval the engine recorded may authorize the higher rung
    approved_state = plugin_state(box, ctx)
    approval = _record_dependency_approval(ctx, box, approved_state)
    recorded, recorded_state = _component(
        ctx, box, rung="new-external-dependency", name="date-range-kit",
        alternatives=[{"name": "keep the existing control", "reason": "misses the range requirement"}],
        existing_equivalent={"checked": True, "reason": "the existing control has no range mode"},
        findings=findings, registry_entry="shadcn-ui",
        approval_id=str(approval["approval_id"]), state=approved_state,
    )
    problems = []
    if without["decision"] != "blocked":
        problems.append(f"without approval decision={without['decision']}")
    if not without["approval_required"]:
        problems.append("the candidate did not record that approval is required")
    if fabricated["decision"] != "blocked":
        problems.append(f"a fabricated approval id selected the candidate ({fabricated['approval_source']})")
    if fabricated["approval_source"] != "unverified":
        problems.append(f"fabricated approval source={fabricated['approval_source']}")
    if recorded["decision"] != "selected":
        problems.append(f"a recorded approval did not select the candidate: {recorded['problems']}")
    if recorded["approval_source"] != "recorded":
        problems.append(f"recorded approval source={recorded['approval_source']}")
    for record in (without, fabricated, recorded):
        if record["install_authority"] != "none — human G2 required":
            problems.append("install authority was not recorded as human-only")
    return Outcome(
        status="pass" if not problems else "fail",
        actual=f"without={without['decision']} fabricated={fabricated['decision']} recorded={recorded['decision']}",
        evidence={"without": without, "fabricated": fabricated, "recorded": recorded, "problems": problems},
    )


@case(
    id="component-intelligence.registry-metadata-retained",
    group="component-intelligence",
    title="Registry metadata is retained with its provenance and freshness",
    task="Evaluate a registry candidate and inspect the recorded registry record.",
    expectation="The registry id, the queried entry, its checked_on date and freshness window are recorded.",
    evaluation="Evaluate against the repository registry and read the registry block.",
    evidence_required="The registry block of the evaluation record.",
    layer="deterministic",
)
def component_registry_provenance(ctx: Ctx) -> Outcome:
    box = plugin_project(ctx, ctx.case.id)
    approved_state = plugin_state(box, ctx)
    approval = _record_dependency_approval(ctx, box, approved_state)
    record, _state = _component(
        ctx, box, rung="approved-registry", name="shadcn-ui", registry_entry="shadcn-ui",
        approval_id=str(approval["approval_id"]), state=approved_state,
        alternatives=[{"name": "hand-rolled dialog", "reason": "keyboard and focus handling would be re-invented"}],
        existing_equivalent={"checked": False, "reason": "no dialog primitive exists in this project"},
        findings={
            "project_compatibility": {"verdict": "verified", "detail": "declared for this stack"},
            "framework_compatibility": {"verdict": "verified", "detail": "same framework"},
            "licence": {"verdict": "verified", "detail": "MIT"},
        },
    )
    registry = record["registry"]
    problems = []
    if record["decision"] != "selected":
        problems.append(f"decision={record['decision']}: {record['problems']}")
    if not registry:
        problems.append("no registry record was retained")
    if registry.get("registry") != "local-capability-registry":
        problems.append(f"registry id={registry.get('registry')}")
    if not registry.get("checked_on"):
        problems.append("the registry record has no checked_on date")
    if not registry.get("entry"):
        problems.append("the registry record does not carry the queried entry")
    return Outcome(
        status="pass" if not problems else "fail",
        actual=f"registry={registry.get('registry')} entry={bool(registry.get('entry'))} "
               f"checked_on={registry.get('checked_on')} approval={record.get('approval_source')}",
        evidence={"registry": registry, "problems": problems},
    )


# ============================================================= design direction


DIRECTION_EVENT = {
    "type": "direction",
    "goal": "a pricing page that reads commitment before price",
    "scope": "src/pages/pricing.tsx",
    "product_context": ["self-serve SaaS priced per seat"],
    "key_hierarchy": ["the plan choice precedes the tier comparison"],
    "interaction_principles": [
        "the annual toggle sits above the tier row and updates prices in place",
        "secondary plan details open in place rather than navigating away",
    ],
    "visual_principles": ["one accent colour carries the primary action and nothing else"],
    "content_principles": ["each tier states its audience before its feature list"],
    "constraints": ["no new dependency for the toggle behaviour"],
    "existing_system": ["the existing type scale and spacing scale are preserved"],
    "reference_findings_adopted": [
        "no reference findings were adopted: this direction was written before any reference was analysed"
    ],
    "findings_rejected": ["a full-width comparison table: it hides the choice on 375px"],
    "accessibility_requirements": ["the toggle is reachable and operable by keyboard"],
    "responsive_requirements": ["the tier row stacks to one column below 768px"],
    "approved_deviations": ["no deviation from the existing system is approved for this task"],
}


def _direction_setup(ctx: Ctx, box=None, request: str = "build a new pricing page with a tier comparison"):
    if box is None:
        box = started_box(ctx, ctx.case.id, request)
    created = record_events(ctx, box, [DIRECTION_EVENT])
    state = box.state()
    direction = (state.get("design_directions") or [{}])[-1]
    return created, direction


@case(
    id="design-direction.actionable-direction-accepted",
    group="design-direction",
    title="An actionable direction record is accepted and constrains implementation",
    task="Record a direction with concrete hierarchy, interaction and responsive rules.",
    expectation="The record is accepted, unapproved, and every constraining section is present.",
    evaluation="Record the direction and read the record and its status.",
    evidence_required="The direction record with its sections and status.",
    layer="deterministic",
)
def direction_actionable(ctx: Ctx) -> Outcome:
    box = started_box(ctx, ctx.case.id, "build a new pricing page with a tier comparison")
    created, direction = _direction_setup(ctx, box)
    problems = []
    if not created.ok:
        problems.append("a valid direction was refused")
    if str(direction.get("status")) != "candidate":
        problems.append(f"a new direction recorded status={direction.get('status')}")
    for name in ("key_hierarchy", "interaction_principles", "responsive_requirements"):
        if not direction.get(name):
            problems.append(f"{name} is empty")
    if not any("373" in item or "768px" in item for item in direction.get("responsive_requirements") or []):
        problems.append("the responsive requirement is not concrete")
    return Outcome(
        status="pass" if not problems else "fail",
        actual=f"status={direction.get('status')} sections_ok={not problems}",
        evidence={"direction": direction, "problems": problems},
    )


@case(
    id="design-direction.generic-direction-refused",
    group="design-direction",
    title="A vague direction is refused as unactionable",
    task="Record a direction whose only visual principle is 'modern, sleek and intuitive'.",
    expectation="The record is refused with a message naming the generic language.",
    evaluation="Attempt the vague direction and read the refusal.",
    evidence_required="The refusal text and the absence of a record.",
    layer="deterministic",
)
def direction_generic_refused(ctx: Ctx) -> Outcome:
    box = started_box(ctx, ctx.case.id, "build a new pricing page with a tier comparison")
    vague = dict(DIRECTION_EVENT)
    vague["visual_principles"] = ["modern, sleek and intuitive"]
    result = record_events(ctx, box, [vague])
    state = box.state()
    problems = []
    if result.ok:
        problems.append("a vague direction was accepted")
    if not state.get("design_directions"):
        pass  # correct: nothing was recorded
    else:
        problems.append("a direction record was written for the refused input")
    if "actionable" not in result.combined and "generic" not in result.combined:
        problems.append(f"the refusal did not name the problem: {result.tail(3)}")
    return Outcome(
        status="pass" if not problems else "fail",
        actual=f"refused={not result.ok} records={len(state.get('design_directions') or [])}",
        evidence={"refusal": result.tail(4), "problems": problems},
    )


@case(
    id="design-direction.worker-cannot-self-approve",
    group="design-direction",
    title="An implementer cannot approve its own design direction",
    task="Record the handoff worker identity, then attempt to approve the direction as that worker.",
    expectation="The approval is refused and no G1D approval is recorded.",
    evaluation="Set the worker identity in the state, attempt approval, read the refusal and the approvals.",
    evidence_required="The refusal and the empty approval list.",
    layer="deterministic",
)
def direction_no_self_approval(ctx: Ctx) -> Outcome:
    box = started_box(ctx, ctx.case.id, "build a new pricing page with a tier comparison")
    _created, direction = _direction_setup(ctx, box)
    state = box.state()
    state["worker"] = {"worker_role": "bulk", "provider": "claude", "model": "sonnet", "identity": "impl-worker"}
    runtime_module = runtime(ctx)
    refused = ""
    try:
        runtime_module.DESIGN.approve_direction(
            state, str(direction["direction_id"]), identity="impl-worker",
        )
    except Exception as exc:
        refused = str(exc)
    approvals = box.state().get("approvals") or []
    problems = []
    if "cannot approve its own design direction" not in refused:
        problems.append(f"the self-approval refusal did not name the rule: {refused!r}")
    if any(record.get("gate") == "G1D" for record in approvals):
        problems.append("a G1D approval was written for the implementer identity")
    return Outcome(
        status="pass" if not problems else "fail",
        actual=f"refused={bool(refused)} g1d_approvals={len([r for r in approvals if r.get('gate') == 'G1D'])}",
        evidence={"refusal": refused, "approvals": approvals, "problems": problems},
    )


@case(
    id="design-direction.stale-approval-rejected-after-material-edit",
    group="design-direction",
    title="A material direction edit invalidates its approval",
    task="Approve a direction, then change an interaction principle and re-check.",
    expectation="The approval is valid before the edit and stale after it; a cosmetic edit does not invalidate it.",
    evaluation="Approve, mutate the record, and read the gate result each time.",
    evidence_required="The three gate results and the two revision fingerprints.",
    layer="deterministic",
)
def direction_stale_approval(ctx: Ctx) -> Outcome:
    box = started_box(ctx, ctx.case.id, "build a new pricing page with a tier comparison")
    _created, direction = _direction_setup(ctx, box)
    cli = ctx.repo.cli(
        "approve-design-direction", "--run-root", str(box.run_root), "--identity", "operator",
    )
    state = box.state()
    runtime_module = runtime(ctx)
    record = runtime_module.DESIGN.direction(state, str(direction["direction_id"]))
    before_revision = runtime_module.DESIGN.direction_revision(record)
    satisfied_before, _reason_before = runtime_module.POLICY.gate_satisfied(
        state, "G1D", runtime_module.DESIGN.direction_subject(record),
    )
    # a cosmetic edit outside the constraining sections leaves the fingerprint alone
    record["editorial_note"] = "typo fix in the draft body"
    unchanged = runtime_module.DESIGN.direction_revision(record) == before_revision
    record["interaction_principles"] = list(record["interaction_principles"]) + [
        "the toggle moves into an overflow menu on 375px",
    ]
    after_revision = runtime_module.DESIGN.direction_revision(record)
    satisfied_after, reason_after = runtime_module.POLICY.gate_satisfied(
        state, "G1D", runtime_module.DESIGN.direction_subject(record),
    )
    problems = []
    if not cli.ok:
        problems.append(f"the operator approval failed: {cli.tail(3)}")
    if not satisfied_before:
        problems.append("the approval was not valid for the approved revision")
    if not unchanged:
        problems.append("a cosmetic edit changed the revision fingerprint")
    if satisfied_after:
        problems.append("the approval still satisfied the gate after a material edit")
    if "stale" not in reason_after:
        problems.append(f"the refusal did not name staleness: {reason_after!r}")
    return Outcome(
        status="pass" if not problems else "fail",
        actual=f"before={satisfied_before} cosmetic_kept_fingerprint={unchanged} after={satisfied_after}",
        evidence={
            "before_revision": before_revision, "after_revision": after_revision,
            "reason_after": reason_after, "problems": problems,
        },
    )


@case(
    id="design-direction.trivial-task-needs-no-direction",
    group="design-direction",
    title="A trivial task is not forced through the direction workflow",
    task="Characterise a one-file spacing fix and check the direction requirement it produces.",
    expectation="DIRECT is not REQUIRED and the boundary declares no direction approval requirement.",
    evaluation="Characterise, select the pipeline, then evaluate the S4B requirement record.",
    evidence_required="The selected DIRECT stage and the requirement record.",
    layer="deterministic",
)
def direction_trivial_task(ctx: Ctx) -> Outcome:
    box = plugin_project(ctx, ctx.case.id)
    box.write(
        "HANDOFF.md",
        "# HANDOFF\n\n## Worker execution contract\n\n| Field | Value |\n| --- | --- |\n| Role | bulk |\n\n"
        "## Permitted scope\n\n| Path | Change |\n| --- | --- |\n"
        "| src/styles/settings.css | fix the spacing around the settings button |\n\n"
        "## Validation commands\n\n| Command | Expected |\n| --- | --- |\n| npm test | pass |\n",
    )
    runtime_module = runtime(ctx)
    record = characterise(ctx, box, "fix the spacing around the settings button")
    plan = runtime_module.DESIGN.select_pipeline(record)
    direct = plan["stages"]["DIRECT"]["selection"]
    state = plugin_state(box, ctx)
    runtime_module.DESIGN.record_characterisation(state, record)
    runtime_module.DESIGN.plan(state, record, task_id="bench-S4B")
    requirement = runtime_module.POLICY.design_evidence_requirement(state, box.project, "S4B")
    problems = []
    if direct == "REQUIRED":
        problems.append("DIRECT was REQUIRED for a spacing fix")
    if requirement.get("required"):
        problems.append("the boundary required a direction approval for a spacing fix")
    return Outcome(
        status="pass" if not problems else "fail",
        actual=f"direct={direct} required={requirement.get('required')} depth={plan['depth']}",
        evidence={"plan": plan["stages"]["DIRECT"], "requirement": requirement, "problems": problems},
    )


# ========================================================== requirement closure


def _closure_state(ctx: Ctx, box):
    """An engine state with one approved direction and one rendered capture."""
    runtime_module = runtime(ctx)
    state = plugin_state(box, ctx)
    box.write("HANDOFF.md", FRONTEND_HANDOFF)
    direction = runtime_module.DESIGN.create_direction(
        state, task_id="bench-S4B", goal="a pricing page that reads commitment before price",
        scope="src/pages/pricing.tsx",
        product_context=["self-serve SaaS"],
        key_hierarchy=["plan choice precedes tier comparison"],
        interaction_principles=["the annual toggle sits above the tier row"],
        visual_principles=["one accent colour carries the primary action"],
        content_principles=["each tier states its audience first"],
        constraints=["no new dependency for the toggle"],
        existing_system=["the existing type scale is preserved"],
        reference_findings_adopted=["no reference findings were adopted: reference research was not required"],
        findings_rejected=["a full-width comparison table"],
        accessibility_requirements=["the toggle is keyboard operable"],
        responsive_requirements=["the tier row stacks below 768px"],
        approved_deviations=["no deviation from the existing system is approved for this task"],
    )
    runtime_module.DESIGN.approve_direction(state, direction["direction_id"], identity="operator")
    capture = runtime_module.RENDER.OfflineFixtureAdapter(
        box.run_root, {
            "scenes": [{
                "route": "/pricing",
                "viewport": {"width": 375, "height": 812, "device_pixel_ratio": 2},
                "dom": "<main><h1>Pricing</h1><button class=\"primary\">Choose</button></main>",
                "interaction": [{"step": 1, "action": "scroll 400", "observed": "the CTA stays at the bottom edge"}],
            }],
        },
    )
    artifact = capture.capture({"route": "/pricing", "kind": "screenshot"})
    revision = "a" * 64
    evidence = runtime_module.RENDER.record(
        state, task_id="bench-S4B", revision_hash=revision, artifact=artifact,
        adapter="offline-fixture", capture_execution="exe_20260101T000000Z_00000000",
        requirement_id="signature-moment",
    )
    return runtime_module, state, evidence, revision


@case(
    id="requirement-closure.source-evidence-sufficient-for-source-claim",
    group="requirement-closure",
    title="A source-level requirement closes from source evidence",
    task="Close a source-level requirement with a source suggestion at its real anchor.",
    expectation="The requirement reaches observed from source evidence; a rendered requirement could not.",
    evaluation="Record the requirement and read its state, then attempt the same evidence for a rendered claim.",
    evidence_required="The closure records and the refusal for the rendered claim.",
    layer="deterministic",
)
def closure_source_sufficient(ctx: Ctx) -> Outcome:
    box = plugin_project(ctx, ctx.case.id)
    runtime_module, state, _evidence, revision = _closure_state(ctx, box)
    source = box.write("src/components/Toggle.tsx", "export const Toggle = () => <button type=\"button\" />;\n")
    suggestion = runtime_module.RENDER.record_source_suggests(
        state, task_id="bench-S4B", revision_hash=revision, source_path=source,
        source_anchor="<button type=\"button\"", observation="the control is a semantic button element",
        requirement_id="semantic-control",
    )
    closed = runtime_module.DESIGN.record_requirement(
        state, requirement_id="semantic-control", evidence_kind="source", task_id="bench-S4B",
        decision={"summary": "use a semantic button", "basis": "thesis"},
        implementation={"status": "implemented", "summary": "Toggle.tsx uses a real button element"},
        evidence_ids=[suggestion["evidence_id"]], state_name="observed", revision_hash=revision,
    )
    rendered_refusal = ""
    try:
        runtime_module.DESIGN.record_requirement(
            state, requirement_id="signature-moment", evidence_kind="rendered", task_id="bench-S4B",
            decision={"summary": "persistent CTA"}, implementation={"status": "implemented", "summary": "CTA added"},
            evidence_ids=[suggestion["evidence_id"]], state_name="verified", revision_hash=revision,
        )
    except Exception as exc:
        rendered_refusal = str(exc)
    problems = []
    if closed["state"] != "observed":
        problems.append(f"state={closed['state']}")
    if "too weak" not in rendered_refusal:
        problems.append(f"the rendered claim was not refused for weak evidence: {rendered_refusal!r}")
    return Outcome(
        status="pass" if not problems else "fail",
        actual=f"source_state={closed['state']} rendered_refused={bool(rendered_refusal)}",
        evidence={
            "closed": closed, "rendered_refusal": rendered_refusal, "problems": problems,
        },
    )


@case(
    id="requirement-closure.rendered-requirement-cannot-close-from-source",
    group="requirement-closure",
    title="A rendered requirement cannot be verified from source inspection alone",
    task="Attempt to verify a rendered requirement using only a source suggestion.",
    expectation="The closure is refused: a source suggestion is not a rendered observation.",
    evaluation="Attempt the closure and read the refusal naming the evidence weakness.",
    evidence_required="The refusal text and the unchanged requirement list.",
    layer="deterministic",
)
def closure_rendered_needs_rendered(ctx: Ctx) -> Outcome:
    box = plugin_project(ctx, ctx.case.id)
    runtime_module, state, _evidence, revision = _closure_state(ctx, box)
    source = box.write("src/styles/pricing.css", ".cta { position: sticky; bottom: 0; }\n")
    suggestion = runtime_module.RENDER.record_source_suggests(
        state, task_id="bench-S4B", revision_hash=revision, source_path=source,
        source_anchor="position: sticky", observation="the CTA is declared sticky",
        requirement_id="signature-moment",
    )
    refusal = ""
    try:
        runtime_module.DESIGN.record_requirement(
            state, requirement_id="signature-moment", evidence_kind="rendered", task_id="bench-S4B",
            decision={"summary": "persistent CTA"}, implementation={"status": "implemented", "summary": "sticky CTA"},
            evidence_ids=[suggestion["evidence_id"]], state_name="verified", revision_hash=revision,
        )
    except Exception as exc:
        refusal = str(exc)
    problems = []
    if "too weak" not in refusal and "independent" not in refusal:
        problems.append(f"the refusal did not name the evidence weakness: {refusal!r}")
    if state.get("design_requirements"):
        problems.append("a requirement record was written for the refused closure")
    return Outcome(
        status="pass" if not problems else "fail",
        actual=f"refused={bool(refusal)} records={len(state.get('design_requirements') or [])}",
        evidence={"refusal": refusal, "problems": problems},
    )


@case(
    id="requirement-closure.missing-evidence-stays-unverified",
    group="requirement-closure",
    title="A requirement with no evidence stays unobserved, and an unverified capture is honest",
    task="Record a rendered requirement with no evidence, and one explicitly unverified with a blocker.",
    expectation="No state above implemented is recorded without evidence; the blocker is preserved.",
    evaluation="Attempt the closure, then record the unverified capture and read the requirement problems.",
    evidence_required="The refusal and the unverified record with its blocker.",
    layer="deterministic",
)
def closure_missing_evidence(ctx: Ctx) -> Outcome:
    box = plugin_project(ctx, ctx.case.id)
    runtime_module, state, _evidence, revision = _closure_state(ctx, box)
    refusal = ""
    try:
        runtime_module.DESIGN.record_requirement(
            state, requirement_id="signature-moment", evidence_kind="rendered", task_id="bench-S4B",
            decision={"summary": "persistent CTA"}, implementation={"status": "implemented", "summary": "CTA added"},
            state_name="observed", revision_hash=revision,
        )
    except Exception as exc:
        refusal = str(exc)
    unverified = runtime_module.RENDER.mark_unverified(
        state, task_id="bench-S4B", revision_hash=revision, requirement_id="signature-moment",
        blocker="no capture capability was available for the 1280px viewport",
    )
    problems = runtime_module.DESIGN.requirement_problems(
        state, [{"id": "signature-moment", "evidence_kind": "rendered"}], revision_hash=revision,
    )
    issues = []
    if "must cite the evidence" not in refusal and "too weak" not in refusal:
        issues.append(f"the evidence-free closure was not refused: {refusal!r}")
    if unverified["state"] != "UNVERIFIED" or not unverified.get("blocker"):
        issues.append("the unverified capture did not record its blocker")
    if not problems:
        issues.append("the requirement is not reported as unclosed")
    return Outcome(
        status="pass" if not issues else "fail",
        actual=f"refused={bool(refusal)} unverified_blocker={bool(unverified.get('blocker'))} problems={len(problems)}",
        evidence={"refusal": refusal, "unverified": unverified, "problems": problems, "issues": issues},
    )


@case(
    id="requirement-closure.stale-artifact-invalidates-verification",
    group="requirement-closure",
    title="A stale rendered artifact invalidates the verification that used it",
    task="Verify a requirement from a capture, then change the captured artifact and re-check.",
    expectation="The requirement is verified while current and stale as soon as the artifact changes.",
    evaluation="Verify, modify the artifact, and compare stale_requirements before and after.",
    evidence_required="The stale report before and after the edit.",
    layer="deterministic",
)
def closure_stale_artifact(ctx: Ctx) -> Outcome:
    box = plugin_project(ctx, ctx.case.id)
    runtime_module, state, evidence, revision = _closure_state(ctx, box)
    runtime_module.DESIGN.record_requirement(
        state, requirement_id="signature-moment", evidence_kind="rendered", task_id="bench-S4B",
        decision={"summary": "persistent CTA"}, implementation={"status": "implemented", "summary": "CTA added"},
        evidence_ids=[evidence["evidence_id"]], state_name="observed", revision_hash=revision,
    )
    before = runtime_module.DESIGN.stale_requirements(state, revision_hash=revision)
    Path(evidence["artifact"]["path"]).write_text("<html>changed</html>", encoding="utf-8")
    after = runtime_module.DESIGN.stale_requirements(state, revision_hash=revision)
    problems = runtime_module.DESIGN.requirement_problems(
        state, [{"id": "signature-moment", "evidence_kind": "rendered"}], revision_hash=revision,
    )
    issues = []
    if before:
        issues.append(f"the fresh requirement was already stale: {before}")
    if not after:
        issues.append("the requirement did not become stale after its artifact changed")
    if not any("stale" in item for item in problems):
        issues.append(f"the requirement problems did not report staleness: {problems}")
    return Outcome(
        status="pass" if not issues else "fail",
        actual=f"stale_before={len(before)} stale_after={len(after)} problems={len(problems)}",
        evidence={"after": after, "problems": problems, "issues": issues},
    )


# ============================================================= rendered evidence


@case(
    id="rendered-evidence.capture-provenance-required",
    group="rendered-evidence",
    title="A screenshot file without capture provenance is not trusted",
    task="Attempt to record an arbitrary screenshot file as rendered evidence.",
    expectation="The record is refused: evidence must arrive through a capture adapter with a verified digest.",
    evaluation="Attempt to record the bare file and read the refusal; the file is never accepted.",
    evidence_required="The refusal and the absent evidence record.",
    layer="deterministic",
)
def rendered_provenance_required(ctx: Ctx) -> Outcome:
    box = plugin_project(ctx, ctx.case.id)
    runtime_module, state, _evidence, revision = _closure_state(ctx, box)
    arbitrary = box.write("design/screenshots/home.png", "\x89PNG-arbitrary\n")
    digest = hashlib.sha256(arbitrary.read_bytes()).hexdigest()
    refusal = ""
    try:
        runtime_module.RENDER.record(
            state, task_id="bench-S4B", revision_hash=revision,
            artifact={"kind": "screenshot", "path": str(arbitrary), "sha256": digest,
                      "viewport": {"width": 375}, "method": "offline-fixture"},
            adapter="offline-fixture",
        )
    except Exception as exc:
        refusal = str(exc)
    wrong_digest = ""
    try:
        runtime_module.RENDER.record(
            state, task_id="bench-S4B", revision_hash=revision,
            artifact=runtime_module.RENDER.CaptureArtifact(
                kind="screenshot", path=str(arbitrary), sha256="b" * 64,
                viewport={"width": 375}, method="offline-fixture",
            ),
            adapter="offline-fixture",
        )
    except Exception as exc:
        wrong_digest = str(exc)
    problems = []
    if not refusal:
        problems.append("a bare file path was accepted as rendered evidence")
    if "digest" not in wrong_digest and "match" not in wrong_digest:
        problems.append(f"a mismatched digest was not refused: {wrong_digest!r}")
    if "viewport" not in refusal and "path" not in refusal and "artifact" not in refusal:
        problems.append(f"the refusal did not name the missing provenance: {refusal!r}")
    return Outcome(
        status="pass" if not problems else "fail",
        actual=f"bare_refused={bool(refusal)} digest_mismatch_refused={bool(wrong_digest)}",
        evidence={"bare_refusal": refusal, "digest_refusal": wrong_digest, "problems": problems},
    )


@case(
    id="rendered-evidence.wrong-revision-rejected",
    group="rendered-evidence",
    title="Evidence captured for another revision is stale",
    task="Capture at one revision and query staleness at another.",
    expectation="The capture is current for its own revision and stale for a different one.",
    evaluation="Compare stale_records at the capturing revision and at a new revision.",
    evidence_required="Both stale reports and the captured revision.",
    layer="deterministic",
)
def rendered_wrong_revision(ctx: Ctx) -> Outcome:
    box = plugin_project(ctx, ctx.case.id)
    runtime_module, state, evidence, revision = _closure_state(ctx, box)
    same = runtime_module.RENDER.stale_records(state, revision_hash=revision)
    other = runtime_module.RENDER.stale_records(state, revision_hash="b" * 64)
    problems = []
    if same:
        problems.append(f"evidence was stale at its own revision: {same}")
    if not other:
        problems.append("evidence was not stale at a different revision")
    elif "different revision" not in " ".join(other[0]["reasons"]):
        problems.append(f"the staleness reason did not name the revision: {other[0]['reasons']}")
    return Outcome(
        status="pass" if not problems else "fail",
        actual=f"same_revision_stale={len(same)} other_revision_stale={len(other)}",
        evidence={"captured_revision": evidence["revision_hash"], "other": other, "problems": problems},
    )


@case(
    id="rendered-evidence.wrong-viewport-detected",
    group="rendered-evidence",
    title="Evidence for one viewport does not satisfy another",
    task="Capture at 375px and ask for the strongest evidence at 1280px.",
    expectation="The 375px capture is found for 375 and not returned for 1280.",
    evaluation="Query the strongest evidence per viewport and compare.",
    evidence_required="The per-viewport results.",
    layer="deterministic",
)
def rendered_wrong_viewport(ctx: Ctx) -> Outcome:
    box = plugin_project(ctx, ctx.case.id)
    runtime_module, state, evidence, _revision = _closure_state(ctx, box)
    mobile = runtime_module.RENDER.strongest(state, "signature-moment", viewport_width="375")
    desktop = runtime_module.RENDER.strongest(state, "signature-moment", viewport_width="1280")
    problems = []
    if mobile.get("evidence_id") != evidence["evidence_id"]:
        problems.append("the 375px capture was not found at 375px")
    if desktop:
        problems.append("a 375px capture answered for 1280px")
    return Outcome(
        status="pass" if not problems else "fail",
        actual=f"mobile_match={mobile.get('evidence_id') == evidence['evidence_id']} desktop={bool(desktop)}",
        evidence={"viewport": evidence.get("viewport"), "desktop": desktop, "problems": problems},
    )


@case(
    id="rendered-evidence.offline-fixture-records-evidence",
    group="rendered-evidence",
    title="The offline fixture adapter records hashed evidence for the workflow",
    task="Capture a screenshot, DOM and accessibility result from the offline fixture.",
    expectation="Each artifact exists, hashes match, the record names its method and environment, and no browser is claimed.",
    evaluation="Capture three kinds, re-hash the files, and read the recorded provenance.",
    evidence_required="The capture records, their hashes and their declared method.",
    layer="deterministic",
)
def rendered_offline_fixture(ctx: Ctx) -> Outcome:
    box = plugin_project(ctx, ctx.case.id)
    runtime_module = runtime(ctx)
    adapter = runtime_module.RENDER.OfflineFixtureAdapter(
        box.run_root,
        {"scenes": [{
            "route": "/pricing",
            "viewport": {"width": 375, "height": 812, "device_pixel_ratio": 2},
            "dom": "<main><h1>Pricing</h1></main>",
            "accessibility": [{"rule": "color-contrast", "severity": "serious", "target": ".cta"}],
        }]},
    )
    artifacts = [
        adapter.capture({"route": "/pricing", "kind": kind, "viewport": {"width": 375}})
        for kind in ("screenshot", "dom", "accessibility")
    ]
    problems = []
    for artifact in artifacts:
        path = Path(artifact.path)
        if not path.is_file():
            problems.append(f"{artifact.kind} artifact is missing")
            continue
        if hashlib.sha256(path.read_bytes()).hexdigest() != artifact.sha256:
            problems.append(f"{artifact.kind} hash does not match the file")
        if artifact.method != "offline-fixture":
            problems.append(f"{artifact.kind} method={artifact.method}")
        if str(artifact.viewport.get("width")) != "375":
            problems.append(f"{artifact.kind} viewport={artifact.viewport}")
    environment = dict(artifacts[0].environment)
    if environment.get("browser") != "none":
        problems.append("the offline fixture claims a browser")
    manifest = Path(artifacts[0].path).parent / "capture-manifest.json"
    if not manifest.is_file():
        problems.append("no capture manifest was written beside the artifacts")
    return Outcome(
        status="pass" if not problems else "fail",
        actual=f"artifacts={len(artifacts)} manifest={manifest.is_file()} browser={environment.get('browser')}",
        evidence={
            "kinds": [artifact.kind for artifact in artifacts],
            "environment": environment,
            "manifest": str(manifest),
            "problems": problems,
        },
        metrics={"artifacts": len(artifacts)},
    )


@case(
    id="rendered-evidence.declared-observer-cannot-exceed-rendered",
    group="rendered-evidence",
    title="Externally declared evidence cannot be promoted to observed",
    task="Record a declared-observer artifact, then attempt to promote it to observed.",
    expectation="The artifact records as RENDERED and the promotion is refused.",
    evaluation="Record the declared artifact and attempt the observation.",
    evidence_required="The record's state and the refusal.",
    layer="deterministic",
)
def rendered_declared_observer(ctx: Ctx) -> Outcome:
    box = plugin_project(ctx, ctx.case.id)
    runtime_module, state, _evidence, revision = _closure_state(ctx, box)
    shot = box.write("design/observer/home.png", "\x89PNG-declared\n")
    observer = runtime_module.RENDER.DeclaredObserverAdapter(
        method="operator recorded this with their own browser",
        environment={"browser": "operator's browser", "os": "unknown"},
    )
    artifact = observer.capture({
        "path": str(shot), "kind": "screenshot", "viewport": {"width": 375}, "observation": "",
    })
    record = runtime_module.RENDER.record(
        state, task_id="bench-S4B", revision_hash=revision, artifact=artifact,
        adapter="declared-observer",
    )
    refusal = ""
    try:
        runtime_module.RENDER.observe(
            state, record["evidence_id"],
            artifact={"path": str(shot), "sha256": artifact.sha256},
            observation="the CTA stays pinned while scrolling",
        )
    except Exception as exc:
        refusal = str(exc)
    problems = []
    if record["state"] != "RENDERED":
        problems.append(f"state={record['state']}")
    if record["capture_method"] != "declared-observer":
        problems.append(f"method={record['capture_method']}")
    if "ceiling" not in refusal and "declared" not in refusal:
        problems.append(f"the promotion was not refused as declared evidence: {refusal!r}")
    return Outcome(
        status="pass" if not problems else "fail",
        actual=f"state={record['state']} promotion_refused={bool(refusal)}",
        evidence={"record": record, "refusal": refusal, "problems": problems},
    )


@case(
    id="rendered-evidence.declared-observer-cannot-be-verified",
    group="rendered-evidence",
    title="Externally declared evidence cannot be promoted to verified",
    task="Record a declared-observer artifact and attempt to verify it by re-production.",
    expectation="The verification is refused: re-hashing the same external file under a second execution is not independent re-production.",
    evaluation="Record the declared artifact, attempt verify, and read the refusal and the unchanged state.",
    evidence_required="The refusal, the record state and the verification execution used.",
    layer="deterministic",
)
def rendered_declared_observer_verify(ctx: Ctx) -> Outcome:
    box = plugin_project(ctx, ctx.case.id)
    runtime_module, state, _evidence, revision = _closure_state(ctx, box)
    shot = box.write("design/observer/home.png", "\x89PNG-declared\n")
    observer = runtime_module.RENDER.DeclaredObserverAdapter(
        method="operator recorded this with their own browser",
        environment={"browser": "operator's browser", "os": "unknown"},
    )
    artifact = observer.capture({
        "path": str(shot), "kind": "screenshot", "viewport": {"width": 375}, "observation": "",
    })
    record = runtime_module.RENDER.record(
        state, task_id="bench-S4B", revision_hash=revision, artifact=artifact,
        adapter="declared-observer",
    )
    verifier = runtime_module.EXECUTION.create(
        state, task_id="bench-S4B", role="validator",
        adapter="scripts/ariadne.py:design-verify:declared-observer",
        revision={"revision_hash": revision},
    )
    refusal = ""
    try:
        runtime_module.RENDER.verify(
            state, record["evidence_id"],
            verification_execution=str(verifier["execution_id"]),
            reproduced_sha256=artifact.sha256,
            method="independent re-capture",
        )
    except Exception as exc:
        refusal = str(exc)
    problems = []
    if not refusal:
        problems.append("a declared-observer artifact was promoted to VERIFIED")
    if "declared" not in refusal:
        problems.append(f"the refusal did not name the declared evidence ceiling: {refusal!r}")
    if record["state"] != "RENDERED":
        problems.append(f"state={record['state']}")
    return Outcome(
        status="pass" if not problems else "fail",
        actual=f"state={record['state']} verify_refused={bool(refusal)}",
        evidence={"record": record, "refusal": refusal, "problems": problems},
    )


@case(
    id="rendered-evidence.browser-capability-reported-honestly",
    group="rendered-evidence",
    title="An unconfigured browser capability is reported, never faked",
    task="Ask the capture adapters what they can do and attempt a browser capture.",
    expectation="The browser adapter reports unavailable with a reason and capture is refused.",
    evaluation="Read the capability matrix and attempt the capture.",
    evidence_required="The capability matrix, the refusal and the route decision status.",
    layer="deterministic",
)
def rendered_browser_honest(ctx: Ctx) -> Outcome:
    box = plugin_project(ctx, ctx.case.id)
    runtime_module = runtime(ctx)
    adapters = runtime_module.RENDER.default_adapters(box.run_root)
    browser = adapters["local-browser"]
    available, reason = browser.available()
    refusal = ""
    try:
        browser.capture({"route": "/", "kind": "screenshot", "viewport": {"width": 375}})
    except Exception as exc:
        refusal = str(exc)
    matrix = runtime_module.RENDER.capability_matrix(adapters)
    problems = []
    if available:
        problems.append("the browser adapter reported itself available without configuration")
    if not reason:
        problems.append("the unavailable browser adapter recorded no reason")
    if "unavailable" not in refusal.lower() and "cannot capture" not in refusal.lower():
        problems.append(f"the capture refusal did not name availability: {refusal!r}")
    if not any(item["id"] == "local-browser" and item["available"] is False for item in matrix):
        problems.append("the capability matrix did not report the browser as unavailable")
    return Outcome(
        status="pass" if not problems else "fail",
        actual=f"available={available} refusal={bool(refusal)}",
        evidence={"matrix": matrix, "refusal": refusal, "problems": problems},
    )


# ============================================================ independent critique


def _critique_state(ctx: Ctx, box):
    """A design run with an approved direction, observed evidence and two executions."""
    runtime_module = runtime(ctx)
    state = plugin_state(box, ctx)
    characterisation = runtime_module.DESIGN.characterize(
        state, project=box.project, stage="S4B",
        request=(
            "build a new landing page with a hero and pricing cards; research reference sites; "
            "make it accessible and responsive at 375 and 1280"
        ),
        task_id="bench-S4B", transport=runtime_module.TRANSPORT,
    )
    runtime_module.DESIGN.record_characterisation(state, characterisation)
    runtime_module.DESIGN.plan(state, characterisation, task_id="bench-S4B")
    direction = runtime_module.DESIGN.create_direction(
        state, task_id="bench-S4B", goal="a landing page that states the offer before the tiers",
        scope="src/pages/landing.tsx",
        product_context=["self-serve SaaS"],
        key_hierarchy=["the offer statement precedes the pricing tiers"],
        interaction_principles=["the primary action stays at the bottom edge on mobile"],
        visual_principles=["one accent colour carries the primary action"],
        content_principles=["each section states its outcome before its features"],
        constraints=["no new dependency for the sticky action"],
        existing_system=["the existing type and spacing scales are preserved"],
        reference_findings_adopted=["no reference findings were adopted: the fixture analyses no reference before the direction"],
        findings_rejected=["a full-width comparison table"],
        accessibility_requirements=["the primary action is keyboard operable with visible focus"],
        responsive_requirements=["the tier cards stack to one column below 768px"],
        approved_deviations=["no deviation from the existing system is approved for this task"],
    )
    runtime_module.DESIGN.approve_direction(state, direction["direction_id"], identity="operator")
    adapter = runtime_module.RENDER.OfflineFixtureAdapter(
        box.run_root,
        {"scenes": [{
            "route": "/landing",
            "viewport": {"width": 375, "height": 812, "device_pixel_ratio": 2},
            "dom": "<main><h1>Ship faster</h1><button class=\"primary\">Start</button></main>",
            "accessibility": [{"rule": "color-contrast", "severity": "serious", "target": ".primary"}],
            "interaction": [{"step": 1, "action": "scroll 400", "observed": "the primary action stays at the bottom edge"}],
        }]},
    )
    artifact = adapter.capture({"route": "/landing", "kind": "screenshot"})
    revision = "c" * 64
    implementer = runtime_module.EXECUTION.create(
        state, task_id="bench-S4B", role="implementer",
        adapter="scripts/prepare-stage.py:worker",
        requested={"worker_role": "bulk", "provider": "claude", "model": "sonnet"},
        revision={"revision_hash": revision},
    )
    runtime_module.EXECUTION.mark_started(state, implementer["execution_id"])
    evidence = runtime_module.RENDER.record(
        state, task_id="bench-S4B", revision_hash=revision, artifact=artifact,
        adapter="offline-fixture", capture_execution="exe_20260101T000000Z_00000000",
        requirement_id="signature-moment",
    )
    observation_file = box.write("design/references/scroll-observation.md", "step 1: scroll 400\nobserved: the action stays pinned\n")
    runtime_module.RENDER.observe(
        state, evidence["evidence_id"],
        artifact={"path": str(observation_file), "sha256": hashlib.sha256(observation_file.read_bytes()).hexdigest()},
        observation="the primary action stays at the bottom edge after 400px of scroll",
    )
    reviewer = runtime_module.EXECUTION.create(
        state, task_id="bench-S4B", role="reviewer",
        adapter="scripts/ariadne.py:record-design:review",
        requested={"provider": "reviewer", "model": "design-critique"},
        revision={"revision_hash": revision},
        parent=implementer["execution_id"],
    )
    return runtime_module, state, {
        "direction": direction, "evidence": evidence, "implementer": implementer,
        "reviewer": reviewer, "revision": revision, "characterisation": characterisation,
    }


def _finding(evidence_id: str, **overrides) -> dict:
    row = {
        "dimension": "accessibility",
        "severity": "major",
        "evidence_ids": [evidence_id],
        "requirement_id": "signature-moment",
        "location": "src/pages/landing.tsx:42 (.primary)",
        "explanation": "the captured contrast result is 3.1:1 against the required 4.5:1",
        "repair_scope": "the .primary colour token only",
        "confidence": "supported",
    }
    row.update(overrides)
    return row


@case(
    id="design-critique.implementer-cannot-review-own-work",
    group="design-critique",
    title="An implementer cannot certify its own visual quality",
    task="Attempt a critique whose reviewer identity and execution are the implementer's.",
    expectation="The critique is refused on both the identity and the execution check.",
    evaluation="Attempt the self-review and read the refusal; assert no review record exists.",
    evidence_required="The refusal text and the unchanged review list.",
    layer="deterministic",
)
def critique_self_review(ctx: Ctx) -> Outcome:
    box = plugin_project(ctx, ctx.case.id)
    runtime_module, state, kit = _critique_state(ctx, box)
    state["worker"] = {"worker_role": "bulk", "provider": "claude", "model": "sonnet", "identity": "impl-bot"}
    refusal = ""
    try:
        runtime_module.CRITIQUE.build_review(
            state, task_id="bench-S4B", direction_id=str(kit["direction"]["direction_id"]),
            findings=[_finding(kit["evidence"]["evidence_id"])],
            reviewer_identity="impl-bot",
            reviewer_execution=str(kit["implementer"]["execution_id"]),
            implementing_execution=str(kit["implementer"]["execution_id"]),
            requirement_ids=["signature-moment"], evidence_ids=[kit["evidence"]["evidence_id"]],
        )
    except Exception as exc:
        refusal = str(exc)
    problems = []
    if not refusal:
        problems.append("a self-review was accepted")
    if "independence" not in refusal and "implementer" not in refusal:
        problems.append(f"the refusal did not name independence: {refusal!r}")
    if state.get("design_reviews"):
        problems.append("a design review record was written for the self-review")
    return Outcome(
        status="pass" if not problems else "fail",
        actual=f"refused={bool(refusal)} reviews={len(state.get('design_reviews') or [])}",
        evidence={"refusal": refusal, "problems": problems},
    )


@case(
    id="design-critique.review-without-rendered-evidence-refused",
    group="design-critique",
    title="A critique of rendered work without rendered evidence is refused",
    task="Prepare a critique for a task whose rendered QA is REQUIRED, with no evidence ids.",
    expectation="Preparation is refused and names the missing rendered evidence.",
    evaluation="Call prepare_review with no evidence and read the refusal.",
    evidence_required="The refusal and the characterisation that required rendering.",
    layer="deterministic",
)
def critique_without_evidence(ctx: Ctx) -> Outcome:
    box = plugin_project(ctx, ctx.case.id)
    runtime_module, state, kit = _critique_state(ctx, box)
    refusal = ""
    try:
        runtime_module.CRITIQUE.prepare_review(
            state, task_id="bench-S4B", direction_id=str(kit["direction"]["direction_id"]),
            requirement_ids=["signature-moment"],
            reviewer_role="independent-reviewer",
            reviewer_execution=str(kit["reviewer"]["execution_id"]),
            implementing_execution=str(kit["implementer"]["execution_id"]),
        )
    except Exception as exc:
        refusal = str(exc)
    values = {
        name: value["value"]
        for name, value in (kit["characterisation"]["characteristics"] or {}).items()
    }
    problems = []
    if not refusal:
        problems.append("a critique without rendered evidence was prepared")
    if "rendered evidence" not in refusal:
        problems.append(f"the refusal did not name the missing rendered evidence: {refusal!r}")
    if values.get("rendered_qa") != "REQUIRED":
        problems.append(f"the fixture did not require rendered QA: {values.get('rendered_qa')}")
    return Outcome(
        status="pass" if not problems else "fail",
        actual=f"rendered_qa={values.get('rendered_qa')} refused={bool(refusal)}",
        evidence={"refusal": refusal, "rendered_qa": values.get("rendered_qa"), "problems": problems},
    )


@case(
    id="design-critique.review-against-stale-direction-refused",
    group="design-critique",
    title="A critique against a changed direction is refused",
    task="Approve a direction, change a constraining rule, then attempt the critique.",
    expectation="The critique is refused because it would judge against a revision nobody approved.",
    evaluation="Mutate the direction and attempt the review; read the refusal.",
    evidence_required="The refusal and the earlier approval revision.",
    layer="deterministic",
)
def critique_stale_direction(ctx: Ctx) -> Outcome:
    box = plugin_project(ctx, ctx.case.id)
    runtime_module, state, kit = _critique_state(ctx, box)
    direction = runtime_module.DESIGN.direction(state, str(kit["direction"]["direction_id"]))
    approved_revision = runtime_module.DESIGN.direction_revision(direction)
    direction["responsive_requirements"] = list(direction["responsive_requirements"]) + [
        "the tiers collapse into an accordion below 480px",
    ]
    refusal = ""
    try:
        runtime_module.CRITIQUE.build_review(
            state, task_id="bench-S4B", direction_id=str(direction["direction_id"]),
            findings=[_finding(kit["evidence"]["evidence_id"])],
            reviewer_identity="independent-reviewer",
            reviewer_execution=str(kit["reviewer"]["execution_id"]),
            implementing_execution=str(kit["implementer"]["execution_id"]),
            requirement_ids=["signature-moment"], evidence_ids=[kit["evidence"]["evidence_id"]],
        )
    except Exception as exc:
        refusal = str(exc)
    problems = []
    if not refusal:
        problems.append("a critique against a changed direction was accepted")
    if "stale" not in refusal.lower() and "approved revision" not in refusal:
        problems.append(f"the refusal did not name the stale direction: {refusal!r}")
    if runtime_module.DESIGN.direction_revision(direction) == approved_revision:
        problems.append("the direction fingerprint did not change")
    return Outcome(
        status="pass" if not problems else "fail",
        actual=f"approved={approved_revision[:12]} now={runtime_module.DESIGN.direction_revision(direction)[:12]} refused={bool(refusal)}",
        evidence={"refusal": refusal, "problems": problems},
    )


@case(
    id="design-critique.valid-critique-records-findings",
    group="design-critique",
    title="A valid independent critique records structured findings",
    task="Run a critique from a distinct reviewer execution against observed evidence.",
    expectation="The record binds two executions, the direction revision and structured findings that cite evidence.",
    evaluation="Build the review and read the record's bindings and findings.",
    evidence_required="The review record with its execution binding, direction revision and findings.",
    layer="deterministic",
)
def critique_valid_findings(ctx: Ctx) -> Outcome:
    box = plugin_project(ctx, ctx.case.id)
    runtime_module, state, kit = _critique_state(ctx, box)
    record = runtime_module.CRITIQUE.build_review(
        state, task_id="bench-S4B", direction_id=str(kit["direction"]["direction_id"]),
        findings=[
            _finding(kit["evidence"]["evidence_id"]),
            _finding(kit["evidence"]["evidence_id"], dimension="spacing", severity="minor",
                     location="src/styles/landing.css:18", explanation="the tier cards use an off-scale gap",
                     repair_scope="the tier card gap token only", confidence="supported"),
        ],
        reviewer_identity="independent-reviewer",
        reviewer_execution=str(kit["reviewer"]["execution_id"]),
        implementing_execution=str(kit["implementer"]["execution_id"]),
        requirement_ids=["signature-moment"], evidence_ids=[kit["evidence"]["evidence_id"]],
        outcome="failed",
        differential="the primary action is present and persistent; its contrast is the only defect",
        qa_records={
            "functional": {"state": "passed", "evidence": ["npm test: 42 passed"]},
            "accessibility": {"state": "failed", "evidence": [kit["evidence"]["evidence_id"]],
                              "detail": "contrast 3.1:1"},
            "regression": {"state": "passed", "evidence": ["campaign-2026-09"]},
            "judgement": {"state": "failed", "evidence": [kit["evidence"]["evidence_id"]]},
        },
    )
    findings = record["findings"]
    qa = record["qa_activities"]
    problems = []
    if record["reviewer_execution"] == record["implementing_execution"]:
        problems.append("the review bound one execution as both")
    if record["direction_revision"] != runtime_module.DESIGN.direction_revision(kit["direction"]):
        problems.append("the review did not bind the approved direction revision")
    if len(findings) != 2:
        problems.append(f"findings={len(findings)}")
    for finding in findings:
        for field in ("dimension", "severity", "evidence_ids", "explanation", "repair_scope"):
            if not finding.get(field):
                problems.append(f"finding {finding.get('finding_id')} has no {field}")
    if set(qa) - {"note", "functional", "accessibility", "regression", "judgement"}:
        problems.append(f"unexpected QA keys: {sorted(qa)}")
    if "score" in json.dumps(qa).lower() and "no combined design score" not in json.dumps(qa).lower():
        problems.append("the QA record contains a score-like value")
    return Outcome(
        status="pass" if not problems else "fail",
        actual=f"findings={len(findings)} reviewer!=implementer={record['reviewer_execution'] != record['implementing_execution']}",
        evidence={"review": record, "qa": qa, "problems": problems},
        metrics={"findings": len(findings)},
    )


@case(
    id="design-critique.finding-without-evidence-refused",
    group="design-critique",
    title="A finding must cite evidence and name a repair scope",
    task="Submit a critique whose finding cites no evidence.",
    expectation="The critique is refused and no review record is written.",
    evaluation="Attempt the review and read the refusal.",
    evidence_required="The refusal text and the unchanged review list.",
    layer="deterministic",
)
def critique_finding_needs_evidence(ctx: Ctx) -> Outcome:
    box = plugin_project(ctx, ctx.case.id)
    runtime_module, state, kit = _critique_state(ctx, box)
    refusal = ""
    try:
        runtime_module.CRITIQUE.build_review(
            state, task_id="bench-S4B", direction_id=str(kit["direction"]["direction_id"]),
            findings=[_finding(kit["evidence"]["evidence_id"], evidence_ids=[])],
            reviewer_identity="independent-reviewer",
            reviewer_execution=str(kit["reviewer"]["execution_id"]),
            implementing_execution=str(kit["implementer"]["execution_id"]),
            requirement_ids=["signature-moment"], evidence_ids=[kit["evidence"]["evidence_id"]],
        )
    except Exception as exc:
        refusal = str(exc)
    problems = []
    if "evidence_ids" not in refusal:
        problems.append(f"the refusal did not name the missing citation: {refusal!r}")
    if state.get("design_reviews"):
        problems.append("a review record was written for the refused finding")
    return Outcome(
        status="pass" if not problems else "fail",
        actual=f"refused={bool(refusal)} reviews={len(state.get('design_reviews') or [])}",
        evidence={"refusal": refusal, "problems": problems},
    )


# ================================================================= refinement


def _refinement_state(ctx: Ctx, box):
    runtime_module, state, kit = _critique_state(ctx, box)
    review = runtime_module.CRITIQUE.build_review(
        state, task_id="bench-S4B", direction_id=str(kit["direction"]["direction_id"]),
        findings=[_finding(kit["evidence"]["evidence_id"])],
        reviewer_identity="independent-reviewer",
        reviewer_execution=str(kit["reviewer"]["execution_id"]),
        implementing_execution=str(kit["implementer"]["execution_id"]),
        requirement_ids=["signature-moment"], evidence_ids=[kit["evidence"]["evidence_id"]],
        outcome="failed",
    )
    return runtime_module, state, kit, review


def _proposal(kit, review, **overrides) -> dict:
    options = {
        "task_id": "bench-S4B",
        "artifact": "src/pages/landing.tsx",
        "intended_change": "raise the primary action contrast to the approved floor",
        "permitted_scope": ["src/pages/landing.tsx", "src/styles/landing.css"],
        "expected_evidence": [kit["evidence"]["evidence_id"]],
        "regression_checks": ["npm test", "campaign-2026-09 screenshot comparison"],
    }
    options.update(overrides)
    return options


@case(
    id="design-refinement.targeted-finding-leads-to-scoped-repair",
    group="design-refinement",
    title="A finding produces a scoped repair, not a redesign",
    task="Propose a refinement for a contrast finding and inspect its scope.",
    expectation="The plan names the finding, the scope, the expected evidence and the regression checks.",
    evaluation="Propose the refinement and read the record; the finding state only changes after the result.",
    evidence_required="The refinement record and the still-open finding.",
    layer="deterministic",
)
def refinement_scoped_repair(ctx: Ctx) -> Outcome:
    box = plugin_project(ctx, ctx.case.id)
    runtime_module, state, kit, review = _refinement_state(ctx, box)
    finding_id = review["findings"][0]["finding_id"]
    record = runtime_module.CRITIQUE.propose_refinement(state, finding_id, **_proposal(kit, review))
    problems = []
    if record["finding_id"] != finding_id:
        problems.append("the plan does not name the finding it repairs")
    if not record["permitted_scope"]:
        problems.append("the plan names no scope")
    if not record["regression_checks"]:
        problems.append("the plan declares no regression checks")
    if record["state"] != "proposed":
        problems.append(f"state={record['state']}")
    finding = runtime_module.CRITIQUE.finding(state, finding_id)
    if str(finding.get("state")) != "open":
        problems.append(f"the finding changed to {finding.get('state')} before any repair was recorded")
    return Outcome(
        status="pass" if not problems else "fail",
        actual=f"scope={len(record['permitted_scope'])} checks={len(record['regression_checks'])} finding=open",
        evidence={"refinement": record, "finding": finding, "problems": problems},
    )


@case(
    id="design-refinement.affected-evidence-recaptured",
    group="design-refinement",
    title="A repair re-captures the affected evidence and resolves its finding",
    task="Apply the refinement, re-capturing the evidence it declared.",
    expectation="The cycle verifies, the finding becomes repaired, and no regression is reported.",
    evaluation="Record the refinement result with the declared evidence and read the outcome.",
    evidence_required="The refinement result, the resolved finding and the summary.",
    layer="deterministic",
)
def refinement_recapture(ctx: Ctx) -> Outcome:
    box = plugin_project(ctx, ctx.case.id)
    runtime_module, state, kit, review = _refinement_state(ctx, box)
    finding_id = review["findings"][0]["finding_id"]
    record = runtime_module.CRITIQUE.propose_refinement(state, finding_id, **_proposal(kit, review))
    applied = runtime_module.CRITIQUE.record_refinement(
        state, record["refinement_id"], applied=True,
        changed_artifacts=["src/styles/landing.css"],
        revalidated={"npm test": "42 passed"},
        recaptured=[kit["evidence"]["evidence_id"]],
        regressions=[],
    )
    runtime_module.CRITIQUE.resolve_findings(state, record["refinement_id"], resolved=[])
    finding = runtime_module.CRITIQUE.finding(state, finding_id)
    summary = runtime_module.CRITIQUE.refinement_summary(state, task_id="bench-S4B")
    problems = []
    if applied["state"] != "verified":
        problems.append(f"state={applied['state']}")
    if str(finding.get("state")) != "repaired":
        problems.append(f"finding state={finding.get('state')}")
    if summary["remaining_findings"]:
        problems.append(f"findings still open: {summary['remaining_findings']}")
    if applied["regressions"]:
        problems.append(f"unexpected regressions: {applied['regressions']}")
    return Outcome(
        status="pass" if not problems else "fail",
        actual=f"refinement={applied['state']} finding={finding.get('state')} remaining={len(summary['remaining_findings'])}",
        evidence={"refinement": applied, "finding": finding, "summary": summary, "problems": problems},
    )


@case(
    id="design-refinement.unrelated-artifact-unchanged",
    group="design-refinement",
    title="A repair that touches artifacts outside its scope is refused",
    task="Record a refinement result that changed a file outside the permitted scope.",
    expectation="The result is refused and the refinement stays proposed.",
    evaluation="Attempt the out-of-scope result and read the refusal.",
    evidence_required="The refusal and the unchanged refinement state.",
    layer="deterministic",
)
def refinement_scope_enforced(ctx: Ctx) -> Outcome:
    box = plugin_project(ctx, ctx.case.id)
    runtime_module, state, kit, review = _refinement_state(ctx, box)
    finding_id = review["findings"][0]["finding_id"]
    record = runtime_module.CRITIQUE.propose_refinement(state, finding_id, **_proposal(kit, review))
    refusal = ""
    try:
        runtime_module.CRITIQUE.record_refinement(
            state, record["refinement_id"], applied=True,
            changed_artifacts=["src/pages/pricing.tsx", "src/app/layout.tsx"],
            revalidated={"npm test": "42 passed"},
            recaptured=[kit["evidence"]["evidence_id"]],
        )
    except Exception as exc:
        refusal = str(exc)
    current = runtime_module.CRITIQUE.refinement(state, record["refinement_id"])
    problems = []
    if not refusal:
        problems.append("an out-of-scope change was accepted")
    if "outside its permitted scope" not in refusal:
        problems.append(f"the refusal did not name the scope: {refusal!r}")
    if current["state"] != "proposed":
        problems.append(f"the refinement moved to {current['state']}")
    if "src/pages/pricing.tsx" not in refusal or "src/app/layout.tsx" not in refusal:
        problems.append("the refusal did not name the offending artifacts")
    return Outcome(
        status="pass" if not problems else "fail",
        actual=f"refused={bool(refusal)} state={current['state']}",
        evidence={"refusal": refusal, "refinement": current, "problems": problems},
    )


@case(
    id="design-refinement.repair-limit-enforced",
    group="design-refinement",
    title="Design refinement stops at the bounded budget",
    task="Propose and apply refinements until the budget is exhausted, then attempt one more.",
    expectation="The budget reports the limit, the extra proposal is refused, and the reason is named.",
    evaluation="Loop proposals, read the budget and the final refusal.",
    evidence_required="The budget records and the refusal.",
    layer="deterministic",
)
def refinement_limit(ctx: Ctx) -> Outcome:
    box = plugin_project(ctx, ctx.case.id)
    runtime_module, state, kit, review = _refinement_state(ctx, box)
    finding_id = review["findings"][0]["finding_id"]
    attempts = []
    refusal = ""
    for index in range(runtime_module.CRITIQUE.MAX_DESIGN_REFINEMENTS + 1):
        try:
            record = runtime_module.CRITIQUE.propose_refinement(
                state, finding_id, **_proposal(kit, review, intended_change=f"repair attempt {index + 1}"),
            )
            attempts.append(record)
            runtime_module.CRITIQUE.record_refinement(
                state, record["refinement_id"], applied=True,
                changed_artifacts=["src/styles/landing.css"],
                revalidated={"npm test": "42 passed"},
                recaptured=[kit["evidence"]["evidence_id"]],
            )
        except Exception as exc:
            refusal = str(exc)
    budget = runtime_module.CRITIQUE.refinement_budget(state, task_id="bench-S4B")
    problems = []
    if len(attempts) != runtime_module.CRITIQUE.MAX_DESIGN_REFINEMENTS:
        problems.append(f"attempts={len(attempts)} limit={runtime_module.CRITIQUE.MAX_DESIGN_REFINEMENTS}")
    if not refusal:
        problems.append("the budget did not stop the extra proposal")
    if "REFINEMENT_LIMIT_REACHED" not in refusal:
        problems.append(f"the refusal did not name the limit: {refusal!r}")
    if budget["remaining"] != 0:
        problems.append(f"remaining={budget['remaining']}")
    return Outcome(
        status="pass" if not problems else "fail",
        actual=f"attempts={len(attempts)} limit={budget['limit']} remaining={budget['remaining']}",
        evidence={"budget": budget, "refusal": refusal, "problems": problems},
        metrics={"refinement_attempts": len(attempts)},
    )


@case(
    id="design-refinement.unresolved-finding-remains-visible",
    group="design-refinement",
    title="A repair that breaks a passing check is a regression, not a fix",
    task="Record a refinement result that reports a regression.",
    expectation="The cycle fails, the finding stays unresolved, and both remain visible in the summary.",
    evaluation="Record the regressing result and read the refinement, the finding and the summary.",
    evidence_required="The failed refinement, the unresolved finding and the summary.",
    layer="deterministic",
)
def refinement_regression_visible(ctx: Ctx) -> Outcome:
    box = plugin_project(ctx, ctx.case.id)
    runtime_module, state, kit, review = _refinement_state(ctx, box)
    finding_id = review["findings"][0]["finding_id"]
    record = runtime_module.CRITIQUE.propose_refinement(state, finding_id, **_proposal(kit, review))
    applied = runtime_module.CRITIQUE.record_refinement(
        state, record["refinement_id"], applied=True,
        changed_artifacts=["src/styles/landing.css"],
        revalidated={"npm test": "40 passed, 2 failed"},
        recaptured=[kit["evidence"]["evidence_id"]],
        regressions=["campaign-2026-09 screenshot comparison changed in an unrelated region"],
    )
    runtime_module.CRITIQUE.resolve_findings(state, record["refinement_id"], resolved=[])
    finding = runtime_module.CRITIQUE.finding(state, finding_id)
    summary = runtime_module.CRITIQUE.refinement_summary(state, task_id="bench-S4B")
    problems = []
    if applied["state"] != "failed":
        problems.append(f"state={applied['state']}")
    if not applied["regressions"]:
        problems.append("the regression was not recorded")
    if str(finding.get("state")) != "unresolved":
        problems.append(f"finding state={finding.get('state')}")
    if not summary["remaining_findings"]:
        problems.append("the unresolved finding disappeared from the summary")
    if summary["regressions"] != applied["regressions"]:
        problems.append("the summary does not report the regression")
    return Outcome(
        status="pass" if not problems else "fail",
        actual=f"refinement={applied['state']} finding={finding.get('state')} remaining={len(summary['remaining_findings'])}",
        evidence={"refinement": applied, "summary": summary, "problems": problems},
    )


@case(
    id="design-refinement.broad-redesign-refused",
    group="design-refinement",
    title="A non-blocking finding cannot authorize a broad redesign",
    task="Propose a refinement for a minor finding whose scope is the whole interface.",
    expectation="The proposal is refused: the repair must name the smallest affected artifacts.",
    evaluation="Attempt the broad proposal and read the refusal.",
    evidence_required="The refusal and the absence of a refinement record.",
    layer="deterministic",
)
def refinement_broad_refused(ctx: Ctx) -> Outcome:
    box = plugin_project(ctx, ctx.case.id)
    runtime_module, state, kit, review = _refinement_state(ctx, box)
    review["findings"][0]["severity"] = "minor"
    refusal = ""
    try:
        runtime_module.CRITIQUE.propose_refinement(
            state, review["findings"][0]["finding_id"],
            **_proposal(kit, review, permitted_scope=["the entire interface", "everything"]),
        )
    except Exception as exc:
        refusal = str(exc)
    problems = []
    if not refusal:
        problems.append("a broad redesign was authorized by a minor finding")
    if "broad redesign" not in refusal:
        problems.append(f"the refusal did not name the scope problem: {refusal!r}")
    if state.get("design_refinements"):
        problems.append("a refinement record was written for the refused proposal")
    return Outcome(
        status="pass" if not problems else "fail",
        actual=f"refused={bool(refusal)} records={len(state.get('design_refinements') or [])}",
        evidence={"refusal": refusal, "problems": problems},
    )


# ============================================================== trust invariants


@case(
    id="design-invariants.direction-gate-is-separate",
    group="design-invariants",
    title="The direction-record gate never substitutes for the DESIGN.md gate",
    task="Approve a design direction (G1D) and check the G1 gate and the reverse.",
    expectation="G1D satisfies only G1D; G1 still reports no approval and DESIGN.md staleness still applies.",
    evaluation="Approve G1D, then evaluate both gates and try to satisfy G1D with a G1 approval.",
    evidence_required="Both gate results and the recorded approvals.",
    layer="deterministic",
)
def invariants_gate_separation(ctx: Ctx) -> Outcome:
    box = plugin_project(ctx, ctx.case.id)
    runtime_module, state, kit = _critique_state(ctx, box)
    direction = kit["direction"]
    g1d, _reason = runtime_module.POLICY.gate_satisfied(
        state, "G1D", runtime_module.DESIGN.direction_subject(direction),
    )
    box.write(
        "DESIGN.md",
        "# DESIGN\n\n**Status:** locked at G1 on 2026-01-01\n\n## Design thesis\n\n"
        "**Commitment is decided before price is compared.**\n\n"
        "## Signature moment\n\n- **What / where:** the toggle reorders the tiers in place\n"
        "- **Mobile equivalent:** the toggle becomes a full-width segmented control\n",
    )
    box.write("AGENTS.md", "## Current state\n\n| **Stage** | `S3` |\n| **Last gate passed** | `none` |\n")
    g1_problems = runtime_module.POLICY.g1_problems(state, box.project)
    g1d_after_g1_shape = runtime_module.POLICY.gate_satisfied(
        state, "G1D", runtime_module.CONTRACTS.Subject(
            "design-direction-record", "ddr_other", "d" * 64,
        ),
    )
    problems = []
    if not g1d:
        problems.append("G1D was not satisfied by its own approval")
    if not g1_problems:
        problems.append("a G1D approval satisfied or bypassed the G1 gate")
    if g1d_after_g1_shape[0]:
        problems.append("G1D was satisfied by a subject it does not bind")
    gates = {record.get("gate") for record in state.get("approvals") or []}
    if gates != {"G1D"}:
        problems.append(f"recorded gates={sorted(gates)}")
    return Outcome(
        status="pass" if not problems else "fail",
        actual=f"g1d={g1d} g1_blocked={bool(g1_problems)} approvals={sorted(gates)}",
        evidence={"g1_problems": g1_problems, "gates": sorted(gates), "problems": problems},
    )


@case(
    id="design-invariants.only-the-human-channel-approves",
    group="design-invariants",
    title="A non-human channel cannot approve a design direction",
    task="Attempt a direction approval on the worker channel.",
    expectation="The approval is refused and nothing is recorded.",
    evaluation="Attempt the approval with channel=worker-cli and read the refusal.",
    evidence_required="The refusal and the empty approval list.",
    layer="deterministic",
)
def invariants_channel(ctx: Ctx) -> Outcome:
    box = plugin_project(ctx, ctx.case.id)
    runtime_module = runtime(ctx)
    state = plugin_state(box, ctx)
    direction = runtime_module.DESIGN.create_direction(
        state, task_id="bench-S4B", goal="commitment before price", scope="src/pages/pricing.tsx",
        product_context=["self-serve SaaS"], key_hierarchy=["plan choice precedes the tiers"],
        interaction_principles=["the toggle sits above the tier row"],
        visual_principles=["one accent colour carries the action"],
        content_principles=["each tier states its audience first"],
        constraints=["no new dependency"], existing_system=["existing type scale"],
        reference_findings_adopted=["no reference findings were adopted: reference research was not required"],
        findings_rejected=["a full-width comparison table"],
        accessibility_requirements=["the toggle is keyboard operable"],
        responsive_requirements=["the tiers stack below 768px"],
        approved_deviations=["no deviation from the existing system is approved for this task"],
    )
    refusal = ""
    try:
        runtime_module.DESIGN.approve_direction(
            state, direction["direction_id"], identity="a-worker", channel="worker-cli",
        )
    except Exception as exc:
        refusal = str(exc)
    problems = []
    if not refusal:
        problems.append("a worker channel recorded an approval")
    if "human-cli" not in refusal:
        problems.append(f"the refusal did not name the only channel: {refusal!r}")
    if state.get("approvals"):
        problems.append("an approval was recorded for the refused channel")
    if direction["status"] != "candidate":
        problems.append(f"the direction status changed to {direction['status']}")
    return Outcome(
        status="pass" if not problems else "fail",
        actual=f"refused={bool(refusal)} approvals={len(state.get('approvals') or [])}",
        evidence={"refusal": refusal, "problems": problems},
    )


@case(
    id="design-invariants.component-research-cannot-install",
    group="design-invariants",
    title="Component research cannot install or change the project",
    task="Evaluate a new dependency and inspect the module for any installation path.",
    expectation="No dependency is installed, no project file changes, and the module imports no process launcher.",
    evaluation="Run the evaluation, compare the project before and after, and inspect the module source.",
    evidence_required="The before/after file set, the install authority string and the module imports.",
    layer="deterministic",
)
def invariants_component_no_install(ctx: Ctx) -> Outcome:
    box = plugin_project(ctx, ctx.case.id)
    runtime_module = runtime(ctx)
    state = plugin_state(box, ctx)
    box.write("package.json", json.dumps({"dependencies": {"react": "^18.0.0"}}))
    before = sorted(str(path.relative_to(box.project)) for path in box.project.rglob("*") if path.is_file())
    before_package = box.read("package.json")
    record = runtime_module.COMPONENTS.evaluate(
        state, need="a date range picker", task_id="bench-S4B",
        rung="new-external-dependency", name="date-range-kit",
        alternatives=[{"name": "hand-rolled range input", "reason": "loses the built-in accessibility work"}],
        existing_equivalent={"checked": True, "reason": "no range control exists in this project"},
        findings={
            "project_compatibility": {"verdict": "verified", "detail": "peer range matches"},
            "framework_compatibility": {"verdict": "verified", "detail": "same framework major"},
            "licence": {"verdict": "verified", "detail": "MIT"},
        },
        registry_entry="shadcn-ui",
    )
    after = sorted(str(path.relative_to(box.project)) for path in box.project.rglob("*") if path.is_file())
    source = (ctx.repo.script("ariadne.py")).read_text(encoding="utf-8")
    engine_source = (ctx.repo.root / "src" / "ariadne_engine" / "components.py").read_text(encoding="utf-8")
    problems = []
    if before != after:
        problems.append(f"the project file set changed: {sorted(set(after) ^ set(before))}")
    if box.read("package.json") != before_package:
        problems.append("package.json changed during a component evaluation")
    if record["install_authority"] != "none — human G2 required":
        problems.append(f"install_authority={record['install_authority']!r}")
    for needle in ("subprocess", "os.system", "pip ", "npm install", "urlopen", "requests."):
        if needle in engine_source:
            problems.append(f"the component module references {needle!r}")
    if "install" in engine_source and "human G2 required" not in engine_source:
        problems.append("the component module does not state the human-only install authority")
    return Outcome(
        status="pass" if not problems else "fail",
        actual=f"files_unchanged={before == after} install_authority={record['install_authority']!r}",
        evidence={"record": record, "problems": problems,
                  "engine_module_chars": len(engine_source)},
    )


@case(
    id="design-invariants.source-suggestion-is-not-rendered-quality",
    group="design-invariants",
    title="Source inspection can never prove rendered quality",
    task="Record a source suggestion and compare its strength with rendered and observed evidence.",
    expectation="A source suggestion is the weakest state and cannot satisfy a rendered threshold.",
    evaluation="Record a source suggestion and compare ordinal strengths.",
    evidence_required="The recorded state and the strengths.",
    layer="deterministic",
)
def invariants_source_is_weakest(ctx: Ctx) -> Outcome:
    box = plugin_project(ctx, ctx.case.id)
    runtime_module, state, _evidence, revision = _closure_state(ctx, box)
    source = box.write("src/styles/landing.css", ".cta { position: sticky; bottom: 0; }\n")
    suggestion = runtime_module.RENDER.record_source_suggests(
        state, task_id="bench-S4B", revision_hash=revision, source_path=source,
        source_anchor="position: sticky", observation="the CTA is declared sticky",
    )
    strengths = {
        "source": runtime_module.RENDER.strength("SOURCE_SUGGESTS"),
        "rendered": runtime_module.RENDER.strength("RENDERED"),
        "observed": runtime_module.RENDER.strength("OBSERVED"),
        "verified": runtime_module.RENDER.strength("VERIFIED"),
        "unverified": runtime_module.RENDER.strength("UNVERIFIED"),
    }
    problems = []
    if suggestion["state"] != "SOURCE_SUGGESTS":
        problems.append(f"state={suggestion['state']}")
    if not strengths["source"] < strengths["rendered"] < strengths["observed"] < strengths["verified"]:
        problems.append(f"strengths are not ordered: {strengths}")
    if strengths["unverified"] >= strengths["source"]:
        problems.append("unverified evidence is not distinguished from a source claim")
    return Outcome(
        status="pass" if not problems else "fail",
        actual=f"state={suggestion['state']} strengths_ordered={not problems}",
        evidence={"strengths": strengths, "problems": problems},
    )


@case(
    id="design-invariants.events-join-the-canonical-chain",
    group="design-invariants",
    title="Design events join the canonical chain and never weaken it",
    task="Run design-plan and record one reference, then verify the engine event log.",
    expectation="Design events are present, the digest chain verifies, and the new types are declared.",
    evaluation="Read the event log, its integrity check and the declared vocabulary.",
    evidence_required="The event type counts, the integrity report and the log path.",
    layer="deterministic",
)
def invariants_events_chain(ctx: Ctx) -> Outcome:
    box = started_box(ctx, ctx.case.id, "build a new landing page and research reference sites")
    plan_input = design_input(box, capture=rendered_fixture(box))
    planned = ctx.repo.cli("design-plan", "--run-root", str(box.run_root), "--input", str(plan_input))
    reference = box.write("design/references/rival.md", "# Rival\n\nThree tiers.\n")
    recorded = record_events(ctx, box, [{
        "type": "reference", "source": "rival", "locator": str(reference), "title": "rival page",
        "source_type": "local-file", "adapter": "local-reference",
    }])
    runtime_module = runtime(ctx)
    run_root = box.run_root
    events = runtime_module.EVENTS.read(run_root)
    integrity = runtime_module.EVENTS.integrity_problems(run_root)
    types = sorted({str(event.get("type")) for event in events})
    declared = set(runtime_module.EVENTS.EVENT_TYPES)
    problems = []
    if not planned.ok:
        problems.append(f"design-plan failed: {planned.tail(3)}")
    if not recorded.ok:
        problems.append(f"the reference event failed: {recorded.tail(3)}")
    if integrity:
        problems.append(f"event chain problems: {integrity}")
    for expected in ("design_task_characterized", "design_plan_selected", "reference_found"):
        if expected not in types:
            problems.append(f"missing design event: {expected}")
    if not {"design_task_characterized", "reference_found"} <= declared:
        problems.append("the design event vocabulary is not declared")
    telemetry = box.telemetry()
    if not telemetry:
        problems.append("the legacy telemetry projection received nothing")
    return Outcome(
        status="pass" if not problems else "fail",
        actual=f"events={len(events)} design_types={[item for item in types if 'reference' in item or 'design' in item]}",
        evidence={"types": types, "integrity": integrity, "problems": problems},
        metrics={"events": len(events)},
    )


@case(
    id="design-invariants.context-isolation-preserved",
    group="design-invariants",
    title="Design context stays role- and task-specific",
    task="Decide context for a design source with and without a design requirement, and for a forbidden source.",
    expectation="A design source is omitted when the task needs no design work, never resurrected when forbidden, and included when required.",
    evaluation="Compare three context decisions: irrelevant, forbidden, required.",
    evidence_required="The three decision records with their reasons.",
    layer="deterministic",
)
def invariants_context_isolation(ctx: Ctx) -> Outcome:
    box = plugin_project(ctx, ctx.case.id)
    runtime_module = runtime(ctx)
    reference = box.write("design/references/source.md", "reference material\n")
    candidate = lambda: {
        "path": str(reference), "label": "design reference", "kind": "reference",
        "bucket": "optional", "removable": True, "exists": True, "requires": "design",
    }
    backend_state = plugin_state(box, ctx)
    backend = runtime_module.CONTEXT.decide(
        backend_state, stage="S4B", candidates=[candidate()],
        characterisation={"task_id": "bench-S4B"},
    )
    design_state = plugin_state(box, ctx)
    characterisation = runtime_module.DESIGN.characterize(
        design_state, project=box.project, stage="S4B",
        request="build a new landing page with a hero and research reference sites",
        task_id="bench-S4B", transport=runtime_module.TRANSPORT,
    )
    runtime_module.DESIGN.record_characterisation(design_state, characterisation)
    design = runtime_module.CONTEXT.decide(
        design_state, stage="S4B", candidates=[candidate()],
        characterisation={"task_id": "bench-S4B", "characterisation_id": ""},
    )
    forbidden_state = plugin_state(box, ctx)
    runtime_module.DESIGN.record_characterisation(forbidden_state, characterisation)
    forbidden_candidate = candidate()
    forbidden_candidate["forbidden"] = True
    forbidden = runtime_module.CONTEXT.decide(
        forbidden_state, stage="S4B", candidates=[forbidden_candidate],
        characterisation={"task_id": "bench-S4B"},
    )
    def entry(decision):
        return (decision.get("decisions") or [{}])[0]
    problems = []
    if entry(backend)["decision"] != "omitted" or entry(backend)["reason"] != "IRRELEVANT_TO_TASK":
        problems.append(f"backend decision={entry(backend)}")
    if entry(design)["decision"] != "included":
        problems.append(f"design decision={entry(design)}")
    if entry(forbidden)["decision"] != "omitted" or entry(forbidden)["reason"] != "FORBIDDEN_FOR_STAGE":
        problems.append(f"forbidden decision={entry(forbidden)}")
    return Outcome(
        status="pass" if not problems else "fail",
        actual=f"backend={entry(backend)['reason']} design={entry(design)['decision']} forbidden={entry(forbidden)['reason']}",
        evidence={
            "backend": entry(backend), "design": entry(design), "forbidden": entry(forbidden),
            "problems": problems,
        },
    )


@case(
    id="design-invariants.evidence-routing-never-guesses",
    group="design-invariants",
    title="A design evidence need with no declared adapter blocks the route",
    task="Route a task that requires rendered observation with no capture adapter configured.",
    expectation="The route is blocked by the design-evidence rule, and a configured adapter satisfies it.",
    evaluation="Route once with no adapters and once with the offline fixture; compare.",
    evidence_required="Both routing decisions and their rules.",
    layer="deterministic",
)
def invariants_evidence_routing(ctx: Ctx) -> Outcome:
    box = plugin_project(ctx, ctx.case.id)
    runtime_module = runtime(ctx)
    state = plugin_state(box, ctx)
    characterisation = runtime_module.DESIGN.characterize(
        state, project=box.project, stage="S4B",
        request="build a new landing page with a hero, accessible and responsive at 375 and 1280",
        task_id="bench-S4B", transport=runtime_module.TRANSPORT,
    )
    unconfigured = runtime_module.ROUTING.route_evidence(
        state, stage="S4B", design_characterisation=characterisation,
    )
    configured = runtime_module.ROUTING.route_evidence(
        state, stage="S4B", design_characterisation=characterisation,
        capture_adapters=runtime_module.RENDER.default_adapters(
            box.run_root, fixture=rendered_fixture(box),
        ),
        reference_adapters=runtime_module.REFERENCES.default_adapters(box.project),
    )
    problems = []
    if unconfigured["status"] != "blocked" or unconfigured["rule"] != "design-evidence-unavailable":
        problems.append(f"unconfigured route={unconfigured['status']}/{unconfigured['rule']}")
    if unconfigured["status"] == "blocked":
        runtime_module.ROUTING.record(state, unconfigured)
    if configured["status"] != "selected":
        problems.append(f"configured route={configured['status']}: {configured['reason']}")
    if not configured.get("needs"):
        problems.append("the route recorded no evidence needs")
    return Outcome(
        status="pass" if not problems else "fail",
        actual=f"unconfigured={unconfigured['status']} configured={configured['status']} needs={len(configured.get('needs') or [])}",
        evidence={"unconfigured": unconfigured, "configured": configured, "problems": problems},
    )


# ================================================================ measurement


@case(
    id="design-measurements.deterministic-counters",
    group="design-measurements",
    title="Design measurements are deterministic and match the records",
    task="Run a small design workflow and compare the counters with the recorded collections.",
    expectation="Counters equal the records; no design quality score is reported.",
    evaluation="Run the engine workflow and compare measure() with the state collections.",
    evidence_required="The measurement record and the state collection sizes.",
    layer="measurement",
)
def measurements_deterministic(ctx: Ctx) -> Outcome:
    box = plugin_project(ctx, ctx.case.id)
    runtime_module, state, kit, review = _refinement_state(ctx, box)
    finding_id = review["findings"][0]["finding_id"]
    record = runtime_module.CRITIQUE.propose_refinement(state, finding_id, **_proposal(kit, review))
    runtime_module.CRITIQUE.record_refinement(
        state, record["refinement_id"], applied=True,
        changed_artifacts=["src/styles/landing.css"],
        revalidated={"npm test": "42 passed"},
        recaptured=[kit["evidence"]["evidence_id"]],
    )
    runtime_module.CRITIQUE.resolve_findings(state, record["refinement_id"], resolved=[])
    measurements = runtime_module.DESIGN.measure(state)
    again = runtime_module.DESIGN.measure(state)
    problems = []
    if measurements != again:
        problems.append("two measurements of the same state differ")
    if measurements["critique"]["reviews"] != len(state.get("design_reviews") or []):
        problems.append("the review counter does not match the records")
    if measurements["refinement"]["attempts"] != len(state.get("design_refinements") or []):
        problems.append("the refinement counter does not match the records")
    if measurements["rendered_evidence"]["records"] != len(state.get("rendered_evidence") or []):
        problems.append("the rendered-evidence counter does not match the records")
    if "score" in json.dumps(measurements).lower():
        problems.append("a design score leaked into the measurements")
    return Outcome(
        status="observed",
        actual=(
            f"references={measurements['references']['records']} "
            f"evidence={measurements['rendered_evidence']['records']} "
            f"findings={measurements['critique']['findings']} "
            f"refinements={measurements['refinement']['attempts']}"
        ),
        evidence={"measurements": measurements, "problems": problems},
        metrics={
            "references": measurements["references"]["records"],
            "rendered_evidence": measurements["rendered_evidence"]["records"],
            "findings": measurements["critique"]["findings"],
            "refinement_attempts": measurements["refinement"]["attempts"],
        },
    )


# ============================================================= hardening (AR-202D-H)
#
# The cases below are the adversarial counterparts of the seven review findings
# the hardening pass closed. Each one fails if its finding is reintroduced, and
# each records the refusal and the unchanged state rather than describing them.


def _hardening_reference(runtime_module, state, box) -> dict:
    """One ANALYSED reference whose evidence is a real in-project file."""
    source = box.write("design/references/hardening.md", "# Hardening\n\nA concrete reference body.\n")
    record = runtime_module.REFERENCES.register(
        state, source="hardening", locator=str(source), title="hardening reference",
        source_type="local-file", adapter="local-reference", task_id="bench-S4B",
    )
    runtime_module.REFERENCES.mark_accessible(
        state, record["reference_id"], content_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
    )
    runtime_module.REFERENCES.inspect(
        state, record["reference_id"], inspection_type="CONTENT",
        observations=["a concrete observation"], evidence_path=source, project=box.project,
    )
    inspection = record["inspections"][0]["inspection_id"]
    runtime_module.REFERENCES.analyse(state, record["reference_id"], findings=[{
        "dimension": "hierarchy", "observation": "a concrete observation",
        "interpretation": "commitment precedes comparison", "applicability": "fits this page",
        "decision": "adopted", "mechanism": "single decision point",
        "inspection_ids": [inspection],
    }])
    return record


@case(
    id="design-hardening.traversal-escape-refused",
    group="design-hardening",
    title="Traversal, absolute and prefix-collision paths cannot become provenance",
    task="Cite usage artifacts outside the project: a sibling file, a .. traversal to it, and a sibling directory that shares the project's name prefix.",
    expectation="Every attempt is refused before anything is stored, and the reference stays ANALYSED.",
    evaluation="Attempt each citation and read the refusals and the unchanged record.",
    evidence_required="The refusal texts, the record state and the absent usage record.",
    layer="deterministic",
)
def hardening_traversal(ctx: Ctx) -> Outcome:
    box = plugin_project(ctx, ctx.case.id)
    runtime_module = runtime(ctx)
    state = plugin_state(box, ctx)
    record = _hardening_reference(runtime_module, state, box)
    outside = box.root / "outside-project.md"
    outside.write_text("outside the project root\n", encoding="utf-8")
    prefix_collision = Path(str(box.project) + "-evil") / "x.md"
    candidates = {
        "absolute sibling": outside,
        ".. traversal": box.project / ".." / "outside-project.md",
        "name-prefix sibling": prefix_collision,
    }
    refusals: dict[str, str] = {}
    for label, path in candidates.items():
        try:
            runtime_module.REFERENCES.mark_used(
                state, record["reference_id"], decision="d", principle="p",
                artifact_path=path, artifact_anchor="outside",
            )
            refusals[label] = ""
        except Exception as exc:
            refusals[label] = str(exc)
    problems = []
    for label, refusal in refusals.items():
        if not refusal:
            problems.append(f"{label} was accepted as provenance")
        elif "permitted root" not in refusal:
            problems.append(f"{label} was refused for the wrong reason: {refusal!r}")
    if record["state"] != "ANALYSED" or record.get("usage"):
        problems.append(f"the refused citations mutated the reference: {record['state']}")
    return Outcome(
        status="pass" if not problems else "fail",
        actual=f"refused={sum(1 for value in refusals.values() if value)}/3 state={record['state']}",
        evidence={"refusals": refusals, "problems": problems},
    )


@case(
    id="design-hardening.cli-traversal-escape-refused",
    group="design-hardening",
    title="The CLI ingest path refuses an out-of-project usage artifact too",
    task="Drive the full reference lifecycle through record-design, then cite a usage artifact outside the project.",
    expectation="The CLI event is refused, the reference stays ANALYSED and no usage record is written.",
    evaluation="Submit the events through the CLI and read the refusal and the persisted state.",
    evidence_required="The refusal, the exit code and the reference record.",
    layer="deterministic",
)
def hardening_cli_traversal(ctx: Ctx) -> Outcome:
    box = started_box(ctx, ctx.case.id, "build a new pricing page with a tier comparison")
    reference = box.write("design/references/rival.md", "# Rival\n\nThree tiers.\n")
    digest = hashlib.sha256(reference.read_bytes()).hexdigest()
    found = record_events(ctx, box, [{
        "type": "reference", "source": "rival", "locator": str(reference), "title": "rival pricing",
        "source_type": "local-file", "adapter": "local-reference",
    }])
    state = box.state()
    reference_id = str((state.get("design_references") or [{}])[-1].get("reference_id", ""))
    record_events(ctx, box, [{
        "type": "reference-accessible", "reference_id": reference_id, "content_sha256": digest,
    }])
    record_events(ctx, box, [{
        "type": "reference-inspection", "reference_id": reference_id, "inspection_type": "CONTENT",
        "observations": ["three tiers are shown"], "evidence_path": str(reference),
    }])
    state = box.state()
    record = (state.get("design_references") or [{}])[-1]
    inspection_id = str((record.get("inspections") or [{}])[-1].get("inspection_id", ""))
    record_events(ctx, box, [{
        "type": "reference-analysis", "reference_id": reference_id, "findings": [{
            "dimension": "hierarchy", "observation": "three tiers", "interpretation": "commitment first",
            "applicability": "fits this page", "decision": "adopted", "mechanism": "single decision point",
            "inspection_ids": [inspection_id],
        }],
    }])
    outside = box.root / "outside-project.md"
    outside.write_text("outside the project root\n", encoding="utf-8")
    used = record_events(ctx, box, [{
        "type": "reference-used", "reference_id": reference_id, "decision": "d", "principle": "p",
        "artifact_path": str(outside), "artifact_anchor": "outside",
    }])
    state = box.state()
    final = (state.get("design_references") or [{}])[-1]
    problems = []
    if found.ok is False:
        problems.append(f"the reference could not be registered: {found.tail(3)}")
    if used.ok:
        problems.append("the CLI accepted an out-of-project usage artifact")
    if "permitted root" not in used.combined:
        problems.append(f"the refusal did not name the containment rule: {used.tail(3)}")
    if str(final.get("state")) != "ANALYSED" or final.get("usage"):
        problems.append(f"the refused event mutated the persisted record: {final.get('state')}")
    return Outcome(
        status="pass" if not problems else "fail",
        actual=f"refused={not used.ok} state={final.get('state')}",
        evidence={"refusal_tail": used.tail(4), "problems": problems},
    )


@case(
    id="design-hardening.refused-operation-leaves-state-unchanged",
    group="design-hardening",
    title="A refused operation leaves the reference byte-identical",
    task="Attempt an illegal lifecycle move, a re-retrieval, a late inaccessible move, an analysis citing a missing inspection, and an unanchored usage.",
    expectation="Each refusal leaves the record exactly as it was; nothing partial is written.",
    evaluation="Snapshot the record, attempt each refusal, and compare the snapshot.",
    evidence_required="The snapshots and the refusals.",
    layer="deterministic",
)
def hardening_refusal_immutable(ctx: Ctx) -> Outcome:
    box = plugin_project(ctx, ctx.case.id)
    runtime_module = runtime(ctx)
    state = plugin_state(box, ctx)
    source = box.write("design/references/immutable.md", "# Ref\n\nA body.\n")
    record = runtime_module.REFERENCES.register(
        state, source="immutable", locator=str(source), title="immutable reference",
        source_type="local-file", adapter="local-reference", task_id="bench-S4B",
    )
    snapshots: list[tuple[str, str, str]] = []
    refusals: dict[str, str] = {}

    def attempt(label: str, action) -> None:
        before = json.dumps(record, sort_keys=True)
        try:
            action()
            snapshots.append((label, before, json.dumps(record, sort_keys=True)))
        except Exception as exc:
            refusals[label] = str(exc)
            snapshots.append((label, before, json.dumps(record, sort_keys=True)))

    attempt("FOUND -> INSPECTED", lambda: runtime_module.REFERENCES.inspect(
        state, record["reference_id"], inspection_type="CONTENT",
        observations=["o"], evidence_path=source, project=box.project,
    ))
    runtime_module.REFERENCES.mark_accessible(
        state, record["reference_id"], content_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
    )
    runtime_module.REFERENCES.inspect(
        state, record["reference_id"], inspection_type="CONTENT",
        observations=["a concrete observation"], evidence_path=source, project=box.project,
    )
    attempt("re-retrieval", lambda: runtime_module.REFERENCES.mark_accessible(
        state, record["reference_id"], content_sha256="b" * 64,
    ))
    attempt("INSPECTED -> INACCESSIBLE", lambda: runtime_module.REFERENCES.mark_inaccessible(
        state, record["reference_id"], blocker="not really",
    ))
    attempt("analysis with a missing inspection", lambda: runtime_module.REFERENCES.analyse(
        state, record["reference_id"], findings=[{
            "dimension": "hierarchy", "observation": "o", "interpretation": "i", "applicability": "a",
            "decision": "adopted", "mechanism": "m",
            "inspection_ids": ["ins_20260101T000000Z_deadbeef"],
        }],
    ))
    runtime_module.REFERENCES.analyse(state, record["reference_id"], findings=[{
        "dimension": "hierarchy", "observation": "a concrete observation",
        "interpretation": "commitment precedes comparison", "applicability": "fits this page",
        "decision": "adopted", "mechanism": "single decision point",
        "inspection_ids": [record["inspections"][0]["inspection_id"]],
    }])
    attempt("usage with a wrong anchor", lambda: runtime_module.REFERENCES.mark_used(
        state, record["reference_id"], decision="d", principle="p",
        artifact_path=box.project / "HANDOFF.md", artifact_anchor="no such anchor",
    ))
    problems = []
    if len(refusals) != 5:
        problems.append(f"expected 5 refusals, recorded {sorted(refusals)}")
    for label, before, after in snapshots:
        if before != after:
            problems.append(f"{label} mutated the record")
    if record["state"] != "ANALYSED" or record.get("usage") is not None or record.get("blocker"):
        problems.append(f"final record is not the untouched ANALYSED state: {record['state']}")
    return Outcome(
        status="pass" if not problems else "fail",
        actual=f"refusals={len(refusals)} unchanged={sum(1 for _, b, a in snapshots if b == a)}/{len(snapshots)}",
        evidence={"refusals": refusals, "problems": problems},
    )


@case(
    id="design-hardening.missing-direction-section-refused",
    group="design-hardening",
    title="A direction missing a required section is refused",
    task="Record a direction event that omits findings_rejected entirely.",
    expectation="The event is refused and no direction record is written.",
    evaluation="Submit the event through the CLI and read the refusal and the empty collection.",
    evidence_required="The refusal text and the absent record.",
    layer="deterministic",
)
def hardening_direction_missing(ctx: Ctx) -> Outcome:
    box = started_box(ctx, ctx.case.id, "build a new pricing page with a tier comparison")
    incomplete = {key: value for key, value in DIRECTION_EVENT.items() if key != "findings_rejected"}
    result = record_events(ctx, box, [incomplete])
    state = box.state()
    refusal = result.combined
    problems = []
    if result.ok:
        problems.append("a direction missing findings_rejected was accepted")
    if "findings_rejected" not in refusal:
        problems.append(f"the refusal did not name the missing section: {refusal[-200:]!r}")
    if state.get("design_directions"):
        problems.append("a direction record was written for a refused event")
    return Outcome(
        status="pass" if not problems else "fail",
        actual=f"refused={not result.ok} records={len(state.get('design_directions') or [])}",
        evidence={"refusal_tail": result.tail(4), "problems": problems},
    )


@case(
    id="design-hardening.empty-direction-section-refused",
    group="design-hardening",
    title="A direction with an empty required section is refused",
    task="Record a direction whose approved_deviations and reference_findings_adopted sections are present but empty.",
    expectation="Both variants are refused and no direction record is written.",
    evaluation="Submit each event through the CLI and read the refusals.",
    evidence_required="The refusal texts and the empty collection.",
    layer="deterministic",
)
def hardening_direction_empty(ctx: Ctx) -> Outcome:
    box = started_box(ctx, ctx.case.id, "build a new pricing page with a tier comparison")
    refusals: dict[str, str] = {}
    for name in ("approved_deviations", "reference_findings_adopted", "existing_system"):
        empty = dict(DIRECTION_EVENT)
        empty[name] = []
        result = record_events(ctx, box, [empty])
        refusals[name] = result.combined
        if result.ok:
            break
    state = box.state()
    problems = []
    for name, text in refusals.items():
        if name not in text:
            problems.append(f"the refusal for {name} did not name the section")
    if state.get("design_directions"):
        problems.append("a direction record was written for a refused event")
    return Outcome(
        status="pass" if not problems else "fail",
        actual=f"sections_refused={sorted(refusals)} records={len(state.get('design_directions') or [])}",
        evidence={"refusals": {name: text[-200:] for name, text in refusals.items()}, "problems": problems},
    )


@case(
    id="design-hardening.near-match-scope-refused",
    group="design-hardening",
    title="A near-match artifact cannot inherit a refinement's scope",
    task="Propose a refinement scoped to the substring 'styles', then report a change to srcx/styles/landing.css.",
    expectation="The near-match is refused as out of scope and the refinement stays proposed; the old substring rule accepted this pair.",
    evaluation="Attempt the out-of-scope close and read the refusal and the unchanged record.",
    evidence_required="The refusal, the state and the scope comparison.",
    layer="deterministic",
)
def hardening_scope_near_match(ctx: Ctx) -> Outcome:
    box = plugin_project(ctx, ctx.case.id)
    runtime_module, state, kit, review = _refinement_state(ctx, box)
    finding_id = review["findings"][0]["finding_id"]
    record = runtime_module.CRITIQUE.propose_refinement(
        state, finding_id, **_proposal(kit, review, permitted_scope=["styles"]),
    )
    refusal = ""
    try:
        runtime_module.CRITIQUE.record_refinement(
            state, record["refinement_id"], applied=True,
            changed_artifacts=["srcx/styles/landing.css"],
            recaptured=[kit["evidence"]["evidence_id"]],
        )
    except Exception as exc:
        refusal = str(exc)
    problems = []
    if "outside its permitted scope" not in refusal:
        problems.append(f"the near-match was not refused as out of scope: {refusal!r}")
    if record["state"] != "proposed":
        problems.append(f"the refused close changed the refinement to {record['state']}")
    return Outcome(
        status="pass" if not problems else "fail",
        actual=f"refused={bool(refusal)} state={record['state']}",
        evidence={"refusal": refusal, "problems": problems},
    )


@case(
    id="design-hardening.exact-scope-accepted",
    group="design-hardening",
    title="An in-scope artifact still closes a refinement",
    task="Close the same refinement with the src/styles/** vocabulary and its re-taken evidence.",
    expectation="The glob-scoped artifact is accepted and the refinement closes as verified.",
    evaluation="Close the refinement and read the state and the recorded change.",
    evidence_required="The refinement record and its state.",
    layer="deterministic",
)
def hardening_scope_exact(ctx: Ctx) -> Outcome:
    box = plugin_project(ctx, ctx.case.id)
    runtime_module, state, kit, review = _refinement_state(ctx, box)
    finding_id = review["findings"][0]["finding_id"]
    record = runtime_module.CRITIQUE.propose_refinement(
        state, finding_id, **_proposal(kit, review, permitted_scope=["src/styles/**"]),
    )
    runtime_module.CRITIQUE.record_refinement(
        state, record["refinement_id"], applied=True,
        changed_artifacts=["src/styles/landing.css"],
        recaptured=[kit["evidence"]["evidence_id"]],
        revalidated={"npm test": "42 passed"},
    )
    problems = []
    if record["state"] != "verified":
        problems.append(f"the in-scope refinement closed as {record['state']}")
    if record.get("changed_artifacts") != ["src/styles/landing.css"]:
        problems.append(f"changed artifacts were not recorded: {record.get('changed_artifacts')}")
    return Outcome(
        status="pass" if not problems else "fail",
        actual=f"state={record['state']} changed={record.get('changed_artifacts')}",
        evidence={"record": record, "problems": problems},
    )


@case(
    id="design-hardening.excluded-tree-omitted",
    group="design-hardening",
    title="Dependency, build and VCS trees are never scanned",
    task="Give a project a design token in src and a large fake design system under node_modules and .git.",
    expectation="Only the project's own stylesheet contributes design-system evidence.",
    evaluation="Characterise the project and read the maturity evidence.",
    evidence_required="The maturity evidence text and the scan bound note.",
    layer="deterministic",
)
def hardening_excluded_tree(ctx: Ctx) -> Outcome:
    box = plugin_project(ctx, ctx.case.id)
    box.write("src/styles/app.css", ":root { --brand: #111; }\n")
    box.write(
        "node_modules/pkg/dependency.css",
        ":root {" + "".join(f"--dep-{index}: {index};" for index in range(30)) + "}\n",
    )
    box.write(".git/runtime.css", ":root { --vcs: 1; }\n")
    box.write("NODE_MODULES/upper.css", ":root { --upper: 1; }\n")
    record = characterise(ctx, box, "build a new landing page with a hero")
    maturity = record["characteristics"]["design_system_maturity"]
    text = " ".join(maturity["evidence"])
    problems = []
    if "across 1 stylesheet" not in text:
        problems.append(f"dependency or VCS stylesheets were counted: {text!r}")
    if "1 CSS custom property" not in text:
        problems.append(f"the project's own stylesheet was not the only contributor: {text!r}")
    return Outcome(
        status="pass" if not problems else "fail",
        actual=f"value={maturity['value']} evidence={len(maturity['evidence'])}",
        evidence={"maturity": maturity, "problems": problems},
    )


@case(
    id="design-hardening.oversized-collection-refused",
    group="design-hardening",
    title="An oversized authoritative collection is refused, never truncated",
    task="Pre-fill the reference collection to its safety bound and register one more reference.",
    expectation="The registration is refused with an explicit bound error and nothing is truncated.",
    evaluation="Attempt the registration and compare the collection length.",
    evidence_required="The refusal text and the unchanged length.",
    layer="deterministic",
)
def hardening_oversized_collection(ctx: Ctx) -> Outcome:
    box = plugin_project(ctx, ctx.case.id)
    runtime_module = runtime(ctx)
    state = plugin_state(box, ctx)
    bound = runtime_module.CONTRACTS.MAX_DESIGN_RECORDS
    state["design_references"] = [
        {"reference_id": f"ref_{index:08d}"} for index in range(bound)
    ]
    source = box.write("design/references/one-more.md", "# One more\n")
    refusal = ""
    try:
        runtime_module.REFERENCES.register(
            state, source="one more", locator=str(source), title="one more",
            source_type="local-file", adapter="local-reference",
        )
    except Exception as exc:
        refusal = str(exc)
    problems = []
    if "safety bound" not in refusal:
        problems.append(f"the oversized collection was not refused with a bound: {refusal!r}")
    if len(state["design_references"]) != bound:
        problems.append(f"the collection was truncated to {len(state['design_references'])}")
    return Outcome(
        status="pass" if not problems else "fail",
        actual=f"refused={bool(refusal)} records={len(state['design_references'])}",
        evidence={"refusal": refusal, "bound": bound, "problems": problems},
    )


@case(
    id="design-hardening.normal-collection-accepted",
    group="design-hardening",
    title="A normal collection is unaffected by the bound",
    task="Register and inspect one reference in an ordinary run.",
    expectation="The record is accepted and the bound is not reached.",
    evaluation="Register the reference and read its state and the collection length.",
    evidence_required="The reference record and the collection size.",
    layer="deterministic",
)
def hardening_normal_collection(ctx: Ctx) -> Outcome:
    box = plugin_project(ctx, ctx.case.id)
    runtime_module = runtime(ctx)
    state = plugin_state(box, ctx)
    record = _hardening_reference(runtime_module, state, box)
    problems = []
    if record["state"] != "ANALYSED":
        problems.append(f"a normal reference did not reach ANALYSED: {record['state']}")
    if len(state["design_references"]) != 1:
        problems.append(f"unexpected collection size: {len(state['design_references'])}")
    return Outcome(
        status="pass" if not problems else "fail",
        actual=f"state={record['state']} records={len(state['design_references'])}",
        evidence={"reference": record, "problems": problems},
    )


@case(
    id="design-hardening.capability-vocabulary-enforced",
    group="design-hardening",
    title="The capability vocabulary is consulted, not decorative",
    task="Check the vocabulary is consistent, then route with a table entry that names an undeclared capability.",
    expectation="The consistent vocabulary routes; the inconsistent one is refused before a decision is made.",
    evaluation="Call the vocabulary check, then inject an undeclared capability and route.",
    evidence_required="The vocabulary problems and the routing refusal.",
    layer="deterministic",
)
def hardening_capability_vocabulary(ctx: Ctx) -> Outcome:
    box = plugin_project(ctx, ctx.case.id)
    runtime_module = runtime(ctx)
    state = plugin_state(box, ctx)
    problems = list(runtime_module.ROUTING.evidence_vocabulary_problems())
    characterisation = characterise(ctx, box, "build a new landing page with a hero and research references")
    table = runtime_module.ROUTING.DESIGN_EVIDENCE_REQUIREMENTS
    injected = dict(table)
    injected["undeclared-capability-need"] = (("reference_research", "not-a-declared-capability"),)
    runtime_module.ROUTING.DESIGN_EVIDENCE_REQUIREMENTS = injected
    refusal = ""
    try:
        runtime_module.ROUTING.route_evidence(
            state, stage="S4B", design_characterisation=characterisation, task_id="bench-S4B",
        )
    except Exception as exc:
        refusal = str(exc)
    finally:
        runtime_module.ROUTING.DESIGN_EVIDENCE_REQUIREMENTS = table
    if "not-a-declared-capability" not in refusal:
        problems.append(f"an undeclared capability was not refused: {refusal!r}")
    return Outcome(
        status="pass" if not problems else "fail",
        actual=f"vocabulary_clean=True undeclared_refused={bool(refusal)}",
        evidence={"refusal": refusal, "problems": problems},
    )


@case(
    id="design-hardening.previous-fixes-still-hold",
    group="design-hardening",
    title="The seven previously fixed review issues remain fixed",
    task="Re-attempt: declared-observer verification, a fabricated component approval, an empty usage anchor, and an empty expected-evidence list.",
    expectation="All four are refused: none can be elevated by assertion.",
    evaluation="Attempt each bypass and read the refusals and the unchanged records.",
    evidence_required="The four refusals and the unchanged evidence state.",
    layer="deterministic",
)
def hardening_previous_fixes(ctx: Ctx) -> Outcome:
    box = plugin_project(ctx, ctx.case.id)
    runtime_module, state, evidence, revision = _closure_state(ctx, box)
    shot = box.write("design/observer/home.png", "\x89PNG-declared\n")
    observer = runtime_module.RENDER.DeclaredObserverAdapter(
        method="operator recorded this with their own browser",
        environment={"browser": "operator's browser"},
    )
    artifact = observer.capture({
        "path": str(shot), "kind": "screenshot", "viewport": {"width": 375}, "observation": "",
    })
    declared = runtime_module.RENDER.record(
        state, task_id="bench-S4B", revision_hash=revision, artifact=artifact,
        adapter="declared-observer",
    )
    verifier = runtime_module.EXECUTION.create(
        state, task_id="bench-S4B", role="validator",
        adapter="scripts/ariadne.py:design-verify:declared-observer",
        revision={"revision_hash": revision},
    )
    verify_refusal = ""
    try:
        runtime_module.RENDER.verify(
            state, declared["evidence_id"],
            verification_execution=str(verifier["execution_id"]),
            reproduced_sha256=artifact.sha256, method="independent re-capture",
        )
    except Exception as exc:
        verify_refusal = str(exc)

    component = runtime_module.COMPONENTS.evaluate(
        plugin_state(box, ctx), need="a date range picker", task_id="bench-S4B",
        rung="new-external-dependency", name="range-kit",
        alternatives=[{"name": "hand-rolled", "reason": "loses built-in accessibility"}],
        existing_equivalent={"checked": True, "reason": "no range control exists"},
        findings={
            "project_compatibility": {"verdict": "verified", "detail": "peers match"},
            "framework_compatibility": {"verdict": "verified", "detail": "same major"},
            "licence": {"verdict": "verified", "detail": "MIT"},
        },
        registry_entry="shadcn-ui", approval_id="apv_20260101T000000Z_00000000",
    )

    reference_state = plugin_state(box, ctx)
    record = _hardening_reference(runtime_module, reference_state, box)
    anchor_refusal = ""
    try:
        runtime_module.REFERENCES.mark_used(
            reference_state, record["reference_id"], decision="d", principle="p",
            artifact_path=box.project / "HANDOFF.md", artifact_anchor="",
        )
    except Exception as exc:
        anchor_refusal = str(exc)

    scope_state = plugin_state(box, ctx)
    scope_state["design_reviews"] = [{
        "review_id": "dsr_20260101T000000Z_00000000",
        "findings": [{
            "finding_id": "dfn_20260101T000000Z_00000000", "dimension": "spacing",
            "severity": "minor", "state": "open",
        }],
    }]
    evidence_refusal = ""
    try:
        runtime_module.CRITIQUE.propose_refinement(
            scope_state, "dfn_20260101T000000Z_00000000", task_id="bench-S4B",
            artifact="src/styles/landing.css", intended_change="align the gap",
            permitted_scope=["src/styles/landing.css"], expected_evidence=[],
            regression_checks=["npm test"],
        )
    except Exception as exc:
        evidence_refusal = str(exc)

    problems = []
    if not verify_refusal:
        problems.append("declared-observer evidence reached VERIFIED")
    if component["decision"] != "blocked":
        problems.append(f"a fabricated approval id selected the component: {component['decision']}")
    if not anchor_refusal:
        problems.append("an empty usage anchor was accepted")
    if not evidence_refusal:
        problems.append("a refinement with no expected evidence was accepted")
    if declared["state"] != "RENDERED":
        problems.append(f"the declared evidence state changed: {declared['state']}")
    return Outcome(
        status="pass" if not problems else "fail",
        actual=(
            f"declared_verify_refused={bool(verify_refusal)} component={component['decision']} "
            f"anchor_refused={bool(anchor_refusal)} expected_evidence_refused={bool(evidence_refusal)}"
        ),
        evidence={
            "verify_refusal": verify_refusal, "anchor_refusal": anchor_refusal,
            "evidence_refusal": evidence_refusal, "component_decision": component["decision"],
            "problems": problems,
        },
    )
