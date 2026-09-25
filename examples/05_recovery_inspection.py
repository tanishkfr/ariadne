"""Example 05: recovery inspection reports an interrupted write; it never repairs it."""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from ariadne_engine import persistence  # noqa: E402


def main() -> int:
    work = Path(tempfile.mkdtemp(prefix="ariadne-example-05-"))
    run_root = work / "demo-project-ariadne"
    packet = run_root / "demo-S1"
    packet.mkdir(parents=True)
    (packet / "manifest.json").write_text(json.dumps({"schema_version": 1}), encoding="utf-8")
    state = {
        "schema_version": 1,
        "run_id": "demo",
        "project": str(work / "demo-project"),
        "packets": [{"id": "demo-S1", "stage": "S1", "path": str(packet)}],
        "next": "Complete the brief.",
    }
    (run_root / "ariadne-run.json").write_text(json.dumps(state, indent=2), encoding="utf-8")
    (run_root / ".ariadne-run.json.deadbeef.tmp").write_text("{}", encoding="utf-8")

    report = persistence.recovery_report(run_root)
    print("status:", report["status"])
    for finding in report["findings"]:
        print("-", finding["kind"], "->", finding["effect"])
    print(
        "\nThe written state is intact; the leftover temporary file is reported so an "
        "operator can decide what to do with it."
    )
    shutil.rmtree(work, ignore_errors=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
