"""Example 03: the verification ladder, and an unsatisfied claim."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from ariadne_engine import verification  # noqa: E402


def main() -> int:
    work = Path(tempfile.mkdtemp(prefix="ariadne-example-03-"))
    artifact = work / "report.txt"
    artifact.write_text("the check ran\n", encoding="utf-8")
    state: dict = {}

    declared = verification.create(
        state,
        subject="example-task",
        claim="the artifact exists and contains what the task asked for",
        level="DECLARED",
        method="operator statement",
    )
    print("recorded level:", declared["level"])

    view = verification.status(state, subject="example-task")
    print("status:", json.dumps(view, indent=2, sort_keys=True)[:400])
    print(
        "\nA declaration is recorded, but it does not answer a claim that requires "
        "observed or reproduced evidence; promoting it needs a real record at that level."
    )
    import shutil

    shutil.rmtree(work, ignore_errors=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
