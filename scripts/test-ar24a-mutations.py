#!/usr/bin/env python3
"""AR-24A mutation suite: does the 2.4A reliability suite actually bite?

A green suite proves the cases pass. It does not prove they would notice if one
of the 2.4A safeguards were deleted. Each mutation below removes or inverts one
load-bearing behaviour and the named tests must go red. A mutation that survives
is a boundary that is not being enforced, however many cases are green.

Boundaries attacked, in the order a correction would be forged:

```text
attempt identity                 parent/child correction linkage
validation revision binding      cross-attempt evidence isolation
review authorization            reviewer independence (label and execution)
review freshness                 stale revision at review ingress
scope containment                review-correction budget (T1 and S4B)
recovery idempotency             interrupted worker treated as successful
failed validation treated as a pass
proof-receipt integrity          human acceptance authority
```

Two properties of the harness itself, borrowed from AR-222D because they were
learned the hard way:

**Transactional.** Every mutation runs inside
:func:`harness.mutation_ledger.mutation_transaction`, which captures the bytes
before editing, stashes them, registers in the shared ledger, and restores and
verifies them in a ``finally``. Restoration is verified by digest, not by an
empty ``git diff``.

**Isolated.** Run this from a disposable worktree. It edits the implementation
it lives in, and although the ledger restores it even on an exception, the only
way to make "the authoritative repository is never mutated" true by
construction is to point the harness at a copy.

Usage:
    python scripts/test-ar24a-mutations.py [--report <path>] [--keep-going]

Exit: 0 only when every valid mutation was killed and restoration was proven.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from harness import mutation_ledger  # noqa: E402

HARNESS = "ar24a-mutations"
ENGINE = ROOT / "src" / "ariadne_engine"
CLI = ROOT / "scripts" / "ariadne.py"
AR24A = ROOT / "scripts" / "test-ar24a.py"


def test(script: Path, *cases: str) -> dict:
    return {"script": str(script), "cases": list(cases)}


MUTATIONS: list[dict] = [
    # -- validation revision binding -----------------------------------------
    {
        "id": "M01",
        "boundary": "validation revision binding",
        "rule": "a validation from an earlier implementation revision is accepted as current",
        "edits": [{
            "path": ENGINE / "task_execution.py",
            "before": '        elif recorded != str(current_fingerprint):',
            "after": '        elif False:  # mutation: revision drift is ignored',
        }],
        "tests": [test(AR24A, "stale_validation_is_refused_by_review_and_proof")],
        "why": (
            "the fingerprint is the only thing that distinguishes 'validated on this tree' from "
            "'validated before someone edited it'. Removing the mismatch branch reuses an old pass."
        ),
    },
    {
        "id": "M02",
        "boundary": "cross-attempt evidence isolation",
        "rule": "a validation record copied from another attempt is accepted",
        "edits": [{
            "path": ENGINE / "task_execution.py",
            "before": (
                '    if str(record.get("packet_id", "")) != str(attempt.get("packet_id", "")):\n'
                '        return False\n'
                '    attempt_name = str(record.get("attempt_id", ""))\n'
                '    if attempt_name and attempt_name != str(attempt.get("attempt_id", "")):\n'
                '        return False\n'
                '    execution = dict(record.get("execution") or {})\n'
                '    implementing = str(execution.get("implementing_execution", ""))\n'
                '    attempt_execution = str(attempt.get("execution_id", ""))\n'
                '    if implementing and attempt_execution and implementing != attempt_execution:\n'
                '        return False\n'
                '    return True'
            ),
            "after": '    return True  # mutation: evidence from any attempt is accepted',
        }],
        "tests": [test(AR24A, "cross_attempt_validation_evidence_is_refused")],
        "why": (
            "packet, attempt and implementing execution are the three identities that make a "
            "validation belong to one attempt. Removing all three is 'accept the other attempt's proof'."
        ),
    },
    {
        "id": "M03",
        "boundary": "reviewer independence",
        "rule": "the implementer's own identity can review its work",
        "edits": [
            {
                "path": CLI,
                "before": '    if identity and (identity in task_workers or identity in worker_identities):',
                "after": '    if False and identity and (identity in task_workers or identity in worker_identities):',
            },
            {
                "path": ENGINE / "review.py",
                "before": '    elif identity.lower() in worker_identities(state):',
                "after": '    elif False and identity.lower() in worker_identities(state):',
            },
        ],
        "tests": [test(AR24A, "forged_reviewer_identity_is_refused_without_leaving_an_open_execution")],
        "why": (
            "both label checks are removed together. The engine-execution checks remain, so this "
            "tests the identity half of independence rather than replacing it."
        ),
    },
    {
        "id": "M04",
        "boundary": "review freshness",
        "rule": "a review is ingested against a revision whose validation is stale",
        "edits": [{
            "path": CLI,
            "before": (
                '    if stale:\n'
                '        raise RuntimeError_(\n'
                '            "Independent review rejected: the validated revision is no longer current: "\n'
                '            + "; ".join(stale)\n'
                '        )'
            ),
            "after": (
                '    if False:  # mutation: a stale revision can be reviewed\n'
                '        raise RuntimeError_(\n'
                '            "Independent review rejected: the validated revision is no longer current: "\n'
                '            + "; ".join(stale)\n'
                '        )'
            ),
        }],
        "tests": [test(AR24A, "stale_validation_is_refused_by_review_and_proof")],
        "why": (
            "a review of a revision that has moved is evidence of nothing. The gate must run before "
            "a reviewer execution exists, or a refused review leaves a phantom session behind."
        ),
    },
    # -- correction authorization and scope ----------------------------------
    {
        "id": "M05",
        "boundary": "scope containment",
        "rule": "a correction may widen the task's declared scope",
        "edits": [{
            "path": ENGINE / "task_execution.py",
            "before": '    if parent_digest and parent_digest != expected:',
            "after": '    if False and parent_digest and parent_digest != expected:',
        }],
        "tests": [test(AR24A, "out_of_scope_correction_is_refused_before_a_packet_is_prepared")],
        "why": (
            "the scope digest is what ties a correction to the authorization granted for the "
            "original work; without it the task record becomes a permission channel."
        ),
    },
    {
        "id": "M06",
        "boundary": "review-correction budget (T1)",
        "rule": "review-directed corrections never exhaust their budget",
        "edits": [{
            "path": ENGINE / "task_execution.py",
            "before": (
                '    return sum(\n'
                '        1\n'
                '        for attempt in (task or {}).get("attempts") or ()\n'
                '        if str(attempt.get("repair_kind", "")) == "review"\n'
                '    )'
            ),
            "after": '    return 0  # mutation: the review budget never counts',
        }],
        "tests": [test(AR24A, "two_sequential_review_corrections_are_bounded_and_reviewable")],
        "why": "an unbounded review loop spends the operator's subscription without a human decision.",
    },
    {
        "id": "M07",
        "boundary": "parent/child correction linkage",
        "rule": "a corrective attempt loses its parent attempt identity",
        "edits": [{
            "path": ENGINE / "task_execution.py",
            "before": '        "parent_attempt_id": str(parent_attempt_id),',
            "after": '        "parent_attempt_id": "",  # mutation: the correction is detached from its parent',
        }],
        "tests": [test(AR24A, "failed_review_produces_a_linked_correction_and_fresh_validation")],
        "why": (
            "a correction that does not name its parent cannot be distinguished from a fresh "
            "attempt, and its review authorization stops being traceable."
        ),
    },
    {
        "id": "M08",
        "boundary": "review authorization (S4B)",
        "rule": "a passing S4B review authorizes a correction",
        "edits": [{
            "path": ENGINE / "policy.py",
            "before": (
                '    if str(review.get("outcome")) != "failed":\n'
                '        return [\n'
                '            f"the current review outcome is {review.get(\'outcome\') or \'unrecorded\'}; only a failed review "\n'
                '            "authorizes a corrective revision"\n'
                '        ]'
            ),
            "after": (
                '    if False:  # mutation: any review authorizes a correction\n'
                '        return [\n'
                '            f"the current review outcome is {review.get(\'outcome\') or \'unrecorded\'}; only a failed review "\n'
                '            "authorizes a corrective revision"\n'
                '        ]'
            ),
        }],
        "tests": [test(AR24A, "s4b_review_correction_contract_is_bounded_and_review_authorized")],
        "why": (
            "only a failed review with 'fix and re-review' is a correction instruction. A passing "
            "review authorizing a rerun is how a gate becomes a suggestion."
        ),
    },
    {
        "id": "M09",
        "boundary": "review-correction budget (S4B)",
        "rule": "the S4B correction count is always zero",
        "edits": [{
            "path": ENGINE / "policy.py",
            "before": (
                '                count += 1\n'
                '                break\n'
                '    return count'
            ),
            "after": (
                '                count += 1\n'
                '                break\n'
                '    return 0  # mutation: the S4B correction budget never counts'
            ),
        }],
        "tests": [test(AR24A, "s4b_review_correction_contract_is_bounded_and_review_authorized")],
        "why": "the S4B and T1 budgets are separate; making the S4B one invisible removes its bound.",
    },
    # -- evidence status and proof integrity ---------------------------------
    {
        "id": "M10",
        "boundary": "validation revision binding (reported state)",
        "rule": "stale evidence is reported as validated instead of stale-evidence",
        "edits": [{
            "path": ENGINE / "task_execution.py",
            "before": (
                '    if evidence_current is False and (\n'
                '        task.get("proof") or str(attempt.get("state", "")) == "validated"\n'
                '    ):\n'
                '        return "stale-evidence"'
            ),
            "after": (
                '    if False and evidence_current is False and (\n'
                '        task.get("proof") or str(attempt.get("state", "")) == "validated"\n'
                '    ):\n'
                '        return "stale-evidence"'
            ),
        }],
        "tests": [test(AR24A, "stale_validation_is_refused_by_review_and_proof")],
        "why": (
            "the gate can refuse and the status still lie. task-status is what an operator and the "
            "MCP surface read, so a stale revision must be named there too."
        ),
    },
    {
        "id": "M11",
        "boundary": "interrupted worker treated as successful",
        "rule": "an open/running worker is reported as validated",
        "edits": [{
            "path": ENGINE / "task_execution.py",
            "before": '    if state_value == "running":\n        return "worker-running"',
            "after": '    if state_value == "running":\n        return "validated"',
        }],
        "tests": [test(AR24A, "real_subprocess_interruption_during_worker_execution_recovers_safely")],
        "why": (
            "a killed worker did not finish. Reporting it as validated turns a missing observation "
            "into a passing one, which is the failure the recovery design exists to prevent."
        ),
    },
    {
        "id": "M12",
        "boundary": "failed validation treated as a pass",
        "rule": "a failed attempt is reported as validated",
        "edits": [{
            "path": ENGINE / "task_execution.py",
            "before": '        return "repair-pending" if validation.get("retryable") else "blocked"',
            "after": '        return "validated"  # mutation: a failed attempt looks validated',
        }],
        "tests": [test(AR24A, "correction_that_fails_validation_cannot_become_accepted")],
        "why": "the latest attempt is authoritative; an older pass must never rescue a fresh failure.",
    },
    {
        "id": "M13",
        "boundary": "proof receipt integrity",
        "rule": "a proof receipt whose digest no longer binds its contents is accepted",
        "edits": [{
            "path": ENGINE / "proof.py",
            "before": (
                '    else:\n'
                '        if receipt_digest(record) != digest:\n'
                '            problems.append("proof receipt digest does not bind its contents")'
            ),
            "after": (
                '    else:\n'
                '        if False:  # mutation: the digest is decorative\n'
                '            problems.append("proof receipt digest does not bind its contents")'
            ),
        }],
        "tests": [test(ROOT / "scripts" / "test-ar224.py")],
        "why": (
            "the receipt digest is the integrity check, not a signature. Removing it lets a tampered "
            "verdict keep its old digest and still be read as proof."
        ),
    },
    {
        "id": "M14",
        "boundary": "proof receipt integrity (store lookup)",
        "rule": "a receipt id absent from the durable store is accepted",
        "edits": [{
            "path": ENGINE / "proof.py",
            "before": (
                '    for row in _existing(state):\n'
                '        if str(row.get("proof_id", "")) == str(proof_id):\n'
                '            return row\n'
                '    return None'
            ),
            "after": (
                '    for row in _existing(state):\n'
                '        if str(row.get("proof_id", "")) == str(proof_id):\n'
                '            return row\n'
                '    return {"proof_id": str(proof_id), "task_id": ""}  # mutation: a forged id resolves'
            ),
        }],
        "tests": [test(AR24A, "forged_proof_receipt_in_task_state_cannot_mint_acceptance")],
        "why": (
            "task state can name any proof id. The durable receipt store is the authority; a fallback "
            "that invents a record makes the state field self-certifying."
        ),
    },
    # -- recovery idempotency and reviewer execution independence ------------
    {
        "id": "M15",
        "boundary": "recovery idempotency",
        "rule": "resuming a completed task mints a second proof receipt",
        "edits": [{
            "path": CLI,
            "before": (
                '    if TASKX.proof_is_current(task):\n'
                '        # Resuming a task whose engine determination is already recorded must not\n'
                '        # mint a second receipt: the first one stays the record of this revision.\n'
                '        return 0, "The engine\'s determination is already recorded; the human acceptance decision remains (task-accept)."'
            ),
            "after": (
                '    if False:  # mutation: resume mints another receipt\n'
                '        # Resuming a task whose engine determination is already recorded must not\n'
                '        # mint a second receipt: the first one stays the record of this revision.\n'
                '        return 0, "The engine\'s determination is already recorded; the human acceptance decision remains (task-accept)."'
            ),
        }],
        "tests": [test(AR24A, "unchanged_passing_attempt_is_not_rerun_or_repaired")],
        "why": (
            "a repeated run is the normal resume path. Minting a second receipt rewrites the record "
            "of a revision that did not change and breaks proof history."
        ),
    },
    {
        "id": "M16",
        "boundary": "reviewer independence (engine execution)",
        "rule": "the reviewer and implementer may be the same engine execution",
        "edits": [{
            "path": ENGINE / "review.py",
            "before": '    if str(reviewer_execution) and str(reviewer_execution) == str(implementing_execution):',
            "after": '    if False and str(reviewer_execution) and str(reviewer_execution) == str(implementing_execution):',
        }],
        "tests": [test(ROOT / "scripts" / "test-engine-core.py")],
        "why": (
            "labels can be chosen; execution ids are minted by the engine. This is the stronger half "
            "of independence and the half a worker cannot forge."
        ),
    },
    {
        "id": "M17",
        "boundary": "human acceptance authority",
        "rule": "the engine supplies a human identity and records acceptance",
        "edits": [
            {
                "path": CLI,
                "before": '    task_accept_p.add_argument("--identity", required=True, help="the human making the decision")',
                "after": '    task_accept_p.add_argument("--identity", default="engine", help="the human making the decision")',
            },
            {
                "path": CLI,
                "before": (
                    '    if not identity:\n'
                    '        raise RuntimeError_("--identity must name the human making the decision; the engine cannot mint it")'
                ),
                "after": (
                    '    if not identity:\n'
                    '        identity = "engine"  # mutation: the engine supplies the human'
                ),
            },
        ],
        "tests": [test(AR24A, "acceptance_cannot_be_minted_without_a_human_identity")],
        "why": (
            "a gate an agent can satisfy by naming itself is not a gate. Both the CLI requirement and "
            "the runtime check are removed so the only remaining defense is the test."
        ),
    },
]


# --------------------------------------------------------------- runner

def _spec_key(spec: dict) -> tuple[str, tuple[str, ...]]:
    return (spec["script"], tuple(spec["cases"]))


def _spec_command(spec: dict) -> list[str]:
    return [sys.executable, spec["script"], *spec["cases"]]


def run_spec(spec: dict, timeout: int = 300) -> tuple[bool, str]:
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["NO_COLOR"] = "1"
    try:
        completed = subprocess.run(
            _spec_command(spec), cwd=str(ROOT), capture_output=True, text=True,
            timeout=timeout, env=env, shell=False, stdin=subprocess.DEVNULL,
        )
    except subprocess.TimeoutExpired:
        return False, f"TIMEOUT after {timeout}s"
    tail = (completed.stdout or "")[-2500:] + (completed.stderr or "")[-1500:]
    return completed.returncode == 0, tail


def apply_edits(edits: list[dict]) -> tuple[dict[Path, str], list[str]]:
    """Return the mutated texts and the reasons any edit could not be applied."""
    texts: dict[Path, str] = {}
    problems: list[str] = []
    for edit in edits:
        path = Path(edit["path"])
        if path not in texts:
            if not path.is_file():
                problems.append(f"no such file: {path}")
                continue
            texts[path] = path.read_text(encoding="utf-8")
        original = texts[path]
        count = original.count(edit["before"])
        if count != 1:
            problems.append(
                f"anchor occurs {count} times in {path.name} (want exactly 1): {edit['before'][:70]!r}"
            )
            continue
        texts[path] = original.replace(edit["before"], edit["after"], 1)
    return texts, problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", default="", help="write the JSON report here")
    parser.add_argument("--keep-going", action="store_true",
                        help="continue after a survivor (still exits non-zero)")
    parser.add_argument("--only", action="append", default=[], help="run only these mutation ids")
    args = parser.parse_args(argv)

    selected = [m for m in MUTATIONS if not args.only or m["id"] in args.only]
    started = time.time()
    report = {
        "schema_version": 1,
        "harness": HARNESS,
        "repo": str(ROOT),
        "commit": subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=str(ROOT), capture_output=True, text=True
        ).stdout.strip(),
        "version": (ROOT / "VERSION").read_text(encoding="utf-8").strip(),
        "started_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "mutations": [],
        "baseline": [],
        "restoration": {},
        "summary": {},
    }

    # Every distinct test is green before any mutation is applied, otherwise a
    # red result cannot be attributed to the mutation.
    specs = {_spec_key(spec): spec for mutation in selected for spec in mutation["tests"]}
    print(f"baseline: {len(specs)} test command(s)")
    baseline_ok = True
    for key, spec in specs.items():
        passed, tail = run_spec(spec)
        report["baseline"].append({"script": spec["script"], "cases": spec["cases"], "passed": passed})
        print(f"  {'ok  ' if passed else 'FAIL'} {Path(spec['script']).name}"
              + (f" {' '.join(spec['cases'])}" if spec["cases"] else ""))
        if not passed:
            baseline_ok = False
            print(tail[-1200:])
    if not baseline_ok:
        print("\nthe baseline is not green; mutations cannot be judged")
        report["summary"] = {"verdict": "BASELINE_RED"}
        _write_report(args.report, report)
        return 1

    invalid: list[dict] = []
    survivors: list[dict] = []
    killed = 0
    valid = 0
    for mutation in selected:
        print(f"\n{mutation['id']}  {mutation['rule']}")
        texts, problems = apply_edits(mutation["edits"])
        if problems:
            print("  INVALID: " + "; ".join(problems))
            invalid.append({"id": mutation["id"], "rule": mutation["rule"], "problems": problems})
            continue

        paths = list(texts)
        changed = {path: text for path, text in texts.items() if path.read_text(encoding="utf-8") != text}
        if len(changed) != len(paths):
            missing = [str(p) for p in paths if p not in changed]
            print(f"  INVALID: the edit produced no byte change in {missing}")
            invalid.append({"id": mutation["id"], "rule": mutation["rule"],
                            "problems": [f"no byte change in {missing}"]})
            continue

        ledger_report: dict = {}
        try:
            with mutation_ledger.mutation_transaction(
                ROOT, harness=HARNESS, mutation_id=mutation["id"], targets=paths,
            ) as opened:
                for path, text in changed.items():
                    path.write_text(text, encoding="utf-8")
                applied = all(path.read_text(encoding="utf-8") == changed[path] for path in changed)
                if not applied:
                    raise mutation_ledger.MutationStateError(
                        "the mutated bytes could not be read back after the write"
                    )
                results = []
                for spec in mutation["tests"]:
                    passed, tail = run_spec(spec)
                    results.append({"script": spec["script"], "cases": spec["cases"],
                                    "passed": passed, "tail": tail[-1200:]})
                    if not passed:
                        break
            ledger_report = dict(opened)
        except mutation_ledger.MutationStateError as exc:
            print(f"  INVALID: harness refused the mutation: {exc}")
            invalid.append({"id": mutation["id"], "rule": mutation["rule"], "problems": [str(exc)]})
            continue

        restoration = ledger_report.get("restoration") or {}
        if not restoration.get("restored"):
            print(f"  HARNESS FAILURE: restoration not proven: {restoration.get('problems') or restoration}")
            survivors.append({"id": mutation["id"], "rule": mutation["rule"],
                              "cause": "restoration not proven", "results": results})
            continue
        valid += 1
        caught = any(not result["passed"] for result in results)
        report["mutations"].append({
            "id": mutation["id"],
            "boundary": mutation["boundary"],
            "rule": mutation["rule"],
            "why": mutation["why"],
            "targets": [str(path.relative_to(ROOT)) for path in paths],
            "applied": True,
            "caught": caught,
            "restored": True,
            "results": results,
        })
        if caught:
            killed += 1
            failing = next(result for result in results if not result["passed"])
            first = next((line for line in failing["tail"].splitlines()
                          if line.startswith(("FAIL", "ERROR", "AssertionError"))), "")
            print(f"  killed by {Path(failing['script']).name} {first}".rstrip())
        else:
            survivors.append({"id": mutation["id"], "rule": mutation["rule"], "results": results})
            print("  SURVIVED: every targeted test stayed green")
            if not args.keep_going:
                break

    print("\npost-mutation restoration check")
    restored_ok = True
    for key, spec in specs.items():
        passed, tail = run_spec(spec)
        if not passed:
            restored_ok = False
            print(f"  FAIL {Path(spec['script']).name}: {tail[-800:]}")
    report["restoration"] = {
        "tests_green_after_all_mutations": restored_ok,
        "ledger": str(mutation_ledger.ledger_path(ROOT)),
        "state": mutation_ledger.mutation_state(ROOT),
    }
    print(f"  {'ok  ' if restored_ok else 'FAIL'} all baseline tests green after restoration")

    report["summary"] = {
        "attempted": len(selected),
        "valid": valid,
        "killed": killed,
        "survived": len(survivors),
        "invalid": len(invalid),
        "restoration_proven": bool(restored_ok and not mutation_ledger.mutation_state(ROOT)["active"]),
        "verdict": (
            "PASS" if valid and killed == valid and not survivors and not invalid and restored_ok
            else "FAIL"
        ),
    }
    report["invalid"] = invalid
    report["survivors"] = survivors
    report["duration_seconds"] = round(time.time() - started, 1)

    print(f"\nattempted={len(selected)} valid={valid} killed={killed} "
          f"survived={len(survivors)} invalid={len(invalid)}")
    if survivors:
        print("survivors -- investigate; do not weaken or delete the mutation:")
        for row in survivors:
            print(f"  - {row['id']} {row['rule']}")
    if invalid:
        print("invalid mutations:")
        for row in invalid:
            print(f"  - {row['id']} {row.get('problems')}")
    print(f"verdict: {report['summary']['verdict']}")
    _write_report(args.report, report)
    return 0 if report["summary"]["verdict"] == "PASS" else 1


def _write_report(path_value: str, report: dict) -> None:
    if not path_value:
        return
    path = Path(path_value)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"report: {path}")


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:  # pragma: no cover - interruption path
        print("\ninterrupted; the mutation ledger names the stash, and the next run can restore it")
        raise
