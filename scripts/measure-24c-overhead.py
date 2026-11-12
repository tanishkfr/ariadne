#!/usr/bin/env python3
"""Measure the 2.4C overhead on the real qualification artifacts.

This is a local wall-clock measurement, not a benchmark score. It reports
median and p95 for the new host projection, event page, creative-binding
construction, screenshot comparison, accessibility reporting and context
assembly. Where a new feature has no pre-2.4C baseline, the report says so
instead of inventing a comparison.
"""

from __future__ import annotations

import json
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ariadne_engine import creative_proof, host, proof  # noqa: E402
from ariadne_engine import context, persistence  # noqa: E402
from ariadne_engine import visual_diff  # noqa: E402
from ariadne_engine.rendered_critique import evidence  # noqa: E402

DESIGN = ROOT / "validation" / "runs" / "2.4c" / "design"
RUN = DESIGN / "run"


def timed(fn, *, repeats: int = 50) -> dict:
    samples = []
    for _ in range(repeats):
        started = time.perf_counter()
        fn()
        samples.append((time.perf_counter() - started) * 1000)
    samples.sort()
    return {
        "repeats": repeats,
        "median_ms": round(statistics.median(samples), 3),
        "p95_ms": round(samples[min(len(samples) - 1, int(len(samples) * 0.95))], 3),
        "min_ms": round(samples[0], 3),
        "max_ms": round(samples[-1], 3),
    }


def main() -> int:
    report: dict = {
        "schema_version": "ariadne-24c-performance-1",
        "measured_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "environment": {"platform": sys.platform, "python": sys.version.split()[0]},
        "measurements": {},
        "limitations": [],
    }
    state_path = RUN / "state.json"
    report_path = DESIGN / "report-after.json"
    if not state_path.is_file() or not report_path.is_file():
        report["limitations"].append("the design qualification artifacts are absent; run the design qualification first")
        print(json.dumps(report, indent=2, sort_keys=True))
        return 1
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["run_root"] = str(RUN)
    design = json.loads(report_path.read_text(encoding="utf-8"))
    receipt = json.loads((RUN / "proof-receipt.json").read_text(encoding="utf-8"))
    captures = [row for row in design.get("captures") or [] if row.get("artifact_path")]
    before_capture = next(
        (row for row in json.loads((DESIGN / "report-before.json").read_text(encoding="utf-8")).get("captures") or []
         if row.get("viewport", {}).get("width") == 390),
        {},
    )
    after_capture = next((row for row in captures if row.get("viewport", {}).get("width") == 390), {})
    report["measurements"]["host_status"] = timed(
        lambda: host.status(state, task_report={"task_id": "design-qualification"}), repeats=100,
    )
    report["measurements"]["host_event_page"] = timed(lambda: host.event_page(RUN, limit=100), repeats=100)
    report["measurements"]["creative_binding"] = timed(
        lambda: creative_proof.current_problems(
            receipt["creative_review"], state,
            work_digest=receipt["work_digest"],
            implementation_fingerprint=receipt.get("implementation_fingerprint", ""),
        ),
        repeats=100,
    )
    report["measurements"]["proof_receipt_validation"] = timed(
        lambda: proof.receipt_problems(receipt), repeats=200,
    )
    if before_capture and after_capture:
        report["measurements"]["visual_comparison_390"] = timed(
            lambda: visual_diff.compare_files(
                Path(before_capture["artifact_path"]), Path(after_capture["artifact_path"]),
            ),
            repeats=30,
        )
    synthetic_report = {
        "focusable_count": 8,
        "focusable_without_ring": [],
        "small_targets": [],
        "unlabelled_controls": [],
        "prefers_reduced_motion": False,
        "transition_duration": "0s",
        "accessibility": {
            "contrast": {"checks": 12, "failures": [], "unverified": 0},
            "dialogs": [], "form_controls": [], "status_messages": [], "landmarks": [],
        },
    }
    report["measurements"]["accessibility_report"] = timed(
        lambda: evidence.accessibility_report(synthetic_report), repeats=500,
    )
    candidates = []
    for index in range(25):
        path = DESIGN / "project" / f"measure_{index:02d}.py"
        path.write_text(f"VALUE = {index}\n", encoding="utf-8")
        candidates.append({
            "label": path.name, "path": str(path), "kind": "project-scope-file",
            "required": False, "bytes": path.stat().st_size,
        })
    candidates.append({
        "label": "task contract", "path": str(DESIGN / "project" / "QA.md"),
        "kind": "project-task-contract", "required": True,
    })
    report["measurements"]["context_off"] = timed(
        lambda: context.decide({}, stage="T1", candidates=candidates, revision_hash="r1", reduction="off"),
        repeats=30,
    )
    report["measurements"]["context_adaptive"] = timed(
        lambda: context.decide(
            {"request": "fix measure_00.py"}, stage="T1", candidates=candidates,
            revision_hash="r1", reduction="adaptive",
        ),
        repeats=30,
    )
    report["measurements"]["recovery_report"] = timed(
        lambda: persistence.recovery_report(RUN), repeats=100,
    )
    manifest = json.loads(Path(str(design.get("manifest_path", ""))).read_text(encoding="utf-8"))
    report["capture_run"] = {
        "duration_seconds": manifest.get("duration_seconds"),
        "captures": len(manifest.get("captures") or []),
        "capture_bytes": manifest.get("capture_bytes"),
        "browser": manifest.get("browser"),
    }
    report["limitations"] = [
        "Wall-clock measurements on one Windows machine; not a cross-platform benchmark.",
        "The host contract, creative binding and visual comparison are new in 2.4C, so there is no pre-2.4C baseline to compare them against.",
        "Capture duration includes browser launch and page settle time; it is not pure Ariadne overhead.",
        "No optimization has removed any verification step to obtain these numbers.",
    ]
    target = ROOT / "validation" / "runs" / "2.4c" / "performance.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
