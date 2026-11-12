#!/usr/bin/env python3
"""Ariadne 2.4B evaluation runner.

This is the reproducible harness for the 2.4B workload set. It is deliberately
boring: it validates the workload definitions, runs the mapped deterministic
benchmark cases through the repository's own benchmark driver, optionally runs
the same shared cases on a baseline worktree, and measures a real context
before/after on two disposable task packets.

It does not call a model and does not estimate tokens. Live workloads are
recorded in the workload document and reported as NOT_RUN unless a separate,
explicit live qualification supplied results. Nothing here turns a fixture pass
into a provider-performance claim.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

WORKLOADS = ROOT / "benchmarks" / "workloads" / "2.4b-intelligence.json"
RESULTS = ROOT / "validation" / "runs" / "2.4b"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_workloads(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or not isinstance(value.get("workloads"), list):
        raise SystemExit(f"{path} is not a workload document")
    return value


def validation_problems(document: dict) -> list[str]:
    problems: list[str] = []
    workloads = document.get("workloads") or []
    if not 24 <= len(workloads) <= 30:
        problems.append(f"expected 24-30 workloads, found {len(workloads)}")
    ids = [str(item.get("id", "")) for item in workloads]
    if len(ids) != len(set(ids)):
        problems.append("workload ids are not unique")
    required = (
        "id", "category", "request", "starting_revision", "permitted_scope",
        "required_validation", "expected_behavior", "execution_kind",
    )
    for item in workloads:
        missing = [name for name in required if name not in item]
        if missing:
            problems.append(f"{item.get('id', '?')} is missing {', '.join(missing)}")
        if str(item.get("execution_kind")) not in ("deterministic", "live"):
            problems.append(f"{item.get('id', '?')} has an unsupported execution kind")
        if str(item.get("execution_kind")) == "deterministic" and not item.get("benchmark_cases"):
            problems.append(f"{item.get('id', '?')} is deterministic with no benchmark case")
    categories = {str(item.get("category", "")) for item in workloads}
    expected = {
        "simple-bug-fix", "multi-file-bug-fix", "feature", "refactor",
        "architecture-sensitive", "performance-investigation", "tests-and-validation",
        "ui-implementation", "accessibility", "read-only-research",
    }
    missing_categories = sorted(expected - categories)
    if missing_categories:
        problems.append("missing workload categories: " + ", ".join(missing_categories))
    return problems


def benchmark_cases(document: dict) -> list[str]:
    cases: list[str] = []
    for item in document["workloads"]:
        if str(item.get("execution_kind")) != "deterministic":
            continue
        for case_id in item.get("benchmark_cases") or ():
            if str(case_id) not in cases:
                cases.append(str(case_id))
    return cases


def run_benchmarks(*, repo: Path, cases: list[str], results_dir: Path) -> dict:
    results_dir.mkdir(parents=True, exist_ok=True)
    argv = [
        sys.executable, str(repo / "benchmarks" / "run_benchmarks.py"),
        "--results-dir", str(results_dir), "--label", "2.4b-evaluation",
    ]
    for case_id in cases:
        argv.extend(["--case", case_id])
    completed = subprocess.run(argv, cwd=str(repo), capture_output=True, text=True, timeout=1800)
    latest = results_dir / "LATEST.json"
    document = json.loads(latest.read_text(encoding="utf-8")) if latest.is_file() else {}
    return {
        "argv": argv,
        "returncode": completed.returncode,
        "stdout_tail": "\n".join(completed.stdout.splitlines()[-12:]),
        "stderr_tail": "\n".join(completed.stderr.splitlines()[-12:]),
        "document": document,
    }


def _base_support():
    spec = importlib.util.spec_from_file_location("ar23b_support", ROOT / "scripts" / "test-ar23b.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules["ar23b_support"] = module
    spec.loader.exec_module(module)
    return module


def context_experiment(base: Path) -> dict:
    """Prepare two real task packets: default context and adaptive reduction."""
    import contextlib
    import io

    support = _base_support()
    results = {}
    for profile in ("off", "adaptive"):
        work = base / profile
        work.mkdir(parents=True, exist_ok=True)
        project = support.make_project(work, name="app")
        # Six unchanged scope files the request does not name are the eligible
        # optional sources. This is a realistic multi-file scope: the worker may
        # read them in place, but re-delivering all of them duplicates context.
        helper_paths = []
        for index in range(1, 7):
            path = project / f"helpers_{index}.py"
            path.write_text(
                "".join(f"def helper_{index}_{line}():\n    return {line}\n\n" for line in range(1, 120)),
                encoding="utf-8",
            )
            helper_paths.append(path.name)
        subprocess.run(["git", "add", "-A"], cwd=project, capture_output=True, text=True)
        subprocess.run(
            ["git", "-c", "user.email=fixture@example.com", "-c", "user.name=Fixture",
             "commit", "-qm", "add helper"],
            cwd=project, capture_output=True, text=True,
        )
        scope_args = []
        for name in ["export.py", *helper_paths]:
            scope_args.extend(["--scope", name])
        code, text = support.run_cli(
            "task-start", "--project", str(project),
            "--request", support.BUG_REQUEST,
            *scope_args,
            "--validate", "python -m pytest -q",
            "--context-reduction", profile,
        )
        run_root = support.run_root_for(project)
        packet = None
        state = {}
        if code == 0:
            packets = support.packet_dirs(run_root)
            packet = packets[-1] / "packet.txt" if packets else None
            state = support.state_of(run_root)
        decision = (state.get("context_decisions") or [{}])[-1] if state else {}
        results[profile] = {
            "exit_code": code,
            "output_tail": "\n".join(text.splitlines()[-6:]),
            "packet_path": str(packet) if packet else "",
            "packet_bytes": packet.stat().st_size if packet and packet.is_file() else "UNKNOWN",
            "context": {
                "included": decision.get("included"),
                "omitted": decision.get("omitted"),
                "included_bytes": decision.get("included_bytes"),
                "omitted_bytes": decision.get("omitted_bytes"),
                "reduction": decision.get("reduction"),
                "cache": decision.get("cache"),
            },
            "omitted_paths": [
                str(item.get("path", "")) for item in decision.get("decisions") or ()
                if str(item.get("decision")) == "omitted"
            ],
        }
    off_bytes = results["off"].get("packet_bytes")
    adaptive_bytes = results["adaptive"].get("packet_bytes")
    saved = (
        int(off_bytes) - int(adaptive_bytes)
        if isinstance(off_bytes, int) and isinstance(adaptive_bytes, int) else "UNKNOWN"
    )
    return {
        "profiles": results,
        "packet_bytes_saved": saved,
        "note": (
            "both packets were prepared by the real CLI on identical disposable projects; "
            "the only difference is the context_reduction profile. Bytes are file sizes, not tokens."
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workloads", default=str(WORKLOADS))
    parser.add_argument("--baseline-worktree", default="", help="a clean 2.4A-R worktree to compare shared cases")
    parser.add_argument("--results-dir", default=str(RESULTS))
    parser.add_argument("--skip-bench", action="store_true")
    parser.add_argument("--skip-context", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    document = load_workloads(Path(args.workloads))
    problems = validation_problems(document)
    if problems:
        print("Workload definition is not valid:", file=sys.stderr)
        for problem in problems:
            print(f"  - {problem}", file=sys.stderr)
        return 2
    cases = benchmark_cases(document)
    output = {
        "schema_version": 1,
        "kind": "ariadne-2.4b-evaluation",
        "recorded_at": utc_now(),
        "workloads": {
            "path": str(Path(args.workloads)),
            "count": len(document["workloads"]),
            "deterministic": sum(1 for item in document["workloads"] if item["execution_kind"] == "deterministic"),
            "live": sum(1 for item in document["workloads"] if item["execution_kind"] == "live"),
            "categories": sorted({str(item["category"]) for item in document["workloads"]}),
        },
        "runtime": {
            "repo": str(ROOT),
            "git_head": subprocess.run(
                ["git", "rev-parse", "HEAD"], cwd=str(ROOT), capture_output=True, text=True
            ).stdout.strip(),
            "baseline_revision": document.get("baseline_revision", ""),
        },
        "limitations": [
            "deterministic cases verify engine behaviour, not provider output quality",
            "no model was called by the default run; token usage and provider cost are UNKNOWN",
            "a live workload is not a result unless a separate authenticated run records one",
        ],
    }
    if not args.skip_bench:
        bench_dir = Path(args.results_dir) / "bench-candidate"
        bench = run_benchmarks(repo=ROOT, cases=cases, results_dir=bench_dir)
        by_id = {
            str(row.get("id", "")): row
            for row in (bench["document"].get("results") or [])
            if isinstance(row, dict)
        }
        records = []
        for item in document["workloads"]:
            if item["execution_kind"] != "deterministic":
                continue
            case_ids = [str(case) for case in item.get("benchmark_cases") or ()]
            rows = [by_id.get(case) for case in case_ids]
            statuses = [str(row.get("status", "missing")) if row else "missing" for row in rows]
            records.append({
                "id": item["id"],
                "category": item["category"],
                "benchmark_cases": case_ids,
                "statuses": statuses,
                "verified_outcome": (
                    "verified-engine-behaviour" if statuses and all(status == "pass" for status in statuses)
                    else "not-verified" if any(status in ("fail", "error", "missing") for status in statuses)
                    else "observed-or-skipped"
                ),
                "evidence": [
                    str(row.get("evidence")) for row in rows if row and row.get("evidence")
                ],
            })
        output["benchmark"] = {
            "returncode": bench["returncode"],
            "summary": bench["document"].get("summary", {}),
            "cases_requested": len(cases),
            "cases_present": len(by_id),
            "workload_records": records,
            "stdout_tail": bench["stdout_tail"],
            "stderr_tail": bench["stderr_tail"],
        }
        if args.baseline_worktree:
            baseline_cases = [case for case in cases if _baseline_has_case(Path(args.baseline_worktree), case)]
            baseline_dir = Path(args.results_dir) / "bench-baseline"
            baseline = run_benchmarks(repo=Path(args.baseline_worktree), cases=baseline_cases, results_dir=baseline_dir)
            output["baseline"] = {
                "worktree": str(Path(args.baseline_worktree)),
                "cases_requested": len(baseline_cases),
                "skipped_new_cases": sorted(set(cases) - set(baseline_cases)),
                "summary": baseline["document"].get("summary", {}),
                "returncode": baseline["returncode"],
            }
    if not args.skip_context:
        with tempfile.TemporaryDirectory(prefix="ariadne-24b-context-") as tmp:
            output["context_experiment"] = context_experiment(Path(tmp))

    results_dir = Path(args.results_dir)
    results_dir.mkdir(parents=True, exist_ok=True)
    target = results_dir / "evaluation.json"
    target.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if args.json:
        print(json.dumps(output, indent=2, sort_keys=True, default=str))
    else:
        print("2.4B evaluation")
        print(f"  workloads: {output['workloads']['count']} "
              f"({output['workloads']['deterministic']} deterministic, {output['workloads']['live']} live)")
        if "benchmark" in output:
            print(f"  benchmark: {output['benchmark']['summary'].get('counts')}")
        if "baseline" in output:
            print(f"  baseline : {output['baseline']['summary'].get('counts')} "
                  f"({len(output['baseline']['skipped_new_cases'])} new case(s) not on baseline)")
        if "context_experiment" in output:
            experiment = output["context_experiment"]
            print(f"  context  : packet bytes saved {experiment['packet_bytes_saved']} "
                  f"(off {experiment['profiles']['off']['packet_bytes']} -> "
                  f"adaptive {experiment['profiles']['adaptive']['packet_bytes']})")
        print(f"  evidence : {target}")
        print("  note     : deterministic only; no model was called and no provider claim is made")
    return 0 if not output.get("benchmark", {}).get("returncode") else 1


def _baseline_has_case(repo: Path, case_id: str) -> bool:
    completed = subprocess.run(
        [sys.executable, str(repo / "benchmarks" / "run_benchmarks.py"), "--list"],
        cwd=str(repo), capture_output=True, text=True, timeout=120,
    )
    return case_id in completed.stdout


if __name__ == "__main__":
    sys.exit(main())
