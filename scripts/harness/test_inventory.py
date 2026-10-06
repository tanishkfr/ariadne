"""Test inventory integrity: a green suite is not the same as coverage (AR-222D).

AR-222 recorded the cleanest argument in the project for running mutations, and it is
not about any individual mutation:

> During the containment-test rewrite, line-range surgery swallowed
> ``a_launch_argument_may_not_carry_a_nul_or_an_implausible_length``. The suite went
> green — 86/86 — and only the mutation *"browser launch argument injection"* surviving
> revealed that a real guarantee had lost its coverage.

A test disappeared. The suite still reported a count. The count went *down* and nobody
was watching it, because the only gate was "did the count change", and the only signal
was the number itself.

Two mechanisms here, and the reason both are needed:

**A named inventory of critical cases.** :data:`CRITICAL_CASES` lists the guarantees
that must be individually named and present. Checking membership catches the specific
failure above -- a named guarantee that vanished -- regardless of the raw count.

**A count floor, recorded per suite.** :func:`check_inventory` refuses a suite whose case
count has fallen below its recorded floor. This catches the *unnamed* losses that no
manifest can enumerate.

And one rule about what a mutation may do:

> **A surviving mutation is a failure to investigate, not a boundary to move.**

If a mutation survives, the cause is missing coverage, a broken mutation, or a wrong
assumption in the code. Weakening the mutation or deleting it to restore green destroys
the one signal that any of those three is true.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Iterable, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[1]

CASE_LINE = re.compile(r"^\s*(?:ok|FAIL|HELD|held|caught|SURVIVED)\s{2,}(?P<name>.+?)\s*$", re.MULTILINE)
PASS_LINE = re.compile(r"^(?:PASS|FAILED)\s+(?P<passed>\d+)/(?P<total>\d+)\b", re.MULTILINE)
BARE_PASS_LINE = re.compile(r"^(?P<passed>\d+)/(?P<total>\d+)\s+passed\s*$", re.MULTILINE)
CAUGHT_LINE = re.compile(r"^(?P<caught>\d+)/(?P<total>\d+)\s+mutations caught", re.MULTILINE)
HELD_LINE = re.compile(r"^(?P<held>\d+)/(?P<held_total>\d+)\s+attacks held", re.MULTILINE)
GREEN_LINE = re.compile(r"all green|every mutation caught|every attempted bypass was refused|every attempted bypass was refused or honestly reported")
"""Summary matchers are ``MULTILINE``.

Without the flag, ``^`` matches only the start of the whole output, so a ``PASS  87/87``
on the last line of a suite that printed ninety results beforehand was invisible. The
consequence is not a crash: it is an inventory check that reads every suite as having
printed no summary at all, which quietly turns the floor check off.

``BARE_PASS_LINE`` exists because not every suite prefixes its summary with ``PASS``. The
first version of this module only understood the prefixed form, so two of the suites
reported ``0/0`` -- which read as "no floor violation" and passed silently. A summary this
module cannot parse is a gate it cannot enforce, and :func:`check_inventory` now refuses
rather than skipping.
"""


class InventoryError(RuntimeError):
    """Raised when test coverage has been lost and the loss must not be silent."""


def _case(path: str, name: str) -> str:
    return f"{path}::{name}"


#: Guarantees that must be individually named somewhere in the repository.
#:
#: Each entry is the *identity* of a guarantee, matched as a distinctive phrase. These
#: are the failures AR-222 actually shipped: each one is a case that existed, was real,
#: and stopped existing without any count noticing.
CRITICAL_CASES: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "render-and-capture-identity",
        (
            "capture not bound to a source revision",
            "stale screenshot accepted",
            "stale render laundering",
        ),
    ),
    (
        "critique-independence",
        (
            "reviewer sees implementation rationale",
            "critique self-certification",
            "worker closes its own critique finding",
            "the reviewer may be the implementer",
        ),
    ),
    (
        "record-identity-semantics",
        (
            "record lookup returns detached copy where canonical mutation required",
            "by_id returns a detached copy",
            "scope enforcement mutation becomes no-op",
            "self-review prevention becomes no-op",
        ),
    ),
    (
        "repair-lineage",
        (
            "old before-image overwritten",
            "repair history overwritten",
            "requirement ID dropped from finding",
            "reviewer identity preserved",
            "historical evidence not overwritten",
        ),
    ),
    (
        "mutation-harness-integrity",
        (
            "active mutation sentinel ignored",
            "repository considered restored with mutated untracked state",
            "critical test removed but test-count-only gate stays green",
            "mutation harness restores transactionally",
        ),
    ),
    (
        "design-specificity-grammar",
        (
            "three candidates materially differ",
            "category default detection does not imply automatic rejection",
            "own-slop exists",
            "content model precedes layout plan",
            "richness source is explicit",
            "platform-specific rule does not leak into universal grammar",
        ),
    ),
    (
        "source-ecosystem",
        (
            "no query-everything behavior",
            "browser-only source remains browser-only",
            "no unsupported adapter claim",
            "paid source treated as free/public",
        ),
    ),
    (
        "user-autonomy",
        (
            "simple vague request does not trigger unnecessary questions",
            "G1D requires human approval",
            "routine refinement does not",
        ),
    ),
    (
    "beacon-negative-case",
    (
        "hidden overflow",
        "partial re-review",
        "focus indication",
        "duplicate heading",
    ),
    ),
    (
        "acceptance-intelligence",
        (
            "a claim is not evidence",
            "missing evidence is not failure",
            "acceptance state",
            "independent review",
            "re-verification",
        ),
    ),
    (
        "verified-intelligence",
        (
            "confidence is not permission",
            "provider probability",
            "answer space",
            "false-confidence",
            "held-out",
        ),
    ),
    (
        "proof-pass",
        (
            "ambiguous current task refuses rather than choosing",
            "receipt history is append only and never overwritten",
            "receipt digest binds content and detects tampering",
            "unrelated receipts refuse direct comparison",
            "mcp cannot mint reviewer or human approval",
        ),
    ),
)

#: Recorded floors per suite. A count below its floor is a loss even when every named
#: guarantee is present -- this is the net that catches unnamed cases.
SUITE_FLOORS: dict[str, int] = {
    "scripts/test-engine-core.py": 570,
    "scripts/test-decision-runtime.py": 500,
    "scripts/test-design-reference.py": 105,
    "scripts/test-design-execution.py": 65,
    "scripts/test-rendered-critique.py": 85,
    "scripts/test-rendered-critique-adversarial.py": 25,
    "scripts/test-design-execution-adversarial.py": 33,
    "scripts/test-design-reference-mutations.py": 20,
    "scripts/test-design-execution-mutations.py": 23,
    "scripts/test-rendered-critique-mutations.py": 38,
    "scripts/test-ar222d.py": 60,
    "scripts/test-ar222d-mutations.py": 20,
    "scripts/test-ar222d-adversarial.py": 20,
    "scripts/test-ar223.py": 75,
    "scripts/test-ar223-adversarial.py": 40,
    "scripts/test-ar223-mutations.py": 25,
    "scripts/test-ar224.py": 35,
    "scripts/test-ar224-adversarial.py": 20,
    "scripts/test-ar224-mutations.py": 18,
}


def parse_cases(text: str) -> list[str]:
    """Every named case in a suite's output.

    Named, not counted, deliberately: the AR-222 failure was a *named* guarantee
    disappearing, so the unit of accounting here has to be a name. A raw count cannot
    distinguish "lost a case" from "renamed a case" from "merged two cases", and only
    the first is a defect.
    """
    return [
        match.group("name").strip()
        for line in str(text or "").splitlines()
        if (match := CASE_LINE.match(line))
    ]


def parse_summary(text: str) -> dict:
    """(passed, total, green) from whichever summary shape the suite uses."""
    result = {"passed": 0, "total": 0, "green": False, "kind": ""}
    body = str(text or "")
    for match in PASS_LINE.finditer(body):
        result.update(passed=int(match.group("passed")), total=int(match.group("total")))
        result["green"] = match.group(0).startswith("PASS")
        result["kind"] = "checks"
    for match in BARE_PASS_LINE.finditer(body):
        if result["kind"] == "checks":
            break
        result.update(passed=int(match.group("passed")), total=int(match.group("total")))
        result["green"] = True
        result["kind"] = "bare-checks"
    for match in CAUGHT_LINE.finditer(body):
        result.update(passed=int(match.group("caught")), total=int(match.group("total")))
        result["green"] = result["passed"] == result["total"]
        result["kind"] = "mutations"
    for match in HELD_LINE.finditer(body):
        result.update(passed=int(match.group("held")), total=int(match.group("held_total")))
        result["green"] = result["passed"] == result["total"]
        result["kind"] = "attacks"
    if not result["kind"]:
        result["green"] = bool(GREEN_LINE.search(body))
        result["kind"] = "narrative"
    return result


def corpus_text(roots: Sequence[Path | str] | None = None) -> str:
    """All text the inventory may be satisfied from.

    Deliberately the whole corpus, not one file: a guarantee may legitimately be asserted
    in whichever suite owns it, and pinning it to a file would make the manifest a
    refactoring hazard rather than a safety net.
    """
    paths = [Path(item) for item in (roots or ())] or [
        ROOT / "scripts", ROOT / "benchmarks" / "arbench", ROOT / "src"
    ]
    chunks: list[str] = []
    for path in paths:
        if path.is_file():
            chunks.append(path.read_text(encoding="utf-8", errors="replace"))
            continue
        for candidate in sorted(path.rglob("*")):
            if candidate.is_file() and candidate.suffix in (".py", ".md"):
                chunks.append(candidate.read_text(encoding="utf-8", errors="replace"))
    return "\n".join(chunks)


def missing_critical_cases(present: Iterable[str], corpus: str | None = None) -> dict[str, list[str]]:
    """Named guarantees with no evidence anywhere in the corpus."""
    haystack = corpus if corpus is not None else corpus_text()
    names = {str(item).strip().lower() for item in present}
    missing: dict[str, list[str]] = {}
    for group, phrases in CRITICAL_CASES:
        absent = [
            phrase for phrase in phrases
            if phrase.lower() not in names and phrase.lower() not in haystack.lower()
        ]
        if absent:
            missing[group] = absent
    return missing


def check_inventory(
    outputs: Mapping[str, str],
    *,
    floors: Mapping[str, int] | None = None,
    corpus: str | None = None,
) -> dict:
    """Full inventory verdict: named guarantees present, counts above their floors.

    Returns a report rather than raising, so a gate can decide. ``ok`` is true only when
    both the named inventory and every floor hold.
    """
    limits = dict(SUITE_FLOORS) if floors is None else {str(k): int(v) for k, v in floors.items()}
    all_cases: list[str] = []
    floor_failures: list[dict] = []
    not_green: list[str] = []
    unparsed: list[str] = []
    counts: dict[str, dict] = {}
    for path, text in (outputs or {}).items():
        summary = parse_summary(text)
        key = str(path).replace("\\", "/")
        short = key.split("/")[-1]
        counts[short] = summary
        all_cases.extend(parse_cases(text))
        floor = limits.get(key, limits.get(short))
        if floor is None:
            continue
        if summary["kind"] == "narrative" or not summary["total"]:
            # A floor this module cannot evaluate is a floor that is not being enforced.
            # Skipping it reads as a pass, which is the exact silent green AR-222 hit.
            unparsed.append({
                "suite": short,
                "recorded_floor": floor,
                "observed_total": 0,
                "note": (
                    "no parseable summary line was found, so the recorded floor could not be "
                    "checked. An unparsed summary is an unenforced floor, not a satisfied one"
                ),
            })
            continue
        if summary["total"] < floor:
            floor_failures.append({
                "suite": short,
                "recorded_floor": floor,
                "observed_total": summary["total"],
                "shortfall": floor - summary["total"],
                "note": (
                    "the raw count fell below its recorded floor. A count can fall because a case "
                    "was deleted, renamed, or merged -- only the first is a defect, and all three "
                    "are worth knowing about"
                ),
            })
        if not summary["green"]:
            not_green.append(short)
    missing = missing_critical_cases(all_cases, corpus)
    return {
        "ok": not missing and not floor_failures and not unparsed and not not_green,
        "named_guarantees": sum(len(phrases) for _group, phrases in CRITICAL_CASES),
        "missing_named_guarantees": missing,
        "floor_failures": floor_failures,
        "unparsed_summaries": unparsed,
        "suites": counts,
        "not_green": not_green,
        "principle": (
            "a green suite is not the same as coverage. A named guarantee that vanishes must be "
            "caught by name, and a raw count that falls must be caught by floor, because the two "
            "failures are independent. A summary this module cannot parse means neither net can "
            "fire, so it is reported rather than skipped."
        ),
    }


def survivor_report(label: str, caught: bool, *, suite_green: bool = True) -> dict:
    """Classify a mutation outcome. A survivor is always a failure.

    Three causes, and the correct response is to investigate rather than to adjust:
    missing coverage, a broken mutation, or an invalid invariant assumption in the code.
    Weakening the mutation to make it die, or deleting it to make the suite green,
    destroys the only evidence that one of the three is true.
    """
    return {
        "mutation": str(label),
        "caught": bool(caught),
        "classification": "CAUGHT" if caught else "SURVIVED",
        "investigate": [] if caught else [
            "missing coverage: no case asserts the behaviour this mutation removed",
            "broken mutation: the mutation did not actually change the behaviour",
            "invalid invariant: the code's assumption is wrong and the tests encode it",
        ],
        "permitted_responses": [] if caught else [
            "add the missing case",
            "fix the mutation so it changes the behaviour",
            "correct the invariant and the tests that encode it",
        ],
        "forbidden_responses": [] if caught else [
            "weaken the mutation until it dies",
            "delete the mutation to restore green",
            "raise the recorded floor to match the new lower count",
        ],
    }


def manifest() -> dict:
    """The manifest itself, as a record."""
    return {
        "schema": "ariadne-test-inventory-1",
        "critical_cases": {group: list(phrases) for group, phrases in CRITICAL_CASES},
        "suite_floors": dict(sorted(SUITE_FLOORS.items())),
        "named_total": sum(len(phrases) for _group, phrases in CRITICAL_CASES),
        "survivor_policy": (
            "a surviving mutation is a failure to investigate: missing coverage, a broken mutation, "
            "or an invalid invariant. Weakening or deleting it to restore green is forbidden"
        ),
    }


def write_manifest(path: Path | str) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(manifest(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return target


__all__ = [
    "CRITICAL_CASES",
    "InventoryError",
    "SUITE_FLOORS",
    "check_inventory",
    "corpus_text",
    "manifest",
    "missing_critical_cases",
    "parse_cases",
    "parse_summary",
    "survivor_report",
    "write_manifest",
]