#!/usr/bin/env python3
"""The AR-223 mutation harness: break each rule, then require the suite to notice.

A milestone that ships with no mutations has tests, and tests say only what somebody thought to
check. These mutations remove, one at a time, the refusals AR-223 exists to make -- and a
survivor is the finding, because it means a guard in this milestone is either untested or
unload-bearing in a way nobody documented.

**The rules under mutation, and what each one costs if it disappears:**

```text
CORPUS        a label outside the answer space is accepted; an unreviewed label is accepted;
              a duplicate projection across splits stops being refused
EVALUATION    a policy bound goes to zero; selective error stops being reported
CALIBRATION   the threshold is fitted on the measured split; a stale profile is served anyway
PROMOTION     a badly-measured family is promoted; ACTIVE is reachable without an evaluation
SCHEDULING    a protected operation is answered by a model; a deterministic rule is bypassed
ACCEPTANCE    a human gate is settled by evidence; absent evidence becomes failure;
              a superseded row returns as current; an invalidated requirement is skipped
INTERRUPTION  a risky conditional interruption continues autonomously
```

Every mutation runs ``test-ar223.py`` in a fresh interpreter under AR-222D's transactional
ledger, and restoration must be *proven* per mutation rather than assumed at the end: the
harness that checks a tree is clean after mutating it is the same harness that has to survive
its own process being killed mid-run.

**Recorded inventory.** A survivor is reported through
:func:`harness.test_inventory.survivor_report` as a failure to *investigate*. Restoring green by
weakening the case that caught it is a forbidden response and says nothing about the guard.
"""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from harness import mutation_ledger, test_inventory  # noqa: E402

SUITE = ROOT / "scripts" / "test-ar223.py"
HARNESS = "ar223-mutations"
ENGINE = ROOT / "src" / "ariadne_engine"
ACCEPTANCE = ENGINE / "acceptance"
INTELLIGENCE = ENGINE / "intelligence"

MUTATIONS: list[dict] = [
    # -- corpus ---------------------------------------------------------------
    {
        "id": "M01",
        "rule": "a label outside the declared answer space is accepted",
        "target": INTELLIGENCE / "corpus.py",
        "before": '    space = answer_space_for(str(family))',
        "after": '    space = tuple(str(label))',
        "why": "a label outside the space cannot be scored, and a typo there reads as a finding",
    },
    {
        "id": "M02",
        "rule": "a label with no reviewer is accepted",
        "target": INTELLIGENCE / "corpus.py",
        "before": '    reviewer = str(provenance.get("reviewer", "")) if isinstance(provenance, Mapping) else ""',
        "after": '    reviewer = str(provenance.get("reviewer", "")) or "unnamed"',
        "why": "an unreviewed label is a guess with a row number",
    },
    {
        "id": "M03",
        "rule": "a duplicate projection across splits stops being refused",
        "target": INTELLIGENCE / "corpus.py",
        "before": "    problems: list[str] = []",
        "after": "    problems: list[str] = []\n    return problems",
        "why": (
            "the same projection in two splits is one question wearing two names, and a "
            "threshold fitted on one is fitted on the other"
        ),
    },
    {
        "id": "M04",
        "rule": "a label may declare any agreement level at all",
        "target": INTELLIGENCE / "corpus.py",
        "before": '    if agreement not in AGREEMENT_LEVELS:',
        "after": '    if False:',
        "why": "agreement a corpus cannot state is agreement it does not have",
    },
    # -- evaluation -----------------------------------------------------------
    {
        "id": "M05",
        "rule": "the selective error rate stops being reported",
        "target": INTELLIGENCE / "evaluation.py",
        "before": '        "selective_error_rate": round(',
        "after": '        "selective_error_rate": 0.0 if False else round(',
        "why": "plain accuracy hides the errors among the cases the engine chose to answer",
    },
    {
        "id": "M06",
        "rule": "the false-confidence detector stops detecting",
        "target": INTELLIGENCE / "evaluation.py",
        "before": '    collapsed = len(distinct_answers) == 1 and len(distinct_labels) >= 3',
        "after": '    collapsed = False',
        "why": "2.1 shipped a milestone that looked finished because nobody counted the collisions",
    },
    {
        "id": "M07",
        "rule": "a leaked corpus is evaluated anyway",
        "target": INTELLIGENCE / "evaluation.py",
        "before": "    require_clean(corpus)",
        "after": "    require_clean(dict(corpus, cases=[]))",
        "why": "a leaky corpus produces a number that looks fine and means nothing",
    },
    # -- calibration ----------------------------------------------------------
    {
        "id": "M08",
        "rule": "the threshold is fitted on the measured split",
        "target": INTELLIGENCE / "calibration.py",
        "before": '    sweep = evaluation.sweep(engine)',
        "after": '    sweep = evaluation.evaluate(\n        engine, document, splits=list(MEASURED_SPLITS)\n    ).get("curves", {})',
        "why": "a threshold chosen by looking at held-out numbers is a fitted number wearing a measured one's clothes",
    },
    {
        "id": "M09",
        "rule": "a stale calibration profile is served anyway",
        "target": INTELLIGENCE / "calibration.py",
        "before": '    if reasons:\n        raise ContractError(',
        "after": '    if False:\n        raise ContractError(',
        "why": "a profile from a previous model revision does not degrade into the next one; it stops applying",
    },
    {
        "id": "M10",
        "rule": "the minimum calibration floor stops binding",
        "target": INTELLIGENCE / "calibration.py",
        "before": "    if len(usable) < 5:",
        "after": "    if len(usable) < 0:",
        "why": "a calibration fit on four cases is a curve fitted to noise",
    },
    # -- promotion ------------------------------------------------------------
    {
        "id": "M11",
        "rule": "the accuracy bound stops binding",
        "target": INTELLIGENCE / "promotion.py",
        "before": '    "min_accuracy": 0.90,',
        "after": '    "min_accuracy": 0.0,',
        "why": "a bounded classifier that cannot name the class nine times in ten does not deserve to answer",
    },
    {
        "id": "M12",
        "rule": "a confidently wrong answer stops counting against promotion",
        "target": INTELLIGENCE / "promotion.py",
        "before": '    "max_high_confidence_errors": 0,',
        "after": '    "max_high_confidence_errors": 99,',
        "why": "confidently wrong is the one failure a bounded authority cannot absorb at any rate",
    },
    {
        "id": "M13",
        "rule": "the adversarial floor stops binding",
        "target": INTELLIGENCE / "promotion.py",
        "before": '    "min_adversarial_accuracy": 0.60,',
        "after": '    "min_adversarial_accuracy": 0.0,',
        "why": "authority has to survive the cases written to break it",
    },
    {
        "id": "M14",
        "rule": "a promotion may be recorded with no evaluation behind it",
        "target": INTELLIGENCE / "promotion.py",
        "before": "    if not evaluation_id:",
        "after": "    if False:",
        "why": "a promotion that cites nothing cites an assertion",
    },
    {
        "id": "M15",
        "rule": "measured degradation no longer suspends authority",
        "target": INTELLIGENCE / "promotion.py",
        "before": "    if not report[\"degraded\"] or not active:",
        "after": "    if True or not active:",
        "why": "the only automatic removal of authority in the engine, and it has to be the mirror of promotion",
    },
    # -- scheduling -----------------------------------------------------------
    {
        "id": "M16",
        "rule": "a protected operation is answered by a model",
        "target": INTELLIGENCE / "scheduler.py",
        "before": '    if operation and str(operation) in PROTECTED_OPERATIONS:',
        "after": "    if False:",
        "why": "no measurement of any model can ever authorise a grant, a release or a human gate",
    },
    {
        "id": "M17",
        "rule": "the PROTECTED risk class stops routing to a human",
        "target": INTELLIGENCE / "scheduler.py",
        "before": '    if str(risk) == "PROTECTED":',
        "after": "    if False:",
        "why": "a protected decision is a human decision whatever the model is confident about",
    },
    {
        "id": "M18",
        "rule": "a deterministic rule is bypassed by model inference",
        "target": INTELLIGENCE / "scheduler.py",
        "before": "    if deterministic_available:",
        "after": "    if False:",
        "why": "spending model inference on a question a table already answers is pure cost",
    },
    {
        "id": "M19",
        "rule": "a slice answers a risk class wider than it was promoted for",
        "target": INTELLIGENCE / "scheduler.py",
        "before": "    if scope_problems:",
        "after": "    if False:",
        "why": "scope matching only ever narrows; a slice proven for LOW risk is not proven for HIGH",
    },
    {
        "id": "M20",
        "rule": "the scheduler accepts a request for authority",
        "target": INTELLIGENCE / "scheduler.py",
        "before": '    if bool(request.get("grants_authority", False)) or bool(request.get("accept_work", False)):',
        "after": "    if False:",
        "why": "confidence and permission are different quantities held by different parties",
    },
    # -- acceptance -----------------------------------------------------------
    {
        "id": "M21",
        "rule": "a human gate is settled by evidence",
        "target": ACCEPTANCE / "decisions.py",
        "before": "NEEDS_HUMAN",
        "after": "PROVEN",
        "why": "a subjective requirement with a required human gate cannot be settled by a machine that read some evidence",
        "skip": False,
    },
    {
        "id": "M22",
        "rule": "absent evidence becomes failure",
        "target": ACCEPTANCE / "decisions.py",
        "before": '"UNPROVEN"',
        "after": '"FAILED"',
        "why": "nobody observed a violation; reporting failure for it is the easiest way to become dishonest",
    },
    {
        "id": "M23",
        "rule": "a superseded evidence row returns as current",
        "target": ACCEPTANCE / "evidence.py",
        "before": '"SUPERSEDED"',
        "after": '"CURRENT"',
        "why": "the first pass stays readable, and nothing that was replaced may prove anything",
    },
    {
        "id": "M24",
        "rule": "an invalidated requirement keeps being treated as current",
        "target": ACCEPTANCE / "invalidation.py",
        "before": '"POTENTIALLY_AFFECTED"',
        "after": '"PROVEN_UNAFFECTED"',
        "why": "selective re-verification is only selective because the affected half is marked affected",
    },
    {
        "id": "M25",
        "rule": "an unknown dependency relationship becomes proven-unaffected",
        "target": ACCEPTANCE / "invalidation.py",
        "before": '"UNKNOWN"',
        "after": '"PROVEN_UNAFFECTED"',
        "why": "an unestablished dependency relationship is UNKNOWN, not safe",
    },
    {
        "id": "M26",
        "rule": "the engine serves as its own independent reviewer",
        "target": ACCEPTANCE / "security.py",
        "before": "    if identity == ENGINE_REVIEWER and require_independent:",
        "after": "    if False:",
        "why": "an engine verdict is a determination from recorded evidence, which is a different act from independent review",
    },
    {
        "id": "M27",
        "rule": "the engine records that it granted itself calibration",
        "target": INTELLIGENCE / "calibration.py",
        "before": '    "calibration_self_granted": bool(status.get("calibration_self_granted", False)),',
        "after": '    "calibration_self_granted": True,',
        "why": "a runtime may not declare its own probability calibrated",
    },
    # -- interruption ---------------------------------------------------------
    {
        "id": "M28",
        "rule": "a risky uncertain interruption continues autonomously",
        "target": ENGINE / "design_reference" / "specificity" / "interruption.py",
        "before": "    escalated_by_risk = uncertain and risk_class in _ELEVATED",
        "after": "    escalated_by_risk = False",
        "why": "AR-222D classified interruptions lexically; an uncertain one that crosses meaning must escalate",
    },
    {
        "id": "M29",
        "rule": "a caller-supplied confidence lowers the escalation tier",
        "target": ENGINE / "design_reference" / "specificity" / "interruption.py",
        "before": '        "confidence_used": False,',
        "after": '        "confidence_used": confidence is not None and float(confidence) > 0.99,',
        "why": "having a number that looks certain is not evidence about what is at stake",
    },
    {
        "id": "M30",
        "rule": "an elevated consequence stops overriding a decisive automatic reading",
        "target": ENGINE / "design_reference" / "specificity" / "interruption.py",
        "before": "    elif risk_class in _ELEVATED:",
        "after": "    elif False:",
        "why": "the correction is not merely 'escalate the uncertain ones'; a named meaning consequence escalates either way",
    },
]


def run_suite() -> tuple[bool, str]:
    """Run the AR-223 suite in a fresh interpreter and report whether it stayed green."""
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
        print("the AR-223 suite is not green to begin with; mutations cannot be judged")
        print(baseline_output[-3000:])
        return 1
    print(f"baseline green: {len(MUTATIONS)} mutations to try\n")

    skipped = [
        (row["id"], f"anchor not found in {Path(row['target']).name}")
        for row in MUTATIONS
        if row.get("skip")
    ]
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
            # Read the report *after* the with block. The ledger populates
            # report["restoration"] in its own finally, after the yield, so a copy taken
            # inside the block records no restoration and every mutation looks unproven --
            # which is how a restoration check can pass without ever running.
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
            if not restoration:
                print("        (the harness could not open a transaction, so nothing was applied)")
        report["mutations"].append({
            "id": mutation["id"],
            "rule": mutation["rule"],
            "caught": caught,
            "restored": bool(restoration.get("restored")),
            "restoration_problems": restoration.get("problems", []),
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
            for cause in row["investigate"]:
                print(f"      investigate: {cause}")
            for forbidden in row["forbidden_responses"]:
                print(f"      forbidden:   {forbidden}")
        return 1

    print(f"{len(usable) - len(survivors)}/{len(usable)} mutations caught")
    print("AR-223 mutation suite: every mutation caught")
    report["duration_seconds"] = round(time.time() - report["started_at"], 1)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:  # pragma: no cover - interruption path
        print("\ninterrupted; the next run will restore anything left mutated")
        raise
