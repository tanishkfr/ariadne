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
SOCIAL_EVIDENCE_CLASSES = ("documented", "observed", "inferred", "speculative")
GENERIC_SOCIAL_OPENERS = (
    "i'm excited to share", "i’m excited to share", "here's a deep dive",
    "here’s a deep dive", "this journey taught me", "i'm thrilled to announce",
    "i’m thrilled to announce", "game changer", "this changes everything",
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
    required = ("strongest", "weakest", "biggest_risk", "highest_value_improvement")
    row = {key: str(event.get(key, "")).strip() for key in required}
    if not all(row.values()):
        raise OperationsError("creative review needs strongest, weakest, risk, and highest-value improvement")
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
        "do_not_change": str(event.get("do_not_change", "")).strip(),
        "recorded_at": now(),
    })
    ledger.setdefault("creative_reviews", []).append(row)


def _creative_references(project: Path) -> dict[str, dict]:
    path = project / ".builderos" / "creative-evidence.json"
    if not path.is_file():
        return {}
    value = read_json(path)
    return {item.get("id"): item for item in value.get("references", []) if item.get("id")}


def record_social_strategy(project: Path, ledger: dict, event: dict) -> None:
    strategy_id = str(event.get("id", "")).strip()
    if not strategy_id or any(item.get("id") == strategy_id for item in ledger.get("social_strategies", [])):
        raise OperationsError("social strategy needs a new non-empty ID")
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
    recommendations = event.get("recommendations", [])
    if not isinstance(recommendations, list) or not recommendations:
        raise OperationsError("social strategy needs at least one recommendation")
    for recommendation in recommendations:
        evidence_class = str(recommendation.get("evidence_class", "")).strip()
        source_ids = recommendation.get("source_reference_ids", [])
        if evidence_class not in SOCIAL_EVIDENCE_CLASSES:
            raise OperationsError("social recommendation has an unsupported evidence class")
        if str(recommendation.get("platform", "")).strip() not in platform_names:
            raise OperationsError("social recommendation needs one of the selected platforms")
        if evidence_class in ("documented", "observed"):
            if not source_ids or any(references.get(item, {}).get("state") != "inspected" for item in source_ids):
                raise OperationsError("documented or observed social recommendation needs inspected sources")
            if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(recommendation.get("checked_on", ""))):
                raise OperationsError("documented or observed social recommendation needs a checked_on date")
        if evidence_class == "inferred" and source_ids and any(
            references.get(item, {}).get("state") != "inspected" for item in source_ids
        ):
            raise OperationsError("inferred social recommendation cites an uninspected source")
        if not str(recommendation.get("recommendation", "")).strip() or not str(recommendation.get("reason", "")).strip():
            raise OperationsError("social recommendation needs recommendation and reason")
    concepts = event.get("content_concepts", [])
    if not isinstance(concepts, list) or len(concepts) < 3:
        raise OperationsError("social strategy needs at least three project-specific content concepts")
    for concept in concepts:
        if not isinstance(concept, dict):
            raise OperationsError("each social content concept must be an object")
        required = ("platform", "concept", "format", "hook", "cta")
        if any(not str(concept.get(field, "")).strip() for field in required):
            raise OperationsError("each social content concept needs platform, concept, format, hook, and CTA")
        if str(concept["platform"]).strip() not in platform_names:
            raise OperationsError("social content concept names an unselected platform")
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
    lowered = example.lower()
    found = [phrase for phrase in GENERIC_SOCIAL_OPENERS if phrase in lowered]
    if found:
        raise OperationsError("example social copy contains generic AI phrasing: " + ", ".join(found))
    voice_basis = str(event.get("voice_basis", "")).strip()
    draft_status = str(event.get("draft_status", "")).strip()
    if voice_basis != "provided-examples" and draft_status != "rough-draft":
        raise OperationsError("copy without provided voice examples must be marked rough-draft")
    artifact = evidence_record(Path(str(event.get("artifact_path", ""))))
    revises = str(event.get("revises", "")).strip()
    if revises and not any(item.get("id") == revises for item in ledger.get("social_strategies", [])):
        raise OperationsError("social strategy revision names an unknown parent strategy")
    ledger.setdefault("social_strategies", []).append({
        "id": strategy_id,
        "activated_by": activation,
        "audience": audience,
        "platforms": platforms,
        "recommendations": recommendations,
        "content_concepts": concepts,
        "timing": timing,
        "sequence": sequence,
        "measurement": measurement,
        "iteration": iteration,
        "example_post": example,
        "voice_basis": voice_basis,
        "draft_status": draft_status,
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
    return list(dict.fromkeys(problems))


def project_problems(project: Path, require: str = "plan") -> list[str]:
    if require not in ("plan", "implementation", "visual", "review", "social"):
        return [f"unsupported creative operations requirement: {require}"]
    ledger = load_ledger(project)
    if ledger is None:
        return ["post-G1 creative operations are not recorded"]
    problems = ledger_problems(project, ledger)
    if require == "social":
        if not ledger.get("social_strategies"):
            problems.append("no explicitly requested social strategy is recorded")
        return list(dict.fromkeys(problems))
    levels = {"plan": 0, "implementation": 1, "visual": 2, "review": 3}
    required_level = levels[require]
    requirement_ids = {item.get("id") for item in ledger.get("requirements", [])}
    if required_level >= 1:
        mapped = {item.get("requirement_id") for item in ledger.get("implementations", [])}
        for requirement_id in sorted(requirement_ids - mapped):
            problems.append(f"implementation mapping is missing: {requirement_id}")
    if required_level >= 2:
        evidence = ledger.get("visual_evidence", [])
        for target in ledger.get("visual_qa_plan", {}).get("targets", []):
            for requirement_id in target.get("requirement_ids", []):
                rows = [item for item in evidence if item.get("requirement_id") == requirement_id]
                for viewport in target.get("viewports", []):
                    if not any(item.get("viewport") == viewport for item in rows):
                        problems.append(
                            f"visual evidence is missing: {requirement_id} at {viewport}px"
                        )
    if required_level >= 3 and not ledger.get("creative_reviews"):
        problems.append("no evidence-backed creative review is recorded")
    return list(dict.fromkeys(problems))


def summary(ledger: dict | None) -> dict:
    if ledger is None:
        return {"status": "not-tracked", "requirements": 0, "implemented": 0, "observed": 0, "drift": 0, "creative_reviews": 0, "social_strategies": 0}
    return {
        "status": "tracked",
        "requirements": len(ledger.get("requirements", [])),
        "implemented": sum(item.get("status") == "implemented" for item in ledger.get("implementations", [])),
        "observed": sum(item.get("level") in ("observed", "verified") for item in ledger.get("visual_evidence", [])),
        "drift": sum(item.get("state") == "drift" for item in ledger.get("drift_findings", [])),
        "creative_reviews": len(ledger.get("creative_reviews", [])),
        "social_strategies": len(ledger.get("social_strategies", [])),
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
        "review": ["rendered or observed", "highest-value improvement", "cannot approve", "`DESIGN.md`"],
        "social": ["explicitly asks", "one to three platforms", "documented", "rough-draft", "does not publish"],
        "social_template": ["## Platforms", "## Content concepts", "## Timing and sequence", "## Measurement and iteration", "## Evidence register"],
        "runtime_reference": ["operations-plan", "record-operations", "operations-check", "social-strategy", "No event grants G1-G5"],
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
        record_implementation(ledger, {
            "requirement_id": "signature-moment", "status": "implemented",
            "summary": "The thread crosses the archive boundary.",
            "source_path": str(source), "source_anchor": "red thread",
        })
        case("implementation maps to an approved requirement", len(ledger["implementations"]) == 1)

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
        case("creative review produces one actionable priority", ledger["creative_reviews"][0]["highest_value_improvement"].startswith("Inspect"))
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
