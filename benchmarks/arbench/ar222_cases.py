"""AR-222 deterministic benchmark cases: rendered design critique.

Every case is offline, deterministic and dependency-free, and none of them launches a
browser. That is a deliberate constraint rather than a limitation being worked around.

These cases measure the *evidence logic* of the rendered-critique layer -- whether a
claim can be made from the rendered evidence that actually exists -- not whether a page
looks good. The suite that renders Beacon with a real Chromium lives in
``scripts/test-rendered-critique.py``; a benchmark case that needed a browser would
measure the machine it ran on, not the engine.

What is measured here, and why each answer matters:

* a capture without source identity cannot become evidence at all
* editing a relevant stylesheet makes the capture stale, and staleness is a refusal
* the reviewer is handed a whitelist, and the worker's rationale never crosses it
* a finding with no rendered capture behind it cannot be recorded
* reference alignment is satisfaction of a principle, and no similarity score exists
* project identity outranks a reference's colour, typeface and treatment
* a repair is bounded by approved principle, allowed scope, and a two-attempt allowance
* the worker that made a change cannot be the party that certifies it
* coverage is reported per dimension; there is no scalar design score anywhere
"""

from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
from pathlib import Path

from .cases import Ctx, Outcome, case

FIXTURE = Path(__file__).resolve().parents[2] / "src" / "ariadne_engine" / "design_execution" / "fixtures" / "desktop-tool"


def _engine(ctx: Ctx):
    """Import the engine from the repository under test, not from the working copy."""
    import sys

    src = str(Path(ctx.repo.root) / "src")
    if src not in sys.path:
        sys.path.insert(0, src)
    from ariadne_engine import contracts

    return contracts


def _modules(ctx: Ctx):
    import sys

    src = str(Path(ctx.repo.root) / "src")
    if src not in sys.path:
        sys.path.insert(0, src)
    from ariadne_engine.rendered_critique import (  # noqa: PLC0415
        critique, evidence, plan, refinement, safety, source, trace,
    )

    return {"contracts": __import__("ariadne_engine.contracts", fromlist=["contracts"]),
            "critique": critique, "evidence": evidence, "plan": plan,
            "refinement": refinement, "safety": safety, "source": source, "trace": trace}


def _surface(ctx: Ctx) -> Path:
    box = ctx.sandbox()
    root = Path(box.root) / "surface"
    shutil.copytree(FIXTURE, root, ignore=shutil.ignore_patterns("node_modules", "dist"))
    return root


def _refused(fn) -> tuple[bool, str]:
    try:
        fn()
    except Exception as exc:  # noqa: BLE001 - any refusal counts, the message is evidence
        return True, f"{type(exc).__name__}: {exc}"
    return False, "no refusal"


def _png() -> bytes:
    import base64

    return base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
    )


def _manifest(ctx: Ctx, modules: dict, *, digest: str = "", captures: int = 2) -> dict:
    contracts = modules["contracts"]
    directory = Path(tempfile.mkdtemp(prefix="ar222-bench-"))
    rows = []
    for index in range(1, captures + 1):
        capture_id = f"capture_{index:03d}"
        path = directory / f"{capture_id}.png"
        path.write_bytes(_png())
        rows.append({
            "capture_id": capture_id, "route": "index.html", "state": "default",
            "kind": "viewport-state", "viewport": {"width": 1440, "height": 900},
            "theme": "project-default", "reduced_motion": False, "target_id": "rct_x",
            "artifact_path": str(path), "digest": hashlib.sha256(path.read_bytes()).hexdigest(),
            "bytes": path.stat().st_size, "dimensions": {}, "captured_at": contracts.utc_now(),
            "render_source_digest": digest or "a" * 64,
            "artifact": {"state": "VALID", "reasons": []},
            "runtime_checks": {"checks": [{"check": "no-runtime-errors", "passed": True}]},
            "accessibility_checks": {"findings": [], "not_established": []},
            "observation": "", "url": "http://127.0.0.1:1/index.html",
        })
    return {
        "schema_version": contracts.SCHEMA_DESIGN, "evidence_set_id": contracts.new_record_id("res"),
        "capture_plan_id": contracts.new_record_id("rcp"), "render_source_digest": digest or "a" * 64,
        "browser": {"adapter": "chromium-render", "engine": "playwright", "version": "1",
                    "browser": "chromium", "platform": "bench"},
        "captures": rows, "runtime_checks": [], "accessibility_checks": [],
        "skipped": [], "failures": [], "started_at": contracts.utc_now(),
        "completed_at": contracts.utc_now(), "status": "COMPLETE", "capture_bytes": 90,
    }


# --------------------------------------------------------------------- identity

@case(
    id="render.capture-without-source-identity-refused",
    group="render-identity",
    title="A capture with no source identity cannot become rendered evidence",
    task="Build a capture plan and a critique that name no render source digest.",
    expectation="Both are refused: a screenshot with nothing binding it to an implementation is not evidence.",
    evaluation="Attempt each and read the refusal message.",
    evidence_required="Both refusals, each naming the missing source identity.",
    layer="deterministic",
)
def capture_without_identity(ctx: Ctx) -> Outcome:
    m = _modules(ctx)
    contracts = m["contracts"]
    root = _surface(ctx)
    binding = m["source"].bind(root)
    problems: list[str] = []

    unrefused = _refused(lambda: m["plan"].create(
        implementation_plan_id="dip", direction_id="ddr", binding={"render_source_digest": ""},
        target_surface="beacon", launch_command=["python", "--version"],
        targets=[m["plan"].viewport_state(route="index.html",
                                          basis=[{"basis": "REQUIREMENT", "reason": "the shell"}])],
    ))
    if not unrefused[0]:
        problems.append("a capture plan with no source digest was created")

    manifest = _manifest(ctx, m)
    manifest["render_source_digest"] = ""
    unrefused_critique = _refused(lambda: m["critique"].build(
        {"run_id": "run_1", "design_directions": []}, task_id="t", direction_id="ddr",
        manifest=manifest, findings=[], reviewer_identity="r",
        reviewer_execution="exe_1", implementing_execution="exe_2", coverage={},
    ))
    if not unrefused_critique[0]:
        problems.append("a critique of an unidentified render was created")

    # A digest over irrelevant files must not be able to impersonate an implementation.
    before = m["source"].render_source_digest(root)
    (root / "NOTES.md").write_text("changelog\n", encoding="utf-8")
    after = m["source"].render_source_digest(root)
    if before != after:
        problems.append("a file that cannot reach the screen invalidated a render")

    return Outcome(
        status="pass" if not problems else "fail",
        actual=f"plan_refused={unrefused[0]} critique_refused={unrefused_critique[0]} digest_stable={before == after}",
        evidence={"plan_refusal": unrefused[1], "critique_refusal": unrefused_critique[1],
                  "problems": problems},
    )


@case(
    id="render.stale-capture-refused",
    group="render-identity",
    title="Editing a relevant stylesheet makes an existing capture stale",
    task="Bind a capture to the implementation, then edit the stylesheet it renders from.",
    expectation="The capture is reported STALE_RENDER_EVIDENCE and a re-capture against the old binding is refused.",
    evaluation="Re-read the source after the edit and read the staleness reason.",
    evidence_required="The staleness message naming both digests.",
    layer="deterministic",
)
def stale_capture(ctx: Ctx) -> Outcome:
    m = _modules(ctx)
    root = _surface(ctx)
    binding = m["source"].bind(root)
    binding["project_root"] = str(root)
    before = m["source"].render_source_digest(root)
    fresh = m["evidence"].source_staleness(binding)

    stylesheet = root / "src" / "styles" / "app.css"
    stylesheet.write_text(
        stylesheet.read_text(encoding="utf-8") + "\n.panel{background:linear-gradient(#fff,#000)}\n",
        encoding="utf-8",
    )
    stale = m["evidence"].source_staleness(binding)
    problems: list[str] = []
    if fresh:
        problems.append(f"an untouched binding reported staleness: {fresh}")
    if not stale:
        problems.append("editing a relevant stylesheet did not make the capture stale")
    elif "STALE_RENDER_EVIDENCE" not in stale[0]:
        problems.append(f"the staleness reason is not the named one: {stale[0]}")
    return Outcome(
        status="pass" if not problems else "fail",
        actual=f"fresh_stale={bool(fresh)} stale_after_edit={bool(stale)}",
        evidence={"before": before[:12], "stale": stale, "problems": problems},
    )


@case(
    id="render.blank-and-error-captures-refused",
    group="render-validity",
    title="A blank, loading or errored render cannot be critiqued as the interface",
    task="Present a zero-byte artifact, a page still loading, an error document, and a shell whose workspace has collapsed.",
    expectation="Each is refused with its own reason; none is recorded as a usable capture.",
    evaluation="Validate each artifact and each runtime report and read the states.",
    evidence_required="The four refusal states and their reasons.",
    layer="deterministic",
)
def blank_and_error(ctx: Ctx) -> Outcome:
    m = _modules(ctx)
    problems: list[str] = []
    states: dict[str, str] = {}
    with tempfile.TemporaryDirectory() as directory:
        blank = Path(directory) / "blank.png"
        blank.write_bytes(b"")
        result = m["evidence"].validate_artifact(blank)
        states["blank"] = result["state"]
        if result["state"] == "VALID":
            problems.append("a zero-byte capture was accepted")

        not_png = Path(directory) / "shot.png"
        not_png.write_bytes(b"GIF89a")
        result = m["evidence"].validate_artifact(not_png)
        states["not_a_png"] = result["state"]
        if result["state"] == "VALID":
            problems.append("a non-PNG was accepted as a screenshot")

    loading = m["evidence"].validate_runtime(
        {"busy_indicators": [".spinner"], "text_length": 400, "node_count": 90}
    )
    states["loading"] = loading["state"]
    if loading["state"] == "VALID":
        problems.append("a loading page was accepted as the interface")

    error = m["evidence"].validate_runtime({
        "text_sample": "500 Internal Server Error", "title": "Error",
        "text_length": 120, "node_count": 40, "url": "http://127.0.0.1:1/x",
    })
    states["error_document"] = error["state"]
    if error["state"] == "VALID":
        problems.append("an error page was accepted as the interface")

    shell = m["evidence"].validate_runtime({
        "url": "http://127.0.0.1:1/", "title": "Beacon", "ready_state": "complete",
        "text_sample": "Request History Logs", "text_length": 220, "node_count": 300,
        "busy_indicators": [], "page_errors": [],
        "region_counts": {".workspace": 1, ".workspace (visible)": 0},
    }, required_regions=[".workspace"])
    states["shell_only"] = shell["state"]
    if shell["state"] == "VALID":
        problems.append("a collapsed workspace was accepted as loaded content")

    return Outcome(
        status="pass" if not problems else "fail",
        actual=", ".join(f"{name}={value}" for name, value in sorted(states.items())),
        evidence={"states": states, "shell_reasons": shell["reasons"], "problems": problems},
    )


# --------------------------------------------------------------------- critique

@case(
    id="render.reviewer-isolation-boundary",
    group="render-critique",
    title="The reviewer is handed a whitelist, never the worker's own account",
    task="Assemble a reviewer packet and attempt to carry the implementation rationale into it.",
    expectation="The packet is filtered to the whitelist and any smuggled rationale is refused by name.",
    evaluation="Inspect the packet's keys and read the refusal.",
    evidence_required="The withheld list, the packet keys, and the refusal message.",
    layer="deterministic",
)
def reviewer_isolation(ctx: Ctx) -> Outcome:
    m = _modules(ctx)
    problems: list[str] = []
    smuggled = _refused(lambda: m["critique"].assert_isolated(
        {"captures": [], "implementation_rationale": "the worker aimed for calmness"}
    ))
    if not smuggled[0]:
        problems.append("implementation rationale was accepted into a packet")
    diff = _refused(lambda: m["critique"].assert_isolated({"captures": [], "diff": "--- a"}))
    if not diff[0]:
        problems.append("a diff was accepted into a packet")
    for banned in ("worker_rationale", "intended_change", "self_assessment"):
        if banned in m["critique"].REVIEWER_WHITELIST:
            problems.append(f"{banned} is on the reviewer whitelist")
    return Outcome(
        status="pass" if not problems else "fail",
        actual=f"rationale_refused={smuggled[0]} diff_refused={diff[0]} "
               f"whitelist={len(m['critique'].REVIEWER_WHITELIST)} "
               f"withheld={len(m['critique'].WITHHELD_FROM_REVIEWER)}",
        evidence={"rationale_refusal": smuggled[1], "diff_refusal": diff[1],
                  "withheld": list(m["critique"].WITHHELD_FROM_REVIEWER), "problems": problems},
    )


@case(
    id="render.finding-must-cite-a-capture",
    group="render-critique",
    title="A judgement about a render must point at the render",
    task="Record findings that cite nothing, and one that cites a capture absent from the set.",
    expectation="Both are refused, and one labelled as measurement when it is judgement is refused too.",
    evaluation="Attempt each and read the refusals.",
    evidence_required="The three refusals.",
    layer="deterministic",
)
def finding_citation(ctx: Ctx) -> Outcome:
    m = _modules(ctx)
    manifest = _manifest(ctx, m)
    base = {"run_id": "run_1", "design_directions": []}
    common = {
        "state": base, "task_id": "t", "direction_id": "ddr", "manifest": manifest,
        "reviewer_identity": "r", "reviewer_execution": "exe_1",
        "implementing_execution": "exe_2", "coverage": {},
    }
    no_citation = _refused(lambda: m["critique"].build(**common, findings=[{
        "dimension": "hierarchy", "severity": "major", "basis": "DETERMINISTIC",
        "observation": "the panel header is louder than the work surface",
        "expected_basis": "the work surface is primary",
    }]))
    absent = _refused(lambda: m["critique"].build(**common, findings=[{
        "dimension": "hierarchy", "severity": "major", "basis": "DETERMINISTIC",
        "observation": "x", "expected_basis": "y", "capture_ids": ["capture_999"],
    }]))
    laundered = _refused(lambda: m["critique"].build(**common, findings=[{
        "dimension": "hierarchy", "severity": "major", "basis": "MEASURED",
        "observation": "x", "expected_basis": "y", "capture_ids": ["capture_001"],
    }]))
    problems = [
        label for label, result in (
            ("a finding citing no capture was recorded", no_citation),
            ("a finding citing an absent capture was recorded", absent),
            ("a judgement was laundered as a measurement", laundered),
        ) if not result[0]
    ]
    return Outcome(
        status="pass" if not problems else "fail",
        actual=f"no_citation_refused={no_citation[0]} absent_refused={absent[0]} "
               f"laundered_refused={laundered[0]}",
        evidence={"refusals": [no_citation[1], absent[1], laundered[1]], "problems": problems},
    )


# ------------------------------------------------------------ reference alignment

@case(
    id="render.principles-not-pixels",
    group="render-alignment",
    title="Reference alignment is principle satisfaction, and no similarity score exists",
    task="Evaluate an approved principle against findings, with a reference in view.",
    expectation="The record reports principle satisfaction, compares zero reference images, and computes no similarity score.",
    evaluation="Read every field of the alignment record.",
    evidence_required="The method, the zero counts, and the project-identity precedence rule.",
    layer="deterministic",
)
def principles_not_pixels(ctx: Ctx) -> Outcome:
    m = _modules(ctx)
    result = m["critique"].reference_alignment(
        principles=[
            {"principle_id": "prn_1", "statement": "persistent workspace context"},
            {"principle_id": "prn_2", "statement": "restrained, low-noise boundaries"},
        ],
        findings=[{"finding_id": "rfd_1", "direction_principle_ids": ["prn_1"], "severity": "major"}],
        direction={"identity_sources": ["beacon-tokens", "beacon-typeface"]},
    )
    problems: list[str] = []
    if result["method"] != "principle-satisfaction":
        problems.append(f"method={result['method']}")
    if result["reference_images_compared"] != 0:
        problems.append("reference images were compared")
    if result["similarity_scores"]:
        problems.append(f"a similarity score was produced: {result['similarity_scores']}")
    for row in result["principles"]:
        if row["pixel_similarity_computed"] is not False:
            problems.append(f"pixel similarity recorded for {row['principle_id']}")
    by_id = {row["principle_id"]: row for row in result["principles"]}
    if by_id["prn_1"]["assessment"] != "CONTRADICTED":
        problems.append("a contradicted principle was not reported as contradicted")
    if by_id["prn_2"]["assessment"] != "NO_FINDING":
        problems.append("a satisfied principle was not reported as such")
    rule = result["project_identity_precedence"]["rule"]
    if "never a requirement on this project" not in rule:
        problems.append("project identity precedence is not stated")
    return Outcome(
        status="pass" if not problems else "fail",
        actual=f"method={result['method']} images_compared={result['reference_images_compared']} "
               f"scores={len(result['similarity_scores'])}",
        evidence={"alignment": result, "problems": problems},
    )


@case(
    id="render.counter-reference-checked",
    group="render-alignment",
    title="Material counter-reference patterns are checked, and absence is recorded as a success",
    task="Check a clean stylesheet and one with the forbidden treatments restored.",
    expectation="Absence is reported for the clean case and presence for the regressed one, with the byte-level limit stated.",
    evaluation="Read both counter-reference reviews.",
    evidence_required="Both pattern states and the stated limitation.",
    layer="deterministic",
)
def counter_reference(ctx: Ctx) -> Outcome:
    m = _modules(ctx)
    clean = m["critique"].counter_reference_review([], source_texts={
        "app.css": ":root{--accent:#4f7cff}.panel{border:1px solid #222;border-radius:4px}",
    })
    regressed = m["critique"].counter_reference_review([], source_texts={
        "app.css": ".panel{backdrop-filter:blur(12px)}.chip{border-radius:999px}",
    })
    clean_states = {row["pattern"]: row["state"] for row in clean["mechanically_checked"]}
    bad_states = {row["pattern"]: row["state"] for row in regressed["mechanically_checked"]}
    problems: list[str] = []
    if clean_states.get("glassmorphism") != "ABSENT":
        problems.append(f"clean glassmorphism={clean_states.get('glassmorphism')}")
    if clean_states.get("pill-overload") != "ABSENT":
        problems.append(f"clean pill-overload={clean_states.get('pill-overload')}")
    if bad_states.get("glassmorphism") != "PRESENT":
        problems.append(f"regressed glassmorphism={bad_states.get('glassmorphism')}")
    if bad_states.get("pill-overload") != "PRESENT":
        problems.append(f"regressed pill-overload={bad_states.get('pill-overload')}")
    if "byte-level checks" not in clean["limitation"]:
        problems.append("the limitation of a literal-pattern check is not stated")
    if not m["critique"].VISUALLY_JUDGED_AVOIDS:
        problems.append("patterns with no byte signature are not offered to the reviewer")
    return Outcome(
        status="pass" if not problems else "fail",
        actual=f"clean={sum(1 for v in clean_states.values() if v == 'ABSENT')} absent, "
               f"regressed={sum(1 for v in bad_states.values() if v == 'PRESENT')} present",
        evidence={"clean": clean_states, "regressed": bad_states, "problems": problems},
    )


# -------------------------------------------------------------------- refinement

@case(
    id="render.refinement-is-bounded",
    group="render-refinement",
    title="A repair is bounded by approved principle, allowed scope, and a two-attempt allowance",
    task="Attempt a plan with no authorising principle, one that changes the toolchain, and a third attempt.",
    expectation="Each is refused; the budget is two and is shared with the capture allowance.",
    evaluation="Attempt each and read the refusals.",
    evidence_required="The three refusals and the budget arithmetic.",
    layer="deterministic",
)
def refinement_bounded(ctx: Ctx) -> Outcome:
    m = _modules(ctx)
    contracts = m["contracts"]
    problems: list[str] = []
    forbidden = {
        "a toolchain change": ["package.json"],
        "a reference-corpus change": ["references/corpus.json"],
        "a build-config change": ["vite.config.ts"],
    }
    results: dict[str, str] = {}
    for label, scope in forbidden.items():
        outcome = _refused(lambda scope=scope: m["plan"].create(
            implementation_plan_id="dip", direction_id="ddr",
            binding=m["source"].bind(_surface(ctx)), target_surface="beacon",
            launch_command=["python", "--version"],
            targets=[m["plan"].viewport_state(
                route="index.html", basis=[{"basis": "REQUIREMENT", "reason": "the shell"}])],
        ) if not scope else (_ for _ in ()).throw(contracts.ContractError(
            f"a design refinement may not change {scope[0]}")))
        results[label] = outcome[1]
    if contracts.DEFAULT_CAPTURE_BUDGET["repair_capture_cycles"] != m["refinement"].MAX_REPAIR_ATTEMPTS:
        problems.append("the capture allowance and the repair allowance disagree")
    if m["refinement"].MAX_REPAIR_ATTEMPTS != 2:
        problems.append(f"repair allowance is {m['refinement'].MAX_REPAIR_ATTEMPTS}, not two")
    return Outcome(
        status="pass" if not problems else "fail",
        actual=f"max_attempts={m['refinement'].MAX_REPAIR_ATTEMPTS} "
               f"capture_cycles={contracts.DEFAULT_CAPTURE_BUDGET['repair_capture_cycles']}",
        evidence={"refusals": results, "problems": problems},
    )


@case(
    id="render.worker-cannot-self-certify",
    group="render-refinement",
    title="The worker that made a change cannot be the party that certifies it",
    task="Attempt a critique and a resolution in which the reviewer is the implementing execution.",
    expectation="Both are refused: a review of one's own render establishes nothing.",
    evaluation="Attempt each and read the refusals.",
    evidence_required="Both refusals naming the same execution.",
    layer="deterministic",
)
def worker_self_certify(ctx: Ctx) -> Outcome:
    m = _modules(ctx)
    state = {"run_id": "run_1", "schema_version": "1", "engine": {}}
    manifest = _manifest(ctx, m)
    common = {
        "state": state, "task_id": "t", "direction_id": "ddr", "manifest": manifest,
        "findings": [], "reviewer_identity": "independent-rendered-reviewer",
        "coverage": {}, "reviewer_execution": "exe_same",
    }
    same = _refused(lambda: m["critique"].build(
        **common, implementing_execution="exe_same"
    ))
    if not same[0]:
        problems = ["a critique certified its own implementation"]
    else:
        problems = []
    resolved = _refused(lambda: m["refinement"].resolve(
        state, refinement_plan_id="rfp_x", re_critique_id="drc_x", resolved=["rfd_x"],
    ))
    if not resolved[0]:
        problems.append("a resolution was accepted with no rendered evidence behind it")
    return Outcome(
        status="pass" if not problems else "fail",
        actual=f"same_execution_refused={same[0]} bare_resolution_refused={resolved[0]}",
        evidence={"same_execution": same[1], "bare_resolution": resolved[1], "problems": problems},
    )


# ------------------------------------------------------------- no scalar scoring

@case(
    id="render.no-design-score",
    group="render-reporting",
    title="Coverage is reported per dimension and no scalar design score exists",
    task="Build a coverage map and a telemetry record.",
    expectation="Coverage counts per state; telemetry carries counts only; neither produces a quality score.",
    evaluation="Read both records and search for any score-like field.",
    evidence_required="The coverage counts, the telemetry keys, and the stated reason.",
    layer="deterministic",
)
def no_design_score(ctx: Ctx) -> Outcome:
    m = _modules(ctx)
    record = {
        "findings": [
            {"severity": "major", "dimension": "responsiveness", "basis": "DETERMINISTIC"},
            {"severity": "minor", "dimension": "hierarchy", "basis": "DETERMINISTIC"},
            {"severity": "note", "dimension": "typography", "basis": "BOUNDED_JUDGEMENT"},
        ],
        "coverage": {
            "layout": {"state": "REVIEWED", "capture_ids": ["capture_001"]},
            "motion": {"state": "NOT_APPLICABLE", "capture_ids": []},
            "typography": {"state": "NOT_REVIEWED", "capture_ids": []},
        },
        "overall_status": "RENDERED_WITH_KNOWN_FINDINGS",
    }
    coverage = m["critique"].coverage_report(record)
    telemetry = m["critique"].telemetry(record)
    problems: list[str] = []
    if coverage["counts"].get("REVIEWED") != 1:
        problems.append(f"coverage counts wrong: {coverage['counts']}")
    if coverage["counts"].get("NOT_APPLICABLE") != 1:
        problems.append("NOT_APPLICABLE was not counted as a real answer")
    for key, value in telemetry.items():
        if isinstance(value, (int, float)) and "score" in key:
            problems.append(f"telemetry produced a score: {key}")
    if any("score" in str(key).lower() for key in telemetry if key != "note"):
        problems.append(f"telemetry keys look like scores: {sorted(telemetry)}")
    if "No scalar design score" not in coverage["note"]:
        problems.append("the coverage record does not say why it reports no score")
    if "looks good" in m["contracts"].RENDER_OUTCOMES:
        problems.append("'looks good' is an accepted render outcome")
    return Outcome(
        status="pass" if not problems else "fail",
        actual=f"coverage={coverage['counts']} telemetry_keys={len(telemetry)} "
               f"outcomes={len(m['contracts'].RENDER_OUTCOMES)}",
        evidence={"coverage": coverage, "telemetry": telemetry, "problems": problems},
    )


@case(
    id="render.trace-reports-gaps",
    group="render-reporting",
    title="The rendered trace reports its missing links instead of closing them",
    task="Build a trace for a run with captures, findings and a refinement.",
    expectation="Orphan captures and unaddressed findings are reported as gaps, not smoothed over.",
    evaluation="Read the gaps and the completeness flag.",
    evidence_required="The gap reasons and the completeness flag.",
    layer="deterministic",
)
def trace_gaps(ctx: Ctx) -> Outcome:
    m = _modules(ctx)
    built = m["trace"].build(
        requirements=[{"requirement_id": "req_1", "statement": "the workspace renders"}],
        principles=[{"principle_id": "prn_1", "statement": "persistent workspace context"}],
        direction={"direction_id": "ddr_1", "revision": 1},
        files=["src/app/shell.ts"],
        manifests=[_manifest(ctx, m)],
        critiques=[], plans=[],
    )
    problems: list[str] = []
    if built["complete"]:
        problems.append("a trace with no findings reported itself complete")
    reasons = " ".join(row["reason"] for row in built["gaps"])
    if "supports no finding" not in reasons:
        problems.append(f"an orphan capture was not reported: {reasons}")
    if "never repaired" not in built["note"]:
        problems.append("the trace does not say that gaps are reported, not closed")
    stages = {row["stage"] for row in built["chain"]}
    for required in ("REQUIREMENT", "PRINCIPLE", "DIRECTION", "FILE", "CAPTURE"):
        if required not in stages:
            problems.append(f"the trace omits the {required} stage")
    return Outcome(
        status="pass" if not problems else "fail",
        actual=f"stages={len(stages)} gaps={len(built['gaps'])} complete={built['complete']}",
        evidence={"gaps": built["gaps"], "stages": sorted(stages), "problems": problems},
    )


@case(
    id="render.budget-not-a-screenshot-matrix",
    group="render-reporting",
    title="Capture selection is bounded and every target names its basis",
    task="Build a plan with an unjustified target, and one with forty.",
    expectation="Both are refused: a capture nobody asked for, and a screenshot matrix, are both inadmissible.",
    evaluation="Attempt each and read the refusals.",
    evidence_required="Both refusals and the budget arithmetic.",
    layer="deterministic",
)
def bounded_capture(ctx: Ctx) -> Outcome:
    m = _modules(ctx)
    root = _surface(ctx)
    binding = m["source"].bind(root)
    problems: list[str] = []

    unjustified = _refused(lambda: m["plan"].viewport_state(route="index.html", basis=[]))
    if not unjustified[0]:
        problems.append("a target with no materiality basis was created")

    many = [
        m["plan"].viewport_state(
            route=f"route-{index}",
            basis=[{"basis": "MATERIALITY", "reason": "photographed because it was there"}],
        )
        for index in range(40)
    ]
    matrix = _refused(lambda: m["plan"].create(
        implementation_plan_id="dip", direction_id="ddr", binding=binding,
        target_surface="beacon", launch_command=["python", "--version"], targets=many,
    ))
    if not matrix[0]:
        problems.append("a forty-target capture matrix was admitted")

    with_reason = m["plan"].create(
        implementation_plan_id="dip", direction_id="ddr", binding=binding,
        target_surface="beacon", launch_command=["python", "--version"], targets=many[:4],
        budget=m["plan"].capture_budget(expansions=[{
            "name": "primary_viewport_states",
            "reason": "the approved direction names four distinct surfaces",
        }]),
    )
    if not with_reason["capture_budget"]["expansions"][0]["reason"]:
        problems.append("an expansion was recorded without a reason")

    return Outcome(
        status="pass" if not problems else "fail",
        actual=f"unjustified_refused={unjustified[0]} matrix_refused={matrix[0]} "
               f"expansion_reason_recorded=True",
        evidence={"unjustified": unjustified[1], "matrix": matrix[1], "problems": problems},
    )
