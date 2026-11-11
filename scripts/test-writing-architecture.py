#!/usr/bin/env python3
"""Deterministic checks for Ariadne's small writing architecture."""

from __future__ import annotations

import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))

from check import DocumentResolutionError, resolve_document  # noqa: E402


def document(name: str, fallback: str) -> Path:
    """Resolve a document through the repository's one layout-aware resolver.

    The public repository groups policies under ``docs/policies``; the
    maintainer tree may keep a copy at the root. Reading a fixed root path made
    this suite pass only in the layout it was written in. A name that cannot be
    resolved stays the root path so the failure names the document that is
    actually missing instead of raising from an unrelated ``open``.
    """
    try:
        return ROOT / resolve_document(name)
    except DocumentResolutionError:
        return ROOT / fallback


POLICY = document("WRITING-POLICY.md", "WRITING-POLICY.md")
BENCHMARK = ROOT / "tests" / "writing-benchmark.md"
ROUTER = document("ROUTER.md", "ROUTER.md")


CASES = [
    "WB-01", "WB-02", "WB-03", "WB-04", "WB-05", "WB-06",
    "WB-07", "WB-08", "WB-09", "WB-10", "WB-11", "WB-12",
]
INTENTS = [
    "CREATIVE", "ACADEMIC", "SCIENTIFIC", "HUMAN-DRAFT TRANSFORMATION", "SOCIAL",
]
CASE_REQUIREMENTS = {
    "WB-01": ("CREATIVE", "review checks"),
    "WB-02": ("CREATIVE", "subtext"),
    "WB-03": ("CREATIVE", "voice"),
    "WB-04": ("HUMAN-DRAFT TRANSFORMATION", "Silent rewrite"),
    "WB-05": ("ACADEMIC", "claim, reasoning, evidence"),
    "WB-06": ("ACADEMIC", "Source-by-source"),
    "WB-07": ("ACADEMIC", "word limit"),
    "WB-08": ("HUMAN-DRAFT TRANSFORMATION", "New claims"),
    "WB-09": ("SCIENTIFIC", "IMRAD"),
    "WB-10": ("SCIENTIFIC", "root cause"),
    "WB-11": ("SCIENTIFIC", "DOI"),
    "WB-12": ("SCIENTIFIC", "causal"),
}


def main() -> int:
    missing = [str(path.relative_to(ROOT)) for path in (POLICY, BENCHMARK, ROUTER) if not path.is_file()]
    if missing:
        print("ARIADNE WRITING ARCHITECTURE SELF-TEST\n")
        for path in missing:
            print(f"FAIL  required document is missing: {path}")
        print(f"\nFAILED  0/{len(missing)} documents resolved")
        return 1
    policy = POLICY.read_text(encoding="utf-8")
    benchmark = BENCHMARK.read_text(encoding="utf-8")
    router = ROUTER.read_text(encoding="utf-8")
    checks: list[tuple[str, bool]] = []

    checks.append(("writing policy exists", POLICY.is_file()))
    checks.append(("benchmark has twelve cases", all(case in benchmark for case in CASES)))
    checks.append(("benchmark cases define expected behavior", benchmark.count("- Expected behavior:") == 12))
    checks.append(("benchmark cases define failure signals", benchmark.count("- Failure signals:") == 12))
    checks.append(("benchmark cases define pass criteria", benchmark.count("- Pass criteria:") == 12))
    sections = {
        match.group(1): match.group(2)
        for match in re.finditer(r"### (WB-\d\d)(.*?)(?=\n### |\Z)", benchmark, re.S)
    }
    checks.append(("benchmark cases test their intended failure", all(
        intent in sections.get(case, "") and signal.lower() in sections.get(case, "").lower()
        for case, (intent, signal) in CASE_REQUIREMENTS.items()
    )))
    checks.append(("all writing intents are explicit", all(intent in policy and intent in router for intent in INTENTS)))
    checks.append(("creative method is purpose-sensitive", "sensory detail" in policy and "Do not force" in policy))
    checks.append(("academic method is argument-driven", "claim -> reasoning -> evidence -> implication" in policy and "five-paragraph" in policy))
    checks.append(("scientific method calibrates claims", "correlation/causation discipline" in policy and "observation/inference" in policy))
    checks.append(("transformation contract preserves provenance", all(field in policy for field in ("original draft", "requested degree of intervention", "change summary", "voice drift"))))
    checks.append(("evidence ladder is reused", "Reuse Ariadne's Evidence Ladder" in policy and "never invents a reference" in policy))
    checks.append(("review remains independent", all(term in policy for term in ("independent editorial review", "drafting rationale as proof", "Review packet", "excludes the drafting rationale"))))
    checks.append(("social rules remain isolated", "Do not apply" in router and "social hook" in router and "CONTENT-SYSTEM.md" in policy))
    implementation_text = "\n".join(
        path.read_text(encoding="utf-8")
        for root in (ROOT / "scripts", ROOT / "skills", ROOT / "templates")
        for path in root.rglob("*")
        if path.is_file() and path.suffix in {".py", ".md"} and path.name not in {POLICY.name, Path(__file__).name}
    ).lower()
    checks.append(("no detector-evasion subsystem exists", not any(term in implementation_text for term in ("semantic similarity subsystem", "perplexity manipulation", "ai-detector integration"))))

    print("ARIADNE WRITING ARCHITECTURE SELF-TEST\n")
    failed = []
    for name, passed in checks:
        print(("ok    " if passed else "FAIL  ") + name)
        if not passed:
            failed.append(name)
    print(f"\n{'FAILED' if failed else 'PASS'}  {len(checks) - len(failed)}/{len(checks)}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
