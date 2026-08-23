#!/usr/bin/env python3
"""Project-local creative planning, provenance, and anti-assertion checks.

This module owns a small evidence schema, not creative policy. Canonical Builder
OS skills and policies still decide what good research and design mean. The
ledger records what was selected, what actually ran, which source artifact
supports an inspection claim, and where a result was used downstream.
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import re
import shutil
import sys
import uuid
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SCHEMA_VERSION = 1
LEDGER_RELATIVE = Path(".ariadne") / "creative-evidence.json"
LEVELS = ("low", "medium", "high")
DIMENSIONS = (
    "novelty",
    "uncertainty",
    "visual_dependence",
    "technical_uncertainty",
    "domain_complexity",
    "reference_sensitivity",
    "generic_risk",
    "interaction_complexity",
    "asset_uncertainty",
    "motion_dependence",
)
SKILL_STATES = ("recommended", "invoked", "completed", "used", "skipped", "failed")
SKILL_TRANSITIONS = {
    "recommended": {"invoked", "skipped"},
    "invoked": {"completed", "failed"},
    "completed": {"used"},
    "used": {"used"},
    "skipped": set(),
    "failed": set(),
}
REFERENCE_STATES = ("found", "inspected", "inaccessible")
INSPECTION_KINDS = ("content", "visual", "interaction")
RESOURCE_CATEGORIES = (
    "library", "framework", "browser-api", "font", "icon-set", "asset-source",
    "image-source", "technique", "design-tool", "component-primitive",
)
RESOURCE_DECISIONS = ("use", "do-not-use", "defer")
STAGE_ORDER = {"S1": 1, "S2": 2, "S3": 3, "S4A": 4, "S4B": 5, "S5": 6}


class CreativeError(RuntimeError):
    pass


def now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


def read_json(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CreativeError(f"creative evidence is malformed: {exc}") from exc
    if not isinstance(value, dict):
        raise CreativeError("creative evidence must be a JSON object")
    return value


def ledger_path(project: Path) -> Path:
    return project.resolve() / LEDGER_RELATIVE


def evidence_record(path: Path) -> dict:
    path = path.resolve()
    if not path.is_file() or path.stat().st_size == 0:
        raise CreativeError(f"evidence artifact is missing or empty: {path}")
    if path.name.lower() == ".env" or path.name.lower().startswith(".env."):
        raise CreativeError("credential files cannot be creative evidence")
    return {"path": str(path), "sha256": digest(path)}


def _assessment_item(assessment: dict, name: str) -> dict:
    value = assessment.get("characteristics", {}).get(name)
    if not isinstance(value, dict):
        raise CreativeError(f"creative assessment is missing characteristic: {name}")
    level = value.get("level")
    reason = str(value.get("reason", "")).strip()
    if level not in LEVELS or not reason:
        raise CreativeError(f"creative assessment characteristic {name} needs level and reason")
    return {"level": level, "reason": reason}


def validate_assessment(assessment: dict) -> dict:
    if not isinstance(assessment, dict):
        raise CreativeError("creative assessment must be a JSON object")
    normalised = {"characteristics": {}}
    for name in DIMENSIONS:
        normalised["characteristics"][name] = _assessment_item(assessment, name)
    normalised["references_supplied"] = bool(assessment.get("references_supplied", False))
    alternative = assessment.get("alternatives_helpful")
    if not isinstance(alternative, dict) or not isinstance(alternative.get("value"), bool):
        raise CreativeError("alternatives_helpful needs a boolean value and reason")
    alternative_reason = str(alternative.get("reason", "")).strip()
    if not alternative_reason:
        raise CreativeError("alternatives_helpful needs a reason")
    normalised["alternatives_helpful"] = {
        "value": alternative["value"], "reason": alternative_reason
    }
    social = assessment.get("social_request", {"value": False, "request": ""})
    if not isinstance(social, dict) or not isinstance(social.get("value"), bool):
        raise CreativeError("social_request needs a boolean value")
    social_request = str(social.get("request", "")).strip()
    if social["value"] and not social_request:
        raise CreativeError("an activated social strategy needs the user's explicit request")
    normalised["social_request"] = {"value": social["value"], "request": social_request}
    questions = assessment.get("research_questions", [])
    if not isinstance(questions, list):
        raise CreativeError("research_questions must be a list")
    normalised["research_questions"] = []
    for index, question in enumerate(questions, 1):
        if not isinstance(question, dict):
            raise CreativeError(f"research question {index} must be an object")
        row = {
            "id": str(question.get("id") or f"rq-{index}"),
            "question": str(question.get("question", "")).strip(),
            "reason": str(question.get("reason", "")).strip(),
            "strategy": str(question.get("strategy", "")).strip(),
            "kind": str(question.get("kind", "")).strip(),
            "blocking": bool(question.get("blocking", False)),
            "status": "planned",
        }
        if not all(row[key] for key in ("question", "reason", "strategy")):
            raise CreativeError(f"research question {row['id']} needs question, reason, and strategy")
        if row["kind"] not in ("reference", "technical", "domain", "resource", "asset"):
            raise CreativeError(f"research question {row['id']} has unsupported kind")
        normalised["research_questions"].append(row)
    ids = [item["id"] for item in normalised["research_questions"]]
    if len(ids) != len(set(ids)):
        raise CreativeError("research question IDs must be unique")
    return normalised


def research_depth(assessment: dict) -> str:
    values = assessment["characteristics"]
    scored = [values[name]["level"] for name in DIMENSIONS[:7]]
    score = sum({"low": 0, "medium": 1, "high": 2}[level] for level in scored)
    highs = scored.count("high")
    if highs >= 3 or score >= 9:
        return "deep"
    if highs or score >= 3 or assessment["research_questions"]:
        return "standard"
    return "minimal"


def _skill(
    name: str,
    stage: str,
    mandatory: bool,
    reason: str,
    question: str,
    inputs: list[str],
    output: str,
    selected: bool = True,
) -> dict:
    recorded = now()
    return {
        "name": name,
        "stage": stage,
        "mandatory": mandatory,
        "selected": selected,
        "reason": reason,
        "question": question,
        "inputs": inputs,
        "expected_output": output,
        "state": "recommended" if selected else "skipped",
        "history": [{
            "state": "recommended" if selected else "skipped",
            "recorded_at": recorded,
            "reason": reason,
        }],
    }


def create_ledger(project: Path, assessment_value: dict) -> dict:
    project = project.resolve()
    assessment = validate_assessment(assessment_value)
    c = assessment["characteristics"]
    supplied = assessment["references_supplied"]
    reference_level = max(
        (c["visual_dependence"]["level"], c["reference_sensitivity"]["level"], c["generic_risk"]["level"]),
        key=LEVELS.index,
    )
    reference_selected = supplied or reference_level != "low"
    reference_mandatory = supplied or reference_level == "high"
    component_level = max(
        (c["technical_uncertainty"]["level"], c["interaction_complexity"]["level"]),
        key=LEVELS.index,
    )
    component_selected = component_level != "low"
    technical_questions = [
        item for item in assessment["research_questions"]
        if item["kind"] in ("technical", "resource", "domain")
    ]
    technical_selected = bool(technical_questions) or c["technical_uncertainty"]["level"] != "low"
    asset_selected = c["asset_uncertainty"]["level"] != "low" or any(
        item["kind"] == "asset" for item in assessment["research_questions"]
    )
    motion_selected = c["motion_dependence"]["level"] != "low"
    visual_qa_selected = any(
        c[name]["level"] != "low"
        for name in ("visual_dependence", "interaction_complexity", "motion_dependence", "generic_risk")
    )
    creative_review_selected = visual_qa_selected or c["novelty"]["level"] == "high"
    social_selected = assessment["social_request"]["value"]

    skills = [
        _skill("intake", "S1", True, "Every project needs a falsifiable brief before creative work.",
               "What problem, audience, outcome, constraints, and non-goals define the work?",
               ["ordinary-language request"], "PROJECT.md"),
        _skill("technical-research", "S2", any(item["blocking"] for item in technical_questions),
               "A current fact or implementation uncertainty needs evidence." if technical_selected else
               "No current fact or technical uncertainty needs a separate research pass.",
               "Which external facts or techniques must be verified before direction?",
               ["PROJECT.md open questions", "research plan"], "RESEARCH.md", technical_selected),
        _skill("reference-analysis", "S3", reference_mandatory,
               "The visual language is reference-sensitive or at risk of becoming generic." if reference_selected else
               "The project can derive its direction from its subject without external visual references.",
               "Which inspected mechanisms can inform a project-specific direction without copying a surface?",
               ["PROJECT.md", "retrieval or visual evidence"], "reference mechanisms and trace records",
               reference_selected),
        _skill("component-research", "S3", component_level == "high",
               "A non-trivial interaction or technical mechanism needs comparison." if component_selected else
               "No non-trivial interaction currently justifies component research.",
               "What technique meets the interaction requirement with the least dependency cost?",
               ["interaction requirement", "source evidence"], "technique and build-or-install decision",
               component_selected),
        _skill("motion", "S3", c["motion_dependence"]["level"] == "high",
               "Motion carries project meaning." if motion_selected else "Motion is not required by the current brief.",
               "What structural purpose would motion serve?", ["PROJECT.md"], "motion rationale", motion_selected),
        _skill("asset-research", "S3", c["asset_uncertainty"]["level"] == "high",
               "The direction may depend on unresolved assets or licences." if asset_selected else
               "No unresolved asset need currently warrants research.",
               "Which assets are necessary, obtainable, and licensable?", ["PROJECT.md"], "asset decision", asset_selected),
        _skill("design-direction", "S3", True, "Every build mode needs a testable direction before G1.",
               "What thesis, tension, signature, and rejection set make this project specific?",
               ["PROJECT.md", "completed selected research"], "DESIGN.md"),
        _skill("implementation-planning", "S4A", True, "Approved direction must become bounded build context.",
               "What exactly should the implementer build and preserve?", ["PROJECT.md", "DESIGN.md"], "HANDOFF.md"),
        _skill("QA", "S4B", True, "Implementation claims need mechanical evidence.",
               "Does the implementation meet the approved requirements?", ["HANDOFF.md", "built project"], "QA.md"),
        _skill("visual-qa", "S4B", c["visual_dependence"]["level"] == "high",
               "Rendered project-specific behaviour needs evidence." if visual_qa_selected else
               "No visual, interaction, motion, or genericness risk currently justifies a visual pass.",
               "Which thesis-critical behaviours and responsive transformations need rendered evidence?",
               ["locked DESIGN.md", "rendered target", ".ariadne/creative-operations.json"],
               "visual evidence and drift findings", visual_qa_selected),
        _skill("creative-review", "S4B", c["generic_risk"]["level"] == "high",
               "The rendered result needs an actionable creative-quality judgement." if creative_review_selected else
               "The current project does not justify a separate internal creative review.",
               "Is the implemented result actually strong, and what single change matters most?",
               ["rendered visual evidence", "approved requirement trace"],
               "creative review event", creative_review_selected),
        _skill("independent-review", "S5", True, "Creative quality needs judgement isolated from build context.",
               "Is the finished work strong enough for the intended audience?", ["isolated live target"], "QA judgement"),
        _skill("social-strategy", "optional", social_selected,
               "The user explicitly requested a project-aware social strategy." if social_selected else
               "No explicit social strategy request exists; this optional capability stays off.",
               "Which audience, platforms, content sequence, and evidence fit this specific project?",
               ["project context", "current inspected platform evidence", "voice examples if supplied"],
               "SOCIAL-STRATEGY.md", social_selected),
    ]
    created = now()
    return {
        "schema_version": SCHEMA_VERSION,
        "project": str(project),
        "created_at": created,
        "updated_at": created,
        "research_depth": research_depth(assessment),
        "assessment": assessment,
        "skills": skills,
        "references": [],
        "resources": [],
        "decisions": [],
        "conflicts": [],
        "directions": [],
    }


def load_ledger(project: Path) -> dict | None:
    path = ledger_path(project)
    return read_json(path) if path.is_file() else None


def save_ledger(project: Path, ledger: dict) -> Path:
    ledger["updated_at"] = now()
    path = ledger_path(project)
    write_json(path, ledger)
    return path


def _skill_by_name(ledger: dict, name: str) -> dict:
    matches = [item for item in ledger.get("skills", []) if item.get("name") == name]
    if len(matches) != 1:
        raise CreativeError(f"creative plan does not contain one skill named {name}")
    return matches[0]


def activate_optional_skill(ledger: dict, event: dict) -> None:
    name = str(event.get("skill", "")).strip()
    request = str(event.get("explicit_request", "")).strip()
    skill = _skill_by_name(ledger, name)
    if skill.get("mandatory"):
        raise CreativeError("mandatory creative work cannot use optional late activation")
    if skill.get("state") != "skipped":
        raise CreativeError(f"optional late activation requires a skipped skill: {name}")
    if not request:
        raise CreativeError("optional late activation needs the user's explicit request")
    skill["selected"] = True
    skill["state"] = "recommended"
    skill["reason"] = "The user explicitly activated this optional capability after intake."
    skill.setdefault("history", []).append({
        "state": "recommended",
        "activated_by": request,
        "recorded_at": now(),
    })


def record_skill_event(ledger: dict, event: dict) -> None:
    name = str(event.get("skill", "")).strip()
    state = str(event.get("state", "")).strip()
    skill = _skill_by_name(ledger, name)
    if state not in SKILL_STATES[1:]:
        raise CreativeError(f"unsupported skill evidence state: {state}")
    current = skill.get("state")
    if state not in SKILL_TRANSITIONS.get(current, set()):
        raise CreativeError(f"invalid skill transition for {name}: {current} -> {state}")
    if state == "skipped" and skill.get("mandatory"):
        raise CreativeError(f"mandatory skill cannot be skipped: {name}")
    row = {"state": state, "recorded_at": now()}
    reason = str(event.get("reason", "")).strip()
    if state in ("skipped", "failed"):
        if not reason:
            raise CreativeError(f"{state} skill evidence needs a reason")
        row["reason"] = reason
    if state == "invoked":
        row["evidence"] = evidence_record(Path(str(event.get("evidence_path", ""))))
    if state == "completed":
        row["output"] = evidence_record(Path(str(event.get("output_path", ""))))
        usefulness = str(event.get("usefulness", "useful"))
        if usefulness not in ("useful", "not-useful"):
            raise CreativeError("completed skill usefulness must be useful or not-useful")
        row["usefulness"] = usefulness
        row["result"] = str(event.get("result", "")).strip() or "output recorded"
    if state == "used":
        if skill.get("history", [])[-1].get("usefulness") == "not-useful":
            raise CreativeError(f"skill output recorded as not useful cannot be marked used: {name}")
        row["downstream"] = evidence_record(Path(str(event.get("downstream_path", ""))))
        decisions = event.get("decision_ids", [])
        known = {item.get("id") for item in ledger.get("decisions", [])}
        if not isinstance(decisions, list) or not decisions or any(item not in known for item in decisions):
            raise CreativeError("used skill evidence needs existing downstream decision IDs")
        row["decision_ids"] = decisions
    skill["state"] = state
    skill.setdefault("history", []).append(row)


def record_reference(ledger: dict, event: dict) -> None:
    reference_id = str(event.get("id", "")).strip()
    source = str(event.get("source", "")).strip()
    state = str(event.get("state", "")).strip()
    if not reference_id or not source or state not in REFERENCE_STATES:
        raise CreativeError("reference evidence needs id, source, and a valid state")
    existing = next((item for item in ledger.get("references", []) if item.get("id") == reference_id), None)
    if existing and existing.get("source") != source:
        raise CreativeError(f"reference ID {reference_id} already records a different source")
    if existing and existing.get("state") != "found":
        raise CreativeError(f"reference evidence is already terminal: {reference_id}")
    row = existing or {"id": reference_id, "source": source, "found_at": now(), "used_by": []}
    row["state"] = state
    if state == "inspected":
        kind = str(event.get("inspection", "")).strip()
        observations = event.get("observations", [])
        mechanisms = event.get("mechanisms", [])
        if kind not in INSPECTION_KINDS:
            raise CreativeError("inspected reference needs content, visual, or interaction inspection")
        if not isinstance(observations, list) or not observations or not all(str(item).strip() for item in observations):
            raise CreativeError("inspected reference needs concrete observations")
        if not isinstance(mechanisms, list) or len(mechanisms) > 2:
            raise CreativeError("a reference may contribute at most two mechanisms")
        row.update({
            "inspected_at": str(event.get("inspected_at") or now()),
            "inspection": kind,
            "evidence": evidence_record(Path(str(event.get("evidence_path", "")))),
            "observations": [str(item).strip() for item in observations],
            "mechanisms": [str(item).strip() for item in mechanisms if str(item).strip()],
            "why_it_matters": str(event.get("why_it_matters", "")).strip(),
            "borrow": str(event.get("borrow", "")).strip(),
            "reject": str(event.get("reject", "")).strip(),
        })
        if not all(row[key] for key in ("why_it_matters", "borrow", "reject")):
            raise CreativeError("inspected reference needs why, borrow, and reject decisions")
    elif state == "inaccessible":
        blocker = str(event.get("blocker", "")).strip()
        if not blocker:
            raise CreativeError("inaccessible reference needs the observed blocker")
        if event.get("observations") or event.get("mechanisms"):
            raise CreativeError("an inaccessible reference cannot carry observations or mechanisms")
        row.update({"attempted_at": str(event.get("attempted_at") or now()), "blocker": blocker})
        if event.get("evidence_path"):
            row["attempt_evidence"] = evidence_record(Path(str(event["evidence_path"])))
    if not existing:
        ledger.setdefault("references", []).append(row)


def record_resource(ledger: dict, event: dict) -> None:
    resource_id = str(event.get("id", "")).strip()
    name = str(event.get("name", "")).strip()
    category = str(event.get("category", "")).strip()
    decision = str(event.get("decision", "")).strip()
    if not resource_id or not name or category not in RESOURCE_CATEGORIES:
        raise CreativeError("resource evidence needs id, name, and a valid category")
    if decision not in RESOURCE_DECISIONS:
        raise CreativeError("resource evidence needs use, do-not-use, or defer decision")
    if any(item.get("id") == resource_id for item in ledger.get("resources", [])):
        raise CreativeError(f"resource ID is already recorded: {resource_id}")
    alternatives = event.get("alternatives", [])
    if (
        not isinstance(alternatives, list)
        or not alternatives
        or not all(
            isinstance(item, dict)
            and str(item.get("name", "")).strip()
            and str(item.get("reason", "")).strip()
            for item in alternatives
        )
    ):
        raise CreativeError("resource evidence needs at least one named alternative and reason")
    reference_ids = event.get("source_reference_ids", [])
    references = {item.get("id"): item for item in ledger.get("references", [])}
    if not isinstance(reference_ids, list) or not reference_ids:
        raise CreativeError("resource evidence needs at least one inspected source reference")
    for reference_id in reference_ids:
        reference = references.get(reference_id)
        if not reference or reference.get("state") != "inspected":
            raise CreativeError(f"resource cites an uninspected source: {reference_id}")
    artifact = evidence_record(Path(str(event.get("artifact_path", ""))))
    anchor = str(event.get("artifact_anchor", "")).strip()
    if not anchor or anchor not in Path(artifact["path"]).read_text(encoding="utf-8"):
        raise CreativeError("resource decision anchor is not present in the downstream artifact")
    row = {
        "id": resource_id,
        "name": name,
        "category": category,
        "provides": str(event.get("provides", "")).strip(),
        "appropriate_because": str(event.get("appropriate_because", "")).strip(),
        "compatibility": str(event.get("compatibility", "")).strip(),
        "license": str(event.get("license", "")).strip(),
        "implementation_cost": str(event.get("implementation_cost", "")).strip(),
        "alternatives": [
            {"name": str(item["name"]).strip(), "reason": str(item["reason"]).strip()}
            for item in alternatives
        ],
        "necessary": bool(event.get("necessary", False)),
        "decision": decision,
        "source_reference_ids": reference_ids,
        "artifact": artifact,
        "artifact_anchor": anchor,
        "recorded_at": now(),
    }
    if not all(
        row[key]
        for key in ("provides", "appropriate_because", "compatibility", "license", "implementation_cost")
    ):
        raise CreativeError(
            "resource evidence needs provides, why, compatibility, licence, and implementation cost"
        )
    if decision == "use" and not row["necessary"]:
        raise CreativeError("a resource selected for use must be marked necessary")
    if decision == "do-not-use" and row["necessary"]:
        raise CreativeError("a rejected resource cannot be marked necessary")
    ledger.setdefault("resources", []).append(row)


def record_decision(ledger: dict, event: dict) -> None:
    decision_id = str(event.get("id", "")).strip()
    decision = str(event.get("decision", "")).strip()
    principle = str(event.get("principle", "")).strip()
    basis = str(event.get("basis", "")).strip()
    if not decision_id or not decision or not principle or basis not in ("reference", "research", "thesis", "constraint"):
        raise CreativeError("decision evidence needs id, decision, principle, and a valid basis")
    if any(item.get("id") == decision_id for item in ledger.get("decisions", [])):
        raise CreativeError(f"decision ID is already recorded: {decision_id}")
    artifact = evidence_record(Path(str(event.get("artifact_path", ""))))
    anchor = str(event.get("artifact_anchor", "")).strip()
    if not anchor or anchor not in Path(artifact["path"]).read_text(encoding="utf-8"):
        raise CreativeError("decision anchor is not present in the downstream artifact")
    reference_ids = event.get("reference_ids", [])
    if not isinstance(reference_ids, list):
        raise CreativeError("decision reference_ids must be a list")
    references = {item.get("id"): item for item in ledger.get("references", [])}
    if basis == "reference" and not reference_ids:
        raise CreativeError("reference-based decision needs at least one reference ID")
    for reference_id in reference_ids:
        reference = references.get(reference_id)
        if not reference or reference.get("state") != "inspected":
            raise CreativeError(f"decision cites an uninspected reference: {reference_id}")
    row = {
        "id": decision_id,
        "decision": decision,
        "principle": principle,
        "basis": basis,
        "reference_ids": reference_ids,
        "artifact": artifact,
        "artifact_anchor": anchor,
        "status": str(event.get("status", "proposed")),
        "gate": str(event.get("gate", "pending")),
        "recorded_at": now(),
    }
    ledger.setdefault("decisions", []).append(row)
    for reference_id in reference_ids:
        references[reference_id].setdefault("used_by", []).append(decision_id)


def record_conflict(ledger: dict, event: dict) -> None:
    references = event.get("reference_ids", [])
    implication = str(event.get("implication", "")).strip()
    known = {item.get("id") for item in ledger.get("references", [])}
    if not isinstance(references, list) or len(references) < 2 or len(set(references)) != len(references):
        raise CreativeError("reference conflict needs at least two distinct reference IDs")
    if any(item not in known for item in references) or not implication:
        raise CreativeError("reference conflict needs known references and a design implication")
    ledger.setdefault("conflicts", []).append({
        "reference_ids": references, "implication": implication, "recorded_at": now()
    })


def _generic_thesis(thesis: str) -> bool:
    return bool(re.search(r"\b(clean|modern|minimal|premium|sleek|elegant|sophisticated|immersive)\b", thesis, re.I))


def record_direction(ledger: dict, event: dict) -> None:
    row = {
        "id": str(event.get("id", "")).strip(),
        "thesis": str(event.get("thesis", "")).strip(),
        "mechanism": str(event.get("mechanism", "")).strip(),
        "experience": str(event.get("experience", "")).strip(),
        "status": str(event.get("status", "candidate")).strip(),
        "recorded_at": now(),
    }
    if not all(row[key] for key in ("id", "thesis", "mechanism", "experience")):
        raise CreativeError("direction candidate needs id, thesis, mechanism, and experience")
    if _generic_thesis(row["thesis"]):
        raise CreativeError("direction thesis uses generic mood language")
    if any(item.get("id") == row["id"] for item in ledger.get("directions", [])):
        raise CreativeError(f"direction ID is already recorded: {row['id']}")
    ledger.setdefault("directions", []).append(row)


def apply_event(ledger: dict, event: dict) -> None:
    if not isinstance(event, dict):
        raise CreativeError("creative evidence event must be an object")
    kind = event.get("type")
    if kind == "skill-activation":
        activate_optional_skill(ledger, event)
    elif kind == "skill":
        record_skill_event(ledger, event)
    elif kind == "reference":
        record_reference(ledger, event)
    elif kind == "resource":
        record_resource(ledger, event)
    elif kind == "decision":
        record_decision(ledger, event)
    elif kind == "conflict":
        record_conflict(ledger, event)
    elif kind == "direction":
        record_direction(ledger, event)
    else:
        raise CreativeError(f"unsupported creative evidence event type: {kind}")


def apply_events(ledger: dict, value: dict | list) -> None:
    events = value.get("events") if isinstance(value, dict) and "events" in value else value
    if isinstance(events, dict):
        events = [events]
    if not isinstance(events, list) or not events:
        raise CreativeError("creative evidence input needs one or more events")
    for event in events:
        apply_event(ledger, event)
    ledger["updated_at"] = now()


def _section(text: str, heading: str) -> str:
    match = re.search(
        rf"(?ms)^##\s+{re.escape(heading)}\s*$\r?\n(.*?)(?=^##\s+|\Z)", text
    )
    return match.group(1) if match else ""


def _table_rows(section: str) -> list[list[str]]:
    rows = []
    for line in section.splitlines():
        if not line.strip().startswith("|"):
            continue
        cells = [re.sub(r"[`*_]", "", cell.strip()) for cell in line.strip().strip("|").split("|")]
        if all(re.fullmatch(r"[-: ]*", cell) for cell in cells):
            continue
        rows.append(cells)
    return rows[1:] if len(rows) > 1 else []


def _url(value: str) -> str:
    match = re.search(r"https?://[^\s|)>]+", value)
    return match.group(0).rstrip(".,;") if match else ""


def _artifact_problems(record: dict, label: str) -> list[str]:
    path = Path(str(record.get("path", "")))
    if not path.is_file():
        return [f"{label} artifact is missing: {path}"]
    if digest(path) != record.get("sha256"):
        return [f"{label} artifact changed after evidence was recorded: {path}"]
    return []


def ledger_problems(project: Path, ledger: dict) -> list[str]:
    project = project.resolve()
    problems = []
    if ledger.get("schema_version") != SCHEMA_VERSION:
        problems.append("creative evidence has unsupported schema version")
    try:
        if Path(str(ledger.get("project", ""))).resolve() != project:
            problems.append("creative evidence records a different project")
    except OSError:
        problems.append("creative evidence project path is invalid")
    if ledger.get("research_depth") not in ("minimal", "standard", "deep"):
        problems.append("creative evidence has invalid research depth")
    skills = ledger.get("skills", [])
    names = [item.get("name") for item in skills if isinstance(item, dict)]
    if len(names) != len(set(names)):
        problems.append("creative evidence duplicates a skill")
    for skill in skills:
        if skill.get("state") not in SKILL_STATES:
            problems.append(f"skill has invalid state: {skill.get('name')}")
        history = skill.get("history", [])
        if not history or history[-1].get("state") != skill.get("state"):
            problems.append(f"skill history does not match current state: {skill.get('name')}")
        expected_initial = "recommended" if skill.get("selected") else "skipped"
        if history and history[0].get("state") != expected_initial:
            problems.append(f"skill history has invalid initial state: {skill.get('name')}")
        previous = None
        for index, event in enumerate(history):
            state = event.get("state")
            if state not in SKILL_STATES:
                problems.append(f"skill history has invalid state: {skill.get('name')} event {index + 1}")
            elif previous is not None and state not in SKILL_TRANSITIONS.get(previous, set()):
                problems.append(
                    f"skill history has invalid transition: {skill.get('name')} {previous} -> {state}"
                )
            previous = state
        for event in history:
            if event.get("evidence"):
                problems.extend(_artifact_problems(event["evidence"], f"{skill.get('name')} invocation"))
            if event.get("output"):
                problems.extend(_artifact_problems(event["output"], f"{skill.get('name')} output"))
            if event.get("downstream"):
                problems.extend(_artifact_problems(event["downstream"], f"{skill.get('name')} downstream"))
    references = ledger.get("references", [])
    reference_ids = [item.get("id") for item in references]
    if len(reference_ids) != len(set(reference_ids)):
        problems.append("creative evidence duplicates a reference ID")
    for reference in references:
        state = reference.get("state")
        if state not in REFERENCE_STATES:
            problems.append(f"reference has invalid state: {reference.get('id')}")
        if state == "inspected":
            problems.extend(_artifact_problems(reference.get("evidence", {}), f"reference {reference.get('id')}"))
            if not reference.get("observations"):
                problems.append(f"inspected reference has no observations: {reference.get('id')}")
            if len(reference.get("mechanisms", [])) > 2:
                problems.append(f"reference contributes more than two mechanisms: {reference.get('id')}")
        if state == "inaccessible" and (reference.get("observations") or reference.get("mechanisms")):
            problems.append(f"inaccessible reference carries invented observations: {reference.get('id')}")
    resources = ledger.get("resources", [])
    resource_ids = [item.get("id") for item in resources]
    if len(resource_ids) != len(set(resource_ids)):
        problems.append("creative evidence duplicates a resource ID")
    references_by_id = {item.get("id"): item for item in references}
    for resource in resources:
        if resource.get("category") not in RESOURCE_CATEGORIES:
            problems.append(f"resource has invalid category: {resource.get('id')}")
        if resource.get("decision") not in RESOURCE_DECISIONS:
            problems.append(f"resource has invalid decision: {resource.get('id')}")
        if not resource.get("alternatives"):
            problems.append(f"resource has no considered alternative: {resource.get('id')}")
        if resource.get("decision") == "use" and not resource.get("necessary"):
            problems.append(f"selected resource is not marked necessary: {resource.get('id')}")
        if resource.get("decision") == "do-not-use" and resource.get("necessary"):
            problems.append(f"rejected resource is marked necessary: {resource.get('id')}")
        source_ids = resource.get("source_reference_ids", [])
        if not source_ids:
            problems.append(f"resource has no inspected source: {resource.get('id')}")
        for reference_id in source_ids:
            reference = references_by_id.get(reference_id)
            if not reference or reference.get("state") != "inspected":
                problems.append(f"resource cites uninspected source: {resource.get('id')} -> {reference_id}")
        problems.extend(_artifact_problems(resource.get("artifact", {}), f"resource {resource.get('id')}"))
        artifact_path = Path(str(resource.get("artifact", {}).get("path", "")))
        if artifact_path.is_file() and resource.get("artifact_anchor") not in artifact_path.read_text(encoding="utf-8"):
            problems.append(f"resource decision anchor disappeared: {resource.get('id')}")
    decisions = ledger.get("decisions", [])
    decision_ids = {item.get("id") for item in decisions}
    for decision in decisions:
        problems.extend(_artifact_problems(decision.get("artifact", {}), f"decision {decision.get('id')}"))
        artifact_path = Path(str(decision.get("artifact", {}).get("path", "")))
        if artifact_path.is_file() and decision.get("artifact_anchor") not in artifact_path.read_text(encoding="utf-8"):
            problems.append(f"decision anchor disappeared from downstream artifact: {decision.get('id')}")
        for reference_id in decision.get("reference_ids", []):
            reference = next((item for item in references if item.get("id") == reference_id), None)
            if not reference or reference.get("state") != "inspected":
                problems.append(f"decision cites uninspected reference: {decision.get('id')} -> {reference_id}")
    for reference in references:
        for decision_id in reference.get("used_by", []):
            if decision_id not in decision_ids:
                problems.append(f"reference points to missing decision: {reference.get('id')} -> {decision_id}")
    return problems


def stage_problems(ledger: dict, stage: str) -> list[str]:
    problems = []
    for skill in ledger.get("skills", []):
        if skill.get("stage") != stage or not skill.get("selected"):
            continue
        if skill.get("state") in ("recommended", "invoked"):
            requirement = "mandatory" if skill.get("mandatory") else "optional"
            problems.append(
                f"{requirement} {skill.get('name')} is unresolved; complete, fail, or explicitly skip it"
            )
        if skill.get("mandatory") and skill.get("state") in ("failed", "skipped"):
            problems.append(f"mandatory {skill.get('name')} did not complete")
    return problems


def _recorded_reference_by_source(ledger: dict, source: str) -> dict | None:
    normal = source.rstrip("/")
    return next(
        (item for item in ledger.get("references", []) if str(item.get("source", "")).rstrip("/") == normal),
        None,
    )


def claim_problems(project: Path, ledger: dict) -> list[str]:
    problems = []
    research_path = project / "RESEARCH.md"
    if research_path.is_file():
        research = research_path.read_text(encoding="utf-8")
        for heading, column in (
            ("Findings", 4), ("Reference analysis", 0), ("Component and technique research", 2)
        ):
            for row in _table_rows(_section(research, heading)):
                if len(row) <= column:
                    continue
                source = _url(row[column])
                if not source:
                    continue
                reference = _recorded_reference_by_source(ledger, source)
                if not reference or reference.get("state") != "inspected":
                    problems.append(f"RESEARCH.md claims an uninspected source: {source}")
        resource_names = {
            str(item.get("name", "")).strip().lower() for item in ledger.get("resources", [])
        }
        for row in _table_rows(_section(research, "Library checks")):
            if row and row[0].strip() and not row[0].startswith("<") and row[0].strip().lower() not in resource_names:
                problems.append(f"RESEARCH.md claims an unevaluated resource: {row[0].strip()}")
    design_path = project / "DESIGN.md"
    if design_path.is_file():
        design = design_path.read_text(encoding="utf-8")
        for row in _table_rows(_section(design, "Visual references")):
            if not row:
                continue
            source = _url(row[0])
            if not source:
                continue
            reference = _recorded_reference_by_source(ledger, source)
            if not reference or reference.get("state") != "inspected":
                problems.append(f"DESIGN.md claims an uninspected reference: {source}")
            elif not reference.get("used_by"):
                problems.append(f"DESIGN.md reference has no downstream decision trace: {source}")
    return problems


def design_quality_problems(project: Path, ledger: dict) -> list[str]:
    path = project / "DESIGN.md"
    if not path.is_file():
        return []
    text = path.read_text(encoding="utf-8")
    thesis_section = _section(text, "Design thesis")
    thesis_match = re.search(r"(?m)^\*\*(.+?)\*\*\s*$", thesis_section)
    thesis = thesis_match.group(1).strip() if thesis_match else ""
    problems = []
    if not thesis or "<" in thesis:
        problems.append("design thesis is missing")
    elif _generic_thesis(thesis):
        problems.append("design thesis uses generic mood language")
    tension = re.search(r"(?im)^\*\*The tension:\*\*\s*(.+)$", thesis_section)
    if not tension or not tension.group(1).strip() or "<" in tension.group(1):
        problems.append("design tension is missing")
    signature = _section(text, "Signature moment")
    if not re.search(r"(?im)^-\s*\*\*What / where:\*\*\s*(?!<|$).+", signature):
        problems.append("signature moment is not concrete")
    if not re.search(r"(?im)^-\s*\*\*Mobile equivalent:\*\*\s*(?!<|$).+", signature):
        problems.append("signature moment has no mobile equivalent")
    rejections = [
        line for line in _section(text, "Anti-patterns for this project").splitlines()
        if re.match(r"^\s*\d+\.\s+(?!<).+", line)
    ]
    if len(rejections) < 3:
        problems.append("design direction has fewer than three project-specific rejections")
    check_rows = _table_rows(_section(text, "G1 direction check"))
    if len(check_rows) < 10 or any(len(row) < 3 or row[2].strip().lower() not in ("y", "yes") for row in check_rows[:10]):
        problems.append("the complete G1 check is not affirmative")
    alternatives = ledger.get("assessment", {}).get("alternatives_helpful", {}).get("value", False)
    directions = ledger.get("directions", [])
    if alternatives:
        if len(directions) < 2:
            problems.append("the plan called for alternatives but fewer than two directions are recorded")
        else:
            signatures = {(item.get("mechanism"), item.get("experience")) for item in directions}
            if len(signatures) != len(directions):
                problems.append("recorded alternatives do not differ in mechanism and experience")
    return problems


def project_problems(project: Path, stage: str | None = None) -> list[str]:
    ledger = load_ledger(project)
    if ledger is None:
        return []
    problems = ledger_problems(project, ledger)
    problems.extend(claim_problems(project, ledger))
    if stage:
        problems.extend(stage_problems(ledger, stage))
    if stage == "S3" or (project / "DESIGN.md").is_file():
        problems.extend(design_quality_problems(project, ledger))
    return list(dict.fromkeys(problems))


def summary(ledger: dict | None) -> dict:
    if ledger is None:
        return {
            "status": "legacy-untracked", "research_depth": "not recorded",
            "selected": 0, "completed": 0, "references": {"found": 0, "inspected": 0, "inaccessible": 0},
            "decisions": 0,
            "resources": {"evaluated": 0, "selected": 0},
        }
    selected = [item for item in ledger.get("skills", []) if item.get("selected")]
    return {
        "status": "tracked",
        "research_depth": ledger.get("research_depth"),
        "selected": len(selected),
        "completed": sum(item.get("state") in ("completed", "used") for item in selected),
        "references": {
            state: sum(item.get("state") == state for item in ledger.get("references", []))
            for state in REFERENCE_STATES
        },
        "decisions": len(ledger.get("decisions", [])),
        "resources": {
            "evaluated": len(ledger.get("resources", [])),
            "selected": sum(item.get("decision") == "use" for item in ledger.get("resources", [])),
        },
    }


def low_assessment(**overrides) -> dict:
    characteristics = {
        name: {"level": "low", "reason": f"Fixture records low {name.replace('_', ' ')}."}
        for name in DIMENSIONS
    }
    for name, level in overrides.items():
        characteristics[name] = {"level": level, "reason": f"Fixture records {level} {name.replace('_', ' ')}."}
    return {
        "characteristics": characteristics,
        "references_supplied": False,
        "alternatives_helpful": {"value": False, "reason": "One direction is sufficient for this fixture."},
        "social_request": {"value": False, "request": ""},
        "research_questions": [],
    }


@contextlib.contextmanager
def self_test_workspace():
    path = ROOT / "validation" / f"creative-intelligence-self-test-{uuid.uuid4().hex}"
    path.mkdir()
    try:
        yield path
    finally:
        if path.exists():
            shutil.rmtree(path)


def self_test() -> int:
    cases = []

    def case(name: str, passed: bool) -> None:
        cases.append((name, bool(passed)))

    with self_test_workspace() as workspace:
        project = workspace / "project"
        project.mkdir()
        (project / "PROJECT.md").write_text("# PROJECT\n\n## Goal\n\nA fixture goal.\n", encoding="utf-8")
        packet = workspace / "packet.txt"
        packet.write_text("verified fixture packet\n", encoding="utf-8")

        minimal = create_ledger(project, low_assessment())
        case("minimal project chooses minimal research", minimal["research_depth"] == "minimal")
        case(
            "minimal project skips unnecessary reference and component work",
            _skill_by_name(minimal, "reference-analysis")["state"] == "skipped"
            and _skill_by_name(minimal, "component-research")["state"] == "skipped"
            and _skill_by_name(minimal, "visual-qa")["state"] == "skipped"
            and _skill_by_name(minimal, "social-strategy")["state"] == "skipped",
        )
        social_assessment = low_assessment()
        social_assessment["social_request"] = {
            "value": True,
            "request": "Create a social strategy for this project.",
        }
        social_ledger = create_ledger(project, social_assessment)
        case(
            "social strategy activates only from an explicit request",
            _skill_by_name(social_ledger, "social-strategy")["state"] == "recommended",
        )
        try:
            missing_social_request = low_assessment()
            missing_social_request["social_request"] = {"value": True, "request": ""}
            create_ledger(project, missing_social_request)
            unsupported_social_activation = True
        except CreativeError:
            unsupported_social_activation = False
        case("social strategy cannot self-activate without request evidence", not unsupported_social_activation)
        late_social = create_ledger(project, low_assessment())
        activate_optional_skill(late_social, {
            "skill": "social-strategy",
            "explicit_request": "Help me launch this finished project on social.",
        })
        case(
            "explicit later request can activate previously skipped social work",
            _skill_by_name(late_social, "social-strategy")["state"] == "recommended"
            and _skill_by_name(late_social, "social-strategy")["selected"],
        )
        try:
            missing_late_request = create_ledger(project, low_assessment())
            activate_optional_skill(missing_late_request, {
                "skill": "social-strategy", "explicit_request": "",
            })
            late_without_request = True
        except CreativeError:
            late_without_request = False
        case("late social activation cannot invent a user request", not late_without_request)

        reference_assessment = low_assessment(visual_dependence="high", reference_sensitivity="high", generic_risk="high")
        reference_assessment["alternatives_helpful"] = {
            "value": True, "reason": "Two mechanisms need comparison before committing."
        }
        reference_assessment["research_questions"] = [{
            "id": "rq-reference",
            "question": "Which archival interfaces use sequence rather than cards?",
            "reason": "The project needs a non-generic organising mechanism.",
            "strategy": "Inspect three live institutional collections at desktop and mobile widths.",
            "kind": "reference",
            "blocking": False,
        }]
        ledger = create_ledger(project, reference_assessment)
        case("reference-sensitive project selects mandatory reference analysis", _skill_by_name(ledger, "reference-analysis")["mandatory"])
        case("novel reference-sensitive project chooses deep research", ledger["research_depth"] == "deep")

        record_skill_event(ledger, {"skill": "reference-analysis", "state": "invoked", "evidence_path": str(packet)})
        try:
            record_skill_event(create_ledger(project, reference_assessment), {
                "skill": "reference-analysis", "state": "completed", "output_path": str(project / "PROJECT.md")
            })
            impossible_completion = False
        except CreativeError:
            impossible_completion = True
        case("skill cannot be completed without invocation", impossible_completion)

        for index in range(1, 4):
            capture = workspace / f"reference-{index}.html"
            capture.write_text(f"<html><title>Reference {index}</title><main>Observed mechanism {index}</main></html>", encoding="utf-8")
            record_reference(ledger, {
                "id": f"ref-{index}", "source": f"https://example.test/reference-{index}",
                "state": "inspected", "inspection": "visual", "evidence_path": str(capture),
                "observations": [f"The live fixture exposes hierarchy {index}."],
                "mechanisms": [f"Mechanism {index}"], "why_it_matters": "It tests a distinct hierarchy.",
                "borrow": f"Borrow mechanism {index}.", "reject": f"Do not copy surface {index}.",
            })
        try:
            record_reference(ledger, {
                "id": "ref-no-proof", "source": "https://example.test/no-proof", "state": "inspected",
                "inspection": "visual", "observations": ["invented"], "mechanisms": [],
                "why_it_matters": "x", "borrow": "x", "reject": "x",
            })
            proof_required = False
        except CreativeError:
            proof_required = True
        case("inspection cannot be recorded without an evidence artifact", proof_required)

        record_reference(ledger, {
            "id": "ref-blocked", "source": "https://example.test/blocked", "state": "inaccessible",
            "blocker": "The fixture returned 403 Forbidden.",
        })
        case("inaccessible source records blocker without observations", next(item for item in ledger["references"] if item["id"] == "ref-blocked").get("observations") is None)
        try:
            record_reference(ledger, {
                "id": "ref-fake-blocked", "source": "https://example.test/fake", "state": "inaccessible",
                "blocker": "403", "observations": ["not observable"],
            })
            inaccessible_observation_blocked = False
        except CreativeError:
            inaccessible_observation_blocked = True
        case("inaccessible source cannot acquire fabricated observations", inaccessible_observation_blocked)

        record_reference(ledger, {"id": "ref-unused", "source": "https://example.test/unused", "state": "found"})
        case("found reference can remain explicitly unused", next(item for item in ledger["references"] if item["id"] == "ref-unused")["used_by"] == [])
        record_conflict(ledger, {
            "reference_ids": ["ref-1", "ref-2"],
            "implication": "Keep the archive hierarchy but reject the second source's image-led pacing.",
        })
        case("conflicting references retain a design implication", len(ledger["conflicts"]) == 1)

        design = project / "DESIGN.md"
        design.write_text(
            "# DESIGN\n\n**Status:** draft\n\n## Design thesis\n\n"
            "**A numbered archive leaf lets one stitch connect each memory to the next.**\n\n"
            "**The tension:** archival but immediate\n\n## Visual references\n\n"
            "| Reference | Mechanism taken (max 2 each) |\n|---|---|\n"
            "| https://example.test/reference-1 | Numbered hierarchy |\n"
            "| https://example.test/reference-2 | Sequential pacing |\n"
            "| https://example.test/reference-3 | Hard editorial edges |\n\n"
            "## Signature moment\n\n- **What / where:** A stitch crosses each memory.\n"
            "- **Why memorable:** It turns connection into structure.\n"
            "- **Mobile equivalent:** The stitch becomes one continuous vertical rule.\n\n"
            "## Anti-patterns for this project\n\n1. No card grid.\n2. No generic hero.\n3. No decorative fade.\n\n"
            "## G1 direction check\n\n| # | Check | Y/N | If no, why not |\n|---|---|---|---|\n"
            + "".join(f"| {i} | Fixture check {i} | Y | |\n" for i in range(1, 11)),
            encoding="utf-8",
        )
        for index in range(1, 4):
            record_decision(ledger, {
                "id": f"decision-{index}", "decision": f"Use mechanism {index}",
                "principle": "Translate the reference into the archive subject.", "basis": "reference",
                "reference_ids": [f"ref-{index}"], "artifact_path": str(design),
                "artifact_anchor": f"https://example.test/reference-{index}", "status": "proposed", "gate": "pending",
            })
        record_skill_event(ledger, {
            "skill": "reference-analysis", "state": "completed", "output_path": str(design),
            "result": "Three sources inspected and synthesised.", "usefulness": "useful",
        })
        record_skill_event(ledger, {
            "skill": "reference-analysis", "state": "used", "downstream_path": str(design),
            "decision_ids": ["decision-1", "decision-2", "decision-3"],
        })
        record_direction(ledger, {
            "id": "direction-archive", "thesis": "A numbered archive leaf lets one stitch connect each memory.",
            "mechanism": "numbered sequence", "experience": "editorial trail",
        })
        record_direction(ledger, {
            "id": "direction-map", "thesis": "A place index reveals each memory as a changing coordinate.",
            "mechanism": "spatial index", "experience": "map exploration",
        })
        case("genuinely different alternatives pass the mechanism test", not design_quality_problems(project, ledger))
        try:
            record_direction(ledger, {
                "id": "generic", "thesis": "A clean modern premium experience.",
                "mechanism": "cards", "experience": "scroll",
            })
            generic_rejected = False
        except CreativeError:
            generic_rejected = True
        case("generic direction is rejected", generic_rejected)
        case("reference to design trace passes with inspected sources", not claim_problems(project, ledger))

        technical = low_assessment(technical_uncertainty="high", interaction_complexity="high")
        technical["research_questions"] = [{
            "id": "rq-tech", "question": "Can the interaction use a platform API without a package?",
            "reason": "A dependency should not be proposed if the browser already supplies the mechanism.",
            "strategy": "Compare the platform documentation with one maintained alternative.",
            "kind": "technical", "blocking": True,
        }]
        technical_ledger = create_ledger(project, technical)
        case(
            "technical project selects research and component comparison",
            _skill_by_name(technical_ledger, "technical-research")["selected"]
            and _skill_by_name(technical_ledger, "component-research")["selected"],
        )
        platform_doc = workspace / "platform-doc.html"
        platform_doc.write_text(
            "<html><title>Platform observer fixture</title><main>Observer support and behaviour.</main></html>",
            encoding="utf-8",
        )
        package_doc = workspace / "package-doc.html"
        package_doc.write_text(
            "<html><title>Package fixture</title><main>Package compatibility and licence.</main></html>",
            encoding="utf-8",
        )
        for reference_id, source, capture in (
            ("ref-platform", "https://platform.example.test/observer", platform_doc),
            ("ref-package", "https://registry.example.test/motion", package_doc),
        ):
            record_reference(technical_ledger, {
                "id": reference_id, "source": source, "state": "inspected",
                "inspection": "content", "evidence_path": str(capture),
                "observations": ["The fixture exposes the capability fields needed for comparison."],
                "mechanisms": [], "why_it_matters": "The dependency decision needs inspected evidence.",
                "borrow": "Use the verified capability boundary.", "reject": "Do not infer unrecorded features.",
            })
        technical_output = workspace / "technical-decision.md"
        technical_output.write_text(
            "# Technical decision\n\nUse the platform observer; no motion package is necessary.\n",
            encoding="utf-8",
        )
        record_resource(technical_ledger, {
            "id": "resource-platform-observer", "name": "Platform observer", "category": "browser-api",
            "provides": "Active-section observation without a package.",
            "appropriate_because": "The project only needs threshold-based section activation.",
            "compatibility": "Compatible with the fixture target described by the inspected platform record.",
            "license": "N/A — browser platform capability.",
            "implementation_cost": "One observer and deterministic fallback logic.",
            "alternatives": [{"name": "scroll listener", "reason": "More manual work and event-frequency risk."}],
            "necessary": True, "decision": "use", "source_reference_ids": ["ref-platform"],
            "artifact_path": str(technical_output), "artifact_anchor": "Use the platform observer",
        })
        record_resource(technical_ledger, {
            "id": "resource-motion-package", "name": "Motion package", "category": "library",
            "provides": "A general component animation runtime.",
            "appropriate_because": "It was compared because the interaction includes motion.",
            "compatibility": "No compatibility advantage over the platform observer was established.",
            "license": "Fixture source records a permissive package licence.",
            "implementation_cost": "Adds installation, bundle, and maintenance cost.",
            "alternatives": [{"name": "Platform observer", "reason": "Supplies the bounded behaviour without a dependency."}],
            "necessary": False, "decision": "do-not-use", "source_reference_ids": ["ref-package"],
            "artifact_path": str(technical_output), "artifact_anchor": "no motion package is necessary",
        })
        case(
            "technical resource decision records compatibility cost and alternatives",
            not ledger_problems(project, technical_ledger)
            and all(item.get("alternatives") for item in technical_ledger["resources"]),
        )
        case(
            "dependency decision distinguishes selected platform capability from rejected package",
            summary(technical_ledger)["resources"] == {"evaluated": 2, "selected": 1}
            and {item["decision"] for item in technical_ledger["resources"]} == {"use", "do-not-use"},
        )
        try:
            record_resource(technical_ledger, {
                "id": "resource-unproved", "name": "Unproved package", "category": "library",
                "provides": "Unknown capability.", "appropriate_because": "It was familiar.",
                "compatibility": "Claimed only.", "license": "Claimed only.",
                "implementation_cost": "Unknown.",
                "alternatives": [{"name": "none", "reason": "No comparison ran."}],
                "necessary": False, "decision": "defer", "source_reference_ids": ["missing-reference"],
                "artifact_path": str(technical_output), "artifact_anchor": "Technical decision",
            })
            unproved_resource_blocked = False
        except CreativeError:
            unproved_resource_blocked = True
        case("resource claim cannot cite an uninspected source", unproved_resource_blocked)

        save_ledger(project, ledger)
        reloaded = load_ledger(project)
        case("fresh task can reload creative state", reloaded is not None and reloaded["decisions"][0]["id"] == "decision-1")
        case("project resumption preserves research and design provenance", not ledger_problems(project, reloaded))
        tampered = json.loads(json.dumps(reloaded))
        tampered_skill = _skill_by_name(tampered, "reference-analysis")
        tampered_skill["history"] = [tampered_skill["history"][0], *tampered_skill["history"][2:]]
        case(
            "hand-edited skill history cannot bypass the invocation boundary",
            any("recommended -> completed" in item for item in ledger_problems(project, tampered)),
        )
        saved_design = design.read_text(encoding="utf-8")
        design.write_text(saved_design + "\nchanged after evidence\n", encoding="utf-8")
        case("changed downstream artifact makes evidence stale", any("changed" in item for item in ledger_problems(project, reloaded)))
        design.write_text(saved_design, encoding="utf-8")

        untracked = create_ledger(project, low_assessment())
        fake_design = project / "DESIGN.md"
        fake_design.write_text(saved_design.replace("https://example.test/reference-1", "https://unsupported.test/reference"), encoding="utf-8")
        case("design cannot prove an inspection by assertion alone", any("uninspected" in item for item in claim_problems(project, untracked)))

    print("CREATIVE INTELLIGENCE SELF-TEST\n")
    for name, passed in cases:
        print(("ok    " if passed else "FAIL  ") + name)
    failed = [name for name, passed in cases if not passed]
    print(f"\n{'FAILED' if failed else 'PASS'}  {len(cases) - len(failed)}/{len(cases)}")
    return 1 if failed else 0


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description=__doc__)
    value.add_argument("--self-test", action="store_true")
    return value


def main() -> int:
    args = parser().parse_args()
    if args.self_test:
        return self_test()
    parser().print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
