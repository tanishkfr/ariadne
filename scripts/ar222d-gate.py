#!/usr/bin/env python3
"""The AR-222D gate: mutation state, test inventory, and the three new suites.

Three checks that must pass before anything is committed or released:

```text
1. NO ACTIVE MUTATION      fail closed if the tree is mid-edit, by us or by a killed harness
2. TEST INVENTORY          named critical guarantees present, and no suite below its floor
3. AR-222D SUITES          the design grammar, its mutations, and the adversarial review
```

Each answers a question the previous phase could not:

**1** answers *"is the repository safe to record?"* AR-222's finding was that a mutated
engine could be committed and the corruption would be invisible to ``git diff`` when the
file was untracked. :func:`mutation_ledger.assert_no_active_mutation` refuses instead, and
an unreadable ledger counts as active because unknown is not clear.

**2** answers *"did we lose a guarantee?"* AR-222 watched a real test disappear while the
suite reported green. The named inventory catches that by name; the recorded floors catch
the unnamed losses no manifest can enumerate. Neither replaces the other: a count can fall
because a case was renamed or merged, and a manifest cannot list every case that matters.

**3** is the phase's own work, run here so a single command reports the whole thing.

Exit codes are distinct so a caller can tell them apart: ``1`` a mutation is active, ``2``
inventory loss, ``3`` a suite failure.
"""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from harness import mutation_ledger, test_inventory  # noqa: E402

AR222D_SUITES = ("test-ar222d", "test-ar222d-mutations", "test-ar222d-adversarial")

#: Suites whose output the inventory check reads. Only the AR-222D suites and the AR-222
#: rendered-critique suite are named here; the full regression is ``scripts/check.py``'s job
#: and duplicating it here would create two places to forget to update.
INVENTORY_SUITES = (
    "test-ar222d",
    "test-rendered-critique",
    "test-rendered-critique-adversarial",
)


def run_suite(name: str) -> tuple[str, int, float]:
    start = time.monotonic()
    completed = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / f"{name}.py")],
        cwd=str(ROOT), capture_output=True, text=True,
        timeout=5400, shell=False, stdin=subprocess.DEVNULL,
    )
    elapsed = round(time.monotonic() - start, 2)
    return (completed.stdout or "") + (completed.stderr or ""), completed.returncode, elapsed


def main() -> int:
    print("ARIADNE 2.2 -- AR-222D GATE\n")

    print("== 1. mutation state ==")
    state = mutation_ledger.mutation_state(ROOT)
    if state["active"]:
        owners = sorted({str(row.get("harness", "unknown")) for row in state["entries"]})
        stale = sorted({str(row.get("harness", "unknown")) for row in state["stale_entries"]})
        print(f"FAIL  an active mutation blocks this gate ({state['count']} entr(y/ies))")
        print(f"      harnesses: {', '.join(owners) or 'unknown'}")
        if stale:
            print(f"      STALE (owning process is gone, run recovery): {', '.join(stale)}")
        print(f"      ledger: {state['ledger']}")
        if not state["known"]:
            print(f"      {state['reason']}")
        return 1
    print(f"ok    the tree is not mid-mutation ({state['ledger']})\n")

    print("== 2. test inventory ==")
    outputs: dict[str, str] = {}
    for name in INVENTORY_SUITES:
        output, code, elapsed = run_suite(name)
        outputs[name] = output
        verdict = test_inventory.parse_summary(output)
        print(f"  {name:<34} {verdict['passed']}/{verdict['total']} "
              f"green={verdict['green']} in {elapsed}s")
    corpus = test_inventory.corpus_text([ROOT / "scripts", ROOT / "src"])
    inventory = test_inventory.check_inventory(outputs, corpus=corpus)
    if not inventory["ok"]:
        for group, phrases in inventory["missing_named_guarantees"].items():
            print(f"FAIL  named guarantees missing from {group}:")
            for phrase in phrases:
                print(f"        - {phrase}")
        for row in inventory["floor_failures"]:
            print(f"FAIL  {row['suite']} has {row['observed_total']} cases, "
                  f"floor is {row['recorded_floor']} (short by {row['shortfall']})")
        for row in inventory.get("unparsed_summaries") or ():
            print(f"FAIL  {row['suite']} printed no parseable summary, so its recorded floor of "
                  f"{row['recorded_floor']} could not be checked. An unenforced floor is a failure.")
        for name in inventory.get("not_green") or ():
            print(f"FAIL  {name} is not green")
        return 2
    print(f"ok    {inventory['named_guarantees']} named guarantees present, "
          f"every suite at or above its recorded floor\n")

    print("== 3. AR-222D suites ==")
    failures: list[str] = []
    for name in AR222D_SUITES:
        output, code, elapsed = run_suite(name)
        summary = test_inventory.parse_summary(output)
        verdict = "ok  " if code == 0 else "FAIL"
        print(f"  {verdict} {name:<34} exit={code} in {elapsed}s")
        if code != 0:
            failures.append(name)
            for line in output.splitlines():
                if line.startswith(("FAIL", "ERROR", "SURVIVED", "skipped")):
                    print(f"        {line}")
    if failures:
        print(f"\nFAILED: {', '.join(failures)}")
        return 3
    print("\nAR-222D gate: green")
    print("  no active mutation, inventory intact, and all three AR-222D suites passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
