#!/usr/bin/env python3
"""Mutation testing for the AR-221 suite.

A test that passes tells you nothing unless the code it exercises can fail. Each
mutation below breaks one rule in the engine and asserts that the AR-221 suite
notices. A surviving mutant is the serious outcome: it means a test documents a rule
it does not actually enforce.

Every mutation is a temporary source edit, reverted in a ``finally``. Nothing here
writes to the repository permanently, and a mutation that cannot be applied is
reported as *not caught* rather than as a pass.
"""

from __future__ import annotations

import importlib.util
import io
import json
import re
import subprocess
import sys
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ariadne_engine import contracts  # noqa: E402
from ariadne_engine.design_execution import (  # noqa: E402
    changes,
    execution,
    grounding,
    inventory,
    packet,
    plan,
    vertical_slice,
)

SUITE = ROOT / "scripts" / "test-design-execution.py"
CONTRACTS = ROOT / "src" / "ariadne_engine" / "contracts.py"
PLAN = ROOT / "src" / "ariadne_engine" / "design_execution" / "plan.py"
GROUNDING = ROOT / "src" / "ariadne_engine" / "design_execution" / "grounding.py"
INVENTORY = ROOT / "src" / "ariadne_engine" / "design_execution" / "inventory.py"
CHANGES = ROOT / "src" / "ariadne_engine" / "design_execution" / "changes.py"
EXECUTION = ROOT / "src" / "ariadne_engine" / "design_execution" / "execution.py"
PACKET_SRC = ROOT / "src" / "ariadne_engine" / "design_execution" / "packet.py"

MUTATIONS = [
    {
        "id": "M01",
        "rule": "project identity precedence is ignored",
        "target": CONTRACTS,
        "before": '    "PROJECT_IDENTITY": 80,',
        "after": '    "PROJECT_IDENTITY": 20,',
    },
    {
        "id": "M02",
        "rule": "the G1D approval check is skipped",
        "target": PLAN,
        "before": '    if str(direction_record.get("status", "")) != "approved":',
        "after": '    if False:',
    },
    {
        "id": "M03",
        "rule": "a candidate direction is treated as implementable",
        "target": PLAN,
        "before": '    if str(direction_record.get("status", "")) != "approved":',
        "after": '    if str(direction_record.get("status", "")) == "never":',
    },
    {
        "id": "M04",
        "rule": "a reference is treated as a direct implementation instruction",
        "target": CONTRACTS,
        "before": '    "REFERENCE_PRINCIPLE": 20,',
        "after": '    "REFERENCE_PRINCIPLE": 120,',
    },
    {
        "id": "M05",
        "rule": "the AVOID treatment loses its detectors",
        "target": PLAN,
        "before": '    found: list[str] = []\n    for key, signatures in _COUNTER_DETECTORS.items():',
        "after": '    found: list[str] = []\n    for key, signatures in {}:',
    },
    {
        "id": "M06",
        "rule": "an ADAPT treatment may forget its project anchor",
        "target": CONTRACTS,
        "before": 'if str(binding_row.get("treatment", "")) == "ADAPT" and not str(binding_row.get("project_anchor", "")).strip():',
        "after": 'if False:',
    },
    {
        "id": "M07",
        "rule": "a material ungrounded change is allowed",
        "target": GROUNDING,
        "before": '    result["verdict"] = "UNGROUNDED_DESIGN_CHANGE"\n    return result',
        "after": '    result["verdict"] = "GROUNDED"\n    return result',
    },
    {
        "id": "M08",
        "rule": "the grounding set is widened to any declared constraint",
        "target": GROUNDING,
        "before": "            for item in contracts.CATEGORY_GROUNDS_MATERIAL.get(str(row.get(\"category\", \"\")), ())\n        )\n    ]\n    if grounding:",
        "after": "            for item in contracts.CATEGORY_GROUNDS_MATERIAL.get(str(row.get(\"category\", \"\")), ())\n            for _item in ()\n        ) or [\"brand_color\"]\n    ]\n    if grounding:",
    },
    {
        "id": "M09",
        "rule": "an existing project component is replaced unnecessarily",
        "target": INVENTORY,
        "before": '    if candidates:\n        return {\n            "need": str(need),\n            "decision": "REUSE_PROJECT_COMPONENT",',
        "after": '    if candidates and False:\n        return {\n            "need": str(need),\n            "decision": "REUSE_PROJECT_COMPONENT",',
    },
    {
        "id": "M10",
        "rule": "an external registry component is selected without approval",
        "target": INVENTORY,
        "before": '    approval_id = str(approvals.get(str(need), "")).strip()\n    if approval_id:',
        "after": '    approval_id = str(approvals.get(str(need), "")).strip() or "apv_forged"\n    if approval_id:',
    },
    {
        "id": "M11",
        "rule": "a dependency may be installed from a reference",
        "target": INVENTORY,
        "before": '        "status": "APPROVED" if approved else "REFUSED_PENDING_HUMAN_G2",',
        "after": '        "status": "APPROVED",',
    },
    {
        "id": "M12",
        "rule": "reference provenance is dropped from a grounded change",
        "target": GROUNDING,
        "before": '    result["reference_ids"] = sorted({\n        str(reference_id)\n        for row in constraints\n        for reference_id in (row.get("reference_ids") or [])\n    })',
        "after": '    result["reference_ids"] = []',
    },
    {
        "id": "M13",
        "rule": "a requirement binding is dropped from the plan",
        "target": PLAN,
        "before": '        rows.append({\n            "binding": value,\n            "actionable": bool(statement.get("actionable", True)),',
        "after": '        continue\n        rows.append({\n            "binding": value,\n            "actionable": bool(statement.get("actionable", True)),',
    },
    {
        "id": "M14",
        "rule": "source validation is treated as visual acceptance",
        "target": EXECUTION,
        "before": '"acceptance": dict(acceptance or {"visual_acceptance": "NOT_CLAIMED", "reason": NOT_CLAIMED_REASON}),',
        "after": '"acceptance": dict(acceptance or {"visual_acceptance": "VERIFIED_BY_RENDERED_CHECK", "reason": NOT_CLAIMED_REASON, "rendered_check_id": "src"}),',
    },
    {
        "id": "M15",
        "rule": "an out-of-scope file modification is allowed",
        "target": EXECUTION,
        "before": "        elif not allowed_scope or not _within_scope(relative, allowed_scope):",
        "after": "        elif False:",
    },
    {
        "id": "M16",
        "rule": "a validation command bypasses the transport allowlist",
        "target": PLAN,
        "before": "        argv, reason = transport.safe_validation_argv(command)",
        "after": "        argv, reason = ([command], None)",
    },
    {
        "id": "M17",
        "rule": "an accessibility floor is outrankable by a reference",
        "target": PLAN,
        "before": '            if str(other.get("basis", "")) not in REFERENCE_SOURCED_BASES:\n                continue',
        "after": "            if False:\n                continue",
    },
    {
        "id": "M18",
        "rule": "an accessibility regression is downgraded to incidental",
        "target": GROUNDING,
        "before": '    lost = accessibility_regressions(str(before), str(after))\n    if lost:',
        "after": '    lost = []\n    if lost:',
    },
    {
        "id": "M19",
        "rule": "literal reference cloning is not detected",
        "target": GROUNDING,
        "before": '        if str(detector) in live_body and str(detector) not in prior',
        "after": "        if False:",
    },
    {
        "id": "M20",
        "rule": "a trace gap is filled in rather than reported",
        "target": CHANGES,
        "before": '    if verdict in ("GROUNDED", "GROUNDED_INCIDENTAL"):\n            continue\n        gaps.append(',
        "after": '    if True:\n            continue\n        gaps.append(',
    },
    {
        "id": "M21",
        # Raise the budget rather than freezing the counter. A true infinite loop is a
        # faithful mutation but never returns, so the harness waits out its full
        # timeout and the run costs forty minutes to learn something this learns in
        # seconds: the repair budget is not being enforced.
        "rule": "the design repair budget is not enforced",
        "target": EXECUTION,
        "before": "                                       repair_limit=_repair_limit())",
        "after": "                                       repair_limit=_repair_limit() + 50)",
    },
    {
        "id": "M22",
        "rule": "an invalid constraint id is believed",
        "target": GROUNDING,
        "before": "        if constraint_row is None:\n            result[\"verdict\"] = \"UNGROUNDED_DESIGN_CHANGE\"",
        "after": "        if constraint_row is None:\n            constraint_row = declared[0] if declared else {}",
    },
    {
        "id": "M23",
        "rule": "the reference transport budget stops binding",
        "target": PACKET_SRC,
        "before": "        if transported_bytes + size > MAX_TRANSPORTED_REFERENCE_BYTES:",
        "after": "        if False:",
    },
    {
        "id": "M24",
        "rule": "path containment stops checking for traversal",
        "target": GROUNDING,
        "before": '    if ".." in normalised.split("/"):\n        return True',
        "after": "    if False:\n        return True",
    },
    {
        "id": "M25",
        "rule": "context economics stops omitting uncited references",
        "target": PACKET_SRC,
        "before": "        if reference_id not in needed_reference_ids:",
        "after": "        if False:",
    },
]

PACKET_SRC = ROOT / "src" / "ariadne_engine" / "design_execution" / "packet.py"


def suite_passes() -> tuple[bool, str]:
    """Run the AR-221 suite in a fresh interpreter and report whether it stayed green."""
    try:
        completed = subprocess.run(
            [sys.executable, str(SUITE)], capture_output=True, text=True, cwd=str(ROOT), timeout=2400
        )
    except subprocess.TimeoutExpired:
        # A suite that never terminates has been caught as surely as one that fails.
        return False, "TIMEOUT: the suite did not terminate"
    tail = (completed.stdout or "")[-400:]
    return completed.returncode == 0, tail


RESTORE_MARKER = ROOT / ".ariadne-mutation-restore.json"
"""Where a mutation in flight records the bytes it replaced.

Written *before* the source is edited and deleted only after it is restored, so a run
that is interrupted - killed by a supervisor, a timeout, a laptop lid - can be
recovered on the next invocation.

This is not hypothetical. An interrupted run once left mutation M21 applied to
``execution.py``: the repair loop became ``attempt_index = attempt_index``, so the
suite ran forever. It was invisible to ``git diff`` because the file was untracked, and
cost a long detour into a phantom performance problem before the cause was spotted in
the source. A harness that edits files in place has to be able to undo itself.
"""


def recover_interrupted_mutation() -> list[str]:
    """Restore any mutation a previous interrupted run left applied."""
    if not RESTORE_MARKER.exists():
        return []
    try:
        record = json.loads(RESTORE_MARKER.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        RESTORE_MARKER.unlink(missing_ok=True)
        return []
    # A marker this harness does not recognise is not ours to act on, and must not be a
    # crash. Another harness may write the same filename with its own shape; reading it
    # as if it were ours raises TypeError and takes the whole engine-suites gate with it.
    # Leave it in place -- deleting another harness's recovery state would be worse -- and
    # say so, so the collision is visible rather than silently ignored.
    if not isinstance(record, dict) or not {"path", "contents"} <= set(record):
        print(
            f"note: {RESTORE_MARKER.name} is not in this harness's format; leaving it for "
            "whatever wrote it"
        )
        return []
    target = ROOT / record["path"]
    target.write_text(record["contents"], encoding="utf-8")
    RESTORE_MARKER.unlink(missing_ok=True)
    return [f"restored an interrupted mutation of {record['path']} ({record['mutation']})"]


def apply_mutation(mutation: dict) -> bool:
    path = mutation["target"]
    original = path.read_text(encoding="utf-8")
    if mutation["before"] not in original:
        return False
    RESTORE_MARKER.write_text(
        json.dumps({
            "path": str(path.relative_to(ROOT)),
            "mutation": mutation["id"],
            "contents": original,
        }),
        encoding="utf-8",
    )
    mutated = original.replace(mutation["before"], mutation["after"], 1)
    path.write_text(mutated, encoding="utf-8")
    mutation["__original"] = original
    return True


def restore(mutation: dict) -> None:
    if "__original" in mutation:
        mutation["target"].write_text(mutation.pop("__original"), encoding="utf-8")
    RESTORE_MARKER.unlink(missing_ok=True)


def main() -> int:
    recovered = recover_interrupted_mutation()
    for row in recovered:
        print(f"RECOVERED  {row}")
    if recovered:
        print()

    baseline_ok, baseline_tail = suite_passes()
    if not baseline_ok:
        print("The AR-221 suite is not green to begin with; mutations cannot be judged.")
        print(baseline_tail)
        return 1
    print("AR-221 suite green before mutation.\n")

    survivors: list[str] = []
    not_applied: list[str] = []
    caught = 0
    for mutation in MUTATIONS:
        applied = apply_mutation(mutation)
        if not applied:
            not_applied.append(f"{mutation['id']} {mutation['rule']}")
            print(f"NOT-APPLIED {mutation['id']}  {mutation['rule']}")
            continue
        try:
            still_green, tail = suite_passes()
        finally:
            restore(mutation)
        if still_green:
            survivors.append(f"{mutation['id']} {mutation['rule']}")
            print(f"SURVIVED     {mutation['id']}  {mutation['rule']}")
        else:
            caught += 1
            first_failure = ""
            for line in tail.splitlines():
                if line.startswith(("FAIL", "ERROR")):
                    first_failure = line.strip()
                    break
            print(f"caught       {mutation['id']}  {mutation['rule']}")
            if first_failure:
                print(f"             -> {first_failure}")

    print(f"\n{caught}/{len(MUTATIONS)} mutations caught")
    if survivors:
        print("\nSurvived - each of these is a rule no test actually enforces:")
        for row in survivors:
            print(f"  - {row}")
    if not_applied:
        print("\nNot applied - the source text these mutations target has moved:")
        for row in not_applied:
            print(f"  - {row}")
    if survivors or not_applied:
        return 1
    print("AR-221 design-execution mutation suite: every mutation caught")
    return 0


if __name__ == "__main__":
    sys.exit(main())