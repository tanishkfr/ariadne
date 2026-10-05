#!/usr/bin/env python3
"""AR-223 regression runner: the whole suite list, strictly serially.

AR-222 found that two mutation harnesses could share one restore marker, and AR-222D
wrapped mutation state in a transactional ledger. Neither of those is a licence to
parallelise: a mutation suite edits engine source in place and restores it afterwards,
so any cleanliness-sensitive suite that reads that source at the same moment observes a
tree that does not exist. This runner therefore executes suites one at a time and waits
for each to exit, rather than relying on a scheduler that would eventually put two of
them in the same instant.

Three groups, in order:

1. CLEANLINESS-SENSITIVE  repository structure, release contract, distribution
2. FUNCTIONAL            engine core, decision runtime, per-AR suites
3. MUTATION              every mutation harness, one at a time

Usage::

    python scripts/ar223-regression.py                 # everything
    python scripts/ar223-regression.py --group clean   # one group
    python scripts/ar223-regression.py --list

Exit 0 only when every selected suite exited 0.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

#: Suites that read repository structure, the release contract, or the working tree as a
#: whole. These run first and alone, because they are the ones a concurrent mutation
#: harness would corrupt.
CLEAN = (
    "check",
    "test-release",
    "test-distribution",
)

#: Ordinary functional suites. Fast, and none of them edit engine source.
FUNCTIONAL = (
    "test-engine-core",
    "test-decision-runtime",
    "test-design-reference",
    "test-design-execution",
    "test-design-execution-adversarial",
    "test-rendered-critique",
    "test-rendered-critique-adversarial",
    "test-ar222d",
    "test-ar222d-adversarial",
)

#: Mutation harnesses. Each one edits source, runs a suite, and restores byte-exact.
#: AR-222 measured these at minutes, not seconds, which is the whole reason this runner
#: exists rather than a bare for-loop in a shell.
MUTATION = (
    "test-decision-mutations",
    "test-decision-runtime-mutations",
    "test-design-reference-mutations",
    "test-design-execution-mutations",
    "test-rendered-critique-mutations",
    "test-ar222d-mutations",
)

GROUPS = {"clean": CLEAN, "functional": FUNCTIONAL, "mutation": MUTATION}

#: `check` is a repository checker rather than a named script suite, so it is spelled out
#: instead of being derived from the suite name.
COMMAND = {"check": "check.py"}


def suite_script(name: str) -> Path:
    return ROOT / "scripts" / COMMAND.get(name, f"{name}.py")


def run_suite(name: str, timeout: float) -> dict:
    script = suite_script(name)
    if not script.is_file():
        return {"suite": name, "script": script.name, "exit": None, "seconds": 0.0,
                "ok": False, "summary": "suite script is missing"}
    start = time.monotonic()
    completed = subprocess.run(
        [sys.executable, str(script)],
        cwd=str(ROOT), capture_output=True, text=True,
        timeout=timeout, shell=False, stdin=subprocess.DEVNULL,
    )
    elapsed = round(time.monotonic() - start, 2)
    output = (completed.stdout or "") + (completed.stderr or "")
    tail = [line for line in output.splitlines()
            if line.startswith(("FAIL", "ERROR", "SURVIVED", "SELF-TEST FAILED", "Traceback"))]
    return {
        "suite": name,
        "script": script.name,
        "exit": completed.returncode,
        "seconds": elapsed,
        "ok": completed.returncode == 0,
        "summary": next((line for line in output.splitlines() if "passed" in line), ""),
        "diagnostics": tail[:20],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--group", choices=sorted(GROUPS), action="append")
    parser.add_argument("--suite", action="append", help="run exactly these, in this order")
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--json", help="write the run record here")
    parser.add_argument("--timeout", type=float, default=7200.0,
                        help="per-suite seconds before the runner gives up on it")
    args = parser.parse_args()

    if args.list:
        for group, names in GROUPS.items():
            for name in names:
                print(f"{group:<11} {name}")
        return 0

    if args.suite:
        names = tuple(args.suite)
    else:
        selected = args.group or sorted(GROUPS)
        names = tuple(name for group in selected for name in GROUPS[group])

    print(f"ARIADNE 2.2 -- AR-223 REGRESSION ({len(names)} suites, strictly serial)\n")
    results = []
    for name in names:
        row = run_suite(name, args.timeout)
        results.append(row)
        verdict = "ok  " if row["ok"] else "FAIL"
        print(f"{verdict} {name:<36} exit={row['exit']} {row['seconds']}s "
              f"{row['summary'][:80]}")
        for line in row["diagnostics"]:
            print(f"       {line[:160]}")
        sys.stdout.flush()

    failed = [row["suite"] for row in results if not row["ok"]]
    record = {
        "schema": "ariadne-ar223-regression-1",
        "head": subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=str(ROOT),
            capture_output=True, text=True, shell=False,
        ).stdout.strip(),
        "version": (ROOT / "VERSION").read_text(encoding="utf-8").strip(),
        "serial": True,
        "suites": results,
        "failed": failed,
    }
    if args.json:
        target = Path(args.json)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"\nrecord: {target}")

    if failed:
        print(f"\nFAILED: {', '.join(failed)}")
        return 1
    print("\nregression: green")
    return 0


if __name__ == "__main__":
    sys.exit(main())