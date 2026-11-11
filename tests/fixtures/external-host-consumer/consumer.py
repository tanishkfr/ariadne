#!/usr/bin/env python3
"""External host-consumer fixture for the Ariadne 2.4C contract.

This file is deliberately outside the engine package and imports no
``ariadne_engine`` module. It consumes only the versioned CLI surface a real
host would use, keeps a cursor in its own state file, and refuses malformed or
stale host state instead of guessing.

It is not Juno and does not claim Juno integration. It is a consumer that proves
the contract is consumable from outside the Python module boundary.

Usage:
    python consumer.py --ariadne <path/to/scripts/ariadne.py> --run-root <run> \
        --state <consumer-state.json> --json
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


def call(ariadne: Path, *args: str) -> tuple[int, str]:
    completed = subprocess.run(
        [sys.executable, str(ariadne), *args],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    return completed.returncode, (completed.stdout or "") + (completed.stderr or "")


def load(path: Path) -> dict:
    if not path.is_file():
        return {"cursor": None, "seen_event_ids": [], "last_proof": "", "runs": 0}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"cursor": None, "seen_event_ids": [], "last_proof": "", "runs": 0}
    return value if isinstance(value, dict) else {"cursor": None, "seen_event_ids": [], "runs": 0}


def save(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ariadne", required=True)
    parser.add_argument("--run-root", required=True)
    parser.add_argument("--state", required=True)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    ariadne = Path(args.ariadne)
    state_path = Path(args.state)
    saved = load(state_path)
    report: dict = {
        "schema_version": "external-host-consumer-1",
        "run_count": int(saved.get("runs", 0)) + 1,
        "problems": [],
    }

    code, text = call(ariadne, "host-status", "--run-root", args.run_root, "--json")
    if code != 0:
        report["status"] = "REFUSED"
        report["problems"].append(text.strip()[-500:])
        print(json.dumps(report, indent=2, sort_keys=True))
        return 1
    status = json.loads(text)
    report["contract"] = status.get("contract")
    report["read_only"] = bool(status.get("read_only"))
    report["authority_effect"] = status.get("authority_effect")
    report["task"] = {
        "task_id": (status.get("task") or {}).get("task_id", ""),
        "state": (status.get("task") or {}).get("lifecycle_state", ""),
        "revision": (status.get("task") or {}).get("repository_revision", ""),
    }
    report["validation"] = (status.get("verification") or {}).get("last_validation", {})
    report["proof"] = (status.get("verification") or {}).get("proof", {})
    report["gate"] = status.get("authority", {})
    cursor = (status.get("events") or {}).get("cursor") or {}
    report["cursor"] = cursor

    arguments = ["host-events", "--run-root", args.run_root, "--json"]
    if saved.get("cursor"):
        arguments.extend(["--cursor", json.dumps(saved["cursor"])])
    code, page_text = call(ariadne, *arguments)
    if code != 0:
        report["problems"].append(page_text.strip()[-500:])
        report["events"] = {"status": "REFUSED"}
    else:
        page = json.loads(page_text)
        seen = {str(item) for item in saved.get("seen_event_ids") or []}
        duplicate = [
            row.get("event_id") for row in page.get("events") or []
            if str(row.get("event_id")) in seen
        ]
        report["events"] = {
            "status": page.get("status"),
            "count": len(page.get("events") or []),
            "duplicate_event_ids": duplicate,
            "next_cursor": page.get("next_cursor"),
        }
        if duplicate:
            report["problems"].append("the resumed cursor replayed an event the host already processed")
        saved["cursor"] = page.get("next_cursor")
        seen.update(str(row.get("event_id")) for row in page.get("events") or [])
        saved["seen_event_ids"] = sorted(seen)[-300:]

    # A malformed cursor must be refused, never treated as "start over".
    bad_cursor = {"schema_version": "ariadne-host-event-cursor-1", "seq": 999999, "digest": "0" * 64}
    code, bad_text = call(
        ariadne, "host-events", "--run-root", args.run_root, "--json",
        "--cursor", json.dumps(bad_cursor),
    )
    if code == 0:
        report["problems"].append("a stale cursor was accepted")
    else:
        try:
            report["refused_cursor"] = json.loads(bad_text).get("status")
        except json.JSONDecodeError:
            report["refused_cursor"] = "REFUSED"

    # Read-only means no approval/acceptance command was available through this
    # consumer. The consumer never invokes one; it asserts the surface's own
    # statement so an accidental write endpoint would be visible here.
    if report["authority_effect"] != "none":
        report["problems"].append("the host surface reported an authority effect")
    if report["gate"].get("authority_effect") != "none":
        report["problems"].append("the authority block reported an authority effect")
    if not report["read_only"]:
        report["problems"].append("the host surface did not declare itself read-only")

    saved["runs"] = report["run_count"]
    saved["last_proof"] = str((report.get("proof") or {}).get("proof_id", ""))
    save(state_path, saved)
    report["status"] = "OK" if not report["problems"] else "PROBLEMS"
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(f"Host consumer: {report['status']}")
        print(f"Task: {report['task']['task_id']} ({report['task']['state']})")
        print(f"Gate: {report['gate'].get('pending_gate') or 'none'}")
        print(f"Events: {report['events'].get('count')}")
    return 0 if not report["problems"] else 1


if __name__ == "__main__":
    sys.exit(main())
