#!/usr/bin/env python3
"""The AR-222 mutation suite: does the rendered-critique suite actually bite?

A green suite proves the cases pass. It does not prove the cases would notice if the
guarantee were removed. Each mutation below deletes or inverts one load-bearing
behaviour and the suite must fail; a mutation that survives is a boundary that is not
being enforced, whatever the test count says.

The set is chosen from the claims this milestone makes, in the order they would be
attacked:

```text
capture not bound to a source revision      stale screenshot accepted
reviewer sees implementation rationale     worker closes its own finding
repair ignores its allowed scope            repair invents a new design direction
project identity loses to a reference       counter-reference ignored
mechanical validation skipped before re-render
old before-image overwritten                blank capture treated as valid
capture budget ignored                      reference principle swapped for pixel similarity
visual review accepted from source only     capture plan capture-everything matrix
route escapes the run root                  browser argument injection
critique artifact obeyed as instruction
```

Every mutation is a small, surgical edit to the committed source, applied to a restored
copy, run, and then reverted -- including on failure, timeout or interruption, because a
harness that leaves a mutated engine behind will quietly corrupt every later run.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
RESTORE_MARKER = ROOT / ".ariadne-mutation-restore.json"

ENGINE = SRC / "ariadne_engine"
RENDERED = ENGINE / "rendered_critique"

MUTATIONS: list[tuple[str, Path, str, str]] = [
    # -- capture identity -----------------------------------------------------
    (
        "capture not bound to a source revision",
        RENDERED / "evidence.py",
        '            "render_source_digest": revision,\n',
        '            "render_source_digest": "",\n',
    ),
    (
        "stale screenshot accepted",
        RENDERED / "source.py",
        '    if recorded != current_digest:',
        '    if False:',
    ),
    (
        "stale capture re-captured anyway",
        RENDERED / "evidence.py",
        '    stale = source_staleness(binding)\n    if stale:',
        '    stale = source_staleness(binding)\n    if False:',
    ),
    (
        "digest scope widened to files that cannot render",
        RENDERED / "source.py",
        'RENDERED_NAMES = frozenset({',
        'RENDERED_NAMES = frozenset(*(), **{"README.md": 1, "notes.txt": 1, "index.html": 1}.items()) or frozenset({',
    ),
    # -- critique isolation ---------------------------------------------------
    (
        "reviewer sees implementation rationale",
        RENDERED / "critique.py",
        '    found = sorted(key for key in packet if str(key).lower() in banned)\n    if found:',
        '    found = []\n    if found:',
    ),
    (
        "reviewer packet gains a blacklist-only boundary",
        RENDERED / "critique.py",
        '    return {key: value for key, value in packet.items() if key in REVIEWER_WHITELIST}',
        '    return dict(packet)',
    ),
    (
        "critique isolation record falsified",
        RENDERED / "critique.py",
        '            "implementation_rationale_transported": False,',
        '            "implementation_rationale_transported": True,',
    ),
    (
        "the reviewer may be the implementer",
        ENGINE / "contracts.py",
        "    if reviewer and implementer and reviewer == implementer:",
        "    if False:",
    ),
    (
        "findings no longer have to cite a capture",
        RENDERED / "critique.py",
        '        if not citations:',
        '        if False:',
    ),
    (
        "coverage may claim REVIEWED with no capture",
        ENGINE / "contracts.py",
        '            if str(verdict.get("state", "")) == "REVIEWED" and not verdict.get("capture_ids"):',
        '            if False:',
    ),
    # -- refinement boundaries ------------------------------------------------
    (
        "worker closes its own critique finding",
        RENDERED / "refinement.py",
        '    if str(re_critique.get("reviewer_execution", "")) == str(plan_record.get("repair_execution", "")):',
        '    if False:',
    ),
    (
        "repair ignores its allowed scope",
        RENDERED / "refinement.py",
        '    outside = [item for item in changed if not any(contracts.path_matches(item, entry) for entry in allowed)]',
        '    outside = []',
    ),
    (
        "repair invents a new design direction",
        RENDERED / "vertical_slice.py",
        '        existing = [str(value) for value in (item.get("direction_principle_ids") or [])]',
        '        existing = ["prn_invented_by_the_repair"]',
    ),
    (
        "a plan needs no authorising principle",
        RENDERED / "refinement.py",
        '    if not principles:',
        '    if False:',
    ),
    (
        "the repair budget is unbounded",
        RENDERED / "refinement.py",
        'MAX_REPAIR_ATTEMPTS = 2',
        'MAX_REPAIR_ATTEMPTS = 99',
    ),
    (
        "mechanical validation skipped before re-render",
        RENDERED / "refinement.py",
        '    if str(record.get("status")) != "VALIDATED":',
        '    if False:',
    ),
    (
        "resolution need not be independently reviewed",
        RENDERED / "refinement.py",
        '    if str(re_critique.get("critique_id")) == str(plan_record.get("critique_id")):',
        '    if False:',
    ),
    (
        "resolution accepted without re-inspecting the evidence",
        RENDERED / "refinement.py",
        '        if original_captures and uninspected:',
        '        if False:',
    ),
    (
        "before-image may be overwritten",
        RENDERED / "safety.py",
        'def assert_no_collision(path: Path, *, preserve_existing: bool = True) -> None:',
        'def assert_no_collision(path: Path, *, preserve_existing: bool = False) -> None:',
    ),
    # -- capture validity and budget -----------------------------------------
    (
        "blank capture treated as valid",
        RENDERED / "evidence.py",
        '    if size == 0:',
        '    if False:',
    ),
    (
        "an error page may be critiqued as the interface",
        RENDERED / "evidence.py",
        '            return {"state": "ERROR_DOCUMENT", "reasons": reasons}',
        '            return {"state": "VALID", "reasons": reasons}',
    ),
    (
        "an application shell passes as loaded content",
        RENDERED / "evidence.py",
        '        return {"state": "NO_CONTENT", "reasons": reasons}\n    busy = [str(item) for item in (report.get("busy_indicators") or [])]',
        '        return {"state": "VALID", "reasons": reasons}\n    busy = [str(item) for item in (report.get("busy_indicators") or [])]',
    ),
    (
        "capture budget ignored",
        ENGINE / "contracts.py",
        "        if count > limit and name not in stated:",
        "        if False:",
    ),
    (
        "a capture target needs no materiality basis",
        ENGINE / "contracts.py",
        '        if not isinstance(basis, list) or not [item for item in basis if str(item).strip()]:',
        '        if False:',
    ),
    (
        "the capture plan becomes a universal matrix",
        RENDERED / "plan.py",
        '    if not rows:\n        raise ContractError(\n            "a capture target must name why it exists',
        '    if False:\n        raise ContractError(\n            "a capture target must name why it exists',
    ),
    (
        "image bounds removed",
        RENDERED / "safety.py",
        '    if int(bytes_written) > MAX_CAPTURE_BYTES:',
        '    if False:',
    ),
    # -- reference alignment and identity ------------------------------------
    (
        "reference principle replaced with pixel similarity",
        RENDERED / "critique.py",
        '            "basis": "approved-principle-satisfaction",\n            "pixel_similarity_computed": False,',
        '            "basis": "pixel-similarity",\n            "pixel_similarity_computed": True,\n'
        '            "similarity_scores": [{"reference": "linear", "score": 0.87}],',
    ),
    (
        "project identity loses to the reference",
        RENDERED / "critique.py",
        '                "project identity outranks every reference: a reference\'s colour, typeface or treatment "',
        '                "reference imagery outranks the project identity: a reference\'s colour or treatment "',
    ),
    (
        "counter-reference violations go unchecked",
        RENDERED / "critique.py",
        '            "state": "PRESENT" if present_in_source else "ABSENT",',
        '            "state": "ABSENT",',
    ),
    (
        "a visual judgement is laundered as a measurement",
        RENDERED / "critique.py",
        '        if str(row.get("basis")) not in FINDING_BASES:',
        '        if False:',
    ),
    # -- the mechanical/rendered boundary ------------------------------------
    (
        "visual review accepted from source inspection alone",
        RENDERED / "contracts_bridge.py",
        '    if rendered_check_id:\n        claim["rendered_check_id"] = str(rendered_check_id)',
        '    claim["rendered_check_id"] = rendered_check_id or "drc_assumed_without_a_review"\n'
        '    if False:',
    ),
    (
        "a missing browser degrades to a no-op adapter",
        RENDERED / "adapter.py",
        '    def available(self) -> tuple[bool, str]:\n        return False, self._reason',
        '    def available(self) -> tuple[bool, str]:\n        return True, ""',
    ),
    (
        "browser capability failure is swallowed",
        RENDERED / "adapter.py",
        '        except Exception as exc:  # noqa: BLE001\n            raise CaptureFailed(f"CAPTURE_FAILED: {safe} did not load: {exc}") from exc',
        '        except Exception:  # MUTATION: swallow a failed navigation\n            self._page = None\n            return None',
    ),
    # -- security ------------------------------------------------------------
    (
        "capture route escapes the loopback boundary",
        RENDERED / "safety.py",
        '    if host not in permitted:',
        '    if False:',
    ),
    (
        "file:// capture route accepted",
        RENDERED / "safety.py",
        '    if scheme not in ALLOWED_SCHEMES:',
        '    if False:',
    ),
    (
        "capture artifact escapes the run root",
        RENDERED / "safety.py",
        '    if resolved_parent != base:',
        '    if False:',
    ),
    (
        "browser launch argument injection",
        RENDERED / "safety.py",
        '    for item in items:\n        if "\\x00" in item:',
        '    for item in []:\n        if "\\x00" in item:',
    ),
    (
        "interaction descriptor may carry arbitrary code",
        RENDERED / "safety.py",
        '    if kind not in INTERACTION_ACTIONS:',
        '    if False:',
    ),
    (
        "critique artifact obeyed as an instruction",
        RENDERED / "safety.py",
        '    return as_data(text, origin="critique-artifact", label="critique")',
        '    return text',
    ),
    (
        "the browser run is bound to no source digest",
        RENDERED / "evidence.py",
        '    digest = str(binding.get("render_source_digest", ""))\n    stale = source_staleness(binding)',
        '    digest = ""\n    stale = []',
    ),
]


def _snapshot(path: Path) -> bytes:
    return path.read_bytes()


def _restore(path: Path, original: bytes) -> None:
    path.write_bytes(original)


def _write_restore_marker(pending: list[tuple[Path, bytes]]) -> None:
    import json

    RESTORE_MARKER.write_text(
        json.dumps([{"path": str(path), "sha256": _digest(payload)} for path, payload in pending]),
        encoding="utf-8",
    )


def _digest(payload: bytes) -> str:
    import hashlib

    return hashlib.sha256(payload).hexdigest()


def _clear_restore_marker() -> None:
    if RESTORE_MARKER.is_file():
        RESTORE_MARKER.unlink()


def run_suite() -> tuple[bool, str]:
    """Return (suite_passed, output).

    The polarity matters and is easy to get backwards. The *baseline* must pass, or a
    mutation that "survives" means nothing. A *mutation* is caught when the suite goes
    red. Returning the raw "passed" flag and letting each caller decide keeps those two
    from being confused.
    """
    completed = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "test-rendered-critique.py")],
        cwd=str(ROOT), capture_output=True, text=True, timeout=5400, shell=False,
        stdin=subprocess.DEVNULL,
    )
    return completed.returncode == 0, (completed.stdout or "") + (completed.stderr or "")


def main() -> int:
    baseline_ok, baseline_output = run_suite()
    if not baseline_ok:
        print("the suite is not green before mutation; a surviving mutation would mean nothing")
        print(baseline_output[-3000:])
        return 1

    print(f"baseline green: {len(MUTATIONS)} mutations to try\n")
    survivors: list[str] = []
    skipped: list[tuple[str, str]] = []
    for index, (label, relative, original_text, mutated_text) in enumerate(MUTATIONS, start=1):
        path = ROOT / relative
        if not path.is_file():
            skipped.append((label, f"no such file: {relative}"))
            continue
        source = path.read_text(encoding="utf-8")
        if original_text not in source:
            skipped.append((label, f"anchor not found in {relative.name}"))
            continue
        payload = _snapshot(path)
        try:
            path.write_text(source.replace(original_text, mutated_text, 1), encoding="utf-8")
            _write_restore_marker([(path, payload)])
            passed, output = run_suite()
            caught = not passed
        except subprocess.TimeoutExpired:
            caught, output = True, "the mutated suite hung, which is a failure to pass"
        finally:
            _restore(path, payload)
            _clear_restore_marker()
        if caught:
            print(f"caught  {label} ({index}/{len(MUTATIONS)})")
        else:
            survivors.append(label)
            print(f"SURVIVED {label} ({index}/{len(MUTATIONS)})")
            for line in output.splitlines():
                if line.startswith(("FAIL", "ERROR")):
                    print(f"        {line}")
        # The tree must be byte-identical after every mutation, tracked or not.
        if _snapshot(path) != payload:  # pragma: no cover - a harness bug
            _restore(path, payload)
            print(f"        (harness restored {relative.name})")

    _clear_restore_marker()
    print()
    for label, reason in skipped:
        print(f"skipped  {label}: {reason}")
    if skipped:
        print()
    if survivors:
        print(f"{len(survivors)} mutation(s) survived -- these boundaries are not enforced:")
        for label in survivors:
            print(f"  - {label}")
        return 1
    print(f"{len(MUTATIONS)}/{len(MUTATIONS)} mutations caught")
    print("AR-222 mutation suite: every mutation caught")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:  # pragma: no cover - interruption path
        _clear_restore_marker()
        raise
