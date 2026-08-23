#!/usr/bin/env python3
"""Post-G1 creative trace, visual evidence, review, and social provenance.

Canonical Builder OS documents and policies still own decisions and quality.
This module derives a project-local execution trace from approved documents and
records what was implemented, rendered, observed, reviewed, and used. It never
approves a gate or treats expected prose as execution evidence.
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
LEDGER_RELATIVE = Path(".builderos") / "creative-operations.json"
EVIDENCE_LEVELS = ("code-suggests", "rendered", "observed", "verified", "unverified")
EVIDENCE_KINDS = ("source", "screenshot", "browser", "dom", "measurement", "interaction")
DRIFT_STATES = ("approved", "allowed", "drift", "unknown")
INTERVENTION_CLASSES = ("necessary", "valuable", "avoidable", "unacceptable")
REVIEW_DIMENSIONS = (
    "thesis", "distinctiveness", "memorability", "visual_craft", "interaction",
    "narrative", "implementation_quality", "design_fidelity", "portfolio_value",
    "genericness",
)
SOCIAL_EVIDENCE_CLASSES = ("documented", "observed", "researched", "inferred", "speculative")
SOCIAL_RESEARCH_DEPTHS = ("minimal", "standard", "deep")
SOCIAL_SOURCE_QUALITIES = (
    "official-platform", "platform-creator-guidance", "primary-research",
    "credible-industry-research", "observed-example",
)
SOCIAL_VISUAL_STATES = ("existing", "to-create", "missing")
SOCIAL_RESULT_METRICS = (
    "impressions", "reach", "likes", "comments", "saves", "shares", "clicks",
    "profile_visits", "watch_time_seconds", "retention_percent", "follows",
)
SOCIAL_LEARNING_OUTCOMES = ("supported", "contradicted", "inconclusive")
SOCIAL_LEARNING_CONFIDENCE = ("weak", "limited", "moderate")
MAX_SOCIAL_POSTS = 6
MAX_CURRENT_SOURCE_AGE_DAYS = 180
MAX_AUTOMATIC_CREATIVE_ITERATIONS = 2
GENERIC_SOCIAL_OPENERS = (
    "i'm excited to share", "i’m excited to share", "here's a deep dive",
    "here’s a deep dive", "this journey taught me", "i'm thrilled to announce",
    "i’m thrilled to announce", "thrilled to announce", "at the intersection of",
    "design isn't just about", "design isn’t just about", "game changer",
    "this changes everything", "unpopular opinion", "let that sink in",
    "read that again",
)
SOCIAL_GUARANTEE_PATTERNS = (
    r"\bguarantee(?:d|s)?\s+(?:reach|engagement|impressions|followers|virality)\b",
    r"\bwill\s+(?:go viral|increase (?:reach|engagement)|perform)\b",
    r"\bproven\s+(?:growth|algorithm|viral)\s+(?:hack|tactic|formula)\b",
)


class OperationsError(RuntimeError):
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
        raise OperationsError(f"creative operations evidence is malformed: {exc}") from exc
    if not isinstance(value, dict):
        raise OperationsError("creative operations evidence must be a JSON object")
    return value


def ledger_path(project: Path) -> Path:
    return project.resolve() / LEDGER_RELATIVE


def evidence_record(path: Path, anchor: str | None = None) -> dict:
    path = path.resolve()
    if not path.is_file() or path.stat().st_size == 0:
        raise OperationsError(f"evidence artifact is missing or empty: {path}")
    if path.name.lower() == ".env" or path.name.lower().startswith(".env."):
        raise OperationsError("credential files cannot be creative evidence")
    if anchor and anchor not in path.read_text(encoding="utf-8", errors="ignore"):
        raise OperationsError(f"evidence anchor is absent from {path}: {anchor}")
    record = {"path": str(path), "sha256": digest(path)}
    if anchor:
        record["anchor"] = anchor
    return record


def section(text: str, heading: str) -> str:
    match = re.search(
        rf"(?ms)^##\s+{re.escape(heading)}\s*$\r?\n(.*?)(?=^##\s+|\Z)", text
    )
    return match.group(1).strip() if match else ""


def table_rows(value: str) -> list[list[str]]:
    rows = []
    for line in value.splitlines():
        if not line.strip().startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if not cells or all(re.fullmatch(r":?-+:?", cell) for cell in cells):
            continue
        rows.append(cells)
    return rows[1:] if rows else []


def clean(value: str) -> str:
    value = re.sub(r"<!--.*?-->", "", value, flags=re.S)
    value = re.sub(r"[*_`]", "", value)
    return " ".join(value.split()).strip()


def design_thesis(text: str) -> str:
    for line in section(text, "Design thesis").splitlines():
        candidate = clean(line)
        if candidate and not candidate.lower().startswith(("one sentence", "test:", "banned:", "the tension:")):
            return candidate
    return ""


def labelled_value(value: str, label: str) -> str:
    match = re.search(rf"(?im)^\s*[-*]?\s*\*\*{re.escape(label)}:\*\*\s*(.+)$", value)
    return clean(match.group(1)) if match else ""


def design_locked(project: Path) -> bool:
    design = (project / "DESIGN.md").read_text(encoding="utf-8")
    agents = (project / "AGENTS.md").read_text(encoding="utf-8")
    return bool(
        re.search(r"(?im)^\*\*Status:\*\*\s*locked at G1", design)
        and re.search(r"(?im)^\|\s*\*\*Last gate passed\*\*\s*\|\s*`?G[1-5]\b", agents)
    )


def _requirement(
    requirement_id: str,
    kind: str,
    decision: str,
    implementation_requirement: str,
    source: Path,
    anchor: str,
    priority: int,
    viewports: list[int] | None = None,
    evidence_kind: str = "screenshot",
) -> dict:
    return {
        "id": requirement_id,
        "kind": kind,
        "decision": decision,
        "implementation_requirement": implementation_requirement,
        "design_source": evidence_record(source, anchor),
        "priority": priority,
        "viewports": viewports or [],
        "expected_evidence_kind": evidence_kind,
        "status": "approved",
    }


def derive_requirements(project: Path) -> list[dict]:
    project = project.resolve()
    required = [project / name for name in ("PROJECT.md", "DESIGN.md", "HANDOFF.md", "AGENTS.md")]
    missing = [path.name for path in required if not path.is_file()]
    if missing:
        raise OperationsError("post-G1 trace is missing: " + ", ".join(missing))
    if not design_locked(project):
        raise OperationsError("post-G1 trace requires human-locked DESIGN.md and G1 in AGENTS.md")

    design_path = project / "DESIGN.md"
    handoff_path = project / "HANDOFF.md"
    design = design_path.read_text(encoding="utf-8")
    handoff = handoff_path.read_text(encoding="utf-8")
    requirements = []

    thesis = design_thesis(design)
    if not thesis:
        raise OperationsError("DESIGN.md has no usable design thesis")
    requirements.append(_requirement(
        "design-thesis", "thesis", thesis,
        "The rendered experience must make the approved thesis perceptible, not merely repeat it in copy.",
        design_path, thesis, 1,
    ))

    signature_section = section(design, "Signature moment")
    signature = labelled_value(signature_section, "What / where")
    mobile = labelled_value(signature_section, "Mobile equivalent")
    if not signature or not mobile:
        raise OperationsError("DESIGN.md signature moment and mobile equivalent are required")
    requirements.append(_requirement(
        "signature-moment", "signature", signature,
        f"Implement {signature}; at narrow widths preserve it as: {mobile}",
        design_path, signature, 1, [375, 1280], "interaction",
    ))

    fixed_rows = table_rows(section(handoff, "Decisions that are fixed"))
    fixed = {clean(row[0]).lower(): clean(row[1]) for row in fixed_rows if len(row) >= 2}
    for label, kind, evidence_kind in (
        ("typography", "typography", "measurement"),
        ("palette", "colour", "measurement"),
        ("grid", "layout", "screenshot"),
        ("motion", "motion", "interaction"),
    ):
        decision = fixed.get(label, "")
        if decision and not decision.startswith("<"):
            requirements.append(_requirement(
                f"fixed-{label}", kind, decision,
                f"Implement the locked {label} decision exactly enough to preserve its design purpose.",
                handoff_path, decision, 3 if label in ("typography", "palette") else 2,
                [375, 1280], evidence_kind,
            ))

    responsive_rows = table_rows(section(design, "Responsive behaviour"))
    for row in responsive_rows:
        if len(row) < 2:
            continue
        width_text, composition = clean(row[0]), clean(row[1])
        width_match = re.search(r"\d+", width_text)
        if not width_match or not composition or composition.startswith("<"):
            continue
        width = int(width_match.group())
        requirements.append(_requirement(
            f"responsive-{width}", "responsive", composition,
            f"At {width}px the rendered composition must preserve this transformation: {composition}",
            design_path, composition, 2, [width], "screenshot",
        ))

    interaction = clean(section(design, "Interaction principles"))
    if interaction and not interaction.startswith("<"):
        requirements.append(_requirement(
            "interaction-principles", "interaction", interaction,
            "Implement and exercise the approved interaction, including its non-hover equivalent.",
            design_path, interaction, 2, [375, 1280], "interaction",
        ))

    ids = [item["id"] for item in requirements]
    if len(ids) != len(set(ids)):
        raise OperationsError("derived design requirement IDs are not unique")
    return requirements


def qa_plan(requirements: list[dict]) -> dict:
    targets = []
    for requirement in requirements:
        targets.append({
            "id": f"target-{requirement['id']}",
            "requirement_ids": [requirement["id"]],
            "priority": requirement["priority"],
            "why": f"The approved {requirement['kind']} decision can drift during implementation.",
            "viewports": requirement["viewports"] or [375, 1280],
            "evidence_kind": requirement["expected_evidence_kind"],
            "stop_when": "Observed with evidence, or explicitly unverified with the environmental blocker recorded.",
        })
    targets.sort(key=lambda item: (item["priority"], item["id"]))
    return {
        "generated_at": now(),
        "selection_basis": "approved project requirements, ordered by thesis/signature criticality",
        "targets": targets,
    }


def create_ledger(project: Path) -> dict:
    project = project.resolve()
    requirements = derive_requirements(project)
    created = now()
    return {
        "schema_version": SCHEMA_VERSION,
        "project": str(project),
        "created_at": created,
        "updated_at": created,
        "requirements": requirements,
        "visual_qa_plan": qa_plan(requirements),
        "implementations": [],
        "visual_evidence": [],
        "drift_findings": [],
        "creative_reviews": [],
        "social_strategies": [],
        "social_results": [],
        "social_learnings": [],
    }


def load_ledger(project: Path) -> dict | None:
    path = ledger_path(project)
    return read_json(path) if path.is_file() else None


def save_ledger(project: Path, ledger: dict) -> Path:
    ledger["updated_at"] = now()
    path = ledger_path(project)
    write_json(path, ledger)
    return path


def by_id(rows: list[dict], value: str, label: str) -> dict:
    matches = [item for item in rows if item.get("id") == value]
    if len(matches) != 1:
        raise OperationsError(f"{label} does not contain exactly one ID {value}")
    return matches[0]


def record_implementation(ledger: dict, event: dict) -> None:
    requirement_id = str(event.get("requirement_id", "")).strip()
    by_id(ledger.get("requirements", []), requirement_id, "requirements")
    if any(item.get("requirement_id") == requirement_id for item in ledger.get("implementations", [])):
        raise OperationsError(f"implementation mapping already exists: {requirement_id}")
    status = str(event.get("status", "")).strip()
    if status not in ("implemented", "partial", "not-implemented"):
        raise OperationsError("implementation status must be implemented, partial, or not-implemented")
    summary = str(event.get("summary", "")).strip()
    if not summary:
        raise OperationsError("implementation mapping needs a concrete summary")
    row = {
        "requirement_id": requirement_id,
        "status": status,
        "summary": summary,
        "recorded_at": now(),
    }
    if status in ("implemented", "partial"):
        row["source"] = evidence_record(
            Path(str(event.get("source_path", ""))), str(event.get("source_anchor", "")).strip()
        )
    else:
        blocker = str(event.get("blocker", "")).strip()
        if not blocker:
            raise OperationsError("not-implemented mapping needs a blocker")
        row["blocker"] = blocker
    ledger.setdefault("implementations", []).append(row)


def record_visual_evidence(ledger: dict, event: dict) -> None:
    evidence_id = str(event.get("id", "")).strip()
    if not evidence_id or any(item.get("id") == evidence_id for item in ledger.get("visual_evidence", [])):
        raise OperationsError("visual evidence needs a new non-empty ID")
    requirement_id = str(event.get("requirement_id", "")).strip()
    by_id(ledger.get("requirements", []), requirement_id, "requirements")
    level = str(event.get("level", "")).strip()
    kind = str(event.get("kind", "")).strip()
    if level not in EVIDENCE_LEVELS or kind not in EVIDENCE_KINDS:
        raise OperationsError("visual evidence needs a supported level and kind")
    observation = str(event.get("observation", "")).strip()
    if not observation:
        raise OperationsError("visual evidence needs a concrete observation")
    row = {
        "id": evidence_id,
        "requirement_id": requirement_id,
        "level": level,
        "kind": kind,
        "observation": observation,
        "viewport": event.get("viewport"),
        "recorded_at": now(),
    }
    if level == "unverified":
        blocker = str(event.get("blocker", "")).strip()
        if not blocker:
            raise OperationsError("unverified visual evidence needs a blocker")
        row["blocker"] = blocker
    else:
        row["evidence"] = evidence_record(Path(str(event.get("evidence_path", ""))))
    if level == "verified":
        prior_ids = event.get("prior_evidence_ids", [])
        prior = {item.get("id"): item for item in ledger.get("visual_evidence", [])}
        if not isinstance(prior_ids, list) or not prior_ids:
            raise OperationsError("verified evidence needs prior rendered or observed evidence IDs")
        if any(prior.get(item, {}).get("level") not in ("rendered", "observed") for item in prior_ids):
            raise OperationsError("verified evidence cites no rendered or observed control")
        row["prior_evidence_ids"] = prior_ids
        verification = str(event.get("verification", "")).strip()
        if not verification:
            raise OperationsError("verified evidence needs the verification method")
        row["verification"] = verification
    ledger.setdefault("visual_evidence", []).append(row)


def record_drift(ledger: dict, event: dict) -> None:
    drift_id = str(event.get("id", "")).strip()
    if not drift_id or any(item.get("id") == drift_id for item in ledger.get("drift_findings", [])):
        raise OperationsError("drift finding needs a new non-empty ID")
    requirement_id = str(event.get("requirement_id", "")).strip()
    by_id(ledger.get("requirements", []), requirement_id, "requirements")
    state = str(event.get("state", "")).strip()
    if state not in DRIFT_STATES:
        raise OperationsError("drift state must be approved, allowed, drift, or unknown")
    evidence_ids = event.get("evidence_ids", [])
    evidence = {item.get("id"): item for item in ledger.get("visual_evidence", [])}
    if not isinstance(evidence_ids, list) or not evidence_ids or any(item not in evidence for item in evidence_ids):
        raise OperationsError("drift finding needs existing visual evidence IDs")
    row = {
        "id": drift_id,
        "requirement_id": requirement_id,
        "state": state,
        "evidence_ids": evidence_ids,
        "what_changed": str(event.get("what_changed", "")).strip(),
        "why_it_matters": str(event.get("why_it_matters", "")).strip(),
        "recommendation": str(event.get("recommendation", "")).strip(),
        "recorded_at": now(),
    }
    if not row["what_changed"] or not row["why_it_matters"]:
        raise OperationsError("drift finding needs what changed and why it matters")
    if state in ("drift", "unknown") and not row["recommendation"]:
        raise OperationsError("drift or unknown finding needs a recommendation")
    ledger.setdefault("drift_findings", []).append(row)


def record_creative_review(ledger: dict, event: dict) -> None:
    review_id = str(event.get("id", "")).strip()
    if not review_id or any(item.get("id") == review_id for item in ledger.get("creative_reviews", [])):
        raise OperationsError("creative review needs a new non-empty ID")
    evidence_ids = event.get("evidence_ids", [])
    evidence = {item.get("id"): item for item in ledger.get("visual_evidence", [])}
    if not isinstance(evidence_ids, list) or not evidence_ids or any(item not in evidence for item in evidence_ids):
        raise OperationsError("creative review needs existing visual evidence IDs")
    if not any(evidence[item].get("level") in ("rendered", "observed", "verified") for item in evidence_ids):
        raise OperationsError("creative review cannot run from code suggestions alone")
    iteration = str(event.get("iteration", "")).strip()
    if iteration not in ("yes", "no", "conditional"):
        raise OperationsError("creative review iteration must be yes, no, or conditional")
    reviews = ledger.get("creative_reviews", [])
    parent_review_id = str(event.get("parent_review_id", "")).strip()
    if reviews and parent_review_id != reviews[-1].get("id"):
        raise OperationsError("a follow-up creative review must name the latest review as parent_review_id")
    if not reviews and parent_review_id:
        raise OperationsError("the first creative review cannot name a parent_review_id")
    required = ("strongest", "weakest", "biggest_risk", "highest_value_improvement")
    row = {key: str(event.get(key, "")).strip() for key in required}
    if not all(row.values()):
        raise OperationsError("creative review needs strongest, weakest, risk, and highest-value improvement")
    do_not_change = str(event.get("do_not_change", "")).strip()
    if not do_not_change:
        raise OperationsError("creative review needs a do_not_change boundary")
    dimensions = event.get("dimensions", {})
    if not isinstance(dimensions, dict) or set(dimensions) != set(REVIEW_DIMENSIONS):
        raise OperationsError("creative review needs all ten project-quality dimensions")
    for name, value in dimensions.items():
        if not isinstance(value, dict) or not str(value.get("judgement", "")).strip():
            raise OperationsError(f"creative review dimension {name} needs a judgement")
        ids = value.get("evidence_ids", [])
        if not isinstance(ids, list) or any(item not in evidence for item in ids):
            raise OperationsError(f"creative review dimension {name} cites unknown evidence")
    row.update({
        "id": review_id,
        "evidence_ids": evidence_ids,
        "dimensions": dimensions,
        "iteration": iteration,
        "parent_review_id": parent_review_id or None,
        "do_not_change": do_not_change,
        "recorded_at": now(),
    })
    ledger.setdefault("creative_reviews", []).append(row)


def _creative_references(project: Path) -> dict[str, dict]:
    path = project / ".builderos" / "creative-evidence.json"
    if not path.is_file():
        return {}
    value = read_json(path)
    return {item.get("id"): item for item in value.get("references", []) if item.get("id")}


def _social_copy_problems(value: str) -> list[str]:
    lowered = value.lower()
    problems = [
        f"generic AI phrasing: {phrase}"
        for phrase in GENERIC_SOCIAL_OPENERS
        if phrase in lowered
    ]
    problems.extend(
        f"unsupported performance promise: {pattern}"
        for pattern in SOCIAL_GUARANTEE_PATTERNS
        if re.search(pattern, lowered)
    )
    return problems


def _checked_date(value: object, *, current: bool) -> str:
    checked = str(value or "").strip()
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", checked):
        raise OperationsError("source-backed social recommendation needs a checked_on date")
    try:
        checked_at = datetime.strptime(checked, "%Y-%m-%d").date()
    except ValueError as exc:
        raise OperationsError("social recommendation checked_on is not a real date") from exc
    age = (datetime.now().astimezone().date() - checked_at).days
    if age < 0:
        raise OperationsError("social recommendation checked_on cannot be in the future")
    if current and age > MAX_CURRENT_SOURCE_AGE_DAYS:
        raise OperationsError("time-sensitive social recommendation uses an outdated source")
    return checked


def _event_evidence(rows: object, label: str, minimum: int = 1) -> list[dict]:
    if not isinstance(rows, list) or len(rows) < minimum:
        raise OperationsError(f"{label} needs at least {minimum} evidence artifact(s)")
    records = []
    for item in rows:
        if not isinstance(item, dict) or not str(item.get("path", "")).strip():
            raise OperationsError(f"{label} evidence needs a path")
        records.append(evidence_record(
            Path(str(item["path"])), str(item.get("anchor", "")).strip() or None
        ))
    return records


def _social_strategy(ledger: dict, strategy_id: str) -> dict:
    return by_id(ledger.get("social_strategies", []), strategy_id, "social strategies")


def _social_concept(strategy: dict, concept_id: str) -> dict:
    return by_id(strategy.get("content_concepts", []), concept_id, "social content concepts")


def record_social_strategy(project: Path, ledger: dict, event: dict) -> None:
    strategy_id = str(event.get("id", "")).strip()
    if not strategy_id or any(item.get("id") == strategy_id for item in ledger.get("social_strategies", [])):
        raise OperationsError("social strategy needs a new non-empty ID")
    contract_version = event.get("contract_version", 1)
    if contract_version not in (1, 2):
        raise OperationsError("social strategy contract_version must be 1 or 2")
    activation = str(event.get("activated_by", "")).strip()
    if not activation:
        raise OperationsError("social strategy needs the user's explicit activation request")
    audience = str(event.get("audience", "")).strip()
    platforms = event.get("platforms", [])
    if not audience or not isinstance(platforms, list) or not 1 <= len(platforms) <= 3:
        raise OperationsError("social strategy needs an audience and one to three relevant platforms")
    if any(not isinstance(item, dict) or not str(item.get("name", "")).strip() or not str(item.get("why", "")).strip() for item in platforms):
        raise OperationsError("each social platform needs a name and project-specific reason")
    references = _creative_references(project)
    platform_names = {str(item["name"]).strip() for item in platforms}
    project_story = event.get("project_story", {})
    project_evidence = []
    visual_assets = []
    research_depth = None
    pillars = []
    pillars_decision = ""
    excluded_platforms = []
    conflicts = []
    voice_evidence = []
    if contract_version == 2:
        research_depth = str(event.get("research_depth", "")).strip()
        if research_depth not in SOCIAL_RESEARCH_DEPTHS:
            raise OperationsError("social intelligence needs minimal, standard, or deep research depth")
        required_story = ("what", "why", "specific_interest", "maker_decision", "strongest_moment")
        if not isinstance(project_story, dict) or any(
            not str(project_story.get(field, "")).strip() for field in required_story
        ):
            raise OperationsError("social intelligence needs a concrete project story before platform advice")
        project_evidence = _event_evidence(event.get("project_evidence"), "project story")
        excluded_platforms = event.get("not_recommended", [])
        if not isinstance(excluded_platforms, list) or any(
            not isinstance(item, dict)
            or not str(item.get("name", "")).strip()
            or not str(item.get("why_not", "")).strip()
            for item in excluded_platforms
        ):
            raise OperationsError("not-recommended platforms need a name and project-specific reason")
        if platform_names & {str(item.get("name", "")).strip() for item in excluded_platforms}:
            raise OperationsError("a platform cannot be both selected and not recommended")
        conflicts = event.get("source_conflicts", [])
        if not isinstance(conflicts, list):
            raise OperationsError("social source_conflicts must be a list")
        for conflict in conflicts:
            ids = conflict.get("source_reference_ids", []) if isinstance(conflict, dict) else []
            if len(ids) < 2 or any(references.get(item, {}).get("state") != "inspected" for item in ids):
                raise OperationsError("conflicting platform evidence needs at least two inspected sources")
            if not str(conflict.get("resolution", "")).strip():
                raise OperationsError("conflicting platform evidence needs an explicit resolution")
        visual_assets_value = event.get("visual_assets", [])
        if not isinstance(visual_assets_value, list) or not visual_assets_value:
            raise OperationsError("social intelligence must record actual visual availability")
        visual_ids = set()
        for visual in visual_assets_value:
            if not isinstance(visual, dict):
                raise OperationsError("each social visual asset must be an object")
            visual_id = str(visual.get("id", "")).strip()
            status = str(visual.get("status", "")).strip()
            description = str(visual.get("description", "")).strip()
            if not visual_id or visual_id in visual_ids or status not in SOCIAL_VISUAL_STATES or not description:
                raise OperationsError("social visual assets need unique IDs, status, and a concrete description")
            visual_ids.add(visual_id)
            row = {"id": visual_id, "status": status, "description": description}
            path_value = str(visual.get("path", "")).strip()
            if status == "existing":
                if not path_value:
                    raise OperationsError("an existing social visual needs a real artifact path")
                row["evidence"] = evidence_record(Path(path_value))
            elif path_value:
                raise OperationsError("a missing or to-create visual cannot claim an existing path")
            visual_assets.append(row)
        pillars = event.get("content_pillars", [])
        pillars_decision = str(event.get("pillars_decision", "")).strip()
        if not isinstance(pillars, list) or (pillars and not 3 <= len(pillars) <= 5):
            raise OperationsError("social content pillars must be omitted or contain three to five project-specific pillars")
        for pillar in pillars:
            if not isinstance(pillar, dict) or any(
                not str(pillar.get(field, "")).strip() for field in ("name", "why", "post_type")
            ):
                raise OperationsError("each social content pillar needs name, why, and post_type")
        if not pillars and not pillars_decision:
            raise OperationsError("omitted social content pillars need a project-specific reason")
    recommendations = event.get("recommendations", [])
    if not isinstance(recommendations, list) or not recommendations:
        raise OperationsError("social strategy needs at least one recommendation")
    used_reference_ids = set()
    for recommendation in recommendations:
        evidence_class = str(recommendation.get("evidence_class", "")).strip()
        source_ids = recommendation.get("source_reference_ids", [])
        if evidence_class not in SOCIAL_EVIDENCE_CLASSES:
            raise OperationsError("social recommendation has an unsupported evidence class")
        if str(recommendation.get("platform", "")).strip() not in platform_names:
            raise OperationsError("social recommendation needs one of the selected platforms")
        if evidence_class in ("documented", "observed", "researched"):
            if not source_ids or any(references.get(item, {}).get("state") != "inspected" for item in source_ids):
                raise OperationsError("source-backed social recommendation needs inspected sources")
            recommendation["checked_on"] = _checked_date(
                recommendation.get("checked_on"), current=bool(recommendation.get("time_sensitive"))
            )
            if contract_version == 2 and str(recommendation.get("source_quality", "")).strip() not in SOCIAL_SOURCE_QUALITIES:
                raise OperationsError("source-backed social recommendation needs a supported source_quality")
        if evidence_class in ("inferred", "speculative") and source_ids and any(
            references.get(item, {}).get("state") != "inspected" for item in source_ids
        ):
            raise OperationsError("social inference or hypothesis cites an uninspected source")
        if not str(recommendation.get("recommendation", "")).strip() or not str(recommendation.get("reason", "")).strip():
            raise OperationsError("social recommendation needs recommendation and reason")
        if contract_version == 2 and not str(recommendation.get("finding", "")).strip():
            raise OperationsError("social recommendation needs an explicit SOURCE -> FINDING -> DECISION trace")
        copy_problems = _social_copy_problems(
            " ".join(str(recommendation.get(field, "")) for field in ("recommendation", "reason", "finding"))
        )
        if copy_problems:
            raise OperationsError("social recommendation contains " + "; ".join(copy_problems))
        used_reference_ids.update(source_ids)
    concepts = event.get("content_concepts", [])
    if not isinstance(concepts, list) or not 3 <= len(concepts) <= MAX_SOCIAL_POSTS:
        raise OperationsError("social strategy needs three to six project-specific content concepts")
    normalised_concepts = []
    concept_ids = set()
    visual_ids = {item["id"] for item in visual_assets}
    for index, concept in enumerate(concepts, start=1):
        if not isinstance(concept, dict):
            raise OperationsError("each social content concept must be an object")
        required = ("platform", "concept", "format", "hook", "cta")
        if any(not str(concept.get(field, "")).strip() for field in required):
            raise OperationsError("each social content concept needs platform, concept, format, hook, and CTA")
        if str(concept["platform"]).strip() not in platform_names:
            raise OperationsError("social content concept names an unselected platform")
        row = dict(concept)
        row["id"] = str(concept.get("id", "")).strip() or f"{strategy_id}-post-{index}"
        if row["id"] in concept_ids:
            raise OperationsError("social content concept IDs must be unique")
        concept_ids.add(row["id"])
        if contract_version == 2:
            for field in ("purpose", "hypothesis", "draft", "visual_asset_id"):
                if not str(concept.get(field, "")).strip():
                    raise OperationsError(f"social content concept needs {field}")
            if str(concept["visual_asset_id"]).strip() not in visual_ids:
                raise OperationsError("social content concept cites an unknown visual asset")
            concept_evidence_class = str(concept.get("evidence_class", "")).strip()
            if concept_evidence_class not in SOCIAL_EVIDENCE_CLASSES:
                raise OperationsError("social content concept needs a supported evidence class")
            concept_source_ids = concept.get("source_reference_ids", [])
            if not isinstance(concept_source_ids, list) or any(
                references.get(item, {}).get("state") != "inspected" for item in concept_source_ids
            ):
                raise OperationsError("social content concept cites an uninspected source")
            used_reference_ids.update(concept_source_ids)
            copy_problems = _social_copy_problems(
                " ".join(str(concept.get(field, "")) for field in ("hook", "draft", "hypothesis"))
            )
            if copy_problems:
                raise OperationsError("social content concept contains " + "; ".join(copy_problems))
        normalised_concepts.append(row)
    sequence = event.get("sequence", [])
    measurement = event.get("measurement", [])
    timing = str(event.get("timing", "")).strip()
    iteration = str(event.get("iteration", "")).strip()
    if not isinstance(sequence, list) or not sequence or not isinstance(measurement, list) or not measurement:
        raise OperationsError("social strategy needs a content sequence and measurement plan")
    if not timing or not iteration:
        raise OperationsError("social strategy needs timing and iteration guidance")
    example = str(event.get("example_post", "")).strip()
    if not example:
        raise OperationsError("social strategy needs at least one example post")
    copy_problems = _social_copy_problems(example)
    if copy_problems:
        raise OperationsError("example social copy contains " + "; ".join(copy_problems))
    voice_basis = str(event.get("voice_basis", "")).strip()
    draft_status = str(event.get("draft_status", "")).strip()
    if voice_basis != "provided-examples" and draft_status != "rough-draft":
        raise OperationsError("copy without provided voice examples must be marked rough-draft")
    if contract_version == 2 and voice_basis == "provided-examples":
        voice_evidence = _event_evidence(event.get("voice_evidence"), "voice matching", 2)
    artifact = evidence_record(Path(str(event.get("artifact_path", ""))))
    revises = str(event.get("revises", "")).strip()
    if revises and not any(item.get("id") == revises for item in ledger.get("social_strategies", [])):
        raise OperationsError("social strategy revision names an unknown parent strategy")
    source_evidence = []
    for reference_id in sorted(used_reference_ids):
        reference = references.get(reference_id, {})
        if reference.get("state") == "inspected" and isinstance(reference.get("evidence"), dict):
            source_evidence.append({
                "id": reference_id,
                "source": reference.get("source"),
                "evidence": dict(reference["evidence"]),
            })
    ledger.setdefault("social_strategies", []).append({
        "id": strategy_id,
        "contract_version": contract_version,
        "activated_by": activation,
        "audience": audience,
        "platforms": platforms,
        "not_recommended": excluded_platforms,
        "research_depth": research_depth,
        "project_story": project_story if contract_version == 2 else {},
        "project_evidence": project_evidence,
        "visual_assets": visual_assets,
        "content_pillars": pillars,
        "pillars_decision": pillars_decision,
        "source_conflicts": conflicts,
        "source_evidence": source_evidence,
        "recommendations": recommendations,
        "content_concepts": normalised_concepts,
        "timing": timing,
        "sequence": sequence,
        "measurement": measurement,
        "iteration": iteration,
        "example_post": example,
        "voice_basis": voice_basis,
        "voice_evidence": voice_evidence,
        "draft_status": draft_status,
        "artifact": artifact,
        "revises": revises or None,
        "recorded_at": now(),
    })


def record_social_result(ledger: dict, event: dict) -> None:
    result_id = str(event.get("id", "")).strip()
    if not result_id or any(item.get("id") == result_id for item in ledger.get("social_results", [])):
        raise OperationsError("social result needs a new non-empty ID")
    if str(event.get("provided_by", "")).strip() != "user":
        raise OperationsError("social performance data must be explicitly user-provided")
    strategy = _social_strategy(ledger, str(event.get("strategy_id", "")).strip())
    concept = _social_concept(strategy, str(event.get("concept_id", "")).strip())
    platform = str(event.get("platform", "")).strip()
    if platform != str(concept.get("platform", "")).strip():
        raise OperationsError("social result platform does not match its planned post")
    observed_on = _checked_date(event.get("observed_on"), current=False)
    metrics = event.get("metrics", {})
    if not isinstance(metrics, dict):
        raise OperationsError("social result metrics must be an object")
    unknown = sorted(set(metrics) - set(SOCIAL_RESULT_METRICS))
    if unknown:
        raise OperationsError("social result uses unsupported metrics: " + ", ".join(unknown))
    for name, value in metrics.items():
        if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
            raise OperationsError(f"social metric {name} must be a non-negative observed number")
        if name == "retention_percent" and value > 100:
            raise OperationsError("social retention_percent cannot exceed 100")
    qualitative = event.get("qualitative_signals", [])
    if not isinstance(qualitative, list) or any(not str(item).strip() for item in qualitative):
        raise OperationsError("social qualitative_signals must be concrete text entries")
    if not metrics and not qualitative:
        raise OperationsError("social result needs actual performance data or a qualitative signal")
    evidence = evidence_record(Path(str(event.get("evidence_path", ""))))
    revises = str(event.get("revises", "")).strip()
    same_observation = [
        item for item in ledger.get("social_results", [])
        if item.get("strategy_id") == strategy["id"]
        and item.get("concept_id") == concept["id"]
        and item.get("observed_on") == observed_on
    ]
    if same_observation and not revises:
        raise OperationsError("contradictory or replacement social data must revise the prior result")
    if revises:
        parent = by_id(ledger.get("social_results", []), revises, "social results")
        if parent.get("strategy_id") != strategy["id"] or parent.get("concept_id") != concept["id"]:
            raise OperationsError("social result correction must revise the same planned post")
        if not str(event.get("correction_reason", "")).strip():
            raise OperationsError("social result correction needs a reason")
    ledger.setdefault("social_results", []).append({
        "id": result_id,
        "strategy_id": strategy["id"],
        "concept_id": concept["id"],
        "platform": platform,
        "observed_on": observed_on,
        "provided_by": "user",
        "metrics": metrics,
        "qualitative_signals": qualitative,
        "evidence": evidence,
        "revises": revises or None,
        "correction_reason": str(event.get("correction_reason", "")).strip() or None,
        "recorded_at": now(),
    })


def record_social_learning(ledger: dict, event: dict) -> None:
    learning_id = str(event.get("id", "")).strip()
    if not learning_id or any(item.get("id") == learning_id for item in ledger.get("social_learnings", [])):
        raise OperationsError("social learning needs a new non-empty ID")
    strategy = _social_strategy(ledger, str(event.get("strategy_id", "")).strip())
    result_ids = event.get("result_ids", [])
    if not isinstance(result_ids, list) or not result_ids or len(result_ids) != len(set(result_ids)):
        raise OperationsError("social learning needs distinct result IDs")
    results = [by_id(ledger.get("social_results", []), item, "social results") for item in result_ids]
    if any(item.get("strategy_id") != strategy["id"] for item in results):
        raise OperationsError("social learning cannot combine results from different strategies")
    outcome = str(event.get("outcome", "")).strip()
    confidence = str(event.get("confidence", "")).strip()
    if outcome not in SOCIAL_LEARNING_OUTCOMES or confidence not in SOCIAL_LEARNING_CONFIDENCE:
        raise OperationsError("social learning needs a supported outcome and confidence")
    if len(results) < 2 and outcome != "inconclusive":
        raise OperationsError("one social result cannot support or contradict a hypothesis")
    interpretation = str(event.get("interpretation", "")).strip()
    if not interpretation:
        raise OperationsError("social learning needs a bounded interpretation")
    next_test = event.get("next_test", {})
    if not isinstance(next_test, dict) or any(
        not str(next_test.get(field, "")).strip() for field in ("hypothesis", "variable", "measure")
    ):
        raise OperationsError("social learning needs one falsifiable next test and one changing variable")
    promoted_rule = str(event.get("promoted_rule", "")).strip()
    if promoted_rule and len(results) < 3:
        raise OperationsError("a social rule needs at least three recorded results")
    artifact = evidence_record(Path(str(event.get("artifact_path", ""))))
    revises = str(event.get("revises", "")).strip()
    if revises and not any(item.get("id") == revises for item in ledger.get("social_learnings", [])):
        raise OperationsError("social learning revision names an unknown parent")
    plans = []
    for result in results:
        concept = _social_concept(strategy, result["concept_id"])
        plans.append({
            "concept_id": concept["id"],
            "hypothesis": str(concept.get("hypothesis", "")).strip() or "legacy strategy: hypothesis not recorded",
        })
    ledger.setdefault("social_learnings", []).append({
        "id": learning_id,
        "strategy_id": strategy["id"],
        "result_ids": result_ids,
        "plans": plans,
        "outcome": outcome,
        "confidence": confidence,
        "interpretation": interpretation,
        "next_test": next_test,
        "promoted_rule": promoted_rule or None,
        "artifact": artifact,
        "revises": revises or None,
        "recorded_at": now(),
    })


def apply_event(project: Path, ledger: dict, event: dict) -> None:
    event_type = str(event.get("type", "")).strip()
    if event_type == "implementation":
        record_implementation(ledger, event)
    elif event_type == "visual-evidence":
        record_visual_evidence(ledger, event)
    elif event_type == "drift":
        record_drift(ledger, event)
    elif event_type == "creative-review":
        record_creative_review(ledger, event)
    elif event_type == "social-strategy":
        record_social_strategy(project, ledger, event)
    elif event_type == "social-result":
        record_social_result(ledger, event)
    elif event_type == "social-learning":
        record_social_learning(ledger, event)
    else:
        raise OperationsError(f"unsupported creative operations event: {event_type}")


def apply_events(project: Path, ledger: dict, value: dict | list) -> None:
    events = value.get("events", []) if isinstance(value, dict) and "events" in value else value
    if isinstance(events, dict):
        events = [events]
    if not isinstance(events, list) or not events:
        raise OperationsError("creative operations input needs an event or non-empty events list")
    for event in events:
        if not isinstance(event, dict):
            raise OperationsError("creative operations event must be an object")
        apply_event(project, ledger, event)


def artifact_problems(record: dict, label: str) -> list[str]:
    path = Path(str(record.get("path", "")))
    if not path.is_file():
        return [f"{label} artifact is missing: {path}"]
    if digest(path) != record.get("sha256"):
        return [f"{label} artifact changed after evidence was recorded: {path}"]
    anchor = record.get("anchor")
    if anchor and anchor not in path.read_text(encoding="utf-8", errors="ignore"):
        return [f"{label} anchor is no longer present: {anchor}"]
    return []


def ledger_problems(project: Path, ledger: dict) -> list[str]:
    problems = []
    if ledger.get("schema_version") != SCHEMA_VERSION:
        problems.append("unsupported creative operations schema")
    if Path(str(ledger.get("project", ""))).resolve() != project.resolve():
        problems.append("creative operations project path does not match")
    requirement_ids = [item.get("id") for item in ledger.get("requirements", [])]
    if not requirement_ids or len(requirement_ids) != len(set(requirement_ids)):
        problems.append("creative operations requirements are missing or duplicate")
    for item in ledger.get("requirements", []):
        problems.extend(artifact_problems(item.get("design_source", {}), f"requirement {item.get('id')}") )
    target_ids = {
        requirement_id
        for target in ledger.get("visual_qa_plan", {}).get("targets", [])
        for requirement_id in target.get("requirement_ids", [])
    }
    missing_targets = set(requirement_ids) - target_ids
    if missing_targets:
        problems.append("visual QA plan omits requirements: " + ", ".join(sorted(missing_targets)))
    targets = ledger.get("visual_qa_plan", {}).get("targets", [])
    if targets and targets[0].get("priority") != 1:
        problems.append("visual QA plan does not start with thesis-critical work")
    for item in ledger.get("implementations", []):
        if item.get("source"):
            problems.extend(artifact_problems(item["source"], f"implementation {item.get('requirement_id')}") )
    for item in ledger.get("visual_evidence", []):
        if item.get("evidence"):
            problems.extend(artifact_problems(item["evidence"], f"visual evidence {item.get('id')}") )
    for item in ledger.get("social_strategies", []):
        problems.extend(artifact_problems(item.get("artifact", {}), f"social strategy {item.get('id')}") )
    if ledger.get("social_strategies"):
        latest_strategy = ledger["social_strategies"][-1]
        for index, item in enumerate(latest_strategy.get("project_evidence", []), start=1):
            problems.extend(artifact_problems(item, f"social project evidence {index}"))
        for item in latest_strategy.get("visual_assets", []):
            if item.get("evidence"):
                problems.extend(artifact_problems(item["evidence"], f"social visual {item.get('id')}"))
        for index, item in enumerate(latest_strategy.get("voice_evidence", []), start=1):
            problems.extend(artifact_problems(item, f"social voice evidence {index}"))
        for item in latest_strategy.get("source_evidence", []):
            problems.extend(artifact_problems(item.get("evidence", {}), f"social source {item.get('id')}"))
    for item in ledger.get("social_results", []):
        problems.extend(artifact_problems(item.get("evidence", {}), f"social result {item.get('id')}"))
    if ledger.get("social_learnings"):
        latest_learning = ledger["social_learnings"][-1]
        problems.extend(artifact_problems(
            latest_learning.get("artifact", {}), f"social learning {latest_learning.get('id')}"
        ))
    return list(dict.fromkeys(problems))


def project_problems(project: Path, require: str = "plan") -> list[str]:
    if require not in ("plan", "implementation", "visual", "review", "social", "social-learning"):
        return [f"unsupported creative operations requirement: {require}"]
    ledger = load_ledger(project)
    if ledger is None:
        return ["post-G1 creative operations are not recorded"]
    problems = ledger_problems(project, ledger)
    if require == "social":
        if not ledger.get("social_strategies"):
            problems.append("no explicitly requested social strategy is recorded")
        return list(dict.fromkeys(problems))
    if require == "social-learning":
        if not ledger.get("social_strategies"):
            problems.append("no explicitly requested social strategy is recorded")
        if not ledger.get("social_results"):
            problems.append("no user-provided social performance result is recorded")
        if not ledger.get("social_learnings"):
            problems.append("no social PLAN -> RESULT -> INTERPRETATION -> NEXT TEST record exists")
        return list(dict.fromkeys(problems))
    levels = {"plan": 0, "implementation": 1, "visual": 2, "review": 3}
    required_level = levels[require]
    requirement_ids = {item.get("id") for item in ledger.get("requirements", [])}
    if required_level >= 1:
        implementations = ledger.get("implementations", [])
        mapped = {item.get("requirement_id") for item in implementations}
        for requirement_id in sorted(requirement_ids - mapped):
            problems.append(f"implementation mapping is missing: {requirement_id}")
        for item in implementations:
            if item.get("requirement_id") in requirement_ids and item.get("status") != "implemented":
                problems.append(
                    f"implementation is not complete: {item.get('requirement_id')} ({item.get('status', 'unknown')})"
                )
    if required_level >= 2:
        evidence = ledger.get("visual_evidence", [])
        for target in ledger.get("visual_qa_plan", {}).get("targets", []):
            for requirement_id in target.get("requirement_ids", []):
                rows = [item for item in evidence if item.get("requirement_id") == requirement_id]
                for viewport in target.get("viewports", []):
                    at_viewport = [item for item in rows if item.get("viewport") == viewport]
                    if not at_viewport:
                        problems.append(
                            f"visual evidence is missing: {requirement_id} at {viewport}px"
                        )
                    elif not any(
                        item.get("level") in ("rendered", "observed", "verified")
                        for item in at_viewport
                    ):
                        problems.append(
                            f"visual result is not observed: {requirement_id} at {viewport}px"
                        )
        drift_by_requirement = {}
        for item in ledger.get("drift_findings", []):
            drift_by_requirement[item.get("requirement_id")] = item
        for requirement_id in sorted(requirement_ids):
            finding = drift_by_requirement.get(requirement_id)
            if finding is None:
                problems.append(f"drift classification is missing: {requirement_id}")
            elif finding.get("state") in ("drift", "unknown"):
                problems.append(
                    f"unresolved design drift: {requirement_id} ({finding.get('state')})"
                )
    if required_level >= 3:
        reviews = ledger.get("creative_reviews", [])
        if not reviews:
            problems.append("no evidence-backed creative review is recorded")
        else:
            latest = reviews[-1]
            if latest.get("iteration") == "yes":
                if len(reviews) >= MAX_AUTOMATIC_CREATIVE_ITERATIONS:
                    problems.append(
                        "creative iteration budget is exhausted; a human must decide whether to continue"
                    )
                else:
                    problems.append("creative review requires one focused implementation iteration")
            elif latest.get("iteration") == "conditional":
                problems.append("creative review needs a human creative decision")
    return list(dict.fromkeys(problems))


def summary(ledger: dict | None) -> dict:
    if ledger is None:
        return {"status": "not-tracked", "requirements": 0, "implemented": 0, "observed": 0, "drift": 0, "creative_reviews": 0, "social_strategies": 0, "social_results": 0, "social_learnings": 0}
    return {
        "status": "tracked",
        "requirements": len(ledger.get("requirements", [])),
        "implemented": sum(item.get("status") == "implemented" for item in ledger.get("implementations", [])),
        "observed": sum(item.get("level") in ("observed", "verified") for item in ledger.get("visual_evidence", [])),
        "drift": sum(item.get("state") == "drift" for item in ledger.get("drift_findings", [])),
        "creative_reviews": len(ledger.get("creative_reviews", [])),
        "social_strategies": len(ledger.get("social_strategies", [])),
        "social_results": len(ledger.get("social_results", [])),
        "social_learnings": len(ledger.get("social_learnings", [])),
    }


def repository_contract_problems(texts: dict[str, str] | None = None) -> list[str]:
    paths = {
        "visual": ROOT / "skills" / "visual-qa.md",
        "review": ROOT / "skills" / "creative-review.md",
        "social": ROOT / "skills" / "social-strategy.md",
        "social_template": ROOT / "templates" / "SOCIAL-STRATEGY.md",
        "runtime_reference": ROOT / ".agents" / "skills" / "builderos" / "references" / "creative-operations.md",
    }
    problems = []
    values = dict(texts or {})
    for name, path in paths.items():
        if name not in values:
            if not path.is_file():
                problems.append(f"creative operations contract source missing: {path.relative_to(ROOT)}")
                continue
            values[name] = path.read_text(encoding="utf-8")
    required_tokens = {
        "visual": ["project-specific", "code-suggests", "unverified", "operations-check", "does not replace"],
        "review": [
            "rendered or observed", "highest-value improvement", "cannot approve",
            "`DESIGN.md`", "parent_review_id", "two reviews",
        ],
        "social": [
            "explicitly asks", "one to three platforms", "researched", "rough-draft",
            "PLAN -> RESULT -> INTERPRETATION -> NEXT TEST", "never publishes",
        ],
        "social_template": [
            "## Project story", "## Platform decisions", "## Source to decision",
            "## Visual inventory", "## What I'd post", "## What I'd test",
        ],
        "runtime_reference": [
            "operations-plan", "record-operations", "operations-check",
            "social-result", "social-learning", "No event grants G1-G5",
        ],
    }
    for name, tokens in required_tokens.items():
        value = values.get(name, "")
        for token in tokens:
            if token not in value:
                problems.append(f"{name} creative operations contract missing: {token}")
    return problems


@contextlib.contextmanager
def self_test_workspace():
    path = ROOT / "validation" / f"creative-operations-self-test-{uuid.uuid4().hex}"
    path.mkdir()
    try:
        yield path
    finally:
        if path.exists():
            shutil.rmtree(path)


def fixture_project(root: Path) -> Path:
    project = root / "project"
    project.mkdir(parents=True)
    (project / "PROJECT.md").write_text("# PROJECT\n\n## Goal\n\nMake the archive legible.\n", encoding="utf-8")
    (project / "DESIGN.md").write_text(
        "# DESIGN\n\n**Status:** locked at G1 on 2026-08-23\n\n"
        "## Design thesis\n\n**A red thread makes every archive fragment part of one remembered route.**\n\n"
        "## Signature moment\n\n- **What / where:** A red thread crosses the archive boundary.\n"
        "- **Why memorable:** The connection becomes physical.\n"
        "- **Mobile equivalent:** The thread becomes a vertical reading rail.\n\n"
        "## Interaction principles\n\nSelecting a fragment tightens the thread and exposes its source.\n\n"
        "## Responsive behaviour\n\n| Width | Composition |\n|---|---|\n"
        "| 375 | The thread becomes a vertical reading rail. |\n"
        "| 1280 | The title crosses into the archive index. |\n",
        encoding="utf-8",
    )
    (project / "HANDOFF.md").write_text(
        "# HANDOFF\n\n## Decisions that are fixed\n\n| Decision | Value |\n|---|---|\n"
        "| Typography | editorial serif, 8x scale |\n| Palette | warm paper, red thread |\n"
        "| Grid | eight columns with one boundary break |\n| Motion | continuity, 360ms |\n",
        encoding="utf-8",
    )
    (project / "AGENTS.md").write_text(
        "# AGENTS\n\n| **Last gate passed** | G1 |\n", encoding="utf-8"
    )
    return project


def self_test() -> int:
    cases = []

    def case(name: str, passed: bool) -> None:
        cases.append((name, bool(passed)))

    with self_test_workspace() as workspace:
        case("creative operations method contracts pass (positive control)", not repository_contract_problems())
        social_contract = (ROOT / "skills" / "social-strategy.md").read_text(encoding="utf-8")
        case(
            "social skill cannot lose explicit activation",
            bool(repository_contract_problems({"social": social_contract.replace("explicitly asks", "might benefit", 1)})),
        )
        visual_contract = (ROOT / "skills" / "visual-qa.md").read_text(encoding="utf-8")
        case(
            "visual QA skill cannot collapse rendered evidence into source inference",
            bool(repository_contract_problems({"visual": visual_contract.replace("code-suggests", "source-reviewed", 1)})),
        )
        project = fixture_project(workspace)
        ledger = create_ledger(project)
        ids = {item["id"] for item in ledger["requirements"]}
        case("approved documents derive thesis and signature requirements", {"design-thesis", "signature-moment"} <= ids)
        case("visual QA plan starts with thesis-critical work", ledger["visual_qa_plan"]["targets"][0]["priority"] == 1)
        case("visual QA plan carries narrow and desktop signature checks", by_id(ledger["requirements"], "signature-moment", "requirements")["viewports"] == [375, 1280])
        case("fresh trace passes (positive control)", not ledger_problems(project, ledger))
        save_ledger(project, ledger)
        case("plan readiness does not imply rendered readiness", not project_problems(project, "plan") and bool(project_problems(project, "visual")))
        record_visual_evidence(ledger, {
            "id": "visual-thesis-unverified", "requirement_id": "design-thesis",
            "level": "unverified", "kind": "screenshot", "viewport": 375,
            "observation": "The fixture could not render the narrow thesis state.",
            "blocker": "The visual environment was unavailable for this negative control.",
        })
        save_ledger(project, ledger)
        case(
            "unverified evidence cannot satisfy an observed visual target",
            "visual result is not observed: design-thesis at 375px"
            in project_problems(project, "visual"),
        )

        unlocked = fixture_project(workspace / "unlocked")
        (unlocked / "DESIGN.md").write_text((unlocked / "DESIGN.md").read_text(encoding="utf-8").replace("locked at G1", "draft"), encoding="utf-8")
        try:
            create_ledger(unlocked)
            unlocked_blocked = False
        except OperationsError:
            unlocked_blocked = True
        case("trace cannot promote an unapproved direction", unlocked_blocked)

        source = project / "app.tsx"
        source.write_text("export const signature = 'red thread';\n", encoding="utf-8")
        partial_source = project / "partial.html"
        partial_source.write_text("<main>Archive thesis placeholder.</main>\n", encoding="utf-8")
        record_implementation(ledger, {
            "requirement_id": "design-thesis", "status": "partial",
            "summary": "The archive is visible, but the approved connection is not complete.",
            "source_path": str(partial_source), "source_anchor": "Archive thesis",
        })
        save_ledger(project, ledger)
        case(
            "partial implementation cannot satisfy implementation readiness",
            "implementation is not complete: design-thesis (partial)"
            in project_problems(project, "implementation"),
        )
        record_implementation(ledger, {
            "requirement_id": "signature-moment", "status": "implemented",
            "summary": "The thread crosses the archive boundary.",
            "source_path": str(source), "source_anchor": "red thread",
        })
        case(
            "implementation maps to an approved requirement",
            summary(ledger)["implemented"] == 1,
        )

        screenshot = project / "signature-375.txt"
        screenshot.write_text("Rendered 375px capture: vertical red reading rail.\n", encoding="utf-8")
        record_visual_evidence(ledger, {
            "id": "visual-signature-rendered", "requirement_id": "signature-moment",
            "level": "rendered", "kind": "screenshot", "viewport": 375,
            "observation": "The narrow composition contains the vertical reading rail.",
            "evidence_path": str(screenshot),
        })
        browser = project / "interaction.txt"
        browser.write_text("Browser interaction: selecting a fragment tightened the thread.\n", encoding="utf-8")
        record_visual_evidence(ledger, {
            "id": "visual-signature-observed", "requirement_id": "signature-moment",
            "level": "observed", "kind": "interaction", "viewport": 375,
            "observation": "Selection tightened the thread without losing the reading rail.",
            "evidence_path": str(browser),
        })
        verification = project / "measurement.txt"
        verification.write_text("Measured rail boundary at 375px.\n", encoding="utf-8")
        record_visual_evidence(ledger, {
            "id": "visual-signature-verified", "requirement_id": "signature-moment",
            "level": "verified", "kind": "measurement", "viewport": 375,
            "observation": "The rail remains inside the intended boundary.",
            "evidence_path": str(verification), "prior_evidence_ids": ["visual-signature-observed"],
            "verification": "Measured the rendered boundary after exercising the state.",
        })
        case("verified evidence requires and accepts an observed positive control", summary(ledger)["observed"] == 2)
        try:
            record_visual_evidence(ledger, {
                "id": "visual-fake-verified", "requirement_id": "design-thesis",
                "level": "verified", "kind": "measurement", "observation": "Claim only.",
                "evidence_path": str(verification), "verification": "Claimed.",
            })
            fake_verified_blocked = False
        except OperationsError:
            fake_verified_blocked = True
        case("verified evidence cannot skip rendered or observed evidence", fake_verified_blocked)

        record_drift(ledger, {
            "id": "drift-signature", "requirement_id": "signature-moment", "state": "approved",
            "evidence_ids": ["visual-signature-observed"], "what_changed": "Nothing material.",
            "why_it_matters": "The signature remains recognisable.", "recommendation": "Preserve it.",
        })
        case("drift classification cites observed evidence", len(ledger["drift_findings"]) == 1)
        save_ledger(project, ledger)
        case(
            "missing drift classification remains explicit",
            "drift classification is missing: design-thesis"
            in project_problems(project, "visual"),
        )

        dimensions = {
            name: {"judgement": f"Fixture judgement for {name}.", "evidence_ids": ["visual-signature-observed"]}
            for name in REVIEW_DIMENSIONS
        }
        record_creative_review(ledger, {
            "id": "review-1", "evidence_ids": ["visual-signature-observed"],
            "strongest": "The thread remains memorable.", "weakest": "The desktop title is not yet evidenced.",
            "biggest_risk": "The device could become decoration.",
            "highest_value_improvement": "Inspect the desktop boundary before changing surface polish.",
            "iteration": "conditional", "do_not_change": "Typography and palette.", "dimensions": dimensions,
        })
        save_ledger(project, ledger)
        case("creative review produces one actionable priority", ledger["creative_reviews"][0]["highest_value_improvement"].startswith("Inspect"))
        case(
            "conditional creative review remains a human decision",
            "creative review needs a human creative decision" in project_problems(project, "review"),
        )
        try:
            record_creative_review(ledger, {
                "id": "review-unlinked", "evidence_ids": ["visual-signature-observed"],
                "strongest": "The thread remains memorable.", "weakest": "The tablet state remains weak.",
                "biggest_risk": "The correction could broaden.",
                "highest_value_improvement": "Correct only the tablet boundary.",
                "iteration": "yes", "do_not_change": "Typography and palette.", "dimensions": dimensions,
            })
            unlinked_review_allowed = True
        except OperationsError:
            unlinked_review_allowed = False
        case("follow-up creative review cannot lose its parent", not unlinked_review_allowed)
        record_creative_review(ledger, {
            "id": "review-2", "parent_review_id": "review-1",
            "evidence_ids": ["visual-signature-observed"],
            "strongest": "The thread remains memorable.", "weakest": "The tablet state remains weak.",
            "biggest_risk": "Another correction could become an open loop.",
            "highest_value_improvement": "Correct only the tablet boundary.",
            "iteration": "yes", "do_not_change": "Typography and palette.", "dimensions": dimensions,
        })
        save_ledger(project, ledger)
        case(
            "creative iteration budget has a fixed stop",
            "creative iteration budget is exhausted; a human must decide whether to continue"
            in project_problems(project, "review"),
        )
        record_creative_review(ledger, {
            "id": "review-3", "parent_review_id": "review-2",
            "evidence_ids": ["visual-signature-observed"],
            "strongest": "The thread remains memorable.", "weakest": "No material weakness remains in the observed state.",
            "biggest_risk": "Unobserved widths remain an evidence gap.",
            "highest_value_improvement": "Preserve the corrected tablet boundary.",
            "iteration": "no", "do_not_change": "Typography and palette.", "dimensions": dimensions,
        })
        save_ledger(project, ledger)
        case(
            "latest linked review can close the internal iteration loop",
            not any("creative review" in problem or "iteration budget" in problem for problem in project_problems(project, "review")),
        )
        case("partial evidence cannot claim the full visual plan", bool(project_problems(project, "visual")))
        try:
            empty_review = create_ledger(project)
            record_creative_review(empty_review, {
                "id": "review-no-render", "evidence_ids": [], "strongest": "x", "weakest": "x",
                "biggest_risk": "x", "highest_value_improvement": "x", "iteration": "no",
                "dimensions": dimensions,
            })
            assertion_review_blocked = False
        except OperationsError:
            assertion_review_blocked = True
        case("creative review cannot prove itself without rendered evidence", assertion_review_blocked)

        social_artifact = project / "SOCIAL-STRATEGY.md"
        social_artifact.write_text("# Social strategy\n\nShow the archive thread before explaining the project.\n", encoding="utf-8")
        creative_dir = project / ".builderos"
        creative_dir.mkdir(exist_ok=True)
        source_capture = project / "platform-source.html"
        source_capture.write_text("Official platform format guidance.\n", encoding="utf-8")
        write_json(creative_dir / "creative-evidence.json", {
            "references": [{"id": "social-source", "state": "inspected", "source": "https://platform.example.test", "evidence": evidence_record(source_capture)}]
        })
        social_event = {
            "id": "social-1", "activated_by": "Create a social strategy for this project.",
            "audience": "People interested in public-memory archives.",
            "platforms": [{"name": "LinkedIn", "why": "The project has a concrete process story."}],
            "recommendations": [{"recommendation": "Lead with the visible thread mechanism.",
                "reason": "It gives the audience a project-specific hook.", "platform": "LinkedIn",
                "checked_on": "2026-08-23", "evidence_class": "documented",
                "source_reference_ids": ["social-source"]}],
            "content_concepts": [
                {"platform": "LinkedIn", "concept": "Reveal the red thread", "format": "image carousel", "hook": "The archive was not a grid problem.", "cta": "Ask what makes an archive feel connected."},
                {"platform": "LinkedIn", "concept": "Show the failed index", "format": "process post", "hook": "The first index was legible and forgettable.", "cta": "None — end on the design lesson."},
                {"platform": "LinkedIn", "concept": "Explain the evidence chain", "format": "annotated still", "hook": "Every fragment needed a visible reason to belong.", "cta": "Invite archive designers to compare approaches."},
            ],
            "timing": "Test one post per week; no universal best-time claim is available.",
            "sequence": ["visual teaser", "process note"], "measurement": ["saves", "qualified replies"],
            "iteration": "Compare saves and qualified replies after three posts; change one variable at a time.",
            "example_post": "The archive only became legible when one red thread stopped being decoration and started carrying provenance.",
            "voice_basis": "project-context", "draft_status": "rough-draft", "artifact_path": str(social_artifact),
        }
        record_social_strategy(project, ledger, social_event)
        case("optional social strategy uses inspected current evidence", summary(ledger)["social_strategies"] == 1)

        revised_artifact = project / "SOCIAL-STRATEGY-REVISION.md"
        revised_artifact.write_text(
            "# Social strategy revision\n\nLead with the failed index before revealing the red thread.\n",
            encoding="utf-8",
        )
        revised_event = json.loads(json.dumps(social_event))
        revised_event.update({
            "id": "social-2",
            "revises": "social-1",
            "artifact_path": str(revised_artifact),
            "example_post": "The first archive index was legible and forgettable. The red thread changed what each fragment meant.",
        })
        record_social_strategy(project, ledger, revised_event)
        case(
            "social strategy revision retains its explicit parent (positive control)",
            summary(ledger)["social_strategies"] == 2
            and ledger["social_strategies"][-1]["revises"] == "social-1",
        )
        unknown_parent_event = json.loads(json.dumps(social_event))
        unknown_parent_event.update({
            "id": "social-bad-parent",
            "revises": "social-missing",
            "artifact_path": str(revised_artifact),
        })
        try:
            record_social_strategy(project, ledger, unknown_parent_event)
            unknown_parent_blocked = False
        except OperationsError:
            unknown_parent_blocked = True
        case("social strategy revision cannot name an unknown parent", unknown_parent_blocked)
        try:
            record_social_strategy(project, ledger, {
                "id": "social-generic", "activated_by": "Promote this.", "audience": "designers",
                "platforms": [{"name": "X", "why": "A visual process audience exists."}],
                "recommendations": [{"platform": "X", "recommendation": "Post it.", "reason": "Test.", "evidence_class": "speculative", "source_reference_ids": []}],
                "content_concepts": [
                    {"platform": "X", "concept": str(index), "format": "still", "hook": "hook", "cta": "none"}
                    for index in range(3)
                ],
                "timing": "Test.", "sequence": ["one"], "measurement": ["replies"],
                "iteration": "Review after the test.",
                "example_post": "I'm excited to share this journey.", "voice_basis": "project-context",
                "draft_status": "rough-draft", "artifact_path": str(social_artifact),
            })
            generic_copy_blocked = False
        except OperationsError:
            generic_copy_blocked = True
        case("generic AI social opener is rejected", generic_copy_blocked)

        try:
            record_social_strategy(project, ledger, {
                "id": "social-thin", "activated_by": "Create a social strategy.",
                "audience": "archive designers", "platforms": [{"name": "LinkedIn", "why": "process fit"}],
                "recommendations": [{"platform": "LinkedIn", "recommendation": "Show the thread.",
                    "reason": "It is specific.", "evidence_class": "inferred", "source_reference_ids": []}],
                "content_concepts": [], "timing": "Test weekly.", "sequence": ["launch"],
                "measurement": ["saves"], "iteration": "Review after three posts.",
                "example_post": "The red thread carries provenance.", "voice_basis": "project-context",
                "draft_status": "rough-draft", "artifact_path": str(social_artifact),
            })
            thin_strategy_blocked = False
        except OperationsError:
            thin_strategy_blocked = True
        case("social strategy cannot omit project-specific content concepts", thin_strategy_blocked)

        saved = json.loads(json.dumps(ledger))
        source.write_text("changed after mapping\n", encoding="utf-8")
        case("changed implementation evidence becomes stale", any("changed" in item for item in ledger_problems(project, saved)))

    print("CREATIVE OPERATIONS SELF-TEST\n")
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
