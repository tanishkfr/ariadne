#!/usr/bin/env python3
"""AR-224 mutation harness: break each Proof Pass rule, require the suite to notice."""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from harness import mutation_ledger, test_inventory  # noqa: E402

SUITE = ROOT / "scripts" / "test-ar224.py"
HARNESS = "ar224-mutations"
ENGINE = ROOT / "src" / "ariadne_engine"
PROOF = ENGINE / "proof.py"
MCP = ENGINE / "mcp.py"

MUTATIONS: list[dict] = [
    {
        "id": "M01",
        "rule": "UNPROVEN printed as PROVEN",
        "target": PROOF,
        "before": '    for verdict in ("PROVEN", "PARTIAL", "UNPROVEN", "FAILED", "NEEDS_HUMAN"):',
        "after": '    for verdict in ("PROVEN", "PROVEN", "PROVEN", "PROVEN", "PROVEN"):',
        "why": "a receipt that upgrades verdicts in print is a completion overclaim",
    },
    {
        "id": "M02",
        "rule": "NOT_ACCEPTED converted to success",
        "target": PROOF,
        "before": '    if acceptance_state == "ACCEPTED":\n        return CI_EXIT["ACCEPTED"]\n    return CI_EXIT["NOT_ACCEPTED"]',
        "after": '    return CI_EXIT["ACCEPTED"]',
        "why": "CI laundering a blocked receipt to green hides unresolved work",
    },
    {
        "id": "M03",
        "rule": "receipt overwritten instead of appended",
        "target": PROOF,
        "before": '            raise contracts.ContractError(f"receipt {receipt.get(\'proof_id\')} already stored; history is append-only")',
        "after": '            rows.clear()',
        "why": "history that overwrites destroys the audit of failures",
    },
    {
        "id": "M04",
        "rule": "receipt digest stops binding content",
        "target": PROOF,
        "before": "        if receipt_digest(record) != digest:",
        "after": "        if False:",
        "why": "a digest that never fires cannot detect tampering",
    },
    {
        "id": "M05",
        "rule": "unrelated receipts compare directly",
        "target": PROOF,
        "before": "    if _lineage_key(a) != _lineage_key(b):",
        "after": "    if False:",
        "why": "comparing unrelated lineages invents progress",
    },
    {
        "id": "M06",
        "rule": "MCP bypasses core engine",
        "target": MCP,
        "before": '    return api_module.verify_work_state(',
        "after": '    return {"proof_id": "VP-0001", "acceptance_state": "ACCEPTED"}  # noqa\n    _unused = api_module.verify_work_state(',
        "why": "an MCP that answers without the engine is a second implementation",
    },
    {
        "id": "M07",
        "rule": "MCP grants human approval",
        "target": MCP,
        "before": '    for forbidden in ("reviewer", "reviewer_identity", "human_approval", "human_acceptance",',
        "after": '    for forbidden in ():',
        "why": "authority minted by a transport is not human authority",
    },
    {
        "id": "M08",
        "rule": "worker identity treated as independent reviewer",
        "target": PROOF,
        "before": '    worker_identity: str = "worker",',
        "after": '    worker_identity: str = "independent_reviewer",',
        "why": "the worker cannot independently certify itself",
    },
    {
        "id": "M09",
        "rule": "share-safe receipt leaks absolute path",
        "target": PROOF,
        "before": '            return "<redacted-path>"',
        "after": '            return value',
        "why": "share-safe that leaks machine paths leaks the operator",
    },
    {
        "id": "M10",
        "rule": "active mutation allowed during release",
        "target": PROOF,
        "before": 'def verify_digest(receipt: Mapping[str, Any]) -> dict:',
        "after": 'def verify_digest(receipt: Mapping[str, Any]) -> dict:  # mutation-ok\n    assert True, "placeholder"',
        "why": "placeholder to keep the harness honest about restoration; replaced below",
    },
    {
        "id": "M11",
        "rule": "ambiguous contract silently chosen",
        "target": PROOF,
        "before": '        raise contracts.ContractError(\n            "more than one active contract matches; disambiguate explicitly, refusing to choose"\n        )',
        "after": '        return active[0]',
        "why": "silently choosing a task verifies the wrong work",
    },
    {
        "id": "M12",
        "rule": "empty request accepted",
        "target": PROOF,
        "before": '    if not str(task_text or "").strip():\n        raise contracts.ContractError("verify needs the original request text")',
        "after": '    task_text = task_text or "unspecified work"',
        "why": "verification without a request verifies nothing",
    },
    {
        "id": "M13",
        "rule": "proof id format not enforced",
        "target": PROOF,
        "before": "    if not PROOF_ID_RE.fullmatch(pid):",
        "after": "    if False:",
        "why": "a forged id that parses is a traversal waiting to happen",
    },
    {
        "id": "M14",
        "rule": "MCP unknown tool answered anyway",
        "target": MCP,
        "before": '    if name not in TOOLS:\n        raise contracts.ContractError(f"unknown MCP tool: {tool!r}")',
        "after": '    if False:\n        raise contracts.ContractError(f"unknown MCP tool: {tool!r}")',
        "why": "an unknown tool that answers invents a surface",
    },
    {
        "id": "M15",
        "rule": "oversized MCP payload reaches the engine",
        "target": MCP,
        "before": "    if len(text) > MAX_TEXT_CHARS:",
        "after": "    if False:",
        "why": "unbounded inputs become denial of service",
    },
    {
        "id": "M16",
        "rule": "command injection shapes pass through MCP",
        "target": MCP,
        "before": "    if _FORBIDDEN_CMD.search(text):",
        "after": "    if False:",
        "why": "a transport that passes shell shapes invites execution",
    },
    {
        "id": "M17",
        "rule": "common design pattern becomes hard banned",
        "target": PROOF,
        "before": '    # SUBJECTIVE-looking obligations still become EXPLICIT requirements;',
        "after": '    raise contracts.ContractError("common patterns banned")  # noqa\n    # SUBJECTIVE-looking obligations still become EXPLICIT requirements;',
        "why": "a house style ban is the opposite of specificity",
    },
    {
        "id": "M18",
        "rule": "G1D bypassed by auto-approval",
        "target": MCP,
        "before": '        "authority": "MCP cannot grant human approval, reviewer identity, or authorization_effect",',
        "after": '        "authority": "MCP grants approval",',
        "why": "auto-approval removes the principal creative interruption",
    },
    {
        "id": "M19",
        "rule": "ACTIVE profile grants authorization",
        "target": PROOF,
        "before": '        "previous_proof_id": previous_id,',
        "after": '        "previous_proof_id": previous_id,\n        "authorization_effect": "granted",',
        "why": "promotion never grants authority; a granted flag is a privilege escalation",
    },
    {
        "id": "M20",
        "rule": "global slop score introduced on receipts",
        "target": PROOF,
        "before": '    receipt["receipt_digest"] = receipt_digest(receipt)',
        "after": '    receipt["slop_score"] = 0.0\n    receipt["receipt_digest"] = receipt_digest(receipt)',
        "why": "a single score destroys requirement-level distinctions",
    },
]


def _fix_m10():
    for row in MUTATIONS:
        if row["id"] == "M10":
            row.update({
                "rule": "empty evidence observation accepted",
                "before": '    if not str(observation or "").strip():',
                "after": '    if False:',
                "target": ENGINE / "acceptance" / "evidence.py",
                "why": "evidence without an observation is an assertion",
            })


_fix_m10()


def run_suite() -> tuple[bool, str]:
    try:
        completed = subprocess.run(
            [sys.executable, str(SUITE)],
            cwd=str(ROOT), capture_output=True, text=True, timeout=1800,
            shell=False, stdin=subprocess.DEVNULL,
        )
    except subprocess.TimeoutExpired:
        return False, "TIMEOUT: the suite did not terminate"
    tail = (completed.stdout or "")[-3000:] + (completed.stderr or "")[-1500:]
    return completed.returncode == 0, tail


def main() -> int:
    report = {"started_at": time.time(), "suites": [], "mutations": [], "recoveries": []}
    baseline_ok, baseline_output = run_suite()
    report["suites"].append({"suite": SUITE.name, "verdict": "EXIT_0" if baseline_ok else "RED"})
    if not baseline_ok:
        print("the AR-224 suite is not green to begin with; mutations cannot be judged")
        print(baseline_output[-3000:])
        return 1
    print(f"baseline green: {len(MUTATIONS)} mutations to try\n")
    skipped: list[tuple[str, str]] = []
    usable = [row for row in MUTATIONS if not row.get("skip")]
    survivors: list[dict] = []
    for mutation in usable:
        path = Path(mutation["target"])
        if not path.is_file():
            skipped.append((mutation["id"], f"target missing: {path.name}"))
            continue
        original = path.read_text(encoding="utf-8")
        if mutation["before"] not in original:
            skipped.append((mutation["id"], f"anchor not found in {path.name}: {mutation['before'][:60]!r}"))
            continue
        mutated = original.replace(mutation["before"], mutation["after"], 1)
        ledger_report: dict = {}
        try:
            with mutation_ledger.mutation_transaction(
                ROOT, harness=HARNESS, mutation_id=mutation["id"], targets=[path],
            ) as opened:
                path.write_text(mutated, encoding="utf-8")
                passed, output = run_suite()
            ledger_report = dict(opened)
            caught = not passed
        except subprocess.TimeoutExpired:
            caught, output = True, "the mutated suite hung, which is a failure to pass"
        except mutation_ledger.MutationStateError as exc:
            caught, output = False, f"harness refused the mutation: {exc}"
        restoration = ledger_report.get("restoration") or {}
        if not restoration.get("restored"):
            problems = restoration.get("problems") or ["the transaction recorded no restoration report"]
            print(f"        HARNESS RESTORATION NOT PROVEN for {mutation['id']}: {problems}")
        report["mutations"].append({
            "id": mutation["id"], "rule": mutation["rule"], "caught": caught,
            "restored": bool(restoration.get("restored")),
        })
        if caught:
            print(f"caught  {mutation['id']}  {mutation['rule']}")
        else:
            survivors.append(test_inventory.survivor_report(mutation["rule"], caught=False))
            print(f"SURVIVED {mutation['id']}  {mutation['rule']}")
            for line in output.splitlines():
                if line.startswith(("FAIL", "ERROR")):
                    print(f"        {line}")
    print()
    for mutation_id, reason in skipped:
        print(f"skipped  {mutation_id}: {reason}")
    if skipped:
        print()
    if survivors:
        print(f"{len(survivors)} mutation(s) survived -- these boundaries are not enforced:")
        for row in survivors:
            print(f"  - {row['mutation']}")
        return 1
    print(f"{len(usable) - len(survivors)}/{len(usable)} mutations caught")
    print("AR-224 mutation suite: every mutation caught")
    report["duration_seconds"] = round(time.time() - report["started_at"], 1)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\ninterrupted; the next run will restore anything left mutated")
        raise
