"""Example 02: an approval cannot be forced; the engine decides what binds one."""

from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from ariadne_engine import public  # noqa: E402


def main() -> int:
    work = Path(tempfile.mkdtemp(prefix="ariadne-example-02-"))
    try:
        client = public.connect(ROOT)
        project = work / "demo-project"
        client.start_run(project=str(project), request="Build a small typographic experiment.")
        attempt = client.approve_gate(
            project=str(project), gate="G1", identity="example-operator",
            note="Try to approve before the brief and direction exist.",
        )
        print("approval exit:", attempt.exit_code)
        print(attempt.message.strip())
        print(
            "\nThe engine records an approval only when the gate is pending and the bound "
            "revision is current; a document note never satisfies it."
        )
    finally:
        shutil.rmtree(work, ignore_errors=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
