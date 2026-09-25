#!/usr/bin/env python3
"""AR-200 deterministic benchmark runner.

Usage:
    python benchmarks/run_benchmarks.py                 # run every executable case
    python benchmarks/run_benchmarks.py --list          # list cases without running
    python benchmarks/run_benchmarks.py --only suites   # run one group
    python benchmarks/run_benchmarks.py --case lifecycle.s5-isolation
    python benchmarks/run_benchmarks.py --write-manifest  # regenerate manifest.json
    python benchmarks/run_benchmarks.py --release        # the curated release gate
    python benchmarks/run_benchmarks.py --work-root D:/tmp/ar-bench

Design rules:
  * standard library only; no network; no model calls; no paid evaluation
  * every fixture is created under --work-root (default: OS temp), never in a repository
  * the runtime under test is executed as a subprocess exactly as an operator would
  * results are machine-readable and include the commands and artifacts behind each verdict
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import sys
import tempfile
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent
sys.path.insert(0, str(HERE))

from arbench import cases as C  # noqa: E402
from arbench.driver import Repo  # noqa: E402

RESULTS_SCHEMA = 1
RESULT_STATUSES = ("pass", "fail", "observed", "error", "skip")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def runtime_identity(repo: Repo) -> dict:
    return {
        "repo_root": str(repo.root),
        "git_head": repo.commit(),
        "git_branch": repo.git("rev-parse", "--abbrev-ref", "HEAD"),
        "version_file": (repo.root / "VERSION").read_text(encoding="utf-8").strip()
        if (repo.root / "VERSION").is_file() else None,
        "dirty_entries": len(repo.status_porcelain()),
    }


def environment() -> dict:
    return {
        "python": sys.version.split()[0],
        "python_executable": sys.executable,
        "platform": platform.platform(),
        "machine": platform.machine(),
        "cwd": os.getcwd(),
    }


def case_manifest() -> dict:
    return {
        "schema_version": RESULTS_SCHEMA,
        "kind": "ariadne-v2-deterministic-benchmark-manifest",
        "generated_at": utc_now(),
        "runtime": {"repo_root": str(REPO_ROOT)},
        "statuses": list(RESULT_STATUSES),
        "cases": [
            {
                "id": case.id,
                "group": case.group,
                "title": case.title,
                "task": case.task,
                "required_inputs": ["repository at the pinned commit", "isolated sandbox under --work-root"],
                "expected_outcome": case.expectation,
                "evaluation_method": case.evaluation,
                "evidence_required_for_success": case.evidence_required,
                "environment_requirements": list(case.requires) or ["python >= 3.10", "git on PATH"],
                "provider_requirements": [],
                "cost_implications": case.cost,
                "currently_executable": case.executable,
                "layer": case.layer,
                "notes": case.notes,
            }
            for case in C.CASES
        ],
    }


def write_manifest(path: Path) -> None:
    path.write_text(json.dumps(case_manifest(), indent=2, sort_keys=False) + "\n", encoding="utf-8")


def run_case(repo: Repo, work_root: Path, fixtures: dict, case: C.Case) -> dict:
    started = time.monotonic()
    record = {
        "id": case.id,
        "group": case.group,
        "title": case.title,
        "layer": case.layer,
        "expected_outcome": case.expectation,
        "started_at": utc_now(),
    }
    if not case.executable:
        record.update({"status": "skip", "actual": case.notes or "declared not executable",
                       "duration_seconds": 0.0, "evidence": {}, "metrics": {"model_calls": 0}})
        return record
    ctx = C.Ctx(repo=repo, work_root=work_root, fixtures=fixtures, case=case)
    try:
        outcome = case.runner(ctx)
        record.update({
            "status": outcome.status,
            "actual": outcome.actual,
            "evidence": outcome.evidence,
            "metrics": {"model_calls": 0, "cost": 0.0, **outcome.metrics},
        })
    except Exception as exc:  # harness failure, never a silent pass
        record.update({
            "status": "error",
            "actual": f"{type(exc).__name__}: {exc}",
            "evidence": {"traceback": traceback.format_exc()[-1500:]},
            "metrics": {"model_calls": 0, "cost": 0.0},
        })
    record["duration_seconds"] = round(time.monotonic() - started, 3)
    record["sandbox"] = str(work_root / case.id.replace(".", "-"))
    return record


def summarise(records: list[dict]) -> dict:
    counts = {status: sum(1 for r in records if r["status"] == status) for status in RESULT_STATUSES}
    metrics = {}
    for r in records:
        for key, value in (r.get("metrics") or {}).items():
            if isinstance(value, (int, float)):
                metrics[key] = metrics.get(key, 0) + value
    return {
        "cases": len(records),
        "counts": counts,
        "totals": metrics,
        "total_duration_seconds": round(sum(r.get("duration_seconds") or 0 for r in records), 3),
    }


def print_table(records: list[dict]) -> None:
    width = max(len(r["id"]) for r in records) if records else 10
    print()
    print(f"{'CASE'.ljust(width)}  {'STATUS'.ljust(8)}  {'SECONDS'.rjust(7)}  RESULT")
    print("-" * (width + 40))
    for record in records:
        line = record.get("actual", "")[:110]
        print(f"{record['id'].ljust(width)}  {record['status'].ljust(8)}  "
              f"{record.get('duration_seconds', 0):7.2f}  {line}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work-root", default=None,
                        help="sandbox root (default: %%TEMP%%/ariadne-bench-<timestamp>)")
    parser.add_argument("--only", default=None, help="run only this group")
    parser.add_argument("--release", action="store_true",
                        help="run the curated AR-205 release-gate subset instead of every case")
    parser.add_argument("--case", action="append", default=[], help="run only this case id (repeatable)")
    parser.add_argument("--list", action="store_true", help="list cases and exit")
    parser.add_argument("--write-manifest", action="store_true", help="regenerate manifest.json and exit")
    parser.add_argument("--results-dir", default=str(HERE / "results"))
    parser.add_argument("--keep-sandbox", action="store_true", help="do not delete the sandbox afterwards")
    parser.add_argument("--label", default="", help="free-form label recorded with the results")
    args = parser.parse_args(argv)

    if args.write_manifest:
        write_manifest(HERE / "manifest.json")
        print(f"wrote {HERE / 'manifest.json'} ({len(C.CASES)} cases)")
        return 0

    if args.list:
        for case in C.CASES:
            flag = "exec" if case.executable else "skip"
            print(f"{case.id.ljust(46)} {case.group.ljust(13)} {flag}  {case.title}")
        print(f"\n{len(C.CASES)} cases")
        return 0

    from arbench.release_subset import RELEASE_SUBSET

    selected = [case for case in C.CASES
                if (not args.release or case.id in RELEASE_SUBSET)
                and (not args.only or case.group == args.only)
                and (not args.case or case.id in args.case)]
    if args.release:
        known = {case.id for case in C.CASES}
        missing = sorted(set(RELEASE_SUBSET) - known)
        if missing:
            print(f"Release subset names unknown cases: {', '.join(missing)}", file=sys.stderr)
            return 2
    if not selected:
        print("No cases selected.", file=sys.stderr)
        return 2

    repo = Repo(REPO_ROOT)
    fixtures = {"handoff": None}
    if not (REPO_ROOT / "VERSION").is_file():
        print(f"Not an Ariadne worktree: {REPO_ROOT}", file=sys.stderr)
        return 2

    from arbench import fixtures as FX
    fixtures = FX.runtime_fixtures(repo)

    work_root = Path(args.work_root) if args.work_root else Path(
        tempfile.mkdtemp(prefix="ariadne-bench-", dir=tempfile.gettempdir()))
    work_root.mkdir(parents=True, exist_ok=True)

    print(f"Ariadne AR-200 deterministic benchmark")
    print(f"  runtime : {repo.root} @ {repo.commit()[:7]}")
    print(f"  sandbox : {work_root}")
    print(f"  subset  : {'release gate' if args.release else 'exhaustive'}")
    print(f"  cases   : {len(selected)}")

    records = []
    for case in selected:
        record = run_case(repo, work_root, fixtures, case)
        records.append(record)
        marker = {"pass": "ok  ", "fail": "FAIL", "observed": "obs ", "error": "ERR ", "skip": "skip"}[record["status"]]
        print(f"  {marker} {record['id']}  ({record['duration_seconds']:.1f}s)")

    summary = summarise(records)
    document = {
        "schema_version": RESULTS_SCHEMA,
        "kind": "ariadne-v2-deterministic-benchmark-results",
        "subset": "release" if args.release else "exhaustive",
        "label": args.label,
        "recorded_at": utc_now(),
        "runtime": runtime_identity(repo),
        "environment": environment(),
        "sandbox_root": str(work_root),
        "summary": summary,
        "measurement_boundaries": {
            "model_calls": 0,
            "token_usage": "UNKNOWN - no model provider was invoked",
            "cost": 0.0,
            "note": "This run is deterministic and offline. Model-backed metrics are NOT measured here.",
        },
        "results": records,
    }

    results_dir = Path(args.results_dir)
    results_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%dT%H%M%S")
    prefix = "ar-205-release" if args.release else "ar-200"
    result_path = results_dir / f"{prefix}-{stamp}.json"
    result_path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
    (results_dir / "LATEST.json").write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")

    print_table(records)
    print()
    print(f"summary: {summary['counts']} in {summary['total_duration_seconds']}s")
    print(f"results: {result_path}")
    print(f"latest : {results_dir / 'LATEST.json'}")

    if not args.keep_sandbox:
        shutil.rmtree(work_root, ignore_errors=True)

    return 1 if summary["counts"].get("fail") or summary["counts"].get("error") else 0


if __name__ == "__main__":
    raise SystemExit(main())
