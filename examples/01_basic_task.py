"""Example 01: start a run and read it back through the public API."""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from ariadne_engine import public  # noqa: E402


def main() -> int:
    work = Path(tempfile.mkdtemp(prefix="ariadne-example-01-"))
    try:
        client = public.connect(ROOT)
        print(f"engine {client.version}")
        project = work / "demo-project"
        started = client.start_run(project=str(project), request="Build a small typographic experiment.")
        print("start:", started.exit_code)
        print(started.message.strip().splitlines()[0])
        status = client.status(project=str(project), as_json=True)
        print("status exit:", status.exit_code)
        try:
            view = json.loads(status.message)
        except ValueError:
            view = {}
        print("status fields:", sorted(view)[:8])
        print("run root:", project.parent / f"{project.name}-ariadne")
    finally:
        shutil.rmtree(work, ignore_errors=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
