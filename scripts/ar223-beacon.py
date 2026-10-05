#!/usr/bin/env python3
"""Run the AR-223 proof-pass slices and print what they actually decided.

Two slices, deliberately unlike each other:

```text
BEACON      real preserved history. The AR-222 results document is read and checked, and the
            requirements are decided from the evidence that document records. Nothing is
            improved: the log table reached 568px at 390px, so the responsive requirement is
            FAILED, and the keyboard requirement is UNPROVEN because history holds a build
            result and screenshots and nothing else.

REPAIR      a controlled fixture, clearly labelled as one. Pass 1 fails, the edit changes the
            work digest, the invalidation pass marks one requirement stale and proves another
            unaffected, one targeted check is selected, and pass 2 is accepted. This is not a
            rewrite of a real project's history; AR-222's own repair left its finding
            persistent and this milestone says so in both places.

Usage::

    python scripts/ar223-beacon.py                 # both slices
    python scripts/ar223-beacon.py --slice beacon
    python scripts/ar223-beacon.py --json out.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ariadne_engine.acceptance import beacon, gates  # noqa: E402


def beacon_slice() -> dict:
    state = beacon.beacon_state(str(ROOT))
    record = beacon.beacon_pass(state)
    print("== BEACON: real preserved history ==")
    print(f"   source  {state['beacon']['history']['path']}")
    print(f"   digest  {state['beacon']['work_digest']}")
    for row in record["acceptance_readiness"]["blocking"] + record["acceptance_readiness"]["non_blocking"]:
        print(f"   {row['verdict']:<13} {row['text'][:66]}")
    for row in record["claim_assessments"]:
        print(f"   {row['claim_verdict']:<13} claim by {row['actor']}: {row['statement'][:52]}")
    print(f"   state    {record['acceptance_state']}")
    print()
    for line in gates.explain(record["acceptance_readiness"]).splitlines():
        print(f"   {line}")
    print()
    return {"record": record, "state": state}


def repair_slice() -> dict:
    outcome = beacon.repair_slices(beacon.repair_state())
    print("== REPAIR: controlled fixture ==")
    for label, row in (("pass 1", outcome["pass_one"]), ("pass 2", outcome["pass_two"])):
        for item in row["acceptance_readiness"]["blocking"]:
            print(f"   {label}  {item['verdict']:<13} {item['text'][:60]}")
        print(f"   {label}  -> {row['acceptance_state']}")
    impacts = {row["requirement_id"][-6:]: row["impact"] for row in outcome["invalidation"]["impacts"]}
    print(f"   invalidation  {impacts}")
    print(f"   stale         {[item[-6:] for item in outcome['stale_requirement_ids']]}")
    print(f"   plan          {len(outcome['plan']['selected'])} targeted check(s), "
          f"cost {outcome['plan']['total_cost']}")
    print(f"   parser rerun  {outcome['parser_rerun']}")
    print(f"   readmitted    {len(outcome['parser_evidence_readmitted'])} evidence row(s) "
          "on a proved dependency fingerprint")
    print(f"   lineage       {[row.get('verdict') for row in outcome['lineage']]}")
    print()
    return outcome


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--slice", choices=("beacon", "repair"), action="append")
    parser.add_argument("--json")
    args = parser.parse_args()
    wanted = args.slice or ["beacon", "repair"]

    report: dict = {"version": beacon.BEACON_VERSION}
    if "beacon" in wanted:
        report["beacon"] = beacon_slice()
    if "repair" in wanted:
        report["repair"] = repair_slice()

    if args.json:
        target = Path(args.json)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(report, indent=2, sort_keys=True, default=str) + "\n",
                          encoding="utf-8")
        print(f"record: {target}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
