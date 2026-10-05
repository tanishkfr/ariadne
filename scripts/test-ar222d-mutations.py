#!/usr/bin/env python3
"""The AR-222D mutation suite: does the AR-222D suite actually bite?

A green suite proves the cases pass. It does not prove they would notice if the guarantee
were removed. Each mutation below deletes or inverts one load-bearing behaviour and the
suite must go red; a mutation that survives is a boundary that is not being enforced,
whatever the test count says.

The nineteen, in the order they would be attacked:

```text
category pattern becomes a hard ban
three directions differ only by colour
own-slop omitted
content model created after layout
project identity loses to a generic reference
implementation registry treated as design authority
all sources queried regardless of need
browser-only provider marked API-capable
paid source treated as free/public
critic session changed silently mid-loop
implementation rationale leaks to the critic
requirement id dropped from a finding
repair history overwritten
record lookup returns a detached copy
scope enforcement becomes a no-op
self-review prevention becomes a no-op
active mutation sentinel ignored
repository considered restored with mutated untracked state
critical test removed but a count-only gate stays green
```

Two properties of the harness itself, because AR-222 found both failure modes here:

**Transactional.** Every mutation runs inside
:func:`harness.mutation_ledger.mutation_transaction`, which captures the bytes and the
expected state *before* editing, stashes them to disk, registers in a shared ledger, and
restores and verifies in a ``finally``. A crash, an exception or a timeout cannot leave a
mutated engine behind, and the restoration is verified by digest rather than by an empty
``git diff``.

**Recorded inventory.** A survivor is reported through
:func:`harness.test_inventory.survivor_report` as a failure to *investigate* -- missing
coverage, a broken mutation, or an invalid invariant -- with weakening or deleting the
mutation listed explicitly as a forbidden response. Restoring green by making the mutation
stop biting destroys the only evidence that one of those three is true.

The suite under mutation is ``test-ar222d.py``, which is fast and offline, so nineteen
mutations cost seconds rather than the ninety minutes the AR-222 suite takes.
"""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from harness import mutation_ledger, test_inventory  # noqa: E402

SUITE = ROOT / "scripts" / "test-ar222d.py"
HARNESS = "ar222d-mutations"
ENGINE = ROOT / "src" / "ariadne_engine"
SP = ENGINE / "design_reference" / "specificity"
RC = ENGINE / "rendered_critique"

MUTATIONS: list[dict] = [
    # -- category defaults must stay contextual --------------------------------
    {
        "id": "M01",
        "rule": "category pattern becomes hard ban",
        "target": SP / "defaults.py",
        "before": '    kept = [row for row in present if str(row.get("verdict")) == "EARNED"]',
        "after": '    kept = [row for row in present if str(row.get("verdict")) == "EARNED"]\n    kept, present = [], list(present)',
        "why": (
            "an earned pattern must stay earned. Dropping earned patterns out of the report is "
            "anti-slop analysis behaving like the blocklist it claims to avoid: it removes them "
            "precisely because they are recognisable, which is not the same as because they are wrong"
        ),
    },
    {
        "id": "M02",
        "rule": "a pattern with no valid case is allowed into the registry",
        "target": SP / "defaults.py",
        "before": '    if not [item for item in (record.get("valid_when") or []) if str(item).strip()]:',
        "after": '    if False:',
        "why": "a pattern with no valid_when is a ban wearing a pattern\'s clothes",
    },
    # -- divergence ------------------------------------------------------------
    {
        "id": "M03",
        "rule": "three directions differ only by colour",
        "target": SP / "concepts.py",
        "before": '    "richness_source",\n    "interaction_character",',
        "after": '    "interaction_character",',
        "why": (
            "colour is not a divergence axis. Leaving it out is what makes three identical options "
            "refusable as a choice; the mutant lets colour count as real divergence"
        ),
    },
    {
        "id": "M04",
        "rule": "the three-candidate floor stops binding",
        "target": SP / "concepts.py",
        "before": "    if len(rows) < MIN_CANDIDATES:",
        "after": "    if False:",
        "why": "two candidates is a choice already made",
    },
    {
        "id": "M05",
        "rule": "own-slop omitted",
        "target": SP / "defaults.py",
        "before": '    if not stated:\n        problems.append(',
        "after": '    if False:\n        problems.append(',
        "why": "a direction that cannot name its own attractor has not been examined closely enough",
    },
    # -- content before layout -------------------------------------------------
    {
        "id": "M06",
        "rule": "content model created after layout",
        "target": SP / "content.py",
        "before": "            if int(plan_order) >= int(layout_order):",
        "after": "            if False:",
        "why": (
            "content before layout is a constraint, not a preference. A layout committed before its "
            "content is a layout for content nobody has"
        ),
    },
    {
        "id": "M07",
        "rule": "a layout plan with no content model is accepted",
        "target": SP / "content.py",
        "before": '    if model is None:\n        problems.append(',
        "after": '    if False:\n        problems.append(',
        "why": "without this the ordering rule is optional, because the first gate is the model existing",
    },
    {
        "id": "M08",
        "rule": "lorem ipsum accepted as content evidence",
        "target": SP / "content.py",
        "before": "    filler = filler_findings(\" \".join(all_text))",
        "after": "    filler = []",
        "why": "a layout validated against filler has been validated against nothing",
    },
    # -- authority -------------------------------------------------------------
    {
        "id": "M09",
        "rule": "project identity loses to a generic reference",
        "target": SP / "sources.py",
        "before": "    merely_exists = bool(reason) and (",
        "after": "    merely_exists = False and bool(reason) and (",
        "why": (
            "a registry is a place to find primitives, not an authority. When the only "
            "justification is that a registry has it, the adoption is unjustified"
        ),
    },
    {
        "id": "M10",
        "rule": "implementation registry treated as design authority with no rationale",
        "target": SP / "sources.py",
        "before": '    if not reason:\n        return {\n            "ok": False,\n            "source_id": source_id,\n            "problem": "no adoption rationale was recorded",',
        "after": '    if not reason:\n        return {\n            "ok": True,\n            "source_id": source_id,\n            "problem": "",',
        "why": "a component earns its place by satisfying a requirement or a principle, never by existing",
    },
    # -- source selection ------------------------------------------------------
    {
        "id": "M11",
        "rule": "all sources queried regardless of need",
        "target": SP / "sources.py",
        "before": "    selected = selected[: max(1, int(limit))]",
        "after": "    selected = list(selected)  # no bound: consult everything that matched",
        "why": (
            "searching every source is the behaviour this exists to prevent: it is slow, it drowns "
            "the useful evidence in the irrelevant, and it makes 'we consulted 30 sources' look "
            "like diligence when the honest statement is 'we did not know which two mattered'"
        ),
    },
    {
        "id": "M12",
        "rule": "source selection ranks by name rather than usability",
        "target": SP / "sources.py",
        "before": '    selected.sort(key=lambda entry: (entry["_rank"], str(entry["source_id"])))',
        "after": '    selected.sort(key=lambda entry: (str(entry["source_id"]),))',
        "why": (
            "name-order selection makes a metered, key-gated, per-component-licence source outrank "
            "a public MIT one, which is the 'did not know which two mattered' outcome the need-driven "
            "model exists to avoid"
        ),
    },
    {
        "id": "M13",
        "rule": "a paid source is treated as free and public",
        "target": SP / "sources.py",
        "before": '        if str(row.get("access_mode")) == "paid":\n            skipped.append({',
        "after": '        if False:\n            skipped.append({',
        "why": "paid capability requires explicit authorization before use",
    },
    {
        "id": "M14",
        "rule": "browser-only provider marked API-capable",
        "target": SP / "sources.py",
        "before": '        if "BROWSER_ONLY" in (record.get("capabilities") or []):\n            problems.append(',
        "after": '        if False:\n            problems.append(',
        "why": (
            "a browser-only source cannot have an automated adapter. This is the exact "
            "contradiction that turns browser research into a fabricated integration"
        ),
    },
    {
        "id": "M15",
        "rule": "a registry entry stops being an integration",
        "target": SP / "sources.py",
        "before": '    if status == "ADAPTER_AVAILABLE":\n        if not str(record.get("adapter_id", "")).strip():',
        "after": '    if status == "ADAPTER_AVAILABLE":\n        if False:',
        "why": "a source with an available adapter must name it, or it is a claim rather than an integration",
    },
    # -- continuity and independence ------------------------------------------
    {
        "id": "M16",
        "rule": "critic session changed silently mid-loop",
        "target": RC / "continuity.py",
        "before": '    if str(session.get("mode")) == CONTINUITY_MODES[1] and not str(session.get("restart_reason", "")).strip():',
        "after": '    if False:',
        "why": "a silent reviewer switch looks like progress while re-litigating settled questions",
    },
    {
        "id": "M17",
        "rule": "implementation rationale leaks to the critic",
        "target": RC / "continuity.py",
        "before": '    for name in MEMORY_FORBIDDEN_FIELDS:\n        if name in memory:\n            problems.append(',
        "after": '    for name in MEMORY_FORBIDDEN_FIELDS:\n        if False:\n            problems.append(',
        "why": "continuity is not familiarity: a reviewer who knows how the work was done is not fresh eyes",
    },
    {
        "id": "M18",
        "rule": "self-review prevention becomes a no-op",
        "target": RC / "continuity.py",
        "before": "    if reviewer and implementer and reviewer == implementer:",
        "after": "    if False:",
        "why": "the worker may not certify itself, and continuity must not make that easier to hide",
    },
    # -- proof readiness -------------------------------------------------------
    {
        "id": "M19",
        "rule": "requirement id dropped from a finding is no longer a gap",
        "target": RC / "proof.py",
        "before": '        if not str(finding.get("requirement_id_on_finding", "")):',
        "after": '        if False:',
        "why": "AR-223 would have to guess which requirement an unattributed finding is about",
    },
    {
        "id": "M20",
        "rule": "repair history overwritten goes unreported",
        "target": RC / "proof.py",
        "before": '            if not before:\n                problems.append(',
        "after": '            if False:\n                problems.append(',
        "why": "a proof that cannot compare before to after proves nothing",
    },
    # -- harness integrity -----------------------------------------------------
    {
        "id": "M21",
        "rule": "record lookup returns detached copy where canonical mutation required",
        "target": RC / "refinement.py",
        "before": '    for row in plans(state):\n        if str(row.get("refinement_plan_id", "")) == str(refinement_plan_id):\n            return row\n    return None',
        "after": '    for row in plans(state):\n        if str(row.get("refinement_plan_id", "")) == str(refinement_plan_id):\n            return dict(row)\n    return None',
        "why": (
            "every write in the refinement module goes through this handle. A defensive copy here "
            "makes each of those writes vanish while still returning a plausible value"
        ),
    },
    {
        "id": "M22",
        "rule": "scope enforcement mutation becomes a no-op",
        "target": RC / "refinement.py",
        "before": '    outside = [item for item in changed if not any(contracts.path_matches(item, entry) for entry in allowed)]',
        "after": "    outside = []",
        "why": "a repair that touches files outside its allowed scope is not a bounded repair",
    },
    {
        "id": "M23",
        "rule": "active mutation sentinel ignored",
        "target": ROOT / "scripts" / "harness" / "mutation_ledger.py",
        "before": "    if not state[\"active\"]:\n        return",
        "after": "    if True:\n        return",
        "why": (
            "a commit over a mutated tree records a corrupted engine as though it were the real "
            "one, and the corruption is invisible to git when the file is untracked"
        ),
    },
    {
        "id": "M24",
        "rule": "unknown mutation state treated as clear",
        "target": ROOT / "scripts" / "harness" / "mutation_ledger.py",
        "before": '        "active": bool(entries) or not known,',
        "after": '        "active": bool(entries),',
        "why": "an unreadable ledger means the state is unknown, and unknown is not clear",
    },
    {
        "id": "M25",
        "rule": "repository considered restored with mutated untracked state",
        "target": ROOT / "scripts" / "harness" / "mutation_ledger.py",
        "before": '    for key, digest in (expected.get("untracked_inventory") or {}).items():',
        "after": '    for key, digest in ({} or {}).items():',
        "why": (
            "an empty git diff is equally consistent with restored, never-mutated, and a mutation to "
            "a path git does not track. This repository has both untracked and ignored fixtures, so "
            "the inventory is the only thing that can see them"
        ),
    },
    {
        "id": "M26",
        "rule": "critical test removed but a test-count-only gate stays green",
        "target": ROOT / "scripts" / "harness" / "test_inventory.py",
        "before": 'PASS_LINE = re.compile(r"^(?:PASS|FAILED)\\s+(?P<passed>\\d+)/(?P<total>\\d+)\\b", re.MULTILINE)',
        "after": 'PASS_LINE = re.compile(r"^(?:PASS|FAILED)\\s+(?P<passed>\\d+)/(?P<total>\\d+)\\b")',
        "why": (
            "without MULTILINE, `^` matches only the start of the output, so a PASS line on the last "
            "line of a suite that printed ninety results beforehand is invisible. The consequence is "
            "not a crash: it is an inventory check that reads every suite as having printed no "
            "summary at all, which quietly turns the floor check off"
        ),
    },
    {
        "id": "M27",
        "rule": "the recorded case floor stops catching an unnamed loss",
        "target": ROOT / "scripts" / "harness" / "test_inventory.py",
        "before": "        if summary[\"total\"] < floor:",
        "after": "        if False:",
        "why": "the count floor is the net that catches losses no named manifest can enumerate",
    },
    {
        "id": "M35",
        "rule": "an unparseable suite summary is read as a satisfied floor",
        "target": ROOT / "scripts" / "harness" / "test_inventory.py",
        "before": '        if summary["kind"] == "narrative" or not summary["total"]:',
        "after": "        if False:",
        "why": (
            "two suites print 'N/N passed' without a PASS prefix. When only the prefixed form was "
            "understood they reported 0/0, read as 'no floor violation', and passed silently -- "
            "the same failure shape as AR-222's vanished test, one level up"
        ),
    },
    # -- interruption ----------------------------------------------------------
    {
        "id": "M28",
        "rule": "routine refinement interrupts the user",
        "target": SP / "interruption.py",
        "before": "    if words & ROUTINE_VOCABULARY:\n        return \"AUTOMATIC\"",
        "after": "    if False:\n        return \"AUTOMATIC\"",
        "why": "the user must never be asked which component library, font or provider to use",
    },
    {
        "id": "M29",
        "rule": "meaning-change detection stops firing",
        "target": SP / "interruption.py",
        "before": "    if resolved == \"CONDITIONAL\" and triggered:",
        "after": "    if False:",
        "why": (
            "a bare meaning noun with no replacement verb must not fire, but a real paradigm change "
            "must -- and that asymmetry is only held by both halves of the rule"
        ),
    },
    {
        "id": "M30",
        "rule": "a meaning noun alone is treated as a meaning change",
        "target": SP / "interruption.py",
        "before": "    for verb in REPLACEMENT_VERBS:\n        if re.search(rf\"{re.escape(verb)}[^.]{{0,40}}{re.escape(noun)}\", text):",
        "after": "    for verb in REPLACEMENT_VERBS:\n        if True or re.search(rf\"{re.escape(verb)}[^.]{{0,40}}{re.escape(noun)}\", text):",
        "why": (
            "that makes every bare mention of 'design system' a meaning change, so the question the "
            "brief forbids -- 'which design system should I use' -- becomes the one question the "
            "policy raises"
        ),
    },
    # -- proposal --------------------------------------------------------------
    {
        "id": "M31",
        "rule": "internal provider identity leaks into the user-facing proposal",
        "target": SP / "proposal.py",
        "before": "    for field_name in INTERNAL_ONLY_FIELDS:\n        if field_name in text:",
        "after": "    for field_name in INTERNAL_ONLY_FIELDS:\n        if False:",
        "why": "a registry entry the user cannot see is a dependency the user cannot question",
    },
    {
        "id": "M32",
        "rule": "the approval no longer binds the text the user read",
        "target": SP / "proposal.py",
        "before": '        if str(record.get("proposal_digest", "")) != expected:',
        "after": "        if False:",
        "why": "an approval that binds a digest nobody read is not an approval",
    },
    # -- platform boundary ----------------------------------------------------
    {
        "id": "M33",
        "rule": "a platform-specific rule leaks into the universal grammar",
        "target": SP / "platform.py",
        "before": "    for platform, rules in PLATFORM_SPECIFIC_RULES.items():",
        "after": "    for platform, rules in {}:",
        "why": (
            "iPhone dimensions, 44pt targets and safe-area insets are true of iPhone and false "
            "elsewhere, and the boundary is the only thing keeping them out of general design"
        ),
    },
    # -- grammar ---------------------------------------------------------------
    {
        "id": "M34",
        "rule": "the grammar accepts a house style",
        "target": SP / "grammar.py",
        "before": '    if record.get("house_style") is not None:',
        "after": "    if False:",
        "why": (
            "an aesthetic encoded in the methodology would be inherited by every future run. That "
            "is the difference between a house method and a house style, and it is the whole point"
        ),
    },
]


def run_suite() -> tuple[bool, str]:
    """Run the AR-222D suite in a fresh interpreter and report whether it stayed green."""
    try:
        completed = subprocess.run(
            [sys.executable, str(SUITE)],
            cwd=str(ROOT), capture_output=True, text=True, timeout=900,
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
        print("the AR-222D suite is not green to begin with; mutations cannot be judged")
        print(baseline_output[-3000:])
        return 1
    print(f"baseline green: {len(MUTATIONS)} mutations to try\n")

    skipped = [(row["id"], f"anchor not found in {row['target'].name}") for row in MUTATIONS if row.get("skip")]
    usable = [row for row in MUTATIONS if not row.get("skip")]

    survivors: list[dict] = []
    for mutation in usable:
        path = Path(mutation["target"])
        if not path.is_file():
            skipped.append((mutation["id"], f"no such file: {path.name}"))
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
                untracked_globs=(
                    "src/ariadne_engine/design_reference/fixtures/getdesign-md/*.md",
                ),
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
    print("AR-222D mutation suite: every mutation caught")
    report["duration_seconds"] = round(time.time() - report["started_at"], 1)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:  # pragma: no cover - interruption path
        # Deliberately not clearing the ledger here. The stash is on disk and the entry names
        # this pid, so the next run's recovery restores the tree; clearing the marker would
        # discard the only record of which file was mid-mutation.
        print("\ninterrupted; the next run will restore anything left mutated")
        raise
