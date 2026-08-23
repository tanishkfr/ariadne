#!/usr/bin/env python3
"""Deterministic V1.5 real-project fixtures.

These fixtures exercise planning and recovery contracts with realistic briefs.
They do not claim that a provider ran, a visual was rendered, or a human gate
passed. Temporary project files are local test artifacts and are removed after
each run.
"""

from __future__ import annotations

import contextlib
import hashlib
import importlib.util
import json
import shutil
import sys
import uuid
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "validation" / "fixtures" / "v1.5-real-projects.json"


def load_module(name: str, relative: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load {relative}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


CREATIVE = load_module("ariadne_v15_creative", "scripts/creative-intelligence.py")
BUILDER = load_module("ariadne_v15_runtime", "scripts/ariadne.py")


def fixture_source_sha256() -> str:
    return hashlib.sha256(FIXTURES.read_bytes()).hexdigest()


def project_document(fixture: dict) -> str:
    criteria = "\n".join(
        f"{index}. {criterion}"
        for index, criterion in enumerate(fixture["success_criteria"], 1)
    )
    return (
        f"# PROJECT: {fixture['name']}\n\n"
        "**Mode:** client-or-portfolio · **Status:** fixture intake\n\n"
        f"## Goal\n\n{fixture['request']}\n\n"
        f"## Success criteria\n\n{criteria}\n\n"
        "## Open questions\n\nFixture-specific branch recorded in the fixture source.\n"
    )


def agents_document() -> str:
    return (
        "# AGENTS\n\n## Current state\n\n"
        "| Field | Value |\n|---|---|\n"
        "| **Stage** | `S1` |\n"
        "| **Last gate passed** | `none` |\n"
        "| **Next prompt** | `prompts/design-direction.md` |\n"
    )


def assessment(fixture: dict) -> dict:
    value = CREATIVE.low_assessment(**fixture["creative_profile"])
    value["references_supplied"] = fixture["references_supplied"]
    value["alternatives_helpful"] = {
        "value": fixture["alternatives_helpful"],
        "reason": (
            "Competing mechanisms need comparison for this fixture."
            if fixture["alternatives_helpful"]
            else "One direction is sufficient unless evidence changes the brief."
        ),
    }
    value["social_request"] = {
        "value": bool(fixture["social_request"]),
        "request": fixture["social_request"],
    }
    value["research_questions"] = fixture["research_questions"]
    return value


@contextlib.contextmanager
def workspace():
    path = ROOT / "validation" / f"real-projects-self-test-{uuid.uuid4().hex}"
    path.mkdir()
    try:
        yield path
    finally:
        if path.exists():
            shutil.rmtree(path)


def inspect_reference(ledger: dict, reference_id: str, source: str, evidence: Path, mechanism: str) -> None:
    CREATIVE.record_reference(ledger, {
        "id": reference_id,
        "source": source,
        "state": "inspected",
        "inspection": "content",
        "evidence_path": str(evidence),
        "observations": [f"The fixture describes {mechanism} as its organising mechanism."],
        "mechanisms": [mechanism],
        "why_it_matters": "The organising mechanism changes the direction, not only its surface.",
        "borrow": f"Test {mechanism} as a structural principle.",
        "reject": "Do not copy the fixture's visual styling.",
    })


def run_fixture(fixture: dict, root: Path) -> list[tuple[str, bool]]:
    cases: list[tuple[str, bool]] = []
    project = root / fixture["id"]
    project.mkdir()

    if fixture["existing_project"]:
        readme = project / "README.md"
        source = project / "src" / "calendar.js"
        source.parent.mkdir()
        readme.write_text("# Existing civic calendar\n", encoding="utf-8")
        source.write_text("export const events = [];\n", encoding="utf-8")
        before = (hashlib.sha256(readme.read_bytes()).hexdigest(), hashlib.sha256(source.read_bytes()).hexdigest())
        try:
            BUILDER.ensure_project(project, adopt_existing=False)
            unsafe_adoption_allowed = True
        except BUILDER.RuntimeError_:
            unsafe_adoption_allowed = False
        cases.append(("existing project refuses implicit adoption", not unsafe_adoption_allowed))
        BUILDER.ensure_project(project, adopt_existing=True)
        after = (hashlib.sha256(readme.read_bytes()).hexdigest(), hashlib.sha256(source.read_bytes()).hexdigest())
        cases.append(("explicit adoption preserves existing source", before == after))
    else:
        BUILDER.ensure_project(project)

    (project / "PROJECT.md").write_text(project_document(fixture), encoding="utf-8")
    (project / "AGENTS.md").write_text(agents_document(), encoding="utf-8")
    packet = project / "fixture-s1-input.txt"
    packet.write_text(fixture["request"] + "\n", encoding="utf-8")

    ledger = CREATIVE.create_ledger(project, assessment(fixture))
    CREATIVE.record_skill_event(ledger, {
        "skill": "intake", "state": "invoked", "evidence_path": str(packet),
    })
    CREATIVE.record_skill_event(ledger, {
        "skill": "intake", "state": "completed", "output_path": str(project / "PROJECT.md"),
        "result": "The realistic fixture brief was converted into falsifiable project state.",
        "usefulness": "useful",
    })
    CREATIVE.save_ledger(project, ledger)
    selected = [item["name"] for item in ledger["skills"] if item["selected"]]
    cases.extend([
        ("research depth matches the project", ledger["research_depth"] == fixture["expected_research_depth"]),
        ("selected capabilities match the project", selected == fixture["expected_selected_skills"]),
        ("intake execution is evidenced", not CREATIVE.stage_problems(ledger, "S1")),
    ])

    if fixture["id"] == "field-notes":
        cases.append((
            "minimal fixture does not claim optional creative machinery",
            all(
                next(item for item in ledger["skills"] if item["name"] == name)["state"] == "skipped"
                for name in ("technical-research", "reference-analysis", "component-research", "visual-qa", "social-strategy")
            ),
        ))
    elif fixture["id"] == "kinetic-index":
        unresolved = CREATIVE.stage_problems(ledger, "S3")
        decision, _reason = BUILDER.preflight_decision("available", "insufficient", "large")
        cases.extend([
            ("ambitious fixture blocks on unresolved selected creative work", bool(unresolved)),
            ("ambitious fixture does not downgrade insufficient provider quota", decision == "blocked"),
        ])
    elif fixture["id"] == "counter-archive":
        chronology = project / "chronology-reference.html"
        provenance = project / "provenance-reference.html"
        chronology.write_text("<main>Chronology orders records as one public sequence.</main>\n", encoding="utf-8")
        provenance.write_text("<main>Provenance keeps each physical chain visible.</main>\n", encoding="utf-8")
        inspect_reference(ledger, "ref-chronology", "https://fixture.invalid/chronology", chronology, "a public chronology")
        inspect_reference(ledger, "ref-provenance", "https://fixture.invalid/provenance", provenance, "visible provenance chains")
        CREATIVE.record_conflict(ledger, {
            "reference_ids": ["ref-chronology", "ref-provenance"],
            "implication": "A single timeline would erase the disagreement; the interface must expose competing chains.",
        })
        CREATIVE.record_direction(ledger, {
            "id": "direction-chronology", "status": "rejected",
            "thesis": "One public sequence makes the archive readable at a glance.",
            "mechanism": "single chronological rail", "experience": "linear editorial reading",
        })
        CREATIVE.record_direction(ledger, {
            "id": "direction-provenance", "status": "candidate",
            "thesis": "Competing custody chains make disagreement navigable.",
            "mechanism": "switchable provenance threads", "experience": "comparative archive exploration",
        })
        CREATIVE.save_ledger(project, ledger)
        cases.extend([
            ("conflicting references are independently inspected", len(ledger["references"]) == 2 and all(item["state"] == "inspected" for item in ledger["references"])),
            ("reference conflict changes the recorded mechanism", len(ledger["conflicts"]) == 1 and len({(item["mechanism"], item["experience"]) for item in ledger["directions"]}) == 2),
            ("rejected direction remains in history", [item["status"] for item in ledger["directions"]] == ["rejected", "candidate"]),
        ])
    elif fixture["id"] == "small-press-launch":
        social = next(item for item in ledger["skills"] if item["name"] == "social-strategy")
        broken = assessment(fixture)
        broken["social_request"]["request"] = ""
        try:
            CREATIVE.create_ledger(project, broken)
            missing_activation_allowed = True
        except CREATIVE.CreativeError:
            missing_activation_allowed = False
        cases.extend([
            ("social capability carries the explicit user request", social["selected"] and assessment(fixture)["social_request"]["request"] == fixture["social_request"]),
            ("social activation cannot lose its explicit request", not missing_activation_allowed),
        ])

    return [(f"{fixture['id']}: {name}", passed) for name, passed in cases]


def main() -> int:
    value = json.loads(FIXTURES.read_text(encoding="utf-8"))
    fixtures = value.get("fixtures", [])
    cases: list[tuple[str, bool]] = []
    ids = [item.get("id") for item in fixtures]
    cases.extend([
        ("fixture schema is current", value.get("schema_version") == 1),
        ("five distinct real-project fixtures exist", len(fixtures) == 5 and len(ids) == len(set(ids))),
        ("every fixture includes a non-success branch", all(item.get("expected_branch") for item in fixtures)),
        ("every fixture names its human boundary", all(item.get("expected_human_boundary") for item in fixtures)),
    ])
    with workspace() as root:
        for fixture in fixtures:
            cases.extend(run_fixture(fixture, root))

    print("V1.5 REAL-PROJECT FIXTURES\n")
    for name, passed in cases:
        print(("ok    " if passed else "FAIL  ") + name)
    failed = [name for name, passed in cases if not passed]
    print(f"\nFixture source SHA-256: {fixture_source_sha256()}")
    print(f"PASS  {len(cases)}/{len(cases)}" if not failed else f"FAILED  {len(cases) - len(failed)}/{len(cases)}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
