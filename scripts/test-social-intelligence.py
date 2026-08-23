#!/usr/bin/env python3
"""Deterministic V1.5.2 social strategy, evidence, and learning fixtures."""

from __future__ import annotations

import contextlib
import copy
import importlib.util
import json
import shutil
import sys
import uuid
from datetime import datetime, timedelta
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "validation" / "fixtures" / "v1.5.2-social-flows.json"


def load_module(name: str, relative: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {relative}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


OPS = load_module("ariadne_social_operations", "scripts/creative-operations.py")
CREATIVE = load_module("ariadne_social_creative", "scripts/creative-intelligence.py")


@contextlib.contextmanager
def workspace():
    path = ROOT / "validation" / f"social-self-test-{uuid.uuid4().hex}"
    path.mkdir()
    try:
        yield path
    finally:
        if path.exists():
            shutil.rmtree(path)


def fixture_project(root: Path, fixture: dict) -> tuple[Path, Path | None]:
    project = root / fixture["id"]
    project.mkdir()
    (project / "PROJECT.md").write_text(
        f"# PROJECT: {fixture['id']}\n\n## Goal\n\n{fixture['goal']}\n\n"
        f"## Audience\n\n{fixture['audience']}\n",
        encoding="utf-8",
    )
    (project / "DESIGN.md").write_text(
        "# DESIGN\n\n**Status:** locked at G1 on 2026-08-23\n\n"
        f"## Design thesis\n\n**{fixture['story']['strongest_moment']}**\n\n"
        "## Signature moment\n\n"
        f"- **What / where:** {fixture['story']['strongest_moment']}\n"
        "- **Why memorable:** It exposes the project's specific mechanism.\n"
        "- **Mobile equivalent:** The same evidence becomes a single readable sequence.\n\n"
        "## Responsive behaviour\n\n| Width | Composition |\n|---|---|\n"
        "| 375 | One evidence sequence remains legible. |\n"
        "| 1280 | The evidence and explanation share one frame. |\n",
        encoding="utf-8",
    )
    (project / "HANDOFF.md").write_text(
        "# HANDOFF\n\n## Decisions that are fixed\n\n| Decision | Value |\n|---|---|\n"
        "| Typography | editorial system |\n| Palette | evidence-led contrast |\n"
        "| Grid | responsive narrative |\n| Motion | purposeful only |\n",
        encoding="utf-8",
    )
    (project / "AGENTS.md").write_text("# AGENTS\n\n| **Last gate passed** | G1 |\n", encoding="utf-8")
    asset = None
    if fixture["visual_status"] == "existing":
        asset = project / "social-visual.svg"
        asset.write_text(
            "<svg xmlns='http://www.w3.org/2000/svg' width='1280' height='720'>"
            f"<title>{fixture['visual']}</title><rect width='1280' height='720'/></svg>\n",
            encoding="utf-8",
        )
    return project, asset


def source_ledger(project: Path) -> tuple[Path, Path]:
    source_a = project / "platform-guidance.html"
    source_b = project / "platform-research.html"
    source_a.write_text("<main>Official fixture guidance describes native visual formats.</main>\n", encoding="utf-8")
    source_b.write_text("<main>Research fixture observes audience response to process evidence.</main>\n", encoding="utf-8")
    blocked = project / "blocked-source.txt"
    blocked.write_text("403 Forbidden\n", encoding="utf-8")
    OPS.write_json(project / ".ariadne" / "creative-evidence.json", {
        "references": [
            {"id": "platform-official", "state": "inspected", "source": "https://platform.example.test/guidance", "evidence": OPS.evidence_record(source_a)},
            {"id": "platform-research", "state": "inspected", "source": "https://research.example.test/study", "evidence": OPS.evidence_record(source_b)},
            {"id": "platform-blocked", "state": "inaccessible", "source": "https://platform.example.test/blocked", "blocker": "403 Forbidden"}
        ]
    })
    return source_a, source_b


def strategy_event(project: Path, fixture: dict, asset: Path | None) -> tuple[dict, Path]:
    strategy_path = project / "SOCIAL-STRATEGY.md"
    strategy_path.write_text(
        f"# SOCIAL STRATEGY: {fixture['id']}\n\n## What I recommend\n\n"
        f"Use {', '.join(fixture['platforms'])} to show {fixture['story']['strongest_moment']}\n\n"
        "## What I'd post\n\nThree project-specific treatments.\n",
        encoding="utf-8",
    )
    visual = {
        "id": "primary-visual",
        "status": fixture["visual_status"],
        "description": fixture["visual"],
    }
    if asset is not None:
        visual["path"] = str(asset)
    voices = []
    for index in range(fixture["voice_examples"]):
        path = project / f"voice-example-{index + 1}.txt"
        path.write_text(f"A concise first-person project note {index + 1}.\n", encoding="utf-8")
        voices.append({"path": str(path)})
    today = datetime.now().astimezone().date().isoformat()
    concepts = []
    for index in range(3):
        platform = fixture["platforms"][index % len(fixture["platforms"])]
        concepts.append({
            "id": f"{fixture['id']}-post-{index + 1}",
            "platform": platform,
            "concept": f"Treatment {index + 1}: {fixture['story']['maker_decision']}",
            "format": "captioned visual sequence" if index == 0 else "project process note",
            "hook": f"{fixture['story']['specific_interest']} Treatment {index + 1} shows the consequence.",
            "draft": f"{fixture['story']['maker_decision']} {fixture['story']['specific_interest']} This treatment shows the evidence before making a broader claim.",
            "purpose": "Test whether the concrete project decision attracts the intended audience.",
            "visual_asset_id": "primary-visual",
            "cta": "none",
            "evidence_class": "inferred",
            "source_reference_ids": [],
            "hypothesis": f"Treatment {index + 1} may produce more qualified responses than a generic project announcement.",
        })
    pillars = [] if fixture["id"] == "weak-visual-assets" else [
        {"name": "The decision", "why": fixture["story"]["maker_decision"], "post_type": "decision evidence"},
        {"name": "The consequence", "why": fixture["story"]["specific_interest"], "post_type": "before and after"},
        {"name": "The useful lesson", "why": fixture["story"]["why"], "post_type": "bounded process note"},
    ]
    event = {
        "type": "social-strategy",
        "contract_version": 2,
        "id": f"strategy-{fixture['id']}",
        "activated_by": "I want to launch this project on social.",
        "research_depth": fixture["research_depth"],
        "audience": fixture["audience"],
        "project_story": fixture["story"],
        "project_evidence": [
            {"path": str(project / "PROJECT.md"), "anchor": fixture["goal"]},
            {"path": str(project / "DESIGN.md"), "anchor": fixture["story"]["strongest_moment"]},
        ],
        "platforms": [{"name": item, "why": f"{item} supports the project's {fixture['story']['specific_interest']} story."} for item in fixture["platforms"]],
        "not_recommended": [{"name": item, "why_not": "The current project material has no native treatment strong enough to justify this platform."} for item in fixture["not_recommended"]],
        "source_conflicts": [{
            "source_reference_ids": ["platform-official", "platform-research"],
            "resolution": "Use official format guidance for mechanics and treat audience response as a bounded test, not a promise."
        }],
        "recommendations": [{
            "platform": item,
            "recommendation": f"Test one native {item} treatment using the project's strongest evidence.",
            "finding": "The inspected fixture documents native visual formats without promising distribution.",
            "reason": f"The chosen treatment exposes {fixture['story']['strongest_moment']} instead of a generic announcement.",
            "evidence_class": "documented",
            "source_quality": "official-platform",
            "checked_on": today,
            "time_sensitive": true_value,
            "source_reference_ids": ["platform-official"],
        } for item in fixture["platforms"]],
        "visual_assets": [visual],
        "content_pillars": pillars,
        "pillars_decision": "Use one bounded launch sequence until a stronger visual exists." if not pillars else "",
        "content_concepts": concepts,
        "timing": "Run one treatment at a time at a cadence the owner can sustain.",
        "sequence": [item["id"] for item in concepts],
        "measurement": ["qualified replies", "saves", "clicks when supplied"],
        "iteration": "Change one treatment variable and preserve inconclusive outcomes.",
        "example_post": concepts[0]["draft"],
        "voice_basis": "provided-examples" if voices else "project-context",
        "voice_evidence": voices,
        "draft_status": "voice-matched" if voices else "rough-draft",
        "artifact_path": str(strategy_path),
    }
    return event, strategy_path


# JSON has no Python boolean token; keeping this named value makes generated
# fixture events easy to scan without encoding provider behaviour in fixture data.
true_value = True


def rejected(function) -> bool:
    try:
        function()
        return False
    except OPS.OperationsError:
        return True


def self_test() -> int:
    value = json.loads(FIXTURES.read_text(encoding="utf-8"))
    fixtures = value.get("fixtures", [])
    cases = []

    def case(name: str, passed: bool) -> None:
        cases.append((name, bool(passed)))

    case("social fixture schema is current", value.get("schema_version") == 1)
    case("five requested social archetypes exist", len(fixtures) == 5 and len({item["archetype"] for item in fixtures}) == 5)

    with workspace() as root:
        records = {}
        for fixture in fixtures:
            project, asset = fixture_project(root, fixture)
            source_a, _source_b = source_ledger(project)
            ledger = OPS.create_ledger(project)
            event, strategy_path = strategy_event(project, fixture, asset)
            OPS.record_social_strategy(project, ledger, copy.deepcopy(event))
            OPS.save_ledger(project, ledger)
            reloaded = OPS.load_ledger(project)
            records[fixture["id"]] = (project, ledger, event, strategy_path, source_a)
            latest = reloaded["social_strategies"][-1]
            case(f"{fixture['id']}: strategy survives a fresh task", not OPS.project_problems(project, "social"))
            case(f"{fixture['id']}: project story is artifact-backed", len(latest["project_evidence"]) == 2)
            case(f"{fixture['id']}: platform selection is bounded", 1 <= len(latest["platforms"]) <= 3)
            case(f"{fixture['id']}: three complete post treatments exist", len(latest["content_concepts"]) == 3 and all(item.get("draft") and item.get("hypothesis") for item in latest["content_concepts"]))
            case(f"{fixture['id']}: visual availability is explicit", latest["visual_assets"][0]["status"] == fixture["visual_status"])
            case(f"{fixture['id']}: current source changed a decision", all(item.get("finding") and item.get("recommendation") for item in latest["recommendations"]))
            if fixture["voice_examples"]:
                case(f"{fixture['id']}: voice claim has supplied examples", latest["draft_status"] == "voice-matched" and len(latest["voice_evidence"]) >= 2)
            else:
                case(f"{fixture['id']}: unsupported voice stays rough", latest["draft_status"] == "rough-draft")

        project, ledger, event, strategy_path, source_a = records["portfolio-launch"]
        missing_audience = copy.deepcopy(event)
        missing_audience.update({"id": "missing-audience", "audience": ""})
        case("no audience stops for the smallest useful question", rejected(lambda: OPS.record_social_strategy(project, ledger, missing_audience)))

        thin_story = copy.deepcopy(event)
        thin_story.update({"id": "thin-story", "project_story": {}})
        case("insufficient project information cannot become a story", rejected(lambda: OPS.record_social_strategy(project, ledger, thin_story)))

        no_visual_record = copy.deepcopy(event)
        no_visual_record.update({"id": "no-visual-record", "visual_assets": []})
        case("visual availability cannot be omitted", rejected(lambda: OPS.record_social_strategy(project, ledger, no_visual_record)))

        unresolved_conflict = copy.deepcopy(event)
        unresolved_conflict.update({"id": "unresolved-conflict", "source_conflicts": [{"source_reference_ids": ["platform-official", "platform-research"], "resolution": ""}]})
        case("conflicting platform evidence needs a resolution", rejected(lambda: OPS.record_social_strategy(project, ledger, unresolved_conflict)))

        outdated = copy.deepcopy(event)
        outdated.update({"id": "outdated-source"})
        outdated["recommendations"][0]["checked_on"] = (datetime.now().date() - timedelta(days=400)).isoformat()
        case("outdated current-platform evidence is rejected", rejected(lambda: OPS.record_social_strategy(project, ledger, outdated)))

        inaccessible = copy.deepcopy(event)
        inaccessible.update({"id": "inaccessible-source"})
        inaccessible["recommendations"][0]["source_reference_ids"] = ["platform-blocked"]
        case("inaccessible source cannot support a recommendation", rejected(lambda: OPS.record_social_strategy(project, ledger, inaccessible)))

        no_finding = copy.deepcopy(event)
        no_finding.update({"id": "no-finding"})
        no_finding["recommendations"][0]["finding"] = ""
        case("source URL alone cannot count as completed research", rejected(lambda: OPS.record_social_strategy(project, ledger, no_finding)))

        fake_voice = copy.deepcopy(event)
        fake_voice.update({"id": "fake-voice", "voice_basis": "provided-examples", "voice_evidence": [], "draft_status": "voice-matched"})
        case("voice matching cannot be claimed without examples", rejected(lambda: OPS.record_social_strategy(project, ledger, fake_voice)))

        generic = copy.deepcopy(event)
        generic.update({"id": "generic-copy"})
        generic["content_concepts"][0]["draft"] = "I'm excited to share this journey."
        case("generic AI copy is rejected inside every post", rejected(lambda: OPS.record_social_strategy(project, ledger, generic)))

        guaranteed = copy.deepcopy(event)
        guaranteed.update({"id": "guaranteed-reach"})
        guaranteed["content_concepts"][0]["hypothesis"] = "This will increase reach."
        case("unsupported performance promise is rejected", rejected(lambda: OPS.record_social_strategy(project, ledger, guaranteed)))

        project, ledger, event, strategy_path, source_a = records["performance-return"]
        strategy = ledger["social_strategies"][-1]
        result_ids = []
        for index, concept in enumerate(strategy["content_concepts"], start=1):
            result_evidence = project / f"result-{index}.csv"
            result_evidence.write_text(
                "impressions,saves,comments\n" + f"{900 + index * 100},{8 + index},{index}\n",
                encoding="utf-8",
            )
            result = {
                "id": f"result-{index}", "strategy_id": strategy["id"],
                "concept_id": concept["id"], "platform": concept["platform"],
                "observed_on": datetime.now().date().isoformat(), "provided_by": "user",
                "metrics": {"impressions": 900 + index * 100, "saves": 8 + index, "comments": index},
                "qualitative_signals": ["One film programmer asked for the full programme."],
                "evidence_path": str(result_evidence),
            }
            OPS.record_social_result(ledger, result)
            result_ids.append(result["id"])
        learnings = project / "CONTENT-LEARNINGS.md"
        learnings.write_text(
            "# CONTENT LEARNINGS\n\nPLAN: editorial framing.\nRESULT: three supplied records.\n"
            "INTERPRETATION: useful replies appeared, but reach remains noisy.\n"
            "NEXT TEST: change only the opening frame.\n",
            encoding="utf-8",
        )
        OPS.record_social_learning(ledger, {
            "id": "learning-1", "strategy_id": strategy["id"], "result_ids": result_ids,
            "outcome": "supported", "confidence": "limited",
            "interpretation": "The editorial programme framing coincided with qualified replies across three treatments; reach remains uncontrolled.",
            "next_test": {"hypothesis": "Opening on the programme connection may retain qualified attention.", "variable": "opening frame", "measure": "qualified replies and saves"},
            "promoted_rule": "Lead with a programme connection before logistical screening detail.",
            "artifact_path": str(learnings),
        })
        OPS.save_ledger(project, ledger)
        fresh = OPS.load_ledger(project)
        case("user-supplied performance results remain distinct from strategy", len(fresh["social_results"]) == 3 and len(fresh["social_learnings"]) == 1)
        case("PLAN RESULT INTERPRETATION NEXT TEST survives a fresh task", not OPS.project_problems(project, "social-learning"))
        case("project learning stays in the project", Path(fresh["social_learnings"][0]["artifact"]["path"]).parent == project)

        result_template = {
            "id": "bad-result", "strategy_id": strategy["id"],
            "concept_id": strategy["content_concepts"][0]["id"], "platform": "Instagram",
            "observed_on": datetime.now().date().isoformat(), "provided_by": "provider",
            "metrics": {"impressions": 100}, "qualitative_signals": [],
            "evidence_path": str(project / "result-1.csv"),
        }
        case("provider-generated metric is rejected as fabricated evidence", rejected(lambda: OPS.record_social_result(ledger, copy.deepcopy(result_template))))
        empty_result = copy.deepcopy(result_template)
        empty_result.update({"id": "empty-result", "provided_by": "user", "metrics": {}, "qualitative_signals": []})
        case("no performance data cannot produce a result", rejected(lambda: OPS.record_social_result(ledger, empty_result)))
        unknown_metric = copy.deepcopy(result_template)
        unknown_metric.update({"id": "unknown-metric", "provided_by": "user", "metrics": {"virality_score": 99}})
        case("unsupported metric names are rejected", rejected(lambda: OPS.record_social_result(ledger, unknown_metric)))

        duplicate = copy.deepcopy(result_template)
        duplicate.update({"id": "contradictory-result", "provided_by": "user"})
        case("contradictory performance data cannot overwrite an observation", rejected(lambda: OPS.record_social_result(ledger, duplicate)))

        correction = copy.deepcopy(duplicate)
        correction.update({
            "id": "corrected-result", "revises": result_ids[0],
            "correction_reason": "The first export omitted saves.",
        })
        OPS.record_social_result(ledger, correction)
        case(
            "explicit correction preserves both performance records",
            len([item for item in ledger["social_results"] if item["concept_id"] == correction["concept_id"]]) == 2,
        )
        case(
            "corrected data makes the prior learning explicitly stale",
            any("superseded" in item for item in OPS.ledger_problems(project, ledger)),
        )

        one_result_learning = {
            "id": "overclaim", "strategy_id": strategy["id"], "result_ids": [result_ids[0]],
            "outcome": "supported", "confidence": "weak", "interpretation": "One post proves the pattern.",
            "next_test": {"hypothesis": "Test again.", "variable": "opening frame", "measure": "saves"},
            "artifact_path": str(learnings),
        }
        case("one post cannot establish a performance learning", rejected(lambda: OPS.record_social_learning(ledger, one_result_learning)))

        creative = CREATIVE.create_ledger(project, CREATIVE.low_assessment())
        CREATIVE.activate_optional_skill(creative, {
            "skill": "social-strategy",
            "explicit_request": "I want to launch this project on social.",
        })
        CREATIVE.record_skill_event(creative, {"skill": "social-strategy", "state": "invoked", "evidence_path": str(source_a)})
        CREATIVE.record_skill_event(creative, {"skill": "social-strategy", "state": "completed", "output_path": str(strategy_path), "result": "Project-aware strategy recorded.", "usefulness": "useful"})
        CREATIVE.record_decision(creative, {"id": "social-decision", "decision": "Use the editorial programme frame.", "principle": "The actual project mechanism should lead distribution.", "basis": "thesis", "reference_ids": [], "artifact_path": str(strategy_path), "artifact_anchor": "What I recommend", "status": "proposed", "gate": "G5 pending"})
        CREATIVE.record_skill_event(creative, {"skill": "social-strategy", "state": "used", "downstream_path": str(strategy_path), "decision_ids": ["social-decision"]})
        social_history = next(item for item in creative["skills"] if item["name"] == "social-strategy")
        case(
            "late social request preserves skipped recommended invoked completed used history",
            social_history["state"] == "used"
            and [item["state"] for item in social_history["history"]][-4:]
            == ["recommended", "invoked", "completed", "used"],
        )

        saved_learning = learnings.read_text(encoding="utf-8")
        learnings.write_text(saved_learning + "changed without a new event\n", encoding="utf-8")
        case("changed learning evidence becomes stale", any("social learning" in item and "changed" in item for item in OPS.ledger_problems(project, fresh)))
        learnings.write_text(saved_learning, encoding="utf-8")

    print("V1.5.2 SOCIAL INTELLIGENCE SELF-TEST\n")
    for name, passed in cases:
        print(("ok    " if passed else "FAIL  ") + name)
    failed = [name for name, passed in cases if not passed]
    print(f"\n{'FAILED' if failed else 'PASS'}  {len(cases) - len(failed)}/{len(cases)}")
    return 1 if failed else 0


def main() -> int:
    return self_test()


if __name__ == "__main__":
    sys.exit(main())
